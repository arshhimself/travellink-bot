# import os
# import json
# import requests
# from datetime import datetime, timedelta
# from typing import TypedDict, Annotated, Sequence, Optional
# import operator
# from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.memory import MemorySaver
# from langgraph.prebuilt import ToolNode, tools_condition
# from langchain_openai import ChatOpenAI
# from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
# from langchain_core.tools import tool
# from dotenv import load_dotenv
# import dateparser
# import re
# from thefuzz import fuzz

# load_dotenv()

# os.environ["LANGCHAIN_TRACING_V2"] = "false"

# AUTHID = os.getenv("AUTHID")
# AUTHPASSSWORD = os.getenv("AUTHPASSSWORD")
# BASE_URL = "https://api.aerocrs.com/v5"

# llm = ChatOpenAI(
#     model="gpt-4o-mini",
#     temperature=0,
#     max_tokens=500
# )


# # ─────────────────────────────────────────────
# # STATE
# # ─────────────────────────────────────────────

# class FlightState(TypedDict):
#     messages: Annotated[
#         Sequence[HumanMessage | AIMessage | SystemMessage],
#         operator.add
#     ]
#     # Flight details
#     from_city: str
#     to_city: str
#     start_date: str
#     end_date: str
#     from_code: str
#     to_code: str
#     flights: bool
#     round_trip: bool
#     return_date: str
#     adults: int
#     child: int
#     infant: int
#     # Passenger details (for confirmation)
#     pax_firstname: Optional[str]
#     pax_lastname: Optional[str]
#     pax_birthdate: Optional[str]   # YYYY/MM/DD
#     pax_phone: Optional[str]
#     pax_email: Optional[str]
#     booking_confirmed: bool


# # ─────────────────────────────────────────────
# # HELPERS
# # ─────────────────────────────────────────────

# def normalize_date(date_text):
#     if not date_text:
#         return None
#     today = datetime.today()
#     parsed = dateparser.parse(
#         date_text,
#         settings={'PREFER_DATES_FROM': 'future', 'RELATIVE_BASE': today}
#     )
#     if not parsed:
#         return None
#     if parsed.date() < today.date():
#         try:
#             parsed = parsed.replace(year=parsed.year + 1)
#         except ValueError:
#             return "PAST_DATE"
#     if parsed.date() < today.date():
#         return "PAST_DATE"
#     return parsed.strftime("%Y/%m/%d")


# def normalize_birthdate(date_text):
#     """Parse birthdate — allows past dates."""
#     if not date_text:
#         return None
#     parsed = dateparser.parse(
#         date_text,
#         settings={'PREFER_DATES_FROM': 'past', 'RETURN_AS_TIMEZONE_AWARE': False}
#     )
#     if not parsed:
#         return None
#     return parsed.strftime("%Y/%m/%d")


# def clean_text(text):
#     text = text.lower()
#     text = re.sub(r"[^a-z0-9 ]", " ", text)
#     text = re.sub(r"\s+", " ", text).strip()
#     return text


# def match_airport_code(city_name, destinations):
#     city_clean = clean_text(city_name)
#     best_match = None
#     best_score = 0
#     for dest in destinations:
#         name_clean = clean_text(dest["name"])
#         code = dest["code"].lower()
#         iata = dest.get("iatacode", "").lower()
#         if city_clean in name_clean or city_clean == code or city_clean == iata:
#             return dest["code"]
#         city_words = city_clean.split()
#         if all(word in name_clean for word in city_words):
#             return dest["code"]
#         first_word = name_clean.split()[0] if name_clean.split() else ""
#         score = max(
#             fuzz.partial_ratio(city_clean, name_clean),
#             fuzz.partial_ratio(city_clean, first_word)
#         )
#         if score > best_score:
#             best_score = score
#             best_match = dest["code"]
#     return best_match if best_score >= 60 else None


# # ─────────────────────────────────────────────
# # RAW API CALLS
# # ─────────────────────────────────────────────

# def _get_headers():
#     return {
#         "Content-Type": "application/json",
#         "auth_id": AUTHID,
#         "auth_password": AUTHPASSSWORD
#     }


# def api_get_destinations():
#     r = requests.get(f"{BASE_URL}/getDestinations", headers=_get_headers())
#     return r.json()


# def api_get_availability(from_code, to_code, start_date, end_date):
#     payload = {
#         "aerocrs": {
#             "parms": {
#                 "dates": {"start": start_date, "end": end_date},
#                 "destinations": {"from": from_code, "to": to_code}
#             }
#         }
#     }
#     r = requests.post(f"{BASE_URL}/getAvailability", headers=_get_headers(), json=payload)
#     data = r.json()
#     return data["aerocrs"]["flights"]["count"] > 0


# def api_get_deeplink(from_code, to_code, start_date, adults=1, child=0, infant=0, end_date=None):
#     params = {
#         "from": from_code,
#         "to": to_code,
#         "start": start_date,
#         "adults": adults,
#         "child": child,
#         "infant": infant
#     }
#     if end_date:
#         params["end"] = end_date
#     query = "&".join(f"{k}={v}" for k, v in params.items())
#     url = f"{BASE_URL}/getDeepLink?{query}"
#     r = requests.get(url, headers=_get_headers())
#     return r.json()


# def api_get_ancillaries(booking_id, flight_id):
#     payload = {
#         "aerocrs": {
#             "parms": {
#                 "bookingid": booking_id,
#                 "flightid": flight_id,
#                 "currency": "USD"
#             }
#         }
#     }
#     try:
#         r = requests.post(f"{BASE_URL}/getAncillaries", headers=_get_headers(), json=payload)
#         return r.json()
#     except Exception as e:
#         return {"error": str(e)}


# def api_create_ancillary(booking_id, flight_id, item_id, pax_num=0):
#     payload = {
#         "aerocrs": {
#             "parms": {
#                 "ancillaries": {
#                     "ancillary": [{
#                         "paxnum": pax_num,
#                         "itemid": item_id,
#                         "bookingid": booking_id,
#                         "flightid": flight_id
#                     }]
#                 }
#             }
#         }
#     }
#     try:
#         r = requests.post(f"{BASE_URL}/createAncillary", headers=_get_headers(), json=payload)
#         return r.json()
#     except Exception as e:
#         return {"error": str(e)}


# def api_confirm_booking(booking_id, firstname, lastname, birthdate, phone, email):
#     payload = {
#         "aerocrs": {
#             "parms": {
#                 "bookingid": booking_id,
#                 "agentconfirmation": "apiconnector",
#                 "confirmationemail": email,
#                 "passenger": [{
#                     "paxtitle": "Mr.",
#                     "firstname": firstname,
#                     "lastname": lastname,
#                     "paxage": None,
#                     "paxnationailty": "US",
#                     "paxdoctype": "PP",
#                     "paxdocnumber": "9919239123",
#                     "paxdocissuer": "US",
#                     "paxdocexpiry": "2030/12/31",
#                     "paxbirthdate": birthdate,
#                     "paxphone": phone,
#                     "paxemail": email
#                 }]
#             }
#         }
#     }
#     try:
#         r = requests.post(f"{BASE_URL}/confirmBooking", headers=_get_headers(), json=payload)
#         return r.json()
#     except Exception as e:
#         return {"error": str(e)}


# # ─────────────────────────────────────────────
# # TOOLS
# # ─────────────────────────────────────────────

# @tool
# def check_ancillaries(booking_id: int, flight_id: int) -> dict:
#     """Check available ancillary extras (baggage, seats, meals) for a booking.
#     Call immediately after a booking is created.
#     If result has available_count=0, skip asking about extras and go straight to passenger details."""
#     result = api_get_ancillaries(booking_id, flight_id)
#     # Normalise the response so the LLM gets a clear signal
#     try:
#         aerocrs = result.get("aerocrs", {})
#         # Response shape: {"aerocrs": {"success": true, "ancillaries": []}}
#         # ancillaries can be [] (empty list) or a list of items
#         ancillaries = aerocrs.get("ancillaries", [])
#         if not ancillaries:
#             return {"available": False, "available_count": 0, "items": []}
#         return {"available": True, "available_count": len(ancillaries), "items": ancillaries}
#     except Exception:
#         return {"available": False, "available_count": 0, "items": []}


# @tool
# def add_ancillary(booking_id: int, flight_id: int, item_id: int, pax_num: int = 0) -> dict:
#     """Add an ancillary extra to a booking using item_id from check_ancillaries.
#     Only call this if check_ancillaries returned available=True."""
#     return api_create_ancillary(booking_id, flight_id, item_id, pax_num)


# @tool
# def confirm_booking(
#     booking_id: int,
#     firstname: str,
#     lastname: str,
#     birthdate: str,
#     phone: str,
#     email: str
# ) -> dict:
#     """Confirm a booking with passenger details.
#     Only call when you have ALL of: firstname, lastname, birthdate (YYYY/MM/DD), phone, email.
#     Do NOT tell the user the booking is confirmed until this tool returns a success response."""
#     return api_confirm_booking(booking_id, firstname, lastname, birthdate, phone, email)


# tools = [check_ancillaries, add_ancillary, confirm_booking]
# llm_with_tools = llm.bind_tools(tools)


# # ─────────────────────────────────────────────
# # FORMAT
# # ─────────────────────────────────────────────

# def format_deeplink_results(data, state):
#     try:
#         flights = data["aerocrs"]["flights"]["flight"]
#     except Exception:
#         return "No flights available."

#     outbound = [f for f in flights if f.get("direction") == "outbound"]
#     inbound = [f for f in flights if f.get("direction") == "inbound"]
#     structured_data = []

#     def process_flights(flight_list, direction_label):
#         for f in flight_list:
#             cheapest = min(f["classes"].values(), key=lambda c: float(c["fare"]["adultFare"]))
#             structured_data.append({
#                 "direction": direction_label,
#                 "flight_code": f["flightcode"],
#                 "flight_number": f["fltnum"],
#                 "flight_type": f["flighttype"],
#                 "origin": state["from_city"].title(),
#                 "destination": state["to_city"].title(),
#                 "start_time": f["STD"][5:16],
#                 "end_time": f["STA"][5:16],
#                 "via": f["via"] if f.get("via") else None,
#                 "price": cheapest["fare"]["adultFare"],
#                 "tax": cheapest["fare"]["tax"],
#                 "seats": cheapest["freeseats"],
#                 "classes": f["classes"]
#             })

#     if outbound:
#         process_flights(outbound, "Outbound")
#     if inbound:
#         process_flights(inbound, "Return")

#     return json.dumps({
#         "type": "flight_results",
#         "header": f"✈️  {state['from_city'].title()} → {state['to_city'].title()}",
#         "sub_header": f"👥  {state.get('adults', 1)} Adult(s)",
#         "context": {
#             "from_code": state.get("from_code"),
#             "to_code": state.get("to_code"),
#             "adults": state.get("adults", 1),
#             "child": state.get("child", 0),
#             "infant": state.get("infant", 0),
#             "triptype": "RT" if state.get("round_trip") else "OW"
#         },
#         "data": structured_data
#     })


# # ─────────────────────────────────────────────
# # NODES
# # ─────────────────────────────────────────────

# def conversation_node(state: FlightState):
#     system_prompt = """You are a friendly flight booking assistant. Be brief and natural — no bullet lists, no formal tone.
# - ask one question at a time
# FLOW:
# 1. Collect: from city, to city, date, passengers, one-way or round trip. Ask one thing at a time.
# 2. Flight results are shown in the UI — wait for user to pick a flight and fare class. Do NOT ask for passenger details yet. Just wait.
# 3. ONLY after receiving a system message that contains "BookingID" and "FlightID":
#    - Immediately call check_ancillaries with those exact IDs.
#    - If extras available, mention them casually. Add with add_ancillary if user wants.
#    - Once extras done (or none), THEN ask for passenger info in one casual message.
#      Example: "Quick — full name, date of birth, phone, and email?"
# 4. Once you have all 4, call confirm_booking.
# 5. Only say booking is confirmed AFTER confirm_booking returns success.

# CRITICAL:
# - NEVER ask for name/dob/phone/email before you see a BookingID system message.
# - User selects flight and class from the UI — you never need to ask about fare class.
# - No bullet points. Short and natural.
# - Only ask for missing info, never repeat what you already have.
# """

#     def trim_message(m):
#         """Keep messages lean for LLM context. Never crash — always return a valid message."""
#         try:
#             if isinstance(m, AIMessage):
#                 c = m.content
#                 # String content: strip heavy flight JSON
#                 if isinstance(c, str) and '"type": "flight_results"' in c:
#                     return AIMessage(
#                         content="[Flight options were displayed to the user]",
#                         tool_calls=m.tool_calls if hasattr(m, "tool_calls") else []
#                     )
#                 # List content (tool_calls block): pass through as-is
#                 return m
#             if isinstance(m, ToolMessage):
#                 raw = m.content if isinstance(m.content, str) else json.dumps(m.content)
#                 if "available_count" in raw:
#                     data = json.loads(raw)
#                     trimmed = {
#                         "available": data.get("available", False),
#                         "available_count": data.get("available_count", 0),
#                         "items": data.get("items", [])[:3]
#                     }
#                     return ToolMessage(content=json.dumps(trimmed), tool_call_id=m.tool_call_id)
#         except Exception:
#             pass
#         return m

#     # Use smaller window once flights are confirmed — passenger phase needs less context
#     window = -6 if state.get("flights") else -12

#     clean_msgs = [
#         trim_message(m)
#         for m in state["messages"][window:]
#         if isinstance(m, (HumanMessage, SystemMessage, AIMessage, ToolMessage))
#     ]

#     response = llm_with_tools.invoke([SystemMessage(content=system_prompt)] + clean_msgs)

#     return {**state, "messages": state["messages"] + [response]}


# def extraction_node(state: FlightState):
#     today = datetime.today().strftime("%Y-%m-%d")

#     already_known = {
#         "from_city": state.get("from_city"),
#         "to_city": state.get("to_city"),
#         "start_date": state.get("start_date"),
#         "adults": state.get("adults"),
#         "child": state.get("child"),
#         "infant": state.get("infant"),
#         "round_trip": state.get("round_trip"),
#         "return_date": state.get("return_date"),
#         "pax_firstname": state.get("pax_firstname"),
#         "pax_lastname": state.get("pax_lastname"),
#         "pax_birthdate": state.get("pax_birthdate"),
#         "pax_phone": state.get("pax_phone"),
#         "pax_email": state.get("pax_email"),
#     }

#     prompt = f"""Extract ALL details from this conversation — both flight info AND passenger info.
# Today is {today}.
# Already collected: {json.dumps(already_known)}

# FLIGHT RULES:
# - Only extract explicitly mentioned values. Never assume.
# - Never default adults to 1 unless user said "just me", "1 adult", or "solo".
# - round_trip: true only if user said yes to round trip. false only if user said no/one way. else null.
# - If a field is already known and unchanged, return null.

# PASSENGER RULES:
# - pax_firstname / pax_lastname: extract from full name. e.g. "arsh khan" → firstname=arsh, lastname=khan.
#   If only one name given, put it in firstname, lastname=null.
# - pax_birthdate: any date of birth mentioned. Can be past. e.g. "27 nov 2004" → "2004/11/27"
# - pax_phone: any phone/mobile number mentioned.
# - pax_email: any email address mentioned.
# - If already collected and not changed, return null.

# Return JSON only:
# {{
#   "from_city": null,
#   "to_city": null,
#   "start_date": null,
#   "adults": null,
#   "child": null,
#   "infant": null,
#   "round_trip": null,
#   "return_date": null,
#   "pax_firstname": null,
#   "pax_lastname": null,
#   "pax_birthdate": null,
#   "pax_phone": null,
#   "pax_email": null
# }}"""

#     clean_messages = []
#     for m in state["messages"][-10:]:
#         if isinstance(m, HumanMessage):
#             clean_messages.append(f"User: {m.content}")
#         elif isinstance(m, AIMessage) and m.content and isinstance(m.content, str) and m.content.strip():
#             clean_messages.append(f"Assistant: {m.content}")

#     convo = "\n".join(clean_messages)
#     response = llm.invoke([HumanMessage(content=prompt + "\n\n" + convo)])

#     try:
#         raw = response.content.strip()
#         if raw.startswith("```"):
#             raw = re.sub(r"```[a-z]*\n?", "", raw).strip().rstrip("```").strip()
#         data = json.loads(raw)
#     except Exception:
#         return state

#     print("DEBUG extracted:", data)
#     updates = {}

#     # ── Flight fields ──
#     if data.get("from_city"):
#         updates["from_city"] = data["from_city"]
#     if data.get("to_city"):
#         updates["to_city"] = data["to_city"]

#     if data.get("start_date"):
#         normalized_start = normalize_date(data["start_date"])
#         if normalized_start == "PAST_DATE":
#             return {
#                 **state,
#                 "messages": state["messages"] + [AIMessage(content="That date is in the past — pick a future date!")]
#             }
#         if normalized_start:
#             updates["start_date"] = normalized_start

#     if updates.get("start_date"):
#         start_dt = datetime.strptime(updates["start_date"], "%Y/%m/%d")
#         updates["end_date"] = (start_dt + timedelta(days=7)).strftime("%Y/%m/%d")

#     if data.get("adults") is not None:
#         updates["adults"] = data["adults"]
#     if data.get("child") is not None:
#         updates["child"] = data["child"]
#     if data.get("infant") is not None:
#         updates["infant"] = data["infant"]
#     if data.get("round_trip") is not None:
#         updates["round_trip"] = data["round_trip"]
#     if data.get("return_date"):
#         norm = normalize_date(data["return_date"])
#         if norm and norm != "PAST_DATE":
#             updates["return_date"] = norm

#     # ── Passenger fields ──
#     if data.get("pax_firstname"):
#         updates["pax_firstname"] = data["pax_firstname"]
#     if data.get("pax_lastname"):
#         updates["pax_lastname"] = data["pax_lastname"]
#     if data.get("pax_birthdate"):
#         bd = normalize_birthdate(data["pax_birthdate"])
#         if bd:
#             updates["pax_birthdate"] = bd
#     if data.get("pax_phone"):
#         updates["pax_phone"] = str(data["pax_phone"])
#     if data.get("pax_email"):
#         updates["pax_email"] = data["pax_email"]

#     # ── Reset logic ──
#     route_changed = (
#         (updates.get("from_city") and updates["from_city"] != state.get("from_city")) or
#         (updates.get("to_city") and updates["to_city"] != state.get("to_city"))
#     )
#     date_changed = updates.get("start_date") and updates["start_date"] != state.get("start_date")

#     if route_changed:
#         updates["from_code"] = None
#         updates["to_code"] = None
#         updates["flights"] = False

#     if date_changed:
#         updates["flights"] = False
#         updates["return_date"] = None

#     if route_changed and date_changed:
#         updates["round_trip"] = None
#         updates["return_date"] = None

#     return {**state, **updates}


# def flight_search_node(state: FlightState):
#     if not all([state.get("from_city"), state.get("to_city"), state.get("start_date"), state.get("end_date")]):
#         return state

#     if not state.get("from_code") or not state.get("to_code"):
#         destinations_data = api_get_destinations()
#         try:
#             dest_list = destinations_data["aerocrs"]["destinations"]["destination"]
#         except Exception:
#             return {**state, "messages": state["messages"] + [AIMessage(content="Couldn't fetch destinations, please try again.")]}

#         if not state.get("from_code"):
#             from_code = match_airport_code(state["from_city"], dest_list)
#             if not from_code:
#                 return {**state, "messages": state["messages"] + [AIMessage(content=f"Couldn't find '{state['from_city']}' as a departure city.")]}
#             state = {**state, "from_code": from_code}

#         if not state.get("to_code"):
#             to_code = match_airport_code(state["to_city"], dest_list)
#             if not to_code:
#                 return {**state, "messages": state["messages"] + [AIMessage(content=f"Couldn't find '{state['to_city']}' as a destination.")]}
#             state = {**state, "to_code": to_code}

#     has_flights = api_get_availability(
#         state["from_code"], state["to_code"], state["start_date"], state["end_date"]
#     )

#     if not has_flights:
#         return {**state, "flights": False, "messages": state["messages"] + [AIMessage(content="No flights found for this route and date.")]}

#     if state.get("adults") is None:
#         return {**state, "flights": False, "messages": state["messages"] + [AIMessage(content="How many passengers? (adults / kids / infants)")]}

#     if state.get("round_trip") is None:
#         return {**state, "flights": False, "messages": state["messages"] + [AIMessage(content="One way or round trip?")]}

#     if state.get("round_trip") and not state.get("return_date"):
#         return {**state, "flights": False, "messages": state["messages"] + [AIMessage(content="What's your return date?")]}

#     deeplink_data = api_get_deeplink(
#         from_code=state["from_code"],
#         to_code=state["to_code"],
#         start_date=state["start_date"],
#         adults=state.get("adults", 1),
#         child=state.get("child", 0),
#         infant=state.get("infant", 0),
#         end_date=state.get("return_date") if state.get("round_trip") else None
#     )

#     summary = format_deeplink_results(deeplink_data, state)

#     return {
#         **state,
#         "from_code": state["from_code"],
#         "to_code": state["to_code"],
#         "flights": True,
#         "messages": state["messages"] + [AIMessage(content=summary)]
#     }


# # ─────────────────────────────────────────────
# # ROUTING
# # ─────────────────────────────────────────────

# def should_search(state: FlightState):
#     if all([state.get("from_city"), state.get("to_city"), state.get("start_date"), state.get("end_date")]):
#         if state.get("flights") is not True:
#             return "search"
#     return "continue"


# # ─────────────────────────────────────────────
# # GRAPH
# # ─────────────────────────────────────────────

# def create_graph():
#     workflow = StateGraph(FlightState)

#     workflow.add_node("conversation", conversation_node)
#     workflow.add_node("extract", extraction_node)
#     workflow.add_node("search", flight_search_node)
#     workflow.add_node("tools", ToolNode(tools))

#     workflow.set_entry_point("conversation")

#     workflow.add_conditional_edges(
#         "conversation",
#         tools_condition,
#         {"tools": "tools", END: "extract"}
#     )

#     workflow.add_edge("tools", "conversation")

#     workflow.add_conditional_edges(
#         "extract",
#         should_search,
#         {"search": "search", "continue": END}
#     )

#     workflow.add_edge("search", END)

#     memory = MemorySaver()
#     return workflow.compile(checkpointer=memory)


# # ─────────────────────────────────────────────
# # MAIN
# # ─────────────────────────────────────────────

# def main():
#     graph = create_graph()
#     thread_id = "flight-thread-1"
#     print("Flight assistant ready. Type 'quit' to exit.\n")

#     while True:
#         user_input = input("You: ").strip()
#         if user_input.lower() in ["quit", "exit"]:
#             break
#         result = graph.invoke(
#             {"messages": [HumanMessage(content=user_input)]},
#             config={"configurable": {"thread_id": thread_id}}
#         )
#         last = result["messages"][-1]
#         print("Assistant:", last.content if hasattr(last, "content") else str(last), "\n")


# if __name__ == "__main__":
#     main()


import os
import json
import requests
from datetime import datetime, timedelta
from typing import TypedDict, Annotated, Sequence, Optional
import operator
import re
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from dotenv import load_dotenv
import dateparser
from thefuzz import fuzz

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "false"

AUTHID = os.getenv("AUTHID")
AUTHPASSSWORD = os.getenv("AUTHPASSSWORD")
BASE_URL = "https://api.aerocrs.com/v5"

llm = ChatOpenAI(
    model="gpt-4o",
    temperature=0.2,
    max_tokens=800
)




class FlightState(TypedDict):
    messages: Annotated[Sequence[HumanMessage | AIMessage | SystemMessage | ToolMessage], operator.add]




def normalize_date(date_text: str, allow_past: bool = False) -> Optional[str]:
    """Parse natural language date → YYYY/MM/DD. Returns None or 'PAST_DATE'."""
    if not date_text:
        return None
    today = datetime.today()
    settings = {
        'PREFER_DATES_FROM': 'past' if allow_past else 'future',
        'RELATIVE_BASE': today
    }
    parsed = dateparser.parse(date_text, settings=settings)
    if not parsed:
        return None
    if not allow_past and parsed.date() < today.date():

        try:
            parsed = parsed.replace(year=parsed.year + 1)
        except ValueError:
            return "PAST_DATE"
        if parsed.date() < today.date():
            return "PAST_DATE"
    return parsed.strftime("%Y/%m/%d")


def _parse_time(dt_str: str) -> str:
    """Robustly extract HH:MM from any datetime string format."""
    if not dt_str:
        return ''
    for sep in ['T', ' ']:
        if sep in dt_str:
            parts = dt_str.split(sep)
            if len(parts) >= 2:
                return parts[1][:5]
    return dt_str[-5:] if len(dt_str) >= 5 else dt_str


def clean_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9 ]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "auth_id": AUTHID,
        "auth_password": AUTHPASSSWORD
    }


def _match_airport_code(city_name: str, destinations: list) -> Optional[str]:
    city_clean = clean_text(city_name)
    best_match, best_score = None, 0
    for dest in destinations:
        name_clean = clean_text(dest.get("name", ""))
        code = dest.get("code", "").lower()
        iata = dest.get("iatacode", "").lower()
        if city_clean in (code, iata) or city_clean in name_clean:
            return dest["code"]
        if all(w in name_clean for w in city_clean.split()):
            return dest["code"]
        score = max(
            fuzz.partial_ratio(city_clean, name_clean),
            fuzz.partial_ratio(city_clean, name_clean.split()[0] if name_clean else "")
        )
        if score > best_score:
            best_score, best_match = score, dest["code"]
    return best_match if best_score >= 60 else None




@tool
def search_destinations(query: str) -> dict:
    """Search for available airport/city destinations by name.
    Use this to validate city names and get their airport codes.
    Args:
        query: City or airport name to look up (e.g. "Arusha", "Dar es Salaam")
    Returns:
        dict with 'found' bool, 'code' (IATA), 'name', and 'similar' alternatives if not found.
    """
    try:
        r = requests.get(f"{BASE_URL}/getDestinations", headers=_get_headers())
        dest_list = r.json()["aerocrs"]["destinations"]["destination"]
    except Exception as e:
        return {"found": False, "error": str(e)}

    code = _match_airport_code(query, dest_list)
    if code:
        matched = next((d for d in dest_list if d["code"] == code), {})
        return {"found": True, "code": code, "name": matched.get("name", query)}


    query_clean = clean_text(query)
    similar = []
    for dest in dest_list:
        score = fuzz.partial_ratio(query_clean, clean_text(dest.get("name", "")))
        if score >= 40:
            similar.append({"name": dest.get("name"), "code": dest.get("code"), "score": score})
    similar = sorted(similar, key=lambda x: -x["score"])[:5]
    return {"found": False, "query": query, "similar_destinations": similar}


@tool
def check_flight_availability(
    from_code: str,
    to_code: str,
    travel_date: str,
    adults: int,
    children: int = 0,
    infants: int = 0,
    round_trip: bool = False,
    return_date: str = None
) -> dict:
    """Check if flights are available and fetch flight options for a given route and date.
    Call this once you have confirmed: from city code, to city code, date, passengers, and trip type.
    Args:
        from_code: Departure IATA code (e.g. "JRO")
        to_code: Arrival IATA code (e.g. "DAR")
        travel_date: Departure date in YYYY/MM/DD format
        adults: Number of adult passengers (>=1)
        children: Number of child passengers
        infants: Number of infant passengers
        round_trip: True if return flight needed
        return_date: Return date in YYYY/MM/DD if round_trip is True
    Returns:
        Structured flight results JSON for the UI, or an error message.
    """

    dep_date = normalize_date(travel_date)
    if not dep_date or dep_date == "PAST_DATE":
        return {"error": "Departure date is invalid or in the past. Please provide a future date."}

    end_date = (datetime.strptime(dep_date, "%Y/%m/%d") + timedelta(days=7)).strftime("%Y/%m/%d")


    try:
        payload = {
            "aerocrs": {
                "parms": {
                    "dates": {"start": dep_date, "end": end_date},
                    "destinations": {"from": from_code, "to": to_code}
                }
            }
        }
        avail_r = requests.post(f"{BASE_URL}/getAvailability", headers=_get_headers(), json=payload)
        avail_data = avail_r.json()
        count = avail_data["aerocrs"]["flights"]["count"]
        if count == 0:
            return {"error": f"No flights available from {from_code} to {to_code} around {dep_date}. Try different dates."}
    except Exception as e:
        return {"error": f"Availability check failed: {e}"}


    try:
        params = {
            "from": from_code, "to": to_code,
            "start": dep_date,
            "adults": adults, "child": children, "infant": infants
        }
        if round_trip and return_date:
            ret_date = normalize_date(return_date)
            if ret_date and ret_date != "PAST_DATE":
                params["end"] = ret_date

        query = "&".join(f"{k}={v}" for k, v in params.items())
        dl_r = requests.get(f"{BASE_URL}/getDeepLink?{query}", headers=_get_headers())
        data = dl_r.json()
        flights = data["aerocrs"]["flights"]["flight"]
    except Exception as e:
        return {"error": f"Could not retrieve flight details: {e}"}


    outbound = [f for f in flights if f.get("direction") == "outbound"]
    inbound = [f for f in flights if f.get("direction") == "inbound"]
    structured = []

    def process(flight_list, direction_label):
        for f in flight_list:
            try:
                cheapest = min(f["classes"].values(), key=lambda c: float(c["fare"]["adultFare"]))
                structured.append({
                    "direction": direction_label,
                    "flight_code": f.get("flightcode"),
                    "flight_number": f.get("fltnum"),
                    "origin_code": from_code,
                    "destination_code": to_code,
                    "departure_time": _parse_time(f.get("STD", "")),
                    "arrival_time": _parse_time(f.get("STA", "")),
                    "via": f.get("via") or None,
                    "price": cheapest["fare"]["adultFare"],
                    "tax": cheapest["fare"]["tax"],
                    "seats_available": cheapest.get("freeseats"),
                    "classes": f["classes"]
                })
            except Exception:
                continue

    process(outbound, "Outbound")
    process(inbound, "Return")

    return {
        "type": "flight_results",
        "header": f"✈️  {from_code} → {to_code}",
        "sub_header": f"👥 {adults} Adult(s)" + (f", {children} Child(ren)" if children else "") + (f", {infants} Infant(s)" if infants else ""),
        "context": {
            "from_code": from_code,
            "to_code": to_code,
            "adults": adults,
            "child": children,
            "infant": infants,
            "triptype": "RT" if round_trip else "OW",
            "departure_date": dep_date,
            "return_date": params.get("end")
        },
        "data": structured
    }


@tool
def check_ancillaries(booking_id: int, flight_id: int) -> dict:
    """Check available add-ons (baggage, meals, seats) for a booking.
    Always call this immediately after a booking is created (after seeing a BookingID in the conversation).
    Args:
        booking_id: The booking ID from the system message
        flight_id: The flight ID from the system message
    Returns:
        dict with available add-ons or empty if none.
    """
    try:
        payload = {
            "aerocrs": {
                "parms": {
                    "bookingid": booking_id,
                    "flightid": flight_id,
                    "currency": "USD"
                }
            }
        }
        r = requests.post(f"{BASE_URL}/getAncillaries", headers=_get_headers(), json=payload)
        aerocrs = r.json().get("aerocrs", {})
        items = aerocrs.get("ancillaries", [])
        if not items:
            return {"available": False, "available_count": 0, "items": []}
        return {"available": True, "available_count": len(items), "items": items}
    except Exception as e:
        return {"available": False, "available_count": 0, "error": str(e)}


@tool
def add_ancillary(booking_id: int, flight_id: int, item_id: int, pax_num: int = 0) -> dict:
    """Add an ancillary extra (baggage, meal, etc.) to a booking.
    Only call if check_ancillaries returned available=True and user confirmed they want an extra.
    Args:
        booking_id: Booking ID
        flight_id: Flight ID
        item_id: The item ID from check_ancillaries results
        pax_num: Passenger number (default 0 = first passenger)
    Returns:
        API response dict.
    """
    try:
        payload = {
            "aerocrs": {
                "parms": {
                    "ancillaries": {
                        "ancillary": [{
                            "paxnum": pax_num,
                            "itemid": item_id,
                            "bookingid": booking_id,
                            "flightid": flight_id
                        }]
                    }
                }
            }
        }
        r = requests.post(f"{BASE_URL}/createAncillary", headers=_get_headers(), json=payload)
        return r.json()
    except Exception as e:
        return {"error": str(e)}


@tool
def confirm_booking(
    booking_id: int,
    firstname: str,
    lastname: str,
    birthdate: str,
    phone: str,
    email: str
) -> dict:
    """Finalize a booking with passenger details.
    ONLY call when you have ALL of: firstname, lastname, birthdate, phone, and email.
    If any detail is missing, ask the user first — do NOT call with placeholder values.
    Birthdate must be in YYYY/MM/DD format.
    Args:
        booking_id: Booking ID from the system message
        firstname: Passenger's first name
        lastname: Passenger's last name
        birthdate: Date of birth in YYYY/MM/DD
        phone: Contact phone number
        email: Contact email address
    Returns:
        Confirmation response from the API.
    """
    try:
        bd = normalize_date(birthdate, allow_past=True) or birthdate
        payload = {
            "aerocrs": {
                "parms": {
                    "bookingid": booking_id,
                    "agentconfirmation": "apiconnector",
                    "confirmationemail": email,
                    "passenger": [{
                        "paxtitle": "Mr.",
                        "firstname": firstname,
                        "lastname": lastname,
                        "paxage": None,
                        "paxnationailty": "US",
                        "paxdoctype": "PP",
                        "paxdocnumber": "9919239123",
                        "paxdocissuer": "US",
                        "paxdocexpiry": "2028/12/31",
                        "paxbirthdate": bd,
                        "paxphone": str(phone),
                        "paxemail": email,
                    }]
                }
            }
        }
        r = requests.post(f"{BASE_URL}/confirmBooking", headers=_get_headers(), json=payload)
        result = r.json()
        print(f"[CONFIRM RESPONSE] {result}")
        return result
    except Exception as e:
        return {"error": str(e)}


tools = [search_destinations, check_flight_availability, check_ancillaries, add_ancillary, confirm_booking]
llm_with_tools = llm.bind_tools(tools)



SYSTEM_PROMPT = f"""You are Aria, a warm and natural flight booking assistant. You speak like a helpful human — conversational, clear, and friendly. No bullet lists unless absolutely necessary. Never robotic.

Today's date: {datetime.today().strftime("%A, %B %d, %Y")}

## YOUR TOOLS
You have 5 tools. Use them intelligently:
1. `search_destinations` — Validate city names and get airport codes. Use this before searching flights if you're unsure about a city name.
2. `check_flight_availability` — Fetch available flights once you have: origin, destination, date, passenger count, and trip type.
3. `check_ancillaries` — Check for add-ons (baggage, meals) right after a booking is created.
4. `add_ancillary` — Add an extra if the user wants one.
5. `confirm_booking` — Finalize the booking once you have ALL passenger details.
- ask only one thing at a time

## CONVERSATION FLOW

### Phase 1: Gather flight details (ask one thing at a time if unclear)
Collect: departure city, arrival city, travel date, number of passengers (adults/children/infants), and one-way vs round trip.
- ask one question at a time
- dont proceed to next step unless you have all the details like origin, destination, date, passenger count, and trip type.
SMART CLARIFICATION RULES:
- If user says "one" for passengers, ask: "Just one adult, or do you have kids or infants too?"
- If user says "tomorrow" for date, that's fine — use it.
- If user says a city that's ambiguous, call `search_destinations` and ask to confirm.
- Never assume adults=1 unless user explicitly said "just me", "solo", or "1 adult".
- If round trip: also ask for return date before searching.
- Validate cities with `search_destinations` before calling `check_flight_availability`.

### Phase 2: Show flights
Once you have everything, call `check_flight_availability`.
IMPORTANT: Flight results are automatically rendered as interactive cards in the UI — do NOT list, describe, or summarise the flights in text.
After calling the tool, say ONLY something brief like: "Here you go! Pick a flight and fare class from the cards and I'll get you booked." Then WAIT.
Do not ask for passenger details yet.

### Phase 3: After booking created (system message with BookingID + FlightID)
1. Immediately call `check_ancillaries` with the exact BookingID and FlightID.
2. If extras are available, casually mention 1-2 highlights: "Want to add checked baggage or a meal?"
3. Once extras are sorted (or skipped), ask for passenger details in ONE natural message:
   "Almost there! Just need a few details — full name, date of birth, phone number, and email?"

### Phase 4: Confirm booking
Once you have firstname, lastname, birthdate, phone, and email — call `confirm_booking`.
Only announce success AFTER the tool returns a successful response.

## CRITICAL RULES
- NEVER ask for passenger details before you see a BookingID system message.
- NEVER call confirm_booking with missing or placeholder data.
- NEVER make up airport codes — always use search_destinations first.
- If something is unclear, ask ONE focused clarifying question.
- Be warm, brief, human. No formal language.
"""



def conversation_node(state: FlightState) -> FlightState:
    """Main LLM node — decides what to say or which tool to call."""

    def trim_message(m):
        """Trim heavy messages to save tokens — but NEVER break tool_calls pairing.
        
        OpenAI requires every ToolMessage to follow an AIMessage that has tool_calls.
        We must never strip/replace the AIMessage tool_calls or remove ToolMessages,
        as that causes a 400 BadRequestError. Instead, just slim the data payload.
        """
        try:
            if isinstance(m, ToolMessage):
                content = m.content if isinstance(m.content, str) else json.dumps(m.content)
                if '"type": "flight_results"' in content:

                    try:
                        data = json.loads(content)
                        flights = data.get("data", [])
                        data["data"] = [{
                            "flight_code": f.get("flight_code"),
                            "direction": f.get("direction"),
                            "departure_time": f.get("departure_time"),
                            "arrival_time": f.get("arrival_time"),
                            "price": f.get("price"),
                        } for f in flights[:4]]
                        data["_trimmed"] = True
                        return ToolMessage(content=json.dumps(data), tool_call_id=m.tool_call_id)
                    except Exception:
                        pass
        except Exception:
            pass
        return m

   

    all_msgs = list(state["messages"])


    trimmed = [trim_message(m) for m in all_msgs]


    def is_complete_window(msgs):
        """Return True if msgs has no broken tool_call groups."""
        pending_ids = set()
        for m in msgs:
            if isinstance(m, AIMessage):
                tc = getattr(m, "tool_calls", [])
                if tc:
                    pending_ids = {c["id"] for c in tc}
                else:
                    pending_ids = set()
            elif isinstance(m, ToolMessage):
                pending_ids.discard(m.tool_call_id)
        return len(pending_ids) == 0


    window = trimmed[-30:]


    for start in range(len(window)):
        candidate = window[start:]

        if isinstance(candidate[0], ToolMessage):
            continue

        if isinstance(candidate[0], AIMessage) and getattr(candidate[0], "tool_calls", []):
            continue
        if is_complete_window(candidate):
            window = candidate
            break
    else:
        window = trimmed[-6:]

    response = llm_with_tools.invoke([SystemMessage(content=SYSTEM_PROMPT)] + window)
    return {"messages": [response]}



def create_graph():
    workflow = StateGraph(FlightState)

    workflow.add_node("conversation", conversation_node)
    workflow.add_node("tools", ToolNode(tools))

    workflow.set_entry_point("conversation")

    workflow.add_conditional_edges(
        "conversation",
        tools_condition,
        {"tools": "tools", END: END}
    )

    workflow.add_edge("tools", "conversation")

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)




def main():
    graph = create_graph()
    thread_id = "flight-thread-1"
    print("Aria (Flight Assistant) ready. Type 'quit' to exit.\n")
    print("Aria: Hey! I'm Aria, your flight assistant. Where are you thinking of flying to?\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit"]:
            print("Aria: Safe travels! 👋")
            break

        result = graph.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config={"configurable": {"thread_id": thread_id}}
        )

        last = result["messages"][-1]
        content = last.content if hasattr(last, "content") else str(last)

        if isinstance(content, str) and '"type": "flight_results"' in content:
            try:
                data = json.loads(content)
                print(f"\nAria: {data.get('header', '')} | {data.get('sub_header', '')}")
                for f in data.get("data", []):
                    print(f"  [{f['direction']}] Flight {f['flight_code']} | "
                          f"{f['departure_time']} → {f['arrival_time']} | "
                          f"From ${f['price']} | {f['seats_available']} seats left")
                print()
                continue
            except Exception:
                pass

        if content:
            print(f"Aria: {content}\n")


if __name__ == "__main__":
    main()