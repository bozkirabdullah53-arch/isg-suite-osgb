import React, {useEffect, useMemo, useRef, useState} from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  Download,
  FileText,
  ImagePlus,
  Lightbulb,
  MapPin,
  MapPinned,
  Pencil,
  RefreshCw,
  Save,
  ScanLine,
  ShieldAlert,
  Sparkles,
  Trash2,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import {api, downloadFile, downloadFormFile, uploadFile} from "./api";
import {getAccessToken} from "./auth_session";
import {
  enqueueOfflineFinding,
  flushOfflineFindings,
  listOfflineFindings,
  readOfflineReference,
  saveOfflineReference,
} from "./field_inspection_offline";
import {buildMobileSyncStatus, isMobileSyncStatusEnabled} from "./mobile_sync_status";
import {VisualFieldInspectionPage} from "./visual_field_inspection";
import "./field_inspection.css";

const EMPTY_FORM = {
  company_id: "",
  department_id: "",
  department_name: "",
  category_id: "",
  hazard_id: "",
  location: "",
  summary: "",
  existing_measures: "",
  action: "",
  responsible_person: "",
  responsible_department: "",
  term_date: "",
  probability: 3,
  severity: 3,
};

function numberOrNull(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function formatVisionPenalty(value) {
  if (!value) return "";
  if (value.display) return String(value.display);
  const min = Number(value.min_tl);
  const max = Number(value.max_tl);
  if (Number.isFinite(min) && Number.isFinite(max)) {
    return `${min.toLocaleString("tr-TR")}–${max.toLocaleString("tr-TR")} TL`;
  }
  return "İhlal niteliği ve güncel idari para cezası tarife doğrulaması bekliyor.";
}

function visionProviderLabel(provider) {
  if (provider === "api") return "Vision API";
  if (provider === "yolo") return "YOLO";
  if (provider === "unavailable") return "Görsel AI kullanılamıyor";
  return "Heuristik";
}

function makeClientReference() {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  } catch {
    /* fallback below */
  }
  return `field_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function scopeFor(user) {
  return {
    user_id: Number(user?.id) || 0,
    osgb_id: Number(user?.osgb_id) || 0,
  };
}

function listFrom(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.items)) return value.items;
  if (Array.isArray(value?.data)) return value.data;
  return [];
}

function formatDate(value) {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("tr-TR", {
      dateStyle: "short",
      timeStyle: "short",
    });
  } catch {
    return String(value);
  }
}

function riskClass(level) {
  const text = String(level || "").toLocaleLowerCase("tr-TR");
  if (text.includes("çok yüksek")) return "risk-critical";
  if (text.includes("yüksek")) return "risk-high";
  if (text.includes("orta")) return "risk-medium";
  return "risk-low";
}

function dateInputValue(value) {
  if (!value) return "";
  const raw = String(value);
  if (/^\d{4}-\d{2}-\d{2}/.test(raw)) return raw.slice(0, 10);
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  return parsed.toISOString().slice(0, 10);
}

function compressPhoto(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Fotoğraf okunamadı."));
    reader.onload = () => {
      const image = new Image();
      image.onerror = () => reject(new Error("Fotoğraf biçimi desteklenmiyor."));
      image.onload = () => {
        const maxEdge = 1280;
        const scale = Math.min(1, maxEdge / Math.max(image.naturalWidth || 1, image.naturalHeight || 1));
        const canvas = document.createElement("canvas");
        canvas.width = Math.max(1, Math.round((image.naturalWidth || 1) * scale));
        canvas.height = Math.max(1, Math.round((image.naturalHeight || 1) * scale));
        const context = canvas.getContext("2d");
        if (!context) {
          reject(new Error("Fotoğraf işlenemedi."));
          return;
        }
        context.drawImage(image, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL("image/jpeg", 0.78);
        resolve({
          id: makeClientReference(),
          name: String(file.name || "saha-fotografi.jpg").replace(/\.[^.]+$/, "") + ".jpg",
          type: "image/jpeg",
          data_url: dataUrl,
          description: "Saha denetimi fotoğraf kanıtı",
          tags: [],
          captured_at: new Date().toISOString(),
          gps_lat: null,
          gps_lng: null,
          gps_accuracy_m: null,
          client_reference: null,
        });
      };
      image.src = String(reader.result || "");
    };
      reader.readAsDataURL(file);
  });
}

// Fotoğraf önizlemesi data: URL olarak tutulur. Bunu tekrar fetch() etmek,
// canlıdaki connect-src 'self' CSP kuralı nedeniyle mobil tarayıcılarda
// "Failed to fetch" üretebilir. Ağ isteği yapmadan doğrudan File oluştur.
function dataUrlToFile(dataUrl, filename = "saha-fotografi.jpg") {
  const value = String(dataUrl || "");
  const comma = value.indexOf(",");
  if (!value.startsWith("data:") || comma < 0) {
    throw new Error("Fotoğraf verisi okunamadı.");
  }

  const header = value.slice(0, comma);
  const encoded = value.slice(comma + 1);
  const mime = header.match(/^data:([^;,]+)/i)?.[1] || "image/jpeg";
  const binary = atob(encoded);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1) {
    bytes[index] = binary.charCodeAt(index);
  }
  return new File([bytes], filename, {type: mime});
}

// Fotoğraf üzerinde bounding box çizimi (normalize 0-1 koordinat → px)
const SEV_COLORS = {5: "#991b1b", 4: "#9a3412", 3: "#92400e", 2: "#1e40af", 1: "#475569"};
const SEV_LABELS = {5: "Kritik", 4: "Yüksek", 3: "Orta", 2: "Düşük", 1: "Çok düşük"};

function BboxOverlay({imageSrc, annotations}) {
  const imgRef = useRef(null);
  const [size, setSize] = useState({w: 0, h: 0});

  useEffect(() => {
    function update() {
      if (imgRef.current) setSize({w: imgRef.current.clientWidth, h: imgRef.current.clientHeight});
    }
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, []);

  if (!imageSrc) return null;
  return (
    <div className="field-bbox-wrap">
      <img
        ref={imgRef}
        src={imageSrc}
        alt="Saha kanıtı"
        onLoad={() => { if (imgRef.current) setSize({w: imgRef.current.clientWidth, h: imgRef.current.clientHeight}); }}
        className="field-bbox-img"
      />
      {annotations?.length > 0 && size.w > 0 && annotations.map((a, i) => {
        const [x, y, w, h] = a.box || [0, 0, 1, 1];
        const c = a.color || SEV_COLORS[a.severity] || "#475569";
        return (
          <div key={i} className="field-bbox-rect" style={{
            left: x * size.w, top: y * size.h, width: w * size.w, height: h * size.h,
            borderColor: c,
          }}>
            <span className="field-bbox-label" style={{background: c}}>
              {a.label}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function LegacyFieldInspectionPage({user}) {
  const scope = useMemo(() => scopeFor(user), [user?.id, user?.osgb_id]);
  const [companies, setCompanies] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [categories, setCategories] = useState([]);
  const [hazards, setHazards] = useState([]);
  const [tagCatalog, setTagCatalog] = useState([]);
  const [recent, setRecent] = useState([]);
  const [editingRiskId, setEditingRiskId] = useState(null);
  const [editingRiskCode, setEditingRiskCode] = useState("");
  const [editingRiskStatus, setEditingRiskStatus] = useState("Açık");
  const [editingDofId, setEditingDofId] = useState(null);
  const [deleteBusy, setDeleteBusy] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [photos, setPhotos] = useState([]);
  const [mode, setMode] = useState("ai");  // "ai" | "manual"
  const [visionResults, setVisionResults] = useState({});  // {photoId: analysis}
  const [visionBusy, setVisionBusy] = useState(null);  // photoId analyzing
  const [visionErr, setVisionErr] = useState({});  // {photoId: msg}
  const cameraInputRef = useRef(null);
  const galleryInputRef = useRef(null);
  const [selectedPhotoTags, setSelectedPhotoTags] = useState([]);
  const [gps, setGps] = useState({lat: null, lng: null, accuracy: null, captured_at: null});
  const [pending, setPending] = useState([]);
  const [online, setOnline] = useState(
    typeof navigator === "undefined" || navigator.onLine !== false,
  );
  const [busy, setBusy] = useState(false);
  const [syncBusy, setSyncBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [referenceLoading, setReferenceLoading] = useState(true);
  const [dlBusy, setDlBusy] = useState(null);
  const [aiHint, setAiHint] = useState(null);
  const [aiBusy, setAiBusy] = useState(false);
  const [pendingVisionHazardCode, setPendingVisionHazardCode] = useState("");
  const aiTimer = useRef(null);
  const aiSeq = useRef(0);

  const mobileSyncStatusEnabled = isMobileSyncStatusEnabled();
  const pendingCount = pending.length;
  const mobileSyncStatus = useMemo(
    () => mobileSyncStatusEnabled
      ? buildMobileSyncStatus({online, pendingCount, syncBusy})
      : null,
    [mobileSyncStatusEnabled, online, pendingCount, syncBusy],
  );

  const selectedCompany = companies.find((row) => Number(row.id) === Number(form.company_id));
  const selectedDepartment = departments.find((row) => Number(row.id) === Number(form.department_id));
  const selectedHazard = hazards.find((row) => Number(row.id) === Number(form.hazard_id));

  function updateField(name, value) {
    setForm((current) => ({...current, [name]: value}));
  }

  async function requestAiHint(text) {
    const seq = ++aiSeq.current;
    setAiBusy(true);
    try {
      const body = {text};
      if (form.company_id) body.company_id = Number(form.company_id);
      const r = await api("/risks/assistant", {method: "POST", body: JSON.stringify(body)});
      if (seq === aiSeq.current) setAiHint(r);
    } catch {
      /* öneri yardımcıdır; hata formu bozmaz */
    } finally {
      if (seq === aiSeq.current) setAiBusy(false);
    }
  }

  function applyAiHint() {
    if (!aiHint) return;
    const hh = aiHint.hazard_hint;
    const rs = aiHint.risk_suggestion;
    const next = {...form};
    if (hh?.matched) {
      const cat = categories.find((c) => c.name === hh.suggested_category);
      if (cat) next.category_id = String(cat.id);
    }
    if (rs) {
      if (rs.probability_hint) next.probability = rs.probability_hint;
      if (rs.severity_hint) next.severity = rs.severity_hint;
    }
    if (aiHint.compliance_preview?.compliance_score != null && aiHint.compliance_preview.compliance_score < 60) {
      if (!next.action) next.action = "Mevzuat uyum skoru düşük — düzeltici aksiyon planı hazırlayın.";
    }
    setForm(next);
    if (hh?.suggested_photo_tags?.length) {
      setSelectedPhotoTags((current) => {
        const merged = new Set([...current, ...hh.suggested_photo_tags]);
        return Array.from(merged);
      });
    }
    setAiHint(null);
  }

  useEffect(() => {
    if (aiTimer.current) clearTimeout(aiTimer.current);
    if (editingRiskId) {
      setAiHint(null);
      return;
    }
    const text = String(form.summary || "").trim();
    if (text.length < 5) {
      setAiHint(null);
      return;
    }
    aiTimer.current = setTimeout(() => void requestAiHint(text), 900);
    return () => clearTimeout(aiTimer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form.summary, editingRiskId]);

  function refreshPending() {
    setPending(listOfflineFindings(scope));
  }

  async function loadRecent(companyId) {
    if (!companyId) {
      setRecent([]);
      return;
    }
    try {
      const rows = listFrom(await api(`/risks?company_id=${encodeURIComponent(companyId)}`));
      setRecent(rows.filter((row) => row.record_origin === "field_inspection").slice(0, 30));
    } catch {
      // Saha kaydı offline iken son sunucu listesi zorunlu değildir.
    }
  }

  async function downloadReport(row) {
    if (!row?.id) return;
    setDlBusy(row.id);
    try {
      await downloadFile(`/risks/${row.id}/report.pdf`, `saha-bulgu-${row.risk_code || row.id}.pdf`);
    } catch {
      setError("Rapor indirilemedi; tekrar deneyin.");
    } finally {
      setDlBusy(null);
    }
  }

  function beginEditing(row) {
    if (!row?.id) return;
    if (photos.length && !(globalThis.confirm?.("Yeni kayıt taslağındaki fotoğraflar temizlenecek. Düzenlemeye geçilsin mi?") ?? true)) {
      return;
    }
    const dof = Array.isArray(row.dofs) && row.dofs.length ? row.dofs[0] : null;
    const categoryId = row.category_id || categories.find((item) => item.name === row.category_name)?.id || "";
    setEditingRiskId(Number(row.id));
    setEditingRiskCode(row.risk_code || "");
    setEditingRiskStatus(row.status || "Açık");
    setEditingDofId(dof?.id || null);
    setForm({
      ...EMPTY_FORM,
      company_id: String(row.company_id || ""),
      department_id: row.department_id ? String(row.department_id) : "",
      department_name: row.department_name || "",
      category_id: categoryId ? String(categoryId) : "",
      hazard_id: row.hazard_id ? String(row.hazard_id) : "",
      location: row.observation_location || "",
      summary: row.risk_definition || "",
      existing_measures: row.existing_measures || "",
      action: row.additional_measures || dof?.description || "",
      responsible_person: dof?.responsible_person || "",
      responsible_department: dof?.responsible_department || "",
      term_date: dateInputValue(dof?.term_date || row.term_date),
      probability: Number(row.probability) || 3,
      severity: Number(row.severity) || 3,
    });
    setPhotos([]);
    setVisionResults({});
    setVisionErr({});
    setSelectedPhotoTags([]);
    setGps({
      lat: row.gps_lat ?? null,
      lng: row.gps_lng ?? null,
      accuracy: row.gps_accuracy_m ?? null,
      captured_at: row.observed_at || null,
    });
    setMode("manual");
    setError("");
    setMessage(
      (row.risk_code || "Saha bulgusu") +
      " düzenleme modunda. Mevcut fotoğraflar korunur; yeni seçilen fotoğraflar kayda eklenir.",
    );
    globalThis.requestAnimationFrame?.(() => {
      document.querySelector(".field-form")?.scrollIntoView({behavior: "smooth", block: "start"});
    });
  }

  function cancelEditing() {
    resetForm();
    setMessage("Düzenleme iptal edildi.");
  }

  async function deleteRecent(row) {
    if (!row?.id || deleteBusy) return;
    if (!online) {
      setError("Kayıt silmek için internet bağlantısı gerekir.");
      return;
    }
    const confirmed = globalThis.confirm?.(
      (row.risk_code || "Bu saha bulgusu") +
      " silinsin mi? Bu işlem kaydı ve ona bağlı fotoğraf/DÖF verilerini kaldırır.",
    ) ?? true;
    if (!confirmed) return;
    setDeleteBusy(row.id);
    setError("");
    setMessage("");
    try {
      await api("/risks/" + row.id, {method: "DELETE"});
      setRecent((current) => current.filter((item) => Number(item.id) !== Number(row.id)));
      if (Number(editingRiskId) === Number(row.id)) resetForm();
      setMessage((row.risk_code || "Saha bulgusu") + " silindi.");
    } catch (ex) {
      setError(ex.message || "Saha bulgusu silinemedi.");
    } finally {
      setDeleteBusy(null);
    }
  }

  async function downloadDraftReport() {
    if (!photos.length) {
      setError("PDF raporu için önce fotoğraf ekleyin.");
      return;
    }
    if (!online) {
      setError("Fotoğraflı PDF raporu için internet bağlantısı gerekir.");
      return;
    }
    setDlBusy("draft");
    setError("");
    try {
      const formData = new FormData();
      formData.append("company_id", String(form.company_id));
      if (selectedDepartment?.name || form.department_name) formData.append("department_name", selectedDepartment?.name || form.department_name);
      if (form.location) formData.append("location", form.location);
      if (form.hazard_id) formData.append("hazard_id", String(form.hazard_id));
      if (form.summary) formData.append("summary", form.summary);
      if (form.existing_measures) formData.append("existing_measures", form.existing_measures);
      if (form.action) formData.append("action", form.action);
      if (form.responsible_person) formData.append("responsible_person", form.responsible_person);
      if (form.term_date) formData.append("term_date", form.term_date);
      formData.append("probability", String(form.probability));
      formData.append("severity", String(form.severity));
      formData.append("observed_at", new Date().toISOString());
      if (gps.lat != null) formData.append("gps_lat", String(gps.lat));
      if (gps.lng != null) formData.append("gps_lng", String(gps.lng));
      if (gps.accuracy != null) formData.append("gps_accuracy_m", String(gps.accuracy));
      formData.append("photo_meta", JSON.stringify(photos.map((photo) => ({
        id: photo.id,
        name: photo.name,
        captured_at: photo.captured_at,
        gps_lat: photo.gps_lat ?? gps.lat,
        gps_lng: photo.gps_lng ?? gps.lng,
        gps_accuracy_m: photo.gps_accuracy_m ?? gps.accuracy,
        tags: selectedPhotoTags,
      }))));
      formData.append("vision_results", JSON.stringify(photos.map((photo) => visionResults[photo.id] || null)));
      photos.forEach((photo) => {
        formData.append("files", dataUrlToFile(photo.data_url, photo.name || "saha-fotografi.jpg"), photo.name || "saha-fotografi.jpg");
      });
      await downloadFormFile(
        "/risks/field-report.pdf",
        formData,
        `saha-denetim-${selectedCompany?.id || "taslak"}.pdf`,
        {timeoutMs: 120_000},
      );
      setMessage("Fotoğraflı saha PDF raporu indirildi.");
    } catch (ex) {
      setError(ex.message || "Fotoğraflı PDF raporu oluşturulamadı.");
    } finally {
      setDlBusy(null);
    }
  }

  function renderDraftReportAction() {
    if (!photos.length) return null;
    return (
      <div className="field-photo-report-actions">
        <button
          type="button"
          className="field-photo-report-btn"
          onClick={() => void downloadDraftReport()}
          disabled={busy || dlBusy === "draft" || !online}
        >
          <Download size={16} /> {dlBusy === "draft" ? "PDF hazırlanıyor…" : "Fotoğraflı PDF raporu al"}
        </button>
        <small>Seçili fotoğraflar ve mevcut saha bilgileri rapora eklenir.</small>
      </div>
    );
  }

  async function synchronize() {
    refreshPending();
    const networkAvailable = typeof navigator === "undefined" || navigator.onLine !== false;
    if (!networkAvailable || !scope.user_id || !scope.osgb_id) return;
    setSyncBusy(true);
    try {
      const result = await flushOfflineFindings(api, uploadFile, scope);
      refreshPending();
      if (result.synced > 0) {
        setMessage(`${result.synced} saha kaydı senkronlandı; ${result.photos} fotoğraf işlendi.`);
        await loadRecent(form.company_id);
      } else if (result.failed > 0) {
        setError(result.errors?.[0]?.message || "Bekleyen saha kaydı senkronlanamadı.");
      }
    } catch (ex) {
      setError(ex.message || "Senkronizasyon başarısız.");
    } finally {
      setSyncBusy(false);
    }
  }

  useEffect(() => {
    refreshPending();
    let active = true;
    async function loadReferences() {
      setReferenceLoading(true);
      const cached = readOfflineReference(scope);
      if (cached && active) {
        setCompanies(listFrom(cached.companies));
        setCategories(listFrom(cached.categories));
        setTagCatalog(listFrom(cached.tag_catalog));
        if (!form.company_id && cached.companies?.length) {
          const preferred = cached.companies.find((row) => Number(row.id) === Number(user?.company_id));
          setForm((current) => ({
            ...current,
            company_id: preferred ? String(preferred.id) : "",
          }));
        }
      }
      try {
        const [companyResponse, categoryResponse, tagResponse] = await Promise.all([
          api("/companies"),
          api("/risks/categories"),
          api("/risks/photo-tag-catalog"),
        ]);
        if (!active) return;
        const nextCompanies = listFrom(companyResponse);
        const nextCategories = listFrom(categoryResponse);
        const nextTags = listFrom(tagResponse?.items || tagResponse);
        setCompanies(nextCompanies);
        setCategories(nextCategories);
        setTagCatalog(nextTags);
        const preferred = nextCompanies.find((row) => Number(row.id) === Number(user?.company_id));
        setForm((current) => ({
          ...current,
          company_id: current.company_id || (preferred ? String(preferred.id) : ""),
        }));
        const previous = readOfflineReference(scope) || {};
        saveOfflineReference(scope, {
          ...previous,
          companies: nextCompanies,
          categories: nextCategories,
          tag_catalog: nextTags,
        });
      } catch (ex) {
        if (!cached) setError(ex.message || "Saha referansları yüklenemedi.");
      } finally {
        if (active) setReferenceLoading(false);
      }
    }
    void loadReferences();
    return () => {
      active = false;
    };
  }, [scope.user_id, scope.osgb_id]);

  useEffect(() => {
    const companyId = Number(form.company_id);
    if (!companyId) {
      setDepartments([]);
      return;
    }
    let active = true;
    async function loadDepartments() {
      const cached = readOfflineReference(scope);
      const cachedRows = cached?.departments_by_company?.[String(companyId)];
      if (Array.isArray(cachedRows)) setDepartments(cachedRows);
      try {
        const rows = listFrom(await api(`/risks/departments?company_id=${companyId}`));
        if (!active) return;
        setDepartments(rows);
        const previous = readOfflineReference(scope) || {};
        saveOfflineReference(scope, {
          ...previous,
          departments_by_company: {
            ...(previous.departments_by_company || {}),
            [String(companyId)]: rows,
          },
        });
      } catch {
        // Cached departments let the field form continue offline.
      }
      void loadRecent(companyId);
    }
    void loadDepartments();
    return () => {
      active = false;
    };
  }, [form.company_id, scope.user_id, scope.osgb_id]);

  useEffect(() => {
    const categoryId = Number(form.category_id);
    if (!categoryId) {
      setHazards([]);
      return;
    }
    let active = true;
    function adoptHazards(rows) {
      setHazards(rows);
      if (!pendingVisionHazardCode) return;
      const match = rows.find((row) => String(row.code || "").toUpperCase() === String(pendingVisionHazardCode).toUpperCase());
      if (!match) return;
      setForm((current) => ({...current, hazard_id: String(match.id)}));
      setPendingVisionHazardCode("");
    }
    async function loadHazards() {
      const cached = readOfflineReference(scope);
      const cachedRows = cached?.hazards_by_category?.[String(categoryId)];
      if (Array.isArray(cachedRows)) adoptHazards(cachedRows);
      try {
        const rows = listFrom(await api(`/risks/hazards?category_id=${categoryId}`));
        if (!active) return;
        adoptHazards(rows);
        const previous = readOfflineReference(scope) || {};
        saveOfflineReference(scope, {
          ...previous,
          hazards_by_category: {
            ...(previous.hazards_by_category || {}),
            [String(categoryId)]: rows,
          },
        });
      } catch {
        // Cached hazards are sufficient for an offline draft.
      }
    }
    void loadHazards();
    return () => {
      active = false;
    };
  }, [form.category_id, pendingVisionHazardCode, scope.user_id, scope.osgb_id]);

  useEffect(() => {
    const onOnline = () => {
      setOnline(true);
      void synchronize();
    };
    const onOffline = () => setOnline(false);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
  }, [scope.user_id, scope.osgb_id, form.company_id, online]);

  function captureGps() {
    if (!navigator.geolocation) {
      setError("Bu cihaz konum bilgisini desteklemiyor.");
      return;
    }
    setMessage("Konum alınıyor…");
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const next = {
          lat: Number(position.coords.latitude.toFixed(7)),
          lng: Number(position.coords.longitude.toFixed(7)),
          accuracy: Number(position.coords.accuracy.toFixed(1)),
          captured_at: new Date().toISOString(),
        };
        setGps(next);
        setPhotos((current) => current.map((photo) => ({
          ...photo,
          gps_lat: next.lat,
          gps_lng: next.lng,
          gps_accuracy_m: next.accuracy,
        })));
        setMessage(`Konum alındı (±${next.accuracy} m).`);
        setError("");
      },
      (ex) => setError(ex.message || "Konum alınamadı. GPS iznini kontrol edin."),
      {enableHighAccuracy: true, timeout: 12_000, maximumAge: 60_000},
    );
  }

  async function handlePhotoSelect(event) {
    const files = Array.from(event.target.files || []).slice(0, Math.max(0, 5 - photos.length));
    event.target.value = "";
    if (!files.length) return;
    setBusy(true);
    setError("");
    try {
      const compressed = await Promise.all(files.map((file) => compressPhoto(file)));
      setPhotos((current) => [...current, ...compressed].slice(0, 5));
      setMessage(`${compressed.length} fotoğraf kanıt için hazırlandı.`);
    } catch (ex) {
      setError(ex.message || "Fotoğraf hazırlanamadı.");
    } finally {
      setBusy(false);
    }
  }

  function removePhoto(id) {
    setPhotos((current) => current.filter((photo) => photo.id !== id));
    setVisionResults((current) => { const n = {...current}; delete n[id]; return n; });
  }

  async function analyzePhotoVision(photo) {
    if (!photo) return;
    setVisionBusy(photo.id);
    setVisionErr((cur) => { const n = {...cur}; delete n[photo.id]; return n; });
    try {
      // data_url (base64) → File. Burada fetch(data_url) kullanılmaz;
      // mobilde CSP connect-src 'self' data: URL'sini engelleyebilir.
      const file = dataUrlToFile(photo.data_url, photo.name || "saha.jpg");
      const fd = new FormData();
      fd.append("file", file);
      const deptLabel = selectedDepartment?.name || form.department_name || "Saha";
      fd.append("activity", `Saha denetimi — ${String(form.location || "").trim() || deptLabel}`);
      const summary = String(form.summary || "").trim();
      if (summary && !/tespit|alinacak tedbir|alınacak tedbir|ilgili mevzuat/i.test(summary)) {
        fd.append("risk_definition", summary.slice(0, 400));
      }
      if (selectedPhotoTags.length) fd.append("photo_tags", JSON.stringify({selected: selectedPhotoTags}));
      // api.js retry/refresh karmaşıklığı uzun vision çağrısını bozuyor;
      // doğrudan fetch ile sade, tek denemelik çağrı.
      const token = getAccessToken();
      const apiRes = await fetch("/api/v1/risks/vision-analyze", {
        method: "POST",
        body: fd,
        credentials: "include",
        headers: token ? {Authorization: `Bearer ${token}`} : {},
      });
      if (!apiRes.ok) {
        const txt = await apiRes.text().catch(() => "");
        throw new Error(`HTTP ${apiRes.status}: ${txt.slice(0, 200) || apiRes.statusText}`);
      }
      const r = await apiRes.json();
      setVisionResults((cur) => ({...cur, [photo.id]: r}));
    } catch (ex) {
      let msg = ex.message || "AI analizi başarısız.";
      if (/fetch|network|timeout|Failed/i.test(msg)) {
        msg = "Sunucuya ulaşılamadı. İnternet bağlantınızı kontrol edin ve tekrar deneyin.";
      }
      setVisionErr((cur) => ({...cur, [photo.id]: msg}));
    } finally {
      setVisionBusy(null);
    }
  }

  function toggleTag(code) {
    setSelectedPhotoTags((current) => (
      current.includes(code) ? current.filter((item) => item !== code) : [...current, code]
    ));
    setPhotos((current) => current.map((photo) => ({
      ...photo,
      tags: selectedPhotoTags.includes(code)
        ? selectedPhotoTags.filter((item) => item !== code)
        : [...selectedPhotoTags, code],
    })));
  }

  function applyAnalysisToForm(analysis) {
    if (!analysis?.hazards?.length) return;
    // En yüksek şiddetli tehlikeden form alanlarını doldur
    const top = [...analysis.hazards].sort((a, b) => (b.severity || 0) - (a.severity || 0))[0];
    // Kategori eşleştir
    const matchedCat = categories.find((c) => c.name === top.category);
    const matchedHazard = hazards.find((row) => top.hazard_code && String(row.code || "").toUpperCase() === String(top.hazard_code).toUpperCase());
    setPendingVisionHazardCode(top.hazard_code || "");
    // Tutanak metni: tespit + mevzuat + tedbirler
    const lines = [];
    lines.push(`TESPİT: ${top.observed || top.note || "Saha gözlemi"}`);
    lines.push(`TEHLİKE: ${top.hazard_name || top.category}${top.detail_category ? ` [${top.detail_category}]` : ""} (şiddet ${top.severity}/5, güven %${Math.round((top.confidence || 0) * 100)})`);
    if (top.mevzuat) {
      lines.push(`İLGİLİ MEVZUAT: ${top.mevzuat.kanun || ""} ${top.mevzuat.madde || ""}`.trim());
      if (top.mevzuat.yonetmelik) lines.push(`  Yönetmelik: ${top.mevzuat.yonetmelik}`);
      if (top.mevzuat.standart) lines.push(`  Standart: ${top.mevzuat.standart}`);
      const penaltyText = formatVisionPenalty(top.mevzuat.ceza_riski);
      if (penaltyText) lines.push(`  Ceza değerlendirmesi: ${penaltyText}`);
    }
    // Alınacak tedbirler (tüm tehlikelerin DÖF önerileri)
    const tedbirler = [];
    const seenDofs = new Set();
    for (const h of analysis.hazards) {
      for (const d of (h.dof_suggestions || [])) {
        const description = String(d.description || "").trim();
        if (!description || seenDofs.has(description)) continue;
        seenDofs.add(description);
        tedbirler.push(`• ${description}`);
      }
    }
    if (tedbirler.length) lines.push(`ALINACAK TEDBİRLER:\n${tedbirler.join("\n")}`);
    if (top.termin) lines.push(`TERMİN: ${top.termin.term_days} gün (${top.termin.term_date})`);

    setForm((current) => ({
      ...current,
      summary: lines.join("\n"),
      severity: top.severity || current.severity,
      category_id: matchedCat ? String(matchedCat.id) : current.category_id,
      hazard_id: matchedHazard ? String(matchedHazard.id) : matchedCat && String(matchedCat.id) !== String(current.category_id) ? "" : current.hazard_id,
      action: tedbirler.length ? tedbirler.join("\n") : current.action,
      term_date: top.termin?.term_date || current.term_date,
    }));
    // Kategori seçildiyse tehlike listesini tetiklemek için tekrar ayarla
    if (matchedCat) {
      setTimeout(() => updateField("category_id", String(matchedCat.id)), 0);
    }
    setMode("manual");
    setMessage("AI tespitleri forma aktarıldı. Kontrol edip kaydedin.");
  }

  function resetForm() {
    setEditingRiskId(null);
    setEditingRiskCode("");
    setEditingRiskStatus("Açık");
    setEditingDofId(null);
    setForm((current) => ({
      ...EMPTY_FORM,
      company_id: current.company_id,
    }));
    setPhotos([]);
    setVisionResults({});
    setVisionErr({});
    setSelectedPhotoTags([]);
    setPendingVisionHazardCode("");
    setGps({lat: null, lng: null, accuracy: null, captured_at: null});
  }

  async function submit(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    const companyId = Number(form.company_id);
    const hazardId = Number(form.hazard_id);
    const departmentName = String(form.department_name || "").trim();
    if (!companyId) return setError("Önce işyeri seçin.");
    if (!hazardId) return setError("Tehlike seçin.");
    if (!form.department_id && !departmentName) return setError("Bölüm veya saha alanı girin.");
    if (String(form.summary || "").trim().length < 3) return setError("Uygunsuzluğu kısa ve açık yazın.");

    if (editingRiskId) {
      if (!online) return setError("Mevcut kaydı düzenlemek için internet bağlantısı gerekir.");
      const riskId = Number(editingRiskId);
      const departmentLabel = selectedDepartment?.name || departmentName || "Saha";
      const actionText = String(form.action || "").trim();
      const responsiblePerson = String(form.responsible_person || "").trim() || null;
      const responsibleDepartment = String(form.responsible_department || "").trim() || null;
      let riskSaved = false;
      let uploadedPhotos = 0;
      setBusy(true);
      try {
        const updated = await api("/risks/" + riskId, {
          method: "PATCH",
          body: JSON.stringify({
            department_id: form.department_id ? Number(form.department_id) : null,
            department_name: departmentName || null,
            hazard_id: hazardId,
            observation_location: String(form.location || "").trim() || null,
            gps_lat: gps.lat,
            gps_lng: gps.lng,
            gps_accuracy_m: gps.accuracy,
            activity: "Saha denetimi — " + (String(form.location || "").trim() || departmentLabel),
            risk_definition: String(form.summary).trim(),
            existing_measures: String(form.existing_measures || "").trim() || null,
            additional_measures: actionText || null,
            probability: Number(form.probability),
            severity: Number(form.severity),
            status: editingRiskStatus || "Açık",
            change_reason: "Saha bulguları bölümünden düzenlendi",
          }),
        });
        riskSaved = true;

        if (editingDofId && actionText) {
          await api("/risks/" + riskId + "/dofs/" + editingDofId, {
            method: "PATCH",
            body: JSON.stringify({
              description: actionText,
              responsible_person: responsiblePerson,
              responsible_department: responsibleDepartment,
              term_date: form.term_date || null,
            }),
          });
        } else if (editingDofId && !actionText) {
          await api("/risks/" + riskId + "/dofs/" + editingDofId, {method: "DELETE"});
        } else if (actionText) {
          await api("/risks/" + riskId + "/dofs", {
            method: "POST",
            body: JSON.stringify({
              description: actionText,
              responsible_person: responsiblePerson,
              responsible_department: responsibleDepartment,
              term_date: form.term_date || null,
              client_reference: "field-edit:" + riskId + ":" + Date.now(),
            }),
          });
        }

        for (const photo of photos) {
          await uploadFile("/risks/" + riskId + "/media", dataUrlToFile(photo.data_url, photo.name || "saha-fotografi.jpg"), {
            tags: JSON.stringify(selectedPhotoTags),
            description: photo.description,
            client_reference: "field-edit:" + riskId + ":" + photo.id,
            captured_at: photo.captured_at || undefined,
            gps_lat: photo.gps_lat ?? gps.lat ?? undefined,
            gps_lng: photo.gps_lng ?? gps.lng ?? undefined,
            gps_accuracy_m: photo.gps_accuracy_m ?? gps.accuracy ?? undefined,
          });
          uploadedPhotos += 1;
        }

        await loadRecent(companyId);
        resetForm();
        setMessage(
          (updated?.risk_code || editingRiskCode || "Saha bulgusu") +
          " güncellendi" +
          (uploadedPhotos ? "; " + uploadedPhotos + " yeni fotoğraf eklendi." : "."),
        );
      } catch (ex) {
        setError(
          (riskSaved ? "Bulgu güncellendi ancak ek bilgiler tamamlanamadı: " : "Bulgu güncellenemedi: ") +
          (ex.message || "Tekrar deneyin."),
        );
      } finally {
        setBusy(false);
      }
      return;
    }

    const clientReference = makeClientReference();
    const observedAt = new Date().toISOString();
    const departmentLabel = selectedDepartment?.name || departmentName || "Saha";
    const actionText = String(form.action || "").trim();
    const actionReference = actionText ? `${clientReference}:dof` : null;
    const payload = {
      company_id: companyId,
      department_id: form.department_id ? Number(form.department_id) : null,
      department_name: departmentName || null,
      hazard_id: hazardId,
      method_code: "5x5_l",
      record_origin: "field_inspection",
      client_reference: clientReference,
      observed_at: observedAt,
      observation_location: String(form.location || "").trim() || null,
      gps_lat: gps.lat,
      gps_lng: gps.lng,
      gps_accuracy_m: gps.accuracy,
      activity: `Saha denetimi — ${String(form.location || "").trim() || departmentLabel}`,
      risk_definition: String(form.summary).trim(),
      affected_people: "Çalışanlar",
      affected_group: "Çalışan",
      existing_measures: String(form.existing_measures || "").trim() || null,
      additional_measures: actionText || null,
      probability: Number(form.probability),
      severity: Number(form.severity),
      status: "Açık",
    };
    const queueItem = {
      id: `finding_${clientReference}`,
      type: "field_finding",
      user_id: scope.user_id,
      osgb_id: scope.osgb_id,
      company_id: companyId,
      payload,
      action: actionText ? {
        description: actionText,
        responsible_person: String(form.responsible_person || "").trim() || null,
        responsible_department: String(form.responsible_department || "").trim() || null,
        term_date: form.term_date || null,
        client_reference: actionReference,
      } : null,
      photos: photos.map((photo, index) => ({
        ...photo,
        tags: selectedPhotoTags,
        gps_lat: photo.gps_lat ?? gps.lat,
        gps_lng: photo.gps_lng ?? gps.lng,
        gps_accuracy_m: photo.gps_accuracy_m ?? gps.accuracy,
        client_reference: `${clientReference}:photo:${index}`,
      })),
    };

    setBusy(true);
    try {
      const queued = enqueueOfflineFinding(queueItem);
      if (!queued) throw new Error("Saha kaydı hazırlanamadı.");
      refreshPending();
      const result = online
        ? await flushOfflineFindings(api, uploadFile, scope)
        : {synced: 0, failed: 0, pending: 1, errors: []};
      refreshPending();
      if (result.synced > 0) {
        setMessage(`Saha uygunsuzluğu kaydedildi. ${result.photos} fotoğraf kanıtı bağlandı.`);
        await loadRecent(companyId);
        resetForm();
      } else {
        setMessage("Bağlantı yok: kayıt ve fotoğraflar cihazda kuyruğa alındı; bağlantı gelince gönderilecek.");
        resetForm();
      }
      if (result.failed > 0) {
        setError(result.errors?.[0]?.message || "Kayıt kuyruğa alındı; sunucuya gönderilemedi.");
      }
    } catch (ex) {
      setError(ex.message || "Saha kaydı oluşturulamadı.");
    } finally {
      setBusy(false);
    }
  }

  if (user?.role !== "safety_specialist") {
    return (
      <section className="field-inspection-page">
        <div className="field-empty">
          <ShieldAlert size={28} />
          <h2>Saha denetimi</h2>
          <p>Bu modül yalnızca iş güvenliği uzmanı rolü için açıktır.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="field-inspection-page">
      <header className="field-inspection-head">
        <div>
          <span className="eyebrow"><ClipboardCheck size={16} /> Mobil saha akışı</span>
          <h1>Saha Denetimi</h1>
          <p>Uygunsuzluğu fotoğraf, konum ve DÖF aksiyonuyla tek kayıtta yönetin.</p>
        </div>
        <button type="button" className="mini secondary field-sync-button" onClick={() => void synchronize()} disabled={syncBusy}>
          <RefreshCw size={15} className={syncBusy ? "spin" : ""} /> {syncBusy ? "Senkronlanıyor…" : "Senkronla"}
        </button>
      </header>

      <div className={online ? "field-connectivity online" : "field-connectivity offline"}>
        {online ? <Wifi size={17} /> : <WifiOff size={17} />}
        <span>{online ? "Çevrimiçi" : "Çevrimdışı"} · {pending.length ? `${pending.length} kayıt bekliyor` : "Bekleyen kayıt yok"}</span>
        {mobileSyncStatusEnabled && mobileSyncStatus && (
          <span className="field-sync-status-v1" data-sync-state={mobileSyncStatus.state} aria-live="polite">
            {mobileSyncStatus.label}
          </span>
        )}
        {pending.length > 0 && <strong>Veri cihazdaki kullanıcı/OSGB kapsamlı yerel kuyrukta tutulur; çıkışta temizlenir.</strong>}
      </div>

      {(message || error) && (
        <div className={error ? "field-alert error" : "field-alert success"} role="status">
          {error ? <AlertTriangle size={18} /> : <CheckCircle2 size={18} />}
          <span>{error || message}</span>
          <button type="button" aria-label="Mesajı kapat" onClick={() => {setError(""); setMessage("");}}><X size={16} /></button>
        </div>
      )}

      <div className="field-inspection-layout">
        {/* ===== Mod seçici ===== */}
        <div className="field-mode-picker" role="tablist">
          <button type="button" role="tab" aria-selected={mode === "ai"} className={`field-mode-card ${mode === "ai" ? "active" : ""}`} onClick={() => setMode("ai")} disabled={Boolean(editingRiskId)}>
            <ScanLine size={22} />
            <div>
              <strong>AI Destekli</strong>
              <small>Fotoğraf çek, yapay zeka tespit etsin</small>
            </div>
          </button>
          <button type="button" role="tab" aria-selected={mode === "manual"} className={`field-mode-card ${mode === "manual" ? "active" : ""}`} onClick={() => setMode("manual")} disabled={Boolean(editingRiskId)}>
            <ClipboardCheck size={22} />
            <div>
              <strong>Manuel Giriş</strong>
              <small>Tüm alanları kendin doldur</small>
            </div>
          </button>
        </div>

        <form className="field-card field-form" onSubmit={submit}>
          {editingRiskId && (
            <div className="field-edit-banner" role="status">
              <div className="field-edit-banner-copy">
                <Pencil size={18} />
                <span>
                  <strong>{editingRiskCode || "Saha bulgusu"} düzenleniyor</strong>
                  <small>Mevcut fotoğraflar korunur. Bu formda seçilen yeni fotoğraflar kayda eklenir.</small>
                </span>
              </div>
              <button type="button" className="mini secondary" onClick={cancelEditing} disabled={busy}>
                <X size={14} /> Vazgeç
              </button>
            </div>
          )}
          {/* ===== Ortak bağlam bar (her iki modda) ===== */}
          <div className="field-context-bar">
            <label className="field-control">
              <span>İşyeri <b>*</b></span>
              <select value={form.company_id} onChange={(event) => {
                updateField("company_id", event.target.value);
                updateField("department_id", "");
              }} disabled={referenceLoading || busy || Boolean(editingRiskId)}>
                <option value="">İşyeri seçin</option>
                {companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>

            <label className="field-control">
              <span>Bölüm / saha alanı</span>
              <select value={form.department_id} onChange={(event) => updateField("department_id", event.target.value)} disabled={!form.company_id || busy}>
                <option value="">Bölüm seçin</option>
                {departments.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>

            <label className="field-control">
              <span>Yeni alan adı</span>
              <input value={form.department_name} onChange={(event) => updateField("department_name", event.target.value)} placeholder="Örn. Pres hattı" disabled={Boolean(form.department_id) || busy} />
            </label>

            <label className="field-control">
              <span>Gözlem konumu</span>
              <input value={form.location} onChange={(event) => updateField("location", event.target.value)} placeholder="Örn. Üretim alanı, pres önü" maxLength={220} disabled={busy} />
            </label>

            <div className="field-gps-row">
              <button type="button" className="mini secondary" onClick={captureGps} disabled={busy}>
                <MapPinned size={15} /> {gps.lat ? "Konum güncellendi" : "Konum al"}
              </button>
              {gps.lat ? <span><MapPin size={14} /> {gps.lat}, {gps.lng} · ±{gps.accuracy} m</span> : <span>Konum isteğe bağlıdır.</span>}
            </div>
          </div>

          {/* ===== AI MODU ===== */}
          {mode === "ai" && (
            <div className="field-ai-panel">
              <div className="field-card-title">
                <div>
                  <span className="eyebrow"><ScanLine size={16} /> AI ile saha analizi</span>
                  <h2>Fotoğraf → tespit → tutanak</h2>
                </div>
                <Camera size={22} />
              </div>

              <div className="field-photo-actions" aria-label="Fotoğraf ekleme">
                <button type="button" className="field-photo-action primary" onClick={() => cameraInputRef.current?.click()} disabled={busy || photos.length >= 5} aria-label="Kamera ile fotoğraf çek">
                  <Camera size={22} />
                  <span><strong>Fotoğraf çek</strong><small>Kamerayı aç</small></span>
                </button>
                <button type="button" className="field-photo-action" onClick={() => galleryInputRef.current?.click()} disabled={busy || photos.length >= 5} aria-label="Galeriden fotoğraf seç">
                  <ImagePlus size={22} />
                  <span><strong>Galeriden seç</strong><small>En fazla {Math.max(0, 5 - photos.length)} fotoğraf</small></span>
                </button>
                <input ref={cameraInputRef} className="field-photo-input" type="file" accept="image/*" capture="environment" onChange={handlePhotoSelect} disabled={busy || photos.length >= 5} aria-label="Kamera dosyası" />
                <input ref={galleryInputRef} className="field-photo-input" type="file" accept="image/*" multiple onChange={handlePhotoSelect} disabled={busy || photos.length >= 5} aria-label="Galeri dosyası" />
              </div>

              {photos.length > 0 && (
                <div className="field-photo-grid">
                  {photos.map((photo, photoIndex) => {
                    const va = visionResults[photo.id];
                    const vErr = visionErr[photo.id];
                    const vBusy = visionBusy === photo.id;
                    return (
                      <figure key={photo.id} className={`field-photo-card${va ? " is-analyzed" : ""}${vErr ? " has-error" : ""}${vBusy ? " is-busy" : ""}`}>
                        <img src={photo.data_url} alt="Saha kanıtı önizleme" />
                        <button type="button" aria-label="Fotoğrafı kaldır" onClick={() => removePhoto(photo.id)}><X size={15} /></button>
                        <figcaption className="field-photo-caption">
                          <span className="field-photo-number">{String(photoIndex + 1).padStart(2, "0")}</span>
                          <span className="field-photo-caption-copy">
                            <strong>Fotoğraf {photoIndex + 1}</strong>
                            <small>{vBusy ? "Analiz ediliyor" : va ? "Analiz tamamlandı" : vErr ? "Analiz başarısız" : "Analiz bekliyor"}</small>
                          </span>
                          <span className={`field-photo-status ${vBusy ? "pending" : va ? "done" : vErr ? "error" : "idle"}`} aria-label={vBusy ? "Analiz ediliyor" : va ? "Analiz tamamlandı" : vErr ? "Analiz başarısız" : "Analiz bekliyor"} />
                        </figcaption>
                        <button type="button" className="field-photo-analyze-btn" onClick={() => analyzePhotoVision(photo)} disabled={vBusy} aria-label="AI ile fotoğrafı analiz et">
                          {vBusy ? <RefreshCw size={14} className="spin" /> : <ScanLine size={14} />}
                          {vBusy ? "Analiz ediliyor…" : "AI Analiz Et"}
                        </button>
                        {vErr && <div className="field-photo-analyze-err">{vErr}</div>}
                        {va && (
                          <div className="field-vision-result">
                            {/* Bbox overlay: fotoğraf üzerinde riskli bölgeler */}
                            <BboxOverlay imageSrc={photo.data_url} annotations={va.bbox_annotations || []} />
                            <div className="field-vision-summary">
                              <ScanLine size={13} />
                              <strong>{va.summary || "Analiz tamam"}</strong>
                              <span className="field-vision-provider">{visionProviderLabel(va.provider)}</span>
                            </div>

                            {/* Tutanak: mevzuata göre tespitler */}
                            <div className="field-tutanak">
                              <div className="field-tutanak-head"><FileText size={14} /> {va.protocol?.title || "SAHA İSG DENETİM VE RİSK ANALİZ TUTANAĞI"}</div>
                              {va.protocol?.disclaimer && <p className="field-vision-obs">{va.protocol.disclaimer}</p>}
                              {(va.hazards || []).map((h, hi) => (
                                <div key={hi} className="field-tutanak-item">
                                  <div className="field-vision-hazard-head">
                                    <span className={`field-vision-sev sev-${h.severity}`}>{h.severity}/5</span>
                                    <strong>{h.hazard_name || h.category}</strong>
                                    {h.detail_category && <small> · {h.detail_category}</small>}
                                    {h.hazard_code && <small> · {h.hazard_code}</small>}
                                    <span className="field-vision-conf">%{Math.round((h.confidence || 0) * 100)}</span>
                                  </div>
                                  {(h.observed || h.note) && <p className="field-vision-obs"><strong>Tespit:</strong> {h.observed || h.note}</p>}
                                  {h.mevzuat && (
                                    <div className="field-tutanak-mevzuat">
                                      <ShieldAlert size={12} /> <strong>Mevzuat:</strong> {h.mevzuat.kanun} {h.mevzuat.madde}
                                      {h.mevzuat.ceza_riski && <span> · Ceza: {formatVisionPenalty(h.mevzuat.ceza_riski)}</span>}
                                    </div>
                                  )}
                                  {h.recommended_ppe?.length > 0 && (
                                    <div className="field-vision-ppe"><span>KKD:</span> {h.recommended_ppe.join(", ")}</div>
                                  )}
                                  {h.termin && <div className="field-vision-termin">Termin: {h.termin.term_days} gün ({h.termin.term_date})</div>}
                                  {h.dof_suggestions?.length > 0 && (
                                    <div className="field-tutanak-tedbir">
                                      <strong>Alınacak tedbirler:</strong>
                                      <ul>
                                        {h.dof_suggestions.map((d, di) => (
                                          <li key={di}>{d.type === "preventive" ? "Önleyici" : "Düzeltici"}: {d.description}</li>
                                        ))}
                                      </ul>
                                    </div>
                                  )}
                                </div>
                              ))}
                              {va.protocol?.legal?.length > 0 && (
                                <div className="field-tutanak-tedbir">
                                  <strong>Mevzuat uygunluğu</strong>
                                  <ul>
                                    {va.protocol.legal.map((row, index) => (
                                      <li key={index}>{row.no}. {row.instrument}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                              {va.protocol?.risk_matrix?.length > 0 && (
                                <div className="field-tutanak-tedbir">
                                  <strong>5x5 görsel taslak</strong>
                                  <ul>
                                    {va.protocol.risk_matrix.map((row, index) => (
                                      <li key={index}>{row.hazard}: {row.probability}×{row.severity}={row.score} · {row.level}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>

                            <button type="button" className="field-ai-apply field-ai-apply-big" onClick={() => applyAnalysisToForm(va)} disabled={busy}>
                              <CheckCircle2 size={15} /> Tespitleri kayda aktar
                            </button>
                          </div>
                        )}
                      </figure>
                    );
                  })}
                </div>
              )}
              {renderDraftReportAction()}

              {photos.length === 0 && (
                <p className="field-muted field-ai-empty">Fotoğraf çekip veya galeriden seçip "AI Analiz Et" ile başlayın. Yapay zeka uygunsuzlukları fotoğraf üzerinde işaretler, mevzuata göre tespitleri tutanak haline getirir ve alınacak tedbirleri yazar.</p>
              )}

              {tagCatalog.length > 0 && photos.length > 0 && (
                <div className="field-tags">
                  <span>Fotoğraf etiketi (tüm fotoğraflara uygulanır)</span>
                  <div>
                    {tagCatalog.map((tag) => {
                      const aiSuggested = aiHint?.hazard_hint?.suggested_photo_tags?.includes(tag.code);
                      return (
                        <label key={tag.code} className={aiSuggested ? "field-ai-tag-suggest" : ""}>
                          <input type="checkbox" checked={selectedPhotoTags.includes(tag.code)} onChange={() => toggleTag(tag.code)} />
                          {tag.label}
                          {aiSuggested && <Sparkles size={11} style={{verticalAlign: 'middle', marginLeft: 4, color: '#7c3aed'}} />}
                        </label>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ===== MANUEL MODU ===== */}
          {mode === "manual" && (
            <>
          <div className="field-card-title">
            <div>
              <span className="eyebrow">1 · Tehlike seçimi</span>
              <h2>Kategori ve tehlike</h2>
            </div>
            <Camera size={22} />
          </div>

          <div className="field-two-col">
            <label className="field-control">
              <span>Tehlike kategorisi <b>*</b></span>
              <select value={form.category_id} onChange={(event) => {
                updateField("category_id", event.target.value);
                updateField("hazard_id", "");
                setPendingVisionHazardCode("");
              }} disabled={busy}>
                <option value="">Kategori seçin</option>
                {categories.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
              </select>
            </label>
            <label className="field-control">
              <span>Tehlike <b>*</b></span>
              <select value={form.hazard_id} onChange={(event) => updateField("hazard_id", event.target.value)} disabled={!form.category_id || busy}>
                <option value="">Tehlike seçin</option>
                {hazards.map((row) => <option key={row.id} value={row.id}>{row.code} · {row.name}</option>)}
              </select>
            </label>
          </div>

          <div className="field-card-title compact">
            <div>
              <span className="eyebrow">2 · Bulguyu kaydet</span>
              <h2>{editingRiskId ? "Bulgu düzenleme" : "Risk / uygunsuzluk"}</h2>
            </div>
            <ShieldAlert size={22} />
          </div>

          <label className="field-control">
            <span>Uygunsuzluk / risk tanımı <b>*</b></span>
            <textarea value={form.summary} onChange={(event) => updateField("summary", event.target.value)} placeholder="Ne gördünüz, hangi çalışanı veya süreci etkiliyor?" rows={4} maxLength={2000} disabled={busy} />
          </label>

          {(aiBusy || aiHint) && (
            <div className="field-ai-suggest" role="status" aria-live="polite">
              {aiBusy && !aiHint && (
                <div className="field-ai-suggest-head">
                  <Sparkles size={15} className="field-ai-spin" />
                  <span>AI öneri hazırlanıyor…</span>
                </div>
              )}
              {aiHint && (
                <>
                  <div className="field-ai-suggest-head">
                    <Sparkles size={15} style={{color: "#7c3aed"}} />
                    <strong>AI Önerisi</strong>
                    {aiHint.hazard_hint?.matched && (
                      <span className="field-ai-chip">
                        {aiHint.hazard_hint.suggested_category} · {Math.round((aiHint.hazard_hint.confidence || 0) * 100)}%
                      </span>
                    )}
                  </div>
                  {aiHint.hazard_hint?.matched && (
                    <div className="field-ai-suggest-body">
                      {aiHint.risk_suggestion && (
                        <div className="field-ai-suggest-scores">
                          <span>O={aiHint.risk_suggestion.probability_hint}</span>
                          <span>Ş={aiHint.risk_suggestion.severity_hint}</span>
                          <span className="field-ai-suggest-score">{(aiHint.risk_suggestion.probability_hint || 0) * (aiHint.risk_suggestion.severity_hint || 0)}</span>
                        </div>
                      )}
                      {aiHint.hazard_hint.suggested_photo_tags?.length > 0 && (
                        <div className="field-ai-tags">
                          {aiHint.hazard_hint.suggested_photo_tags.map((t) => (
                            <span key={t} className="field-ai-tag">{t}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                  <button type="button" className="field-ai-apply" onClick={applyAiHint} disabled={busy}>
                    <Lightbulb size={14} /> Öneriyi forma uygula
                  </button>
                </>
              )}
            </div>
          )}

          <label className="field-control">
            <span>Mevcut önlemler</span>
            <textarea value={form.existing_measures} onChange={(event) => updateField("existing_measures", event.target.value)} placeholder="Varsa mevcut kontrol / bariyer" rows={2} maxLength={2000} disabled={busy} />
          </label>

          <div className="field-card-title compact">
            <div>
              <span className="eyebrow">3 · Risk skoru</span>
              <h2>5 × 5 değerlendirme</h2>
            </div>
            <span className="field-score-preview">{Number(form.probability) * Number(form.severity)}</span>
          </div>
          <div className="field-score-grid">
            {[
              ["probability", "Olasılık"],
              ["severity", "Şiddet"],
            ].map(([key, label]) => (
              <label className="field-control" key={key}>
                <span>{label}</span>
                <select value={form[key]} onChange={(event) => updateField(key, Number(event.target.value))} disabled={busy}>
                  {[1, 2, 3, 4, 5].map((value) => <option key={value} value={value}>{value} · {value === 1 ? "Düşük" : value === 5 ? "Çok yüksek" : "Orta"}</option>)}
                </select>
              </label>
            ))}
          </div>

          <div className="field-card-title compact">
            <div>
              <span className="eyebrow">4 · DÖF / aksiyon</span>
              <h2>Düzeltici faaliyet</h2>
            </div>
            <ClipboardCheck size={22} />
          </div>
          <label className="field-control">
            <span>Aksiyon açıklaması</span>
            <textarea value={form.action} onChange={(event) => updateField("action", event.target.value)} placeholder="Kapatmak için yapılması gereken iş" rows={3} maxLength={2000} disabled={busy} />
          </label>
          <div className="field-two-col">
            <label className="field-control">
              <span>Sorumlu kişi</span>
              <input value={form.responsible_person} onChange={(event) => updateField("responsible_person", event.target.value)} placeholder="Ad soyad" maxLength={150} disabled={busy} />
            </label>
            <label className="field-control">
              <span>Termin tarihi</span>
              <input type="date" value={form.term_date} onChange={(event) => updateField("term_date", event.target.value)} disabled={busy} />
            </label>
          </div>

          <div className="field-card-title compact">
            <div>
              <span className="eyebrow">5 · Fotoğraf kanıtı</span>
              <h2>{photos.length}/5 fotoğraf</h2>
            </div>
            <ImagePlus size={22} />
          </div>
          <div className="field-photo-actions" aria-label="Fotoğraf kanıtı ekleme">
            <button
              type="button"
              className="field-photo-action primary"
              onClick={() => cameraInputRef.current?.click()}
              disabled={busy || photos.length >= 5}
              aria-label="Kamera ile fotoğraf çek"
            >
              <Camera size={22} />
              <span><strong>Fotoğraf çek</strong><small>Kamerayı aç</small></span>
            </button>
            <button
              type="button"
              className="field-photo-action"
              onClick={() => galleryInputRef.current?.click()}
              disabled={busy || photos.length >= 5}
              aria-label="Galeriden fotoğraf seç"
            >
              <ImagePlus size={22} />
              <span><strong>Galeriden seç</strong><small>En fazla {Math.max(0, 5 - photos.length)} fotoğraf</small></span>
            </button>
            <input
              ref={cameraInputRef}
              className="field-photo-input"
              type="file"
              accept="image/*"
              capture="environment"
              onChange={handlePhotoSelect}
              disabled={busy || photos.length >= 5}
              aria-label="Kamera dosyası"
            />
            <input
              ref={galleryInputRef}
              className="field-photo-input"
              type="file"
              accept="image/*"
              multiple
              onChange={handlePhotoSelect}
              disabled={busy || photos.length >= 5}
              aria-label="Galeri dosyası"
            />
          </div>
          {photos.length > 0 && (
            <div className="field-photo-grid">
              {photos.map((photo, photoIndex) => {
                const va = visionResults[photo.id];
                const vErr = visionErr[photo.id];
                const vBusy = visionBusy === photo.id;
                return (
                  <figure key={photo.id} className={`field-photo-card${va ? " is-analyzed" : ""}${vErr ? " has-error" : ""}${vBusy ? " is-busy" : ""}`}>
                    <img src={photo.data_url} alt="Saha kanıtı önizleme" />
                    <button type="button" aria-label="Fotoğrafı kaldır" onClick={() => removePhoto(photo.id)}><X size={15} /></button>
                    <figcaption className="field-photo-caption">
                      <span className="field-photo-number">{String(photoIndex + 1).padStart(2, "0")}</span>
                      <span className="field-photo-caption-copy">
                        <strong>Fotoğraf {photoIndex + 1}</strong>
                        <small>{vBusy ? "Analiz ediliyor" : va ? "Analiz tamamlandı" : vErr ? "Analiz başarısız" : "Analiz bekliyor"}</small>
                      </span>
                      <span className={`field-photo-status ${vBusy ? "pending" : va ? "done" : vErr ? "error" : "idle"}`} aria-label={vBusy ? "Analiz ediliyor" : va ? "Analiz tamamlandı" : vErr ? "Analiz başarısız" : "Analiz bekliyor"} />
                    </figcaption>
                    <button
                      type="button"
                      className="field-photo-analyze-btn"
                      onClick={() => analyzePhotoVision(photo)}
                      disabled={vBusy}
                      aria-label="AI ile fotoğrafı analiz et"
                    >
                      {vBusy ? <RefreshCw size={14} className="spin" /> : <ScanLine size={14} />}
                      {vBusy ? "Analiz…" : "AI Analiz Et"}
                    </button>
                    {vErr && <div className="field-photo-analyze-err">{vErr}</div>}
                    {va && (
                      <div className="field-vision-result">
                        <div className="field-vision-summary">
                          <ScanLine size={13} />
                          <strong>{va.summary || "Analiz tamam"}</strong>
                          <span className="field-vision-provider">
                            {visionProviderLabel(va.provider)}
                          </span>
                        </div>
                        {(va.hazards || []).map((h, hi) => (
                          <div key={hi} className="field-vision-hazard">
                            <div className="field-vision-hazard-head">
                              <span className={`field-vision-sev sev-${h.severity}`}>{h.severity}/5</span>
                              <strong>{h.hazard_name || h.category}</strong>
                              {h.detail_category && <small> · {h.detail_category}</small>}
                              {h.hazard_code && <small> · {h.hazard_code}</small>}
                              <span className="field-vision-conf">%{Math.round((h.confidence || 0) * 100)}</span>
                            </div>
                            {(h.observed || h.note) && <p className="field-vision-obs">{h.observed || h.note}</p>}
                            {h.recommended_ppe?.length > 0 && (
                              <div className="field-vision-ppe">
                                <span>KKD:</span> {h.recommended_ppe.join(", ")}
                              </div>
                            )}
                            {h.mevzuat && (
                              <div className="field-vision-mevzuat">
                                <ShieldAlert size={12} /> {h.mevzuat.kanun} {h.mevzuat.madde}
                                {h.mevzuat.ceza_riski && (
                                  <span> · Ceza: {formatVisionPenalty(h.mevzuat.ceza_riski)}</span>
                                )}
                              </div>
                            )}
                            {h.termin && (
                              <div className="field-vision-termin">
                                Termin: {h.termin.term_days} gün ({h.termin.term_date})
                              </div>
                            )}
                            {h.dof_suggestions?.length > 0 && (
                              <details className="field-vision-dofs">
                                <summary>{h.dof_suggestions.length} DÖF önerisi</summary>
                                <ul>
                                  {h.dof_suggestions.map((d, di) => (
                                    <li key={di}>{d.type === "preventive" ? "Önleyici" : "Düzeltici"}: {d.description}</li>
                                  ))}
                                </ul>
                              </details>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </figure>
                );
              })}
            </div>
          )}
          {renderDraftReportAction()}

          {tagCatalog.length > 0 && photos.length > 0 && (
            <div className="field-tags">
              <span>Fotoğraf etiketi (tüm fotoğraflara uygulanır)</span>
              <div>
                {tagCatalog.map((tag) => {
                  const aiSuggested = aiHint?.hazard_hint?.suggested_photo_tags?.includes(tag.code);
                  return (
                    <label key={tag.code} className={aiSuggested ? "field-ai-tag-suggest" : ""}>
                      <input type="checkbox" checked={selectedPhotoTags.includes(tag.code)} onChange={() => toggleTag(tag.code)} />
                      {tag.label}
                      {aiSuggested && <Sparkles size={11} style={{verticalAlign: 'middle', marginLeft: 4, color: '#7c3aed'}} />}
                    </label>
                  );
                })}
              </div>
            </div>
          )}

          <button type="submit" className="field-submit" disabled={busy || referenceLoading}>
            <Save size={18} /> {busy ? (editingRiskId ? "Güncelleniyor…" : "Hazırlanıyor…") : editingRiskId ? "Değişiklikleri kaydet" : online ? "Kaydet ve senkronla" : "Çevrimdışı kuyruğa al"}
          </button>
          <p className="field-legal-note">Kayıt; saha gözlemi, risk puanı, fotoğraf kanıtı ve varsa DÖF aksiyonunu tek zincirde tutar. Resmî bildirim entegrasyonu bu akışın parçası değildir.</p>
            </>
          )}
        </form>

        <aside className="field-side">
          <div className="field-card field-queue-card">
            <div className="field-card-title compact">
              <div>
                <span className="eyebrow">Cihaz kuyruğu</span>
                <h2>Bekleyen kayıtlar</h2>
              </div>
              <Clock3 size={21} />
            </div>
            {pending.length ? pending.map((row) => (
              <div className="field-queue-item" key={row.id}>
                <strong>{row.payload?.risk_definition || "Saha kaydı"}</strong>
                <small>{formatDate(row.created_at)} · {row.photos?.length || 0} fotoğraf</small>
                {row.last_error && <em>{row.last_error}</em>}
              </div>
            )) : <p className="field-muted">Bekleyen kayıt yok. Kayıtlar bağlantı yokken burada korunur.</p>}
          </div>

          <div className="field-card field-recent-card">
            <div className="field-card-title compact">
              <div>
                <span className="eyebrow">Sunucu kayıtları</span>
                <h2>Son saha bulguları</h2>
              </div>
              <RefreshCw size={21} />
            </div>
            {recent.length ? recent.slice(0, 10).map((row) => (
              <article className="field-recent-item" key={row.id}>
                <div className="field-recent-top">
                  <strong>{row.risk_code}</strong>
                  <span className={`field-risk-badge ${riskClass(row.risk_level)}`}>{row.risk_level}</span>
                </div>
                <p>{row.risk_definition}</p>
                <div className="field-recent-meta">
                  <small>{row.department_name || "Saha"} · {row.media?.length || 0} fotoğraf · {row.dofs?.length || 0} DÖF</small>
                  <div className="field-recent-actions">
                    <button type="button" className="mini secondary" onClick={() => beginEditing(row)} disabled={busy || Boolean(deleteBusy)}>
                      <Pencil size={13} /> Düzenle
                    </button>
                    <button type="button" className="mini field-recent-delete" onClick={() => void deleteRecent(row)} disabled={busy || deleteBusy === row.id}>
                      <Trash2 size={13} /> {deleteBusy === row.id ? "Siliniyor…" : "Sil"}
                    </button>
                    <button type="button" className="mini secondary" onClick={() => void downloadReport(row)} disabled={dlBusy === row.id || Boolean(deleteBusy)}>
                      <Download size={13} /> {dlBusy === row.id ? "…" : "PDF rapor"}
                    </button>
                  </div>
                </div>
              </article>
            )) : <p className="field-muted">Bu işyeri için henüz saha bulgusu yok.</p>}
          </div>

          <div className="field-card field-help-card">
            <strong><CheckCircle2 size={18} /> Saha kullanım notu</strong>
            <p>İnternete bağlıyken ekranı bir kez açıp işyeri, bölüm ve tehlike kütüphanesini yükleyin. Sonrasında bağlantı kesilse bile yeni kayıt ve fotoğraflar cihaz kuyruğuna alınır.</p>
          </div>
        </aside>
      </div>
    </section>
  );
}

export function FieldInspectionPage({user}) {
  const [view, setView] = useState("visual");
  if (user?.role !== "safety_specialist") return <LegacyFieldInspectionPage user={user} />;
  return (
    <>
      <nav className="field-inspection-mode-tabs" aria-label="Saha denetimi görünümü">
        <button type="button" className={view === "visual" ? "is-active" : ""} onClick={() => setView("visual")}>Görsel denetim</button>
        <button type="button" className={view === "legacy" ? "is-active" : ""} onClick={() => setView("legacy")}>Hızlı bulgu (mevcut)</button>
      </nav>
      {view === "visual" ? <VisualFieldInspectionPage user={user} /> : <LegacyFieldInspectionPage user={user} />}
    </>
  );
}

export default FieldInspectionPage;
