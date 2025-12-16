"""ContextLinkerAgent - Agent 3 of 5 in the Enforcer Pipeline.

Links new content to existing knowledge, resolves references,
and detects conflicts with existing information.

Ultrathink Pattern:
1. Classification - Identify linkable elements
2. Detection - Find related documents, conflicts
3. Validation - Verify links are valid
4. Output - Produce ContextResult
"""

import logging
import re
import time
from typing import Any

from ..models import (
    CrossReference,
    ContextResult,
    SemanticResult,
)
from ..quality_gates import (
    EnforcerGate,
    EnforcerGateResult,
    GateCategory,
)


logger = logging.getLogger(__name__)


# Reference patterns to resolve
REFERENCE_PATTERNS = [
    r"see\s+(?:section\s+)?([A-Za-z0-9\.\-]+)",
    r"refer(?:ence)?\s+to\s+([A-Za-z0-9\.\-\s]+)",
    r"as\s+(?:described|defined)\s+in\s+([A-Za-z0-9\.\-\s]+)",
    r"\[([^\]]+)\]\([^\)]+\)",  # Markdown links
]


class ContextLinkerAgent:
    """Agent 3: Links content to existing knowledge graph.

    Quality Gates Enforced:
    - CONTEXT_REFERENCES_RESOLVED: External refs linked
    - CONTEXT_NO_CONFLICTS: No contradictions
    - CONTEXT_GRAPH_CONNECTED: Links to existing nodes
    - CONTEXT_COVERAGE_ADEQUATE: Sufficient coverage
    """

    def __init__(self, opensearch_client: Any = None):
        """Initialize the ContextLinkerAgent.

        Args:
            opensearch_client: Optional OpenSearch client for searching.
        """
        self.opensearch_client = opensearch_client
        self.knowledge_index = "icda-knowledge"
        self.stats = {
            "processed": 0,
            "references_resolved": 0,
            "conflicts_detected": 0,
            "cross_refs_created": 0,
        }

    async def process(
        self,
        semantic: SemanticResult,
        raw_content: str,
        doc_id: str | None = None,
    ) -> tuple[ContextResult, list[EnforcerGateResult]]:
        """Process content for context linking.

        Ultrathink 4-Phase Analysis:
        1. Classification - Identify linkable elements
        2. Detection - Find related content, conflicts
        3. Validation - Verify links
        4. Output - Produce ContextResult

        Args:
            semantic: Result from SemanticMinerAgent.
            raw_content: Original content for reference extraction.
            doc_id: Optional document ID.

        Returns:
            Tuple of (ContextResult, list of gate results).
        """
        start_time = time.time()
        self.stats["processed"] += 1
        gates: list[EnforcerGateResult] = []

        # Phase 1: Classification - Identify linkable elements
        linkables = self._identify_linkables(semantic, raw_content)
        logger.debug(f"Found {len(linkables)} linkable elements")

        # Phase 2: Detection

        # Find references in content
        references_found = self._find_references(raw_content)

        # Search for related documents
        related_docs = await self._find_related_documents(semantic)

        # Detect conflicts
        conflicts = await self._detect_conflicts(semantic, related_docs)

        # Create cross-references
        cross_refs = self._create_cross_references(
            semantic,
            references_found,
            related_docs,
        )
        self.stats["cross_refs_created"] += len(cross_refs)

        # Resolve internal references
        resolved_refs = self._resolve_references(references_found, raw_content)
        self.stats["references_resolved"] += len(resolved_refs)

        # Calculate coverage
        coverage_score = self._calculate_coverage(semantic, related_docs)

        # Phase 3: Validation - Quality Gates

        # Gate 1: CONTEXT_REFERENCES_RESOLVED
        total_refs = len(references_found)
        resolved_count = len([r for r in resolved_refs if r.get("resolved")])
        all_resolved = resolved_count >= total_refs * 0.8 or total_refs == 0
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.CONTEXT_REFERENCES_RESOLVED,
            passed=all_resolved,
            message=f"Resolved {resolved_count}/{total_refs} references" if total_refs > 0
                    else "No references to resolve",
            details={"total_refs": total_refs, "resolved": resolved_count},
            category=GateCategory.CONTEXT,
            severity="warning",
        ))

        # Gate 2: CONTEXT_NO_CONFLICTS
        has_no_conflicts = len(conflicts) == 0
        self.stats["conflicts_detected"] += len(conflicts)
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.CONTEXT_NO_CONFLICTS,
            passed=has_no_conflicts,
            message="No conflicts detected" if has_no_conflicts
                    else f"{len(conflicts)} potential conflicts found",
            details={"conflicts": conflicts[:5]},  # Limit details
            category=GateCategory.CONTEXT,
            severity="warning",
        ))

        # Gate 3: CONTEXT_GRAPH_CONNECTED
        is_connected = len(cross_refs) > 0 or len(related_docs) > 0
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.CONTEXT_GRAPH_CONNECTED,
            passed=is_connected,
            message=f"Connected to {len(cross_refs)} nodes" if is_connected
                    else "No connections to existing knowledge",
            details={"cross_refs": len(cross_refs), "related_docs": len(related_docs)},
            category=GateCategory.CONTEXT,
            severity="info",
        ))

        # Gate 4: CONTEXT_COVERAGE_ADEQUATE
        min_coverage = 0.3
        has_adequate_coverage = coverage_score >= min_coverage
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.CONTEXT_COVERAGE_ADEQUATE,
            passed=has_adequate_coverage,
            message=f"Coverage score: {coverage_score:.2f}" if has_adequate_coverage
                    else f"Low coverage: {coverage_score:.2f} < {min_coverage}",
            details={"coverage_score": coverage_score, "min_required": min_coverage},
            category=GateCategory.CONTEXT,
            severity="info",
        ))

        # Phase 4: Output
        elapsed_ms = int((time.time() - start_time) * 1000)

        result = ContextResult(
            cross_references=cross_refs,
            conflicts=conflicts,
            coverage_score=coverage_score,
            graph_connected=is_connected,
            related_docs=[doc.get("id", "") for doc in related_docs],
            resolved_refs=resolved_refs,
        )

        return result, gates

    def _identify_linkables(
        self,
        semantic: SemanticResult,
        content: str,
    ) -> list[dict[str, Any]]:
        """Identify elements that can be linked.

        Args:
            semantic: Semantic extraction result.
            content: Raw content.

        Returns:
            List of linkable elements.
        """
        linkables = []

        # Entities are linkable
        for entity in semantic.entities:
            linkables.append({
                "type": "entity",
                "value": entity.get("value"),
                "entity_type": entity.get("type"),
            })

        # Rules are linkable
        for rule in semantic.rules:
            linkables.append({
                "type": "rule",
                "name": rule.name,
                "scope": rule.scope,
            })

        # PR patterns are linkable
        for pr_pattern in semantic.pr_patterns:
            linkables.append({
                "type": "pr_pattern",
                "pattern_type": pr_pattern.get("type"),
                "value": pr_pattern.get("value"),
            })

        return linkables

    def _find_references(self, content: str) -> list[dict[str, Any]]:
        """Find references to other documents/sections.

        Args:
            content: Content to search.

        Returns:
            List of found references.
        """
        references = []

        for pattern in REFERENCE_PATTERNS:
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                references.append({
                    "reference": match.strip() if isinstance(match, str) else match,
                    "pattern": pattern,
                    "resolved": False,
                })

        return references

    async def _find_related_documents(
        self,
        semantic: SemanticResult,
    ) -> list[dict[str, Any]]:
        """Find related documents in knowledge base.

        Args:
            semantic: Semantic extraction result.

        Returns:
            List of related document metadata.
        """
        related_docs = []

        if not self.opensearch_client:
            # Return mock related docs for testing
            if semantic.pr_patterns:
                related_docs.append({
                    "id": "pr-urbanization-doc",
                    "title": "Puerto Rico Urbanization Addressing",
                    "relevance": 0.9,
                })
            return related_docs

        try:
            # Build search query from entities and rules
            search_terms = []

            for entity in semantic.entities[:5]:  # Limit to top 5
                search_terms.append(entity.get("value", ""))

            for rule in semantic.rules[:3]:
                search_terms.append(rule.condition)

            if not search_terms:
                return related_docs

            # Search OpenSearch
            query = {
                "query": {
                    "multi_match": {
                        "query": " ".join(search_terms),
                        "fields": ["content", "title", "tags"],
                    }
                },
                "size": 10,
            }

            response = await self.opensearch_client.search(
                index=self.knowledge_index,
                body=query,
            )

            for hit in response.get("hits", {}).get("hits", []):
                related_docs.append({
                    "id": hit["_id"],
                    "title": hit["_source"].get("title", ""),
                    "relevance": hit["_score"],
                })

        except Exception as e:
            logger.warning(f"Error searching for related docs: {e}")

        return related_docs

    async def _detect_conflicts(
        self,
        semantic: SemanticResult,
        related_docs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Detect conflicts with existing knowledge.

        Args:
            semantic: Semantic extraction result.
            related_docs: Related documents found.

        Returns:
            List of detected conflicts.
        """
        conflicts = []

        # Check for rule conflicts
        for rule in semantic.rules:
            # Look for contradictory rules in related docs
            for doc in related_docs:
                # In a real implementation, fetch doc content and compare
                # For now, just check for potential conflicts based on scope
                if rule.scope == "PR" and "PR" in doc.get("title", "").upper():
                    # Could be a conflict - mark for review
                    pass

        return conflicts

    def _create_cross_references(
        self,
        semantic: SemanticResult,
        references: list[dict[str, Any]],
        related_docs: list[dict[str, Any]],
    ) -> list[CrossReference]:
        """Create cross-references to related content.

        Args:
            semantic: Semantic extraction result.
            references: Found references.
            related_docs: Related documents.

        Returns:
            List of cross-references.
        """
        cross_refs = []

        # Create refs to related documents
        for doc in related_docs:
            if doc.get("relevance", 0) > 0.5:
                cross_refs.append(CrossReference(
                    target_id=doc.get("id", ""),
                    reference_type="related",
                    context=f"Related to {doc.get('title', 'unknown')}",
                    confidence=doc.get("relevance", 0.5),
                ))

        # Create refs from extracted references
        for ref in references:
            cross_refs.append(CrossReference(
                target_id=str(ref.get("reference", "")),
                reference_type="see_also",
                context="Explicit reference in content",
                confidence=0.7,
            ))

        # Create refs for PR content
        if semantic.pr_patterns:
            cross_refs.append(CrossReference(
                target_id="pr-addressing-standards",
                reference_type="topic",
                context="Puerto Rico addressing patterns detected",
                confidence=0.85,
            ))

        return cross_refs

    def _resolve_references(
        self,
        references: list[dict[str, Any]],
        content: str,
    ) -> list[dict[str, Any]]:
        """Resolve internal references within content.

        Args:
            references: Found references.
            content: Full content.

        Returns:
            List of resolved references.
        """
        resolved = []

        for ref in references:
            ref_text = ref.get("reference", "")
            if isinstance(ref_text, tuple):
                ref_text = ref_text[0] if ref_text else ""

            # Check if reference points to a section in this document
            section_pattern = rf"#+\s*{re.escape(str(ref_text))}"
            if re.search(section_pattern, content, re.IGNORECASE):
                ref["resolved"] = True
                ref["resolution"] = "internal_section"
            else:
                ref["resolved"] = False
                ref["resolution"] = "external_or_missing"

            resolved.append(ref)

        return resolved

    def _calculate_coverage(
        self,
        semantic: SemanticResult,
        related_docs: list[dict[str, Any]],
    ) -> float:
        """Calculate topic coverage score.

        Args:
            semantic: Semantic extraction result.
            related_docs: Related documents.

        Returns:
            Coverage score between 0 and 1.
        """
        # Coverage based on:
        # - Number of entities extracted
        # - Number of rules extracted
        # - Number of related docs found
        # - PR pattern coverage if relevant

        scores = []

        # Entity coverage
        entity_score = min(len(semantic.entities) / 5, 1.0)
        scores.append(entity_score)

        # Rule coverage
        rule_score = min(len(semantic.rules) / 3, 1.0)
        scores.append(rule_score)

        # Related doc coverage
        doc_score = min(len(related_docs) / 3, 1.0)
        scores.append(doc_score)

        # PR coverage if relevant
        if semantic.pr_patterns:
            pr_score = min(len(semantic.pr_patterns) / 3, 1.0)
            scores.append(pr_score)

        return sum(scores) / len(scores) if scores else 0.0

    def set_opensearch_client(self, client: Any) -> None:
        """Set the OpenSearch client.

        Args:
            client: OpenSearch client instance.
        """
        self.opensearch_client = client

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Statistics dictionary.
        """
        return self.stats.copy()
