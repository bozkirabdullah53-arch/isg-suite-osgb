import React, {useEffect, useMemo, useRef, useState} from "react";
import {
  Camera,
  CheckCircle2,
  ChevronDown,
  Download,
  ImagePlus,
  MapPin,
  Plus,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  Trash2,
  X,
} from "lucide-react";
import {api, authBlobUrl, downloadFile, uploadFile} from "./api";
import "./visual_field_inspection.css";

const EMPTY_GPS = {
  gps_lat: null,
  gps_lng: null,
  gps_accuracy_m: null,
  gps_captured_at: null,
  gps_status: "not_available",
  gps_provider: null,
  gps_reason: null,
  manual_location_note: "",
};

const EMPTY_MANUAL = {
  hazard_name: "",
  visual_evidence: "",
  nonconformity_description: "",
  suggested_priority: "medium",
  category_id: "",
  photo_id: "",
};

function listFrom(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  return [];
}

function clientReference(prefix = "field") {
  try {
    if (globalThis.crypto?.randomUUID) return `${prefix}_${globalThis.crypto.randomUUID()}`;
  } catch { /* fallback */ }
  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function browserTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "Europe/Istanbul";
  } catch {
    return "Europe/Istanbul";
  }
}

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("tr-TR", {dateStyle: "short", timeStyle: "short"});
  } catch {
    return String(value);
  }
}

function formatStatus(status) {
  return {
    draft: "Taslak",
    in_review: "Uzman incelemesinde",
    approved: "Onaylandı",
    queued: "Kuyrukta",
    running: "Analiz ediliyor",
    completed: "Analiz tamamlandı",
    failed: "Analiz başarısız",
    ai_draft: "Uzman onayı bekliyor",
    under_review: "Uzman incelemesinde",
    accepted: "Kabul edildi",
    corrected: "Düzenlendi",
    rejected: "Reddedildi",
    not_verifiable: "Görüntüden doğrulanamadı",
    open: "Açık",
    in_progress: "Devam ediyor",
    completed_action: "Tamamlandı",
  }[status] || status || "—";
}

function messageFrom(error) {
  return error?.message || "İşlem tamamlanamadı; tekrar deneyin.";
}

function groupCategories(categories) {
  const groups = [];
  for (let index = 0; index < categories.length; index += 15) {
    groups.push({title: `${index + 1}–${Math.min(index + 15, categories.length)}. kategori`, rows: categories.slice(index, index + 15)});
  }
  return groups;
}

export function VisualFieldInspectionPage() {
  const [catalog, setCatalog] = useState({companies: [], categories: [], sites: [], areas: [], equipment: [], custom_hazards: [], site_types: [], area_types: [], equipment_types: []});
  const [companyId, setCompanyId] = useState("");
  const [siteId, setSiteId] = useState("");
  const [areaId, setAreaId] = useState("");
  const [equipmentId, setEquipmentId] = useState("");
  const [selectedCategories, setSelectedCategories] = useState([]);
  const [selectedHazards, setSelectedHazards] = useState([]);
  const [scanAll, setScanAll] = useState(true);
  const [categoryQuery, setCategoryQuery] = useState("");
  const [locationQuery, setLocationQuery] = useState("");
  const [gps, setGps] = useState(EMPTY_GPS);
  const [photos, setPhotos] = useState([]);
  const [privacyBlur, setPrivacyBlur] = useState(false);
  const [notes, setNotes] = useState("");
  const [manual, setManual] = useState(EMPTY_MANUAL);
  const [customHazardScope, setCustomHazardScope] = useState("company");
  const [annotationDraft, setAnnotationDraft] = useState({photo_id: "", finding_id: "", shape_type: "rectangle", x: 0.35, y: 0.25, width: 0.3, height: 0.3, label: "", color: "#dc2626"});
  const [legalDraft, setLegalDraft] = useState({finding_id: "", regulation_name: "", article: "", relation_explanation: "", verification_status: "needs_expert_review"});
  const [responsibles, setResponsibles] = useState([]);
  const [actionDraft, setActionDraft] = useState({finding_id: "", title: "", activity: "", responsible_employee_id: "", term_date: "", priority: "medium"});
  const [current, setCurrent] = useState(null);
  const [recent, setRecent] = useState([]);
  const [photoUrls, setPhotoUrls] = useState({});
  const [photoVariant, setPhotoVariant] = useState("marked");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [gpsBusy, setGpsBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const cameraRef = useRef(null);
  const galleryRef = useRef(null);

  const company = useMemo(() => catalog.companies.find((item) => Number(item.id) === Number(companyId)), [catalog.companies, companyId]);
  const sites = useMemo(() => listFrom(catalog.sites).filter((item) => !locationQuery || item.name.toLocaleLowerCase("tr-TR").includes(locationQuery.toLocaleLowerCase("tr-TR"))), [catalog.sites, locationQuery]);
  const areas = useMemo(() => listFrom(catalog.areas).filter((item) => Number(item.site_id) === Number(siteId) && (!locationQuery || item.name.toLocaleLowerCase("tr-TR").includes(locationQuery.toLocaleLowerCase("tr-TR")))), [catalog.areas, siteId, locationQuery]);
  const equipment = useMemo(() => listFrom(catalog.equipment).filter((item) => Number(item.area_id) === Number(areaId) && (!locationQuery || item.name.toLocaleLowerCase("tr-TR").includes(locationQuery.toLocaleLowerCase("tr-TR")))), [catalog.equipment, areaId, locationQuery]);
  const photoAreas = useMemo(() => listFrom(catalog.areas).filter((item) => Number(item.site_id) === Number(siteId)), [catalog.areas, siteId]);
  const filteredCategories = useMemo(() => listFrom(catalog.categories).filter((item) => !categoryQuery || item.name.toLocaleLowerCase("tr-TR").includes(categoryQuery.toLocaleLowerCase("tr-TR"))), [catalog.categories, categoryQuery]);
  const categoryGroups = useMemo(() => groupCategories(filteredCategories), [filteredCategories]);
  const selectedCompanyHazards = useMemo(() => listFrom(catalog.custom_hazards).filter((item) => selectedCategories.includes(Number(item.category_id)) || selectedCategories.length === 0), [catalog.custom_hazards, selectedCategories]);

  async function loadCatalog(nextCompanyId = companyId) {
    const query = nextCompanyId ? `?company_id=${encodeURIComponent(nextCompanyId)}` : "";
    const data = await api(`/field-inspections/catalog${query}`);
    setCatalog((previous) => ({
      ...previous,
      ...data,
      selected_company_id: nextCompanyId ? data.selected_company_id : null,
      sites: nextCompanyId ? listFrom(data.sites) : [],
      areas: nextCompanyId ? listFrom(data.areas) : [],
      equipment: nextCompanyId ? listFrom(data.equipment) : [],
      custom_hazards: nextCompanyId ? listFrom(data.custom_hazards) : [],
    }));
    return data;
  }

  async function loadRecent(nextCompanyId = companyId) {
    if (!nextCompanyId) return;
    const data = await api(`/field-inspections?company_id=${encodeURIComponent(nextCompanyId)}&limit=12`);
    setRecent(listFrom(data));
  }

  useEffect(() => {
    let active = true;
    setLoading(true);
    loadCatalog("").catch((ex) => active && setError(messageFrom(ex))).finally(() => active && setLoading(false));
    return () => { active = false; };
    // Initial load intentionally runs once; company changes use the next effect.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!companyId) return;
    let active = true;
    setSiteId(""); setAreaId(""); setEquipmentId(""); setSelectedHazards([]);
    loadCatalog(companyId).then(() => loadRecent(companyId)).catch((ex) => active && setError(messageFrom(ex)));
    api(`/field-inspections/responsibles?company_id=${encodeURIComponent(companyId)}`).then((data) => active && setResponsibles(listFrom(data))).catch(() => active && setResponsibles([]));
    return () => { active = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [companyId]);

  useEffect(() => {
    if (!current?.id || !["queued", "running"].includes(current.ai_status)) return undefined;
    const timer = window.setTimeout(async () => {
      try { setCurrent(await api(`/field-inspections/${current.id}`)); } catch { /* next poll / user can retry */ }
    }, 2500);
    return () => window.clearTimeout(timer);
  }, [current]);

  useEffect(() => {
    let active = true;
    const urls = {};
    const rows = current?.photos || [];
    Promise.all(rows.map(async (photo) => {
      try { urls[photo.id] = await authBlobUrl(photo.variants?.[photoVariant] || photo.variants?.marked || photo.variants?.preview); } catch { /* protected image may be unavailable */ }
    })).then(() => active && setPhotoUrls(urls));
    return () => {
      active = false;
      Object.values(urls).forEach((url) => URL.revokeObjectURL(url));
    };
  }, [current, photoVariant]);

  function clearFeedback() { setMessage(""); setError(""); }

  async function changeCompany(value) {
    clearFeedback();
    setCompanyId(value);
    setCurrent(null);
    setSiteId("");
    setAreaId("");
    setEquipmentId("");
    setSelectedCategories([]);
    setSelectedHazards([]);
    setRecent([]);
    setResponsibles([]);
    if (!value) {
      setCatalog((previous) => ({...previous, selected_company_id: null, sites: [], areas: [], equipment: [], custom_hazards: []}));
    }
  }

  async function addNamed(kind) {
    if (!companyId) return setError("Önce işyeri seçin.");
    const labels = {site: "Tesis/saha adı", area: "Bölüm/alan adı", equipment: "Ekipman/nokta adı"};
    const name = window.prompt(`${labels[kind]}:`, "");
    if (!name?.trim()) return;
    try {
      setBusy(true); clearFeedback();
      let data;
      if (kind === "site") data = await api("/field-inspections/sites", {method: "POST", body: JSON.stringify({company_id: Number(companyId), name: name.trim()})});
      if (kind === "area") {
        if (!siteId) return setError("Önce tesis/saha seçin.");
        data = await api("/field-inspections/areas", {method: "POST", body: JSON.stringify({company_id: Number(companyId), site_id: Number(siteId), name: name.trim()})});
      }
      if (kind === "equipment") {
        if (!siteId || !areaId) return setError("Önce tesis/saha ve bölüm seçin.");
        data = await api("/field-inspections/equipment", {method: "POST", body: JSON.stringify({company_id: Number(companyId), site_id: Number(siteId), area_id: Number(areaId), name: name.trim()})});
      }
      await loadCatalog(companyId);
      const item = data?.item;
      if (kind === "site" && item?.id) setSiteId(String(item.id));
      if (kind === "area" && item?.id) setAreaId(String(item.id));
      if (kind === "equipment" && item?.id) setEquipmentId(String(item.id));
      setMessage("Yeni kayıt eklendi ve seçildi.");
    } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function addCustomHazard() {
    if (!companyId || !selectedCategories.length) return setError("Özel tehlike için önce en az bir kategori seçin.");
    const name = window.prompt("Yeni tehlike başlığı:", "");
    if (!name?.trim()) return;
    try {
      setBusy(true); clearFeedback();
      await api("/field-inspections/hazards", {method: "POST", body: JSON.stringify({company_id: Number(companyId), category_id: Number(selectedCategories[0]), name: name.trim(), scope: customHazardScope, is_active: true})});
      const data = await loadCatalog(companyId);
      const item = listFrom(data.custom_hazards).find((hazard) => hazard.name === name.trim());
      if (item) setSelectedHazards((rows) => [...new Set([...rows, Number(item.id)])]);
      setMessage("Özel tehlike eklendi; yalnız bu işyerinin kapsamındadır.");
    } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  function captureGps() {
    clearFeedback();
    if (!navigator.geolocation) {
      setGps({...EMPTY_GPS, gps_status: "unavailable", gps_reason: "Bu cihaz konum servisini desteklemiyor."});
      return setError("Bu cihaz konum servisini desteklemiyor; manuel açıklamayla devam edebilirsiniz.");
    }
    setGpsBusy(true);
    navigator.geolocation.getCurrentPosition((position) => {
      const accuracy = Number(position.coords.accuracy || 0);
      setGps({gps_lat: Number(position.coords.latitude.toFixed(7)), gps_lng: Number(position.coords.longitude.toFixed(7)), gps_accuracy_m: Number(accuracy.toFixed(1)), gps_captured_at: new Date().toISOString(), gps_status: accuracy > 50 ? "low_accuracy" : "captured", gps_provider: "browser_geolocation", gps_reason: null, manual_location_note: ""});
      setMessage(accuracy > 50 ? `Konum alındı; doğruluk düşük (±${accuracy.toFixed(1)} m).` : `Konum alındı (±${accuracy.toFixed(1)} m).`);
      setGpsBusy(false);
    }, (ex) => {
      const reason = ex?.code === 1 ? "Konum izni reddedildi." : ex?.code === 2 ? "Konum kullanılamıyor." : "Konum alma zaman aşımına uğradı.";
      setGps({...EMPTY_GPS, gps_status: ex?.code === 1 ? "denied" : "unavailable", gps_reason: reason});
      setError(`${reason} Fotoğraf kaybolmaz; manuel konum açıklaması yazabilirsiniz.`);
      setGpsBusy(false);
    }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 60000});
  }

  function capturePhotoGps(photoId) {
    if (!navigator.geolocation) {
      const reason = "Bu cihaz konum servisini desteklemiyor.";
      updatePhoto(photoId, {gps: {...EMPTY_GPS, gps_status: "unavailable", gps_reason: reason}});
      return setError(`${reason} Fotoğraf yine de saklanabilir.`);
    }
    setGpsBusy(true);
    navigator.geolocation.getCurrentPosition((position) => {
      const accuracy = Number(position.coords.accuracy || 0);
      updatePhoto(photoId, {gps: {gps_lat: Number(position.coords.latitude.toFixed(7)), gps_lng: Number(position.coords.longitude.toFixed(7)), gps_accuracy_m: Number(accuracy.toFixed(1)), gps_captured_at: new Date().toISOString(), gps_status: accuracy > 50 ? "low_accuracy" : "captured", gps_provider: "browser_geolocation", gps_reason: null, manual_location_note: ""}});
      setMessage(accuracy > 50 ? "Fotoğraf konumu alındı; doğruluk düşük." : "Fotoğraf konumu alındı.");
      setGpsBusy(false);
    }, (ex) => {
      const reason = ex?.code === 1 ? "Konum izni reddedildi." : ex?.code === 2 ? "Konum kullanılamıyor." : "Konum alma zaman aşımına uğradı.";
      updatePhoto(photoId, {gps: {...EMPTY_GPS, gps_status: ex?.code === 1 ? "denied" : "unavailable", gps_reason: reason}});
      setError(`${reason} Fotoğraf yine de saklanabilir.`);
      setGpsBusy(false);
    }, {enableHighAccuracy: true, timeout: 12000, maximumAge: 60000});
  }

  function photoGpsStatus(photo) {
    const value = photo.gps || gps;
    return value.gps_lat != null ? `${value.gps_status === "low_accuracy" ? "Düşük doğruluk" : "Konum alındı"} · ±${value.gps_accuracy_m ?? "—"} m` : "GPS alınamadı";
  }

  function selectPhotos(event) {
    const incoming = Array.from(event.target.files || []).slice(0, Math.max(0, 8 - photos.length)).map((file) => ({id: clientReference("photo"), file, url: URL.createObjectURL(file), captured_at: new Date(file.lastModified || Date.now()).toISOString(), rotation: 0, square: false, site_id: siteId, area_id: areaId, equipment_id: equipmentId, gps: {...gps}}));
    event.target.value = "";
    if (incoming.length) setPhotos((rows) => [...rows, ...incoming]);
  }

  function updatePhoto(id, patch) { setPhotos((rows) => rows.map((photo) => photo.id === id ? {...photo, ...patch} : photo)); }
  function removePhoto(id) { setPhotos((rows) => rows.filter((photo) => { if (photo.id === id) URL.revokeObjectURL(photo.url); return photo.id !== id; })); }

  function toggleCategory(id) { setSelectedCategories((rows) => rows.includes(Number(id)) ? rows.filter((item) => item !== Number(id)) : [...rows, Number(id)]); }
  function toggleHazard(id) { setSelectedHazards((rows) => rows.includes(Number(id)) ? rows.filter((item) => item !== Number(id)) : [...rows, Number(id)]); }

  async function createAndAnalyze(event) {
    event?.preventDefault(); clearFeedback();
    if (!companyId) return setError("İşyeri seçilmeden denetim başlatılamaz.");
    if (!siteId || !areaId) return setError("Tesis/saha ve bölüm/alan seçin.");
    if (!photos.length) return setError("En az bir fotoğraf ekleyin.");
    try {
      setBusy(true);
      const created = await api("/field-inspections", {method: "POST", body: JSON.stringify({company_id: Number(companyId), site_id: Number(siteId), area_id: Number(areaId), equipment_id: equipmentId ? Number(equipmentId) : null, inspection_date: new Date().toISOString().slice(0, 10), inspection_at: new Date().toISOString(), timezone: browserTimezone(), ...gps, selected_category_ids: selectedCategories, selected_hazard_ids: selectedHazards, scan_all_hazards: scanAll, notes: notes.trim() || null, client_reference: clientReference()})});
      for (const [index, photo] of photos.entries()) {
        setUploadProgress(`Fotoğraf ${index + 1}/${photos.length} güvenli depolamaya yükleniyor…`);
        const photoGps = photo.gps || gps;
        await uploadFile(`/field-inspections/${created.id}/photos`, photo.file, {captured_at: photo.captured_at || new Date().toISOString(), timezone: browserTimezone(), site_id: photo.site_id || siteId, area_id: photo.area_id || areaId, equipment_id: photo.equipment_id || null, gps_status: photoGps.gps_status, gps_lat: photoGps.gps_lat, gps_lng: photoGps.gps_lng, gps_accuracy_m: photoGps.gps_accuracy_m, gps_captured_at: photoGps.gps_captured_at, gps_provider: photoGps.gps_provider, gps_reason: photoGps.gps_reason, manual_location_note: photoGps.manual_location_note, privacy_blur: privacyBlur, rotation_degrees: photo.rotation || 0, crop_to_square: Boolean(photo.square), client_reference: `${created.client_reference || created.id}:${photo.id}`}, {timeoutMs: 5 * 60 * 1000});
      }
      setUploadProgress("Fotoğraflar yüklendi; analiz kuyruğa alınıyor…");
      let fresh = await api(`/field-inspections/${created.id}`);
      setCurrent(fresh);
      const analyzed = await api(`/field-inspections/${created.id}/analyze`, {method: "POST"});
      fresh = analyzed.inspection || fresh;
      setCurrent(fresh);
      setMessage(fresh.ai_status === "failed" ? "Denetim kaydedildi; AI taslağı oluşturulamadı. Fotoğraflar ve kayıt korunuyor." : "Denetim kaydedildi; AI analizi uzman onayı bekleyen taslak olarak kuyruğa alındı.");
      setPhotos([]); setNotes(""); setGps(EMPTY_GPS); setManual(EMPTY_MANUAL); await loadRecent(companyId);
    } catch (ex) { setError(messageFrom(ex)); } finally { setUploadProgress(""); setBusy(false); }
  }

  async function retryAnalysis() {
    if (!current?.id) return;
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/analyze`, {method: "POST"}); setCurrent(data.inspection); setMessage("AI analizi yeniden kuyruğa alındı; sonuçlar uzman onayı bekler."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function reviewFinding(finding, status) {
    let review_note = null;
    if (status === "rejected" || status === "not_verifiable") {
      review_note = window.prompt(status === "rejected" ? "Reddetme gerekçesi:" : "Görüntüden doğrulanamadı gerekçesi:", "")?.trim() || null;
    }
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/findings/${finding.id}`, {method: "PATCH", body: JSON.stringify({status, review_note})}); setCurrent((row) => ({...row, findings: row.findings.map((item) => item.id === data.id ? data : item)})); setMessage(`Bulgu ${formatStatus(status).toLocaleLowerCase("tr-TR")} olarak kaydedildi.`); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function editFinding(finding) {
    const hazard_name = window.prompt("Tehlike başlığı:", finding.hazard_name || "")?.trim();
    if (!hazard_name) return;
    const visual_evidence = window.prompt("Fotoğrafta görülen kanıt:", finding.visual_evidence || "")?.trim();
    if (!visual_evidence) return;
    const nonconformity_description = window.prompt("Uygunsuzluk açıklaması:", finding.nonconformity_description || "")?.trim();
    if (!nonconformity_description) return;
    const suggested_priority = (window.prompt("Önerilen öncelik (low, medium, high, critical):", finding.suggested_priority || "medium") || "medium").trim().toLowerCase();
    if (!["low", "medium", "high", "critical"].includes(suggested_priority)) return setError("Öncelik low, medium, high veya critical olmalıdır.");
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/findings/${finding.id}`, {method: "PATCH", body: JSON.stringify({status: finding.status, hazard_name, visual_evidence, nonconformity_description, suggested_priority})}); setCurrent((row) => ({...row, findings: row.findings.map((item) => item.id === data.id ? data : item)})); setMessage("Bulgu uzman tarafından düzenlendi."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function saveLegalReference(event) {
    event.preventDefault();
    const target = current?.findings?.find((finding) => finding.id === Number(legalDraft.finding_id));
    if (!target || !legalDraft.regulation_name) return setError("Bulgu ve mevzuat başlığı seçin.");
    const references = (target.legal_references || []).map((reference) => ({regulation_name: reference.regulation_name, article: reference.article, paragraph: reference.paragraph, source_url: reference.source_url, source_version: reference.source_version, relation_explanation: reference.relation_explanation, verification_status: reference.verification_status}));
    references.push({regulation_name: legalDraft.regulation_name, article: legalDraft.article.trim() || null, relation_explanation: legalDraft.relation_explanation.trim() || null, verification_status: legalDraft.verification_status});
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/findings/${target.id}/legal-references`, {method: "PUT", body: JSON.stringify({references})}); setCurrent((row) => ({...row, findings: row.findings.map((item) => item.id === data.id ? data : item)})); setLegalDraft({finding_id: "", regulation_name: "", article: "", relation_explanation: "", verification_status: "needs_expert_review"}); setMessage("Mevzuat atfı uzman kontrolü kaydıyla eklendi."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function createManualFinding(event) {
    event.preventDefault();
    if (!current?.id) return setError("Önce denetimi kaydedin.");
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/findings`, {method: "POST", body: JSON.stringify({...manual, category_id: manual.category_id ? Number(manual.category_id) : null, photo_id: manual.photo_id ? Number(manual.photo_id) : null})}); setCurrent((row) => ({...row, findings: [...(row.findings || []), data], status: "in_review"})); setManual(EMPTY_MANUAL); setMessage("Manuel bulgu uzman incelemesine eklendi."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function createAction(event) {
    event.preventDefault();
    if (!current?.id) return;
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/findings/${actionDraft.finding_id}/actions`, {method: "POST", body: JSON.stringify({finding_id: Number(actionDraft.finding_id), title: actionDraft.title, activity: actionDraft.activity, responsible_employee_id: actionDraft.responsible_employee_id ? Number(actionDraft.responsible_employee_id) : null, term_date: actionDraft.term_date || null, priority: actionDraft.priority, responsible_role: "İşveren / sorumlu birim"})}); setCurrent((row) => ({...row, actions: [...(row.actions || []), data], findings: row.findings.map((finding) => finding.id === Number(actionDraft.finding_id) ? {...finding, actions: [...(finding.actions || []), data]} : finding)})); setActionDraft({finding_id: "", title: "", activity: "", responsible_employee_id: "", term_date: "", priority: "medium"}); setMessage("Düzeltici/önleyici faaliyet kaydedildi."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function createAnnotation(event) {
    event.preventDefault();
    if (!current?.id || !annotationDraft.photo_id) return setError("İşaret için fotoğraf seçin.");
    try {
      setBusy(true); clearFeedback();
      await api(`/field-inspections/${current.id}/photos/${annotationDraft.photo_id}/annotations`, {method: "POST", body: JSON.stringify({...annotationDraft, photo_id: Number(annotationDraft.photo_id), finding_id: annotationDraft.finding_id ? Number(annotationDraft.finding_id) : null, x: Number(annotationDraft.x), y: Number(annotationDraft.y), width: Number(annotationDraft.width), height: Number(annotationDraft.height)})});
      setCurrent(await api(`/field-inspections/${current.id}`));
      setMessage("Fotoğraf işareti kaydedildi; işaretlenmiş türev güncellendi.");
    } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function editAnnotation(annotation) {
    const raw = window.prompt("İşaret konumu ve boyutu (x,y,genişlik,yükseklik; 0–1):", [annotation.x, annotation.y, annotation.width, annotation.height].map((value) => Number(value || 0).toFixed(3)).join(","));
    if (raw == null) return;
    const values = raw.split(",").map((value) => Number(value.trim()));
    if (values.length !== 4 || values.some((value) => !Number.isFinite(value) || value < 0 || value > 1)) return setError("İşaret koordinatları 0 ile 1 arasında dört sayı olmalıdır.");
    try { setBusy(true); clearFeedback(); await api(`/field-inspections/${current.id}/annotations/${annotation.id}`, {method: "PATCH", body: JSON.stringify({x: values[0], y: values[1], width: values[2], height: values[3]})}); setCurrent(await api(`/field-inspections/${current.id}`)); setMessage("İşaret konumu güncellendi."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function deleteAnnotation(annotation) {
    try { setBusy(true); clearFeedback(); await api(`/field-inspections/${current.id}/annotations/${annotation.id}`, {method: "DELETE"}); setCurrent(await api(`/field-inspections/${current.id}`)); setMessage("İşaret kaldırıldı; orijinal fotoğraf korunuyor."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function approve() {
    try { setBusy(true); clearFeedback(); const data = await api(`/field-inspections/${current.id}/approve`, {method: "POST", body: JSON.stringify({note: "Uzman incelemesi tamamlandı."})}); setCurrent(data); setMessage("Denetim onaylandı; PDF ve Excel raporları hazır."); } catch (ex) { setError(messageFrom(ex)); } finally { setBusy(false); }
  }

  async function downloadReport(extension) {
    if (!current?.id) return;
    try { await downloadFile(`/field-inspections/${current.id}/report.${extension}`, `saha-denetim-${current.inspection_no}.${extension}`); } catch (ex) { setError(messageFrom(ex)); }
  }

  if (loading) return <section className="visual-field-page"><div className="visual-field-loading">Görsel saha denetimi hazırlanıyor…</div></section>;

  return (
    <section className="visual-field-page">
      <header className="visual-field-hero">
        <div><span className="visual-eyebrow">Yeni görsel saha denetimi</span><h1>Fotoğrafı kanıta, kanıtı aksiyona dönüştür.</h1><p>GPS, tesis–alan bağlamı ve güvenli fotoğraf türevleri tek denetim zincirinde tutulur.</p></div>
        <div className="visual-hero-badge"><Sparkles size={18} /> AI yalnızca uzman yardımcısıdır</div>
      </header>
      {(message || error) && <div className={`visual-feedback ${error ? "is-error" : "is-success"}`} role="status">{error || message}</div>}
      <div className="visual-field-layout">
        <main className="visual-field-main">
          <section className="visual-card">
            <div className="visual-card-heading"><div><span className="visual-step">01</span><h2>İşyeri ve saha bağlamı</h2></div><ShieldAlert size={21} /></div>
            <label className="visual-control"><span>Yetkili olduğunuz işyeri</span><select value={companyId} onChange={(event) => changeCompany(event.target.value)}><option value="">İşyeri seçin</option>{catalog.companies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>
            {company && <div className="visual-company-meta"><strong>{company.name}</strong><span>{company.address || "Adres yok"}</span><span>İşveren: {company.authorized_person || "—"}</span><span>SGK: {company.sgk_registry_no || "—"} · NACE: {company.nace_code || "—"} · {company.hazard_class || "Tehlike sınıfı yok"}</span></div>}
            {!companyId && <p className="visual-inline-warning">Denetime başlamak için önce işyeri seçin. İşyeri seçilmeden tesis, alan ve ekipman bilgileri gösterilmez.</p>}
            <label className="visual-control"><span>Arama (tesis, alan veya ekipman)</span><input value={locationQuery} onChange={(event) => setLocationQuery(event.target.value)} placeholder="Sahada hızlı bul…" /></label>
            <div className="visual-select-grid">
              <label className="visual-control"><span>Tesis / saha</span><select value={siteId} onChange={(event) => {setSiteId(event.target.value); setAreaId(""); setEquipmentId("");}} disabled={!companyId}><option value="">Seçin</option>{sites.map((item) => <option key={item.id} value={item.id}>{item.name}{item.site_type ? ` · ${item.site_type}` : ""}</option>)}</select><button type="button" className="visual-link-button" onClick={() => addNamed("site")}><Plus size={14} /> Yeni tesis/saha</button></label>
              <label className="visual-control"><span>Bölüm / alan</span><select value={areaId} onChange={(event) => {setAreaId(event.target.value); setEquipmentId("");}} disabled={!siteId}><option value="">Seçin</option>{areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><button type="button" className="visual-link-button" onClick={() => addNamed("area")} disabled={!siteId}><Plus size={14} /> Yeni bölüm</button></label>
              <label className="visual-control"><span>Ekipman / nokta <small>(isteğe bağlı)</small></span><select value={equipmentId} onChange={(event) => setEquipmentId(event.target.value)} disabled={!areaId}><option value="">Belirtmek istemiyorum</option>{equipment.map((item) => <option key={item.id} value={item.id}>{item.name}{item.equipment_type ? ` · ${item.equipment_type}` : ""}</option>)}</select><button type="button" className="visual-link-button" onClick={() => addNamed("equipment")} disabled={!areaId}><Plus size={14} /> Yeni ekipman</button></label>
            </div>
          </section>

          <section className="visual-card">
            <div className="visual-card-heading"><div><span className="visual-step">02</span><h2>İncelenecek tehlikeler</h2></div><span className="visual-count">{selectedCategories.length} kategori</span></div>
            <label className="visual-check-line"><input type="checkbox" checked={scanAll} onChange={(event) => setScanAll(event.target.checked)} /><span><strong>Tüm görünür tehlikeleri tara</strong><small>Kategori seçimi AI’yi diğer açıkça görülen tehlikeleri değerlendirmekten alıkoymaz.</small></span></label>
            <div className="visual-category-tools"><input value={categoryQuery} onChange={(event) => setCategoryQuery(event.target.value)} placeholder="75 kategoride ara…" /><button type="button" onClick={() => setSelectedCategories(catalog.categories.map((item) => Number(item.id)))}>Tümünü seç</button><button type="button" onClick={() => setSelectedCategories([])}>Temizle</button></div>
            <div className="visual-category-groups">{categoryGroups.map((group) => <details key={group.title} open><summary>{group.title}<ChevronDown size={16} /></summary><div className="visual-category-list">{group.rows.map((item) => <label key={item.id}><input type="checkbox" checked={selectedCategories.includes(Number(item.id))} onChange={() => toggleCategory(item.id)} /><span>{item.name}</span></label>)}</div></details>)}</div>
            <div className="visual-custom-hazards"><div><strong>Özel tehlikeler</strong><small>İşyeri veya OSGB kapsamı tenant içinde tutulur.</small></div><div className="visual-custom-hazard-controls"><select value={customHazardScope} onChange={(event) => setCustomHazardScope(event.target.value)} aria-label="Özel tehlike kapsamı"><option value="company">İşyeri kapsamı</option><option value="osgb">OSGB kapsamı</option></select><button type="button" className="visual-secondary-button" onClick={addCustomHazard} disabled={!selectedCategories.length}><Plus size={15} /> Yeni tehlike</button></div></div>
            {selectedCompanyHazards.length > 0 && <div className="visual-hazard-chips">{selectedCompanyHazards.map((item) => <label key={item.id} className={selectedHazards.includes(Number(item.id)) ? "is-selected" : ""}><input type="checkbox" checked={selectedHazards.includes(Number(item.id))} onChange={() => toggleHazard(item.id)} />{item.name}</label>)}</div>}
          </section>

          <section className="visual-card">
            <div className="visual-card-heading"><div><span className="visual-step">03</span><h2>Konum</h2></div><MapPin size={21} /></div>
            <div className="visual-gps-row"><button type="button" className="visual-gps-button" onClick={captureGps} disabled={gpsBusy}><MapPin size={18} /> {gpsBusy ? "Konum alınıyor…" : gps.gps_status === "captured" || gps.gps_status === "low_accuracy" ? "Konumu yenile" : "Konumu al"}</button><span className={`visual-gps-state ${gps.gps_status === "captured" ? "is-ok" : gps.gps_status === "low_accuracy" ? "is-warn" : ""}`}>{gps.gps_lat != null ? `${gps.gps_status === "low_accuracy" ? "Düşük doğruluk" : "Konum alındı"} · ±${gps.gps_accuracy_m} m` : "GPS alınamadı — manuel açıklama ile devam edilebilir"}</span></div>
            {gps.gps_reason && <p className="visual-inline-warning">{gps.gps_reason}</p>}
            <label className="visual-control"><span>Manuel konum / iç mekân açıklaması <small>(GPS alınamazsa)</small></span><input value={gps.manual_location_note} onChange={(event) => setGps((row) => ({...row, manual_location_note: event.target.value}))} placeholder="Örn. B blok, zemin kat, doğu kapısı" maxLength={500} /></label>
          </section>

          <section className="visual-card">
            <div className="visual-card-heading"><div><span className="visual-step">04</span><h2>Fotoğraf kanıtı</h2></div><span className="visual-count">{photos.length}/8</span></div>
            <div className="visual-photo-buttons"><button type="button" onClick={() => cameraRef.current?.click()} disabled={photos.length >= 8}><Camera size={20} /><span>Fotoğraf çek<small>Kamerayı aç</small></span></button><button type="button" onClick={() => galleryRef.current?.click()} disabled={photos.length >= 8}><ImagePlus size={20} /><span>Galeriden seç<small>Birden fazla ekleyin</small></span></button><input ref={cameraRef} hidden type="file" accept="image/jpeg,image/png,image/webp" capture="environment" onChange={selectPhotos} /><input ref={galleryRef} hidden type="file" accept="image/jpeg,image/png,image/webp" multiple onChange={selectPhotos} /></div>
            <label className="visual-check-line compact"><input type="checkbox" checked={privacyBlur} onChange={(event) => setPrivacyBlur(event.target.checked)} /><span><strong>Gizlilik bulanıklığı</strong><small>Orijinal korunur; analiz ve önizleme türevinde hassas ayrıntılar yumuşatılır.</small></span></label>
            {photos.length > 0 && <div className="visual-local-photos">{photos.map((photo) => <figure key={photo.id}><img src={photo.url} alt="Yüklenecek saha kanıtı" style={{transform: `rotate(${photo.rotation}deg)`, objectFit: photo.square ? "cover" : "contain"}} /><div className="visual-photo-context"><label><span>Bölüm</span><select value={photo.area_id || areaId} onChange={(event) => updatePhoto(photo.id, {area_id: event.target.value, equipment_id: ""})}>{photoAreas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label><span>Ekipman</span><select value={photo.equipment_id || ""} onChange={(event) => updatePhoto(photo.id, {equipment_id: event.target.value})}><option value="">Denetim ekipmanı</option>{listFrom(catalog.equipment).filter((item) => Number(item.area_id) === Number(photo.area_id || areaId)).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><button type="button" className="visual-photo-gps-button" onClick={() => capturePhotoGps(photo.id)} disabled={gpsBusy}>{gpsBusy ? "Konum alınıyor…" : photoGpsStatus(photo)}</button></div><div className="visual-photo-actions"><button type="button" onClick={() => updatePhoto(photo.id, {rotation: (photo.rotation + 90) % 360})} aria-label="Fotoğrafı döndür">↻</button><button type="button" onClick={() => updatePhoto(photo.id, {square: !photo.square})} aria-label="Kare kırpma önizlemesi">□</button><button type="button" onClick={() => removePhoto(photo.id)} aria-label="Fotoğrafı kaldır"><Trash2 size={14} /></button></div><figcaption>{photo.file.name}</figcaption></figure>)}</div>}
            {uploadProgress && <p className="visual-upload-progress" role="status">{uploadProgress}</p>}
            <label className="visual-control"><span>Denetim notu</span><textarea value={notes} onChange={(event) => setNotes(event.target.value)} rows={3} maxLength={5000} placeholder="Gözlem bağlamı, vardiya veya ek not…" /></label>
          </section>
          <button className="visual-submit" type="button" onClick={createAndAnalyze} disabled={busy || !companyId || !siteId || !areaId || !photos.length}><Sparkles size={18} /> {busy ? "Denetim hazırlanıyor…" : "Denetimi kaydet ve AI taslağını başlat"}</button>
          <p className="visual-privacy-note">AI çıktısı kesin karar değildir. Fotoğrafta açıkça görülmeyen hususlar bulgu olarak yazılmamalı; her bulgu uzman onayı olmadan rapora giremez.</p>
        </main>

        <aside className="visual-field-side">
          <section className="visual-card visual-current-card">
            <div className="visual-card-heading"><div><span className="visual-eyebrow">Aktif denetim</span><h2>{current?.inspection_no || "Henüz kayıt yok"}</h2></div><RefreshCw size={19} /></div>
            {!current ? <p className="visual-muted">Fotoğraf yükleyip kaydettiğinizde analiz durumu, işaretli görseller ve uzman incelemesi burada görünür.</p> : <>
              <div className="visual-status-pills"><span>{formatStatus(current.status)}</span><span className={current.ai_status === "failed" ? "is-error" : ""}>AI: {formatStatus(current.ai_status)}</span></div>
              {current.ai_error && <p className="visual-inline-warning">{current.ai_error}</p>}
              {current.ai_general_assessment && <div className="visual-ai-summary"><Sparkles size={16} /><p>{current.ai_general_assessment}</p></div>}
              {current.ai_warning && <p className="visual-inline-warning">{current.ai_warning}</p>}
              {current.revisions?.length > 0 && <details className="visual-revision-details"><summary>Revizyon / audit geçmişi ({current.revisions.length})</summary><div>{current.revisions.slice(0, 12).map((item) => <p key={item.id}><strong>{formatDate(item.created_at)}</strong> · {item.action} · {item.description}</p>)}</div></details>}
              <div className="visual-photo-view-toggle" role="group" aria-label="Fotoğraf görünümü"><button type="button" className={photoVariant === "marked" ? "is-active" : ""} onClick={() => setPhotoVariant("marked")}>İşaretlenmiş</button><button type="button" className={photoVariant === "original" ? "is-active" : ""} onClick={() => setPhotoVariant("original")}>Orijinal</button></div>
              <div className="visual-current-photos">{(current.photos || []).map((photo) => <div className="visual-marked-photo" key={photo.id}>{photoUrls[photo.id] ? <img src={photoUrls[photo.id]} alt={photoVariant === "original" ? "Orijinal saha kanıtı" : "İşaretlenmiş saha kanıtı"} /> : <span>Görsel yükleniyor…</span>}<small>{photo.original_name} · {photo.gps?.status || "GPS gizli"} · {photo.location?.area?.name || "Alan yok"}{photo.location?.equipment?.name ? ` · ${photo.location.equipment.name}` : ""}</small></div>)}</div>
              <form className="visual-mini-form visual-annotation-form" onSubmit={createAnnotation}><h3>Fotoğraf üzerinde uzman işareti</h3><p className="visual-muted">Koordinatlar fotoğrafın genişlik/yüksekliğine göre 0–1 aralığındadır. Orijinal fotoğraf değişmez.</p><div className="visual-form-two"><select required value={annotationDraft.photo_id} onChange={(event) => setAnnotationDraft((row) => ({...row, photo_id: event.target.value}))}><option value="">Fotoğraf seçin</option>{current.photos?.map((photo) => <option key={photo.id} value={photo.id}>{photo.original_name}</option>)}</select><select value={annotationDraft.finding_id} onChange={(event) => setAnnotationDraft((row) => ({...row, finding_id: event.target.value}))}><option value="">Bulguya bağlama (isteğe bağlı)</option>{current.findings?.map((finding) => <option key={finding.id} value={finding.id}>#{finding.finding_no} {finding.hazard_name}</option>)}</select></div><div className="visual-form-two"><select value={annotationDraft.shape_type} onChange={(event) => setAnnotationDraft((row) => ({...row, shape_type: event.target.value}))}><option value="rectangle">Kutu</option><option value="arrow">Ok</option><option value="point">Nokta</option><option value="region">Bölge</option></select><input value={annotationDraft.label} onChange={(event) => setAnnotationDraft((row) => ({...row, label: event.target.value}))} placeholder="İşaret etiketi (örn. 1)" /></div><div className="visual-form-two"><input type="number" min="0" max="1" step="0.01" value={annotationDraft.x} onChange={(event) => setAnnotationDraft((row) => ({...row, x: event.target.value}))} aria-label="İşaret x" /><input type="number" min="0" max="1" step="0.01" value={annotationDraft.y} onChange={(event) => setAnnotationDraft((row) => ({...row, y: event.target.value}))} aria-label="İşaret y" /><input type="number" min="0" max="1" step="0.01" value={annotationDraft.width} onChange={(event) => setAnnotationDraft((row) => ({...row, width: event.target.value}))} aria-label="İşaret genişlik" /><input type="number" min="0" max="1" step="0.01" value={annotationDraft.height} onChange={(event) => setAnnotationDraft((row) => ({...row, height: event.target.value}))} aria-label="İşaret yükseklik" /></div><button type="submit" className="visual-secondary-button full" disabled={busy}><Plus size={15} /> İşareti ekle</button></form>
              {(current.photos || []).some((photo) => photo.annotations?.length) && <div className="visual-annotation-list"><h3>Kayıtlı işaretler</h3>{(current.photos || []).flatMap((photo) => (photo.annotations || []).map((annotation) => <div className="visual-annotation-row" key={annotation.id}><span><strong>{annotation.label || `#${annotation.id}`}</strong><small>{photo.original_name} · {annotation.shape_type}</small></span><div><button type="button" onClick={() => editAnnotation(annotation)} disabled={busy}>Taşı/düzenle</button><button type="button" onClick={() => deleteAnnotation(annotation)} disabled={busy}>Sil</button></div></div>))}</div>}
              {current.ai_status === "failed" && <button type="button" className="visual-secondary-button full" onClick={retryAnalysis} disabled={busy}><RefreshCw size={15} /> AI analizini yeniden dene</button>}
              <form className="visual-mini-form visual-legal-form" onSubmit={saveLegalReference}><h3>Mevzuat atfı ve uzman doğrulaması</h3><div className="visual-form-two"><select required value={legalDraft.finding_id} onChange={(event) => setLegalDraft((row) => ({...row, finding_id: event.target.value}))}><option value="">Bulgu seçin</option>{current.findings?.map((finding) => <option key={finding.id} value={finding.id}>#{finding.finding_no} {finding.hazard_name}</option>)}</select><select required value={legalDraft.regulation_name} onChange={(event) => setLegalDraft((row) => ({...row, regulation_name: event.target.value}))}><option value="">Mevzuat başlığı seçin</option>{(catalog.legal_catalog || []).map((item) => <option key={item.name} value={item.name}>{item.name}</option>)}</select></div><div className="visual-form-two"><input value={legalDraft.article} onChange={(event) => setLegalDraft((row) => ({...row, article: event.target.value}))} placeholder="Madde/fıkra (uzman kontrolü)" /><select value={legalDraft.verification_status} onChange={(event) => setLegalDraft((row) => ({...row, verification_status: event.target.value}))}><option value="needs_expert_review">Uzman kontrolü gerekli</option><option value="verified">Resmî kaynakla doğrulandı</option><option value="rejected">Atıf reddedildi</option></select></div><input value={legalDraft.relation_explanation} onChange={(event) => setLegalDraft((row) => ({...row, relation_explanation: event.target.value}))} placeholder="Fotoğraftaki bulguyla ilişki açıklaması" /><button className="visual-secondary-button full" type="submit" disabled={busy}><Plus size={15} /> Mevzuat atfını kaydet</button></form>
              {current.findings?.length > 0 && <div className="visual-findings"><h3>Bulgular · uzman onayı bekliyor</h3>{current.findings.map((finding) => <article key={finding.id} className="visual-finding"><div className="visual-finding-top"><strong>#{finding.finding_no} {finding.hazard_name}</strong><span className={`priority-${finding.suggested_priority}`}>{finding.suggested_priority}</span></div><p>{finding.visual_evidence}</p><p className="visual-finding-description">{finding.nonconformity_description}</p>{finding.review_note && <p className="visual-inline-warning">İnceleme notu: {finding.review_note}</p>}<small>{formatStatus(finding.status)} · kaynak: {finding.source === "ai" ? "AI taslağı" : "manuel"}</small>{finding.legal_references?.length > 0 && <div className="visual-legal-mini">{finding.legal_references.map((reference) => <span key={reference.id}>{reference.regulation_name} · {reference.article || "madde uzman kontrolü"} · {reference.verification_status}</span>)}</div>}{finding.status === "ai_draft" || finding.status === "under_review" ? <div className="visual-finding-actions"><button type="button" onClick={() => editFinding(finding)} disabled={busy}>Düzenle</button><button type="button" onClick={() => reviewFinding(finding, "accepted")} disabled={busy}><CheckCircle2 size={14} /> Kabul et</button><button type="button" onClick={() => reviewFinding(finding, "not_verifiable")} disabled={busy}>Doğrulanamadı</button><button type="button" onClick={() => reviewFinding(finding, "rejected")} disabled={busy}><X size={14} /> Reddet</button></div> : <><button type="button" className="visual-link-button" onClick={() => editFinding(finding)}>Bulgu metnini düzenle</button><button type="button" className="visual-link-button" onClick={() => setActionDraft((draft) => ({...draft, finding_id: String(finding.id)}))}>Bu bulguya faaliyet ekle</button></>}</article>)}</div>}
              <form className="visual-mini-form" onSubmit={createManualFinding}><h3>Manuel bulgu ekle</h3><input required value={manual.hazard_name} onChange={(event) => setManual((row) => ({...row, hazard_name: event.target.value}))} placeholder="Tehlike / uygunsuzluk başlığı" /><textarea required value={manual.visual_evidence} onChange={(event) => setManual((row) => ({...row, visual_evidence: event.target.value}))} placeholder="Fotoğrafta görülen kanıt" rows={2} /><textarea required value={manual.nonconformity_description} onChange={(event) => setManual((row) => ({...row, nonconformity_description: event.target.value}))} placeholder="Uygunsuzluk açıklaması" rows={2} /><div className="visual-form-two"><select value={manual.category_id} onChange={(event) => setManual((row) => ({...row, category_id: event.target.value}))}><option value="">Kategori yok</option>{catalog.categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><select value={manual.photo_id} onChange={(event) => setManual((row) => ({...row, photo_id: event.target.value}))}><option value="">Fotoğraf yok</option>{current.photos?.map((photo) => <option key={photo.id} value={photo.id}>{photo.original_name}</option>)}</select></div><button className="visual-secondary-button full" type="submit" disabled={busy}><Plus size={15} /> Manuel bulguyu incelemeye al</button></form>
              <form className="visual-mini-form" onSubmit={createAction}><h3>Düzeltici / önleyici faaliyet</h3><select required value={actionDraft.finding_id} onChange={(event) => setActionDraft((row) => ({...row, finding_id: event.target.value}))}><option value="">Bağlı bulgu seçin</option>{current.findings?.filter((finding) => !["rejected", "superseded"].includes(finding.status)).map((finding) => <option key={finding.id} value={finding.id}>#{finding.finding_no} {finding.hazard_name}</option>)}</select><input required value={actionDraft.title} onChange={(event) => setActionDraft((row) => ({...row, title: event.target.value}))} placeholder="Faaliyet başlığı" /><textarea required value={actionDraft.activity} onChange={(event) => setActionDraft((row) => ({...row, activity: event.target.value}))} placeholder="Yapılacak faaliyet" rows={2} /><div className="visual-form-two"><select required value={actionDraft.responsible_employee_id} onChange={(event) => setActionDraft((row) => ({...row, responsible_employee_id: event.target.value}))}><option value="">Sorumlu çalışan seçin</option>{responsibles.map((person) => <option key={person.id} value={person.id}>{person.full_name}{person.job_title ? ` · ${person.job_title}` : ""}</option>)}</select><input required type="date" value={actionDraft.term_date} onChange={(event) => setActionDraft((row) => ({...row, term_date: event.target.value}))} /></div><button className="visual-secondary-button full" type="submit" disabled={busy}><Plus size={15} /> Faaliyeti kaydet</button></form>
              <div className="visual-approval"><p>AI ve manuel taslaklar kabul/reddedilmeden onay kilidi açılmaz.</p><button type="button" className="visual-approve-button" onClick={approve} disabled={busy || current.status === "approved"}><CheckCircle2 size={17} /> {current.status === "approved" ? "Onaylandı" : "Uzman onayı ver"}</button>{current.status === "approved" && <div className="visual-report-buttons"><button type="button" onClick={() => downloadReport("pdf")}><Download size={14} /> PDF</button><button type="button" onClick={() => downloadReport("xlsx")}><Download size={14} /> Excel</button></div>}</div>
            </>}
          </section>
          <section className="visual-card"><div className="visual-card-heading"><div><span className="visual-eyebrow">Geçmiş</span><h2>Son denetimler</h2></div></div>{recent.length ? recent.map((item) => <button type="button" className="visual-recent-row" key={item.id} onClick={async () => { try { setCurrent(await api(`/field-inspections/${item.id}`)); } catch (ex) { setError(messageFrom(ex)); } }}><span><strong>{item.inspection_no}</strong><small>{formatDate(item.inspection_at)} · {item.photo_count || 0} fotoğraf</small></span><em>{formatStatus(item.status)}</em></button>) : <p className="visual-muted">Bu işyeri için kayıt yok.</p>}</section>
        </aside>
      </div>
    </section>
  );
}

export default VisualFieldInspectionPage;
