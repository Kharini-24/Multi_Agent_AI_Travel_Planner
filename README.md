# Multi-Agent AI Travel Planner with Memory

A LangGraph multi-agent app that turns a trip request like
*"2 day trip to Goa for 2 people from Chennai under 30k"* into a labelled travel plan.
The main idea: **code handles the facts, the LLM only handles the language.**
## 📸 Screenshots

<table>
  <tr>
    <td align="center">
      <strong>Screenshot 1</strong><br/>
      <img src="https://github.com/user-attachments/assets/f0b688fe-33f0-4368-ad09-9c8d933e3f8b" width="400" />
    </td>
    <td align="center">
      <strong>Screenshot 2</strong><br/>
      <img src="https://github.com/user-attachments/assets/19cab588-3ead-441e-ba5d-e8f750afea7b" width="400" />
    </td>
  </tr>
  <tr>
    <td align="center">
      <strong>Screenshot 3</strong><br/>
      <img src="https://github.com/user-attachments/assets/690c9211-4042-4e90-a179-5d9c932bd2fa" width="400" />
    </td>
    <td align="center">
      <strong>Screenshot 4</strong><br/>
      <img src="https://github.com/user-attachments/assets/4ecbe3a3-8c81-45cd-9ebe-228d482ccbd3" width="400" />
    </td>
  </tr>
</table>

## Features
- **Request parsing:** the LLM turns free text into a typed form (origin, destination, days, budget, ...) using structured output.
- **Parallel search:** flight and hotel agents run at the same time (fan-out / fan-in).
- **Result validation:** irrelevant web results are removed, and a weak hotel search is retried once.
- **Budget check:** the arithmetic is done in Python, not by the LLM.
- **Grounded output:** the itinerary and final answer may not invent hotel names, prices or flight times.
- **Source labels:** every section says whether it is live API data, web search, an estimate or an AI suggestion.
- **Long-term memory:** remembers home city and preferences across trips (PostgreSQL Store).
- **Streamlit UI:** shows each agent's result live.

## Architecture
```
START -> parse_request -> load_memory -> router --(no destination)--> ask_user -> END
                                            |
                                            +--> flight_agent --+
                                            +--> hotel_agent ---+--> validate_results
                                                                      |-- weak hotels --> hotel_retry
                                                                      v
                                            budget_check -> itinerary_agent -> final_agent -> save_memory -> END
```
- 4 agents: Flight, Hotel, Itinerary, Final. Parser, validator and budget checker are plain nodes.
- 3 LLM calls per run (parse, itinerary, final).
- Checkpointer (`PostgresSaver`) saves each run. Store (`PostgresStore`) saves facts about the user.

## Tech stack
Python, LangChain, LangGraph, Groq (`gpt-oss-120b`), Tavily Search API, AviationStack API, PostgreSQL, Streamlit.

## Setup
1. Create a PostgreSQL database named `langgraph_memory`.
2. Install dependencies:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and add your keys (Groq, Tavily, AviationStack, DATABASE_URL).
4. Run:
   ```
   streamlit run frontend.py
   ```
   or, for the command line: `python main.py`

## Known limitations
- The free AviationStack plan gives recent live flights only. It has **no prices, no availability and no future timetable**.
- Fare and hotel prices come from web search snippets ("from" prices), so they are rough and not a quote.
- The budget is a **minimum estimate** built from the cheapest advertised prices plus fixed assumptions for food and transport.
- The airport lookup has a small built-in list of cities.
- Nothing in the app books anything.
