# MA-CLI 10/10 Domain Matrix

This matrix is evidence-driven. A domain is not 10/10 until production verification is complete.

| Domain | Implemented | Integrated | Tested | Secured | Documented | Automated | Production Verified | Release |
|---|---|---|---|---|---|---|---|---|
| Native Runtime | PASS | PASS | PASS | PASS | PASS | PASS | UNVERIFIED | BLOCKED |
| Tool Engine | PASS | PASS | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Security / Sandbox | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Model Routing | PASS | PASS | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Providers | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | PASS | UNVERIFIED | BLOCKED |
| MCP | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Git | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Browser | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Desktop | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Windows Installer | PARTIAL | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | UNVERIFIED | BLOCKED |
| Upgrade / Rollback | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | NOT COMPLETE | PARTIAL | PARTIAL | UNVERIFIED | BLOCKED |
| Observability | PARTIAL | PARTIAL | PARTIAL | PASS | PASS | PASS | UNVERIFIED | BLOCKED |
| QA / Release Gate | PASS | PASS | PASS | PASS | PASS | PASS | UNVERIFIED | BLOCKED |

## Release rule

No row may become `PASS / PRODUCTION VERIFIED` without live evidence from the target environment. A green unit-test suite alone is insufficient.
