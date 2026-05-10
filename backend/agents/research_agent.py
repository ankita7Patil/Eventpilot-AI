from typing import Any

from models import ScrapedEvent
from services.llm_service import LLMService


class ResearchAgent:
    """Researches scraped opportunity content and creates an AI briefing."""

    def __init__(self, llm: LLMService) -> None:
        self.llm = llm

    async def run(self, scraped: ScrapedEvent, user_goal: str | None) -> dict[str, Any]:
        briefing = await self.llm.generate_briefing(scraped, user_goal)
        briefing["title"] = briefing.get("title") or scraped.title
        briefing["raw_extracted"] = {
            "platform": scraped.platform,
            "source": scraped.source,
            "dates": scraped.dates,
            "deadlines": scraped.deadlines,
            "sponsor_tracks": scraped.sponsor_tracks,
            "prizes": scraped.prizes,
            "mentorship_timings": scraped.mentorship_timings,
            "links": scraped.links,
        }
        return briefing
