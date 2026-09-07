import asyncio
import http.server
import threading

import pytest

from ma_cli.browser import BrowserConfig, BrowserEngine, BrowserSecurityError, BrowserUnavailable


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = b'<html><body><button id="go" onclick="document.body.dataset.clicked=\'yes\'">Go</button><input id="name"></body></html>'
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        return


@pytest.mark.asyncio
async def test_browser_real_navigation_and_computer_use():
    try:
        from playwright.async_api import Error as PlaywrightError  # noqa: F401
    except ImportError:
        pytest.skip("playwright is not installed")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    engine = BrowserEngine(BrowserConfig(allow_private_networks=True, allowed_hosts={"127.0.0.1"}))
    try:
        try:
            await engine.start()
        except Exception as exc:
            if "Executable doesn't exist" in str(exc) or "browser" in str(exc).lower():
                pytest.skip(f"Playwright browser runtime unavailable: {exc}")
            raise
        result = await engine.navigate(f"http://127.0.0.1:{port}/")
        assert result["status"] == 200
        await engine.type_text("#name", "AIO-CLi")
        await engine.click("#go")
        assert await engine.evaluate("document.body.dataset.clicked") == "yes"
        snapshot = await engine.snapshot()
        assert "AIO-CLi" in snapshot["content"]
    finally:
        await engine.close()
        server.shutdown()
        server.server_close()


def test_browser_blocks_private_network_by_default():
    engine = BrowserEngine(BrowserConfig())
    with pytest.raises(BrowserSecurityError):
        engine._validate_url("http://127.0.0.1:8080/")
