@echo off
REM ================================================================
REM ICDA Unified Stop - Cleanly stop all services
REM ================================================================

echo.
echo ============================================================
echo    ICDA Unified Stop
echo ============================================================
echo.

REM Stop Docker containers
echo Stopping Docker containers...
docker-compose down 2>nul

REM Kill application processes on known ports
echo Stopping application processes...

REM Backend (8000)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo   Killing process on port 8000 ^(PID: %%a^)
    taskkill /F /PID %%a >nul 2>&1
)

REM Frontend (5173)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    echo   Killing process on port 5173 ^(PID: %%a^)
    taskkill /F /PID %%a >nul 2>&1
)

REM Preview (4173)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":4173 " ^| findstr "LISTENING"') do (
    echo   Killing process on port 4173 ^(PID: %%a^)
    taskkill /F /PID %%a >nul 2>&1
)

echo.
echo [SUCCESS] All ICDA services stopped.
echo.
