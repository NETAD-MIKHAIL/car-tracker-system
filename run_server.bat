@echo off
echo Starting Car Tracker FastAPI Server...
cd /d "%~dp0"
"C:\Users\Stefanie Anne Obenza\.local\bin\python3.14.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
pause