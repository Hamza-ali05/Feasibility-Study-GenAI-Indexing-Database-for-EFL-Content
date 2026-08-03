@echo off
setlocal
cd /d "%~dp0..\frontend"
set "BROWSER=none"
set "REACT_APP_API_URL=http://localhost:8000"
echo ============================================================
echo   EFL IndexDB Frontend  -  http://localhost:3000/authentication/sign-in
echo ============================================================
echo.
call npm start
pause
