"""5-Agent Address Verification Orchestrator.

This module implements a multi-agent architecture for intelligent
address verification with context awareness and multi-state support.

The 5 agents are:
1. Context Agent - Extracts geographic context from conversation history
2. Parser Agent - Normalizes and parses raw address input
3. Inference Agent - Infers missing components (state, city, ZIP)
4. Match Agent - Finds matches using fuzzy + semantic search
5. Enforcer Agent - Validates results with quality gates
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from icda.address_models import (
    ParsedAddress,
    VerificationResult,
    VerificationStatus,
)
from icda.address_index import AddressIndex
from icda.address_normalizer import AddressNormalizer
from icda.indexes.zip_database import ZipDatabase
from icda.indexes.address_vector_index import AddressVectorIndex

logger = logging.getLogger(__name__)


class QualityGate(str, Enum):
    """Quality gates for address verification."""
    PARSEABLE = "parseable"
    HAS_STREET = "has_street"
    HAS_LOCATION = "has_location"
    STATE_VALID = "state_valid"
    ZIP_VALID = "zip_valid"
    CONFIDENCE_THRESHOLD = "confidence_threshold"


@dataclass(slots=True)
class QualityGateResult:
    """Result of a quality gate check."""
    gate: QualityGate
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AgentResult:
    """Result from processing through all agents."""
    status: VerificationStatus
    verified_address: ParsedAddress | None
    confidence: float
    alternatives: list[ParsedAddress]
    multi_state_results: dict[str, list[ParsedAddress]] | None
    quality_gates: list[QualityGateResult]
    metadata: dict[str, Any]


@dataclass(slots=True)
class PipelineTrace:
    """Visual trace of the pipeline execution."""
    stages: list[dict[str, Any]]
    total_time_ms: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "stages": self.stages,
            "total_time_ms": self.total_time_ms,
        }


class ContextAgent:
    """Extracts geographic context from conversation history."""

    def extract_context(
        self,
        session_history: list[dict[str, Any]] | None,
        hints: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Extract location context from history and hints.

        Args:
            session_history: Previous conversation messages.
            hints: Explicit location hints.

        Returns:
            Dict with extracted context (state, city, zip, confidence).
        """
        context = {
            "state": None,
            "city": None,
            "zip_code": None,
            "confidence": 0.0,
            "signals": [],
        }

        # Priority 1: Explicit hints
        if hints:
            if hints.get("state"):
                context["state"] = hints["state"].upper()
                context["signals"].append("explicit_hint_state")
                context["confidence"] = 0.9
            if hints.get("city"):
                context["city"] = hints["city"]
                context["signals"].append("explicit_hint_city")
            if hints.get("zip"):
                context["zip_code"] = hints["zip"]
                context["signals"].append("explicit_hint_zip")
                context["confidence"] = 0.95

        # Priority 2: Extract from conversation history
        if session_history and not context["state"]:
            for msg in reversed(session_history[-10:]):
                content = msg.get("content", "")
                if isinstance(content, list):
                    content = " ".join(
                        b.get("text", "") for b in content if isinstance(b, dict)
                    )

                # Look for state mentions
                state = self._extract_state(content)
                if state and not context["state"]:
                    context["state"] = state
                    context["signals"].append("history_state")
                    context["confidence"] = max(context["confidence"], 0.6)

                # Look for city mentions
                city = self._extract_city(content)
                if city and not context["city"]:
                    context["city"] = city
                    context["signals"].append("history_city")

                # Look for ZIP mentions
                zip_code = self._extract_zip(content)
                if zip_code and not context["zip_code"]:
                    context["zip_code"] = zip_code
                    context["signals"].append("history_zip")
                    context["confidence"] = max(context["confidence"], 0.7)

        return context

    def _extract_state(self, text: str) -> str | None:
        """Extract state code from text."""
        import re
        # Look for 2-letter state codes
        match = re.search(r'\b([A-Z]{2})\b', text)
        if match:
            state = match.group(1)
            # Validate it's a real state
            valid_states = {
                "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
                "DC",
            }
            if state in valid_states:
                return state
        return None

    def _extract_city(self, text: str) -> str | None:
        """Extract city name from text (basic implementation)."""
        # This is a simplified implementation
        # A production version would use NER or a city database
        return None

    def _extract_zip(self, text: str) -> str | None:
        """Extract ZIP code from text."""
        import re
        match = re.search(r'\b(\d{5})\b', text)
        if match:
            return match.group(1)
        return None


class ParserAgent:
    """Normalizes and parses raw address input."""

    def __init__(self):
        self.normalizer = AddressNormalizer()

    def parse(self, raw_address: str) -> ParsedAddress:
        """Parse raw address string into components.

        Args:
            raw_address: Raw address string.

        Returns:
            Parsed address with extracted components.
        """
        return self.normalizer.normalize(raw_address)


class InferenceAgent:
    """Infers missing address components."""

    def __init__(
        self,
        address_index: AddressIndex,
        zip_database: ZipDatabase | None,
    ):
        self.address_index = address_index
        self.zip_database = zip_database

    def infer(
        self,
        parsed: ParsedAddress,
        context: dict[str, Any],
    ) -> tuple[ParsedAddress, dict[str, Any]]:
        """Infer missing components using context and indexes.

        Args:
            parsed: Parsed address with possibly missing components.
            context: Geographic context from ContextAgent.

        Returns:
            Tuple of (updated address, inference metadata).
        """
        inferences = {}

        # Apply context if components are missing
        if not parsed.state and context.get("state"):
            parsed.state = context["state"]
            inferences["state"] = f"from_context:{context['state']}"

        if not parsed.city and context.get("city"):
            parsed.city = context["city"]
            inferences["city"] = f"from_context:{context['city']}"

        if not parsed.zip_code and context.get("zip_code"):
            parsed.zip_code = context["zip_code"]
            inferences["zip_code"] = f"from_context:{context['zip_code']}"

        # Infer from ZIP database
        if self.zip_database and parsed.zip_code:
            city_state = self.zip_database.get_city_state(parsed.zip_code)
            if city_state:
                city, state = city_state
                if not parsed.city:
                    parsed.city = city
                    inferences["city"] = f"from_zip:{parsed.zip_code}"
                if not parsed.state:
                    parsed.state = state
                    inferences["state"] = f"from_zip:{parsed.zip_code}"

        return parsed, inferences


class MatchAgent:
    """Finds address matches using multiple strategies."""

    def __init__(
        self,
        address_index: AddressIndex,
        vector_index: AddressVectorIndex | None,
    ):
        self.address_index = address_index
        self.vector_index = vector_index

    async def find_matches(
        self,
        parsed: ParsedAddress,
        max_results: int = 20,
        enable_multi_state: bool = True,
    ) -> tuple[list[ParsedAddress], dict[str, list[ParsedAddress]] | None]:
        """Find matching addresses.

        Args:
            parsed: Parsed address to match.
            max_results: Maximum results to return.
            enable_multi_state: Enable multi-state results.

        Returns:
            Tuple of (alternatives list, multi-state results dict).
        """
        alternatives = []
        multi_state_results = None

        # Strategy 1: Exact match
        exact = self.address_index.lookup_exact(parsed)
        for match in exact[:max_results]:
            alternatives.append(match.address.parsed)

        if alternatives:
            return alternatives, None

        # Strategy 2: Fuzzy match within ZIP
        if parsed.zip_code and parsed.street_name:
            fuzzy = self.address_index.lookup_street_in_zip(
                parsed.street_name,
                parsed.zip_code,
                threshold=0.5,
            )
            for match in fuzzy[:max_results]:
                if match.address.parsed not in alternatives:
                    alternatives.append(match.address.parsed)

        # Strategy 3: Fuzzy match with all components
        fuzzy_all = self.address_index.lookup_fuzzy(parsed, threshold=0.5)
        for match in fuzzy_all[:max_results - len(alternatives)]:
            if match.address.parsed not in alternatives:
                alternatives.append(match.address.parsed)

        # Strategy 4: Semantic search if available
        if self.vector_index and self.vector_index.available:
            query = parsed.single_line
            semantic = await self.vector_index.search_semantic(
                query,
                limit=max_results,
                state_filter=parsed.state,
                zip_filter=parsed.zip_code,
            )
            for result in semantic:
                addr = ParsedAddress(
                    raw=result.get("address_text", ""),
                    street_number=result.get("street_number"),
                    street_name=result.get("street_name"),
                    street_type=result.get("street_type"),
                    city=result.get("city"),
                    state=result.get("state"),
                    zip_code=result.get("zip_code"),
                )
                if addr not in alternatives:
                    alternatives.append(addr)

            # Multi-state search if state is uncertain
            if enable_multi_state and not parsed.state and self.vector_index:
                states_to_search = ["NV", "CA", "TX", "AZ", "FL"]  # Common states
                multi_state_results = {}

                for state in states_to_search:
                    state_matches = await self.vector_index.search_semantic(
                        query,
                        limit=5,
                        state_filter=state,
                    )
                    if state_matches:
                        multi_state_results[state] = [
                            ParsedAddress(
                                raw=r.get("address_text", ""),
                                street_number=r.get("street_number"),
                                street_name=r.get("street_name"),
                                street_type=r.get("street_type"),
                                city=r.get("city"),
                                state=r.get("state"),
                                zip_code=r.get("zip_code"),
                            )
                            for r in state_matches
                        ]

        return alternatives, multi_state_results


class EnforcerAgent:
    """Validates results with quality gates."""

    def __init__(self, zip_database: ZipDatabase | None):
        self.zip_database = zip_database

    def enforce(
        self,
        parsed: ParsedAddress,
        alternatives: list[ParsedAddress],
    ) -> tuple[VerificationStatus, float, list[QualityGateResult]]:
        """Run quality gates and determine final status.

        Args:
            parsed: Original parsed address.
            alternatives: Found alternatives.

        Returns:
            Tuple of (status, confidence, gate results).
        """
        gates = []
        passed_count = 0

        # Gate 1: Parseable
        parseable = bool(parsed.street_name or parsed.street_number)
        gates.append(QualityGateResult(
            gate=QualityGate.PARSEABLE,
            passed=parseable,
            message="Address can be parsed" if parseable else "Address not parseable",
        ))
        if parseable:
            passed_count += 1

        # Gate 2: Has street info
        has_street = bool(parsed.street_name)
        gates.append(QualityGateResult(
            gate=QualityGate.HAS_STREET,
            passed=has_street,
            message="Street name found" if has_street else "Street name missing",
        ))
        if has_street:
            passed_count += 1

        # Gate 3: Has location (city/state or ZIP)
        has_location = bool(parsed.city or parsed.state or parsed.zip_code)
        gates.append(QualityGateResult(
            gate=QualityGate.HAS_LOCATION,
            passed=has_location,
            message="Location info found" if has_location else "No location info",
        ))
        if has_location:
            passed_count += 1

        # Gate 4: State valid
        if parsed.state:
            valid_states = {
                "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
                "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
                "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
                "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
                "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
                "DC",
            }
            state_valid = parsed.state.upper() in valid_states
            gates.append(QualityGateResult(
                gate=QualityGate.STATE_VALID,
                passed=state_valid,
                message=f"State {parsed.state} valid" if state_valid else f"Invalid state: {parsed.state}",
            ))
            if state_valid:
                passed_count += 1

        # Gate 5: ZIP valid
        if parsed.zip_code and self.zip_database:
            zip_valid = self.zip_database.lookup_zip(parsed.zip_code) is not None
            gates.append(QualityGateResult(
                gate=QualityGate.ZIP_VALID,
                passed=zip_valid,
                message=f"ZIP {parsed.zip_code} found" if zip_valid else f"Unknown ZIP: {parsed.zip_code}",
            ))
            if zip_valid:
                passed_count += 1

        # Calculate confidence based on gates passed
        total_gates = len(gates)
        confidence = passed_count / total_gates if total_gates > 0 else 0.0

        # Determine status
        if alternatives:
            if confidence >= 0.8:
                status = VerificationStatus.VERIFIED
            elif confidence >= 0.6:
                status = VerificationStatus.CORRECTED
            elif confidence >= 0.4:
                status = VerificationStatus.SUGGESTED
            else:
                status = VerificationStatus.UNVERIFIED
        else:
            status = VerificationStatus.UNVERIFIED

        return status, confidence, gates


class AddressAgentOrchestrator:
    """Orchestrates the 5-agent address verification pipeline."""

    def __init__(
        self,
        address_index: AddressIndex,
        zip_database: ZipDatabase | None = None,
        vector_index: AddressVectorIndex | None = None,
    ):
        """Initialize orchestrator with dependencies.

        Args:
            address_index: Address lookup index.
            zip_database: ZIP code database.
            vector_index: Vector index for semantic search.
        """
        self.context_agent = ContextAgent()
        self.parser_agent = ParserAgent()
        self.inference_agent = InferenceAgent(address_index, zip_database)
        self.match_agent = MatchAgent(address_index, vector_index)
        self.enforcer_agent = EnforcerAgent(zip_database)

        self._process_count = 0
        self._total_time_ms = 0

    async def process(
        self,
        raw_address: str,
        session_id: str | None = None,
        session_history: list[dict[str, Any]] | None = None,
        hints: dict[str, str] | None = None,
        max_results: int = 20,
        enable_trace: bool = True,
    ) -> tuple[AgentResult, PipelineTrace | None]:
        """Process address through all agents.

        Args:
            raw_address: Raw address string to verify.
            session_id: Optional session ID for context.
            session_history: Conversation history.
            hints: Explicit location hints.
            max_results: Maximum matches to return.
            enable_trace: Include pipeline trace in response.

        Returns:
            Tuple of (AgentResult, PipelineTrace or None).
        """
        start_time = time.perf_counter()
        trace_stages = []
        agent_timings = {}

        # Stage 1: Context extraction
        stage_start = time.perf_counter()
        context = self.context_agent.extract_context(session_history, hints)
        agent_timings["context"] = int((time.perf_counter() - stage_start) * 1000)
        if enable_trace:
            trace_stages.append({
                "agent": "context",
                "output": context,
                "time_ms": agent_timings["context"],
            })

        # Stage 2: Parse
        stage_start = time.perf_counter()
        parsed = self.parser_agent.parse(raw_address)
        agent_timings["parser"] = int((time.perf_counter() - stage_start) * 1000)
        if enable_trace:
            trace_stages.append({
                "agent": "parser",
                "output": parsed.to_dict(),
                "time_ms": agent_timings["parser"],
            })

        # Stage 3: Inference
        stage_start = time.perf_counter()
        parsed, inferences = self.inference_agent.infer(parsed, context)
        agent_timings["inference"] = int((time.perf_counter() - stage_start) * 1000)
        if enable_trace:
            trace_stages.append({
                "agent": "inference",
                "output": {"parsed": parsed.to_dict(), "inferences": inferences},
                "time_ms": agent_timings["inference"],
            })

        # Stage 4: Match
        stage_start = time.perf_counter()
        alternatives, multi_state = await self.match_agent.find_matches(
            parsed, max_results, enable_multi_state=True
        )
        agent_timings["match"] = int((time.perf_counter() - stage_start) * 1000)
        if enable_trace:
            trace_stages.append({
                "agent": "match",
                "output": {
                    "alternatives_count": len(alternatives),
                    "multi_state_count": len(multi_state) if multi_state else 0,
                },
                "time_ms": agent_timings["match"],
            })

        # Stage 5: Enforce
        stage_start = time.perf_counter()
        status, confidence, gates = self.enforcer_agent.enforce(parsed, alternatives)
        agent_timings["enforcer"] = int((time.perf_counter() - stage_start) * 1000)
        if enable_trace:
            trace_stages.append({
                "agent": "enforcer",
                "output": {
                    "status": status.value,
                    "confidence": confidence,
                    "gates_passed": sum(1 for g in gates if g.passed),
                },
                "time_ms": agent_timings["enforcer"],
            })

        # Calculate total time
        total_time_ms = int((time.perf_counter() - start_time) * 1000)

        # Update stats
        self._process_count += 1
        self._total_time_ms += total_time_ms

        # Build result
        result = AgentResult(
            status=status,
            verified_address=alternatives[0] if alternatives else None,
            confidence=confidence,
            alternatives=alternatives[1:] if len(alternatives) > 1 else [],
            multi_state_results=multi_state,
            quality_gates=gates,
            metadata={
                "total_time_ms": total_time_ms,
                "agent_timings": agent_timings,
                "inferences_made": inferences,
                "context_confidence": context.get("confidence", 0),
                "context_signals": context.get("signals", []),
            },
        )

        trace = None
        if enable_trace:
            trace = PipelineTrace(
                stages=trace_stages,
                total_time_ms=total_time_ms,
            )

        return result, trace

    def get_agent_stats(self) -> dict[str, Any]:
        """Get statistics for all agents."""
        avg_time = self._total_time_ms / self._process_count if self._process_count > 0 else 0

        return {
            "context_agent": {"available": True},
            "parser_agent": {"available": True},
            "inference_agent": {"available": True},
            "match_agent": {
                "available": True,
                "vector_search": self.match_agent.vector_index is not None,
            },
            "enforcer_agent": {"available": True},
            "indexes": {
                "address_index": True,
                "zip_database": self.inference_agent.zip_database is not None,
                "vector_index": self.match_agent.vector_index is not None,
            },
            "stats": {
                "process_count": self._process_count,
                "avg_time_ms": round(avg_time, 2),
            },
        }
