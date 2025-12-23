"""
Progress Tracker for Long-Running Indexing Operations.

Provides real-time progress tracking with Redis storage and SSE streaming.

Usage:
    tracker = ProgressTracker(cache)
    op_id = await tracker.start_operation("customer_index", total=50000)

    # During indexing:
    await tracker.update_progress(op_id, processed=100, context_tokens=15000)

    # SSE streaming:
    async for event in tracker.stream_progress(op_id):
        yield event
"""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import AsyncIterator


class OperationStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ProgressState:
    """Tracks the state of a long-running operation."""
    operation_id: str
    operation_type: str  # "customer_index", "knowledge_index", etc.
    status: OperationStatus = OperationStatus.PENDING
    total_items: int = 0
    processed_items: int = 0
    error_count: int = 0
    current_batch: int = 0
    total_batches: int = 0
    # Data metrics
    bytes_processed: int = 0
    context_tokens_used: int = 0
    embeddings_generated: int = 0
    # Timing
    start_time: float = 0.0
    last_update: float = 0.0
    elapsed_seconds: float = 0.0
    estimated_remaining_seconds: float = 0.0
    items_per_second: float = 0.0
    # Messages
    current_phase: str = ""
    last_message: str = ""
    error_message: str = ""

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        d = asdict(self)
        d["status"] = self.status.value
        d["percent_complete"] = round(
            (self.processed_items / self.total_items * 100) if self.total_items > 0 else 0, 1
        )
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "ProgressState":
        """Create from dict (Redis deserialization)."""
        data["status"] = OperationStatus(data.get("status", "pending"))
        # Remove computed fields
        data.pop("percent_complete", None)
        return cls(**data)


class ProgressTracker:
    """
    Manages progress tracking for long-running operations.

    Uses Redis for state storage to support distributed workers.
    Provides SSE streaming for real-time frontend updates.
    """

    REDIS_PREFIX = "icda:progress:"
    EXPIRY_SECONDS = 3600  # Keep progress for 1 hour after completion

    def __init__(self, cache):
        """
        Initialize progress tracker.

        Args:
            cache: RedisCache instance for state storage.
        """
        self._cache = cache
        self._active_operations: dict[str, ProgressState] = {}

    @property
    def available(self) -> bool:
        """Check if Redis is available for progress tracking."""
        return self._cache and self._cache.available

    async def start_operation(
        self,
        operation_type: str,
        total_items: int,
        total_batches: int = 0,
        metadata: dict = None,
    ) -> str:
        """
        Start tracking a new operation.

        Args:
            operation_type: Type of operation (e.g., "customer_index")
            total_items: Total number of items to process
            total_batches: Total number of batches (optional)
            metadata: Additional metadata to store

        Returns:
            Operation ID for tracking
        """
        op_id = f"op_{uuid.uuid4().hex[:12]}"
        now = time.time()

        state = ProgressState(
            operation_id=op_id,
            operation_type=operation_type,
            status=OperationStatus.RUNNING,
            total_items=total_items,
            total_batches=total_batches or (total_items // 100 + 1),
            start_time=now,
            last_update=now,
            current_phase="Initializing",
        )

        self._active_operations[op_id] = state
        await self._save_state(op_id, state)

        return op_id

    async def update_progress(
        self,
        operation_id: str,
        processed: int = None,
        errors: int = None,
        batch: int = None,
        phase: str = None,
        message: str = None,
        bytes_processed: int = None,
        context_tokens: int = None,
        embeddings: int = None,
    ) -> ProgressState:
        """
        Update progress for an operation.

        Args:
            operation_id: Operation ID to update
            processed: Total items processed so far
            errors: Total errors so far
            batch: Current batch number
            phase: Current phase description
            message: Status message
            bytes_processed: Total bytes processed
            context_tokens: Total context tokens used
            embeddings: Total embeddings generated

        Returns:
            Updated ProgressState
        """
        state = await self._get_state(operation_id)
        if not state:
            return None

        now = time.time()

        if processed is not None:
            state.processed_items = processed
        if errors is not None:
            state.error_count = errors
        if batch is not None:
            state.current_batch = batch
        if phase is not None:
            state.current_phase = phase
        if message is not None:
            state.last_message = message
        if bytes_processed is not None:
            state.bytes_processed = bytes_processed
        if context_tokens is not None:
            state.context_tokens_used = context_tokens
        if embeddings is not None:
            state.embeddings_generated = embeddings

        # Update timing metrics
        state.last_update = now
        state.elapsed_seconds = now - state.start_time

        if state.elapsed_seconds > 0 and state.processed_items > 0:
            state.items_per_second = state.processed_items / state.elapsed_seconds
            remaining = state.total_items - state.processed_items
            state.estimated_remaining_seconds = remaining / state.items_per_second if state.items_per_second > 0 else 0

        self._active_operations[operation_id] = state
        await self._save_state(operation_id, state)

        return state

    async def complete_operation(
        self,
        operation_id: str,
        success: bool = True,
        message: str = None,
        error: str = None,
    ) -> ProgressState:
        """
        Mark an operation as completed.

        Args:
            operation_id: Operation ID to complete
            success: Whether operation succeeded
            message: Final message
            error: Error message if failed

        Returns:
            Final ProgressState
        """
        state = await self._get_state(operation_id)
        if not state:
            return None

        state.status = OperationStatus.COMPLETED if success else OperationStatus.FAILED
        state.last_update = time.time()
        state.elapsed_seconds = state.last_update - state.start_time
        state.current_phase = "Complete" if success else "Failed"

        if message:
            state.last_message = message
        if error:
            state.error_message = error

        # Remove from active, but keep in Redis for status checks
        self._active_operations.pop(operation_id, None)
        await self._save_state(operation_id, state)

        return state

    async def get_progress(self, operation_id: str) -> ProgressState | None:
        """Get current progress for an operation."""
        return await self._get_state(operation_id)

    async def get_active_operations(self) -> list[ProgressState]:
        """Get all active (running) operations."""
        return list(self._active_operations.values())

    async def stream_progress(
        self,
        operation_id: str,
        interval: float = 0.5,
    ) -> AsyncIterator[str]:
        """
        Stream progress updates as Server-Sent Events.

        Args:
            operation_id: Operation ID to stream
            interval: Update interval in seconds

        Yields:
            SSE-formatted event strings
        """
        last_update = 0.0

        while True:
            state = await self._get_state(operation_id)

            if not state:
                yield self._format_sse({"error": "Operation not found"}, event="error")
                break

            # Only send if updated
            if state.last_update > last_update:
                last_update = state.last_update
                yield self._format_sse(state.to_dict(), event="progress")

            # Check if complete
            if state.status in (OperationStatus.COMPLETED, OperationStatus.FAILED, OperationStatus.CANCELLED):
                yield self._format_sse(state.to_dict(), event="complete")
                break

            await asyncio.sleep(interval)

    def _format_sse(self, data: dict, event: str = "message") -> str:
        """Format data as Server-Sent Event."""
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    async def _save_state(self, operation_id: str, state: ProgressState) -> None:
        """Save state to Redis."""
        if not self.available:
            return

        key = f"{self.REDIS_PREFIX}{operation_id}"
        try:
            await self._cache.set(key, json.dumps(state.to_dict()), ttl=self.EXPIRY_SECONDS)
        except Exception:
            pass  # Non-critical, we have in-memory fallback

    async def _get_state(self, operation_id: str) -> ProgressState | None:
        """Get state from memory or Redis."""
        # Check in-memory first
        if operation_id in self._active_operations:
            return self._active_operations[operation_id]

        # Try Redis
        if not self.available:
            return None

        key = f"{self.REDIS_PREFIX}{operation_id}"
        try:
            data = await self._cache.get(key)
            if data:
                return ProgressState.from_dict(json.loads(data))
        except Exception:
            pass

        return None


def format_bytes(size: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        m, s = divmod(int(seconds), 60)
        return f"{m}m {s}s"
    else:
        h, rem = divmod(int(seconds), 3600)
        m, s = divmod(rem, 60)
        return f"{h}h {m}m {s}s"
