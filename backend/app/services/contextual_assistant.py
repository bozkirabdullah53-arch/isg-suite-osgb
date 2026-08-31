"""Safe, page-aware help for the independent OSGB application."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app.core.config import contextual_assistant_active, settings
from app.core.database import SessionLocal
from app.core.request_id import current_request_id
from app.services.ai_gateway_config import managed_config

logger = logging.getLogger(__name__)
UNAVAILABLE_MESSAGE = "Asistan geçici olarak kullanılamıyor. Uygulamayı normal şekilde kullanmaya devam edebilirsiniz."

ROLE_MODULES = {
    "global_admin": {"eisa_overview", "eisa_osgb_users", "eisa_individual_subscriptions", "eisa_subscriptions", "eisa_payments", "eisa_packages", "eisa_question_bank", "eisa_error_reports", "eisa_notifications", "eisa_emails", "eisa_reports", "eisa_archives", "eisa_audit_logs", "eisa_system_settings", "security"},
    "company_admin": {"osgb_dashboard", "visits", "notifications", "training", "employer_oversight", "companies", "workplace_status", "professionals", "assignments", "pro_performance", "osgb_oversight", "capacity_engine", "csgb_audit", "crm", "contracts", "finance", "branches", "reports", "mevzuat", "users", "subscription", "security", "remote_training"},
    "safety_specialist": {"dashboard", "visit_notebook", "visit_qr", "field_inspection", "risk", "capa", "employees", "visits", "field_pwa", "notifications", "ppe", "near_miss", "accident", "training", "belge_onay", "workplace_status", "facility_summary", "acil_plan", "acil_ekipler", "tatbikat", "periyodik_kontrol", "ortam_olcum", "isg_kurulu", "sds", "annual_plans", "annual_eval_report", "documents", "work_permits", "contractors", "visitors", "customer_portal", "specialist_reports", "mevzuat", "security"},
    "workplace_physician": {"dashboard", "health", "prescriptions", "visit_notebook", "visit_qr", "employees", "visits", "belge_onay", "eyas_inbox", "workplace_status", "ortam_olcum", "training", "annual_plans", "annual_eval_report", "documents", "security"},
    "other_health_personnel": {"visits", "field_pwa", "facility_summary", "dashboard", "workplace_status", "health", "employees", "annual_plans", "documents", "work_permits", "security"},
    "read_only": {"employee_self_service", "employee_training", "security"},
}
WORKPLACE_MANAGER_MODULES = {"employer_oversight", "eyas_inbox", "employees", "ppe", "periyodik_kontrol", "ortam_olcum", "sds", "accident", "near_miss", "security"}
CAPABILITY_MODULES = {"dashboard.open_risk": "risk", "dashboard.open_companies": "companies", "dashboard.open_employees": "employees", "dashboard.open_training": "training", "employee.create": "employees", "employee.import_excel": "employees", "employee.edit": "employees", "employee.training.assign": "training", "company.create": "companies", "company.edit": "companies", "company.select": "companies", "company.open_status": "workplace_status", "training.create": "training", "training.assign": "training", "exam.generate": "training", "training.remote": "remote_training", "risk.create": "risk", "risk.review": "risk", "risk.open": "risk", "risk.report": "risk", "corrective_action.create": "capa", "corrective_action.complete": "capa", "near_miss.create": "near_miss", "accident.create": "accident", "accident.review": "accident", "reports.open": "reports", "visit.view": "visits", "field_inspection.open": "field_inspection", "field_inspection.create": "field_inspection", "field_inspection.add_photo": "field_inspection", "medical_exam.view": "health", "health.record.view": "health", "document.create": "documents", "document.view": "documents", "employee.report": "employees"}
CAPABILITY_LABELS = {"employee.create": "Personel Ekle", "employee.import_excel": "Excel ile Yükle", "employee.edit": "Personeli Düzenle", "employee.training.assign": "Eğitim Ata", "company.create": "İşyeri Ekle", "training.create": "Eğitim Oluştur", "training.assign": "Çalışanlara Ata", "exam.generate": "Sınav Oluştur", "training.remote": "Uzaktan Eğitim", "risk.create": "Risk Kaydı Oluştur", "corrective_action.create": "DÖF Oluştur", "near_miss.create": "Ramak Kala Kaydı Aç", "accident.create": "Kaza Kaydı Aç", "field_inspection.create": "Denetim Başlat"}

def _role(user) -> str:
    return str(getattr(getattr(user, "role", None), "value", getattr(user, "role", "unknown")) or "unknown")

def _modules(user) -> set[str]:
    return WORKPLACE_MANAGER_MODULES if _role(user) == "company_admin" and getattr(user, "company_id", None) else ROLE_MODULES.get(_role(user), set())

def sanitize_context(raw: dict[str, Any] | None, user) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    page = raw.get("currentPage") if isinstance(raw.get("currentPage"), dict) else {}
    raw_user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    allowed = _modules(user)
    supplied = {str(value)[:100] for value in raw_user.get("accessibleModules", []) if isinstance(value, str)}
    if supplied:
        allowed = allowed & supplied
    sensitive = {"national_id", "tc", "tckn", "phone", "address", "email", "diagnosis", "medical", "employees", "records", "full_name"}
    state = raw.get("state") if isinstance(raw.get("state"), dict) else {}
    safe_state = {str(key)[:40]: value for key, value in list(state.items())[:20] if str(key).casefold() not in sensitive and (isinstance(value, (bool, int)) or (isinstance(value, str) and len(value) <= 40))}
    capabilities = [str(value)[:120] for value in raw.get("capabilities", []) if isinstance(value, str) and CAPABILITY_MODULES.get(value) in _modules(user)][:40]
    return {"currentPage": {"id": str(page.get("id", "unknown"))[:100], "module": str(page.get("module", "unknown"))[:100], "title": str(page.get("title", "Uygulama"))[:160], "purpose": str(page.get("purpose", ""))[:500]}, "user": {"role": _role(user), "accessibleModules": sorted(allowed)[:80]}, "state": safe_state, "capabilities": capabilities}

def _action(context, module: str, label: str, target: str | None = None):
    if module not in context["user"]["accessibleModules"]:
        return None
    return {"type": "show", "targetId": target, "label": label} if target else {"type": "navigate", "moduleId": module, "label": label}

def answer(*, question: str, raw_context: dict[str, Any], user) -> dict[str, Any]:
    if not contextual_assistant_active():
        return {"message": UNAVAILABLE_MESSAGE, "source": "disabled", "domain": "app", "actions": []}
    question = str(question or "").strip()[:2000]
    if not question:
        return {"message": "Kısa bir soru yazın. Örneğin: Bu sayfada ne yapmalıyım?", "source": "verified", "domain": "app", "actions": []}
    context = sanitize_context(raw_context, user)
    page = context["currentPage"]
    q = question.casefold()
    labels = [CAPABILITY_LABELS[item] for item in context["capabilities"] if item in CAPABILITY_LABELS][:6]
    message = f"{page['title']} sayfasındasınız. {page['purpose']}\n\n"
    message += ", ".join(labels) if labels else "Bu ekran için doğrulanmış ek işlem tanımı bulunmuyor."
    actions = []
    if "excel" in q or "içe aktar" in q or "yükle" in q:
        action = _action(context, "employees", "Excel ile Yükle alanını göster", "employee.import_excel")
        if action: message = "Personel sayfasında önce işyerini seçin. Sonra şablonu doldurup Excel Yükle kontrolünden aktarımı başlatın."; actions.append(action)
    elif "personel" in q and "ekle" in q:
        action = _action(context, "employees", "Personel Ekle alanını göster", "employee.create")
        if action: message = "Önce işyerini seçin. Ardından Personel Ekle ile Ad Soyad alanını doldurup Kaydet işlemini siz onaylayın."; actions.append(action)
    elif "eğitim" in q and ("ata" in q or "atama" in q):
        action = _action(context, "training", "Eğitimler modülüne git")
        if action: message = "Eğitimler modülünde işyerini ve katılımcıları seçin, bilgileri kontrol edin ve atamayı siz onaylayın."; actions.append(action)
    elif "sınav" in q or "soru" in q:
        action = _action(context, "training", "Sınav alanını göster", "training.generate_exam")
        if action: message = "Sınav seçeneği eğitim kaydı oluşturulduktan sonra kullanılabilir."; actions.append(action)
    elif "risk" in q:
        action = _action(context, "risk", "Risk Analizine git")
        if action: message = "Risk Analizi modülünde işyerini seçip Yeni Risk ile değerlendirmeyi başlatabilirsiniz."; actions.append(action)
    elif "döf" in q or "düzeltici" in q:
        action = _action(context, "capa", "DÖF modülüne git")
        if action: message = "DÖF modülünde konu, kaynak, açıklama, sorumlu ve termin bilgilerini kontrol edin."; actions.append(action)
    elif "sil" in q or "yetki" in q or "eriş" in q:
        message = "Bu işlem mevcut rolünüz için açık değil. Asistan yetki veremez ve gizli menüleri göstermez."
    message += "\n\nAsistan kayıt silmez, form göndermez ve resmi işlemi sizin yerinize tamamlamaz."
    provider_message = _ask_provider(question, context, message)
    source = "ai" if provider_message else "verified"
    if provider_message:
        message = provider_message
    logger.info("contextual assistant request request_id=%s user_id=%s page_id=%s source=%s", current_request_id(), getattr(user, "id", None), page["id"], source)
    return {"message": message, "source": source, "domain": "app", "actions": actions[:2]}


def _provider_config() -> dict[str, Any] | None:
    """Resolve the assistant provider, preferring the Global AI panel.

    Once a Global Admin has saved managed AI settings, those settings are the
    single source of truth for both vision analysis and the contextual assistant.
    A managed local/disabled selection intentionally does not fall back to a
    different external assistant key.
    """
    try:
        with SessionLocal() as db:
            managed = managed_config(db)
    except Exception:
        logger.warning("contextual assistant could not read managed AI settings", exc_info=True)
        return None

    if managed is not None:
        if not bool(managed.get("enabled")):
            return None
        if bool(getattr(settings, "vision_analysis_force_off", False)):
            return None
        if str(managed.get("provider") or "") in {"heuristic", "yolo"}:
            return None
        api_key = managed.get("api_key")
        api_url = managed.get("base_url")
        model = managed.get("model")
        if not api_key or not api_url or not model:
            return None
        return {
            "source": "global_panel",
            "provider": str(managed.get("provider") or "custom_openai"),
            "api_key": str(api_key),
            "api_url": str(api_url),
            "model": str(model),
            "timeout_sec": int(managed.get("timeout_sec") or 30),
        }

    api_key = getattr(settings, "contextual_assistant_api_key", None)
    api_url = getattr(settings, "contextual_assistant_api_url", None)
    model = getattr(settings, "contextual_assistant_model", "")
    if not api_key or not api_url or not model:
        return None
    return {
        "source": "environment",
        "provider": "legacy_contextual",
        "api_key": str(api_key),
        "api_url": str(api_url),
        "model": str(model),
        "timeout_sec": int(getattr(settings, "contextual_assistant_timeout_seconds", 30) or 30),
    }


def _ask_provider(question: str, context: dict[str, Any], verified_message: str) -> str | None:
    if not contextual_assistant_active() or getattr(settings, "contextual_assistant_force_off", False):
        return None
    provider = _provider_config()
    if not provider:
        return None
    payload = {
        "model": provider["model"],
        "messages": [
            {"role": "system", "content": "Sen İSG Suite OSGB uygulamasının sayfa farkındalıklı yardımcısısın. Yalnızca verilen doğrulanmış özet ve bağlama göre Türkçe, kısa ve pratik cevap ver. Buton, modül, yetki veya başarı uydurma. Kayıt silme, form gönderme veya kritik işlem yapma. Kişisel, kimlik veya tıbbi veri isteme."},
            {"role": "user", "content": f"Doğrulanmış uygulama özeti: {verified_message}\nHassas veri içermeyen bağlam: {context}\nSoru: {question}"},
        ],
        "temperature": 0.1,
        "max_tokens": 500,
    }
    try:
        timeout = min(max(int(provider.get("timeout_sec") or 30), 5), 120)
        with httpx.Client(timeout=timeout) as client:
            response = client.post(f"{str(provider['api_url']).removesuffix('/chat/completions').rstrip('/')}/chat/completions", headers={"Authorization": f"Bearer {provider['api_key']}", "Content-Type": "application/json"}, json=payload)
            response.raise_for_status()
            content = response.json().get("choices", [{}])[0].get("message", {}).get("content")
            if content:
                logger.info("contextual assistant used provider request_id=%s source=%s provider=%s model=%s", current_request_id(), provider["source"], provider["provider"], provider["model"])
                return str(content).strip()[:4000]
            return None
    except httpx.TimeoutException:
        logger.warning("contextual assistant provider timeout request_id=%s page_id=%s", current_request_id(), context["currentPage"]["id"])
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError):
        logger.warning("contextual assistant provider failure request_id=%s page_id=%s", current_request_id(), context["currentPage"]["id"], exc_info=True)
    return None
