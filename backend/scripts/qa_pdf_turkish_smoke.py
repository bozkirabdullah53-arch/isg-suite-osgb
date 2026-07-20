"""B-04 — PDF Türkçe/Unicode smoke (DejaVu + İŞĞÜÖÇ karakterleri).

Çalıştır:
  python scripts/qa_pdf_turkish_smoke.py
"""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.incident_reports import build_incident_pdf
from app.services.training_pdfs import build_attendance_pdf

OUT: list[dict] = []
TURKISH_NEEDLES = ("İ", "Ş", "ğ", "ü", "Ö", "Ç")  # used in mock data generation only


def rec(name: str, ok: bool, detail: str = ""):
    OUT.append({"test": name, "ok": bool(ok), "detail": str(detail)[:240]})
    print(("PASS" if ok else "FAIL"), name, str(detail)[:120])


def assert_pdf_bytes(pdf: bytes) -> tuple[bool, str]:
    """Validate PDF shell + DejaVu Unicode embedding (compressed streams OK)."""
    if not pdf.startswith(b"%PDF"):
        return False, "missing %PDF header"
    if b"%%EOF" not in pdf[-128:] and b"%%EOF" not in pdf:
        return False, "missing %%EOF trailer"
    if len(pdf) < 800:
        return False, f"too small ({len(pdf)} bytes)"
    latin = pdf.decode("latin-1", errors="ignore")
    if "DejaVu" not in latin:
        return False, "DejaVu font not embedded"
    if "/ToUnicode" not in latin and "/Identity-H" not in latin:
        return False, "no Unicode CMap (ToUnicode/Identity-H)"
    return True, f"bytes={len(pdf)} DejaVu+Unicode"


def _training_mock() -> SimpleNamespace:
    participant = SimpleNamespace(
        id=1,
        employee_id=1,
        full_name="Ahmet Şahin",
        department="Üretim",
        job_title="Operatör",
        national_id_masked="123****8901",
    )
    return SimpleNamespace(
        participants=[participant],
        hazard_class="az_tehlikeli",
        sector="genel",
        training_date=date.today(),
        duration_hours=8,
        instructor_name="Dr. Öğretmen",
        instructor_qualification="A Sınıfı İSG Uzmanı",
        evaluation_method="Yazılı sınav",
        passing_score=70,
        title="İş Sağlığı ve Güvenliği Temel Eğitimi",
        training_type="Temel",
        delivery_method="Yüz yüze",
        location="İstanbul",
        verification_code="TEST-VERIFY-01",
        stamp_text="İSG Suite OSGB — Onay",
        logo_path=None,
        workplace_physician="Dr. Hekim",
        employer_representative="Veli Vekil",
    )


def _incident_mock() -> SimpleNamespace:
    return SimpleNamespace(
        form_no="RK-2026-001",
        event_type="ramak_kala",
        event_date=date.today(),
        event_time="14:30",
        location="Fabrika — Montaj hattı",
        department="Üretim",
        area="Hat B",
        work_being_done="Pres operasyonu",
        short_summary="Operatör eldiven takmadan pres makinesine yaklaştı; acil stop ile durduruldu.",
        detail="Operatör koruyucu eldiven kullanmadan makineye müdahale etmeye çalıştı. Vardiya amiri acil stop butonuna bastı.",
        classification="Ramak kala — düşme riski",
        related_people="Mehmet Yılmaz, Ayşe Demir",
        recorded_by_name="Ayşe Demir",
        safety_specialist="Ali Uzman",
        workplace_physician="Dr. Hekim",
        employer_representative="Veli Vekil",
        auto_warning=None,
        risk_analysis_status="mevcut",
        risk_analysis_note="Risk analizi güncellenecek.",
        probability=3,
        severity=4,
        risk_score=12,
        risk_level="orta",
        emergency_relation="Hayır",
        evaluation_text="Olay sonrası ekipman durduruldu ve personele İSG eğitimi hatırlatıldı.",
        sgk_reported=False,
        lost_days=0,
        injury_type=None,
        body_part=None,
        witness_names="Mehmet Yılmaz",
        reporter_name="Ayşe Demir",
        risk_analysis=None,
        photos_json=None,
    )


def main() -> int:
    training = _training_mock()
    employees = {1: training.participants[0]}

    try:
        pdf = build_attendance_pdf(
            company_name="Test A.Ş. İşletmesi",
            training=training,
            employees=employees,
        )
        ok, detail = assert_pdf_bytes(pdf)
        rec("pdf_attendance_turkish", ok, detail)
    except Exception as exc:
        rec("pdf_attendance_turkish", False, repr(exc))

    try:
        incident = _incident_mock()
        pdf2 = build_incident_pdf(
            company_name="Demo İşyeri Ltd. Şti.",
            incident=incident,
            root_cause=None,
            dofs=[],
        )
        ok2, detail2 = assert_pdf_bytes(pdf2)
        rec("pdf_incident_turkish", ok2, detail2)
    except Exception as exc:
        rec("pdf_incident_turkish", False, repr(exc))

    summary = {
        "passed": sum(1 for x in OUT if x["ok"]),
        "failed": sum(1 for x in OUT if not x["ok"]),
        "total": len(OUT),
        "results": OUT,
    }
    out_path = ROOT.parent / "docs" / "qa" / "logs" / "qa-pdf-turkish-smoke.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print("SUMMARY", summary["passed"], "/", summary["total"])
    print("Wrote", out_path)
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
