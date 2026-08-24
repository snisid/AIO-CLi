# MA-CLI 10/10 Domain Matrix

Scores below are **evidence states**, not marketing claims. `UNVERIFIED` prevents a release from being called 10/10.

| Domain | Implemented | Integrated | Tested | Secured | Documented | Automated | Production Verified | Release state |
|---|---|---|---|---|---|---|---|---|
| Native Runtime | PASS | PASS | PASS* | PASS* | PASS | PASS | UNVERIFIED | BLOCKED |
| Tool Engine | PASS | PASS | PASS* | PASS* | PASS | PASS | UNVERIFIED | BLOCKED |
| Security/Sandbox | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Model Routing | PASS | PASS | PARTIAL | PASS* | PASS | PASS | UNVERIFIED | BLOCKED |
| Providers | PARTIAL | PARTIAL | PARTIAL | PASS* | PASS | PASS | UNVERIFIED | BLOCKED |
| MCP | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Git | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Browser | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Desktop | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Windows Installer | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Observability | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | PASS | UNVERIFIED | BLOCKED |
| QA/Release Gate | PASS | PASS | PASS | PASS | PASS | PASS | UNVERIFIED | BLOCKED |

`*` means deterministic repository tests exist; it is not a claim of clean-host production verification.

## Rule

No row may be changed to `PASS / PRODUCTION VERIFIED` without live evidence from the target environment. A green unit-test suite is insufficient.
