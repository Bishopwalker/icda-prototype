@echo off
REM ICDA - One Command Start
REM Just run: start.bat

echo.
echo ============================================
echo   ICDA Prototype
echo ============================================

docker info >nul 2>&1
if errorlevel 1 (
    echo ERROR: Start Docker Desktop first!
    exit /b 1
)

for /f "tokens=*" %%a in ('aws configure get aws_access_key_id 2^>nul') do set AWS_ACCESS_KEY_ID=%%a
for /f "tokens=*" %%a in ('aws configure get aws_secret_access_key 2^>nul') do set AWS_SECRET_ACCESS_KEY=%%a
set AWS_REGION=us-east-1

echo Starting ICDA...
docker-compose up -d --build

echo.
echo ============================================
echo   Ready: http://localhost:8000
echo   Stop:  docker-compose down
echo ============================================
