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

REM ---------- backend venv + deps (skip if already importable) ----------
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

set "BACKEND_READY=0"
"%ROOT%\.venv\Scripts\python.exe" -c "import fastapi,uvicorn,pandas,numpy" >nul 2>&1
if not errorlevel 1 set "BACKEND_READY=1"

if "!BACKEND_READY!"=="1" (
  echo [OK] Backend already installed — skipping pip install.
) else (
  echo       Backend packages missing — checking internet to PyPI...
  powershell -NoProfile -Command "try { [System.Net.Dns]::GetHostEntry('files.pythonhosted.org') | Out-Null; exit 0 } catch { exit 1 }" >nul 2>&1
  if errorlevel 1 (
    echo.
    echo [ERROR] Cannot reach files.pythonhosted.org ^(DNS / network^).
    echo         pip needs internet to download packages the first time.
    echo         Fix: check Wi-Fi/VPN/firewall, then double-click start.bat again.
    echo.
    pause
    exit /b 1
  )
  echo       Installing backend packages ^(retries enabled^)...
  python -m pip install --upgrade pip --retries 5 --timeout 60
  python -m pip install -r "%ROOT%\backend\requirements.txt" --retries 5 --timeout 60
  if errorlevel 1 (
    echo.
    echo [ERROR] Backend pip install failed.
    echo         Usually this is a temporary network/DNS issue to PyPI.
    echo         Wait a minute, confirm internet works, then run start.bat again.
    echo         Packages already in .venv will be reused; only missing ones re-download.
    echo.
    pause
    exit /b 1
  )
  "%ROOT%\.venv\Scripts\python.exe" -c "import fastapi,uvicorn" >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Install finished but fastapi/uvicorn still missing. Check the log above.
    pause
    exit /b 1
  )
  echo [OK] Backend packages installed.
)
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

REM ---------- frontend deps (skip if already present) ----------
echo [2/5] Frontend dependencies...
if not exist "%ROOT%\frontend\package.json" (
  echo [ERROR] frontend\package.json missing. Clone or copy the frontend app into frontend\
  pause
  exit /b 1
)

if exist "%ROOT%\frontend\node_modules\react-scripts\package.json" (
  echo [OK] Frontend already installed — skipping npm install.
) else (
  echo       Running npm install (first run may take several minutes)...
  pushd "%ROOT%\frontend"
  call npm install
  if errorlevel 1 (
    echo [ERROR] npm install failed.
    popd
    pause
    exit /b 1
  )
  popd
  echo [OK] Frontend packages ready.
)
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

REM ---------- wait for servers, open sign-in ----------
echo [5/5] Waiting for servers, then opening Sign In...
echo       Backend  http://localhost:8000
echo       Frontend http://localhost:3000/authentication/sign-in
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
    echo       You can open http://localhost:3000/authentication/sign-in manually.
    goto done
  )
  timeout /t 2 /nobreak >nul
  goto wait_frontend
)
echo [OK] Frontend is responding.

start "" "http://localhost:3000/authentication/sign-in"

:done
echo.
echo ============================================================
echo   Launch complete. Leave CMD 1 and CMD 2 open while using
echo   the app. This setup window can be closed.
echo ============================================================
echo.
exit /b 0
