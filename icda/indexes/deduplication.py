"""
Deduplication Manager - Cross-Index Content Deduplication.

Handles deduplication of content that appears in multiple indexes
using content hashing and similarity detection.

Features:
- Content hash-based exact dedup
- Similarity-based near-dedup
- Source tracking for duplicates
- Merge strategies for federated results
"""

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING
import hashlib
import logging

if TYPE_CHECKING:
    from .index_federation import FederatedResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DuplicateInfo:
    """Information about a duplicate content item."""
    content_hash: str
    primary_source: str
    alternate_sources: list[str] = field(default_factory=list)
    occurrence_count: int = 1


class DeduplicationManager:
    """
    Manages content deduplication across the index hierarchy.

    Strategy:
    1. Each chunk gets a content_hash (SHA256 of normalized text)
    2. During federated search, results are grouped by content_hash
    3. Duplicates are merged, keeping the highest-scored version
    4. Alternate sources are tracked for transparency

    Usage:
        dedup = DeduplicationManager()
        results, dedup_count = dedup.deduplicate_results(federated_results)
    """

    # Similarity threshold for near-duplicate detection
    SIMILARITY_THRESHOLD = 0.95

    def __init__(self):
        """Initialize the deduplication manager."""
        self._hash_cache: dict[str, DuplicateInfo] = {}
        self.stats = {
            "total_processed": 0,
            "duplicates_found": 0,
            "exact_matches": 0,
            "near_matches": 0,
        }

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """
        Compute a hash for content deduplication.

        Normalizes text before hashing to catch near-duplicates.

        Args:
            text: Text content

        Returns:
            str: SHA256 hash (first 16 chars)
        """
        # Normalize: lowercase, collapse whitespace, remove punctuation
        normalized = " ".join(text.lower().split())
        # Remove common punctuation that might differ
        for char in ".,;:!?'\"()[]{}":
            normalized = normalized.replace(char, "")

        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def deduplicate_results(
        self,
        results: list["FederatedResult"],
    ) -> tuple[list["FederatedResult"], int]:
        """
        Deduplicate federated search results.

        Groups results by content hash and keeps the highest-scored
        version while tracking alternate sources.

        Args:
            results: List of FederatedResult objects

        Returns:
            tuple: (deduplicated_results, duplicate_count)
        """
        if not results:
            return [], 0

        # Group by content hash
        by_hash: dict[str, list["FederatedResult"]] = {}

        for result in results:
            content_hash = self.compute_content_hash(result.text)

            if content_hash not in by_hash:
                by_hash[content_hash] = []
            by_hash[content_hash].append(result)

        # Merge duplicates
        deduplicated: list["FederatedResult"] = []
        duplicate_count = 0

        for content_hash, group in by_hash.items():
            self.stats["total_processed"] += len(group)

            if len(group) == 1:
                # No duplicates
                deduplicated.append(group[0])
            else:
                # Has duplicates - keep highest scored
                duplicate_count += len(group) - 1
                self.stats["duplicates_found"] += len(group) - 1
                self.stats["exact_matches"] += len(group) - 1

                # Sort by score descending
                group.sort(key=lambda r: r.score, reverse=True)

                # Keep the best one
                primary = group[0]

                # Track alternate sources
                alternate_sources = [
                    r.source_index for r in group[1:]
                    if r.source_index != primary.source_index
                ]

                primary.is_deduplicated = True
                primary.alternate_sources = list(set(alternate_sources))

                deduplicated.append(primary)

        return deduplicated, duplicate_count

    def find_near_duplicates(
        self,
        texts: list[str],
        threshold: float = None,
    ) -> list[tuple[int, int, float]]:
        """
        Find near-duplicate text pairs using simple similarity.

        Uses a fast heuristic based on word overlap.

        Args:
            texts: List of text strings
            threshold: Similarity threshold (default: SIMILARITY_THRESHOLD)

        Returns:
            List of (index1, index2, similarity) tuples
        """
        threshold = threshold or self.SIMILARITY_THRESHOLD
        duplicates = []

        # Build word sets for each text
        word_sets = [set(t.lower().split()) for t in texts]

        # Compare pairs
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                # Jaccard similarity
                intersection = len(word_sets[i] & word_sets[j])
                union = len(word_sets[i] | word_sets[j])

                if union > 0:
                    similarity = intersection / union

                    if similarity >= threshold:
                        duplicates.append((i, j, similarity))
                        self.stats["near_matches"] += 1

        return duplicates

    def merge_duplicate_chunks(
        self,
        chunks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Merge duplicate chunks from different sources.

        Keeps the chunk with the most metadata/context.

        Args:
            chunks: List of chunk dicts

        Returns:
            List of merged chunks
        """
        by_hash: dict[str, list[dict[str, Any]]] = {}

        for chunk in chunks:
            content_hash = self.compute_content_hash(chunk.get("text", ""))

            if content_hash not in by_hash:
                by_hash[content_hash] = []
            by_hash[content_hash].append(chunk)

        merged = []

        for group in by_hash.values():
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Merge by keeping the one with most metadata
                best = max(
                    group,
                    key=lambda c: len(c.get("tags", [])) + (1 if c.get("category") else 0),
                )

                # Combine tags from all
                all_tags = set()
                for chunk in group:
                    all_tags.update(chunk.get("tags", []))

                best["tags"] = list(all_tags)
                best["merged_from"] = len(group)

                merged.append(best)

        return merged

    def register_content(
        self,
        content_hash: str,
        source_index: str,
        doc_id: str,
    ) -> None:
        """
        Register content in the dedup cache.

        Used for tracking content across indexes.

        Args:
            content_hash: Content hash
            source_index: Which index contains this content
            doc_id: Document ID
        """
        if content_hash not in self._hash_cache:
            self._hash_cache[content_hash] = DuplicateInfo(
                content_hash=content_hash,
                primary_source=source_index,
            )
        else:
            info = self._hash_cache[content_hash]
            if source_index != info.primary_source:
                if source_index not in info.alternate_sources:
                    info.alternate_sources.append(source_index)
            info.occurrence_count += 1

    def get_duplicate_info(self, content_hash: str) -> DuplicateInfo | None:
        """
        Get duplicate information for a content hash.

        Args:
            content_hash: Content hash to look up

        Returns:
            DuplicateInfo or None if not found
        """
        return self._hash_cache.get(content_hash)

    def get_stats(self) -> dict[str, Any]:
        """Get deduplication statistics."""
        return {
            **self.stats,
            "cached_hashes": len(self._hash_cache),
            "multi_source_content": sum(
                1 for info in self._hash_cache.values()
                if info.alternate_sources
            ),
        }

    def clear_cache(self) -> None:
        """Clear the hash cache."""
        self._hash_cache.clear()

    def get_cross_index_content(self) -> list[DuplicateInfo]:
        """
        Get content that exists in multiple indexes.

        Returns:
            List of DuplicateInfo for multi-source content
        """
        return [
            info for info in self._hash_cache.values()
            if info.alternate_sources
        ]
