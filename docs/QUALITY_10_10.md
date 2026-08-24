# MA-CLI 10/10 Quality Contract

MA-CLI is **10/10 only when the implementation is real, integrated, tested, secured, documented, automated, and production verified**.

## Mandatory lifecycle

`IMPLEMENTED -> INTEGRATED -> TESTED -> SECURED -> DOCUMENTED -> AUTOMATED -> PRODUCTION VERIFIED`

A domain score is capped at 9/10 if any lifecycle stage is missing. A feature is not complete when it only has tests, documentation, mocks, or placeholders.

## Forbidden completion states

- TODO as an implementation substitute
- `pass` as an unimplemented production path
- placeholder/stub/future implementation
- mock-only verification
- documentation without executable integration
- code without tests
- tests without runtime integration
- inaccessible features
- silent skipped gates

## Live verification rule

A mock test proves an interface contract. It does **not** prove a real provider, process, filesystem, browser, MCP server, installer, or Windows executable works.

Provider integrations require both deterministic tests and live capability tests where the environment supports them. Unavailable external services must produce an explicit `UNVERIFIED` state, never a false `PASS`.

## Release gate

A release is approved only when every mandatory gate is `PASS` and no gate is `UNVERIFIED`, `SKIPPED`, or `BLOCKED`.

Required domains include:

1. Native runtime
2. Tool engine
3. Security and sandbox
4. Model routing and provider fallback
5. MCP
6. Git
7. Browser
8. Observability
9. Windows packaging/installer
10. Documentation
11. Upgrade/rollback
12. E2E production verification

## Evidence

Every domain must produce machine-readable evidence containing:

- implementation paths
- test paths
- integration entry point
- security controls
- documentation path
- automation workflow
- live verification status
- timestamp
- commit SHA

The score is evidence-driven, not based on test count.
