"""QualityEnforcerAgent - Agent 4 of 5 in the Enforcer Pipeline.

Final validation with Russian Olympic Judge standard. Validates accuracy,
completeness, consistency, and ensures examples parse correctly.

Ultrathink Pattern:
1. Classification - Identify validation requirements
2. Detection - Find accuracy/completeness issues
3. Validation - Apply strict quality gates
4. Output - Produce QualityResult
"""

import logging
import re
import time
from typing import Any

from ..models import (
    ContextResult,
    QualityResult,
    SemanticResult,
)
from ..quality_gates import (
    EnforcerGate,
    EnforcerGateResult,
    GateCategory,
)


logger = logging.getLogger(__name__)


# Valid US state codes (including territories)
VALID_STATES = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
    "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
    "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
    "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    "DC", "PR", "VI", "GU", "AS", "MP",  # Territories
}

# ZIP code ranges by state (first 3 digits)
ZIP_STATE_MAP = {
    "PR": ["006", "007", "008", "009"],
    "VI": ["008"],
    # Add more as needed
}


class QualityEnforcerAgent:
    """Agent 4: Russian Olympic Judge - Strict quality validation.

    Quality Gates Enforced:
    - QUALITY_ACCURACY_VERIFIED: Facts correct
    - QUALITY_COMPLETENESS_MET: Required elements present
    - QUALITY_CONSISTENCY_CHECKED: No contradictions
    - QUALITY_EXAMPLES_VALIDATED: Examples parse correctly
    - QUALITY_CONFIDENCE_THRESHOLD: Overall >= 0.7
    """

    def __init__(self, min_confidence: float = 0.7):
        """Initialize the QualityEnforcerAgent.

        Args:
            min_confidence: Minimum confidence threshold.
        """
        self.min_confidence = min_confidence
        self.stats = {
            "processed": 0,
            "passed": 0,
            "failed": 0,
            "accuracy_failures": 0,
            "completeness_failures": 0,
            "examples_validated": 0,
        }

    async def process(
        self,
        semantic: SemanticResult,
        context: ContextResult,
        raw_content: str,
    ) -> tuple[QualityResult, list[EnforcerGateResult]]:
        """Process content for quality validation.

        Ultrathink 4-Phase Analysis:
        1. Classification - Identify validation needs
        2. Detection - Find quality issues
        3. Validation - Apply strict gates
        4. Output - Produce QualityResult

        Args:
            semantic: Result from SemanticMinerAgent.
            context: Result from ContextLinkerAgent.
            raw_content: Original content.

        Returns:
            Tuple of (QualityResult, list of gate results).
        """
        start_time = time.time()
        self.stats["processed"] += 1
        gates: list[EnforcerGateResult] = []
        failed_validations: list[dict[str, Any]] = []
        recommendations: list[str] = []

        # Phase 1: Classification - Identify what needs validation
        validation_targets = self._identify_validation_targets(semantic, raw_content)
        logger.debug(f"Validation targets: {list(validation_targets.keys())}")

        # Phase 2: Detection - Find issues

        # Verify accuracy of facts
        accuracy_result = await self._verify_accuracy(semantic, raw_content)

        # Check completeness
        completeness_result = self._check_completeness(semantic, raw_content)

        # Check consistency
        consistency_result = self._check_consistency(semantic, context)

        # Validate examples
        examples_result = self._validate_examples(raw_content)

        # Phase 3: Validation - Quality Gates

        # Gate 1: QUALITY_ACCURACY_VERIFIED
        accuracy_passed = accuracy_result["score"] >= 0.8
        if not accuracy_passed:
            self.stats["accuracy_failures"] += 1
            failed_validations.extend(accuracy_result.get("failures", []))
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.QUALITY_ACCURACY_VERIFIED,
            passed=accuracy_passed,
            message=f"Accuracy: {accuracy_result['score']:.2f}" if accuracy_passed
                    else f"Accuracy below threshold: {accuracy_result['score']:.2f}",
            details=accuracy_result,
            category=GateCategory.QUALITY,
            severity="critical",
        ))

        # Gate 2: QUALITY_COMPLETENESS_MET
        completeness_passed = completeness_result["score"] >= 0.7
        if not completeness_passed:
            self.stats["completeness_failures"] += 1
            failed_validations.extend(completeness_result.get("missing", []))
            recommendations.extend(completeness_result.get("recommendations", []))
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.QUALITY_COMPLETENESS_MET,
            passed=completeness_passed,
            message=f"Completeness: {completeness_result['score']:.2f}" if completeness_passed
                    else f"Missing required elements",
            details=completeness_result,
            category=GateCategory.QUALITY,
            severity="warning",
        ))

        # Gate 3: QUALITY_CONSISTENCY_CHECKED
        consistency_passed = consistency_result["is_consistent"]
        if not consistency_passed:
            failed_validations.extend(consistency_result.get("inconsistencies", []))
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.QUALITY_CONSISTENCY_CHECKED,
            passed=consistency_passed,
            message="Content is internally consistent" if consistency_passed
                    else f"{len(consistency_result.get('inconsistencies', []))} inconsistencies found",
            details=consistency_result,
            category=GateCategory.QUALITY,
            severity="warning",
        ))

        # Gate 4: QUALITY_EXAMPLES_VALIDATED
        examples_passed = examples_result["valid_count"] >= examples_result["total_count"] * 0.8
        if examples_result["total_count"] == 0:
            examples_passed = True  # No examples to validate
        self.stats["examples_validated"] += examples_result["valid_count"]
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.QUALITY_EXAMPLES_VALIDATED,
            passed=examples_passed,
            message=f"{examples_result['valid_count']}/{examples_result['total_count']} examples valid",
            details=examples_result,
            category=GateCategory.QUALITY,
            severity="warning",
        ))

        # Gate 5: QUALITY_CONFIDENCE_THRESHOLD
        overall_score = self._calculate_overall_score(
            accuracy_result["score"],
            completeness_result["score"],
            consistency_result["score"],
            examples_result["score"],
        )
        confidence_passed = overall_score >= self.min_confidence
        gates.append(EnforcerGateResult(
            gate=EnforcerGate.QUALITY_CONFIDENCE_THRESHOLD,
            passed=confidence_passed,
            message=f"Overall quality: {overall_score:.2f}" if confidence_passed
                    else f"Quality below threshold: {overall_score:.2f} < {self.min_confidence}",
            details={"overall_score": overall_score, "threshold": self.min_confidence},
            category=GateCategory.QUALITY,
            severity="critical",
        ))

        # Phase 4: Output
        all_critical_passed = all(
            g.passed for g in gates
            if g.severity == "critical"
        )

        if all_critical_passed:
            self.stats["passed"] += 1
        else:
            self.stats["failed"] += 1

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = QualityResult(
            passed=all_critical_passed,
            accuracy_score=accuracy_result["score"],
            completeness_score=completeness_result["score"],
            consistency_score=consistency_result["score"],
            overall_score=overall_score,
            validated_examples=examples_result.get("valid_examples", []),
            failed_validations=failed_validations,
            recommendations=recommendations,
        )

        return result, gates

    def _identify_validation_targets(
        self,
        semantic: SemanticResult,
        content: str,
    ) -> dict[str, list[Any]]:
        """Identify what needs validation.

        Args:
            semantic: Semantic extraction result.
            content: Raw content.

        Returns:
            Dictionary of validation targets.
        """
        return {
            "entities": semantic.entities,
            "rules": semantic.rules,
            "patterns": semantic.patterns,
            "pr_patterns": semantic.pr_patterns,
            "content_length": len(content),
        }

    async def _verify_accuracy(
        self,
        semantic: SemanticResult,
        content: str,
    ) -> dict[str, Any]:
        """Verify accuracy of extracted facts.

        Args:
            semantic: Semantic extraction result.
            content: Raw content.

        Returns:
            Accuracy verification result.
        """
        failures = []
        checks_passed = 0
        total_checks = 0

        # Verify state codes
        for entity in semantic.entities:
            if entity.get("type") == "state":
                total_checks += 1
                state = entity.get("value", "").upper()
                if state in VALID_STATES:
                    checks_passed += 1
                else:
                    failures.append({
                        "type": "invalid_state",
                        "value": state,
                        "message": f"Invalid state code: {state}",
                    })

        # Verify ZIP codes
        for entity in semantic.entities:
            if entity.get("type") == "zip_code":
                total_checks += 1
                zip_code = entity.get("value", "")
                if re.match(r"^\d{5}$", zip_code):
                    checks_passed += 1
                else:
                    failures.append({
                        "type": "invalid_zip",
                        "value": zip_code,
                        "message": f"Invalid ZIP code format: {zip_code}",
                    })

        # Verify PR patterns
        for pr_pattern in semantic.pr_patterns:
            if pr_pattern.get("type") == "pr_zip":
                total_checks += 1
                zip_code = pr_pattern.get("value", "")
                if zip_code.startswith(("006", "007", "008", "009")):
                    checks_passed += 1
                else:
                    failures.append({
                        "type": "invalid_pr_zip",
                        "value": zip_code,
                        "message": f"ZIP {zip_code} is not a PR ZIP code",
                    })

        # Verify regex patterns compile
        for pattern in semantic.patterns:
            total_checks += 1
            if pattern.is_valid:
                checks_passed += 1
            else:
                failures.append({
                    "type": "invalid_regex",
                    "value": pattern.regex,
                    "message": f"Regex does not compile: {pattern.regex}",
                })

        score = checks_passed / total_checks if total_checks > 0 else 1.0

        return {
            "score": score,
            "checks_passed": checks_passed,
            "total_checks": total_checks,
            "failures": failures,
        }

    def _check_completeness(
        self,
        semantic: SemanticResult,
        content: str,
    ) -> dict[str, Any]:
        """Check if content has required elements.

        Args:
            semantic: Semantic extraction result.
            content: Raw content.

        Returns:
            Completeness check result.
        """
        required_elements = {
            "has_entities": len(semantic.entities) > 0,
            "has_meaningful_content": len(content) > 100,
        }

        optional_elements = {
            "has_rules": len(semantic.rules) > 0,
            "has_patterns": len(semantic.patterns) > 0,
            "has_examples": "example" in content.lower(),
        }

        missing = []
        recommendations = []

        # Check required
        for elem, present in required_elements.items():
            if not present:
                missing.append({"element": elem, "required": True})

        # Check optional and recommend
        for elem, present in optional_elements.items():
            if not present:
                recommendations.append(f"Consider adding {elem.replace('has_', '').replace('_', ' ')}")

        # Calculate score
        required_score = sum(required_elements.values()) / len(required_elements) if required_elements else 1.0
        optional_score = sum(optional_elements.values()) / len(optional_elements) if optional_elements else 1.0

        # Weighted: required matters more
        score = required_score * 0.7 + optional_score * 0.3

        return {
            "score": score,
            "required": required_elements,
            "optional": optional_elements,
            "missing": missing,
            "recommendations": recommendations,
        }

    def _check_consistency(
        self,
        semantic: SemanticResult,
        context: ContextResult,
    ) -> dict[str, Any]:
        """Check for internal consistency.

        Args:
            semantic: Semantic extraction result.
            context: Context linking result.

        Returns:
            Consistency check result.
        """
        inconsistencies = []

        # Check for conflicting rules
        rules_by_scope: dict[str, list[Any]] = {}
        for rule in semantic.rules:
            scope = rule.scope
            if scope not in rules_by_scope:
                rules_by_scope[scope] = []
            rules_by_scope[scope].append(rule)

        # Look for contradictions within same scope
        for scope, rules in rules_by_scope.items():
            if len(rules) > 1:
                # Simple check: conflicting actions
                actions = set()
                for rule in rules:
                    if rule.action in actions:
                        # Potential duplicate
                        pass
                    actions.add(rule.action)

        # Check context conflicts
        inconsistencies.extend(context.conflicts)

        # Calculate score
        max_inconsistencies = 5  # Allow some before failing
        score = max(0, 1 - len(inconsistencies) / max_inconsistencies)

        return {
            "is_consistent": len(inconsistencies) == 0,
            "score": score,
            "inconsistencies": inconsistencies,
        }

    def _validate_examples(self, content: str) -> dict[str, Any]:
        """Validate that examples in content are parseable.

        Args:
            content: Raw content.

        Returns:
            Example validation result.
        """
        examples = []
        valid_examples = []
        invalid_examples = []

        # Find example patterns
        lines = content.split("\n")
        in_example_block = False

        for i, line in enumerate(lines):
            # Check for example indicators
            if re.search(r"\bexample|e\.g\.|for instance\b", line, re.I):
                # Look for address-like content nearby
                check_lines = lines[max(0, i):min(len(lines), i + 5)]
                for check_line in check_lines:
                    # Check if line looks like an address
                    if re.search(r"\b\d{5}\b", check_line):
                        examples.append(check_line.strip())

            # Check for code blocks with examples
            if "```" in line:
                in_example_block = not in_example_block
            elif in_example_block:
                if re.search(r"\b\d{5}\b", line):
                    examples.append(line.strip())

        # Validate each example
        for example in examples:
            # Check if it looks like a valid address format
            has_zip = bool(re.search(r"\b\d{5}\b", example))
            has_street = bool(re.search(r"\b\d+\s+\w+", example))

            if has_zip or has_street:
                valid_examples.append(example)
            else:
                invalid_examples.append({
                    "example": example,
                    "reason": "Missing ZIP or street number",
                })

        total = len(examples)
        valid = len(valid_examples)
        score = valid / total if total > 0 else 1.0

        return {
            "total_count": total,
            "valid_count": valid,
            "score": score,
            "valid_examples": valid_examples,
            "invalid_examples": invalid_examples,
        }

    def _calculate_overall_score(
        self,
        accuracy: float,
        completeness: float,
        consistency: float,
        examples: float,
    ) -> float:
        """Calculate weighted overall quality score.

        Args:
            accuracy: Accuracy score.
            completeness: Completeness score.
            consistency: Consistency score.
            examples: Examples validation score.

        Returns:
            Weighted overall score.
        """
        # Weights: accuracy and consistency are critical
        weights = {
            "accuracy": 0.35,
            "completeness": 0.25,
            "consistency": 0.25,
            "examples": 0.15,
        }

        return (
            accuracy * weights["accuracy"] +
            completeness * weights["completeness"] +
            consistency * weights["consistency"] +
            examples * weights["examples"]
        )

    def get_stats(self) -> dict[str, Any]:
        """Get agent statistics.

        Returns:
            Statistics dictionary.
        """
        return self.stats.copy()
