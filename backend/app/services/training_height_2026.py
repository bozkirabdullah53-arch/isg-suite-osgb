# -*- coding: utf-8 -*-
"""2026 mevzuat uyumlu Yüksekte Çalışma özel eğitim belge katmanı.

Bu modül yalnız ``yuksekte_calisma`` özel profilini etkiler. Diğer eğitim
profillerinin veri, doğrulama ve PDF davranışını değiştirmez.
"""
from __future__ import annotations

from math import ceil
import unicodedata
from reportlab.lib.units import mm

from app.services.special_training_profiles import (
    SPECIAL_INSTRUCTOR_ROLES,
    SPECIAL_TRAINING_PROFILES,
    resolve_special_profile_key,
    special_topics_with_minutes,
)

NAVY = (7 / 255, 45 / 255, 82 / 255)
TEAL = (0 / 255, 118 / 255, 118 / 255)
SAFETY = (239 / 255, 151 / 255, 35 / 255)
PALE = (247 / 255, 250 / 255, 252 / 255)
TEXT = (18 / 255, 36 / 255, 54 / 255)
MUTED = (78 / 255, 92 / 255, 105 / 255)
LINE = (198 / 255, 211 / 255, 220 / 255)

HEIGHT_LEGAL_BASIS = (
    "6331 sayılı İş Sağlığı ve Güvenliği Kanunu m.17; 02.04.2026 tarihli, "
    "33212 sayılı Resmî Gazete'de yayımlanan Çalışanların İş Sağlığı ve "
    "Güvenliği Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik m.5, 9, m.10, "
    "13, 17, 24, 26 ve Ek-1/Ek-2; Yapı İşlerinde İş Sağlığı ve Güvenliği "
    "Yönetmeliği Ek-4/2(g); İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik "
    "Şartları Yönetmeliğinin ilgili hükümleri."
)

HEIGHT_INSTRUCTOR_NOTE = (
    "Eğiticinin uzmanlık alanı eğitim konusuna uygun olmalıdır (Yönetmelik m.10). "
    "Yüksekte çalışma eğitici eğitimi/iple erişim sertifikası tek başına mevzuat "
    "kapsamında eğitici yetkisi oluşturmaz."
)

HEIGHT_DISCLAIMER = (
    "Bu belge eğitim katılımı ve başarı kaydıdır; mesleki yeterlilik belgesi, "
    "çalışma izin belgesi veya her koşulda yüksekte çalışma yetkisi yerine geçmez."
)


def apply_height_training_profile_2026() -> str:
    """Yalnız yüksekte çalışma profilinin 2026 eğitici/dayanak kurallarını uygula."""
    profile = SPECIAL_TRAINING_PROFILES.get("yuksekte_calisma")
    if not profile:
        raise RuntimeError("Yüksekte çalışma özel eğitim profili bulunamadı.")

    profile["legal_basis"] = HEIGHT_LEGAL_BASIS
    profile["disclaimer"] = HEIGHT_DISCLAIMER
    profile["instructor_legal_note"] = HEIGHT_INSTRUCTOR_NOTE
    profile["allowed_roles"] = [
        "isg_a",
        "isg_b",
        "isg_c",
        "isyeri_hekimi",
        "m10_bc_kurum_egiticisi",
        "m10_cde_belgeli_egitici",
        "az_tehlikeli_50_alti_egitimli_isveren",
    ]

    physician = SPECIAL_INSTRUCTOR_ROLES.setdefault(
        "isyeri_hekimi",
        {"label": "İşyeri Hekimi", "profiles": []},
    )
    physician_profiles = list(physician.get("profiles") or [])
    if "yuksekte_calisma" not in physician_profiles:
        physician_profiles.append("yuksekte_calisma")
    physician["profiles"] = physician_profiles

    SPECIAL_INSTRUCTOR_ROLES["m10_bc_kurum_egiticisi"] = {
        "label": "ÇASGEM / Üniversite / Kamu Kurumu Eğitim Birimi Eğiticisi (m.10/1-b,c; uzmanlık alanı uygun)",
        "profiles": ["yuksekte_calisma"],
    }
    SPECIAL_INSTRUCTOR_ROLES["m10_cde_belgeli_egitici"] = {
        "label": (
            "m.10/1-ç,d,e Kapsamındaki Kurum/Kuruluş Bünyesinde Belgeli Eğitici "
            "(İSG Uzmanlığı / İşyeri Hekimliği / Eğitici Belgesi)"
        ),
        "profiles": ["yuksekte_calisma"],
    }
    SPECIAL_INSTRUCTOR_ROLES["az_tehlikeli_50_alti_egitimli_isveren"] = {
        "label": (
            "50'den Az Çalışanı Bulunan Az Tehlikeli İşyerinde "
            "İlgili Eğitimi Tamamlamış İşveren / İşveren Vekili"
        ),
        "profiles": ["yuksekte_calisma"],
    }

    # Bu sertifika uzmanlığın tevsikinde kullanılabilir; tek başına mevzuat yetkisi
    # değildir. Eski kodu silmiyoruz, fakat yüksekte çalışma için seçilebilir rol
    # olmaktan çıkarıyoruz.
    legacy = SPECIAL_INSTRUCTOR_ROLES.get("yuksekte_egitmen")
    if legacy is not None:
        legacy["label"] = "Yüksekte Çalışma Eğitici Sertifikası (tek başına yetki değildir)"
        legacy["profiles"] = [
            key for key in list(legacy.get("profiles") or [])
            if key != "yuksekte_calisma"
        ]

    return "active"


def is_height_training(training, curriculum: dict | None = None) -> bool:
    curriculum = curriculum or {}
    key = str(curriculum.get("profile_key") or "").strip()
    if not key and training is not None:
        key = str(resolve_special_profile_key(training) or "")
    return key == "yuksekte_calisma"


def _norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", str(value or "").casefold())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.replace("ı", "i").strip()


def height_instructor_is_authorized(
    qualification: str | None,
    training=None,
) -> bool:
    """Yüksekte çalışma belgesine yalnız doğrulanabilir mevzuat rolü düşürür.

    Yönetmelik m.10/1-a kapsamındaki işyerinde görevli İSG uzmanı/işyeri hekimi,
    m.10/1-b,c kapsamındaki kurum eğiticisi ve m.10/1-ç,d,e kapsamındaki gerekli
    belgeye sahip kurum eğiticisi kabul edilir. Bakanlık SSS'de açıklanan
    50'den az çalışanlı az tehlikeli işyeri istisnası, unvan üzerinde koşullar
    açıkça yazılıysa ve eğitim kaydı da ``Az Tehlikeli`` ise kabul edilir.
    """
    text = _norm(qualification)
    if not text:
        return False

    conditional_employer = _norm(
        "50'den Az Çalışanı Bulunan Az Tehlikeli İşyerinde "
        "İlgili Eğitimi Tamamlamış İşveren / İşveren Vekili"
    )
    if conditional_employer in text:
        if training is None:
            return False
        return _norm(getattr(training, "hazard_class", "")) == "az tehlikeli"

    authorized_markers = tuple(_norm(marker) for marker in (
        "A Sınıfı İş Güvenliği Uzmanı",
        "B Sınıfı İş Güvenliği Uzmanı",
        "C Sınıfı İş Güvenliği Uzmanı",
        "İş Güvenliği Uzmanı",
        "İSG Uzmanı",
        "İşyeri Hekimi",
        "ÇASGEM / Üniversite / Kamu Kurumu Eğitim Birimi Eğiticisi",
        "m.10/1-ç,d,e Kapsamındaki Kurum/Kuruluş Bünyesinde Belgeli Eğitici",
    ))
    if any(marker in text for marker in authorized_markers):
        return True

    # Salt özel yüksekte çalışma/eğitici sertifikası mevzuat yetkisi değildir.
    if "yuksekte calisma" in text and "egit" in text:
        return False
    return False


def _fit(tp, c, text: str, width: float, font: str, size: float) -> str:
    return tp._fit(c, text, width, font, size)


def _wrap(tp, c, text: str, width: float, font: str, size: float, max_lines: int = 3):
    return tp._wrap(c, text, width, font, size, max_lines)


def _draw_height_watermark(c, w: float, h: float) -> None:
    """Sadece yüksekte çalışma sertifikasına ait iskele/ankraj/kemer line-art."""
    c.saveState()
    try:
        c.setStrokeAlpha(0.075)
        c.setFillAlpha(0.045)
    except Exception:
        pass
    c.setStrokeColorRGB(*TEAL)
    c.setFillColorRGB(*TEAL)

    # Platform + korkuluk.
    px = w - 82 * mm
    py = 40 * mm
    c.setLineWidth(1.8)
    c.line(px, py, px + 63 * mm, py)
    c.line(px + 4 * mm, py, px + 4 * mm, py + 86 * mm)
    c.line(px + 59 * mm, py, px + 59 * mm, py + 86 * mm)
    c.line(px + 4 * mm, py + 70 * mm, px + 59 * mm, py + 70 * mm)
    c.line(px + 4 * mm, py + 86 * mm, px + 59 * mm, py + 86 * mm)
    c.line(px + 4 * mm, py + 55 * mm, px + 59 * mm, py + 55 * mm)

    # Üst ankraj ve yaşam hattı.
    anchor_x = px + 32 * mm
    c.circle(anchor_x, py + 99 * mm, 3.5 * mm, stroke=1, fill=0)
    c.line(anchor_x, py + 95.5 * mm, anchor_x, py + 61 * mm)

    # Çalışan + tam vücut kemeri.
    head_y = py + 76 * mm
    c.circle(anchor_x, head_y, 5 * mm, stroke=1, fill=0)
    c.line(anchor_x, head_y - 5 * mm, anchor_x, py + 49 * mm)
    c.line(anchor_x, py + 64 * mm, anchor_x - 12 * mm, py + 56 * mm)
    c.line(anchor_x, py + 64 * mm, anchor_x + 12 * mm, py + 56 * mm)
    c.line(anchor_x, py + 49 * mm, anchor_x - 10 * mm, py + 34 * mm)
    c.line(anchor_x, py + 49 * mm, anchor_x + 10 * mm, py + 34 * mm)
    # Harness "X" ve bel kemeri.
    c.setLineWidth(2.2)
    c.line(anchor_x - 6 * mm, py + 66 * mm, anchor_x + 6 * mm, py + 52 * mm)
    c.line(anchor_x + 6 * mm, py + 66 * mm, anchor_x - 6 * mm, py + 52 * mm)
    c.line(anchor_x - 7 * mm, py + 55 * mm, anchor_x + 7 * mm, py + 55 * mm)

    # Şok emicili bağlantı hattı.
    c.setLineWidth(1.2)
    c.line(anchor_x + 5 * mm, py + 61 * mm, anchor_x + 18 * mm, py + 80 * mm)
    c.line(anchor_x + 18 * mm, py + 80 * mm, anchor_x + 18 * mm, py + 94 * mm)
    c.circle(anchor_x + 18 * mm, py + 96 * mm, 2.2 * mm, stroke=1, fill=0)

    # Düşmeye karşı uyarı üçgeni.
    tx, ty = px - 9 * mm, py + 18 * mm
    path = c.beginPath()
    path.moveTo(tx + 8 * mm, ty + 15 * mm)
    path.lineTo(tx + 16 * mm, ty)
    path.lineTo(tx, ty)
    path.close()
    c.drawPath(path, stroke=1, fill=0)
    c.line(tx + 8 * mm, ty + 10 * mm, tx + 8 * mm, ty + 5 * mm)
    c.circle(tx + 8 * mm, ty + 2.5 * mm, 0.6 * mm, stroke=1, fill=1)
    c.restoreState()


def _topic_columns(topics: list[dict], column_count: int = 4) -> list[list[dict]]:
    if not topics:
        return [[] for _ in range(column_count)]
    size = ceil(len(topics) / column_count)
    columns = [topics[i:i + size] for i in range(0, len(topics), size)]
    while len(columns) < column_count:
        columns.append([])
    if len(columns) > column_count:
        overflow = columns[column_count:]
        columns = columns[:column_count]
        for extra in overflow:
            columns[-1].extend(extra)
    return columns


def draw_height_certificate_page(
    c, w, h, *, company_name, training, employee, belge_no, bugun,
    egitim_tarihi, kural, sektor, sol, sag, curriculum=None, tp=None
):
    """Yüksekte çalışma özel eğitimi için izole premium katılım/başarı belgesi."""
    if tp is None:
        from app.services import training_pdfs as tp

    curriculum = curriculum or {}
    if not is_height_training(training, curriculum):
        raise ValueError("Yüksekte çalışma renderer'ı yalnız yuksekte_calisma profili için kullanılabilir.")

    apply_height_training_profile_2026()
    profile = curriculum.get("profile") or SPECIAL_TRAINING_PROFILES["yuksekte_calisma"]

    instructor = str(getattr(training, "instructor_name", "") or "").strip()
    instructor_title = str(getattr(training, "instructor_qualification", "") or "").strip()
    if not height_instructor_is_authorized(instructor_title, training):
        raise ValueError(
            "Yüksekte çalışma belgesi için Yönetmelik m.10 kapsamında uygun eğitici "
            "unvanı/yeterliliği seçilmelidir. Yüksekte çalışma eğitici sertifikası "
            "tek başına eğitici yetkisi değildir."
        )

    employer = str(getattr(training, "employer_representative", "") or "").strip()
    additional_instructor = str(getattr(training, "additional_instructor_name", "") or "").strip()
    additional_title = str(
        getattr(training, "additional_instructor_qualification", "") or ""
    ).strip()

    ml, mr = 7 * mm, 7 * mm
    uw = w - ml - mr

    # Kağıt ve çift çerçeve.
    c.setFillColorRGB(1, 1, 1)
    c.rect(0, 0, w, h, fill=1, stroke=0)
    c.setStrokeColorRGB(*NAVY)
    c.setLineWidth(1.15)
    c.rect(3 * mm, 3 * mm, w - 6 * mm, h - 6 * mm, stroke=1, fill=0)
    c.setStrokeColorRGB(*SAFETY)
    c.setLineWidth(0.45)
    c.rect(4.6 * mm, 4.6 * mm, w - 9.2 * mm, h - 9.2 * mm, stroke=1, fill=0)

    _draw_height_watermark(c, w, h)

    # Başlık bandı.
    header_y = h - 32 * mm
    c.setFillColorRGB(*NAVY)
    c.rect(4.6 * mm, header_y, w - 9.2 * mm, 27.4 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*TEAL)
    c.rect(w - 66 * mm, header_y, 61.4 * mm, 27.4 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*SAFETY)
    c.rect(w - 66 * mm, header_y, 2.2 * mm, 27.4 * mm, fill=1, stroke=0)

    logo_x, logo_y, logo_w, logo_h = 9 * mm, header_y + 3.2 * mm, 42 * mm, 20 * mm
    c.setStrokeColorRGB(0.73, 0.82, 0.88)
    c.setLineWidth(0.45)
    c.roundRect(logo_x, logo_y, logo_w, logo_h, 2 * mm, stroke=1, fill=0)
    tp._draw_logo(
        c,
        training,
        x=logo_x + 2 * mm,
        y=logo_y + 1.5 * mm,
        max_w=logo_w - 4 * mm,
        max_h=logo_h - 3 * mm,
    )

    title = (
        curriculum.get("certificate_title")
        or "YÜKSEKTE ÇALIŞMA GÜVENLİĞİ EĞİTİMİ KATILIM VE BAŞARI BELGESİ"
    )
    c.setFillColorRGB(1, 1, 1)
    main_title_left = logo_x + logo_w + 4 * mm
    main_title_right = w - 69 * mm
    main_title_center = (main_title_left + main_title_right) / 2
    main_title_width = main_title_right - main_title_left
    c.setFont(tp._FONT_B, 10.7)
    c.drawCentredString(
        main_title_center,
        h - 14 * mm,
        _fit(tp, c, title, main_title_width, tp._FONT_B, 10.7),
    )
    c.setFont(tp._FONT_B, 8.2)
    c.drawCentredString(
        main_title_center,
        h - 21.5 * mm,
        _fit(tp, c, company_name or "", main_title_width - 18 * mm, tp._FONT_B, 8.2),
    )
    c.setFont(tp._FONT_B, 6.6)
    c.drawRightString(w - 10 * mm, h - 11 * mm, "YÜKSEKTE ÇALIŞMA")
    c.setFont(tp._FONT, 5.8)
    c.drawRightString(w - 10 * mm, h - 16 * mm, "Düşmeye karşı korunma • ankraj • yaşam hattı")
    c.drawRightString(w - 10 * mm, h - 20 * mm, "uygulamalı güvenli çalışma eğitimi")

    # Meta şeridi.
    strip_y = header_y - 13.5 * mm
    c.setFillColorRGB(*PALE)
    c.rect(4.6 * mm, strip_y, w - 9.2 * mm, 13.5 * mm, fill=1, stroke=0)
    meta = [
        ("Belge No", str(belge_no or "—")),
        ("Eğitim Tarihi", str(egitim_tarihi or "—")),
        ("Süre", str(curriculum.get("duration_hint") or f"{getattr(training, 'duration_hours', '')} ders saati")),
        ("Eğitim Şekli", str(getattr(training, "delivery_method", "") or "—")),
        ("Değerlendirme", str(getattr(training, "evaluation_method", "") or "—")),
        ("Doğrulama", str(getattr(training, "verification_code", "") or "—")),
    ]
    meta_w = (w - 13.2 * mm) / len(meta)
    for i, (label, value) in enumerate(meta):
        x = 6.6 * mm + i * meta_w
        if i:
            c.setStrokeColorRGB(*LINE)
            c.setLineWidth(0.35)
            c.line(x, strip_y + 2 * mm, x, strip_y + 11.5 * mm)
        c.setFillColorRGB(*MUTED)
        c.setFont(tp._FONT_B, 5.2)
        c.drawCentredString(x + meta_w / 2, strip_y + 8.2 * mm, label)
        c.setFillColorRGB(*NAVY)
        c.setFont(tp._FONT_B, 5.6)
        c.drawCentredString(
            x + meta_w / 2,
            strip_y + 3.7 * mm,
            _fit(tp, c, value, meta_w - 3 * mm, tp._FONT_B, 5.6),
        )

    # Katılımcı bölümü.
    participant_top = strip_y - 4.5 * mm
    c.setFillColorRGB(*TEAL)
    c.setFont(tp._FONT, 7)
    c.drawCentredString(w / 2, participant_top - 2.5 * mm, "Bu belge aşağıda bilgileri bulunan çalışan adına düzenlenmiştir.")
    name = str(getattr(employee, "full_name", "") or "—")
    tc = str(getattr(employee, "national_id_masked", "") or "—")
    job = str(getattr(employee, "job_title", "") or "—")
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 16)
    c.drawCentredString(
        w / 2,
        participant_top - 12 * mm,
        _fit(tp, c, name, 105 * mm, tp._FONT_B, 16),
    )
    c.setFillColorRGB(*TEXT)
    c.setFont(tp._FONT_B, 6.3)
    c.drawString(10 * mm, participant_top - 19.5 * mm, "T.C. Kimlik No:")
    c.setFont(tp._FONT, 6.3)
    c.drawString(32 * mm, participant_top - 19.5 * mm, tc)
    c.setFont(tp._FONT_B, 6.3)
    c.drawRightString(w - 37 * mm, participant_top - 19.5 * mm, "Görevi:")
    c.setFont(tp._FONT, 6.3)
    c.drawRightString(w - 10 * mm, participant_top - 19.5 * mm, job)

    completion_text = (
        "Çalışan; yüksekte çalışma tehlikeleri ve riskleri, kontrol tedbirleri, güvenli çalışma "
        "yöntemleri, düşmeye karşı korunma sistemleri ve uygulamalı konuları tamamlamıştır."
    )
    c.setFillColorRGB(*MUTED)
    c.setFont(tp._FONT, 5.8)
    for idx, line in enumerate(_wrap(tp, c, completion_text, 205 * mm, tp._FONT, 5.8, 2)):
        c.drawCentredString(w / 2, participant_top - 25.5 * mm - idx * 3.1 * mm, line)

    # İmza alanı: yalnız mevzuata uygun eğitici(ler) + işveren/işveren vekili.
    sign_y, sign_h = 94 * mm, 28.5 * mm
    signers = [("Eğitici (Yönetmelik m.10)", instructor, instructor_title, TEAL)]
    if additional_instructor and height_instructor_is_authorized(additional_title, training):
        signers.append(("Eğitici (Yönetmelik m.10)", additional_instructor, additional_title, TEAL))
    signers.append(("İşveren / İşveren Vekili", employer, "İşveren / İşveren Vekili", NAVY))

    gap = 6 * mm
    box_w = (uw - gap * (len(signers) - 1)) / len(signers)
    for i, (role, person, title_text, accent) in enumerate(signers):
        x = ml + i * (box_w + gap)
        c.setFillColorRGB(1, 1, 1)
        c.setStrokeColorRGB(*accent)
        c.setLineWidth(0.7)
        c.roundRect(x, sign_y, box_w, sign_h, 2.2 * mm, fill=1, stroke=1)
        c.setFillColorRGB(*accent)
        c.roundRect(x, sign_y + sign_h - 7.8 * mm, box_w, 7.8 * mm, 2.2 * mm, fill=1, stroke=0)
        c.setFillColorRGB(1, 1, 1)
        c.setFont(tp._FONT_B, 6.7)
        c.drawCentredString(
            x + box_w / 2,
            sign_y + sign_h - 5.2 * mm,
            _fit(tp, c, role, box_w - 5 * mm, tp._FONT_B, 6.7),
        )
        c.setFillColorRGB(*TEXT)
        c.setFont(tp._FONT_B, 8)
        c.drawCentredString(
            x + box_w / 2,
            sign_y + 13 * mm,
            _fit(tp, c, person or " ", box_w - 7 * mm, tp._FONT_B, 8),
        )
        c.setStrokeColorRGB(0.38, 0.43, 0.47)
        c.setLineWidth(0.4)
        c.line(x + 10 * mm, sign_y + 8.1 * mm, x + box_w - 10 * mm, sign_y + 8.1 * mm)
        c.setFillColorRGB(*MUTED)
        c.setFont(tp._FONT, 5.4)
        c.drawCentredString(
            x + box_w / 2,
            sign_y + 3.4 * mm,
            _fit(tp, c, title_text, box_w - 5 * mm, tp._FONT, 5.4),
        )

    # Konular: 4 eşit kolon, homojen kart ızgarası.
    band_y = 85.5 * mm
    c.setFillColorRGB(*NAVY)
    c.rect(4.6 * mm, band_y, w - 9.2 * mm, 6.8 * mm, fill=1, stroke=0)
    c.setFillColorRGB(*SAFETY)
    c.rect(4.6 * mm, band_y, 58 * mm, 6.8 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont(tp._FONT_B, 7.5)
    c.drawCentredString(w / 2, band_y + 2.2 * mm, "YÜKSEKTE ÇALIŞMA EĞİTİM PROGRAMI VE KONU SÜRELERİ")

    topics = special_topics_with_minutes(profile)
    columns = _topic_columns(topics, 4)
    area_top = band_y - 3.5 * mm
    area_bottom = 26 * mm
    col_gap = 3.2 * mm
    col_w = (uw - 3 * col_gap) / 4
    for col_i, items in enumerate(columns):
        x = ml + col_i * (col_w + col_gap)
        if not items:
            continue
        card_gap = 2.1 * mm
        usable_h = area_top - area_bottom - card_gap * (len(items) - 1)
        card_h = usable_h / len(items)
        y_top = area_top
        for row_i, item in enumerate(items):
            y = y_top - card_h
            c.setFillColorRGB(1, 1, 1)
            c.setStrokeColorRGB(*LINE)
            c.setLineWidth(0.35)
            c.roundRect(x, y, col_w, card_h, 1.5 * mm, fill=1, stroke=1)

            mode = str(item.get("tur") or "")
            duration = int(item.get("dakika") or 0)
            c.setFillColorRGB(*TEAL if mode.casefold().startswith("teor") else SAFETY)
            c.roundRect(x + 1.2 * mm, y + card_h - 5.5 * mm, 23 * mm, 4.3 * mm, 1 * mm, fill=1, stroke=0)
            c.setFillColorRGB(1, 1, 1)
            c.setFont(tp._FONT_B, 4.8)
            c.drawCentredString(x + 12.7 * mm, y + card_h - 4.1 * mm, f"{mode.upper()} • {duration} DK")

            number = col_i * len(columns[0]) + row_i + 1
            c.setFillColorRGB(*NAVY)
            c.setFont(tp._FONT_B, 6)
            c.drawRightString(x + col_w - 2 * mm, y + card_h - 4.2 * mm, f"{number:02d}")

            topic_text = str(item.get("konu") or "")
            lines = _wrap(tp, c, topic_text, col_w - 4 * mm, tp._FONT, 5.25, 3)
            text_y = y + card_h - 9.2 * mm
            c.setFillColorRGB(*TEXT)
            c.setFont(tp._FONT, 5.25)
            for line in lines:
                c.drawString(x + 2 * mm, text_y, line)
                text_y -= 2.7 * mm
            y_top = y - card_gap

    # Hukuki dayanak ve uyarı; yüksekte çalışma belgesine özgü.
    c.setStrokeColorRGB(*SAFETY)
    c.setLineWidth(0.65)
    c.line(ml, 23.3 * mm, w - mr, 23.3 * mm)
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 5.1)
    c.drawString(ml, 19.7 * mm, "Hukuki Dayanak:")
    c.setFillColorRGB(*MUTED)
    c.setFont(tp._FONT, 4.55)
    legal_lines = _wrap(tp, c, HEIGHT_LEGAL_BASIS, uw - 27 * mm, tp._FONT, 4.55, 3)
    for idx, line in enumerate(legal_lines):
        c.drawString(ml + 25 * mm, 19.7 * mm - idx * 2.45 * mm, line)

    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 4.8)
    c.drawString(ml, 11.7 * mm, "Eğitici Uygunluğu:")
    c.setFillColorRGB(*MUTED)
    c.setFont(tp._FONT, 4.45)
    note_lines = _wrap(tp, c, HEIGHT_INSTRUCTOR_NOTE, uw - 31 * mm, tp._FONT, 4.45, 2)
    for idx, line in enumerate(note_lines):
        c.drawString(ml + 29 * mm, 11.7 * mm - idx * 2.35 * mm, line)

    c.setFont(tp._FONT, 4.3)
    c.drawString(ml, 6.6 * mm, _fit(tp, c, HEIGHT_DISCLAIMER, uw - 30 * mm, tp._FONT, 4.3))
    c.setFillColorRGB(*NAVY)
    c.setFont(tp._FONT_B, 5)
    c.drawRightString(w - mr, 6.5 * mm, f"Düzenleme: {bugun}")
