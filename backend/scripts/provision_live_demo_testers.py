"""
Canlı (veya verilen) API üzerinde 4 demo test hesabı oluşturur / şifreyi sabitler.

Gerekli: SEED_ADMIN_EMAIL + SEED_ADMIN_PASSWORD (.env) — EİSA yetkisiyle giriş.

  python scripts/provision_live_demo_testers.py
  python scripts/provision_live_demo_testers.py --base https://isg-suite-api-1u9t.onrender.com/api/v1
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# .env yükle
try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except Exception:
    pass

DEMO_PASSWORD = "DemoIsgSuite2026!"
DEFAULT_BASE = "https://isg-suite-api-1u9t.onrender.com/api/v1"

ACCOUNTS = {
    "eisa": {
        "email": "demo.eisa@example.com",
        "full_name": "[DEMO_TEST] EİSA Global Yönetici",
        "role": "global_admin",
    },
    "osgb": {
        "email": "demo.osgb@example.com",
        "full_name": "[DEMO_TEST] OSGB Yöneticisi",
        "role": "company_admin",
    },
    "uzman": {
        "email": "demo.uzman@example.com",
        "full_name": "[DEMO_TEST] İş Güvenliği Uzmanı",
        "role": "safety_specialist",
        "professional_type": "safety_specialist",
    },
    "hekim": {
        "email": "demo.hekim@example.com",
        "full_name": "[DEMO_TEST] İşyeri Hekimi",
        "role": "workplace_physician",
        "professional_type": "workplace_physician",
    },
}


def login(client: httpx.Client, base: str, email: str, password: str) -> str:
    r = client.post(f"{base}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        raise SystemExit(f"EİSA girişi başarısız ({r.status_code}): {r.text[:300]}")
    return r.json()["access_token"]


def headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def find_user_id(client: httpx.Client, base: str, token: str, email: str) -> int | None:
    r = client.get(f"{base}/users", headers=headers(token))
    if r.status_code != 200:
        return None
    for u in r.json() or []:
        if str(u.get("email", "")).lower() == email.lower():
            return u.get("id")
    return None


def set_password(client: httpx.Client, base: str, token: str, user_id: int, password: str) -> None:
    r = client.put(
        f"{base}/users/{user_id}",
        headers=headers(token),
        json={"password": password},
    )
    if r.status_code not in (200, 204):
        raise RuntimeError(f"Şifre atanamadı user#{user_id}: {r.status_code} {r.text[:200]}")


def ensure_eisa(client: httpx.Client, base: str, token: str) -> int:
    email = ACCOUNTS["eisa"]["email"]
    uid = find_user_id(client, base, token, email)
    if uid:
        set_password(client, base, token, uid, DEMO_PASSWORD)
        return uid
    r = client.post(
        f"{base}/users",
        headers=headers(token),
        json={
            "email": email,
            "full_name": ACCOUNTS["eisa"]["full_name"],
            "password": DEMO_PASSWORD,
            "role": "global_admin",
        },
    )
    if r.status_code not in (200, 201):
        raise RuntimeError(f"EİSA kullanıcı oluşturulamadı: {r.status_code} {r.text[:300]}")
    return r.json()["id"]


def pick_osgb(client: httpx.Client, base: str, token: str) -> dict:
    r = client.get(f"{base}/osgb", headers=headers(token))
    if r.status_code != 200 or not r.json():
        raise RuntimeError(f"OSGB listesi alınamadı: {r.status_code} {r.text[:200]}")
    rows = r.json()
    active = [o for o in rows if o.get("is_active", True)]
    return (active or rows)[0]


def ensure_osgb_admin(client: httpx.Client, base: str, token: str, osgb_id: int) -> int:
    email = ACCOUNTS["osgb"]["email"]
    r = client.post(
        f"{base}/eisa/osgb-users/{osgb_id}/provision-admin",
        headers=headers(token),
        json={"email": email, "full_name": ACCOUNTS["osgb"]["full_name"]},
    )
    if r.status_code not in (200, 201):
        # belki eisa prefix farklı
        raise RuntimeError(f"OSGB admin provision başarısız: {r.status_code} {r.text[:400]}")
    data = r.json()
    uid = data.get("user_id") or find_user_id(client, base, token, email)
    if not uid:
        raise RuntimeError("OSGB admin user_id bulunamadı.")
    set_password(client, base, token, uid, DEMO_PASSWORD)
    return uid


def ensure_company(client: httpx.Client, base: str, token: str, osgb_id: int) -> int:
    r = client.get(f"{base}/companies", headers=headers(token))
    if r.status_code == 200:
        for c in r.json() or []:
            if c.get("osgb_id") == osgb_id and c.get("is_active", True):
                return c["id"]
            if str(c.get("name", "")).startswith("[DEMO_TEST]"):
                return c["id"]
    # oluştur
    body = {
        "name": "[DEMO_TEST] Demo İşyeri",
        "sgk_registry_no": "DEMO-SGK-001",
        "hazard_class": "Tehlikeli",
        "address": "Demo Adres",
        "phone": "05550002222",
        "authorized_person": "Demo Yetkili",
        "osgb_id": osgb_id,
    }
    r = client.post(f"{base}/companies", headers=headers(token), json=body)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"İşyeri oluşturulamadı: {r.status_code} {r.text[:300]}")
    return r.json()["id"]


def ensure_professional(
    client: httpx.Client,
    base: str,
    token: str,
    *,
    osgb_id: int,
    company_id: int,
    email: str,
    full_name: str,
    professional_type: str,
) -> int:
    # mevcut?
    r = client.get(f"{base}/osgb/professionals?osgb_id={osgb_id}", headers=headers(token))
    pro_id = None
    if r.status_code == 200:
        for p in r.json() or []:
            if str(p.get("email", "")).lower() == email.lower():
                pro_id = p["id"]
                break
    if not pro_id:
        body = {
            "osgb_id": osgb_id,
            "full_name": full_name,
            "email": email,
            "phone": "05550003333",
            "professional_type": professional_type,
            "certificate_class": "A" if professional_type == "safety_specialist" else None,
            "certificate_number": f"DEMO-{professional_type[:3].upper()}-001",
            "certificate_date": "2022-01-01",
        }
        r = client.post(f"{base}/osgb/professionals", headers=headers(token), json=body)
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Profesyonel oluşturulamadı ({email}): {r.status_code} {r.text[:400]}")
        data = r.json()
        pro_id = data["id"]
        # login_account varsa user_id ile şifre sabitle
        login = data.get("login_account") or {}
        uid = login.get("user_id") or find_user_id(client, base, token, email)
    else:
        uid = find_user_id(client, base, token, email)

    if not uid:
        raise RuntimeError(f"Kullanıcı bulunamadı: {email}")
    set_password(client, base, token, uid, DEMO_PASSWORD)

    # görevlendirme
    r = client.get(f"{base}/osgb/assignments?osgb_id={osgb_id}", headers=headers(token))
    has = False
    if r.status_code == 200:
        for a in r.json() or []:
            if a.get("professional_id") == pro_id and a.get("company_id") == company_id:
                if a.get("status") in (None, "active", "ACTIVE"):
                    has = True
                    break
    if not has:
        body = {
            "osgb_id": osgb_id,
            "company_id": company_id,
            "professional_id": pro_id,
            "professional_type": professional_type,
            "start_date": "2025-01-01",
            "required_minutes_monthly": 480,
            "planned_minutes_monthly": 480,
            "actual_minutes_monthly": 0,
            "isg_katip_contract_number": f"DEMO-KATIP-{pro_id}",
        }
        r = client.post(f"{base}/osgb/assignments", headers=headers(token), json=body)
        # 409 / validation olabilir — kritik değil
        if r.status_code not in (200, 201, 409):
            print(f"UYARI görevlendirme: {email} -> {r.status_code} {r.text[:180]}")
    return uid


def verify_login(client: httpx.Client, base: str, email: str) -> bool:
    r = client.post(f"{base}/auth/login", json={"email": email, "password": DEMO_PASSWORD})
    return r.status_code == 200


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=os.getenv("API_BASE", DEFAULT_BASE))
    args = parser.parse_args()
    base = args.base.rstrip("/")

    admin_email = (os.getenv("SEED_ADMIN_EMAIL") or "").strip()
    admin_password = os.getenv("SEED_ADMIN_PASSWORD") or ""
    if not admin_email or not admin_password:
        print("SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD .env içinde gerekli.")
        return 1

    with httpx.Client(timeout=60.0) as client:
        token = login(client, base, admin_email, admin_password)
        me = client.get(f"{base}/auth/me", headers=headers(token))
        if me.status_code != 200 or me.json().get("role") != "global_admin":
            print("Giriş yapılan hesap global_admin değil.")
            return 1

        results = []
        eisa_id = ensure_eisa(client, base, token)
        results.append(("EİSA Yönetici", ACCOUNTS["eisa"]["email"], eisa_id))

        osgb = pick_osgb(client, base, token)
        osgb_id = osgb["id"]
        print(f"OSGB seçildi: #{osgb_id} {osgb.get('name')}")

        osgb_admin_id = ensure_osgb_admin(client, base, token, osgb_id)
        results.append(("OSGB Yöneticisi", ACCOUNTS["osgb"]["email"], osgb_admin_id))

        company_id = ensure_company(client, base, token, osgb_id)
        print(f"İşyeri: #{company_id}")

        for key in ("uzman", "hekim"):
            acc = ACCOUNTS[key]
            uid = ensure_professional(
                client,
                base,
                token,
                osgb_id=osgb_id,
                company_id=company_id,
                email=acc["email"],
                full_name=acc["full_name"],
                professional_type=acc["professional_type"],
            )
            label = "İş Güvenliği Uzmanı" if key == "uzman" else "İşyeri Hekimi"
            results.append((label, acc["email"], uid))

        print("\n=== DEMO TEST HESAPLARI ===")
        print(f"Şifre (hepsi): {DEMO_PASSWORD}")
        print("---")
        ok_all = True
        for label, email, uid in results:
            ok = verify_login(client, base, email)
            ok_all = ok_all and ok
            print(f"{'OK' if ok else 'FAIL'}  {label}")
            print(f"     E-posta: {email}")
            print(f"     Şifre  : {DEMO_PASSWORD}")
            print(f"     user_id: {uid}")
        print("---")
        out = {
            "password": DEMO_PASSWORD,
            "accounts": [
                {"role": r[0], "email": r[1], "user_id": r[2]} for r in results
            ],
            "osgb_id": osgb_id,
            "company_id": company_id,
        }
        out_path = ROOT / "scripts" / "demo_testers.json"
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Kaydedildi: {out_path}")
        return 0 if ok_all else 2


if __name__ == "__main__":
    raise SystemExit(main())
