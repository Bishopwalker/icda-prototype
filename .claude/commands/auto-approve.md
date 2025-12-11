# /auto-approve

Grants all necessary permissions to Claude for the remainder of the session, allowing autonomous execution of common development tasks without requiring approval for each action.

## Usage
```
/auto-approve
```

## Permissions Granted
The following tools will be auto-approved for the remainder of the session:
- `git add` - Stage files for commit
- `git commit` - Create commits with generated messages
- `git push` - Push changes to remote repository
- `npm install` - Install dependencies
- `npm run build` - Build the project
- `npm run test` - Run tests
- `npm run dev` - Start development server
- `npm run lint` - Run linting
- `npx` commands - Execute npm packages
- `python` - Run Python scripts
- `pip install` - Install Python packages
- `uvicorn` - Start FastAPI server
- `curl` - Make HTTP requests for testing
- File operations (Read, Write, Edit) - Modify project files
- Web searches - Look up documentation and solutions

## Notes
- These permissions last only for the current Claude Code session
- You can still interrupt any operation with Ctrl+C
- This is useful for complex tasks requiring multiple operations
- Helps maintain development flow without constant approval prompts