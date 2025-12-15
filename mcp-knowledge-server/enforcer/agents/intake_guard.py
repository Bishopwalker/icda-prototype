"""IntakeGuardAgent - Agent 1 of 5 in the Enforcer Pipeline.

Validates input format, detects PR/batch content, and ensures content
meets basic requirements before semantic extraction.

Ultrathink Pattern:
1. Classification - Determine content type (address, rule, example, etc.)
2. Detection - Identify special cases (PR content, batch, duplicates)
3. Validation - Apply intake quality gates
4. Output - Produce IntakeResult with parsed content
"""

import hashlib
import logging
import re
import time
from typing import Any

from ..models import ContentType, IntakeResult
from ..quality_gates import (
    EnforcerGate,
    EnforcerGateResult,
    GateCategory,
    get_gate_config,
)


logger = logging.getLogger(__name__)


# PR ZIP code prefixes (006-009 are Puerto Rico)
PR_ZIP_PREFIXES = ("006", "007", "008", "009")

# Content type detection patterns
CONTENT_PATTERNS = {
    ContentType.ADDRESS: [
        r"\b\d{5}(-\d{4})?\b",  # ZIP code
        r"\b(st|ave|blvd|rd|ln|dr|ct|pl|way|cir)\b",  # Street types
        r"\b(urb|urbanizacion)\b",  # PR urbanization
    ],
    ContentType.RULE: [
        r"\b(if|when|must|should|require|validate)\b",
        r"\b(rule|condition|constraint)\b",
    ],
    ContentType.PATTERN: [
        r"regex|pattern|match",
        r"\^.*\$",  # Regex anchors
        r"\[.*\]",  # Character classes
    ],
    ContentType.EXAMPLE: [
        r"\bexample\b",
        r"e\.g\.",
        r"for instance",
        r"→|=>|->",  # Arrow indicators
    ],
}

# Maximum content size (10MB)
MAX_CONTENT_SIZE = 10 * 1024 * 1024

# Supported formats
SUPPORTED_FORMATS = {".md", ".txt", ".json", ".yaml", ".yml", ".csv"}


class IntakeGuardAgent:
    """Agent 1: Validates and classifies incoming content.

    Quality Gates Enforced:
    - INTAKE_PARSEABLE: Content can be read
    - INTAKE_NOT_EMPTY: Content has data
    - INTAKE_VALID_FORMAT: Supported format
    - INTAKE_SIZE_LIMIT: Under 10MB
    - INTAKE_DUPLICATE_CHECK: Not already indexed
    """

    def __init__(self, known_hashes: set[str] | None = None):
        """Initialize the IntakeGuardAgent.

        Args:
            known_hashes: Set of content hashes already indexed.
        """
        self.known_hashes = known_hashes or set()
        self.stats = {
            "processed": 0,
            "passed": 0,
            "failed": 0,
            "duplicates_detected": 0,
            "pr_content_detected": 0,
            "batch_detected": 0,
        }

    async def process(
        self,
        content: str,
        filename: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[IntakeResult, list[EnforcerGateResult]]:
        """Process content through intake validation.

        Ultrathink 4-Phase Analysis:
        1. Classification - Determine content type
        2. Detection - Identify special cases
        3. Validation - Apply quality gates
        4. Output - Produce IntakeResult

        Args:
            content: Raw content to process.
            filename: Optional filename for format detection.
            metadata: Optional metadata hints.

        Returns:
            Tuple of (IntakeResult, list of gate results).
        """
        start_time = time.time()
        self.stats["processed"] += 1
        gates: list[EnforcerGateResult] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Phase 1: Classification
        content_type = self._classify_content(content)
        logger.debug(f"Classified content as: {content_type.value}")

        # Phase 2: Detection
        is_pr_relevant = self._detect_pr_content(content)
        is_batch = self._detect_batch_content(content)
        content_hash = self._compute_hash(content)

        if is_pr_relevant:
            self.stats["pr_content_detected"] += 1
        if is_batch:
            self.stats["batch_detected"] += 1

        # Phase 3: Validation (Quality Gates)

        # Gate 1: INTAKE_PARSEABLE
        is_parseable = self._check_parseable(content)
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INTAKE_PARSEABLE,
            passed=is_parseable,
            message="Content is parseable" if is_parseable else "Content failed to parse",
            category=GateCategory.INTAKE,
            severity="critical",
        ))
        if not is_parseable:
            errors.append("Content could not be parsed")

        # Gate 2: INTAKE_NOT_EMPTY
        is_not_empty = bool(content and content.strip())
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INTAKE_NOT_EMPTY,
            passed=is_not_empty,
            message="Content has data" if is_not_empty else "Content is empty",
            category=GateCategory.INTAKE,
            severity="critical",
        ))
        if not is_not_empty:
            errors.append("Content is empty or whitespace only")

        # Gate 3: INTAKE_VALID_FORMAT
        is_valid_format = self._check_format(filename)
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INTAKE_VALID_FORMAT,
            passed=is_valid_format,
            message="Format is supported" if is_valid_format else f"Unsupported format: {filename}",
            details={"filename": filename, "supported": list(SUPPORTED_FORMATS)},
            category=GateCategory.INTAKE,
            severity="critical",
        ))
        if not is_valid_format:
            errors.append(f"Unsupported file format: {filename}")

        # Gate 4: INTAKE_SIZE_LIMIT
        content_size = len(content.encode("utf-8"))
        is_under_limit = content_size <= MAX_CONTENT_SIZE
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INTAKE_SIZE_LIMIT,
            passed=is_under_limit,
            message=f"Content size OK ({content_size} bytes)" if is_under_limit
                    else f"Content too large ({content_size} > {MAX_CONTENT_SIZE})",
            details={"size_bytes": content_size, "limit_bytes": MAX_CONTENT_SIZE},
            category=GateCategory.INTAKE,
            severity="critical",
        ))
        if not is_under_limit:
            errors.append(f"Content exceeds size limit: {content_size} bytes")

        # Gate 5: INTAKE_DUPLICATE_CHECK
        is_duplicate = content_hash in self.known_hashes
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.INTAKE_DUPLICATE_CHECK,
            passed=not is_duplicate,
            message="Content is unique" if not is_duplicate else "Content already indexed",
            details={"content_hash": content_hash, "is_duplicate": is_duplicate},
            category=GateCategory.INTAKE,
            severity="warning",
        ))
        if is_duplicate:
            self.stats["duplicates_detected"] += 1
            warnings.append("Content appears to be already indexed")

        # Phase 4: Output
        all_critical_passed = all(
            g.passed for g in gates
            if get_gate_config(g.gate).get("severity") == "critical"
        )

        if all_critical_passed:
            self.stats["passed"] += 1
        else:
            self.stats["failed"] += 1

        # Parse content for downstream agents
        parsed_content = self._parse_content(content, content_type)

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = IntakeResult(
            is_valid=all_critical_passed,
            content_type=content_type,
            is_pr_relevant=is_pr_relevant,
            is_batch=is_batch,
            raw_content=content,
            parsed_content=parsed_content,
            warnings=warnings,
            errors=errors,
            metadata={
                "content_hash": content_hash,
                "content_size": content_size,
                "filename": filename,
                "processing_time_ms": elapsed_ms,
                **(metadata or {}),
            },
        )

        return result, gates

    def _classify_content(self, content: str) -> ContentType:
        """Classify content type based on patterns.

        Args:
            content: Content to classify.

        Returns:
            Detected content type.
        """
        content_lower = content.lower()
        scores: dict[ContentType, int] = {ct: 0 for ct in ContentType}

        for content_type, patterns in CONTENT_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, content_lower, re.IGNORECASE)
                scores[content_type] += len(matches)

        # Get highest scoring type
        max_score = max(scores.values())
        if max_score == 0:
            return ContentType.UNKNOWN

        for ct, score in scores.items():
            if score == max_score:
                return ct

        return ContentType.UNKNOWN

    def _detect_pr_content(self, content: str) -> bool:
        """Detect if content is Puerto Rico relevant.

        Args:
            content: Content to check.

        Returns:
            True if PR-relevant content detected.
        """
        content_lower = content.lower()

        # Check for PR indicators
        pr_indicators = [
            r"\bpuerto rico\b",
            r"\bp\.?r\.?\b",
            r"\burb\b",
            r"\burbanizacion\b",
            r"\burbanización\b",
        ]

        for pattern in pr_indicators:
            if re.search(pattern, content_lower):
                return True

        # Check for PR ZIP codes
        zip_matches = re.findall(r"\b(\d{5})(?:-\d{4})?\b", content)
        for zip_code in zip_matches:
            if zip_code.startswith(PR_ZIP_PREFIXES):
                return True

        return False

    def _detect_batch_content(self, content: str) -> bool:
        """Detect if content contains batch data.

        Args:
            content: Content to check.

        Returns:
            True if batch content detected.
        """
        # Check for multiple addresses (more than 5 ZIP codes)
        zip_matches = re.findall(r"\b\d{5}(?:-\d{4})?\b", content)
        if len(zip_matches) > 5:
            return True

        # Check for list indicators
        lines = content.strip().split("\n")
        if len(lines) > 10:
            # Check if lines look like a list
            numbered = sum(1 for line in lines if re.match(r"^\d+[\.\)]\s", line))
            if numbered > 5:
                return True

        # Check for CSV-like structure
        if "," in content and len(lines) > 5:
            comma_counts = [line.count(",") for line in lines if line.strip()]
            if comma_counts and all(c == comma_counts[0] for c in comma_counts[:5]):
                return True

        return False

    def _check_parseable(self, content: str) -> bool:
        """Check if content can be parsed.

        Args:
            content: Content to check.

        Returns:
            True if content is parseable.
        """
        try:
            # Basic parsing check - can it be decoded and processed?
            if not isinstance(content, str):
                return False
            # Try to identify structure
            content.encode("utf-8")
            return True
        except (UnicodeDecodeError, AttributeError):
            return False

    def _check_format(self, filename: str | None) -> bool:
        """Check if file format is supported.

        Args:
            filename: Filename to check.

        Returns:
            True if format is supported or no filename provided.
        """
        if not filename:
            return True  # No filename = raw content, acceptable

        # Get extension
        ext = ""
        if "." in filename:
            ext = "." + filename.rsplit(".", 1)[-1].lower()

        return ext in SUPPORTED_FORMATS or ext == ""

    def _compute_hash(self, content: str) -> str:
        """Compute content hash for duplicate detection.

        Args:
            content: Content to hash.

        Returns:
            SHA-256 hash of content.
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _parse_content(
        self,
        content: str,
        content_type: ContentType,
    ) -> dict[str, Any]:
        """Parse content into structured format.

        Args:
            content: Raw content.
            content_type: Detected content type.

        Returns:
            Parsed content dictionary.
        """
        parsed: dict[str, Any] = {
            "type": content_type.value,
            "lines": content.strip().split("\n"),
            "line_count": len(content.strip().split("\n")),
            "word_count": len(content.split()),
            "char_count": len(content),
        }

        # Extract sections if markdown
        if content.startswith("#") or "##" in content:
            sections = self._extract_markdown_sections(content)
            parsed["sections"] = sections

        # Extract frontmatter if present
        if content.startswith("---"):
            frontmatter = self._extract_frontmatter(content)
            parsed["frontmatter"] = frontmatter

        return parsed

    def _extract_markdown_sections(self, content: str) -> list[dict[str, Any]]:
        """Extract markdown sections.

        Args:
            content: Markdown content.

        Returns:
            List of section dictionaries.
        """
        sections = []
        current_section: dict[str, Any] | None = None
        current_content: list[str] = []

        for line in content.split("\n"):
            if line.startswith("#"):
                # Save previous section
                if current_section:
                    current_section["content"] = "\n".join(current_content)
                    sections.append(current_section)

                # Start new section
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("#").strip()
                current_section = {"level": level, "title": title}
                current_content = []
            else:
                current_content.append(line)

        # Save last section
        if current_section:
            current_section["content"] = "\n".join(current_content)
            sections.append(current_section)

        return sections

    def _extract_frontmatter(self, content: str) -> dict[str, str]:
        """Extract YAML frontmatter from markdown.

        Args:
            content: Content with potential frontmatter.

        Returns:
            Frontmatter key-value pairs.
        """
        frontmatter: dict[str, str] = {}

        if not content.startswith("---"):
            return frontmatter

        lines = content.split("\n")
        in_frontmatter = False
        for i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_frontmatter:
                    in_frontmatter = True
                    continue
                else:
                    break

            if in_frontmatter and ":" in line:
                key, value = line.split(":", 1)
                frontmatter[key.strip()] = value.strip()

        return frontmatter

    def add_known_hash(self, content_hash: str) -> None:
        """Add a hash to known hashes set.

        Args:
            content_hash: Hash to add.
        """
        self.known_hashes.add(content_hash)

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Statistics dictionary.
        """
        return {
            **self.stats,
            "known_hashes_count": len(self.known_hashes),
        }
