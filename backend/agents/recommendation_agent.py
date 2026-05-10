from typing import Any

from models import ScrapedEvent


class RecommendationAgent:
    """Decides the highest-value preparation and project strategy."""

    async def run(self, scraped: ScrapedEvent, briefing: dict[str, Any]) -> dict[str, Any]:
        recommendations = briefing.get("recommendations") or []
        if not recommendations:
            signals = len(scraped.sponsor_tracks) + len(scraped.prizes) + len(scraped.deadlines)
            recommendations = [
                {
                    "name": "Focus on the strongest extracted opportunity signal",
                    "score": min(95, 65 + signals * 4),
                    "reason": "EventPilot found real page signals that can drive a concrete action plan.",
                }
            ]

        if scraped.sponsor_tracks:
            recommendations.insert(
                0,
                {
                    "name": "Map your project to a detected sponsor track",
                    "score": 92,
                    "reason": f"Detected track signals include: {', '.join(scraped.sponsor_tracks[:3])}.",
                },
            )

        briefing["recommendations"] = recommendations[:6]
        return briefing
