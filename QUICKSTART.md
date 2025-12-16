# ICDA Quick Start

## Prerequisites
- Docker Desktop (running)
- AWS CLI (configured with `aws configure`)

## Start ICDA (3 steps)

### 1. Clone the repo
```cmd
git clone https://github.com/Bishopwalker/icda-prototype.git
cd icda-prototype
git checkout feature-branch-test
```

### 2. Start the app
```cmd
start-icda.bat
```

### 3. Open browser
```
http://localhost:8000
```

Wait ~30 seconds for all services to start.

---

## Verify It's Working

You should see in the UI:
- ✅ Redis: Connected
- ✅ OpenSearch: Connected
- ✅ Nova: Connected
- ✅ Embeddings: Connected

If Nova/Embeddings show disconnected, check your AWS credentials:
```cmd
aws configure list
```

---

## Stop ICDA
```cmd
docker-compose -f docker-compose.prod.yml down
```

---

## Troubleshooting

**"No AWS credentials found"**
```cmd
aws configure
```
Enter your Access Key, Secret Key, and region (us-east-1).

**Docker not running**
Start Docker Desktop first.

**Port 8000 in use**
```cmd
docker-compose -f docker-compose.prod.yml down
netstat -ano | findstr :8000
```

---

## Questions?
Contact Bishop Walker
