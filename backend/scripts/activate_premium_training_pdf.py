"""Idempotently wire the approved premium certificate renderer into training_pdfs.py.

This changes only the page drawing implementation. Existing data preparation,
training topic contents, ordering, durations and legal text remain untouched.
"""
from __future__ import annotations

from pathlib import Path

TARGET = Path(__file__).resolve().parents[1] / "app" / "services" / "training_pdfs.py"
MARKER = "# PREMIUM_TRAINING_CERTIFICATE_ACTIVE"


def main() -> None:
    source = TARGET.read_text(encoding="utf-8")
    if MARKER in source:
        print("premium training certificate renderer already active")
        return

    start = source.find("def _draw_certificate_page(")
    if start < 0:
        raise RuntimeError("_draw_certificate_page function not found")

    signature_end = source.find("\n):", start)
    if signature_end < 0:
        raise RuntimeError("_draw_certificate_page signature end not found")
    insert_at = signature_end + len("\n):")

    delegation = f'''\n    {MARKER}\n    from app.services.training_pdf_premium import draw_certificate_page\n    return draw_certificate_page(\n        c, w, h,\n        company_name=company_name, training=training, employee=employee,\n        belge_no=belge_no, bugun=bugun, egitim_tarihi=egitim_tarihi,\n        kural=kural, sektor=sektor, sol=sol, sag=sag,\n        curriculum=curriculum, tp=__import__(__name__, fromlist=["*"]),\n    )\n'''

    TARGET.write_text(source[:insert_at] + delegation + source[insert_at:], encoding="utf-8")
    print("premium training certificate renderer activated")


if __name__ == "__main__":
    main()
