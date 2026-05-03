@echo off
title REALM - Prediction Engine
echo ========================================
echo  REALM Prediction Engine - Starting...
echo ========================================
echo.

cd /d %~dp0

echo [1/2] Starting FastAPI prediction server on port 8420...
start "REALM API" cmd /k ".venv\Scripts\python.exe -m uvicorn realm.api.predict:app --host 127.0.0.1 --port 8420 --reload"

echo [2/2] Starting dashboard HTTP server on port 8080...
start "REALM Dashboard" cmd /k ".venv\Scripts\python.exe -m http.server 8080 --directory outputs"

timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo  REALM is running.
echo  Dashboard:  http://127.0.0.1:8080/realm_dashboard_v2.html
echo  API:        http://127.0.0.1:8420/api/predict
echo  API docs:   http://127.0.0.1:8420/docs
echo ========================================
echo.
echo Opening dashboard in browser...
start http://127.0.0.1:8080/realm_dashboard_v2.html

echo.
echo Press any key to stop all REALM services...
pause >nul

echo Stopping services...
taskkill /FI "WindowTitle eq REALM API*" /F >nul 2>&1
taskkill /FI "WindowTitle eq REALM Dashboard*" /F >nul 2>&1
echo Done.
