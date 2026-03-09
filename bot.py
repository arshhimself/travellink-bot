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



AUTHID = os.getenv("AUTHID")
AUTHPASSSWORD = os.getenv("AUTHPASSSWORD")
BASE_URL = "https://api.aerocrs.com/v5"

# Model tiering — cheap model for simple Q&A, full model for complex phases
llm_mini = ChatOpenAI(model="gpt-4o-mini", temperature=0.2, max_tokens=500)
llm_full = ChatOpenAI(model="gpt-4o", temperature=0.2, max_tokens=800)

# Context window size — keep small to save tokens
MAX_CONTEXT_MESSAGES = 16


# ─────────────────────────────────────────────
# STATE — lean, single source of truth
# ─────────────────────────────────────────────

class FlightState(TypedDict):
    messages: Annotated[Sequence[HumanMessage | AIMessage | SystemMessage | ToolMessage], operator.add]


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

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
        # Try bumping year
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


# ─────────────────────────────────────────────
# TOOLS — ALL logic lives here now
# ─────────────────────────────────────────────

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

    # Return similar options to help clarify
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
    # Parse + validate dates
    dep_date = normalize_date(travel_date)
    if not dep_date or dep_date == "PAST_DATE":
        return {"error": "Departure date is invalid or in the past. Please provide a future date."}

    # Validate return date for round trips
    if round_trip and return_date:
        ret_date = normalize_date(return_date)
        if not ret_date or ret_date == "PAST_DATE":
            return {"error": "Return date is invalid or in the past. Please provide a future date."}
        if ret_date < dep_date:
            return {"error": f"Return date ({ret_date}) cannot be before departure date ({dep_date}). Please pick a return date on or after {dep_date}."}

    end_date = (datetime.strptime(dep_date, "%Y/%m/%d") + timedelta(days=7)).strftime("%Y/%m/%d")

    # Availability check
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

    # Fetch deeplink flights
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

    # Format results
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
        "header": f"{from_code} → {to_code}",
        "sub_header": f"{adults} Adult{'' if adults == 1 else 's'}" + (f", {children} Child{'ren' if children != 1 else ''}" if children else "") + (f", {infants} Infant{'' if infants == 1 else 's'}" if infants else ""),
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
        raw_json = r.json()
        print(f"[ANCILLARIES RAW] booking={booking_id} flight={flight_id} → {json.dumps(raw_json)[:1500]}")

        aerocrs = raw_json.get("aerocrs", {})

        # Real API shape:
        # {"aerocrs": {"ancillaries": {"ancillary": [
        #   {"name": "WHEELCHAIR SERVICE", "description": "...", "groupname": "...",
        #    "items": [{"itemid": "17520", "itemname": "Wheelchair service charge",
        #               "fare": {"adult": "25.00"}, ...}]}
        # ]}}}
        ancillaries_block = aerocrs.get("ancillaries") or {}
        if isinstance(ancillaries_block, list):
            groups = ancillaries_block
        elif isinstance(ancillaries_block, dict):
            raw_anc = ancillaries_block.get("ancillary") or []
            groups = raw_anc if isinstance(raw_anc, list) else [raw_anc]
        else:
            groups = []

        normalised = []
        for group in groups:
            if not isinstance(group, dict):
                continue
            group_name = group.get("groupname") or group.get("name") or "Add-on"
            group_desc = group.get("name") or group.get("description") or ""

            # Each group has sub-items with itemid + fare
            sub_items = group.get("items") or []
            if isinstance(sub_items, dict):
                sub_items = [sub_items]

            if sub_items:
                for sub in sub_items:
                    if not isinstance(sub, dict):
                        continue
                    fare = sub.get("fare") or {}
                    if isinstance(fare, str):
                        price = fare or "0"
                    else:
                        price = fare.get("adult") or fare.get("adultFare") or sub.get("price") or "0"
                    normalised.append({
                        "itemid": sub.get("itemid") or sub.get("id"),
                        "name": sub.get("itemname") or sub.get("name") or group_desc or "Extra",
                        "category": group_name,
                        "price": str(price),
                        "currency": "USD",
                        "description": group.get("description") or group_desc or "",
                    })
            else:
                # Group itself is the purchasable item
                fare = group.get("fare") or {}
                if isinstance(fare, str):
                    price = fare or "0"
                else:
                    price = fare.get("adult") or fare.get("adultFare") or group.get("price") or "0"
                normalised.append({
                    "itemid": group.get("itemid") or group.get("id"),
                    "name": group_desc or group_name,
                    "category": group_name,
                    "price": str(price),
                    "currency": "USD",
                    "description": group.get("description") or "",
                })

        if not normalised:
            print(f"[ANCILLARIES] No items parsed for booking={booking_id}")
            return {"type": "ancillary_results", "available": False, "available_count": 0, "items": []}

        print(f"[ANCILLARIES] {len(normalised)} items found")
        return {
            "type": "ancillary_results",
            "available": True,
            "available_count": len(normalised),
            "items": normalised,
            "booking_id": booking_id,
            "flight_id": flight_id
        }
    except Exception as e:
        print(f"[ANCILLARIES ERROR] {e}")
        return {"type": "ancillary_results", "available": False, "available_count": 0, "error": str(e)}


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



ALL_TOOLS = [search_destinations, check_flight_availability, check_ancillaries, add_ancillary, confirm_booking]


PHASE_TOOLS = {
    "gathering":    [search_destinations, check_flight_availability],
    "searching":    [search_destinations, check_flight_availability],
    "post_booking": [check_ancillaries, add_ancillary, confirm_booking],
}


PHASE_MODEL = {
    "gathering":    llm_mini,
    "searching":    llm_mini,
    "post_booking": llm_mini,
}




def detect_phase(messages: list) -> str:
    """Scan recent messages to determine conversation phase.
    
    Returns one of: 'gathering', 'searching', 'post_booking'
    """
    has_booking_id = False
    has_flight_results = False
    
    # Scan in reverse for efficiency — most recent signals matter most
    for msg in reversed(messages[-20:]):
        content = getattr(msg, "content", "")
        if isinstance(content, dict):
            content = json.dumps(content)
        if not isinstance(content, str):
            content = str(content)
        
        content_lower = content.lower()
        
        # BookingID in a system message = post-booking phase
        if isinstance(msg, SystemMessage) and "bookingid" in content_lower:
            has_booking_id = True
        
        # Flight results returned = we've already searched
        if '"type": "flight_results"' in content:
            has_flight_results = True
    
    # Determine phase based on signals
    if has_booking_id:
        return "post_booking"
    if has_flight_results:
        return "searching"
    
    return "gathering"


# ─────────────────────────────────────────────
# SYSTEM PROMPTS — phase-specific, compressed
# ─────────────────────────────────────────────

_TODAY = datetime.today().strftime("%A, %B %d, %Y")

_PROMPT_PREAMBLE = f"""You are a warm and natural flight booking assistant. Conversational, clear, friendly. No bullet lists unless necessary. Never robotic.
Today: {_TODAY}
CRITICAL: Be warm and brief. Ask ONE clarifying question at a time. Never make up airport codes."""

PHASE_PROMPTS = {
    "gathering": _PROMPT_PREAMBLE + """

Your job now: collect flight details — departure city, arrival city, travel date, passengers (adults/children/infants), one-way or round trip.
- If user says a city, call `search_destinations` to validate it and get the airport code.
- If user says "one" for passengers, ask: "Just one adult, or do you have kids or infants too?"
- Never assume adults=1 unless they explicitly said "just me" / "solo" / "1 adult".
- If the user gives an ambiguous date (just a number like "29", or a day without a month like "the 5th"), ask once to confirm the month before proceeding. Do not guess.
- If round trip, also ask for return date. The return date MUST be on or after the departure date — if the user gives a return date before the outbound date, politely tell them and ask for a valid return date.
- Once you have ALL details, confirm them with the user before proceeding.""",

    "searching": _PROMPT_PREAMBLE + """

You have all flight details. Call `check_flight_availability` to fetch flights.
- If a city needs re-validation, use `search_destinations`.
- IMPORTANT: Flight results render as interactive cards in the UI — do NOT list or describe flights in text.
- After calling the tool, say ONLY something brief like: "Here you go! Pick a flight and fare class from the cards."
- Do NOT ask for passenger details yet — wait for a BookingID.""",

    "post_booking": _PROMPT_PREAMBLE + """

A booking has been created. Follow this EXACT order:
1. Immediately call `check_ancillaries` with the BookingID and FlightID from the system message.
2. If extras are available, casually mention 1-2 highlights: "Want to add checked baggage or a meal?"
3. Use `add_ancillary` if the user wants an extra.
4. Once extras are sorted (or skipped), ask for passenger details in ONE message:
   "Almost there! Just need your full name, date of birth, phone number, and email."
5. Once the user gives ALL details (firstname, lastname, birthdate, phone, email), call `confirm_booking`.
6. Only announce success AFTER the tool returns a successful response.

⚠️ CRITICAL: NEVER call `confirm_booking` with made-up or placeholder data like "John Doe".
You MUST ask the user for their real name, birthdate, phone, and email BEFORE calling confirm_booking.
If ANY detail is missing, ask for it — do NOT guess or fill in defaults.""",
}


# ─────────────────────────────────────────────
# NODES
# ─────────────────────────────────────────────


def conversation_node(state: FlightState) -> FlightState:
    """Main LLM node — detects phase, binds only relevant tools, picks model."""

    def trim_message(m):
        """Trim heavy ToolMessage payloads to save tokens. Never removes messages."""
        try:
            if isinstance(m, ToolMessage):
                content = m.content if isinstance(m.content, str) else json.dumps(m.content)
                if '"type": "flight_results"' in content:
                    try:
                        data = json.loads(content)
                        data["data"] = [{
                            "flight_code": f.get("flight_code"),
                            "direction": f.get("direction"),
                            "departure_time": f.get("departure_time"),
                            "arrival_time": f.get("arrival_time"),
                            "price": f.get("price"),
                        } for f in data.get("data", [])[:4]]
                        data["_trimmed"] = True
                        return ToolMessage(content=json.dumps(data), tool_call_id=m.tool_call_id)
                    except Exception:
                        pass
                if '"type": "ancillary_results"' in content:
                    try:
                        data = json.loads(content)
                        slim = {
                            "type": "ancillary_results",
                            "available": data.get("available"),
                            "available_count": data.get("available_count"),
                            "booking_id": data.get("booking_id"),
                            "flight_id": data.get("flight_id"),
                            "items": [
                                {"itemid": i.get("itemid"), "name": i.get("name"),
                                 "price": i.get("price"), "category": i.get("category")}
                                for i in data.get("items", [])[:6]
                            ],
                        }
                        return ToolMessage(content=json.dumps(slim), tool_call_id=m.tool_call_id)
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

    window = trimmed[-MAX_CONTEXT_MESSAGES:]

    # Advance start past any incomplete leading tool group
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

    # ── Phase-aware tool binding & model selection ──
    phase = detect_phase(all_msgs)
    phase_tools = PHASE_TOOLS.get(phase, ALL_TOOLS)
    phase_model = PHASE_MODEL.get(phase, llm_full)
    phase_prompt = PHASE_PROMPTS.get(phase, PHASE_PROMPTS["gathering"])

    llm_with_phase_tools = phase_model.bind_tools(phase_tools)

    print(f"[PHASE] {phase} | tools={[t.name for t in phase_tools]} | model={phase_model.model_name}")

    response = llm_with_phase_tools.invoke([SystemMessage(content=phase_prompt)] + window)
    return {"messages": [response]}


# ─────────────────────────────────────────────
# GRAPH
# ─────────────────────────────────────────────

def create_graph():
    workflow = StateGraph(FlightState)

    workflow.add_node("conversation", conversation_node)
    workflow.add_node("tools", ToolNode(ALL_TOOLS))  # ToolNode keeps ALL tools to execute any call

    workflow.set_entry_point("conversation")

    # After conversation: if tool called → go to tools, else END
    workflow.add_conditional_edges(
        "conversation",
        tools_condition,
        {"tools": "tools", END: END}
    )

    # After tools: always return to conversation for follow-up
    workflow.add_edge("tools", "conversation")

    memory = MemorySaver()
    return workflow.compile(checkpointer=memory)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    graph = create_graph()
    thread_id = "flight-thread-1"
    print("Flight Assistant ready. Type 'quit' to exit.\n")
    print("Assistant: Hey! I'm your flight assistant. Where are you thinking of flying to?\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ["quit", "exit"]:
            print("Assistant: Safe travels! 👋")
            break

        result = graph.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config={"configurable": {"thread_id": thread_id}}
        )

        last = result["messages"][-1]
        content = last.content if hasattr(last, "content") else str(last)

        # Pretty-print flight results JSON if present
        if isinstance(content, str) and '"type": "flight_results"' in content:
            try:
                data = json.loads(content)
                print(f"\nAssistant: {data.get('header', '')} | {data.get('sub_header', '')}")
                for f in data.get("data", []):
                    print(f"  [{f['direction']}] Flight {f['flight_code']} | "
                          f"{f['departure_time']} → {f['arrival_time']} | "
                          f"From ${f['price']} | {f['seats_available']} seats left")
                print()
                continue
            except Exception:
                pass

        if content:
            print(f"Assistant: {content}\n")


if __name__ == "__main__":
    main()