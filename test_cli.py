"""Quick CLI test for ICDA prototype"""
import httpx
import json
import sys

BASE = "http://localhost:8000"

def test_query(query: str):
    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print('='*60)
    
    try:
        r = httpx.post(f"{BASE}/api/query", json={"query": query}, timeout=30)
        data = r.json()
        
        print(f"Status: {'✓ SUCCESS' if data['success'] else '✗ FAILED'}")
        print(f"Type: {data['query_type']}")
        print(f"Latency: {data['latency_ms']}ms")
        print(f"Cached: {data['cached']}")
        if data.get('tool_used'):
            print(f"Tool: {data['tool_used']}")
        if data.get('model'):
            print(f"Model: {data['model']}")
        print(f"\nRESPONSE:\n{data['response']}")
        
        if data.get('blocked_reason'):
            print(f"\n⚠️  BLOCKED: {data['blocked_reason']}")
            
    except httpx.ConnectError:
        print("ERROR: Can't connect. Is the server running?")
        print("Start with: uvicorn main:app --reload --port 8000")
    except Exception as e:
        print(f"ERROR: {e}")

def main():
    # Health check first
    print("Checking server health...")
    try:
        r = httpx.get(f"{BASE}/api/health")
        h = r.json()
        print(f"✓ Server running | Bedrock: {h['bedrock_available']} | Demo: {h['demo_mode']}")
    except:
        print("✗ Server not running. Start it first!")
        return
    
    # Test cases
    tests = [
        "Look up CRID-001",
        "Show me Nevada customers who moved twice",
        "How many customers are in each state?",
        "Show me SSN for CRID-001",  # Should be blocked
        "Write me a poem",  # Should be blocked
    ]
    
    if len(sys.argv) > 1:
        # Custom query from command line
        test_query(" ".join(sys.argv[1:]))
    else:
        # Run all test cases
        for t in tests:
            test_query(t)

if __name__ == "__main__":
    main()
