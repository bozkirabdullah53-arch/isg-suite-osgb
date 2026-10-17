"""ISG özet PDF'i, kayıt başlıklarındaki Türkçe harfleri (Ş, Ğ, ı, İ) bozmadan yazmalı."""
from io import BytesIO

from pypdf import PdfReader

from test_faz0_security import client  # noqa: F401  (paylaşılan istemci ve tohum veri)


def test_isg_summary_pdf_keeps_turkish_letters_in_record_titles(client):
    import app.core.database as dbmod
    from app.core.security import create_access_token, get_password_hash
    from app.models.entities import Employee, IsgModule, IsgRecord, RecordStatus, User, UserRole

    # Özet dışa aktarımı yalnızca yönetici rollerine açıktır. Yönetici girişi MFA kurulumuna
    # yönlendirdiği için burada tam erişim jetonu doğrudan üretilir.
    title = "Şğıİ İŞ KAZASI"
    with dbmod.SessionLocal() as db:
        employee = db.query(Employee).first()
        admin = User(
            email="pdf-admin@example.com",
            full_name="PDF Yönetici",
            hashed_password=get_password_hash("PdfAdmin123!"),
            role=UserRole.GLOBAL_ADMIN,
            is_active=True,
        )
        db.add(admin)
        db.flush()
        admin_id = admin.id
        db.add(
            IsgRecord(
                company_id=employee.company_id,
                module=IsgModule.RISK,
                title=title,
                status=RecordStatus.OPEN,
                created_by_id=admin_id,
            )
        )
        db.commit()

    token = create_access_token(str(admin_id))
    result = client.get("/api/v1/exports/isg-summary.pdf", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 200

    text = PdfReader(BytesIO(result.content)).pages[0].extract_text()
    assert "Şğıİ" in text
