"""0.9.136 — Yıllık plan değerlendirme Excel/PDF (plan kayıtlarını değiştirmez)."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_ASSETS = Path(__file__).resolve().parents[1] / "assets"
_FONT_REG = "EvalDejaVu"
_FONT_BOLD = "EvalDejaVu-Bold"


def _register_fonts() -> tuple[str, str]:
    candidates = [
        (_ASSETS / "DejaVuSans.ttf", _ASSETS / "DejaVuSans-Bold.ttf"),
        (
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
            Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ),
        (Path("C:/Windows/Fonts/arial.ttf"), Path("C:/Windows/Fonts/arialbd.ttf")),
    ]
    for regular, bold in candidates:
        if not regular.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(_FONT_REG, str(regular)))
            pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold if bold.exists() else regular)))
            registerFontFamily(_FONT_REG, normal=_FONT_REG, bold=_FONT_BOLD)
            return _FONT_REG, _FONT_BOLD
        except Exception:
            continue
    return "Helvetica", "Helvetica-Bold"


def build_eval_xlsx(
    *,
    company_name: str,
    year: int,
    items: list[dict[str, Any]],
    unplanned: list[dict[str, Any]],
    kpis: dict[str, Any],
    capas: list[dict[str, Any]] | None = None,
    suggestions: list[dict[str, Any]] | None = None,
) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Genel ozet"
    ws.append(["Firma", company_name])
    ws.append(["Yil", year])
    for k, v in kpis.items():
        if k == "formulas":
            continue
        ws.append([k, str(v)])

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

    w_miss = wb.create_sheet("Gerceklesmeyen")
    w_miss.append(["Plan ID", "Faaliyet", "Durum", "Gerekce", "Sonraki yil onerisi"])
    for it in items:
        if it.get("outcome_status") not in ("gerceklesmedi", "ertelendi"):
            continue
        plan = it.get("plan") or {}
        w_miss.append([
            plan.get("id"),
            plan.get("activity"),
            it.get("outcome_status"),
            (it.get("deviation_reason") or "")[:400],
            (it.get("next_year_suggestion") or "")[:400],
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

    w4 = wb.create_sheet("Duzeltici faaliyetler")
    w4.append(["Baslik", "Sorumlu", "Hedef", "Oncelik", "Durum", "Kok neden"])
    for c in capas or []:
        w4.append([
            c.get("title"),
            c.get("responsible"),
            str(c.get("due_date") or ""),
            c.get("priority"),
            c.get("status"),
            (c.get("root_cause") or "")[:300],
        ])

    w5 = wb.create_sheet("Sonraki yil onerileri")
    w5.append(["Faaliyet", "Neden", "Oneri"])
    for s in suggestions or []:
        w5.append([s.get("activity"), s.get("reason"), (s.get("suggestion") or "")[:400]])

    stream = BytesIO()
    wb.save(stream)
    return stream.getvalue()


def build_eval_pdf(
    *,
    company_name: str,
    year: int,
    kpis: dict[str, Any],
    items: list[dict[str, Any]],
    unplanned: list[dict[str, Any]] | None = None,
    suggestions: list[dict[str, Any]] | None = None,
) -> bytes:
    font, font_b = _register_fonts()
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    w, h = A4
    y = h - 40

    def line(txt: str, size: int = 9, bold: bool = False, gap: int = 12):
        nonlocal y
        if y < 50:
            pdf.showPage()
            y = h - 40
        pdf.setFont(font_b if bold else font, size)
        pdf.drawString(40, y, (txt or "")[:110])
        y -= gap

    line(f"Yıllık Plan Değerlendirme Raporu — {year}", 14, True, 18)
    line(f"Firma: {company_name}", 10)
    line(
        f"Planlanan: {kpis.get('planned_total')} | Tamam: {kpis.get('tamam')} | "
        f"Gerçekleşme: {kpis.get('completion_rate')}% | Zamanında: {kpis.get('on_time_rate')}% | "
        f"Kanıt: {kpis.get('evidence_rate')}%",
        9,
        gap=16,
    )
    line("1. Faaliyet değerlendirmeleri", 11, True, 14)
    for it in items:
        plan = it.get("plan") or {}
        line(
            f"• {plan.get('activity', '')[:48]} | {it.get('outcome_status')} | "
            f"{it.get('actual_end') or '-'} | kanıt:{it.get('evidence_count') or 0}"
        )
    line("2. Gerçekleştirilemeyen / ertelenen", 11, True, 14)
    miss = [it for it in items if it.get("outcome_status") in ("gerceklesmedi", "ertelendi")]
    if not miss:
        line("Kayıt yok.")
    for it in miss:
        plan = it.get("plan") or {}
        line(f"• {plan.get('activity', '')[:50]} — {(it.get('deviation_reason') or '')[:40]}")
    line("3. Plan dışı faaliyetler", 11, True, 14)
    if not unplanned:
        line("Kayıt yok.")
    for u in unplanned or []:
        line(f"• {u.get('activity', '')[:60]} ({u.get('done_date') or '-'})")
    line("4. Bir sonraki yıl önerileri", 11, True, 14)
    if not suggestions:
        line("Öneri yok.")
    for s in suggestions or []:
        line(f"• {s.get('activity', '')[:50]} — {s.get('reason')}")
    line("Not: Plan alanları bu raporda değiştirilmez. Plan dışı faaliyetler gerçekleşme oranına girmez.", 8, gap=10)
    pdf.save()
    return stream.getvalue()
