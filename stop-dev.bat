@echo off
echo ============================================================
echo    ICDA Prototype - Stop All Development Servers (FORCE)
echo ============================================================
echo.

REM Stop Docker containers
echo [INFO] Stopping Docker containers (Redis, OpenSearch)...
docker-compose down >nul 2>&1
if %errorlevel%==0 (
    echo        Docker containers stopped.
) else (
    echo        No Docker containers running or Docker not available.
)
echo.

REM Kill ALL node processes
echo [INFO] Force killing ALL Node.js processes...
taskkill /F /IM "node.exe" >nul 2>&1
if %errorlevel%==0 (
    echo        Node.js processes killed.
) else (
    echo        No Node.js processes found.
)

REM Kill ALL python processes
echo [INFO] Force killing ALL Python processes...
taskkill /F /IM "python.exe" >nul 2>&1
if %errorlevel%==0 (
    echo        Python processes killed.
) else (
    echo        No Python processes found.
)

REM Kill processes on backend port 8000
echo [INFO] Checking port 8000 (FastAPI Backend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo        Force killing PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill processes on Vite port 5173
echo [INFO] Checking port 5173 (Vite Frontend)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 ^| findstr LISTENING') do (
    echo        Force killing PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

REM Kill processes on Vite preview port 4173
echo [INFO] Checking port 4173 (Vite Preview)...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :4173 ^| findstr LISTENING') do (
    echo        Force killing PID %%a...
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo ============================================================
echo [SUCCESS] All processes force killed!
echo ============================================================
echo.
echo Ports cleared: 8000, 5173, 4173, 9200, 6379
echo Docker containers: stopped
echo.
pause
