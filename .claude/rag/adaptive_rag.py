"""
Adaptive RAG System - Kubernetes-like Auto-Configuration
Automatically detects environment and configures itself accordingly.

Supports:
- AWS Bedrock (Claude API)
- GitHub Copilot (Claude via Copilot)
- Docker AI Agents
- Claude Code (MCP)
- Standalone REST API

No external accounts required - runs entirely local with ChromaDB.
"""

import os
import sys
import json
import subprocess
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from pathlib import Path
from enum import Enum
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InterfaceType(Enum):
    """Detected interface types"""
    BEDROCK = "bedrock"           # AWS Bedrock Claude API
    COPILOT = "copilot"           # GitHub Copilot
    DOCKER_AGENT = "docker_agent" # Docker AI Agent
    CLAUDE_CODE = "claude_code"   # Claude Code CLI with MCP
    REST_API = "rest_api"         # Standalone REST API
    STDIN = "stdin"               # Command line / pipe
    UNKNOWN = "unknown"


class ProjectType(Enum):
    """Detected project types for smart indexing"""
    JAVA_SPRING = "java_spring"
    JAVA_MAVEN = "java_maven"
    JAVA_GRADLE = "java_gradle"
    PYTHON_FASTAPI = "python_fastapi"
    PYTHON_DJANGO = "python_django"
    PYTHON_FLASK = "python_flask"
    NODE_EXPRESS = "node_express"
    NODE_REACT = "node_react"
    NODE_NEXTJS = "node_nextjs"
    DOTNET = "dotnet"
    GO = "go"
    RUST = "rust"
    GENERIC = "generic"


@dataclass
class EnvironmentContext:
    """
    Detected environment context - like Kubernetes pod context
    """
    interface: InterfaceType
    project_type: ProjectType
    project_root: str

    # Detected features
    has_docker: bool = False
    has_kubernetes: bool = False
    has_aws: bool = False
    has_azure: bool = False
    has_gcp: bool = False

    # Security context
    is_fedramp: bool = False
    is_air_gapped: bool = False

    # Detected files
    config_files: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "interface": self.interface.value,
            "project_type": self.project_type.value,
            "project_root": self.project_root,
            "has_docker": self.has_docker,
            "has_kubernetes": self.has_kubernetes,
            "has_aws": self.has_aws,
            "has_azure": self.has_azure,
            "has_gcp": self.has_gcp,
            "is_fedramp": self.is_fedramp,
            "is_air_gapped": self.is_air_gapped,
            "config_files": self.config_files
        }


class EnvironmentDetector:
    """
    Detects the runtime environment - like Kubernetes service discovery
    """

    @staticmethod
    def detect_interface() -> InterfaceType:
        """Detect which Claude interface is being used"""

        # Check for Claude Code MCP
        if os.getenv("CLAUDE_CODE") or os.getenv("MCP_SERVER"):
            return InterfaceType.CLAUDE_CODE

        # Check for AWS Bedrock
        if os.getenv("AWS_BEDROCK_RUNTIME") or os.getenv("AWS_REGION"):
            if EnvironmentDetector._check_bedrock_available():
                return InterfaceType.BEDROCK

        # Check for GitHub Copilot environment
        if os.getenv("GITHUB_COPILOT") or os.getenv("COPILOT_AGENT"):
            return InterfaceType.COPILOT

        # Check for Docker AI Agent
        if os.getenv("DOCKER_AI_AGENT") or Path("/.dockerenv").exists():
            return InterfaceType.DOCKER_AGENT

        # Check if running as REST API
        if os.getenv("RAG_REST_API") or os.getenv("FLASK_APP") or os.getenv("FASTAPI_APP"):
            return InterfaceType.REST_API

        # Check if stdin has data (pipe)
        if not sys.stdin.isatty():
            return InterfaceType.STDIN

        return InterfaceType.UNKNOWN

    @staticmethod
    def _check_bedrock_available() -> bool:
        """Check if AWS Bedrock is accessible"""
        try:
            import boto3
            client = boto3.client('bedrock-runtime')
            return True
        except Exception:
            return False

    @staticmethod
    def detect_project_type(project_root: str) -> ProjectType:
        """Detect project type from file structure"""
        root = Path(project_root)

        # Java Spring Boot
        if (root / "pom.xml").exists():
            pom_content = (root / "pom.xml").read_text()
            if "spring-boot" in pom_content:
                return ProjectType.JAVA_SPRING
            return ProjectType.JAVA_MAVEN

        if (root / "build.gradle").exists() or (root / "build.gradle.kts").exists():
            gradle_content = ""
            if (root / "build.gradle").exists():
                gradle_content = (root / "build.gradle").read_text()
            elif (root / "build.gradle.kts").exists():
                gradle_content = (root / "build.gradle.kts").read_text()
            if "spring" in gradle_content.lower():
                return ProjectType.JAVA_SPRING
            return ProjectType.JAVA_GRADLE

        # Python
        if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
            req_content = ""
            if (root / "requirements.txt").exists():
                req_content = (root / "requirements.txt").read_text().lower()
            if (root / "pyproject.toml").exists():
                req_content += (root / "pyproject.toml").read_text().lower()

            if "fastapi" in req_content:
                return ProjectType.PYTHON_FASTAPI
            if "django" in req_content:
                return ProjectType.PYTHON_DJANGO
            if "flask" in req_content:
                return ProjectType.PYTHON_FLASK

        # Node.js
        if (root / "package.json").exists():
            pkg_content = (root / "package.json").read_text().lower()
            if "next" in pkg_content:
                return ProjectType.NODE_NEXTJS
            if "react" in pkg_content:
                return ProjectType.NODE_REACT
            if "express" in pkg_content:
                return ProjectType.NODE_EXPRESS

        # .NET
        if list(root.glob("*.csproj")) or list(root.glob("*.sln")):
            return ProjectType.DOTNET

        # Go
        if (root / "go.mod").exists():
            return ProjectType.GO

        # Rust
        if (root / "Cargo.toml").exists():
            return ProjectType.RUST

        return ProjectType.GENERIC

    @staticmethod
    def detect_full_context(project_root: str) -> EnvironmentContext:
        """Detect full environment context"""
        root = Path(project_root)

        interface = EnvironmentDetector.detect_interface()
        project_type = EnvironmentDetector.detect_project_type(project_root)

        # Detect infrastructure
        has_docker = (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()
        has_kubernetes = (root / "kubernetes").exists() or list(root.glob("**/*.yaml"))

        # Detect cloud providers
        has_aws = (root / ".aws").exists() or os.getenv("AWS_REGION") is not None
        has_azure = (root / ".azure").exists() or os.getenv("AZURE_SUBSCRIPTION_ID") is not None
        has_gcp = (root / ".gcloud").exists() or os.getenv("GOOGLE_CLOUD_PROJECT") is not None

        # Security context
        is_fedramp = os.getenv("FEDRAMP_ENVIRONMENT") == "true" or (root / "SECURITY_COMPLIANCE.md").exists()
        is_air_gapped = os.getenv("AIR_GAPPED") == "true" or not EnvironmentDetector._check_internet()

        # Collect config files
        config_files = []
        for pattern in ["*.yml", "*.yaml", "*.json", "*.toml", "*.ini", "*.env*"]:
            config_files.extend([str(f.relative_to(root)) for f in root.glob(pattern)])

        return EnvironmentContext(
            interface=interface,
            project_type=project_type,
            project_root=str(root.absolute()),
            has_docker=has_docker,
            has_kubernetes=bool(has_kubernetes),
            has_aws=has_aws,
            has_azure=has_azure,
            has_gcp=has_gcp,
            is_fedramp=is_fedramp,
            is_air_gapped=is_air_gapped,
            config_files=config_files[:20]  # Limit to 20
        )

    @staticmethod
    def _check_internet() -> bool:
        """Check if internet is available"""
        try:
            import socket
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False


class InterfaceAdapter(ABC):
    """
    Base class for interface adapters - like Kubernetes ingress controllers
    Each adapter knows how to serve RAG results to its target interface
    """

    @abstractmethod
    def serve(self, rag_engine: 'AdaptiveRAGEngine'):
        """Start serving RAG results via this interface"""
        pass

    @abstractmethod
    def query(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Query the RAG system"""
        pass


class RESTAdapter(InterfaceAdapter):
    """REST API adapter using FastAPI"""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080):
        self.host = host
        self.port = port
        self.rag_engine = None

    def serve(self, rag_engine: 'AdaptiveRAGEngine'):
        """Start FastAPI server"""
        self.rag_engine = rag_engine

        try:
            from fastapi import FastAPI, HTTPException
            from pydantic import BaseModel
            import uvicorn
        except ImportError:
            logger.error("FastAPI not installed. Run: pip install fastapi uvicorn")
            return

        app = FastAPI(
            title="Adaptive RAG API",
            description="Self-configuring RAG system for code search",
            version="1.0.0"
        )

        class QueryRequest(BaseModel):
            query: str
            n_results: int = 5
            filters: Optional[Dict[str, Any]] = None

        class IndexRequest(BaseModel):
            force_reindex: bool = False

        @app.get("/health")
        def health():
            return {"status": "healthy", "context": rag_engine.context.to_dict()}

        @app.post("/query")
        def query(request: QueryRequest):
            try:
                results = rag_engine.query(
                    request.query,
                    n_results=request.n_results,
                    filters=request.filters
                )
                return results
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.post("/index")
        def index(request: IndexRequest):
            try:
                rag_engine.index_project(force_reindex=request.force_reindex)
                return {"status": "indexed", "stats": rag_engine.get_stats()}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @app.get("/stats")
        def stats():
            return rag_engine.get_stats()

        @app.get("/context")
        def context():
            return rag_engine.context.to_dict()

        logger.info(f"Starting REST API on {self.host}:{self.port}")
        uvicorn.run(app, host=self.host, port=self.port)

    def query(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Query via REST (for client use)"""
        import requests
        response = requests.post(
            f"http://{self.host}:{self.port}/query",
            json={"query": query, "n_results": n_results}
        )
        return response.json()


class STDINAdapter(InterfaceAdapter):
    """STDIN/STDOUT adapter for CLI and pipe usage"""

    def __init__(self):
        self.rag_engine = None

    def serve(self, rag_engine: 'AdaptiveRAGEngine'):
        """Read queries from stdin, output results to stdout"""
        self.rag_engine = rag_engine

        logger.info("RAG Engine ready. Enter queries (JSON format) or plain text:")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                # Try JSON input
                try:
                    request = json.loads(line)
                    query = request.get("query", line)
                    n_results = request.get("n_results", 5)
                except json.JSONDecodeError:
                    query = line
                    n_results = 5

                results = rag_engine.query(query, n_results=n_results)
                print(json.dumps(results, indent=2))
                sys.stdout.flush()

            except Exception as e:
                print(json.dumps({"error": str(e)}))
                sys.stdout.flush()

    def query(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Query the RAG system"""
        return self.rag_engine.query(query, n_results)


class FileInjectAdapter(InterfaceAdapter):
    """
    File injection adapter for GitHub Copilot and similar tools.
    Writes context to files that Copilot can read.
    """

    def __init__(self, output_dir: str = ".claude/context"):
        self.output_dir = Path(output_dir)
        self.rag_engine = None

    def serve(self, rag_engine: 'AdaptiveRAGEngine'):
        """Write context files for Copilot to discover"""
        self.rag_engine = rag_engine
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Write project context file
        context_file = self.output_dir / "PROJECT_CONTEXT.md"
        context_content = self._generate_context_markdown()
        context_file.write_text(context_content)

        logger.info(f"Context written to {context_file}")
        logger.info("Copilot will discover this context automatically")

    def _generate_context_markdown(self) -> str:
        """Generate markdown context for Copilot"""
        ctx = self.rag_engine.context
        stats = self.rag_engine.get_stats()

        return f"""# Project Context (Auto-Generated)

## Environment
- **Project Type**: {ctx.project_type.value}
- **Interface**: {ctx.interface.value}
- **Project Root**: {ctx.project_root}

## Infrastructure
- Docker: {'Yes' if ctx.has_docker else 'No'}
- Kubernetes: {'Yes' if ctx.has_kubernetes else 'No'}
- AWS: {'Yes' if ctx.has_aws else 'No'}
- Azure: {'Yes' if ctx.has_azure else 'No'}
- GCP: {'Yes' if ctx.has_gcp else 'No'}

## Security
- FedRAMP: {'Yes' if ctx.is_fedramp else 'No'}
- Air-Gapped: {'Yes' if ctx.is_air_gapped else 'No'}

## RAG Statistics
- Total Indexed Chunks: {stats.get('total_documents', 0)}
- Provider: {stats.get('provider', 'Unknown')}

## Configuration Files
{chr(10).join('- ' + f for f in ctx.config_files)}

---
*This file is auto-generated by the Adaptive RAG System*
"""

    def query(self, query: str, n_results: int = 5) -> Dict[str, Any]:
        """Query and write results to file"""
        results = self.rag_engine.query(query, n_results)

        # Write results to file for Copilot
        results_file = self.output_dir / "QUERY_RESULTS.md"
        results_content = self._format_results_markdown(query, results)
        results_file.write_text(results_content)

        return results

    def _format_results_markdown(self, query: str, results: Dict) -> str:
        """Format results as markdown"""
        content = f"# Query Results\n\n**Query**: {query}\n\n"

        for i, result in enumerate(results.get("results", []), 1):
            content += f"## Result {i}\n"
            content += f"- **File**: {result.get('metadata', {}).get('file_path', 'Unknown')}\n"
            content += f"- **Type**: {result.get('metadata', {}).get('chunk_type', 'Unknown')}\n"
            content += f"- **Similarity**: {result.get('similarity_score', 0):.2f}\n\n"
            content += "```\n"
            content += result.get("content", "")[:500]
            content += "\n```\n\n"

        return content


class AdaptiveRAGEngine:
    """
    The main adaptive RAG engine - like Kubernetes controller
    Auto-configures based on detected environment
    """

    def __init__(self, project_root: str = "."):
        """
        Initialize the adaptive RAG engine

        Args:
            project_root: Root directory of the project to index
        """
        self.project_root = Path(project_root).absolute()
        self.context = EnvironmentDetector.detect_full_context(str(self.project_root))

        # Initialize vector database (ChromaDB - local, no accounts)
        # Use absolute imports to support both package and direct script execution
        try:
            from .vector_database import ChromaVectorDatabase
            from .chunking_strategy import UniversalChunkingStrategy
        except ImportError:
            from vector_database import ChromaVectorDatabase
            from chunking_strategy import UniversalChunkingStrategy

        self.vector_db = ChromaVectorDatabase(
            persist_directory=str(self.project_root / ".claude" / "rag" / "chroma_db")
        )
        self.chunker = UniversalChunkingStrategy(str(self.project_root))

        # Select appropriate adapter based on detected interface
        self.adapter = self._select_adapter()

        logger.info(f"Adaptive RAG initialized")
        logger.info(f"  Interface: {self.context.interface.value}")
        logger.info(f"  Project Type: {self.context.project_type.value}")
        logger.info(f"  Adapter: {type(self.adapter).__name__}")

    def _select_adapter(self) -> InterfaceAdapter:
        """Select the appropriate adapter based on environment"""
        interface = self.context.interface

        if interface == InterfaceType.REST_API:
            return RESTAdapter()
        elif interface == InterfaceType.COPILOT:
            return FileInjectAdapter()
        elif interface == InterfaceType.STDIN:
            return STDINAdapter()
        elif interface == InterfaceType.DOCKER_AGENT:
            # Docker agents can use REST or STDIN
            if os.getenv("RAG_REST_API"):
                return RESTAdapter()
            return STDINAdapter()
        elif interface == InterfaceType.BEDROCK:
            # Bedrock uses REST API
            return RESTAdapter()
        elif interface == InterfaceType.CLAUDE_CODE:
            # Claude Code uses file injection + STDIN
            return FileInjectAdapter()
        else:
            # Default to REST API
            return RESTAdapter()

    def index_project(self, force_reindex: bool = False, analyze_conventions: bool = True) -> Dict[str, Any]:
        """
        Index the project codebase

        Args:
            force_reindex: Force re-indexing even if already indexed
            analyze_conventions: Analyze and save coding conventions

        Returns:
            Dict with indexing stats including files_indexed, chunks_indexed
        """
        stats = self.vector_db.get_stats()

        if not force_reindex and stats.get('total_documents', 0) > 0:
            logger.info(f"Project already indexed ({stats['total_documents']} chunks)")
            return {"files_indexed": 0, "chunks_indexed": stats['total_documents'], "status": "already_indexed"}

        if force_reindex:
            logger.info("Force re-indexing...")
            self.vector_db.clear_database()

        # Analyze coding conventions first
        if analyze_conventions:
            self._analyze_and_save_conventions()

        logger.info(f"Indexing project: {self.project_root}")
        chunks = self.chunker.chunk_project()

        if chunks:
            self.vector_db.add_chunks(chunks)
            logger.info(f"Indexed {len(chunks)} chunks")
            return {"files_indexed": len(set(c.file_path for c in chunks)), "chunks_indexed": len(chunks), "status": "indexed"}
        else:
            logger.warning("No chunks found to index")
            return {"files_indexed": 0, "chunks_indexed": 0, "status": "no_chunks"}

    def _analyze_and_save_conventions(self):
        """Analyze coding conventions and save to file"""
        try:
            try:
                from .conventions_analyzer import ConventionsAnalyzer, save_conventions
            except ImportError:
                from conventions_analyzer import ConventionsAnalyzer, save_conventions

            logger.info("Analyzing coding conventions...")
            analyzer = ConventionsAnalyzer(str(self.project_root))
            conventions = analyzer.analyze()

            # Save conventions file
            conventions_file = self.project_root / ".claude" / "CONVENTIONS.md"
            conventions_file.parent.mkdir(parents=True, exist_ok=True)
            save_conventions(conventions, str(conventions_file))

            logger.info(f"Conventions saved to {conventions_file}")
            logger.info(f"  Language: {conventions.language}")
            logger.info(f"  Frameworks: {', '.join(conventions.frameworks) or 'None detected'}")
            logger.info(f"  Rules detected: {len(conventions.rules)}")

            # Store conventions in context
            self._conventions = conventions

        except Exception as e:
            logger.warning(f"Could not analyze conventions: {e}")
            self._conventions = None

    def query(
        self,
        query: str,
        n_results: int = 5,
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Query the RAG system

        Args:
            query: Search query
            n_results: Number of results to return
            filters: Optional metadata filters

        Returns:
            Dictionary with query results
        """
        results = self.vector_db.search(query, n_results, filters)

        # Add context to results
        results["context"] = {
            "project_type": self.context.project_type.value,
            "interface": self.context.interface.value
        }

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get RAG system statistics"""
        db_stats = self.vector_db.get_stats()
        return {
            **db_stats,
            "project_root": str(self.project_root),
            "project_type": self.context.project_type.value,
            "interface": self.context.interface.value
        }

    def serve(self):
        """Start serving via the selected adapter"""
        # Auto-index if not already indexed
        self.index_project()

        # Start adapter
        self.adapter.serve(self)

    def get_context_for_prompt(self, query: str, n_results: int = 3) -> str:
        """
        Get context formatted for injection into an LLM prompt.
        Useful for Bedrock/Copilot integration.

        Args:
            query: The user's query
            n_results: Number of relevant chunks to include

        Returns:
            Formatted context string for prompt injection
        """
        results = self.query(query, n_results)

        context_parts = [
            f"# Relevant Code Context for: {query}\n",
            f"Project Type: {self.context.project_type.value}\n",
            "---\n"
        ]

        for i, result in enumerate(results.get("results", []), 1):
            metadata = result.get("metadata", {})
            context_parts.append(f"\n## [{i}] {metadata.get('file_path', 'Unknown')}")
            context_parts.append(f"Type: {metadata.get('chunk_type', 'Unknown')}")
            context_parts.append(f"Lines: {metadata.get('start_line', '?')}-{metadata.get('end_line', '?')}")
            context_parts.append(f"\n```\n{result.get('content', '')}\n```\n")

        return "\n".join(context_parts)


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Adaptive RAG System")
    parser.add_argument("--project", "-p", default=".", help="Project root directory")
    parser.add_argument("--index", "-i", action="store_true", help="Index/re-index project")
    parser.add_argument("--query", "-q", help="Query the RAG system")
    parser.add_argument("--serve", "-s", action="store_true", help="Start serving")
    parser.add_argument("--port", type=int, default=8080, help="REST API port")
    parser.add_argument("--adapter", choices=["rest", "stdin", "file"], help="Force adapter type")
    parser.add_argument("--wizard", "-w", action="store_true", help="Run project setup wizard")
    parser.add_argument("--wizard-config", help="JSON config file for non-interactive wizard")
    parser.add_argument("--conventions", "-c", action="store_true", help="Analyze and show conventions only")

    args = parser.parse_args()

    # Run wizard for new projects
    if args.wizard:
        from .project_wizard import run_wizard
        config = None
        if args.wizard_config:
            with open(args.wizard_config) as f:
                config = json.load(f)
        run_wizard(args.project, config)
        return

    # Analyze conventions only
    if args.conventions:
        from .conventions_analyzer import analyze_project
        conventions = analyze_project(args.project)
        print(conventions.to_markdown())
        return

    # Initialize engine
    engine = AdaptiveRAGEngine(args.project)

    # Override adapter if specified
    if args.adapter:
        if args.adapter == "rest":
            engine.adapter = RESTAdapter(port=args.port)
        elif args.adapter == "stdin":
            engine.adapter = STDINAdapter()
        elif args.adapter == "file":
            engine.adapter = FileInjectAdapter()

    # Handle commands
    if args.index:
        engine.index_project(force_reindex=True)
        print(json.dumps(engine.get_stats(), indent=2))

    elif args.query:
        results = engine.query(args.query)
        print(json.dumps(results, indent=2))

    elif args.serve:
        engine.serve()

    else:
        # Default: show status
        print("Adaptive RAG System")
        print("=" * 40)
        print(json.dumps(engine.context.to_dict(), indent=2))
        print("\nUsage:")
        print("  --wizard   Run project setup wizard (new projects)")
        print("  --index    Index the project (existing projects)")
        print("  --query    Query the RAG system")
        print("  --serve    Start serving")
        print("  --conventions  Analyze coding conventions")


if __name__ == "__main__":
    main()
