#!/bin/bash
# ================================================
# ICDA Quick Start - No Docker Required!
# ================================================

echo ""
echo "========================================"
echo "  ICDA Prototype - Quick Start"
echo "========================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python not found! Install Python 3.10+"
    exit 1
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt -q

# Check for .env
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: No .env file found!"
    echo "Creating from .env.example..."
    cp .env.example .env
    echo ""
    echo "EDIT .env with your AWS credentials for AI features."
    echo "Without AWS creds, the app runs in LITE MODE."
    echo ""
fi

echo ""
echo "========================================"
echo "  Starting ICDA Server"
echo "========================================"
echo ""
echo "  API:  http://localhost:8000"
echo "  Docs: http://localhost:8000/docs"
echo ""
echo "  Press Ctrl+C to stop"
echo "========================================"
echo ""

# Run the app
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
