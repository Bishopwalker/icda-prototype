"""
Visual Progress Display System for RAG Indexing

Provides rich console output with progress bars, statistics,
and real-time feedback during the indexing process.

Features:
- Animated progress bars
- Phase indicators
- Chunk visualization
- Statistics dashboard
- Color-coded output (cross-platform)

Author: Universal Context Template
"""

import sys
import os
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

# Try to import rich for fancy output, fallback to basic
try:
    from rich.console import Console
    from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.panel import Panel
    from rich.live import Live
    from rich.layout import Layout
    from rich.text import Text
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


class PhaseStatus(Enum):
    """Status of an indexing phase."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


@dataclass
class PhaseInfo:
    """Information about an indexing phase."""
    name: str
    status: PhaseStatus
    total: int
    current: int
    message: str
    result: Optional[Dict[str, Any]] = None


class BasicProgressDisplay:
    """Basic progress display using print statements."""

    def __init__(self):
        self.phases: Dict[str, PhaseInfo] = {}
        self.current_phase: Optional[str] = None
        self.start_time = time.time()
        self._last_progress_len = 0

    def _clear_line(self):
        """Clear the current line."""
        sys.stdout.write('\r' + ' ' * self._last_progress_len + '\r')
        sys.stdout.flush()

    def _print_progress_bar(self, current: int, total: int, width: int = 40) -> str:
        """Create a text-based progress bar."""
        if total == 0:
            return f"[{'=' * width}] 100%"

        percent = current / total
        filled = int(width * percent)
        bar = '=' * filled + '-' * (width - filled)
        return f"[{bar}] {percent * 100:.1f}%"

    def show_header(self, title: str, target_chunks: int):
        """Display header."""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print(f"  Target: {target_chunks} chunks")
        print("=" * 60 + "\n")

    def on_phase_start(self, phase: str, total: int):
        """Handle phase start."""
        self._clear_line()
        self.current_phase = phase
        self.phases[phase] = PhaseInfo(
            name=phase,
            status=PhaseStatus.RUNNING,
            total=total,
            current=0,
            message=""
        )
        print(f"\n[*] {phase} phase started...")

    def on_progress(self, current: int, total: int, message: str):
        """Handle progress update."""
        if self.current_phase:
            self.phases[self.current_phase].current = current
            self.phases[self.current_phase].message = message

        if total > 0:
            bar = self._print_progress_bar(current, total, 30)
            output = f"\r    {bar} {message[:40]}"
        else:
            output = f"\r    [{current}] {message[:50]}"

        self._last_progress_len = len(output)
        sys.stdout.write(output)
        sys.stdout.flush()

    def on_phase_complete(self, phase: str, result: Dict[str, Any]):
        """Handle phase completion."""
        self._clear_line()
        if phase in self.phases:
            self.phases[phase].status = PhaseStatus.COMPLETE
            self.phases[phase].result = result

        print(f"[+] {phase} complete!")

        # Print results
        for key, value in result.items():
            if isinstance(value, dict):
                print(f"    {key}:")
                for k, v in value.items():
                    print(f"      - {k}: {v}")
            else:
                print(f"    {key}: {value}")

    def on_chunk_created(self, chunk_type: str, file_path: str):
        """Handle chunk creation."""
        pass  # Handled in progress updates

    def on_validation(self, validator: str, passed: bool, message: str):
        """Handle validation result."""
        status = "[PASS]" if passed else "[FAIL]"
        print(f"    {status} {validator}: {message}")

    def show_stats(self, stats: Dict[str, Any]):
        """Display final statistics."""
        print("\n" + "-" * 60)
        print("  INDEXING STATISTICS")
        print("-" * 60)

        for key, value in stats.items():
            if isinstance(value, dict):
                print(f"\n  {key}:")
                for k, v in value.items():
                    print(f"    - {k}: {v}")
            elif isinstance(value, float):
                print(f"  {key}: {value:.2f}")
            else:
                print(f"  {key}: {value}")

        elapsed = time.time() - self.start_time
        print(f"\n  Total time: {elapsed:.2f}s")
        print("-" * 60 + "\n")

    def show_chunk_distribution(self, distribution: Dict[str, int]):
        """Display chunk distribution visualization."""
        print("\n  Chunk Distribution:")

        if not distribution:
            print("    (no chunks)")
            return

        max_count = max(distribution.values())
        max_bar_width = 40

        for category, count in sorted(distribution.items(), key=lambda x: -x[1]):
            bar_width = int((count / max_count) * max_bar_width) if max_count > 0 else 0
            bar = '#' * bar_width
            print(f"    {category:20} {bar} {count}")

    def show_completion(self, success: bool, message: str):
        """Display completion message."""
        print("\n" + "=" * 60)
        if success:
            print(f"  SUCCESS: {message}")
        else:
            print(f"  FAILED: {message}")
        print("=" * 60 + "\n")


class RichProgressDisplay:
    """Rich progress display with fancy formatting."""

    def __init__(self):
        self.console = Console()
        self.phases: Dict[str, PhaseInfo] = {}
        self.current_phase: Optional[str] = None
        self.progress: Optional[Progress] = None
        self.task_id = None
        self.start_time = time.time()
        self.chunk_counts: Dict[str, int] = {}

    def show_header(self, title: str, target_chunks: int):
        """Display fancy header."""
        header = Panel(
            f"[bold cyan]{title}[/bold cyan]\n"
            f"[dim]Target: {target_chunks} chunks[/dim]",
            title="[bold white]RAG INDEXER[/bold white]",
            border_style="cyan"
        )
        self.console.print(header)

    def on_phase_start(self, phase: str, total: int):
        """Handle phase start with progress bar."""
        self.current_phase = phase
        self.phases[phase] = PhaseInfo(
            name=phase,
            status=PhaseStatus.RUNNING,
            total=total,
            current=0,
            message=""
        )

        self.console.print(f"\n[bold yellow]>>> {phase}[/bold yellow]")

        if total > 0:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(bar_width=40),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                console=self.console
            )
            self.progress.start()
            self.task_id = self.progress.add_task(phase, total=total)

    def on_progress(self, current: int, total: int, message: str):
        """Handle progress update."""
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, completed=current, description=message[:50])

        if self.current_phase:
            self.phases[self.current_phase].current = current
            self.phases[self.current_phase].message = message

    def on_phase_complete(self, phase: str, result: Dict[str, Any]):
        """Handle phase completion."""
        if self.progress:
            self.progress.stop()
            self.progress = None
            self.task_id = None

        if phase in self.phases:
            self.phases[phase].status = PhaseStatus.COMPLETE
            self.phases[phase].result = result

        # Create result table
        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="dim")
        table.add_column("Value", style="cyan")

        for key, value in result.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    table.add_row(f"  {k}", str(v))
            else:
                table.add_row(key, str(value))

        self.console.print(f"[bold green]<<< {phase} complete[/bold green]")
        self.console.print(table)

    def on_chunk_created(self, chunk_type: str, file_path: str):
        """Track chunk creation."""
        self.chunk_counts[chunk_type] = self.chunk_counts.get(chunk_type, 0) + 1

    def on_validation(self, validator: str, passed: bool, message: str):
        """Handle validation result."""
        if passed:
            self.console.print(f"    [green]PASS[/green] {validator}: {message}")
        else:
            self.console.print(f"    [red]FAIL[/red] {validator}: {message}")

    def show_stats(self, stats: Dict[str, Any]):
        """Display statistics in a fancy table."""
        table = Table(title="Indexing Statistics", border_style="blue")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        for key, value in stats.items():
            if isinstance(value, dict):
                for k, v in value.items():
                    table.add_row(f"  {k}", str(v))
            elif isinstance(value, float):
                table.add_row(key, f"{value:.2f}")
            else:
                table.add_row(key, str(value))

        elapsed = time.time() - self.start_time
        table.add_row("Total Time", f"{elapsed:.2f}s")

        self.console.print()
        self.console.print(table)

    def show_chunk_distribution(self, distribution: Dict[str, int]):
        """Display chunk distribution as a bar chart."""
        if not distribution:
            return

        self.console.print("\n[bold]Chunk Distribution[/bold]")

        max_count = max(distribution.values())

        for category, count in sorted(distribution.items(), key=lambda x: -x[1]):
            bar_width = int((count / max_count) * 30) if max_count > 0 else 0
            bar = '█' * bar_width
            self.console.print(f"  [dim]{category:20}[/dim] [cyan]{bar}[/cyan] {count}")

    def show_completion(self, success: bool, message: str):
        """Display completion panel."""
        if success:
            panel = Panel(
                f"[bold green]{message}[/bold green]",
                title="[bold white]SUCCESS[/bold white]",
                border_style="green"
            )
        else:
            panel = Panel(
                f"[bold red]{message}[/bold red]",
                title="[bold white]FAILED[/bold white]",
                border_style="red"
            )
        self.console.print()
        self.console.print(panel)


class ProgressDisplay:
    """Factory that returns appropriate display based on environment."""

    @staticmethod
    def create() -> 'BasicProgressDisplay | RichProgressDisplay':
        """Create appropriate progress display."""
        # Check if we're in a terminal and rich is available
        if RICH_AVAILABLE and sys.stdout.isatty():
            return RichProgressDisplay()
        return BasicProgressDisplay()


class RAGProgressCallback:
    """
    Progress callback implementation that connects RAGOrchestrator
    to the visual progress display.
    """

    def __init__(self, display=None):
        self.display = display or ProgressDisplay.create()
        self.target_chunks = 333

    def set_target(self, target: int):
        """Set target chunk count for display."""
        self.target_chunks = target

    def show_header(self, title: str = "RAG Indexing Pipeline"):
        """Show header."""
        self.display.show_header(title, self.target_chunks)

    def on_phase_start(self, phase: str, total: int):
        """Delegate to display."""
        self.display.on_phase_start(phase, total)

    def on_progress(self, current: int, total: int, message: str):
        """Delegate to display."""
        self.display.on_progress(current, total, message)

    def on_phase_complete(self, phase: str, result: Dict[str, Any]):
        """Delegate to display."""
        self.display.on_phase_complete(phase, result)

    def on_chunk_created(self, chunk):
        """Handle chunk creation from CodeChunk object."""
        chunk_type = chunk.chunk_type.value if hasattr(chunk.chunk_type, 'value') else str(chunk.chunk_type)
        self.display.on_chunk_created(chunk_type, chunk.file_path)

    def on_validation(self, validator: str, passed: bool, message: str):
        """Delegate to display."""
        self.display.on_validation(validator, passed, message)

    def show_stats(self, stats: Dict[str, Any]):
        """Show final statistics."""
        self.display.show_stats(stats)

    def show_chunk_distribution(self, distribution: Dict[str, int]):
        """Show chunk distribution."""
        self.display.show_chunk_distribution(distribution)

    def show_completion(self, success: bool, message: str):
        """Show completion message."""
        self.display.show_completion(success, message)


# Demo/test
if __name__ == "__main__":
    # Demo the progress display
    display = ProgressDisplay.create()

    display.show_header("Demo Indexing", 333)

    # Simulate discovery phase
    display.on_phase_start("Discovery", 0)
    for i in range(50):
        display.on_progress(i + 1, 0, f"Found file_{i}.py")
        time.sleep(0.02)
    display.on_phase_complete("Discovery", {
        "total_files": 50,
        "categories": {"source_code": 30, "documentation": 15, "config": 5}
    })

    # Simulate chunking phase
    display.on_phase_start("Chunking", 50)
    for i in range(50):
        display.on_progress(i + 1, 50, f"Chunking file_{i}.py")
        time.sleep(0.02)
    display.on_phase_complete("Chunking", {
        "total_chunks": 333,
        "target": 333
    })

    # Show validation
    display.on_validation("Size Check", True, "All chunks within limits")
    display.on_validation("Coverage", True, "100% file coverage")

    # Show stats
    display.show_stats({
        "total_files": 50,
        "total_chunks": 333,
        "avg_chunk_size": 450.5,
        "chunks_by_type": {
            "class": 50,
            "function": 200,
            "documentation": 83
        }
    })

    display.show_chunk_distribution({
        "source_code": 200,
        "documentation": 80,
        "configuration": 30,
        "tests": 23
    })

    display.show_completion(True, "Indexing completed successfully!")
