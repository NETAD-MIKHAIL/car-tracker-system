# Car Tracker System

A FastAPI-based vehicle tracking system that monitors fleet vehicles and sends alerts via Telegram.

## Auto-Run Options

### 🚀 Option 1: Desktop Shortcut (Easiest)

Double-click the "Car Tracker Server" shortcut on your desktop to start the server instantly.

### 📁 Option 2: Batch File

Double-click `run_server.bat` in the project folder.

### 💻 Option 3: PowerShell Script

Right-click `run_server.ps1` → "Run with PowerShell"

### 🔧 Option 4: VS Code Tasks

1. Press `Ctrl+Shift+P` (or `Cmd+Shift+P` on Mac)
2. Type "Tasks: Run Task"
3. Select "Run FastAPI Server"

### 🐛 Option 5: Debug Mode

1. Press `F5` or go to Run → Start Debugging
2. Select "FastAPI Server" configuration

### 💻 Option 6: Command Line

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

- `GET /` - Health check
- `POST /tracker` - Manual vehicle tracking test
- `GET /cars` - Get all vehicles from Cartrack API
- `GET /sync-fleet` - Sync fleet and send alerts

## Configuration

Create a `.env` file with:

```
BOT_TOKEN=your_telegram_bot_token
CHAT_ID=your_telegram_chat_id
CARTRACK_API_URL=https://fleetapi-ph.cartrack.com/rest/vehicles/status
CARTRACK_USERNAME=your_username
CARTRACK_PASSWORD=your_password
```

## Features

- 🚗 Real-time vehicle monitoring
- ⚡ Speed limit alerts (80 km/h default)
- 🔑 Ignition status tracking
- ⏱️ Idle time monitoring (10 minutes limit)
- ⛽ Fuel level alerts (< 20%)
- 📱 Telegram notifications

Server runs on: http://localhost:8000
