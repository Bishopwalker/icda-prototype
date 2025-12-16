@echo off
REM Frontend watch mode - auto-rebuilds on file changes
REM Run this in a separate terminal alongside dev.bat

echo Starting frontend watch mode...
echo Changes to frontend files will auto-rebuild.
echo.

cd frontend && npm run build -- --watch
