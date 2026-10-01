# NSL account and health follow-up — 2026-10-01

This change is prepared for review, not evidence of production or external closure.
The user confirmed 202602, 202606 and 202607 are open, 202603 remains partial because
IP-only protection permits distributed guesses, and 202609 remains partial because
`/health` is anonymous. The user's `NSL-02609` reference is treated as NSL-202609.
The user selected CAPTCHA after the account threshold rather than an account lock.

## Current status and remaining work

| Finding | Current status | Required closure evidence |
| --- | --- | --- |
| NSL-202602 | Open; provider/mail TLS work pending | Validated encrypted mailbox authentication, send and receive; provider remediation of exposed plaintext endpoints |
| NSL-202603 | Partial in production; account CAPTCHA implementation prepared | Enable configured account protection, then verify distributed requests and normal password/MFA login in production |
| NSL-202606 | Open; DNS/provider work pending | Provider-issued DKIM selector/key, aligned real messages and enforced DMARC after legitimate sender validation |
| NSL-202607 | Open; provider platform work pending | Provider upgrade or migration plus external retest of the affected platform |
| NSL-202609 | Partial in production; authenticated health implementation prepared | Protected `/health` on custom and direct API origins; verified Render probe on `/live`; external acceptance of minimal public liveness |

Read-only observation on 2026-10-01: `https://www.isgsuite.tr/health` returned HTTP 200
with exactly `{"status":"ok"}`. Google DNS-over-HTTPS returned MX
`10 mx01.isgsuite.tr.`, an SPF record, and NXDOMAIN for `_dmarc.isgsuite.tr`.
These observations do not validate mailbox TLS, DKIM or external closure. No real
production accounts were used for password guessing. Do not publish a guessed DKIM
key, change the live mail endpoints, or enable reject before legitimate mail is tested.

## Account protection

Before password verification, every attempt reserves one slot in a rolling
ten-minute account budget (default 10). Successful and failed guesses consume slots.
The account ID joins username/email aliases; nonexistent identifiers use the same
challenge flow. HMAC keys avoid storing submitted identifiers in Redis.

Redis server time and one atomic Lua operation share the budget across IPs and
workers. Missing/unavailable shared storage in production requires CAPTCHA
immediately. Existing source/subnet throttles remain. A solved CAPTCHA authorizes
only its request and does not reset the budget or bypass password/MFA verification.
This reduces automated distributed guessing; it is not a claim that human-assisted
or CAPTCHA-solving attacks are impossible.

The backend calls the fixed Turnstile Siteverify endpoint and requires literal
`success: true`, the allowed frontend hostname and `action: login`. Verification
failure permits no login; temporary provider failure returns 503. Provider calls
have a timeout, bounded concurrency and no checked-out database connection.
The secret stays in backend environment configuration. Expired/reused tokens are
rejected by Siteverify; frontend retries discard the old token.

## Ordered production rollout

1. Create a production Turnstile widget restricted to the real frontend hostnames.
   Put `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET_KEY` and
   `TURNSTILE_ALLOWED_HOSTNAMES` into the API service's secure environment settings.
   Use `isgsuite.tr,www.isgsuite.tr` only if these are the actual login origins;
   add other owned login origins explicitly if required. Keep
   `LOGIN_CAPTCHA_ENABLED=false` and `HEALTH_AUTH_REQUIRED=false` for the first deploy.
2. Deploy backend support first. Confirm direct API `/live` returns empty HTTP 204
   and existing login/MFA still works. Deploy frontend support, the `/live` static
   rewrite before the SPA fallback and the CSP script/frame allowlist for
   `https://challenges.cloudflare.com`. Existing `'self'` frame support is preserved.
   This repository uses an imperative Render static site: a render.yaml edit alone
   does not prove the live routes or headers changed. Verify the Render settings.
3. Confirm custom-origin `/live` is the backend's empty 204, not HTML HTTP 200.
   Frontend wakeup requires that exact status. Change the API Render health check
   from `/health` to `/live`, then verify the service is healthy.
4. Enable `LOGIN_CAPTCHA_ENABLED=true` and `LOGIN_ACCOUNT_WINDOW_LIMIT=10` only
   after the frontend widget and CSP load correctly. Enable `HEALTH_AUTH_REQUIRED=true`
   after the Render probe change. Production configuration requires shared Redis
   and nonempty CAPTCHA keys/hostnames. Missing keys must fail startup validation.
5. Use a dedicated test account to verify: attempts from multiple sources share
   the same threshold; the eleventh attempt requires CAPTCHA before password
   checking; email and username cannot obtain separate budgets; invalid, expired
   and reused tokens fail; valid CAPTCHA plus correct password follows normal MFA;
   another account can log in. Verify `/health` is 401 without auth, 403 for an
   ordinary authenticated user and 200 for an authenticated global admin on both
   custom and direct API origins. `/api/v1/system/health` remains authenticated.
6. Record commit, deployment IDs, flags, response times and tester acceptance.
   Do not label any finding closed until the corresponding evidence is accepted.

For availability rollback, turn the newly enabled flags off and restore the prior
probe configuration only as needed. Such rollback returns 202603/202609 to partial
status; it is not a security closure. No schema migration is required.

`/live` is deliberately anonymous and empty: it proves that the process responds,
not that the database, mail or backups work. If the tester's acceptance criterion
prohibits every anonymous probe, resolve that criterion with the Render probe
architecture before claiming closure; an empty public endpoint is not authentication.

## Verification scope

Dedicated regression tests cover rotated IPs, aliases, unknown accounts, password
and MFA checks, invalid provider responses, provider outages, Redis loss and atomic
reservations across two workers. Frontend tests cover challenge error metadata,
widget token invalidation and rejection of HTML liveness fallback.

The full backend test command was interrupted by automatic approval review because
an existing test attempted a request to a cloud metadata endpoint. It was not
rerun. Use the targeted security suite and recorded frontend checks; do not report
the full backend suite as passing. This change has no production retest evidence yet.

Turnstile integration follows the provider's server validation and CSP guidance:
- https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- https://developers.cloudflare.com/turnstile/reference/content-security-policy/

PR dependency audit also reported CVE-2026-101918 in the existing PyJWT 2.14.0
pin and identified 2.15.0 as the fixed version. The pin is updated in this PR;
token, refresh/MFA and targeted security checks must pass with that version.
The provider release is https://github.com/jpadilla/pyjwt/releases/tag/2.15.0.

Local verification with PyJWT 2.15.0: targeted account/security/Redis suite 59
passed, token/revoke suite 5 passed, refresh-cookie suite 3 passed; frontend
364 tests passed and build passed. The broader authentication test
`test_specialist_register_does_not_create_osgb` still fails because registration
returns an OSGB ID where the test expects none. The same assertion fails with
the prior 2.14.0 package; this PR does not change that registration behavior.
