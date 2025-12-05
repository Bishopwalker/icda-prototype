@echo off
setlocal EnableExtensions EnableDelayedExpansion
echo ============================================
echo Stopping EBL Development Environment
echo ============================================
echo.

rem Target ports for dev services and similar alternates
rem - Vite: 5173 and nearby when auto-incrementing
rem - Vite preview: 4173
rem - Backend (Uvicorn): 8000 and nearby when auto-incrementing
rem - Common frontend alts: 3000,3001
 for %%P in (5173 5174 5175 5176 8000 8001 8002 8003 8004 8005 8006 8007 8008 8009 8010) do (
     echo Checking port %%P...
     for /f "tokens=5" %%a in ('netstat -ano ^| findstr :%%P') do (
         echo Found process %%a on port %%P - killing...
         taskkill /F /PID %%a 2>nul
     )
 )

  rem IPv6 LISTENING (exact port match: "]:PORT ")
  for /f "tokens=5" %%A in ('netstat -ano -p tcp ^| findstr /R /C:"]:%%P " ^| findstr LISTENING') do (
    echo Killing PID %%A (IPv6)
    taskkill /F /T /PID %%A >nul 2>&1
  )
)
echo.
echo ============================================
echo All dev server stop attempts completed.
echo ============================================
echo.
echo Ports checked: %PORTS%
echo.
echo If servers are still running, try:
echo   1. Run this script as Administrator
echo   2. Check Task Manager for node/python processes
echo   3. Use: netstat -ano ^| findstr :5173
echo.
endlocal
pause