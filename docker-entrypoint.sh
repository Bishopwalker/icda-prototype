#!/bin/bash
# ICDA Docker Entrypoint
# Knowledge documents are auto-indexed on startup via Python

set -e

echo "=========================================="
echo "ICDA Starting..."
echo "=========================================="

# Run uvicorn (knowledge auto-indexing happens in lifespan startup)
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
