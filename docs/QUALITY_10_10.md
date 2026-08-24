# MA-CLI 10/10 Quality Contract

MA-CLI is 10/10 only when every mandatory domain passes the complete lifecycle:

`IMPLEMENTED -> INTEGRATED -> TESTED -> SECURED -> DOCUMENTED -> AUTOMATED -> PRODUCTION VERIFIED`

## Non-negotiable rules

The following states are not completion:

- TODO used as an implementation substitute
- `pass` used for an unimplemented production path
- placeholder, stub, or future implementation
- mock-only verification
- documentation without executable integration
- code without tests
- tests without runtime integration
- a feature that cannot be reached from MA-CLI
- a skipped or silently disabled release gate

## Evidence rule

A mock proves an interface contract. It does not prove that a real provider, process, filesystem, browser, MCP server, executable, installer, or Windows host works.

Live integrations must report `PASS`, `UNVERIFIED`, or `FAIL` explicitly. `UNVERIFIED` must never be converted into `PASS` to make a release green.

## Mandatory release domains

1. Native autonomous runtime
2. Tool engine
3. Security and sandbox
4. Model routing and provider fallback
5. MCP lifecycle
6. Git engine
7. Browser engine
8. Desktop runtime
9. Windows executable and installer
10. Upgrade, rollback, repair, diagnostics
11. Observability
12. Documentation
13. Production E2E verification

## Required evidence per domain

Each domain must identify:

- implementation paths
- MA-CLI integration entry point
- tests
- security controls
- documentation
- automation workflow
- live verification status
- timestamp
- commit SHA

A release is approved only when every mandatory gate is `PASS` and no mandatory gate is `UNVERIFIED`, `SKIPPED`, or `BLOCKED`.
