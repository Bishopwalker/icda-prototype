# PROJECT CONFIGURATION
**Fill this out for each new project - Claude will reference these settings**

## Technology Stack
**Primary Language**: [Python/JavaScript/TypeScript/Go/Rust/Java/C#/etc]
**Framework**: [React/FastAPI/Django/Express/Next.js/Vue/Angular/Flask/etc]
**Package Manager**: [npm/yarn/pnpm/pip/pipenv/poetry/cargo/go mod/maven/etc]

## Development Tools
**Testing Framework**: [Jest/Pytest/Mocha/Vitest/Go test/JUnit/etc]
**Test Runner Command**: [npm test/pytest/go test/mvn test/etc]
**Linting Tool**: [ESLint/Pylint/Flake8/Ruff/golangci-lint/etc]
**Lint Command**: [npm run lint/flake8 ./pylint/golangci-lint run/etc]
**Code Formatter**: [Prettier/Black/gofmt/rustfmt/etc]
**Format Command**: [npm run format/black ./gofmt/cargo fmt/etc]
**Type Checker**: [TypeScript/mypy/None/etc]
**Type Check Command**: [npx tsc --noEmit/mypy ./go build/etc]

## Development Servers
**Frontend Port**: [3000/5173/8080/etc]
**Backend Port**: [8000/3001/9000/etc]
**Database Port**: [5432/3306/27017/6379/etc]
**Frontend Start Command**: [npm run dev/yarn dev/npm start/etc]
**Backend Start Command**: [uvicorn main:app --reload/python manage.py runserver/go run main.go/etc]
**Full Stack Command**: [npm run dev:all/docker-compose up/etc]

## CI/CD & Deployment
**CI/CD Platform**: [GitHub Actions/GitLab CI/Jenkins/CircleCI/etc]
**Build Command**: [npm run build/python setup.py build/go build/mvn package/etc]
**Deployment Platform**: [Vercel/Netlify/AWS/Railway/Heroku/Docker/etc]
**Environment Variables Method**: [.env files/docker-compose.yml/AWS Parameter Store/etc]

## Database & Storage
**Database Type**: [PostgreSQL/MySQL/MongoDB/SQLite/Redis/etc]
**Database URL Format**: [postgresql://user:pass@localhost:5432/dbname]
**Migration Tool**: [Alembic/Django migrations/Prisma/Flyway/etc]
**Migration Command**: [alembic upgrade head/python manage.py migrate/etc]

## Dependencies & Package Installation
**Install Dependencies Command**: [npm install/pip install -r requirements.txt/go mod download/etc]
**Development Dependencies Command**: [npm install --dev/pip install -r requirements-dev.txt/etc]
**Lock File**: [package-lock.json/yarn.lock/requirements.txt/go.mod/etc]

## Environment Setup
**Virtual Environment**: [venv/conda/virtualenv/None/etc]
**Environment Activation**: [source venv/bin/activate/conda activate env/etc]
**Node Version**: [18/20/latest/etc]
**Python Version**: [3.8/3.9/3.10/3.11/etc]
**Go Version**: [1.19/1.20/latest/etc]

## Project-Specific Cleanup Rules
**Language-Specific Unused Code Patterns**:
- Unused imports: [import statements not used/require() not used/etc]
- Unused variables: [let/const/var declarations not referenced/etc]
- Dead code patterns: [unreachable code/unused functions/etc]

**File Extensions to Watch**:
- Source files: [.js/.jsx/.ts/.tsx/.py/.go/.rs/etc]
- Test files: [.test.js/.spec.py/_test.go/etc]
- Config files: [.json/.yaml/.toml/etc]

## Project Structure Notes
**Source Directory**: [src/app/lib/cmd/etc]
**Test Directory**: [tests/__tests__/test/etc]
**Build Output**: [dist/build/target/bin/etc]
**Static Assets**: [public/static/assets/etc]
**Documentation**: [docs/README.md/wiki/etc]

---

## Quick Reference Commands
**Full Development Setup**:
```bash
# Add your common command sequences here
[your install -> setup -> run commands]
```

**Testing**:
```bash
# Add your testing commands here
[your test commands]
```

**Build & Deploy**:
```bash
# Add your build/deploy commands here
[your build/deploy commands]
```
