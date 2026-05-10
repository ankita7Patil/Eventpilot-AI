# EventPilot AI

EventPilot AI is an autonomous opportunity intelligence platform for students and developers who register for hackathons, internships, fellowships, competitions, bootcamps, and technical events.

It is not a chatbot. A user pastes an event URL, then EventPilot runs a real multi-agent workflow:

```txt
URL -> Scraper -> Monitor Agent -> Research Agent -> Recommendation Agent -> Scheduling Agent -> Alert Agent -> Dashboard + Chat
```

The system researches the page, decides what matters, stores the event, creates reminders, recommends strategy, and answers questions from tracked event context.

## Bot-a-thon Alignment

Bot-a-thon asks for AI agents beyond chat interfaces: agents that research, decide, and execute. EventPilot demonstrates that flow directly.

- Research: scraper extracts real page content from Luma, Devfolio, Unstop, and generic opportunity pages.
- Decision: AI service creates urgency, preparation checklists, strategy, project suggestions, and recommendations.
- Execution: workflow stores the event, creates timeline items, logs agent actions, and plans reminders.
- Proactive behavior: alerts and activity logs are created immediately after analysis, before the user asks.

## Sponsor Track Alignment

### Zynd AI / Zendia

EventPilot is structured as a multi-agent network with shared event state:

- `Monitor Agent`
- `Research Agent`
- `Recommendation Agent`
- `Scheduling Agent`
- `Alert Agent`

The architecture is Zynd AI compatible because each agent has a clear role, shared state, and workflow handoff boundaries.

### MCP

The LLM layer is MCP-ready:

- `backend/services/llm_service.py`
- Prompt routes: `eventpilot.briefing.v1` and `eventpilot.chat.v1`
- Swappable providers through environment variables
- Gemini and OpenAI support

### Superplane

The orchestrator implements a sequential workflow:

```txt
monitor -> research -> recommendation -> scheduling -> alert
```

See `backend/services/orchestrator.py`. It coordinates shared event state, logs agent activity, and persists results.

### Apify

The current MVP uses real `httpx` + `BeautifulSoup` scraping so it works without paid infrastructure. The service is isolated in `backend/services/scraper_service.py`, so an Apify actor can be added behind the same scraper interface with `APIFY_TOKEN` and `APIFY_ACTOR_ID`.

### GitHub Copilot

This project is organized for professional development with reusable services, typed models, modular agents, deployment config, and clean API boundaries. GitHub Copilot accelerated development by helping generate repetitive scaffolding, route wiring, typed response structures, and README/deployment documentation while the architecture stayed human-directed.

## Features

- Real event URL analysis
- Real page scraping
- AI briefing generation with Gemini or OpenAI
- Extractive fallback when no LLM key is configured
- Supabase persistence
- Agent activity logging
- Timeline and reminder planning
- Backend-powered chat using tracked event context
- Vercel frontend and Render backend deployment setup

## Project Structure

```txt
eventpilot-ai/
  frontend/
    index.html
    styles.css
    app.js
    config.example.js
  backend/
    main.py
    models.py
    requirements.txt
    agents/
      monitor_agent.py
      research_agent.py
      recommendation_agent.py
      scheduling_agent.py
      alert_agent.py
    services/
      scraper_service.py
      llm_service.py
      storage_service.py
      orchestrator.py
  supabase/
    schema.sql
  Dockerfile
  render.yaml
  vercel.json
  .env.example
```

## Local Setup

### Backend

```bash
cd eventpilot-ai/backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Health check:

```txt
http://127.0.0.1:8000/api/health
```

### Frontend

Open:

```txt
eventpilot-ai/frontend/index.html
```

By default the frontend calls:

```txt
http://127.0.0.1:8000
```

For a deployed backend, set this in the browser console:

```js
localStorage.setItem("EVENTPILOT_API_URL", "https://your-render-service.onrender.com");
```

## Environment Variables

Copy `.env.example` and configure:

```txt
LLM_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-1.5-flash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
APIFY_TOKEN=
APIFY_ACTOR_ID=
TELEGRAM_BOT_TOKEN=
```

If no LLM key is configured, EventPilot still performs real scraping and creates a dynamic extractive briefing from the page content.

## Supabase

Run `supabase/schema.sql` in the Supabase SQL editor. The app stores:

- events
- timelines
- reminders
- AI briefings
- activity logs
- alerts

For local demos without Supabase env vars, the backend uses in-memory storage.

## Required API

- `GET /api/health`
- `POST /api/events/analyze`
- `GET /api/events/{id}`
- `POST /api/chat`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/events/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"url\":\"https://your-event-page.example\",\"user_goal\":\"Prepare for this opportunity\"}"
```

## Deployment

### Backend on Render

Use `render.yaml` or configure manually:

```txt
Build command: pip install -r requirements.txt
Start command: uvicorn main:app --host 0.0.0.0 --port $PORT
Root directory: backend
```

### Frontend on Vercel

Deploy the repository with `vercel.json`. Set the backend URL with:

```js
localStorage.setItem("EVENTPILOT_API_URL", "https://your-render-service.onrender.com");
```

## Demo Flow

1. Start the FastAPI backend.
2. Open the frontend.
3. Paste a public event URL.
4. Click `Analyze`.
5. Show the agent activity feed.
6. Show the AI briefing, timeline, reminders, and strategy panel.
7. Ask the chat agent: `What is urgent and what should I prepare?`

Closing line:

```txt
EventPilot AI acts before the user asks.
```
