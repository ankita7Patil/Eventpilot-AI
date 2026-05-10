from models import ScrapedEvent
from services.scraper_service import ScraperService


class MonitorAgent:
    """Monitors opportunity URLs by scraping current page state."""

    def __init__(self, scraper: ScraperService) -> None:
        self.scraper = scraper

    async def run(self, url: str) -> ScrapedEvent:
        return await self.scraper.scrape(url)
