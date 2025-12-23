@echo off
REM Git cleanup and commit script for ICDA project
REM Run this from the icda-prototype directory

cd /d C:\Users\bisho\IdeaProjects\icda-prototype

echo ========================================
echo  ICDA Git Cleanup Script
echo ========================================
echo.

REM Show current branch
echo Current branch:
git branch --show-current
echo.

REM Show git status
echo Git Status:
git status --short
echo.

REM List all worktrees
echo Current Worktrees:
git worktree list
echo.

REM Stage all changes
echo Staging all changes...
git add -A

REM Show what's staged
echo.
echo Staged changes:
git diff --cached --stat
echo.

REM Commit with message
echo Committing changes...
git commit -m "feat: Fix model routing - add Micro/Lite/Pro tiered routing

- Fixed ModelRouter to properly route to Pro/Lite/Micro based on complexity
- Added model_config parameter to NovaClient for routing settings  
- Updated main.py to pass model routing config from .env
- Added complexity_metrics to API response for live visibility
- Created test_model_routing.py for routing verification
- Updated .env with proper 3-tier model configuration

Routing triggers:
- PRO: COMPLEX queries, analysis/comparison intents, low confidence, multi-part, SQL keywords
- LITE: MEDIUM complexity, large result sets (>100)
- MICRO: SIMPLE queries with high confidence (fast path)"

echo.
echo ========================================
echo  Cleaning up worktrees
echo ========================================

REM Prune stale worktrees (removes references to non-existent directories)
echo Pruning stale worktrees...
git worktree prune -v

REM List worktrees after prune
echo.
echo Worktrees after cleanup:
git worktree list
echo.

REM Check for claude-worktrees directory and clean it
echo Checking for stale Claude worktrees...
if exist "C:\Users\bisho\.claude-worktrees\icda-prototype" (
    echo Found Claude worktrees directory. Contents:
    dir /b "C:\Users\bisho\.claude-worktrees\icda-prototype" 2>nul
    echo.
    echo To remove all Claude worktrees, run:
    echo   rmdir /s /q "C:\Users\bisho\.claude-worktrees\icda-prototype"
    echo Then run: git worktree prune
) else (
    echo No Claude worktrees directory found.
)

echo.
echo ========================================
echo  Done! 
echo ========================================
echo.
echo To push to remote, run:
echo   git push origin withClaude
echo.

pause
