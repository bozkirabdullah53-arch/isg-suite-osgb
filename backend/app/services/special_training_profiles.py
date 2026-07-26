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


def resolve_training_document_titles(training) -> dict[str, str | None]:
    """Eğitim türüne göre belge / imza formu başlığı (özel eğitim ≠ temel İSG)."""
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
