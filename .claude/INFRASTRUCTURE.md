# INFRASTRUCTURE.md
# Universal Context Template - Deployment & Distribution Guide

## 🐳 Docker Infrastructure

This template is designed for easy distribution via Docker, allowing users to quickly initialize new projects with full context engineering support.

### Architecture Overview

```
Universal Context Template Container
├── Alpine Linux (lightweight base)
├── Essential tools (bash, git, python, node)
├── Template files (/template)
├── Initialization scripts (/template/scripts)
└── Output directory (/output for user projects)
```

## 📦 Building the Image

### Local Build

```bash
# Build from Dockerfile
docker build -t universal-context-template:latest .

# Or use docker-compose
docker-compose build

# Verify build
docker images | grep universal-context-template
```

### Multi-platform Build (for distribution)

```bash
# Build for multiple architectures
docker buildx build --platform linux/amd64,linux/arm64 \
  -t universal-context-template:latest .

# For Apple Silicon (M1/M2) compatibility
docker buildx build --platform linux/arm64 \
  -t universal-context-template:latest-arm64 .
```

## 🚀 Distribution Methods

### Method 1: Docker Image Export (Recommended)

**For distributors:**
```bash
# Save image as tar file
docker save universal-context-template:latest > context-template.tar

# Compress for smaller file size
docker save universal-context-template:latest | gzip > context-template.tar.gz

# Share the file via file transfer, cloud storage, etc.
```

**For recipients:**
```bash
# Load the image
docker load < context-template.tar

# Or if compressed
gunzip -c context-template.tar.gz | docker load

# Verify loaded
docker images | grep universal-context-template
```

### Method 2: Docker Registry

**Push to Docker Hub:**
```bash
# Tag image with your Docker Hub username
docker tag universal-context-template:latest your-username/universal-context-template:latest

# Login to Docker Hub
docker login

# Push image
docker push your-username/universal-context-template:latest
```

**Pull and use:**
```bash
# Users can pull directly
docker pull your-username/universal-context-template:latest

# Run it
docker-compose up
```

### Method 3: Private Registry

**For enterprise/private deployment:**
```bash
# Tag for private registry
docker tag universal-context-template:latest registry.yourcompany.com/context-template:latest

# Push to private registry
docker push registry.yourcompany.com/context-template:latest
```

## 🎯 Usage Patterns

### Pattern 1: One-Shot Project Initialization

```bash
# Initialize new project and exit
docker run --rm -v $(pwd)/output:/output \
  universal-context-template:latest \
  bash /template/scripts/init-project.sh my-project
```

### Pattern 2: Interactive Development

```bash
# Enter container interactively
docker-compose run context-template bash

# Inside container, initialize multiple projects
./template/scripts/init-project.sh project1
./template/scripts/init-project.sh project2
./template/scripts/init-project.sh project3
```

### Pattern 3: Windows PowerShell

```powershell
# Using the PowerShell script directly
.\scripts\init-project.ps1 -ProjectName my-project -OutputDir "C:\Projects"

# Or via Docker on Windows
docker run --rm -v ${PWD}/output:/output `
  universal-context-template:latest `
  bash /template/scripts/init-project.sh my-project
```

### Pattern 4: CI/CD Integration

```yaml
# Example GitHub Actions workflow
name: Initialize Project
on: workflow_dispatch

jobs:
  init:
    runs-on: ubuntu-latest
    steps:
      - name: Load template
        run: docker load < context-template.tar

      - name: Initialize project
        run: |
          docker run --rm -v $PWD/output:/output \
            universal-context-template:latest \
            bash /template/scripts/init-project.sh ${{ github.event.inputs.project_name }}

      - name: Commit initialized project
        run: |
          cd output/${{ github.event.inputs.project_name }}
          git init
          git add .
          git commit -m "Initial project setup with context templates"
```

## 🔧 Configuration

### Environment Variables

```bash
# Template home directory
TEMPLATE_HOME=/template

# Output directory for new projects
OUTPUT_DIR=/output

# Template version
TEMPLATE_VERSION=2.1

# User/Group IDs (for permission management)
USER_ID=1000
GROUP_ID=1000
```

### Docker Compose Configuration

```yaml
# Customize docker-compose.yml for your needs
services:
  context-template:
    volumes:
      # Mount your desired output location
      - /path/to/your/projects:/output

      # Mount custom templates (optional)
      - ./custom-templates:/template/custom

    environment:
      # Set custom environment variables
      - TEMPLATE_VERSION=2.1
      - OUTPUT_DIR=/output
```

## 🛠️ Customization

### Adding Custom Templates

1. Create custom templates in `./custom/` directory
2. Mount into container:
   ```yaml
   volumes:
     - ./custom:/template/custom
   ```
3. Reference in initialization scripts

### Extending the Dockerfile

```dockerfile
# Add additional tools
RUN apk add --no-cache your-tool

# Add custom scripts
COPY custom-scripts/ /usr/local/bin/

# Set custom environment
ENV CUSTOM_VAR=value
```

## 📊 Size Optimization

### Current Image Size
- Base Alpine: ~5MB
- With tools: ~200MB
- Total: ~205MB

### Optimization Strategies

1. **Use multi-stage builds:**
   ```dockerfile
   FROM alpine:latest AS builder
   # Build steps...

   FROM alpine:latest
   COPY --from=builder /output /app
   ```

2. **Remove unnecessary files:**
   ```dockerfile
   RUN apk add --no-cache package && \
       # Use package && \
       apk del package
   ```

3. **Compress templates:**
   ```bash
   tar -czf templates.tar.gz .claude/
   ```

## 🔒 Security Considerations

### Best Practices

1. **Don't include secrets in image:**
   - No API keys, tokens, or passwords
   - Use environment variables or mounted secrets

2. **Run as non-root user:**
   ```dockerfile
   RUN adduser -D -u 1000 template-user
   USER template-user
   ```

3. **Scan for vulnerabilities:**
   ```bash
   docker scan universal-context-template:latest
   ```

4. **Use specific base image versions:**
   ```dockerfile
   FROM alpine:3.18
   # Instead of alpine:latest
   ```

## 🐛 Troubleshooting

### Issue: Permission Denied

**Problem:** Cannot write to output directory

**Solution:**
```bash
# Set correct permissions
chmod -R 777 ./output

# Or set USER_ID/GROUP_ID
docker-compose run -e USER_ID=$(id -u) -e GROUP_ID=$(id -g) context-template bash
```

### Issue: Image Too Large

**Problem:** Docker image is too big for sharing

**Solution:**
```bash
# Compress before sharing
docker save universal-context-template:latest | gzip > context-template.tar.gz

# Or use docker export (smaller but loses layers)
docker export $(docker create universal-context-template:latest) | gzip > context-template-rootfs.tar.gz
```

### Issue: Scripts Not Executable

**Problem:** Shell scripts won't run

**Solution:**
```dockerfile
# In Dockerfile, ensure scripts are executable
RUN chmod +x /template/scripts/*.sh
```

### Issue: Windows Line Endings

**Problem:** Scripts fail on Linux due to CRLF

**Solution:**
```bash
# Convert line endings
dos2unix scripts/*.sh

# Or in Dockerfile
RUN find /template/scripts -name "*.sh" -exec dos2unix {} \;
```

## 📈 Monitoring & Logging

### Container Logs

```bash
# View container logs
docker-compose logs -f context-template

# Check initialization output
docker run universal-context-template:latest bash /template/scripts/init-project.sh test
```

### Health Checks

```dockerfile
# Add health check to Dockerfile
HEALTHCHECK --interval=30s --timeout=3s \
  CMD test -f /template/README.md || exit 1
```

## 🚀 Advanced Usage

### Batch Project Initialization

```bash
# Initialize multiple projects at once
for project in project1 project2 project3; do
  docker run --rm -v $(pwd)/output:/output \
    universal-context-template:latest \
    bash /template/scripts/init-project.sh $project
done
```

### Custom Template Variants

```bash
# Build different variants
docker build -t context-template:python --build-arg VARIANT=python .
docker build -t context-template:node --build-arg VARIANT=node .
docker build -t context-template:full --build-arg VARIANT=full .
```

### Integration with Project Generators

```bash
# Combine with Yeoman, Create React App, etc.
docker run --rm -v $(pwd):/output context-template:latest bash -c "
  cd /output
  npx create-react-app my-app
  cd my-app
  /template/scripts/init-project.sh .
"
```

## 📝 Maintenance

### Updating the Template

1. Make changes to template files
2. Rebuild image: `docker-compose build`
3. Test with new project initialization
4. Tag with version: `docker tag context-template:latest context-template:v1.1`
5. Distribute updated image

### Version Management

```bash
# Tag versions
docker tag universal-context-template:latest universal-context-template:1.0.0
docker tag universal-context-template:latest universal-context-template:1.0
docker tag universal-context-template:latest universal-context-template:1

# Push all tags
docker push universal-context-template:1.0.0
docker push universal-context-template:1.0
docker push universal-context-template:1
```

---

**Last Updated:** 2025-12-02
**Template Version:** 2.1
**Docker Support:** ✅ Full Docker distribution ready (with security hardening)
