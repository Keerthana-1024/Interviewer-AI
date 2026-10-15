#!/usr/bin/env bash
# setup_wsl.sh — Run inside WSL to set up the full AI Interviewer environment
# Usage: bash setup_wsl.sh
set -e

WORKSPACE="/mnt/c/Keertha/javaProjects/interview-ai"
BACKEND="$WORKSPACE/backend"

echo "=========================================="
echo "  AI Interviewer — WSL Environment Setup"
echo "=========================================="

# ─── 1. Create all __init__.py files ──────────────────────────────────────────
echo "[1/7] Creating Python package structure..."
DIRS=(
  "$BACKEND/app"
  "$BACKEND/app/api"
  "$BACKEND/app/core"
  "$BACKEND/app/db"
  "$BACKEND/app/models"
  "$BACKEND/app/schemas"
  "$BACKEND/app/services"
  "$BACKEND/app/services/document_processing"
  "$BACKEND/app/services/matching"
  "$BACKEND/app/services/interview"
  "$BACKEND/app/services/evaluation"
  "$BACKEND/app/graph"
  "$BACKEND/tests"
  "$BACKEND/tests/unit"
  "$BACKEND/alembic"
  "$BACKEND/alembic/versions"
  "$WORKSPACE/docs"
)
for d in "${DIRS[@]}"; do
  mkdir -p "$d"
  touch "$d/__init__.py"
done
echo "  ✓ Package structure created"

# ─── 2. Python setup ──────────────────────────────────────────────────────────
echo "[2/7] Setting up Python virtual environment..."
cd "$BACKEND"

# Install Python 3.11 if needed
if ! python3.11 --version &>/dev/null; then
  echo "  Installing Python 3.11..."
  sudo apt-get update -qq
  sudo apt-get install -y python3.11 python3.11-venv python3.11-dev build-essential libpq-dev -qq
fi

# Create venv
if [ ! -d ".venv" ]; then
  python3.11 -m venv .venv
  echo "  ✓ Virtual environment created at $BACKEND/.venv"
else
  echo "  ✓ Virtual environment already exists"
fi

# Activate and install deps
source .venv/bin/activate
pip install --upgrade pip -q
echo "[3/7] Installing Python dependencies (this may take a few minutes)..."
pip install -r requirements.txt -q
echo "  ✓ Python dependencies installed"

# ─── 3. Create .env from example ──────────────────────────────────────────────
echo "[4/7] Setting up environment file..."
if [ ! -f "$BACKEND/.env" ]; then
  cp "$BACKEND/.env.example" "$BACKEND/.env"
  echo "  ✓ .env created from .env.example"
  echo "  ⚠  IMPORTANT: Edit $BACKEND/.env and fill in:"
  echo "       DATABASE_URL  (your Supabase PostgreSQL connection string)"
  echo "       DEEPGRAM_API_KEY  (from https://console.deepgram.com)"
  echo "     The LLM is Ollama (already configured — uses qwen2.5:7b-instruct-q4_0)"
else
  echo "  ✓ .env already exists — not overwriting"
fi

# ─── 4. Check Ollama ──────────────────────────────────────────────────────────
echo "[5/7] Checking Ollama..."
if command -v ollama &>/dev/null; then
  echo "  ✓ Ollama is installed"
  ollama list 2>/dev/null || echo "  (Ollama not running — start with: ollama serve)"
else
  echo "  ⚠ Ollama not found in WSL PATH."
  echo "    Ollama runs on Windows — it should be accessible via http://localhost:11434"
  echo "    The backend will connect to it automatically."
fi

# ─── 5. Run DB migrations ─────────────────────────────────────────────────────
echo "[6/7] Running database migrations..."
cd "$BACKEND"
source .venv/bin/activate
if grep -q "xxxx" .env 2>/dev/null; then
  echo "  ⚠ DATABASE_URL still has placeholder values — skipping migrations"
  echo "    Edit .env first, then run: cd backend && alembic upgrade head"
else
  alembic upgrade head && echo "  ✓ Migrations applied" || echo "  ✗ Migration failed — check DATABASE_URL in .env"
fi

# ─── 6. Node.js for frontend ──────────────────────────────────────────────────
echo "[7/7] Setting up Node.js for React frontend..."
if ! command -v node &>/dev/null; then
  echo "  Installing Node.js 20..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - -q
  sudo apt-get install -y nodejs -qq
fi
NODE_VER=$(node --version 2>/dev/null || echo "not found")
echo "  ✓ Node.js: $NODE_VER"

FRONTEND="$WORKSPACE/frontend"
if [ -d "$FRONTEND" ] && [ -f "$FRONTEND/package.json" ]; then
  cd "$FRONTEND"
  npm install -q
  echo "  ✓ Frontend dependencies installed"
fi

echo ""
echo "=========================================="
echo "  Setup complete!"
echo "=========================================="
echo ""
echo "To start the backend:"
echo "  cd $BACKEND && source .venv/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "To start the frontend:"
echo "  cd $WORKSPACE/frontend && npm run dev"
echo ""
echo "API docs: http://localhost:8000/docs"
echo "Frontend: http://localhost:5173"
echo ""
echo "⚠  Make sure .env has your Supabase DATABASE_URL and DEEPGRAM_API_KEY set!"
