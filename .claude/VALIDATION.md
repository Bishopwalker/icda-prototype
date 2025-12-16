# VALIDATION.md - Universal Quality Checklist

## PRE-COMMIT VALIDATION CHECKLIST
**MANDATORY: Complete ALL items before any commit**

### Code Cleanup (MANDATORY)
- [ ] **Unused imports removed** - zero unused import statements
- [ ] **Unused variables removed** - zero orphaned variable declarations
- [ ] **Unused functions removed** - zero uncalled functions (unless exported)
- [ ] **Debug statements removed** - all console.logs, print statements cleaned up
- [ ] **Commented code removed** - no old commented-out code blocks
- [ ] **Empty functions removed** - no functions with empty implementations
- [ ] **Duplicate code consolidated** - no copy-pasted code blocks

### Testing Requirements
- [ ] **Unit tests exist** - new functionality has corresponding tests
- [ ] **Tests pass locally** - all tests run successfully
- [ ] **Test coverage adequate** - critical paths are tested
- [ ] **Edge cases covered** - error conditions and boundaries tested
- [ ] **Integration tests pass** - if applicable to the change

### Code Quality
- [ ] **Linting passes** - zero linting errors (run lint command from PROJECT_CONFIG.md)
- [ ] **Type checking passes** - zero type errors (if applicable)
- [ ] **Formatting applied** - code formatted with project formatter
- [ ] **No compiler warnings** - zero warnings in build output
- [ ] **File size under 500 lines** - split larger files into modules

### Build & Integration
- [ ] **Local build succeeds** - project builds without errors
- [ ] **Dependencies resolved** - all imports/requires work correctly
- [ ] **Environment variables set** - required config available
- [ ] **Database migrations work** - if schema changes were made
- [ ] **Static assets accessible** - images, fonts, etc. load correctly

### Runtime Verification
- [ ] **Application starts** - dev server runs without errors
- [ ] **Core features work** - primary user flows function correctly
- [ ] **New functionality works** - the specific change operates as expected
- [ ] **No runtime errors** - console/logs show no JavaScript/runtime errors
- [ ] **Performance acceptable** - no significant performance regressions

### CI/CD Pipeline
- [ ] **Pipeline configured** - CI/CD system is setup and accessible
- [ ] **Pipeline passes** - automated tests and builds succeed
- [ ] **Deployment ready** - code can be deployed to target environment
- [ ] **Environment compatibility** - works in target deployment environment

---

## LANGUAGE-SPECIFIC CHECKLISTS
**Customize based on your PROJECT_CONFIG.md**

### TypeScript/JavaScript Projects
- [ ] **TypeScript compilation passes** - `npx tsc --noEmit` succeeds
- [ ] **ESLint passes** - `npm run lint` succeeds
- [ ] **Prettier formatting applied** - `npm run format` or equivalent
- [ ] **Package vulnerabilities checked** - `npm audit` shows no critical issues
- [ ] **Bundle size reasonable** - no unexpected bundle bloat

### Python Projects
- [ ] **Type hints present** - functions have appropriate type annotations
- [ ] **Docstrings written** - public functions have Google-style docstrings
- [ ] **Import organization** - imports sorted and organized properly
- [ ] **Virtual environment active** - using correct Python environment
- [ ] **Requirements up to date** - requirements.txt/poetry.lock current

### Go Projects
- [ ] **Go fmt applied** - code formatted with `gofmt`
- [ ] **Go vet passes** - `go vet` shows no issues
- [ ] **Go modules tidy** - `go mod tidy` applied
- [ ] **Build tags correct** - appropriate build constraints used
- [ ] **Race conditions checked** - `go test -race` if applicable

### Rust Projects
- [ ] **Clippy passes** - `cargo clippy` shows no warnings
- [ ] **Rustfmt applied** - `cargo fmt` applied
- [ ] **Documentation tests pass** - doc examples work correctly
- [ ] **Dependency audit clean** - `cargo audit` shows no vulnerabilities
- [ ] **Feature flags tested** - conditional compilation works correctly

---

## DEPLOYMENT CHECKLIST

### Pre-Production
- [ ] **Secrets secured** - no hardcoded passwords/API keys
- [ ] **Environment config** - production environment variables set
- [ ] **Database ready** - migrations applied, data seeded if needed
- [ ] **Assets optimized** - images compressed, bundles minified
- [ ] **Monitoring configured** - logging and metrics collection setup

### Production Deploy
- [ ] **Backup created** - database/state backed up before deploy
- [ ] **Deployment tested** - deploy process tested in staging
- [ ] **Rollback plan ready** - can revert if deployment fails
- [ ] **Health checks pass** - application responds to health endpoints
- [ ] **User acceptance** - key stakeholder approval obtained

---

## COMMON FAILURE PATTERNS
**Watch out for these issues:**

### Code Issues
- Unused imports accumulating over time
- Debug statements left in production code
- Copy-pasted code instead of shared utilities
- Functions that are never called
- Variables declared but never used

### Testing Issues
- Tests that don't actually test the new functionality
- Mock data that doesn't reflect real scenarios
- Tests that pass but don't cover error cases
- Integration tests that depend on external services

### Build Issues
- Missing dependencies in production
- Environment-specific code that breaks in other environments
- Build artifacts not properly ignored in git
- Configuration that works locally but fails in CI/CD

### Performance Issues
- Memory leaks from unclosed connections
- N+1 database queries
- Large bundle sizes from unnecessary dependencies
- Blocking operations on the main thread

---

**When ALL items are checked, code is ready for commit**
