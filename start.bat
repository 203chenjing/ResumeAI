@echo off
chcp 65001 > nul
echo ===========================================
echo   ResumeAI · 一键启动（Windows）
echo ===========================================
echo.

REM 检查 .env
if not exist "backend\.env" (
    echo [WARN] backend\.env 不存在，从 .env.example 复制...
    copy "backend\.env.example" "backend\.env"
    echo.
    echo [ACTION] 请编辑 backend\.env 填入 DEEPSEEK_API_KEY 后重新运行。
    pause
    exit /b 1
)

if not exist "frontend\.env.local" (
    echo [INFO] frontend\.env.local 不存在，从 .env.example 复制...
    copy "frontend\.env.example" "frontend\.env.local"
)

REM 清理旧进程（避免多实例占端口导致 Failed to fetch）
echo [INFO] 清理 8000/3000 端口旧进程...
powershell -NoProfile -Command "foreach ($p in 8000,3000) { Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } }"
timeout /t 2 /nobreak > nul

REM 启动后端
echo [1/2] 启动后端 (端口 8000)...
start "ResumeAI Backend" cmd /k "cd backend && python -m venv .venv 2>nul & call .venv\Scripts\activate && pip install -q -r requirements.txt && python -m playwright install chromium && python run_server.py"

REM 启动前端
echo [2/2] 启动前端 (端口 3000)...
start "ResumeAI Frontend" cmd /k "cd frontend && npm install && npm run dev"

echo.
echo ===========================================
echo   启动完成！
echo   前端: http://localhost:3000
echo   后端 API 文档: http://localhost:8000/docs
echo ===========================================
echo.
pause
