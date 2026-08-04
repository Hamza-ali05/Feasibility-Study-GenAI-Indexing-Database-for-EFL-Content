@echo off
setlocal
cd /d "%~dp0..\frontend"
set "BROWSER=none"
set "REACT_APP_API_URL=http://localhost:8000"
REM Do not fail the CRA overlay/compile on Prettier CRLF noise on Windows
set "ESLINT_NO_DEV_ERRORS=true"
set "TSC_COMPILE_ON_ERROR=true"
echo ============================================================
echo   EFL IndexDB Frontend  -  http://localhost:3000/authentication/sign-in
echo ============================================================
echo.
call npm.cmd start
echo.
echo Frontend process ended.
pause
