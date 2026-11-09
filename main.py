# LangGraph Multi-Agent Travel Planner with Long-Term Memory
#
# Setup:
#   1. pip install -r requirements.txt
#   2. Create a PostgreSQL database named langgraph_memory
#   3. Copy .env.example to .env and fill in your keys
# LangGraph Multi-Agent Travel Booking System with Long-Term Memory

# main.py

import os
from typing import TypedDict, Annotated
import operator
from typing import Optional
from pydantic import BaseModel, Field
from datetime import date
from validators import validate_web_results
from budget import check_budget
from memory import load_profile, save_profile

import psycopg
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import (
    AnyMessage,
    HumanMessage,
    AIMessage,
    SystemMessage,
)

from langchain_groq import ChatGroq

from tools.tavily_tool import search_hotels, search_flight_fares
from tools.flight_tool import search_flights
from report import flights_section, fares_section, hotels_section, budget_section
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    max_tokens=4000,
)

# What we want to extract from the user's sentence
class TripRequest(BaseModel):
    origin: Optional[str] = Field(
        default=None, description="City the user travels from, if mentioned"
    )
    destination: Optional[str] = Field(
        default=None, description="Main destination, spelled correctly"
    )
    days: Optional[int] = Field(
        default=None, description="Number of days of the trip"
    )
    travelers: Optional[int] = Field(
        default=1, description="Number of people travelling"
    )
    currency: Optional[str] = Field(
        default="INR", description="Currency of the budget"
    )
    budget: Optional[float] = Field(
        default=None, description="Total budget as a number, no symbols"
    )
    
    start_date: Optional[str] = Field(
        default=None, description="Travel start date in YYYY-MM-DD, if mentioned"
    )
    preferences: Optional[list[str]] = Field(
        default_factory=list,
        description="Things the user likes, e.g. beaches, food, budget hotels",
    )

class TravelState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    user_query: str
    user_id: str
    trip_request: dict
    flight_results: dict
    fare_results: dict
    hotel_results: dict
    itinerary: str
    llm_calls: int
    budget_report: dict
    
def parse_request(user_text: str) -> TripRequest:
    parser_llm = llm.with_structured_output(
        TripRequest, method="function_calling"
    )

    system_prompt = f"""You extract trip details from a user's message.
Today's date is {date.today()}.

Rules:
- Fix spelling mistakes in place names (for example kerla -> Kerala).
- Only fill a field if the user actually said it. Otherwise leave it empty.
- Never guess the origin, budget or dates.
- Convert budgets like 30k or 2 lakhs into plain numbers (30000, 200000).
"""

    result = parser_llm.invoke([
    SystemMessage(content=system_prompt),
    HumanMessage(content=user_text),
    ])

    # The LLM may return null for fields the user did not mention.
    # We fill in safe defaults here, in Python.
    if result.travelers is None:
        result.travelers = 1
    if not result.currency:
        result.currency = "INR"
    if result.preferences is None:
        result.preferences = []

    return result
     
def parse_request_node(state: TravelState):
    trip = parse_request(state["user_query"])
    return {
        "trip_request": trip.model_dump(),
        "messages": [AIMessage(content="Trip request parsed")],
        "llm_calls": state.get("llm_calls", 0) + 1
    } 
def load_memory_node(state: TravelState):
    trip = dict(state["trip_request"])
    profile = load_profile(state["user_id"])
    used = []

    if not trip.get("origin") and profile.get("home_city"):
        trip["origin"] = profile["home_city"]
        used.append("origin (home city)")

    if not trip.get("preferences") and profile.get("preferences"):
        trip["preferences"] = profile["preferences"]
        used.append("preferences")

    trip["memory_used"] = used
    return {"trip_request": trip} 
# State
# Node: stops the graph and asks the user for the missing detail
def ask_user_node(state: TravelState):
    return {
        "messages": [
            AIMessage(
                content="I need a destination to plan your trip. "
                        "Please try again, for example: '3 day trip to Goa from Chennai'."
            )
        ]
    }


# Router: decides where to go next (not a node, just a decision function)
def route_after_parse(state: TravelState):
    if not state["trip_request"].get("destination"):
        return "ask_user"
    return ["flight_agent", "hotel_agent"]

# Flight Agent
def flight_agent(state: TravelState):
    trip = state["trip_request"]
    origin = trip.get("origin")
    destination = trip.get("destination")

    return {
        "flight_results": search_flights(origin, destination),
        "fare_results": search_flight_fares(origin, destination),
    }


# Hotel Agent
def hotel_agent(state: TravelState):
    trip = state["trip_request"]

    return {
        "hotel_results": search_hotels(
            trip.get("destination"), trip.get("preferences")
        ),
    }
# Validation node (plain Python, no LLM)
def validate_results(state: TravelState):
    trip = state["trip_request"]
    origin = trip.get("origin")
    destination = trip.get("destination")

    checked_fares = validate_web_results(
        state["fare_results"], [origin, destination], match_all=True
    )
    checked_hotels = validate_web_results(
        state["hotel_results"], [destination]
    )

    return {
        "fare_results": checked_fares,
        "hotel_results": checked_hotels,
    }
# Node: one broader hotel search if the first one found nothing relevant
def hotel_retry_node(state: TravelState):
    destination = state["trip_request"].get("destination")

    retry = search_hotels(destination, broad=True)
    checked = validate_web_results(retry, [destination])

    return {"hotel_results": checked}


# Router: decide whether a retry is needed
def route_after_validation(state: TravelState):
    if state["hotel_results"].get("status") == "no_data":
        return "hotel_retry"
    return "budget_check"

# Budget node (plain Python, no LLM)
def budget_check_node(state: TravelState):
    report = check_budget(
        state["trip_request"], state["fare_results"], state["hotel_results"]
    )
    return {"budget_report": report}   
# Itinerary Agent
# --- Helpers: turn our data into short, labelled text for the prompt ---
def format_flights(result: dict) -> str:
    if result.get("status") != "ok":
        return f"NOT AVAILABLE ({result.get('message', 'no data')})"
    return "\n".join(
        f"- {f['airline']} {f['flight_number']}" for f in result["flights"]
    )


def format_web_results(result: dict) -> str:
    if result.get("status") != "ok":
        return f"NOT AVAILABLE ({result.get('message', 'no data')})"
    return "\n".join(
        f"- {r['title']} ({r['url']}): {r['snippet']}" for r in result["results"]
    )


# Itinerary Agent
def itinerary_agent(state: TravelState):
    trip = state["trip_request"]
    days = trip.get("days") or 3
    days_note = "" if trip.get("days") else " (the user did not say; 3 days is an assumption)"

    system_prompt = """You are a careful travel planner who writes day-wise itineraries.

STRICT RULES:
- Never invent prices, hotel names, flight times or availability.
- Use a hotel name or price ONLY if it appears in the DATA below. Otherwise recommend an area to stay in, not a named hotel.
- Do not state any ticket, activity or meal price unless it appears in the DATA.
- Use time blocks (Morning, Afternoon, Evening), not exact clock times.
- Plan only the number of days requested.
- Keep days realistic: the first and last day are lighter because of travel. Plan 2 to 3 main activities per day, grouped by area so there is little travel between them.
- Put each suggestion under a heading and label general ideas as "Suggestion".
- If the budget report says the trip is over budget or cannot be checked, suggest cheaper choices and mention it, without inventing numbers.
- Do not say a place is well-reviewed, popular or highly rated unless the DATA says so.
- Do not state when a flight departs or arrives.
- Only suggest places within about one hour of where the traveller is staying. Never suggest a long day trip (for example Dudhsagar Falls) on a short trip or on the departure day.
- Flight numbers in the DATA are for the outbound trip only. For the return, say "book a return flight" and do not name a flight number.
- Describe a hotel only with facts found in the DATA. Do not add claims such as "clean" or "convenient".
- Do not repeat the budget table. Write the plan only."""

    user_prompt = f"""TRIP REQUEST: {trip}
NUMBER OF DAYS: {days}{days_note}

DATA 1, live flight data (AviationStack, no prices):
{format_flights(state['flight_results'])}

DATA 2, web search results about hotels:
{format_web_results(state['hotel_results'])}

DATA 3, budget report:
{state.get('budget_report', {}).get('message', 'No budget information.')}

Write the itinerary now. Write a separate section for EVERY day from Day 1 to Day {days}. Each day must have Morning, Afternoon and Evening parts."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    return {
        "itinerary": response.content,
        "llm_calls": state.get("llm_calls", 0) + 1,
    }


# Final Response Agent
# Final Response Agent
def final_agent(state: TravelState):
    trip = state["trip_request"]
    budget = state.get("budget_report") or {}

    system_prompt = """You write a short, friendly summary of a trip plan.

STRICT RULES:
- Write 2 to 3 sentences only.
- Use only the information given to you.
- Do not mention any price, hotel name, flight number or time.
- Do not promise availability or bookings.
- Do not say anything about whether the trip fits the budget. The budget is shown in a separate section.
- Do not use words like "comfortably", "perfect" or "guaranteed"."""

    user_prompt = f"""Trip request: {trip}
Budget check result: {budget.get('message', 'No budget information.')}

Write the summary now."""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt),
    ])

    destination = trip.get("destination") or "your trip"

    parts = [
        f"## Your trip plan: {destination}",
        response.content.strip(),
        "---",
        flights_section(state["flight_results"]),
        fares_section(state["fare_results"]),
        hotels_section(state["hotel_results"]),
        budget_section(budget),
        "---",
        "### 🗓️ Day-wise itinerary",
        "*Source: AI-generated suggestions. Check every place and price before you book.*",
        state["itinerary"],
        "---",
        "*Nothing here is a booking or a confirmed price.*",
    ]

    return {
        "messages": [AIMessage(content="\n\n".join(parts))],
        "llm_calls": state.get("llm_calls", 0) + 1,
    }
def save_memory_node(state: TravelState):
    trip = state["trip_request"]
    used = trip.get("memory_used", [])
    profile = load_profile(state["user_id"])

    home_city = None
    if trip.get("origin") and "origin (home city)" not in used and not profile.get("home_city"):
        home_city = trip["origin"]

    preferences = None
    if trip.get("preferences") and "preferences" not in used:
        preferences = trip["preferences"]

    if home_city or preferences:
        save_profile(state["user_id"], home_city=home_city, preferences=preferences)

    return {}

graph = StateGraph(TravelState)

graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)
graph.add_node("parse_request", parse_request_node)
graph.add_node("validate_results", validate_results)
graph.add_node("hotel_retry", hotel_retry_node)
graph.add_node("budget_check", budget_check_node)
graph.add_node("load_memory", load_memory_node)

graph.add_edge(START, "parse_request")
graph.add_node("ask_user", ask_user_node)

graph.add_conditional_edges(
    
    "load_memory",
    route_after_parse,
    {
        "ask_user": "ask_user",
        "flight_agent": "flight_agent",
        "hotel_agent": "hotel_agent",
    },
)


graph.add_edge("ask_user", END)
graph.add_edge(["flight_agent", "hotel_agent"], "validate_results")
graph.add_conditional_edges(
    "validate_results",
    route_after_validation,
    {
        "hotel_retry": "hotel_retry",
        "budget_check": "budget_check",
    },
)

graph.add_edge("hotel_retry", "budget_check")
graph.add_edge("budget_check", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("parse_request", "load_memory")
graph.add_node("save_memory", save_memory_node)
graph.add_edge("final_agent", "save_memory")
graph.add_edge("save_memory", END)


# PostgreSQL connection
_conn = psycopg.connect(
    DATABASE_URL,
    autocommit=True
)

checkpointer = PostgresSaver(_conn)

# Setup database tables and indexes
checkpointer.setup()

# Compile graph with persistent memory
app = graph.compile(checkpointer=checkpointer)


if __name__ == "__main__":
    config = {
        "configurable": {
            "thread_id": "user_aarohi"
        }
    }

    user_input = input("Enter travel request: ")

    result = app.invoke(
        {
            "messages": [
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "user_id": "aarohi_user",
            "trip_request": {},
            "flight_results": {},
            "fare_results": {},
            "hotel_results": {},
            "budget_report": {},
            "itinerary": "",
            "llm_calls": 0
        },
        config=config
    )
    print("\nPARSED REQUEST:", result["trip_request"])

    print("\nFINAL RESPONSE:\n")
    print(result["messages"][-1].content)

    print("\n" + "=" * 40)
    print("PARSED REQUEST:", result["trip_request"])
    for name in ["flight_results", "fare_results", "hotel_results"]:
        info = result.get(name) or {}
        print(name.upper() + ":", info.get("status", "not run"), "-", info.get("message", ""))
    budget = result.get("budget_report") or {}
    print("BUDGET:", budget.get("status", "not run"), "-", budget.get("message", ""))
    print("\nITINERARY:\n", result["itinerary"])
    with open("last_itinerary.txt", "w", encoding="utf-8") as f:
      f.write(result["itinerary"])
    with open("last_final.txt", "w", encoding="utf-8") as f:
      f.write(result["messages"][-1].content)