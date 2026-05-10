from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class EventAnalyzeRequest(BaseModel):
    url: HttpUrl
    user_id: str | None = "demo-user"
    user_goal: str | None = None


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    event_id: str | None = None
    user_id: str | None = "demo-user"


class ScrapedEvent(BaseModel):
    url: str
    source: str
    platform: str
    title: str
    description: str
    raw_text: str
    dates: list[str] = []
    deadlines: list[str] = []
    sponsor_tracks: list[str] = []
    prizes: list[str] = []
    mentorship_timings: list[str] = []
    links: list[str] = []
    metadata: dict[str, Any] = {}


class AgentActivity(BaseModel):
    agent_name: str
    action: str
    status: str = "completed"
    details: dict[str, Any] = {}


class EventBriefing(BaseModel):
    title: str
    summary: str
    urgency: str
    facts: list[dict[str, str]]
    preparation_checklist: list[str]
    deadlines: list[dict[str, str]]
    timeline: list[dict[str, str]]
    sponsor_tracks: list[str]
    recommendations: list[dict[str, Any]]
    project_suggestions: list[dict[str, str]]
    reminders: list[dict[str, str]]
    raw_extracted: dict[str, Any]
