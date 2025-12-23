"""
Knowledge Index State Tracker
=============================
Tracks which files are indexed and their content hashes to enable incremental reindexing.
Avoids re-indexing unchanged files by comparing SHA256 content hashes.

Usage:
    state = load_index_state(Path("knowledge/.index_state.json"))
    hash = compute_file_hash(Path("knowledge/data/doc.md"))
    if needs_reindex(state, "data/doc.md", hash):
        # index the file
        update_file_state(state, "data/doc.md", doc_id, hash, chunks)
    save_index_state(state_file, state)
"""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Supported file extensions for indexing
SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.json',           # Text
    '.pdf',                            # PDF
    '.doc', '.docx',                   # Word
    '.xls', '.xlsx',                   # Excel
    '.csv',                            # CSV
    '.odt', '.odf',                    # OpenDocument
    '.html', '.htm',                   # HTML
}


def compute_file_hash(path: Path) -> str:
    """
    Compute SHA256 hash of file content.

    Args:
        path: Path to the file

    Returns:
        SHA256 hash prefixed with 'sha256:'
    """
    sha256 = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return f"sha256:{sha256.hexdigest()}"


def create_empty_state() -> dict[str, Any]:
    """Create a new empty index state."""
    return {
        "version": "1.0",
        "last_full_index": None,
        "files": {}
    }


def load_index_state(state_file: Path) -> dict[str, Any]:
    """
    Load index state from JSON file.

    Args:
        state_file: Path to the state file

    Returns:
        State dictionary, or empty state if file doesn't exist
    """
    if not state_file.exists():
        return create_empty_state()

    try:
        with open(state_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
            # Validate version
            if state.get("version") != "1.0":
                print(f"  Warning: Unknown state version {state.get('version')}, creating new state")
                return create_empty_state()
            return state
    except (json.JSONDecodeError, IOError) as e:
        print(f"  Warning: Could not load index state: {e}")
        return create_empty_state()


def save_index_state(state_file: Path, state: dict[str, Any]) -> bool:
    """
    Save index state to JSON file atomically.

    Args:
        state_file: Path to the state file
        state: State dictionary to save

    Returns:
        True if successful
    """
    state_file.parent.mkdir(parents=True, exist_ok=True)

    # Write to temp file first, then rename (atomic on most systems)
    temp_file = state_file.with_suffix('.json.tmp')
    try:
        with open(temp_file, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2, default=str)
        temp_file.replace(state_file)
        return True
    except IOError as e:
        print(f"  Error saving index state: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False


def get_file_state(state: dict[str, Any], relative_path: str) -> dict[str, Any] | None:
    """
    Get indexed state for a specific file.

    Args:
        state: Index state dictionary
        relative_path: Path relative to knowledge directory (e.g., "data/doc.md")

    Returns:
        File state dict or None if not indexed
    """
    return state.get("files", {}).get(relative_path)


def update_file_state(
    state: dict[str, Any],
    relative_path: str,
    doc_id: str,
    content_hash: str,
    chunks_indexed: int = 0
) -> None:
    """
    Update or add file state after successful indexing.

    Args:
        state: Index state dictionary (modified in place)
        relative_path: Path relative to knowledge directory
        doc_id: Document ID returned from indexing
        content_hash: SHA256 hash of file content
        chunks_indexed: Number of chunks indexed
    """
    if "files" not in state:
        state["files"] = {}

    state["files"][relative_path] = {
        "doc_id": doc_id,
        "content_hash": content_hash,
        "indexed_at": datetime.now(timezone.utc).isoformat(),
        "chunks_indexed": chunks_indexed
    }


def remove_file_state(state: dict[str, Any], relative_path: str) -> str | None:
    """
    Remove file from state (when file is deleted).

    Args:
        state: Index state dictionary (modified in place)
        relative_path: Path relative to knowledge directory

    Returns:
        doc_id if file was tracked, None otherwise
    """
    file_state = state.get("files", {}).pop(relative_path, None)
    return file_state.get("doc_id") if file_state else None


def needs_reindex(state: dict[str, Any], relative_path: str, current_hash: str) -> bool:
    """
    Check if a file needs to be reindexed.

    Args:
        state: Index state dictionary
        relative_path: Path relative to knowledge directory
        current_hash: Current SHA256 hash of file content

    Returns:
        True if file is new or content has changed
    """
    file_state = get_file_state(state, relative_path)
    if not file_state:
        return True  # New file
    return file_state.get("content_hash") != current_hash


def get_stale_files(
    state: dict[str, Any],
    knowledge_dir: Path,
    data_dirs: list[str] | None = None
) -> list[tuple[str, str]]:
    """
    Find files that have been modified since last indexing.

    Args:
        state: Index state dictionary
        knowledge_dir: Base knowledge directory
        data_dirs: Subdirectories to scan (default: ["data", "data-uploaded"])

    Returns:
        List of (relative_path, current_hash) tuples for modified files
    """
    if data_dirs is None:
        data_dirs = ["data", "data-uploaded"]

    stale = []
    for subdir in data_dirs:
        dir_path = knowledge_dir / subdir
        if not dir_path.exists():
            continue

        for filepath in dir_path.rglob("*"):
            if not _should_process_file(filepath):
                continue

            relative_path = str(filepath.relative_to(knowledge_dir))
            current_hash = compute_file_hash(filepath)

            if needs_reindex(state, relative_path, current_hash):
                stale.append((relative_path, current_hash))

    return stale


def get_orphaned_entries(state: dict[str, Any], knowledge_dir: Path) -> list[tuple[str, str]]:
    """
    Find indexed documents whose source files no longer exist.

    Args:
        state: Index state dictionary
        knowledge_dir: Base knowledge directory

    Returns:
        List of (relative_path, doc_id) tuples for orphaned entries
    """
    orphaned = []
    for relative_path, file_state in state.get("files", {}).items():
        filepath = knowledge_dir / relative_path
        if not filepath.exists():
            orphaned.append((relative_path, file_state.get("doc_id", "")))

    return orphaned


def get_new_files(
    state: dict[str, Any],
    knowledge_dir: Path,
    data_dirs: list[str] | None = None
) -> list[tuple[Path, str]]:
    """
    Find files that are not yet indexed.

    Args:
        state: Index state dictionary
        knowledge_dir: Base knowledge directory
        data_dirs: Subdirectories to scan (default: ["data", "data-uploaded"])

    Returns:
        List of (filepath, relative_path) tuples for new files
    """
    if data_dirs is None:
        data_dirs = ["data", "data-uploaded"]

    new_files = []
    for subdir in data_dirs:
        dir_path = knowledge_dir / subdir
        if not dir_path.exists():
            continue

        for filepath in dir_path.rglob("*"):
            if not _should_process_file(filepath):
                continue

            relative_path = str(filepath.relative_to(knowledge_dir))
            if relative_path not in state.get("files", {}):
                new_files.append((filepath, relative_path))

    return new_files


def mark_full_reindex(state: dict[str, Any]) -> None:
    """Mark that a full reindex was performed."""
    state["last_full_index"] = datetime.now(timezone.utc).isoformat()


def get_stats(state: dict[str, Any]) -> dict[str, Any]:
    """
    Get statistics about the index state.

    Returns:
        Dict with tracked_files, total_chunks, last_full_index
    """
    files = state.get("files", {})
    total_chunks = sum(f.get("chunks_indexed", 0) for f in files.values())

    return {
        "tracked_files": len(files),
        "total_chunks": total_chunks,
        "last_full_index": state.get("last_full_index"),
        "version": state.get("version", "unknown")
    }


def _should_process_file(filepath: Path) -> bool:
    """Check if file should be processed for indexing."""
    if not filepath.is_file():
        return False
    if filepath.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False
    if filepath.name.startswith('.'):
        return False
    if filepath.name.lower() == 'readme.md':
        return False
    return True
