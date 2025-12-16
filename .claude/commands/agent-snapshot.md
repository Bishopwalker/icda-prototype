# Agent Snapshot Command
# Automated pristine state snapshot and RAG mapping

## Purpose
This command is invoked by Claude after creating the implementation plan.
The Agent takes a snapshot of all affected files and builds/updates the RAG dependency map.

## CLI Options

There are two ways to invoke the snapshot system:

### Option 1: RAG Pipeline CLI (Recommended)
```bash
# Basic indexing (creates snapshot of project state)
python .claude/rag/rag_pipeline.py

# Index specific project
python .claude/rag/rag_pipeline.py --project /path/to/project

# Full pipeline with all agents
python .claude/rag/rag_pipeline.py --full

# JSON output for programmatic use
python .claude/rag/rag_pipeline.py --json
```

### Option 2: Bootstrap CLI
```bash
# Run full bootstrap (includes snapshot)
python .claude/rag/bootstrap.py

# Force re-snapshot
python .claude/rag/bootstrap.py --force

# Check current status
python .claude/rag/bootstrap.py --check-only
```

## Invocation

```javascript
// Claude calls this after creating CURRENT_PLAN.md
// Using the RAG pipeline for comprehensive snapshot
exec({
  command: `python .claude/rag/rag_pipeline.py --full`,
  timeout: 120000 // 2 minutes for thorough analysis
})
```

## Your Responsibilities:

1. **Read the Implementation Plan**
   - File: .claude/CURRENT_PLAN.md
   - Extract: All affected files
   - Extract: All new files to be created
   - Extract: Expected changes

2. **Take Pristine Snapshot**
   - Read current content of ALL affected files
   - Store complete file contents
   - Calculate file hashes
   - Record metadata (imports, exports, functions, types)
   - Generate snapshot ID: YYYYMMDD_HHMMSS format

3. **Build/Update RAG Dependency Map**
   - Map all imports → exports relationships
   - Map function call graph (who calls what)
   - Map type dependencies (which types use others)
   - Identify current dead code candidates
   - Identify current unused imports
   - Identify orphaned types

4. **Generate Snapshot Artifacts**
   - Create: .claude/AGENT_SNAPSHOT.json
     ```json
     {
       "snapshot_id": "20251025_143022",
       "task": "[task description]",
       "timestamp": "2025-10-25T14:30:22Z",
       "files": {
         "path/to/file.ts": {
           "path": "path/to/file.ts",
           "hash": "sha256_hash",
           "size": 8547,
           "lines": 303,
           "content": "[full file content as string]",
           "metadata": {
             "imports": ["list of imports"],
             "exports": ["list of exports"],
             "functions": ["list of function names"],
             "classes": ["list of class names"],
             "types": ["list of type names"],
             "interfaces": ["list of interfaces"]
           }
         }
       }
     }
     ```

   - Create/Update: .claude/AGENT_RAG_MAP.json
     ```json
     {
       "rag_map_version": "1.0",
       "generated": "2025-10-25T14:30:25Z",
       "task_context": "[task description]",
       "dependency_graph": {
         "file_path": {
           "imports_from": ["files this imports from"],
           "imported_by": ["files that import this"],
           "exports": ["what this file exports"],
           "functions": {
             "functionName": {
               "parameters": ["param: type"],
               "return_type": "type",
               "called_by": ["file:function pairs"],
               "calls": ["file:function pairs"],
               "affects": ["variables/state it modifies"]
             }
           }
         }
       },
       "function_call_graph": {
         "functionName": {
           "file": "path",
           "line": 123,
           "calls": ["other functions"],
           "called_by": ["calling functions"]
         }
       },
       "type_graph": {
         "TypeName": {
           "file": "path",
           "line": 45,
           "used_by": ["files using this type"],
           "properties": ["property: type"]
         }
       },
       "dead_code_candidates": [],
       "unused_imports": [],
       "orphaned_types": []
     }
     ```

5. **Signal Readiness**
   - Create: .claude/AGENT_STATUS.md
     ```
     # Agent Status

     **Status:** READY FOR EXECUTION
     **Snapshot ID:** 20251025_143022
     **Files Tracked:** 4
     **RAG Map Version:** 1.0
     **Pristine State:** Confirmed

     **Affected Files:**
     - src/utils/AudioMixer.ts
     - src/types/index.ts
     - backend/core/audio_engine.py
     - src/hooks/useHybridAudioEngine.ts

     **Message to Claude:**
     Snapshot complete! All affected files mapped and stored.
     Dependency graph updated with current state.
     Ready for your implementation.
     Proceed when ready! 🎯
     ```

## Context Files to Reference:

- .claude/CURRENT_PLAN.md (input - read this first)
- .claude/RAG_CONTEXT.md (patterns for dependency mapping)
- .claude/INFRASTRUCTURE.md (infrastructure context)

## Working Directory:

[Current project root - use relative paths from project root]

## Success Criteria:

- ✓ All affected files snapshotted
- ✓ File hashes calculated
- ✓ Metadata extracted (imports, exports, functions, types)
- ✓ RAG dependency map created/updated
- ✓ Function call graph built
- ✓ Type dependency graph built
- ✓ Dead code candidates identified
- ✓ Snapshot saved to AGENT_SNAPSHOT.json
- ✓ RAG map saved to AGENT_RAG_MAP.json
- ✓ Status file created (AGENT_STATUS.md)
- ✓ Ready signal sent to Claude

## Important Notes:

- Use relative file paths from project root
- Store COMPLETE file contents in snapshot (for diff later)
- RAG map should capture CURRENT state (before changes)
- Snapshot is read-only archive - don't modify original files
- Be thorough - this is the foundation for enforcement later

## Output Format:

Return a summary of what was snapshotted and confirm readiness.

## Expected Output

Agent should return a summary like:

```
✅ AGENT SNAPSHOT COMPLETE

Snapshot ID: 20251025_143022
Task: Add volume boost mode to AudioMixer

Files Snapshotted: 4
- src/utils/AudioMixer.ts (303 lines, hash: a1b2c3d4)
- src/types/index.ts (666 lines, hash: e5f6g7h8)
- backend/core/audio_engine.py (367 lines, hash: i9j0k1l2)
- src/hooks/useHybridAudioEngine.ts (245 lines, hash: m3n4o5p6)

RAG Map Updated:
- Dependency graph: 48 nodes, 127 edges
- Function call graph: 89 functions
- Type graph: 34 types
- Dead code candidates: 0
- Unused imports: 0

Artifacts Created:
✓ .claude/AGENT_SNAPSHOT.json (487 KB)
✓ .claude/AGENT_RAG_MAP.json (152 KB)
✓ .claude/AGENT_STATUS.md

Status: READY FOR EXECUTION
Message to Claude: Proceed with implementation! 🎯
```

## Troubleshooting

**If Agent fails:**
- Check that CURRENT_PLAN.md exists and is readable
- Verify affected files exist at specified paths
- Check file permissions (need read access)
- Verify working directory is correct

**If RAG map is incomplete:**
- Ensure Agent has access to read all source files
- Check that TypeScript/Python parsing is working
- Verify import/export statements are standard format

**If snapshot too large:**
- Consider excluding node_modules and build artifacts
- Only snapshot files listed in CURRENT_PLAN.md
- Compress snapshot JSON if needed

---

**Last Updated:** 2025-12-11
**Version:** 2.0
**Part of:** Agent Development System
**See:** AGENT_WORKFLOW.md for complete workflow
