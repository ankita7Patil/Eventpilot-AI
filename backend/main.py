
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import ChatRequest, EventAnalyzeRequest
from services.orchestrator import AgentOrchestrator
from services.storage_service import StorageService
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env with explicit path FIRST before anything else
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Verify key loaded
print("🔑 GEMINI KEY LOADED:", bool(os.getenv("GEMINI_API_KEY")))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, EventAnalyzeRequest
from services.orchestrator import AgentOrchestrator
from services.storage_service import StorageService

app = FastAPI(
    title="EventPilot AI API",
    version="1.0.0",
    description="Autonomous opportunity intelligence agent platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

storage = StorageService()
orchestrator = AgentOrchestrator(storage=storage)


@app.get("/api/health")
async def health() -> dict:
    return {
        "status": "ok",
        "service": "eventpilot-ai",
        "storage": storage.mode,
        "workflow": "monitor -> research -> recommendation -> scheduling -> alert",
    }


@app.post("/api/events/analyze")
async def analyze_event(payload: EventAnalyzeRequest) -> dict:
    return await orchestrator.analyze_event(payload)


@app.get("/api/events/{event_id}")
async def get_event(event_id: str) -> dict:
    return await storage.get_event(event_id)


@app.post("/api/chat")
async def chat(payload: ChatRequest) -> dict:
    return await orchestrator.chat(payload)
