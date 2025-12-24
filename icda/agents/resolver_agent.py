"""Resolver Agent - Resolves entities and expands query scope.

This agent:
1. Validates extracted CRIDs exist in the database
2. Resolves ambiguous references
3. Expands scope for multi-state queries
4. Determines fallback strategies if resolution fails
"""

import logging
from typing import Any

from .models import ParsedQuery, QueryContext, ResolvedQuery

logger = logging.getLogger(__name__)


class ResolverAgent:
    """Resolves entities and prepares query for search.

    Follows the enforcer pattern - receives only the context it needs.
    """
    __slots__ = ("_db", "_vector_index", "_available")

    def __init__(self, db, vector_index=None):
        """Initialize ResolverAgent.

        Args:
            db: CustomerDB for validation.
            vector_index: Optional VectorIndex for semantic resolution.
        """
        self._db = db
        self._vector_index = vector_index
        self._available = True

    @property
    def available(self) -> bool:
        """Check if agent is available."""
        return self._available

    async def resolve(
        self,
        parsed: ParsedQuery,
        context: QueryContext,
    ) -> ResolvedQuery:
        """Resolve entities and expand scope.

        Args:
            parsed: Parsed query from ParserAgent.
            context: Context from ContextAgent.

        Returns:
            ResolvedQuery with resolved entities.
        """
        resolved_crids = []
        resolved_customers = None
        unresolved = []
        fallback_strategies = []
        expanded_scope = {}

        # CRITICAL: Validate requested state FIRST before determining fallbacks
        # This prevents hallucinated results for states not in database
        state_validation = self._validate_state(parsed)

        # Expand scope for multi-state or ambiguous queries
        expanded_scope = self._expand_scope(parsed, context)

        # Add state validation info to expanded_scope BEFORE determining fallbacks
        if state_validation:
            expanded_scope.update(state_validation)
            if not state_validation.get("state_valid", True):
                unresolved.append(f"state:{state_validation.get('requested_state')}")
                logger.debug("ResolverAgent: Invalid state detected - clearing fallback strategies")

        # Resolve CRIDs
        if parsed.entities.get("crids"):
            resolved_crids, unresolved_crids = await self._resolve_crids(
                parsed.entities["crids"]
            )
            unresolved.extend(unresolved_crids)

            # If CRIDs resolved, get customer data
            if resolved_crids:
                resolved_customers = await self._lookup_customers(resolved_crids)

        # CRITICAL FIX: Don't provide fallback strategies if state is invalid
        # This forces search agent to return "state not available" instead of random results
        if state_validation and not state_validation.get("state_valid", True):
            # No fallback strategies for invalid state - let search agent handle gracefully
            fallback_strategies = []
            logger.debug("ResolverAgent: No fallback strategies - state is invalid")
        else:
            # Determine fallback strategies based on what we have
            fallback_strategies = self._determine_fallbacks(parsed, resolved_crids)

        # Calculate resolution confidence
        confidence = self._calculate_confidence(
            parsed, resolved_crids, unresolved, fallback_strategies
        )

        return ResolvedQuery(
            resolved_crids=resolved_crids,
            resolved_customers=resolved_customers,
            expanded_scope=expanded_scope,
            fallback_strategies=fallback_strategies,
            resolution_confidence=confidence,
            unresolved_entities=unresolved,
        )

    def _validate_state(self, parsed: ParsedQuery) -> dict[str, Any] | None:
        """Validate requested state exists in database.

        Args:
            parsed: Parsed query with filters.

        Returns:
            Dict with validation info or None if no state filter.
        """
        requested_state = parsed.filters.get("state")
        logger.debug(f"ResolverAgent._validate_state: requested_state={requested_state}")
        if not requested_state:
            return None

        # Get available states from database
        available_states = set(self._db.by_state.keys())
        logger.debug(f"ResolverAgent._validate_state: available_states={available_states}")

        if requested_state.upper() in available_states:
            logger.debug(f"ResolverAgent._validate_state: state {requested_state} IS VALID")
            return {
                "state_valid": True,
                "requested_state": requested_state.upper(),
            }

        logger.debug(f"ResolverAgent._validate_state: state {requested_state} NOT IN DATABASE!")
        
        # State not found - provide helpful alternatives
        # Get states with customer counts, sorted by count descending
        state_counts = {
            state: len(customers) 
            for state, customers in self._db.by_state.items()
        }
        sorted_states = sorted(
            state_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # Map state codes to full names for better UX
        state_names = {
            "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
            "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
            "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
            "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
            "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
            "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
            "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
            "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
            "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
            "OR": "Oregon", "PA": "Pennsylvania", "PR": "Puerto Rico", "RI": "Rhode Island",
            "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
            "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington",
            "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington DC",
        }
        
        requested_name = state_names.get(requested_state.upper(), requested_state)
        
        return {
            "state_valid": False,
            "requested_state": requested_state.upper(),
            "requested_state_name": requested_name,
            "available_states": [s for s, _ in sorted_states],
            "available_states_with_counts": [
                {"code": s, "name": state_names.get(s, s), "count": c}
                for s, c in sorted_states
            ],
            "suggestion": f"{requested_name} is not in our database. We have customer data for {len(available_states)} states.",
        }

    async def _resolve_crids(self, crids: list[str]) -> tuple[list[str], list[str]]:
        """Validate CRIDs exist in database.

        Args:
            crids: List of CRIDs to validate.

        Returns:
            Tuple of (resolved_crids, unresolved_crids).
        """
        resolved = []
        unresolved = []

        for crid in crids:
            try:
                result = self._db.lookup(crid)
                # Database returns "data" key, not "customer"
                if result.get("success") and result.get("data"):
                    resolved.append(crid)
                else:
                    unresolved.append(crid)
            except Exception as e:
                logger.warning(f"Failed to validate CRID {crid}: {e}")
                unresolved.append(crid)

        return resolved, unresolved

    async def _lookup_customers(self, crids: list[str]) -> list[dict[str, Any]]:
        """Look up full customer records for CRIDs.

        Args:
            crids: List of validated CRIDs.

        Returns:
            List of customer records.
        """
        customers = []
        for crid in crids:
            try:
                result = self._db.lookup(crid)
                # Database returns "data" key, not "customer"
                if result.get("success") and result.get("data"):
                    customers.append(result["data"])
            except Exception as e:
                logger.warning(f"Failed to lookup customer {crid}: {e}")
        return customers

    def _determine_fallbacks(
        self,
        parsed: ParsedQuery,
        resolved_crids: list[str],
    ) -> list[str]:
        """Determine fallback search strategies.

        Args:
            parsed: Parsed query.
            resolved_crids: Successfully resolved CRIDs.

        Returns:
            List of fallback strategy names.
        """
        strategies = []

        # If we have CRIDs, direct lookup is primary
        if resolved_crids:
            return ["direct_lookup"]

        # Determine strategies based on available filters
        has_state = bool(parsed.filters.get("state"))
        has_city = bool(parsed.filters.get("city"))
        has_moves = bool(parsed.filters.get("min_move_count"))
        has_entities = bool(parsed.entities.get("names"))

        # Primary strategy based on filters
        if has_state or has_city or has_moves:
            strategies.append("filtered_search")

        # Fuzzy search for potential typos
        if has_entities or has_city:
            strategies.append("fuzzy_search")

        # Semantic search if complex query
        if self._vector_index and getattr(self._vector_index, "available", False):
            if len(parsed.original_query.split()) > 5:
                strategies.append("semantic_search")

        # Hybrid search for best results
        if self._vector_index and getattr(self._vector_index, "available", False):
            strategies.append("hybrid_search")

        # Always have basic search as last resort
        if "filtered_search" not in strategies:
            strategies.append("basic_search")

        return strategies

    def _expand_scope(
        self,
        parsed: ParsedQuery,
        context: QueryContext,
    ) -> dict[str, Any]:
        """Expand query scope for comprehensive results.

        Args:
            parsed: Parsed query.
            context: Session context.

        Returns:
            Dict with scope expansion info.
        """
        scope = {
            "multi_state": False,
            "additional_states": [],
            "geographic_expansion": None,
        }

        # Check if query mentions multiple states
        states = parsed.entities.get("states", [])
        if len(states) > 1:
            scope["multi_state"] = True

        # Check for implicit multi-state (e.g., "west coast")
        query_lower = parsed.original_query.lower()
        regional_expansions = {
            "west coast": ["CA", "OR", "WA"],
            "east coast": ["NY", "NJ", "MA", "CT", "RI", "ME", "NH", "VT"],
            "southwest": ["AZ", "NM", "TX", "NV"],
            "midwest": ["OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO"],
            "south": ["TX", "FL", "GA", "NC", "SC", "TN", "AL", "MS", "LA"],
            "northeast": ["NY", "NJ", "PA", "MA", "CT"],
        }

        for region, region_states in regional_expansions.items():
            if region in query_lower:
                scope["multi_state"] = True
                scope["additional_states"] = region_states
                scope["geographic_expansion"] = region
                break

        # No explicit state - might need multi-state search
        if not states and not scope["multi_state"]:
            # If context has a state, use it
            if context.geographic_context.get("state"):
                pass  # Single state from context
            else:
                # Consider common states for broader search
                scope["additional_states"] = ["CA", "TX", "FL", "NY", "NV"]

        return scope

    def _calculate_confidence(
        self,
        parsed: ParsedQuery,
        resolved_crids: list[str],
        unresolved: list[str],
        fallbacks: list[str],
    ) -> float:
        """Calculate resolution confidence.

        Args:
            parsed: Parsed query.
            resolved_crids: Successfully resolved CRIDs.
            unresolved: Unresolved entities.
            fallbacks: Available fallback strategies.

        Returns:
            Confidence score (0.0 - 1.0).
        """
        confidence = 0.5  # Base

        # High confidence if CRIDs resolved
        if resolved_crids:
            confidence = 0.95
            # Reduce if some unresolved
            if unresolved:
                confidence -= 0.1 * len(unresolved) / (len(resolved_crids) + len(unresolved))
            return round(confidence, 3)

        # Good confidence if we have filters
        if parsed.filters:
            confidence += 0.2

        # Good confidence if we have entities
        if any(parsed.entities.get(k) for k in ["states", "cities", "names"]):
            confidence += 0.15

        # Boost if we have multiple fallback strategies
        if len(fallbacks) >= 2:
            confidence += 0.1

        # Reduce if we have unresolved entities
        if unresolved:
            confidence -= 0.1

        return max(0.1, min(1.0, round(confidence, 3)))
