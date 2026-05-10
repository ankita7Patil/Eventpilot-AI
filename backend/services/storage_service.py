from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException


class StorageService:
    """Supabase-backed storage with in-memory fallback for local hackathon demos."""

    def __init__(self) -> None:
        self.mode = "memory"
        self._events: dict[str, dict[str, Any]] = {}
        self._client = None
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        if url and key:
            try:
                from supabase import create_client

                self._client = create_client(url, key)
                self.mode = "supabase"
            except Exception:
                self._client = None
                self.mode = "memory"

    async def save_event(self, event: dict[str, Any]) -> dict[str, Any]:
        event_id = event.get("id") or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        event = {**event, "id": event_id, "updated_at": now, "created_at": event.get("created_at", now)}
        self._events[event_id] = event

        if self._client:
            self._save_supabase(event)
        return event

    async def get_event(self, event_id: str) -> dict[str, Any]:
        if event_id in self._events:
            return self._events[event_id]
        if self._client:
            result = self._client.table("events").select("*").eq("id", event_id).limit(1).execute()
            if result.data:
                row = result.data[0]
                event = {
                    "id": row["id"],
                    "user_id": row.get("user_id"),
                    "source_url": row.get("source_url"),
                    "title": row.get("title"),
                    "briefing": row.get("briefing") or {},
                    "scraped": row.get("scraped") or {},
                    "activities": row.get("activities") or [],
                    "alerts": row.get("alerts") or [],
                }
                self._events[event_id] = event
                return event
        raise HTTPException(status_code=404, detail="Event not found")

    async def latest_event(self, user_id: str | None) -> dict[str, Any] | None:
        events = list(self._events.values())
        if user_id:
            events = [event for event in events if event.get("user_id") == user_id]
        events.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return events[0] if events else None

    def _save_supabase(self, event: dict[str, Any]) -> None:
        row = {
            "id": event["id"],
            "user_id": event.get("user_id"),
            "source_url": event.get("source_url"),
            "title": event.get("title"),
            "event_type": event.get("scraped", {}).get("platform"),
            "summary": event.get("briefing", {}).get("summary"),
            "urgency": event.get("briefing", {}).get("urgency"),
            "briefing": event.get("briefing", {}),
            "scraped": event.get("scraped", {}),
            "activities": event.get("activities", []),
            "alerts": event.get("alerts", []),
            "updated_at": event["updated_at"],
        }
        self._client.table("events").upsert(row).execute()

        for activity in event.get("activities", []):
            self._client.table("activity_logs").insert(
                {
                    "event_id": event["id"],
                    "agent_name": activity.get("agent_name"),
                    "action": activity.get("action"),
                    "status": activity.get("status"),
                    "details": activity.get("details", {}),
                }
            ).execute()

        for reminder in event.get("briefing", {}).get("reminders", []):
            self._client.table("reminders").insert(
                {
                    "event_id": event["id"],
                    "message": reminder.get("message"),
                    "priority": reminder.get("priority", "medium"),
                    "scheduled_for_text": reminder.get("scheduled_for"),
                }
            ).execute()
