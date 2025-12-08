"""Address normalization and parsing utilities.

This module provides functions to parse raw address strings into structured
components, normalize formatting, and standardize abbreviations.
"""

import re
from functools import cache

from icda.address_models import (
    AddressComponent,
    AddressQuality,
    AddressClassification,
    ParsedAddress,
)


# Standard street type abbreviations (USPS standard)
STREET_TYPES: dict[str, str] = {
    # Full names to abbreviations
    "street": "St",
    "avenue": "Ave",
    "boulevard": "Blvd",
    "drive": "Dr",
    "lane": "Ln",
    "road": "Rd",
    "court": "Ct",
    "circle": "Cir",
    "place": "Pl",
    "way": "Way",
    "trail": "Trl",
    "terrace": "Ter",
    "parkway": "Pkwy",
    "highway": "Hwy",
    "expressway": "Expy",
    "run": "Run",
    "crossing": "Xing",
    "ridge": "Rdg",
    "point": "Pt",
    "pike": "Pike",
    "pass": "Pass",
    "path": "Path",
    "loop": "Loop",
    "landing": "Lndg",
    "junction": "Jct",
    "heights": "Hts",
    "grove": "Grv",
    "green": "Grn",
    "glen": "Gln",
    "gardens": "Gdns",
    "ford": "Frd",
    "ferry": "Fry",
    "estate": "Est",
    "estates": "Ests",
    "cove": "Cv",
    "creek": "Crk",
    "corner": "Cor",
    "commons": "Cmns",
    "center": "Ctr",
    "canyon": "Cnyn",
    "branch": "Br",
    "bend": "Bnd",
    "alley": "Aly",
    # Common abbreviations (keep as-is)
    "st": "St",
    "ave": "Ave",
    "blvd": "Blvd",
    "dr": "Dr",
    "ln": "Ln",
    "rd": "Rd",
    "ct": "Ct",
    "cir": "Cir",
    "pl": "Pl",
    "trl": "Trl",
    "ter": "Ter",
    "pkwy": "Pkwy",
    "hwy": "Hwy",
}

# State abbreviations (full name to 2-letter code)
STATE_ABBREVIATIONS: dict[str, str] = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY", "district of columbia": "DC",
    # Already abbreviated
    "al": "AL", "ak": "AK", "az": "AZ", "ar": "AR", "ca": "CA", "co": "CO",
    "ct": "CT", "de": "DE", "fl": "FL", "ga": "GA", "hi": "HI", "id": "ID",
    "il": "IL", "in": "IN", "ia": "IA", "ks": "KS", "ky": "KY", "la": "LA",
    "me": "ME", "md": "MD", "ma": "MA", "mi": "MI", "mn": "MN", "ms": "MS",
    "mo": "MO", "mt": "MT", "ne": "NE", "nv": "NV", "nh": "NH", "nj": "NJ",
    "nm": "NM", "ny": "NY", "nc": "NC", "nd": "ND", "oh": "OH", "ok": "OK",
    "or": "OR", "pa": "PA", "ri": "RI", "sc": "SC", "sd": "SD", "tn": "TN",
    "tx": "TX", "ut": "UT", "vt": "VT", "va": "VA", "wa": "WA", "wv": "WV",
    "wi": "WI", "wy": "WY", "dc": "DC",
}

# Directional prefixes/suffixes
DIRECTIONALS: dict[str, str] = {
    "north": "N", "south": "S", "east": "E", "west": "W",
    "northeast": "NE", "northwest": "NW", "southeast": "SE", "southwest": "SW",
    "n": "N", "s": "S", "e": "E", "w": "W",
    "ne": "NE", "nw": "NW", "se": "SE", "sw": "SW",
}

# Unit type keywords
UNIT_TYPES: set[str] = {
    "apt", "apartment", "suite", "ste", "unit", "bldg", "building",
    "floor", "fl", "room", "rm", "#",
}


class AddressNormalizer:
    """Normalizes and parses address strings into structured components.

    This class handles the first stage of the address verification pipeline,
    converting raw address input into a structured ParsedAddress object with
    standardized formatting.
    """

    # Regex patterns for address parsing
    _ZIP_PATTERN = re.compile(r"\b(\d{5})(?:-(\d{4}))?\b")
    _STREET_NUM_PATTERN = re.compile(r"^(\d+[A-Za-z]?)\b")
    _UNIT_PATTERN = re.compile(
        r"\b(?:apt|apartment|suite|ste|unit|#|bldg|building|floor|fl|room|rm)"
        r"\.?\s*([A-Za-z0-9-]+)\b",
        re.IGNORECASE,
    )
    _STATE_PATTERN = re.compile(
        r"\b([A-Za-z]{2})\s*(?:,?\s*\d{5}|\s*$)",
        re.IGNORECASE,
    )

    @classmethod
    def normalize(cls, raw: str) -> ParsedAddress:
        """Parse and normalize a raw address string.

        Args:
            raw: Raw address string input.

        Returns:
            ParsedAddress with extracted components.
        """
        if not raw or not raw.strip():
            return ParsedAddress(raw=raw or "")

        # Clean and prepare input
        cleaned = cls._clean_input(raw)
        components_found: list[AddressComponent] = []
        components_missing: list[AddressComponent] = []

        # Extract ZIP code first (most reliable anchor)
        zip_code, zip_plus4, cleaned = cls._extract_zip(cleaned)
        if zip_code:
            components_found.append(AddressComponent.ZIP_CODE)
            if zip_plus4:
                components_found.append(AddressComponent.ZIP_PLUS4)
        else:
            components_missing.append(AddressComponent.ZIP_CODE)

        # Extract state
        state, cleaned = cls._extract_state(cleaned)
        if state:
            components_found.append(AddressComponent.STATE)
        else:
            components_missing.append(AddressComponent.STATE)

        # Extract unit/apartment
        unit, cleaned = cls._extract_unit(cleaned)
        if unit:
            components_found.append(AddressComponent.UNIT)

        # Extract street number
        street_number, cleaned = cls._extract_street_number(cleaned)
        if street_number:
            components_found.append(AddressComponent.STREET_NUMBER)
        else:
            components_missing.append(AddressComponent.STREET_NUMBER)

        # Extract street name and type from remaining text
        street_name, street_type, city = cls._extract_street_and_city(cleaned)
        if street_name:
            components_found.append(AddressComponent.STREET_NAME)
        else:
            components_missing.append(AddressComponent.STREET_NAME)
        if street_type:
            components_found.append(AddressComponent.STREET_TYPE)
        if city:
            components_found.append(AddressComponent.CITY)
        else:
            components_missing.append(AddressComponent.CITY)

        return ParsedAddress(
            raw=raw,
            street_number=street_number,
            street_name=street_name,
            street_type=street_type,
            unit=unit,
            city=city,
            state=state,
            zip_code=zip_code,
            zip_plus4=zip_plus4,
            components_found=components_found,
            components_missing=components_missing,
        )

    @classmethod
    def classify(cls, parsed: ParsedAddress) -> AddressClassification:
        """Classify the quality of a parsed address.

        Args:
            parsed: ParsedAddress to classify.

        Returns:
            AddressClassification with quality assessment.
        """
        issues: list[str] = []
        suggestions: list[str] = []

        # Check required components
        has_street = bool(parsed.street_number and parsed.street_name)
        has_city = bool(parsed.city)
        has_state = bool(parsed.state)
        has_zip = bool(parsed.zip_code)

        # Count missing required fields
        missing_count = sum([
            not has_street,
            not has_city,
            not has_state,
            not has_zip,
        ])

        # Check for minimal viable address (can we work with this?)
        # Even with missing pieces, we can try to complete if we have SOME info
        has_location_anchor = has_zip or (has_city and has_state)
        has_street_anchor = has_street or parsed.street_name

        # Determine quality - more forgiving thresholds
        if missing_count == 0:
            quality = AddressQuality.COMPLETE
            confidence = 0.95
        elif missing_count == 1:
            quality = AddressQuality.PARTIAL
            confidence = 0.80  # Bumped from 0.75 - one missing is still very usable
            if not has_zip:
                issues.append("Missing ZIP code")
                suggestions.append("ZIP code can be inferred from city/state")
            elif not has_city:
                issues.append("Missing city")
                suggestions.append("City can be inferred from ZIP code")
            elif not has_state:
                issues.append("Missing state")
                suggestions.append("State can be inferred from ZIP code")
            elif not has_street:
                issues.append("Missing or incomplete street address")
        elif missing_count == 2:
            quality = AddressQuality.PARTIAL
            confidence = 0.60  # Bumped from 0.50 - still workable
            if not has_street:
                issues.append("Missing street address")
            if not has_city:
                issues.append("Missing city")
            if not has_state:
                issues.append("Missing state")
            if not has_zip:
                issues.append("Missing ZIP code")
        elif missing_count == 3 and (has_location_anchor or has_street_anchor):
            # Still PARTIAL if we have something to work with
            quality = AddressQuality.PARTIAL
            confidence = 0.40
            issues.append("Multiple missing components")
            if has_location_anchor:
                suggestions.append("Location identified - street details needed")
            else:
                suggestions.append("Street identified - location details needed")
            if not has_street:
                issues.append("Missing street address")
            if not has_city:
                issues.append("Missing city")
            if not has_state:
                issues.append("Missing state")
            if not has_zip:
                issues.append("Missing ZIP code")
        else:
            # Only INVALID if we have almost nothing to work with
            quality = AddressQuality.INVALID
            confidence = 0.15
            issues.append("Insufficient address information")
            suggestions.append("Provide street address, city, state, or ZIP code")

        # Check for ambiguity
        if parsed.street_name and not parsed.street_type:
            # Could be ambiguous street type
            if quality == AddressQuality.COMPLETE:
                quality = AddressQuality.AMBIGUOUS
                confidence *= 0.9
            issues.append("Street type not specified")
            suggestions.append("Street type (St, Ave, Blvd, etc.) may be needed")

        return AddressClassification(
            quality=quality,
            confidence=confidence,
            parsed=parsed,
            issues=issues,
            suggestions=suggestions,
        )

    @classmethod
    def _clean_input(cls, raw: str) -> str:
        """Clean and normalize raw input string."""
        # Normalize whitespace and remove extra punctuation
        cleaned = re.sub(r"\s+", " ", raw.strip())
        # Remove periods except in abbreviations
        cleaned = re.sub(r"\.(?!\w)", "", cleaned)
        # Normalize common separators
        cleaned = cleaned.replace(";", ",")
        return cleaned

    @classmethod
    def _extract_zip(cls, text: str) -> tuple[str | None, str | None, str]:
        """Extract ZIP code from text."""
        match = cls._ZIP_PATTERN.search(text)
        if match:
            zip_code = match.group(1)
            zip_plus4 = match.group(2)
            # Remove from text
            text = text[:match.start()] + text[match.end():]
            text = text.strip(" ,")
            return zip_code, zip_plus4, text
        return None, None, text

    @classmethod
    def _extract_state(cls, text: str) -> tuple[str | None, str]:
        """Extract state from text."""
        # Try to find state abbreviation at end or before comma
        match = cls._STATE_PATTERN.search(text)
        if match:
            state_raw = match.group(1).lower()
            state = STATE_ABBREVIATIONS.get(state_raw)
            if state:
                text = text[:match.start()] + text[match.end():]
                text = text.strip(" ,")
                return state, text

        # Try full state names
        text_lower = text.lower()
        for full_name, abbr in STATE_ABBREVIATIONS.items():
            if len(full_name) > 2 and full_name in text_lower:
                # Remove the state name
                pattern = re.compile(re.escape(full_name), re.IGNORECASE)
                text = pattern.sub("", text).strip(" ,")
                return abbr, text

        return None, text

    @classmethod
    def _extract_unit(cls, text: str) -> tuple[str | None, str]:
        """Extract unit/apartment number from text."""
        match = cls._UNIT_PATTERN.search(text)
        if match:
            unit = f"#{match.group(1)}"
            text = text[:match.start()] + text[match.end():]
            text = text.strip(" ,")
            return unit, text
        return None, text

    @classmethod
    def _extract_street_number(cls, text: str) -> tuple[str | None, str]:
        """Extract street number from beginning of text."""
        match = cls._STREET_NUM_PATTERN.match(text)
        if match:
            number = match.group(1)
            text = text[match.end():].strip()
            return number, text
        return None, text

    @classmethod
    def _extract_street_and_city(
        cls,
        text: str,
    ) -> tuple[str | None, str | None, str | None]:
        """Extract street name, type, and city from remaining text.

        Returns:
            Tuple of (street_name, street_type, city).
        """
        if not text:
            return None, None, None

        # Split on comma to separate street from city
        parts = [p.strip() for p in text.split(",") if p.strip()]

        if not parts:
            return None, None, None

        # First part is likely street, last part might be city
        street_part = parts[0]
        city = parts[-1] if len(parts) > 1 else None

        # Extract street type from street part
        words = street_part.split()
        street_name = None
        street_type = None

        if words:
            # Check if last word is a street type
            last_word_lower = words[-1].lower().rstrip(".")
            if last_word_lower in STREET_TYPES:
                street_type = STREET_TYPES[last_word_lower]
                street_name = " ".join(words[:-1])
            else:
                street_name = " ".join(words)

            # Normalize directionals in street name
            if street_name:
                name_words = street_name.split()
                normalized_words = []
                for word in name_words:
                    word_lower = word.lower()
                    if word_lower in DIRECTIONALS:
                        normalized_words.append(DIRECTIONALS[word_lower])
                    else:
                        normalized_words.append(word.title())
                street_name = " ".join(normalized_words)

        # Normalize city
        if city:
            city = city.title()

        return street_name, street_type, city


@cache
def normalize_state(state: str) -> str | None:
    """Normalize state to 2-letter code.

    Args:
        state: State name or abbreviation.

    Returns:
        2-letter state code or None if not recognized.
    """
    return STATE_ABBREVIATIONS.get(state.lower().strip())


@cache
def normalize_street_type(street_type: str) -> str:
    """Normalize street type to standard abbreviation.

    Args:
        street_type: Street type (full or abbreviated).

    Returns:
        Standard abbreviation.
    """
    return STREET_TYPES.get(street_type.lower().strip().rstrip("."), street_type)
