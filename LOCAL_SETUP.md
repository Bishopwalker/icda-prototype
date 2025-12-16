 # Local Setup Instructions for ICDA Prototype

This guide explains how to get the full ICDA stack (Application, Redis, and OpenSearch) running locally.

## Prerequisites

1.  **Docker Desktop**: Ensure Docker Desktop is installed and running.
2.  **Git**: To clone/pull the repository.
3.  **AWS Credentials**: You need valid AWS credentials for Bedrock access.

## Quick Start (Recommended)

The easiest way to run everything is using Docker Compose. This spins up the app, Redis, and OpenSearch in a pre-configured network.

1.  **Configure Environment**:
    Ensure your AWS credentials are set in your environment or a `.env` file.
    ```bash
    # Linux/Mac
    export AWS_ACCESS_KEY_ID=your_key
    export AWS_SECRET_ACCESS_KEY=your_secret
    export AWS_REGION=us-east-1

    # Windows (PowerShell)
    $env:AWS_ACCESS_KEY_ID="your_key"
    $env:AWS_SECRET_ACCESS_KEY="your_secret"
    $env:AWS_REGION="us-east-1"
    ```

2.  **Start Services**:
    Run the following command from the project root:
    ```bash
    docker-compose up -d --build
    ```
    *   `--build`: Rebuilds the images to ensure you have the latest code.
    *   `-d`: Detached mode (runs in background).

3.  **Verify Status**:
    Check if all containers are healthy:
    ```bash
    docker ps
    ```
    You should see:
    *   `icda`: The main application (Port 8000)
    *   `icda-redis`: Redis cache (Port 6379)
    *   `icda-opensearch`: OpenSearch vector DB (Port 9200)

4.  **Access the App**:
    Open [http://localhost:8000](http://localhost:8000) in your browser.

5.  **Stop Services**:
    ```bash
    docker-compose down
    ```

## Manual Setup (Development Mode)

If you want to run the Python backend locally (for debugging) while keeping the database services in Docker:

1.  **Start Databases Only**:
    ```bash
    docker-compose up -d redis opensearch
    ```

2.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the Application**:
    Set the environment variables to point to localhost ports:
    ```bash
    # Windows PowerShell
    $env:REDIS_URL="redis://localhost:6379"
    $env:OPENSEARCH_HOST="http://localhost:9200"
    $env:AWS_ACCESS_KEY_ID="your_key"
    $env:AWS_SECRET_ACCESS_KEY="your_secret"
    
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
    ```

## Troubleshooting

*   **"OpenSearch host not configured"**: Ensure you are using `docker-compose up` so the `OPENSEARCH_HOST` variable is passed automatically.
*   **Redis Connection Error**: Ensure the `redis` container is running (`docker ps`).
*   **AWS Bedrock Errors**: Verify your AWS keys have permission to invoke Bedrock models (specifically Nova Micro).