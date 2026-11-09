import math
import re

# Assumptions (rough estimates, change them if you like)
FOOD_PER_PERSON_PER_DAY = 600
LOCAL_TRANSPORT_PER_DAY = 400

PRICE_PATTERN = re.compile(r"(?:₹|Rs\.?|INR)\s?(\d[\d,]*)")


def find_prices(results):
    prices = []
    for item in results:
        text = f"{item.get('title', '')} {item.get('snippet', '')}"
        for match in PRICE_PATTERN.finditer(text):
            after = text[match.end():match.end() + 5].lower()
            if "off" in after:
                continue
            amount = int(match.group(1).replace(",", ""))
            if amount >= 100:
                prices.append(amount)
    return prices


def lowest_price(web_result):
    if web_result.get("status") != "ok":
        return None
    prices = find_prices(web_result.get("results", []))
    return min(prices) if prices else None


def check_budget(trip, fare_results, hotel_results):
    days = trip.get("days")
    travelers = trip.get("travelers") or 1
    budget = trip.get("budget")
    origin = trip.get("origin")

    report = {"status": "cannot_check", "budget": budget, "total": None,
              "lines": [], "message": ""}

    if not days:
        report["message"] = "Trip length is unknown, so cost cannot be estimated."
        return report
    if trip.get("currency", "INR") != "INR":
        report["message"] = "Budget checking only supports INR for now."
        return report

    nights = max(days - 1, 0)
    rooms = math.ceil(travelers / 2)
    lines = []
    missing = []

    if origin:
        fare = lowest_price(fare_results)
        if fare:
            lines.append({"item": "Flights (round trip)", "amount": fare * 2 * travelers,
                          "type": "web_search",
                          "note": f"lowest advertised fare Rs {fare}, doubled for return, x {travelers}"})
        else:
            missing.append("flight fares")

    if nights > 0:
        rate = lowest_price(hotel_results)
        if rate:
            lines.append({"item": "Hotel", "amount": rate * nights * rooms,
                          "type": "web_search",
                          "note": f"lowest advertised Rs {rate}/night x {nights} night(s) x {rooms} room(s)"})
        else:
            missing.append("hotel prices")

    lines.append({"item": "Food", "amount": FOOD_PER_PERSON_PER_DAY * days * travelers,
                  "type": "assumption",
                  "note": f"Rs {FOOD_PER_PERSON_PER_DAY}/person/day"})
    lines.append({"item": "Local transport", "amount": LOCAL_TRANSPORT_PER_DAY * days,
                  "type": "assumption",
                  "note": f"Rs {LOCAL_TRANSPORT_PER_DAY}/day"})

    report["lines"] = lines

    if missing:
        report["message"] = ("Could not find " + " and ".join(missing)
                             + " in the search results, so the total cannot be checked.")
        return report

    total = sum(line["amount"] for line in lines)
    report["total"] = total

    if not budget:
        report["status"] = "no_budget"
        report["message"] = f"Estimated minimum cost is about Rs {total}. No budget was given."
    elif total > budget:
        report["status"] = "over_budget"
        report["message"] = (f"Even with the cheapest advertised options, the estimate "
                             f"(Rs {total}) is above your budget (Rs {int(budget)}).")
    else:
        report["status"] = "within_budget"
        report["message"] = (f"The cheapest estimate (Rs {total}) fits your budget "
                             f"(Rs {int(budget)}). Real prices may be higher.")
    return report