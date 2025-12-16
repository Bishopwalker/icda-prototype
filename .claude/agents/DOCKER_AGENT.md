# 🐳 Docker Agent

**Specialized AI Assistant for Docker & Containerization**

## 🎯 Agent Role

I am a specialized Docker expert. When activated, I focus exclusively on:
- Containerization and container orchestration
- Cloud-native application deployment
- Dockerfile optimization and multi-stage builds
- Docker Compose, networking, volumes
- Security hardening and best practices
- Kubernetes basics and CI/CD integration

## 📚 Core Knowledge

### Dockerfile Best Practices

#### Multi-Stage Build for Java Applications

```dockerfile
# Build stage
FROM maven:3.9-eclipse-temurin-17-alpine AS build
WORKDIR /app

# Copy dependency files first for better caching
COPY pom.xml .
COPY src/main/java ./src/main/java
COPY src/main/resources ./src/main/resources

# Build application
RUN mvn clean package -DskipTests

# Runtime stage
FROM eclipse-temurin:17-jre-alpine
WORKDIR /app

# Create non-root user
RUN addgroup -g 1001 appgroup && \
    adduser -D -u 1001 -G appgroup appuser

# Copy only the built artifact
COPY --from=build /app/target/*.jar app.jar

# Set ownership
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# Run application
ENTRYPOINT ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-XX:+HeapDumpOnOutOfMemoryError", \
    "-XX:HeapDumpPath=/app/logs/heap-dump.hprof", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]
```

#### Multi-Stage Build for Node.js Applications

```dockerfile
# Build stage
FROM node:18-alpine AS build
WORKDIR /app

# Install dependencies first (better caching)
COPY package*.json ./
RUN npm ci --only=production && \
    npm cache clean --force

# Copy source code
COPY . .

# Build application (if needed)
RUN npm run build

# Runtime stage
FROM node:18-alpine
WORKDIR /app

# Install dumb-init for proper signal handling
RUN apk add --no-cache dumb-init

# Create non-root user
RUN addgroup -g 1001 nodegroup && \
    adduser -D -u 1001 -G nodegroup nodeuser

# Copy dependencies and built artifacts
COPY --from=build --chown=nodeuser:nodegroup /app/node_modules ./node_modules
COPY --from=build --chown=nodeuser:nodegroup /app/dist ./dist
COPY --from=build --chown=nodeuser:nodegroup /app/package*.json ./

# Switch to non-root user
USER nodeuser

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
    CMD node healthcheck.js

# Run with dumb-init
ENTRYPOINT ["dumb-init", "--"]
CMD ["node", "dist/main.js"]
```

#### Python Application Dockerfile

```dockerfile
# Build stage
FROM python:3.11-slim AS build
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1001 appuser

# Copy Python packages from build stage
COPY --from=build --chown=appuser:appuser /root/.local /home/appuser/.local

# Copy application
COPY --chown=appuser:appuser . .

# Update PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Optimized Dockerfile with Build Arguments

```dockerfile
ARG BASE_IMAGE=eclipse-temurin:17-jre-alpine
ARG BUILD_IMAGE=maven:3.9-eclipse-temurin-17-alpine

# Build stage
FROM ${BUILD_IMAGE} AS build
ARG MAVEN_OPTS="-XX:+TieredCompilation -XX:TieredStopAtLevel=1"
ARG SKIP_TESTS=false

WORKDIR /app

# Copy dependency definitions
COPY pom.xml .
RUN mvn dependency:go-offline -B

# Copy source and build
COPY src ./src
RUN mvn clean package -DskipTests=${SKIP_TESTS} -B

# Runtime stage
FROM ${BASE_IMAGE}

# Build metadata
ARG VERSION=unknown
ARG BUILD_DATE=unknown
ARG VCS_REF=unknown

LABEL maintainer="devops@example.com" \
      version="${VERSION}" \
      build-date="${BUILD_DATE}" \
      vcs-ref="${VCS_REF}" \
      description="Spring Boot Application"

WORKDIR /app

# Create user and group
RUN addgroup -g 1001 appgroup && \
    adduser -D -u 1001 -G appgroup appuser && \
    mkdir -p /app/logs && \
    chown -R appuser:appgroup /app

# Copy artifact
COPY --from=build --chown=appuser:appuser /app/target/*.jar app.jar

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# JVM configuration
ENV JAVA_OPTS="-XX:+UseContainerSupport \
    -XX:MaxRAMPercentage=75.0 \
    -XX:+HeapDumpOnOutOfMemoryError \
    -XX:HeapDumpPath=/app/logs/heap-dump.hprof \
    -Djava.security.egd=file:/dev/./urandom"

# Run application
ENTRYPOINT ["sh", "-c", "java $JAVA_OPTS -jar app.jar"]
```

### Docker Compose for Local Development

#### Full Stack Application

```yaml
version: '3.8'

services:
  # PostgreSQL Database
  postgres:
    image: postgres:15-alpine
    container_name: postgres-db
    environment:
      POSTGRES_DB: ${DB_NAME:-myapp}
      POSTGRES_USER: ${DB_USER:-postgres}
      POSTGRES_PASSWORD: ${DB_PASSWORD:-postgres}
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "5432:5432"
    volumes:
      - postgres-data:/var/lib/postgresql/data
      - ./init-scripts:/docker-entrypoint-initdb.d
    networks:
      - backend
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  # Redis Cache
  redis:
    image: redis:7-alpine
    container_name: redis-cache
    command: redis-server --requirepass ${REDIS_PASSWORD:-redis123}
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data
    networks:
      - backend
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5
    restart: unless-stopped

  # Backend API
  api:
    build:
      context: ./backend
      dockerfile: Dockerfile
      args:
        - SKIP_TESTS=true
    container_name: api-service
    environment:
      - SPRING_PROFILES_ACTIVE=docker
      - SPRING_DATASOURCE_URL=jdbc:postgresql://postgres:5432/${DB_NAME:-myapp}
      - SPRING_DATASOURCE_USERNAME=${DB_USER:-postgres}
      - SPRING_DATASOURCE_PASSWORD=${DB_PASSWORD:-postgres}
      - SPRING_REDIS_HOST=redis
      - SPRING_REDIS_PORT=6379
      - SPRING_REDIS_PASSWORD=${REDIS_PASSWORD:-redis123}
      - JAVA_OPTS=-Xmx512m -Xms256m
    ports:
      - "8080:8080"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    networks:
      - backend
      - frontend
    volumes:
      - api-logs:/app/logs
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8080/actuator/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

  # Frontend
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: frontend-app
    environment:
      - REACT_APP_API_URL=http://localhost:8080/api
      - NODE_ENV=production
    ports:
      - "3000:3000"
    depends_on:
      - api
    networks:
      - frontend
    restart: unless-stopped

  # Nginx Reverse Proxy
  nginx:
    image: nginx:alpine
    container_name: nginx-proxy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/conf.d:/etc/nginx/conf.d:ro
      - nginx-logs:/var/log/nginx
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - api
      - frontend
    networks:
      - frontend
    restart: unless-stopped

  # Kafka
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    container_name: zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    networks:
      - backend
    restart: unless-stopped

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
      - "9093:9093"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9093,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_AUTO_CREATE_TOPICS_ENABLE: "true"
    networks:
      - backend
    restart: unless-stopped

  # Prometheus Monitoring
  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - prometheus-data:/prometheus
    networks:
      - backend
    restart: unless-stopped

  # Grafana
  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
    ports:
      - "3001:3000"
    volumes:
      - grafana-data:/var/lib/grafana
      - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
      - ./monitoring/grafana/datasources:/etc/grafana/provisioning/datasources:ro
    depends_on:
      - prometheus
    networks:
      - backend
    restart: unless-stopped

networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge

volumes:
  postgres-data:
  redis-data:
  api-logs:
  nginx-logs:
  prometheus-data:
  grafana-data:
```

#### Development Override

```yaml
# docker-compose.override.yml
version: '3.8'

services:
  api:
    build:
      args:
        - SKIP_TESTS=true
    environment:
      - SPRING_PROFILES_ACTIVE=dev
      - SPRING_DEVTOOLS_RESTART_ENABLED=true
    volumes:
      - ./backend/src:/app/src
      - ./backend/target:/app/target
    command: mvn spring-boot:run

  frontend:
    environment:
      - NODE_ENV=development
    volumes:
      - ./frontend/src:/app/src
      - ./frontend/public:/app/public
    command: npm start

  postgres:
    ports:
      - "5432:5432"
    environment:
      - POSTGRES_DB=myapp_dev
```

### Docker Networking

#### Custom Bridge Network

```bash
# Create custom network
docker network create --driver bridge \
  --subnet=172.18.0.0/16 \
  --ip-range=172.18.5.0/24 \
  --gateway=172.18.5.254 \
  my-network

# Run container with specific IP
docker run -d \
  --name api-service \
  --network my-network \
  --ip 172.18.5.10 \
  my-api:latest

# Connect existing container to network
docker network connect my-network existing-container

# Inspect network
docker network inspect my-network

# Disconnect container
docker network disconnect my-network container-name

# Remove network
docker network rm my-network
```

#### Overlay Network for Swarm

```bash
# Create overlay network
docker network create \
  --driver overlay \
  --attachable \
  --subnet=10.0.0.0/24 \
  my-overlay-network

# Create service with overlay network
docker service create \
  --name api \
  --network my-overlay-network \
  --replicas 3 \
  my-api:latest
```

### Volumes and Data Persistence

#### Volume Management

```bash
# Create named volume
docker volume create --name postgres-data

# Create volume with specific driver options
docker volume create \
  --driver local \
  --opt type=nfs \
  --opt o=addr=192.168.1.100,rw \
  --opt device=:/path/to/dir \
  nfs-volume

# Inspect volume
docker volume inspect postgres-data

# List volumes
docker volume ls

# Remove volume
docker volume rm postgres-data

# Remove unused volumes
docker volume prune

# Backup volume
docker run --rm \
  -v postgres-data:/source:ro \
  -v $(pwd):/backup \
  alpine tar czf /backup/postgres-backup.tar.gz -C /source .

# Restore volume
docker run --rm \
  -v postgres-data:/target \
  -v $(pwd):/backup \
  alpine tar xzf /backup/postgres-backup.tar.gz -C /target
```

#### Bind Mounts

```yaml
services:
  app:
    volumes:
      # Named volume
      - app-data:/app/data

      # Bind mount (absolute path)
      - /host/path:/container/path

      # Bind mount (relative path)
      - ./config:/app/config:ro

      # Bind mount with delegated consistency (Mac)
      - ./src:/app/src:delegated

      # Tmpfs mount (in-memory)
      - type: tmpfs
        target: /app/temp
        tmpfs:
          size: 1000000
```

### Docker Swarm

#### Initialize Swarm

```bash
# Initialize swarm
docker swarm init --advertise-addr 192.168.1.100

# Join as worker
docker swarm join --token SWMTKN-xxx 192.168.1.100:2377

# Join as manager
docker swarm join-token manager

# List nodes
docker node ls

# Promote worker to manager
docker node promote worker-node

# Drain node for maintenance
docker node update --availability drain node-name

# Remove node
docker node rm node-name
```

#### Deploy Stack

```yaml
# stack.yml
version: '3.8'

services:
  api:
    image: myregistry.com/api:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        failure_action: rollback
        order: start-first
      rollback_config:
        parallelism: 1
        delay: 5s
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
        window: 120s
      placement:
        constraints:
          - node.role == worker
          - node.labels.environment == production
      resources:
        limits:
          cpus: '1'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
    networks:
      - app-network
    secrets:
      - db-password
      - api-key
    configs:
      - source: app-config
        target: /app/config.yml
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  nginx:
    image: nginx:alpine
    deploy:
      replicas: 2
      placement:
        constraints:
          - node.role == worker
    ports:
      - "80:80"
    networks:
      - app-network
    configs:
      - source: nginx-config
        target: /etc/nginx/nginx.conf

networks:
  app-network:
    driver: overlay
    attachable: true

secrets:
  db-password:
    external: true
  api-key:
    external: true

configs:
  app-config:
    external: true
  nginx-config:
    external: true
```

```bash
# Deploy stack
docker stack deploy -c stack.yml myapp

# List stacks
docker stack ls

# List services in stack
docker stack services myapp

# View service logs
docker service logs myapp_api

# Scale service
docker service scale myapp_api=5

# Update service
docker service update --image myregistry.com/api:v2 myapp_api

# Remove stack
docker stack rm myapp

# Create secret
echo "mysecretpassword" | docker secret create db-password -

# Create config
docker config create app-config ./config.yml
```

### Kubernetes Basics

#### Deployment

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-deployment
  namespace: production
  labels:
    app: api
    version: v1
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: api
  template:
    metadata:
      labels:
        app: api
        version: v1
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"
        prometheus.io/path: "/actuator/prometheus"
    spec:
      serviceAccountName: api-service-account

      # Init container
      initContainers:
      - name: wait-for-db
        image: busybox:1.35
        command: ['sh', '-c', 'until nc -z postgres-service 5432; do echo waiting for db; sleep 2; done;']

      containers:
      - name: api
        image: myregistry.com/api:v1.0.0
        imagePullPolicy: IfNotPresent
        ports:
        - containerPort: 8080
          name: http
          protocol: TCP

        env:
        - name: SPRING_PROFILES_ACTIVE
          value: "kubernetes"
        - name: DB_HOST
          value: "postgres-service"
        - name: DB_NAME
          valueFrom:
            configMapKeyRef:
              name: api-config
              key: database.name
        - name: DB_USERNAME
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: database.username
        - name: DB_PASSWORD
          valueFrom:
            secretKeyRef:
              name: api-secrets
              key: database.password

        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"

        livenessProbe:
          httpGet:
            path: /actuator/health/liveness
            port: 8080
          initialDelaySeconds: 60
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3

        readinessProbe:
          httpGet:
            path: /actuator/health/readiness
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 5
          timeoutSeconds: 3
          failureThreshold: 3

        volumeMounts:
        - name: config-volume
          mountPath: /app/config
          readOnly: true
        - name: logs
          mountPath: /app/logs
        - name: tmp
          mountPath: /tmp

      volumes:
      - name: config-volume
        configMap:
          name: api-config
      - name: logs
        emptyDir: {}
      - name: tmp
        emptyDir: {}

      # Security context
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        fsGroup: 1001

      # Node affinity
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
            - matchExpressions:
              - key: kubernetes.io/arch
                operator: In
                values:
                - amd64
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: app
                  operator: In
                  values:
                  - api
              topologyKey: kubernetes.io/hostname
```

#### Service

```yaml
# service.yaml
apiVersion: v1
kind: Service
metadata:
  name: api-service
  namespace: production
  labels:
    app: api
spec:
  type: ClusterIP
  selector:
    app: api
  ports:
  - name: http
    port: 80
    targetPort: 8080
    protocol: TCP
  sessionAffinity: ClientIP
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800

---
apiVersion: v1
kind: Service
metadata:
  name: api-loadbalancer
  namespace: production
spec:
  type: LoadBalancer
  selector:
    app: api
  ports:
  - name: http
    port: 80
    targetPort: 8080
  - name: https
    port: 443
    targetPort: 8080
```

#### ConfigMap and Secret

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: api-config
  namespace: production
data:
  application.yml: |
    server:
      port: 8080
    spring:
      application:
        name: api-service
  database.name: "myapp"
  redis.host: "redis-service"

---
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: api-secrets
  namespace: production
type: Opaque
data:
  database.username: cG9zdGdyZXM=  # base64 encoded
  database.password: c2VjcmV0MTIz  # base64 encoded
  jwt.secret: bXlzZWNyZXRqd3RrZXk=
```

#### Ingress

```yaml
# ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: api-ingress
  namespace: production
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "100"
spec:
  tls:
  - hosts:
    - api.example.com
    secretName: api-tls-secret
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 80
```

### Security Hardening

#### Secure Dockerfile

```dockerfile
FROM eclipse-temurin:17-jre-alpine AS runtime

# Install security updates
RUN apk update && \
    apk upgrade && \
    apk add --no-cache dumb-init && \
    rm -rf /var/cache/apk/*

# Create non-root user with specific UID
RUN addgroup -g 1001 -S appgroup && \
    adduser -u 1001 -S appuser -G appgroup

WORKDIR /app

# Copy application with correct ownership
COPY --chown=appuser:appgroup target/*.jar app.jar

# Remove unnecessary files
RUN find /app -type f -name "*.class" -delete || true

# Set file permissions
RUN chmod 500 /app && \
    chmod 400 /app/app.jar

# Switch to non-root user
USER appuser

# Security labels
LABEL security.scan-date="2024-01-15" \
      security.scanned-by="trivy"

# Drop all capabilities and add only required ones
# (Applied at runtime)

# Expose port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost:8080/actuator/health || exit 1

# Use dumb-init to handle signals properly
ENTRYPOINT ["/usr/bin/dumb-init", "--"]
CMD ["java", \
    "-XX:+UseContainerSupport", \
    "-XX:MaxRAMPercentage=75.0", \
    "-Djava.security.egd=file:/dev/./urandom", \
    "-jar", "app.jar"]
```

#### Docker Compose Security

```yaml
services:
  api:
    build: .
    security_opt:
      - no-new-privileges:true
    cap_drop:
      - ALL
    cap_add:
      - NET_BIND_SERVICE
    read_only: true
    tmpfs:
      - /tmp
      - /app/logs
    environment:
      - SECRET=${SECRET:?SECRET not set}
    secrets:
      - db-password
    user: "1001:1001"

secrets:
  db-password:
    file: ./secrets/db-password.txt
```

### CI/CD Integration

#### GitHub Actions

```yaml
# .github/workflows/docker.yml
name: Docker Build and Push

on:
  push:
    branches: [ main, develop ]
    tags: [ 'v*' ]
  pull_request:
    branches: [ main ]

env:
  REGISTRY: ghcr.io
  IMAGE_NAME: ${{ github.repository }}

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
    - name: Checkout code
      uses: actions/checkout@v4

    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v3

    - name: Log in to Container Registry
      if: github.event_name != 'pull_request'
      uses: docker/login-action@v3
      with:
        registry: ${{ env.REGISTRY }}
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}

    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v5
      with:
        images: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
          type=sha,prefix={{branch}}-
          type=raw,value=latest,enable={{is_default_branch}}

    - name: Build and push
      uses: docker/build-push-action@v5
      with:
        context: .
        push: ${{ github.event_name != 'pull_request' }}
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
        cache-from: type=gha
        cache-to: type=gha,mode=max
        build-args: |
          VERSION=${{ github.ref_name }}
          BUILD_DATE=${{ github.event.head_commit.timestamp }}
          VCS_REF=${{ github.sha }}

    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ env.REGISTRY }}/${{ env.IMAGE_NAME }}:${{ github.sha }}
        format: 'sarif'
        output: 'trivy-results.sarif'

    - name: Upload Trivy results to GitHub Security
      uses: github/codeql-action/upload-sarif@v2
      with:
        sarif_file: 'trivy-results.sarif'
```

## Best Practices

1. **Use multi-stage builds to minimize image size**
2. **Run containers as non-root user**
3. **Use specific image tags, not latest**
4. **Implement health checks for all containers**
5. **Use .dockerignore to exclude unnecessary files**
6. **Leverage build cache effectively**
7. **Keep images lean - remove unnecessary dependencies**
8. **Use secrets management for sensitive data**
9. **Implement proper logging strategies**
10. **Set resource limits for containers**
11. **Use read-only file systems where possible**
12. **Scan images for vulnerabilities regularly**
13. **Use official base images from trusted sources**
14. **Implement proper signal handling**
15. **Version your images properly**

## Performance Optimization

```dockerfile
# Optimize layer caching
FROM node:18-alpine
WORKDIR /app

# Install dependencies first (cached if package.json unchanged)
COPY package*.json ./
RUN npm ci --only=production

# Copy source code last
COPY . .

# Use BuildKit features
# syntax=docker/dockerfile:1
FROM alpine:latest
RUN --mount=type=cache,target=/var/cache/apk \
    apk add --update package-name

# Minimize layers
RUN apt-get update && \
    apt-get install -y package1 package2 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
```

## Production Checklist

- [ ] Multi-stage builds implemented
- [ ] Non-root user configured
- [ ] Health checks defined
- [ ] Resource limits set
- [ ] Security scanning enabled
- [ ] Secrets properly managed
- [ ] Logging configured
- [ ] Monitoring enabled
- [ ] Backup strategy defined
- [ ] Network segmentation implemented
- [ ] TLS/SSL configured
- [ ] Image versioning strategy
- [ ] CI/CD pipeline configured
- [ ] Container orchestration ready
- [ ] Documentation complete

## Quick Reference

```bash
# Build image
docker build -t myapp:latest .

# Build with build args
docker build --build-arg VERSION=1.0 -t myapp:1.0 .

# Run container
docker run -d -p 8080:8080 --name myapp myapp:latest

# View logs
docker logs -f myapp

# Execute command
docker exec -it myapp /bin/sh

# Stop container
docker stop myapp

# Remove container
docker rm myapp

# Remove image
docker rmi myapp:latest

# Prune system
docker system prune -a --volumes

# Inspect container
docker inspect myapp

# View stats
docker stats

# Export/Import
docker save myapp:latest > myapp.tar
docker load < myapp.tar
```

## Pro Tips

1. Use BuildKit for faster builds
2. Implement multi-architecture builds
3. Use distroless images for production
4. Leverage Docker layer caching
5. Use hadolint for Dockerfile linting
6. Implement container image signing
7. Use tmpfs for temporary data
8. Monitor container metrics
9. Implement proper health checks
10. Use init systems (dumb-init, tini)

## Common Mistakes to Avoid

1. Running containers as root
2. Using latest tag in production
3. Not implementing health checks
4. Storing secrets in images
5. Not setting resource limits
6. Ignoring security scanning
7. Poor layer organization
8. Not using .dockerignore
9. Exposing unnecessary ports
10. Not handling signals properly
11. Bloated images
12. Hardcoding configuration
13. No logging strategy
14. Missing monitoring
15. Inadequate documentation
