#!/bin/bash
# ============================================
# ICDA Docker Startup Script
# ============================================
# Handles service initialization and server startup
# All services connect immediately - no manual configuration
# ============================================

set -e

echo "============================================"
echo "  ICDA Unified Container Starting"
echo "============================================"
echo ""

# ============================================
# Parse Redis URL
# ============================================
REDIS_URL="${REDIS_URL:-redis://redis:6379}"
# Strip protocol prefix
REDIS_HOST_PORT="${REDIS_URL#redis://}"
REDIS_HOST="${REDIS_HOST_PORT%%:*}"
REDIS_PORT="${REDIS_HOST_PORT##*:}"
REDIS_PORT="${REDIS_PORT%%/*}"
REDIS_HOST="${REDIS_HOST:-redis}"
REDIS_PORT="${REDIS_PORT:-6379}"

echo "[1/4] Waiting for Redis (${REDIS_HOST}:${REDIS_PORT})..."
for i in {1..30}; do
    if python3 -c "
import socket
import sys
try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    s.connect(('${REDIS_HOST}', ${REDIS_PORT}))
    s.send(b'PING\r\n')
    response = s.recv(1024)
    s.close()
    if b'PONG' in response:
        sys.exit(0)
    sys.exit(1)
except:
    sys.exit(1)
" 2>/dev/null; then
        echo "  ✓ Redis is ready"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "  ⚠ Redis not responding after 30 attempts, continuing anyway..."
    fi
    sleep 1
done

# ============================================
# Wait for OpenSearch
# ============================================
echo "[2/4] Waiting for OpenSearch..."
OPENSEARCH_URL="${OPENSEARCH_HOST:-http://opensearch:9200}"

for i in {1..60}; do
    if curl -sf "${OPENSEARCH_URL}/_cluster/health" 2>/dev/null | grep -qE '(green|yellow)'; then
        echo "  ✓ OpenSearch is ready (cluster healthy)"
        break
    fi
    # Also try just checking if it responds at all
    if curl -sf "${OPENSEARCH_URL}" 2>/dev/null | grep -q 'opensearch'; then
        echo "  ✓ OpenSearch is responding (waiting for cluster...)"
    fi
    if [ $i -eq 60 ]; then
        echo "  ⚠ OpenSearch not fully ready after 60 attempts, continuing..."
    fi
    sleep 2
done

# ============================================
# Verify Frontend Assets
# ============================================
echo "[3/4] Checking frontend assets..."
if [ -d "/app/frontend/dist" ] && [ -f "/app/frontend/dist/index.html" ]; then
    ASSET_COUNT=$(find /app/frontend/dist -name "*.js" -o -name "*.css" 2>/dev/null | wc -l)
    echo "  ✓ Frontend ready (${ASSET_COUNT} assets)"
else
    echo "  ⚠ Frontend dist not found - serving template fallback"
fi

# ============================================
# Optional: Auto-index customers
# ============================================
if [ "${AUTO_INDEX_CUSTOMERS:-false}" = "true" ]; then
    echo "[3.5/4] Auto-indexing customer data..."
    python index_customers.py --force --batch-size 100 2>/dev/null || echo "  ⚠ Customer indexing skipped"
fi

# ============================================
# Start the Server
# ============================================
echo "[4/4] Starting FastAPI server..."
echo ""
echo "============================================"
echo "  ICDA is running!"
echo "============================================"
echo ""
echo "  🌐 App:     http://0.0.0.0:8000"
echo "  📚 API Docs: http://localhost:8000/docs"
echo "  ❤️  Health:  http://localhost:8000/api/health"
echo ""
echo "  Services connected:"
echo "    - Redis:      ${REDIS_HOST}:${REDIS_PORT}"
echo "    - OpenSearch: ${OPENSEARCH_URL}"
echo ""
echo "============================================"
echo ""

# Start uvicorn with the app
exec python -m uvicorn main:app --host 0.0.0.0 --port 8000
