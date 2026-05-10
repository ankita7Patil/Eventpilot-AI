from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

from models import ScrapedEvent

load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env")


class LLMService:
    """MCP-ready prompt router with Groq (free), Gemini, and OpenAI support."""

    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.openai_key = os.getenv("OPENAI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        self.openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.groq_model = "llama-3.1-8b-instant"

        key_available = bool(self.groq_key or self.gemini_key or self.openai_key)
        print(f"🤖 LLMService init — provider: {self.provider}, key: {key_available}")

    # ──────────────────────────────────────────────
    # PUBLIC METHODS
    # ──────────────────────────────────────────────

    async def generate_briefing(self, scraped, user_goal=None) -> dict:
        print(f"🔍 generate_briefing called — provider: {self.provider}")
        prompt = self._briefing_prompt(scraped, user_goal)
        data = await self._complete_json(prompt)
        if data:
            print("✅ AI briefing received!")
            return data
        print("⚠️ AI failed — using extractive fallback")
        return self._extractive_briefing(scraped)

    async def answer_chat(self, message: str, event: dict | None) -> str:
        lowered = message.lower().strip()
        greetings = {"hi", "hello", "hey", "hii", "namaste"}

        if lowered in greetings:
            return self._extractive_answer(message, event)

        if not event:
            return "Add and analyze an event link first, then I can help you with deadlines, tracks, and preparation!"

        print(f"🚀 Sending to AI: {message[:50]}")
        prompt = self._chat_prompt(message, event)
        text = await self._complete_text(prompt)
        print(f"✅ AI replied: {str(text)[:100]}")

        if text:
            return text.strip()

        return self._extractive_answer(message, event)

    # ──────────────────────────────────────────────
    # INTERNAL ROUTING
    # ──────────────────────────────────────────────

    async def _complete_json(self, prompt: str) -> dict[str, Any] | None:
        text = await self._complete_text(prompt)
        if not text:
            return None
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    async def _complete_text(self, prompt: str) -> str:
        if self.provider == "groq" and self.groq_key:
            return await self._groq(prompt)
        if self.provider == "openai" and self.openai_key:
            return await self._openai(prompt)
        if self.gemini_key:
            return await self._gemini(prompt)
        return ""

    # ──────────────────────────────────────────────
    # GROQ (FREE — PRIMARY)
    # ──────────────────────────────────────────────

    async def _groq(self, prompt: str) -> str:
        payload = {
            "model": self.groq_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are EventPilot AI, an autonomous event intelligence agent. Always respond with valid JSON when asked.",
                },
                {"role": "user", "content": prompt},
            ],
            "max_tokens": 1500,
            "temperature": 0.3,
        }
        headers = {
            "Authorization": f"Bearer {self.groq_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=35) as client:
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                print("Groq Status:", response.status_code)
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print("GROQ ERROR:", str(e))
                return ""

    # ──────────────────────────────────────────────
    # GEMINI (FALLBACK)
    # ──────────────────────────────────────────────

    async def _gemini(self, prompt: str) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.gemini_model}:generateContent?key={self.gemini_key}"
        )
        payload = {"contents": [{"parts": [{"text": prompt}]}]}
        async with httpx.AsyncClient(timeout=35) as client:
            try:
                response = await client.post(url, json=payload)
                print("Gemini Status:", response.status_code)
                response.raise_for_status()
                return response.json()["candidates"][0]["content"]["parts"][0].get("text", "")
            except Exception as e:
                print("GEMINI ERROR:", str(e))
                return ""

    # ──────────────────────────────────────────────
    # OPENAI (FALLBACK)
    # ──────────────────────────────────────────────

    async def _openai(self, prompt: str) -> str:
        payload = {
            "model": self.openai_model,
            "messages": [
                {"role": "system", "content": "You are EventPilot AI, an autonomous opportunity intelligence agent."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.25,
        }
        headers = {"Authorization": f"Bearer {self.openai_key}"}
        async with httpx.AsyncClient(timeout=35) as client:
            try:
                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()["choices"][0]["message"]["content"]
            except Exception as e:
                print("OPENAI ERROR:", str(e))
                return ""

    # ──────────────────────────────────────────────
    # PROMPTS
    # ──────────────────────────────────────────────

    def _briefing_prompt(self, scraped, user_goal=None) -> str:
        has_content = len(scraped.raw_text.strip()) > 100

        if has_content:
            content_section = f"Scraped page text:\n{scraped.raw_text[:6000]}"
        else:
            content_section = (
                f"The page at {scraped.url} could not be scraped (JavaScript-rendered site). "
                f"Use your knowledge about this URL/event to fill in details. "
                f"If unknown, write 'Check event page' for dates/deadlines."
            )

        return f"""You are EventPilot AI — autonomous event intelligence agent.
Extract or infer ALL details about this event.

URL: {scraped.url}
Platform: {scraped.platform}
{content_section}

User goal: {user_goal or "Help user track this event and never miss deadlines."}

Return ONLY valid JSON, no markdown, no explanation:
{{
  "title": "event name",
  "summary": "2-3 line summary of what this event is",
  "urgency": "low|medium|high|critical",
  "facts": [
    {{"label": "Start Date", "value": "date or Check event page"}},
    {{"label": "End Date", "value": "date or Check event page"}},
    {{"label": "Platform", "value": "{scraped.platform}"}},
    {{"label": "Source", "value": "{scraped.source}"}}
  ],
  "preparation_checklist": ["action 1", "action 2", "action 3"],
  "deadlines": [
    {{"label": "Submission deadline", "time": "exact date if found else Check event page", "priority": "critical"}}
  ],
  "timeline": [
    {{"time": "date or time", "title": "what happens", "detail": "details"}}
  ],
  "sponsor_tracks": ["track 1", "track 2"],
  "recommendations": [
    {{"name": "top strategy", "score": 85, "reason": "why this strategy works"}}
  ],
  "project_suggestions": [
    {{"name": "project idea name", "why": "why this fits", "stack": "recommended tech stack"}}
  ],
  "reminders": [
    {{"message": "reminder text", "priority": "high", "scheduled_for": "date or time"}}
  ]
}}"""

    def _chat_prompt(self, message: str, event: dict[str, Any] | None) -> str:
        briefing = (event or {}).get("briefing", {})
        return f"""You are EventPilot AI. Answer the user's question in plain conversational English.
    DO NOT return JSON. Just answer directly in 2-3 sentences.

    Event: {(event or {}).get("title", "Unknown")}
    Deadlines: {briefing.get("deadlines", [])}
    Timeline: {briefing.get("timeline", [])}
    Checklist: {briefing.get("preparation_checklist", [])}
    Tracks: {briefing.get("sponsor_tracks", [])}

    User asked: {message}

    Answer in plain English only:"""
    

    # ──────────────────────────────────────────────
    # EXTRACTIVE FALLBACK
    # ──────────────────────────────────────────────

    def _extractive_briefing(self, scraped: ScrapedEvent) -> dict[str, Any]:
        date_contexts = scraped.metadata.get("date_contexts", [])
        important_actions = scraped.metadata.get("important_actions", [])
        deadlines = self._deadline_items(scraped.deadlines, date_contexts)
        timeline = [
            {"time": item.get("time", ""), "title": item.get("title", "Event timing"), "detail": item.get("detail", "")}
            for item in date_contexts[:10]
        ] or [
            {"time": date, "title": "Event timing", "detail": "Check the original event page for context."}
            for date in scraped.dates[:8]
        ]

        tracks = scraped.sponsor_tracks[:8]
        prizes = scraped.prizes[:4]
        mentorship = scraped.mentorship_timings[:4]

        facts = [
            {"label": "Platform", "value": scraped.platform},
            {"label": "Source", "value": scraped.source},
            {"label": "Extracted links", "value": str(len(scraped.links))},
            {"label": "Detected dates", "value": str(len(scraped.dates))},
        ]
        if tracks:
            facts.append({"label": "Detected tracks", "value": "; ".join(tracks[:3])})
        if prizes:
            facts.append({"label": "Prize/resources", "value": "; ".join(prizes[:2])})
        if mentorship:
            facts.append({"label": "Mentorship", "value": "; ".join(mentorship[:2])})

        urgency = "high" if deadlines or scraped.dates else "medium"
        checklist = self._preparation_checklist(scraped, deadlines, important_actions)

        return {
            "summary": scraped.description or scraped.raw_text[:420],
            "urgency": urgency,
            "facts": facts,
            "preparation_checklist": checklist,
            "deadlines": deadlines,
            "timeline": timeline,
            "sponsor_tracks": tracks,
            "recommendations": [{"name": self._recommendation_name(scraped), "score": 85, "reason": self._recommendation_reason(scraped, deadlines, tracks)}],
            "project_suggestions": [{"name": self._project_suggestion_name(scraped), "why": self._project_suggestion_why(scraped), "stack": "FastAPI, Groq AI, scraper, Vercel/Render"}],
            "reminders": [{"message": item["label"], "priority": item["priority"], "scheduled_for": item["time"]} for item in deadlines[:5]],
        }

    def _deadline_items(self, deadline_lines, date_contexts):
        items = []
        seen = set()
        for line in sorted(deadline_lines, key=len):
            date = self._first_date(line)
            label = self._short_label(line)
            key = (date or label).lower()
            if key not in seen:
                items.append({"label": label, "time": date or "Check event page", "priority": "critical" if "deadline" in line.lower() else "high"})
                seen.add(key)
        for context in date_contexts:
            text = f"{context.get('title', '')} {context.get('detail', '')}".lower()
            if not any(w in text for w in ["deadline", "submit", "submission", "closes", "ends"]):
                continue
            label = self._short_label(context.get("detail", context.get("title", "Deadline")))
            date = context.get("time", "")
            key = (date or label).lower()
            if key not in seen:
                items.append({"label": label, "time": date or "Check event page", "priority": "critical"})
                seen.add(key)
        return items[:6]

    def _preparation_checklist(self, scraped, deadlines, important_actions):
        checklist = []
        if deadlines:
            first = deadlines[0]
            checklist.append(f"Submit before {first['time']}: {first['label']}")
        if scraped.sponsor_tracks:
            checklist.append(f"Pick the best matching track: {scraped.sponsor_tracks[0]}")
        if scraped.prizes:
            checklist.append(f"Optimize your demo for: {scraped.prizes[0]}")
        for action in important_actions:
            if len(checklist) >= 6:
                break
            short = self._short_label(action, limit=150)
            if short and short not in checklist:
                checklist.append(short)
        if not checklist:
            checklist = ["Read eligibility and rules from the original event page.", "Identify the submission deadline.", "Choose one track that best matches your skills."]
        return checklist[:6]

    def _recommendation_name(self, scraped):
        if scraped.sponsor_tracks:
            return "Build around the strongest detected track"
        if scraped.deadlines:
            return "Prioritize submission readiness"
        return "Turn the opportunity page into an action plan"

    def _recommendation_reason(self, scraped, deadlines, tracks):
        parts = []
        if deadlines:
            parts.append(f"Deadline: {deadlines[0]['time']}")
        if tracks:
            parts.append(f"Track: {tracks[0]}")
        if scraped.prizes:
            parts.append(f"Prize: {scraped.prizes[0]}")
        return "; ".join(parts) or "The page has enough context to generate next actions."

    def _project_suggestion_name(self, scraped):
        text = " ".join(scraped.sponsor_tracks + scraped.description.split()[:30]).lower()
        if "agent" in text or "workflow" in text:
            return "Autonomous workflow agent"
        if "fine-tuning" in text:
            return "Domain-tuned assistant"
        return "Opportunity-specific AI assistant"

    def _project_suggestion_why(self, scraped):
        if scraped.sponsor_tracks:
            return f"Maps to detected track: {scraped.sponsor_tracks[0]}"
        return "Converts event requirements into a concrete, demo-friendly workflow."

    def _first_date(self, text):
        for pattern in [
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–—]\s*\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s+\d{4})?",
            r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*(?:UTC|IST|GMT|PST|EST)?\b",
        ]:
            m = re.search(pattern, text)
            if m:
                return m.group(0)
        return ""

    def _short_label(self, text, limit=110):
        return re.sub(r"\s+", " ", text).strip(" -|")[:limit]

    def _extractive_answer(self, message, event):
        lowered = message.lower().strip()
        if lowered in {"hi", "hello", "hey", "hii", "namaste"}:
            if event:
                return f"Hi! I am tracking {event.get('title', 'this event')}. Ask me about deadlines, timeline, tracks, or preparation."
            return "Hi! Paste and analyze an event link first."
        if not event:
            return "Add and analyze an event link first."

        briefing = event.get("briefing", {})
        if "deadline" in lowered or "urgent" in lowered:
            deadlines = briefing.get("deadlines", [])
            if deadlines:
                return "Most urgent deadlines: " + "; ".join(item.get("time", item.get("label", "")) for item in deadlines[:3])
        if any(w in lowered for w in ["prepare", "submit", "what", "kya"]):
            checklist = briefing.get("preparation_checklist", [])
            if checklist:
                return "You should: " + "; ".join(checklist[:4])
        if "track" in lowered or "sponsor" in lowered:
            tracks = briefing.get("sponsor_tracks", [])
            if tracks:
                return "Detected tracks: " + "; ".join(tracks[:5])
        return briefing.get("summary", "Analyze an event first for detailed answers.")

    def _answer_for_requested_date(self, message, briefing):
        requested = self._date_tokens(message)
        if not requested:
            return ""
        matches = []
        for item in briefing.get("timeline", []):
            searchable = f"{item.get('time','')} {item.get('title','')} {item.get('detail','')}".lower()
            if any(t in searchable for t in requested):
                matches.append(item)
        if not matches:
            return "I could not find a tracked action for that date."
        parts = []
        seen = set()
        for item in matches[:5]:
            key = str(item.get("detail") or item.get("title") or item.get("time")).lower()
            if key not in seen:
                seen.add(key)
                parts.append(f"{item.get('time','That date')}: {item.get('title','Event action')} - {item.get('detail','')}")
        return "For that date: " + " | ".join(parts)

    def _date_tokens(self, message):
        lowered = message.lower()
        tokens = []
        tokens.extend(m.group(0) for m in re.finditer(r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}", lowered))
        tokens.extend(re.findall(r"\b\d{1,2}[:/.-]\d{1,2}(?:[:/.-]\d{2,4})?\b", lowered))
        tokens.extend(re.findall(r"\b(?:date|day|may|on|ko)\s+(\d{1,2})\b", lowered))
        return list(dict.fromkeys(t.strip() for t in tokens if t.strip()))