"""
Index 50K customers into OpenSearch for semantic search.

Usage:
    python index_customers.py                    # Index all customers
    python index_customers.py --count            # Show current index count
    python index_customers.py --delete           # Delete and recreate index
    python index_customers.py --test             # Test search after indexing

Requires OPENSEARCH_HOST environment variable to be set.
"""
import asyncio
import argparse
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env BEFORE importing config
load_dotenv()

from icda.config import Config
from icda.embeddings import EmbeddingClient
from icda.vector_index import VectorIndex
from icda.database import CustomerDB

# Create fresh config after dotenv is loaded
cfg = Config()


async def show_count(vector_index: VectorIndex):
    """Show current indexed customer count"""
    count = await vector_index.customer_count()
    print(f"Indexed customers: {count:,}")
    return count


async def delete_index(vector_index: VectorIndex):
    """Delete the customer index"""
    print("Deleting customer index...")
    success = await vector_index.delete_customer_index()
    if success:
        print("Customer index deleted.")
    else:
        print("Failed to delete index.")
    return success


async def index_customers(vector_index: VectorIndex, customers: list[dict], batch_size: int = 50):
    """Index all customers with progress reporting"""
    total = len(customers)
    start_time = time.time()
    last_report = 0

    def progress(indexed: int, total: int):
        nonlocal last_report
        # Report every 500 or at completion
        if indexed - last_report >= 500 or indexed == total:
            elapsed = time.time() - start_time
            rate = indexed / elapsed if elapsed > 0 else 0
            eta = (total - indexed) / rate if rate > 0 else 0
            print(f"  Indexed {indexed:,}/{total:,} ({indexed/total*100:.1f}%) - {rate:.0f}/sec - ETA: {eta:.0f}s")
            last_report = indexed

    print(f"Indexing {total:,} customers into OpenSearch...")
    print(f"  Batch size: {batch_size}")
    print(f"  Index: {vector_index.customer_index}")
    print()

    result = await vector_index.index_customers(customers, batch_size=batch_size, progress_callback=progress)

    elapsed = time.time() - start_time
    print()
    print(f"Indexing complete!")
    print(f"  Indexed: {result['indexed']:,}")
    print(f"  Errors: {result['errors']:,}")
    print(f"  Time: {elapsed:.1f}s")
    print(f"  Rate: {result['indexed']/elapsed:.0f} customers/sec")

    return result


async def test_search(vector_index: VectorIndex):
    """Run test searches to verify indexing"""
    print("\nTesting semantic search...")

    test_queries = [
        ("customers in Las Vegas", None),
        ("high movers in California", {"state": "CA", "min_moves": 3}),
        ("business customers in Texas", {"state": "TX", "customer_type": "BUSINESS"}),
        ("123 Main Street", None),
        ("John Smith", None),
    ]

    for query, filters in test_queries:
        print(f"\nQuery: '{query}'" + (f" + filters: {filters}" if filters else ""))
        result = await vector_index.search_customers_semantic(query, limit=3, filters=filters)

        if result["success"]:
            print(f"  Found {result['count']} results:")
            for c in result["data"][:3]:
                print(f"    - {c['crid']}: {c['name']} ({c['city']}, {c['state']}) score={c['score']}")
        else:
            print(f"  Error: {result['error']}")

    # Test hybrid search
    print("\n\nTesting hybrid search (fuzzy + semantic)...")
    query = "mian street las vagas"  # Intentional typos
    result = await vector_index.search_customers_hybrid(query, limit=5)
    print(f"Query: '{query}' (with typos)")
    if result["success"]:
        print(f"  Found {result['count']} results:")
        for c in result["data"][:5]:
            print(f"    - {c['crid']}: {c['name']} @ {c['address']} ({c['city']}, {c['state']})")
    else:
        print(f"  Error: {result['error']}")


async def main():
    parser = argparse.ArgumentParser(description="Index customers into OpenSearch")
    parser.add_argument("--count", action="store_true", help="Show current index count")
    parser.add_argument("--delete", action="store_true", help="Delete the customer index")
    parser.add_argument("--test", action="store_true", help="Run test searches")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for indexing (default: 50)")
    parser.add_argument("--limit", type=int, help="Only index first N customers (for testing)")
    parser.add_argument("--force", action="store_true", help="Force delete and reindex without prompting")
    args = parser.parse_args()

    # Check OpenSearch config
    if not cfg.opensearch_host:
        print("ERROR: OPENSEARCH_HOST environment variable not set.")
        print()
        print("Set it in your .env file or environment:")
        print("  OPENSEARCH_HOST=your-domain.us-east-1.es.amazonaws.com")
        sys.exit(1)

    print(f"OpenSearch host: {cfg.opensearch_host}")
    print(f"AWS region: {cfg.aws_region}")
    print()

    # Initialize components
    embedder = EmbeddingClient(cfg.aws_region, cfg.titan_embed_model, cfg.embed_dimensions)
    vector_index = VectorIndex(embedder, cfg.opensearch_index)

    # Connect to OpenSearch
    await vector_index.connect(cfg.opensearch_host, cfg.aws_region)

    if not vector_index.available:
        print("ERROR: Could not connect to OpenSearch")
        sys.exit(1)

    print(f"Connected to OpenSearch")
    print()

    # Handle commands
    if args.count:
        await show_count(vector_index)

    elif args.delete:
        await delete_index(vector_index)

    elif args.test:
        count = await show_count(vector_index)
        if count == 0:
            print("No customers indexed. Run without --test to index first.")
        else:
            await test_search(vector_index)

    else:
        # Index customers
        db = CustomerDB(Path("customer_data.json"))
        customers = db.customers

        if args.limit:
            customers = customers[:args.limit]
            print(f"Limiting to first {args.limit} customers (--limit)")

        # Check if already indexed
        current_count = await vector_index.customer_count()
        if current_count > 0:
            print(f"Customer index already has {current_count:,} documents.")
            if args.force:
                print("Force flag set - deleting and reindexing...")
                await delete_index(vector_index)
            else:
                try:
                    response = input("Delete and reindex? (y/N): ").strip().lower()
                    if response == 'y':
                        await delete_index(vector_index)
                    else:
                        print("Aborted. Use --count to check status or --test to search.")
                        await vector_index.close()
                        return
                except EOFError:
                    print("Non-interactive mode. Use --force to delete and reindex.")
                    await vector_index.close()
                    return

        await index_customers(vector_index, customers, batch_size=args.batch_size)

        # Run quick test
        print("\n" + "=" * 60)
        await test_search(vector_index)

    await vector_index.close()


if __name__ == "__main__":
    asyncio.run(main())
