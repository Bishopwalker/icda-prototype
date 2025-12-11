"""
Universal Memory Service - Persistent Session & Context Memory with Mem0
Tracks conversation context, code work, decisions, and learning across sessions
Domain-agnostic memory management for any codebase
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
import json
from dataclasses import dataclass, asdict
from enum import Enum


class MemoryType(Enum):
    """Types of memories tracked by the system"""
    SESSION = "session"              # Conversation context
    CODE_CONTEXT = "code_context"    # Recently accessed files/functions
    DECISION = "decision"            # Architectural/design decisions
    LEARNING = "learning"            # What worked/failed
    ENTITY = "entity"                # Projects, features, bugs


@dataclass
class Memory:
    """
    Represents a single memory entry

    Attributes:
        id: Unique identifier
        type: Type of memory (session, code_context, decision, etc.)
        content: The actual memory content
        metadata: Additional context (file paths, timestamps, etc.)
        timestamp: When the memory was created
        session_id: Associated session ID (if applicable)
    """
    id: str
    type: MemoryType
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    session_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert memory to dictionary for storage"""
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Memory":
        """Create memory from dictionary"""
        return cls(
            id=data["id"],
            type=MemoryType(data["type"]),
            content=data["content"],
            metadata=data["metadata"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            session_id=data.get("session_id")
        )


class MemoryService:
    """
    Manages persistent memory using Mem0

    Hybrid Approach:
    - Session Memory: Track conversation context across Claude sessions
    - Code Context: Remember recently accessed files, functions, bugs
    - Decision History: Store architectural decisions and rationale
    - Learning: Remember patterns that worked/failed
    - Entity Tracking: Track projects, files, bugs, features

    Integration with RAG:
    - RAG = Code search and discovery (find relevant code)
    - Memory = Session context (what you're currently working on)
    - Both work together: Memory enhances RAG queries
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Memory Service with Mem0

        Args:
            config: Configuration dict from RAGConfig.get_mem0_config()
                   - mode: "local" or "cloud"
                   - api_key: (cloud only) Mem0 API key
                   - organization_id: (optional) Mem0 organization
                   - project_id: (optional) Mem0 project

        Example:
            >>> from .config import load_config
            >>> config = load_config()
            >>> memory = MemoryService(config.get_mem0_config())
        """
        self.config = config
        self.mode = config.get("mode", "local")

        # Initialize Mem0 client
        self._init_mem0_client()

    def _init_mem0_client(self):
        """Initialize the Mem0 client based on configuration"""
        try:
            from mem0 import Memory as Mem0Client

            if self.mode == "cloud":
                # Cloud mode requires API key
                self.client = Mem0Client(
                    api_key=self.config.get("api_key"),
                    organization_id=self.config.get("organization_id"),
                    project_id=self.config.get("project_id")
                )
            else:
                # Local mode - no API key needed
                self.client = Mem0Client()

        except ImportError:
            raise ImportError(
                "mem0ai package not installed. Install with: pip install mem0ai"
            )

    def save_session_memory(
        self,
        session_id: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Save session context for later retrieval

        Args:
            session_id: Unique session identifier
            content: Memory content (e.g., "Working on API performance optimization")
            metadata: Additional context (file paths, features, etc.)

        Returns:
            Memory ID

        Example:
            >>> memory_id = service.save_session_memory(
            ...     session_id="session_123",
            ...     content="Fixed connection pool timeout in DatabaseService.ts",
            ...     metadata={"files": ["src/services/DatabaseService.ts"], "feature": "database"}
            ... )
        """
        metadata = metadata or {}
        metadata["type"] = MemoryType.SESSION.value
        metadata["session_id"] = session_id
        metadata["timestamp"] = datetime.now().isoformat()

        result = self.client.add(
            messages=[{"role": "user", "content": content}],
            user_id=session_id,
            metadata=metadata
        )

        return result.get("id") if isinstance(result, dict) else str(result)

    def get_session_memory(self, session_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Retrieve all memory for a session

        Args:
            session_id: Session identifier
            limit: Maximum number of memories to return

        Returns:
            List of memory dictionaries

        Example:
            >>> memories = service.get_session_memory("session_123")
            >>> for memory in memories:
            ...     print(f"- {memory['content']}")
        """
        try:
            results = self.client.get_all(
                user_id=session_id,
                limit=limit
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            print(f"Warning: Failed to retrieve session memory: {e}")
            return []

    def search_memory(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search across all memories using semantic search

        Args:
            query: Search query
            filters: Optional filters (type, session_id, etc.)
            limit: Maximum results

        Returns:
            List of matching memories

        Example:
            >>> results = service.search_memory(
            ...     query="API authentication issues",
            ...     filters={"type": "code_context"}
            ... )
        """
        try:
            results = self.client.search(
                query=query,
                limit=limit,
                filters=filters
            )
            return results if isinstance(results, list) else []
        except Exception as e:
            print(f"Warning: Memory search failed: {e}")
            return []

    def save_code_context(
        self,
        file_path: str,
        context: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Save recently accessed code context

        Args:
            file_path: Path to the file
            context: What was done (e.g., "Fixed buffer starvation issue")
            session_id: Associated session (optional)

        Returns:
            Memory ID

        Example:
            >>> service.save_code_context(
            ...     file_path="src/services/DatabaseService.ts",
            ...     context="Increased connection pool size from 10 to 20 connections to handle load"
            ... )
        """
        metadata = {
            "type": MemoryType.CODE_CONTEXT.value,
            "file_path": file_path,
            "timestamp": datetime.now().isoformat()
        }
        if session_id:
            metadata["session_id"] = session_id

        result = self.client.add(
            messages=[{"role": "user", "content": f"{file_path}: {context}"}],
            user_id=session_id or "global",
            metadata=metadata
        )

        return result.get("id") if isinstance(result, dict) else str(result)

    def get_code_context(self, file_path: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get context for a specific file

        Args:
            file_path: Path to the file
            limit: Maximum number of context entries

        Returns:
            List of code contexts for the file

        Example:
            >>> contexts = service.get_code_context("src/services/DatabaseService.ts")
            >>> for ctx in contexts:
            ...     print(f"Previous work: {ctx['content']}")
        """
        return self.search_memory(
            query=file_path,
            filters={"type": MemoryType.CODE_CONTEXT.value, "file_path": file_path},
            limit=limit
        )

    def save_decision(
        self,
        decision: str,
        rationale: str,
        outcome: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Record architectural/design decisions

        Args:
            decision: The decision made
            rationale: Why it was made
            outcome: Result (optional, can be added later)
            session_id: Associated session (optional)

        Returns:
            Memory ID

        Example:
            >>> service.save_decision(
            ...     decision="Use Redis for session storage instead of in-memory",
            ...     rationale="Better scalability, persistence across server restarts",
            ...     outcome="Successfully improved session reliability across deployments"
            ... )
        """
        content = f"Decision: {decision}\nRationale: {rationale}"
        if outcome:
            content += f"\nOutcome: {outcome}"

        metadata = {
            "type": MemoryType.DECISION.value,
            "decision": decision,
            "rationale": rationale,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat()
        }
        if session_id:
            metadata["session_id"] = session_id

        result = self.client.add(
            messages=[{"role": "user", "content": content}],
            user_id=session_id or "global",
            metadata=metadata
        )

        return result.get("id") if isinstance(result, dict) else str(result)

    def search_decisions(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find relevant past decisions

        Args:
            query: Search query (e.g., "database architecture")
            limit: Maximum results

        Returns:
            List of matching decisions

        Example:
            >>> decisions = service.search_decisions("buffer management")
            >>> for decision in decisions:
            ...     print(f"- {decision['metadata']['decision']}")
        """
        return self.search_memory(
            query=query,
            filters={"type": MemoryType.DECISION.value},
            limit=limit
        )

    def save_learning(
        self,
        lesson: str,
        category: str,
        outcome: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Record what worked or failed

        Args:
            lesson: What was learned
            category: Category (e.g., "database", "performance", "bug_fix")
            outcome: "success" or "failure"
            session_id: Associated session (optional)

        Returns:
            Memory ID

        Example:
            >>> service.save_learning(
            ...     lesson="Increasing connection pool size to 20 reduces timeout errors",
            ...     category="database_performance",
            ...     outcome="success"
            ... )
        """
        content = f"Learning ({outcome}): {lesson}"

        metadata = {
            "type": MemoryType.LEARNING.value,
            "category": category,
            "outcome": outcome,
            "timestamp": datetime.now().isoformat()
        }
        if session_id:
            metadata["session_id"] = session_id

        result = self.client.add(
            messages=[{"role": "user", "content": content}],
            user_id=session_id or "global",
            metadata=metadata
        )

        return result.get("id") if isinstance(result, dict) else str(result)

    def get_learnings(
        self,
        category: Optional[str] = None,
        outcome: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Retrieve learnings (successes and failures)

        Args:
            category: Filter by category (optional)
            outcome: Filter by outcome ("success" or "failure", optional)
            limit: Maximum results

        Returns:
            List of learnings

        Example:
            >>> successes = service.get_learnings(category="database", outcome="success")
            >>> for learning in successes:
            ...     print(f"✓ {learning['content']}")
        """
        filters = {"type": MemoryType.LEARNING.value}
        if category:
            filters["category"] = category
        if outcome:
            filters["outcome"] = outcome

        return self.search_memory(
            query=category or "learnings",
            filters=filters,
            limit=limit
        )

    def enhance_rag_query(
        self,
        query: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Enhance a RAG query with session context

        This helps RAG understand what you're currently working on,
        making search results more relevant.

        Args:
            query: Original RAG query
            session_id: Current session ID

        Returns:
            Enhanced query with context

        Example:
            >>> # User working on API optimization
            >>> enhanced = service.enhance_rag_query(
            ...     query="connection pooling",
            ...     session_id="session_123"
            ... )
            >>> # Result: "connection pooling (context: working on API optimization, recent files: DatabaseService.ts)"
        """
        if not session_id:
            return query

        # Get recent session context
        recent_memories = self.get_session_memory(session_id, limit=3)

        if not recent_memories:
            return query

        # Extract context
        context_items = []
        for memory in recent_memories:
            if isinstance(memory, dict):
                content = memory.get("content", "")
                if content:
                    context_items.append(content[:100])  # First 100 chars

        if context_items:
            context = ", ".join(context_items)
            enhanced_query = f"{query} (recent context: {context})"
            return enhanced_query

        return query

    def clear_session(self, session_id: str):
        """
        Clear all memories for a session

        Args:
            session_id: Session to clear

        Example:
            >>> service.clear_session("session_123")
        """
        try:
            self.client.delete_all(user_id=session_id)
        except Exception as e:
            print(f"Warning: Failed to clear session: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get memory system statistics

        Returns:
            Dictionary with stats (total memories, by type, etc.)

        Example:
            >>> stats = service.get_stats()
            >>> print(f"Total memories: {stats['total']}")
        """
        # Note: Actual implementation depends on Mem0 API capabilities
        # This is a placeholder that can be enhanced based on Mem0's features
        return {
            "mode": self.mode,
            "status": "active"
        }


# Example usage
if __name__ == "__main__":
    from .config import load_config

    # Load configuration
    config = load_config()
    mem0_config = config.get_mem0_config()

    # Initialize memory service
    memory = MemoryService(mem0_config)

    # Example: Save session memory
    session_id = "demo_session"
    memory.save_session_memory(
        session_id=session_id,
        content="Working on API connection pooling optimization",
        metadata={"feature": "database", "priority": "high"}
    )

    # Example: Save code context
    memory.save_code_context(
        file_path="src/services/DatabaseService.ts",
        context="Increased connection pool size from 10 to 20",
        session_id=session_id
    )

    # Example: Search memories
    results = memory.search_memory("connection pooling")
    print(f"Found {len(results)} memories about connection pooling")

    # Example: Enhance RAG query
    enhanced = memory.enhance_rag_query("database optimization", session_id)
    print(f"Enhanced query: {enhanced}")
