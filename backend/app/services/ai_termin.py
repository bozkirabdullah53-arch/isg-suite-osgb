"""Termin (bitiş tarihi) hesaplama motoru — saha fotoğrafı AI analizi (0.9.246).

Tespit edilen her tehlike için, şiddet seviyesi + ilgili mevzuat zorunluluğuna
göre otomatik bir düzeltici/önleyici faaliyet bitiş tarihi (termin) önerir.

Kural tabanlıdır; ücretli AI API gerektirmez. ai_vision.py tarafından kullanılır.

Dayanak:
- 6331 md.10 (risk değerlendirme + düzeltici/önleyici faaliyet)
- İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği
  (periyodik kontrol süreleri)
- 6331 md.27 (idari para cezası; geciken düzeltici faaliyet cezayı artırır)

Yaklaşım: Şiddet ne kadar yüksekse termin o kadar kısa. Mevzuatın açık bir
periyodik süre belirlediği hallerde (ör. yıllık periyodik kontrol) o tarih
esas alınır; şiddet ıraksasa bile mevzuat tarihi geçilmez.
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

TERMIN_ENGINE = "termin-v1-6331"

# Şiddet (1-5) → önerilen gün sayısı. AI analizinden gelen severity değerine
# göre seçilir. Mevzuat zorunluluğu bu tablonun üzerine yazabilir.
_SEVERITY_DAYS: dict[int, int] = {
    5: 3,   # Çok yüksek / kritik: 3 gün (acil)
    4: 7,   # Yüksek / kritik: 7 gün
    3: 30,  # Orta: 30 gün
    2: 60,  # Düşük: 60 gün
    1: 90,  # Çok düşük: 90 gün
}

# Mevzuat bazlı maksimum/zorunlu süreler (gün). Eğer ilgili mevzuat bir
# periyodik kontrol/düzeltme süresi belirtiyorsa, şiddet ıraksasa bile
# bu sınır aşılır ama mevzuat tarihi de çok geciktirilmez. Burada "kategorik"
# periyodik kontrol önerileri yer alır; gerçek periyodik kontrol tarihleri
# ayrı bir modülde (İş Ekipmanları) takip edilir.
_MEVZUAT_MAX_DAYS: dict[str, int] = {
    "Yüksekte Çalışma Riskleri": 15,      # acil iskele/korkuluk düzeltme
    "Yangın ve Patlama Riskleri": 7,      # yangın güvenliği acil
    "Elektrik Riskleri": 15,              # tesisat/topraklama acil
    "Kimyasal Riskler": 7,                # dökülme/maruziyet acil
    "Mekanik Riskler": 15,               # koruyucu/LOTO
    "Fiziksel Riskler": 30,               # gürültü/ölçüm
    "Biyolojik Riskler": 7,               # enfeksiyon kontrol
    "İnşaat ve Yapı Riskleri": 7,         # şantiye acil
    "Ergonomik Riskler": 60,
    "Psikososyal Riskler": 90,
    "Nakliye ve Trafik Riskleri": 15,
    "Çevresel Riskler": 30,
    "Diğer Riskler": 60,
}


def suggest_term(
    *,
    severity: int,
    category: str | None = None,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """Şiddet + mevzuat kategorisine göre bitiş tarihi (termin) önerir.

    severity: 1-5 (5 = en kritik)
    category: ai_hazard_hint.py kategori adı (mevzuat maksimumu için)
    reference_date: hesap tabanı; None ise bugün

    Döndürür: {engine, term_days, term_date, basis, note}
    """
    base = reference_date or date.today()
    sev = max(1, min(5, int(severity or 0) or 1))

    # 1. Şiddete göre önerilen gün
    sev_days = _SEVERITY_DAYS.get(sev, 90)

    # 2. Mevzuat maksimum gün (varsa) ile kıyasla
    mevzuat_max = _MEVZUAT_MAX_DAYS.get(category or "Diğer Riskler")

    if mevzuat_max is not None:
        # Kritik mevzuat kategorilerinde, şiddet düşük olsa bile termini
        # çok uzatma; ama şiddet acil istiyorsa mevzuat maksimumunu bekleme.
        # Eğilim: iki değerden makul olanı — kritikse kısa, değilse mevzuat.
        if sev >= 4:
            # Kritik: şiddet günü esas (daha kısa)
            term_days = min(sev_days, mevzuat_max)
            basis = f"şiddet {sev}/5 (kritik) → {sev_days} gün"
        else:
            # Kritik değil: mevzuat maksimumu aşma, ama şiddet kısa istiyorsa onu al
            term_days = min(sev_days, mevzuat_max)
            basis = f"şiddet {sev}/5 + mevzuat kategorisi '{category}' (max {mevzuat_max} gün)"
    else:
        term_days = sev_days
        basis = f"şiddet {sev}/5 → {sev_days} gün"

    term_date = base + timedelta(days=term_days)

    note = (
        f"Önerilen termin: {term_days} gün ({term_date.isoformat()}). "
        "Termin, 6331 md.10 düzeltici/önleyici faaliyet yükümlülüğü ve ilgili "
        "yönetmelik periyotları gözetilerek hesaplanmıştır. Uzman onayıyla "
        "uzatılabilir."
    )

    return {
        "engine": TERMIN_ENGINE,
        "term_days": term_days,
        "term_date": term_date.isoformat(),
        "basis": basis,
        "note": note,
    }
