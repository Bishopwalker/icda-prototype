# Universal Context Template - MCP Server
# Production-ready Docker image for MCP server distribution
# Compliance: FedRAMP Moderate, CIS Docker Benchmark v1.6.0

FROM python:3.11-slim-bookworm AS base

LABEL org.opencontainers.image.title="Universal Context MCP Server" \
      org.opencontainers.image.description="Model Context Protocol server for AI-assisted development" \
      org.opencontainers.image.version="2.2.0" \
      org.opencontainers.image.vendor="Universal Context Template" \
      security.hardening.cis-benchmark="docker-1.6.0"

# Security: Create non-root user
RUN groupadd -g 10001 mcpuser && \
    useradd -u 10001 -g mcpuser -s /bin/bash -m mcpuser

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Set working directory
WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt /app/
COPY ../../rag/rag_requirements.txt /app/rag_requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -r rag_requirements.txt

# Copy MCP server code
COPY . /app/mcp-server/

# Copy RAG system
COPY ../../rag /app/rag/

# Copy agents for context
COPY ../../agents /app/agents/

# Copy context files
COPY ../../*.md /app/context/

# Set ownership
RUN chown -R mcpuser:mcpuser /app

# Create data directories
RUN mkdir -p /app/data/chroma /app/data/memory && \
    chown -R mcpuser:mcpuser /app/data

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MCP_SERVER_HOME=/app/mcp-server \
    RAG_HOME=/app/rag \
    CHROMA_PERSIST_DIR=/app/data/chroma \
    MEM0_MODE=local

# Switch to non-root user
USER mcpuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import mcp; print('healthy')" || exit 1

# Default command - run MCP server
WORKDIR /app/mcp-server
CMD ["python", "server.py"]
