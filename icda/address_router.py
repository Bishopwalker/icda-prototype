"""FastAPI router for address verification endpoints.

This module provides the REST API endpoints for the address verification
pipeline, including single address verification, batch processing,
and index management.

Now includes the 5-agent architecture endpoints for intelligent
address inference with context awareness and multi-state support.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from icda.address_models import (
    BatchItem,
    VerificationStatus,
)
from icda.address_pipeline import AddressPipeline, BatchProcessor

from icda.agents.orchestrator import AddressAgentOrchestrator


logger = logging.getLogger(__name__)

# Router instance - will be configured with pipeline in main.py
router = APIRouter(prefix="/api/address", tags=["Address Verification"])

# Global reference to pipeline (set during app startup)
_pipeline: AddressPipeline | None = None
_batch_processor: BatchProcessor | None = None
_orchestrator = None  # Will be AddressAgentOrchestrator when implemented


def configure_router(
    pipeline: AddressPipeline,
    orchestrator=None,
) -> None:
    """Configure the router with pipeline dependencies.

    Args:
        pipeline: Initialized address verification pipeline.
        orchestrator: Optional 5-agent orchestrator for intelligent verification.
    """
    global _pipeline, _batch_processor, _orchestrator
    _pipeline = pipeline
    _batch_processor = BatchProcessor(pipeline)
    _orchestrator = orchestrator
    logger.info(f"Address router configured (orchestrator={'enabled' if orchestrator else 'disabled'})")


# ============================================================================
# Request/Response Models
# ============================================================================


class AddressVerifyRequest(BaseModel):
    """Request model for single address verification."""

    address: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Raw address string to verify",
        examples=["101 turkey ok 22222", "123 Main St, New York, NY 10001"],
    )
    context: dict[str, str] = Field(
        default_factory=dict,
        description="Optional context hints (zip, state, etc.)",
    )


class AddressVerifyResponse(BaseModel):
    """Response model for single address verification."""

    success: bool
    status: str
    original: dict[str, Any]
    verified: dict[str, Any] | None
    confidence: float
    match_type: str | None
    alternatives: list[dict[str, Any]]
    processing_time_ms: int
    metadata: dict[str, Any]
    # Puerto Rico specific fields
    is_puerto_rico: bool = Field(
        default=False,
        description="True if address is Puerto Rico (ZIP 006-009)",
    )
    urbanization: str | None = Field(
        default=None,
        description="Puerto Rico urbanization name (URB) if applicable",
    )
    pr_warnings: list[str] = Field(
        default_factory=list,
        description="Puerto Rico-specific warnings (e.g., missing urbanization)",
    )


class BatchVerifyRequest(BaseModel):
    """Request model for batch address verification."""

    addresses: list[str] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of addresses to verify",
    )
    concurrency: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum concurrent verifications",
    )


class BatchRecordRequest(BaseModel):
    """Request model for batch verification with record format."""

    records: list[dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="List of records with address data",
    )
    address_field: str = Field(
        default="address",
        description="Field name containing address",
    )
    id_field: str = Field(
        default="id",
        description="Field name for unique ID",
    )
    concurrency: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum concurrent verifications",
    )


class BatchVerifyResponse(BaseModel):
    """Response model for batch verification."""

    success: bool
    results: list[dict[str, Any]]
    summary: dict[str, Any]


class StreetSuggestionRequest(BaseModel):
    """Request model for street name suggestions."""

    partial: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Partial street name",
    )
    zip_code: str = Field(
        ...,
        min_length=5,
        max_length=5,
        description="5-digit ZIP code",
    )
    street_number: str | None = Field(
        default=None,
        description="Optional street number for context",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum suggestions to return",
    )


class StreetSuggestionResponse(BaseModel):
    """Response model for street suggestions."""

    suggestions: list[dict[str, Any]]
    zip_code: str
    partial: str


class IndexStatsResponse(BaseModel):
    """Response model for index statistics."""

    total_addresses: int
    unique_zips: int
    unique_states: int
    unique_cities: int
    unique_streets: int
    indexed: bool


# ============================================================================
# Endpoints
# ============================================================================


@router.post("/verify", response_model=AddressVerifyResponse)
async def verify_address(request: AddressVerifyRequest) -> AddressVerifyResponse:
    """Verify a single address through the pipeline.

    This endpoint processes the address through all verification stages:
    1. Normalize and parse the address
    2. Classify quality and identify issues
    3. Look for exact matches in known addresses
    4. Find fuzzy matches if no exact match
    5. Use Nova AI to complete/correct if needed

    Args:
        request: Address verification request.

    Returns:
        Verification result with status, confidence, and alternatives.
    """
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    result = await _pipeline.verify(request.address)

    # Extract PR-specific warnings from metadata
    pr_warnings: list[str] = []
    if result.original.is_puerto_rico and not result.original.urbanization:
        pr_warnings.append("Puerto Rico address missing urbanization (URB) - deliverability uncertain")
    if result.metadata.get("pr_warnings"):
        pr_warnings.extend(result.metadata["pr_warnings"])

    return AddressVerifyResponse(
        success=result.status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.CORRECTED,
            VerificationStatus.COMPLETED,
        ),
        status=result.status.value,
        original=result.original.to_dict(),
        verified=result.verified.to_dict() if result.verified else None,
        confidence=result.confidence,
        match_type=result.match_type,
        alternatives=[a.to_dict() for a in result.alternatives],
        processing_time_ms=result.metadata.get("total_time_ms", 0),
        metadata=result.metadata,
        is_puerto_rico=result.original.is_puerto_rico,
        urbanization=result.original.urbanization,
        pr_warnings=pr_warnings,
    )


@router.post("/verify/batch", response_model=BatchVerifyResponse)
async def verify_batch(request: BatchVerifyRequest) -> BatchVerifyResponse:
    """Verify a batch of addresses.

    Processes multiple addresses concurrently with configurable
    parallelism. Returns individual results and summary statistics.

    Args:
        request: Batch verification request.

    Returns:
        Results for each address and overall summary.
    """
    if not _batch_processor:
        raise HTTPException(status_code=503, detail="Batch processor not initialized")

    results, summary = await _batch_processor.process_list(
        request.addresses,
        concurrency=request.concurrency,
    )

    return BatchVerifyResponse(
        success=summary.success_rate > 0.5,
        results=[r.to_dict() for r in results],
        summary=summary.to_dict(),
    )


@router.post("/verify/records", response_model=BatchVerifyResponse)
async def verify_records(request: BatchRecordRequest) -> BatchVerifyResponse:
    """Verify addresses from structured records.

    Accepts records with flexible field names for address data.
    Useful for processing data exports or database dumps.

    Args:
        request: Batch record verification request.

    Returns:
        Results for each record and overall summary.
    """
    if not _batch_processor:
        raise HTTPException(status_code=503, detail="Batch processor not initialized")

    results, summary = await _batch_processor.process_records(
        request.records,
        address_field=request.address_field,
        id_field=request.id_field,
        concurrency=request.concurrency,
    )

    return BatchVerifyResponse(
        success=summary.success_rate > 0.5,
        results=[r.to_dict() for r in results],
        summary=summary.to_dict(),
    )


@router.post("/suggest/street", response_model=StreetSuggestionResponse)
async def suggest_street(request: StreetSuggestionRequest) -> StreetSuggestionResponse:
    """Get street name suggestions for a partial input.

    Useful for autocomplete functionality or manual address
    correction. Returns street names within the specified ZIP
    that match the partial input.

    Example: partial="turkey", zip="22222" -> ["Turkey Run", "Turkey Trot Ln"]

    Args:
        request: Street suggestion request.

    Returns:
        List of matching street name suggestions.
    """
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    suggestions = await _pipeline.completer.suggest_street_completion(
        request.partial,
        request.zip_code,
        request.street_number,
    )

    return StreetSuggestionResponse(
        suggestions=suggestions[:request.limit],
        zip_code=request.zip_code,
        partial=request.partial,
    )


@router.get("/index/stats", response_model=IndexStatsResponse)
async def get_index_stats() -> IndexStatsResponse:
    """Get address index statistics.

    Returns information about the known address index including
    total addresses indexed and unique counts.

    Returns:
        Index statistics.
    """
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    stats = _pipeline.index.stats()

    return IndexStatsResponse(
        total_addresses=stats["total_addresses"],
        unique_zips=stats["unique_zips"],
        unique_states=stats["unique_states"],
        unique_cities=stats["unique_cities"],
        unique_streets=stats["unique_streets"],
        indexed=stats["indexed"],
    )


@router.post("/index/rebuild")
async def rebuild_index(background_tasks: BackgroundTasks) -> dict[str, str]:
    """Trigger a rebuild of the address index.

    Rebuilds the index from the current customer database.
    This operation runs in the background.

    Returns:
        Status message.
    """
    if not _pipeline:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")

    # For now, just return status - in production you'd queue this
    return {
        "status": "Index rebuild would be triggered here",
        "note": "Current implementation builds index on startup",
    }


@router.get("/health")
async def health_check() -> dict[str, Any]:
    """Check address verification service health.

    Returns:
        Health status of the address verification components.
    """
    return {
        "status": "healthy" if _pipeline else "not_initialized",
        "pipeline": _pipeline is not None,
        "batch_processor": _batch_processor is not None,
        "orchestrator": _orchestrator is not None,
        "index_ready": _pipeline.index.is_indexed if _pipeline else False,
        "completer_available": _pipeline.completer.available if _pipeline else False,
    }


# ============================================================================
# Agent-Based Verification (5-Agent Architecture)
# ============================================================================


class AgentVerifyRequest(BaseModel):
    """Request model for agent-based address verification."""

    address: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Raw address string to verify",
        examples=["101 turkey", "123 Main St", "456 Oak Ave Las Vegas"],
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID for conversation context",
    )
    session_history: list[dict[str, Any]] | None = Field(
        default=None,
        description="Conversation history for context extraction",
    )
    hints: dict[str, str] | None = Field(
        default=None,
        description="Explicit hints like {'state': 'NV', 'city': 'Las Vegas'}",
    )
    multi_state: bool = Field(
        default=True,
        description="Enable multi-state results when state uncertain",
    )
    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum matches to return",
    )
    include_trace: bool = Field(
        default=True,
        description="Include visual pipeline trace in response",
    )


class AgentVerifyResponse(BaseModel):
    """Response model for agent-based verification."""

    success: bool
    status: str
    verified: dict[str, Any] | None
    confidence: float
    alternatives: list[dict[str, Any]]
    multi_state_results: dict[str, list[dict[str, Any]]] | None
    inferences_made: dict[str, Any]
    context_used: dict[str, Any]
    quality_gates: list[dict[str, Any]]
    processing_time_ms: int
    agent_timings: dict[str, int]
    pipeline_trace: dict[str, Any] | None = Field(
        default=None,
        description="Visual pipeline trace showing query flow through agents",
    )


class AgentStatsResponse(BaseModel):
    """Response model for agent statistics."""

    agents: dict[str, Any]
    indexes: dict[str, Any]


@router.post("/verify/agent", response_model=AgentVerifyResponse)
async def verify_with_agents(request: AgentVerifyRequest) -> AgentVerifyResponse:
    """Verify address using 5-agent intelligent pipeline.

    This endpoint uses the new agent-based architecture for:
    - Context extraction from conversation history
    - Intelligent inference of missing components
    - Multi-state matching when state is uncertain
    - Semantic vector search for similar addresses
    - Quality gate validation

    The 5 agents are:
    1. Context Agent - Extracts geographic context from history
    2. Parser Agent - Normalizes and parses the address
    3. Inference Agent - Infers missing state, city, ZIP
    4. Match Agent - Finds matches using fuzzy + semantic search
    5. Enforcer Agent - Validates results with quality gates

    Args:
        request: Agent verification request with optional context.

    Returns:
        Comprehensive verification result with inferences, multi-state results, and pipeline trace.
    """
    if not _orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Agent orchestrator not initialized. Use /verify for legacy pipeline."
        )

    result, trace = await _orchestrator.process(
        raw_address=request.address,
        session_id=request.session_id,
        session_history=request.session_history,
        hints=request.hints,
        max_results=request.max_results,
        enable_trace=request.include_trace,
    )

    # Convert ParsedAddress objects to dicts
    verified_dict = None
    if result.verified_address:
        verified_dict = {
            "street_number": result.verified_address.street_number,
            "street_name": result.verified_address.street_name,
            "street_type": result.verified_address.street_type,
            "city": result.verified_address.city,
            "state": result.verified_address.state,
            "zip_code": result.verified_address.zip_code,
            "single_line": result.verified_address.single_line,
        }

    alternatives_list = []
    for alt in result.alternatives:
        alternatives_list.append({
            "street_number": alt.street_number,
            "street_name": alt.street_name,
            "street_type": alt.street_type,
            "city": alt.city,
            "state": alt.state,
            "zip_code": alt.zip_code,
            "single_line": alt.single_line,
        })

    # Convert multi-state results
    multi_state_dict = None
    if result.multi_state_results:
        multi_state_dict = {}
        for state, addresses in result.multi_state_results.items():
            multi_state_dict[state] = [
                {
                    "street_number": a.street_number,
                    "street_name": a.street_name,
                    "street_type": a.street_type,
                    "city": a.city,
                    "state": a.state,
                    "zip_code": a.zip_code,
                    "single_line": a.single_line,
                }
                for a in addresses
            ]

    # Convert quality gates
    quality_gates_list = [
        {
            "gate": g.gate.value,
            "passed": g.passed,
            "message": g.message,
            "details": g.details,
        }
        for g in result.quality_gates
    ]

    return AgentVerifyResponse(
        success=result.status in (
            VerificationStatus.VERIFIED,
            VerificationStatus.CORRECTED,
            VerificationStatus.COMPLETED,
        ),
        status=result.status.value,
        verified=verified_dict,
        confidence=result.confidence,
        alternatives=alternatives_list,
        multi_state_results=multi_state_dict,
        inferences_made=result.metadata.get("inferences_made", {}),
        context_used={
            "confidence": result.metadata.get("context_confidence", 0),
            "signals": result.metadata.get("context_signals", []),
        },
        quality_gates=quality_gates_list,
        processing_time_ms=result.metadata.get("total_time_ms", 0),
        agent_timings=result.metadata.get("agent_timings", {}),
        pipeline_trace=trace.to_dict() if trace else None,
    )


@router.get("/agents/stats", response_model=AgentStatsResponse)
async def get_agent_stats() -> AgentStatsResponse:
    """Get statistics for all agents in the pipeline.

    Returns:
        Agent performance statistics and index information.
    """
    if not _orchestrator:
        raise HTTPException(
            status_code=503,
            detail="Agent orchestrator not initialized"
        )

    stats = _orchestrator.get_agent_stats()

    return AgentStatsResponse(
        agents={
            "context": stats.get("context_agent", {}),
            "parser": stats.get("parser_agent", {}),
            "inference": stats.get("inference_agent", {}),
            "match": stats.get("match_agent", {}),
            "enforcer": stats.get("enforcer_agent", {}),
        },
        indexes=stats.get("indexes", {}),
    )
