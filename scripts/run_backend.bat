@echo off
setlocal EnableExtensions
REM Always run from repo root so "import backend" resolves.
cd /d "%~dp0.."
set "ROOT=%CD%"

if not exist "%ROOT%\backend\api\main.py" (
  echo [ERROR] Could not find backend\api\main.py under %ROOT%
  echo         Run this script from the repo, or use start.bat.
  pause
  exit /b 1
)

REM Prefer project venv if present
if exist "%ROOT%\.venv\Scripts\python.exe" (
  set "PATH=%ROOT%\.venv\Scripts;%PATH%"
  set "VIRTUAL_ENV=%ROOT%\.venv"
  set "UVICORN_EXE=%ROOT%\.venv\Scripts\uvicorn.exe"
) else (
  set "UVICORN_EXE=uvicorn"
)

REM Repo root is required for "backend.*" and "research.*".
REM backend\ is also on the path so "api.*" imports used inside the app resolve.
set "PYTHONPATH=%ROOT%;%ROOT%\backend"

echo ============================================================
echo   EFL IndexDB Backend
echo   Working directory : %ROOT%
echo   PYTHONPATH        : %PYTHONPATH%
echo   API               : http://127.0.0.1:8000
echo   Docs              : http://127.0.0.1:8000/docs
echo ============================================================
echo.
echo   NOTE: Do NOT run "uvicorn backend.api.main:app" from inside
echo         the backend\ folder without setting PYTHONPATH to the
echo         repo root — that causes: No module named 'backend'
echo.

REM Watch backend + research so academic modules reload safely
"%UVICORN_EXE%" backend.api.main:app --reload --host 127.0.0.1 --port 8000 --reload-dir "%ROOT%\backend" --reload-dir "%ROOT%\research"
set "ERR=%ERRORLEVEL%"
echo.
if not "%ERR%"=="0" (
  echo Backend exited with code %ERR%.
  echo If you see WinError 10013 / address in use, free port 8000:
  echo   Get-NetTCPConnection -LocalPort 8000
  echo   Stop-Process -Id ^<PID^> -Force
)
echo Backend process ended.
pause
exit /b %ERR%
