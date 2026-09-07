"""Browser engine with a swappable driver. Playwright is optional and fail-closed."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class BrowserError(RuntimeError):
    """Raised when a browser operation fails."""


class BrowserUnavailableError(BrowserError):
    """Raised when no browser backend is installed or running."""


class BrowserDriver(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def navigate(self, url: str) -> str: ...
    def content(self) -> str: ...
    def screenshot(self, path: Path) -> Path: ...
    def evaluate(self, expression: str) -> Any: ...
    def console_logs(self) -> list[str]: ...
    def network_log(self) -> list[dict[str, Any]]: ...


@dataclass
class InMemoryDriver:
    """Deterministic driver used by tests and offline diagnostics."""

    url: str = "about:blank"
    html: str = "<html><body></body></html>"
    logs: list[str] = field(default_factory=list)
    network: list[dict[str, Any]] = field(default_factory=list)
    started: bool = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.started = False

    def navigate(self, url: str) -> str:
        if not self.started:
            raise BrowserError("browser is not started")
        if not url.startswith(("http://", "https://", "about:")):
            raise BrowserError(f"refusing non-http navigation: {url}")
        self.url = url
        self.network.append({"url": url, "status": 200})
        return url

    def content(self) -> str:
        return self.html

    def screenshot(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"PNG")
        return path

    def evaluate(self, expression: str) -> Any:
        self.logs.append(expression)
        return {"expression": expression, "url": self.url}

    def console_logs(self) -> list[str]:
        return list(self.logs)

    def network_log(self) -> list[dict[str, Any]]:
        return list(self.network)


class PlaywrightDriver:
    def __init__(self) -> None:
        self._playwright: Any = None
        self._browser: Any = None
        self._page: Any = None
        self._console: list[str] = []
        self._network: list[dict[str, Any]] = []

    def start(self) -> None:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise BrowserUnavailableError("playwright is not installed") from exc
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page()
        self._page.on("console", lambda msg: self._console.append(msg.text))
        self._page.on("request", lambda req: self._network.append({"url": req.url, "method": req.method}))

    def stop(self) -> None:
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None

    def navigate(self, url: str) -> str:
        if self._page is None:
            raise BrowserError("browser is not started")
        if not url.startswith(("http://", "https://")):
            raise BrowserError(f"refusing non-http navigation: {url}")
        self._page.goto(url, wait_until="domcontentloaded")
        return self._page.url

    def content(self) -> str:
        if self._page is None:
            raise BrowserError("browser is not started")
        return self._page.content()

    def screenshot(self, path: Path) -> Path:
        if self._page is None:
            raise BrowserError("browser is not started")
        path.parent.mkdir(parents=True, exist_ok=True)
        self._page.screenshot(path=str(path))
        return path

    def evaluate(self, expression: str) -> Any:
        if self._page is None:
            raise BrowserError("browser is not started")
        return self._page.evaluate(expression)

    def console_logs(self) -> list[str]:
        return list(self._console)

    def network_log(self) -> list[dict[str, Any]]:
        return list(self._network)


class BrowserEngine:
    def __init__(self, driver: BrowserDriver | None = None, workspace: Path | None = None):
        self.workspace = (workspace or Path.cwd()).resolve()
        self.driver = driver
        self._started = False

    def _driver(self) -> BrowserDriver:
        if self.driver is None:
            self.driver = PlaywrightDriver()
        return self.driver

    def start(self) -> None:
        self._driver().start()
        self._started = True

    def stop(self) -> None:
        if self.driver is not None:
            self.driver.stop()
        self._started = False

    def navigate(self, url: str) -> str:
        self._ensure_started()
        return self._driver().navigate(url)

    def content(self) -> str:
        self._ensure_started()
        return self._driver().content()

    def screenshot(self, name: str = "screenshot.png") -> Path:
        self._ensure_started()
        target = (self.workspace / name).resolve()
        target.relative_to(self.workspace)
        return self._driver().screenshot(target)

    def evaluate(self, expression: str) -> Any:
        self._ensure_started()
        return self._driver().evaluate(expression)

    def evidence(self) -> dict[str, Any]:
        self._ensure_started()
        driver = self._driver()
        return {
            "console": driver.console_logs(),
            "network": driver.network_log(),
            "dom": driver.content()[:4000],
        }

    def _ensure_started(self) -> None:
        if not self._started:
            self.start()


_engine: BrowserEngine | None = None


def get_browser_engine(workspace: Path | None = None) -> BrowserEngine:
    global _engine
    resolved = (workspace or Path.cwd()).resolve()
    if _engine is None or _engine.workspace != resolved:
        _engine = BrowserEngine(workspace=resolved)
    return _engine
