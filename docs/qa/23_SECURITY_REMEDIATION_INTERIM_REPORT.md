# Security remediation — interim report

**Date:** 2026-10-12  
**Scope:** Repository review based on the available summary page of external report NSL-2026-PRJ-106 and current repository QA records.  
**Status:** Partial remediation prepared; this is not a closure certificate.

## Confirmed residual risk addressed in this branch

### Production file-upload antivirus enforcement

**Prior condition:** `CLAMAV_REQUIRED` defaults to `false`. With no ClamAV host configured, `scan_bytes` returns `(True, "skipped")`, allowing uploads to proceed without antivirus scanning. The QA decision document also lists production ClamAV as disabled/optional.

**Change prepared:** Production runtime validation now fails closed unless `CLAMAV_REQUIRED=true` and `CLAMAV_HOST` is set. This intentionally prevents a production release until the service is configured. Unit tests were added for both missing enforcement and missing host.

**Deployment prerequisite:** Configure a reachable ClamAV service, set `CLAMAV_REQUIRED=true` and `CLAMAV_HOST`, and verify the readiness/scan path before merging or deploying. Do not merge this change into a live deployment before these environment settings are ready, or startup will fail.

## Existing positive evidence

- Repository QA reports 54/54 isolated archive smoke checks passing, including a cross-OSGB archive access attempt returning HTTP 403.
- Existing code includes company/OSGB scope helpers, RLS context, JWT validation, security headers and request rate limiting.

These are useful controls, but isolated tests do not prove that every API route and data export enforces tenant scope.

## Items not certified closed

The complete 18-page external assessment was not available in the reviewed material; only its summary page was available. Therefore the individual evidence, reproduction steps, affected endpoints and closure criteria for all seven findings cannot yet be mapped. In particular, the highest-risk Broken Tenant Isolation finding requires a complete endpoint-by-endpoint authorization review and cross-tenant read/write regression tests against all sensitive modules, not only the archive endpoints.

Before declaring the assessment closed:
1. Obtain the full report and map every finding ID to affected routes and acceptance criteria.
2. Run automated cross-tenant read/write tests across all tenant-bound APIs, exports, uploads, health records, training, documents, risk, incidents and administrative routes.
3. Run the full QA suite and production-like PostgreSQL/RLS integration tests.
4. Validate live security headers, CORS, Redis rate limiting, ClamAV reachability, storage access policy, backups and monitoring.
5. Perform an independent retest and attach evidence for each finding.

**Conclusion:** This branch addresses one confirmed residual configuration risk. It does not claim all seven external findings are fixed, and it has not been deployed to production.
