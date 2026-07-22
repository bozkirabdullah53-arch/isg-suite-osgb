"""0.9.135 — Yıllık plan değerlendirme Excel/PDF (plan kayıtlarını değiştirmez)."""
from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def build_eval_xlsx(*, company_name: str, year: int, items: list[dict[str, Any]], unplanned: list[dict[str, Any]], kpis: dict[str, Any]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Genel ozet"
    ws.append(["Firma", company_name])
    ws.append(["Yil", year])
    for k, v in kpis.items():
        ws.append([k, v])

    w2 = wb.create_sheet("Faaliyetler")
    w2.append([
        "Plan ID", "Kategori", "Faaliyet", "Ay", "Hedef", "Sorumlu",
        "Durum", "Gerceklesme", "Oran", "Gecikme", "Kanit", "Sonuc",
    ])
    for it in items:
        plan = it.get("plan") or {}
        w2.append([
            plan.get("id"),
            plan.get("category"),
            plan.get("activity"),
            plan.get("month"),
            str(plan.get("target_date") or ""),
            plan.get("responsible_name"),
            it.get("outcome_status"),
            str(it.get("actual_end") or ""),
            it.get("completion_pct"),
            it.get("delay_days"),
            it.get("evidence_count"),
            (it.get("result_text") or "")[:500],
        ])

    w3 = wb.create_sheet("Plan disi")
    w3.append(["Faaliyet", "Kategori", "Tarih", "Neden", "Sonuc", "Sonraki yila oner"])
    for u in unplanned:
        w3.append([
            u.get("activity"),
            u.get("category"),
            str(u.get("done_date") or ""),
            (u.get("reason") or "")[:300],
            (u.get("result_text") or "")[:300],
            u.get("suggest_next_year"),
        ])

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def build_eval_pdf(*, company_name: str, year: int, kpis: dict[str, Any], items: list[dict[str, Any]]) -> bytes:
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    w, h = A4
    y = h - 40
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, y, f"Yillik Plan Degerlendirme - {year}")
    y -= 18
    pdf.setFont("Helvetica", 10)
    pdf.drawString(40, y, f"Firma: {company_name}")
    y -= 16
    pdf.drawString(40, y, f"Planlanan: {kpis.get('planned_total')} | Tamam: {kpis.get('tamam')} | Oran: {kpis.get('completion_rate')}")
    y -= 24
    pdf.setFont("Helvetica", 8)
    for it in items[:40]:
        plan = it.get("plan") or {}
        line = f"{plan.get('activity', '')[:50]} | {it.get('outcome_status')} | {it.get('actual_end') or '-'}"
        if y < 50:
            pdf.showPage()
            y = h - 40
            pdf.setFont("Helvetica", 8)
        pdf.drawString(40, y, line[:110])
        y -= 12
    pdf.save()
    return stream.getvalue()
