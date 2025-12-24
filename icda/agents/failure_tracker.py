"""Failure Tracker - Tracks failed queries and manages strategy escalation.

This module tracks queries that fail quality gates (especially FACTUAL and RESPONSIVE),
remembers failed query patterns per session, and determines which strategies to skip
on retry. This prevents the system from giving repeat wrong answers.

Escalation order: filtered_search -> fuzzy_search -> semantic_search -> hybrid_search -> basic_search
"""

import hashlib
import json
import logging
import time
from typing import Any, TYPE_CHECKING

from .models import (
    FailureRecord,
    EscalationContext,
    QualityGate,
    EnforcedResponse,
    ResponseStatus,
)

if TYPE_CHECKING:
    from icda.cache import RedisCache

logger = logging.getLogger(__name__)


class FailureTracker:
    """Tracks failed queries and manages strategy escalation.

    Prevents repeat wrong answers by tracking which queries failed and
    which strategies were tried, then recommending alternative strategies
    on retry.
    """

    __slots__ = ("_cache", "_ttl", "_max_failures", "_fallback")

    # Configuration
    DEFAULT_TTL = 1800  # 30 minutes
    MAX_FAILURES_PER_SESSION = 20

    # Strategy escalation order (skip previously failed ones)
    ESCALATION_ORDER: list[str] = [
        "filtered_search",
        "fuzzy_search",
        "semantic_search",
        "hybrid_search",
        "basic_search",
    ]

    # Critical gates that trigger escalation
    ESCALATION_TRIGGERS: set[QualityGate] = {
        QualityGate.FACTUAL,
        QualityGate.RESPONSIVE,
        QualityGate.COMPLETE,
    }

    # User-friendly escalation messages by level
    ESCALATION_MESSAGES: dict[int, str] = {
        1: "Trying a different search approach...",
        2: "Escalating to semantic search for better results...",
        3: "Trying hybrid search to find matches...",
        4: "Using broadest search strategy available...",
    }

    def __init__(
        self,
        cache: "RedisCache | None" = None,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        """Initialize the failure tracker.

        Args:
            cache: Optional Redis cache for persistent storage.
            ttl: Time-to-live for failure records in seconds.
        """
        self._cache = cache
        self._ttl = ttl
        self._fallback: dict[str, dict[str, FailureRecord]] = {}

    @property
    def available(self) -> bool:
        """Check if tracker is available (always true, has fallback)."""
        return True

    def _key(self, session_id: str) -> str:
        """Generate Redis key for session failures.

        Args:
            session_id: Session identifier.

        Returns:
            Redis key string.
        """
        return f"icda:failures:{session_id}"

    def _hash_query(self, query: str) -> str:
        """Create a hash of normalized query for matching.

        Removes common stop words and normalizes the query to improve
        matching of semantically similar queries.

        Args:
            query: Original query text.

        Returns:
            16-character hash string.
        """
        normalized = query.lower().strip()

        # Remove common stop words for better matching
        stop_words = {
            "the", "a", "an", "show", "me", "find", "get", "list",
            "please", "can", "you", "what", "are", "is", "all", "for",
        }
        words = [w for w in normalized.split() if w not in stop_words]
        key = " ".join(sorted(words))

        return hashlib.md5(key.encode()).hexdigest()[:16]

    async def check_for_retry(
        self,
        session_id: str | None,
        query: str,
    ) -> EscalationContext:
        """Check if this query is a retry of a failed query.

        Args:
            session_id: Session identifier.
            query: Current query text.

        Returns:
            EscalationContext with retry info and recommended strategies.
        """
        if not session_id:
            return EscalationContext()

        query_hash = self._hash_query(query)
        failures = await self._load_failures(session_id)

        if query_hash not in failures:
            return EscalationContext()

        failure = failures[query_hash]

        # Determine escalation level based on failure count
        level = min(failure.failure_count, len(self.ESCALATION_ORDER))

        # Get strategies to exclude (previously failed)
        excluded = failure.failed_strategies.copy()

        # Determine recommended strategies (not in excluded list)
        recommended = [
            s for s in self.ESCALATION_ORDER
            if s not in excluded
        ]

        # Generate user message
        message = self.ESCALATION_MESSAGES.get(level, "Trying alternative approach...")

        logger.info(
            f"Retry detected for query '{query[:30]}...': "
            f"level={level}, excluded={excluded}"
        )

        return EscalationContext(
            is_retry=True,
            previous_failures=[failure],
            excluded_strategies=excluded,
            escalation_level=level,
            user_message=message,
            recommended_strategies=recommended,
        )

    async def record_failure(
        self,
        session_id: str | None,
        query: str,
        enforced: EnforcedResponse,
        strategies_tried: list[str],
    ) -> None:
        """Record a query failure for future reference.

        Args:
            session_id: Session identifier.
            query: Original query text.
            enforced: Enforced response with gate results.
            strategies_tried: Strategies that were attempted.
        """
        if not session_id:
            return

        # Only track if critical gates failed
        failed_gates = [
            g.gate for g in enforced.gates_failed
            if g.gate in self.ESCALATION_TRIGGERS
        ]

        if not failed_gates:
            logger.debug("No critical gate failures - not tracking")
            return  # No critical failures, don't track

        query_hash = self._hash_query(query)
        failures = await self._load_failures(session_id)
        now = time.time()

        if query_hash in failures:
            # Update existing failure record
            record = failures[query_hash]
            record.failure_count += 1
            record.last_attempt = now
            record.failed_strategies = list(
                set(record.failed_strategies) | set(strategies_tried)
            )
            record.failed_gates = list(
                set(record.failed_gates) | set(failed_gates)
            )
            record.last_response = enforced.final_response
            logger.info(
                f"Updated failure record for '{query[:30]}...': "
                f"count={record.failure_count}"
            )
        else:
            # Create new failure record
            failures[query_hash] = FailureRecord(
                query_hash=query_hash,
                original_query=query,
                failed_gates=failed_gates,
                failed_strategies=strategies_tried,
                last_response=enforced.final_response,
                failure_count=1,
                created_at=now,
                last_attempt=now,
                session_id=session_id,
            )
            logger.info(f"Created failure record for '{query[:30]}...'")

        # Prune old failures if too many
        if len(failures) > self.MAX_FAILURES_PER_SESSION:
            # Remove oldest failures
            sorted_failures = sorted(
                failures.items(),
                key=lambda x: x[1].last_attempt,
            )
            failures = dict(sorted_failures[-self.MAX_FAILURES_PER_SESSION:])
            logger.debug(f"Pruned failures to {self.MAX_FAILURES_PER_SESSION}")

        await self._save_failures(session_id, failures)

    async def clear_on_success(
        self,
        session_id: str | None,
        query: str,
    ) -> None:
        """Clear failure tracking for a query after successful response.

        Args:
            session_id: Session identifier.
            query: Query that succeeded.
        """
        if not session_id:
            return

        query_hash = self._hash_query(query)
        failures = await self._load_failures(session_id)

        if query_hash in failures:
            del failures[query_hash]
            await self._save_failures(session_id, failures)
            logger.info(f"Cleared failure tracking for successful query")

    async def clear_session(self, session_id: str) -> None:
        """Clear all failure records for a session.

        Args:
            session_id: Session identifier.
        """
        try:
            if self._cache and self._cache.available:
                await self._cache.client.delete(self._key(session_id))
            elif session_id in self._fallback:
                del self._fallback[session_id]
            logger.info(f"Cleared all failures for session {session_id}")
        except Exception as e:
            logger.warning(f"Failed to clear session failures: {e}")

    async def _load_failures(
        self,
        session_id: str,
    ) -> dict[str, FailureRecord]:
        """Load failure records from storage.

        Args:
            session_id: Session identifier.

        Returns:
            Dictionary of query_hash -> FailureRecord.
        """
        try:
            if self._cache and self._cache.available:
                data = await self._cache.client.get(self._key(session_id))
                if data:
                    records = json.loads(data)
                    return {
                        k: FailureRecord.from_dict(v)
                        for k, v in records.items()
                    }
            elif session_id in self._fallback:
                return self._fallback[session_id].copy()
        except Exception as e:
            logger.warning(f"Failed to load failures: {e}")

        return {}

    async def _save_failures(
        self,
        session_id: str,
        failures: dict[str, FailureRecord],
    ) -> None:
        """Save failure records to storage.

        Args:
            session_id: Session identifier.
            failures: Dictionary of failure records.
        """
        try:
            data = json.dumps({
                k: v.to_dict() for k, v in failures.items()
            })
            if self._cache and self._cache.available:
                await self._cache.client.setex(
                    self._key(session_id), self._ttl, data
                )
            else:
                self._fallback[session_id] = failures
        except Exception as e:
            logger.warning(f"Failed to save failures: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get failure tracker statistics.

        Returns:
            Dictionary with stats about the tracker.
        """
        return {
            "available": self.available,
            "ttl": self._ttl,
            "max_failures_per_session": self.MAX_FAILURES_PER_SESSION,
            "fallback_sessions": len(self._fallback),
            "escalation_order": self.ESCALATION_ORDER,
            "escalation_triggers": [g.value for g in self.ESCALATION_TRIGGERS],
        }


def apply_escalation(
    base_strategies: list[str],
    escalation: EscalationContext,
) -> list[str]:
    """Apply escalation context to strategy list.

    Removes excluded strategies and reorders based on escalation level.
    This is a utility function that can be used by SearchAgent.

    Args:
        base_strategies: Base strategies from resolver.
        escalation: Escalation context from failure tracker.

    Returns:
        Filtered and reordered strategy list.
    """
    if not escalation.is_retry:
        return base_strategies

    # Remove excluded strategies
    filtered = [
        s for s in base_strategies
        if s not in escalation.excluded_strategies
    ]

    # If we have recommended strategies, use that order
    if escalation.recommended_strategies:
        # Prioritize recommended strategies
        result = []
        for s in escalation.recommended_strategies:
            if s in filtered:
                result.append(s)
        # Add any remaining strategies
        for s in filtered:
            if s not in result:
                result.append(s)
        return result

    return filtered
