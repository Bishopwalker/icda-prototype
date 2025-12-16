#!/usr/bin/env python3
"""
RAG Pipeline - Master Controller for Complete RAG Indexing

This is the main entry point for the comprehensive RAG indexing system.
It orchestrates all components:
- RAG Orchestrator (chunking with 333/666/999 adaptive targets)
- Progress Display (visual feedback)
- AI Enforcer (quality validation with any AI provider)
- Specialized Agents (content analysis, quality, coverage, relationships)

Usage:
    python rag_pipeline.py                    # Index current directory
    python rag_pipeline.py --project /path    # Index specific project
    python rag_pipeline.py --enforce          # Run AI enforcer validation
    python rag_pipeline.py --full             # Full pipeline with all agents

Author: Universal Context Template
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import asdict
from typing import Dict, Any, Optional

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from rag_orchestrator import RAGOrchestrator, IndexManifest, IndexStats
from progress_display import RAGProgressCallback, ProgressDisplay
from rag_agents import RAGAgentSwarm, AgentReport


def load_chunk_content(manifest: Dict[str, Any], project_root: Path) -> Dict[str, str]:
    """Load actual chunk content from files."""
    chunks_content = {}

    for chunk in manifest.get('chunks', []):
        chunk_id = chunk.get('chunk_id', '')
        file_path = chunk.get('file_path', '')
        start_line = chunk.get('start_line', 1)
        end_line = chunk.get('end_line', -1)

        full_path = project_root / file_path
        if full_path.exists():
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()
                    if end_line > 0:
                        content = ''.join(lines[start_line-1:end_line])
                    else:
                        content = ''.join(lines[start_line-1:])
                    chunks_content[chunk_id] = content
            except Exception:
                chunks_content[chunk_id] = ""
        else:
            chunks_content[chunk_id] = ""

    return chunks_content


def run_pipeline(
    project_root: str,
    output_dir: Optional[str] = None,
    run_enforcer: bool = False,
    run_full: bool = False,
    validate_all: bool = False,
    quiet: bool = False
) -> Dict[str, Any]:
    """
    Run the complete RAG indexing pipeline.

    Args:
        project_root: Path to project to index
        output_dir: Output directory for manifests
        run_enforcer: Whether to run AI enforcer
        run_full: Run full pipeline with all agents
        validate_all: Validate all chunks (not just sample)
        quiet: Suppress progress output

    Returns:
        Pipeline results including manifest and reports
    """
    project_path = Path(project_root).resolve()

    # Setup progress display
    if quiet:
        progress = None
    else:
        progress = RAGProgressCallback()
        progress.show_header("RAG INDEXING PIPELINE")

    results = {
        'success': False,
        'project_root': str(project_path),
        'timestamp': datetime.now().isoformat(),
        'manifest_path': None,
        'stats': None,
        'enforcer_report': None,
        'agent_reports': None,
        'errors': []
    }

    try:
        # ================================================================
        # PHASE 1: Orchestration - Discovery and Chunking
        # ================================================================
        if progress:
            progress.on_phase_start("Initialization", 0)
            progress.on_progress(1, 1, "Creating orchestrator...")

        orchestrator = RAGOrchestrator(
            project_root=str(project_path),
            output_dir=output_dir,
            progress_callback=progress
        )

        if progress:
            progress.on_phase_complete("Initialization", {"status": "ready"})

        # Run orchestration
        manifest = orchestrator.run()

        # Convert to dict for further processing
        manifest_dict = {
            'version': manifest.version,
            'created_at': manifest.created_at,
            'project_root': manifest.project_root,
            'target_chunks': manifest.target_chunks,
            'actual_chunks': manifest.actual_chunks,
            'stats': asdict(manifest.stats) if manifest.stats else {},
            'categories': manifest.categories,
            'chunks': [asdict(c) for c in manifest.chunks],
            'quality_report': manifest.quality_report
        }

        results['stats'] = manifest_dict['stats']
        results['manifest_path'] = str(orchestrator.output_dir / "index_manifest.json")

        # Show chunk distribution
        if progress:
            progress.show_chunk_distribution(manifest_dict['stats'].get('chunks_by_category', {}))

        # ================================================================
        # PHASE 2: Agent Analysis
        # ================================================================
        if run_full or run_enforcer:
            if progress:
                progress.on_phase_start("Agent Analysis", 5)

            # Load chunk content
            chunks_content = load_chunk_content(manifest_dict, project_path)

            # Run agent swarm
            swarm = RAGAgentSwarm()
            agent_reports = swarm.analyze_all(
                manifest_dict,
                chunks_content,
                progress_callback=progress.on_progress if progress else None
            )

            results['agent_reports'] = {}
            for name, report in agent_reports.items():
                if hasattr(report, 'status'):
                    findings_list = []
                    if report.findings:
                        for f in report.findings:
                            if hasattr(f, '__dict__'):
                                findings_list.append(asdict(f))
                    results['agent_reports'][name] = {
                        'status': report.status,
                        'score': report.score,
                        'findings': findings_list,
                        'metrics': report.metrics,
                        'recommendations': report.recommendations
                    }

            combined_score = swarm.get_combined_score(agent_reports)

            if progress:
                progress.on_phase_complete("Agent Analysis", {
                    "combined_score": f"{combined_score:.2f}",
                    "agents_run": len(agent_reports)
                })

                # Show agent results
                print("\n  Agent Results:")
                for name, report in agent_reports.items():
                    status_color = "green" if report.status == "passed" else "yellow" if report.status == "warnings" else "red"
                    print(f"    {name}: {report.status} ({report.score:.2f})")

        # ================================================================
        # PHASE 3: AI Enforcer (Optional)
        # ================================================================
        if run_enforcer:
            try:
                from ai_enforcer import AIEnforcer

                if progress:
                    progress.on_phase_start("AI Enforcer", len(manifest_dict.get('chunks', [])))

                enforcer = AIEnforcer(validate_all=validate_all)

                # Load content if not already loaded
                if 'chunks_content' not in dir():
                    chunks_content = load_chunk_content(manifest_dict, project_path)

                enforcer_report = enforcer.validate_manifest(
                    manifest_dict,
                    chunks_content,
                    progress_callback=progress.on_progress if progress else None
                )

                # Apply improvements
                manifest_dict = enforcer.apply_improvements(manifest_dict, enforcer_report)

                results['enforcer_report'] = {
                    'timestamp': enforcer_report.timestamp,
                    'ai_provider': enforcer_report.ai_provider,
                    'overall_quality': enforcer_report.overall_quality,
                    'coverage_score': enforcer_report.coverage_score,
                    'approved_chunks': enforcer_report.approved_chunks,
                    'improved_chunks': enforcer_report.improved_chunks,
                    'flagged_chunks': enforcer_report.flagged_chunks,
                    'recommendations': enforcer_report.recommendations
                }

                if progress:
                    progress.on_phase_complete("AI Enforcer", {
                        "provider": enforcer_report.ai_provider,
                        "quality": f"{enforcer_report.overall_quality:.2f}",
                        "approved": enforcer_report.approved_chunks,
                        "flagged": enforcer_report.flagged_chunks
                    })

                # Save updated manifest
                with open(results['manifest_path'], 'w') as f:
                    json.dump(manifest_dict, f, indent=2, default=str)

            except ImportError:
                results['errors'].append("AI Enforcer not available (missing requests library)")
            except Exception as e:
                results['errors'].append(f"AI Enforcer error: {str(e)}")

        # ================================================================
        # FINAL: Summary
        # ================================================================
        results['success'] = True

        if progress:
            stats = results['stats']
            progress.show_stats({
                'Total Files': stats.get('total_files', 0),
                'Total Chunks': stats.get('total_chunks', 0),
                'Target Chunks': stats.get('target_chunks', 333),
                'Avg Chunk Size': f"{stats.get('avg_chunk_size', 0):.0f} chars",
                'Est. Tokens': f"{stats.get('total_tokens_estimate', 0):,}",
                'Duration': f"{stats.get('indexing_duration_ms', 0)}ms"
            })

            if results['enforcer_report']:
                progress.on_validation(
                    "AI Enforcer",
                    results['enforcer_report']['flagged_chunks'] == 0,
                    f"Quality: {results['enforcer_report']['overall_quality']:.2f}"
                )

            progress.show_completion(True, "RAG indexing completed successfully!")

    except Exception as e:
        results['success'] = False
        results['errors'].append(str(e))

        if progress:
            progress.show_completion(False, f"Pipeline failed: {str(e)}")

    return results


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="RAG Pipeline - Comprehensive RAG Indexing System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python rag_pipeline.py                     # Index current directory
  python rag_pipeline.py -p /path/to/project # Index specific project
  python rag_pipeline.py --enforce           # Run with AI quality validation
  python rag_pipeline.py --full              # Full pipeline with all agents
  python rag_pipeline.py --full --enforce    # Complete analysis
        """
    )

    parser.add_argument(
        "--project", "-p",
        default=".",
        help="Project root directory to index"
    )

    parser.add_argument(
        "--output", "-o",
        help="Output directory for manifests (default: .github/rag/index)"
    )

    parser.add_argument(
        "--enforce",
        action="store_true",
        help="Run AI enforcer for quality validation"
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Run full pipeline with all specialized agents"
    )

    parser.add_argument(
        "--validate-all",
        action="store_true",
        help="Validate all chunks (not just a sample) - slower"
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress progress output"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )

    args = parser.parse_args()

    # Run pipeline
    results = run_pipeline(
        project_root=args.project,
        output_dir=args.output,
        run_enforcer=args.enforce,
        run_full=args.full,
        validate_all=args.validate_all,
        quiet=args.quiet or args.json
    )

    # Output
    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        if not args.quiet:
            print(f"\nManifest saved to: {results['manifest_path']}")

            if results['errors']:
                print("\nErrors:")
                for error in results['errors']:
                    print(f"  - {error}")

    # Exit code
    sys.exit(0 if results['success'] else 1)


if __name__ == "__main__":
    main()
