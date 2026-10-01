# NSL verification follow-up — 2026-09-30

2026-10-01 update: the user confirms 202602/202606/202607 remain open and
202603/202609 remain partial. The account threshold now has a prepared CAPTCHA
follow-up, and `/health` has prepared administrator authentication with a separate
empty `/live` probe. These are not deployed closure claims. See
[the ordered rollout and evidence requirements](NSL-2026-account-health-rollout.md).

The external tester confirmed closure of MFA bypass (202601), account lockout (202605), and spreadsheet formula injection (202608). Other findings remain externally open until verification is accepted.

## Password spray (202603)

At 09:03 UTC, the production www origin returned 401 for all twelve requests against twelve synthetic nonexistent example.invalid accounts. The earlier 30/minute request limit did not meet this exact scenario.

The follow-up counts distinct identifiers in failed (401) login responses per source over a sliding ten-minute window. Ten distinct failures trigger a source restriction: subsequent login requests return 429 and Retry-After. Successful logins do not consume the distinct-account budget. Existing account/IP, total source and subnet protections remain. Identifiers are HMAC-digested; logs omit submitted names and passwords. Redis uses a server-time atomic sorted-set operation, shared by workers, with a continuously mirrored bounded local fallback.

## Contextual assistant (202604)

Client rendering already used React text nodes, but the API reflected page title/purpose markup verbatim. Encode message and spoken output at the server boundary, including AI-generated output and entity-obfuscated payloads. The frontend decodes only fixed entities into a string and renders that string in React text nodes; it never parses the response as HTML. Tests cover img/script/style/form/meta, double encoding, the authenticated API route, readable display and speech, and absence of injected DOM elements. Global inline-style policy is retained for compatibility; no client-controlled tags are rendered.

## Health (202609)

At 08:52 UTC, cache-bypassed GET /health returned exactly {"status":"ok"} on both www and the direct API origin. No service name or dependency detail was present. The attached document is version V1.0 dated 28 September; its evidence contains the former degraded/service response. The user states the external verification ran after the 30 September deployment. Obtain the tester's current response/time/IP to reconcile this discrepancy; do not declare external closure merely from our observation. Dependency detail endpoints remain authenticated. Public health is process liveness, not proof of database/mail/backup readiness.

## Provider findings

202602, 202606 and 202607 remain open. Provider supplied secure mailmatik endpoints but mailbox authentication and send/receive have not been validated. Do not change live mail credentials/endpoints, disable mail, merge the pending inbound-TLS PR, or loosen SMTP TLS protection until delivery is verified. SPF presence is not a substitute for DKIM or DMARC enforcement. The provider must address the old plaintext/EOL endpoints or provide migration.

## Release evidence

See the follow-up pull request for CI run, final merged SHA, Render deploy IDs and production verification. No confidential PDF, PDF password, access tokens, real mailbox credentials or customer records are committed.
