"""Address verification data models and enums.

This module defines the core data structures used throughout the address
verification pipeline, including classification results, verification
statuses, and batch processing structures.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AddressQuality(str, Enum):
    """Classification of address data quality."""

    COMPLETE = "complete"       # All required fields present and valid
    PARTIAL = "partial"         # Missing some fields but recoverable
    AMBIGUOUS = "ambiguous"     # Multiple possible interpretations
    INVALID = "invalid"         # Cannot be parsed or verified
    UNKNOWN = "unknown"         # Not yet classified


class VerificationStatus(str, Enum):
    """Result status of address verification."""

    VERIFIED = "verified"           # Exact match found
    CORRECTED = "corrected"         # Fixed and verified
    COMPLETED = "completed"         # Missing parts filled in
    SUGGESTED = "suggested"         # Best guess, needs confirmation
    UNVERIFIED = "unverified"       # Could not verify
    FAILED = "failed"               # Processing error


class AddressComponent(str, Enum):
    """Standard address components."""

    STREET_NUMBER = "street_number"
    STREET_NAME = "street_name"
    STREET_TYPE = "street_type"     # St, Ave, Blvd, etc.
    UNIT = "unit"                   # Apt, Suite, etc.
    CITY = "city"
    STATE = "state"
    ZIP_CODE = "zip_code"
    ZIP_PLUS4 = "zip_plus4"
    COUNTRY = "country"
<<<<<<< HEAD
=======
    URBANIZATION = "urbanization"   # Puerto Rico only (URB field)
>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add


@dataclass(slots=True)
class ParsedAddress:
    """Structured representation of a parsed address.

    Attributes:
        raw: Original input string.
        street_number: House/building number.
        street_name: Name of the street.
        street_type: Type suffix (St, Ave, Blvd, etc.).
        unit: Apartment, suite, or unit number.
        city: City name.
        state: State code (2-letter).
        zip_code: 5-digit ZIP code.
        zip_plus4: Optional 4-digit ZIP extension.
        country: Country code (default US).
<<<<<<< HEAD
=======
        urbanization: Puerto Rico urbanization name (URB field, required for PR).
        is_puerto_rico: True if this is a Puerto Rico address (ZIP 006-009).
>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add
        components_found: List of components successfully parsed.
        components_missing: List of components that couldn't be found.
    """

    raw: str
    street_number: str | None = None
    street_name: str | None = None
    street_type: str | None = None
    unit: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    zip_plus4: str | None = None
    country: str = "US"
<<<<<<< HEAD
=======
    urbanization: str | None = None
    is_puerto_rico: bool = False
>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add
    components_found: list[AddressComponent] = field(default_factory=list)
    components_missing: list[AddressComponent] = field(default_factory=list)

    @property
    def formatted(self) -> str:
<<<<<<< HEAD
        """Return formatted address string."""
        parts = []

=======
        """Return formatted address string.

        For Puerto Rico addresses, includes URB line before street address:
            URB URBANIZATION_NAME
            STREET ADDRESS
            CITY PR ZIP
        """
        parts = []

        # Urbanization line (Puerto Rico only - before street address)
        if self.urbanization and self.is_puerto_rico:
            parts.append(f"URB {self.urbanization}")

>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add
        # Street line
        street_parts = []
        if self.street_number:
            street_parts.append(self.street_number)
        if self.street_name:
            street_parts.append(self.street_name)
        if self.street_type:
            street_parts.append(self.street_type)
        if street_parts:
            parts.append(" ".join(street_parts))

        # Unit line
        if self.unit:
            parts.append(self.unit)

        # City, State ZIP line
        city_state_zip = []
        if self.city:
            city_state_zip.append(self.city)
        if self.state:
            if city_state_zip:
                city_state_zip[-1] += ","
            city_state_zip.append(self.state)
        if self.zip_code:
            zip_str = self.zip_code
            if self.zip_plus4:
                zip_str += f"-{self.zip_plus4}"
            city_state_zip.append(zip_str)
        if city_state_zip:
            parts.append(" ".join(city_state_zip))

        return "\n".join(parts) if parts else self.raw

    @property
    def single_line(self) -> str:
        """Return single-line formatted address."""
        return self.formatted.replace("\n", ", ")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "raw": self.raw,
            "street_number": self.street_number,
            "street_name": self.street_name,
            "street_type": self.street_type,
            "unit": self.unit,
            "city": self.city,
            "state": self.state,
            "zip_code": self.zip_code,
            "zip_plus4": self.zip_plus4,
            "country": self.country,
<<<<<<< HEAD
=======
            "urbanization": self.urbanization,
            "is_puerto_rico": self.is_puerto_rico,
>>>>>>> 04ca1a3554d0e96a498278e69485ff09f1595add
            "formatted": self.single_line,
        }


@dataclass(slots=True)
class AddressClassification:
    """Result of address classification stage.

    Attributes:
        quality: Overall quality assessment.
        confidence: Confidence score (0.0 - 1.0).
        parsed: Parsed address components.
        issues: List of identified issues.
        suggestions: Potential fixes or completions.
    """

    quality: AddressQuality
    confidence: float
    parsed: ParsedAddress
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VerificationResult:
    """Result of address verification.

    Attributes:
        status: Verification outcome status.
        original: Original input address.
        verified: Verified/corrected address (if successful).
        confidence: Confidence in the result (0.0 - 1.0).
        match_type: How the match was found (exact, fuzzy, ai, etc.).
        alternatives: Other possible addresses if ambiguous.
        metadata: Additional context and processing info.
    """

    status: VerificationStatus
    original: ParsedAddress
    verified: ParsedAddress | None = None
    confidence: float = 0.0
    match_type: str | None = None
    alternatives: list[ParsedAddress] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.status.value,
            "original": self.original.to_dict(),
            "verified": self.verified.to_dict() if self.verified else None,
            "confidence": self.confidence,
            "match_type": self.match_type,
            "alternatives": [a.to_dict() for a in self.alternatives],
            "metadata": self.metadata,
        }


@dataclass(slots=True)
class BatchItem:
    """Single item in a batch verification request.

    Attributes:
        id: Unique identifier for this item.
        address: Raw address string to verify.
        context: Optional context hints (zip, state, etc.).
    """

    id: str
    address: str
    context: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BatchResult:
    """Result of batch address verification.

    Attributes:
        id: Identifier matching the input item.
        result: Verification result for this address.
        processing_time_ms: Time taken to process this item.
        stage_reached: Last pipeline stage processed.
    """

    id: str
    result: VerificationResult
    processing_time_ms: int = 0
    stage_reached: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "result": self.result.to_dict(),
            "processing_time_ms": self.processing_time_ms,
            "stage_reached": self.stage_reached,
        }


@dataclass(slots=True)
class BatchSummary:
    """Summary statistics for batch processing.

    Attributes:
        total: Total items processed.
        verified: Count of verified addresses.
        corrected: Count of corrected addresses.
        completed: Count of completed addresses.
        suggested: Count of suggested addresses.
        unverified: Count that couldn't be verified.
        failed: Count of processing failures.
        total_time_ms: Total processing time.
        avg_time_ms: Average time per item.
    """

    total: int = 0
    verified: int = 0
    corrected: int = 0
    completed: int = 0
    suggested: int = 0
    unverified: int = 0
    failed: int = 0
    total_time_ms: int = 0

    @property
    def avg_time_ms(self) -> float:
        """Calculate average processing time per item."""
        return self.total_time_ms / self.total if self.total > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """Calculate success rate (verified + corrected + completed)."""
        successful = self.verified + self.corrected + self.completed
        return successful / self.total if self.total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total": self.total,
            "verified": self.verified,
            "corrected": self.corrected,
            "completed": self.completed,
            "suggested": self.suggested,
            "unverified": self.unverified,
            "failed": self.failed,
            "total_time_ms": self.total_time_ms,
            "avg_time_ms": round(self.avg_time_ms, 2),
            "success_rate": round(self.success_rate * 100, 2),
        }