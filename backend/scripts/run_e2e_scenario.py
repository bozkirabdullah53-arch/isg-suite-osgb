"""
Uçtan uca demo senaryosu — firma atamaları + uzman/hekim tüm işlemler (%100 deneme).

Çalıştırma:
  # Canlı
  python scripts/run_e2e_scenario.py --live

  # Yerel (TestClient + geçici SQLite)
  python scripts/run_e2e_scenario.py --local

Rapor:
  docs/qa/logs/e2e-scenario-report.json
  docs/qa/logs/e2e-scenario-report.txt
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT))

DEMO_PASSWORD = "DemoIsgSuite2026!"
PASS_FALLBACK = "TestPass12345!"
LIVE_BASE = "https://isg-suite-api-1u9t.onrender.com/api/v1"

REPORT: list[dict] = []


def today_utc() -> date:
    """Sunucu UTC ise yerel 'bugün' gelecek sayılmasın diye UTC günü kullan."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).date()


def rec(phase: str, step: str, ok: bool, *, http: int | None = None, detail: str = "", firm: str = ""):
    item = {
        "phase": phase,
        "step": step,
        "ok": bool(ok),
        "http": http,
        "firm": firm,
        "detail": str(detail or "")[:400],
    }
    REPORT.append(item)
    mark = "PASS" if ok else "FAIL"
    firm_s = f" [{firm}]" if firm else ""
    line = f"{mark} {phase} :: {step}{firm_s}"
    if http is not None:
        line += f" http={http}"
    if detail and not ok:
        line += f" -- {detail[:120]}"
    try:
        print(line)
    except UnicodeEncodeError:
        print(line.encode("ascii", "replace").decode("ascii"))


class Api:
    def __init__(self, mode: str):
        self.mode = mode
        self._client = None
        self._httpx = None
        self.base = ""
        if mode == "live":
            try:
                from dotenv import load_dotenv
                load_dotenv(ROOT / ".env")
            except Exception:
                pass
            import httpx
            self._httpx = httpx.Client(timeout=90.0)
            self.base = os.getenv("API_BASE", LIVE_BASE).rstrip("/")
        else:
            # izole SQLite — app importundan ÖNCE env (force overwrite)
            qa_db = ROOT / "qa_e2e_scenario.db"
            if qa_db.exists():
                qa_db.unlink()
            os.environ["DATABASE_URL"] = f"sqlite:///{qa_db.as_posix()}"
            os.environ["UPLOAD_DIR"] = str(ROOT / "uploads_e2e")
            os.environ["ENVIRONMENT"] = "qa"
            os.environ["SECRET_KEY"] = "qa-e2e-secret-key-at-least-32-characters-ok"
            os.environ["SEED_ADMIN_EMAIL"] = "demo.eisa@example.com"
            os.environ["SEED_ADMIN_PASSWORD"] = DEMO_PASSWORD
            # .env dosyasını baypas: Settings'i env_file olmadan yükle
            from pydantic_settings import SettingsConfigDict
            from app.core.config import Settings
            import app.core.config as cfg

            class _QaSettings(Settings):
                model_config = SettingsConfigDict(env_file=None, case_sensitive=False)

            cfg.settings = _QaSettings()
            import app.core.database as dbmod
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker

            url = cfg.settings.database_url
            dbmod.engine = create_engine(url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
            dbmod.SessionLocal = sessionmaker(bind=dbmod.engine, autoflush=False, autocommit=False)
            from fastapi.testclient import TestClient
            from app.main import app
            from app.core.database import Base
            Base.metadata.create_all(bind=dbmod.engine)
            from app.services.seed import seed_admin, seed_demo_osgbs
            with dbmod.SessionLocal() as s:
                seed_admin(s)
                try:
                    seed_demo_osgbs(s)
                except Exception:
                    pass
            self._client = TestClient(app, raise_server_exceptions=False)
            self.base = "/api/v1"

    def close(self):
        if self._httpx:
            self._httpx.close()

    def request(self, method: str, path: str, **kwargs):
        url = path if path.startswith("http") else f"{self.base}{path}"
        if self._httpx:
            return self._httpx.request(method, url, **kwargs)
        # TestClient
        headers = kwargs.pop("headers", None)
        json_body = kwargs.pop("json", None)
        files = kwargs.pop("files", None)
        data = kwargs.pop("data", None)
        params = kwargs.pop("params", None)
        return self._client.request(
            method,
            url,
            headers=headers,
            json=json_body,
            files=files,
            data=data,
            params=params,
        )

    def login(self, email: str, password: str) -> str | None:
        r = self.request("POST", "/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            return r.json().get("access_token")
        return None

    def H(self, token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}


def try_ga_login(api: Api) -> tuple[str | None, str]:
    candidates = [
        ("demo.eisa@example.com", DEMO_PASSWORD),
        (os.getenv("SEED_ADMIN_EMAIL") or "", os.getenv("SEED_ADMIN_PASSWORD") or ""),
        ("test.global.admin@example.com", PASS_FALLBACK),
    ]
    for email, pwd in candidates:
        if not email or not pwd:
            continue
        tok = api.login(email, pwd)
        if tok:
            return tok, email
    return None, ""


def ensure_osgbs(api: Api, ga: str) -> list[dict]:
    """2 demo OSGB — yoksa oluştur."""
    specs = [
        {
            "name": "[DEMO_TEST] OSGB Alfa Merkez",
            "authorization_number": "DEMO-OSGB-ALFA-001",
            "tax_number": "1111111111",
            "responsible_manager": "Demo Alfa Mudur",
            "email": "demo.osgb.alfa@example.com",
            "phone": "05551110001",
            "address": "Demo Alfa Adres",
        },
        {
            "name": "[DEMO_TEST] OSGB Beta Merkez",
            "authorization_number": "DEMO-OSGB-BETA-001",
            "tax_number": "2222222222",
            "responsible_manager": "Demo Beta Mudur",
            "email": "demo.osgb.beta@example.com",
            "phone": "05551110002",
            "address": "Demo Beta Adres",
        },
    ]
    r = api.request("GET", "/osgb", headers=api.H(ga))
    rec("SETUP", "OSGB listesi", r.status_code == 200, http=r.status_code, detail=r.text[:120])
    existing = {o.get("name"): o for o in (r.json() or [])} if r.status_code == 200 else {}
    out = []
    for spec in specs:
        if spec["name"] in existing:
            out.append(existing[spec["name"]])
            rec("SETUP", f"OSGB mevcut: {spec['name']}", True)
            continue
        cr = api.request("POST", "/osgb", headers=api.H(ga), json=spec)
        ok = cr.status_code in (200, 201)
        rec("SETUP", f"OSGB oluştur: {spec['name']}", ok, http=cr.status_code, detail=cr.text[:200])
        if ok:
            out.append(cr.json())
        elif spec["name"] in existing:
            out.append(existing[spec["name"]])
    # yeniden listele
    r2 = api.request("GET", "/osgb", headers=api.H(ga))
    by_name = {o.get("name"): o for o in (r2.json() or [])} if r2.status_code == 200 else {}
    final = []
    for spec in specs:
        if spec["name"] in by_name:
            final.append(by_name[spec["name"]])
    return final


def ensure_firms(api: Api, ga: str, osgb: dict) -> list[dict]:
    oid = osgb["id"]
    names = [
        ("[DEMO_TEST] Az Tehlikeli Firma 1", "Az Tehlikeli", "DEMO-SGK-AZ-01"),
        ("[DEMO_TEST] Az Tehlikeli Firma 2", "Az Tehlikeli", "DEMO-SGK-AZ-02"),
        ("[DEMO_TEST] Tehlikeli Firma 1", "Tehlikeli", "DEMO-SGK-TH-01"),
        ("[DEMO_TEST] Tehlikeli Firma 2", "Tehlikeli", "DEMO-SGK-TH-02"),
        ("[DEMO_TEST] Cok Tehlikeli Firma 1", "Çok Tehlikeli", "DEMO-SGK-CK-01"),
        ("[DEMO_TEST] Cok Tehlikeli Firma 2", "Çok Tehlikeli", "DEMO-SGK-CK-02"),
    ]
    # OSGB bağlamı: GA için company create osgb_id ile
    lst = api.request("GET", "/companies", headers=api.H(ga))
    by_name = {c.get("name"): c for c in (lst.json() or [])} if lst.status_code == 200 else {}
    firms = []
    for name, hazard, sgk in names:
        # OSGB adına göre ayırt: Alfa / Beta öneki ekle
        full = name.replace("[DEMO_TEST]", f"[DEMO_TEST][{osgb['name'].split(']')[0].split('[')[-1] if False else ''}]")
        # Daha net: OSGB id'sini isme göm
        full = f"[DEMO_TEST] O{oid} {name.replace('[DEMO_TEST] ', '')}"
        if full in by_name and by_name[full].get("osgb_id") == oid:
            firms.append(by_name[full])
            rec("SETUP", "Firma mevcut", True, firm=full)
            continue
        body = {
            "name": full,
            "sgk_registry_no": f"{sgk}-O{oid}",
            "hazard_class": hazard,
            "address": "Demo senaryo adresi",
            "phone": "05550005555",
            "authorized_person": "Demo Yetkili",
            "osgb_id": oid,
        }
        r = api.request("POST", "/companies", headers=api.H(ga), json=body)
        ok = r.status_code in (200, 201)
        rec("SETUP", f"Firma oluştur ({hazard})", ok, http=r.status_code, detail=r.text[:200], firm=full)
        if ok:
            firms.append(r.json())
            by_name[full] = r.json()
    return firms


def set_password(api: Api, ga: str, user_id: int) -> bool:
    r = api.request("PUT", f"/users/{user_id}", headers=api.H(ga), json={"password": DEMO_PASSWORD})
    return r.status_code in (200, 204)


def ensure_osgb_admin(api: Api, ga: str, osgb: dict) -> tuple[str, str]:
    email = f"demo.osgb.o{osgb['id']}@example.com"
    r = api.request(
        "POST",
        f"/eisa/osgb-users/{osgb['id']}/provision-admin",
        headers=api.H(ga),
        json={"email": email, "full_name": f"[DEMO_TEST] OSGB Admin {osgb['id']}"},
    )
    ok = r.status_code in (200, 201)
    rec("SETUP", "OSGB admin provision", ok, http=r.status_code, detail=r.text[:200])
    uid = None
    if ok:
        uid = r.json().get("user_id")
    if not uid:
        users = api.request("GET", "/users", headers=api.H(ga))
        if users.status_code == 200:
            for u in users.json() or []:
                if str(u.get("email", "")).lower() == email.lower():
                    uid = u["id"]
                    break
    if uid:
        set_password(api, ga, uid)
    tok = api.login(email, DEMO_PASSWORD)
    rec("SETUP", "OSGB admin giriş", bool(tok), detail=email)
    return email, tok or ""


def ensure_professional(
    api: Api,
    ga: str,
    osgb_id: int,
    *,
    email: str,
    full_name: str,
    ptype: str,
) -> tuple[int | None, str | None]:
    lst = api.request("GET", f"/osgb/professionals?osgb_id={osgb_id}", headers=api.H(ga))
    pro_id = None
    if lst.status_code == 200:
        for p in lst.json() or []:
            if str(p.get("email", "")).lower() == email.lower():
                pro_id = p["id"]
                break
    if not pro_id:
        body = {
            "osgb_id": osgb_id,
            "full_name": full_name,
            "email": email,
            "phone": "05550006666",
            "professional_type": ptype,
            "certificate_class": "A" if ptype == "safety_specialist" else None,
            "certificate_number": f"DEMO-{ptype[:3].upper()}-{osgb_id}",
            "certificate_date": "2022-01-01",
        }
        r = api.request("POST", "/osgb/professionals", headers=api.H(ga), json=body)
        ok = r.status_code in (200, 201)
        rec("SETUP", f"Profesyonel oluştur ({ptype})", ok, http=r.status_code, detail=r.text[:200])
        if not ok:
            return None, None
        data = r.json()
        pro_id = data["id"]
        uid = (data.get("login_account") or {}).get("user_id")
    else:
        rec("SETUP", f"Profesyonel mevcut ({ptype})", True)
        uid = None
        users = api.request("GET", "/users", headers=api.H(ga))
        if users.status_code == 200:
            for u in users.json() or []:
                if str(u.get("email", "")).lower() == email.lower():
                    uid = u["id"]
                    break
    if uid:
        set_password(api, ga, uid)
    tok = api.login(email, DEMO_PASSWORD)
    rec("SETUP", f"Profesyonel giriş ({ptype})", bool(tok), detail=email)
    return pro_id, tok


def ensure_assignments(api: Api, ga: str, osgb_id: int, firms: list[dict], pro_id: int, ptype: str):
    for firm in firms:
        cid = firm["id"]
        lst = api.request("GET", f"/osgb/assignments?osgb_id={osgb_id}", headers=api.H(ga))
        has = False
        if lst.status_code == 200:
            for a in lst.json() or []:
                if a.get("professional_id") == pro_id and a.get("company_id") == cid:
                    has = True
                    break
        if has:
            rec("ASSIGN", "Görevlendirme mevcut", True, firm=firm.get("name", ""))
            continue
        body = {
            "osgb_id": osgb_id,
            "company_id": cid,
            "professional_id": pro_id,
            "professional_type": ptype,
            "start_date": "2025-01-01",
            "required_minutes_monthly": 480,
            "planned_minutes_monthly": 480,
            "actual_minutes_monthly": 0,
            "isg_katip_contract_number": f"DEMO-KATIP-{pro_id}-{cid}",
        }
        r = api.request("POST", "/osgb/assignments", headers=api.H(ga), json=body)
        # sözleşme dosyası zorunlu olabilir
        ok = r.status_code in (200, 201)
        detail = r.text[:250]
        if not ok and ("sözleşme" in detail.lower() or "contract" in detail.lower() or r.status_code == 422):
            # yine de kaydetmeyi denedik
            rec("ASSIGN", "Görevlendirme (sözleşme kısıtı?)", False, http=r.status_code, detail=detail, firm=firm.get("name", ""))
        else:
            rec("ASSIGN", "Görevlendirme oluştur", ok, http=r.status_code, detail=detail, firm=firm.get("name", ""))


def run_uzman_ops(api: Api, token: str, firm: dict):
    """İş güvenliği uzmanı — atandığı firma için tüm ana işlemler."""
    cid = firm["id"]
    fname = firm.get("name") or str(cid)
    H = api.H(token)

    # Personel
    emp_id = None
    r = api.request(
        "POST",
        "/employees",
        headers=H,
        json={
            "company_id": cid,
            "full_name": "Demo Senaryo Calisan",
            "job_title": "Operator",
            "department": "Uretim",
        },
    )
    ok = r.status_code in (200, 201)
    if ok:
        emp_id = r.json().get("id")
    rec("UZMAN", "Personel ekle", ok, http=r.status_code, detail=r.text[:180], firm=fname)

    # Risk library + risk
    api.request("POST", "/risks/seed-library", headers=H)
    meta = api.request("GET", "/risks/meta", headers=H)
    hid = 1
    if meta.status_code == 200:
        data = meta.json() or {}
        hazards = data.get("hazards") or data.get("hazard_library") or []
        if isinstance(hazards, list) and hazards and isinstance(hazards[0], dict):
            hid = hazards[0].get("id") or 1
    r = api.request(
        "POST",
        "/risks",
        headers=H,
        json={
            "company_id": cid,
            "department_name": "Uretim",
            "hazard_id": hid,
            "activity": "Demo kesme ve montaj isi",
            "risk_definition": "Demo senaryo kayma dusme riski tanimi",
            "probability": 2,
            "severity": 3,
            "status": "Açık",
        },
    )
    rec("UZMAN", "Risk analizi kaydı", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)

    # Ramak kala
    r = api.request(
        "POST",
        "/incidents",
        headers=H,
        json={
            "company_id": cid,
            "event_type": "ramak_kala",
            "short_summary": "Demo ramak kala ozeti — yeterli uzunlukta metin",
            "event_date": str(today_utc()),
            "location": "Atolye alani",
            "detail": "Demo senaryo detay metni — olayin nasil gelistigini anlatan en az otuz karakter.",
            "classification": "Düşme / kayma / takılma",
            "would_have_injured": True,
            "probability": 3,
            "severity": 3,
            "safety_specialist": "Demo Uzman",
            "employer_representative": "Demo Yetkili",
        },
    )
    rec("UZMAN", "Ramak kala kaydı", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)

    # İş kazası
    r = api.request(
        "POST",
        "/incidents",
        headers=H,
        json={
            "company_id": cid,
            "event_type": "is_kazasi",
            "short_summary": "Demo is kazasi ozeti — yeterli uzunlukta metin",
            "event_date": str(today_utc()),
            "location": "Montaj hatti",
            "detail": "Demo senaryo is kazasi detayi — yaralanma olmamistir, raporlanmistir ve kayda alinmistir.",
            "classification": "Düşme / kayma / takılma",
            "injury_occurred": False,
            "probability": 2,
            "severity": 2,
            "safety_specialist": "Demo Uzman",
            "employer_representative": "Demo Yetkili",
        },
    )
    rec("UZMAN", "İş kazası kaydı", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)

    # PPE
    cat = api.request("GET", "/ppe/catalog", headers=H)
    item_id = None
    if cat.status_code == 200:
        items = cat.json() if isinstance(cat.json(), list) else (cat.json() or {}).get("items") or []
        if items and isinstance(items[0], dict):
            item_id = items[0].get("id")
    if emp_id and item_id:
        r = api.request(
            "POST",
            "/ppe/assignments",
            headers=H,
            json={
                "company_id": cid,
                "employee_id": emp_id,
                "catalog_item_id": item_id,
                "assigned_date": str(today_utc()),
                "quantity": 1,
            },
        )
        rec("UZMAN", "KKD zimmet", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)
    else:
        pl = api.request("GET", f"/ppe/assignments?company_id={cid}", headers=H)
        rec("UZMAN", "KKD liste (katalog/personel yoksa)", pl.status_code == 200, http=pl.status_code, firm=fname)

    # Eğitim
    start = today_utc() + timedelta(days=14)
    end = start + timedelta(days=1)
    hazard = firm.get("hazard_class") or "Tehlikeli"
    # saat kuralları: az 8->1 gün, teh 12->2 gün, cok 16->2 gün
    if "Çok" in hazard or "Cok" in hazard:
        end = start + timedelta(days=1)
    elif hazard == "Tehlikeli":
        end = start + timedelta(days=1)
    r = api.request(
        "POST",
        "/trainings",
        headers=H,
        json={
            "company_id": cid,
            "title": f"Demo Temel ISG Egitimi {cid}",
            "start_date": str(start),
            "end_date": str(end),
            "hazard_class": hazard if hazard in ("Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli") else "Tehlikeli",
            "instructor_name": "Demo Egitmen Uzman",
            "participant_ids": [emp_id] if emp_id else [],
        },
    )
    # katılımcı yoksa 422 beklenir — o zaman personel zorunlu
    if r.status_code == 422 and not emp_id:
        rec("UZMAN", "Eğitim (personel yok — atlandı)", False, http=r.status_code, detail=r.text[:180], firm=fname)
    else:
        rec("UZMAN", "Eğitim kaydı", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)

    # Yıllık plan
    r = api.request(
        "POST",
        "/annual-plans/generate",
        headers=H,
        json={"company_id": cid, "year": today_utc().year},
    )
    if r.status_code == 422:
        r = api.request(
            "POST",
            f"/annual-plans/generate?company_id={cid}&year={today_utc().year}",
            headers=H,
        )
    rec("UZMAN", "Yıllık plan üret", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)

    # Doküman
    r = api.request(
        "POST",
        "/documents",
        headers=H,
        json={
            "company_id": cid,
            "category": "general",
            "title": "Demo senaryo dokuman kaydi",
            "file_name": "demo-dokuman.pdf",
            "description": "E2E senaryo",
            "version": "1.0",
        },
    )
    rec("UZMAN", "Doküman kaydı", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)

    # Saha ziyareti (+ notebook)
    r = api.request(
        "POST",
        "/operations/visits",
        headers=H,
        json={
            "osgb_id": firm.get("osgb_id"),
            "company_id": cid,
            "visit_date": str(today_utc()),
            "start_time": "09:00",
            "end_time": "12:00",
            "duration_minutes": 180,
            "subject": "Demo periyodik saha ziyareti",
            "notes": "E2E senaryo ziyaret notu",
        },
    )
    ok = r.status_code in (200, 201)
    rec("UZMAN", "Saha ziyareti oluştur", ok, http=r.status_code, detail=r.text[:180], firm=fname)
    if ok:
        vid = r.json().get("id")
        # minimal pdf bytes
        pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        files = {"file": ("tespit.pdf", BytesIO(pdf), "application/pdf")}
        up = api.request("POST", f"/operations/visits/{vid}/notebook", headers=H, files=files)
        rec("UZMAN", "Tespit öneri defteri yükle", up.status_code in (200, 201), http=up.status_code, detail=up.text[:180], firm=fname)

    # Duty board
    d = api.request("GET", "/dashboard/my-duties", headers=H)
    rec("UZMAN", "Görev panosu", d.status_code == 200, http=d.status_code, detail=d.text[:120], firm=fname)


def run_hekim_ops(api: Api, token: str, firm: dict):
    cid = firm["id"]
    fname = firm.get("name") or str(cid)
    H = api.H(token)

    # personel (hekim de ekleyebilir)
    r = api.request(
        "POST",
        "/employees",
        headers=H,
        json={
            "company_id": cid,
            "full_name": "Demo Senaryo Saglik Personeli",
            "job_title": "Teknisyen",
            "department": "Bakim",
        },
    )
    emp_id = r.json().get("id") if r.status_code in (200, 201) else None
    rec("HEKIM", "Personel ekle", r.status_code in (200, 201), http=r.status_code, detail=r.text[:160], firm=fname)

    if not emp_id:
        lst = api.request("GET", f"/employees?company_id={cid}", headers=H)
        if lst.status_code == 200 and lst.json():
            emp_id = lst.json()[0].get("id")

    if emp_id:
        r = api.request(
            "POST",
            "/health-records",
            headers=H,
            json={
                "company_id": cid,
                "employee_id": emp_id,
                "record_type": "periodic_exam",
                "examination_date": str(today_utc()),
                "fitness_status": "fit",
                "physician_name": "Demo Hekim",
                "summary": "Demo periyodik muayene ozeti uygun",
            },
        )
        rec("HEKIM", "Sağlık kaydı", r.status_code in (200, 201), http=r.status_code, detail=r.text[:180], firm=fname)
    else:
        rec("HEKIM", "Sağlık kaydı", False, detail="Personel yok", firm=fname)

    # yıllık plan hekim de üretebilir
    r = api.request(
        "POST",
        "/annual-plans/generate",
        headers=H,
        json={"company_id": cid, "year": today_utc().year},
    )
    rec("HEKIM", "Yıllık plan üret", r.status_code in (200, 201), http=r.status_code, detail=r.text[:160], firm=fname)

    # ziyaret
    r = api.request(
        "POST",
        "/operations/visits",
        headers=H,
        json={
            "osgb_id": firm.get("osgb_id"),
            "company_id": cid,
            "visit_date": str(today_utc()),
            "start_time": "13:00",
            "end_time": "15:00",
            "duration_minutes": 120,
            "subject": "Demo hekim saha ziyareti",
            "notes": "E2E hekim ziyaret notu",
        },
    )
    ok = r.status_code in (200, 201)
    rec("HEKIM", "Saha ziyareti", ok, http=r.status_code, detail=r.text[:160], firm=fname)
    if ok:
        vid = r.json().get("id")
        pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
        up = api.request(
            "POST",
            f"/operations/visits/{vid}/notebook",
            headers=H,
            files={"file": ("tespit.pdf", BytesIO(pdf), "application/pdf")},
        )
        rec("HEKIM", "Tespit defteri", up.status_code in (200, 201), http=up.status_code, detail=up.text[:160], firm=fname)

    d = api.request("GET", "/dashboard/my-duties", headers=H)
    rec("HEKIM", "Görev panosu", d.status_code == 200, http=d.status_code, firm=fname)


def write_reports():
    out_dir = REPO / "docs" / "qa" / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    passed = sum(1 for x in REPORT if x["ok"])
    failed = sum(1 for x in REPORT if not x["ok"])
    summary = {
        "passed": passed,
        "failed": failed,
        "total": len(REPORT),
        "results": REPORT,
        "errors": [x for x in REPORT if not x["ok"]],
    }
    (out_dir / "e2e-scenario-report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "İSG Suite — E2E Senaryo Raporu",
        f"Tarih: {date.today().isoformat()}",
        f"Özet: {passed}/{len(REPORT)} geçti, {failed} hata",
        "",
        "=== HATALAR (madde madde) ===",
    ]
    if not summary["errors"]:
        lines.append("Hata yok. Tüm adımlar geçti.")
    else:
        for i, e in enumerate(summary["errors"], 1):
            lines.append(
                f"{i}. [{e['phase']}] {e['step']}"
                + (f" | Firma: {e['firm']}" if e.get("firm") else "")
                + (f" | HTTP {e['http']}" if e.get("http") is not None else "")
                + (f" | {e['detail']}" if e.get("detail") else "")
            )
    lines.append("")
    lines.append("=== TÜM ADIMLAR ===")
    for i, e in enumerate(REPORT, 1):
        lines.append(
            f"{i}. {'OK' if e['ok'] else 'HATA'} | {e['phase']} | {e['step']}"
            + (f" | {e['firm']}" if e.get("firm") else "")
        )
    txt = "\n".join(lines) + "\n"
    (out_dir / "e2e-scenario-report.txt").write_text(txt, encoding="utf-8")
    print("\n" + txt)
    print(f"JSON: {out_dir / 'e2e-scenario-report.json'}")
    return 0 if failed == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Canlı API (Render)")
    parser.add_argument("--local", action="store_true", help="Yerel TestClient (varsayılan)")
    args = parser.parse_args()
    mode = "live" if args.live else "local"

    api = Api(mode)
    try:
        ga, who = try_ga_login(api)
        rec("AUTH", f"EİSA giriş ({who or 'yok'})", bool(ga))
        if not ga:
            write_reports()
            return 2

        osgbs = ensure_osgbs(api, ga)
        if len(osgbs) < 1:
            rec("SETUP", "En az 1 OSGB gerekli", False)
            return write_reports()

        for osgb in osgbs[:2]:
            firms = ensure_firms(api, ga, osgb)
            email_admin, admin_tok = ensure_osgb_admin(api, ga, osgb)
            _ = email_admin, admin_tok

            uzman_email = f"demo.uzman.o{osgb['id']}@example.com"
            hekim_email = f"demo.hekim.o{osgb['id']}@example.com"
            uzman_pro, uzman_tok = ensure_professional(
                api, ga, osgb["id"],
                email=uzman_email,
                full_name="Demo Senaryo Is Guvenligi Uzmani",
                ptype="safety_specialist",
            )
            hekim_pro, hekim_tok = ensure_professional(
                api, ga, osgb["id"],
                email=hekim_email,
                full_name="Demo Senaryo Isyeri Hekimi",
                ptype="workplace_physician",
            )

            if uzman_pro:
                ensure_assignments(api, ga, osgb["id"], firms, uzman_pro, "safety_specialist")
            if hekim_pro:
                ensure_assignments(api, ga, osgb["id"], firms, hekim_pro, "workplace_physician")

            api.request("POST", "/osgb/sync-field-roles", headers=api.H(ga))

            if uzman_tok:
                for firm in firms:
                    run_uzman_ops(api, uzman_tok, firm)
            else:
                rec("UZMAN", "Token yok — firma işlemleri atlandı", False)

            if hekim_tok:
                for firm in firms:
                    run_hekim_ops(api, hekim_tok, firm)
            else:
                rec("HEKIM", "Token yok — firma işlemleri atlandı", False)

            ov = api.request("GET", f"/osgb/oversight?osgb_id={osgb['id']}", headers=api.H(ga))
            rec("OSGB", "Hizmet denetimi", ov.status_code == 200, http=ov.status_code, detail=ov.text[:120])

        return write_reports()
    finally:
        api.close()


if __name__ == "__main__":
    raise SystemExit(main())
