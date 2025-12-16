@echo off
REM ICDA - One Command Start
REM Works with: aws configure OR .env file

REM Check for .env file first
if exist .env (
    echo Loading credentials from .env file...
    for /f "tokens=1,2 delims==" %%a in (.env) do (
        if "%%a"=="AWS_ACCESS_KEY_ID" set AWS_ACCESS_KEY_ID=%%b
        if "%%a"=="AWS_SECRET_ACCESS_KEY" set AWS_SECRET_ACCESS_KEY=%%b
        if "%%a"=="AWS_REGION" set AWS_REGION=%%b
    )
) else (
    REM Try aws configure
    echo Loading credentials from AWS CLI...
    for /f "tokens=*" %%a in ('aws configure get aws_access_key_id 2^>nul') do set AWS_ACCESS_KEY_ID=%%a
    for /f "tokens=*" %%a in ('aws configure get aws_secret_access_key 2^>nul') do set AWS_SECRET_ACCESS_KEY=%%a
    for /f "tokens=*" %%a in ('aws configure get region 2^>nul') do set AWS_REGION=%%a
)

if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

if "%AWS_ACCESS_KEY_ID%"=="" (
    echo.
    echo ERROR: No AWS credentials found!
    echo.
    echo Option 1: Run 'aws configure' and enter your credentials
    echo Option 2: Copy .env.template to .env and fill in your keys
    echo.
    exit /b 1
)

echo.
echo Starting ICDA...
echo   AWS Region: %AWS_REGION%
echo   Credentials: Found
echo.

docker-compose -f docker-compose.prod.yml up -d

echo.
echo ============================================
echo   ICDA is starting...
echo   Wait 30 seconds then open:
echo   http://localhost:8000
echo ============================================
