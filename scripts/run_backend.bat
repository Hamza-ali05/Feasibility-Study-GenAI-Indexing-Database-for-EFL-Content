@echo off
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
call "%ROOT%\.venv\Scripts\activate.bat"
set "PYTHONPATH=%ROOT%;%ROOT%\backend"
echo ============================================================
echo   EFL IndexDB Backend  -  http://localhost:8000
echo   API docs             -  http://localhost:8000/docs
echo ============================================================
echo.
"%ROOT%\.venv\Scripts\uvicorn.exe" backend.api.main:app --reload --port 8000
pause
