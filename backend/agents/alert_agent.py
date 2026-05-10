from typing import Any


class AlertAgent:
    """Executes reminder planning from deadlines and timeline state."""

    async def run(self, briefing: dict[str, Any]) -> dict[str, Any]:
        reminders = briefing.get("reminders") or []
        existing = {item.get("message") for item in reminders if isinstance(item, dict)}

        for deadline in briefing.get("deadlines", [])[:6]:
            label = deadline.get("label") or "Upcoming deadline"
            time = deadline.get("time") or ""
            message = f"{label}: {time}".strip(": ")
            if message not in existing:
                reminders.append(
                    {
                        "message": message,
                        "priority": deadline.get("priority", "high"),
                        "scheduled_for": time,
                    }
                )
                existing.add(message)

        if not reminders and briefing.get("timeline"):
            first = briefing["timeline"][0]
            reminders.append(
                {
                    "message": f"Review upcoming event timing: {first.get('time', '')}",
                    "priority": "medium",
                    "scheduled_for": first.get("time", ""),
                }
            )

        briefing["reminders"] = reminders[:8]
        return briefing
