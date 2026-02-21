from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

from bot import create_graph
import requests
import os
import json

AUTHID = os.getenv("AUTHID")
AUTHPASSSWORD = os.getenv("AUTHPASSSWORD")
BASE_URL = "https://api.aerocrs.com/v5"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


graph = create_graph()


class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "default_thread"

class ChatResponse(BaseModel):
    response: str
    thread_id: str
    flight_results: Optional[dict] = None  

class FlightLogRequest(BaseModel):
    flight_code: str

class BookingRequest(BaseModel):
    flight_id: int
    fare_id: int
    from_code: str
    to_code: str
    trip_type: str = "OW"
    adults: int = 1
    child: int = 0
    infant: int = 0
    thread_id: Optional[str] = "default_thread" 




def _get_headers() -> dict:
    return {
        "Content-Type": "application/json",
        "auth_id": AUTHID,
        "auth_password": AUTHPASSSWORD
    }


def _extract_last_text(messages: list, new_from_index: int = 0) -> tuple:
    """
    Extract the bot's text reply and any flight_results from THIS invocation only.

    `new_from_index` is the length of the message list BEFORE graph.invoke was called.
    We only scan messages added during this turn — this prevents stale flight data
    from a previous search bleeding into every subsequent response.

    Returns (text_content, flight_results_dict_or_None)
    """
    flight_results = None
    text_content = None


    new_messages = messages[new_from_index:]

    for msg in reversed(new_messages):
        raw = getattr(msg, "content", None)
        if not raw:
            continue

        content_str = raw if isinstance(raw, str) else json.dumps(raw)


        if flight_results is None and '"type": "flight_results"' in content_str:
            try:
                data = json.loads(content_str) if isinstance(raw, str) else raw
                if isinstance(data, dict) and data.get("type") == "flight_results":
                    flight_results = data
                    continue
            except Exception:
                pass


        if text_content is None and isinstance(msg, AIMessage):
            if isinstance(raw, str) and raw.strip() and '"type": "flight_results"' not in raw:
                text_content = raw.strip()
            elif isinstance(raw, list):
                text = " ".join(
                    b.get("text", "") for b in raw
                    if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
                if text:
                    text_content = text


    if text_content and flight_results:
        lower = text_content.lower()
        if any(p in lower for p in [
            "here are", "here's", "available flights", "i found", "flights from",
            "you can choose", "please pick", "listed below", "options below", "following flights"
        ]):
            text_content = "Here are the available flights — pick one and I'll get you booked!"

    return text_content or "Let me check that for you...", flight_results



@app.get("/")
def read_root():
    return {"message": "Flight Bot API is running"}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Main chat endpoint. Send user messages here.
    If message starts with "__booking__:", it is treated as an internal trigger
    (sent by the frontend after a successful booking) and injected as a SystemMessage
    so the bot starts the ancillaries/passenger flow.
    """
    try:
        config = {"configurable": {"thread_id": request.thread_id}}


        if request.message.startswith("__booking__:"):
            msg = SystemMessage(content=request.message[len("__booking__:"):].strip())
        else:
            msg = HumanMessage(content=request.message)


        try:
            state_before = graph.get_state(config)
            count_before = len(state_before.values.get("messages", [])) if state_before and state_before.values else 0
        except Exception:
            count_before = 0

        result = graph.invoke({"messages": [msg]}, config=config)
        text, flight_results = _extract_last_text(result["messages"], new_from_index=count_before)

        return ChatResponse(
            response=text,
            thread_id=request.thread_id,
            flight_results=flight_results
        )

    except Exception as e:
        import traceback
        print("[CHAT ERROR]", traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/log-flight")
def log_flight(request: FlightLogRequest):
    """Log which flight the user clicked on (for analytics)."""
    print(f"\n[CLICKED] Flight code: {request.flight_code}\n")
    return {"status": "logged", "code": request.flight_code}


@app.post("/book-flight")
def book_flight(request: BookingRequest):
    """
    Called when the user clicks 'Book' on a flight card in the UI.
    Creates the booking via AeroCRS, then injects a system message into
    the bot's conversation thread so the bot knows to check ancillaries
    and collect passenger details.
    """
    print(f"\n[BOOKING REQUEST] Flight: {request.flight_id} | Fare: {request.fare_id}")

    payload = {
        "aerocrs": {
            "parms": {
                "triptype": request.trip_type,
                "adults": request.adults,
                "child": request.child,
                "infant": request.infant,
                "bookflight": [
                    {
                        "fromcode": request.from_code,
                        "tocode": request.to_code,
                        "flightid": request.flight_id,
                        "fareid": request.fare_id
                    }
                ]
            }
        }
    }

    try:
        r = requests.post(f"{BASE_URL}/createBooking", headers=_get_headers(), json=payload)
        booking_response = r.json()
        print(f"[BOOKING RESPONSE] {booking_response}")


        try:
            flights_in_response = (
                booking_response.get("aerocrs", {})
                                .get("booking", {})
                                .get("items", {})
                                .get("flight", [])
            )
            for f in flights_in_response:
                if f.get("error"):
                    raise HTTPException(status_code=400, detail=f["error"])
        except HTTPException:
            raise
        except Exception:
            pass

        try:
            booking_info = booking_response.get("aerocrs", {}).get("booking", {})
            booking_id = booking_info.get("bookingid")
            pnr = booking_info.get("pnrref") or booking_info.get("PNR", "N/A")
        except Exception:
            booking_id = None
            pnr = "N/A"

        return {
            **booking_response,
            "_meta": {
                "booking_id": booking_id,
                "flight_id": request.flight_id,
                "pnr": pnr,
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"[BOOKING ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)