"""
Index Knowledge Documents into ICDA RAG System
Run with: python index_knowledge.py

Requires ICDA server to be running at http://localhost:8000
"""

import requests
from pathlib import Path

BASE_URL = "http://localhost:8000"
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"


def index_file(filepath: Path, category: str = "general", tags: list = None):
    """Index a single file into the knowledge base."""
    url = f"{BASE_URL}/api/knowledge/upload"
    
    with open(filepath, "rb") as f:
        files = {"file": (filepath.name, f, "text/markdown")}
        data = {
            "category": category,
            "tags": ",".join(tags) if tags else ""
        }
        
        response = requests.post(url, files=files, data=data)
    
    if response.status_code == 200:
        result = response.json()
        if result.get("success"):
            print(f"✓ Indexed: {filepath.name}")
            print(f"  Doc ID: {result.get('doc_id')}")
            print(f"  Chunks: {result.get('chunks_indexed')}")
            print(f"  Category: {result.get('category')}")
            print(f"  Tags: {result.get('tags')}")
            return True
        else:
            print(f"✗ Failed: {filepath.name} - {result.get('error')}")
    else:
        print(f"✗ HTTP Error {response.status_code}: {filepath.name}")
    
    return False


def check_health():
    """Check if ICDA server is running."""
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False


def get_stats():
    """Get current knowledge base stats."""
    response = requests.get(f"{BASE_URL}/api/knowledge/stats")
    return response.json() if response.status_code == 200 else None


def main():
    # Check server health
    if not check_health():
        print("ERROR: ICDA server not running at", BASE_URL)
        print("Start with: uvicorn main:app --reload --port 8000")
        return
    
    print("Connected to ICDA server")
    
    # Show current stats
    stats = get_stats()
    if stats and stats.get("available"):
        print(f"Current knowledge base: {stats.get('unique_documents', 0)} docs, {stats.get('total_chunks', 0)} chunks")
    
    print("\nIndexing knowledge documents...")
    print("-" * 50)
    
    # Define documents to index with their metadata
    documents = [
        {
            "file": "puerto-rico-urbanization-addressing.md",
            "category": "address-standards",
            "tags": ["puerto-rico", "urbanization", "usps", "addressing", "zip-codes", "postal"]
        },
        # Add more documents here as needed:
        # {
        #     "file": "another-document.md",
        #     "category": "api-design",
        #     "tags": ["api", "rest", "architecture"]
        # },
    ]
    
    indexed = 0
    failed = 0
    
    for doc in documents:
        filepath = KNOWLEDGE_DIR / doc["file"]
        if filepath.exists():
            if index_file(filepath, doc["category"], doc["tags"]):
                indexed += 1
            else:
                failed += 1
        else:
            print(f"✗ Not found: {filepath}")
            failed += 1
    
    print("-" * 50)
    print(f"Complete: {indexed} indexed, {failed} failed")
    
    # Show updated stats
    stats = get_stats()
    if stats and stats.get("available"):
        print(f"\nKnowledge base now has: {stats.get('unique_documents', 0)} docs, {stats.get('total_chunks', 0)} chunks")
        
        if stats.get("categories"):
            print(f"Categories: {stats['categories']}")


if __name__ == "__main__":
    main()
