"""Real browser + computer-use engine with network safety controls."""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse


class BrowserUnavailable(RuntimeError):
    """Raised when Playwright or its browser runtime is unavailable."""


class BrowserSecurityError(PermissionError):
    """Raised when browser navigation violates network policy."""


@dataclass
class BrowserConfig:
    headless: bool = True
    timeout_ms: int = 30_000
    allowed_hosts: set[str] = field(default_factory=set)
    allow_private_networks: bool = False
    user_agent: str | None = None


class BrowserEngine:
    """Playwright-backed browser engine exposed through safe computer actions."""

    def __init__(self, config: BrowserConfig | None = None):
        self.config = config or BrowserConfig()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def start(self) -> None:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise BrowserUnavailable("Install the browser extra: pip install 'ma-cli[all]' or playwright") from exc
        if self._page is not None:
            return
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.config.headless)
        context_kwargs = {}
        if self.config.user_agent:
            context_kwargs["user_agent"] = self.config.user_agent
        self._context = await self._browser.new_context(**context_kwargs)
        self._page = await self._context.new_page()
        self._page.set_default_timeout(self.config.timeout_ms)

    async def close(self) -> None:
        if self._context is not None:
            await self._context.close()
        if self._browser is not None:
            await self._browser.close()
        if self._playwright is not None:
            await self._playwright.stop()
        self._page = self._context = self._browser = self._playwright = None

    async def __aenter__(self) -> "BrowserEngine":
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise BrowserSecurityError("Only http:// and https:// URLs are permitted")
        host = parsed.hostname.lower().rstrip(".")
        if self.config.allowed_hosts and host not in {h.lower().rstrip(".") for h in self.config.allowed_hosts}:
            raise BrowserSecurityError(f"Host '{host}' is not in the browser allowlist")
        try:
            infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
        except OSError as exc:
            raise BrowserSecurityError(f"Unable to resolve browser host '{host}'") from exc
        if self.config.allow_private_networks:
            return
        addresses = {item[4][0] for item in infos}
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise BrowserSecurityError(f"Private/link-local browser target blocked: {address}")

    def _require_page(self):
        if self._page is None:
            raise BrowserUnavailable("Browser is not started")
        return self._page

    async def navigate(self, url: str, *, wait_until: str = "domcontentloaded") -> dict[str, object]:
        self._validate_url(url)
        page = self._require_page()
        response = await page.goto(url, wait_until=wait_until, timeout=self.config.timeout_ms)
        return {
            "url": page.url,
            "status": response.status if response else None,
            "title": await page.title(),
        }

    async def snapshot(self) -> dict[str, object]:
        page = self._require_page()
        return {"url": page.url, "title": await page.title(), "content": await page.locator("body").inner_text()}

    async def screenshot(self, path: str | None = None, *, full_page: bool = True) -> bytes:
        page = self._require_page()
        return await page.screenshot(path=path, full_page=full_page)

    async def click(self, selector: str) -> None:
        page = self._require_page()
        await page.locator(selector).click()

    async def type_text(self, selector: str, text: str, *, clear: bool = True) -> None:
        page = self._require_page()
        locator = page.locator(selector)
        if clear:
            await locator.fill(text)
        else:
            await locator.type(text)

    async def press(self, selector: str, key: str) -> None:
        await self._require_page().locator(selector).press(key)

    async def evaluate(self, expression: str) -> object:
        """Evaluate page JS only after the page has been explicitly navigated."""
        if not expression.strip():
            raise ValueError("expression cannot be empty")
        return await self._require_page().evaluate(expression)

    async def computer_use(self, action: str, **kwargs) -> dict[str, object]:
        """Execute a narrow, auditable computer-use action.

        Supported actions: click, type, press, screenshot, snapshot.
        Arbitrary OS-level keyboard/mouse control is intentionally not exposed.
        """
        if action == "click":
            await self.click(str(kwargs["selector"]))
        elif action == "type":
            await self.type_text(str(kwargs["selector"]), str(kwargs["text"]))
        elif action == "press":
            await self.press(str(kwargs["selector"]), str(kwargs["key"]))
        elif action == "screenshot":
            data = await self.screenshot(kwargs.get("path"))
            return {"action": action, "bytes": len(data)}
        elif action == "snapshot":
            return {"action": action, **await self.snapshot()}
        else:
            raise ValueError(f"Unsupported computer-use action: {action}")
        return {"action": action, "url": self._require_page().url}
