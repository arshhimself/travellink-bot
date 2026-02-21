# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Frontend (Next.js) — run from `frontend/`
```bash
npm run dev      # Dev server on port 3000
npm run build    # Production build
npm start        # Start production server
npm run lint     # ESLint
```

### Backend (FastAPI) — run from `backend/`
```bash
python app.py                     # Start API server
uvicorn app:app --reload          # Start with hot reload (port 8000)
pip install -r requirements.txt   # Install dependencies
```

## Architecture Overview

TravelLink is an AI-powered conversational flight booking app. The backend is a LangGraph agent served via FastAPI; the frontend is a single-page Next.js chat interface.

### Backend (`backend/`)

**`app.py`** — FastAPI server. Exposes REST endpoints (`/chat`, `/book-flight`) used by the frontend. Handles thread/session management and integrates with the AeroCRS flight API.

**`bot.py`** — LangGraph agent using OpenAI GPT-4o. The conversation is a graph with two nodes: a `Conversation` node (LLM) and a `Tool` node. State is persisted per thread via `MemorySaver`.

Five tools available to the agent:
1. `search_destinations` — Validate city names and resolve IATA codes via AeroCRS
2. `check_flight_availability` — Query available flights
3. `check_ancillaries` — Query available add-ons (baggage, meals, seats)
4. `add_ancillary` — Attach extras to a booking
5. `confirm_booking` — Finalize booking with passenger details

**Conversation phases:** (1) gather origin/destination/date/passengers, (2) display flights, (3) booking + ancillaries, (4) collect passenger info + confirm.

**Special protocol:** A message prefixed with `"__booking__:"` signals the agent to start the ancillaries phase after a flight is selected from the frontend. Booking metadata is returned as `_meta.booking_id`, `_meta.pnr`, `_meta.flight_id` in tool responses.

**Token management:** The backend trims flight JSON from message history, keeps the last 30 messages, and validates tool_call/ToolMessage pairings before sending to OpenAI to avoid API errors.

### Frontend (`frontend/src/app/`)

**`page.tsx`** — The entire UI is one large React component. It renders:
- A chat messages area with user/assistant bubbles
- `FlightResults` / `FlightCard` components to display flight options returned by the backend
- A `ClassModal` for fare class selection
- A `ToastContainer` for notifications (Framer Motion animated, auto-dismiss 4.5s)

**Data flow:**
1. User message → `POST /chat` with `thread_id: "user-session-1"` → LLM response + optional flight JSON
2. Frontend parses response; if flight data present, renders interactive `FlightCard` components
3. User selects flight → `ClassModal` opens → user picks fare class → `POST /book-flight`
4. Backend returns booking ID/PNR; frontend sends `__booking__:` prefixed message to trigger ancillaries phase
5. Agent collects passenger details and calls `confirm_booking`

## Tech Stack

| Layer | Technology |
|---|---|
| LLM | OpenAI GPT-4o via `langchain-openai` |
| Agent orchestration | LangGraph 0.2, LangChain 0.2 |
| Backend API | FastAPI + Uvicorn |
| Flight data | AeroCRS v5 REST API |
| Observability | LangSmith (enabled via `.env`) |
| Frontend framework | Next.js 16 / React 19 |
| Language | TypeScript 5 (strict mode) |
| Styling | Tailwind CSS v4 |
| Animations | Framer Motion 12 |
| HTTP client | Axios |
| Fuzzy matching | `thefuzz` (city name resolution, threshold 60%) |
| Date parsing | `dateparser` (natural language dates) |

## Environment Variables (`backend/.env`)

```
OPENAI_API_KEY=...
AUTHID=...               # AeroCRS auth ID
AUTHPASSSWORD=...        # AeroCRS password
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=...
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=...
```

## Key Implementation Notes

- **Thread ID** is hardcoded as `"user-session-1"` in the frontend; all state is scoped to this thread via LangGraph's `MemorySaver`.
- **City fuzzy matching** uses `thefuzz.fuzz.partial_ratio()` with a minimum score of 60; lower scores return "did you mean?" suggestions.
- **Date handling** supports natural language ("next Friday", "tomorrow") via `dateparser`; past dates are auto-incremented by one year.
- **Import alias** `@/*` maps to `frontend/src/*` in TypeScript.
- The `langchain-anthropic` package is listed in `requirements.txt` but not currently used — the active LLM is OpenAI GPT-4o.
