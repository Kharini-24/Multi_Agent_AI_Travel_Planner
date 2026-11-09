import os
from typing import Optional

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

SOURCE = "Tavily (web search results, not live prices or availability)"

# Social media pages are rarely useful for hotel or fare information
BLOCKED_DOMAINS = [
    "instagram.com",
    "facebook.com",
    "pinterest.com",
    "tiktok.com",
    "youtube.com",
]


def _result(status, message, results=None):
    return {
        "source": SOURCE,
        "status": status,
        "message": message,
        "results": results or [],
    }


def _web_search(query):
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return _result("unavailable", "TAVILY_API_KEY is missing in .env")

    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(
            query=query,
            max_results=5,
            exclude_domains=BLOCKED_DOMAINS,
        )
    except Exception:
        return _result("error", "Tavily web search failed.")

    results = []
    for item in response.get("results") or []:
        snippet = (item.get("content") or "").strip()
        if len(snippet) > 300:
            snippet = snippet[:300].rsplit(" ", 1)[0] + "..."

        results.append({
            "title": item.get("title") or "Untitled",
            "url": item.get("url") or "",
            "snippet": snippet,
        })

    if not results:
        return _result("no_data", "The web search found no results.")

    return _result("ok", f"Found {len(results)} web result(s).", results)


def search_hotels(
    destination: Optional[str],
    preferences: Optional[list] = None,
    broad: bool = False,
):
    if not destination:
        return _result("unavailable", "No destination, so hotels were not searched.")

    if broad:
        query = f"hotels in {destination}"
    else:
        query = f"best hotels in {destination} with price per night"
        if preferences:
            query += " " + " ".join(preferences)

    return _web_search(query)


def search_flight_fares(origin: Optional[str], destination: Optional[str]):
    if not origin or not destination:
        return _result(
            "unavailable",
            "Origin or destination missing, so flight fares were not searched.",
        )

    query = f"typical economy flight fare {origin} to {destination} price"
    return _web_search(query)