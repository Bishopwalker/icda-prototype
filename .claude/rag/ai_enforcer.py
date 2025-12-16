"""
AI Enforcer Agent for RAG Quality Control

Uses any available AI provider (Gemini, OpenAI, Anthropic, OpenRouter) to enforce
quality standards on the RAG indexing process. Acts as an AI supervisor that
validates chunks, suggests improvements, and ensures comprehensive coverage.

Provider-agnostic: Works with whatever AI is configured.

Features:
- Chunk quality validation
- Coverage analysis
- Keyword extraction enhancement
- Summary generation
- Relationship detection between chunks

Author: Universal Context Template
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import re

# Try to import requests for API calls
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class EnforcerAction(Enum):
    """Actions the enforcer can take."""
    APPROVE = "approve"
    IMPROVE = "improve"
    SPLIT = "split"
    MERGE = "merge"
    REJECT = "reject"
    FLAG = "flag"


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    score: float  # 0.0 to 1.0
    action: EnforcerAction
    message: str
    suggestions: List[str]
    improved_content: Optional[Dict[str, Any]] = None


@dataclass
class ChunkAnalysis:
    """Analysis of a single chunk."""
    chunk_id: str
    quality_score: float
    completeness_score: float
    relevance_score: float
    keywords: List[str]
    summary: str
    relationships: List[str]  # Related chunk IDs
    action: EnforcerAction
    suggestions: List[str]


@dataclass
class EnforcerReport:
    """Complete enforcer validation report."""
    timestamp: str
    total_chunks: int
    approved_chunks: int
    improved_chunks: int
    flagged_chunks: int
    overall_quality: float
    coverage_score: float
    analyses: List[ChunkAnalysis]
    recommendations: List[str]
    ai_provider: str


class AIProvider(Enum):
    """Supported AI providers."""
    GEMINI = "gemini"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


class UniversalAIClient:
    """
    Universal AI client that works with multiple providers.
    Auto-detects available providers based on configured API keys.
    """

    # Provider configurations
    PROVIDERS = {
        AIProvider.GEMINI: {
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
            "env_key": "GEMINI_API_KEY",
            "default_model": "gemini-2.5-flash"
        },
        AIProvider.OPENAI: {
            "base_url": "https://api.openai.com/v1",
            "env_key": "OPENAI_API_KEY",
            "default_model": "gpt-4o"
        },
        AIProvider.ANTHROPIC: {
            "base_url": "https://api.anthropic.com/v1",
            "env_key": "ANTHROPIC_API_KEY",
            "default_model": "claude-sonnet-4-20250514"
        },
        AIProvider.OPENROUTER: {
            "base_url": "https://openrouter.ai/api/v1",
            "env_key": "OPENROUTER_API_KEY",
            "default_model": "anthropic/claude-sonnet-4"
        }
    }

    def __init__(self, preferred_provider: Optional[AIProvider] = None):
        self.provider: Optional[AIProvider] = None
        self.api_key: Optional[str] = None
        self.model: Optional[str] = None

        # Auto-detect or use preferred
        if preferred_provider:
            self._try_provider(preferred_provider)

        if not self.provider:
            # Try each provider in order of preference
            for provider in [AIProvider.GEMINI, AIProvider.OPENAI, AIProvider.ANTHROPIC, AIProvider.OPENROUTER]:
                if self._try_provider(provider):
                    break

        if not self.provider:
            raise ValueError(
                "No AI provider configured. Set one of: "
                "GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, OPENROUTER_API_KEY"
            )

    def _try_provider(self, provider: AIProvider) -> bool:
        """Try to configure a specific provider."""
        config = self.PROVIDERS[provider]
        api_key = self._get_api_key(config["env_key"])

        if api_key:
            self.provider = provider
            self.api_key = api_key
            self.model = config["default_model"]
            return True
        return False

    def _get_api_key(self, env_key: str) -> Optional[str]:
        """Get API key from environment or .env file."""
        # Try environment variable
        key = os.environ.get(env_key)
        if key:
            return key

        # Try .env files
        env_paths = [
            Path(__file__).parent.parent.parent / '.env',
            Path(__file__).parent / '.env',
            Path.cwd() / '.env'
        ]

        for env_path in env_paths:
            if env_path.exists():
                with open(env_path, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith(f'{env_key}='):
                            return line.split('=', 1)[1].strip('"\'')

        return None

    @property
    def provider_name(self) -> str:
        """Get human-readable provider name."""
        return self.provider.value if self.provider else "unknown"

    def generate(self, prompt: str, max_tokens: int = 4096, temperature: float = 0.7) -> str:
        """Generate content using the configured AI provider."""
        if not REQUESTS_AVAILABLE:
            raise ImportError("requests library required. Install with: pip install requests")

        if self.provider == AIProvider.GEMINI:
            return self._generate_gemini(prompt, max_tokens, temperature)
        elif self.provider == AIProvider.OPENAI:
            return self._generate_openai(prompt, max_tokens, temperature)
        elif self.provider == AIProvider.ANTHROPIC:
            return self._generate_anthropic(prompt, max_tokens, temperature)
        elif self.provider == AIProvider.OPENROUTER:
            return self._generate_openrouter(prompt, max_tokens, temperature)
        else:
            raise ValueError(f"Unknown provider: {self.provider}")

    def _generate_gemini(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using Gemini API."""
        url = f"{self.PROVIDERS[AIProvider.GEMINI]['base_url']}/models/{self.model}:generateContent"

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature
            }
        }

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', response.text)
            raise Exception(f"Gemini API error: {error_msg}")

        result = response.json()
        return result['candidates'][0]['content']['parts'][0]['text']

    def _generate_openai(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using OpenAI API."""
        url = f"{self.PROVIDERS[AIProvider.OPENAI]['base_url']}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', response.text)
            raise Exception(f"OpenAI API error: {error_msg}")

        result = response.json()
        return result['choices'][0]['message']['content']

    def _generate_anthropic(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using Anthropic API."""
        url = f"{self.PROVIDERS[AIProvider.ANTHROPIC]['base_url']}/messages"

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}]
        }

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', response.text)
            raise Exception(f"Anthropic API error: {error_msg}")

        result = response.json()
        return result['content'][0]['text']

    def _generate_openrouter(self, prompt: str, max_tokens: int, temperature: float) -> str:
        """Generate using OpenRouter API."""
        url = f"{self.PROVIDERS[AIProvider.OPENROUTER]['base_url']}/chat/completions"

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        response = requests.post(url, json=payload, headers=headers, timeout=60)

        if response.status_code != 200:
            error_msg = response.json().get('error', {}).get('message', response.text)
            raise Exception(f"OpenRouter API error: {error_msg}")

        result = response.json()
        return result['choices'][0]['message']['content']

    def analyze_chunk(self, chunk_content: str, chunk_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single chunk for quality."""
        prompt = f"""Analyze this code/documentation chunk for RAG indexing quality.

CHUNK CONTENT:
```
{chunk_content[:2000]}
```

METADATA:
{json.dumps(chunk_metadata, indent=2)}

Respond with JSON only (no markdown):
{{
    "quality_score": <0.0-1.0>,
    "completeness_score": <0.0-1.0>,
    "relevance_score": <0.0-1.0>,
    "keywords": ["keyword1", "keyword2", ...],
    "summary": "<brief one-sentence summary>",
    "action": "<approve|improve|split|merge|flag>",
    "suggestions": ["suggestion1", "suggestion2", ...]
}}

Scoring guide:
- quality_score: Is the chunk well-formed and meaningful?
- completeness_score: Does it contain complete logical units?
- relevance_score: Is it useful for code understanding/search?
- action: approve (good), improve (needs minor fixes), split (too large), merge (too small), flag (problematic)
"""

        try:
            response = self.generate(prompt, max_tokens=1000, temperature=0.3)

            # Parse JSON from response
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                return json.loads(json_match.group())

            # Fallback
            return {
                "quality_score": 0.7,
                "completeness_score": 0.7,
                "relevance_score": 0.7,
                "keywords": [],
                "summary": "Analysis failed",
                "action": "approve",
                "suggestions": []
            }

        except Exception as e:
            return {
                "quality_score": 0.5,
                "completeness_score": 0.5,
                "relevance_score": 0.5,
                "keywords": [],
                "summary": f"Error: {str(e)}",
                "action": "flag",
                "suggestions": [f"Manual review needed: {str(e)}"]
            }

    def enhance_keywords(self, content: str, existing_keywords: List[str]) -> List[str]:
        """Enhance keyword extraction using AI."""
        prompt = f"""Extract the most important search keywords from this code/documentation.

CONTENT:
```
{content[:1500]}
```

EXISTING KEYWORDS: {existing_keywords}

Return a JSON array of 10-15 keywords that would help someone find this code.
Focus on: function names, class names, concepts, APIs, patterns.
Only respond with the JSON array, no explanation.

Example: ["UserAuthentication", "JWT", "login", "OAuth2", "bearer_token"]
"""

        try:
            response = self.generate(prompt, max_tokens=200, temperature=0.3)
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                keywords = json.loads(json_match.group())
                all_keywords = list(set(existing_keywords + keywords))
                return all_keywords[:15]
        except:
            pass

        return existing_keywords

    def generate_summary(self, content: str) -> str:
        """Generate a concise summary of chunk content."""
        prompt = f"""Write a one-sentence summary of what this code/documentation does.
Be specific and technical. Maximum 150 characters.

CONTENT:
```
{content[:1500]}
```

Only respond with the summary sentence, no quotes or explanation."""

        try:
            response = self.generate(prompt, max_tokens=100, temperature=0.3)
            return response.strip()[:150]
        except:
            return "Summary generation failed"

    def detect_relationships(
        self,
        chunk_content: str,
        chunk_id: str,
        other_chunks: List[Tuple[str, str]]
    ) -> List[str]:
        """Detect relationships between chunks."""
        if not other_chunks:
            return []

        sample_chunks = other_chunks[:20]
        chunks_text = "\n".join([f"- {cid}: {summary}" for cid, summary in sample_chunks])

        prompt = f"""Given this chunk, identify which other chunks it's likely related to.

THIS CHUNK ({chunk_id}):
```
{chunk_content[:1000]}
```

OTHER CHUNKS:
{chunks_text}

Return a JSON array of related chunk IDs (max 5).
Only include chunks that have clear relationships (imports, calls, extends, tests, documents).
Only respond with the JSON array.

Example: ["chunk_abc", "chunk_xyz"]
"""

        try:
            response = self.generate(prompt, max_tokens=100, temperature=0.3)
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                return json.loads(json_match.group())[:5]
        except:
            pass

        return []


class AIEnforcer:
    """
    Enforcer agent that uses any available AI to validate and improve RAG indexing.

    Implements the enforcer pattern where an AI agent reviews and validates
    the work of the chunking system. Provider-agnostic.
    """

    def __init__(
        self,
        preferred_provider: Optional[AIProvider] = None,
        batch_size: int = 10,
        validate_all: bool = False
    ):
        self.client = UniversalAIClient(preferred_provider)
        self.batch_size = batch_size
        self.validate_all = validate_all
        self.analyses: List[ChunkAnalysis] = []

        print(f"AI Enforcer initialized with provider: {self.client.provider_name}")

    @property
    def provider_name(self) -> str:
        """Get the active AI provider name."""
        return self.client.provider_name

    def _select_chunks_for_validation(
        self,
        chunks: List[Dict[str, Any]],
        sample_size: int = 50
    ) -> List[Dict[str, Any]]:
        """Select representative chunks for validation."""
        if self.validate_all or len(chunks) <= sample_size:
            return chunks

        # Stratified sampling by category and type
        categories: Dict[str, List[Dict[str, Any]]] = {}
        for chunk in chunks:
            cat = chunk.get('category', 'unknown')
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(chunk)

        selected = []
        for cat, cat_chunks in categories.items():
            proportion = len(cat_chunks) / len(chunks)
            n_samples = max(1, int(sample_size * proportion))
            if len(cat_chunks) <= n_samples:
                selected.extend(cat_chunks)
            else:
                step = len(cat_chunks) // n_samples
                selected.extend(cat_chunks[::step][:n_samples])

        return selected[:sample_size]

    def validate_chunk(
        self,
        chunk_id: str,
        content: str,
        metadata: Dict[str, Any],
        other_chunks: List[Tuple[str, str]] = None
    ) -> ChunkAnalysis:
        """Validate a single chunk using AI."""
        analysis = self.client.analyze_chunk(content, metadata)

        keywords = metadata.get('keywords', [])
        if analysis['quality_score'] >= 0.5:
            keywords = self.client.enhance_keywords(content, keywords)

        summary = analysis.get('summary', '')
        if not summary or summary == "Analysis failed":
            summary = self.client.generate_summary(content)

        relationships = []
        if other_chunks and analysis['quality_score'] >= 0.6:
            relationships = self.client.detect_relationships(content, chunk_id, other_chunks)

        return ChunkAnalysis(
            chunk_id=chunk_id,
            quality_score=analysis['quality_score'],
            completeness_score=analysis['completeness_score'],
            relevance_score=analysis['relevance_score'],
            keywords=keywords,
            summary=summary,
            relationships=relationships,
            action=EnforcerAction(analysis['action']),
            suggestions=analysis['suggestions']
        )

    def validate_manifest(
        self,
        manifest: Dict[str, Any],
        chunks_content: Dict[str, str],
        progress_callback=None
    ) -> EnforcerReport:
        """Validate an entire manifest."""
        from datetime import datetime

        chunks = manifest.get('chunks', [])
        total = len(chunks)

        selected = self._select_chunks_for_validation(chunks)
        chunk_summaries = [(c['chunk_id'], c.get('summary', '')) for c in chunks]

        analyses = []
        approved = 0
        improved = 0
        flagged = 0

        for i, chunk in enumerate(selected):
            chunk_id = chunk['chunk_id']
            content = chunks_content.get(chunk_id, '')

            if progress_callback:
                progress_callback(i + 1, len(selected), f"Validating: {chunk_id}")

            try:
                analysis = self.validate_chunk(
                    chunk_id=chunk_id,
                    content=content,
                    metadata=chunk.get('metadata', {}),
                    other_chunks=chunk_summaries
                )

                analyses.append(analysis)

                if analysis.action == EnforcerAction.APPROVE:
                    approved += 1
                elif analysis.action in [EnforcerAction.IMPROVE, EnforcerAction.SPLIT, EnforcerAction.MERGE]:
                    improved += 1
                else:
                    flagged += 1

            except Exception as e:
                analyses.append(ChunkAnalysis(
                    chunk_id=chunk_id,
                    quality_score=0.0,
                    completeness_score=0.0,
                    relevance_score=0.0,
                    keywords=[],
                    summary=f"Validation error: {e}",
                    relationships=[],
                    action=EnforcerAction.FLAG,
                    suggestions=[f"Manual review needed: {e}"]
                ))
                flagged += 1

        if analyses:
            overall_quality = sum(a.quality_score for a in analyses) / len(analyses)
        else:
            overall_quality = 0.0

        categories = manifest.get('categories', {})
        expected_categories = ['source_code', 'documentation', 'configuration']
        covered = sum(1 for c in expected_categories if c in categories and categories[c])
        coverage_score = covered / len(expected_categories)

        recommendations = self._generate_recommendations(analyses, manifest)

        return EnforcerReport(
            timestamp=datetime.now().isoformat(),
            total_chunks=total,
            approved_chunks=approved,
            improved_chunks=improved,
            flagged_chunks=flagged,
            overall_quality=overall_quality,
            coverage_score=coverage_score,
            analyses=analyses,
            recommendations=recommendations,
            ai_provider=self.provider_name
        )

    def _generate_recommendations(
        self,
        analyses: List[ChunkAnalysis],
        manifest: Dict[str, Any]
    ) -> List[str]:
        """Generate high-level recommendations based on validation."""
        recommendations = []

        low_quality = [a for a in analyses if a.quality_score < 0.5]
        if len(low_quality) > len(analyses) * 0.2:
            recommendations.append(
                f"High number of low-quality chunks ({len(low_quality)}). "
                "Consider adjusting chunk size or adding preprocessing."
            )

        splits = [a for a in analyses if a.action == EnforcerAction.SPLIT]
        if len(splits) > len(analyses) * 0.3:
            recommendations.append(
                f"Many chunks flagged for splitting ({len(splits)}). "
                "Consider reducing maximum chunk size."
            )

        merges = [a for a in analyses if a.action == EnforcerAction.MERGE]
        if len(merges) > len(analyses) * 0.3:
            recommendations.append(
                f"Many chunks flagged for merging ({len(merges)}). "
                "Consider increasing minimum chunk size."
            )

        stats = manifest.get('stats', {})
        chunks_by_cat = stats.get('chunks_by_category', {})
        if chunks_by_cat:
            source_code = chunks_by_cat.get('source_code', 0)
            total = sum(chunks_by_cat.values())
            if total > 0 and source_code / total < 0.4:
                recommendations.append(
                    "Source code chunks underrepresented. "
                    "Consider prioritizing code over documentation."
                )

        target = manifest.get('target_chunks', 333)
        actual = manifest.get('actual_chunks', 0)
        if actual < target * 0.8:
            recommendations.append(
                f"Chunk count ({actual}) significantly below target ({target}). "
                "Consider finer-grained chunking for better retrieval."
            )
        elif actual > target * 1.2:
            recommendations.append(
                f"Chunk count ({actual}) exceeds target ({target}). "
                "Consider merging similar chunks."
            )

        if not recommendations:
            recommendations.append("Indexing quality looks good! No major issues detected.")

        return recommendations

    def apply_improvements(
        self,
        manifest: Dict[str, Any],
        report: EnforcerReport
    ) -> Dict[str, Any]:
        """Apply enforcer improvements to manifest."""
        analysis_lookup = {a.chunk_id: a for a in report.analyses}

        for chunk in manifest.get('chunks', []):
            chunk_id = chunk['chunk_id']
            if chunk_id in analysis_lookup:
                analysis = analysis_lookup[chunk_id]

                chunk['quality_score'] = analysis.quality_score

                if analysis.keywords:
                    chunk['keywords'] = analysis.keywords

                if analysis.summary and analysis.summary != "Analysis failed":
                    chunk['summary'] = analysis.summary

                if analysis.relationships:
                    chunk['relationships'] = analysis.relationships

                if analysis.action in [EnforcerAction.FLAG, EnforcerAction.IMPROVE]:
                    chunk['enforcer_suggestions'] = analysis.suggestions

        manifest['quality_report'] = {
            'enforcer_timestamp': report.timestamp,
            'ai_provider': report.ai_provider,
            'overall_quality': report.overall_quality,
            'coverage_score': report.coverage_score,
            'approved_chunks': report.approved_chunks,
            'improved_chunks': report.improved_chunks,
            'flagged_chunks': report.flagged_chunks,
            'recommendations': report.recommendations
        }

        return manifest


# CLI entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="AI Enforcer Agent")
    parser.add_argument("--manifest", "-m", help="Path to index_manifest.json")
    parser.add_argument("--provider", "-p", choices=['gemini', 'openai', 'anthropic', 'openrouter'],
                        help="Preferred AI provider")
    parser.add_argument("--validate-all", action="store_true", help="Validate all chunks (slow)")
    parser.add_argument("--test", action="store_true", help="Run quick test")

    args = parser.parse_args()

    # Determine provider
    preferred = None
    if args.provider:
        preferred = AIProvider(args.provider)

    # Create enforcer
    try:
        enforcer = AIEnforcer(preferred_provider=preferred, validate_all=args.validate_all)
        print(f"Active provider: {enforcer.provider_name}")

        if args.test:
            # Quick test
            result = enforcer.client.generate("Say hello in 5 words", max_tokens=50)
            print(f"Test response: {result}")

        elif args.manifest:
            with open(args.manifest, 'r') as f:
                manifest = json.load(f)
            print(f"Manifest has {len(manifest.get('chunks', []))} chunks")
            print("Run through RAG pipeline for full validation")

    except Exception as e:
        print(f"Error: {e}")
