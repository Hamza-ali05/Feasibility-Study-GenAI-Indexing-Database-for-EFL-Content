@echo off
setlocal
cd /d "%~dp0..\frontend"
REM Prevent CRA from auto-opening http://localhost:3000/ — start.bat opens Sign In instead
set "BROWSER=none"
set "REACT_APP_API_URL=http://localhost:8000"
REM Do not fail the CRA overlay/compile on Prettier CRLF noise on Windows
set "ESLINT_NO_DEV_ERRORS=true"
set "TSC_COMPILE_ON_ERROR=true"
echo ============================================================
echo   EFL IndexDB Frontend
echo   Dev server : http://localhost:3000
echo   Sign In    : http://localhost:3000/authentication/sign-in
echo   (Browser is opened by start.bat once this server is ready)
echo ============================================================
echo.
call npm.cmd start
echo.
echo Frontend process ended.
pause
