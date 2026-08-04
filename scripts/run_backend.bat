@echo off
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "PATH=%ROOT%\.venv\Scripts;%PATH%"
set "VIRTUAL_ENV=%ROOT%\.venv"
set "PYTHONPATH=%ROOT%;%ROOT%\backend"
echo ============================================================
echo   EFL IndexDB Backend  -  http://localhost:8000
echo   API docs             -  http://localhost:8000/docs
echo ============================================================
echo.
REM Only watch backend/ so edits under scripts/ do not kill the server
"%ROOT%\.venv\Scripts\uvicorn.exe" backend.api.main:app --reload --reload-dir "%ROOT%\backend" --port 8000
echo.
echo Backend process ended.
pause
