@echo off
REM ================================================================
REM ICDA - Unified Stop Script
REM ================================================================
REM Usage: STOP-ALL.bat [options]
REM   Options:
REM     --volumes, -v   Also remove volumes (destroys data)
REM     --help, -h      Show this help message
REM ================================================================

setlocal enabledelayedexpansion

set "REMOVE_VOLUMES="

:parse_args
if "%~1"=="" goto :main
if /i "%~1"=="--volumes" set "REMOVE_VOLUMES=-v" & shift & goto :parse_args
if /i "%~1"=="-v" set "REMOVE_VOLUMES=-v" & shift & goto :parse_args
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="-h" goto :show_help
shift
goto :parse_args

:show_help
echo.
echo ICDA - Unified Stop Script
echo.
echo Usage: STOP-ALL.bat [options]
echo.
echo Options:
echo   --volumes, -v   Also remove volumes (destroys data)
echo   --help, -h      Show this help message
echo.
exit /b 0

:main
echo.
echo ============================================================
echo    ICDA - Unified Stop
echo    %date% %time%
echo ============================================================
echo.

echo [1/2] Stopping Docker containers...
if "%REMOVE_VOLUMES%"=="-v" (
    echo   Removing containers and volumes...
    docker-compose down --remove-orphans -v
) else (
    docker-compose down --remove-orphans
)
echo   [OK] Containers stopped
echo.

echo [2/2] Stopping application processes...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /F /PID %%a >nul 2>&1
)
echo   [OK] Processes stopped
echo.

echo ============================================================
echo   ICDA Services Stopped
echo ============================================================
echo.
if "%REMOVE_VOLUMES%"=="-v" (
    echo Status: All services stopped and data volumes removed
) else (
    echo Status: All services stopped (data preserved)
    echo        Use STOP-ALL.bat -v to also remove volumes
)
echo.
echo Next steps:
echo   Start again:     BUILD-ALL.bat
echo   Clean restart:   BUILD-ALL.bat --clean
echo.
pause
exit /b 0