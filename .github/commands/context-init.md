# Context Initialization Automation
# Auto-executes mandatory context reading workflow AND bootstraps RAG system

## 🚀 Auto-Bootstrap System

**On first run, this command will automatically:**
1. Detect project type (Java/Spring, Python, Node, etc.)
2. Install RAG dependencies if missing
3. Index the codebase for semantic search
4. Analyze project conventions
5. Create initialization marker
6. Display RAG index statistics

**Subsequent runs skip bootstrap and just load context with stats.**

## Startup Display (Always Runs First)

```python
# Display RAG stats on startup
import subprocess
import sys
import os
from pathlib import Path

project_root = os.getcwd()
startup_script = Path(project_root) / ".github" / "rag" / "startup_display.py"

if startup_script.exists():
    subprocess.run([sys.executable, str(startup_script), "-p", project_root])
```

## Bootstrap Check

```python
# Check if bootstrap needed and run it
import subprocess
import sys
import os
from pathlib import Path

project_root = os.getcwd()
marker_file = Path(project_root) / ".github" / ".initialized"
bootstrap_script = Path(project_root) / ".github" / "rag" / "bootstrap.py"

if not marker_file.exists() and bootstrap_script.exists():
    print("🚀 First run detected - initializing RAG system...")
    print("=" * 50)
    result = subprocess.run(
        [sys.executable, str(bootstrap_script), "--project-root", project_root],
        capture_output=False
    )
    print("=" * 50)
    if result.returncode == 0:
        print("✅ Bootstrap complete!")
    else:
        print("⚠️ Bootstrap had issues - check BOOTSTRAP_STATUS.json")
else:
    print("✅ Project already initialized")
```

## Mandatory Context Files (Execute in Order)
1. .github/INDEX.md - Navigation guide
2. .github/copilot-instructions.md - Development standards
3. .github/INITIAL.md - Technical specifications
4. PLANNING.md - Architecture & workflow
5. TASK.md - Current sprint work

## Auto-Execution Commands
```bash
# Read all mandatory context files in proper order
echo "=== CONTEXT INITIALIZATION ==="
echo "Reading mandatory context files..."

echo "1/5: INDEX.md (Navigation Guide)"
cat .github/INDEX.md

echo "2/5: copilot-instructions.md (Development Standards)"
cat .github/copilot-instructions.md

echo "3/5: INITIAL.md (Technical Specifications)"
cat .github/INITIAL.md

echo "4/5: PLANNING.md (Architecture)"
cat PLANNING.md

echo "5/5: TASK.md (Current Tasks)"
cat TASK.md

echo "=== CONTEXT LOADED - READY FOR WORK ==="
```

## RAG System Status Check
```python
# Check RAG system status with Context7 integration
import json
from pathlib import Path

status_file = Path(".github/BOOTSTRAP_STATUS.json")
mcp_file = Path(".mcp.json")

if status_file.exists():
    with open(status_file) as f:
        status = json.load(f)
    print(f"📊 RAG Status:")
    print(f"   - Initialized: {status.get('initialized', False)}")
    print(f"   - Files indexed: {status.get('files_indexed', 0)}")
    print(f"   - Project type: {status.get('project_type', 'unknown')}")
    print(f"   - Conventions analyzed: {status.get('conventions_analyzed', False)}")
else:
    print("⚠️ RAG system not initialized - run bootstrap")

# Check Context7 status
if mcp_file.exists():
    with open(mcp_file) as f:
        mcp_config = json.load(f)
    if "context7" in mcp_config.get("mcpServers", {}):
        print(f"🌐 Context7: ✅ Enabled (auto-fallback for external docs)")
        print(f"   Tip: Add 'use context7' to any query for live documentation")
    else:
        print(f"🌐 Context7: ❌ Not configured")
else:
    print(f"🌐 Context7: ❌ No .mcp.json found")
```

## Usage
- Execute at start of every conversation
- First run automatically bootstraps RAG system
- Required before any development work
- Ensures proper context foundation
- Prevents time waste from missing context

## Manual Bootstrap Commands
```bash
# Force reinitialize RAG system
python .github/rag/bootstrap.py --force

# Check initialization status only
python .github/rag/bootstrap.py --check-only

# Interactive mode (runs project wizard)
python .github/rag/bootstrap.py --interactive
```

## Validation Checklist
- [ ] Bootstrap completed (check .github/.initialized)
- [ ] All 5 context files read successfully
- [ ] RAG system indexed codebase
- [ ] Current task status understood
- [ ] Development standards internalized
- [ ] Architecture patterns clear
- [ ] Technical specs referenced

## Troubleshooting

### "RAG dependencies not installed"
```bash
pip install -r .github/rag/rag_requirements.txt
```

### "Bootstrap failed"
Check `.github/BOOTSTRAP_STATUS.json` for error details.

### "Index empty"
Ensure your project has source code files. The RAG system indexes:
- `.py`, `.java`, `.ts`, `.js`, `.tsx`, `.jsx` files
- Skips `node_modules`, `venv`, `build`, etc.
