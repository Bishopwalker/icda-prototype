@echo off
REM ICDA - Stop Docker Services

echo [INFO] Stopping Redis...
docker stop icda-redis 2>nul

echo [INFO] Stopping OpenSearch...
docker stop icda-opensearch 2>nul

echo.
echo [OK] Services stopped.
echo.
echo To remove containers completely:
echo   docker rm icda-redis icda-opensearch
echo.
pause
