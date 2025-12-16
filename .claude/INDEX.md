# INDEX.md
# Context Navigation Guide

**📍 Start Here First**

This index provides the optimal reading order and navigation paths for AI assistants working on this project.

## 🚨 URGENT - CHECK FOR SESSION CONTEXT FIRST

**BEFORE reading anything else, check for urgent session context:**
- `URGENT_READ_FIRST.md` - Critical info from previous session (if exists)
- `SESSION_*.md` - Detailed session context files (if any exist)

**If these files exist, READ THEM FIRST before proceeding!**

---

## 🚀 Quick Start (Essential Reading)

### 1. **Automated Context Initialization**
```bash
# Run this command first to auto-load all context
/context-init
```

### 2. **Manual Context Reading Order**
```
0. URGENT_READ_FIRST.md - Check this FIRST (if exists)
1. INDEX.md (this file) ← YOU ARE HERE
2. CLAUDE.md - Development rules & standards
3. INITIAL.md - Project specifications & protocols
4. ../PLANNING.md - Architecture & workflow
5. ../TASK.md - Current sprint work
```

### 3. **For Specific Task Types**

#### 🔧 **New Feature Development**
```
INITIAL.md → PLANNING.md → ../TASK.md → relevant code files
```

#### 🐛 **Bug Fixes**
```
CLAUDE.md → ../TASK.md → test files → source code
```

#### 🏗️ **Infrastructure Changes**
```
INFRASTRUCTURE.md → deployment files → configuration
```

#### 🧪 **Testing & Quality**
```
CLAUDE.md → VALIDATION.md → test files
```

#### 🔄 **Continuing Previous Session**
```
URGENT_READ_FIRST.md → SESSION_*.md → TASK.md → proceed with work
```

## 📁 Context Hierarchy (Authority Order)

### **CRITICAL** (Check First - Session Continuity)
- `.claude/URGENT_READ_FIRST.md` - Critical context from previous session
- `.claude/SESSION_*.md` - Detailed session context and troubleshooting

### **PRIMARY** (Always Authoritative)
- `.claude/CLAUDE.md` - Development standards, testing requirements, Git workflow
- `.claude/INITIAL.md` - Technical specifications, project requirements, examples
- `.claude/INFRASTRUCTURE.md` - Environment setup, deployment configuration

### **SECONDARY** (Project Management)
- `../PLANNING.md` - Architecture decisions, naming conventions, workflows
- `../TASK.md` - Current sprint work, completed tasks, known issues
- `VALIDATION.md` - Quality checklists and validation requirements

### **REFERENCE** (Supporting Documentation)
- `CONTEXT_ENGINEERING.md` - Meta-documentation about context practices
- `SETUP_COMPLETE.md` - Setup completion checklist
- Project-specific documentation files

### **AUTOMATION** (Commands & Templates)
- `commands/*.md` - Automation scripts and workflows
- `commands/agent-*.md` - Specialized agent activation commands
- `templates/*.md` - Process templates and procedures

### **AGENTS** (Specialized Domain Experts)
- `agents/README.md` - Agent system overview
- `agents/AGENT_GUIDE.md` - Complete usage guide

**Technology Domain Agents:**
- `agents/KAFKA_AGENT.md` - Apache Kafka expert (800+ lines)
- `agents/AWS_AGENT.md` - Amazon Web Services expert (800+ lines)
- `agents/SPRINGBOOT_AGENT.md` - Spring Boot expert (1000+ lines)
- `agents/SPRINGCLOUD_AGENT.md` - Spring Cloud expert (800+ lines)
- `agents/DOCKER_AGENT.md` - Docker & containers expert (800+ lines)

**Code Refactoring & Quality Agents:**
- `agents/FUNCTIONALITY_PRESERVE_AGENT.md` - Ensures no lost functionality
- `agents/CODE_QUALITY_SENTINEL_AGENT.md` - SOLID principles, complexity metrics
- `agents/DEPENDENCY_GRAPH_AGENT.md` - Import chains, circular dependencies
- `agents/TECHNICAL_DEBT_ANALYST_AGENT.md` - TODOs, missing tests, debt tracking
- `agents/DEAD_CODE_HUNTER_AGENT.md` - Unused imports, functions, files
- `agents/REDUNDANCY_ELIMINATOR_AGENT.md` - Duplicate code detection
- `agents/CODE_CONSOLIDATOR_AGENT.md` - Safe code cleanup execution
- `agents/DOCUMENTATION_AGENT.md` - Ultrathink deep analysis & documentation

## 🎯 Task-Specific Navigation

### **Frontend Development**
1. `CLAUDE.md` - Component standards and naming conventions
2. `PLANNING.md` - Frontend architecture patterns
3. Project source files
4. `../TASK.md` - Frontend-related current tasks

### **Backend Development**
1. `CLAUDE.md` - Backend standards and testing requirements
2. `INITIAL.md` - API specifications and protocols
3. Backend source files
4. Test suite

### **Deployment & Infrastructure**
1. `INFRASTRUCTURE.md` - Complete deployment guide
2. CI/CD configuration files
3. Docker/deployment configurations

## 🤖 Specialized Agents

### **Domain-Expert Agents Available**

Activate specialized AI agents for focused technical assistance:

**Technology Domain Agents:**
```bash
/agent-kafka          # Apache Kafka & event streaming expert
/agent-aws            # Amazon Web Services & cloud infrastructure expert
/agent-springboot     # Spring Boot & REST API expert
/agent-springcloud    # Spring Cloud & microservices expert
/agent-docker         # Docker & containerization expert
```

**Code Refactoring & Quality Agents:**
```bash
/agent-preserve       # Functionality preservation (before/after refactoring)
/agent-sentinel       # Code quality, SOLID principles, complexity
/agent-depgraph       # Dependency graph, circular dependencies
/agent-debt           # Technical debt analysis
/agent-deadcode       # Dead code hunting
/agent-redundancy     # Duplicate code detection
/agent-consolidate    # Safe code cleanup execution
/agent-document       # Ultrathink documentation
```

### **Agent Navigation Path**
1. **Start**: `agents/README.md` - Overview of all agents
2. **Usage Guide**: `agents/AGENT_GUIDE.md` - How to use agents effectively
3. **Activate**: `/agent-[name]` - Slash command to activate specific agent
4. **Context**: `agents/[NAME]_AGENT.md` - Full agent knowledge base

### **When to Use Agents**

#### **Building Microservices Architecture**
```
/agent-springboot → /agent-kafka → /agent-docker → /agent-aws → /agent-springcloud
```

#### **Event-Driven Systems**
```
/agent-kafka → /agent-springboot → /agent-aws
```

#### **Cloud Deployment**
```
/agent-docker → /agent-aws
```

#### **Troubleshooting**
- Kafka issues: `/agent-kafka`
- Spring Boot problems: `/agent-springboot`
- Container issues: `/agent-docker`
- AWS infrastructure: `/agent-aws`
- Microservices coordination: `/agent-springcloud`

#### **Code Cleanup Pipeline**
```
/agent-preserve → /agent-deadcode → /agent-redundancy → /agent-consolidate → /agent-preserve → /agent-document
```
Target: 40% codebase reduction while maintaining ALL functionality

#### **Code Analysis**
- Quality issues: `/agent-sentinel`
- Technical debt: `/agent-debt`
- Dependencies: `/agent-depgraph`
- Documentation: `/agent-document`

**See `agents/AGENT_GUIDE.md` for complete usage patterns and examples.**

---

## 🔍 Quick Reference Lookup

### **Find Code Patterns**
- Project-specific file locations
- Test file locations
- Configuration files

### **Common Issues & Solutions**
- Build failures
- Test failures
- Deployment issues
- Development environment problems

### **External Documentation Links**
- Add relevant framework/library documentation links
- Add relevant tool documentation links

## ⚠️ Important Notes

### **File Authority**
- `.claude/` directory files are **authoritative**
- Root directory may contain backup or symlinked versions
- When in doubt, use the `.claude/` version

### **Session Continuity**
- **ALWAYS check for URGENT_READ_FIRST.md** when starting a new session
- **Read SESSION_*.md files** for context from previous troubleshooting
- **Update session context files** when making significant infrastructure changes
- **User may be waiting for actions** mentioned in session context (e.g., restart required)

### **Context Validation**
Before starting work, ensure:
- [ ] Check for URGENT_READ_FIRST.md
- [ ] Read any SESSION_*.md context files
- [ ] Latest code pulled from repository
- [ ] Development environment running
- [ ] All tests passing locally
- [ ] Current task status checked in `../TASK.md`

### **Emergency Context Recovery**
If you lose context or get confused:
1. **Check URGENT_READ_FIRST.md** for immediate context
2. **Re-read this INDEX.md file**
3. **Check `../TASK.md` for current work status**
4. **Review `CLAUDE.md` for development standards**
5. **Read SESSION_*.md for recent troubleshooting**
6. **Ask for clarification rather than making assumptions**

---

**📋 Context Health Status**
- ✅ Primary files present and up-to-date
- ✅ Navigation paths established
- ✅ Task tracking system active
- ✅ Validation processes defined
- ✅ Session continuity system implemented

**Last Updated:** 2025-12-03
**Context Version:** 3.0
**Features:** Core context + RAG system + 13 specialized agents (5 technology + 8 refactoring)