import requests
from requests.auth import HTTPBasicAuth

CARTRACK_USERNAME = "HEXA00001"
CARTRACK_PASSWORD = "9af99274d0f0b424205b82eadb97b8b2c66dc5edc1f4ddb3c964bee8ecd1c69e"

CARTRACK_API_URL = "https://fleetapi-ph.cartrack.com/rest/vehicles"

try:
    res = requests.get(
        CARTRACK_API_URL,
        auth=HTTPBasicAuth(CARTRACK_USERNAME, CARTRACK_PASSWORD),
        timeout=10
    )

    print("STATUS CODE:", res.status_code)
    print("RESPONSE:")
    print(res.text)

except Exception as e:
    print("ERROR:", e)