from fastapi import FastAPI
import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# =========================
# ENV CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

CARTRACK_API_URL = os.getenv("CARTRACK_API_URL")
CARTRACK_USERNAME = os.getenv("CARTRACK_USERNAME")
CARTRACK_PASSWORD = os.getenv("CARTRACK_PASSWORD")

# =========================
# STATE STORAGE (ANTI-SPAM)
# =========================
last_state = {}

# =========================
# TELEGRAM
# =========================
def send_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("Missing Telegram config")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        }, timeout=5)
    except Exception as e:
        print("Telegram error:", e)

# =========================
# CARTRACK API
# =========================
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
# HOME
# =========================
@app.get("/")
def home():
    return {"status": "car tracker running"}

# =========================
# MANUAL TEST
# =========================
@app.post("/tracker")
async def tracker(data: dict):

    ignition = data.get("ignition", False)
    speed = data.get("speed", 0)
    fuel = data.get("fuel", 100)

    if ignition:
        send_telegram("🔑 Ignition: ON")
    else:
        send_telegram("🔑 Ignition: OFF")

    if speed > 0:
        send_telegram(f"▶️ Moving: {speed} km/h")
    else:
        send_telegram("⏱️ Idle")

    if fuel < 20:
        send_telegram(f"⛽ Fuel LOW: {fuel}%")

    return {"status": "ok"}

from datetime import datetime

# =========================
# SMART FLEET SYNC
# =========================
@app.get("/sync-fleet")
def sync_fleet():

    data = get_fleet_data()

    if not data:
        return {"status": "error", "message": "No data from Cartrack"}

    vehicles = data.get("data") or data.get("vehicles") or []

    for v in vehicles:

        vid = v.get("vehicle_id") or v.get("id")
        name = v.get("vehicle_name") or v.get("registration") or "Vehicle"

        ignition = v.get("ignition", False)
        speed = v.get("speed", 0)
        fuel = v.get("fuel", 100)

        prev = last_state.get(vid, {})

        # IGNITION CHANGE ONLY
        if ignition != prev.get("ignition"):
            send_telegram(f"🔑 {name}: Ignition {'ON' if ignition else 'OFF'}")

        # MOVEMENT CHANGE ONLY
        moving = speed > 0
        if moving != prev.get("moving"):
            if moving:
                send_telegram(f"▶️ {name}: Moving {speed} km/h")
            else:
                send_telegram(f"⏱️ {name}: Idle")

        # FUEL ALERT (ONLY WHEN CROSSING 20%)
        if fuel < 20 and prev.get("fuel", 100) >= 20:

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            msg = (
                f"🚗 {name}\n"
                f"⛽ Fuel: {fuel}%\n"
                f"🕒 {now}"
            )

            send_telegram(msg)

        # SAVE STATE
        last_state[vid] = {
            "ignition": ignition,
            "moving": moving,
            "fuel": fuel
        }

    return {
        "status": "ok",
        "vehicles": len(vehicles)
    }