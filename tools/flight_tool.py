import os
import requests
from dotenv import load_dotenv

from tools.airports import get_airport_code

load_dotenv()

API_KEY = os.getenv("AVIATIONSTACK_API_KEY")
API_URL = "http://api.aviationstack.com/v1/flights"
SOURCE = "AviationStack (live API data, no prices)"


def _result(status, message, flights=None):
    return {
        "source": SOURCE,
        "status": status,
        "message": message,
        "flights": flights or [],
    }


def search_flights(origin, destination):
    dep_code = get_airport_code(origin)
    arr_code = get_airport_code(destination)

    if not API_KEY:
        return _result("unavailable", "AVIATIONSTACK_API_KEY is missing in .env")

    if not dep_code or not arr_code:
        return _result(
            "unavailable",
            f"No airport code known for origin '{origin}' or destination "
            f"'{destination}', so live flight data was not searched.",
        )

    try:
        response = requests.get(
            API_URL,
            params={
                "access_key": API_KEY,
                "dep_iata": dep_code,
                "arr_iata": arr_code,
                "limit": 25,
            },
            timeout=15,
        )
        data = response.json()
    except requests.RequestException:
        return _result("error", "Could not reach AviationStack.")
    except ValueError:
        return _result("error", "AviationStack returned an unreadable response.")

    if isinstance(data, dict) and data.get("error"):
        message = data["error"].get("message", "Unknown API error")
        return _result("error", f"AviationStack error: {message}")

    if not response.ok:
        return _result("error", f"AviationStack returned HTTP {response.status_code}.")

    flights = []
    seen = set()

    for item in data.get("data") or []:
        flight_info = item.get("flight") or {}

        if flight_info.get("codeshared"):
            continue

        airline = (item.get("airline") or {}).get("name") or "Unknown airline"
        number = flight_info.get("iata") or "Unknown"

        key = (airline, number)
        if key in seen:
            continue
        seen.add(key)

        flights.append({
            "airline": airline,
            "flight_number": number,
            "flight_status": item.get("flight_status") or "unknown",
        })

        if len(flights) == 5:
            break

    if not flights:
        return _result(
            "no_data",
            f"No recent live flights found for {dep_code} to {arr_code}.",
        )

    return _result(
        "ok",
        f"Found {len(flights)} flight(s) on {dep_code} to {arr_code} in recent "
        f"live data. This is not a timetable, and has no fares or availability.",
        flights,
    )