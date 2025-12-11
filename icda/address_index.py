"""Known address index for verification lookups.

This module provides an in-memory index of known addresses from customer
data, enabling fast lookups and fuzzy matching for address verification.
"""

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any

from icda.address_models import ParsedAddress
from icda.address_normalizer import (
    AddressNormalizer,
    normalize_state,
    normalize_street_type,
    STREET_TYPES,
)


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IndexedAddress:
    """Address stored in the index with metadata.

    Attributes:
        parsed: Structured address data.
        customer_id: Associated customer ID (CRID).
        source: Where this address came from.
        normalized_key: Pre-computed lookup key.
    """

    parsed: ParsedAddress
    customer_id: str
    source: str  # "current" or "history"
    normalized_key: str = ""

    def __post_init__(self):
        """Compute normalized key after initialization."""
        if not self.normalized_key:
            self.normalized_key = self._compute_key()

    def _compute_key(self) -> str:
        """Compute normalized lookup key."""
        parts = []
        if self.parsed.street_number:
            parts.append(self.parsed.street_number.lower())
        if self.parsed.street_name:
            # Normalize street name - remove common variations
            name = self.parsed.street_name.lower()
            # Remove directional prefixes for key
            name = re.sub(r"^(n|s|e|w|ne|nw|se|sw)\s+", "", name)
            parts.append(name)
        if self.parsed.zip_code:
            parts.append(self.parsed.zip_code)
        return "|".join(parts)


@dataclass(slots=True)
class MatchResult:
    """Result of an address match lookup.

    Attributes:
        address: The matched address.
        score: Similarity score (0.0 - 1.0).
        match_type: How the match was found.
        customer_id: Associated customer ID.
    """

    address: IndexedAddress
    score: float
    match_type: str  # "exact", "fuzzy_street", "fuzzy_zip", etc.
    customer_id: str


class AddressIndex:
    """In-memory index of known addresses for fast lookup.

    Indexes addresses from customer data with multiple lookup strategies:
    - Exact match by normalized key
    - By ZIP code (find all addresses in a ZIP)
    - By street name (fuzzy matching)
    - By city/state combination
    """

    def __init__(self):
        """Initialize empty address index."""
        # Primary index: normalized_key -> list of IndexedAddress
        self._by_key: dict[str, list[IndexedAddress]] = defaultdict(list)

        # Secondary indexes for partial matching
        self._by_zip: dict[str, list[IndexedAddress]] = defaultdict(list)
        self._by_state: dict[str, list[IndexedAddress]] = defaultdict(list)
        self._by_city_state: dict[str, list[IndexedAddress]] = defaultdict(list)
        self._by_street_name: dict[str, list[IndexedAddress]] = defaultdict(list)

        # Street name variations within ZIP codes
        # zip -> {normalized_street_name -> [full street names]}
        self._street_variants: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

        self._total_addresses = 0
        self._indexed = False

    @property
    def total_addresses(self) -> int:
        """Return total number of indexed addresses."""
        return self._total_addresses

    @property
    def is_indexed(self) -> bool:
        """Return whether index has been built."""
        return self._indexed

    def build_from_customers(self, customers: list[dict[str, Any]]) -> int:
        """Build index from customer data.

        Args:
            customers: List of customer records with address fields.

        Returns:
            Number of addresses indexed.
        """
        count = 0

        for customer in customers:
            customer_id = customer.get("crid", "")

            # Index current address
            if current := self._extract_address(customer):
                self._add_address(current, customer_id, "current")
                count += 1

            # Index move history addresses
            for move in customer.get("move_history", []):
                # To address
                if to_addr := self._extract_move_address(move, "to"):
                    self._add_address(to_addr, customer_id, "history")
                    count += 1
                # From address
                if from_addr := self._extract_move_address(move, "from"):
                    self._add_address(from_addr, customer_id, "history")
                    count += 1

        self._total_addresses = count
        self._indexed = True
        logger.info(f"AddressIndex built with {count} addresses")
        return count

    def _extract_address(self, customer: dict[str, Any]) -> ParsedAddress | None:
        """Extract ParsedAddress from customer record."""
        address = customer.get("address")
        if not address:
            return None

        return ParsedAddress(
            raw=f"{address}, {customer.get('city', '')}, {customer.get('state', '')} {customer.get('zip', '')}",
            street_number=self._extract_street_number(address),
            street_name=self._extract_street_name(address),
            street_type=self._extract_street_type(address),
            city=customer.get("city"),
            state=customer.get("state"),
            zip_code=customer.get("zip"),
        )

    def _extract_move_address(
        self,
        move: dict[str, Any],
        prefix: str,
    ) -> ParsedAddress | None:
        """Extract ParsedAddress from move history entry."""
        address = move.get(f"{prefix}_address")
        if not address:
            return None

        city = move.get("city", "")
        state = move.get("state", "")
        zip_code = move.get("zip", "")

        return ParsedAddress(
            raw=f"{address}, {city}, {state} {zip_code}",
            street_number=self._extract_street_number(address),
            street_name=self._extract_street_name(address),
            street_type=self._extract_street_type(address),
            city=city,
            state=state,
            zip_code=zip_code,
        )

    def _extract_street_number(self, address: str) -> str | None:
        """Extract street number from address string."""
        match = re.match(r"^(\d+[A-Za-z]?)\s+", address)
        return match.group(1) if match else None

    def _extract_street_name(self, address: str) -> str | None:
        """Extract street name from address string."""
        # Remove street number
        without_number = re.sub(r"^\d+[A-Za-z]?\s+", "", address)
        # Remove street type at end
        words = without_number.split()
        if words and words[-1].lower().rstrip(".") in STREET_TYPES:
            return " ".join(words[:-1])
        return without_number if without_number else None

    def _extract_street_type(self, address: str) -> str | None:
        """Extract street type from address string."""
        words = address.split()
        if words:
            last = words[-1].lower().rstrip(".")
            if last in STREET_TYPES:
                return STREET_TYPES[last]
        return None

    def _add_address(
        self,
        parsed: ParsedAddress,
        customer_id: str,
        source: str,
    ) -> None:
        """Add address to all indexes."""
        indexed = IndexedAddress(
            parsed=parsed,
            customer_id=customer_id,
            source=source,
        )

        # Primary key index
        if indexed.normalized_key:
            self._by_key[indexed.normalized_key].append(indexed)

        # ZIP index
        if parsed.zip_code:
            self._by_zip[parsed.zip_code].append(indexed)

            # Track street name variants within ZIP
            if parsed.street_name:
                normalized_name = self._normalize_street_name(parsed.street_name)
                full_name = parsed.street_name
                if parsed.street_type:
                    full_name += f" {parsed.street_type}"
                self._street_variants[parsed.zip_code][normalized_name].add(full_name)

        # State index
        if parsed.state:
            self._by_state[parsed.state.upper()].append(indexed)

        # City+State index
        if parsed.city and parsed.state:
            key = f"{parsed.city.lower()}|{parsed.state.upper()}"
            self._by_city_state[key].append(indexed)

        # Street name index (normalized)
        if parsed.street_name:
            normalized = self._normalize_street_name(parsed.street_name)
            self._by_street_name[normalized].append(indexed)

    def _normalize_street_name(self, name: str) -> str:
        """Normalize street name for fuzzy matching."""
        name = name.lower()
        # Remove common words
        name = re.sub(r"\b(the|north|south|east|west|n|s|e|w)\b", "", name)
        # Remove extra spaces
        name = re.sub(r"\s+", " ", name).strip()
        return name

    def lookup_exact(self, parsed: ParsedAddress) -> list[MatchResult]:
        """Look up exact matches for an address.

        Args:
            parsed: Parsed address to look up.

        Returns:
            List of exact matches.
        """
        key = self._compute_lookup_key(parsed)
        results = []

        for indexed in self._by_key.get(key, []):
            results.append(MatchResult(
                address=indexed,
                score=1.0,
                match_type="exact",
                customer_id=indexed.customer_id,
            ))

        return results

    def lookup_by_zip(self, zip_code: str) -> list[IndexedAddress]:
        """Get all addresses in a ZIP code.

        Args:
            zip_code: 5-digit ZIP code.

        Returns:
            List of addresses in that ZIP.
        """
        return self._by_zip.get(zip_code, [])

    def lookup_street_in_zip(
        self,
        partial_street: str,
        zip_code: str,
        threshold: float = 0.6,
    ) -> list[MatchResult]:
        """Find streets in a ZIP code matching a partial name.

        This is the key method for completing partial addresses like
        "101 turkey" in ZIP 22222 -> "101 Turkey Run".

        Args:
            partial_street: Partial or misspelled street name.
            zip_code: ZIP code to search within.
            threshold: Minimum similarity score (0.0 - 1.0).

        Returns:
            List of matching addresses sorted by score.
        """
        results: list[MatchResult] = []
        partial_normalized = self._normalize_street_name(partial_street)

        # Get all street variants in this ZIP
        variants = self._street_variants.get(zip_code, {})

        for normalized_name, full_names in variants.items():
            # Check if partial matches this street
            score = self._fuzzy_match_score(partial_normalized, normalized_name)

            if score >= threshold:
                # Find addresses with this street name
                for indexed in self._by_zip.get(zip_code, []):
                    if indexed.parsed.street_name:
                        indexed_normalized = self._normalize_street_name(
                            indexed.parsed.street_name
                        )
                        if indexed_normalized == normalized_name:
                            results.append(MatchResult(
                                address=indexed,
                                score=score,
                                match_type="fuzzy_street",
                                customer_id=indexed.customer_id,
                            ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def lookup_fuzzy(
        self,
        parsed: ParsedAddress,
        threshold: float = 0.6,
    ) -> list[MatchResult]:
        """Perform fuzzy matching on an address.

        Args:
            parsed: Parsed address to match.
            threshold: Minimum similarity score.

        Returns:
            List of fuzzy matches sorted by score.
        """
        results: list[MatchResult] = []

        # Strategy 1: If we have ZIP, search within ZIP
        if parsed.zip_code:
            zip_addresses = self._by_zip.get(parsed.zip_code, [])
            for indexed in zip_addresses:
                score = self._compute_similarity(parsed, indexed.parsed)
                if score >= threshold:
                    results.append(MatchResult(
                        address=indexed,
                        score=score,
                        match_type="fuzzy_zip",
                        customer_id=indexed.customer_id,
                    ))

        # Strategy 2: If we have city/state, search in that area
        elif parsed.city and parsed.state:
            key = f"{parsed.city.lower()}|{parsed.state.upper()}"
            city_addresses = self._by_city_state.get(key, [])
            for indexed in city_addresses:
                score = self._compute_similarity(parsed, indexed.parsed)
                if score >= threshold:
                    results.append(MatchResult(
                        address=indexed,
                        score=score,
                        match_type="fuzzy_city",
                        customer_id=indexed.customer_id,
                    ))

        # Strategy 3: Match by street name across all addresses
        if parsed.street_name:
            normalized = self._normalize_street_name(parsed.street_name)
            street_addresses = self._by_street_name.get(normalized, [])
            for indexed in street_addresses:
                # Skip if already matched by ZIP or city
                if any(r.address == indexed for r in results):
                    continue
                score = self._compute_similarity(parsed, indexed.parsed)
                if score >= threshold:
                    results.append(MatchResult(
                        address=indexed,
                        score=score,
                        match_type="fuzzy_street",
                        customer_id=indexed.customer_id,
                    ))

        # Sort by score descending and deduplicate
        results.sort(key=lambda r: r.score, reverse=True)
        return results

    def get_street_suggestions(
        self,
        partial: str,
        zip_code: str,
        limit: int = 5,
    ) -> list[str]:
        """Get street name suggestions for autocomplete.

        Args:
            partial: Partial street name typed by user.
            zip_code: ZIP code context.
            limit: Maximum suggestions to return.

        Returns:
            List of complete street names.
        """
        suggestions: list[tuple[float, str]] = []
        partial_lower = partial.lower()

        variants = self._street_variants.get(zip_code, {})
        for normalized, full_names in variants.items():
            # Check prefix match first (highest priority)
            if normalized.startswith(partial_lower):
                for full in full_names:
                    suggestions.append((1.0, full))
            # Then check contains
            elif partial_lower in normalized:
                for full in full_names:
                    suggestions.append((0.8, full))
            # Finally fuzzy match
            else:
                score = self._fuzzy_match_score(partial_lower, normalized)
                if score > 0.5:
                    for full in full_names:
                        suggestions.append((score, full))

        # Sort by score and deduplicate
        suggestions.sort(key=lambda x: x[0], reverse=True)
        seen: set[str] = set()
        result: list[str] = []
        for _, name in suggestions:
            if name not in seen:
                seen.add(name)
                result.append(name)
                if len(result) >= limit:
                    break

        return result

    def _compute_lookup_key(self, parsed: ParsedAddress) -> str:
        """Compute lookup key for a parsed address."""
        parts = []
        if parsed.street_number:
            parts.append(parsed.street_number.lower())
        if parsed.street_name:
            name = parsed.street_name.lower()
            name = re.sub(r"^(n|s|e|w|ne|nw|se|sw)\s+", "", name)
            parts.append(name)
        if parsed.zip_code:
            parts.append(parsed.zip_code)
        return "|".join(parts)

    def _compute_similarity(
        self,
        addr1: ParsedAddress,
        addr2: ParsedAddress,
    ) -> float:
        """Compute similarity score between two addresses."""
        scores: list[float] = []
        weights: list[float] = []

        # Street number (exact match required for high score)
        if addr1.street_number and addr2.street_number:
            if addr1.street_number.lower() == addr2.street_number.lower():
                scores.append(1.0)
            else:
                scores.append(0.0)
            weights.append(0.3)

        # Street name (fuzzy match)
        if addr1.street_name and addr2.street_name:
            name_score = self._fuzzy_match_score(
                self._normalize_street_name(addr1.street_name),
                self._normalize_street_name(addr2.street_name),
            )
            scores.append(name_score)
            weights.append(0.3)

        # ZIP code (exact match)
        if addr1.zip_code and addr2.zip_code:
            if addr1.zip_code == addr2.zip_code:
                scores.append(1.0)
            else:
                scores.append(0.0)
            weights.append(0.2)

        # City (fuzzy match)
        if addr1.city and addr2.city:
            city_score = self._fuzzy_match_score(
                addr1.city.lower(),
                addr2.city.lower(),
            )
            scores.append(city_score)
            weights.append(0.1)

        # State (exact match)
        if addr1.state and addr2.state:
            if addr1.state.upper() == addr2.state.upper():
                scores.append(1.0)
            else:
                scores.append(0.0)
            weights.append(0.1)

        if not scores:
            return 0.0

        # Weighted average
        total_weight = sum(weights)
        if total_weight == 0:
            return 0.0
        return sum(s * w for s, w in zip(scores, weights)) / total_weight

    def _fuzzy_match_score(self, s1: str, s2: str) -> float:
        """Compute fuzzy match score between two strings."""
        return SequenceMatcher(None, s1, s2).ratio()

    def stats(self) -> dict[str, Any]:
        """Return index statistics."""
        return {
            "total_addresses": self._total_addresses,
            "unique_zips": len(self._by_zip),
            "unique_states": len(self._by_state),
            "unique_cities": len(self._by_city_state),
            "unique_streets": len(self._by_street_name),
            "indexed": self._indexed,
        }
