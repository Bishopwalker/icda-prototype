# /commit

Stages all changes, creates a concise commit message, and pushes to the remote repository in one operation.

## Usage
```
/commit
```

## Steps
1. Run `git status` to see what files have changed
2. Run `git diff` to understand the changes
3. Stage all modified files with `git add .`
4. Generate a concise commit message based on the changes
5. Commit with the generated message
6. Push to the current branch

## Notes
- The commit message will be automatically generated based on the actual changes
- Will include the Claude Code co-author signature
- Pushes to the current branch's upstream remote