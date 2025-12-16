@echo off
REM ================================================
REM Git Secret Removal Script for ICDA
REM Run this from the icda-prototype directory
REM ================================================

echo.
echo ========================================
echo  ICDA Git Secret Removal
echo ========================================
echo.

REM Check we're in the right directory
if not exist "main.py" (
    echo ERROR: Run this from the icda-prototype directory!
    pause
    exit /b 1
)

echo Step 1: Removing .env files from git tracking...
git rm --cached .env 2>nul
git rm --cached .env.docker 2>nul  
git rm --cached .env.local 2>nul
echo Done.
echo.

echo Step 2: Installing git-filter-repo...
pip install git-filter-repo
echo.

echo Step 3: Backing up your repo...
xcopy /E /I /H /Y . ..\icda-prototype-backup
echo Backup created at: ..\icda-prototype-backup
echo.

echo Step 4: Removing secrets from git history...
echo This will rewrite ALL commits - you'll need to force push after.
echo.

REM Remove each secret string from history
git filter-repo --replace-text secrets-to-remove.txt --force

echo.
echo ========================================
echo  DONE! 
echo ========================================
echo.
echo NEXT STEPS:
echo 1. ROTATE YOUR AWS CREDENTIALS NOW!
echo    - Go to AWS Console ^> IAM ^> Your User ^> Security Credentials
echo    - Delete the old access key
echo    - Create a new one
echo.
echo 2. ROTATE YOUR DOCKER PAT!
echo    - Go to Docker Hub ^> Account Settings ^> Security
echo    - Delete old PAT, create new one
echo.
echo 3. Force push to remote (if you have one):
echo    git push --force --all
echo.
echo 4. Delete the secrets file:
echo    del secrets-to-remove.txt
echo.
echo 5. Update your .env with NEW credentials
echo.
pause
