from __future__ import annotations

import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from models import ScrapedEvent


class ScraperService:
    """Universal scraper with platform-specific handlers for Luma, Devfolio, Unstop, MLH, etc."""

    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }

    async def scrape(self, url: str) -> ScrapedEvent:
        platform = self._platform(url)

        # Try platform-specific scraper first
        if platform == "devfolio":
            return await self._scrape_devfolio(url)
        if platform == "unstop":
            return await self._scrape_unstop(url)
        if platform == "luma":
            return await self._scrape_luma(url)
        if platform == "mlh":
            return await self._scrape_generic(url)

        return await self._scrape_generic(url)

    # ─────────────────────────────────────────────
    # LUMA
    # ─────────────────────────────────────────────
    async def _scrape_luma(self, url: str) -> ScrapedEvent:
        """Try Luma API first, fallback to HTML scrape."""
        # Extract event slug from URL
        slug = url.rstrip("/").split("/")[-1]

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                api_resp = await client.get(
                    f"https://api.lu.ma/public/v1/event/get?url={slug}",
                    headers={"Accept": "application/json"},
                )
                if api_resp.status_code == 200:
                    data = api_resp.json().get("event", {})
                    title = data.get("name", "")
                    description = data.get("description", "")
                    start = data.get("start_at", "")
                    end = data.get("end_at", "")
                    dates = [d for d in [start, end] if d]
                    text = f"{title}\n{description}\nStart: {start}\nEnd: {end}"

                    return ScrapedEvent(
                        url=url,
                        source="lu.ma",
                        platform="luma",
                        title=title or url,
                        description=description[:500] or text[:420],
                        raw_text=text[:12000],
                        dates=dates,
                        deadlines=self._deadline_lines(text),
                        sponsor_tracks=self._track_lines(text),
                        prizes=self._extract_lines(text, ["prize", "winner", "cash", "swag", "credit"]),
                        mentorship_timings=self._extract_lines(text, ["mentor", "judge", "session"]),
                        links=[url],
                        metadata={
                            "status_code": 200,
                            "content_type": "application/json",
                            "text_length": len(text),
                            "date_contexts": self._date_contexts(text),
                            "important_actions": self._important_actions(text),
                        },
                    )
        except Exception as e:
            print(f"Luma API failed: {e} — falling back to HTML")

        return await self._scrape_generic(url)

    # ─────────────────────────────────────────────
    # DEVFOLIO
    # ─────────────────────────────────────────────
    async def _scrape_devfolio(self, url: str) -> ScrapedEvent:
        """Devfolio hackathon page scraper with API fallback."""
        # Extract slug: devfolio.co/hackathons/slug or devfolio.co/slug
        parts = url.rstrip("/").split("/")
        slug = parts[-1]

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                api_resp = await client.get(
                    f"https://devfolio.co/api/search/hackathons/{slug}",
                    headers={**self.HEADERS, "Accept": "application/json"},
                )
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    return self._parse_devfolio_api(url, data)
        except Exception as e:
            print(f"Devfolio API attempt 1 failed: {e}")

        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                api_resp = await client.get(
                    f"https://api.devfolio.co/api/hackathons/{slug}",
                    headers={**self.HEADERS, "Accept": "application/json"},
                )
                if api_resp.status_code == 200:
                    data = api_resp.json()
                    return self._parse_devfolio_api(url, data)
        except Exception as e:
            print(f"Devfolio API attempt 2 failed: {e}")

        # Final fallback — HTML with extra headers
        return await self._scrape_generic(url)

    def _parse_devfolio_api(self, url: str, data: dict) -> ScrapedEvent:
        title = data.get("name") or data.get("title") or "Devfolio Hackathon"
        description = data.get("description") or data.get("tagline") or ""
        start = data.get("starts_at") or data.get("start_date") or ""
        end = data.get("ends_at") or data.get("end_date") or ""
        submission_deadline = data.get("submission_deadline") or ""
        prizes_raw = data.get("prizes") or []
        prizes = [str(p) for p in prizes_raw[:6]] if prizes_raw else []

        dates = [d for d in [start, end, submission_deadline] if d]
        text = f"{title}\n{description}\nStart: {start}\nEnd: {end}\nSubmission: {submission_deadline}"

        return ScrapedEvent(
            url=url,
            source="devfolio.co",
            platform="devfolio",
            title=title,
            description=description[:500],
            raw_text=text[:12000],
            dates=dates,
            deadlines=([f"Submission deadline: {submission_deadline}"] if submission_deadline else
                       self._deadline_lines(text)),
            sponsor_tracks=self._track_lines(text),
            prizes=prizes or self._extract_lines(text, ["prize", "winner", "cash"]),
            mentorship_timings=self._extract_lines(text, ["mentor", "judge"]),
            links=[url],
            metadata={
                "status_code": 200,
                "content_type": "application/json",
                "text_length": len(text),
                "date_contexts": self._date_contexts(text),
                "important_actions": self._important_actions(text),
            },
        )

    # ─────────────────────────────────────────────
    # UNSTOP
    # ─────────────────────────────────────────────
    async def _scrape_unstop(self, url: str) -> ScrapedEvent:
        """Unstop scraper using their public API."""
        # Extract competition ID from URL: unstop.com/hackathons/name-123456
        match = re.search(r"-(\d+)$", url.rstrip("/"))
        comp_id = match.group(1) if match else None

        if comp_id:
            try:
                async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
                    api_resp = await client.get(
                        f"https://unstop.com/api/public/opportunity/view-more-detail?opportunity={comp_id}",
                        headers={**self.HEADERS, "Accept": "application/json"},
                    )
                    if api_resp.status_code == 200:
                        data = api_resp.json().get("data", {}).get("opportunity", {})
                        return self._parse_unstop_api(url, data)
            except Exception as e:
                print(f"Unstop API failed: {e}")

        return await self._scrape_generic(url)

    def _parse_unstop_api(self, url: str, data: dict) -> ScrapedEvent:
        title = data.get("title") or "Unstop Competition"
        description = data.get("description") or data.get("about") or ""
        start = data.get("start_date") or ""
        end = data.get("end_date") or ""
        reg_deadline = data.get("reg_last_date") or ""

        dates = [d for d in [start, end, reg_deadline] if d]
        text = f"{title}\n{description}\nStart: {start}\nEnd: {end}\nRegistration deadline: {reg_deadline}"

        deadlines = []
        if reg_deadline:
            deadlines.append(f"Registration deadline: {reg_deadline}")
        if end:
            deadlines.append(f"Competition ends: {end}")

        return ScrapedEvent(
            url=url,
            source="unstop.com",
            platform="unstop",
            title=title,
            description=description[:500],
            raw_text=text[:12000],
            dates=dates,
            deadlines=deadlines or self._deadline_lines(text),
            sponsor_tracks=self._track_lines(text),
            prizes=self._extract_lines(text, ["prize", "winner", "cash", "reward"]),
            mentorship_timings=self._extract_lines(text, ["mentor", "judge"]),
            links=[url],
            metadata={
                "status_code": 200,
                "content_type": "application/json",
                "text_length": len(text),
                "date_contexts": self._date_contexts(text),
                "important_actions": self._important_actions(text),
            },
        )

    # ─────────────────────────────────────────────
    # GENERIC HTML SCRAPER (works for most sites)
    # ─────────────────────────────────────────────
    async def _scrape_generic(self, url: str) -> ScrapedEvent:
        """Universal scraper — tries Jina AI first (works for JS sites), then HTML fallback."""
        html = ""
        status_code = 0
        content_type = "text/html"

        # Strategy 1: Jina AI Reader — works for ALL sites including JS-rendered
        try:
            jina_url = f"https://r.jina.ai/{url}"
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                response = await client.get(
                    jina_url,
                    headers={"User-Agent": self.USER_AGENT, "Accept": "text/html"},
                )
                if response.status_code == 200 and len(response.text) > 200:
                    html = response.text
                    status_code = 200
                    print(f"✅ Jina AI scraped: {len(html)} chars")
        except Exception as e:
            print(f"Jina failed: {e}")

        # Strategy 2: Direct HTTP with Chrome headers
        if not html:
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers={"User-Agent": self.USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                ) as client:
                    response = await client.get(url)
                    status_code = response.status_code
                    content_type = response.headers.get("content-type", "")
                    if response.status_code == 200:
                        html = response.text
                        print(f"✅ Direct scrape: {len(html)} chars")
            except Exception as e:
                print(f"Direct scrape failed: {e}")

        # Strategy 3: Googlebot
        if not html:
            try:
                async with httpx.AsyncClient(
                    timeout=25, follow_redirects=True,
                    headers={"User-Agent": "Googlebot/2.1 (+http://www.google.com/bot.html)", "Accept": "text/html"},
                ) as client:
                    response = await client.get(url)
                    if response.status_code == 200:
                        html = response.text
                        print(f"✅ Googlebot scrape: {len(html)} chars")
            except Exception as e:
                print(f"Googlebot failed: {e}")

        if not html:
            return self._empty_event(url, "Could not fetch page — site may block scrapers.")

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            tag.decompose()

        title = (self._first_meta(soup, ["og:title", "twitter:title"])
                 or self._title(soup) or url)
        description = self._first_meta(soup, ["og:description", "description", "twitter:description"])
        text = self._visible_text(soup)
        if not description:
            description = self._first_sentences(text)

        platform = self._platform(url)
        links = self._links(soup, url)
        sponsor_tracks = self._track_lines(text)
        prizes = self._extract_lines(text, ["prize", "winner", "cash", "swag", "credit", "award"])
        mentorship = self._extract_lines(text, ["mentor", "mentorship", "office hour", "judge"])
        deadlines = self._deadline_lines(text)
        important_actions = self._important_actions(text)
        date_contexts = self._date_contexts(text)
        dates = [item["time"] for item in date_contexts] or self._dates(text)

        return ScrapedEvent(
            url=url,
            source=urlparse(url).netloc.replace("www.", ""),
            platform=platform,
            title=title.strip(),
            description=description.strip(),
            raw_text=text[:12000],
            dates=dates[:20],
            deadlines=deadlines[:12],
            sponsor_tracks=sponsor_tracks[:12],
            prizes=prizes[:12],
            mentorship_timings=mentorship[:8],
            links=links[:30],
            metadata={
                "status_code": status_code,
                "content_type": content_type,
                "text_length": len(text),
                "date_contexts": date_contexts[:24],
                "important_actions": important_actions[:24],
            },
        )
    def _empty_event(self, url: str, reason: str) -> ScrapedEvent:
        return ScrapedEvent(
            url=url,
            source=urlparse(url).netloc.replace("www.", ""),
            platform=self._platform(url),
            title=f"Event at {urlparse(url).netloc}",
            description=reason,
            raw_text=reason,
            dates=[],
            deadlines=[],
            sponsor_tracks=[],
            prizes=[],
            mentorship_timings=[],
            links=[url],
            metadata={
                "status_code": 0,
                "content_type": "",
                "text_length": 0,
                "date_contexts": [],
                "important_actions": [],
            },
        )

    # ─────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────
    def _platform(self, url: str) -> str:
        host = urlparse(url).netloc.lower()
        if "luma.com" in host or "lu.ma" in host:
            return "luma"
        if "devfolio" in host:
            return "devfolio"
        if "unstop" in host:
            return "unstop"
        if "mlh.io" in host:
            return "mlh"
        if "lablab.ai" in host:
            return "lablab"
        if "hackerearth" in host:
            return "hackerearth"
        if "hackerrank" in host:
            return "hackerrank"
        if "kaggle" in host:
            return "kaggle"
        if "internshala" in host:
            return "internshala"
        return "generic"

    def _first_meta(self, soup: BeautifulSoup, keys: list[str]) -> str:
        for key in keys:
            selector = {"property": key} if key.startswith("og:") else {"name": key}
            tag = soup.find("meta", attrs=selector)
            if tag and tag.get("content"):
                return tag["content"]
        return ""

    def _title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string
        heading = soup.find(["h1", "h2"])
        return heading.get_text(" ", strip=True) if heading else ""

    def _visible_text(self, soup: BeautifulSoup) -> str:
        text = soup.get_text("\n", strip=True)
        lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
        unique = []
        seen = set()
        for line in lines:
            lowered = line.lower()
            if len(line) >= 3 and lowered not in seen:
                unique.append(line)
                seen.add(lowered)
        return "\n".join(unique)

    def _first_sentences(self, text: str) -> str:
        clean = re.sub(r"\s+", " ", text).strip()
        return clean[:420]

    def _extract_lines(self, text: str, keywords: list[str]) -> list[str]:
        results = []
        for line in text.splitlines():
            lowered = line.lower()
            if any(keyword in lowered for keyword in keywords):
                cleaned = line.strip()
                if 8 <= len(cleaned) <= 260 and not self._is_nav_noise(cleaned):
                    results.append(cleaned)
        return list(dict.fromkeys(results))

    def _track_lines(self, text: str) -> list[str]:
        results = []
        for line in text.splitlines():
            cleaned = line.strip()
            lowered = cleaned.lower()
            if self._is_nav_noise(cleaned):
                continue
            is_track_line = bool(re.search(r"\btrack\s*\d*\b", lowered))
            mentions_track_context = any(
                word in lowered for word in ["sponsor track", "challenge track", "category", "theme"]
            )
            if (is_track_line or mentions_track_context) and 8 <= len(cleaned) <= 260:
                results.append(cleaned)
        return list(dict.fromkeys(results))

    def _deadline_lines(self, text: str) -> list[str]:
        results = []
        for line in text.splitlines():
            cleaned = line.strip()
            lowered = cleaned.lower()
            if self._is_nav_noise(cleaned):
                continue
            has_deadline_word = bool(re.search(r"\b(deadline|due|closes|ends|last date)\b", lowered))
            has_submit_action = any(
                word in lowered for word in ["submit your", "submission deadline", "final submission", "register by"]
            )
            has_time = bool(self._dates(cleaned))
            if has_deadline_word or (has_submit_action and has_time):
                if 8 <= len(cleaned) <= 300:
                    results.append(cleaned)
        return list(dict.fromkeys(results))

    def _important_actions(self, text: str) -> list[str]:
        keywords = ["submit", "register", "apply", "build", "join", "sign up", "deadline", "prize", "track", "mentor"]
        results = []
        for line in text.splitlines():
            cleaned = line.strip()
            lowered = cleaned.lower()
            if self._is_nav_noise(cleaned):
                continue
            if any(keyword in lowered for keyword in keywords) and 12 <= len(cleaned) <= 300:
                results.append(cleaned)
        return list(dict.fromkeys(results))

    def _is_nav_noise(self, line: str) -> bool:
        lowered = line.lower().strip()
        noise = {"submissions", "rules", "overview", "prizes", "tracks", "schedule", "sign in", "login", "home"}
        return lowered in noise or (len(line) < 18 and lowered.endswith("?"))

    def _dates(self, text: str) -> list[str]:
        patterns = [
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?(?:\s*[-–—]\s*\d{1,2}(?:st|nd|rd|th)?)?(?:,?\s+\d{4})?",
            r"\b\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b",
            r"\b\d{1,2}:\d{2}\s*(?:AM|PM|am|pm)?\s*(?:UTC|IST|GMT|PST|EST)?\b",
            r"\b\d{4}-\d{2}-\d{2}\b",
        ]
        matches = []
        for pattern in patterns:
            matches.extend(re.findall(pattern, text))
        return list(dict.fromkeys(m.strip() for m in matches if m.strip()))

    def _date_contexts(self, text: str) -> list[dict[str, str]]:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        contexts: list[dict[str, str]] = []
        seen = set()
        for index, line in enumerate(lines):
            dates = self._dates(line)
            if not dates:
                continue
            window = self._context_window(lines, index)
            title = self._infer_event_title(window)
            detail = self._clean_detail(window)
            for date in dates:
                key = f"{date.lower()}::{detail.lower()}"
                if key in seen:
                    continue
                contexts.append({"time": date, "title": title, "detail": detail})
                seen.add(key)
        return contexts

    def _context_window(self, lines: list[str], index: int) -> str:
        current = lines[index]
        if len(current) >= 18 and self._dates(current) and not current.endswith(":"):
            return current
        neighbors = []
        for offset in (-1, 0, 1):
            pos = index + offset
            if 0 <= pos < len(lines):
                neighbors.append(lines[pos])
        return " | ".join(neighbors)

    def _infer_event_title(self, text: str) -> str:
        lowered = text.lower()
        if any(w in lowered for w in ["submission", "submit", "deadline"]):
            return "Submission deadline"
        if any(w in lowered for w in ["mentor", "judge", "office hour"]):
            return "Mentorship session"
        if any(w in lowered for w in ["start", "begins", "opening", "kickoff"]):
            return "Event starts"
        if any(w in lowered for w in ["end", "ends", "closing", "ceremony"]):
            return "Event ends"
        if any(w in lowered for w in ["register", "registration", "apply"]):
            return "Registration deadline"
        if any(w in lowered for w in ["prize", "credits", "reward"]):
            return "Prize or resource"
        return "Event timing"

    def _clean_detail(self, text: str) -> str:
        return re.sub(r"\s+", " ", text).strip(" |")[:260]

    def _links(self, soup: BeautifulSoup, base_url: str) -> list[str]:
        links = []
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            if href.startswith(("mailto:", "tel:", "#", "javascript:")):
                continue
            links.append(urljoin(base_url, href))
        return list(dict.fromkeys(links))