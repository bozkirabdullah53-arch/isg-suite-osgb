"""Canlı Render smoke — salt okunur / düşük risk.

Varsayılan hedef:
  https://isg-suite-api-1u9t.onrender.com

İsteğe bağlı auth (canlıda yazma YOK):
  $env:LIVE_SMOKE_EMAIL='...'
  $env:LIVE_SMOKE_PASSWORD='...'

Çalıştır:
  python scripts/qa_live_render_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import httpx

API = os.environ.get("LIVE_API_BASE", "https://isg-suite-api-1u9t.onrender.com").rstrip("/")
WEB = os.environ.get("LIVE_WEB_BASE", "https://www.isgsuite.tr").rstrip("/")
EMAIL = os.environ.get("LIVE_SMOKE_EMAIL", "").strip()
PASSWORD = os.environ.get("LIVE_SMOKE_PASSWORD", "").strip()

OUT: list[dict] = []
ROOT = Path(__file__).resolve().parents[1]


def rec(name: str, ok: bool, detail: str = "", http: int | None = None, ms: float | None = None):
    row = {
        "test": name,
        "ok": bool(ok),
        "http": http,
        "ms": round(ms, 1) if ms is not None else None,
        "detail": str(detail)[:320],
    }
    OUT.append(row)
    flag = "PASS" if ok else "FAIL"
    extra = f" {http}" if http is not None else ""
    timing = f" {ms:.0f}ms" if ms is not None else ""
    print(flag, name + extra + timing, str(detail)[:140])


def timed_get(client: httpx.Client, path: str, **kwargs):
    t0 = time.perf_counter()
    r = client.get(path, **kwargs)
    return r, (time.perf_counter() - t0) * 1000


def timed_post(client: httpx.Client, path: str, **kwargs):
    t0 = time.perf_counter()
    r = client.post(path, **kwargs)
    return r, (time.perf_counter() - t0) * 1000


def main() -> int:
    # Cold start: first request may be slow on Render free/sleeping services
    timeout = httpx.Timeout(120.0, connect=30.0)
    with httpx.Client(base_url=API, timeout=timeout, follow_redirects=True) as client:
        # 1) Root health — cold then series for p50/p95-ish warm
        cold_samples = []
        for i in range(3):
            r, ms = timed_get(client, "/health")
            cold_samples.append(ms)
            if i == 0:
                ver = None
                markers = {}
                try:
                    body = r.json()
                    ver = body.get("version")
                    markers = body if isinstance(body, dict) else {}
                except Exception:
                    body = {}
                rec(
                    "live_health_cold",
                    r.status_code == 200 and bool(ver),
                    http=r.status_code,
                    ms=ms,
                    detail=f"version={ver} cold_ms={ms:.0f}",
                )
                if ver:
                    rec(
                        "live_version_recent",
                        str(ver) >= "0.9.56",
                        detail=f"version={ver}",
                    )
                rec(
                    "live_rate_limit_marker",
                    markers.get("rate_limit") == "simple-rpm-120" or "rate_limit" in markers,
                    detail=str(
                        {
                            k: markers.get(k)
                            for k in (
                                "rate_limit",
                                "secret_key_guard",
                                "health_roles",
                                "oversight_score",
                                "upload_security",
                            )
                            if k in markers
                        }
                    ),
                )
        warm_samples = []
        for _ in range(5):
            r2, ms2 = timed_get(client, "/health")
            warm_samples.append(ms2)
        warm_sorted = sorted(warm_samples)
        p95 = warm_sorted[min(len(warm_sorted) - 1, int(len(warm_sorted) * 0.95))]
        rec(
            "live_health_warm",
            r2.status_code == 200,
            http=r2.status_code,
            ms=warm_samples[-1],
            detail=f"warm_last={warm_samples[-1]:.0f} warm_p95~={p95:.0f} samples={warm_samples}",
        )
        rec(
            "live_health_latency_budget",
            p95 < 5000 and min(cold_samples) < 30000,
            detail=f"cold_min={min(cold_samples):.0f} cold_max={max(cold_samples):.0f} warm_p95={p95:.0f}",
        )

        # 3) OpenAPI / docs exposure (info)
        docs, dms = timed_get(client, "/docs")
        rec("live_docs_exposed", docs.status_code in (200, 404), http=docs.status_code, ms=dms, detail="INFO: /docs açık olabilir")

        # 4) Unauth companies → 401
        unauth, ums = timed_get(client, "/api/v1/companies")
        rec("live_companies_no_token", unauth.status_code in (401, 403), http=unauth.status_code, ms=ums)

        # 5) Public training verify (invalid)
        tv, tms = timed_get(client, "/api/v1/trainings/verify/NOTREALCODEXYZ")
        keys = []
        try:
            tj = tv.json()
            keys = list(tj.keys())
            ok_tv = tv.status_code == 200 and tj.get("valid") is False and "national_id" not in tj and "email" not in tj
        except Exception:
            ok_tv = False
            tj = {}
        rec("live_verify_invalid", ok_tv, http=tv.status_code, ms=tms, detail=str(keys))

        # 6) System health if present
        sh, sms = timed_get(client, "/api/v1/system/health")
        rec("live_system_health", sh.status_code in (200, 401, 404), http=sh.status_code, ms=sms)

        # 7) Optional authenticated read-only
        if EMAIL and PASSWORD:
            login, lms = timed_post(
                client,
                "/api/v1/auth/login",
                json={"email": EMAIL, "password": PASSWORD},
            )
            tok = None
            if login.status_code == 200:
                tok = (login.json() or {}).get("access_token")
            rec("live_login", bool(tok), http=login.status_code, ms=lms, detail="credential env kullanıldı")
            if tok:
                h = {"Authorization": f"Bearer {tok}"}
                me, mms = timed_get(client, "/api/v1/auth/me", headers=h)
                rec("live_auth_me", me.status_code == 200, http=me.status_code, ms=mms)
                cos, cms = timed_get(client, "/api/v1/companies", headers=h)
                n = len(cos.json()) if cos.status_code == 200 and isinstance(cos.json(), list) else None
                rec("live_companies_list", cos.status_code == 200, http=cos.status_code, ms=cms, detail=f"n={n}")
                ov, oms = timed_get(client, "/api/v1/osgb/oversight", headers=h)
                rec(
                    "live_osgb_oversight",
                    ov.status_code in (200, 403),
                    http=ov.status_code,
                    ms=oms,
                    detail="read-only",
                )
                # Delayed enum regression: oversight should not contain InvalidTextRepresentation
                txt = ov.text[:400] if ov.status_code == 200 else ""
                rec(
                    "live_oversight_no_delayed_enum_error",
                    ov.status_code != 200 or "annualplanstatus" not in txt.lower(),
                    http=ov.status_code,
                    detail="delayed enum hatası olmamalı",
                )
        else:
            rec("live_login", True, detail="SKIP: LIVE_SMOKE_EMAIL/PASSWORD yok — yalnız public smoke")

    # 8) Web origin reachability
    with httpx.Client(timeout=timeout, follow_redirects=True) as web:
        t0 = time.perf_counter()
        try:
            wr = web.get(WEB)
            wms = (time.perf_counter() - t0) * 1000
            rec("live_web_home", wr.status_code == 200, http=wr.status_code, ms=wms, detail=WEB)
        except Exception as e:
            rec("live_web_home", False, detail=str(e)[:200])

        # CORS preflight sample against API from web origin
        t0 = time.perf_counter()
        try:
            pre = web.options(
                f"{API}/api/v1/companies",
                headers={
                    "Origin": WEB,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization,content-type",
                },
            )
            pms = (time.perf_counter() - t0) * 1000
            acao = pre.headers.get("access-control-allow-origin", "")
            rec(
                "live_cors_preflight",
                pre.status_code in (200, 204) and (WEB in acao or acao == "*"),
                http=pre.status_code,
                ms=pms,
                detail=f"ACA-Origin={acao or '-'}",
            )
        except Exception as e:
            rec("live_cors_preflight", False, detail=str(e)[:200])

    cold = next((x for x in OUT if x["test"] == "live_health_cold"), None)
    warm = next((x for x in OUT if x["test"] == "live_health_warm"), None)
    summary = {
        "target_api": API,
        "target_web": WEB,
        "passed": sum(1 for x in OUT if x["ok"]),
        "failed": sum(1 for x in OUT if not x["ok"]),
        "total": len(OUT),
        "cold_start_ms": cold.get("ms") if cold else None,
        "warm_ms": warm.get("ms") if warm else None,
        "auth_mode": "env" if EMAIL and PASSWORD else "public_only",
        "results": OUT,
    }
    out = ROOT.parent / "docs" / "qa" / "logs" / "qa-live-render-smoke.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", summary["passed"], "/", summary["total"], "failed=", summary["failed"])
    print("Cold", summary["cold_start_ms"], "ms | Warm", summary["warm_ms"], "ms")
    print("Wrote", out)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
