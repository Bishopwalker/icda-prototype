#!/bin/bash
# ================================================================
# ICDA Unified Startup - Auto-detect best mode
# ================================================================
# Usage: ./start.sh [mode] [options]
#   Modes: auto, hybrid, docker, local
#   Options: --verbose, --skip-health
# ================================================================

set -e

# Configuration
BACKEND_PORT=8000
FRONTEND_PORT=5173
REDIS_PORT=6379
OPENSEARCH_PORT=9200

# Defaults
MODE="auto"
VERBOSE=0
SKIP_HEALTH=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        hybrid|docker|local)
            MODE="$1"
            shift
            ;;
        --verbose|-v)
            VERBOSE=1
            shift
            ;;
        --skip-health)
            SKIP_HEALTH=1
            shift
            ;;
        *)
            shift
            ;;
    esac
done

print_header() {
    echo ""
    echo "============================================================"
    echo "   ICDA Unified Startup v2.0"
    echo "   $(date)"
    echo "============================================================"
    echo ""
}

check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

kill_port() {
    local port=$1
    local pid=$(lsof -Pi :$port -sTCP:LISTEN -t 2>/dev/null)
    if [ -n "$pid" ]; then
        echo "  Killing process on port $port (PID: $pid)"
        kill -9 $pid 2>/dev/null || true
    fi
}

wait_for_services() {
    echo "Waiting for required services to be ready..."
    local tries=0
    while [ $tries -lt 30 ]; do
        # Check Redis
        if ! docker exec icda-redis-1 redis-cli ping >/dev/null 2>&1; then
            if ! docker exec redis redis-cli ping >/dev/null 2>&1; then
                echo "  Waiting for Redis... ($tries/30)"
                sleep 2
                ((tries++))
                continue
            fi
        fi

        # Check OpenSearch
        if ! curl -s http://localhost:9200 >/dev/null 2>&1; then
            echo "  Waiting for OpenSearch... ($tries/30)"
            sleep 2
            ((tries++))
            continue
        fi

        echo -e "  ${GREEN}[OK]${NC} All services ready!"
        return 0
    done

    echo -e "  ${RED}[ERROR]${NC} Services failed to start within timeout!"
    echo "        Redis and OpenSearch are REQUIRED for ICDA."
    exit 1
}

# Main script
print_header
echo "Detecting environment..."
echo ""

# Check Docker
DOCKER_OK=0
if docker info >/dev/null 2>&1; then
    DOCKER_OK=1
    echo -e "  ${GREEN}[OK]${NC} Docker: Available"
else
    echo "  [--] Docker: Not available"
fi

# Check ports
REDIS_RUNNING=0
OPENSEARCH_RUNNING=0
BACKEND_RUNNING=0
FRONTEND_RUNNING=0

check_port $REDIS_PORT && REDIS_RUNNING=1
check_port $OPENSEARCH_PORT && OPENSEARCH_RUNNING=1
check_port $BACKEND_PORT && BACKEND_RUNNING=1
check_port $FRONTEND_PORT && FRONTEND_RUNNING=1

# Check Python/Node
PYTHON_OK=0
NODE_OK=0
command -v python3 >/dev/null 2>&1 && PYTHON_OK=1
command -v python >/dev/null 2>&1 && PYTHON_OK=1
command -v node >/dev/null 2>&1 && NODE_OK=1

# Check venv
VENV_OK=0
[ -f "venv/bin/activate" ] && VENV_OK=1

if [ $VERBOSE -eq 1 ]; then
    echo ""
    echo "Environment Status:"
    echo "  Docker:     $DOCKER_OK (1=available)"
    echo "  Python:     $PYTHON_OK"
    echo "  Node.js:    $NODE_OK"
    echo "  Venv:       $VENV_OK"
    echo ""
    echo "Port Status:"
    echo "  Redis ($REDIS_PORT):      $REDIS_RUNNING (1=in use)"
    echo "  OpenSearch ($OPENSEARCH_PORT): $OPENSEARCH_RUNNING"
    echo "  Backend ($BACKEND_PORT):    $BACKEND_RUNNING"
    echo "  Frontend ($FRONTEND_PORT):   $FRONTEND_RUNNING"
    echo ""
fi

# Auto-mode selection
if [ "$MODE" == "auto" ]; then
    if [ $DOCKER_OK -eq 1 ]; then
        if [ $REDIS_RUNNING -eq 0 ] && [ $OPENSEARCH_RUNNING -eq 0 ]; then
            MODE="hybrid"
            echo "  [AUTO] Selected HYBRID mode (Docker services + native app)"
        elif docker ps 2>/dev/null | grep -q "redis"; then
            MODE="hybrid"
            echo "  [AUTO] Selected HYBRID mode (existing Docker services detected)"
        else
            MODE="local"
            echo "  [AUTO] Selected LOCAL mode (external services detected)"
        fi
    else
        if [ $PYTHON_OK -eq 1 ]; then
            MODE="local"
            echo "  [AUTO] Selected LOCAL mode (no Docker available)"
        else
            echo -e "  ${RED}[ERROR]${NC} No Docker and no Python - cannot start!"
            exit 1
        fi
    fi
fi

# Execute selected mode
case $MODE in
    hybrid)
        echo ""
        echo "============================================================"
        echo "  HYBRID MODE: Docker services + Native application"
        echo "============================================================"
        echo ""

        # Start Redis if not running - REQUIRED!
        if [ $REDIS_RUNNING -eq 0 ]; then
            echo "Starting Redis in Docker..."
            if ! docker-compose up -d redis; then
                echo -e "${RED}[ERROR]${NC} Failed to start Redis - ICDA requires Redis!"
                exit 1
            fi
        fi

        # Start OpenSearch if not running - REQUIRED!
        if [ $OPENSEARCH_RUNNING -eq 0 ]; then
            echo "Starting OpenSearch in Docker..."
            if ! docker-compose up -d opensearch; then
                echo -e "${RED}[ERROR]${NC} Failed to start OpenSearch - ICDA requires OpenSearch!"
                exit 1
            fi
        fi

        # Wait for services
        [ $SKIP_HEALTH -eq 0 ] && wait_for_services

        # Kill existing processes
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_PORT

        # Activate venv
        if [ $VENV_OK -eq 1 ]; then
            echo "Activating Python virtual environment..."
            source venv/bin/activate
        fi

        # Set environment
        export OPENSEARCH_HOST="http://localhost:9200"
        export REDIS_URL="redis://localhost:6379"

        # Start application
        echo ""
        echo "Starting ICDA application..."
        npm run dev
        ;;

    docker)
        echo ""
        echo "============================================================"
        echo "  DOCKER MODE: Everything containerized"
        echo "============================================================"
        echo ""

        if [ $DOCKER_OK -eq 0 ]; then
            echo -e "${RED}[ERROR]${NC} Docker is not available!"
            exit 1
        fi

        # Kill conflicting processes
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_PORT

        # Build frontend if needed
        if [ ! -f "frontend/dist/index.html" ]; then
            echo "Building frontend..."
            cd frontend && npm ci && npm run build && cd ..
        fi

        # Start all services
        echo "Starting full Docker stack..."
        docker-compose up -d icda redis opensearch

        echo ""
        echo -e "${GREEN}[SUCCESS]${NC} Docker stack running!"
        docker-compose ps
        ;;

    local)
        echo ""
        echo "============================================================"
        echo "  LOCAL MODE: Everything native (no Docker)"
        echo "============================================================"
        echo ""

        if [ $PYTHON_OK -eq 0 ]; then
            echo -e "${RED}[ERROR]${NC} Python not found!"
            exit 1
        fi

        # Create venv if needed
        if [ $VENV_OK -eq 0 ]; then
            echo "Creating virtual environment..."
            python3 -m venv venv || python -m venv venv
        fi

        source venv/bin/activate
        pip install -r requirements.txt -q

        # Check services - REQUIRED!
        if [ $REDIS_RUNNING -eq 0 ]; then
            echo -e "${RED}[ERROR]${NC} Redis not running - ICDA requires Redis!"
            echo "        Start Redis with: docker-compose up -d redis"
            exit 1
        fi
        if [ $OPENSEARCH_RUNNING -eq 0 ]; then
            echo -e "${RED}[ERROR]${NC} OpenSearch not running - ICDA requires OpenSearch!"
            echo "        Start OpenSearch with: docker-compose up -d opensearch"
            exit 1
        fi

        # Kill conflicting processes
        kill_port $BACKEND_PORT
        kill_port $FRONTEND_PORT

        echo ""
        echo "Starting ICDA application..."
        npm run dev
        ;;
esac

echo ""
echo "============================================================"
echo "  ICDA Running - Mode: $MODE"
echo "============================================================"
echo ""
echo "  Backend API:  http://localhost:$BACKEND_PORT/api"
echo "  API Docs:     http://localhost:$BACKEND_PORT/docs"
echo "  Frontend:     http://localhost:$FRONTEND_PORT"
echo "  Admin:        http://localhost:$FRONTEND_PORT/admin"
echo "  Health:       http://localhost:$BACKEND_PORT/api/health"
echo ""
echo "  Stop with: ./stop.sh (or Ctrl+C)"
echo "============================================================"
