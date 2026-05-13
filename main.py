import asyncio
import json
from fastapi import FastAPI
import requests
from requests.auth import HTTPBasicAuth
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
SYNC_INTERVAL_SECONDS = int(os.getenv("SYNC_INTERVAL_SECONDS", "60"))
ALERT_DEDUPE_SECONDS = int(os.getenv("ALERT_DEDUPE_SECONDS", str(SYNC_INTERVAL_SECONDS)))
SPEED_LIMIT_KMH = 120
LOW_FUEL_LITERS = 4
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
VEHICLE_MODEL_KEYS = (
    "model",
    "vehicle_model",
    "vehicleModel",
    "make_model",
    "makeModel",
    "asset_model",
    "assetModel",
)
VEHICLE_MODEL_BY_PLATE = {
    "KAR6444": "Toyota Hilux",
    "KAR6412": "Toyota Innova",
    "KAR6558": "Toyota Hilux",
}
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
last_alert_messages = {}
auto_sync_task = None
ALERT_CACHE_FILE = ".alert_cache.json"

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

def first_nested_key(data, keys):
    if isinstance(data, dict):
        value = first_key(data, keys)

        if value is not None:
            return value

        for nested in data.values():
            value = first_nested_key(nested, keys)

            if value is not None:
                return value

    if isinstance(data, list):
        for item in data:
            value = first_nested_key(item, keys)

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

def format_percent(value):
    if value is None:
        return "Unknown"

    return format_speed(value)

def format_fuel_liters(value):
    if value is None:
        return "Unknown"

    return f"{format_percent(value)} L"

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

def get_manila_tz():
    try:
        return ZoneInfo("Asia/Manila")
    except ZoneInfoNotFoundError:
        return timezone(timedelta(hours=8))


def parse_event_time(event_time):
    text = str(event_time).strip()
    if not text:
        return None

    if text.endswith("Z"):
        try:
            dt = datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ")
            dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(get_manila_tz())
        except ValueError:
            return None

    try:
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=get_manila_tz())
        return dt.astimezone(get_manila_tz())
    except ValueError:
        pass

    for fmt in [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
    ]:
        try:
            dt = datetime.strptime(text, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=get_manila_tz())
            return dt.astimezone(get_manila_tz())
        except ValueError:
            continue

    return None


def format_event_time(event_time):
    dt = parse_event_time(event_time)
    if dt is not None:
        return dt.strftime("%Y-%m-%d %I:%M:%S %p PHT")

    text = str(event_time).strip()
    if not text:
        return "Unknown time"
    return text

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

def format_car_status_alert(name: str, status_data: dict):
    speed = status_data.get('speed', 0)
    location = status_data.get('location', 'Unknown')
    event_time = status_data.get('time', 'Unknown')
    ignition = status_data.get('ignition', False)
    speeding = status_data.get('speeding', False)
    idling_too_long = status_data.get('idling_too_long', False)
    idle_minutes = status_data.get('idle_minutes')

    icon = "🚗" if ignition else "🛑"
    ignition_status = "RUNNING" if ignition else "STOPPED"
    speed_text = format_speed(speed)

    lines = [
        f"Speed: {speed_text} km/h",
        f"Status: {ignition_status}",
    ]

    if speeding:
        lines.append(f"⚠️ SPEEDING!")

    if idling_too_long and idle_minutes:
        lines.append(f"⏱ Idling for {format_minutes(idle_minutes)}")

    return format_alert(
        f"{icon} STATUS - {name}",
        *lines,
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

def format_location_update_alert(name: str, speed, fuel, location: str, event_time: str):
    return format_alert(
        f"📍 LOCATION UPDATE - {name}",
        f"📍 {location}",
        f"⚡ Speed: {format_speed(speed)} km/h",
        f"⛽ Fuel: {format_fuel_liters(fuel)}",
        f"🕘 {format_event_time(event_time)}"
    )

def format_idle_alert(name: str, location: str, event_time: str):
    return format_alert(
        f"⏱ IDLING - {name}",
        *format_location_time(location, event_time)
    )

def format_idling_too_long_alert(name: str, idle_minutes, fuel, location: str, event_time: str):
    return format_alert(
        f"⏱ IDLING TOO LONG - {name}",
        f"⏱ Idling for {format_minutes(idle_minutes)}",
        f"⛽ Fuel: {format_fuel_liters(fuel)}",
        *format_location_time(location, event_time)
    )

def format_fuel_alert(name: str, fuel, location: str, event_time: str):
    return format_alert(
        f"⛽ FUEL LOW - {name}",
        f"Fuel: {format_fuel_liters(fuel)} (Warning below {LOW_FUEL_LITERS} L)",
        *format_location_time(location, event_time)
    )

def already_sent_recently(message: str, now: datetime):
    last_sent_at = last_alert_messages.get(message)

    if last_sent_at and (now - last_sent_at).total_seconds() < ALERT_DEDUPE_SECONDS:
        return True

    try:
        with open(ALERT_CACHE_FILE, "r", encoding="utf-8") as cache_file:
            cache = json.load(cache_file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        cache = {}

    cutoff = now.timestamp() - ALERT_DEDUPE_SECONDS
    cache = {
        cached_message: sent_at
        for cached_message, sent_at in cache.items()
        if sent_at >= cutoff
    }

    if cache.get(message, 0) >= cutoff:
        last_alert_messages[message] = datetime.fromtimestamp(cache[message])
        return True

    cache[message] = now.timestamp()
    last_alert_messages[message] = now

    try:
        with open(ALERT_CACHE_FILE, "w", encoding="utf-8") as cache_file:
            json.dump(cache, cache_file)
    except OSError as e:
        print(f"Alert cache write failed: {e}")

    return False

def send_vehicle_alerts(alerts):
    if alerts:
        message = alerts[0]
        now = datetime.now()

        if already_sent_recently(message, now):
            return
        send_telegram(message)

# =========================
# TELEGRAM
# =========================
def send_telegram(message: str):
    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Missing Telegram config - BOT_TOKEN or CHAT_ID not set")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    try:
        response = requests.post(url, data={
            "chat_id": CHAT_ID,
            "text": message
        }, timeout=5)

        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print(f"✅ Telegram alert sent! Message ID: {result.get('result', {}).get('message_id')}")
            else:
                print(f"❌ Telegram API error: {result}")
        else:
            print(f"❌ HTTP error {response.status_code}: {response.text}")

    except Exception as e:
        print(f"❌ Telegram exception: {e}")

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

def get_vehicle_model(vehicle: dict):
    name = str(get_vehicle_name(vehicle)).strip().upper()
    return VEHICLE_MODEL_BY_PLATE.get(name) or first_key(vehicle, VEHICLE_MODEL_KEYS)

def get_vehicle_display_name(vehicle: dict):
    name = str(get_vehicle_name(vehicle))
    model = get_vehicle_model(vehicle)

    if model:
        return f"{name} ({model})"

    return name

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
    fuel_level_keys = (
        "fuel_level",
        "fuelLevel",
        "tank_level",
        "tankLevel",
        "fuel",
    )

    fuel_value = first_nested_key(vehicle, fuel_level_keys)

    if isinstance(fuel_value, dict):
        fuel_value = first_key(
            fuel_value,
            (
                "level",
                "value",
                "remaining",
                "liters",
                "litres",
                "liter",
                "litre",
            )
        )

    if fuel_value is None:
        return None

    fuel = to_number(fuel_value, None)

    if fuel is None:
        return None

    return fuel

def get_vehicle_fuel_percent(vehicle: dict):
    fuel_percent_keys = (
        "fuel_percent",
        "fuelPercent",
        "fuel_percentage",
        "fuelPercentage",
        "fuel_level_percentage",
        "fuelLevelPercentage",
        "fuel_tank_percentage",
        "fuelTankPercentage",
        "fuel_level_perc",
        "fuelLevelPerc",
        "fuel_perc",
        "fuelPerc",
    )

    fuel_percent = first_nested_key(vehicle, fuel_percent_keys)

    if isinstance(fuel_percent, dict):
        fuel_percent = first_key(
            fuel_percent,
            (
                "percent",
                "percentage",
                "value",
                "remaining",
                "fuel_percent",
                "fuelPercent",
            )
        )

    if fuel_percent is None:
        return None

    fuel_percent = to_number(fuel_percent, None)

    if fuel_percent is None:
        return None

    if 0 < fuel_percent <= 1:
        return fuel_percent * 100

    return fuel_percent

def is_low_fuel(fuel_liters):
    return fuel_liters is not None and fuel_liters < LOW_FUEL_LITERS

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

    # Handle nested location object from Cartrack API
    if isinstance(location, dict):
        # Check for position_description first (already geocoded)
        if 'position_description' in location and location['position_description']:
            return str(location['position_description'])

        # Extract coordinates from nested object
        latitude = location.get('latitude') or location.get('lat')
        longitude = location.get('longitude') or location.get('lng')

        if latitude is not None and longitude is not None:
            try:
                street_name = reverse_geocode(float(latitude), float(longitude))
                if street_name:
                    return street_name
            except Exception as e:
                print(f"Geocoding error: {e}")

        # Fallback to coordinates
        if latitude is not None and longitude is not None:
            return f"{latitude}, {longitude}"

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

    # Try reverse geocoding if we have coordinates
    if latitude is not None and longitude is not None:
        try:
            street_name = reverse_geocode(float(latitude), float(longitude))
            if street_name:
                return street_name
        except Exception as e:
            print(f"Geocoding error: {e}")

    if latitude is not None and longitude is not None:
        return f"{latitude}, {longitude}"

    return "Location unavailable"

def reverse_geocode(latitude: float, longitude: float) -> str:
    """
    Convert coordinates to street name using Nominatim (OpenStreetMap)
    """
    try:
        # Using Nominatim API (free, no API key required)
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={latitude}&lon={longitude}&zoom=18&addressdetails=1"

        response = requests.get(url, headers={
            'User-Agent': 'CarTracker/1.0'
        }, timeout=5)

        if response.status_code == 200:
            data = response.json()

            if 'address' in data:
                address = data['address']

                # Try to get the most specific street information
                street_parts = []

                # Primary road/street
                if 'road' in address:
                    street_parts.append(address['road'])
                elif 'highway' in address:
                    street_parts.append(address['highway'])
                elif 'pedestrian' in address:
                    street_parts.append(address['pedestrian'])
                elif 'path' in address:
                    street_parts.append(address['path'])

                # Add suburb/neighborhood if available
                if 'suburb' in address:
                    street_parts.append(address['suburb'])
                elif 'neighbourhood' in address:
                    street_parts.append(address['neighbourhood'])
                elif 'residential' in address:
                    street_parts.append(address['residential'])

                # Add city/municipality
                if 'city' in address:
                    street_parts.append(address['city'])
                elif 'town' in address:
                    street_parts.append(address['town'])
                elif 'municipality' in address:
                    street_parts.append(address['municipality'])

                if street_parts:
                    return ", ".join(street_parts)

            # Fallback to display name if no structured address
            if 'display_name' in data:
                # Take first 2-3 parts of the display name
                parts = data['display_name'].split(',')[:3]
                return ", ".join(parts).strip()

    except Exception as e:
        print(f"Reverse geocoding failed: {e}")

    return None

def format_vehicle_status(name: str, speed, location: str, event_time: str):
    speeding = speed >= SPEED_LIMIT_KMH
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
    fuel = get_vehicle_fuel(vehicle)
    fuel_percent = get_vehicle_fuel_percent(vehicle)
    idle_minutes = get_vehicle_idle_minutes(vehicle)
    idling_too_long = (
        get_ignition(vehicle)
        and speed <= 0
        and idle_minutes is not None
        and idle_minutes >= IDLE_LIMIT_MINUTES
    )

    return {
        "id": get_vehicle_id(vehicle) or get_vehicle_name(vehicle),
        "name": get_vehicle_display_name(vehicle),
        "model": get_vehicle_model(vehicle),
        "ignition": get_ignition(vehicle),
        "location": get_vehicle_location(vehicle),
        "time": format_event_time(get_vehicle_time(vehicle)),  # Format to 12-hour
        "speed": speed,
        "speeding": speed >= SPEED_LIMIT_KMH,
        "speed_limit": SPEED_LIMIT_KMH,
        "fuel": fuel,
        "fuel_liters": fuel,
        "fuel_percent": fuel_percent,
        "low_fuel": is_low_fuel(fuel),
        "low_fuel_liters": LOW_FUEL_LITERS,
        "idle_minutes": idle_minutes,
        "idling_too_long": idling_too_long,
        "idle_limit_minutes": IDLE_LIMIT_MINUTES
    }

# =========================
# CAR STATUS CHECK
# =========================
@app.get("/car-status")
def car_status():
    """Get current status of all vehicles with ignition state"""
    data = get_fleet_data()

    if not data:
        return {"status": "error", "message": "No data from Cartrack"}

    vehicles = extract_vehicles(data)
    statuses = []

    for v in vehicles:
        name = get_vehicle_display_name(v)
        ignition = get_ignition(v)
        speed = get_vehicle_speed(v)
        fuel = get_vehicle_fuel(v)
        fuel_percent = get_vehicle_fuel_percent(v)
        location = get_vehicle_location(v)
        event_time = get_vehicle_time(v)
        speeding = speed >= SPEED_LIMIT_KMH
        moving = speed > 0
        idle_minutes = get_vehicle_idle_minutes(v)
        idling_too_long = (
            ignition
            and not moving
            and idle_minutes is not None
            and idle_minutes >= IDLE_LIMIT_MINUTES
        )

        statuses.append({
            "name": name,
            "model": get_vehicle_model(v),
            "ignition": ignition,
            "ignition_status": "RUNNING" if ignition else "STOPPED",
            "speed": speed,
            "speeding": speeding,
            "fuel": fuel,
            "fuel_liters": fuel,
            "fuel_percent": fuel_percent,
            "low_fuel": is_low_fuel(fuel),
            "low_fuel_liters": LOW_FUEL_LITERS,
            "location": location,
            "time": event_time,
            "idle_minutes": idle_minutes,
            "idling_too_long": idling_too_long,
        })

    return {
        "status": "ok",
        "vehicles_count": len(vehicles),
        "vehicles": statuses
    }

# =========================
@app.post("/tracker")
async def tracker(data: dict):

    name = get_vehicle_display_name(data)
    ignition = get_ignition(data)
    speed = get_vehicle_speed(data)
    fuel = get_vehicle_fuel(data)
    fuel_percent = get_vehicle_fuel_percent(data)
    location = get_vehicle_location(data)
    event_time = get_vehicle_time(data)
    speeding = speed >= SPEED_LIMIT_KMH
    moving = speed > 0
    idle_minutes = get_vehicle_idle_minutes(data)
    idling_too_long = (
        ignition
        and not moving
        and idle_minutes is not None
        and idle_minutes >= IDLE_LIMIT_MINUTES
    )

    alerts = []

    if ignition and speeding:
        alerts.append(format_speeding_alert(name, speed, location, event_time))
    elif idling_too_long:
        alerts.append(format_idling_too_long_alert(name, idle_minutes, fuel, location, event_time))
    elif is_low_fuel(fuel):
        alerts.append(format_fuel_alert(name, fuel, location, event_time))
    elif ignition:
        alerts.append(format_ignition_alert(name, True, location, event_time))
    else:
        alerts.append(format_ignition_alert(name, False, location, event_time))

    send_vehicle_alerts(alerts)

    return {
        "status": "ok",
        "name": name,
        "location": location,
        "time": event_time,
        "speed": speed,
        "speeding": speeding,
        "speed_limit": SPEED_LIMIT_KMH,
        "fuel": fuel,
        "fuel_liters": fuel,
        "fuel_percent": fuel_percent,
        "low_fuel": is_low_fuel(fuel),
        "low_fuel_liters": LOW_FUEL_LITERS,
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

        name = get_vehicle_display_name(v)
        vid = get_vehicle_id(v) or get_vehicle_name(v)

        ignition = get_ignition(v)
        speed = get_vehicle_speed(v)
        fuel = get_vehicle_fuel(v)
        fuel_percent = get_vehicle_fuel_percent(v)
        location = get_vehicle_location(v)
        event_time = get_vehicle_time(v)
        speeding = speed >= SPEED_LIMIT_KMH
        low_fuel = is_low_fuel(fuel)

        prev = last_state.get(vid)
        moving = speed > 0
        idle_started_at, idle_minutes, idling_too_long, idle_alert_count, previous_idle_alert_count = get_idle_status(
            ignition,
            moving,
            prev or {},
            get_vehicle_idle_minutes(v)
        )

        if prev is not None:
            alerts = []

            # IGNITION CHANGE ONLY
            if ignition != prev.get("ignition"):
                alerts.append(format_ignition_alert(name, ignition, location, event_time))

            # SPEEDING ALERT (ONLY WHEN RUNNING AND CROSSING SPEED LIMIT)
            if not alerts and ignition and speeding and not prev.get("speeding", False):
                alerts.append(format_speeding_alert(name, speed, location, event_time))

            # FUEL ALERT (ONLY WHEN CROSSING BELOW LOW FUEL WARNING)
            if not alerts and low_fuel and not prev.get("low_fuel", False):
                alerts.append(format_fuel_alert(name, fuel, location, event_time))

            # IDLING TOO LONG ALERT (EVERY NEW 10-MINUTE BUCKET)
            if not alerts and idling_too_long and idle_alert_count > previous_idle_alert_count:
                alerts.append(format_idling_too_long_alert(name, idle_minutes, fuel, location, event_time))

            # MOTION STARTED ALERT (ONLY AFTER A LONG IDLE SESSION)
            if (
                not alerts
                and ignition
                and moving
                and not prev.get("moving", False)
                and prev.get("idling_too_long", False)
            ):
                alerts.append(format_motion_alert(name, location, event_time))

            # LOCATION UPDATE ALERT
            if not alerts and location != prev.get("location"):
                alerts.append(format_location_update_alert(name, speed, fuel, location, event_time))

            send_vehicle_alerts(alerts)

        vehicle_statuses.append({
            "id": vid,
            "name": name,
            "model": get_vehicle_model(v),
            "location": location,
            "time": event_time,
            "speed": speed,
            "speeding": speeding,
            "speed_limit": SPEED_LIMIT_KMH,
            "fuel": fuel,
            "fuel_liters": fuel,
            "fuel_percent": fuel_percent,
            "low_fuel": low_fuel,
            "low_fuel_liters": LOW_FUEL_LITERS,
            "idle_minutes": idle_minutes,
            "idling_too_long": idling_too_long,
            "idle_limit_minutes": IDLE_LIMIT_MINUTES,
            "idle_alert_count": idle_alert_count
        })

        # SAVE STATE
        last_state[vid] = {
            "ignition": ignition,
            "moving": moving,
            "fuel": fuel,
            "fuel_percent": fuel_percent,
            "low_fuel": low_fuel,
            "speed": speed,
            "speeding": speeding,
            "location": location,
            "time": event_time,
            "idle_started_at": idle_started_at,
            "idle_minutes": idle_minutes,
            "idling_too_long": idling_too_long,
            "idling_too_long_alert_count": idle_alert_count
        }

        # PRINT STATUS TO CONSOLE
        status_icon = "🚗" if ignition else "🅿️"
        if ignition:
            if moving:
                print(f"{status_icon} {name}: RUNNING at {speed:.1f} km/h")
            else:
                idle_text = f", idling for {idle_minutes:.0f} min" if idle_minutes else ""
                print(f"{status_icon} {name}: STOPPED (ignition on){idle_text}")
        else:
            print(f"{status_icon} {name}: STOPPED (ignition off)")

    return {
        "status": "ok",
        "vehicles": len(vehicles),
        "data": vehicle_statuses
    }


async def _auto_sync_fleet_loop():
    await asyncio.sleep(5)
    while True:
        try:
            print(f"🔁 Auto-syncing fleet every {SYNC_INTERVAL_SECONDS} seconds...")
            await asyncio.to_thread(sync_fleet)
        except Exception as e:
            print(f"❌ Auto sync error: {e}")
        await asyncio.sleep(SYNC_INTERVAL_SECONDS)


@app.on_event("startup")
async def start_auto_sync():
    global auto_sync_task

    if auto_sync_task and not auto_sync_task.done():
        print("Auto-sync loop already running")
        return

    print(f"🚀 Starting auto-sync loop with interval {SYNC_INTERVAL_SECONDS}s")
    auto_sync_task = asyncio.create_task(_auto_sync_fleet_loop())
