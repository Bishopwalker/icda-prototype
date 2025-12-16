"""
Knowledge Directory Watcher
===========================
Monitors the /knowledge directory for new files and auto-indexes them.

Usage:
    watcher = KnowledgeWatcher(knowledge_dir, knowledge_manager)
    watcher.start()  # Start watching in background thread
    watcher.stop()   # Stop watching
"""

import asyncio
import threading
from pathlib import Path
from typing import Callable, Awaitable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent


# Supported file extensions for auto-indexing
SUPPORTED_EXTENSIONS = {
    '.txt', '.md', '.json',           # Text
    '.pdf',                            # PDF
    '.doc', '.docx',                   # Word
    '.xls', '.xlsx',                   # Excel
    '.csv',                            # CSV
    '.odt', '.odf',                    # OpenDocument
}


class KnowledgeFileHandler(FileSystemEventHandler):
    """Handle file system events for knowledge directory."""

    def __init__(self, index_callback: Callable[[Path], Awaitable[dict]], loop: asyncio.AbstractEventLoop):
        """
        Initialize the handler.

        Args:
            index_callback: Async function to call when a file needs indexing.
            loop: The asyncio event loop to schedule callbacks on.
        """
        self.index_callback = index_callback
        self.loop = loop
        self._processing = set()  # Track files being processed to avoid duplicates

    def _should_process(self, path: Path) -> bool:
        """Check if file should be processed."""
        if not path.is_file():
            return False
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return False
        if path.name.startswith('.'):
            return False
        return True

    def _schedule_index(self, filepath: Path):
        """Schedule async indexing on the event loop."""
        if str(filepath) in self._processing:
            return

        self._processing.add(str(filepath))

        async def do_index():
            try:
                print(f"  Auto-indexing: {filepath.name}")
                result = await self.index_callback(filepath)
                if result.get('success'):
                    print(f"  ✓ Indexed: {filepath.name} ({result.get('chunks_indexed', 0)} chunks)")
                else:
                    print(f"  ✗ Failed: {filepath.name} - {result.get('error')}")
            except Exception as e:
                print(f"  ✗ Error indexing {filepath.name}: {e}")
            finally:
                self._processing.discard(str(filepath))

        asyncio.run_coroutine_threadsafe(do_index(), self.loop)

    def on_created(self, event):
        """Handle file creation."""
        if isinstance(event, FileCreatedEvent):
            filepath = Path(event.src_path)
            if self._should_process(filepath):
                # Small delay to ensure file is fully written
                threading.Timer(1.0, lambda: self._schedule_index(filepath)).start()

    def on_modified(self, event):
        """Handle file modification (re-index)."""
        if isinstance(event, FileModifiedEvent):
            filepath = Path(event.src_path)
            if self._should_process(filepath):
                threading.Timer(1.0, lambda: self._schedule_index(filepath)).start()


class KnowledgeWatcher:
    """
    Watch knowledge directory for new/modified files and auto-index them.

    Example:
        async def index_file(path):
            return await knowledge_manager.index_document(path)

        watcher = KnowledgeWatcher(Path("knowledge"), index_file)
        watcher.start()
    """

    def __init__(self, knowledge_dir: Path, index_callback: Callable[[Path], Awaitable[dict]]):
        """
        Initialize the watcher.

        Args:
            knowledge_dir: Directory to watch for knowledge files.
            index_callback: Async function to index a file path.
        """
        self.knowledge_dir = knowledge_dir
        self.index_callback = index_callback
        self.observer = None
        self._running = False

    def start(self):
        """Start watching the knowledge directory."""
        if self._running:
            return

        if not self.knowledge_dir.exists():
            self.knowledge_dir.mkdir(parents=True, exist_ok=True)

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()

        handler = KnowledgeFileHandler(self.index_callback, loop)
        self.observer = Observer()
        self.observer.schedule(handler, str(self.knowledge_dir), recursive=False)
        self.observer.start()
        self._running = True
        print(f"  Knowledge watcher: monitoring {self.knowledge_dir}")

    def stop(self):
        """Stop watching."""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join(timeout=5)
            self._running = False
            print("  Knowledge watcher: stopped")

    @property
    def running(self) -> bool:
        """Check if watcher is running."""
        return self._running
