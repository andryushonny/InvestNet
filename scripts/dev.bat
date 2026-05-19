@echo off
setlocal EnableExtensions

set "ROOT=%~dp0.."
pushd "%ROOT%"

if not exist "backend\.venv\Scripts\python.exe" (
  python -m venv backend\.venv
  call backend\.venv\Scripts\activate.bat
  python -m pip install --upgrade pip wheel
  pip install -r backend\requirements.txt
) else (
  call backend\.venv\Scripts\activate.bat
)

start "InvestNet backend (dev)" cmd /k "call backend\.venv\Scripts\activate.bat && python -m app.main --port 8000 && pause"

cd frontend
if not exist node_modules call npm install
set NODE_ENV=development
set VITE_API_BASE=http://127.0.0.1:8000/api/v1
call npm run dev

popd
endlocal
