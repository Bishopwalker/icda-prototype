# 🤖 Specialized AI Agents

**Domain-expert agents for focused technical assistance**

## 📋 Available Agents

Each agent is a specialized expert with deep knowledge in their domain:

### Technology Domain Agents

| Agent | Command | Domain | Use When |
|-------|---------|--------|----------|
| **Kafka** | `/agent-kafka` | Apache Kafka, event streaming | Working with message brokers, topics, consumers, producers |
| **AWS** | `/agent-aws` | Amazon Web Services | Cloud infrastructure, Lambda, S3, EC2, RDS, etc. |
| **Spring Boot** | `/agent-springboot` | Spring Boot framework | Building REST APIs, configuration, dependency injection |
| **Spring Cloud** | `/agent-springcloud` | Spring Cloud microservices | Service discovery, config server, API gateway, circuit breakers |
| **Docker** | `/agent-docker` | Docker & containerization | Building images, docker-compose, orchestration |

### Code Refactoring & Quality Agents

| Agent | Command | Purpose | Use When |
|-------|---------|---------|----------|
| **Functionality Preservation** | `/agent-preserve` | Ensures no lost functionality | Before/after refactoring to map and verify functions |
| **Code Quality Sentinel** | `/agent-sentinel` | SOLID violations, complexity metrics | Analyzing code quality and architecture |
| **Dependency Graph** | `/agent-depgraph` | Import chains, circular deps | Understanding module relationships |
| **Technical Debt Analyst** | `/agent-debt` | TODOs, missing tests, deprecated code | Finding and prioritizing technical debt |
| **Dead Code Hunter** | `/agent-deadcode` | Unused imports, functions, files | Finding dead code to remove |
| **Redundancy Eliminator** | `/agent-redundancy` | Duplicate code, similar functions | Finding code to consolidate |
| **Code Consolidator** | `/agent-consolidate` | Execute cleanup, create utilities | Actually removing/merging code safely |
| **Documentation (Ultrathink)** | `/agent-document` | Deep analysis, code labeling | Comprehensive code documentation |

## 🎯 How to Use Agents

### Method 1: Slash Commands

```bash
# Technology Domain Agents
/agent-kafka
/agent-aws
/agent-springboot
/agent-springcloud
/agent-docker

# Code Refactoring & Quality Agents
/agent-preserve      # Functionality preservation
/agent-sentinel      # Code quality analysis
/agent-depgraph      # Dependency graph
/agent-debt          # Technical debt
/agent-deadcode      # Dead code hunting
/agent-redundancy    # Redundancy elimination
/agent-consolidate   # Code consolidation
/agent-document      # Documentation (Ultrathink)
```

### Method 2: Direct Context Load

Load the agent context file directly:

```bash
# Example: Loading Kafka agent
cat .github/agents/KAFKA_AGENT.md
```

### Method 3: Combined Context

Load multiple agents for cross-domain work:

```bash
# Example: Spring Boot + Kafka + Docker
cat .github/agents/SPRINGBOOT_AGENT.md \
    .github/agents/KAFKA_AGENT.md \
    .github/agents/DOCKER_AGENT.md
```

## 🧠 Agent Capabilities

### Kafka Agent
- Topic design and partitioning strategies
- Producer/Consumer configuration
- Kafka Streams and ksqlDB
- Schema Registry and Avro
- Performance tuning and monitoring
- Common issues and troubleshooting

### AWS Agent
- Service selection and architecture
- IAM roles and security best practices
- Serverless (Lambda, API Gateway, EventBridge)
- Storage (S3, EFS, EBS)
- Database services (RDS, DynamoDB, Aurora)
- Networking (VPC, Load Balancers, CloudFront)
- Cost optimization strategies

### Spring Boot Agent
- RESTful API design patterns
- Spring Data JPA and repositories
- Spring Security and authentication
- Configuration management (@ConfigurationProperties)
- Exception handling and validation
- Testing (MockMvc, TestRestTemplate)
- Actuator and monitoring

### Spring Cloud Agent
- Microservices architecture patterns
- Service discovery (Eureka, Consul)
- Config Server centralization
- API Gateway (Spring Cloud Gateway)
- Circuit breakers (Resilience4j)
- Distributed tracing (Sleuth, Zipkin)
- Load balancing and fault tolerance

### Docker Agent
- Dockerfile best practices
- Multi-stage builds for optimization
- docker-compose orchestration
- Networking and volumes
- Security hardening
- CI/CD integration
- Kubernetes basics

## 📚 Agent Context Structure

Each agent includes:

1. **Core Concepts** - Fundamental knowledge
2. **Common Patterns** - Best practices and design patterns
3. **Code Examples** - Ready-to-use snippets
4. **Configuration** - Common config patterns
5. **Troubleshooting** - Common issues and solutions
6. **Performance Tips** - Optimization strategies
7. **Security** - Security best practices
8. **Testing** - Testing strategies and examples
9. **Resources** - Documentation links and references

## 🔄 Agent Workflow

1. **Identify Domain** - Which technology are you working with?
2. **Activate Agent** - Use slash command or load context
3. **Ask Questions** - Agent responds with specialized knowledge
4. **Implement Solution** - Agent provides code and guidance
5. **Switch Agents** - Activate different agent as needed

## 🎓 Multi-Agent Scenarios

### Scenario 1: Building a Microservice
**Agents needed:** Spring Boot + Spring Cloud + Docker
```bash
/agent-springboot
# Discuss: Create REST API with Spring Boot
/agent-springcloud
# Discuss: Add service discovery and config server
/agent-docker
# Discuss: Containerize the application
```

### Scenario 2: Event-Driven Architecture
**Agents needed:** Kafka + Spring Boot + AWS
```bash
/agent-kafka
# Discuss: Design event topics and schemas
/agent-springboot
# Discuss: Implement Kafka producer/consumer
/agent-aws
# Discuss: Deploy to AWS with MSK (Managed Kafka)
```

### Scenario 3: Cloud Deployment
**Agents needed:** Docker + AWS
```bash
/agent-docker
# Discuss: Build optimized container image
/agent-aws
# Discuss: Deploy to ECS/EKS with proper networking
```

## 📊 Agent Selection Guide

Use this flowchart to pick the right agent:

```
Working with...
├── Message queues/events? → Kafka Agent
├── Cloud infrastructure? → AWS Agent
├── Building APIs/services? → Spring Boot Agent
├── Microservices coordination? → Spring Cloud Agent
└── Containers/deployment? → Docker Agent
```

## 🚀 Pro Tips

1. **Start Broad, Get Specific** - Begin with general architecture questions, then dive into specifics
2. **One Agent at a Time** - Focus on one domain, then switch contexts
3. **Combine for Integration** - Load multiple agents when working on integration points
4. **Reference Agent Docs** - Each agent has comprehensive examples and patterns
5. **Ask for Code** - Agents provide production-ready code snippets

## 📝 Creating Custom Agents

You can create your own specialized agents:

1. Copy the agent template: `AGENT_TEMPLATE.md`
2. Fill in domain-specific knowledge
3. Add to this README
4. Create a slash command in `.github/commands/`

## 🔗 Related Documentation

- **Main Context**: `.github/copilot-instructions.md` - General development standards
- **Project Setup**: `.github/INITIAL.md` - Project specifications
- **Architecture**: `PLANNING.md` - System architecture
- **Task Tracking**: `TASK.md` - Current tasks

## 🧹 Code Cleanup Pipeline

The refactoring agents work together in a pipeline for safe code cleanup:

```
RECOMMENDED WORKFLOW:

1. /agent-preserve   → Create functionality baseline BEFORE changes
2. /agent-deadcode   → Find all dead/unused code
3. /agent-redundancy → Find all duplicate code
4. /agent-consolidate → Execute cleanup safely
5. /agent-preserve   → Verify no functionality lost
6. /agent-document   → Update documentation

TARGET: 40% codebase reduction while maintaining ALL functionality
```

### Code Cleanup Agent Capabilities

| Agent | Finds | Action |
|-------|-------|--------|
| **Dead Code Hunter** | Unused imports, functions, classes, unreachable code | Generates removal list |
| **Redundancy Eliminator** | Duplicate code, similar functions, repeated patterns | Generates consolidation plan |
| **Code Consolidator** | N/A (executor) | Executes cleanup with verification |

---

**Status:** ✅ Active
**Total Agents:** 13 (5 technology + 8 refactoring)
**Last Updated:** 2025-12-03