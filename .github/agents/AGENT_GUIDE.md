# 🤖 Specialized Agent System - User Guide

**Domain experts at your fingertips - activate specialized AI agents for focused technical assistance**

## 🎯 What Are Agents?

Agents are specialized AI assistants with deep expertise in specific technologies. When you activate an agent, the AI focuses exclusively on that domain with comprehensive knowledge of best practices, patterns, and solutions.

Think of agents as having different team members to consult:
- **Kafka Agent** = Your event streaming architect
- **AWS Agent** = Your cloud infrastructure expert
- **Spring Boot Agent** = Your REST API specialist
- **Spring Cloud Agent** = Your microservices architect
- **Docker Agent** = Your containerization guru

## 🚀 Quick Start

### Activate an Agent

Simply use the slash command for the technology you're working with:

```bash
/agent-kafka          # Activate Kafka expert
/agent-aws            # Activate AWS expert
/agent-springboot     # Activate Spring Boot expert
/agent-springcloud    # Activate Spring Cloud expert
/agent-docker         # Activate Docker expert
```

### Example Workflow

```bash
# You're building a microservice
/agent-springboot
"Create a REST API for user management with CRUD operations"

# Now you need to containerize it
/agent-docker
"Create an optimized Dockerfile for this Spring Boot app"

# Deploy to AWS
/agent-aws
"Deploy this container to ECS Fargate with auto-scaling"

# Add event streaming
/agent-kafka
"Publish user creation events to Kafka"
```

## 📚 Agent Capabilities

### 🚀 Kafka Agent

**Expertise:**
- Topic design and partitioning strategies
- Producer/Consumer configuration and optimization
- Kafka Streams for stream processing
- Schema Registry and Avro
- Exactly-once semantics and transactional processing
- Performance tuning and monitoring
- Troubleshooting consumer lag, rebalancing issues

**When to Use:**
- Designing event-driven architectures
- Implementing message producers/consumers
- Building real-time stream processing
- Debugging Kafka issues
- Optimizing throughput and latency

**Example Questions:**
- "How do I implement exactly-once semantics in Kafka?"
- "What's the best partition strategy for user events?"
- "Help me troubleshoot consumer lag"
- "Show me how to implement the Saga pattern with Kafka"

---

### ☁️ AWS Agent

**Expertise:**
- Service selection and architecture design
- Infrastructure as Code (CloudFormation, CDK, Terraform)
- Serverless architectures (Lambda, API Gateway, EventBridge)
- Container orchestration (ECS, EKS, Fargate)
- Database services (RDS, DynamoDB, Aurora)
- Networking (VPC, subnets, security groups)
- IAM roles and security best practices
- Cost optimization strategies

**When to Use:**
- Designing cloud architectures
- Choosing between AWS services
- Writing Infrastructure as Code
- Implementing serverless solutions
- Setting up CI/CD pipelines
- Optimizing AWS costs

**Example Questions:**
- "Should I use Lambda or ECS for this microservice?"
- "Create a CloudFormation template for a 3-tier web app"
- "How do I set up a VPC with public and private subnets?"
- "What's the best way to deploy Spring Boot to AWS?"

---

### 🍃 Spring Boot Agent

**Expertise:**
- REST API development and design patterns
- Spring Data JPA (repositories, entities, relationships)
- Spring Security (authentication, authorization, JWT, OAuth2)
- Exception handling and validation
- Testing (unit, integration, MockMvc, TestContainers)
- Actuator and monitoring
- Configuration management
- Performance optimization

**When to Use:**
- Building REST APIs
- Implementing authentication/authorization
- Working with databases via Spring Data JPA
- Writing tests for Spring applications
- Troubleshooting Spring Boot issues
- Optimizing application performance

**Example Questions:**
- "Create a REST API for order management"
- "Implement JWT authentication with Spring Security"
- "How do I solve the N+1 query problem?"
- "Show me how to write integration tests with TestContainers"

---

### ☁️ Spring Cloud Agent

**Expertise:**
- Microservices architecture patterns
- Service Discovery (Eureka, Consul)
- API Gateway (Spring Cloud Gateway)
- Configuration Server (Spring Cloud Config)
- Circuit Breakers (Resilience4j)
- Distributed Tracing (Sleuth, Zipkin)
- Load balancing and fault tolerance
- Inter-service communication (Feign, WebClient)
- Saga pattern for distributed transactions

**When to Use:**
- Designing microservices architectures
- Implementing service discovery
- Setting up API gateways
- Implementing circuit breakers and resilience
- Coordinating distributed transactions
- Troubleshooting microservices issues

**Example Questions:**
- "Set up Eureka service discovery for my microservices"
- "Implement circuit breakers with Resilience4j"
- "How do I coordinate a distributed transaction with the Saga pattern?"
- "Configure Spring Cloud Gateway with rate limiting"

---

### 🐳 Docker Agent

**Expertise:**
- Dockerfile best practices and optimization
- Multi-stage builds for minimal images
- Docker Compose for multi-container apps
- Networking (bridge, overlay, custom networks)
- Volumes and data persistence
- Docker Swarm for orchestration
- Kubernetes basics (pods, services, deployments)
- Security hardening
- CI/CD integration

**When to Use:**
- Creating Dockerfiles
- Optimizing container images
- Setting up local development with Docker Compose
- Containerizing applications
- Implementing CI/CD with Docker
- Troubleshooting container issues

**Example Questions:**
- "Create an optimized Dockerfile for my Spring Boot app"
- "Set up Docker Compose with PostgreSQL, Redis, and Kafka"
- "How do I reduce my Docker image size?"
- "Implement multi-stage builds for production"

## 🎓 Usage Patterns

### Pattern 1: Single Technology Focus

Use when working deeply on one technology:

```bash
/agent-springboot
"I need to implement these features:
1. User registration with email verification
2. JWT authentication
3. Role-based authorization
4. Password reset flow
Guide me through each one."
```

The agent will stay focused on Spring Boot throughout the conversation.

### Pattern 2: Technology Stack

Switch agents as you work through your stack:

```bash
# Step 1: Build the API
/agent-springboot
"Create a REST API for product management"

# Step 2: Add messaging
/agent-kafka
"Publish product events when CRUD operations occur"

# Step 3: Containerize
/agent-docker
"Create a production-ready Dockerfile"

# Step 4: Deploy
/agent-aws
"Deploy to ECS Fargate with RDS database"
```

### Pattern 3: Integration Points

Use multiple agents for integration scenarios:

```bash
# Spring Boot + Kafka integration
/agent-springboot
"Set up Spring Kafka configuration"

/agent-kafka
"What are the best practices for Kafka in microservices?"

# AWS + Docker integration
/agent-docker
"Build container for AWS deployment"

/agent-aws
"Deploy this container to ECS"
```

### Pattern 4: Troubleshooting

Activate the relevant agent when debugging:

```bash
/agent-kafka
"Consumer lag is growing, help me diagnose and fix it"

/agent-springboot
"Getting LazyInitializationException, how do I resolve it?"

/agent-aws
"ECS tasks keep failing health checks, what's wrong?"
```

## 💡 Best Practices

### 1. **Start Specific, Then Go Broad**

**Good:**
```
/agent-springboot
"Create a User entity with JPA relationships to Orders and Addresses"
```

**Not Optimal:**
```
/agent-springboot
"Help me with my application"
```

### 2. **Provide Context**

**Good:**
```
/agent-kafka
"I have a Spring Boot app that needs to publish order events.
We're using Kafka 3.5, need exactly-once semantics,
and expect 10k messages/sec throughput."
```

**Not Optimal:**
```
/agent-kafka
"How do I use Kafka?"
```

### 3. **Switch Agents at Integration Points**

When technologies interact, switch to the appropriate agent:

```bash
# Building Spring Boot + Kafka application
/agent-springboot      # For Spring configuration
/agent-kafka           # For Kafka specifics
/agent-springboot      # Back to Spring for testing
```

### 4. **Use Agents for Code Review**

```bash
/agent-springboot
"Review this controller implementation for best practices:
[paste code]"
```

### 5. **Leverage Agent Expertise for Architecture**

```bash
/agent-aws
"I need to deploy 5 microservices with auto-scaling,
a shared PostgreSQL database, Redis cache, and Kafka.
Design the AWS architecture."
```

## 🔄 Agent Switching

### When to Switch Agents

**Switch agents when:**
- Moving from application code to infrastructure
- Changing technology layers (API → messaging → deployment)
- Debugging technology-specific issues
- Seeking domain-specific expertise

**Example Flow:**
1. `/agent-springboot` - Build REST API
2. `/agent-kafka` - Add event streaming
3. `/agent-docker` - Containerize
4. `/agent-aws` - Deploy infrastructure
5. `/agent-springcloud` - Add service discovery

### Staying with One Agent

**Stay with one agent when:**
- Deep-diving into one technology
- Following a multi-step tutorial
- Troubleshooting a specific issue
- Learning a technology systematically

## 📊 Decision Matrix

Use this to choose the right agent:

| Task | Agent |
|------|-------|
| Building REST APIs | Spring Boot |
| Implementing microservices patterns | Spring Cloud |
| Event-driven architecture | Kafka |
| Cloud infrastructure | AWS |
| Containerization | Docker |
| Database design | Spring Boot |
| Service discovery | Spring Cloud |
| Message queues | Kafka |
| Serverless functions | AWS |
| Container orchestration | Docker |
| Authentication/Authorization | Spring Boot |
| Circuit breakers | Spring Cloud |
| Cost optimization | AWS |
| Image optimization | Docker |

## 🎯 Real-World Scenarios

### Scenario 1: Building a New Microservice

```bash
# Phase 1: Core API
/agent-springboot
"Create a RESTful API for order management with:
- Order CRUD operations
- Spring Data JPA with PostgreSQL
- Input validation
- Exception handling"

# Phase 2: Events
/agent-kafka
"Publish events when orders are created/updated/cancelled"

# Phase 3: Containerization
/agent-docker
"Create production Dockerfile with health checks"

# Phase 4: Deployment
/agent-aws
"Deploy to ECS Fargate with:
- Application Load Balancer
- Auto-scaling (2-10 tasks)
- RDS PostgreSQL Multi-AZ"

# Phase 5: Service Mesh
/agent-springcloud
"Add to existing microservices:
- Register with Eureka
- Add circuit breakers
- Implement distributed tracing"
```

### Scenario 2: Performance Optimization

```bash
/agent-springboot
"Application has N+1 query problems. Help me optimize."

/agent-kafka
"Kafka consumer lag is growing. Diagnose and fix."

/agent-aws
"RDS costs are too high. Suggest optimizations."

/agent-docker
"Container startup is slow. Optimize the image."
```

### Scenario 3: Production Incident

```bash
# Quick diagnosis
/agent-springboot
"Getting OutOfMemoryError in production.
Current heap: 2GB, Container: 4GB
What's likely wrong?"

/agent-kafka
"Consumers stopped processing. Rebalancing constantly.
Help me troubleshoot."

/agent-aws
"ECS service unhealthy. Tasks cycling.
Check CloudWatch logs and diagnose."
```

## 🚨 Important Notes

### Agent Limitations

1. **Agents are specialists** - They focus on their domain exclusively
2. **Context stays within session** - Each agent activation is independent
3. **Switch when needed** - Don't expect a Spring Boot agent to know Docker best practices

### Getting the Best Results

1. **Be specific** with requirements and constraints
2. **Provide code context** when asking for reviews or debugging
3. **Ask follow-up questions** to dive deeper
4. **Request alternatives** - "What are other ways to solve this?"
5. **Ask for trade-offs** - "Pros and cons of approach A vs B?"

## 📚 Additional Resources

- **Agent Documentation**: See `.github/agents/README.md`
- **Individual Agents**: `.github/agents/[AGENT_NAME]_AGENT.md`
- **Slash Commands**: `.github/commands/agent-*.md`

## 🎉 Tips for Success

1. **Start with the right agent** - Choose based on primary technology
2. **Provide context upfront** - Version numbers, constraints, goals
3. **Ask for production-ready solutions** - Agents provide production patterns
4. **Request explanations** - "Why is this approach better?"
5. **Verify understanding** - "Summarize what we just implemented"
6. **Ask for testing strategies** - Agents know how to test their solutions
7. **Request monitoring setup** - Agents can help with observability

---

**Remember:** Agents are your specialized team members. Use them like you would consult domain experts on your team!

**Quick Reference:**
- `/agent-kafka` - Event streaming & messaging
- `/agent-aws` - Cloud infrastructure & deployment
- `/agent-springboot` - REST APIs & Spring applications
- `/agent-springcloud` - Microservices & distributed systems
- `/agent-docker` - Containerization & orchestration

**Happy coding, My Dude!** 🚀