from __future__ import annotations

from datetime import date
from io import BytesIO

from pypdf import PdfReader

from app.api.committee_professional import MANDATORY, ROLE_LABELS, _candidate_key, _normalize
from app.services.committee_meeting_pdf import build_committee_meeting_pdf


def test_identity_key_is_source_and_workplace_bound():
    assert _candidate_key("employee", 7, 12) == "employee:12:7"
    assert _candidate_key("employee", 7, 12) != _candidate_key("employee", 7, 13)
    assert _candidate_key("employee", 7, 12) != _candidate_key("user", 7, 12)


def test_normalize_handles_unicode_spacing_without_exposing_hashes():
    # Unicode casefold is deterministic and intentionally locale-independent.
    assert _normalize("  AYŞE   YILMAZ ") == "ayşe yilmaz"
    assert _normalize("KURUM@EXAMPLE.COM") == "kurum@example.com"


def test_mandatory_roles_are_explicit():
    assert MANDATORY == {"isveren_vekili", "igu", "hekim"}
    assert ROLE_LABELS["isveren_vekili"]
    assert ROLE_LABELS["igu"]
    assert ROLE_LABELS["hekim"]


def test_professional_pdf_deduplicates_members_and_preserves_unsigned_status():
    pdf = build_committee_meeting_pdf(
        company={"name": "Örnek Sanayi A.Ş.", "address": "İstanbul"},
        meeting={
            "id": 3,
            "meeting_no": "2026-04",
            "document_no": "İSG-KRL-04",
            "revision_no": "00",
            "meeting_date": date(2026, 8, 5),
            "start_time": "10:00",
            "end_time": "11:30",
            "location": "Toplantı Salonu",
            "status": "draft",
            "signature_status": "not_signed",
            "agenda": "Risk değerlendirmesi\nEğitim planı",
            "decisions": "Düzeltici faaliyetler 30 gün içinde tamamlanacaktır.",
            "next_meeting_date": date(2026, 9, 5),
        },
        members=[
            {"identity_key": "employee:1:5", "full_name": "Ayşe Yılmaz", "job_title": "Çalışan Temsilcisi", "role_label": "Çalışan Temsilcisi", "signature_status": "İmzalanmadı"},
            {"identity_key": "employee:1:5", "full_name": "Ayşe Yılmaz", "job_title": "Çalışan Temsilcisi", "role_label": "Çalışan Temsilcisi", "signature_status": "İmzalanmadı"},
            {"identity_key": "professional:1:9", "full_name": "Mehmet Çelik", "professional_role": "İş Güvenliği Uzmanı", "role_label": "İş Güvenliği Uzmanı", "signature_status": "İmzalanmadı"},
        ],
    )
    assert pdf.startswith(b"%PDF")
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) >= 1
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Örnek Sanayi" in text
    assert "İŞ SAĞLIĞI VE GÜVENLİĞİ" in text
    assert text.count("Ayşe Yılmaz") == 2
    assert "İmzalanmadı" in text
    assert "Risk değerlendirmesi" in text


def test_large_signature_grid_continues_across_pages():
    members = [
        {"identity_key": f"employee:1:{i}", "full_name": f"Üye {i}", "job_title": "Kurul Üyesi", "role_label": "Diğer Üye", "signature_status": "İmzalanmadı"}
        for i in range(1, 28)
    ]
    pdf = build_committee_meeting_pdf(
        company={"name": "Büyük İşyeri", "address": "Ankara"},
        meeting={"id": 9, "meeting_no": "9", "meeting_date": date(2026, 8, 5), "agenda": "Gündem", "decisions": "Karar"},
        members=members,
    )
    reader = PdfReader(BytesIO(pdf))
    assert len(reader.pages) >= 2
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Üye 1" in text
    assert "Üye 27" in text
