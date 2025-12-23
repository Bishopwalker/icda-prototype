@echo off
cd /d C:\Users\bisho\IdeaProjects\icda-prototype
"C:\Program Files\Git\cmd\git.exe" status
echo.
echo === WORKTREES ===
"C:\Program Files\Git\cmd\git.exe" worktree list
echo.
echo === BRANCH ===
"C:\Program Files\Git\cmd\git.exe" branch -v
