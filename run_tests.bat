@echo off
setlocal
cd /d "%~dp0"
set FAILED=0

echo === ResumeAI Test Suite ===

echo.
echo [1/3] Backend unit tests (pytest)...
cd backend
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
pip install -q -r requirements.txt -r requirements-dev.txt 2>nul
python -m pytest tests -q
if errorlevel 1 set FAILED=1

echo.
echo [2/3] API smoke test...
python scripts\smoke_test.py
if errorlevel 1 set FAILED=1

echo.
echo [3/3] Frontend lint + build...
cd ..\frontend
call npm run lint 2>nul
if errorlevel 1 set FAILED=1
call npm run build
if errorlevel 1 set FAILED=1

echo.
if %FAILED%==0 (
  echo === ALL TESTS PASSED ===
  echo Optional: start backend and run  python backend\scripts\e2e_full_test.py  ^(needs DEEPSEEK_API_KEY^)
  exit /b 0
) else (
  echo === SOME TESTS FAILED ===
  exit /b 1
)
