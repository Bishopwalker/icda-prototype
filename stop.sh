#!/bin/bash
# ================================================================
# ICDA Unified Stop - Cleanly stop all services
# ================================================================

echo ""
echo "============================================================"
echo "   ICDA Unified Stop"
echo "============================================================"
echo ""

# Stop Docker containers
echo "Stopping Docker containers..."
docker-compose down 2>/dev/null || true

# Kill processes on known ports
echo "Stopping application processes..."

kill_port() {
    local port=$1
    local pid=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "  Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
}

kill_port 8000
kill_port 5173
kill_port 4173

echo ""
echo "[SUCCESS] All ICDA services stopped."
echo ""
