import os
import sys

import requests
from requests.auth import HTTPBasicAuth

from main import format_speeding_alert

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

CARTRACK_USERNAME = os.getenv("CARTRACK_USERNAME")
CARTRACK_PASSWORD = os.getenv("CARTRACK_PASSWORD")
CARTRACK_API_URL = os.getenv("CARTRACK_API_URL", "https://fleetapi-ph.cartrack.com/rest/vehicles/status")

SAMPLE_SPEEDING_CAR = {
    "name": "ABC123",
    "speed": 95,
    "location": "14.5995, 120.9842",
    "time": "2026-05-10 15:30:00",
}

sample_speeding_alert = format_speeding_alert(
    SAMPLE_SPEEDING_CAR["name"],
    SAMPLE_SPEEDING_CAR["speed"],
    SAMPLE_SPEEDING_CAR["location"],
    SAMPLE_SPEEDING_CAR["time"]
)

print("SAMPLE SPEEDING TELEGRAM ALERT:")
print(sample_speeding_alert)
print()

if not CARTRACK_USERNAME or not CARTRACK_PASSWORD:
    raise SystemExit("CARTRACK_USERNAME and CARTRACK_PASSWORD must be set in .env")

try:
    res = requests.get(
        CARTRACK_API_URL,
        auth=HTTPBasicAuth(CARTRACK_USERNAME, CARTRACK_PASSWORD),
        timeout=10
    )
    res.raise_for_status()

    print("SUCCESS: Cartrack API request succeeded")
    print("STATUS CODE:", res.status_code)
    print("RESPONSE:")
    print(res.text)

except requests.exceptions.HTTPError as e:
    print("HTTP ERROR:", e)
    print("STATUS CODE:", res.status_code)
    print("RESPONSE:")
    print(res.text)
except requests.exceptions.RequestException as e:
    print("REQUEST ERROR:", e)
except Exception as e:
    print("ERROR:", e)
