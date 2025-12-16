"""Quality gates for the 5-Agent Enforcer System.

Defines quality gates enforced by each agent in the pipeline,
following the Russian Olympic Judge standard for validation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GateCategory(str, Enum):
    """Category of quality gate."""

    INTAKE = "intake"           # Input validation gates
    SEMANTIC = "semantic"       # Extraction quality gates
    CONTEXT = "context"         # Linking quality gates
    QUALITY = "quality"         # Final validation gates
    INDEX = "index"             # Indexing success gates


class EnforcerGate(str, Enum):
    """Quality gates enforced by the 5-agent pipeline.

    Naming convention: AGENT_GATENAME
    """

    # IntakeGuardAgent gates
    INTAKE_PARSEABLE = "intake_parseable"
    INTAKE_NOT_EMPTY = "intake_not_empty"
    INTAKE_VALID_FORMAT = "intake_valid_format"
    INTAKE_SIZE_LIMIT = "intake_size_limit"
    INTAKE_DUPLICATE_CHECK = "intake_duplicate_check"

    # SemanticMinerAgent gates
    SEMANTIC_ENTITIES_FOUND = "semantic_entities_found"
    SEMANTIC_PATTERNS_VALID = "semantic_patterns_valid"
    SEMANTIC_EXAMPLES_COMPLETE = "semantic_examples_complete"
    SEMANTIC_RELATIONS_COHERENT = "semantic_relations_coherent"

    # ContextLinkerAgent gates
    CONTEXT_REFERENCES_RESOLVED = "context_references_resolved"
    CONTEXT_NO_CONFLICTS = "context_no_conflicts"
    CONTEXT_GRAPH_CONNECTED = "context_graph_connected"
    CONTEXT_COVERAGE_ADEQUATE = "context_coverage_adequate"

    # QualityEnforcerAgent gates
    QUALITY_ACCURACY_VERIFIED = "quality_accuracy_verified"
    QUALITY_COMPLETENESS_MET = "quality_completeness_met"
    QUALITY_CONSISTENCY_CHECKED = "quality_consistency_checked"
    QUALITY_EXAMPLES_VALIDATED = "quality_examples_validated"
    QUALITY_CONFIDENCE_THRESHOLD = "quality_confidence_threshold"

    # IndexSyncAgent gates
    INDEX_EMBEDDING_GENERATED = "index_embedding_generated"
    INDEX_DOCUMENT_STORED = "index_document_stored"
    INDEX_SEARCHABLE = "index_searchable"
    INDEX_METADATA_COMPLETE = "index_metadata_complete"
    INDEX_BATCH_COMPLETE = "index_batch_complete"


@dataclass(slots=True)
class EnforcerGateResult:
    """Result of evaluating a quality gate.

    Attributes:
        gate: The quality gate evaluated.
        passed: Whether the gate passed.
        message: Human-readable result message.
        details: Additional gate-specific details.
        category: Gate category for grouping.
        severity: Impact if failed (critical, warning, info).
    """

    gate: EnforcerGate
    passed: bool
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    category: GateCategory = GateCategory.INTAKE
    severity: str = "warning"

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "gate": self.gate.value,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "category": self.category.value,
            "severity": self.severity,
        }


# Gate configuration with default thresholds and descriptions
GATE_CONFIG: dict[EnforcerGate, dict[str, Any]] = {
    # Intake gates
    EnforcerGate.INTAKE_PARSEABLE: {
        "description": "Content can be read and parsed",
        "category": GateCategory.INTAKE,
        "severity": "critical",
        "blocking": True,
    },
    EnforcerGate.INTAKE_NOT_EMPTY: {
        "description": "Content has meaningful data",
        "category": GateCategory.INTAKE,
        "severity": "critical",
        "blocking": True,
    },
    EnforcerGate.INTAKE_VALID_FORMAT: {
        "description": "Content is in supported format",
        "category": GateCategory.INTAKE,
        "severity": "critical",
        "blocking": True,
    },
    EnforcerGate.INTAKE_SIZE_LIMIT: {
        "description": "Content is under 10MB size limit",
        "category": GateCategory.INTAKE,
        "severity": "critical",
        "blocking": True,
        "threshold": 10 * 1024 * 1024,  # 10MB
    },
    EnforcerGate.INTAKE_DUPLICATE_CHECK: {
        "description": "Content is not already indexed",
        "category": GateCategory.INTAKE,
        "severity": "warning",
        "blocking": False,
    },
    # Semantic gates
    EnforcerGate.SEMANTIC_ENTITIES_FOUND: {
        "description": "Named entities were extracted",
        "category": GateCategory.SEMANTIC,
        "severity": "warning",
        "blocking": False,
        "min_entities": 1,
    },
    EnforcerGate.SEMANTIC_PATTERNS_VALID: {
        "description": "Regex patterns compile successfully",
        "category": GateCategory.SEMANTIC,
        "severity": "warning",
        "blocking": False,
    },
    EnforcerGate.SEMANTIC_EXAMPLES_COMPLETE: {
        "description": "Examples have sufficient context",
        "category": GateCategory.SEMANTIC,
        "severity": "info",
        "blocking": False,
    },
    EnforcerGate.SEMANTIC_RELATIONS_COHERENT: {
        "description": "Entity relationships are logical",
        "category": GateCategory.SEMANTIC,
        "severity": "info",
        "blocking": False,
    },
    # Context gates
    EnforcerGate.CONTEXT_REFERENCES_RESOLVED: {
        "description": "External references linked successfully",
        "category": GateCategory.CONTEXT,
        "severity": "warning",
        "blocking": False,
    },
    EnforcerGate.CONTEXT_NO_CONFLICTS: {
        "description": "No contradictions with existing knowledge",
        "category": GateCategory.CONTEXT,
        "severity": "warning",
        "blocking": False,
    },
    EnforcerGate.CONTEXT_GRAPH_CONNECTED: {
        "description": "Links to existing knowledge graph",
        "category": GateCategory.CONTEXT,
        "severity": "info",
        "blocking": False,
    },
    EnforcerGate.CONTEXT_COVERAGE_ADEQUATE: {
        "description": "Sufficient topic coverage",
        "category": GateCategory.CONTEXT,
        "severity": "info",
        "blocking": False,
        "min_coverage": 0.3,
    },
    # Quality gates (Russian Olympic Judge standard)
    EnforcerGate.QUALITY_ACCURACY_VERIFIED: {
        "description": "Facts are verifiable and correct",
        "category": GateCategory.QUALITY,
        "severity": "critical",
        "blocking": True,
        "min_accuracy": 0.8,
    },
    EnforcerGate.QUALITY_COMPLETENESS_MET: {
        "description": "Required elements present",
        "category": GateCategory.QUALITY,
        "severity": "warning",
        "blocking": False,
        "min_completeness": 0.7,
    },
    EnforcerGate.QUALITY_CONSISTENCY_CHECKED: {
        "description": "No self-contradictions found",
        "category": GateCategory.QUALITY,
        "severity": "warning",
        "blocking": False,
    },
    EnforcerGate.QUALITY_EXAMPLES_VALIDATED: {
        "description": "Examples parse correctly",
        "category": GateCategory.QUALITY,
        "severity": "warning",
        "blocking": False,
    },
    EnforcerGate.QUALITY_CONFIDENCE_THRESHOLD: {
        "description": "Overall confidence >= 0.7",
        "category": GateCategory.QUALITY,
        "severity": "critical",
        "blocking": True,
        "min_confidence": 0.7,
    },
    # Index gates
    EnforcerGate.INDEX_EMBEDDING_GENERATED: {
        "description": "Titan embedding created successfully",
        "category": GateCategory.INDEX,
        "severity": "critical",
        "blocking": True,
    },
    EnforcerGate.INDEX_DOCUMENT_STORED: {
        "description": "Document stored in OpenSearch",
        "category": GateCategory.INDEX,
        "severity": "critical",
        "blocking": True,
    },
    EnforcerGate.INDEX_SEARCHABLE: {
        "description": "Test query returns the content",
        "category": GateCategory.INDEX,
        "severity": "warning",
        "blocking": False,
    },
    EnforcerGate.INDEX_METADATA_COMPLETE: {
        "description": "All metadata fields populated",
        "category": GateCategory.INDEX,
        "severity": "info",
        "blocking": False,
    },
    EnforcerGate.INDEX_BATCH_COMPLETE: {
        "description": "All batch items processed",
        "category": GateCategory.INDEX,
        "severity": "critical",
        "blocking": True,
    },
}


def get_gate_config(gate: EnforcerGate) -> dict[str, Any]:
    """Get configuration for a specific gate.

    Args:
        gate: The quality gate.

    Returns:
        Gate configuration dictionary.
    """
    return GATE_CONFIG.get(gate, {
        "description": "Unknown gate",
        "category": GateCategory.INTAKE,
        "severity": "info",
        "blocking": False,
    })


def is_blocking_gate(gate: EnforcerGate) -> bool:
    """Check if a gate is blocking (pipeline stops on failure).

    Args:
        gate: The quality gate.

    Returns:
        True if gate failure should stop the pipeline.
    """
    config = get_gate_config(gate)
    return config.get("blocking", False)


def get_gates_by_category(category: GateCategory) -> list[EnforcerGate]:
    """Get all gates in a category.

    Args:
        category: The gate category.

    Returns:
        List of gates in that category.
    """
    return [
        gate for gate, config in GATE_CONFIG.items()
        if config.get("category") == category
    ]


def summarize_gate_results(results: list[EnforcerGateResult]) -> dict[str, Any]:
    """Summarize a list of gate results.

    Args:
        results: List of gate results.

    Returns:
        Summary with counts and blocking failures.
    """
    passed = [r for r in results if r.passed]
    failed = [r for r in results if not r.passed]
    blocking_failures = [r for r in failed if is_blocking_gate(r.gate)]

    by_category: dict[str, dict[str, int]] = {}
    for result in results:
        cat = result.category.value
        if cat not in by_category:
            by_category[cat] = {"passed": 0, "failed": 0}
        if result.passed:
            by_category[cat]["passed"] += 1
        else:
            by_category[cat]["failed"] += 1

    return {
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "blocking_failures": len(blocking_failures),
        "by_category": by_category,
        "can_continue": len(blocking_failures) == 0,
    }
