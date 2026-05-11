@echo off
echo.
echo ========================================
echo  Car Tracker FastAPI Server
echo ========================================
echo.
echo Starting server...
cd /d "%~dp0"
echo Workspace: %CD%
echo.
echo Server Configuration:
echo   - Host: 0.0.0.0
echo   - Port: 8000
echo   - URL: http://localhost:8000
echo   - Auto-reload: Enabled
echo   - Auto-sync: Every 60 seconds
echo.
echo API Endpoints:
echo   GET  http://localhost:8000/          (Health check)
echo   GET  http://localhost:8000/cars      (List all vehicles)
echo   GET  http://localhost:8000/car-status (Current vehicle status)
echo   POST http://localhost:8000/tracker   (Manual sync)
echo   GET  http://localhost:8000/sync-fleet (Manual full sync)
echo.
echo Starting uvicorn...
echo.
"C:\Users\Stefanie Anne Obenza\.local\bin\python3.14.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause