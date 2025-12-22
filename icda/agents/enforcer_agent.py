"""Enforcer Agent - Quality gates and response validation with LLM integration.

This agent:
1. Validates response quality using 7 quality gates
2. Applies guardrails (PII filtering)
3. Checks response relevance
4. Ensures completeness
5. Uses secondary LLM for enhanced AI-powered validation (when available)
6. Returns final approved/modified response
"""

import logging
import re
from typing import Any

from .models import (
    IntentResult,
    ParsedQuery,
    NovaResponse,
    EnforcedResponse,
    QualityGate,
    QualityGateResult,
    ResponseStatus,
)

# Import LLM enforcer (optional) - supports any provider
try:
    from icda.llm import LLMEnforcer
    LLM_ENFORCER_AVAILABLE = True
except ImportError:
    LLM_ENFORCER_AVAILABLE = False

logger = logging.getLogger(__name__)


class EnforcerAgent:
    """Validates and enforces response quality with secondary LLM integration.

    Follows the enforcer pattern with 7 quality gates:
    1. RESPONSIVE - Response addresses the query
    2. FACTUAL - Response matches tool results
    3. PII_SAFE - No leaked sensitive data
    4. COMPLETE - All requested info included
    5. COHERENT - Response is well-formed
    6. ON_TOPIC - No off-topic content
    7. CONFIDENCE_MET - Above threshold

    When LLM enforcer is available (Gemini, OpenAI, Claude, etc.),
    adds AI-powered validation for hallucination detection.
    """
    __slots__ = ("_guardrails", "_llm_enforcer", "_available")

    # PII patterns for detection and redaction
    PII_PATTERNS = {
        "ssn": r"\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "bank_account": r"\b\d{8,17}\b",
        "phone": r"\b(?:\+1[-\s]?)?\(?\d{3}\)?[-\s]?\d{3}[-\s]?\d{4}\b",
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    }

    # Unsafe content patterns
    UNSAFE_PATTERNS = [
        r"social\s+security",
        r"ssn",
        r"credit\s+card",
        r"bank\s+account",
        r"routing\s+number",
        r"password",
        r"pin\s+number",
    ]

    def __init__(self, guardrails=None, llm_enforcer: "LLMEnforcer | None" = None):
        """Initialize EnforcerAgent with optional LLM validation.

        Args:
            guardrails: Optional Guardrails module for PII filtering.
            llm_enforcer: Optional LLMEnforcer for AI-powered validation.
        """
        self._guardrails = guardrails
        self._llm_enforcer = llm_enforcer
        self._available = True

        if self._llm_enforcer and self._llm_enforcer.available:
            provider = self._llm_enforcer.client.provider if self._llm_enforcer.client else "unknown"
            logger.info(f"EnforcerAgent: LLM validation enabled ({provider})")
        else:
            logger.info("EnforcerAgent: Using rule-based validation only")

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def enforce(
        self,
        nova_response: NovaResponse,
        query: str,
        intent: IntentResult,
        parsed: ParsedQuery,
    ) -> EnforcedResponse:
        """Enforce quality gates on the response.

        Args:
            nova_response: Response from NovaAgent.
            intent: Intent classification.
            parsed: Parsed query.

        Returns:
            EnforcedResponse with validation results.
        """
        original = nova_response.response_text
        modified = original
        modifications = []
        gates_passed = []
        gates_failed = []

        # Gate 1: Responsive - does response address the query?
        responsive_result = self._check_responsive(modified, query, intent)
        if responsive_result.passed:
            gates_passed.append(responsive_result)
        else:
            gates_failed.append(responsive_result)

        # Gate 2: Factual - is response consistent with tool results?
        factual_result = self._check_factual(modified, nova_response.tool_results)
        if factual_result.passed:
            gates_passed.append(factual_result)
        else:
            gates_failed.append(factual_result)

        # Gate 3: PII Safe - no sensitive data leaked?
        pii_result, modified, pii_mods = self._check_pii_safe(modified)
        modifications.extend(pii_mods)
        if pii_result.passed:
            gates_passed.append(pii_result)
        else:
            gates_failed.append(pii_result)

        # Gate 4: Complete - all requested info included?
        complete_result = self._check_complete(modified, parsed, nova_response)
        if complete_result.passed:
            gates_passed.append(complete_result)
        else:
            gates_failed.append(complete_result)

        # Gate 5: Coherent - is response well-formed?
        coherent_result = self._check_coherent(modified)
        if coherent_result.passed:
            gates_passed.append(coherent_result)
        else:
            gates_failed.append(coherent_result)

        # Gate 6: On Topic - no off-topic content?
        on_topic_result = self._check_on_topic(modified, intent)
        if on_topic_result.passed:
            gates_passed.append(on_topic_result)
        else:
            gates_failed.append(on_topic_result)

        # Gate 7: Confidence Met - above threshold?
        confidence_result = self._check_confidence(nova_response.ai_confidence)
        if confidence_result.passed:
            gates_passed.append(confidence_result)
        else:
            gates_failed.append(confidence_result)

        # Optional: LLM AI-powered validation for hallucination detection
        llm_quality_boost = 0.0
        if self._llm_enforcer and self._llm_enforcer.available:
            try:
                # Convert tool_results to chunks format for LLM review
                chunks = []
                for result in nova_response.tool_results:
                    if isinstance(result, dict):
                        for customer in result.get("data", result.get("results", [])):
                            if isinstance(customer, dict):
                                chunks.append({
                                    "chunk_id": customer.get("crid", "unknown"),
                                    "text": f"{customer.get('name', 'N/A')} - {customer.get('city', 'N/A')}, {customer.get('state', 'N/A')}",
                                })

                # Review query with LLM (non-blocking, uses sample rate)
                review = await self._llm_enforcer.review_query(
                    query_id=f"enf_{id(nova_response)}",
                    query_text=query,
                    retrieved_chunks=chunks,
                    response_text=modified,
                    force=False,  # Respect sample rate
                )

                if review:
                    # Apply LLM validation results
                    if review.hallucination_detected:
                        gates_failed.append(QualityGateResult(
                            gate=QualityGate.FACTUAL,
                            passed=False,
                            message=f"LLM detected hallucination: {review.hallucination_details}",
                            details={"llm_review": True},
                        ))
                        modifications.append("LLM enforcer flagged potential hallucination")
                    else:
                        # Boost quality score if LLM validates
                        llm_quality_boost = review.overall_quality * 0.1
                        logger.debug(f"LLM validation passed: {review.overall_quality:.2f}")

            except Exception as e:
                logger.warning(f"LLM validation failed: {e}")
                # Continue without LLM - graceful degradation

        # Calculate quality score (with optional LLM boost)
        total_gates = len(gates_passed) + len(gates_failed)
        quality_score = len(gates_passed) / total_gates if total_gates > 0 else 0.0
        quality_score = min(1.0, quality_score + llm_quality_boost)

        # Determine status
        status = self._determine_status(
            gates_passed, gates_failed, modifications, nova_response
        )

        return EnforcedResponse(
            final_response=modified,
            original_response=original,
            quality_score=quality_score,
            gates_passed=gates_passed,
            gates_failed=gates_failed,
            modifications=modifications,
            status=status,
        )

    def _check_responsive(
        self,
        response: str,
        query: str,
        intent: IntentResult,
    ) -> QualityGateResult:
        """Check if response addresses the query.

        Args:
            response: Response text.
            query: Original query.
            intent: Intent classification.

        Returns:
            QualityGateResult.
        """
        response_lower = response.lower()
        query_lower = query.lower()

        # Check for refusal phrases that are legitimate
        legitimate_refusals = [
            "no customers found",
            "no results",
            "could not find",
            "0 matches",
        ]
        if any(phrase in response_lower for phrase in legitimate_refusals):
            return QualityGateResult(
                gate=QualityGate.RESPONSIVE,
                passed=True,
                message="Response appropriately indicates no results",
            )

        # Check for generic refusals
        refusal_phrases = [
            "i cannot help",
            "i'm not able",
            "i don't have access",
            "unable to assist",
        ]
        if any(phrase in response_lower for phrase in refusal_phrases):
            return QualityGateResult(
                gate=QualityGate.RESPONSIVE,
                passed=False,
                message="Response appears to refuse without attempting",
            )

        # Check for query keywords in response
        query_words = set(query_lower.split()) - {"the", "a", "an", "is", "are", "in", "to", "for"}
        response_words = set(response_lower.split())
        overlap = query_words & response_words

        if len(overlap) >= min(2, len(query_words)):
            return QualityGateResult(
                gate=QualityGate.RESPONSIVE,
                passed=True,
                message="Response addresses query content",
            )

        # Check if response contains customer data (relevant for most queries)
        if re.search(r"CRID[-\s]?\d+", response, re.IGNORECASE):
            return QualityGateResult(
                gate=QualityGate.RESPONSIVE,
                passed=True,
                message="Response contains relevant customer data",
            )

        return QualityGateResult(
            gate=QualityGate.RESPONSIVE,
            passed=True,  # Default to pass if no clear issues
            message="Response appears to address query",
        )

    def _check_factual(
        self,
        response: str,
        tool_results: list[dict[str, Any]],
    ) -> QualityGateResult:
        """Check if response is consistent with tool results.

        Args:
            response: Response text.
            tool_results: Results from tool calls.

        Returns:
            QualityGateResult.
        """
        if not tool_results:
            return QualityGateResult(
                gate=QualityGate.FACTUAL,
                passed=True,
                message="No tool results to validate against",
            )

        # Extract CRIDs from response
        response_crids = set(re.findall(r"CRID[-\s]?\d+", response, re.IGNORECASE))

        # Extract CRIDs from tool results
        tool_crids = set()
        for result in tool_results:
            if isinstance(result, dict):
                # Check results list
                for item in result.get("results", []):
                    if isinstance(item, dict) and "crid" in item:
                        tool_crids.add(item["crid"])
                # Check single customer
                if "customer" in result and isinstance(result["customer"], dict):
                    if "crid" in result["customer"]:
                        tool_crids.add(result["customer"]["crid"])

        # If response mentions CRIDs, verify they're from results
        if response_crids and tool_crids:
            # Normalize for comparison
            response_crids_norm = {c.upper().replace(" ", "-") for c in response_crids}
            tool_crids_norm = {c.upper() for c in tool_crids}

            if not response_crids_norm.issubset(tool_crids_norm):
                extra = response_crids_norm - tool_crids_norm
                return QualityGateResult(
                    gate=QualityGate.FACTUAL,
                    passed=False,
                    message=f"Response mentions CRIDs not in results: {extra}",
                )

        return QualityGateResult(
            gate=QualityGate.FACTUAL,
            passed=True,
            message="Response consistent with tool results",
        )

    def _check_pii_safe(
        self,
        response: str,
    ) -> tuple[QualityGateResult, str, list[str]]:
        """Check and redact PII from response.

        Args:
            response: Response text.

        Returns:
            Tuple of (result, modified_response, modifications).
        """
        modified = response
        modifications = []
        found_pii = []

        # Check each PII pattern
        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, modified)
            if matches:
                found_pii.append(pii_type)
                # Redact
                modified = re.sub(pattern, f"[REDACTED-{pii_type.upper()}]", modified)
                modifications.append(f"Redacted {len(matches)} {pii_type} pattern(s)")

        # Check for unsafe content mentions
        for pattern in self.UNSAFE_PATTERNS:
            if re.search(pattern, modified, re.IGNORECASE):
                found_pii.append(f"mention:{pattern}")

        if found_pii:
            return (
                QualityGateResult(
                    gate=QualityGate.PII_SAFE,
                    passed=False,
                    message=f"PII detected and redacted: {found_pii}",
                    details={"pii_types": found_pii},
                ),
                modified,
                modifications,
            )

        return (
            QualityGateResult(
                gate=QualityGate.PII_SAFE,
                passed=True,
                message="No PII detected",
            ),
            modified,
            modifications,
        )

    def _check_complete(
        self,
        response: str,
        parsed: ParsedQuery,
        nova_response: NovaResponse,
    ) -> QualityGateResult:
        """Check if response includes all requested information.

        Args:
            response: Response text.
            parsed: Parsed query.
            nova_response: Full Nova response.

        Returns:
            QualityGateResult.
        """
        # If query asked for specific count and we have results
        if parsed.limit and nova_response.tool_results:
            # Check if we mentioned a count
            count_pattern = r"\b(\d+)\s*(?:customer|result|match|record)"
            if re.search(count_pattern, response, re.IGNORECASE):
                return QualityGateResult(
                    gate=QualityGate.COMPLETE,
                    passed=True,
                    message="Response includes result count",
                )

        # Basic completeness - response has substance
        if len(response.split()) < 5:
            return QualityGateResult(
                gate=QualityGate.COMPLETE,
                passed=False,
                message="Response seems incomplete (too short)",
            )

        return QualityGateResult(
            gate=QualityGate.COMPLETE,
            passed=True,
            message="Response appears complete",
        )

    def _check_coherent(self, response: str) -> QualityGateResult:
        """Check if response is well-formed.

        Args:
            response: Response text.

        Returns:
            QualityGateResult.
        """
        # Check for garbled text
        if re.search(r"[^\x00-\x7F]{5,}", response):
            return QualityGateResult(
                gate=QualityGate.COHERENT,
                passed=False,
                message="Response contains garbled text",
            )

        # Check for incomplete sentences (ending in...)
        if response.rstrip().endswith("...") and len(response) < 50:
            return QualityGateResult(
                gate=QualityGate.COHERENT,
                passed=False,
                message="Response appears truncated",
            )

        # Check for repeated content
        sentences = response.split(". ")
        if len(sentences) > 2:
            unique = set(s.strip().lower() for s in sentences)
            if len(unique) < len(sentences) * 0.7:
                return QualityGateResult(
                    gate=QualityGate.COHERENT,
                    passed=False,
                    message="Response contains repeated content",
                )

        return QualityGateResult(
            gate=QualityGate.COHERENT,
            passed=True,
            message="Response is well-formed",
        )

    def _check_on_topic(
        self,
        response: str,
        intent: IntentResult,
    ) -> QualityGateResult:
        """Check if response stays on topic.

        Args:
            response: Response text.
            intent: Intent classification.

        Returns:
            QualityGateResult.
        """
        response_lower = response.lower()

        # Check for off-topic indicators
        off_topic_phrases = [
            "i'm an ai",
            "as an ai",
            "i was created",
            "my training",
            "i don't have personal",
            "weather",
            "recipe",
            "joke",
        ]

        for phrase in off_topic_phrases:
            if phrase in response_lower:
                return QualityGateResult(
                    gate=QualityGate.ON_TOPIC,
                    passed=False,
                    message=f"Response contains off-topic content: '{phrase}'",
                )

        return QualityGateResult(
            gate=QualityGate.ON_TOPIC,
            passed=True,
            message="Response stays on topic",
        )

    def _check_confidence(self, ai_confidence: float) -> QualityGateResult:
        """Check if AI confidence meets threshold.

        Args:
            ai_confidence: Confidence score from NovaAgent.

        Returns:
            QualityGateResult.
        """
        threshold = 0.4

        if ai_confidence >= threshold:
            return QualityGateResult(
                gate=QualityGate.CONFIDENCE_MET,
                passed=True,
                message=f"AI confidence {ai_confidence:.2f} >= {threshold}",
            )

        return QualityGateResult(
            gate=QualityGate.CONFIDENCE_MET,
            passed=False,
            message=f"AI confidence {ai_confidence:.2f} < {threshold}",
        )

    def _determine_status(
        self,
        gates_passed: list[QualityGateResult],
        gates_failed: list[QualityGateResult],
        modifications: list[str],
        nova_response: NovaResponse,
    ) -> ResponseStatus:
        """Determine final response status.

        Args:
            gates_passed: Passed quality gates.
            gates_failed: Failed quality gates.
            modifications: Modifications made.
            nova_response: Original Nova response.

        Returns:
            ResponseStatus.
        """
        # Check for fallback model
        if nova_response.model_used == "fallback":
            return ResponseStatus.FALLBACK

        # All gates passed
        if not gates_failed:
            if modifications:
                return ResponseStatus.MODIFIED
            return ResponseStatus.APPROVED

        # Critical gates failed
        critical_gates = {QualityGate.PII_SAFE, QualityGate.RESPONSIVE, QualityGate.FACTUAL}
        critical_failed = [g for g in gates_failed if g.gate in critical_gates]

        if critical_failed:
            # PII was redacted - modified but ok
            if any(g.gate == QualityGate.PII_SAFE for g in critical_failed) and modifications:
                return ResponseStatus.MODIFIED
            return ResponseStatus.REJECTED

        # Non-critical failures - modified
        if modifications:
            return ResponseStatus.MODIFIED

        return ResponseStatus.APPROVED
