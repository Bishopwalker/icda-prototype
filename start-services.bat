@echo off
REM ICDA - Start Redis + OpenSearch in Docker
REM Run this before start-local.bat

echo ============================================================
echo    ICDA - Starting Docker Services (Redis + OpenSearch)
echo ============================================================
echo.

REM Check Docker is running
docker info >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Start Redis
echo [INFO] Starting Redis...
docker run -d --name icda-redis -p 6379:6379 redis:7-alpine 2>nul
if %errorlevel% neq 0 (
    echo [INFO] Redis container may already exist, starting...
    docker start icda-redis 2>nul
)

REM Start OpenSearch
echo [INFO] Starting OpenSearch...
docker run -d --name icda-opensearch -p 9200:9200 -e "discovery.type=single-node" -e "DISABLE_SECURITY_PLUGIN=true" -e "OPENSEARCH_JAVA_OPTS=-Xms512m -Xmx512m" opensearchproject/opensearch:2.11.0 2>nul
if %errorlevel% neq 0 (
    echo [INFO] OpenSearch container may already exist, starting...
    docker start icda-opensearch 2>nul
)

REM Wait for Redis
echo [INFO] Waiting for Redis...
:wait_redis
timeout /t 1 >nul
docker exec icda-redis redis-cli ping >nul 2>&1
if %errorlevel% neq 0 goto wait_redis
echo [OK] Redis is ready!

REM Wait for OpenSearch
echo [INFO] Waiting for OpenSearch (may take 30-60 seconds)...
:wait_opensearch
timeout /t 3 >nul
curl -s http://localhost:9200 >nul 2>&1
if %errorlevel% neq 0 (
    echo      Still waiting...
    goto wait_opensearch
)
echo [OK] OpenSearch is ready!

echo.
echo ============================================================
echo [SUCCESS] Docker services running!
echo ============================================================
echo.
echo   Redis:       localhost:6379
echo   OpenSearch:  http://localhost:9200
echo.
echo Now run: start-local.bat
echo.
pause
