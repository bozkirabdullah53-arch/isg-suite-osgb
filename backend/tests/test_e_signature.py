"""E-imza profili: yükleme, durum, silme, köprü probe."""
from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture()
def client(tmp_path, monkeypatch):
    db_file = tmp_path / "e_signature.db"
    url = f"sqlite:///{db_file.as_posix()}"
    upload = tmp_path / "uploads"
    upload.mkdir()
    monkeypatch.setenv("DATABASE_URL", url)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-at-least-32-chars-long!!")
    monkeypatch.setenv("UPLOAD_DIR", str(upload))
    monkeypatch.delenv("E_SIGN_BRIDGE_URL", raising=False)
    monkeypatch.setattr("app.api.auth.role_requires_mfa", lambda _role: False)

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    import app.core.database as dbmod
    import app.models.entities as ent
    from app.core.config import settings

    settings.database_url = url
    settings.secret_key = "test-secret-key-at-least-32-chars-long!!"
    settings.environment = "development"
    settings.upload_dir = str(upload)
    settings.e_sign_bridge_url = None
    settings.upload_gateway_enabled = False

    engine = create_engine(url, connect_args={"check_same_thread": False})
    dbmod.engine = engine
    dbmod.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    ent.Base.metadata.create_all(bind=engine)

    from app.main import app

    return TestClient(app)


def _png_bytes(w=120, h=40) -> bytes:
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for x in range(10, w - 10):
        y = int(h / 2 + 8 * ((x % 20) / 10 - 1))
        if 0 <= y < h:
            img.putpixel((x, y), (20, 40, 80, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _seed_and_login(client: TestClient) -> dict:
    from app.core.database import SessionLocal
    from app.core.security import get_password_hash
    from app.models.entities import OsgbOrganization, User, UserRole

    with SessionLocal() as db:
        osgb = OsgbOrganization(
            name="ESign OSGB",
            authorization_number="YETKI-ES-1",
            tax_number="9988776655",
            responsible_manager="ESign Yonetici",
            email="esign-osgb@test.com",
            phone="02121110000",
            address="Istanbul",
            is_active=True,
        )
        db.add(osgb)
        db.flush()
        db.add(
            User(
                email="esign-admin@test.com",
                full_name="ESign Admin",
                hashed_password=get_password_hash("TestPass123!"),
                role=UserRole.COMPANY_ADMIN,
                osgb_id=osgb.id,
                is_active=True,
            )
        )
        db.commit()

    r = client.post(
        "/api/v1/auth/login",
        json={"email": "esign-admin@test.com", "password": "TestPass123!"},
    )
    assert r.status_code == 200, r.text
    token = r.json().get("access_token")
    assert token
    return {"Authorization": f"Bearer {token}"}


def test_e_signature_upload_status_delete(client):
    headers = _seed_and_login(client)

    st = client.get("/api/v1/security/e-signature", headers=headers)
    assert st.status_code == 200
    assert st.json()["has_image"] is False

    png = _png_bytes()
    up = client.post(
        "/api/v1/security/e-signature/image",
        headers=headers,
        files={"file": ("imza.png", png, "image/png")},
    )
    assert up.status_code == 200, up.text
    assert up.json()["has_image"] is True

    img = client.get("/api/v1/security/e-signature/image", headers=headers)
    assert img.status_code == 200
    assert img.headers["content-type"].startswith("image/")
    assert len(img.content) > 64

    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["e_signature_has_image"] is True

    title = client.put(
        "/api/v1/security/e-signature/title",
        headers=headers,
        json={"title": "İş Güvenliği Uzmanı"},
    )
    assert title.status_code == 200
    assert title.json()["title"] == "İş Güvenliği Uzmanı"

    probe = client.post("/api/v1/security/e-signature/bridge-probe", headers=headers)
    assert probe.status_code == 200
    assert probe.json()["probe"]["status"] == "not_configured"

    dl = client.delete("/api/v1/security/e-signature/image", headers=headers)
    assert dl.status_code == 200
    assert dl.json()["has_image"] is False


def _scanned_jpeg(w=400, h=300) -> bytes:
    """Beyaz zeminli, ortada küçük mürekkep olan tarama benzeri görsel."""
    img = Image.new("RGB", (w, h), (253, 253, 251))
    for x in range(160, 240):
        img.putpixel((x, 150), (18, 36, 74))
        img.putpixel((x, 151), (18, 36, 74))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return buf.getvalue()


def test_prepared_preview_trims_paper_background(client):
    """Beyaz zemin şeffaflaşır ve kadraj mürekkebe kırpılır (PDF'te kutuya oturur)."""
    headers = _seed_and_login(client)
    up = client.post(
        "/api/v1/security/e-signature/image",
        headers=headers,
        files={"file": ("imza.jpg", _scanned_jpeg(), "image/jpeg")},
    )
    assert up.status_code == 200, up.text

    raw = client.get("/api/v1/security/e-signature/image", headers=headers)
    assert raw.status_code == 200
    assert Image.open(io.BytesIO(raw.content)).size == (400, 300)

    prepared = client.get("/api/v1/security/e-signature/image?prepared=1", headers=headers)
    assert prepared.status_code == 200
    assert prepared.headers["content-type"] == "image/png"
    img = Image.open(io.BytesIO(prepared.content))
    assert img.mode == "RGBA"
    assert img.width < 400 and img.height < 300  # boş kenarlar kırpıldı
    corner = img.getpixel((0, 0))
    assert corner[3] == 0  # kâğıt zemini şeffaf


def test_pdf_layout_reserves_signature_band():
    """İmza görseli, kutudaki ad-soyad ve alt etiketle çakışmamalı."""
    from reportlab.lib.units import mm

    from app.services.e_signature import draw_signature_image

    placed: list[dict] = []

    class FakeCanvas:
        def drawImage(self, img, x, y, width=None, height=None, **kw):
            placed.append({"x": x, "y": y, "w": width, "h": height})

    ok = draw_signature_image(
        FakeCanvas(),
        image_bytes=_png_bytes(600, 180),
        x=10 * mm,
        y=18.2 * mm,
        max_w=70 * mm,
        max_h=8.5 * mm,
    )
    assert ok and placed
    box = placed[0]
    top = box["y"] + box["h"]
    assert top <= 26.7 * mm + 0.01  # ad-soyad satırının (28mm) altında kalır
    assert box["y"] >= 17.5 * mm  # alt etiketin (15.5mm) üstünde kalır
