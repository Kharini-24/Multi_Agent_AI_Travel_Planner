from typing import Optional

# City or region -> main airport code (IATA)
AIRPORT_CODES = {
    # India
    "chennai": "MAA",
    "goa": "GOI",
    "kerala": "COK",
    "kochi": "COK",
    "cochin": "COK",
    "thiruvananthapuram": "TRV",
    "trivandrum": "TRV",
    "delhi": "DEL",
    "mumbai": "BOM",
    "bangalore": "BLR",
    "bengaluru": "BLR",
    "hyderabad": "HYD",
    "kolkata": "CCU",
    "pune": "PNQ",
    "jaipur": "JAI",
    "coimbatore": "CJB",
    "madurai": "IXM",
    # International
    "dubai": "DXB",
    "singapore": "SIN",
    "bangkok": "BKK",
    "kuala lumpur": "KUL",
    "colombo": "CMB",
    "maldives": "MLE",
    "bali": "DPS",
    "tokyo": "HND",
    "paris": "CDG",
    "rome": "FCO",
    "london": "LHR",
    "sydney": "SYD",
    "melbourne": "MEL",
}


def get_airport_code(place: Optional[str]) -> Optional[str]:
    if not place:
        return None
    return AIRPORT_CODES.get(place.strip().lower())