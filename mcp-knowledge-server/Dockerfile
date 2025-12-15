# MCP Knowledge Server Dockerfile
# ================================
# RAG knowledge server for ICDA Claude Code integration
# Indexes internal documentation for PR urbanization, address verification, etc.

FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.title="ICDA MCP Knowledge Server"
LABEL org.opencontainers.image.description="RAG knowledge server for ICDA Claude Code integration"
LABEL org.opencontainers.image.version="1.0.0"
LABEL org.opencontainers.image.source="https://github.com/your-org/icda-prototype"

# Security: Create non-root user
RUN groupadd -g 10001 mcpuser && \
    useradd -u 10001 -g mcpuser -s /bin/bash -m mcpuser

# Install system dependencies for document processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy server code
COPY *.py ./

# Create directories with proper permissions
RUN mkdir -p /app/knowledge /app/data && \
    chown -R mcpuser:mcpuser /app

# Environment configuration
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    KNOWLEDGE_INDEX=icda-knowledge \
    KNOWLEDGE_WATCH_FOLDER=/app/knowledge \
    LOG_LEVEL=INFO

# Switch to non-root user
USER mcpuser

# Health check (optional - for orchestration)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import sys; sys.exit(0)"

# Default command - run the MCP server
CMD ["python", "server.py"]
