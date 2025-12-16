# Adaptive RAG Service - Self-Contained Docker Image
# FedRAMP compliant - no external dependencies required

FROM python:3.11-slim

LABEL maintainer="Universal Context Template"
LABEL description="Adaptive RAG System - Kubernetes-like auto-configuration"
LABEL version="1.0.0"

# Security: Run as non-root
RUN groupadd -g 10001 rag && \
    useradd -u 10001 -g rag -s /bin/bash -m rag

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for caching
COPY rag_requirements.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy RAG system
COPY . /app/rag/

# Create directories
RUN mkdir -p /project /data/chroma_db && \
    chown -R rag:rag /app /project /data

# Environment variables
ENV PYTHONPATH=/app
ENV CHROMA_PERSIST_DIR=/data/chroma_db
ENV PROJECT_ROOT=/project
ENV RAG_REST_API=true

# Switch to non-root user
USER rag

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Expose REST API port
EXPOSE 8080

# Default command - serve REST API
CMD ["python", "-m", "rag.adaptive_rag", "--serve", "--port", "8080"]
