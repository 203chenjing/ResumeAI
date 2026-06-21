#!/bin/bash
set -e

echo "==========================================="
echo "  ResumeAI · 一键启动（Linux/Mac）"
echo "==========================================="
echo

# .env 检查
if [ ! -f "backend/.env" ]; then
    echo "[WARN] backend/.env 不存在，从 .env.example 复制..."
    cp backend/.env.example backend/.env
    echo
    echo "[ACTION] 请编辑 backend/.env 填入 DEEPSEEK_API_KEY 后重新运行。"
    exit 1
fi

if [ ! -f "frontend/.env.local" ]; then
    cp frontend/.env.example frontend/.env.local
fi

echo "[1/2] 启动后端 (端口 8000)..."
cd backend
python3 -m venv .venv 2>/dev/null || true
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

echo "[2/2] 启动前端 (端口 3000)..."
cd frontend
npm install --silent
npm run dev &
FRONTEND_PID=$!
cd ..

echo
echo "==========================================="
echo "  启动完成！"
echo "  前端: http://localhost:3000"
echo "  后端 API: http://localhost:8000/docs"
echo "==========================================="
echo "  Ctrl+C 停止"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
