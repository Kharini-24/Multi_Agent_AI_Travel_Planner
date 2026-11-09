import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv
from langgraph.store.postgres import PostgresStore

load_dotenv()

_conn = psycopg.connect(
    os.getenv("DATABASE_URL"), autocommit=True, row_factory=dict_row
)
_store = PostgresStore(_conn)
_store.setup()


def load_profile(user_id):
    item = _store.get(("user_prefs", user_id), "profile")
    if item is None:
        return {}
    return item.value


def save_profile(user_id, home_city=None, preferences=None):
    profile = load_profile(user_id)

    if home_city:
        profile["home_city"] = home_city

    if preferences:
        saved = profile.get("preferences", [])
        saved_lower = [p.lower() for p in saved]
        for pref in preferences:
            if pref.lower() not in saved_lower:
                saved.append(pref)
        profile["preferences"] = saved

    _store.put(("user_prefs", user_id), "profile", profile)
    return profile