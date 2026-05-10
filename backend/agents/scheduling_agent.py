from typing import Any

from models import ScrapedEvent


class SchedulingAgent:
    """Turns extracted dates and deadlines into timeline-ready workflow state."""

    async def run(self, scraped: ScrapedEvent, briefing: dict[str, Any]) -> dict[str, Any]:
        timeline = briefing.get("timeline") or []
        seen = {self._key(item) for item in timeline if isinstance(item, dict)}
        date_contexts = scraped.metadata.get("date_contexts", [])

        for deadline in scraped.deadlines[:8]:
            time = self._best_time(deadline)
            if not time:
                continue
            item = {
                "time": time,
                "title": self._title_from_text(deadline, "Deadline signal"),
                "detail": deadline,
            }
            key = self._key(item)
            if key not in seen:
                timeline.append(item)
                seen.add(key)

        for context in date_contexts[:16]:
            item = {
                "time": context.get("time", ""),
                "title": context.get("title", "Event timing"),
                "detail": context.get("detail", "Extracted from the event page."),
            }
            key = self._key(item)
            if item["time"] and key not in seen:
                timeline.append(item)
                seen.add(key)

        for date in scraped.dates[:8]:
            if any(date.lower() == item.get("time", "").lower() for item in timeline):
                continue
            item = {"time": date, "title": "Event timing", "detail": "Detected on the event page. Review the original page for exact context."}
            key = self._key(item)
            if key not in seen:
                timeline.append(item)
                seen.add(key)

        briefing["timeline"] = self._dedupe(timeline)[:12]
        return briefing

    def _key(self, item: dict[str, Any]) -> str:
        return "::".join(
            str(item.get(field, "")).lower().strip()
            for field in ("time", "title", "detail")
        )

    def _dedupe(self, timeline: list[dict[str, Any]]) -> list[dict[str, Any]]:
        best: dict[str, dict[str, Any]] = {}
        order = []
        for item in timeline:
            key = "::".join(
                str(item.get(field, "")).lower().strip()
                for field in ("time", "title")
            )
            if key not in best:
                best[key] = item
                order.append(key)
                continue
            current_detail = str(best[key].get("detail", ""))
            new_detail = str(item.get("detail", ""))
            if len(new_detail) < len(current_detail) or "deadline" in new_detail.lower():
                best[key] = item
        return [best[key] for key in order]

    def _best_time(self, text: str) -> str:
        for context in re_find_dates(text):
            return context
        return ""

    def _title_from_text(self, text: str, fallback: str) -> str:
        lowered = text.lower()
        if "submission" in lowered or "submit" in lowered:
            return "Submission deadline"
        if "mentor" in lowered:
            return "Mentorship session"
        if "start" in lowered or "begin" in lowered:
            return "Event starts"
        if "end" in lowered or "close" in lowered:
            return "Event ends"
        return fallback


def re_find_dates(text: str) -> list[str]:
    import re

    patterns = [
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:,?\s+\d{4})?",
        r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*(?:UTC|IST|GMT|PST|EST)?\b",
    ]
    matches: list[str] = []
    for pattern in patterns:
        matches.extend(re.findall(pattern, text))
    return matches
