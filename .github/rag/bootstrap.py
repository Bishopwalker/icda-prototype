#!/usr/bin/env python3
"""
Universal Context Template - Bootstrap Orchestrator
Auto-initializes RAG system, conventions analyzer, and project wizard on first run.

This script implements the "enforcer pattern" - it runs automatically when:
1. /context-init is executed for the first time
2. Docker container installs the template
3. Claude Code hooks detect first interaction

Features:
- First-run detection via marker file
- Automatic dependency installation
- RAG indexing of project codebase
- Conventions analysis and learning
- Project wizard for template customization
- Idempotent - safe to run multiple times
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MARKER_FILE = ".github/.initialized"
RAG_DIR = ".github/rag"
STATUS_FILE = ".github/BOOTSTRAP_STATUS.json"


class BootstrapOrchestrator:
    """
    Orchestrates the first-run initialization of the Universal Context Template.
    Implements idempotent initialization - safe to run multiple times.
    """

    def __init__(self, project_root: Optional[str] = None):
        """
        Initialize the bootstrap orchestrator.

        Args:
            project_root: Root directory of the project. Defaults to cwd.
        """
        self.project_root = Path(project_root or os.getcwd()).resolve()
        self.github_dir = self.project_root / ".github"
        self.rag_dir = self.github_dir / "rag"
        self.marker_file = self.github_dir / ".initialized"
        self.status_file = self.github_dir / "BOOTSTRAP_STATUS.json"

        # Status tracking
        self.status = {
            "initialized": False,
            "timestamp": None,
            "steps_completed": [],
            "steps_failed": [],
            "rag_indexed": False,
            "conventions_analyzed": False,
            "project_type": None,
            "files_indexed": 0,
            "errors": []
        }

    def is_initialized(self) -> bool:
        """Check if the project has already been initialized."""
        return self.marker_file.exists()

    def should_reinitialize(self) -> bool:
        """Check if reinitialization is needed (e.g., major version change)."""
        if not self.status_file.exists():
            return True

        try:
            with open(self.status_file, 'r') as f:
                saved_status = json.load(f)

            # Check version (force reinit on major version changes)
            saved_version = saved_status.get("version", "0.0.0")
            current_version = "2.2.0"

            saved_major = int(saved_version.split('.')[0])
            current_major = int(current_version.split('.')[0])

            return current_major > saved_major
        except Exception:
            return True

    def check_dependencies(self) -> Dict[str, bool]:
        """
        Check which dependencies are installed.

        Returns:
            Dict mapping dependency name to availability status
        """
        deps = {}

        # Check Python packages
        packages = [
            ("chromadb", "chromadb"),
            ("sentence_transformers", "sentence-transformers"),
            ("langchain", "langchain"),
        ]

        for import_name, pip_name in packages:
            try:
                __import__(import_name)
                deps[pip_name] = True
            except ImportError:
                deps[pip_name] = False

        return deps

    def install_dependencies(self, force: bool = False) -> bool:
        """
        Install RAG dependencies if missing.

        Args:
            force: Force reinstall even if already installed

        Returns:
            True if installation succeeded or was skipped
        """
        logger.info("Checking RAG dependencies...")

        requirements_file = self.rag_dir / "rag_requirements.txt"
        if not requirements_file.exists():
            logger.warning(f"Requirements file not found: {requirements_file}")
            self.status["errors"].append("rag_requirements.txt not found")
            return False

        deps = self.check_dependencies()
        missing = [name for name, installed in deps.items() if not installed]

        if not missing and not force:
            logger.info("All dependencies already installed")
            self.status["steps_completed"].append("dependencies_checked")
            return True

        logger.info(f"Installing dependencies: {missing or 'all (forced)'}")

        try:
            # Use pip to install requirements
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-r", str(requirements_file), "-q"],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                logger.info("Dependencies installed successfully")
                self.status["steps_completed"].append("dependencies_installed")
                return True
            else:
                logger.error(f"Dependency installation failed: {result.stderr}")
                self.status["errors"].append(f"pip install failed: {result.stderr}")
                self.status["steps_failed"].append("dependencies_installed")
                return False

        except subprocess.TimeoutExpired:
            logger.error("Dependency installation timed out")
            self.status["errors"].append("pip install timed out")
            self.status["steps_failed"].append("dependencies_installed")
            return False
        except Exception as e:
            logger.error(f"Dependency installation error: {e}")
            self.status["errors"].append(str(e))
            self.status["steps_failed"].append("dependencies_installed")
            return False

    def detect_project_type(self) -> str:
        """
        Detect the type of project for smart indexing.

        Returns:
            Project type string
        """
        logger.info("Detecting project type...")

        # Check for Java/Spring Boot
        if (self.project_root / "pom.xml").exists():
            if self._file_contains("pom.xml", "spring-boot"):
                self.status["project_type"] = "java_spring_boot"
                return "java_spring_boot"
            return "java_maven"

        if (self.project_root / "build.gradle").exists():
            if self._file_contains("build.gradle", "spring"):
                self.status["project_type"] = "java_spring_boot"
                return "java_spring_boot"
            return "java_gradle"

        # Check for Python
        if (self.project_root / "requirements.txt").exists():
            if self._file_contains("requirements.txt", "fastapi"):
                self.status["project_type"] = "python_fastapi"
                return "python_fastapi"
            if self._file_contains("requirements.txt", "django"):
                self.status["project_type"] = "python_django"
                return "python_django"
            if self._file_contains("requirements.txt", "flask"):
                self.status["project_type"] = "python_flask"
                return "python_flask"
            self.status["project_type"] = "python"
            return "python"

        # Check for Node.js
        if (self.project_root / "package.json").exists():
            if self._file_contains("package.json", "react"):
                self.status["project_type"] = "node_react"
                return "node_react"
            if self._file_contains("package.json", "next"):
                self.status["project_type"] = "node_nextjs"
                return "node_nextjs"
            if self._file_contains("package.json", "express"):
                self.status["project_type"] = "node_express"
                return "node_express"
            self.status["project_type"] = "node"
            return "node"

        self.status["project_type"] = "generic"
        return "generic"

    def _file_contains(self, filename: str, search_string: str) -> bool:
        """Check if a file contains a string."""
        filepath = self.project_root / filename
        if not filepath.exists():
            return False
        try:
            content = filepath.read_text(encoding='utf-8', errors='ignore')
            return search_string.lower() in content.lower()
        except Exception:
            return False

    def index_project(self) -> bool:
        """
        Index the project codebase for RAG.

        Returns:
            True if indexing succeeded
        """
        logger.info("Indexing project for RAG...")

        try:
            # Import RAG components
            sys.path.insert(0, str(self.rag_dir))

            from adaptive_rag import AdaptiveRAGEngine

            # Create RAG engine
            engine = AdaptiveRAGEngine(str(self.project_root))

            # Index the project
            stats = engine.index_project()

            self.status["rag_indexed"] = True
            self.status["files_indexed"] = stats.get("files_indexed", 0) if stats else 0
            self.status["chunks_indexed"] = stats.get("chunks_indexed", 0) if stats else 0
            self.status["steps_completed"].append("rag_indexed")

            files_count = stats.get('files_indexed', 0) if stats else 0
            chunks_count = stats.get('chunks_indexed', 0) if stats else 0
            logger.info(f"RAG indexing complete: {files_count} files, {chunks_count} chunks indexed")
            return True

        except ImportError as e:
            logger.warning(f"RAG components not available: {e}")
            self.status["errors"].append(f"RAG import failed: {e}")
            self.status["steps_failed"].append("rag_indexed")
            return False
        except Exception as e:
            logger.error(f"RAG indexing failed: {e}")
            self.status["errors"].append(f"RAG indexing failed: {e}")
            self.status["steps_failed"].append("rag_indexed")
            return False

    def run_conventions_analyzer(self) -> bool:
        """
        Run the conventions analyzer to learn project patterns.

        Returns:
            True if analysis succeeded
        """
        logger.info("Analyzing project conventions...")

        try:
            # Import conventions analyzer
            sys.path.insert(0, str(self.rag_dir))

            from conventions_analyzer import ConventionsAnalyzer

            analyzer = ConventionsAnalyzer(str(self.project_root))
            conventions = analyzer.analyze()

            # Save conventions - convert to dict first since ProjectConventions is a dataclass
            conventions_file = self.github_dir / "PROJECT_CONVENTIONS.json"
            with open(conventions_file, 'w') as f:
                conventions_dict = conventions.to_dict() if hasattr(conventions, 'to_dict') else conventions
                json.dump(conventions_dict, f, indent=2)

            self.status["conventions_analyzed"] = True
            self.status["steps_completed"].append("conventions_analyzed")

            logger.info("Conventions analysis complete")
            return True

        except ImportError as e:
            logger.warning(f"Conventions analyzer not available: {e}")
            # This is optional, don't mark as failed
            return True
        except Exception as e:
            logger.error(f"Conventions analysis failed: {e}")
            self.status["errors"].append(f"Conventions analysis failed: {e}")
            # Optional component, don't mark as critical failure
            return True

    def run_project_wizard(self, interactive: bool = False) -> bool:
        """
        Run the project wizard to customize templates.

        Args:
            interactive: Whether to run in interactive mode

        Returns:
            True if wizard completed
        """
        if not interactive:
            logger.info("Skipping interactive project wizard (non-interactive mode)")
            self.status["steps_completed"].append("project_wizard_skipped")
            return True

        logger.info("Running project wizard...")

        try:
            sys.path.insert(0, str(self.rag_dir))

            from project_wizard import ProjectWizard

            wizard = ProjectWizard(str(self.project_root))
            wizard.run()

            self.status["steps_completed"].append("project_wizard")
            return True

        except ImportError:
            logger.info("Project wizard not available")
            return True
        except Exception as e:
            logger.error(f"Project wizard failed: {e}")
            self.status["errors"].append(f"Project wizard failed: {e}")
            return True  # Not critical

    def save_status(self) -> None:
        """Save the initialization status to file."""
        self.status["timestamp"] = datetime.now().isoformat()
        self.status["version"] = "2.2.0"
        self.status["initialized"] = len(self.status["steps_failed"]) == 0

        try:
            with open(self.status_file, 'w') as f:
                json.dump(self.status, f, indent=2)
            logger.info(f"Status saved to {self.status_file}")
        except Exception as e:
            logger.error(f"Failed to save status: {e}")

    def create_marker(self) -> None:
        """Create the initialization marker file."""
        try:
            self.marker_file.write_text(
                f"Initialized: {datetime.now().isoformat()}\n"
                f"Version: 2.2.0\n"
            )
            logger.info("Initialization marker created")
        except Exception as e:
            logger.error(f"Failed to create marker: {e}")

    def run(self, force: bool = False, interactive: bool = False) -> Dict[str, Any]:
        """
        Run the full bootstrap process.

        Args:
            force: Force reinitialization even if already done
            interactive: Run in interactive mode (for wizards)

        Returns:
            Status dictionary with results
        """
        logger.info("=" * 60)
        logger.info("Universal Context Template - Bootstrap Orchestrator")
        logger.info("=" * 60)

        # Check if already initialized
        if self.is_initialized() and not force:
            if not self.should_reinitialize():
                logger.info("Project already initialized. Use force=True to reinitialize.")
                return {"status": "already_initialized", "marker": str(self.marker_file)}

        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Claude dir: {self.github_dir}")

        # Step 1: Detect project type
        project_type = self.detect_project_type()
        logger.info(f"Detected project type: {project_type}")

        # Step 2: Install dependencies
        deps_ok = self.install_dependencies(force=force)

        # Step 3: Index project (only if deps installed)
        if deps_ok:
            self.index_project()

        # Step 4: Run conventions analyzer
        if deps_ok:
            self.run_conventions_analyzer()

        # Step 5: Run project wizard (if interactive)
        self.run_project_wizard(interactive=interactive)

        # Step 6: Save status and create marker
        self.save_status()

        if len(self.status["steps_failed"]) == 0:
            self.create_marker()
            logger.info("=" * 60)
            logger.info("BOOTSTRAP COMPLETE - Project initialized successfully!")
            logger.info("=" * 60)
        else:
            logger.warning("=" * 60)
            logger.warning("BOOTSTRAP PARTIAL - Some steps failed")
            logger.warning(f"Failed: {self.status['steps_failed']}")
            logger.warning("=" * 60)

        return self.status


def main():
    """CLI entry point for bootstrap."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Universal Context Template Bootstrap Orchestrator"
    )
    parser.add_argument(
        "--project-root", "-p",
        default=os.getcwd(),
        help="Project root directory (default: current directory)"
    )
    parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force reinitialization even if already done"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Run in interactive mode (enables wizards)"
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Only check initialization status, don't run"
    )

    args = parser.parse_args()

    orchestrator = BootstrapOrchestrator(args.project_root)

    if args.check_only:
        if orchestrator.is_initialized():
            print("[OK] Project is initialized")
            if orchestrator.status_file.exists():
                with open(orchestrator.status_file, 'r') as f:
                    status = json.load(f)
                print(json.dumps(status, indent=2))
            sys.exit(0)
        else:
            print("[X] Project is NOT initialized")
            sys.exit(1)

    status = orchestrator.run(force=args.force, interactive=args.interactive)

    if status.get("initialized") or status.get("status") == "already_initialized":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
