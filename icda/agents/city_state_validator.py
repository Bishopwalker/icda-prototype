"""City-State Validator - Detects mismatches between cities and states.

This module validates city/state combinations and suggests corrections
when a city doesn't match the expected state (e.g., "Miami, TX" should
likely be "Miami, FL").

The validator uses a database of major US cities and their canonical states
to detect potential mismatches and generate helpful suggestions.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import CityStateMismatch

logger = logging.getLogger(__name__)

# ============================================================================
# State Name Mappings
# ============================================================================

STATE_NAMES: dict[str, str] = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia",
}

STATE_CODES: dict[str, str] = {v.lower(): k for k, v in STATE_NAMES.items()}

# ============================================================================
# Major City to State Mappings
# ============================================================================

# Maps city names (lowercase) to their canonical state codes.
# Focus on cities that are distinctive to one state and commonly referenced.
MAJOR_CITY_STATES: dict[str, str] = {
    # Florida - Major cities
    "miami": "FL",
    "orlando": "FL",
    "tampa": "FL",
    "jacksonville": "FL",
    "fort lauderdale": "FL",
    "west palm beach": "FL",
    "st petersburg": "FL",
    "tallahassee": "FL",
    "gainesville": "FL",
    "pensacola": "FL",
    "sarasota": "FL",
    "naples": "FL",
    "boca raton": "FL",
    "coral gables": "FL",
    "hialeah": "FL",
    "clearwater": "FL",
    "cape coral": "FL",
    "hollywood": "FL",  # Note: Also exists in CA, but FL is more common in data

    # Texas - Major cities
    "houston": "TX",
    "dallas": "TX",
    "austin": "TX",
    "san antonio": "TX",
    "fort worth": "TX",
    "el paso": "TX",
    "arlington": "TX",
    "plano": "TX",
    "lubbock": "TX",
    "amarillo": "TX",
    "corpus christi": "TX",
    "laredo": "TX",
    "irving": "TX",
    "garland": "TX",
    "frisco": "TX",
    "mckinney": "TX",
    "waco": "TX",
    "brownsville": "TX",
    "midland": "TX",
    "odessa": "TX",

    # California - Major cities
    "los angeles": "CA",
    "san francisco": "CA",
    "san diego": "CA",
    "sacramento": "CA",
    "san jose": "CA",
    "fresno": "CA",
    "oakland": "CA",
    "long beach": "CA",
    "bakersfield": "CA",
    "anaheim": "CA",
    "santa ana": "CA",
    "riverside": "CA",
    "stockton": "CA",
    "irvine": "CA",
    "santa clarita": "CA",
    "chula vista": "CA",
    "fremont": "CA",
    "santa rosa": "CA",
    "modesto": "CA",
    "san bernardino": "CA",
    "pasadena": "CA",
    "berkeley": "CA",
    "palo alto": "CA",
    "santa monica": "CA",
    "burbank": "CA",

    # Nevada
    "las vegas": "NV",
    "reno": "NV",
    "henderson": "NV",
    "north las vegas": "NV",
    "sparks": "NV",

    # Arizona
    "phoenix": "AZ",
    "tucson": "AZ",
    "mesa": "AZ",
    "scottsdale": "AZ",
    "chandler": "AZ",
    "glendale": "AZ",
    "tempe": "AZ",
    "peoria": "AZ",
    "flagstaff": "AZ",
    "sedona": "AZ",

    # New York
    "new york": "NY",
    "new york city": "NY",
    "nyc": "NY",
    "manhattan": "NY",
    "brooklyn": "NY",
    "queens": "NY",
    "bronx": "NY",
    "staten island": "NY",
    "buffalo": "NY",
    "albany": "NY",
    "rochester": "NY",
    "syracuse": "NY",
    "yonkers": "NY",

    # Illinois
    "chicago": "IL",
    "aurora": "IL",
    "naperville": "IL",
    "rockford": "IL",
    "joliet": "IL",
    "springfield": "IL",  # Also in other states, but IL is the capital
    "peoria": "IL",
    "elgin": "IL",
    "waukegan": "IL",

    # Pennsylvania
    "philadelphia": "PA",
    "pittsburgh": "PA",
    "allentown": "PA",
    "erie": "PA",
    "scranton": "PA",
    "harrisburg": "PA",

    # Ohio
    "columbus": "OH",
    "cleveland": "OH",
    "cincinnati": "OH",
    "toledo": "OH",
    "akron": "OH",
    "dayton": "OH",
    "youngstown": "OH",

    # Georgia
    "atlanta": "GA",
    "savannah": "GA",
    "augusta": "GA",
    "macon": "GA",
    "athens": "GA",

    # North Carolina
    "charlotte": "NC",
    "raleigh": "NC",
    "greensboro": "NC",
    "durham": "NC",
    "winston-salem": "NC",
    "fayetteville": "NC",
    "wilmington": "NC",

    # Michigan
    "detroit": "MI",
    "grand rapids": "MI",
    "warren": "MI",
    "ann arbor": "MI",
    "lansing": "MI",
    "flint": "MI",

    # New Jersey
    "newark": "NJ",
    "jersey city": "NJ",
    "paterson": "NJ",
    "trenton": "NJ",
    "atlantic city": "NJ",

    # Virginia
    "virginia beach": "VA",
    "norfolk": "VA",
    "richmond": "VA",
    "newport news": "VA",
    "alexandria": "VA",
    "arlington": "VA",

    # Washington
    "seattle": "WA",
    "spokane": "WA",
    "tacoma": "WA",
    "vancouver": "WA",
    "bellevue": "WA",
    "olympia": "WA",

    # Massachusetts
    "boston": "MA",
    "worcester": "MA",
    "cambridge": "MA",
    "lowell": "MA",
    "springfield": "MA",
    "salem": "MA",

    # Colorado
    "denver": "CO",
    "colorado springs": "CO",
    "aurora": "CO",
    "fort collins": "CO",
    "boulder": "CO",
    "pueblo": "CO",

    # Tennessee
    "nashville": "TN",
    "memphis": "TN",
    "knoxville": "TN",
    "chattanooga": "TN",
    "clarksville": "TN",

    # Maryland
    "baltimore": "MD",
    "annapolis": "MD",
    "rockville": "MD",
    "bethesda": "MD",

    # Missouri
    "kansas city": "MO",
    "st louis": "MO",
    "saint louis": "MO",
    "springfield": "MO",
    "columbia": "MO",

    # Louisiana
    "new orleans": "LA",
    "baton rouge": "LA",
    "shreveport": "LA",
    "lafayette": "LA",

    # Oregon
    "portland": "OR",
    "eugene": "OR",
    "salem": "OR",
    "bend": "OR",

    # Oklahoma
    "oklahoma city": "OK",
    "tulsa": "OK",
    "norman": "OK",

    # Connecticut
    "hartford": "CT",
    "new haven": "CT",
    "bridgeport": "CT",
    "stamford": "CT",

    # Utah
    "salt lake city": "UT",
    "provo": "UT",
    "ogden": "UT",

    # Hawaii
    "honolulu": "HI",
    "hilo": "HI",

    # New Mexico
    "albuquerque": "NM",
    "santa fe": "NM",

    # South Carolina
    "charleston": "SC",
    "columbia": "SC",
    "greenville": "SC",
    "myrtle beach": "SC",

    # Alaska
    "anchorage": "AK",
    "fairbanks": "AK",
    "juneau": "AK",

    # Other notable cities
    "minneapolis": "MN",
    "st paul": "MN",
    "saint paul": "MN",
    "milwaukee": "WI",
    "madison": "WI",
    "indianapolis": "IN",
    "des moines": "IA",
    "omaha": "NE",
    "little rock": "AR",
    "birmingham": "AL",
    "montgomery": "AL",
    "jackson": "MS",
    "providence": "RI",
    "boise": "ID",
    "billings": "MT",
    "cheyenne": "WY",
    "sioux falls": "SD",
    "fargo": "ND",
    "burlington": "VT",
    "manchester": "NH",
    "wilmington": "DE",
    "washington": "DC",
    "washington dc": "DC",
}

# ============================================================================
# Ambiguous Cities (exist in multiple states)
# ============================================================================

# Cities that commonly exist in multiple states - don't flag these as mismatches
AMBIGUOUS_CITIES: dict[str, list[str]] = {
    "springfield": ["IL", "MA", "MO", "OH", "OR"],
    "portland": ["OR", "ME"],
    "columbus": ["OH", "GA", "IN"],
    "richmond": ["VA", "CA", "IN"],
    "jackson": ["MS", "TN", "MI", "WY"],
    "columbia": ["SC", "MO", "MD"],
    "aurora": ["CO", "IL"],
    "arlington": ["TX", "VA"],
    "hollywood": ["FL", "CA"],
    "salem": ["OR", "MA"],
    "greenville": ["SC", "NC", "MS"],
    "manchester": ["NH", "CT"],
    "fayetteville": ["NC", "AR"],
    "wilmington": ["NC", "DE"],
    "peoria": ["IL", "AZ"],
    "glendale": ["AZ", "CA"],
    "pasadena": ["CA", "TX"],
    "athens": ["GA", "OH"],
}


class CityStateValidator:
    """Validates city/state combinations and suggests corrections.

    Detects when a city doesn't match the expected state and generates
    helpful "Did you mean X, Y?" suggestions.
    """

    __slots__ = ("_city_states", "_ambiguous", "_state_names")

    def __init__(self) -> None:
        """Initialize the validator with city-state mappings."""
        self._city_states = MAJOR_CITY_STATES
        self._ambiguous = AMBIGUOUS_CITIES
        self._state_names = STATE_NAMES

    def validate(self, city: str, state: str) -> "CityStateMismatch":
        """Check if city matches expected state.

        Args:
            city: City name to validate.
            state: State code or name provided.

        Returns:
            CityStateMismatch with validation result.
        """
        from .models import CityStateMismatch

        if not city or not state:
            return CityStateMismatch(
                has_mismatch=False,
                city=city or "",
                stated_state=state or "",
            )

        # Normalize inputs
        city_lower = city.lower().strip()
        state_upper = self._normalize_state(state)

        if not state_upper:
            # Couldn't determine the state code
            return CityStateMismatch(
                has_mismatch=False,
                city=city,
                stated_state=state,
            )

        # Check if city is in our database
        expected_state = self._city_states.get(city_lower)

        if not expected_state:
            # City not in our database - can't validate
            return CityStateMismatch(
                has_mismatch=False,
                city=city,
                stated_state=state_upper,
            )

        # Check if city is ambiguous (exists in multiple states)
        if city_lower in self._ambiguous:
            valid_states = self._ambiguous[city_lower]
            if state_upper in valid_states:
                # Valid - city exists in the stated state
                return CityStateMismatch(
                    has_mismatch=False,
                    city=city,
                    stated_state=state_upper,
                    is_ambiguous=True,
                )
            else:
                # Mismatch but ambiguous - lower confidence
                return CityStateMismatch(
                    has_mismatch=True,
                    city=city,
                    stated_state=state_upper,
                    expected_state=expected_state,
                    suggestion=self._build_suggestion(city, state_upper, expected_state),
                    confidence=0.6,  # Lower confidence for ambiguous cities
                    is_ambiguous=True,
                )

        # Check if stated state matches expected
        if state_upper == expected_state:
            return CityStateMismatch(
                has_mismatch=False,
                city=city,
                stated_state=state_upper,
                expected_state=expected_state,
            )

        # Mismatch detected
        return CityStateMismatch(
            has_mismatch=True,
            city=city,
            stated_state=state_upper,
            expected_state=expected_state,
            suggestion=self._build_suggestion(city, state_upper, expected_state),
            confidence=0.85,
        )

    def _normalize_state(self, state: str) -> str | None:
        """Normalize state input to uppercase state code.

        Args:
            state: State code or full name.

        Returns:
            Two-letter state code or None if not found.
        """
        state_stripped = state.strip()

        # If it's already a 2-letter code
        if len(state_stripped) == 2:
            code = state_stripped.upper()
            if code in self._state_names:
                return code

        # Try to match by name
        state_lower = state_stripped.lower()
        if state_lower in STATE_CODES:
            return STATE_CODES[state_lower]

        return None

    def _build_suggestion(
        self,
        city: str,
        stated_state: str,
        expected_state: str,
    ) -> str:
        """Build a human-readable suggestion message.

        Args:
            city: The city name.
            stated_state: The state that was provided.
            expected_state: The expected state for this city.

        Returns:
            Suggestion message like "Did you mean Miami, Florida?"
        """
        expected_name = self._state_names.get(expected_state, expected_state)
        stated_name = self._state_names.get(stated_state, stated_state)

        return (
            f"Did you mean {city.title()}, {expected_name}? "
            f"(You searched for {city.title()}, {stated_name})"
        )

    def get_suggestion(self, city: str, stated_state: str) -> str | None:
        """Get a suggestion if there's a mismatch.

        Args:
            city: City name.
            stated_state: State code or name provided.

        Returns:
            Suggestion message or None if no mismatch.
        """
        result = self.validate(city, stated_state)
        return result.suggestion if result.has_mismatch else None

    def is_known_city(self, city: str) -> bool:
        """Check if a city is in our database.

        Args:
            city: City name to check.

        Returns:
            True if city is known.
        """
        return city.lower().strip() in self._city_states

    def get_expected_state(self, city: str) -> str | None:
        """Get the expected state for a city.

        Args:
            city: City name.

        Returns:
            State code or None if not found.
        """
        return self._city_states.get(city.lower().strip())


# Module-level instance for convenience
_validator: CityStateValidator | None = None


def get_validator() -> CityStateValidator:
    """Get or create the singleton validator instance."""
    global _validator
    if _validator is None:
        _validator = CityStateValidator()
    return _validator
