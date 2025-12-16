@echo off
REM ICDA Development Mode - Auto-reload enabled
REM Backend: Changes to Python files auto-reload
REM Frontend: Run 'npm run build' in /frontend after changes

echo Building frontend...
cd frontend && call npm run build && cd ..

echo.
echo Starting ICDA in dev mode with auto-reload...
echo Backend changes will auto-reload.
echo Frontend changes: run 'npm run build' in /frontend folder.
echo.

docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build
