"""Known address index for verification lookups.

This module provides an in-memory index of known addresses from customer
data, enabling fast lookups and fuzzy matching for address verification.

Matching algorithms:
- Exact match by normalized key
- Levenshtein edit distance for typo tolerance
- Soundex phonetic matching for sound-alike errors
- SequenceMatcher for subsequence similarity
- Adaptive thresholds per component type
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


# =============================================================================
# Advanced Matching Algorithms
# =============================================================================

def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings.

    Edit distance is the minimum number of single-character edits
    (insertions, deletions, substitutions) to transform s1 into s2.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Edit distance (0 = identical).
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Compute Levenshtein similarity as a ratio (0.0 - 1.0).

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Similarity ratio (1.0 = identical).
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0

    max_len = max(len(s1), len(s2))
    distance = levenshtein_distance(s1, s2)
    return 1.0 - (distance / max_len)


def damerau_levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Damerau-Levenshtein distance (includes transpositions).

    This handles adjacent character swaps (common typo: "teh" -> "the").

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Edit distance including transpositions.
    """
    len1, len2 = len(s1), len(s2)

    # Create distance matrix
    d = [[0] * (len2 + 1) for _ in range(len1 + 1)]

    for i in range(len1 + 1):
        d[i][0] = i
    for j in range(len2 + 1):
        d[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            d[i][j] = min(
                d[i-1][j] + 1,      # Deletion
                d[i][j-1] + 1,      # Insertion
                d[i-1][j-1] + cost  # Substitution
            )
            # Transposition
            if i > 1 and j > 1 and s1[i-1] == s2[j-2] and s1[i-2] == s2[j-1]:
                d[i][j] = min(d[i][j], d[i-2][j-2] + cost)

    return d[len1][len2]


def soundex(s: str) -> str:
    """Compute Soundex phonetic code for a string.

    Soundex encodes words by their sound, so "Smith" and "Smyth"
    produce the same code.

    Args:
        s: String to encode.

    Returns:
        4-character Soundex code (letter + 3 digits).
    """
    if not s:
        return "0000"

    # Normalize
    s = s.upper()
    s = re.sub(r'[^A-Z]', '', s)

    if not s:
        return "0000"

    # Keep first letter
    first_letter = s[0]

    # Soundex mapping
    mapping = {
        'B': '1', 'F': '1', 'P': '1', 'V': '1',
        'C': '2', 'G': '2', 'J': '2', 'K': '2', 'Q': '2', 'S': '2', 'X': '2', 'Z': '2',
        'D': '3', 'T': '3',
        'L': '4',
        'M': '5', 'N': '5',
        'R': '6',
        # A, E, I, O, U, H, W, Y are dropped
    }

    # Convert to digits
    coded = first_letter
    prev_code = mapping.get(first_letter, '0')

    for char in s[1:]:
        code = mapping.get(char, '0')
        if code != '0' and code != prev_code:
            coded += code
            if len(coded) == 4:
                break
        prev_code = code if code != '0' else prev_code

    # Pad with zeros
    return (coded + '0000')[:4]


def metaphone_simple(s: str) -> str:
    """Compute simplified Metaphone phonetic code.

    Metaphone is more accurate than Soundex for English pronunciation.
    This is a simplified implementation for common address terms.

    Args:
        s: String to encode.

    Returns:
        Metaphone code string.
    """
    if not s:
        return ""

    s = s.upper()
    s = re.sub(r'[^A-Z]', '', s)

    if not s:
        return ""

    # Common transformations
    transformations = [
        (r'^KN', 'N'),
        (r'^GN', 'N'),
        (r'^PN', 'N'),
        (r'^AE', 'E'),
        (r'^WR', 'R'),
        (r'^WH', 'W'),
        (r'MB$', 'M'),
        (r'PH', 'F'),
        (r'TCH', 'CH'),
        (r'GH', ''),
        (r'GN', 'N'),
        (r'KN', 'N'),
        (r'CK', 'K'),
        (r'SCH', 'SK'),
        (r'SH', 'X'),
        (r'TH', '0'),  # 0 represents 'th' sound
        (r'DG', 'J'),
        (r'C(?=[IEY])', 'S'),
        (r'C', 'K'),
        (r'Q', 'K'),
        (r'X', 'KS'),
        (r'Z', 'S'),
        (r'[AEIOU]', ''),  # Drop vowels except at start
    ]

    # Keep first character if vowel
    first = s[0] if s[0] in 'AEIOU' else ''

    for pattern, replacement in transformations:
        s = re.sub(pattern, replacement, s)

    # Remove duplicate adjacent letters
    result = first
    for char in s:
        if not result or char != result[-1]:
            result += char

    return result[:6]  # Limit length


def phonetic_match(s1: str, s2: str) -> float:
    """Compute phonetic similarity using both Soundex and Metaphone.

    Args:
        s1: First string.
        s2: Second string.

    Returns:
        Phonetic similarity score (0.0 - 1.0).
    """
    if not s1 or not s2:
        return 0.0

    # Soundex comparison
    sx1, sx2 = soundex(s1), soundex(s2)
    soundex_match = 1.0 if sx1 == sx2 else 0.0

    # Metaphone comparison
    mp1, mp2 = metaphone_simple(s1), metaphone_simple(s2)
    if mp1 and mp2:
        # Use sequence matcher on metaphone codes
        metaphone_match = SequenceMatcher(None, mp1, mp2).ratio()
    else:
        metaphone_match = 0.0

    # Combine scores (weight metaphone higher as it's more accurate)
    return soundex_match * 0.4 + metaphone_match * 0.6


# =============================================================================
# Adaptive Thresholds
# =============================================================================

# Component-specific thresholds for matching
# Higher threshold = stricter matching required
COMPONENT_THRESHOLDS = {
    "street_number": 1.0,    # Must be exact (or very close for typos)
    "street_name": 0.70,     # Allow some variation (typos, abbreviations)
    "street_type": 0.90,     # Should mostly match (standardized)
    "city": 0.80,            # Some typo tolerance
    "state": 1.0,            # Must be exact (2-letter code)
    "zip_code": 1.0,         # Must be exact
    "urbanization": 0.75,    # PR urbanizations can have variations
}

# Weights for overall similarity calculation
COMPONENT_WEIGHTS = {
    "street_number": 0.25,   # Critical for exact address
    "street_name": 0.30,     # Most important identifier
    "zip_code": 0.20,        # Strong geographic anchor
    "city": 0.10,            # Supporting info
    "state": 0.10,           # Usually derived from ZIP
    "urbanization": 0.05,    # PR-specific, important when present
}


@dataclass(slots=True)
class MatchExplanation:
    """Detailed explanation of how a match score was computed.

    Provides transparency into the matching algorithm's decision.
    """
    overall_score: float
    component_scores: dict[str, float]
    component_contributions: dict[str, float]
    algorithms_used: list[str]
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "overall_score": round(self.overall_score, 4),
            "component_scores": {k: round(v, 4) for k, v in self.component_scores.items()},
            "component_contributions": {k: round(v, 4) for k, v in self.component_contributions.items()},
            "algorithms_used": self.algorithms_used,
            "notes": self.notes,
        }


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
        """Compute normalized lookup key.

        For Puerto Rico addresses, includes urbanization as part of the key
        since the same street/number/ZIP can exist in multiple urbanizations.
        """
        parts = []

        # For PR addresses, include urbanization first (important disambiguator)
        if self.parsed.is_puerto_rico and self.parsed.urbanization:
            parts.append(self.parsed.urbanization.lower())

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
        explanation: Optional detailed scoring breakdown.
    """

    address: IndexedAddress
    score: float
    match_type: str  # "exact", "fuzzy_street", "fuzzy_zip", etc.
    customer_id: str
    explanation: MatchExplanation | None = None


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

        # Puerto Rico urbanization index: urbanization_name -> list of IndexedAddress
        self._by_urbanization: dict[str, list[IndexedAddress]] = defaultdict(list)

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
        """Extract ParsedAddress from customer record.

        Uses AddressNormalizer for full parsing including PR urbanization detection.
        """
        address = customer.get("address")
        if not address:
            return None

        # Build full address string for normalizer
        full_address = f"{address}, {customer.get('city', '')}, {customer.get('state', '')} {customer.get('zip', '')}"

        # Use normalizer for full parsing (handles PR urbanization, etc.)
        parsed = AddressNormalizer.normalize(full_address)

        # If normalizer didn't extract fields, fall back to manual extraction
        if not parsed.street_number:
            parsed.street_number = self._extract_street_number(address)
        if not parsed.street_name:
            parsed.street_name = self._extract_street_name(address)
        if not parsed.street_type:
            parsed.street_type = self._extract_street_type(address)
        if not parsed.city:
            parsed.city = customer.get("city")
        if not parsed.state:
            parsed.state = customer.get("state")
        if not parsed.zip_code:
            parsed.zip_code = customer.get("zip")

        return parsed

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

        # Puerto Rico urbanization index
        if parsed.is_puerto_rico and parsed.urbanization:
            urb_key = parsed.urbanization.lower()
            self._by_urbanization[urb_key].append(indexed)

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

    def lookup_by_urbanization(
        self,
        urbanization: str,
        zip_code: str | None = None,
    ) -> list[IndexedAddress]:
        """Look up addresses by Puerto Rico urbanization name.

        Urbanization is a required field for PR addresses that identifies
        the specific subdivision within a ZIP code.

        Args:
            urbanization: Urbanization name (case-insensitive).
            zip_code: Optional ZIP code to narrow search.

        Returns:
            List of addresses in that urbanization.
        """
        urb_key = urbanization.lower()
        results = self._by_urbanization.get(urb_key, [])

        # If ZIP provided, filter results
        if zip_code:
            results = [r for r in results if r.parsed.zip_code == zip_code]

        return results

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
        explain: bool = False,
    ) -> float | tuple[float, MatchExplanation]:
        """Compute similarity score between two addresses using multiple algorithms.

        Uses a combination of:
        - Levenshtein distance for typo detection
        - Phonetic matching (Soundex/Metaphone) for sound-alike errors
        - SequenceMatcher for subsequence similarity
        - Adaptive component-specific thresholds

        Args:
            addr1: First parsed address.
            addr2: Second parsed address.
            explain: If True, return detailed explanation.

        Returns:
            Similarity score (0.0 - 1.0), or tuple of (score, explanation).
        """
        component_scores: dict[str, float] = {}
        component_contributions: dict[str, float] = {}
        algorithms_used: list[str] = []
        notes: list[str] = []

        total_weight = 0.0
        weighted_score = 0.0

        # Street number (needs exact or near-exact match)
        if addr1.street_number and addr2.street_number:
            num1 = addr1.street_number.lower()
            num2 = addr2.street_number.lower()
            if num1 == num2:
                score = 1.0
            else:
                # Allow for minor typos in street number (e.g., "101" vs "102")
                score = levenshtein_similarity(num1, num2)
                if score >= 0.8:  # Close but not exact
                    notes.append(f"Street number near-match: {num1} ↔ {num2}")
                    algorithms_used.append("levenshtein_street_number")
            component_scores["street_number"] = score
            weight = COMPONENT_WEIGHTS["street_number"]
            contribution = score * weight
            component_contributions["street_number"] = contribution
            weighted_score += contribution
            total_weight += weight

        # Street name (most important - use all algorithms)
        if addr1.street_name and addr2.street_name:
            name1 = self._normalize_street_name(addr1.street_name)
            name2 = self._normalize_street_name(addr2.street_name)

            score = self._advanced_string_match(name1, name2, "street_name")

            component_scores["street_name"] = score
            weight = COMPONENT_WEIGHTS["street_name"]
            contribution = score * weight
            component_contributions["street_name"] = contribution
            weighted_score += contribution
            total_weight += weight

            if score < 1.0 and score > 0.5:
                algorithms_used.append("multi_algorithm_street")
                notes.append(f"Street fuzzy: '{name1}' ↔ '{name2}' = {score:.2f}")

        # ZIP code (must be exact, but check for transposition typos)
        if addr1.zip_code and addr2.zip_code:
            if addr1.zip_code == addr2.zip_code:
                score = 1.0
            else:
                # Check for transposition (common typo: 22222 vs 22223)
                dist = damerau_levenshtein_distance(addr1.zip_code, addr2.zip_code)
                if dist == 1:
                    score = 0.8  # Single character error in ZIP
                    notes.append(f"ZIP near-match (1 edit): {addr1.zip_code} ↔ {addr2.zip_code}")
                    algorithms_used.append("damerau_zip")
                else:
                    score = 0.0
            component_scores["zip_code"] = score
            weight = COMPONENT_WEIGHTS["zip_code"]
            contribution = score * weight
            component_contributions["zip_code"] = contribution
            weighted_score += contribution
            total_weight += weight

        # City (fuzzy match with phonetic support)
        if addr1.city and addr2.city:
            city1 = addr1.city.lower()
            city2 = addr2.city.lower()

            score = self._advanced_string_match(city1, city2, "city")

            component_scores["city"] = score
            weight = COMPONENT_WEIGHTS["city"]
            contribution = score * weight
            component_contributions["city"] = contribution
            weighted_score += contribution
            total_weight += weight

            if score < 1.0 and score > 0.6:
                algorithms_used.append("fuzzy_city")

        # State (exact match only - 2 letter codes)
        if addr1.state and addr2.state:
            if addr1.state.upper() == addr2.state.upper():
                score = 1.0
            else:
                score = 0.0
                notes.append(f"State mismatch: {addr1.state} ≠ {addr2.state}")
            component_scores["state"] = score
            weight = COMPONENT_WEIGHTS["state"]
            contribution = score * weight
            component_contributions["state"] = contribution
            weighted_score += contribution
            total_weight += weight

        # Puerto Rico urbanization (important for PR addresses)
        if addr1.is_puerto_rico and addr2.is_puerto_rico:
            if addr1.urbanization and addr2.urbanization:
                urb1 = addr1.urbanization.lower()
                urb2 = addr2.urbanization.lower()
                score = self._advanced_string_match(urb1, urb2, "urbanization")

                component_scores["urbanization"] = score
                weight = COMPONENT_WEIGHTS["urbanization"]
                contribution = score * weight
                component_contributions["urbanization"] = contribution
                weighted_score += contribution
                total_weight += weight

                if score < 1.0:
                    notes.append(f"PR urbanization: '{urb1}' ↔ '{urb2}' = {score:.2f}")
            elif addr1.urbanization or addr2.urbanization:
                # One has urbanization, other doesn't - penalize
                score = 0.5
                component_scores["urbanization"] = score
                weight = COMPONENT_WEIGHTS["urbanization"]
                contribution = score * weight
                component_contributions["urbanization"] = contribution
                weighted_score += contribution
                total_weight += weight
                notes.append("PR address missing urbanization on one side")

        if total_weight == 0:
            final_score = 0.0
        else:
            final_score = weighted_score / total_weight

        if explain:
            explanation = MatchExplanation(
                overall_score=final_score,
                component_scores=component_scores,
                component_contributions=component_contributions,
                algorithms_used=algorithms_used if algorithms_used else ["exact_match"],
                notes=notes,
            )
            return final_score, explanation

        return final_score

    def _advanced_string_match(self, s1: str, s2: str, component: str) -> float:
        """Compute string similarity using multiple algorithms.

        Combines:
        1. Exact match (highest priority)
        2. SequenceMatcher (subsequence matching)
        3. Levenshtein similarity (edit distance)
        4. Phonetic matching (sound-alike)

        Args:
            s1: First string (normalized).
            s2: Second string (normalized).
            component: Component type for threshold lookup.

        Returns:
            Best similarity score from all algorithms.
        """
        if not s1 or not s2:
            return 0.0

        # Exact match
        if s1 == s2:
            return 1.0

        # Run multiple algorithms and take the best
        scores = []

        # 1. SequenceMatcher (good for subsequences)
        seq_score = SequenceMatcher(None, s1, s2).ratio()
        scores.append(seq_score)

        # 2. Levenshtein (good for typos)
        lev_score = levenshtein_similarity(s1, s2)
        scores.append(lev_score)

        # 3. Phonetic match (good for sound-alike errors like "Smith"/"Smyth")
        phon_score = phonetic_match(s1, s2)
        scores.append(phon_score)

        # 4. Check if one is a prefix of the other (for abbreviations)
        if s1.startswith(s2) or s2.startswith(s1):
            # Significant prefix match
            min_len = min(len(s1), len(s2))
            max_len = max(len(s1), len(s2))
            prefix_score = min_len / max_len
            scores.append(prefix_score)

        # Take the maximum score (most permissive matching)
        best_score = max(scores)

        # Apply component-specific threshold
        threshold = COMPONENT_THRESHOLDS.get(component, 0.6)
        if best_score < threshold:
            # Reduce score further if below threshold
            best_score *= 0.8

        return best_score

    def _fuzzy_match_score(self, s1: str, s2: str) -> float:
        """Compute fuzzy match score using multiple algorithms.

        This is the enhanced version that combines:
        - SequenceMatcher (original algorithm)
        - Levenshtein distance
        - Phonetic matching

        Args:
            s1: First string.
            s2: Second string.

        Returns:
            Best similarity score (0.0 - 1.0).
        """
        if not s1 or not s2:
            return 0.0

        if s1 == s2:
            return 1.0

        # Use advanced matching with street_name threshold (most common use)
        return self._advanced_string_match(s1, s2, "street_name")

    def lookup_fuzzy_with_explanation(
        self,
        parsed: ParsedAddress,
        threshold: float = 0.5,
        limit: int = 10,
    ) -> list[MatchResult]:
        """Perform fuzzy matching with detailed explanations.

        This is the "debug mode" version of lookup_fuzzy that provides
        insight into why matches scored the way they did.

        Args:
            parsed: Parsed address to match.
            threshold: Minimum similarity score.
            limit: Maximum results to return.

        Returns:
            List of MatchResult with explanations, sorted by score.
        """
        results: list[MatchResult] = []

        # Strategy 1: If we have ZIP, search within ZIP
        if parsed.zip_code:
            zip_addresses = self._by_zip.get(parsed.zip_code, [])
            for indexed in zip_addresses:
                score_result = self._compute_similarity(parsed, indexed.parsed, explain=True)
                score, explanation = score_result if isinstance(score_result, tuple) else (score_result, None)
                if score >= threshold:
                    results.append(MatchResult(
                        address=indexed,
                        score=score,
                        match_type="fuzzy_zip",
                        customer_id=indexed.customer_id,
                        explanation=explanation,
                    ))

        # Strategy 2: If we have city/state, search in that area
        elif parsed.city and parsed.state:
            key = f"{parsed.city.lower()}|{parsed.state.upper()}"
            city_addresses = self._by_city_state.get(key, [])
            for indexed in city_addresses:
                score_result = self._compute_similarity(parsed, indexed.parsed, explain=True)
                score, explanation = score_result if isinstance(score_result, tuple) else (score_result, None)
                if score >= threshold:
                    results.append(MatchResult(
                        address=indexed,
                        score=score,
                        match_type="fuzzy_city",
                        customer_id=indexed.customer_id,
                        explanation=explanation,
                    ))

        # Strategy 3: Match by street name
        if parsed.street_name:
            normalized = self._normalize_street_name(parsed.street_name)
            street_addresses = self._by_street_name.get(normalized, [])
            for indexed in street_addresses:
                if any(r.address == indexed for r in results):
                    continue
                score_result = self._compute_similarity(parsed, indexed.parsed, explain=True)
                score, explanation = score_result if isinstance(score_result, tuple) else (score_result, None)
                if score >= threshold:
                    results.append(MatchResult(
                        address=indexed,
                        score=score,
                        match_type="fuzzy_street",
                        customer_id=indexed.customer_id,
                        explanation=explanation,
                    ))

        # Sort by score descending and limit
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def match_address_robust(
        self,
        input_address: str,
        threshold: float = 0.5,
        limit: int = 5,
        explain: bool = False,
    ) -> list[MatchResult]:
        """High-level robust address matching with all strategies.

        This is the main entry point for address matching that:
        1. Parses the input address
        2. Tries exact match first
        3. Falls back to multi-algorithm fuzzy matching
        4. Optionally provides detailed explanations

        Args:
            input_address: Raw address string to match.
            threshold: Minimum similarity score (default 0.5 for more permissive).
            limit: Maximum results to return.
            explain: Include match explanations.

        Returns:
            List of MatchResult sorted by score.
        """
        # Parse the input
        parsed = AddressNormalizer.normalize(input_address)

        # Try exact match first
        exact_matches = self.lookup_exact(parsed)
        if exact_matches:
            return exact_matches[:limit]

        # Use robust fuzzy matching
        if explain:
            return self.lookup_fuzzy_with_explanation(parsed, threshold, limit)
        else:
            return self.lookup_fuzzy(parsed, threshold)[:limit]

    def stats(self) -> dict[str, Any]:
        """Return index statistics."""
        return {
            "total_addresses": self._total_addresses,
            "unique_zips": len(self._by_zip),
            "unique_states": len(self._by_state),
            "unique_cities": len(self._by_city_state),
            "unique_streets": len(self._by_street_name),
            "unique_urbanizations": len(self._by_urbanization),
            "indexed": self._indexed,
            "matching_algorithms": [
                "exact_match",
                "levenshtein_distance",
                "damerau_levenshtein",
                "soundex_phonetic",
                "metaphone_phonetic",
                "sequence_matcher",
            ],
        }
