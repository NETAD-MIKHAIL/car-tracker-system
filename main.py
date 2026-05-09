from fastapi import FastAPI
import requests
from requests.auth import HTTPBasicAuth

app = FastAPI()

import os
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CARTRACK_API_URL = os.getenv("CARTRACK_API_URL")
CARTRACK_USERNAME = os.getenv("CARTRACK_USERNAME")
CARTRACK_PASSWORD = os.getenv("CARTRACK_PASSWORD")

def send_telegram(message: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        }, timeout=5)
    except Exception as e:
        print("Telegram error:", e)

def get_fleet_data():
    try:
        response = requests.get(
            CARTRACK_API_URL,
            auth=HTTPBasicAuth(CARTRACK_USERNAME, CARTRACK_PASSWORD),
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("Cartrack API error:", e)
        return None

# =========================
# HOME ROUTE
# =========================
@app.get("/")
def home():
    return {"status": "car tracker running"}

# =========================
# MANUAL TEST TRACKER
# =========================
@app.post("/tracker")
async def tracker(data: dict):

    ignition = data.get("ignition", False)
    speed = data.get("speed", 0)
    fuel = data.get("fuel", 100)

    messages = []

    if ignition:
        messages.append("🔑 Ignition: ON")

    if speed > 0:
        messages.append(f"▶️ Moving: {speed} km/h")
    else:
        messages.append("⏱️ Idle")

    if fuel < 20:
        messages.append(f"⛽ Fuel LOW: {fuel}%")

    for msg in messages:
        send_telegram(msg)

    return {
        "status": "ok",
        "ignition": ignition,
        "speed": speed,
        "fuel": fuel
    }

# =========================
# CARTRACK SYNC (REAL DATA)
# =========================
@app.get("/sync-fleet")
def sync_fleet():

    data = get_fleet_data()

    if not data:
        return {"status": "error", "message": "No data from Cartrack"}

    vehicles = data.get("vehicles") or data.get("data") or []

    for v in vehicles:

        name = v.get("name", "Vehicle")
        ignition = v.get("ignition", False)
        speed = v.get("speed", 0)
        fuel = v.get("fuel", 100)

        if ignition:
            send_telegram(f"🔑 {name}: Ignition ON")

        if speed > 0:
            send_telegram(f"▶️ {name}: Moving {speed} km/h")
        else:
            send_telegram(f"⏱️ {name}: Idle")

        if fuel < 20:
            send_telegram(f"⛽ {name}: LOW FUEL {fuel}%")

    return {
        "status": "ok",
        "vehicles": len(vehicles)
    }