"""
Specialized RAG Agents for Comprehensive Indexing

Multiple specialized agents that work together to ensure comprehensive,
high-quality RAG indexing of the codebase.

Agents:
- ContentAnalyzerAgent: Analyzes content types and structures
- ChunkQualityAgent: Validates chunk quality and coherence
- IndexValidatorAgent: Validates index completeness and accuracy
- CoverageAgent: Ensures comprehensive coverage of all content
- RelationshipAgent: Detects relationships between chunks

Author: Universal Context Template
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import re


class AgentRole(Enum):
    """Roles for specialized agents."""
    CONTENT_ANALYZER = "content_analyzer"
    CHUNK_QUALITY = "chunk_quality"
    INDEX_VALIDATOR = "index_validator"
    COVERAGE = "coverage"
    RELATIONSHIP = "relationship"


@dataclass
class AgentFinding:
    """A finding or observation from an agent."""
    agent: AgentRole
    severity: str  # info, warning, error, critical
    category: str
    message: str
    affected_items: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class AgentReport:
    """Report from a single agent's analysis."""
    agent: AgentRole
    status: str  # passed, warnings, failed
    score: float  # 0.0 to 1.0
    findings: List[AgentFinding] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


class BaseRAGAgent(ABC):
    """Base class for all RAG agents."""

    def __init__(self, role: AgentRole):
        self.role = role
        self.findings: List[AgentFinding] = []

    def add_finding(
        self,
        severity: str,
        category: str,
        message: str,
        affected_items: List[str] = None,
        suggestions: List[str] = None
    ):
        """Add a finding."""
        self.findings.append(AgentFinding(
            agent=self.role,
            severity=severity,
            category=category,
            message=message,
            affected_items=affected_items or [],
            suggestions=suggestions or []
        ))

    @abstractmethod
    def analyze(self, manifest: Dict[str, Any], chunks_content: Dict[str, str]) -> AgentReport:
        """Perform analysis and return report."""
        pass

    def _calculate_status(self, score: float) -> str:
        """Calculate status from score."""
        if score >= 0.8:
            return "passed"
        elif score >= 0.5:
            return "warnings"
        return "failed"


class ContentAnalyzerAgent(BaseRAGAgent):
    """
    Analyzes content types and structures in the codebase.

    Responsibilities:
    - Identify content types (code, docs, config, etc.)
    - Analyze language distribution
    - Detect patterns and frameworks
    - Identify special content (PRPs, agents, templates)
    """

    def __init__(self):
        super().__init__(AgentRole.CONTENT_ANALYZER)

    def analyze(self, manifest: Dict[str, Any], chunks_content: Dict[str, str]) -> AgentReport:
        """Analyze content distribution and types."""
        self.findings = []
        metrics = {}

        chunks = manifest.get('chunks', [])
        categories = manifest.get('categories', {})

        # Analyze category distribution
        total_chunks = len(chunks)
        category_counts = {cat: len(ids) for cat, ids in categories.items()}
        metrics['category_distribution'] = category_counts

        # Check for balanced distribution
        if total_chunks > 0:
            source_ratio = category_counts.get('source_code', 0) / total_chunks
            doc_ratio = category_counts.get('documentation', 0) / total_chunks

            if source_ratio < 0.3:
                self.add_finding(
                    "warning", "distribution",
                    f"Source code underrepresented ({source_ratio:.1%})",
                    suggestions=["Consider more granular code chunking"]
                )

            if doc_ratio > 0.5:
                self.add_finding(
                    "info", "distribution",
                    f"High documentation ratio ({doc_ratio:.1%})",
                    suggestions=["Verify docs are properly chunked"]
                )

        # Analyze chunk types
        chunk_types = {}
        for chunk in chunks:
            ctype = chunk.get('chunk_type', 'unknown')
            chunk_types[ctype] = chunk_types.get(ctype, 0) + 1
        metrics['chunk_types'] = chunk_types

        # Analyze languages (from file extensions)
        languages = {}
        for chunk in chunks:
            file_path = chunk.get('file_path', '')
            ext = Path(file_path).suffix.lower()
            lang = self._ext_to_language(ext)
            languages[lang] = languages.get(lang, 0) + 1
        metrics['languages'] = languages

        # Detect frameworks/patterns
        frameworks = self._detect_frameworks(chunks, chunks_content)
        metrics['frameworks'] = frameworks

        if frameworks:
            self.add_finding(
                "info", "frameworks",
                f"Detected frameworks: {', '.join(frameworks)}",
                suggestions=["Ensure framework-specific patterns are captured"]
            )

        # Calculate score
        score = 1.0
        warnings = len([f for f in self.findings if f.severity == 'warning'])
        errors = len([f for f in self.findings if f.severity in ['error', 'critical']])
        score -= warnings * 0.1
        score -= errors * 0.2
        score = max(0.0, min(1.0, score))

        return AgentReport(
            agent=self.role,
            status=self._calculate_status(score),
            score=score,
            findings=self.findings,
            metrics=metrics,
            recommendations=self._generate_recommendations()
        )

    def _ext_to_language(self, ext: str) -> str:
        """Map file extension to language."""
        mapping = {
            '.py': 'Python', '.java': 'Java', '.ts': 'TypeScript',
            '.tsx': 'TypeScript', '.js': 'JavaScript', '.jsx': 'JavaScript',
            '.go': 'Go', '.rs': 'Rust', '.cpp': 'C++', '.c': 'C',
            '.cs': 'C#', '.rb': 'Ruby', '.php': 'PHP', '.swift': 'Swift',
            '.kt': 'Kotlin', '.scala': 'Scala', '.md': 'Markdown',
            '.json': 'JSON', '.yaml': 'YAML', '.yml': 'YAML',
            '.xml': 'XML', '.html': 'HTML', '.css': 'CSS'
        }
        return mapping.get(ext, 'Other')

    def _detect_frameworks(self, chunks: List[Dict], chunks_content: Dict[str, str]) -> List[str]:
        """Detect frameworks from content patterns."""
        frameworks = set()

        # Check chunk content for framework indicators
        for chunk in chunks[:100]:  # Sample first 100
            chunk_id = chunk.get('chunk_id', '')
            content = chunks_content.get(chunk_id, '')

            # Spring Boot
            if '@SpringBoot' in content or '@RestController' in content:
                frameworks.add('Spring Boot')
            # FastAPI
            if 'from fastapi' in content or '@app.get' in content:
                frameworks.add('FastAPI')
            # Django
            if 'from django' in content or 'models.Model' in content:
                frameworks.add('Django')
            # React
            if 'from react' in content.lower() or 'usestate' in content.lower():
                frameworks.add('React')
            # Express
            if 'express()' in content or 'app.listen' in content:
                frameworks.add('Express')

        return list(frameworks)

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on findings."""
        recs = []
        for finding in self.findings:
            if finding.suggestions:
                recs.extend(finding.suggestions)
        return list(set(recs))[:5]


class ChunkQualityAgent(BaseRAGAgent):
    """
    Validates chunk quality and coherence.

    Responsibilities:
    - Check chunk sizes (not too big, not too small)
    - Validate chunk completeness
    - Check for code smell indicators
    - Ensure chunks are self-contained
    """

    # Quality thresholds
    MIN_CHUNK_SIZE = 50  # chars
    MAX_CHUNK_SIZE = 5000  # chars
    IDEAL_MIN_SIZE = 200
    IDEAL_MAX_SIZE = 2000

    def __init__(self):
        super().__init__(AgentRole.CHUNK_QUALITY)

    def analyze(self, manifest: Dict[str, Any], chunks_content: Dict[str, str]) -> AgentReport:
        """Analyze chunk quality."""
        self.findings = []
        metrics = {}

        chunks = manifest.get('chunks', [])

        # Analyze size distribution
        sizes = []
        too_small = []
        too_large = []
        optimal = []

        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', '')
            content = chunks_content.get(chunk_id, '')
            size = len(content)
            sizes.append(size)

            if size < self.MIN_CHUNK_SIZE:
                too_small.append(chunk_id)
            elif size > self.MAX_CHUNK_SIZE:
                too_large.append(chunk_id)
            elif self.IDEAL_MIN_SIZE <= size <= self.IDEAL_MAX_SIZE:
                optimal.append(chunk_id)

        if sizes:
            metrics['size_stats'] = {
                'min': min(sizes),
                'max': max(sizes),
                'avg': sum(sizes) / len(sizes),
                'total_chars': sum(sizes)
            }
            metrics['size_distribution'] = {
                'too_small': len(too_small),
                'too_large': len(too_large),
                'optimal': len(optimal),
                'other': len(chunks) - len(too_small) - len(too_large) - len(optimal)
            }

        # Report size issues
        if too_small:
            self.add_finding(
                "warning", "size",
                f"{len(too_small)} chunks are too small (<{self.MIN_CHUNK_SIZE} chars)",
                affected_items=too_small[:10],
                suggestions=["Consider merging with adjacent chunks"]
            )

        if too_large:
            self.add_finding(
                "warning", "size",
                f"{len(too_large)} chunks are too large (>{self.MAX_CHUNK_SIZE} chars)",
                affected_items=too_large[:10],
                suggestions=["Consider splitting into smaller chunks"]
            )

        # Check for incomplete chunks
        incomplete = self._find_incomplete_chunks(chunks, chunks_content)
        if incomplete:
            self.add_finding(
                "warning", "completeness",
                f"{len(incomplete)} chunks may be incomplete",
                affected_items=incomplete[:10],
                suggestions=["Review chunk boundaries"]
            )

        # Check for duplicates
        duplicates = self._find_duplicates(chunks_content)
        if duplicates:
            self.add_finding(
                "error", "duplicates",
                f"Found {len(duplicates)} duplicate or near-duplicate chunks",
                affected_items=list(duplicates)[:10],
                suggestions=["Remove duplicate chunks"]
            )

        # Calculate quality score
        total = len(chunks)
        if total > 0:
            quality_ratio = len(optimal) / total
            issue_ratio = (len(too_small) + len(too_large) + len(incomplete)) / total
            score = max(0.0, min(1.0, quality_ratio - issue_ratio * 0.5))
        else:
            score = 0.0

        metrics['quality_score'] = score

        return AgentReport(
            agent=self.role,
            status=self._calculate_status(score),
            score=score,
            findings=self.findings,
            metrics=metrics,
            recommendations=self._generate_recommendations()
        )

    def _find_incomplete_chunks(
        self,
        chunks: List[Dict],
        chunks_content: Dict[str, str]
    ) -> List[str]:
        """Find chunks that appear incomplete."""
        incomplete = []

        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', '')
            content = chunks_content.get(chunk_id, '')

            # Check for unclosed brackets/braces
            if content.count('{') != content.count('}'):
                incomplete.append(chunk_id)
            elif content.count('(') != content.count(')'):
                incomplete.append(chunk_id)
            elif content.count('[') != content.count(']'):
                incomplete.append(chunk_id)

        return incomplete

    def _find_duplicates(self, chunks_content: Dict[str, str]) -> Set[str]:
        """Find duplicate chunks."""
        duplicates = set()
        content_hashes = {}

        for chunk_id, content in chunks_content.items():
            # Normalize content for comparison
            normalized = ' '.join(content.split()).lower()
            content_hash = hash(normalized)

            if content_hash in content_hashes:
                duplicates.add(chunk_id)
                duplicates.add(content_hashes[content_hash])
            else:
                content_hashes[content_hash] = chunk_id

        return duplicates

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations."""
        recs = []
        for finding in self.findings:
            if finding.suggestions:
                recs.extend(finding.suggestions)
        return list(set(recs))[:5]


class IndexValidatorAgent(BaseRAGAgent):
    """
    Validates index completeness and accuracy.

    Responsibilities:
    - Verify all files are indexed
    - Check for missing important content
    - Validate metadata completeness
    - Ensure searchability
    """

    def __init__(self):
        super().__init__(AgentRole.INDEX_VALIDATOR)

    def analyze(self, manifest: Dict[str, Any], chunks_content: Dict[str, str]) -> AgentReport:
        """Validate index completeness."""
        self.findings = []
        metrics = {}

        chunks = manifest.get('chunks', [])
        stats = manifest.get('stats', {})

        # Check target vs actual
        target = manifest.get('target_chunks', 333)
        actual = manifest.get('actual_chunks', len(chunks))
        metrics['target_chunks'] = target
        metrics['actual_chunks'] = actual
        metrics['target_ratio'] = actual / target if target > 0 else 0

        if actual < target * 0.8:
            self.add_finding(
                "warning", "count",
                f"Chunk count ({actual}) below target ({target})",
                suggestions=["Consider finer chunking or including more files"]
            )
        elif actual > target * 1.2:
            self.add_finding(
                "info", "count",
                f"Chunk count ({actual}) exceeds target ({target})",
                suggestions=["Consider merging similar chunks"]
            )

        # Check metadata completeness
        missing_keywords = []
        missing_summary = []

        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', '')
            if not chunk.get('keywords'):
                missing_keywords.append(chunk_id)
            if not chunk.get('summary'):
                missing_summary.append(chunk_id)

        if missing_keywords:
            metrics['missing_keywords'] = len(missing_keywords)
            self.add_finding(
                "warning", "metadata",
                f"{len(missing_keywords)} chunks missing keywords",
                affected_items=missing_keywords[:10],
                suggestions=["Run AI enforcer to generate keywords"]
            )

        if missing_summary:
            metrics['missing_summary'] = len(missing_summary)
            self.add_finding(
                "warning", "metadata",
                f"{len(missing_summary)} chunks missing summary",
                affected_items=missing_summary[:10],
                suggestions=["Run AI enforcer to generate summaries"]
            )

        # Check file coverage
        files_indexed = set()
        for chunk in chunks:
            files_indexed.add(chunk.get('file_path', ''))

        metrics['files_indexed'] = len(files_indexed)
        metrics['total_files'] = stats.get('total_files', len(files_indexed))

        # Calculate score
        score = 1.0
        warnings = len([f for f in self.findings if f.severity == 'warning'])
        errors = len([f for f in self.findings if f.severity in ['error', 'critical']])
        score -= warnings * 0.1
        score -= errors * 0.2

        # Bonus for hitting target
        if 0.9 <= metrics['target_ratio'] <= 1.1:
            score = min(1.0, score + 0.1)

        score = max(0.0, min(1.0, score))

        return AgentReport(
            agent=self.role,
            status=self._calculate_status(score),
            score=score,
            findings=self.findings,
            metrics=metrics,
            recommendations=self._generate_recommendations()
        )

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations."""
        recs = []
        for finding in self.findings:
            if finding.suggestions:
                recs.extend(finding.suggestions)
        return list(set(recs))[:5]


class CoverageAgent(BaseRAGAgent):
    """
    Ensures comprehensive coverage of all content types.

    Responsibilities:
    - Check all categories are covered
    - Verify important files are indexed
    - Ensure no blind spots in coverage
    """

    # Important file patterns that should be indexed
    IMPORTANT_PATTERNS = [
        r'README\.md$',
        r'PLANNING\.md$',
        r'CLAUDE\.md$',
        r'.*AGENT.*\.md$',
        r'requirements.*\.txt$',
        r'package\.json$',
        r'pom\.xml$',
        r'Dockerfile$'
    ]

    def __init__(self):
        super().__init__(AgentRole.COVERAGE)

    def analyze(self, manifest: Dict[str, Any], chunks_content: Dict[str, str]) -> AgentReport:
        """Analyze coverage completeness."""
        self.findings = []
        metrics = {}

        chunks = manifest.get('chunks', [])
        categories = manifest.get('categories', {})

        # Check category coverage
        expected_categories = [
            'source_code', 'documentation', 'configuration',
            'agents', 'commands'
        ]

        covered = []
        missing = []
        for cat in expected_categories:
            if cat in categories and categories[cat]:
                covered.append(cat)
            else:
                missing.append(cat)

        metrics['covered_categories'] = covered
        metrics['missing_categories'] = missing
        metrics['coverage_ratio'] = len(covered) / len(expected_categories)

        if missing:
            self.add_finding(
                "warning", "categories",
                f"Missing category coverage: {', '.join(missing)}",
                suggestions=["Check if these content types exist in project"]
            )

        # Check important files
        indexed_files = set(chunk.get('file_path', '') for chunk in chunks)
        important_missing = []

        for pattern in self.IMPORTANT_PATTERNS:
            found = any(re.search(pattern, f, re.IGNORECASE) for f in indexed_files)
            if not found:
                important_missing.append(pattern)

        if important_missing:
            metrics['missing_important_files'] = len(important_missing)
            self.add_finding(
                "info", "important_files",
                f"{len(important_missing)} important file patterns not found",
                affected_items=important_missing[:5],
                suggestions=["Verify if these files exist in project"]
            )

        # Calculate score
        score = metrics['coverage_ratio']
        if important_missing:
            score -= len(important_missing) * 0.05
        score = max(0.0, min(1.0, score))

        return AgentReport(
            agent=self.role,
            status=self._calculate_status(score),
            score=score,
            findings=self.findings,
            metrics=metrics,
            recommendations=self._generate_recommendations()
        )

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations."""
        recs = []
        for finding in self.findings:
            if finding.suggestions:
                recs.extend(finding.suggestions)
        return list(set(recs))[:5]


class RelationshipAgent(BaseRAGAgent):
    """
    Detects and validates relationships between chunks.

    Responsibilities:
    - Identify import/dependency relationships
    - Detect test-code relationships
    - Find documentation-code links
    """

    def __init__(self):
        super().__init__(AgentRole.RELATIONSHIP)

    def analyze(self, manifest: Dict[str, Any], chunks_content: Dict[str, str]) -> AgentReport:
        """Analyze chunk relationships."""
        self.findings = []
        metrics = {}

        chunks = manifest.get('chunks', [])

        # Build file index
        file_chunks: Dict[str, List[Dict]] = {}
        for chunk in chunks:
            file_path = chunk.get('file_path', '')
            if file_path not in file_chunks:
                file_chunks[file_path] = []
            file_chunks[file_path].append(chunk)

        # Detect import relationships
        import_relationships = self._find_import_relationships(chunks, chunks_content)
        metrics['import_relationships'] = len(import_relationships)

        # Detect test relationships
        test_relationships = self._find_test_relationships(file_chunks)
        metrics['test_relationships'] = len(test_relationships)

        # Check for orphan chunks (no relationships)
        chunks_with_relationships = set()
        for rel in import_relationships + test_relationships:
            chunks_with_relationships.add(rel[0])
            chunks_with_relationships.add(rel[1])

        orphans = [c['chunk_id'] for c in chunks if c['chunk_id'] not in chunks_with_relationships]
        metrics['orphan_chunks'] = len(orphans)

        if len(orphans) > len(chunks) * 0.5:
            self.add_finding(
                "info", "relationships",
                f"Many chunks ({len(orphans)}) have no detected relationships",
                suggestions=["Run AI enforcer to detect semantic relationships"]
            )

        # Calculate score based on relationship richness
        if len(chunks) > 0:
            relationship_ratio = len(chunks_with_relationships) / len(chunks)
        else:
            relationship_ratio = 0

        score = min(1.0, 0.5 + relationship_ratio * 0.5)

        return AgentReport(
            agent=self.role,
            status=self._calculate_status(score),
            score=score,
            findings=self.findings,
            metrics=metrics,
            recommendations=self._generate_recommendations()
        )

    def _find_import_relationships(
        self,
        chunks: List[Dict],
        chunks_content: Dict[str, str]
    ) -> List[Tuple[str, str]]:
        """Find import/dependency relationships."""
        relationships = []

        # Build name-to-chunk mapping
        name_to_chunk: Dict[str, str] = {}
        for chunk in chunks:
            metadata = chunk.get('metadata', {})
            for key in ['class_name', 'name', 'method_name']:
                if key in metadata and metadata[key]:
                    name_to_chunk[metadata[key]] = chunk['chunk_id']

        # Find imports in each chunk
        for chunk in chunks:
            chunk_id = chunk.get('chunk_id', '')
            content = chunks_content.get(chunk_id, '')

            # Python imports
            imports = re.findall(r'from\s+(\w+)\s+import|import\s+(\w+)', content)
            for imp in imports:
                name = imp[0] or imp[1]
                if name in name_to_chunk and name_to_chunk[name] != chunk_id:
                    relationships.append((chunk_id, name_to_chunk[name]))

            # Java imports
            java_imports = re.findall(r'import\s+[\w.]+\.(\w+);', content)
            for name in java_imports:
                if name in name_to_chunk and name_to_chunk[name] != chunk_id:
                    relationships.append((chunk_id, name_to_chunk[name]))

        return relationships

    def _find_test_relationships(self, file_chunks: Dict[str, List[Dict]]) -> List[Tuple[str, str]]:
        """Find test-to-implementation relationships."""
        relationships = []

        test_files = [f for f in file_chunks.keys()
                      if 'test' in f.lower() or 'spec' in f.lower()]
        impl_files = [f for f in file_chunks.keys()
                      if f not in test_files]

        for test_file in test_files:
            # Try to find corresponding implementation
            test_name = Path(test_file).stem.lower()
            test_name = test_name.replace('test_', '').replace('_test', '')
            test_name = test_name.replace('.test', '').replace('.spec', '')

            for impl_file in impl_files:
                impl_name = Path(impl_file).stem.lower()
                if test_name == impl_name or impl_name in test_name:
                    # Link test chunks to impl chunks
                    for test_chunk in file_chunks[test_file]:
                        for impl_chunk in file_chunks[impl_file]:
                            relationships.append(
                                (test_chunk['chunk_id'], impl_chunk['chunk_id'])
                            )

        return relationships

    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations."""
        recs = []
        for finding in self.findings:
            if finding.suggestions:
                recs.extend(finding.suggestions)
        return list(set(recs))[:5]


class RAGAgentSwarm:
    """
    Coordinates multiple specialized RAG agents for comprehensive analysis.
    """

    def __init__(self):
        self.agents = [
            ContentAnalyzerAgent(),
            ChunkQualityAgent(),
            IndexValidatorAgent(),
            CoverageAgent(),
            RelationshipAgent()
        ]

    def analyze_all(
        self,
        manifest: Dict[str, Any],
        chunks_content: Dict[str, str],
        progress_callback=None
    ) -> Dict[str, AgentReport]:
        """Run all agents and collect reports."""
        reports = {}

        for i, agent in enumerate(self.agents):
            if progress_callback:
                progress_callback(i + 1, len(self.agents), f"Running {agent.role.value}")

            try:
                report = agent.analyze(manifest, chunks_content)
                reports[agent.role.value] = report
            except Exception as e:
                # Create error report
                reports[agent.role.value] = AgentReport(
                    agent=agent.role,
                    status="failed",
                    score=0.0,
                    findings=[AgentFinding(
                        agent=agent.role,
                        severity="error",
                        category="execution",
                        message=f"Agent failed: {str(e)}"
                    )]
                )

        return reports

    def get_combined_score(self, reports: Dict[str, AgentReport]) -> float:
        """Calculate combined score from all agents."""
        if not reports:
            return 0.0

        scores = [r.score for r in reports.values() if r.score is not None]
        return sum(scores) / len(scores) if scores else 0.0

    def get_all_findings(self, reports: Dict[str, AgentReport]) -> List[AgentFinding]:
        """Get all findings from all agents."""
        findings = []
        for report in reports.values():
            findings.extend(report.findings)
        return findings

    def get_all_recommendations(self, reports: Dict[str, AgentReport]) -> List[str]:
        """Get all unique recommendations."""
        recs = set()
        for report in reports.values():
            recs.update(report.recommendations)
        return list(recs)


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RAG Agents")
    parser.add_argument("--manifest", "-m", required=True, help="Path to index_manifest.json")
    parser.add_argument("--agent", "-a", choices=['all', 'content', 'quality', 'validator', 'coverage', 'relationship'],
                        default='all', help="Which agent to run")

    args = parser.parse_args()

    # Load manifest
    with open(args.manifest, 'r') as f:
        manifest = json.load(f)

    # Create empty content dict for testing
    chunks_content = {c['chunk_id']: "" for c in manifest.get('chunks', [])}

    if args.agent == 'all':
        swarm = RAGAgentSwarm()
        reports = swarm.analyze_all(manifest, chunks_content)

        print("\n=== RAG Agent Swarm Report ===\n")
        for name, report in reports.items():
            print(f"{name}: {report.status} (score: {report.score:.2f})")
            for finding in report.findings:
                print(f"  [{finding.severity}] {finding.message}")

        print(f"\nCombined Score: {swarm.get_combined_score(reports):.2f}")
    else:
        # Run specific agent
        agent_map = {
            'content': ContentAnalyzerAgent,
            'quality': ChunkQualityAgent,
            'validator': IndexValidatorAgent,
            'coverage': CoverageAgent,
            'relationship': RelationshipAgent
        }
        agent = agent_map[args.agent]()
        report = agent.analyze(manifest, chunks_content)

        print(f"\n=== {agent.role.value} Report ===")
        print(f"Status: {report.status}")
        print(f"Score: {report.score:.2f}")
        print(f"\nFindings:")
        for finding in report.findings:
            print(f"  [{finding.severity}] {finding.message}")
