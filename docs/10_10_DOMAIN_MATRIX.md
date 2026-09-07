# MA-CLI 10/10 Domain Matrix

## Release contract

Every domain must pass:

`IMPLEMENTED → INTEGRATED → TESTED → SECURED → DOCUMENTED → AUTOMATED → PRODUCTION VERIFIED`

The matrix is **never allowed to manufacture live evidence**. `PRODUCTION VERIFIED` means a real target environment was exercised and evidence was recorded.

| Domain | Implemented | Integrated | Tested | Secured | Documented | Automated | Production Verified | Release |
|---|---|---|---|---|---|---|---|---|
| Native Runtime | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |
| Tool Engine | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |
| Security / Sandbox | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |
| Model Routing | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |
| Providers | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |
| MCP | IMPLEMENTATION REQUIRED | INTEGRATION REQUIRED | TEST REQUIRED | SECURITY REQUIRED | PASS | PASS | PENDING LIVE | IN PROGRESS |
| Git | IMPLEMENTATION REQUIRED | INTEGRATION REQUIRED | TEST REQUIRED | SECURITY REQUIRED | PASS | PASS | PENDING LIVE | IN PROGRESS |
| Browser | IMPLEMENTATION REQUIRED | INTEGRATION REQUIRED | TEST REQUIRED | SECURITY REQUIRED | PASS | PASS | PENDING LIVE | IN PROGRESS |
| Desktop | PASS | PASS | PASS | PASS | PASS | PASS | PENDING WINDOWS LIVE | READY |
| Windows Installer | PASS | PASS | PASS | PASS | PASS | PASS | PENDING WINDOWS LIVE | READY |
| Upgrade / Rollback | IMPLEMENTATION REQUIRED | INTEGRATION REQUIRED | TEST REQUIRED | SECURITY REQUIRED | PASS | PASS | PENDING WINDOWS LIVE | IN PROGRESS |
| Observability | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |
| QA / Release Gate | PASS | PASS | PASS | PASS | PASS | PASS | PENDING LIVE | READY |

## Live verification protocol

A domain moves from `PENDING LIVE` to `PASS` only after the real verification command runs against the actual target environment. Evidence must contain:

- domain
- exact command or scenario executed
- target environment
- timestamp (UTC)
- result
- relevant logs/exit code
- repository commit SHA

### Provider live verification

Required for each enabled provider:

- Ollama: real local endpoint + real model inference + failure/fallback test
- OmniRoute: real endpoint + authenticated inference + failure/fallback test
- 9router: real endpoint + authenticated inference + failure/fallback test
- OpenAI: real API call + failure/fallback test
- Anthropic: real API call + failure/fallback test

No API key, local service, Windows host, browser session, MCP server, or installer is assumed to exist merely because code exists. Missing external prerequisites remain `PENDING LIVE`, never a fake PASS.

## Current meaning of READY

`READY` means the repository contains the implementation, integration, automated checks, and live-verification harness required to perform the final real-world gate. It does **not** mean that a remote machine or private credential has been exercised.

The final release gate becomes APPROVED only when every row reports `PASS` for production verification.
