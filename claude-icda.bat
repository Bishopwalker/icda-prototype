@echo off
REM ============================================
REM Claude Code - ICDA Project Launcher
REM Uses AWS Bedrock with Opus 4.5
REM ============================================

echo.
echo ========================================
echo  ICDA - Claude Code (AWS Bedrock)
echo  Model: Opus 4.5
echo ========================================
echo.

REM Set Bedrock environment
set CLAUDE_CODE_USE_BEDROCK=1
set AWS_PROFILE=icda-commercial
set AWS_REGION=us-east-1
set ANTHROPIC_MODEL=us.anthropic.claude-opus-4-5-20251101-v1:0
set ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0

REM Check AWS credentials
echo Checking AWS credentials...
aws sts get-caller-identity --profile %AWS_PROFILE% >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] AWS credentials expired or not configured.
    echo Run: aws sso login --profile %AWS_PROFILE%
    echo.
    pause
    exit /b 1
)

echo AWS Profile: %AWS_PROFILE%
echo Region: %AWS_REGION%
echo Model: Opus 4.5
echo.

REM Launch Claude Code
claude
