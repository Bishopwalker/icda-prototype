"""Data models for the 5-Agent Enforcer System.

Defines the core data structures used throughout the enforcer pipeline
for knowledge indexing, validation, and batch processing.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ContentType(str, Enum):
    """Classification of input content type."""

    ADDRESS = "address"           # Individual address data
    RULE = "rule"                 # Business/validation rule
    EXAMPLE = "example"           # Example with context
    PATTERN = "pattern"           # Regex or matching pattern
    DOCUMENTATION = "documentation"  # Reference documentation
    BATCH = "batch"               # Batch of mixed items
    UNKNOWN = "unknown"           # Not yet classified


class ExtractionType(str, Enum):
    """Type of extracted semantic element."""

    ENTITY = "entity"             # Named entity (location, org, etc.)
    RULE = "rule"                 # Business rule
    PATTERN = "pattern"           # Regex/matching pattern
    EXAMPLE = "example"           # Illustrative example
    REFERENCE = "reference"       # Cross-reference to other doc
    DEFINITION = "definition"     # Term definition


@dataclass(slots=True)
class AddressRule:
    """Extracted address validation rule.

    Attributes:
        name: Rule identifier.
        condition: When this rule applies.
        action: What to do when triggered.
        scope: Geographic or content scope.
        confidence: Extraction confidence (0.0-1.0).
        source_doc: Source document ID.
        examples: Example applications of rule.
    """

    name: str
    condition: str
    action: str
    scope: str = "global"
    confidence: float = 0.0
    source_doc: str | None = None
    examples: list[str] = field(default_factory=list)


@dataclass(slots=True)
class AddressPattern:
    """Extracted address matching pattern.

    Attributes:
        name: Pattern identifier.
        regex: Regular expression string.
        description: Human-readable description.
        examples: Example strings that match.
        confidence: Extraction confidence (0.0-1.0).
        is_valid: Whether regex compiles successfully.
    """

    name: str
    regex: str
    description: str
    examples: list[str] = field(default_factory=list)
    confidence: float = 0.0
    is_valid: bool = True


@dataclass(slots=True)
class ExtractionResult:
    """Result of semantic extraction from content.

    Attributes:
        extraction_type: Type of extracted element.
        content: The extracted content.
        metadata: Additional context.
        confidence: Extraction confidence (0.0-1.0).
        position: Location in source (line/char).
    """

    extraction_type: ExtractionType
    content: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    position: tuple[int, int] | None = None


@dataclass(slots=True)
class CrossReference:
    """Cross-reference to related knowledge.

    Attributes:
        target_id: ID of referenced document.
        reference_type: Type of reference (see_also, contradicts, etc.).
        context: Why this reference exists.
        confidence: Reference confidence (0.0-1.0).
    """

    target_id: str
    reference_type: str
    context: str
    confidence: float = 0.0


@dataclass(slots=True)
class KnowledgeChunk:
    """Indexed knowledge chunk for OpenSearch.

    Attributes:
        chunk_id: Unique chunk identifier.
        content: Text content of chunk.
        embedding: Vector embedding (1024 dims for Titan).
        metadata: Chunk metadata for filtering.
        source_doc_id: Parent document ID.
        chunk_index: Position in parent document.
    """

    chunk_id: str
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    source_doc_id: str | None = None
    chunk_index: int = 0


@dataclass(slots=True)
class IntakeResult:
    """Result from IntakeGuardAgent.

    Attributes:
        is_valid: Whether input passes validation.
        content_type: Detected content type.
        is_pr_relevant: Contains PR address content.
        is_batch: Contains multiple items.
        raw_content: Original input content.
        parsed_content: Structured parsed content.
        warnings: Non-blocking warnings.
        errors: Blocking errors.
        metadata: Additional intake metadata.
    """

    is_valid: bool
    content_type: ContentType
    is_pr_relevant: bool = False
    is_batch: bool = False
    raw_content: str = ""
    parsed_content: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class SemanticResult:
    """Result from SemanticMinerAgent.

    Attributes:
        extractions: List of extracted elements.
        rules: Extracted address rules.
        patterns: Extracted regex patterns.
        entities: Named entities found.
        relationships: Entity relationships.
        pr_patterns: PR-specific patterns found.
        confidence: Overall extraction confidence.
    """

    extractions: list[ExtractionResult] = field(default_factory=list)
    rules: list[AddressRule] = field(default_factory=list)
    patterns: list[AddressPattern] = field(default_factory=list)
    entities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    pr_patterns: list[dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


@dataclass(slots=True)
class ContextResult:
    """Result from ContextLinkerAgent.

    Attributes:
        cross_references: Links to existing knowledge.
        conflicts: Detected conflicts with existing.
        coverage_score: Topic coverage (0.0-1.0).
        graph_connected: Links to knowledge graph.
        related_docs: IDs of related documents.
        resolved_refs: Resolved internal references.
    """

    cross_references: list[CrossReference] = field(default_factory=list)
    conflicts: list[dict[str, Any]] = field(default_factory=list)
    coverage_score: float = 0.0
    graph_connected: bool = False
    related_docs: list[str] = field(default_factory=list)
    resolved_refs: list[dict[str, Any]] = field(default_factory=list)


@dataclass(slots=True)
class QualityResult:
    """Result from QualityEnforcerAgent.

    Attributes:
        passed: Overall quality check passed.
        accuracy_score: Factual accuracy (0.0-1.0).
        completeness_score: Required elements present (0.0-1.0).
        consistency_score: Internal consistency (0.0-1.0).
        overall_score: Combined quality score.
        validated_examples: Examples that parse correctly.
        failed_validations: Specific failures.
        recommendations: Quality improvement suggestions.
    """

    passed: bool = False
    accuracy_score: float = 0.0
    completeness_score: float = 0.0
    consistency_score: float = 0.0
    overall_score: float = 0.0
    validated_examples: list[str] = field(default_factory=list)
    failed_validations: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class IndexResult:
    """Result from IndexSyncAgent.

    Attributes:
        success: Indexing completed successfully.
        doc_id: Document ID in OpenSearch.
        chunks_created: Number of chunks indexed.
        embedding_generated: Embedding was created.
        searchable: Test query returned content.
        index_metadata: Metadata stored with index.
    """

    success: bool = False
    doc_id: str | None = None
    chunks_created: int = 0
    embedding_generated: bool = False
    searchable: bool = False
    index_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EnforcerResult:
    """Complete result from 5-agent enforcer pipeline.

    Attributes:
        success: Pipeline completed successfully.
        intake: IntakeGuardAgent result.
        semantic: SemanticMinerAgent result.
        context: ContextLinkerAgent result.
        quality: QualityEnforcerAgent result.
        index: IndexSyncAgent result.
        gates_passed: List of passed quality gates.
        gates_failed: List of failed quality gates.
        total_time_ms: Total processing time.
        agent_timings: Individual agent timings.
    """

    success: bool = False
    intake: IntakeResult | None = None
    semantic: SemanticResult | None = None
    context: ContextResult | None = None
    quality: QualityResult | None = None
    index: IndexResult | None = None
    gates_passed: list[str] = field(default_factory=list)
    gates_failed: list[str] = field(default_factory=list)
    total_time_ms: int = 0
    agent_timings: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "success": self.success,
            "gates_passed": self.gates_passed,
            "gates_failed": self.gates_failed,
            "total_time_ms": self.total_time_ms,
            "agent_timings": self.agent_timings,
            "quality_score": self.quality.overall_score if self.quality else 0.0,
            "chunks_created": self.index.chunks_created if self.index else 0,
        }


@dataclass(slots=True)
class BatchKnowledgeItem:
    """Single item in a batch knowledge processing request.

    Attributes:
        id: Unique identifier for this item.
        content: Content to process.
        content_type: Expected content type.
        context: Optional context hints.
    """

    id: str
    content: str
    content_type: str = "unknown"
    context: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BatchKnowledgeResult:
    """Result for single item in batch processing.

    Attributes:
        id: Identifier matching input item.
        result: Enforcer result for this item.
        processing_time_ms: Time for this item.
        stage_reached: Last agent that processed.
    """

    id: str
    result: EnforcerResult
    processing_time_ms: int = 0
    stage_reached: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "success": self.result.success,
            "processing_time_ms": self.processing_time_ms,
            "stage_reached": self.stage_reached,
            "quality_score": self.result.quality.overall_score if self.result.quality else 0.0,
        }


@dataclass(slots=True)
class BatchSummary:
    """Summary statistics for batch processing.

    Attributes:
        total: Total items processed.
        successful: Successfully indexed.
        failed: Failed processing.
        avg_quality_score: Average quality score.
        total_chunks_created: Total chunks indexed.
        total_time_ms: Total processing time.
        pr_items: Count of PR-relevant items.
    """

    total: int = 0
    successful: int = 0
    failed: int = 0
    avg_quality_score: float = 0.0
    total_chunks_created: int = 0
    total_time_ms: int = 0
    pr_items: int = 0

    @property
    def success_rate(self) -> float:
        """Calculate success rate."""
        return self.successful / self.total if self.total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "total": self.total,
            "successful": self.successful,
            "failed": self.failed,
            "success_rate": round(self.success_rate * 100, 2),
            "avg_quality_score": round(self.avg_quality_score, 3),
            "total_chunks_created": self.total_chunks_created,
            "total_time_ms": self.total_time_ms,
            "pr_items": self.pr_items,
        }
