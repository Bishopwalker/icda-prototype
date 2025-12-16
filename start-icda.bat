@echo off
REM ICDA - One Command Start (with AWS credentials)

REM Get AWS credentials from aws cli
for /f "tokens=*" %%a in ('aws configure get aws_access_key_id') do set AWS_ACCESS_KEY_ID=%%a
for /f "tokens=*" %%a in ('aws configure get aws_secret_access_key') do set AWS_SECRET_ACCESS_KEY=%%a
for /f "tokens=*" %%a in ('aws configure get region') do set AWS_REGION=%%a
if "%AWS_REGION%"=="" set AWS_REGION=us-east-1

echo Starting ICDA with AWS credentials...
docker-compose -f docker-compose.prod.yml up -d

echo.
echo ICDA running at: http://localhost:8000
