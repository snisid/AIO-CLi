import httpx
import pytest

from ma_cli.models.intelligent import IntelligentRouter
from ma_cli.providers.base import ChatMessage, ChatResponse, ModelInfo


class FakeProvider:
    def __init__(self, name: str, failures: int = 0):
        self.name = name
        self.failures = failures
        self.calls = 0
        self.circuit_breaker = type("Breaker", (), {"state": type("State", (), {"OPEN": "open"})()})()

    @property
    def enabled(self):
        return True

    async def discover_models(self):
        return [ModelInfo(model_id=f"{self.name}-model", name=self.name, provider=self.name, capabilities=["chat", "code"], available=True)]

    async def safe_chat(self, messages, model, **kwargs):
        self.calls += 1
        if self.calls <= self.failures:
            request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
            response = httpx.Response(503, request=request, text="temporary unavailable")
            raise httpx.HTTPStatusError("temporary unavailable", request=request, response=response)
        return ChatResponse(content="OK", model=model)


@pytest.mark.asyncio
async def test_failover_rotates_without_fixed_candidate_limit():
    first = FakeProvider("first", failures=20)
    second = FakeProvider("second", failures=0)
    router = IntelligentRouter()
    router._discover = lambda: _discover(first, second)
    response = await router.complete([{"role": "user", "content": "hello"}], task_type="coding")
    assert response.content == "OK"
    assert first.calls == 20
    assert second.calls == 1


async def _discover(first, second):
    return [(first, (await first.discover_models())[0]), (second, (await second.discover_models())[0])]
