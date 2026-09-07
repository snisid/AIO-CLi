import httpx

from ma_cli.providers.resilience import FailoverPolicy, FailureKind, classify_failure


def test_rate_limit_uses_retry_after():
    request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
    response = httpx.Response(429, request=request, headers={"retry-after": "7"}, text='{"error":"rate limit"}')
    info = classify_failure(httpx.HTTPStatusError("429", request=request, response=response))
    assert info.kind == FailureKind.RATE_LIMITED
    assert info.retryable is True
    assert info.cooldown_seconds == 7


def test_quota_is_retryable_and_does_not_become_permanent():
    request = httpx.Request("POST", "https://provider.test/v1/chat/completions")
    response = httpx.Response(429, request=request, text='{"error":"quota exhausted"}')
    info = classify_failure(httpx.HTTPStatusError("429", request=request, response=response))
    assert info.kind == FailureKind.QUOTA_EXHAUSTED
    assert info.retryable is True


def test_failover_policy_has_no_default_attempt_ceiling():
    policy = FailoverPolicy()
    assert policy.max_attempts is None
    assert policy.max_total_seconds is None
