@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%CD%"
title EFL IndexDB - Setup

echo ============================================================
echo   EFL IndexDB - local setup and launch
echo ============================================================
echo.

REM ---------- prerequisites ----------
where python >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Python was not found on PATH. Install Python 3.11+ and retry.
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js was not found on PATH. Install Node.js 18+ and retry.
  pause
  exit /b 1
)

where npm >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm was not found on PATH. Reinstall Node.js and retry.
  pause
  exit /b 1
)

echo [OK] Python:
python --version
echo [OK] Node:
node --version
echo.

REM ---------- backend venv + deps ----------
echo [1/5] Backend dependencies...
if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo       Creating virtual environment at .venv ...
  python -m venv "%ROOT%\.venv"
  if errorlevel 1 (
    echo [ERROR] Failed to create .venv
    pause
    exit /b 1
  )
)

call "%ROOT%\.venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install -r "%ROOT%\backend\requirements.txt"
if errorlevel 1 (
  echo [ERROR] Backend pip install failed.
  pause
  exit /b 1
)
echo [OK] Backend packages installed.
echo.

REM ---------- env files ----------
if not exist "%ROOT%\.env" (
  if exist "%ROOT%\backend\.env.example" (
    copy /Y "%ROOT%\backend\.env.example" "%ROOT%\.env" >nul
    echo [OK] Created .env from backend\.env.example
    echo       Edit .env to set JWT_SECRET / ADMIN_PASSWORD_HASH / ANTHROPIC_API_KEY if needed.
  )
)

if not exist "%ROOT%\frontend\.env" (
  (
    echo REACT_APP_API_URL=http://localhost:8000
  ) > "%ROOT%\frontend\.env"
  echo [OK] Created frontend\.env with REACT_APP_API_URL=http://localhost:8000
)

REM ---------- frontend deps ----------
echo [2/5] Frontend dependencies...
if not exist "%ROOT%\frontend\package.json" (
  echo [ERROR] frontend\package.json missing. Clone or copy the frontend app into frontend\
  pause
  exit /b 1
)

pushd "%ROOT%\frontend"
if not exist "node_modules\" (
  echo       Running npm install (first run may take several minutes)...
) else (
  echo       Syncing npm dependencies...
)
call npm install
if errorlevel 1 (
  echo [ERROR] npm install failed.
  popd
  pause
  exit /b 1
)
popd
echo [OK] Frontend packages ready.
echo.

REM ---------- existing pipeline status (do NOT re-run) ----------
echo [3/5] Existing pipeline status (reusing local artefacts, not re-running)...
echo ------------------------------------------------------------
set "STATE=%ROOT%\data\processed\pipeline_state.json"
if not exist "%STATE%" (
  echo [WARN] data\processed\pipeline_state.json not found.
  echo        Fresh clones do not include gitignored pipeline outputs.
  echo        Copy processed artefacts into data\processed\ and
  echo        data\embeddings\ from a completed run, or run:
  echo          cd backend ^&^& make pipeline-all
  echo.
) else (
  "%ROOT%\.venv\Scripts\python.exe" "%ROOT%\scripts\print_pipeline_status.py"
  if errorlevel 1 (
    echo [WARN] Could not print pipeline status.
  )
)
echo ------------------------------------------------------------
echo.

REM ---------- launch two CMD windows only ----------
echo [4/5] Starting Backend (CMD 1) and Frontend (CMD 2)...

start "EFL IndexDB - Backend (CMD 1)" cmd /k call "%ROOT%\scripts\run_backend.bat"
start "EFL IndexDB - Frontend (CMD 2)" cmd /k call "%ROOT%\scripts\run_frontend.bat"

REM ---------- wait for servers, open dashboard ----------
echo [5/5] Waiting for servers, then opening Dashboard...
echo       Backend  http://localhost:8000
echo       Frontend http://localhost:3000/dashboard
echo.

set /a TRIES=0
:wait_backend
set /a TRIES+=1
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://localhost:8000/docs' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  if !TRIES! GEQ 90 (
    echo [WARN] Backend did not become ready in time. Check CMD 1.
    goto wait_frontend
  )
  timeout /t 2 /nobreak >nul
  goto wait_backend
)
echo [OK] Backend is responding.

set /a TRIES=0
:wait_frontend
set /a TRIES+=1
powershell -NoProfile -Command "try { $r=Invoke-WebRequest -Uri 'http://localhost:3000' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -ge 200) { exit 0 } else { exit 1 } } catch { exit 1 }" >nul 2>&1
if errorlevel 1 (
  if !TRIES! GEQ 120 (
    echo [WARN] Frontend did not become ready in time. Check CMD 2.
    echo       You can open http://localhost:3000/dashboard manually.
    goto done
  )
  timeout /t 2 /nobreak >nul
  goto wait_frontend
)
echo [OK] Frontend is responding.

start "" "http://localhost:3000/dashboard"

:done
echo.
echo ============================================================
echo   Launch complete. Leave CMD 1 and CMD 2 open while using
echo   the app. This setup window can be closed.
echo ============================================================
echo.
exit /b 0
