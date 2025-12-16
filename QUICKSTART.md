# ICDA Quick Start

## Requirements
- Docker Desktop (running)
- AWS CLI configured (`aws configure`)

## Start
```cmd
git clone https://github.com/Bishopwalker/icda-prototype.git
cd icda-prototype
start.bat
```

Open: http://localhost:8000

## Stop
```cmd
stop.bat
```

## Verify
You should see:
- ✅ Redis: Connected
- ✅ OpenSearch: Connected
- ✅ Nova: Connected
- ✅ Embeddings: Connected

## Troubleshooting

**Docker not running** → Start Docker Desktop

**No AWS credentials** → Run `aws configure`
