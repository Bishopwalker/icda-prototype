# ICDA Prototype - Quick Setup Guide

Pull and run the ICDA (Intelligent Customer Data Access) prototype from Docker Hub.

## Prerequisites

- Docker Desktop installed and running
- AWS credentials with Bedrock access (for Nova LLM functionality)

## Quick Start

### 1. Pull the Image

```bash
docker pull saltycoancoder81/icda-prototype:latest
```

### 2. Create Environment File

Create a `.env` file in your working directory:

```env
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1
```

### 3. Run the Container

**Option A: Simple (no Redis caching)**
```bash
docker run -p 8000:8000 --env-file .env saltycoancoder81/icda-prototype:latest
```

**Option B: With Redis (recommended for better performance)**

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  icda:
    image: saltycoancoder81/icda-prototype:latest
    container_name: icda
    ports:
      - "8000:8000"
    environment:
      - AWS_REGION=${AWS_REGION:-us-east-1}
      - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
      - REDIS_URL=redis://redis:6379
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: icda-redis
    ports:
      - "6379:6379"
    restart: unless-stopped
```

Then run:
```bash
docker-compose up
```

### 4. Access the Application

Open your browser to: **http://localhost:8000**

## AWS Credentials Setup

You need AWS credentials with Bedrock access. To create them:

1. Go to AWS IAM Console
2. Create a new IAM user or use existing
3. Attach the `AmazonBedrockFullAccess` policy (or create a custom policy for `bedrock:InvokeModel`)
4. Generate Access Keys
5. Use those keys in your `.env` file

## Features

- **Natural Language Queries**: Ask questions about customer data in plain English
- **Smart Classification**: Automatically routes queries to appropriate handlers
- **Address Verification**: 6-stage pipeline for address validation
- **Guardrails**: Built-in PII, financial, and credential blocking
- **Session Management**: Conversation context tracking

## Example Queries

Try these in the chat interface:

- "Show me John Smith's account"
- "What's the balance for customer 12345?"
- "Find customers in New York"
- "Update address for account 67890"

## Troubleshooting

### Container won't start
- Make sure Docker Desktop is running
- Check that port 8000 isn't already in use

### AWS/Bedrock errors
- Verify your AWS credentials are correct
- Ensure your IAM user has Bedrock access
- Check that `us-east-1` region has Nova models enabled

### Health Check
```bash
curl http://localhost:8000/api/health
```

Should return: `{"status": "healthy", ...}`

## Version Info

- **Image**: `saltycoancoder81/icda-prototype:latest`
- **Also available**: `saltycoancoder81/icda-prototype:0.6.0`
- **Port**: 8000
- **Stack**: FastAPI + React + AWS Bedrock Nova

## Questions?

Contact the ICDA team for support.
