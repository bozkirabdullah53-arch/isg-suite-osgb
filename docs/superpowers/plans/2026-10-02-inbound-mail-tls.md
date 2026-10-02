# Inbound Mail TLS Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement the steps in order.

**Goal:** Prevent POP3 credentials from crossing a plaintext connection and require certificate/hostname validation for every inbound TLS mode.

**Architecture:** Keep the existing IMAP/POP3 adapters and retry behavior. Supply verified TLS contexts and require POP3 STLS before authentication. Extend the existing provider-pending draft; deployment requires a successful mailbox test on the actual provider.

**Tech Stack:** Python 3.12, imaplib/poplib, ssl, pytest, real loopback protocol servers.

**Spec:** docs/security/NSL-2026-remediation.md and docs/security/NSL-2026-account-health-rollout.md.

## Global Constraints

- Preserve working application modules and all customer data.
- Do not modify real mail credentials/endpoints or publish a guessed DKIM record.
- No production mail deployment before validated provider login and send/receive.
- Work in the explicitly requested isg-suite-osgb repository; do not claim this proves deployment to isgsuite.com.tr.

## Review Focus

- A failed STLS negotiation must send no username or password.
- An untrusted, expired or mismatched certificate must send no credentials.
- Valid implicit TLS and STARTTLS/STLS must still authenticate.
- Retry cleanup must leave no open socket after a rejected handshake.
- Provider diagnostics must not send mail, retrieve message contents or print credentials.

### Task 1: Verified inbound transport

**Files:** Modify backend/app/services/inbound_mail.py; create backend/tests/test_inbound_mail_tls.py.

**Interfaces:** Existing `_connect_imap_with_retry()` and `_connect_pop3_with_retry()` return authenticated stdlib clients or raise RuntimeError.

- [x] Add real loopback tests for untrusted implicit TLS, untrusted IMAP STARTTLS, refused POP3 STLS and valid encrypted authentication.
- [x] Run the tests against master and record failures proving the missing protections.
- [x] Supply ssl.create_default_context() to IMAP/POP3 implicit TLS and STARTTLS/STLS; negotiate POP3 STLS before credentials.
- [x] Run the new tests and existing inbox/delivery/security regressions.

### Task 2: Provider readiness diagnostic and rollout record

**Files:** Create backend/scripts/check_inbound_mail_tls.py, backend/tests/test_inbound_mail_tls_probe.py and docs/security/NSL-2026-inbound-tls-readiness.md.

**Interfaces:** `check_inbound_mail_tls()` returns a redacted status dictionary; CLI returns 0 for authenticated verified TLS and 1 otherwise. It uses existing settings and never changes endpoints or settings.

- [x] Add tests for missing configuration, provider rejection, verified authentication and refusal to accept an unverified connection.
- [x] Run the tests and observe the missing diagnostic failure.
- [x] Implement a read-only mailbox login check; do not read/send/delete messages. Print only status/protocol/TLS/error class.
- [x] Record exact deployment blockers and HTTP/DNS remediation steps without guessing the live Plesk configuration.
- [ ] Full suite completion blocked by automatic security review of an existing cloud-metadata request. Targeted regressions passed; partial failures and missing final report documented.
- [ ] Update the existing provider-pending draft with the tested changes. Do not merge/deploy while mailbox readiness is unknown.
