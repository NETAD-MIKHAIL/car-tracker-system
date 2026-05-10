from fastapi import FastAPI
import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

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
SPEED_LIMIT_KMH = 80
IDLE_LIMIT_MINUTES = 10
VEHICLE_ID_KEYS = (
    "vehicle_id",
    "vehicleId",
    "id",
    "unit_id",
    "unitId",
    "asset_id",
    "assetId",
    "device_id",
    "deviceId",
    "registration",
)
VEHICLE_NAME_KEYS = (
    "vehicle_name",
    "vehicleName",
    "registration",
    "reg",
    "plate",
    "plate_number",
    "license_plate",
    "name",
    "label",
)
VEHICLE_LIST_KEYS = (
    "data",
    "vehicles",
    "vehicle",
    "items",
    "results",
    "fleet",
    "assets",
    "units",
)

# =========================
# STATE STORAGE (ANTI-SPAM)
# =========================
last_state = {}

def first_present(*values):
    for value in values:
        if value is not None:
            return value
    return None

def first_key(data: dict, keys):
    for key in keys:
        value = data.get(key)

        if value is not None:
            return value

    return None

def to_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default

def to_bool(value, default=False):
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        normalized = value.strip().lower()

        if normalized in {"true", "on", "1", "yes", "y", "running"}:
            return True

        if normalized in {"false", "off", "0", "no", "n", "stopped"}:
            return False

    return bool(value)

def format_speed(speed):
    if float(speed).is_integer():
        return str(int(speed))

    return str(speed)

def format_minutes(minutes):
    minutes = to_number(minutes, 0)
    minutes = max(0, minutes)

    if float(minutes).is_integer():
        minute_text = str(int(minutes))
    else:
        minute_text = str(round(minutes, 1))

    return f"{minute_text} minute{'s' if minute_text != '1' else ''}"

def format_alert(header: str, *lines):
    return "\n".join([header, "", *lines])

def elapsed_minutes(start_time, end_time):
    if not isinstance(start_time, datetime):
        return 0

    if start_time.tzinfo and not end_time.tzinfo:
        end_time = end_time.replace(tzinfo=start_time.tzinfo)
    elif end_time.tzinfo and not start_time.tzinfo:
        start_time = start_time.replace(tzinfo=end_time.tzinfo)

    return max(0, (end_time - start_time).total_seconds() / 60)

def format_event_time(event_time):
    text = str(event_time)
    upper_text = text.upper()

    if (
        " PHT" in upper_text
        or " UTC" in upper_text
        or " GMT" in upper_text
        or text.endswith("Z")
        or "+" in text[10:]
    ):
        return text

    return f"{text} PHT"

def format_location_time(location: str, event_time: str):
    return (
        f"📍 {location}",
        f"🕘 {format_event_time(event_time)}"
    )

def format_speeding_alert(name: str, speed, location: str, event_time: str):
    speed_text = format_speed(speed)
    excess = max(0, speed - SPEED_LIMIT_KMH)
    excess_text = format_speed(excess)

    return format_alert(
        f"🚨 SPEEDING - {name}",
        f"⚡ Speed: {speed_text} km/h (Limit: {SPEED_LIMIT_KMH} km/h)",
        f"📈 Excess: +{excess_text} km/h over limit",
        *format_location_time(location, event_time)
    )

def format_ignition_alert(name: str, ignition: bool, location: str, event_time: str):
    icon = "🔑" if ignition else "🔒"
    status = "IGNITION ON" if ignition else "IGNITION OFF"

    return format_alert(
        f"{icon} {status} - {name}",
        *format_location_time(location, event_time)
    )

def format_motion_alert(name: str, location: str, event_time: str):
    return format_alert(
        f"🟢 MOTION STARTED - {name}",
        *format_location_time(location, event_time)
    )

def format_idle_alert(name: str, location: str, event_time: str):
    return format_alert(
        f"⏱ IDLING - {name}",
        *format_location_time(location, event_time)
    )

def format_idling_too_long_alert(name: str, idle_minutes, location: str, event_time: str):
    return format_alert(
        f"⏱ IDLING TOO LONG - {name}",
        f"⏱ Idling for {format_minutes(idle_minutes)}",
        *format_location_time(location, event_time)
    )

def format_fuel_alert(name: str, fuel, location: str, event_time: str):
    return format_alert(
        f"⛽ FUEL LOW - {name}",
        f"Fuel: {format_speed(fuel)}%",
        *format_location_time(location, event_time)
    )

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

def get_vehicle_id(vehicle: dict):
    return first_key(vehicle, VEHICLE_ID_KEYS)

def get_vehicle_name(vehicle: dict):
    return first_key(vehicle, VEHICLE_NAME_KEYS) or get_vehicle_id(vehicle) or "Vehicle"

def get_vehicle_speed(vehicle: dict):
    return to_number(
        first_key(
            vehicle,
            (
                "speed",
                "speed_kph",
                "speedKph",
                "speed_kmh",
                "speedKmh",
                "current_speed",
                "currentSpeed",
            )
        ),
        0
    )

def get_vehicle_fuel(vehicle: dict):
    return to_number(
        first_key(
            vehicle,
            (
                "fuel",
                "fuel_level",
                "fuelLevel",
                "fuel_percent",
                "fuelPercent",
            )
        ),
        100
    )

def get_vehicle_idle_minutes(vehicle: dict):
    idle_minutes = first_key(
        vehicle,
        (
            "idle_minutes",
            "idling_minutes",
            "idle_duration_minutes",
            "idleDurationMinutes",
            "idle_time_minutes",
            "idleTimeMinutes",
        )
    )

    if idle_minutes is not None:
        return to_number(idle_minutes, 0)

    idle_seconds = first_key(
        vehicle,
        (
            "idle_seconds",
            "idling_seconds",
            "idle_duration_seconds",
            "idleDurationSeconds",
            "idle_time_seconds",
            "idleTimeSeconds",
        )
    )

    if idle_seconds is not None:
        return to_number(idle_seconds, 0) / 60

    return None

def get_idle_status(ignition: bool, moving: bool, prev: dict, api_idle_minutes=None):
    if not ignition or moving:
        return None, 0, False, 0, 0

    current_time = datetime.now()
    previous_alert_count = int(prev.get("idling_too_long_alert_count", 0) or 0)

    if api_idle_minutes is not None:
        idle_minutes = max(0, to_number(api_idle_minutes, 0))
        idle_started_at = current_time - timedelta(minutes=idle_minutes)
    else:
        idle_started_at = prev.get("idle_started_at") or current_time
        idle_minutes = elapsed_minutes(idle_started_at, current_time)

    current_alert_count = int(idle_minutes // IDLE_LIMIT_MINUTES)

    return (
        idle_started_at,
        idle_minutes,
        idle_minutes >= IDLE_LIMIT_MINUTES,
        current_alert_count,
        previous_alert_count
    )

def looks_like_vehicle(record: dict):
    if not isinstance(record, dict):
        return False

    has_identity = first_key(record, VEHICLE_ID_KEYS + VEHICLE_NAME_KEYS) is not None

    if not has_identity:
        return False

    has_wrapper_list = any(
        isinstance(record.get(key), list)
        for key in VEHICLE_LIST_KEYS
    )

    return not has_wrapper_list

def extract_vehicles(payload):
    vehicles = []
    seen = set()

    def add_vehicle(vehicle):
        vehicle_id = get_vehicle_id(vehicle) or get_vehicle_name(vehicle) or id(vehicle)
        key = str(vehicle_id)

        if key in seen:
            return

        seen.add(key)
        vehicles.append(vehicle)

    def scan(value):
        if isinstance(value, list):
            for item in value:
                scan(item)
            return

        if not isinstance(value, dict):
            return

        for key in VEHICLE_LIST_KEYS:
            nested = value.get(key)

            if nested is not None:
                scan(nested)

        if looks_like_vehicle(value):
            add_vehicle(value)
            return

        for nested in value.values():
            if isinstance(nested, (dict, list)):
                scan(nested)

    scan(payload)
    return vehicles

def get_vehicle_time(vehicle: dict):
    return (
        vehicle.get("event_time")
        or vehicle.get("event_ts")
        or vehicle.get("timestamp")
        or vehicle.get("time")
        or vehicle.get("gps_time")
        or vehicle.get("gpsTime")
        or vehicle.get("server_time")
        or vehicle.get("serverTime")
        or vehicle.get("recorded_at")
        or vehicle.get("recordedAt")
        or vehicle.get("last_update")
        or vehicle.get("updated_at")
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )

def get_ignition(vehicle: dict):
    return to_bool(
        first_present(
            vehicle.get("ignition"),
            vehicle.get("engine"),
            vehicle.get("engine_on"),
            vehicle.get("engine_status"),
            vehicle.get("ignition_status"),
            vehicle.get("acc")
        ),
        False
    )

def get_vehicle_location(vehicle: dict):
    location = first_present(
        vehicle.get("location"),
        vehicle.get("position"),
        vehicle.get("current_position"),
        vehicle.get("gps"),
        {}
    )

    if isinstance(location, str):
        return location

    if not isinstance(location, dict):
        location = {}

    latitude = first_present(
        vehicle.get("latitude"),
        vehicle.get("lat"),
        location.get("latitude"),
        location.get("lat")
    )
    longitude = first_present(
        vehicle.get("longitude"),
        vehicle.get("lng"),
        vehicle.get("lon"),
        location.get("longitude"),
        location.get("lng"),
        location.get("lon")
    )

    location_name = first_present(
        vehicle.get("location_name"),
        vehicle.get("position_description"),
        vehicle.get("location_description"),
        vehicle.get("area"),
        location.get("location_name"),
        location.get("position_description"),
        location.get("location_description"),
        location.get("area"),
        location.get("name"),
        location.get("label"),
        location.get("description"),
        location.get("address")
    )

    if location_name:
        return str(location_name)

    if latitude is not None and longitude is not None:
        return f"{latitude}, {longitude}"

    return "Location unavailable"

def format_vehicle_status(name: str, speed, location: str, event_time: str):
    speeding = speed > SPEED_LIMIT_KMH
    speed_text = format_speed(speed)
    speed_status = "SPEEDING" if speeding else "Within speed limit"

    return format_alert(
        f"🚗 STATUS - {name}",
        f"⚡ Speed: {speed_text} km/h (Limit: {SPEED_LIMIT_KMH} km/h)",
        f"⚠️ Status: {speed_status}",
        *format_location_time(location, event_time)
    )

def build_vehicle_status(vehicle: dict):
    speed = get_vehicle_speed(vehicle)
    idle_minutes = get_vehicle_idle_minutes(vehicle)
    idling_too_long = (
        get_ignition(vehicle)
        and speed <= 0
        and idle_minutes is not None
        and idle_minutes >= IDLE_LIMIT_MINUTES
    )

    return {
        "id": get_vehicle_id(vehicle) or get_vehicle_name(vehicle),
        "name": get_vehicle_name(vehicle),
        "ignition": get_ignition(vehicle),
        "location": get_vehicle_location(vehicle),
        "time": get_vehicle_time(vehicle),
        "speed": speed,
        "speeding": speed > SPEED_LIMIT_KMH,
        "speed_limit": SPEED_LIMIT_KMH,
        "idle_minutes": idle_minutes,
        "idling_too_long": idling_too_long,
        "idle_limit_minutes": IDLE_LIMIT_MINUTES
    }

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

    ignition = get_ignition(data)
    speed = get_vehicle_speed(data)
    fuel = get_vehicle_fuel(data)
    location = get_vehicle_location(data)
    event_time = get_vehicle_time(data)
    speeding = speed > SPEED_LIMIT_KMH
    moving = speed > 0
    idle_minutes = get_vehicle_idle_minutes(data)
    idling_too_long = (
        ignition
        and not moving
        and idle_minutes is not None
        and idle_minutes >= IDLE_LIMIT_MINUTES
    )

    send_telegram(format_vehicle_status("Manual Test", speed, location, event_time))

    if ignition:
        send_telegram(format_ignition_alert("Manual Test", True, location, event_time))
    else:
        send_telegram(format_ignition_alert("Manual Test", False, location, event_time))

    if speeding:
        send_telegram(format_speeding_alert("Manual Test", speed, location, event_time))
    elif ignition and moving:
        send_telegram(format_motion_alert("Manual Test", location, event_time))
    elif idling_too_long:
        send_telegram(format_idling_too_long_alert("Manual Test", idle_minutes, location, event_time))
    elif ignition:
        send_telegram(format_idle_alert("Manual Test", location, event_time))

    if fuel < 20:
        send_telegram(format_fuel_alert("Manual Test", fuel, location, event_time))

    return {
        "status": "ok",
        "location": location,
        "time": event_time,
        "speed": speed,
        "speeding": speeding,
        "speed_limit": SPEED_LIMIT_KMH,
        "idle_minutes": idle_minutes,
        "idling_too_long": idling_too_long,
        "idle_limit_minutes": IDLE_LIMIT_MINUTES
    }

# =========================
# AUTO DETECT CARS
# =========================
@app.get("/cars")
def cars():

    data = get_fleet_data()

    if not data:
        return {"status": "error", "message": "No data from Cartrack"}

    vehicles = extract_vehicles(data)

    return {
        "status": "ok",
        "vehicles": len(vehicles),
        "data": [build_vehicle_status(vehicle) for vehicle in vehicles]
    }

# =========================
# SMART FLEET SYNC
# =========================
@app.get("/sync-fleet")
def sync_fleet():

    data = get_fleet_data()

    if not data:
        return {"status": "error", "message": "No data from Cartrack"}

    vehicles = extract_vehicles(data)

    vehicle_statuses = []

    for v in vehicles:

        name = get_vehicle_name(v)
        vid = get_vehicle_id(v) or name

        ignition = get_ignition(v)
        speed = get_vehicle_speed(v)
        fuel = get_vehicle_fuel(v)
        location = get_vehicle_location(v)
        event_time = get_vehicle_time(v)
        speeding = speed > SPEED_LIMIT_KMH

        prev = last_state.get(vid, {})
        moving = speed > 0
        idle_started_at, idle_minutes, idling_too_long, idle_alert_count, previous_idle_alert_count = get_idle_status(
            ignition,
            moving,
            prev,
            get_vehicle_idle_minutes(v)
        )

        # IGNITION CHANGE ONLY
        if ignition != prev.get("ignition"):
            send_telegram(format_ignition_alert(name, ignition, location, event_time))

        # MOVEMENT CHANGE ONLY, WHILE ENGINE IS ON
        if ignition and moving != prev.get("moving"):
            if moving:
                send_telegram(format_motion_alert(name, location, event_time))
            elif not idling_too_long:
                send_telegram(format_idle_alert(name, location, event_time))

        # IDLING TOO LONG ALERT (EVERY 10 IDLE MINUTES)
        if idling_too_long and idle_alert_count > previous_idle_alert_count:
            send_telegram(format_idling_too_long_alert(name, idle_minutes, location, event_time))
            previous_idle_alert_count = idle_alert_count

        # SPEEDING ALERT (ONLY WHEN CROSSING SPEED LIMIT)
        if speeding and not prev.get("speeding", False):
            send_telegram(format_speeding_alert(name, speed, location, event_time))

        # FUEL ALERT (ONLY WHEN CROSSING 20%)
        if fuel < 20 and prev.get("fuel", 100) >= 20:

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            send_telegram(format_fuel_alert(name, fuel, location, event_time or now))

        vehicle_statuses.append({
            "id": vid,
            "name": name,
            "location": location,
            "time": event_time,
            "speed": speed,
            "speeding": speeding,
            "speed_limit": SPEED_LIMIT_KMH,
            "idle_minutes": idle_minutes,
            "idling_too_long": idling_too_long,
            "idle_limit_minutes": IDLE_LIMIT_MINUTES,
            "idle_alert_count": previous_idle_alert_count
        })

        # SAVE STATE
        last_state[vid] = {
            "ignition": ignition,
            "moving": moving,
            "fuel": fuel,
            "speed": speed,
            "speeding": speeding,
            "location": location,
            "time": event_time,
            "idle_started_at": idle_started_at,
            "idle_minutes": idle_minutes,
            "idling_too_long": idling_too_long,
            "idling_too_long_alert_count": previous_idle_alert_count
        }

    return {
        "status": "ok",
        "vehicles": len(vehicles),
        "data": vehicle_statuses
    }
