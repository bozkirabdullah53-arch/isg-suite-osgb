# -*- coding: utf-8 -*-
"""Generate training sector JSON from official NACE hazard-class CSV."""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = BACKEND_ROOT / "data" / "guncel_nace_tehlike_siniflari_2026.csv"
OUT_PATHS = [
    BACKEND_ROOT / "app" / "services" / "data" / "nace_sectors.json",
    BACKEND_ROOT.parent / "frontend" / "public" / "training-sectors.json",
]

DEFAULT_TOPICS = [
    "Makine ve ekipmanlarla güvenli çalışma",
    "İşyeri içi araç-yaya trafiği ve kör noktalar",
    "Elle taşıma, ergonomi ve güvenli istifleme",
    "Yangın, acil durum ve tahliye uygulamaları",
    "KKD kullanımı, bakım güvenliği ve işyeri düzeni",
]

COL_NACE = "NACE Altılı Kod"
COL_NAME = "Faaliyet Tanımı"
COL_HAZARD = "Tehlike Sınıfı"
COL_SECTION = "Kesit Kodu"
COL_SECTOR = "Ana Sektör"
COL_STATUS = "Durum"

HAZARD_CANONICAL = ("Az Tehlikeli", "Tehlikeli", "Çok Tehlikeli")

# The 13.03.2025 official appendix was originally transferred from a paginated
# table. A small number of wrapped descriptions crossed row boundaries during
# that transfer. Keep the corrections explicit and reviewable instead of
# guessing at runtime.
OFFICIAL_NAME_CORRECTIONS_2025 = {
    "01.13.19": "Diğer sebze tohumlarının yetiştiriciliği (şeker pancarı tohumu dahil, diğer pancar tohumları hariç)",
    "01.13.20": "Meyvesi yenen sebzelerin yetiştirilmesi",
    "13.10.14": "Jüt, keten ve diğer bitkisel tekstil elyaflarının bükülmesi ve iplik haline getirilmesi (pamuk hariç)",
    "13.10.15": "Suni ve sentetik elyafların bükülmesi ve iplik haline getirilmesi (filament ipliği ve suni ipek elyafı imalatı hariç)",
    "16.11.01": "Kereste imalatı (ağaçların biçilmesi, planyalanması, rendelenmesi ve şekillendirilmesi faaliyetleri)",
    "16.11.02": "Ahşap demir yolu veya tramvay traversi imalatı",
    "20.16.01": "Birincil formda poliamitler, üre reçineleri, melamin reçineleri, vb. plastik hammaddelerin imalatı",
    "20.16.02": "Birincil formda alkid reçine, polyester reçine, epoksi reçine, poliasetal, polikarbonat ile diğer polieter ve polyester imalatı",
    "20.59.01": "Fotoğrafik levha ve filmlerin (hassaslaştırılmış, ışığa maruz kalmamış olanlar), anında baskılanan filmlerin, fotoğrafçılıkta kullanılan kimyasal müstahzarların ve karışımsız (saf) ürünlerin imalatı",
    "20.59.02": "Tutkal imalatı",
    "20.59.10": "Dekapaj (temizleme) müstahzarları, eritkenler, hazır vulkanizasyon hızlandırıcı maddeler, kauçuk veya plastikler için plastikleştirici bileşikler ve stabilizatörler, diğer katalitik müstahzarların imalatı",
    "20.59.11": "Jelatin ve jelatin türevleri ile süt albüminlerinin imalatı (gıda endüstrisinde kullanılan jelatinler ve süt albüminleri hariç)",
    "26.30.03": "Kızıl ötesi (enfraruj) sinyal kullanan iletişim cihazlarının imalatı (örn: uzaktan kumanda cihazları)",
    "26.30.05": "Alıcı ve verici antenlerin imalatı (harici, teleskopik, çubuk, uydu, çanak ve hava ve deniz taşıtlarının antenleri)",
    "28.15.03": "Dişliler/dişli takımları, bilyeli ve makaralı vidalar, şanzımanlar, vites kutuları ve diğer hız değiştiricilerin imalatı (motorlu kara taşıtlarında kullanılan vites kutuları ve diferansiyelleri hariç)",
    "28.15.04": "Volanlar ve kasnaklar ile mafsallı bağlantı zincirleri ve güç aktarım zincirlerinin imalatı",
    "33.20.51": "Elektrikli ekipmanların kurulum hizmetleri (yollar, vb. için elektrikli sinyalizasyon ekipmanları hariç)",
    "38.21.05": "Tasnif edilmiş metal dışı atıklar, hurdalar ve diğer parçaların genellikle mekanik veya kimyasal değişim işlemleri ile geri kazanılması (plastik atıkların kimyasal işlemlerle geri kazanılması hariç)",
    "46.17.03": "Tütün ve tütün ürünlerinin toptan satışı ile ilgili aracıların faaliyetleri (aracı üretici birlikleri dahil)",
    "46.17.04": "İçeceklerin toptan satışı ile ilgili aracıların faaliyetleri",
    "46.38.02": "Ev hayvanları için yemlerin veya yiyeceklerin toptan ticareti (çiftlik hayvanları için olanlar hariç)",
    "46.38.03": "Gıda tuzu (sofra tuzu) toptan ticareti",
    "46.61.02": "Tarım, hayvancılık ve ormancılık makine ve ekipmanları ile aksam ve parçalarının toptan ticareti",
    "46.61.03": "Çim biçme ve bahçe makine ve ekipmanları ile aksam ve parçalarının toptan ticareti",
    "46.64.13": "Sanayi, ticaret, seyrüsefer ve diğer hizmetlerde kullanılmak üzere başka yerde sınıflandırılmamış diğer makinelere ait parçaların toptan ticareti (motorlu kara taşıtları için olanlar hariç)",
    "46.64.14": "Zırhlı veya güçlendirilmiş kasalar ve kutular ile kasa daireleri için zırhlı veya güçlendirilmiş kapılar ve kilitli kutular ile para veya evrak kutuları, vb. (adi metalden) toptan ticareti",
    "46.85.03": "Zirai kimyasal ürünlerin toptan ticareti (haşere ilaçları, yabancı ot ilaçları, dezenfektanlar, mantar ilaçları, çimlenmeyi önleyici ürünler, bitki gelişimini düzenleyiciler ve diğer zirai kimyasal ürünler)",
    "46.85.04": "Hayvansal veya bitkisel gübrelerin toptan ticareti (kapalı alanda yapılan ticaret)",
    "47.52.15": "Demirden veya çelikten merkezi ısıtma radyatörleri, merkezi ısıtma kazanları (kombiler dahil) ile bunların parçalarının perakende ticareti (buhar jeneratörleri ve kızgın su üreten kazanlar hariç)",
    "47.52.16": "Çim biçme ve bahçe ekipmanları perakende ticareti (kar küreyiciler dahil) (tarımda kullanılan el aletleri hariç)",
    "47.78.04": "Hediyelik eşyaların, el işi ürünlerin ve imitasyon takıların perakende ticareti (sanat eserleri hariç)",
    "47.78.07": "Optik ve hassas aletlerin perakende ticareti (mikroskop, dürbün ve pusula dahil; gözlük camı, fotoğrafik ürünler hariç)",
    "49.41.05": "Kara yolu ile canlı hayvan taşımacılığı (çiftlik hayvanları, kümes hayvanları, vahşi hayvanlar vb.)",
    "49.41.06": "Sürücüsü ile birlikte kamyon, beton mikseri ve diğer motorlu yük taşıma araçlarının kiralanması",
    "58.13.02": "Eğitime destek amaçlı dergi ve süreli yayınların yayımlanması (haftada dörtten az yayımlananlar)",
    "58.13.03": "Bilimsel, teknik, kültürel vb. dergi ve süreli yayınların yayımlanması (haftada dörtten az yayımlananlar)",
    "77.33.03": "Bilgisayar ve çevre birimlerinin operatörsüz olarak kiralanması ve leasingi (finansal leasing hariç)",
    "78.10.01": "İş bulma acentelerinin faaliyetleri (işe girecek kişilerin seçimi ve yerleştirilmesi faaliyetleri dahil)",
    "78.10.04": "Oyuncu seçme ajansları ve bürolarının faaliyetleri",
    "81.22.04": "Yapıların dış cepheleri için buharlı temizleme, kum püskürtme vb. uzmanlaşmış temizlik faaliyetleri",
    "81.22.05": "Yeni binaların inşaat sonrası temizliği",
    "91.30.00": "Kültürel mirasın konservasyonu, restorasyonu ve diğer destek faaliyetleri (müzeler ve özel koleksiyonlar dahil)",
    "94.99.16": "Engellilere, etnik gruplara ve azınlıklara yönelik üyelik gerektiren birlik ve kuruluşların faaliyetleri",
    "94.99.17": "Üyelik gerektiren, toplumsal hayatı geliştirme ve iyileştirmeye yönelik oluşturulan birlik ve kuruluşların faaliyetleri",
    "94.99.24": "Üyelik gerektiren mezun dernek ve birliklerinin faaliyetleri (profesyonel meslek kuruluşları hariç)",
    "94.99.99": "Üyelik gerektiren, başka yerde sınıflandırılmamış diğer üye olunan kuruluşların faaliyetleri (klasik araba birlikleri, kiracı birlikleri vb. dahil)",
}


def _collapse_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def normalize_hazard(raw: str) -> str | None:
    s = _collapse_ws(raw or "")
    if not s:
        return None
    lower = s.casefold()
    if "cok" in lower.replace("ç", "c") or "çok" in lower:
        if "tehlikeli" in lower:
            return "Çok Tehlikeli"
    if lower.startswith("az") and "tehlikeli" in lower:
        return "Az Tehlikeli"
    if "tehlikeli" in lower:
        return "Tehlikeli"
    for canonical in HAZARD_CANONICAL:
        if s == canonical:
            return canonical
    return None


def nace_to_code(nace: str) -> str:
    return "nace_" + nace.replace(".", "_")


def load_sectors() -> list[dict]:
    if not CSV_PATH.is_file():
        raise SystemExit(f"CSV not found: {CSV_PATH}")

    seen_nace: set[str] = set()
    items: list[dict] = []

    with CSV_PATH.open(encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            status = (row.get(COL_STATUS) or "").strip()
            if status and status.casefold() != "aktif":
                continue

            nace = _collapse_ws(row.get(COL_NACE) or "")
            if not nace:
                continue
            if nace in seen_nace:
                continue
            seen_nace.add(nace)

            name = OFFICIAL_NAME_CORRECTIONS_2025.get(
                nace, _collapse_ws(row.get(COL_NAME) or "")
            )
            hazard = normalize_hazard(row.get(COL_HAZARD) or "")
            if hazard is None:
                print(f"WARN: skip NACE {nace}: unknown hazard {row.get(COL_HAZARD)!r}", file=sys.stderr)
                continue

            section = _collapse_ws(row.get(COL_SECTION) or "") or None
            entry: dict = {
                "code": nace_to_code(nace),
                "name": name,
                "label": f"{nace} / {name} / {hazard}",
                "hazard_class": hazard,
                "nace": nace,
                "topics": list(DEFAULT_TOPICS),
            }
            if section:
                entry["section"] = section
            items.append(entry)

    legacy = {
        "code": "genel_uretim",
        "name": "Genel Fabrika ve Üretim",
        "label": "genel / Genel Fabrika ve Üretim / Tehlikeli",
        "hazard_class": "Tehlikeli",
        "nace": None,
        "topics": list(DEFAULT_TOPICS),
    }
    items.append(legacy)
    return items


def write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def main() -> None:
    data = load_sectors()
    for out in OUT_PATHS:
        write_json(out, data)
    print(len(data))
    if len(data) >= 2:
        print(data[0]["label"])
        print(data[1]["label"])
    print(data[-1]["label"])


if __name__ == "__main__":
    main()
