"""ZIP code database for address verification.

Provides fast lookups of city/state information by ZIP code,
and reverse lookups of ZIPs by city/state.
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ZipInfo:
    """Information about a ZIP code.

    Attributes:
        zip_code: 5-digit ZIP code.
        city: Primary city name.
        state: State abbreviation.
        alternate_cities: Other city names using this ZIP.
    """
    zip_code: str
    city: str
    state: str
    alternate_cities: list[str]


class ZipDatabase:
    """In-memory ZIP code database for address verification.

    Indexes ZIP codes from customer data with lookups:
    - ZIP -> city, state
    - City, State -> list of ZIPs
    - State -> list of ZIPs
    """

    def __init__(self):
        """Initialize empty ZIP database."""
        # Primary index: zip -> ZipInfo
        self._by_zip: dict[str, ZipInfo] = {}

        # Secondary indexes
        self._by_city_state: dict[str, list[str]] = defaultdict(list)  # "city|state" -> [zips]
        self._by_state: dict[str, list[str]] = defaultdict(list)  # state -> [zips]

        self._total_zips = 0

    @property
    def total_zips(self) -> int:
        """Return total unique ZIP codes indexed."""
        return self._total_zips

    def build_from_customers(self, customers: list[dict[str, Any]]) -> int:
        """Build ZIP database from customer data.

        Args:
            customers: List of customer records with zip, city, state fields.

        Returns:
            Number of unique ZIPs indexed.
        """
        # Collect all city/state combinations per ZIP
        zip_cities: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

        for customer in customers:
            zip_code = customer.get("zip", "")
            city = customer.get("city", "")
            state = customer.get("state", "")

            if zip_code and city and state:
                zip_cities[zip_code][state].add(city)

        # Build the indexes
        for zip_code, state_cities in zip_cities.items():
            # Use most common state for this ZIP
            state = max(state_cities.keys(), key=lambda s: len(state_cities[s]))
            cities = list(state_cities[state])

            # Primary city is most common
            primary_city = cities[0] if cities else ""
            alternate_cities = cities[1:] if len(cities) > 1 else []

            zip_info = ZipInfo(
                zip_code=zip_code,
                city=primary_city,
                state=state,
                alternate_cities=alternate_cities,
            )

            self._by_zip[zip_code] = zip_info

            # Index by city|state
            key = f"{primary_city.lower()}|{state.upper()}"
            if zip_code not in self._by_city_state[key]:
                self._by_city_state[key].append(zip_code)

            # Index by state
            if zip_code not in self._by_state[state.upper()]:
                self._by_state[state.upper()].append(zip_code)

        self._total_zips = len(self._by_zip)
        logger.info(f"ZipDatabase built with {self._total_zips} ZIP codes")
        return self._total_zips

    def lookup_zip(self, zip_code: str) -> ZipInfo | None:
        """Look up city/state for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code.

        Returns:
            ZipInfo or None if not found.
        """
        return self._by_zip.get(zip_code)

    def get_city_state(self, zip_code: str) -> tuple[str, str] | None:
        """Get city and state for a ZIP code.

        Args:
            zip_code: 5-digit ZIP code.

        Returns:
            Tuple of (city, state) or None if not found.
        """
        info = self._by_zip.get(zip_code)
        if info:
            return (info.city, info.state)
        return None

    def get_zips_for_city(self, city: str, state: str) -> list[str]:
        """Get all ZIP codes for a city/state.

        Args:
            city: City name.
            state: State abbreviation.

        Returns:
            List of ZIP codes serving that city.
        """
        key = f"{city.lower()}|{state.upper()}"
        return self._by_city_state.get(key, [])

    def get_zips_for_state(self, state: str) -> list[str]:
        """Get all ZIP codes in a state.

        Args:
            state: State abbreviation.

        Returns:
            List of ZIP codes in that state.
        """
        return self._by_state.get(state.upper(), [])

    def validate_zip(self, zip_code: str, city: str = None, state: str = None) -> bool:
        """Validate a ZIP code, optionally against city/state.

        Args:
            zip_code: ZIP code to validate.
            city: Optional city to match.
            state: Optional state to match.

        Returns:
            True if ZIP is valid and matches city/state if provided.
        """
        info = self._by_zip.get(zip_code)
        if not info:
            return False

        if state and info.state.upper() != state.upper():
            return False

        if city:
            city_lower = city.lower()
            if info.city.lower() != city_lower:
                # Check alternate cities
                if city_lower not in [c.lower() for c in info.alternate_cities]:
                    return False

        return True

    def stats(self) -> dict[str, Any]:
        """Return database statistics."""
        return {
            "total_zips": self._total_zips,
            "unique_states": len(self._by_state),
            "unique_city_state_combos": len(self._by_city_state),
        }
