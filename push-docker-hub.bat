@echo off
REM ================================================================
REM ICDA - Push to Docker Hub
REM ================================================================
REM Usage: push-docker-hub.bat
REM Images are already tagged - this just pushes them
REM ================================================================

echo.
echo ============================================================
echo    ICDA - Push to Docker Hub
echo    %date% %time%
echo ============================================================
echo.

echo [1/3] Checking Docker login...
docker login
if %errorlevel% neq 0 (
    echo [ERROR] Docker login failed!
    pause
    exit /b 1
)

echo [2/3] Pushing icda-prototype...
docker push bwalker33/icda-prototype:latest
if %errorlevel% neq 0 (
    echo [WARN] Push failed - Docker Hub may be having issues
    echo        Try again later: docker push bwalker33/icda-prototype:latest
)

echo [3/3] Pushing icda-mcp-knowledge...
docker push bwalker33/icda-mcp-knowledge:latest
if %errorlevel% neq 0 (
    echo [WARN] Push failed - Docker Hub may be having issues
    echo        Try again later: docker push bwalker33/icda-mcp-knowledge:latest
)

echo.
echo ============================================================
echo   Push Complete!
echo ============================================================
echo.
echo Images pushed:
echo   - bwalker33/icda-prototype:latest
echo   - bwalker33/icda-mcp-knowledge:latest
echo.
pause
