#!/bin/bash
# ================================================================
# ICDA Status - Show what's running
# ================================================================

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

check_port() {
    lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1
}

echo ""
echo "============================================================"
echo "   ICDA Service Status"
echo "============================================================"
echo ""

echo "Services:"
echo "---------"

# Check Redis
if check_port 6379; then
    if docker ps 2>/dev/null | grep -q "redis"; then
        echo -e "  Redis:      ${GREEN}RUNNING${NC} (Docker)"
    else
        echo -e "  Redis:      ${GREEN}RUNNING${NC} (External)"
    fi
else
    echo -e "  Redis:      ${RED}NOT RUNNING${NC}"
fi

# Check OpenSearch
if check_port 9200; then
    if docker ps 2>/dev/null | grep -q "opensearch"; then
        echo -e "  OpenSearch: ${GREEN}RUNNING${NC} (Docker)"
    else
        echo -e "  OpenSearch: ${GREEN}RUNNING${NC} (External)"
    fi
else
    echo -e "  OpenSearch: ${RED}NOT RUNNING${NC}"
fi

# Check Backend
if check_port 8000; then
    echo -e "  Backend:    ${GREEN}RUNNING${NC} (http://localhost:8000)"
else
    echo -e "  Backend:    ${RED}NOT RUNNING${NC}"
fi

# Check Frontend
if check_port 5173; then
    echo -e "  Frontend:   ${GREEN}RUNNING${NC} (http://localhost:5173)"
else
    echo -e "  Frontend:   ${RED}NOT RUNNING${NC}"
fi

echo ""

# Docker containers
if docker info >/dev/null 2>&1; then
    echo "Docker Containers:"
    echo "-----------------"
    docker-compose ps 2>/dev/null || echo "  No containers running"
fi

echo ""

# Health check
if curl -s http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "Health Check:"
    echo "-------------"
    curl -s http://localhost:8000/api/health | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8000/api/health
    echo ""
else
    echo -e "Health Check: ${YELLOW}Backend not responding${NC}"
fi

echo ""
