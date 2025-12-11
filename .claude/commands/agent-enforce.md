# Agent Enforcement Command
# Automated code quality enforcement and cleanup

## Purpose
This command is invoked by Claude after implementation is complete.
The Enforcer Agent compares changes against the snapshot, enforces quality standards, and returns code to pristine state.

## CLI Options

There are two ways to invoke the enforcement system:

### Option 1: RAG Pipeline CLI (Recommended)
```bash
# Basic enforcement with agent analysis
python .claude/rag/rag_pipeline.py --full

# Full enforcement with AI validation
python .claude/rag/rag_pipeline.py --full --enforce

# Validate all chunks (thorough but slower)
python .claude/rag/rag_pipeline.py --full --enforce --validate-all

# JSON output for programmatic use
python .claude/rag/rag_pipeline.py --full --json
```

### Option 2: Bootstrap CLI
```bash
# Run bootstrap with enforcement
python .claude/rag/bootstrap.py --force

# Check status only
python .claude/rag/bootstrap.py --check-only

# Interactive mode
python .claude/rag/bootstrap.py --interactive
```

## Invocation

```javascript
// Claude calls this after implementation complete
// Using the RAG pipeline for comprehensive enforcement
exec({
  command: `python .claude/rag/rag_pipeline.py --full --enforce`,
  timeout: 180000 // 3 minutes for thorough enforcement
})
```

## Your Responsibilities:

1. **Load Context**
   - Read: .claude/AGENT_SNAPSHOT.json (pristine state before changes)
   - Read: .claude/AGENT_RAG_MAP.json (dependency map before changes)
   - Read: .claude/CURRENT_PLAN.md (what was supposed to be done)
   - Read: .claude/CLAUDE_STATUS.md (Claude's implementation notes)

2. **Compare Against Snapshot**
   - For each affected file:
     - Read current state
     - Compare vs snapshot
     - Identify: Added code
     - Identify: Modified code
     - Identify: Deleted code
     - Identify: Suspicious patterns (debug logs, TODOs, dead code)

3. **Validate Functionality**
   - ✓ No functionality reduced (all existing features work)
   - ✓ New functionality works as expected
   - ✓ All tests still passing
   - ✓ No breaking changes to public APIs
   - ✓ Performance maintained or improved

4. **Enforce Quality Standards**

   **From CLAUDE.md:**
   - ❌ Remove: console.log / print debug statements
   - ❌ Remove: Commented out dead code
   - ❌ Remove: Unused imports
   - ❌ Remove: Unused functions/classes
   - ❌ Remove: Temporary test files
   - ✓ Ensure: Google-style docstrings on all new functions
   - ✓ Ensure: Type hints on all Python code
   - ✓ Ensure: TypeScript strict mode compliance
   - ✓ Ensure: Files under 500 lines (refactor if over)
   - ✓ Ensure: Tests exist for new features
   - ❌ Resolve: TODOs (implement or track in TASK.md)

   **From VALIDATION.md:**
   - ✓ TypeScript strict mode compliant
   - ✓ ESLint/Prettier formatting applied
   - ✓ Python Black/isort formatting applied
   - ✓ No secrets committed (API keys, tokens, passwords)
   - ✓ Security: SQL injection prevention
   - ✓ Security: XSS prevention
   - ✓ Performance: No significant regression
   - ✓ Memory: No leaks (especially WebSocket)

   **From INFRASTRUCTURE.md:**
   - ✓ Environment variables used (no hardcoded config)
   - ✓ CI/CD pipeline compatible
   - ✓ Monitoring/metrics integration maintained

   **From RAG_CONTEXT.md:**
   - ✓ All imports resolve correctly
   - ✓ Type definitions updated
   - ✓ Dependency graph valid
   - ✓ No circular dependencies introduced

5. **Apply Cleanup & Fixes**

   **Remove:**
   - All debug console.log/print statements
   - All commented-out code blocks
   - All unused imports
   - All dead functions/classes
   - All temporary/test files created during development

   **Add:**
   - Missing docstrings (Google-style)
   - Missing type hints
   - Missing error handling where needed

   **Refactor:**
   - Extract duplicate code into utilities
   - Split files >500 lines
   - Simplify complex functions (>50 lines)

   **Fix:**
   - Type errors
   - Linting issues
   - Security vulnerabilities
   - Performance bottlenecks

6. **Update RAG Map**
   - Add new functions to call graph
   - Add new types to type graph
   - Update dependency graph
   - Remove dead code from graph
   - Update function affects/called_by relationships

7. **Validate After Cleanup**
   - Run: npm run lint (must pass)
   - Run: npm run typecheck (must pass)
   - Run: npm run test:ci (must pass)
   - Run: python -m pytest backend/ (must pass)
   - Verify: Live app still works

8. **Generate Enforcement Report**
   - Create: .claude/AGENT_REPORT.md (see template below)
   - Include: Russian Olympic Judge score (0-10)
   - Include: All cleanup actions taken
   - Include: All validation results
   - Include: Files in pristine state confirmation

## AGENT_REPORT.md Template:

```markdown
# Agent Enforcement Report

**Task:** [Task description]
**Snapshot ID:** [ID]
**Enforcement Date:** [ISO-8601 timestamp]
**Status:** ✅ PRISTINE STATE ACHIEVED / ❌ ISSUES REMAIN

---

## Changes Summary

**Files Modified:** X
- [list of files]

**New Files:** X
- [list of new files]

**Files Deleted:** X
- [list if any]

---

## Cleanup Actions Performed

### [filename]
✅ **Removed:**
- X debug console.log statements
- X lines of commented dead code
- X unused imports

✅ **Added:**
- Google-style docstrings for X functions
- Type annotations for X parameters

✅ **Refactored:**
- Extracted duplicate logic into [utility function]

---

## Validation Results

### Code Quality ✅
- [x] No unused imports
- [x] No dead code
- [x] No console.log/debug statements
- [x] All functions documented
- [x] Type safety maintained
- [x] ESLint/Prettier compliant
- [x] Python PEP8 compliant

### Functionality ✅
- [x] All existing features work
- [x] New features work
- [x] No functionality reduced

### Testing ✅
- [x] Unit tests: XX/XX passing
- [x] Integration tests: XX/XX passing
- [x] Live app test: Passed

### Standards Compliance ✅
- [x] CLAUDE.md standards met
- [x] VALIDATION.md checklist passed
- [x] INFRASTRUCTURE.md requirements met
- [x] RAG_CONTEXT.md mapping updated

### Performance ✅
- [x] Bundle size: Within target
- [x] Response time: Within limits
- [x] Memory usage: Within limits

---

## Russian Olympic Judge Score: X.X/10 🏅

**Deductions:**
- -X.X: [Reason for each deduction]

**Strengths:**
- [What was done well]

---

## Files in Pristine State

✅ All affected files returned to production-ready state
✅ No regression introduced
✅ Ready for commit and deployment

---

## Issues Found (If Any)

### Critical (Must Fix)
- [Issue 1]

### Warning (Should Fix)
- [Issue 1]

### Info (Nice to Have)
- [Issue 1]

---

## Next Steps

1. **Claude:** Review this report
2. **Both:** Final validation together
3. **Claude:** Update TASK.md
4. **Both:** Commit if pristine
5. **Both:** Celebrate! 🎉

---

**Agent Status:** [COMPLETE / NEEDS REVIEW]
```

## Context Files to Reference:

**Quality Standards:**
- .claude/CLAUDE.md
- .claude/VALIDATION.md
- .claude/INFRASTRUCTURE.md
- .claude/RAG_CONTEXT.md

**State Files:**
- .claude/AGENT_SNAPSHOT.json (pristine state)
- .claude/AGENT_RAG_MAP.json (dependency map)
- .claude/CURRENT_PLAN.md (what was planned)
- .claude/CLAUDE_STATUS.md (implementation notes)

## Russian Olympic Judge Standard:

**Scoring Guide:**
- **10.0:** Perfect. Zero flaws. Production-ready perfection.
- **9.5-9.9:** Excellent. Minor style inconsistencies only.
- **9.0-9.4:** Very good. Small issues that don't affect functionality.
- **8.0-8.9:** Good. Some cleanup needed but solid implementation.
- **7.0-7.9:** Acceptable. Noticeable issues that should be fixed.
- **<7.0:** Needs work. Significant problems found.

**Deduction Examples:**
- -0.1: Single debug log left
- -0.2: Multiple debug logs or one TODO unresolved
- -0.5: Dead code or unused import
- -1.0: Missing docstrings or type hints
- -2.0: Security vulnerability
- -5.0: Functionality reduced or broken tests

## Success Criteria:

**Minimum for "Pristine State":**
- ✓ Score ≥9.0/10
- ✓ All tests passing
- ✓ No dead code
- ✓ No unused imports
- ✓ No debug statements
- ✓ All functions documented
- ✓ Type safety complete
- ✓ Performance maintained

**If Score <9.0:**
- List specific issues in report
- Provide fix recommendations
- Do NOT mark as pristine
- Claude must address issues

## Working Directory:

[Current project root - use relative paths from project root]

## Important Notes:

- **NEVER reduce functionality** - only improve quality
- **Be ruthless about dead code** - if not used, delete it
- **Maintain RAG map accuracy** - critical for future tasks
- **Russian Olympic Judge mode** - criticize anything less than perfect
- **Clear communication** - reports must be actionable

## Output Format:

Return the enforcement report and confirm pristine state (or list issues).

---

**Last Updated:** 2025-12-11
**Version:** 2.0
**Part of:** Agent Development System
**See:** AGENT_WORKFLOW.md for complete workflow
