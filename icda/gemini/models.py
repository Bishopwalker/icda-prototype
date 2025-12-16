"""
Gemini Enforcer Data Models.

Type definitions for enforcer results, metrics, and configurations.
"""

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class ChunkQualityScore:
    """Quality assessment for a single chunk."""
    chunk_id: str
    coherence: float = 0.0       # 0-1: Does it make sense?
    completeness: float = 0.0   # 0-1: Is it complete?
    relevance: float = 0.0      # 0-1: Is it useful?
    overall: float = 0.0        # Weighted average
    approved: bool = True       # Passes threshold?
    rejection_reason: Optional[str] = None
    improvements: list[str] = field(default_factory=list)
    processing_ms: int = 0


@dataclass(slots=True)
class ChunkGateResult:
    """Result of chunk quality gate processing."""
    total_processed: int = 0
    approved: int = 0
    rejected: int = 0
    improved: int = 0
    scores: list[ChunkQualityScore] = field(default_factory=list)
    avg_coherence: float = 0.0
    avg_completeness: float = 0.0
    avg_relevance: float = 0.0
    processing_time_ms: int = 0


@dataclass(slots=True)
class DuplicateCluster:
    """A cluster of duplicate or near-duplicate chunks."""
    primary_id: str
    duplicate_ids: list[str] = field(default_factory=list)
    similarity_score: float = 0.0
    recommendation: str = "review"  # "merge", "delete", "keep"


@dataclass(slots=True)
class StaleContent:
    """Identified stale or outdated content."""
    chunk_id: str
    reason: str = ""
    last_modified: Optional[str] = None
    recommendation: str = "review"


@dataclass(slots=True)
class CoverageGap:
    """Identified gap in knowledge coverage."""
    topic: str
    description: str = ""
    related_chunks: list[str] = field(default_factory=list)
    recommendation: str = "add content"


@dataclass(slots=True)
class IndexHealthReport:
    """Complete index health report from Level 2 validation."""
    timestamp: str = ""
    total_chunks: int = 0
    unique_documents: int = 0
    duplicate_clusters: list[DuplicateCluster] = field(default_factory=list)
    stale_content: list[StaleContent] = field(default_factory=list)
    coverage_gaps: list[CoverageGap] = field(default_factory=list)
    health_score: float = 1.0  # 0-1 overall health
    recommendations: list[str] = field(default_factory=list)
    processing_time_ms: int = 0


@dataclass(slots=True)
class QueryReviewResult:
    """Result of query/response review."""
    query_id: str
    query_text: str
    accuracy_score: float = 0.0      # Response matches sources?
    grounding_score: float = 0.0     # Is response grounded in chunks?
    relevance_score: float = 0.0     # Did we retrieve right chunks?
    overall_quality: float = 0.0     # Weighted average
    hallucination_detected: bool = False
    hallucination_details: Optional[str] = None
    chunk_relevance: dict[str, float] = field(default_factory=dict)
    feedback: list[str] = field(default_factory=list)
    processing_ms: int = 0


@dataclass(slots=True)
class QueryPattern:
    """Identified query pattern for learning."""
    pattern: str
    frequency: int = 0
    avg_quality: float = 0.0
    common_issues: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EnforcerMetrics:
    """Aggregated metrics from all enforcement levels."""
    # Level 1 - Chunks
    chunks_processed: int = 0
    chunks_approved: int = 0
    chunks_rejected: int = 0
    avg_chunk_quality: float = 0.0

    # Level 2 - Index
    validations_run: int = 0
    current_health_score: float = 0.0
    duplicates_found: int = 0
    stale_content_found: int = 0

    # Level 3 - Queries
    queries_reviewed: int = 0
    hallucinations_detected: int = 0
    avg_accuracy: float = 0.0
    avg_grounding: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "level_1_chunks": {
                "processed": self.chunks_processed,
                "approved": self.chunks_approved,
                "rejected": self.chunks_rejected,
                "approval_rate": (
                    self.chunks_approved / self.chunks_processed
                    if self.chunks_processed > 0 else 0
                ),
                "avg_quality": self.avg_chunk_quality,
            },
            "level_2_index": {
                "validations_run": self.validations_run,
                "current_health_score": self.current_health_score,
                "duplicates_found": self.duplicates_found,
                "stale_content_found": self.stale_content_found,
            },
            "level_3_queries": {
                "reviewed": self.queries_reviewed,
                "hallucinations_detected": self.hallucinations_detected,
                "hallucination_rate": (
                    self.hallucinations_detected / self.queries_reviewed
                    if self.queries_reviewed > 0 else 0
                ),
                "avg_accuracy": self.avg_accuracy,
                "avg_grounding": self.avg_grounding,
            },
        }


@dataclass(slots=True)
class SchedulerStatus:
    """Status of the validation scheduler."""
    running: bool = False
    last_validation: Optional[str] = None
    next_validation: Optional[str] = None
    uploads_since_validation: int = 0
    upload_threshold: int = 50
    reports_count: int = 0
    latest_health_score: Optional[float] = None
