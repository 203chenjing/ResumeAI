#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== ResumeAI Test Suite ==="

echo ""
echo "[1/3] Backend unit tests (pytest)..."
cd backend
if [ -d .venv ]; then source .venv/bin/activate; fi
pip install -q -r requirements.txt -r requirements-dev.txt
python -m pytest tests -q

echo ""
echo "[2/3] API smoke test..."
python scripts/smoke_test.py

echo ""
echo "[3/3] Frontend lint + build..."
cd ../frontend
npm run lint
npm run build

echo ""
echo "=== ALL TESTS PASSED ==="
echo "Optional: start backend and run: python backend/scripts/e2e_full_test.py (needs DEEPSEEK_API_KEY)"
