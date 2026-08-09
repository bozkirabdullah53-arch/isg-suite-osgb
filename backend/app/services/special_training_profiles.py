# -*- coding: utf-8 -*-
"""ISG Pro 2026 — özel / uzmanlık eğitim profilleri (temel İSG'den bağımsız).

Kaynak: Sistem/Moduller/egitim/app.py SPECIAL_TRAINING_* sabitleri.
Temel eğitim akışını değiştirmez; Suite API bu katalogu okur.
"""
from __future__ import annotations

SPECIAL_TRAINING_PROFILES: dict[str, dict] = {
    "yuksekte_calisma": {
        "short_code": "YC",
        "title": "Yüksekte Çalışma Güvenliği Eğitimi",
        "certificate_title": "YÜKSEKTE ÇALIŞMA GÜVENLİĞİ EĞİTİMİ KATILIM VE BAŞARI BELGESİ",
        "attendance_title": "YÜKSEKTE ÇALIŞMA GÜVENLİĞİ EĞİTİMİ",
        "purpose": (
            "Çalışanların yüksekte çalışma tehlikelerini tanımasını, toplu ve kişisel "
            "korunma tedbirlerini doğru uygulamasını ve güvenli çalışma davranışı kazanmasını sağlamak."
        ),
        "legal_basis": (
            "6331 sayılı İş Sağlığı ve Güvenliği Kanunu, Çalışanların İş Sağlığı ve Güvenliği "
            "Eğitimlerinin Usul ve Esasları Hakkında Yönetmelik ve Yapı İşlerinde İş Sağlığı ve "
            "Güvenliği Yönetmeliği kapsamında kurum içi eğitim kaydıdır."
        ),
        "disclaimer": (
            "Bu belge eğitim katılımı ve başarı kaydıdır; mesleki yeterlilik belgesi, çalışma izin "
            "belgesi veya her koşulda yüksekte çalışma yetkisi yerine geçmez."
        ),
        "default_theory": 4,
        "default_practice": 4,
        "min_total": 4,
        "practice_required": True,
        "training_method": "Yüz yüze ve uygulamalı",
        "evaluation_methods": [
            "Yazılı ve uygulamalı değerlendirme",
            "Sözlü ve uygulamalı değerlendirme",
        ],
        "allowed_roles": ["isg_a", "isg_b", "isg_c", "yuksekte_egitmen"],
        "topics": [
            ("Yüksekte çalışma tanımı, kapsamı ve seviye farkı", "theory", 1.0),
            ("Tehlike tanımlama ve işe özel risk değerlendirmesi", "theory", 1.2),
            ("Çalışmaktan kaçınma ve alternatif çalışma yöntemleri", "theory", 0.8),
            ("Toplu korunma tedbirlerinin önceliği", "theory", 1.0),
            ("Korkuluklar, platformlar ve güvenli geçişler", "theory", 0.9),
            ("İskele, merdiven ve erişim sistemleri", "theory", 1.0),
            ("Kişisel düşüş durdurma sistemleri", "theory", 1.1),
            ("Ankraj, yaşam hattı, bağlantı elemanları ve düşüş faktörü", "theory", 1.1),
            ("Serbest düşme açıklığı ve sarkaç etkisi", "theory", 0.8),
            ("Askıda kalma travması ve ilk müdahale", "theory", 0.8),
            ("Hava şartları, malzeme düşmesi ve çevresel riskler", "theory", 0.8),
            ("Kurtarma planı ve acil durum organizasyonu", "theory", 1.0),
            ("Tam vücut kemerinin kontrolü ve doğru giyilmesi", "practice", 1.2),
            ("Ankraj ve bağlantı uygulaması", "practice", 1.2),
            ("Güvenli yükselme, konumlanma ve hareket uygulaması", "practice", 1.2),
            ("Kurtarma / tahliye senaryosu ve uygulamalı değerlendirme", "practice", 1.4),
        ],
    },
    "hijyen_sanitasyon": {
        "short_code": "HS",
        "title": "İşyeri İçi Hijyen ve Sanitasyon Bilgilendirme Eğitimi",
        "certificate_title": "İŞYERİ İÇİ HİJYEN VE SANİTASYON BİLGİLENDİRME EĞİTİMİ KATILIM BELGESİ",
        "attendance_title": "İŞYERİ İÇİ HİJYEN VE SANİTASYON BİLGİLENDİRME EĞİTİMİ",
        "purpose": (
            "Çalışanların kişisel ve işyeri hijyeni, bulaşın önlenmesi, temizlik, dezenfeksiyon "
            "ve sanitasyon uygulamalarında doğru davranış kazanmasını sağlamak."
        ),
        "legal_basis": (
            "6331 sayılı İş Sağlığı ve Güvenliği Kanunu kapsamında işverenin bilgilendirme ve "
            "eğitim yükümlülüğünü destekleyen kurum içi / hizmet içi eğitim kaydıdır."
        ),
        "disclaimer": (
            "Bu belge kurum içi / hizmet içi eğitim kaydıdır; MEB onaylı Hijyen Eğitimi Belgesi "
            "veya resmî kurs bitirme belgesi yerine geçmez."
        ),
        "default_theory": 3,
        "default_practice": 1,
        "min_total": 2,
        "practice_required": False,
        "training_method": "Yüz yüze",
        "evaluation_methods": [
            "Yazılı değerlendirme",
            "Sözlü değerlendirme",
            "Yazılı ve uygulamalı değerlendirme",
        ],
        "allowed_roles": [
            "isyeri_hekimi",
            "hekim",
            "hemsire",
            "isyeri_hemsiresi",
            "diger_saglik_personeli",
            "saglik_memuru",
            "ebe",
            "cevre_sagligi",
        ],
        "topics": [
            ("Kişisel hijyenin temel ilkeleri", "theory", 1.0),
            ("El hijyeni ve doğru el yıkama tekniği", "theory", 1.2),
            ("İş kıyafetleri ve kişisel koruyucu donanım temizliği", "theory", 0.9),
            ("Temizlik, dezenfeksiyon ve sanitasyon kavramları", "theory", 1.1),
            ("Biyolojik riskler ve bulaşma yolları", "theory", 1.2),
            ("Çapraz bulaşmanın önlenmesi", "theory", 1.1),
            ("Ortak kullanım alanları, lavabo, tuvalet ve soyunma alanları", "theory", 0.9),
            ("Gıda ve içme suyu hijyeni", "theory", 0.8),
            ("Atıkların güvenli toplanması ve uzaklaştırılması", "theory", 0.8),
            ("Zararlılarla mücadele ve ortam hijyeni", "theory", 0.7),
            ("Bulaşıcı hastalık belirtileri ve bildirim sorumluluğu", "theory", 0.9),
            ("Salgın dönemlerinde işyeri tedbirleri", "theory", 0.8),
            ("Doğru el yıkama ve el antiseptiği uygulaması", "practice", 1.0),
            ("İşyerine özgü temizlik / sanitasyon uygulaması", "practice", 1.0),
        ],
    },
    "gida_su_hijyeni": {
        "short_code": "GSH",
        "title": "Gıda ve Su Sektöründe Hijyen Eğitimi",
        "certificate_title": "GIDA VE SU SEKTÖRÜNDE HİJYEN EĞİTİMİ KATILIM BELGESİ",
        "attendance_title": "GIDA VE SU SEKTÖRÜNDE HİJYEN EĞİTİMİ",
        "purpose": "Gıda ve suyla temas eden çalışanların kişisel hijyen, güvenli su, çapraz bulaşmanın önlenmesi ve hijyenik çalışma uygulamalarını doğru biçimde uygulamasını sağlamak.",
        "legal_basis": "1593 sayılı Umumi Hıfzıssıhha Kanunu, 5996 sayılı Veteriner Hizmetleri, Bitki Sağlığı, Gıda ve Yem Kanunu, Hijyen Eğitimi Yönetmeliği ve Gıda Hijyeni Yönetmeliği kapsamında kurum içi eğitim kaydıdır.",
        "disclaimer": "Bu belge, mevzuat kapsamındaki işyeri eğitim kaydıdır; resmî ruhsat, işletme kayıt/onay belgesi veya mesleki yeterlilik belgesi yerine geçmez.",
        "default_theory": 3,
        "default_practice": 1,
        "min_total": 2,
        "practice_required": True,
        "training_method": "Yüz yüze ve uygulamalı",
        "evaluation_methods": ["Yazılı ve uygulamalı değerlendirme", "Yazılı değerlendirme"],
        "allowed_roles": ["gida_muhendisi", "veteriner_hekim", "isyeri_hekimi", "hijyen_egitmeni"],
        "topics": [
            ("Gıda ve su hijyeninin amacı ve çalışan sorumlulukları", "theory", 1.0),
            ("Kişisel hijyen, el yıkama ve el antiseptiği", "theory", 1.3),
            ("Bulaşma yolları ve çapraz bulaşmanın önlenmesi", "theory", 1.3),
            ("Gıda kaynaklı biyolojik, kimyasal ve fiziksel tehlikeler", "theory", 1.2),
            ("İçme ve kullanma suyunun güvenliği; su depoları ve dağıtım", "theory", 1.1),
            ("Soğuk zincir, sıcaklık kontrolü ve güvenli depolama", "theory", 1.1),
            ("Temizlik, dezenfeksiyon, ekipman ve yüzey hijyeni", "theory", 1.2),
            ("Atık yönetimi, haşere kontrolü ve personel hastalık bildirimi", "theory", 1.0),
            ("El yıkama, yüzey dezenfeksiyonu ve hijyen kontrol listesi uygulaması", "practice", 1.2),
            ("Gıda/su akışında kritik kontrol noktası ve uygunsuzluk bildirimi", "practice", 1.2),
        ],
    },
}

SPECIAL_VERIFICATION_METHODS = {
    "kimlik_ve_belge_asli": "Kimlik ve mesleki belgenin aslı görülerek doğrulandı",
    "kurum_ozluk_dosyasi": "Kurum özlük dosyası üzerinden doğrulandı",
    "resmi_dogrulama": "İlgili resmî / e-Devlet doğrulama ekranından kontrol edildi",
}

SPECIAL_INSTRUCTOR_ROLES = {
    "isg_a": {"label": "A Sınıfı İş Güvenliği Uzmanı", "profiles": ["yuksekte_calisma"]},
    "isg_b": {"label": "B Sınıfı İş Güvenliği Uzmanı", "profiles": ["yuksekte_calisma"]},
    "isg_c": {"label": "C Sınıfı İş Güvenliği Uzmanı", "profiles": ["yuksekte_calisma"]},
    "yuksekte_egitmen": {"label": "Belgeli Yüksekte Çalışma Eğitmeni", "profiles": ["yuksekte_calisma"]},
    "isyeri_hekimi": {"label": "İşyeri Hekimi", "profiles": ["hijyen_sanitasyon"]},
    "hekim": {"label": "Hekim", "profiles": ["hijyen_sanitasyon"]},
    "hemsire": {"label": "Hemşire", "profiles": ["hijyen_sanitasyon"]},
    "isyeri_hemsiresi": {"label": "İşyeri Hemşiresi", "profiles": ["hijyen_sanitasyon"]},
    "diger_saglik_personeli": {"label": "Diğer Sağlık Personeli", "profiles": ["hijyen_sanitasyon"]},
    "saglik_memuru": {"label": "Sağlık Memuru", "profiles": ["hijyen_sanitasyon"]},
    "ebe": {"label": "Ebe", "profiles": ["hijyen_sanitasyon"]},
    "cevre_sagligi": {"label": "Çevre Sağlığı Teknisyeni / Teknikeri", "profiles": ["hijyen_sanitasyon"]},
}


def profile_total_hours(profile: dict) -> int:
    """Özel eğitim toplam ders saati (teorik + uygulamalı)."""
    return int(profile.get("default_theory") or 0) + int(profile.get("default_practice") or 0)


def profile_duration_hint(profile: dict) -> str:
    theory = int(profile.get("default_theory") or 0)
    practice = int(profile.get("default_practice") or 0)
    total = theory + practice
    if practice:
        return f"{total} ders saati ({theory} teorik + {practice} uygulamalı)"
    return f"{total} ders saati ({theory} teorik)"


def resolve_special_duration_hours(training) -> int | None:
    """Özel eğitim ise mevzuat/profil saatini döner; temel İSG ise None."""
    key = resolve_special_profile_key(training)
    if not key:
        return None
    return profile_total_hours(SPECIAL_TRAINING_PROFILES[key])


def special_profiles_for_api() -> list[dict]:
    items = []
    for key, profile in SPECIAL_TRAINING_PROFILES.items():
        theory = int(profile.get("default_theory") or 0)
        practice = int(profile.get("default_practice") or 0)
        topics = [
            {"title": title, "mode": mode, "weight": weight}
            for title, mode, weight in profile.get("topics") or []
        ]
        items.append({
            "code": key,
            "short_code": profile.get("short_code"),
            "title": profile.get("title"),
            "certificate_title": profile.get("certificate_title"),
            "attendance_title": profile.get("attendance_title"),
            "purpose": profile.get("purpose"),
            "legal_basis": profile.get("legal_basis"),
            "disclaimer": profile.get("disclaimer"),
            "default_theory_hours": theory,
            "default_practice_hours": practice,
            "default_total_hours": theory + practice,
            "duration_hint": profile_duration_hint(profile),
            "min_total_hours": profile.get("min_total"),
            "practice_required": bool(profile.get("practice_required")),
            "training_method": profile.get("training_method"),
            "evaluation_methods": list(profile.get("evaluation_methods") or []),
            "allowed_roles": list(profile.get("allowed_roles") or []),
            "topics": topics,
        })
    return items


def special_meta_for_api() -> dict:
    return {
        "profiles": special_profiles_for_api(),
        "instructor_roles": [
            {"code": code, "label": meta["label"], "profiles": list(meta["profiles"])}
            for code, meta in SPECIAL_INSTRUCTOR_ROLES.items()
        ],
        "verification_methods": [
            {"code": code, "label": label}
            for code, label in SPECIAL_VERIFICATION_METHODS.items()
        ],
    }


DEFAULT_CERTIFICATE_TITLE = "TEMEL İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİMİ KATILIM BELGESİ"
DEFAULT_ATTENDANCE_TITLE = "İŞ SAĞLIĞI VE GÜVENLİĞİ TEMEL EĞİTİMİ"
DEFAULT_TOPICS_HEADER = "İŞ SAĞLIĞI VE GÜVENLİĞİ EĞİTİM KONULARI"
SPECIAL_TOPICS_HEADER = "EĞİTİM PROGRAMI VE KONU SÜRELERİ"


def resolve_special_profile_key(training) -> str | None:
    """Eğitim kaydından özel profil kodunu çözer."""
    haystack = " ".join(
        str(x or "")
        for x in (
            getattr(training, "training_type", None),
            getattr(training, "title", None),
            getattr(training, "notes", None),
        )
    ).casefold()

    for key, profile in SPECIAL_TRAINING_PROFILES.items():
        markers = [
            key.replace("_", " "),
            str(profile.get("title") or ""),
            str(profile.get("short_code") or ""),
        ]
        if key == "yuksekte_calisma":
            markers += ["yüksekte çalışma", "yuksekte calisma", "yüksekte"]
        if key == "hijyen_sanitasyon":
            markers += ["hijyen", "sanitasyon", "hijyen ve sanitasyon"]
        for marker in markers:
            m = str(marker or "").strip().casefold()
            if m and m in haystack:
                return key
    return None


def resolve_training_document_titles(training) -> dict[str, str | None]:
    """Eğitim türüne göre belge / imza formu başlığı (özel eğitim ≠ temel İSG)."""
    key = resolve_special_profile_key(training)
    if key:
        profile = SPECIAL_TRAINING_PROFILES[key]
        return {
            "certificate_title": str(profile.get("certificate_title") or DEFAULT_CERTIFICATE_TITLE),
            "attendance_title": str(profile.get("attendance_title") or DEFAULT_ATTENDANCE_TITLE),
            "profile_key": key,
        }
    return {
        "certificate_title": DEFAULT_CERTIFICATE_TITLE,
        "attendance_title": DEFAULT_ATTENDANCE_TITLE,
        "profile_key": None,
    }


def _round_to_five(value: float) -> int:
    return max(5, int(round(float(value) / 5.0) * 5))


def weighted_minute_distribution(
    topics: list[str],
    target_minutes: int,
    weights: list[float] | None = None,
) -> list[tuple[str, int]]:
    """Konu sürelerini ağırlıklarla, 5 dakikalık birimlerle hedefe dağıtır (Pro)."""
    topics = list(topics or [])
    if not topics:
        return []
    if weights is None:
        weights = [1.0] * len(topics)
    weights = [max(0.1, float(x)) for x in list(weights)[: len(topics)]]
    if len(weights) < len(topics):
        weights.extend([1.0] * (len(topics) - len(weights)))

    target_minutes = int(target_minutes)
    total_weight = sum(weights) or 1.0
    distribution = [_round_to_five(target_minutes * w / total_weight) for w in weights]
    diff = target_minutes - sum(distribution)

    order = sorted(range(len(topics)), key=lambda i: (-weights[i], i))
    while diff >= 5:
        for i in order:
            if diff < 5:
                break
            distribution[i] += 5
            diff -= 5
    while diff <= -5:
        changed = False
        for i in reversed(order):
            if diff > -5:
                break
            if distribution[i] > 5:
                distribution[i] -= 5
                diff += 5
                changed = True
        if not changed:
            break
    if diff:
        distribution[order[0]] += diff

    return list(zip(topics, distribution))


def special_topics_with_minutes(
    profile: dict,
    theory_hours: int | None = None,
    practice_hours: int | None = None,
) -> list[dict]:
    """Özel eğitim müfredatını ders saati × 45 dk ile dakikalandırır."""
    theory_hours = int(theory_hours if theory_hours is not None else profile.get("default_theory") or 0)
    practice_hours = int(
        practice_hours if practice_hours is not None else profile.get("default_practice") or 0
    )
    theory_topics = [(title, weight) for title, mode, weight in profile.get("topics") or [] if mode == "theory"]
    practice_topics = [
        (title, weight) for title, mode, weight in profile.get("topics") or [] if mode == "practice"
    ]
    result: list[dict] = []
    if theory_topics and theory_hours:
        distributed = weighted_minute_distribution(
            [title for title, _w in theory_topics],
            theory_hours * 45,
            [weight for _t, weight in theory_topics],
        )
        result.extend({"tur": "Teorik", "konu": title, "dakika": minute} for title, minute in distributed)
    if practice_topics and practice_hours:
        distributed = weighted_minute_distribution(
            [title for title, _w in practice_topics],
            practice_hours * 45,
            [weight for _t, weight in practice_topics],
        )
        result.extend({"tur": "Uygulama", "konu": title, "dakika": minute} for title, minute in distributed)
    return result


def _topics_to_pdf_columns(topics: list[dict]) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """PDF draw_col formatı: (başlık_mı, metin)."""
    middle = (len(topics) + 1) // 2

    def column(chunk: list[dict]) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        last_type = None
        for item in chunk:
            tur = str(item.get("tur") or "")
            if tur != last_type:
                out.append((1, tur.upper()))
                last_type = tur
            out.append((0, f"- {item.get('konu', '')} - {item.get('dakika', 0)} DK"))
        return out

    return column(topics[:middle]), column(topics[middle:])


def special_topics_summary(profile: dict) -> str:
    """İmza formu konu özeti."""
    theory = [t for t, mode, _w in profile.get("topics") or [] if mode == "theory"]
    practice = [t for t, mode, _w in profile.get("topics") or [] if mode == "practice"]
    parts: list[str] = []
    if theory:
        shown = theory[:8]
        extra = f" (+{len(theory) - 8})" if len(theory) > 8 else ""
        parts.append("Teorik: " + "; ".join(shown) + extra)
    if practice:
        parts.append("Uygulama: " + "; ".join(practice))
    return " | ".join(parts) if parts else ""


def resolve_training_curriculum(training) -> dict:
    """Belge / imza formu için başlık + müfredat (özel veya temel)."""
    titles = resolve_training_document_titles(training)
    key = titles.get("profile_key")
    if not key:
        return {
            **titles,
            "is_special": False,
            "profile": None,
            "topics_header": DEFAULT_TOPICS_HEADER,
            "purpose": None,
            "legal_basis": None,
            "disclaimer": None,
            "sol": None,
            "sag": None,
            "konu_ozeti": None,
            "duration_hours": None,
            "duration_label": None,
            "duration_hint": None,
        }

    profile = SPECIAL_TRAINING_PROFILES[key]
    topics = special_topics_with_minutes(profile)
    sol, sag = _topics_to_pdf_columns(topics)
    total = profile_total_hours(profile)
    return {
        **titles,
        "is_special": True,
        "profile": profile,
        "topics_header": SPECIAL_TOPICS_HEADER,
        "purpose": str(profile.get("purpose") or ""),
        "legal_basis": str(profile.get("legal_basis") or ""),
        "disclaimer": str(profile.get("disclaimer") or ""),
        "sol": sol,
        "sag": sag,
        "konu_ozeti": special_topics_summary(profile),
        "duration_hours": total,
        "duration_label": f"{total} DERS SAAT" if total else None,
        "duration_hint": profile_duration_hint(profile),
    }
