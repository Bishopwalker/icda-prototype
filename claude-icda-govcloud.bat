@echo off
REM ============================================
REM Claude Code - ICDA GovCloud Launcher
REM For USPS production work (FedRAMP High + IL4/IL5)
REM ============================================

echo.
echo ========================================
echo  ICDA - Claude Code (AWS GovCloud)
echo  FedRAMP High / IL4 / IL5 Compliant
echo  Model: Opus 4.5
echo ========================================
echo.

REM Set GovCloud Bedrock environment
set CLAUDE_CODE_USE_BEDROCK=1
set AWS_PROFILE=icda
set AWS_REGION=us-gov-west-1
set ANTHROPIC_MODEL=us.anthropic.claude-opus-4-5-20251101-v1:0
set ANTHROPIC_SMALL_FAST_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0

REM Check AWS GovCloud credentials
echo Checking AWS GovCloud credentials...
aws sts get-caller-identity --profile %AWS_PROFILE% >nul 2>&1
if errorlevel 1 (
    echo.
    echo [WARNING] AWS GovCloud credentials expired or not configured.
    echo.
    echo To configure GovCloud SSO:
    echo   aws configure sso --profile icda
    echo.
    echo Then login:
    echo   aws sso login --profile icda
    echo.
    pause
    exit /b 1
)

echo AWS Profile: %AWS_PROFILE% (GovCloud)
echo Region: %AWS_REGION%
echo Model: Opus 4.5
echo Compliance: FedRAMP High, IL4, IL5
echo.

REM Launch Claude Code
claude
