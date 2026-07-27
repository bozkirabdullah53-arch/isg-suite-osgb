"""QA: katılımcı imza formu PDF'inde e-imza yerleşimini görsel doğrula.

Kullanım: python scripts/qa_render_attendance_signature.py
Gereksinim: pypdfium2 (yalnızca bu QA aracı için; uygulama bağımlılığı değil)
Çıktı: docs/qa/logs/qa-esign-*.png — imza bandı gözle kontrol edilir.
"""
from __future__ import annotations

import math
import sys
from datetime import date
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image, ImageDraw  # noqa: E402

from app.services.training_pdfs import build_attendance_pdf, build_certificates_pdf  # noqa: E402


def _scribble(d: ImageDraw.ImageDraw, ox: int, oy: int, ink=(15, 30, 70, 255)) -> None:
    pts = []
    for i in range(0, 860, 6):
        y = oy + int(70 * math.sin(i / 38.0)) - int(i / 24)
        pts.append((ox + i, y))
    d.line(pts, fill=ink, width=9, joint="curve")
    d.line([(ox + 20, oy + 80), (ox + 780, oy + 65)], fill=ink, width=5)


def signature_transparent_png() -> bytes:
    """İdeal durum: şeffaf zeminli, sıkı kadrajlı PNG."""
    img = Image.new("RGBA", (900, 260), (255, 255, 255, 0))
    _scribble(ImageDraw.Draw(img), 40, 150)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def signature_scanned_jpeg() -> bytes:
    """Gerçek hayattaki kötü durum: beyaz zemin + geniş boşluk (telefonla çekim)."""
    img = Image.new("RGB", (1400, 1000), (252, 252, 250))
    _scribble(ImageDraw.Draw(img), 260, 520, ink=(20, 35, 80))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=82)
    return buf.getvalue()


def main() -> int:
    employees = {
        i: SimpleNamespace(
            full_name=name,
            national_id_masked=f"{35590387460 + i}",
            job_title="Operatör",
            department="Üretim",
        )
        for i, name in enumerate(
            [
                "ABDULLAH BOZKIR",
                "ABDÜLMETİN KESKİN",
                "ADEM ASLANTAŞ",
                "ALİ AYDURAK",
                "ARZU KARA",
                "ASIM ZEYBEK",
                "AYDIN BULUT",
                "BERNA KÜÇÜKDERELİ",
                "BERTAN HAKKI KÜÇÜKDERELİ",
                "BİLAL GEÇER",
            ],
            start=1,
        )
    }
    training = SimpleNamespace(
        id=1,
        company_id=1,
        title="Temel İş Sağlığı ve Güvenliği Eğitimi",
        training_type="Temel İSG Eğitimi",
        delivery_method="Yüz yüze",
        location="İşyeri Eğitim Salonu",
        start_date=date(2026, 7, 27),
        end_date=date(2026, 7, 28),
        next_training_date=None,
        duration_hours=16,
        renewal_years=1,
        hazard_class="Çok Tehlikeli",
        sector="Cam, Seramik ve Taş Ürünleri",
        instructor_name="abdullah bozkır",
        instructor_qualification="abdullah bozkır — isg 47597",
        workplace_physician="gönül bozkır",
        employer_representative="yusuf bozkır",
        logo_path=None,
        stamp_text=None,
        evaluation_method="Sınav",
        passing_score=None,
        verification_code="B499EDB00654CEAF",
        participants=[SimpleNamespace(employee_id=i) for i in range(1, 11)],
    )

    signer_images = {0: signature_transparent_png(), 1: signature_scanned_jpeg()}
    pdf = build_attendance_pdf(
        company_name="TEST İŞYERİ",
        training=training,
        employees=employees,
        signer_images=signer_images,
    )

    out_dir = Path(__file__).resolve().parents[2] / "docs" / "qa" / "logs"
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = out_dir / "qa-esign-attendance.pdf"
    pdf_path.write_bytes(pdf)

    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(pdf)
    page = doc[0]
    bitmap = page.render(scale=2.4)
    full = bitmap.to_pil()
    full.save(out_dir / "qa-esign-attendance.png")

    # İmza kutuları bandı — sayfanın alt %22'si
    w, h = full.size
    full.crop((0, int(h * 0.78), w, h)).save(out_dir / "qa-esign-attendance-signatures.png")

    cert = build_certificates_pdf(
        company_name="TEST İŞYERİ",
        training=training,
        employees=employees,
        signer_images=signer_images,
    )
    (out_dir / "qa-esign-certificate.pdf").write_bytes(cert)
    cert_page = pdfium.PdfDocument(cert)[0].render(scale=2.4).to_pil()
    cert_page.save(out_dir / "qa-esign-certificate.png")
    cw, ch = cert_page.size
    cert_page.crop((0, int(ch * 0.38), cw, int(ch * 0.62))).save(out_dir / "qa-esign-certificate-signatures.png")
    print("PDF:", pdf_path)
    print("PNG:", out_dir / "qa-esign-attendance.png")
    print("CROP:", out_dir / "qa-esign-attendance-signatures.png")
    print("CERT:", out_dir / "qa-esign-certificate-signatures.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
