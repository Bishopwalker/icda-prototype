# ICDA - Intelligent Customer Data Access
# Multi-stage build for optimized production image

# ============================================
# Stage 1: Build frontend
# ============================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy package files first for layer caching
COPY frontend/package*.json ./
RUN npm ci --silent

# Copy source and build
COPY frontend/ ./
RUN npm run build

# ============================================
# Stage 2: Production image
# ============================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy Python requirements and install (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY main.py .
COPY customer_data.json .
COPY icda/ ./icda/
COPY templates/ ./templates/

# Copy built frontend from builder stage
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Environment variables (defaults)
ENV AWS_REGION=us-east-1 \
    NOVA_MODEL=us.amazon.nova-micro-v1:0 \
    REDIS_URL="" \
    OPENSEARCH_HOST="" \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/api/health || exit 1

# Expose port
EXPOSE 8000

# Run with uvicorn
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]