"""Address verification pipeline with enforcer pattern.

This module implements the main address verification pipeline that
orchestrates the flow of addresses through classification, known
address lookup, and AI-powered completion stages.

The enforcer pattern ensures each stage validates and potentially
enriches the address before passing to the next stage.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Awaitable

from icda.address_models import (
    AddressQuality,
    BatchItem,
    BatchResult,
    BatchSummary,
    ParsedAddress,
    VerificationResult,
    VerificationStatus,
)
from icda.address_normalizer import AddressNormalizer, AddressClassification
from icda.address_index import AddressIndex, MatchResult
from icda.address_completer import NovaAddressCompleter


logger = logging.getLogger(__name__)


class PipelineStage(str, Enum):
    """Stages in the verification pipeline."""

    NORMALIZE = "normalize"
    CLASSIFY = "classify"
    EXACT_MATCH = "exact_match"
    FUZZY_MATCH = "fuzzy_match"
    AI_COMPLETE = "ai_complete"
    FINALIZE = "finalize"


@dataclass(slots=True)
class PipelineContext:
    """Context passed through pipeline stages.

    This object accumulates results as it flows through each stage,
    allowing later stages to make decisions based on earlier results.

    Attributes:
        raw_input: Original input string.
        parsed: Parsed address (after normalize stage).
        classification: Quality classification (after classify stage).
        exact_matches: Exact match results (after exact_match stage).
        fuzzy_matches: Fuzzy match results (after fuzzy_match stage).
        verification: Final verification result.
        current_stage: Current pipeline stage.
        start_time: When processing started.
        metadata: Additional context data.
    """

    raw_input: str
    parsed: ParsedAddress | None = None
    classification: AddressClassification | None = None
    exact_matches: list[MatchResult] = field(default_factory=list)
    fuzzy_matches: list[MatchResult] = field(default_factory=list)
    verification: VerificationResult | None = None
    current_stage: PipelineStage = PipelineStage.NORMALIZE
    start_time: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_ms(self) -> int:
        """Return elapsed time in milliseconds."""
        return int((time.time() - self.start_time) * 1000)

    def should_continue(self) -> bool:
        """Check if pipeline should continue to next stage."""
        # Stop if we have a high-confidence verification
        if self.verification and self.verification.confidence >= 0.95:
            return False
        # Stop if marked invalid with high confidence
        if (
            self.classification
            and self.classification.quality == AddressQuality.INVALID
            and self.classification.confidence >= 0.9
        ):
            return False
        return True


class AddressPipeline:
    """Main address verification pipeline orchestrator.

    Implements the enforcer pattern where each stage acts as a gate,
    validating and enriching the address before the next stage.

    Pipeline Stages:
    1. NORMALIZE: Parse raw input into structured components
    2. CLASSIFY: Assess quality and identify issues
    3. EXACT_MATCH: Look for exact matches in known addresses
    4. FUZZY_MATCH: Find similar addresses if no exact match
    5. AI_COMPLETE: Use Nova to complete/correct if needed
    6. FINALIZE: Compile final verification result
    """

    def __init__(
        self,
        address_index: AddressIndex,
        completer: NovaAddressCompleter,
        max_fuzzy_results: int = 10,
        fuzzy_threshold: float = 0.6,
    ):
        """Initialize the pipeline.

        Args:
            address_index: Index of known addresses.
            completer: Nova AI completer for partial addresses.
            max_fuzzy_results: Maximum fuzzy matches to consider.
            fuzzy_threshold: Minimum score for fuzzy matches.
        """
        self.index = address_index
        self.completer = completer
        self.max_fuzzy_results = max_fuzzy_results
        self.fuzzy_threshold = fuzzy_threshold

        # Stage handlers
        self._stages: dict[PipelineStage, Callable[[PipelineContext], Awaitable[None]]] = {
            PipelineStage.NORMALIZE: self._stage_normalize,
            PipelineStage.CLASSIFY: self._stage_classify,
            PipelineStage.EXACT_MATCH: self._stage_exact_match,
            PipelineStage.FUZZY_MATCH: self._stage_fuzzy_match,
            PipelineStage.AI_COMPLETE: self._stage_ai_complete,
            PipelineStage.FINALIZE: self._stage_finalize,
        }

        logger.info("AddressPipeline initialized")

    async def verify(self, raw_address: str) -> VerificationResult:
        """Verify a single address through the pipeline.

        Args:
            raw_address: Raw address string to verify.

        Returns:
            VerificationResult with verification outcome.
        """
        ctx = PipelineContext(raw_input=raw_address)

        # Run through pipeline stages
        for stage in PipelineStage:
            ctx.current_stage = stage
            handler = self._stages[stage]
            await handler(ctx)

            # Check if we can short-circuit
            if not ctx.should_continue() and stage != PipelineStage.FINALIZE:
                # Skip to finalize
                ctx.current_stage = PipelineStage.FINALIZE
                await self._stage_finalize(ctx)
                break

        ctx.metadata["total_time_ms"] = ctx.elapsed_ms
        return ctx.verification

    async def verify_batch(
        self,
        items: list[BatchItem],
        concurrency: int = 10,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> tuple[list[BatchResult], BatchSummary]:
        """Verify a batch of addresses concurrently.

        Args:
            items: List of batch items to verify.
            concurrency: Maximum concurrent verifications.
            progress_callback: Optional callback(completed, total).

        Returns:
            Tuple of (results list, summary statistics).
        """
        semaphore = asyncio.Semaphore(concurrency)
        results: list[BatchResult] = []
        summary = BatchSummary(total=len(items))
        completed = 0
        start_time = time.time()

        async def process_item(item: BatchItem) -> BatchResult:
            nonlocal completed
            async with semaphore:
                item_start = time.time()
                try:
                    result = await self.verify(item.address)
                    processing_time = int((time.time() - item_start) * 1000)
                    return BatchResult(
                        id=item.id,
                        result=result,
                        processing_time_ms=processing_time,
                        stage_reached=result.metadata.get("final_stage", "unknown"),
                    )
                except Exception as e:
                    logger.error(f"Batch item {item.id} failed: {e}")
                    # Create failed result
                    parsed = AddressNormalizer.normalize(item.address)
                    return BatchResult(
                        id=item.id,
                        result=VerificationResult(
                            status=VerificationStatus.FAILED,
                            original=parsed,
                            metadata={"error": str(e)},
                        ),
                        processing_time_ms=int((time.time() - item_start) * 1000),
                        stage_reached="error",
                    )

        # Process all items
        tasks = [process_item(item) for item in items]
        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)
            completed += 1

            # Update summary
            status = result.result.status
            if status == VerificationStatus.VERIFIED:
                summary.verified += 1
            elif status == VerificationStatus.CORRECTED:
                summary.corrected += 1
            elif status == VerificationStatus.COMPLETED:
                summary.completed += 1
            elif status == VerificationStatus.SUGGESTED:
                summary.suggested += 1
            elif status == VerificationStatus.FAILED:
                summary.failed += 1
            else:
                summary.unverified += 1

            if progress_callback:
                progress_callback(completed, len(items))

        summary.total_time_ms = int((time.time() - start_time) * 1000)

        # Sort results by original order
        id_to_result = {r.id: r for r in results}
        results = [id_to_result[item.id] for item in items]

        return results, summary

    async def _stage_normalize(self, ctx: PipelineContext) -> None:
        """Stage 1: Parse and normalize the raw address."""
        ctx.parsed = AddressNormalizer.normalize(ctx.raw_input)
        ctx.metadata["parse_time_ms"] = ctx.elapsed_ms
        logger.debug(f"Normalized: {ctx.parsed.single_line}")

    async def _stage_classify(self, ctx: PipelineContext) -> None:
        """Stage 2: Classify address quality."""
        if not ctx.parsed:
            return

        ctx.classification = AddressNormalizer.classify(ctx.parsed)
        ctx.metadata["classification"] = {
            "quality": ctx.classification.quality.value,
            "confidence": ctx.classification.confidence,
            "issues": ctx.classification.issues,
        }
        logger.debug(
            f"Classified as {ctx.classification.quality.value} "
            f"(confidence: {ctx.classification.confidence:.2f})"
        )

    async def _stage_exact_match(self, ctx: PipelineContext) -> None:
        """Stage 3: Look for exact matches in the index."""
        if not ctx.parsed:
            return

        ctx.exact_matches = self.index.lookup_exact(ctx.parsed)

        if ctx.exact_matches:
            # Found exact match - we're done
            best = ctx.exact_matches[0]
            ctx.verification = VerificationResult(
                status=VerificationStatus.VERIFIED,
                original=ctx.parsed,
                verified=best.address.parsed,
                confidence=1.0,
                match_type="exact",
                metadata={
                    "customer_id": best.customer_id,
                    "source": best.address.source,
                },
            )
            logger.debug(f"Exact match found: {best.address.parsed.single_line}")

    async def _stage_fuzzy_match(self, ctx: PipelineContext) -> None:
        """Stage 4: Find fuzzy matches if no exact match."""
        if not ctx.parsed or ctx.verification:
            return

        # Try fuzzy matching
        ctx.fuzzy_matches = self.index.lookup_fuzzy(
            ctx.parsed,
            threshold=self.fuzzy_threshold,
        )[:self.max_fuzzy_results]

        # Also try street-in-ZIP matching if we have partial street + ZIP
        if ctx.parsed.street_name and ctx.parsed.zip_code:
            street_matches = self.index.lookup_street_in_zip(
                ctx.parsed.street_name,
                ctx.parsed.zip_code,
                threshold=self.fuzzy_threshold,
            )
            # Merge and dedupe
            seen = {m.address.normalized_key for m in ctx.fuzzy_matches}
            for m in street_matches:
                if m.address.normalized_key not in seen:
                    ctx.fuzzy_matches.append(m)
                    seen.add(m.address.normalized_key)

        # Sort by score
        ctx.fuzzy_matches.sort(key=lambda m: m.score, reverse=True)
        ctx.fuzzy_matches = ctx.fuzzy_matches[:self.max_fuzzy_results]

        if ctx.fuzzy_matches:
            best = ctx.fuzzy_matches[0]
            logger.debug(
                f"Best fuzzy match: {best.address.parsed.single_line} "
                f"(score: {best.score:.2f})"
            )

            # If very high score, accept as verified
            if best.score >= 0.95:
                ctx.verification = VerificationResult(
                    status=VerificationStatus.VERIFIED,
                    original=ctx.parsed,
                    verified=best.address.parsed,
                    confidence=best.score,
                    match_type=best.match_type,
                    alternatives=[m.address.parsed for m in ctx.fuzzy_matches[1:4]],
                    metadata={"customer_id": best.customer_id},
                )

    async def _stage_ai_complete(self, ctx: PipelineContext) -> None:
        """Stage 5: Use Nova AI to complete/correct the address."""
        if not ctx.parsed or ctx.verification:
            return

        # Only use AI if we have something to work with
        if (
            ctx.classification
            and ctx.classification.quality == AddressQuality.INVALID
        ):
            # Too invalid for AI completion
            return

        # Use Nova to complete
        ctx.verification = await self.completer.complete_address(
            ctx.parsed,
            ctx.fuzzy_matches,
        )
        ctx.verification.metadata["ai_completion"] = True

    async def _stage_finalize(self, ctx: PipelineContext) -> None:
        """Stage 6: Finalize the verification result."""
        if not ctx.parsed:
            # No parsed address - create error result
            ctx.verification = VerificationResult(
                status=VerificationStatus.FAILED,
                original=ParsedAddress(raw=ctx.raw_input),
                metadata={"error": "Could not parse address"},
            )
            return

        if not ctx.verification:
            # No verification yet - mark as unverified
            ctx.verification = VerificationResult(
                status=VerificationStatus.UNVERIFIED,
                original=ctx.parsed,
                confidence=0.0,
                metadata={
                    "classification": ctx.classification.quality.value
                    if ctx.classification
                    else "unknown",
                },
            )

        # Add final metadata
        ctx.verification.metadata["final_stage"] = ctx.current_stage.value
        ctx.verification.metadata["exact_matches"] = len(ctx.exact_matches)
        ctx.verification.metadata["fuzzy_matches"] = len(ctx.fuzzy_matches)


class BatchProcessor:
    """High-level batch processing for address verification.

    Provides convenient methods for processing large datasets with
    progress tracking, error handling, and result aggregation.
    """

    def __init__(self, pipeline: AddressPipeline):
        """Initialize batch processor.

        Args:
            pipeline: Address verification pipeline.
        """
        self.pipeline = pipeline

    async def process_list(
        self,
        addresses: list[str],
        concurrency: int = 10,
    ) -> tuple[list[BatchResult], BatchSummary]:
        """Process a list of address strings.

        Args:
            addresses: List of raw address strings.
            concurrency: Maximum concurrent verifications.

        Returns:
            Tuple of (results, summary).
        """
        items = [
            BatchItem(id=str(i), address=addr)
            for i, addr in enumerate(addresses)
        ]
        return await self.pipeline.verify_batch(items, concurrency)

    async def process_records(
        self,
        records: list[dict[str, Any]],
        address_field: str = "address",
        id_field: str = "id",
        concurrency: int = 10,
    ) -> tuple[list[BatchResult], BatchSummary]:
        """Process a list of records with address fields.

        Args:
            records: List of dictionaries with address data.
            address_field: Field name containing address.
            id_field: Field name for unique ID.
            concurrency: Maximum concurrent verifications.

        Returns:
            Tuple of (results, summary).
        """
        items = []
        for i, record in enumerate(records):
            addr = record.get(address_field, "")
            item_id = str(record.get(id_field, i))

            # Build full address from fields if needed
            if not addr:
                # Try to build from components
                parts = []
                if street := record.get("street"):
                    parts.append(street)
                if city := record.get("city"):
                    parts.append(city)
                if state := record.get("state"):
                    parts.append(state)
                if zip_code := record.get("zip") or record.get("zip_code"):
                    parts.append(str(zip_code))
                addr = ", ".join(parts)

            items.append(BatchItem(
                id=item_id,
                address=addr,
                context={k: str(v) for k, v in record.items() if k not in (address_field, id_field)},
            ))

        return await self.pipeline.verify_batch(items, concurrency)

    async def process_csv_data(
        self,
        rows: list[dict[str, str]],
        address_columns: list[str] | None = None,
        id_column: str | None = None,
        concurrency: int = 10,
    ) -> tuple[list[BatchResult], BatchSummary]:
        """Process CSV data with flexible column mapping.

        Args:
            rows: List of CSV rows as dictionaries.
            address_columns: Columns to combine for address.
            id_column: Column to use for ID.
            concurrency: Maximum concurrent verifications.

        Returns:
            Tuple of (results, summary).
        """
        if not address_columns:
            # Auto-detect address columns
            address_columns = []
            sample = rows[0] if rows else {}
            for col in ["address", "street", "addr", "address1"]:
                if col in sample:
                    address_columns.append(col)
                    break
            for col in ["city"]:
                if col in sample:
                    address_columns.append(col)
            for col in ["state", "st"]:
                if col in sample:
                    address_columns.append(col)
                    break
            for col in ["zip", "zip_code", "zipcode", "postal"]:
                if col in sample:
                    address_columns.append(col)
                    break

        items = []
        for i, row in enumerate(rows):
            # Build address from columns
            parts = [row.get(col, "") for col in address_columns if row.get(col)]
            addr = ", ".join(parts)

            # Get ID
            item_id = row.get(id_column, str(i)) if id_column else str(i)

            items.append(BatchItem(
                id=item_id,
                address=addr,
                context=row,
            ))

        return await self.pipeline.verify_batch(items, concurrency)
