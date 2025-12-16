@echo off
REM ================================================================
REM ICDA Status - Show what's running
REM ================================================================

echo.
echo ============================================================
echo    ICDA Service Status
echo ============================================================
echo.

echo Services:
echo ---------

REM Check Redis
set "REDIS_STATUS=NOT RUNNING"
set "REDIS_SOURCE="
netstat -ano 2>nul | findstr ":6379 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    docker ps 2>nul | findstr "redis" >nul 2>&1
    if %errorlevel%==0 (
        set "REDIS_STATUS=RUNNING"
        set "REDIS_SOURCE=(Docker)"
    ) else (
        set "REDIS_STATUS=RUNNING"
        set "REDIS_SOURCE=(External)"
    )
)
echo   Redis:      %REDIS_STATUS% %REDIS_SOURCE%

REM Check OpenSearch
set "OS_STATUS=NOT RUNNING"
set "OS_SOURCE="
netstat -ano 2>nul | findstr ":9200 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    docker ps 2>nul | findstr "opensearch" >nul 2>&1
    if %errorlevel%==0 (
        set "OS_STATUS=RUNNING"
        set "OS_SOURCE=(Docker)"
    ) else (
        set "OS_STATUS=RUNNING"
        set "OS_SOURCE=(External)"
    )
)
echo   OpenSearch: %OS_STATUS% %OS_SOURCE%

REM Check Backend
set "BACKEND_STATUS=NOT RUNNING"
netstat -ano 2>nul | findstr ":8000 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    set "BACKEND_STATUS=RUNNING (http://localhost:8000)"
)
echo   Backend:    %BACKEND_STATUS%

REM Check Frontend
set "FRONTEND_STATUS=NOT RUNNING"
netstat -ano 2>nul | findstr ":5173 " | findstr "LISTENING" >nul 2>&1
if %errorlevel%==0 (
    set "FRONTEND_STATUS=RUNNING (http://localhost:5173)"
)
echo   Frontend:   %FRONTEND_STATUS%

echo.

REM Show Docker containers if available
docker info >nul 2>&1
if %errorlevel%==0 (
    echo Docker Containers:
    echo -----------------
    docker-compose ps 2>nul
    if %errorlevel% neq 0 (
        echo   No containers running
    )
)

echo.

REM Quick health check
curl -s http://localhost:8000/api/health >nul 2>&1
if %errorlevel%==0 (
    echo Health Check:
    echo -------------
    curl -s http://localhost:8000/api/health
    echo.
) else (
    echo Health Check: Backend not responding
)

echo.
