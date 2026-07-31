"""
Yerel API smoke / yetki / izolasyon denetimi.
Çalıştırma: backend çalışırken
  .venv\\Scripts\\python.exe scripts/run_audit_smoke.py

Sonuç: scripts/audit_results.json
Düzeltme YAPMAZ — yalnızca rapor üretir.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import date
from io import BytesIO
from pathlib import Path

import httpx
from openpyxl import Workbook

BASE = "http://127.0.0.1:8000/api/v1"
PASSWORD = "TestPass12345!"
OUT = Path(__file__).resolve().parent / "audit_results.json"

USERS = {
    "global_admin": "test.global.admin@example.com",
    "az_admin": "test.az.admin@example.com",
    "az_uzman": "test.az.uzman@example.com",
    "az_hekim": "test.az.hekim@example.com",
    "az_dsp": "test.az.dsp@example.com",
    "az_readonly": "test.az.readonly@example.com",
    "teh_admin": "test.teh.admin@example.com",
    "cok_admin": "test.cok.admin@example.com",
    "inactive": "test.inactive@example.com",
}


def login(client: httpx.Client, email: str, password: str = PASSWORD) -> tuple[int, dict | None]:
    r = client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        return r.status_code, None
    return r.status_code, r.json()


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def record(results: list, **kwargs):
    results.append(kwargs)


def make_excel(valid: bool = True, bad_header: bool = False) -> bytes:
    wb = Workbook()
    ws = wb.active
    if bad_header:
        ws.append(["Yanlış", "Sütun"])
        ws.append(["Ali", "Veli"])
    elif valid:
        ws.append(["Adı Soyadı", "T.C. Kimlik", "Branş/Görevi", "İşe Giriş Tarihi", "Departman"])
        ws.append(["TEST_ Excel Personel", "10000000001", "Operatör", "2024-01-15", "Üretim"])
        ws.append(["", "", "", "", ""])  # boş satır
        ws.append(["TEST_ Türkçe ÇĞİÖŞÜ", "10000000002", "Teknisyen", "15.01.2024", "Depo"])
    else:
        ws.append(["Adı Soyadı", "T.C. Kimlik"])
        ws.append(["TEST_ Eksik", "abc"])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def main():
    results = []
    started = time.time()
    with httpx.Client(timeout=30.0) as client:
        # Health
        try:
            h = client.get("http://127.0.0.1:8000/health")
            record(results, id="SYS-001", title="API health", module="system", severity="kritik" if h.status_code != 200 else None,
                   status="pass" if h.status_code == 200 else "fail", actual=f"{h.status_code}")
        except Exception as e:
            record(results, id="SYS-001", title="API erişilemiyor", module="system", severity="kritik",
                   status="fail", actual=str(e))
            OUT.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("API down — abort")
            return

        tokens = {}
        for key, email in USERS.items():
            code, data = login(client, email)
            ok = code == 200 and data and data.get("access_token")
            if key == "inactive":
                # Beklenen: login engellenmeli; gerçek: token veriliyor olabilir
                record(
                    results,
                    id="AUTH-001",
                    title="Pasif kullanıcı girişi",
                    module="auth",
                    role="read_only",
                    user=email,
                    status="fail" if ok else "pass",
                    severity="yüksek" if ok else None,
                    expected="Pasif kullanıcıya token verilmemeli",
                    actual=f"HTTP {code}; token={'var' if ok else 'yok'}",
                    type="yetki",
                )
            else:
                record(
                    results,
                    id=f"AUTH-LOGIN-{key}",
                    title=f"Giriş: {key}",
                    module="auth",
                    role=key,
                    user=email,
                    status="pass" if ok else "fail",
                    severity="yüksek" if not ok else None,
                    expected="200 + access_token",
                    actual=f"HTTP {code}",
                    type="fonksiyon",
                )
            if ok:
                tokens[key] = data["access_token"]

        # Wrong password
        code, _ = login(client, USERS["az_admin"], "WrongPass!!!")
        record(results, id="AUTH-002", title="Yanlış şifre reddi", module="auth", status="pass" if code == 401 else "fail",
               severity="yüksek" if code != 401 else None, expected="401", actual=str(code), type="güvenlik")

        # Password reset endpoint
        r = client.post(f"{BASE}/auth/forgot-password", json={"email": USERS["az_admin"]})
        record(results, id="AUTH-003", title="Şifre sıfırlama endpoint", module="auth",
               status="fail" if r.status_code == 404 else ("pass" if r.status_code < 500 else "fail"),
               severity="orta", expected="Şifre sıfırlama mevcut olmalı", actual=f"HTTP {r.status_code}",
               type="eksik_özellik")

        if "az_admin" not in tokens or "teh_admin" not in tokens:
            OUT.write_text(json.dumps({"results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Critical tokens missing")
            return

        # Me
        me = client.get(f"{BASE}/auth/me", headers=auth_headers(tokens["az_admin"]))
        az_company = me.json().get("company_id") if me.status_code == 200 else None
        record(results, id="AUTH-004", title="/auth/me", module="auth", status="pass" if me.status_code == 200 else "fail",
               actual=str(me.status_code), type="fonksiyon")

        teh_me = client.get(f"{BASE}/auth/me", headers=auth_headers(tokens["teh_admin"]))
        teh_company = teh_me.json().get("company_id") if teh_me.status_code == 200 else None

        # Firma izolasyonu: az_admin başka firmanın personelini görmemeli
        emp_az = client.get(f"{BASE}/employees", headers=auth_headers(tokens["az_admin"]))
        emp_teh = client.get(f"{BASE}/employees", headers=auth_headers(tokens["teh_admin"]))
        az_ids = {e["company_id"] for e in (emp_az.json() if emp_az.status_code == 200 else [])}
        teh_ids = {e["company_id"] for e in (emp_teh.json() if emp_teh.status_code == 200 else [])}
        isolation_ok = az_ids <= {az_company} and teh_ids <= {teh_company} and az_company != teh_company
        record(
            results,
            id="ISO-001",
            title="Personel firma izolasyonu",
            module="employees",
            status="pass" if isolation_ok else "fail",
            severity="kritik" if not isolation_ok else None,
            expected="Her firma admin yalnızca kendi company_id personelini görür",
            actual=f"az companies={az_ids} teh={teh_ids}",
            type="güvenlik",
        )

        # Cross-company create attempt
        if teh_company:
            cross = client.post(
                f"{BASE}/employees",
                headers=auth_headers(tokens["az_admin"]),
                json={"company_id": teh_company, "full_name": "TEST_ Cross Leak", "job_title": "x"},
            )
            record(
                results,
                id="ISO-002",
                title="Başka firmaya personel ekleme engeli",
                module="employees",
                status="pass" if cross.status_code == 403 else "fail",
                severity="kritik" if cross.status_code != 403 else None,
                expected="403",
                actual=f"HTTP {cross.status_code} body={cross.text[:200]}",
                type="güvenlik",
            )

        # Companies list isolation
        cos_az = client.get(f"{BASE}/companies", headers=auth_headers(tokens["az_admin"]))
        cos = cos_az.json() if cos_az.status_code == 200 else []
        record(
            results,
            id="ISO-003",
            title="Firma listesi izolasyonu",
            module="companies",
            status="pass" if len(cos) == 1 and cos[0]["id"] == az_company else "fail",
            severity="yüksek" if not (len(cos) == 1) else None,
            expected="1 firma (kendi)",
            actual=f"{len(cos)} firma",
            type="güvenlik",
        )

        # Rol bazlı erişim
        role_checks = [
            ("az_readonly", "/employees", 200, "ISO-ROLE-RO-EMP", "Salt okunur personel listesi (API)"),
            ("az_readonly", "/users", 403, "ISO-ROLE-RO-USR", "Salt okunur kullanıcı yönetimi engeli"),
            ("az_dsp", "/health", 200, "ISO-ROLE-DSP-H", "DSP sağlık erişimi"),
            ("az_dsp", "/isg-records?module=risk", None, "ISO-ROLE-DSP-R", "DSP risk erişimi (UI kapalı; API?)"),
            ("az_hekim", "/health", 200, "ISO-ROLE-HEK", "Hekim sağlık erişimi"),
            ("az_uzman", "/isg-records?module=risk", 200, "ISO-ROLE-UZM", "Uzman risk erişimi"),
            ("az_uzman", "/users", 403, "ISO-ROLE-UZM-U", "Uzman kullanıcı yönetimi engeli"),
        ]
        for user_key, path, expect, rid, title in role_checks:
            if user_key not in tokens:
                continue
            rr = client.get(f"{BASE}{path}", headers=auth_headers(tokens[user_key]))
            if expect is None:
                record(results, id=rid, title=title, module="yetki", status="info",
                       actual=f"HTTP {rr.status_code}", expected="UI kısıtlı; API davranışı kaydedildi", type="gözlem")
            else:
                ok = rr.status_code == expect
                record(results, id=rid, title=title, module="yetki", status="pass" if ok else "fail",
                       severity="yüksek" if not ok else None, expected=str(expect), actual=str(rr.status_code), type="yetki")

        # Direct ID access: get employee from other company via update
        if emp_teh.status_code == 200 and emp_teh.json():
            foreign_id = emp_teh.json()[0]["id"]
            put = client.put(
                f"{BASE}/employees/{foreign_id}",
                headers=auth_headers(tokens["az_admin"]),
                json={"full_name": "TEST_ Hijack"},
            )
            record(
                results,
                id="ISO-004",
                title="URL/ID ile başka firma personeli güncelleme",
                module="employees",
                status="pass" if put.status_code == 403 else "fail",
                severity="kritik" if put.status_code not in (403, 404) else None,
                expected="403",
                actual=f"HTTP {put.status_code}",
                type="güvenlik",
            )

        # Abonelik: cok_admin suspended — sistem kısıtlıyor mu?
        if "cok_admin" in tokens:
            sub = client.get(f"{BASE}/subscriptions/current", headers=auth_headers(tokens["cok_admin"]))
            emp = client.get(f"{BASE}/employees", headers=auth_headers(tokens["cok_admin"]))
            status_sub = sub.json().get("status") if sub.status_code == 200 else None
            record(
                results,
                id="SUB-001",
                title="Askıdaki abonelikte veri erişimi",
                module="subscriptions",
                status="fail" if emp.status_code == 200 else "pass",
                severity="yüksek" if emp.status_code == 200 else None,
                expected="Askıdaki abonelikte işlem/okuma kısıtlanmalı",
                actual=f"sub={status_sub} employees_http={emp.status_code}",
                type="iş_kuralı",
            )

        # Modül smoke (global admin)
        if "global_admin" in tokens:
            gh = auth_headers(tokens["global_admin"])
            endpoints = [
                "/companies", "/branches", "/employees", "/users",
                "/isg-records?module=risk", "/isg-records?module=near_miss",
                "/isg-records?module=accident", "/isg-records?module=capa",
                "/health", "/documents", "/annual-plans", "/reports/summary",
                "/notifications", "/subscriptions/current?company_id=1",
                "/trainings", "/trainings/meta", "/trainings/sectors",
                "/osgb", "/osgb/professionals", "/osgb/assignments",
                "/dashboard/summary", "/security/audit-logs",
            ]
            for ep in endpoints:
                rr = client.get(f"{BASE}{ep}", headers=gh)
                ok = rr.status_code < 400
                record(results, id=f"MOD-{ep.split('?')[0].strip('/').replace('/', '_')}",
                       title=f"GET {ep}", module="modül", status="pass" if ok else "fail",
                       severity="orta" if not ok else None, actual=f"HTTP {rr.status_code}", type="smoke")

            # Training PDF
            tr = client.get(f"{BASE}/trainings", headers=gh)
            if tr.status_code == 200 and tr.json():
                tid = tr.json()[0]["id"]
                for pdf_ep in (f"/trainings/{tid}/attendance.pdf", f"/trainings/{tid}/certificates.pdf"):
                    pr = client.get(f"{BASE}{pdf_ep}", headers=gh)
                    ok = pr.status_code == 200 and pr.headers.get("content-type", "").startswith("application/pdf")
                    record(results, id=f"PDF-{pdf_ep.split('/')[-1]}", title=f"PDF {pdf_ep}", module="trainings",
                           status="pass" if ok else "fail", severity="yüksek" if not ok else None,
                           actual=f"HTTP {pr.status_code} ct={pr.headers.get('content-type')}", type="fonksiyon")

            # XSS probe on isg create
            if az_company:
                xss = client.post(
                    f"{BASE}/isg-records",
                    headers=gh,
                    json={
                        "company_id": az_company,
                        "module": "risk",
                        "title": "<script>alert(1)</script>",
                        "description": "';TEST_DATA] XSS probe",
                        "status": "open",
                    },
                )
                record(results, id="SEC-XSS-001", title="XSS metin kabulü (saklama)", module="isg_records",
                       status="info", actual=f"HTTP {xss.status_code}", expected="Saklanabilir; çıktıda escape edilmeli",
                       type="güvenlik")

            # SQL injection probe on search
            sqli = client.get(f"{BASE}/employees?q=' OR 1=1--", headers=gh)
            record(results, id="SEC-SQL-001", title="Arama SQL injection duman testi", module="employees",
                   status="pass" if sqli.status_code < 500 else "fail",
                   severity="kritik" if sqli.status_code >= 500 else None,
                   actual=f"HTTP {sqli.status_code}", type="güvenlik")

        # Excel import tests
        if "az_admin" in tokens and az_company:
            ah = auth_headers(tokens["az_admin"])
            # valid
            files = {"file": ("personel.xlsx", make_excel(True), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            r = client.post(f"{BASE}/employees/import-excel?company_id={az_company}", headers=ah, files=files)
            record(results, id="XLS-001", title="Geçerli Excel yükleme", module="employees",
                   status="pass" if r.status_code == 200 and r.json().get("created", 0) >= 1 else "fail",
                   severity="yüksek" if r.status_code != 200 else None,
                   actual=f"HTTP {r.status_code} {r.text[:300]}", type="excel")

            # bad header
            files = {"file": ("bad.xlsx", make_excel(bad_header=True), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            r = client.post(f"{BASE}/employees/import-excel?company_id={az_company}", headers=ah, files=files)
            record(results, id="XLS-002", title="Yanlış sütun adı hatası", module="employees",
                   status="pass" if r.status_code == 422 else "fail",
                   severity="orta" if r.status_code != 422 else None,
                   expected="422 anlaşılır mesaj", actual=f"HTTP {r.status_code} {r.text[:200]}", type="excel")

            # wrong format
            files = {"file": ("x.csv", b"a,b\n1,2", "text/csv")}
            r = client.post(f"{BASE}/employees/import-excel?company_id={az_company}", headers=ah, files=files)
            record(results, id="XLS-003", title="Yanlış dosya formatı", module="employees",
                   status="pass" if r.status_code == 422 else "fail",
                   expected="422", actual=f"HTTP {r.status_code}", type="excel")

            # cross company excel
            if teh_company:
                files = {"file": ("personel.xlsx", make_excel(True), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
                r = client.post(f"{BASE}/employees/import-excel?company_id={teh_company}", headers=ah, files=files)
                record(results, id="XLS-004", title="Başka firmaya Excel engeli", module="employees",
                       status="pass" if r.status_code == 403 else "fail",
                       severity="kritik" if r.status_code != 403 else None,
                       expected="403", actual=f"HTTP {r.status_code}", type="güvenlik")

        # Unauthenticated
        r = client.get(f"{BASE}/employees")
        record(results, id="SEC-UNAUTH", title="Token olmadan API", module="auth",
               status="pass" if r.status_code in (401, 403) else "fail",
               severity="kritik" if r.status_code == 200 else None,
               expected="401/403", actual=str(r.status_code), type="güvenlik")

        # Debug / env leak check via openapi
        openapi = client.get("http://127.0.0.1:8000/openapi.json")
        docs = client.get("http://127.0.0.1:8000/docs")
        record(results, id="SEC-DOCS", title="Swagger /docs erişimi (prod riski)", module="system",
               status="info", actual=f"docs={docs.status_code} openapi={openapi.status_code}",
               expected="Üretimde kapatılmalı veya korunmalı", type="güvenlik")

    elapsed = round(time.time() - started, 2)
    passed = sum(1 for x in results if x.get("status") == "pass")
    failed = sum(1 for x in results if x.get("status") == "fail")
    info = sum(1 for x in results if x.get("status") == "info")
    summary = {
        "elapsed_sec": elapsed,
        "total": len(results),
        "pass": passed,
        "fail": failed,
        "info": info,
        "critical_fails": [x for x in results if x.get("status") == "fail" and x.get("severity") == "kritik"],
        "high_fails": [x for x in results if x.get("status") == "fail" and x.get("severity") == "yüksek"],
        "results": results,
        "generated_at": date.today().isoformat(),
        "note": "Yalnızca yerel API smoke. UI/mobil/manuel senaryolar ayrı değerlendirildi.",
    }
    OUT.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("elapsed_sec", "total", "pass", "fail", "info")}, ensure_ascii=False))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
