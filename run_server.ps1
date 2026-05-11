# Car Tracker Server Launcher
Write-Host "Starting Car Tracker FastAPI Server..." -ForegroundColor Green
Set-Location "d:\Car Tracker\car-tracker-system"
& "C:\Users\Stefanie Anne Obenza\.local\bin\python3.14.exe" -m uvicorn main:app --reload --host 0.0.0.0 --port 8000