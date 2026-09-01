"""Singleton Playwright browser lifecycle holder.

Mirrors `core.http.HttpClientHolder`: one async resource per process, started
in the FastAPI lifespan and closed on shutdown. Each request opens its own
`BrowserContext` so cookies / storage / tabs are isolated per call (stateless
flow — no shared state between requests).
"""
from typing import Optional

from playwright.async_api import Browser, async_playwright


class PlaywrightHolder:
    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._pw = None
        self._browser: Optional[Browser] = None

    @property
    def browser(self) -> Optional[Browser]:
        return self._browser

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(headless=self._headless)

    async def close(self) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._pw is not None:
            await self._pw.stop()
            self._pw = None