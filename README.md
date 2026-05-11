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

## 🚀 Online Deployment (Free Options)

### Option 1: Railway (Recommended - Easiest)

Railway offers a generous free tier perfect for this app.

1. **Sign up**: Go to [railway.app](https://railway.app) and create an account
2. **Connect GitHub**: Link your GitHub account
3. **Deploy**: Click "Deploy from GitHub" and select this repository
4. **Environment Variables**: Add your environment variables in Railway dashboard:
   - `BOT_TOKEN`
   - `CHAT_ID`
   - `CARTRACK_API_URL`
   - `CARTRACK_USERNAME`
   - `CARTRACK_PASSWORD`
5. **Done!** Your app will be live at `https://your-project-name.up.railway.app`

### Option 2: Render

Render provides free web services with 750 hours/month.

1. **Sign up**: Go to [render.com](https://render.com) and create an account
2. **New Web Service**: Click "New +" → "Web Service"
3. **Connect Repository**: Link your GitHub repository
4. **Configure**:
   - **Runtime**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment Variables**: Add your `.env` variables
6. **Deploy**: Click "Create Web Service"

### Option 3: Fly.io

Fly.io offers 3 free VMs with persistent storage.

1. **Install Fly CLI**: `curl -L https://fly.io/install.sh | sh`
2. **Sign up**: `fly auth signup`
3. **Launch**: `fly launch` in your project directory
4. **Configure**:
   - Choose a region close to you
   - Set environment variables: `fly secrets set BOT_TOKEN=your_token`
5. **Deploy**: `fly deploy`

### Option 4: Replit

Replit offers free hosting with web server support.

1. **Create Repl**: Go to [replit.com](https://replit.com) and create a Python repl
2. **Upload Files**: Upload your project files
3. **Install Dependencies**: Run `pip install -r requirements.txt` in shell
4. **Run**: Use `uvicorn main:app --host 0.0.0.0 --port 8080`
5. **Keep Alive**: Replit automatically keeps free repls alive

## 📋 Requirements

- Python 3.11+
- Telegram Bot Token
- Cartrack API credentials
- Internet connection for geocoding and API calls

## Features

- 🚗 Real-time vehicle monitoring
- ⚡ Speed limit alerts (80 km/h default)
- 🔑 Ignition status tracking
- ⏱️ Idle time monitoring (10 minutes limit)
- ⛽ Fuel level alerts (< 20%)
- 📱 Telegram notifications

Server runs on: http://localhost:8000
