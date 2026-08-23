import React, {useEffect, useMemo, useRef, useState} from "react";
import {
  AlertTriangle,
  Camera,
  CheckCircle2,
  ClipboardCheck,
  Clock3,
  ImagePlus,
  MapPin,
  MapPinned,
  RefreshCw,
  Save,
  ShieldAlert,
  Wifi,
  WifiOff,
  X,
} from "lucide-react";
import {api, uploadFile} from "./api";
import {
  enqueueOfflineFinding,
  flushOfflineFindings,
  listOfflineFindings,
  readOfflineReference,
  saveOfflineReference,
} from "./field_inspection_offline";
import {buildMobileSyncStatus, isMobileSyncStatusEnabled} from "./mobile_sync_status";
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

export function FieldInspectionPage({user}) {
  const scope = useMemo(() => scopeFor(user), [user?.id, user?.osgb_id]);
  const [companies, setCompanies] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [categories, setCategories] = useState([]);
  const [hazards, setHazards] = useState([]);
  const [tagCatalog, setTagCatalog] = useState([]);
  const [recent, setRecent] = useState([]);
  const [form, setForm] = useState(EMPTY_FORM);
  const [photos, setPhotos] = useState([]);
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
            company_id: String(preferred?.id || cached.companies[0].id),
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
          company_id: current.company_id || String(preferred?.id || nextCompanies[0]?.id || ""),
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
    async function loadHazards() {
      const cached = readOfflineReference(scope);
      const cachedRows = cached?.hazards_by_category?.[String(categoryId)];
      if (Array.isArray(cachedRows)) setHazards(cachedRows);
      try {
        const rows = listFrom(await api(`/risks/hazards?category_id=${categoryId}`));
        if (!active) return;
        setHazards(rows);
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
  }, [form.category_id, scope.user_id, scope.osgb_id]);

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

  function resetForm() {
    setForm((current) => ({
      ...EMPTY_FORM,
      company_id: current.company_id,
    }));
    setPhotos([]);
    setSelectedPhotoTags([]);
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
        <form className="field-card field-form" onSubmit={submit}>
          <div className="field-card-title">
            <div>
              <span className="eyebrow">1 · Kayıt bağlamı</span>
              <h2>İşyeri ve tehlike</h2>
            </div>
            <Camera size={22} />
          </div>

          <label className="field-control">
            <span>İşyeri <b>*</b></span>
            <select value={form.company_id} onChange={(event) => {
              updateField("company_id", event.target.value);
              updateField("department_id", "");
            }} disabled={referenceLoading || busy}>
              <option value="">İşyeri seçin</option>
              {companies.map((row) => <option key={row.id} value={row.id}>{row.name}</option>)}
            </select>
          </label>

          <div className="field-two-col">
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
          </div>

          <div className="field-two-col">
            <label className="field-control">
              <span>Tehlike kategorisi <b>*</b></span>
              <select value={form.category_id} onChange={(event) => {
                updateField("category_id", event.target.value);
                updateField("hazard_id", "");
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

          <div className="field-card-title compact">
            <div>
              <span className="eyebrow">2 · Bulguyu kaydet</span>
              <h2>Risk / uygunsuzluk</h2>
            </div>
            <ShieldAlert size={22} />
          </div>

          <label className="field-control">
            <span>Uygunsuzluk / risk tanımı <b>*</b></span>
            <textarea value={form.summary} onChange={(event) => updateField("summary", event.target.value)} placeholder="Ne gördünüz, hangi çalışanı veya süreci etkiliyor?" rows={4} maxLength={2000} disabled={busy} />
          </label>

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
              {photos.map((photo) => (
                <figure key={photo.id}>
                  <img src={photo.data_url} alt="Saha kanıtı önizleme" />
                  <button type="button" aria-label="Fotoğrafı kaldır" onClick={() => removePhoto(photo.id)}><X size={15} /></button>
                </figure>
              ))}
            </div>
          )}

          {tagCatalog.length > 0 && photos.length > 0 && (
            <div className="field-tags">
              <span>Fotoğraf etiketi (tüm fotoğraflara uygulanır)</span>
              <div>
                {tagCatalog.map((tag) => (
                  <label key={tag.code}>
                    <input type="checkbox" checked={selectedPhotoTags.includes(tag.code)} onChange={() => toggleTag(tag.code)} />
                    {tag.label}
                  </label>
                ))}
              </div>
            </div>
          )}

          <button type="submit" className="field-submit" disabled={busy || referenceLoading}>
            <Save size={18} /> {busy ? "Hazırlanıyor…" : online ? "Kaydet ve senkronla" : "Çevrimdışı kuyruğa al"}
          </button>
          <p className="field-legal-note">Kayıt; saha gözlemi, risk puanı, fotoğraf kanıtı ve varsa DÖF aksiyonunu tek zincirde tutar. Resmî bildirim entegrasyonu bu akışın parçası değildir.</p>
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
                <small>{row.department_name || "Saha"} · {row.media?.length || 0} fotoğraf · {row.dofs?.length || 0} DÖF</small>
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

export default FieldInspectionPage;
