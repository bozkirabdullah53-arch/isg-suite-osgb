"""Saha fotoğrafı → yapay zeka destekli risk analizi (0.9.246).

Hibrit mimari; VISION_PROVIDER ayarına göre üç moddan biri çalışır:
- heuristic (default): medya metaverisi (dosya adı, description, EXIF GPS) +
  ilişkili risk kaydının activity/risk_definition metninden tehlike kategorisi
  çıkarımı. Ücretli API gerektirmez; mevcut ai_hazard_hint.py'yi kullanır.
- api: OpenAI uyumlu vision LLM (varsayılan openai/gpt-5.4-mini) — görüntü + İSG promptu
  → JSON (riskler, bounding box, şiddet). Ücretli; explicit API key gerekir.
- yolo: ön-eğitilmiş nesne tespiti (ultralytics) — KKD/iskele/elektrik vb.
  nesneler + bbox. İSG yorumlama için api veya heuristic'e düşer.

Tüm modlarda çıktı aynı şemaya normalize edilir:
{
  engine, provider, hazards: [{category, hazard_key, hazard_name, severity,
  confidence, bbox}],
  bbox_annotations: [{label, severity, box: [x,y,w,h], confidence}],
  note
}

Güvenlik:
- API hatasında hiçbir istisna fırlatılmaz ve sahte görsel bulgu üretilmez;
  analiz kullanılabilir değil olarak döner.
- API modunda görüntü yalnızca explicit API key varken gönderilir.
- Hiçbir mevcut endpoint/model değiştirilmez; bu yalnızca okuma+analiz.
"""
from __future__ import annotations

import base64
import json
import logging
import re
import unicodedata
from typing import Any

from app.core.config import settings
from app.services.ai_hazard_hint import suggest_hazard_from_text
from app.services.ai_mevzuat import (
    build_report as build_mevzuat_report,
    build_visual_report,
    get_visual_hazard_profile,
)
from app.services.ai_termin import suggest_term

logger = logging.getLogger(__name__)

VISION_ENGINE = "vision-v1"

# Fotoğraf etiketleri (risk_photo_tags.py) → tehlike kategorisi eşlemesi.
# Bu, heuristic modda medya etiketlerinden kategori çıkarımı için kullanılır.
_TAG_TO_CATEGORY: dict[str, str] = {
    "ppe_missing": "Diğer Riskler",
    "slippery_floor": "Fiziksel Riskler",
    "electrical": "Elektrik Riskleri",
    "work_at_height": "Yüksekte Çalışma Riskleri",
    "unguarded_machine": "Mekanik Riskler",
    "chemical_spill": "Kimyasal Riskler",
    "fire_hot_work": "Yangın ve Patlama Riskleri",
    "confined_space": "Diğer Riskler",
    "falling_object": "Yüksekte Çalışma Riskleri",
    "poor_housekeeping": "Mekanik Riskler",
    "noise_vibration": "Fiziksel Riskler",
    "other": "Diğer Riskler",
}

# Fotoğraf etiketi → tipik şiddet (1-5). Sahada yaygın görülen durumlar.
_TAG_TO_SEVERITY: dict[str, int] = {
    "ppe_missing": 3,
    "slippery_floor": 3,
    "electrical": 4,
    "work_at_height": 4,
    "unguarded_machine": 5,
    "chemical_spill": 4,
    "fire_hot_work": 5,
    "confined_space": 4,
    "falling_object": 4,
    "poor_housekeeping": 2,
    "noise_vibration": 3,
    "other": 2,
}

# Bounding box: görüntü boyutları bilinmediği için heuristic modda tüm çerçeve
# varsayılanı (görselin tamamı). API/YOLO modları gerçek koordinat döner.
_FULL_FRAME_BBOX = [0.0, 0.0, 1.0, 1.0]  # normalize [x, y, w, h] (0-1)

_VISION_CATEGORIES = {
    "Yüksekte Çalışma Riskleri",
    "Yangın ve Patlama Riskleri",
    "Elektrik Riskleri",
    "Kimyasal Riskler",
    "Mekanik Riskler",
    "Fiziksel Riskler",
    "Biyolojik Riskler",
    "Ergonomik Riskler",
    "İnşaat ve Yapı Riskleri",
    "Nakliye ve Trafik Riskleri",
    "Diğer Riskler",
}

_VISUAL_HAZARD_KEY_ALIASES = {
    "stair_obstruction": "stair_obstruction",
    "stairway_obstruction": "stair_obstruction",
    "stairs_obstruction": "stair_obstruction",
    "housekeeping_obstruction": "housekeeping_obstruction",
    "poor_housekeeping": "housekeeping_obstruction",
    "trip_obstruction": "housekeeping_obstruction",
}


def _fold_text(value: Any) -> str:
    """Türkçe metni anahtar kelime karşılaştırması için sadeleştirir."""
    raw = unicodedata.normalize("NFKD", str(value or "").casefold())
    raw = "".join(ch for ch in raw if not unicodedata.combining(ch))
    return raw.replace("ı", "i")


def _normalize_visual_hazard_key(value: Any) -> str | None:
    raw = _fold_text(value).strip().replace("-", "_").replace(" ", "_")
    return _VISUAL_HAZARD_KEY_ALIASES.get(raw)


def _infer_visual_hazard_key(hazard: dict[str, Any]) -> str | None:
    """Modelin somut görsel açıklamasından dar tehlike kimliği çıkarır."""
    text = _fold_text(" ".join(
        str(hazard.get(field) or "")
        for field in ("observed", "note")
    ))
    if not text:
        return None

    stair_terms = ("merdiven", "basamak", "sahanlik", "stair", "step")
    object_terms = (
        "kova", "bidon", "damacana", "poset", "kutu", "malzeme", "esya", "sise",
        "bottle", "bottles", "box", "boxes", "bag", "bags", "bucket", "buckets",
        "container", "containers", "item", "items", "object", "objects", "carton",
        "duzensiz", "daginik", "clutter", "cluttered",
    )
    obstruction_terms = (
        "engel", "engell", "gecis", "gecis yolu", "yol", "daralt", "takil",
        "obstruct", "obstacle", "trip", "blocked", "walkway", "passage",
        "access", "clutter", "gecir", "dusme", "kayma", "fall",
    )
    stair_obstruction_terms = (
        "engel", "engell", "gecis", "daralt", "takil", "obstruct", "obstacle",
        "trip", "blocked", "walkway", "passage", "access",
    )
    has_stairs = any(term in text for term in stair_terms)
    has_objects = any(term in text for term in object_terms)
    has_obstruction = any(term in text for term in obstruction_terms)

    if has_stairs and (has_objects or any(term in text for term in stair_obstruction_terms)):
        return "stair_obstruction"
    if has_objects and has_obstruction:
        return "housekeeping_obstruction"
    return None


def _annotate_visual_hazard(hazard: dict[str, Any]) -> dict[str, Any]:
    """Görsel kanıtı varsa hazard'ı tehlike profiliyle zenginleştirir."""
    key = (
        _normalize_visual_hazard_key(hazard.get("hazard_key"))
        or _infer_visual_hazard_key(hazard)
    )
    profile = get_visual_hazard_profile(key)
    if not profile:
        return hazard

    enriched = dict(hazard)
    enriched.update({
        "hazard_key": key,
        "hazard_code": profile["hazard_code"],
        "hazard_name": profile["hazard_name"],
        "detail_category": profile["detail_category"],
        # Bu eşleşme legacy formun geniş kategori alanıyla da uyumludur.
        "category": profile["category"],
        # Bu görsel bulguda KKD eksikliği görülmedi; modelin genel KKD
        # önerisini taşıyarak ilgisiz bir kontrol üretme.
        "recommended_ppe": list(profile.get("recommended_ppe") or []),
    })
    return enriched


def _normalize_bbox(raw: Any) -> list[float] | None:
    """BBox'ı görüntü içinde kalan, pozitif bir [x,y,w,h] kutusuna indirger."""
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        x, y, width, height = (float(value) for value in raw)
    except (TypeError, ValueError):
        return None
    if not all(value == value for value in (x, y, width, height)):
        return None
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    width = max(0.0, min(1.0 - x, width))
    height = max(0.0, min(1.0 - y, height))
    if width <= 0.0 or height <= 0.0:
        return None
    return [round(x, 4), round(y, 4), round(width, 4), round(height, 4)]


def _provider() -> str:
    raw = (settings.vision_provider or "heuristic").strip().lower()
    if raw not in ("heuristic", "api", "yolo"):
        return "heuristic"
    return raw


def _heuristic_hazards(
    *,
    media_text: str,
    risk_activity: str,
    risk_definition: str,
    photo_tags: list[str],
) -> list[dict[str, Any]]:
    """Medya metni + risk metni + etiketlerden tehlike çıkarımı (API'siz)."""
    hazards: list[dict[str, Any]] = []

    # 1) Etiket bazlı tespitler (etiket varsa öncelikli)
    for tag in photo_tags:
        category = _TAG_TO_CATEGORY.get(tag, "Diğer Riskler")
        severity = _TAG_TO_SEVERITY.get(tag, 3)
        hazard = {
            "category": category,
            "severity": severity,
            "confidence": 0.7,
            "bbox": _FULL_FRAME_BBOX,
            "source_tag": tag,
            "note": f"Fotoğraf etiketi '{tag}' ile ilişkili risk.",
        }
        if tag == "poor_housekeeping":
            hazard["hazard_key"] = "housekeeping_obstruction"
        hazards.append(_annotate_visual_hazard(hazard))

    # 2) Metin bazlı kategori önerisi (etiket yoksa veya zenginleştirme)
    blob = " ".join(p.strip() for p in [media_text, risk_activity, risk_definition] if p and p.strip())
    if blob and len(blob) >= 3:
        hint = suggest_hazard_from_text(blob, activity=risk_activity)
        if hint.get("matched"):
            cat = hint["suggested_category"]
            prob = hint.get("probability_hint") or 3
            severity = max(1, min(5, prob + 1))
            hazards.append(_annotate_visual_hazard({
                "category": cat,
                "severity": severity,
                "confidence": hint.get("confidence", 0.0),
                "bbox": _FULL_FRAME_BBOX,
                "source_tag": None,
                "note": "Risk kaydı metninden çıkarılan öneri.",
            }))

    # Tekille (kategoriye göre, en yüksek şiddet)
    by_cat: dict[str, dict[str, Any]] = {}
    for h in hazards:
        cat = h["category"]
        if cat not in by_cat or h["severity"] > by_cat[cat]["severity"]:
            by_cat[cat] = h
    return list(by_cat.values())


def _api_analyze(
    *,
    image_bytes: bytes,
    media_text: str,
    risk_activity: str,
    risk_definition: str,
) -> dict[str, Any] | None:
    """OpenAI-uyumlu vision API çağrısı. Başarısızsa None döner."""
    api_key = settings.vision_api_key
    if not api_key:
        return None
    try:
        import httpx
    except ImportError:
        logger.warning("httpx yok; vision api modu devre dışı")
        return None

    base_url = settings.vision_api_base_url or "https://api.openai.com/v1"
    model = settings.vision_api_model or "openai/gpt-5.4-mini"
    timeout = float(settings.vision_api_timeout_sec or 30)

    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "Sen kıdemli bir iş sağlığı ve güvenliği (İSG) uzmanı ve denetçisisin. "
        "Aşağıdaki saha fotoğrafını dikkatlice inceleyip GÖRÜNTÜ İÇERİĞİNDEN "
        "risk/tehlikeleri tespit et. Fotoğrafın piksellerini gerçekten analiz et; "
        "metin/etikete değil, görselde gördüğüne güven.\n\n"
        "Görselde şunları ara:\n"
        "- Kişisel koruyucu donanım (KKD) eksikliği: baret, güvenlik gözlüğü, "
        "eldiven, güvenlik ayakkabısı, maske, yelek — takılı olmayan çalışan var mı?\n"
        "- Makine/ekipman: koruyucusuz dönen aksam, açık pres, testere, konveyör\n"
        "- Elektrik: açık kablo, hasarlı pano, topraklama eksikliği, izole edilmemiş hat\n"
        "- Yüksekte çalışma: iskele, merdiven, korkuluk eksikliği, emniyet kemeri yok\n"
        "- Kimyasal: dökülme, etiketsiz kap, SDS yok, uygun olmayan depolama\n"
        "- Yangın/sıcak iş: kaynak, açık alev, yanıcı madde yakınında kıvılcım\n"
        "- Ergonomi: yanlış kaldırma, tekrarlayan hareket, uygun olmayan tezgah\n"
        "- Ortam: düzensizlik (5S), kaygan zemin, düşen cisim, düşük aydınlatma\n"
        "- Kapalı alan, trafik/forklift, biyolojik ve yalnızca görüntüde açıkça görülen diğer riskler\n\n"
        "Bağlam (risk kaydından):\n"
        f"- Faaliyet: {risk_activity or 'belirtilmemiş'}\n"
        f"- Risk tanımı: {risk_definition or 'belirtilmemiş'}\n"
        f"- Not: {media_text or 'yok'}\n\n"
        "YALNIZCA aşağıdaki JSON şemasına uyan bir JSON nesnesi döndür; başka "
        "metin, açıklama veya markdown kod bloğu yazma:\n"
        "{\n"
        '  "hazards": [\n'
        '    {\n'
        '      "category": "<aşağıdaki listeden biri, Türkçe>",\n'
        '      "hazard_key": "<stair_obstruction | housekeeping_obstruction | null>",\n'
        '      "hazard_name": "<görselde desteklenen özel tehlike adı>",\n'
        '      "detail_category": "<Merdivenler | Genel işyeri düzeni ve temizlik | null>",\n'
        '      "severity": <1-5, 5=en kritik>,\n'
        '      "confidence": <0.0-1.0>,\n'
        '      "bbox": [<x 0-1>, <y 0-1>, <w 0-1>, <h 0-1>],\n'
        '      "observed": "<görselde somut olarak ne gördün, kanıt>",\n'
        '      "note": "<kısa risk açıklaması>",\n'
        '      "recommended_ppe": ["<önerilen KKD listesi>"]\n'
        '    }\n'
        '  ]\n'
        "}\n\n"
        "Kategoriler (birebir bunlardan biri): Yüksekte Çalışma Riskleri, "
        "Yangın ve Patlama Riskleri, Elektrik Riskleri, Kimyasal Riskler, "
        "Mekanik Riskler, Fiziksel Riskler, Biyolojik Riskler, Ergonomik "
        "Riskler, İnşaat ve Yapı Riskleri, Nakliye ve Trafik Riskleri, "
        "Diğer Riskler.\n\n"
        "Özel görsel kuralları: Merdiven basamakları veya sahanlık üzerinde kova, "
        "bidon, poşet, kutu ya da başka malzeme görülüyorsa hazard_key=stair_obstruction "
        "veya housekeeping_obstruction seç; category=Mekanik Riskler kullan. "
        "Bu durumda hazard_name ve detail_category alanlarını somut bulguya göre doldur. "
        "Gürültü, titreşim, toz, radyasyon, maruziyet, odyometri veya dozimetreyi "
        "yalnızca fotoğrafta doğrudan kanıt varsa raporla; varsayım olarak ekleme. "
        "Açıkça desteklenmeyen risk için hazard üretme.\n\n"
        "bbox: TEHLİKENİN BULUNDUĞU BÖLGE, görüntüye normalize [x, y, w, h] "
        "(sol-üst köşe + genişlik/yükseklik, 0-1). Tüm çerçeveyi [0,0,1,1] "
        "YALNIZCA gerçekten tüm görüntüdeki genel bir risksa kullan. Aksi "
        "halde tehlikenin olduğu dar bölgeyi ver.\n"
        "observed: görselde gördüğün somut kanıt (örn. 'sol altta açık elektrik "
        "panosu', 'çalışanda baret yok').\n"
        "severity: kanıta göre (KKD eksikliği=3, açık elektrik/kimyasal=4-5, "
        "yangın kaynağı=5)."
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": prompt},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{b64}",
                                        "detail": "high",
                                    },
                                },
                            ],
                        }
                    ],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 2000,
                    "temperature": 0.2,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _parse_vision_json(content)
            if not isinstance(parsed, dict) or "hazards" not in parsed:
                return None
            raw_hazards = parsed.get("hazards", [])
            if not isinstance(raw_hazards, list):
                return None
            hazards = []
            for h in raw_hazards:
                if not isinstance(h, dict):
                    continue
                bbox_norm = _normalize_bbox(h.get("bbox"))
                # Bölgesi olmayan veya geçersiz kutu, görsel kanıtı
                # güvenilir biçimde gösteremediği için bulguya alınmaz.
                if bbox_norm is None:
                    continue
                observed = str(h.get("observed", "")).strip()
                note = str(h.get("note", "")).strip()
                if observed and note:
                    full_note = f"{observed}. {note}"
                elif observed:
                    full_note = observed
                else:
                    full_note = note
                ppe = h.get("recommended_ppe", [])
                if isinstance(ppe, str):
                    ppe = [ppe]
                ppe = [str(p) for p in ppe if p] if isinstance(ppe, list) else []
                category = str(h.get("category", "Diğer Riskler")).strip()
                if category not in _VISION_CATEGORIES:
                    category = "Diğer Riskler"
                try:
                    severity = max(1, min(5, int(float(h.get("severity", 3)))))
                except (TypeError, ValueError):
                    severity = 3
                try:
                    confidence = max(0.0, min(1.0, float(h.get("confidence", 0.6))))
                except (TypeError, ValueError):
                    confidence = 0.0
                if not observed:
                    # Görselde somut kanıt yoksa, modelin genel açıklamasını
                    # gerçek bir saha bulgusu gibi kaydetme.
                    continue
                hazards.append(_annotate_visual_hazard({
                    "category": category,
                    "hazard_key": _normalize_visual_hazard_key(h.get("hazard_key")),
                    "hazard_name": str(h.get("hazard_name", "")).strip() or None,
                    "detail_category": str(h.get("detail_category", "")).strip() or None,
                    "severity": severity,
                    "confidence": round(confidence, 2),
                    "bbox": bbox_norm,
                    "source_tag": None,
                    "note": full_note,
                    "recommended_ppe": ppe,
                }))
            if raw_hazards and not hazards:
                return None
            return {"hazards": hazards}
    except Exception:
        logger.exception("vision api çağrısı başarısız")
        return None


def _parse_vision_json(content: str) -> dict[str, Any]:
    """Vision API yanıtından JSON çıkar (markdown fence/önek temizleme)."""
    if not content:
        return {}
    text = content.strip()
    # Markdown kod bloğu temizle
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    # JSON dışı metin varsa ilk { ... } bloğunu al
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("vision API JSON parse edilemedi: %s", text[:200])
        return {}


def analyze_media(
    *,
    image_bytes: bytes | None = None,
    media_text: str = "",
    photo_tags: list[str] | None = None,
    risk_activity: str = "",
    risk_definition: str = "",
) -> dict[str, Any]:
    """Saha fotoğrafı + bağlam → AI risk analizi.

    image_bytes: fotoğraf baytları (api/yolo modunda kullanılır)
    media_text: medya description / dosya adı
    photo_tags: manuel seçilen risk foto etiketleri
    risk_activity: ilişkili risk kaydının faaliyeti
    risk_definition: ilişkili risk kaydının risk tanımı

    Döndürür: normalize analiz sonucu (engine, provider, hazards, bbox_annotations)
    API hatasında provider=unavailable ve boş bulgu döner; hiçbir zaman istisna
    fırlatmaz. Heuristic yalnızca açıkça seçilmiş provider olduğunda kullanılır.
    """
    provider = _provider()
    tags = list(photo_tags or [])

    # --- API modu: başarısızsa fail-closed ---
    if provider == "api":
        if image_bytes:
            api_result = _api_analyze(
                image_bytes=image_bytes,
                media_text=media_text,
                risk_activity=risk_activity,
                risk_definition=risk_definition,
            )
            if api_result is not None:
                hazards = [_annotate_visual_hazard(h) for h in api_result["hazards"]]
                return {
                    "engine": VISION_ENGINE,
                    "provider": "api",
                    "hazards": hazards,
                    "bbox_annotations": _to_bbox_annotations(hazards),
                    "note": (
                        "Görüntüde doğrulanabilir uygunsuzluk bulunamadı."
                        if not hazards else "Görüntü, vision API ile analiz edildi."
                    ),
                }
        return {
            "engine": VISION_ENGINE,
            "provider": "unavailable",
            "hazards": [],
            "bbox_annotations": [],
            "note": "Görüntü AI analizi tamamlanamadı; sahte görsel bulgu oluşturulmadı.",
        }

    # --- YOLO modu (ön-eğitilmiş; bulunamazsa heuristic'e düş) ---
    if provider == "yolo" and image_bytes:
        yolo_result = _yolo_detect(image_bytes)
        if yolo_result and yolo_result.get("hazards"):
            hazards = yolo_result["hazards"]
            return {
                "engine": VISION_ENGINE,
                "provider": "yolo",
                "hazards": hazards,
                "bbox_annotations": _to_bbox_annotations(hazards),
                "note": "Görüntü, nesne tespiti (YOLO) ile analiz edildi.",
            }
        provider = "heuristic"

    # --- Heuristic mod (yalnızca seçili provider) ---
    hazards = _heuristic_hazards(
        media_text=media_text,
        risk_activity=risk_activity,
        risk_definition=risk_definition,
        photo_tags=tags,
    )
    return {
        "engine": VISION_ENGINE,
        "provider": "heuristic",
        "hazards": hazards,
        "bbox_annotations": _to_bbox_annotations(hazards),
        "note": (
            "Heuristik analiz: medya etiketleri ve risk kaydı metninden çıkarım. "
            "Görüntü içeriği analiz edilmedi; uzman doğrulaması önerilir."
            if hazards else
            "Yeterli metin/etiket bulunamadı; görsel bulgu üretilmedi."
        ),
    }


def _yolo_detect(image_bytes: bytes) -> dict[str, Any] | None:
    """Ön-eğitilmiş YOLO ile nesne tespiti. Opsiyonel; yoksa None döner."""
    try:
        from ultralytics import YOLO  # type: ignore
    except Exception:
        logger.info("ultralytics yüklü değil; yolo modu atlandı")
        return None
    # Not: YOLO modu, gerçek KKD/İSG modeli eğitilmediği için varsayılan model
    # (coco) ile genel nesneleri tespit eder ve bunları İSG kategorilerine
    # eşler. Üretimde özel eğitilmiş bir model önerilir. Şimdilik stub.
    try:
        import io
        from PIL import Image  # type: ignore
        img = Image.open(io.BytesIO(image_bytes))
        model = YOLO("yolov8n.pt")
        results = model(img, verbose=False)
        hazards: list[dict[str, Any]] = []
        for r in results:
            for box in r.boxes:
                cls = int(box.cls[0])
                name = r.names.get(cls, "nesne")
                conf = float(box.conf[0])
                xyxy = box.xyxy[0].tolist()
                w, h = float(r.width), float(r.height)
                bbox = [
                    (xyxy[0]) / w,
                    (xyxy[1]) / h,
                    (xyxy[2] - xyxy[0]) / w,
                    (xyxy[3] - xyxy[1]) / h,
                ]
                category = _yolo_class_to_category(name)
                hazards.append({
                    "category": category,
                    "severity": _TAG_TO_SEVERITY.get(category, 3),
                    "confidence": round(conf, 2),
                    "bbox": [round(v, 4) for v in bbox],
                    "source_tag": None,
                    "note": f"Tespit edilen nesne: {name}",
                })
        return {"hazards": hazards} if hazards else None
    except Exception:
        logger.exception("yolo tespiti başarısız")
        return None


def _yolo_class_to_category(name: str) -> str:
    """COCO sınıf adı → İSG tehlike kategorisi eşlemesi (kaba)."""
    n = (name or "").lower()
    if any(k in n for k in ("person",)):
        return "Diğer Riskler"
    if any(k in n for k in ("truck", "car", "bus", "forklift", "vehicle")):
        return "Nakliye ve Trafik Riskleri"
    if any(k in n for k in ("fire", "smoke", "flame")):
        return "Yangın ve Patlama Riskleri"
    if any(k in n for k in ("bottle", "chemical", "tank")):
        return "Kimyasal Riskler"
    if any(k in n for k in ("knife", "scissor", "machine")):
        return "Mekanik Riskler"
    return "Diğer Riskler"


def _to_bbox_annotations(hazards: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Hazard listesi → frontend çizimi için bbox annotation listesi."""
    annotations = []
    for h in hazards:
        bbox = h.get("bbox", _FULL_FRAME_BBOX)
        if not (isinstance(bbox, list) and len(bbox) == 4):
            bbox = _FULL_FRAME_BBOX
        annotations.append({
            "label": h.get("hazard_name") or h.get("category", "Risk"),
            "severity": h.get("severity", 3),
            "confidence": h.get("confidence", 0.0),
            "box": [float(v) for v in bbox],
            "note": h.get("note", ""),
        })
    return annotations


def build_full_analysis(
    *,
    image_bytes: bytes | None = None,
    media_text: str = "",
    photo_tags: list[str] | None = None,
    risk_activity: str = "",
    risk_definition: str = "",
    reference_date=None,
) -> dict[str, Any]:
    """Tam analiz: vision + mevzuat + DÖF önerileri + termin.

    Bu, /media/analyze endpoint'inin çağırdığı ana fonksiyondur. Vision tespitlerini
    alır, her tehlike için mevzuat raporu + termin üretir ve DÖF önerileri derler.
    """
    from datetime import date as _date
    base_date = reference_date or _date.today()

    vision = analyze_media(
        image_bytes=image_bytes,
        media_text=media_text,
        photo_tags=photo_tags,
        risk_activity=risk_activity,
        risk_definition=risk_definition,
    )

    enriched_hazards = []
    for h in vision.get("hazards", []):
        h = _annotate_visual_hazard(h)
        category = h.get("category", "Diğer Riskler")
        severity = h.get("severity", 3)
        hazard_key = h.get("hazard_key")
        # Mevzuat raporu
        mevzuat = None
        try:
            if hazard_key:
                mevzuat = build_visual_report(
                    hazard_key=hazard_key,
                    text=h.get("observed") or h.get("note") or "",
                    confidence=h.get("confidence", 0),
                )
            else:
                mevzuat = build_mevzuat_report(
                    text=f"{risk_activity} {risk_definition}".strip(),
                    hazard_hint={"matched": True, "suggested_category": category, "confidence": h.get("confidence", 0)},
                )
        except Exception:
            mevzuat = None
        # Termin
        termin = suggest_term(severity=severity, category=category, reference_date=base_date)
        # DÖF önerileri (mevzuat tedbirleri → düzeltici faaliyet kalemleri)
        dof_suggestions = _mevzuat_to_dofs(mevzuat, termin) if mevzuat and mevzuat.get("matched") else []
        enriched_hazards.append({
            "category": category,
            "hazard_key": hazard_key,
            "hazard_code": h.get("hazard_code"),
            "hazard_name": h.get("hazard_name"),
            "detail_category": h.get("detail_category"),
            "severity": severity,
            "confidence": h.get("confidence", 0.0),
            "bbox": h.get("bbox", _FULL_FRAME_BBOX),
            "note": h.get("note", ""),
            "observed": h.get("observed", ""),
            "recommended_ppe": h.get("recommended_ppe", []),
            "source_tag": h.get("source_tag"),
            "mevzuat": _slim_mevzuat(mevzuat) if mevzuat else None,
            "termin": termin,
            "dof_suggestions": dof_suggestions,
        })

    return {
        "engine": VISION_ENGINE,
        "provider": vision.get("provider", "heuristic"),
        "analyzed_at": base_date.isoformat(),
        "hazards": enriched_hazards,
        "bbox_annotations": vision.get("bbox_annotations", []),
        "summary": _build_summary(enriched_hazards),
        "note": vision.get("note", ""),
    }


def _slim_mevzuat(mevzuat: dict[str, Any] | None) -> dict[str, Any] | None:
    if not mevzuat or not mevzuat.get("matched"):
        return None
    return {
        "kanun": (mevzuat.get("mevzuat") or {}).get("kanun"),
        "madde": (mevzuat.get("mevzuat") or {}).get("madde"),
        "yonetmelik": (mevzuat.get("mevzuat") or {}).get("yonetmelik"),
        "standart": (mevzuat.get("mevzuat") or {}).get("standart"),
        "tedbirler": mevzuat.get("tedbirler", []),
        "onleyici_faaliyet": mevzuat.get("onleyici_faaliyet", []),
        "ceza_riski": mevzuat.get("ceza_riski"),
        "source": mevzuat.get("source"),
    }


def _mevzuat_to_dofs(mevzuat: dict[str, Any], termin: dict[str, Any]) -> list[dict[str, Any]]:
    """Mevzuat tedbirleri → DÖF öneri kalemleri (uzman onayı bekler)."""
    dofs = []
    term_date = termin.get("term_date")
    for tedbir in (mevzuat.get("tedbirler") or []):
        dofs.append({
            "description": tedbir,
            "type": "corrective",
            "term_date": term_date,
            "source": mevzuat.get("source") or "ai_vision_mevzuat",
            "status": "Önerildi",  # uzman onayı bekler
        })
    for faaliyet in (mevzuat.get("onleyici_faaliyet") or []):
        dofs.append({
            "description": faaliyet,
            "type": "preventive",
            "term_date": term_date,
            "source": mevzuat.get("source") or "ai_vision_mevzuat",
            "status": "Önerildi",
        })
    return dofs


def _build_summary(hazards: list[dict[str, Any]]) -> str:
    if not hazards:
        return "Tespit edilen risk bulunamadı."
    n = len(hazards)
    max_sev = max(h.get("severity", 1) for h in hazards)
    categories = sorted({
        h.get("detail_category") or h.get("category", "")
        for h in hazards
        if h.get("detail_category") or h.get("category")
    })
    if max_sev >= 5:
        seviye = "KRİTİK"
    elif max_sev >= 4:
        seviye = "YÜKSEK"
    elif max_sev >= 3:
        seviye = "ORTA"
    else:
        seviye = "DÜŞÜK"
    cats = ", ".join(categories) if categories else "belirsiz"
    return (
        f"{n} risk tespit edildi. En yüksek şiddet: {max_sev}/5 ({seviye}). "
        f"Kategori(ler): {cats}. AI önerileri uzman onayıyla DÖF oluşturulmalıdır."
    )
