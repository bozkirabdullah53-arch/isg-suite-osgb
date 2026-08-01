"""NACE, tehlike sınıfı ve kayıtlı eğitim konularından 15 soruluk İSG sınavı üretir.

Veritabanına yazmaz; yalnızca mevcut eğitim kaydını okuyup PDF döndürür.
"""
from __future__ import annotations

import random
import re
from datetime import datetime
from io import BytesIO

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from app.services.training_topics import egitim_konularini_hazirla, sektor_kodu_cozumle, tehlike_kurali


def _clean_topic(text: str) -> str:
    text = re.sub(r"\s*-\s*\d+\s*DK\s*$", "", str(text), flags=re.I).strip()
    text = re.sub(r"^[a-zçğıöşü]\)\s*", "", text, flags=re.I)
    text = re.sub(r"^\d+[.)]\s*", "", text)
    return text.strip(" .")


def _topics(training) -> list[str]:
    sector = sektor_kodu_cozumle(training.sector)
    sol, sag, _, _ = egitim_konularini_hazirla(training.hazard_class, sector)
    result: list[str] = []
    for is_heading, text in list(sol) + list(sag):
        if is_heading:
            continue
        topic = _clean_topic(text)
        if topic and topic not in result:
            result.append(topic)
    if not result:
        result = [
            "İş sağlığı ve güvenliği temel kuralları",
            "Risklerden korunma prensipleri",
            "Acil durum ve tahliye",
            "Kişisel koruyucu donanım kullanımı",
            "İş kazalarının önlenmesi",
        ]
    return result


def _question(topic: str, index: int, rnd: random.Random) -> dict:
    stems = [
        "{topic} konusunda çalışan için en doğru uygulama hangisidir?",
        "{topic} ile ilgili riskleri azaltmak için öncelikle ne yapılmalıdır?",
        "{topic} kapsamında güvenli çalışma davranışı hangisidir?",
        "{topic} konusunda aşağıdaki ifadelerden hangisi doğrudur?",
    ]
    correct = [
        "Risk değerlendirmesi ve işyeri talimatlarına uygun çalışmak",
        "Tehlikeyi kaynağında kontrol edip gerekli koruyucu önlemleri uygulamak",
        "Eğitim, talimat ve güvenli çalışma prosedürlerine uymak",
        "Uygunsuzluğu bildirip güvenli yöntem belirlenmeden işe devam etmemek",
    ][index % 4]
    wrong = [
        "İşi hızlandırmak için koruyucu önlemleri geçici olarak kaldırmak",
        "Yalnızca kaza olduktan sonra önlem almak",
        "Tehlikeyi fark etse bile çalışmaya aynı şekilde devam etmek",
        "Kişisel deneyimi yazılı talimatların önünde tutmak",
        "Koruyucu donanımı sadece denetim sırasında kullanmak",
    ]
    distractors = rnd.sample(wrong, 3)
    options = [correct] + distractors
    rnd.shuffle(options)
    return {
        "stem": stems[index % len(stems)].format(topic=topic),
        "options": options,
        "answer": "ABCD"[options.index(correct)],
    }


def _wrap(c, text: str, width: float, font: str, size: float) -> list[str]:
    words = str(text).split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if c.stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def build_exam_pdf(*, company_name: str, training) -> bytes:
    topics = _topics(training)
    # Her tıklamada farklı kombinasyon; kapsam daima kayıtlı konu havuzuyla sınırlı.
    rnd = random.Random()
    expanded = (topics * ((15 // len(topics)) + 2))[:]
    rnd.shuffle(expanded)
    selected = expanded[:15]
    questions = [_question(topic, i, rnd) for i, topic in enumerate(selected)]

    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    navy = (11 / 255, 46 / 255, 79 / 255)
    emerald = (15 / 255, 118 / 255, 110 / 255)
    light = (244 / 255, 248 / 255, 247 / 255)

    def header(page_no: int):
        c.setFillColorRGB(*navy)
        c.rect(0, h - 30 * mm, w, 30 * mm, fill=1, stroke=0)
        c.setFillColorRGB(*emerald)
        c.rect(0, h - 31.5 * mm, w, 1.5 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont("Helvetica-Bold", 14)
        c.drawCentredString(w / 2, h - 13 * mm, "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM SINAVI")
        c.setFont("Helvetica", 8)
        subtitle = f"{training.hazard_class} • NACE/Sektör: {training.sector or '—'} • 15 Soru"
        c.drawCentredString(w / 2, h - 21 * mm, subtitle)
        c.setFillColorRGB(0.25, 0.3, 0.35)
        c.setFont("Helvetica", 7)
        c.drawRightString(w - 15 * mm, 10 * mm, f"Sayfa {page_no}")

    header(1)
    y = h - 39 * mm
    c.setFillColorRGB(*light)
    c.roundRect(14 * mm, y - 25 * mm, w - 28 * mm, 25 * mm, 3 * mm, fill=1, stroke=0)
    c.setFillColorRGB(0.08, 0.14, 0.22)
    c.setFont("Helvetica-Bold", 8)
    fields = [
        ("Katılımcı Adı Soyadı", ""),
        ("Firma Adı", company_name or ""),
        ("Sınav Tarihi", datetime.now().strftime("%d.%m.%Y")),
        ("İmza", ""),
    ]
    col_w = (w - 34 * mm) / 2
    for i, (label, value) in enumerate(fields):
        row, col = divmod(i, 2)
        x = 18 * mm + col * col_w
        yy = y - 7 * mm - row * 11 * mm
        c.drawString(x, yy, f"{label}:")
        c.setFont("Helvetica", 8)
        c.drawString(x + 32 * mm, yy, value)
        c.line(x + 31 * mm, yy - 1.5 * mm, x + col_w - 4 * mm, yy - 1.5 * mm)
        c.setFont("Helvetica-Bold", 8)

    y -= 31 * mm
    page_no = 1
    for qi, q in enumerate(questions, 1):
        needed = 8 + len(_wrap(c, q["stem"], w - 36 * mm, "Helvetica-Bold", 8.5)) * 4 + 4 * 5
        if y < 25 * mm + needed * mm:
            c.showPage()
            page_no += 1
            header(page_no)
            y = h - 38 * mm
        c.setFillColorRGB(*navy)
        c.setFont("Helvetica-Bold", 8.5)
        stem_lines = _wrap(c, f"{qi}. {q['stem']}", w - 32 * mm, "Helvetica-Bold", 8.5)
        for line in stem_lines:
            c.drawString(16 * mm, y, line)
            y -= 4.2 * mm
        c.setFillColorRGB(0.16, 0.2, 0.25)
        c.setFont("Helvetica", 7.5)
        for oi, option in enumerate(q["options"]):
            lines = _wrap(c, f"{'ABCD'[oi]}) {option}", w - 42 * mm, "Helvetica", 7.5)
            for line in lines:
                c.drawString(22 * mm, y, line)
                y -= 3.7 * mm
        y -= 3 * mm

    # Cevap anahtarı ayrı son sayfa; değerlendiren için kesilip ayrılabilir.
    c.showPage()
    page_no += 1
    header(page_no)
    c.setFillColorRGB(*navy)
    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(w / 2, h - 45 * mm, "CEVAP ANAHTARI")
    c.setFont("Helvetica-Bold", 10)
    y = h - 60 * mm
    for i, q in enumerate(questions, 1):
        x = 30 * mm + ((i - 1) % 5) * 32 * mm
        yy = y - ((i - 1) // 5) * 15 * mm
        c.drawString(x, yy, f"{i}. {q['answer']}")
    c.setFont("Helvetica", 7)
    c.setFillColorRGB(0.35, 0.4, 0.45)
    c.drawCentredString(w / 2, 20 * mm, "Sorular yalnızca bu eğitim kaydındaki konu havuzundan üretilmiştir.")

    c.save()
    return buf.getvalue()
