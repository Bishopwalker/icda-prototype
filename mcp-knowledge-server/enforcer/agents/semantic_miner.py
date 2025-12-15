"""SemanticMinerAgent - Agent 2 of 5 in the Enforcer Pipeline.

Extracts entities, patterns, relationships, and rules from content.
Handles PR-specific patterns and address validation rules.

Ultrathink Pattern:
1. Classification - Identify extractable elements
2. Detection - Find entities, patterns, rules
3. Validation - Verify extracted elements
4. Output - Produce SemanticResult
"""

import logging
import re
import time
from typing import Any

from ..models import (
    AddressRule,
    AddressPattern,
    ExtractionResult,
    ExtractionType,
    IntakeResult,
    SemanticResult,
)
from ..quality_gates import (
    EnforcerGate,
    EnforcerGateResult,
    GateCategory,
)


logger = logging.getLogger(__name__)


# Entity extraction patterns
ENTITY_PATTERNS = {
    "state": r"\b([A-Z]{2})\b",
    "zip_code": r"\b(\d{5})(?:-\d{4})?\b",
    "city": r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b",
    "street_type": r"\b(Street|St|Avenue|Ave|Boulevard|Blvd|Road|Rd|Lane|Ln|Drive|Dr|Court|Ct|Place|Pl|Way|Circle|Cir)\b",
    "urbanization": r"\b(?:URB|URBANIZACION|URBANIZACIÓN)\s+([A-Z][A-Za-z\s]+)\b",
}

# Rule extraction patterns
RULE_INDICATORS = [
    r"(?:if|when)\s+(.+?)\s*[,;:]\s*(?:then\s+)?(.+)",
    r"(?:must|should|require)\s+(.+)",
    r"(?:validate|check|verify)\s+that\s+(.+)",
]

# Pattern extraction patterns
REGEX_PATTERN = r"`([^`]+)`|'([^']+)'|\"([^\"]+)\""


class SemanticMinerAgent:
    """Agent 2: Extracts semantic elements from content.

    Quality Gates Enforced:
    - SEMANTIC_ENTITIES_FOUND: Named entities extracted
    - SEMANTIC_PATTERNS_VALID: Regex patterns compile
    - SEMANTIC_EXAMPLES_COMPLETE: Examples have context
    - SEMANTIC_RELATIONS_COHERENT: Relationships logical
    """

    def __init__(self):
        """Initialize the SemanticMinerAgent."""
        self.stats = {
            "processed": 0,
            "entities_extracted": 0,
            "patterns_extracted": 0,
            "rules_extracted": 0,
            "pr_patterns_found": 0,
        }

    async def process(
        self,
        intake: IntakeResult,
    ) -> tuple[SemanticResult, list[EnforcerGateResult]]:
        """Process content for semantic extraction.

        Ultrathink 4-Phase Analysis:
        1. Classification - Identify what can be extracted
        2. Detection - Extract entities, patterns, rules
        3. Validation - Verify extracted elements
        4. Output - Produce SemanticResult

        Args:
            intake: Result from IntakeGuardAgent.

        Returns:
            Tuple of (SemanticResult, list of gate results).
        """
        start_time = time.time()
        self.stats["processed"] += 1
        gates: list[EnforcerGateResult] = []

        content = intake.raw_content
        parsed = intake.parsed_content

        # Phase 1: Classification - Identify extractable elements
        extractable = self._identify_extractables(content, parsed)
        logger.debug(f"Identified extractables: {list(extractable.keys())}")

        # Phase 2: Detection - Extract elements
        extractions: list[ExtractionResult] = []
        entities: list[dict[str, Any]] = []
        rules: list[AddressRule] = []
        patterns: list[AddressPattern] = []
        relationships: list[dict[str, Any]] = []
        pr_patterns: list[dict[str, Any]] = []

        # Extract entities
        extracted_entities = self._extract_entities(content)
        entities.extend(extracted_entities)
        for entity in extracted_entities:
            extractions.append(ExtractionResult(
                extraction_type=ExtractionType.ENTITY,
                content=entity,
                confidence=entity.get("confidence", 0.8),
            ))
        self.stats["entities_extracted"] += len(entities)

        # Extract rules
        extracted_rules = self._extract_rules(content)
        rules.extend(extracted_rules)
        for rule in extracted_rules:
            extractions.append(ExtractionResult(
                extraction_type=ExtractionType.RULE,
                content={"name": rule.name, "condition": rule.condition, "action": rule.action},
                confidence=rule.confidence,
            ))
        self.stats["rules_extracted"] += len(rules)

        # Extract patterns
        extracted_patterns = self._extract_patterns(content)
        patterns.extend(extracted_patterns)
        for pattern in extracted_patterns:
            extractions.append(ExtractionResult(
                extraction_type=ExtractionType.PATTERN,
                content={"name": pattern.name, "regex": pattern.regex},
                confidence=pattern.confidence,
            ))
        self.stats["patterns_extracted"] += len(patterns)

        # Extract PR-specific patterns if relevant
        if intake.is_pr_relevant:
            pr_patterns = self._extract_pr_patterns(content)
            self.stats["pr_patterns_found"] += len(pr_patterns)

        # Extract relationships
        relationships = self._extract_relationships(entities, rules)

        # Phase 3: Validation - Quality Gates

        # Gate 1: SEMANTIC_ENTITIES_FOUND
        has_entities = len(entities) > 0
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.SEMANTIC_ENTITIES_FOUND,
            passed=has_entities,
            message=f"Found {len(entities)} entities" if has_entities else "No entities found",
            details={"entity_count": len(entities), "entity_types": list({e["type"] for e in entities})},
            category=GateCategory.SEMANTIC,
            severity="warning",
        ))

        # Gate 2: SEMANTIC_PATTERNS_VALID
        valid_patterns = [p for p in patterns if p.is_valid]
        all_patterns_valid = len(valid_patterns) == len(patterns)
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.SEMANTIC_PATTERNS_VALID,
            passed=all_patterns_valid or len(patterns) == 0,
            message=f"All {len(patterns)} patterns valid" if all_patterns_valid
                    else f"{len(patterns) - len(valid_patterns)} invalid patterns",
            details={"total_patterns": len(patterns), "valid_patterns": len(valid_patterns)},
            category=GateCategory.SEMANTIC,
            severity="warning",
        ))

        # Gate 3: SEMANTIC_EXAMPLES_COMPLETE
        examples_found = self._extract_examples(content)
        examples_with_context = [e for e in examples_found if e.get("has_context")]
        has_complete_examples = len(examples_with_context) >= len(examples_found) * 0.5 or len(examples_found) == 0
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.SEMANTIC_EXAMPLES_COMPLETE,
            passed=has_complete_examples,
            message=f"{len(examples_with_context)}/{len(examples_found)} examples have context",
            details={"total_examples": len(examples_found), "with_context": len(examples_with_context)},
            category=GateCategory.SEMANTIC,
            severity="info",
        ))

        # Gate 4: SEMANTIC_RELATIONS_COHERENT
        has_coherent_relations = self._validate_relationships(relationships)
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.SEMANTIC_RELATIONS_COHERENT,
            passed=has_coherent_relations,
            message="Relationships are coherent" if has_coherent_relations
                    else "Some relationships may be inconsistent",
            details={"relationship_count": len(relationships)},
            category=GateCategory.SEMANTIC,
            severity="info",
        ))

        # Phase 4: Output
        elapsed_ms = int((time.time() - start_time) * 1000)

        # Calculate overall confidence
        confidence_scores = [e.confidence for e in extractions if e.confidence > 0]
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5

        result = SemanticResult(
            extractions=extractions,
            rules=rules,
            patterns=patterns,
            entities=entities,
            relationships=relationships,
            pr_patterns=pr_patterns,
            confidence=overall_confidence,
        )

        return result, gates

    def _identify_extractables(
        self,
        content: str,
        parsed: dict[str, Any],
    ) -> dict[str, bool]:
        """Identify what types of elements can be extracted.

        Args:
            content: Raw content.
            parsed: Parsed content from intake.

        Returns:
            Dictionary of extractable element types.
        """
        return {
            "entities": bool(re.search(r"\b[A-Z]{2}\b|\b\d{5}\b", content)),
            "rules": bool(re.search(r"\b(if|when|must|should)\b", content, re.I)),
            "patterns": bool(re.search(r"`[^`]+`|'[^']+'", content)),
            "examples": bool(re.search(r"\bexample|e\.g\.|for instance\b", content, re.I)),
            "sections": "sections" in parsed,
        }

    def _extract_entities(self, content: str) -> list[dict[str, Any]]:
        """Extract named entities from content.

        Args:
            content: Content to process.

        Returns:
            List of entity dictionaries.
        """
        entities = []

        for entity_type, pattern in ENTITY_PATTERNS.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                value = match if isinstance(match, str) else match[0]
                if value.strip():
                    entities.append({
                        "type": entity_type,
                        "value": value.strip(),
                        "confidence": 0.8,
                    })

        # Deduplicate
        seen = set()
        unique_entities = []
        for entity in entities:
            key = (entity["type"], entity["value"])
            if key not in seen:
                seen.add(key)
                unique_entities.append(entity)

        return unique_entities

    def _extract_rules(self, content: str) -> list[AddressRule]:
        """Extract business rules from content.

        Args:
            content: Content to process.

        Returns:
            List of extracted rules.
        """
        rules = []

        # Look for rule-like structures
        lines = content.split("\n")
        for i, line in enumerate(lines):
            line_lower = line.lower()

            # Check for rule indicators
            for pattern in RULE_INDICATORS:
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    groups = match.groups()
                    if len(groups) >= 2:
                        condition, action = groups[0], groups[1]
                    elif len(groups) == 1:
                        condition = groups[0]
                        action = "validate"
                    else:
                        continue

                    rule = AddressRule(
                        name=f"rule_{len(rules) + 1}",
                        condition=condition.strip() if condition else "",
                        action=action.strip() if action else "",
                        confidence=0.7,
                    )
                    rules.append(rule)
                    break

            # Check for PR-specific rules
            if "puerto rico" in line_lower or "urbaniz" in line_lower:
                if "required" in line_lower or "must" in line_lower:
                    rules.append(AddressRule(
                        name="pr_urbanization_required",
                        condition="address is Puerto Rico (ZIP 006-009)",
                        action="require urbanization field",
                        scope="PR",
                        confidence=0.9,
                    ))

        return rules

    def _extract_patterns(self, content: str) -> list[AddressPattern]:
        """Extract regex patterns from content.

        Args:
            content: Content to process.

        Returns:
            List of extracted patterns.
        """
        patterns = []

        # Find patterns in backticks, quotes
        matches = re.findall(REGEX_PATTERN, content)
        for match in matches:
            # match is a tuple from the groups
            pattern_str = next((m for m in match if m), None)
            if pattern_str:
                # Check if it looks like a regex
                if any(c in pattern_str for c in ["^", "$", "[", "]", "*", "+", "?", "\\d", "\\w"]):
                    is_valid = self._validate_regex(pattern_str)
                    patterns.append(AddressPattern(
                        name=f"pattern_{len(patterns) + 1}",
                        regex=pattern_str,
                        description="Extracted pattern",
                        is_valid=is_valid,
                        confidence=0.6 if is_valid else 0.3,
                    ))

        return patterns

    def _extract_pr_patterns(self, content: str) -> list[dict[str, Any]]:
        """Extract Puerto Rico specific patterns.

        Args:
            content: Content to process.

        Returns:
            List of PR pattern dictionaries.
        """
        pr_patterns = []

        # Look for urbanization patterns
        urb_matches = re.findall(
            r"(?:URB|URBANIZACION|URBANIZACIÓN)\s+([A-Za-z\s]+)",
            content,
            re.IGNORECASE,
        )
        for match in urb_matches:
            pr_patterns.append({
                "type": "urbanization",
                "value": match.strip(),
                "confidence": 0.85,
            })

        # Look for PR ZIP codes
        zip_matches = re.findall(r"\b(00[6-9]\d{2})(?:-\d{4})?\b", content)
        for match in zip_matches:
            pr_patterns.append({
                "type": "pr_zip",
                "value": match,
                "confidence": 0.95,
            })

        # Look for Spanish street terms
        spanish_terms = ["calle", "avenida", "carretera", "camino"]
        for term in spanish_terms:
            if term in content.lower():
                pr_patterns.append({
                    "type": "spanish_street_term",
                    "value": term,
                    "confidence": 0.8,
                })

        return pr_patterns

    def _extract_examples(self, content: str) -> list[dict[str, Any]]:
        """Extract examples from content.

        Args:
            content: Content to process.

        Returns:
            List of example dictionaries.
        """
        examples = []
        lines = content.split("\n")

        for i, line in enumerate(lines):
            # Look for example indicators
            if re.search(r"\bexample|e\.g\.|for instance|→|=>|->", line, re.I):
                # Get context (surrounding lines)
                context_before = lines[max(0, i - 2):i]
                context_after = lines[i + 1:min(len(lines), i + 3)]

                examples.append({
                    "content": line,
                    "line": i,
                    "has_context": bool(context_before or context_after),
                    "context_before": context_before,
                    "context_after": context_after,
                })

        return examples

    def _extract_relationships(
        self,
        entities: list[dict[str, Any]],
        rules: list[AddressRule],
    ) -> list[dict[str, Any]]:
        """Extract relationships between entities and rules.

        Args:
            entities: Extracted entities.
            rules: Extracted rules.

        Returns:
            List of relationship dictionaries.
        """
        relationships = []

        # Link ZIP codes to states
        zips = [e for e in entities if e["type"] == "zip_code"]
        states = [e for e in entities if e["type"] == "state"]

        for zip_entity in zips:
            zip_code = zip_entity["value"]
            # PR ZIP codes
            if zip_code.startswith(("006", "007", "008", "009")):
                relationships.append({
                    "from": zip_entity,
                    "to": {"type": "state", "value": "PR"},
                    "relationship": "belongs_to",
                    "confidence": 0.95,
                })

        # Link rules to entities
        for rule in rules:
            if "PR" in rule.scope or "puerto rico" in rule.condition.lower():
                relationships.append({
                    "from": {"type": "rule", "value": rule.name},
                    "to": {"type": "state", "value": "PR"},
                    "relationship": "applies_to",
                    "confidence": 0.9,
                })

        return relationships

    def _validate_relationships(self, relationships: list[dict[str, Any]]) -> bool:
        """Validate that relationships are coherent.

        Args:
            relationships: List of relationships.

        Returns:
            True if relationships are coherent.
        """
        if not relationships:
            return True

        # Check for contradictions
        for rel in relationships:
            # Basic coherence check
            if rel.get("from") and rel.get("to") and rel.get("relationship"):
                continue
            return False

        return True

    def _validate_regex(self, pattern: str) -> bool:
        """Validate that a regex pattern compiles.

        Args:
            pattern: Regex pattern string.

        Returns:
            True if pattern compiles.
        """
        try:
            re.compile(pattern)
            return True
        except re.error:
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Statistics dictionary.
        """
        return self.stats.copy()
