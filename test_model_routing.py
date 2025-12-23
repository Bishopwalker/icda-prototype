#!/usr/bin/env python3
"""Test script to verify Nova model routing (Micro → Lite → Pro).

Run with: python test_model_routing.py

Requires the ICDA server to be running on localhost:8000
"""

import asyncio
import httpx
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

# Test queries organized by expected routing tier
TEST_QUERIES = {
    "MICRO (Simple)": [
        "Show me customer CRID-00001",
        "Look up CRID-00042",
        "What is customer CRID-00010?",
    ],
    "LITE (Medium)": [
        "Show me customers in Nevada",
        "Find customers in California",
        "List apartment renters in Texas",
        "How many customers are in Florida?",
    ],
    "PRO (Complex)": [
        "Compare customers in California vs Texas who moved more than 3 times",
        "Show me a breakdown of customer types by state with move counts",
        "What's the average move count for residential customers? Also show apartment vs non-apartment breakdown",
        "Analyze the distribution of customers across all states and identify which states have the highest concentration of frequent movers",
        "1) Show California customers 2) Compare to Nevada 3) Which has more apartment renters?",
    ],
}


async def test_query(client: httpx.AsyncClient, query: str) -> dict:
    """Send a query and return routing info."""
    try:
        response = await client.post(
            "http://localhost:8000/api/query",
            json={"query": query, "bypass_cache": True},
            timeout=60.0,
        )
        data = response.json()
        
        # Extract routing info
        trace = data.get("trace", {})
        routing = trace.get("model_routing_decision", {}) if isinstance(trace, dict) else {}
        
        return {
            "success": data.get("success", False),
            "model_used": data.get("model_used", "unknown"),
            "model_tier": routing.get("model_tier", "unknown"),
            "routing_reason": routing.get("reason", "unknown"),
            "confidence": routing.get("confidence_factor", 0),
            "latency_ms": data.get("latency_ms", 0),
            "route": data.get("route", "unknown"),
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "model_used": "error",
            "model_tier": "error",
            "routing_reason": str(e),
            "confidence": 0,
            "latency_ms": 0,
        }


async def run_tests():
    """Run all test queries and display results."""
    console.print(Panel.fit(
        "[bold cyan]ICDA Model Routing Test[/bold cyan]\n"
        "Testing Micro → Lite → Pro routing based on query complexity",
        border_style="cyan"
    ))
    
    async with httpx.AsyncClient() as client:
        # Check server health first
        try:
            health = await client.get("http://localhost:8000/api/health", timeout=5.0)
            health_data = health.json()
            if health_data.get("mode") != "FULL":
                console.print("[yellow]⚠ Server is in LITE mode - AI routing won't work[/yellow]")
                return
            console.print(f"[green]✓ Server healthy in FULL mode[/green]\n")
        except Exception as e:
            console.print(f"[red]✗ Server not reachable: {e}[/red]")
            console.print("[yellow]Start server with: uvicorn main:app --reload --port 8000[/yellow]")
            return
        
        results = []
        
        for expected_tier, queries in TEST_QUERIES.items():
            console.print(f"\n[bold]{expected_tier}[/bold]")
            console.print("─" * 60)
            
            for query in queries:
                console.print(f"[dim]Testing: {query[:50]}...[/dim]")
                result = await test_query(client, query)
                result["query"] = query
                result["expected_tier"] = expected_tier.split()[0]  # MICRO, LITE, or PRO
                results.append(result)
                
                # Show inline result
                actual = result["model_tier"].upper() if result["model_tier"] != "unknown" else "?"
                expected = result["expected_tier"]
                match = "✓" if actual == expected else "✗"
                color = "green" if actual == expected else "red"
                
                console.print(
                    f"  [{color}]{match}[/{color}] "
                    f"Expected: {expected}, Got: [bold]{actual}[/bold] "
                    f"({result['latency_ms']}ms) - {result['routing_reason'][:40]}"
                )
        
        # Summary table
        console.print("\n")
        table = Table(title="Routing Results Summary")
        table.add_column("Query", style="dim", max_width=40)
        table.add_column("Expected", style="cyan")
        table.add_column("Actual", style="bold")
        table.add_column("Match", justify="center")
        table.add_column("Reason", max_width=30)
        table.add_column("Latency", justify="right")
        
        correct = 0
        total = len(results)
        
        for r in results:
            actual = r["model_tier"].upper() if r["model_tier"] != "unknown" else "?"
            expected = r["expected_tier"]
            match = actual == expected
            if match:
                correct += 1
            
            table.add_row(
                r["query"][:40] + "..." if len(r["query"]) > 40 else r["query"],
                expected,
                actual,
                "[green]✓[/green]" if match else "[red]✗[/red]",
                r["routing_reason"][:30],
                f"{r['latency_ms']}ms",
            )
        
        console.print(table)
        
        # Final score
        pct = (correct / total * 100) if total > 0 else 0
        color = "green" if pct >= 80 else "yellow" if pct >= 50 else "red"
        console.print(f"\n[{color}]Routing Accuracy: {correct}/{total} ({pct:.0f}%)[/{color}]")
        
        # Show routing thresholds
        console.print(Panel.fit(
            "[bold]Routing Triggers:[/bold]\n\n"
            "[cyan]→ PRO[/cyan] (Complex reasoning needed):\n"
            "  • complexity=COMPLEX\n"
            "  • intent=ANALYSIS, COMPARISON, RECOMMENDATION\n"
            "  • confidence < 0.6 (uncertain query)\n"
            "  • Multi-part queries (multiple ? or 'and also')\n"
            "  • SQL keywords: aggregate, join, group by, trend, breakdown\n\n"
            "[yellow]→ LITE[/yellow] (Medium complexity):\n"
            "  • complexity=MEDIUM\n"
            "  • Large result sets (>100 matches)\n\n"
            "[green]→ MICRO[/green] (Fast path):\n"
            "  • complexity=SIMPLE\n"
            "  • High confidence (≥0.6)\n"
            "  • Direct lookups, simple filters",
            title="Model Routing Logic",
            border_style="blue"
        ))


if __name__ == "__main__":
    asyncio.run(run_tests())
