from __future__ import annotations

from typing import Any

from models import AgentActivity, ChatRequest, EventAnalyzeRequest
from agents.alert_agent import AlertAgent
from agents.monitor_agent import MonitorAgent
from agents.recommendation_agent import RecommendationAgent
from agents.research_agent import ResearchAgent
from agents.scheduling_agent import SchedulingAgent
from services.llm_service import LLMService
from services.scraper_service import ScraperService
from services.storage_service import StorageService


class AgentOrchestrator:
    """Superplane-style sequential workflow coordinator with shared event state."""

    def __init__(self, storage: StorageService) -> None:
        self.storage = storage
        self.scraper = ScraperService()
        self.llm = LLMService()
        self.monitor_agent = MonitorAgent(self.scraper)
        self.research_agent = ResearchAgent(self.llm)
        self.recommendation_agent = RecommendationAgent()
        self.scheduling_agent = SchedulingAgent()
        self.alert_agent = AlertAgent()

    async def analyze_event(self, payload: EventAnalyzeRequest) -> dict[str, Any]:
        activities: list[AgentActivity] = []

        scraped = await self.monitor_agent.run(str(payload.url))
        activities.append(
            AgentActivity(
                agent_name="Monitor Agent",
                action="Fetched page and extracted real opportunity signals.",
                details={"platform": scraped.platform, "source": scraped.source, "dates_found": len(scraped.dates)},
            )
        )

        briefing = await self.research_agent.run(scraped, payload.user_goal)
        activities.append(
            AgentActivity(
                agent_name="Research Agent",
                action="Generated AI briefing from scraped content.",
                details={"urgency": briefing.get("urgency"), "facts": len(briefing.get("facts", []))},
            )
        )

        briefing = await self.recommendation_agent.run(scraped, briefing)
        activities.append(
            AgentActivity(
                agent_name="Recommendation Agent",
                action="Ranked strategies and project suggestions.",
                details={"recommendations": len(briefing.get("recommendations", []))},
            )
        )

        briefing = await self.scheduling_agent.run(scraped, briefing)
        activities.append(
            AgentActivity(
                agent_name="Scheduling Agent",
                action="Converted detected dates and deadlines into timeline items.",
                details={"timeline_items": len(briefing.get("timeline", []))},
            )
        )

        briefing = await self.alert_agent.run(briefing)
        activities.append(
            AgentActivity(
                agent_name="Alert Agent",
                action="Created proactive reminders from priority deadlines.",
                details={"reminders": len(briefing.get("reminders", []))},
            )
        )

        event = await self.storage.save_event(
            {
                "user_id": payload.user_id,
                "source_url": str(payload.url),
                "title": briefing.get("title") or scraped.title,
                "scraped": scraped.model_dump(),
                "briefing": briefing,
                "activities": [activity.model_dump() for activity in activities],
                "alerts": briefing.get("reminders", []),
            }
        )

        return event

    async def chat(self, payload: ChatRequest) -> dict[str, str]:
        event = None
        if payload.event_id:
            event = await self.storage.get_event(payload.event_id)
        else:
            event = await self.storage.latest_event(payload.user_id)
        answer = await self.llm.answer_chat(payload.message, event)
        return {"answer": answer, "event_id": event.get("id") if event else ""}
