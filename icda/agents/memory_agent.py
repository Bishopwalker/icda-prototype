"""Memory Agent - Working memory for entity recall across queries.

Provides persistent memory within a session for:
- Remembering customers discussed ("that customer", "him")
- Tracking geographic focus ("that state", "there")
- Learning user preferences (detail level, limits)
- Resolving pronouns to entities
"""

import json
import logging
import re
import time
from typing import Any, TYPE_CHECKING

from .models import (
    MemoryEntity,
    MemoryContext,
    IntentResult,
)

if TYPE_CHECKING:
    from icda.cache import RedisCache

logger = logging.getLogger(__name__)

# Pronoun patterns that might reference previous entities
CUSTOMER_PRONOUNS = {
    "that customer", "this customer", "the customer",
    "that person", "this person", "the person",
    "them", "their", "they",
    "him", "her", "his", "hers",
    "that one", "this one", "the same one",
    "show me them again", "show them again",
}

LOCATION_PRONOUNS = {
    "that state", "this state", "the same state",
    "that city", "this city", "the same city",
    "there", "that area", "that region",
    "nearby", "around there",
}

REFERENCE_PRONOUNS = {
    "those", "these", "the same",
    "again", "more like that", "similar",
}


class MemoryAgent:
    """Agent for managing working memory within a session.

    Stores entities (customers, locations) and preferences in Redis,
    allowing natural references like "show me that customer again".
    """

    __slots__ = ("_cache", "_ttl", "_max_entities", "_fallback")

    # Memory configuration
    DEFAULT_TTL = 3600  # 1 hour (session lifetime)
    MAX_ENTITIES = 50   # LRU eviction after this

    def __init__(
        self,
        cache: "RedisCache | None" = None,
        ttl: int = DEFAULT_TTL,
        max_entities: int = MAX_ENTITIES,
    ):
        """Initialize MemoryAgent.

        Args:
            cache: Redis cache for persistence.
            ttl: Time-to-live in seconds.
            max_entities: Maximum entities per session.
        """
        self._cache = cache
        self._ttl = ttl
        self._max_entities = max_entities
        self._fallback: dict[str, list[MemoryEntity]] = {}

    @property
    def available(self) -> bool:
        """Check if memory agent is operational."""
        return True  # Always available (has fallback)

    def _key(self, session_id: str) -> str:
        """Generate Redis key for session memory."""
        return f"icda:memory:{session_id}"

    async def recall(
        self,
        session_id: str | None,
        query: str,
        intent: IntentResult,
    ) -> MemoryContext:
        """Recall relevant entities from memory.

        Args:
            session_id: Session identifier.
            query: Current query.
            intent: Intent classification.

        Returns:
            MemoryContext with recalled entities and resolved pronouns.
        """
        if not session_id:
            return MemoryContext(memory_signals=["no_session_id"])

        # Load entities from storage
        entities = await self._load_entities(session_id)
        if not entities:
            return MemoryContext(memory_signals=["empty_memory"])

        signals = []
        query_lower = query.lower()

        # Resolve pronouns to entities
        resolved_pronouns = self._resolve_pronouns(query_lower, entities)
        if resolved_pronouns:
            signals.append(f"resolved_{len(resolved_pronouns)}_pronouns")

        # Find active customer (most recently discussed)
        active_customer = self._find_active_customer(query_lower, entities)
        if active_customer:
            signals.append(f"active_customer:{active_customer.canonical_name}")

        # Find active location
        active_location = self._find_active_location(query_lower, entities)
        if active_location:
            signals.append(f"active_location:{active_location}")

        # Extract user preferences from memory
        user_preferences = self._extract_preferences(entities)

        # Calculate recall confidence
        confidence = self._calculate_confidence(
            entities, resolved_pronouns, active_customer
        )

        return MemoryContext(
            recalled_entities=entities,
            active_customer=active_customer,
            active_location=active_location,
            user_preferences=user_preferences,
            resolved_pronouns=resolved_pronouns,
            recall_confidence=confidence,
            memory_signals=signals,
        )

    async def remember(
        self,
        session_id: str | None,
        results: list[dict[str, Any]],
        response: str,
        query: str = "",
    ) -> None:
        """Store entities from results to memory.

        Args:
            session_id: Session identifier.
            results: Search results containing entities.
            response: Generated response.
            query: Original query.
        """
        if not session_id or not results:
            return

        # Load existing entities
        entities = await self._load_entities(session_id)
        now = time.time()

        # Extract new entities from results
        new_entities = self._extract_entities(results, now)

        # Merge with existing (update if exists, add if new)
        entity_map = {e.entity_id: e for e in entities}
        for new_entity in new_entities:
            if new_entity.entity_id in entity_map:
                # Update existing entity
                existing = entity_map[new_entity.entity_id]
                existing.last_accessed = now
                existing.mention_count += 1
                # Merge attributes
                existing.attributes.update(new_entity.attributes)
            else:
                # Add new entity
                entity_map[new_entity.entity_id] = new_entity

        # Extract location entity from query/response if present
        location_entity = self._extract_location_entity(query, response, now)
        if location_entity:
            entity_map[location_entity.entity_id] = location_entity

        # Convert back to list and prune
        entities = list(entity_map.values())
        entities = self._prune_memory(entities)

        # Save to storage
        await self._save_entities(session_id, entities)

    async def _load_entities(self, session_id: str) -> list[MemoryEntity]:
        """Load entities from storage."""
        try:
            if self._cache and self._cache.available:
                data = await self._cache.client.get(self._key(session_id))
                if data:
                    entities_data = json.loads(data)
                    return [MemoryEntity.from_dict(e) for e in entities_data]
            elif session_id in self._fallback:
                return self._fallback[session_id].copy()
        except Exception as e:
            logger.warning(f"Failed to load memory: {e}")

        return []

    async def _save_entities(
        self, session_id: str, entities: list[MemoryEntity]
    ) -> None:
        """Save entities to storage."""
        try:
            data = json.dumps([e.to_dict() for e in entities])
            if self._cache and self._cache.available:
                await self._cache.client.setex(
                    self._key(session_id), self._ttl, data
                )
            else:
                self._fallback[session_id] = entities
        except Exception as e:
            logger.warning(f"Failed to save memory: {e}")

    def _resolve_pronouns(
        self,
        query: str,
        entities: list[MemoryEntity],
    ) -> dict[str, str]:
        """Resolve pronouns in query to entity IDs.

        Args:
            query: Lowercase query string.
            entities: Available entities.

        Returns:
            Dict mapping pronoun to entity_id.
        """
        resolved = {}
        if not entities:
            return resolved

        # Sort by last_accessed (most recent first)
        sorted_entities = sorted(
            entities, key=lambda e: e.last_accessed, reverse=True
        )

        # Check for customer pronouns
        for pronoun in CUSTOMER_PRONOUNS:
            if pronoun in query:
                # Find most recent customer entity
                for entity in sorted_entities:
                    if entity.entity_type == "customer":
                        resolved[pronoun] = entity.entity_id
                        break

        # Check for location pronouns
        for pronoun in LOCATION_PRONOUNS:
            if pronoun in query:
                # Find most recent location entity
                for entity in sorted_entities:
                    if entity.entity_type == "location":
                        resolved[pronoun] = entity.entity_id
                        break

        # Check for general reference pronouns
        for pronoun in REFERENCE_PRONOUNS:
            if pronoun in query and pronoun not in resolved:
                # Use most recent entity of any type
                if sorted_entities:
                    resolved[pronoun] = sorted_entities[0].entity_id

        return resolved

    def _find_active_customer(
        self,
        query: str,
        entities: list[MemoryEntity],
    ) -> MemoryEntity | None:
        """Find the currently active customer from context.

        Args:
            query: Lowercase query.
            entities: Available entities.

        Returns:
            Most relevant customer entity or None.
        """
        customers = [e for e in entities if e.entity_type == "customer"]
        if not customers:
            return None

        # Check if query references a specific customer
        for customer in customers:
            # Check if CRID is mentioned
            if customer.entity_id.lower() in query:
                return customer
            # Check if name is mentioned
            if customer.canonical_name.lower() in query:
                return customer
            # Check aliases
            for alias in customer.aliases:
                if alias.lower() in query:
                    return customer

        # Check for pronoun references
        has_pronoun = any(p in query for p in CUSTOMER_PRONOUNS)
        if has_pronoun:
            # Return most recently accessed customer
            return max(customers, key=lambda c: c.last_accessed)

        return None

    def _find_active_location(
        self,
        query: str,
        entities: list[MemoryEntity],
    ) -> dict[str, str] | None:
        """Find active location from context.

        Args:
            query: Lowercase query.
            entities: Available entities.

        Returns:
            Location dict (state, city) or None.
        """
        locations = [e for e in entities if e.entity_type == "location"]
        if not locations:
            return None

        # Check for location pronoun references
        has_pronoun = any(p in query for p in LOCATION_PRONOUNS)
        if has_pronoun:
            # Return most recent location
            recent = max(locations, key=lambda l: l.last_accessed)
            return recent.attributes.copy()

        return None

    def _extract_preferences(
        self,
        entities: list[MemoryEntity],
    ) -> dict[str, Any]:
        """Extract user preferences from memory.

        Args:
            entities: All memory entities.

        Returns:
            Dict of inferred preferences.
        """
        preferences = {}

        # Find preference entities
        pref_entities = [e for e in entities if e.entity_type == "preference"]
        for pref in pref_entities:
            preferences.update(pref.attributes)

        return preferences

    def _extract_entities(
        self,
        results: list[dict[str, Any]],
        timestamp: float,
    ) -> list[MemoryEntity]:
        """Extract entities from search results.

        Args:
            results: Search results.
            timestamp: Current timestamp.

        Returns:
            List of new MemoryEntity objects.
        """
        entities = []

        for result in results[:5]:  # Only remember top 5
            crid = result.get("crid")
            if not crid:
                continue

            name = result.get("name", "Unknown")
            state = result.get("state", "")
            city = result.get("city", "")

            entity = MemoryEntity(
                entity_id=crid,
                entity_type="customer",
                canonical_name=name,
                aliases=[],
                attributes={
                    "state": state,
                    "city": city,
                    "zip": result.get("zip", ""),
                    "move_count": result.get("move_count", 0),
                    "status": result.get("status", ""),
                    "customer_type": result.get("customer_type", ""),
                },
                first_mentioned=timestamp,
                last_accessed=timestamp,
                mention_count=1,
                confidence=0.9,
            )
            entities.append(entity)

        return entities

    def _extract_location_entity(
        self,
        query: str,
        response: str,
        timestamp: float,
    ) -> MemoryEntity | None:
        """Extract location entity from query context.

        Args:
            query: Original query.
            response: Generated response.
            timestamp: Current timestamp.

        Returns:
            Location MemoryEntity or None.
        """
        # Simple state extraction from query
        state_pattern = r"\b([A-Z]{2})\b"
        states = re.findall(state_pattern, query.upper())

        if states:
            state = states[0]
            return MemoryEntity(
                entity_id=f"location:{state}",
                entity_type="location",
                canonical_name=state,
                aliases=[],
                attributes={"state": state},
                first_mentioned=timestamp,
                last_accessed=timestamp,
                mention_count=1,
                confidence=0.8,
            )

        return None

    def _prune_memory(
        self,
        entities: list[MemoryEntity],
    ) -> list[MemoryEntity]:
        """Prune memory using LRU eviction.

        Args:
            entities: Current entities.

        Returns:
            Pruned list of entities.
        """
        if len(entities) <= self._max_entities:
            return entities

        # Sort by last_accessed (oldest first)
        sorted_entities = sorted(entities, key=lambda e: e.last_accessed)

        # Keep the most recent MAX_ENTITIES
        return sorted_entities[-self._max_entities:]

    def _calculate_confidence(
        self,
        entities: list[MemoryEntity],
        resolved_pronouns: dict[str, str],
        active_customer: MemoryEntity | None,
    ) -> float:
        """Calculate overall recall confidence.

        Args:
            entities: Recalled entities.
            resolved_pronouns: Resolved pronouns.
            active_customer: Active customer if any.

        Returns:
            Confidence score (0.0 - 1.0).
        """
        if not entities:
            return 0.0

        confidence = 0.3  # Base confidence for having entities

        # Boost for resolved pronouns
        if resolved_pronouns:
            confidence += 0.2

        # Boost for active customer
        if active_customer:
            confidence += 0.3
            # Additional boost if high mention count
            if active_customer.mention_count > 2:
                confidence += 0.1

        # Cap at 1.0
        return min(confidence, 1.0)

    async def clear(self, session_id: str) -> None:
        """Clear memory for a session.

        Args:
            session_id: Session to clear.
        """
        try:
            if self._cache and self._cache.available:
                await self._cache.client.delete(self._key(session_id))
            else:
                self._fallback.pop(session_id, None)
        except Exception as e:
            logger.warning(f"Failed to clear memory: {e}")

    def get_stats(self) -> dict[str, Any]:
        """Get memory agent statistics."""
        return {
            "available": self.available,
            "ttl": self._ttl,
            "max_entities": self._max_entities,
            "fallback_sessions": len(self._fallback),
        }
