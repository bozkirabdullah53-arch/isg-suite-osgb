"""NACE-aware risk assessment scope and roadmap.

The NACE code is used as a controlled starting scope for a risk assessment.  It
is deliberately not treated as a substitute for a workplace walk-through,
process review or the risk-assessment team's judgement.  In particular, this
module fails closed for a missing/unknown code and never guesses a neighbouring
sector.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.services.risk_regulations import get_regulations_for_category
from app.services.training_nace_classification import resolve_exact_nace


ROADMAP_SCHEMA_VERSION = "risk-nace-roadmap-v1"

STATUS_LABELS = {
    "verified": "Doğrulanmış NACE teknik eşleşmesi",
    "review_required": "Teknik risk eşleştirmesi uzman incelemesi bekliyor",
    "missing": "NACE kodu girilmemiş",
    "invalid": "NACE kodu katalogda bulunamadı",
}

# These are the report's common legal/control headings.  They intentionally
# describe the evidence to collect, rather than generating a risk record on
# the user's behalf.
REPORT_CHECKLIST: tuple[dict[str, Any], ...] = (
    {
        "key": "workplace_scope",
        "title": "İşyeri kapsamı ve NACE kimliği",
        "description": "İşyeri, şube/bölüm, adres, tehlike sınıfı, tam NACE kodu ve değerlendirme sınırları.",
        "legal_basis": "6331 md.10; Risk Değerlendirmesi Yönetmeliği md.8 ve md.11",
        "module": "risk",
    },
    {
        "key": "premises_layout",
        "title": "Bina, eklenti ve saha düzeni",
        "description": "Bina/eklentiler, geçişler, depolama alanları, kaçış yolları, yükleme-boşaltma ve saha yerleşimi.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.8",
        "module": "risk",
    },
    {
        "key": "activities_processes",
        "title": "Faaliyet, proses ve iş akışları",
        "description": "NACE kapsamındaki gerçek faaliyet; vardiya, bakım, temizlik, taşeron ve olağan dışı işler dahil.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.7-8",
        "module": "risk",
    },
    {
        "key": "equipment_energy",
        "title": "Makine, ekipman ve enerji kaynakları",
        "description": "Makine/araçlar, kaldırma-iletme, elektrik, basınç, hareketli aksam ve enerji izolasyonu.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.8; İş Ekipmanları Yönetmeliği",
        "module": "periodic_control",
    },
    {
        "key": "materials_chemicals_waste",
        "title": "Madde, malzeme, kimyasal ve atıklar",
        "description": "Kullanılan/depolanan maddeler, SDS/etiket, uyumsuzluklar, atıklar ve maruziyet yolları.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.8; Kimyasal Maddelerle Çalışmalarda ... Yönetmelik",
        "module": "sds",
    },
    {
        "key": "organization_workers",
        "title": "Organizasyon, görevler ve çalışan katılımı",
        "description": "Görev/yetki, çalışma düzeni, çalışan grupları, özel politika gerektiren gruplar ve çalışan görüşleri.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.8 ve md.15",
        "module": "personnel",
    },
    {
        "key": "nace_hazards",
        "title": "NACE'ye özgü tehlike alanları",
        "description": "Aşağıdaki NACE teknik risk başlıkları saha gözlemi, faaliyet ve bölüm bazında ayrı ayrı doğrulanır.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.7",
        "module": "risk",
    },
    {
        "key": "measurements_health",
        "title": "Ölçüm, sağlık gözetimi ve mevcut kanıtlar",
        "description": "Gerekli ortam ölçümleri, periyodik kontroller, sağlık gözetimi ve önceki olay/ramak kala kayıtlarının özeti; klinik veri rapora aktarılmaz.",
        "legal_basis": "6331 md.10; ilgili maruziyet ve ölçüm mevzuatı",
        "module": "ortam_olcum",
    },
    {
        "key": "emergency",
        "title": "Acil durum ve yangın senaryoları",
        "description": "NACE faaliyetinden doğan acil durumlar, ekipler, tahliye, ilk yardım, yangın ve tatbikat kanıtları.",
        "legal_basis": "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
        "module": "acil_plan",
    },
    {
        "key": "risk_scoring",
        "title": "Risk analizi yöntemi ve artık risk",
        "description": "Seçilen yöntem, olasılık/şiddet veya yöntem eksenleri, mevcut önlem sonrası skor ve öncelik seviyesi.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.7 ve md.11",
        "module": "risk",
    },
    {
        "key": "controls_dof",
        "title": "Kontrol hiyerarşisi ve DÖF",
        "description": "Ortadan kaldırma, ikame, mühendislik, idari önlem ve KKD sırasına göre önlem; sorumlu, termin, durum ve kanıt.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.10-11",
        "module": "capa",
    },
    {
        "key": "approval_revision",
        "title": "Ekip incelemesi, onay ve revizyon",
        "description": "Risk değerlendirme ekibi, işveren onayı, belge/revizyon numarası, imzalar ve değişiklik gerekçesi.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.11 ve md.15",
        "module": "esign",
    },
    {
        "key": "renewal_triggers",
        "title": "Yenileme ve tetikleyiciler",
        "description": "Yasal yenileme süresi ile kaza, proses/ekipman değişikliği, taşınma, yeni/önemli tehlike ve mevzuat değişiklikleri izlenir.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.12",
        "module": "risk",
    },
)


ROADMAP_STEPS: tuple[dict[str, Any], ...] = (
    {
        "key": "verify_scope",
        "phase": "Kapsam",
        "title": "NACE ve işyeri kapsamını doğrula",
        "description": "Tam NACE kodunu, faaliyet açıklamasını, tehlike sınıfını ve risk değerlendirmesine dahil işyerini karşılaştır.",
        "legal_basis": "6331 md.10; Risk Değerlendirmesi Yönetmeliği md.8",
        "module": "risk",
    },
    {
        "key": "map_processes",
        "phase": "Saha",
        "title": "Bölüm, faaliyet ve iş akışını çıkar",
        "description": "Her bölüm/faaliyet için normal, bakım/temizlik ve olağan dışı çalışma adımlarını saha ile doğrula.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.7-8",
        "module": "risk",
    },
    {
        "key": "inventory",
        "phase": "Saha",
        "title": "Ekipman, madde ve atık envanterini tamamla",
        "description": "Makine, kaldırma/taşıma, elektrik/enerji, kimyasal/SDS, depolama ve atıkları ilgili kayıtlarla eşleştir.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.8",
        "module": "periodic_control",
    },
    {
        "key": "worker_participation",
        "phase": "Saha",
        "title": "Çalışan gruplarını ve görüşlerini kaydet",
        "description": "Çalışan temsilcisi, deneyim, görev grupları ve özel politika gerektiren çalışanları değerlendirmeye dahil et.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.8 ve md.15",
        "module": "personnel",
    },
    {
        "key": "validate_nace_risks",
        "phase": "Analiz",
        "title": "NACE teknik risklerini saha gözlemiyle doğrula",
        "description": "NACE kataloğundan gelen başlıklar başlangıç kontrol listesidir; gerçekleşmeyenleri gerekçelendir, görülenleri bölüm/faaliyet bazında risk kaydına dönüştür.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.7",
        "module": "risk",
    },
    {
        "key": "evidence",
        "phase": "Analiz",
        "title": "Ölçüm, sağlık, acil durum ve geçmiş kayıt kanıtlarını bağla",
        "description": "Gerekli ortam ölçümleri, periyodik kontroller, sağlık gözetimi özeti, kaza/ramak kala ve tatbikat kayıtlarını referansla.",
        "legal_basis": "6331 md.10; ilgili özel mevzuat",
        "module": "ortam_olcum",
    },
    {
        "key": "score",
        "phase": "Analiz",
        "title": "Riskleri seçilen yöntemle puanla",
        "description": "Mevcut önlemleri dikkate alarak olasılık/şiddet veya seçilen yöntemin eksenleriyle ilk ve artık riski belirle.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.7 ve md.11",
        "module": "risk",
    },
    {
        "key": "controls",
        "phase": "Aksiyon",
        "title": "Kontrol hiyerarşisine göre DÖF oluştur",
        "description": "Önlem türünü, sorumluyu, termin tarihini, durumu ve tamamlanma kanıtını kaydet; artık riski yeniden değerlendir.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.10-11",
        "module": "capa",
    },
    {
        "key": "approval",
        "phase": "Onay",
        "title": "Ekip incelemesi, işveren onayı ve belge kontrolünü tamamla",
        "description": "Ekip katılımı, imza/onay, belge numarası, revizyon ve kapsam notunu raporla.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.11 ve md.15",
        "module": "esign",
    },
    {
        "key": "review",
        "phase": "İzleme",
        "title": "Yenileme ve değişiklik tetikleyicilerini izle",
        "description": "Süre, kaza, proses/ekipman değişikliği, taşınma, yeni/önemli tehlike ve mevzuat değişikliklerinde değerlendirmeyi yenile.",
        "legal_basis": "Risk Değerlendirmesi Yönetmeliği md.12",
        "module": "risk",
    },
)


TAG_LABELS: dict[str, str] = {
    "working_at_height": "Yüksekte çalışma ve düşmeye karşı korunma",
    "scaffolding": "İskele ve geçici çalışma platformları",
    "excavation": "Kazı ve göçük",
    "lifting": "Kaldırma ve taşıma faaliyetleri",
    "temporary_electricity": "Geçici elektrik tesisatı",
    "site_traffic": "Şantiye içi araç-yaya trafiği",
    "load_securing": "Yük sabitleme ve güvenli yükleme",
    "storage_stability": "Raf/istif stabilitesi ve yük düşmesi",
    "vehicle_traffic": "Araç-yaya trafiği ve çarpışma",
    "sharp_edges": "Keskin kenarlar ve kesilme",
    "forklifts": "Forklift ve araç kullanımı",
    "loading_docks": "Yükleme rampaları ve yükleme-boşaltma",
    "manual_handling": "Elle taşıma ve ergonomi",
    "falling_objects": "Yukarıdan cisim düşmesi",
    "machinery": "Makine ve hareketli aksam",
    "electrical": "Elektriksel tehlikeler",
    "fire": "Yangın ve tahliye",
    "chemical_exposure": "Kimyasal maruziyet",
    "biological_agents": "Biyolojik etkenler",
    "display_screen": "Ekranlı araçlar ve ergonomi",
    "psychosocial": "Psikososyal riskler",
    "noise": "Gürültü",
    "dust": "Toz maruziyeti",
    "confined_space": "Kapalı alan",
    "energy_isolation": "Enerji izolasyonu / kilitleme",
    "hot_work": "Sıcak çalışma",
    "cold_environment": "Soğuk ortam",
    "special_risk": "NACE'ye özgü özel risk",
    "dropped_load": "Yük düşmesi",
    "load_collapse": "İstif veya yük çökmesi",
    "vehicle_collision": "Araç çarpışması",

    # NACE kontrollü risk kataloğundaki görünen adlar. Anahtarlar veri
    # sözleşmesinde İngilizce kod olarak kalır; kullanıcı arayüzüne yalnızca
    # Türkçe karşılıkları gönderilir.
    "slips_trips": "Kayma, takılma ve düşme",
    "storage_racking": "Raf, depolama ve istifleme",
    "cutting_equipment": "Kesici ekipman kullanımı",
    "crowd_evacuation": "Kalabalık tahliyesi",
    "violence": "Şiddet",
    "machinery_entanglement": "Makineye kapılma ve sıkışma",
    "machine_entanglement": "Makineye kapılma ve sıkışma",
    "maintenance": "Bakım faaliyetleri",
    "textile_dust": "Tekstil tozu",
    "hot_surfaces": "Sıcak yüzeyler",
    "repetitive_work": "Tekrarlı işler ve ergonomi",
    "solder_fume": "Lehim dumanı",
    "static_electricity": "Statik elektrik",
    "robotics": "Robotik sistemler",
    "battery_fire": "Akü/batarya yangını",
    "molten_metal": "Erimiş metal",
    "metal_fume": "Metal dumanı",
    "fine_dust": "İnce toz",
    "heat_stress": "Isı stresi",
    "crushing": "Ezilme ve sıkışma",
    "hot_furnace": "Sıcak fırın",
    "silica_dust": "Silis tozu",
    "grinding": "Taşlama",
    "public_safety": "Kamu güvenliği",
    "laboratory_workshop": "Laboratuvar ve atölye çalışmaları",
    "emergency_evacuation": "Acil tahliye",
    "road_traffic": "Karayolu trafiği",
    "sharps": "Kesici-delici cisimler",
    "vehicle_lift": "Araç kaldırma lifti",
    "welding_fume": "Kaynak dumanı",
    "solvents": "Solventler",
    "high_voltage_vehicle": "Yüksek gerilimli araç sistemleri",
    "woodworking_machinery": "Ağaç işleme makineleri",
    "wood_dust": "Ahşap tozu",
    "nail_gun": "Çivi tabancası",
    "combustible_dust": "Yanıcı toz",
    "injection_moulding": "Enjeksiyon kalıplama",
    "hot_polymer": "Sıcak polimer",
    "conveyors": "Konveyörler",
    "fire_smoke": "Yangın ve duman",
    "ergonomics": "Ergonomi",
    "hot_oil": "Sıcak yağ",
    "lpg_natural_gas": "LPG ve doğal gaz",
    "food_hygiene": "Gıda hijyeni",
    "fitness_equipment": "Spor ekipmanları",
    "pool_chemicals": "Havuz kimyasalları",
    "first_aid": "İlk yardım",
    "printing_chemicals": "Baskı kimyasalları",
    "paper_dust": "Kağıt tozu",
    "heavy_rolls": "Ağır rulolar",
    "static_fire": "Statik elektrik kaynaklı yangın",
    "cutting_machinery": "Kesici makineler",
    "leather_dust": "Deri tozu",
    "adhesives": "Yapıştırıcılar",
    "equipment_inspection": "Ekipman kontrolü",
    "loading_unloading": "Yükleme ve boşaltma",
    "fuel_battery_fire": "Yakıt ve batarya yangını",
    "isocyanates": "İzosiyanatlar",
    "toxic_vapour": "Toksik buhar",
    "atex": "Patlayıcı ortam (ATEX)",
    "chemical_storage": "Kimyasal depolama",
    "mobile_plant": "Mobil iş makineleri",
    "rotating_equipment": "Döner ekipmanlar",
    "concrete_pump": "Beton pompası",
    "fume_hood": "Çeker ocak",
    "compressed_gases": "Basınçlı gazlar",
    "cryogenic_liquids": "Kriyojenik sıvılar",
    "crowd_management": "Kalabalık yönetimi",
    "weather": "Hava koşulları",
    "night_work": "Gece çalışması",
    "animal_contact": "Hayvan teması",
    "zoonoses": "Zoonozlar",
    "manure_gases": "Gübre gazları",
    "agricultural_machinery": "Tarım makineleri",
    "maintenance_pit": "Bakım çukuru",
    "rail_traffic": "Demiryolu trafiği",
    "rf_fields": "RF alanları",
    "roadside_work": "Yol kenarında çalışma",
    "lone_work": "Tek başına çalışma",
    "cleaning_chemicals": "Temizlik kimyasalları",
    "ladder_work": "Merdivenle çalışma",
    "high_voltage": "Yüksek gerilim",
    "tunnel_work": "Tünel çalışması",
    "cosmetic_chemicals": "Kozmetik kimyasallar",
    "skin_exposure": "Cilt maruziyeti",
    "sterilization": "Sterilizasyon",
    "powder_exposure": "Toz maruziyeti",
    "mixing_machinery": "Karıştırma makineleri",
    "clean_room": "Temiz oda",
    "server_room": "Sunucu odası",
    "food_machinery": "Gıda makineleri",
    "steam": "Buhar",
    "refrigerants": "Soğutucu gazlar",
    "security": "Güvenlik",
    "flammable_gases": "Yanıcı gazlar",
    "toxic_gases": "Toksik gazlar",
    "lead_exposure": "Kurşun maruziyeti",
    "sulfuric_acid": "Sülfürik asit",
    "hydrogen_gas": "Hidrojen gazı",
    "chemical_spill": "Kimyasal dökülme",
    "health_surveillance": "Sağlık gözetimi",
    "waste_sorting": "Atık ayrıştırma",
    "baling_machinery": "Balya makineleri",
    "dry_cleaning_solvents": "Kuru temizleme solventleri",
    "laundry_machinery": "Çamaşırhane makineleri",
    "active_pharmaceutical_dust": "Etkin farmasötik madde tozu",
    "heavy_materials": "Ağır malzemeler",
    "hot_process": "Sıcak proses",
    "cleaning_in_place": "Yerinde temizlik (CIP)",
    "bee_stings": "Arı sokması",
    "anaphylaxis": "Anafilaksi",
    "smoker_fire": "Dumanlayıcı kaynaklı yangın",
    "outdoor_weather": "Açık hava koşulları",
    "cold_chain": "Soğuk zincir",
    "suspicious_package": "Şüpheli paket",
    "travel_safety": "Seyahat güvenliği",
    "public_contact": "Halkla temas",
    "emergency": "Acil durum",
    "wire_drawing_machinery": "Tel çekme makineleri",
    "animal_attack": "Hayvan saldırısı",
    "anesthetic_gases": "Anestezik gazlar",
    "ionizing_radiation": "İyonlaştırıcı radyasyon",
    "flammable_liquids": "Yanıcı sıvılar",
    "lpg": "LPG",
    "disinfectants": "Dezenfektanlar",
    "arc_flash": "Ark parlaması",
    "electrical_panels": "Elektrik panoları",
    "permit_to_work": "Çalışma izin sistemi",
    "wild_animal_attack": "Yabani hayvan saldırısı",
    "animal_escape": "Hayvan kaçışı",
    "emergency_capture": "Acil yakalama",
    "tobacco_dust": "Tütün tozu",
    "nicotine_exposure": "Nikotin maruziyeti",
    "loading": "Yükleme",
    "organic_dust": "Organik toz",
    "animal_handling": "Hayvan taşıma ve elleçleme",
    "sharp_tools": "Keskin aletler",
    "segregated_storage": "Ayrıştırılmış kimyasal depolama",
    "spill_response": "Dökülmeye müdahale",
    "tanker_loading": "Tanker yükleme",
    "mineral_dust": "Mineral tozu",
    "hazardous_waste": "Tehlikeli atık",

    "dust_fire": "Toz kaynaklı yangın",
    "dust_explosion": "Toz patlaması",
    "chemical_overexposure": "Aşırı kimyasal maruziyeti",
    "silica_overexposure": "Aşırı silis maruziyeti",
    "molten_metal_release": "Erimiş metal boşalması",
    "severe_heat_stress": "İleri düzey ısı stresi",
    "confined_space_fatality": "Kapalı alanda ölümcül olay",
    "traffic_strike": "Trafik çarpması",
    "biological_exposure": "Biyolojik maruziyet",
    "vehicle_fall": "Araç düşmesi",
    "high_voltage_electrocution": "Yüksek gerilim elektrik çarpması",
    "paint_fire": "Boya yangını",
    "machine_amputation": "Makine kaynaklı uzuv kopması",
    "solvent_fire": "Solvent yangını",
    "molten_polymer_burn": "Erimiş polimer yanığı",
    "toxic_fire_smoke": "Toksik yangın dumanı",
    "flash_fire": "Parlama yangını",
    "toxic_release": "Toksik salım",
    "isocyanate_overexposure": "Aşırı izosiyanat maruziyeti",
    "fall_from_height": "Yüksekten düşme",
    "collapse": "Çökme ve göçük",
    "concrete_hose_whip": "Beton hortumu savrulması",
    "gas_cylinder_rupture": "Gaz tüpü yırtılması",
    "cryogenic_burn": "Kriyojenik yanık",
    "structural_collapse": "Yapısal çökme",
    "crowd_crush": "Kalabalık ezilmesi",
    "temporary_electrical_fatality": "Geçici elektrik kaynaklı ölümcül olay",
    "toxic_manure_atmosphere": "Toksik gübre atmosferi",
    "animal_crush": "Hayvan ezmesi",
    "zoonotic_exposure": "Zoonotik maruziyet",
    "electrocution": "Elektrik çarpması",
    "lone_worker_emergency": "Tek başına çalışan için acil durum",
    "train_strike": "Tren çarpması",
    "tunnel_emergency": "Tünel acil durumu",
    "vapour_cloud_explosion": "Buhar bulutu patlaması",
    "battery_thermal_runaway": "Batarya termal kaçak olayı",
    "waste_fire": "Atık yangını",
    "potent_compound_overexposure": "Etkin bileşik aşırı maruziyeti",
    "pressure_release": "Basınç tahliyesi",
    "wildfire": "Çevre yangını",
    "remote_area_emergency": "Uzak alanda acil durum",
    "zoonotic_outbreak": "Zoonotik salgın",
    "anesthetic_gas_overexposure": "Anestezik gaz aşırı maruziyeti",
    "vehicle_fire": "Araç yangını",
    "arc_flash_fatality": "Ark parlaması kaynaklı ölümcül olay",
    "energized_work": "Enerjili çalışma",
    "combustible_dust_explosion": "Yanıcı toz patlaması",
    "nicotine_overexposure": "Aşırı nikotin maruziyeti",
    "unknown_hazardous_material": "Bilinmeyen tehlikeli madde",
    "pile_collapse": "Yığın çökmesi",
    "major_fire": "Büyük yangın",
    "warehouse_fire": "Depo yangını",
    "tanker_release": "Tanker sızıntısı",
    "incompatible_reaction": "Uyumsuz kimyasal reaksiyon",
    "lead_poisoning": "Kurşun zehirlenmesi",
    "acid_burn": "Asit yanığı",
    "hydrogen_explosion": "Hidrojen patlaması",
}

TAG_CATEGORIES: dict[str, str] = {
    "working_at_height": "Yüksekte Çalışma Riskleri",
    "scaffolding": "Yüksekte Çalışma Riskleri",
    "lifting": "Mekanik Riskler",
    "load_securing": "Mekanik Riskler",
    "storage_stability": "Mekanik Riskler",
    "sharp_edges": "Mekanik Riskler",
    "vehicle_traffic": "Nakliye ve Trafik Riskleri",
    "forklifts": "Nakliye ve Trafik Riskleri",
    "loading_docks": "Nakliye ve Trafik Riskleri",
    "manual_handling": "Ergonomik Riskler",
    "chemical_exposure": "Kimyasal Riskler",
    "biological_agents": "Biyolojik Riskler",
    "noise": "Fiziksel Riskler",
    "dust": "Fiziksel Riskler",
    "fire": "Yangın ve Patlama Riskleri",
    "confined_space": "Mekanik Riskler",
    "electrical": "Elektrik Riskleri",
    "psychosocial": "Psikososyal Riskler",
}

BASE_REGULATIONS = (
    "6331 Sayılı İş Sağlığı ve Güvenliği Kanunu",
    "İş Sağlığı ve Güvenliği Risk Değerlendirmesi Yönetmeliği",
    "İşyeri Bina ve Eklentilerinde Alınacak Sağlık ve Güvenlik Önlemlerine İlişkin Yönetmelik",
    "İş Ekipmanlarının Kullanımında Sağlık ve Güvenlik Şartları Yönetmeliği",
    "Kişisel Koruyucu Donanım Yönetmeliği",
    "İşyerlerinde Acil Durumlar Hakkında Yönetmelik",
)


def _label(value: str) -> str:
    return TAG_LABELS.get(value, value.replace("_", " ").capitalize())


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(str(v).strip() for v in values if str(v).strip()))


def _safe_count(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _coverage(value: Mapping[str, Any] | None) -> dict[str, Any]:
    value = value or {}
    result = {
        "risk_records": _safe_count(value.get("risk_records")),
        "departments": _safe_count(value.get("departments")),
        "open_dofs": _safe_count(value.get("open_dofs")),
        "completed_dofs": _safe_count(value.get("completed_dofs")),
    }
    gaps: list[str] = []
    if result["departments"] == 0:
        gaps.append("Bölüm/faaliyet kapsamı henüz kayıt altına alınmamış.")
    if result["risk_records"] == 0:
        gaps.append("Bu işyeri için henüz risk kaydı yok; NACE başlıkları saha doğrulamasına alınmalı.")
    if result["risk_records"] > 0 and result["open_dofs"] == 0 and result["completed_dofs"] == 0:
        gaps.append("Risk kayıtlarına bağlı DÖF/önlem takibi bulunmuyor; uygunluk saha ekibi tarafından doğrulanmalı.")
    result["gaps"] = gaps
    result["status"] = "başlangıç" if gaps else "izleniyor"
    return result


def build_risk_nace_roadmap(
    company: Any,
    *,
    coverage: Mapping[str, Any] | None = None,
    nace_code_override: str | None = None,
    nace_source: str | None = None,
) -> dict[str, Any]:
    """Build a read-only, deterministic NACE risk scope for a company.

    ``company.nace_code`` is the canonical input.  ``nace_code_override`` is
    used only by the compatibility resolver when the selected company's
    legacy training records contain one unique exact NACE code.
    The returned checklist and roadmap are safe to display and embed in
    reports; they do not create or alter risk, DÖF, health or training records.
    """
    entered = str(
        nace_code_override if nace_code_override is not None
        else getattr(company, "nace_code", None) or ""
    ).strip() or None
    status = "missing" if not entered else "invalid"
    classification = None
    error_reason = None
    if entered:
        try:
            classification = resolve_exact_nace(entered)
            status = classification.classification_status
        except ValueError:
            sgk_scope_only = nace_source == "sgk_registry_nace" and len(entered.split(".")) == 2
            if sgk_scope_only:
                status = "review_required"
                error_reason = (
                    "SGK sicil numarasındaki dört haneli işkolu/NACE kodu okundu; "
                    "altı haneli faaliyet kodu SGK numarasından güvenli biçimde çıkarılamaz. "
                    "Resmî katalogdan altı haneli NACE doğrulanmalıdır."
                )
            else:
                error_reason = "Girilen kod resmî NACE kataloğunda tam eşleşmedi; başka bir NACE ile tahmin yapılmadı."

    technical_tags = list(getattr(classification, "technical_risk_tags", ()) or ())
    special_tags = list(getattr(classification, "special_risks", ()) or ())
    all_tags = technical_tags + special_tags
    related_categories = _unique([TAG_CATEGORIES[tag] for tag in all_tags if tag in TAG_CATEGORIES])
    related_regulations: list[str] = []
    for category in related_categories:
        related_regulations.extend(get_regulations_for_category(category))
    related_regulations = _unique(related_regulations)

    if status == "verified":
        next_action = "NACE teknik başlıklarını bölüm/faaliyet bazında saha gözlemiyle doğrulayın; gerçekleşenleri risk kaydı ve DÖF ile tamamlayın."
    elif status == "review_required":
        if nace_source == "sgk_registry_nace" and len((entered or "").split(".")) == 2:
            next_action = "SGK sicilindeki dört haneli işkolu kodu okundu; resmî katalogdan altı haneli NACE faaliyetini doğrulayın, ardından teknik risk başlıklarını saha ile eşleştirin."
        else:
            next_action = "NACE kimliği doğrulandı; teknik risk eşleştirmesi uzman tarafından saha ve proses verisiyle tamamlanmadan kapsamı kesin kabul etmeyin."
    elif status == "missing":
        next_action = "Firma kartına tam NACE kodunu girip resmî katalogdan seçin; kod girilmeden NACE'ye özgü kapsam üretilemez."
    else:
        next_action = "Firma kartındaki NACE kodunu resmî katalogdan tam olarak düzeltin; sistem komşu/genel sektör varsayımı yapmaz."

    warnings = [
        "NACE kodu yalnızca başlangıç kapsamıdır; saha gözlemi, proses doğrulaması ve risk değerlendirme ekibi incelemesi zorunludur.",
        "Bu yol haritası klinik sağlık verisi içermez ve sağlık kaydının yerine geçmez.",
    ]
    if status in {"missing", "invalid", "review_required"}:
        warnings.insert(0, STATUS_LABELS[status] + ".")
    if error_reason:
        warnings.insert(1, error_reason)

    checklist = [dict(item, required=True) for item in REPORT_CHECKLIST]
    technical_domains = [
        {
            "key": tag,
            "kind": "technical",
            "label": _label(tag),
            "required": True,
            "category": TAG_CATEGORIES.get(tag),
            "source": "controlled NACE technical-risk profile",
            "description": "Faaliyet/bölüm bazında tehlike, maruziyet, mevcut önlem, ilave önlem, skor, termin ve kanıt kaydı oluşturun.",
        }
        for tag in technical_tags
    ]
    special_domains = [
        {
            "key": tag,
            "kind": "special",
            "label": _label(tag),
            "required": True,
            "category": TAG_CATEGORIES.get(tag),
            "source": "controlled NACE special-risk profile",
            "description": "Özel risk senaryosunu ayrıca değerlendirin; saha koşulu yoksa ekip gerekçesini rapora yazın.",
        }
        for tag in special_tags
    ]

    identity = None
    if classification is not None:
        identity = {
            "code": classification.nace_code,
            "description": classification.nace_description,
            "section_code": classification.nace_section_code,
            "section_name": classification.nace_section_name,
            "subsector_code": classification.subsector_code,
            "activity_group_code": classification.activity_group_code,
            "content_profile_code": classification.content_profile_code,
            "content_profile_name": classification.content_profile_name,
            "hazard_class": classification.hazard_class,
            "training_topics": list(classification.training_topics),
            "classification_status": classification.classification_status,
            "catalog_version": classification.catalog_version,
            "catalog_hash": classification.catalog_hash,
        }

    return {
        "schema_version": ROADMAP_SCHEMA_VERSION,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "company_id": getattr(company, "id", None),
        "company_name": getattr(company, "name", None),
        "entered_nace_code": entered,
        "nace_source": nace_source if entered else None,
        # Firma kartındaki kimliği Risk Analizi'ne additive olarak taşıyoruz.
        # Risk kaydı üretmez/değiştirmez; yalnızca seçili company_id'nin
        # kaynak kimliğini ve rapor/arayüzde kullanılacak sicil bilgisini verir.
        "workplace": {
            "id": getattr(company, "id", None),
            "name": getattr(company, "name", None),
            "sgk_registry_no": getattr(company, "sgk_registry_no", None),
            "nace_code": entered,
            "nace_source": nace_source if entered else None,
            "hazard_class": getattr(company, "hazard_class", None),
        },
        "identity": identity,
        "technical_risk_tags": technical_domains,
        "special_risks": special_domains,
        "related_hazard_categories": related_categories,
        "regulations": {
            "common": list(BASE_REGULATIONS),
            "nace_related": related_regulations,
            "source_note": "Mevzuat başlıkları yol göstericidir; güncel metin ve işyerine özgü uygulanabilirlik ekip tarafından doğrulanır.",
        },
        "report_checklist": checklist,
        "roadmap": [dict(step, required=True) for step in ROADMAP_STEPS],
        "coverage": _coverage(coverage),
        "next_action": next_action,
        "warnings": warnings,
        "exact_catalog_match": classification is not None,
    }


__all__ = ["ROADMAP_SCHEMA_VERSION", "build_risk_nace_roadmap"]
