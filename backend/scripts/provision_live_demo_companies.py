"""
Canlıda 6 demo test işyeri oluşturur:
  2× Az Tehlikeli, 2× Tehlikeli, 2× Çok Tehlikeli

Giriş sırası: DEMO hesapları → SEED_ADMIN (.env)

  python scripts/provision_live_demo_companies.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

BASE = os.getenv("API_BASE", "https://isg-suite-api-1u9t.onrender.com/api/v1").rstrip("/")
DEMO_PASSWORD = "DemoIsgSuite2026!"

LOGIN_CANDIDATES = [
    ("demo.eisa@example.com", DEMO_PASSWORD),
    ("demo.osgb@example.com", DEMO_PASSWORD),
    (os.getenv("SEED_ADMIN_EMAIL") or "", os.getenv("SEED_ADMIN_PASSWORD") or ""),
]

FIRMS = [
    ("[DEMO_TEST] Az Tehlikeli Firma 1", "Az Tehlikeli", "DEMO-SGK-AZ-01"),
    ("[DEMO_TEST] Az Tehlikeli Firma 2", "Az Tehlikeli", "DEMO-SGK-AZ-02"),
    ("[DEMO_TEST] Tehlikeli Firma 1", "Tehlikeli", "DEMO-SGK-TH-01"),
    ("[DEMO_TEST] Tehlikeli Firma 2", "Tehlikeli", "DEMO-SGK-TH-02"),
    ("[DEMO_TEST] Çok Tehlikeli Firma 1", "Çok Tehlikeli", "DEMO-SGK-CK-01"),
    ("[DEMO_TEST] Çok Tehlikeli Firma 2", "Çok Tehlikeli", "DEMO-SGK-CK-02"),
]


def login(client: httpx.Client) -> tuple[str, str]:
    for email, password in LOGIN_CANDIDATES:
        email = (email or "").strip()
        password = password or ""
        if not email or not password:
            continue
        r = client.post(f"{BASE}/auth/login", json={"email": email, "password": password})
        if r.status_code == 200:
            return r.json()["access_token"], email
    raise SystemExit(
        "Canlıya giriş başarısız. Önce demo test kullanıcıları oluşturulmalı "
        "(EİSA admin bilgisi gerekir) veya SEED_ADMIN canlı şifresi güncellenmeli."
    )


def main() -> int:
    with httpx.Client(timeout=60.0) as client:
        token, who = login(client)
        h = {"Authorization": f"Bearer {token}"}
        me = client.get(f"{BASE}/auth/me", headers=h).json()
        print(f"Giriş: {who} ({me.get('role')})")

        osgb_id = me.get("osgb_id")
        if not osgb_id:
            r = client.get(f"{BASE}/osgb", headers=h)
            if r.status_code != 200 or not r.json():
                raise SystemExit(f"OSGB listesi alınamadı: {r.status_code}")
            active = [o for o in r.json() if o.get("is_active", True)]
            osgb_id = (active or r.json())[0]["id"]
        print(f"OSGB: #{osgb_id}")

        existing = client.get(f"{BASE}/companies", headers=h)
        by_name = {}
        if existing.status_code == 200:
            by_name = {c.get("name"): c for c in existing.json() or []}

        created = []
        for name, hazard, sgk in FIRMS:
            if name in by_name:
                row = by_name[name]
                created.append({"id": row["id"], "name": name, "hazard_class": hazard, "status": "exists"})
                print(f"VAR  {name}")
                continue
            body = {
                "name": name,
                "sgk_registry_no": sgk,
                "hazard_class": hazard,
                "address": "Demo test adresi",
                "phone": "05550004444",
                "authorized_person": "Demo Yetkili",
                "osgb_id": osgb_id,
            }
            r = client.post(f"{BASE}/companies", headers=h, json=body)
            if r.status_code not in (200, 201):
                print(f"HATA {name}: {r.status_code} {r.text[:250]}")
                created.append({"name": name, "hazard_class": hazard, "status": "error", "detail": r.text[:250]})
                continue
            row = r.json()
            created.append({"id": row.get("id"), "name": name, "hazard_class": hazard, "status": "created"})
            print(f"OK   {name} (#{row.get('id')})")

        out = {"osgb_id": osgb_id, "companies": created}
        path = ROOT / "scripts" / "demo_companies.json"
        path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Kaydedildi: {path}")
        ok = sum(1 for c in created if c.get("status") in ("created", "exists"))
        print(f"Toplam hazır: {ok}/6")
        return 0 if ok == 6 else 2


if __name__ == "__main__":
    raise SystemExit(main())
