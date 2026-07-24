import { canAttemptTokenRefresh, refreshCookieMode, setRefreshCookieMode } from "./auth_session.js";

export { setRefreshCookieMode } from "./auth_session.js";

const isLocalHost =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

const API_URL =
  import.meta.env.VITE_API_URL ||
  (isLocalHost
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : "https://isg-suite-api-1u9t.onrender.com/api/v1");

const API_ROOT = API_URL.replace(/\/api\/v1\/?$/, "");

/** P1-01: HttpOnly refresh cookie için credentials; flag kapalıyken zararsız. */
const FETCH_CREDENTIALS = "include";

let _refreshInFlight = null;

async function tryRefreshAccessToken() {
  if (!refreshCookieMode()) return false;
  if (!_refreshInFlight) {
    _refreshInFlight = (async () => {
      const response = await fetch(`${API_URL}/auth/refresh`, {
        method: "POST",
        credentials: FETCH_CREDENTIALS,
        mode: "cors",
        cache: "no-store",
      });
      if (!response.ok) {
        setRefreshCookieMode(false);
        return false;
      }
      const body = await response.json().catch(() => ({}));
      if (body?.access_token) {
        localStorage.setItem("isg_token", body.access_token);
        return true;
      }
      return false;
    })().finally(() => {
      _refreshInFlight = null;
    });
  }
  return _refreshInFlight;
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isNetworkError(e) {
  // HTTP cevapları (4xx/5xx) asla "API uyanıyor" sanılmasın
  if (e?.httpStatus != null) return false;
  const msg = String(e?.message || e || "").toLowerCase();
  return e instanceof TypeError || msg.includes("failed to fetch") || msg.includes("networkerror") || msg.includes("load failed");
}

/** Render cold-start: kimlik doğrulamasız /health ile API'yi uyandır. */
export async function wakeApi() {
  try {
    await fetch(`${API_ROOT}/health`, {
      method: "GET",
      cache: "no-store",
      mode: "cors",
      credentials: FETCH_CREDENTIALS,
    });
  } catch (_) {
    /* ignore */
  }
}

const FIELD_LABELS_TR = {
  detail: 'Detay',
  short_summary: 'Kısa özet',
  location: 'Olay yeri',
  classification: 'Sınıflandırma',
  event_date: 'Olay tarihi',
  event_type: 'Olay tipi',
  company_id: 'Firma',
  branch_id: 'Şube',
  email: 'E-posta',
  password: 'Şifre',
  full_name: 'Ad soyad',
  name: 'Ad',
  phone: 'Telefon',
  title: 'Başlık',
  description: 'Açıklama',
  visit_date: 'Ziyaret tarihi',
  subject: 'Konu',
  notes: 'Notlar',
  safety_specialist: 'İSG uzmanı',
  workplace_physician: 'İşyeri hekimi',
  employer_representative: 'İşveren / vekili',
  recorded_by_name: 'Kaydeden',
  witness_names: 'Şahit isimleri',
  probability: 'Olasılık',
  severity: 'Şiddet',
  start_date: 'Başlangıç tarihi',
  end_date: 'Bitiş tarihi',
  valid_from: 'Geçerlilik başlangıcı',
  valid_until: 'Geçerlilik bitişi',
};

function fieldLabelTr(field) {
  if (!field) return '';
  return FIELD_LABELS_TR[field] || field;
}

function localizeValidationMsg(rawMsg) {
  let msg = String(rawMsg || '').trim();
  if (!msg) return 'Geçersiz değer';
  // Pydantic bazen "Value error, ..." öneki koyar
  if (/^value error[,:]?\s*/i.test(msg)) msg = msg.replace(/^value error[,:]?\s*/i, '');
  const low = msg.toLowerCase();

  let m = low.match(/at least (\d+) characters?/);
  if (m) return `en az ${m[1]} karakter olmalıdır`;
  m = low.match(/at most (\d+) characters?/);
  if (m) return `en fazla ${m[1]} karakter olabilir`;
  m = low.match(/should have at least (\d+)/);
  if (m) return `en az ${m[1]} karakter olmalıdır`;
  m = low.match(/ensure this value has at least (\d+)/);
  if (m) return `en az ${m[1]} karakter olmalıdır`;

  if (low.includes('field required') || low === 'missing' || low.includes('field required')) {
    return 'bu alan zorunludur';
  }
  if (low.includes('input should be a valid integer') || low.includes('not a valid integer')) {
    return 'geçerli bir sayı giriniz';
  }
  if (low.includes('input should be a valid number') || low.includes('not a valid float')) {
    return 'geçerli bir sayı giriniz';
  }
  if (low.includes('input should be a valid date') || low.includes('invalid date')) {
    return 'geçerli bir tarih giriniz (YYYY-AA-GG)';
  }
  if (low.includes('input should be a valid datetime')) {
    return 'geçerli bir tarih/saat giriniz';
  }
  if (low.includes('input should be a valid email') || low.includes('value is not a valid email')) {
    return 'geçerli bir e-posta adresi giriniz';
  }
  if (low.includes('input should be a valid boolean')) {
    return 'geçerli bir evet/hayır değeri giriniz';
  }
  if (low.includes('string does not match') || low.includes('string should match')) {
    return 'girilen biçim geçersiz';
  }
  if (low.includes('none is not an allowed') || low.includes('input should be a valid string')) {
    return 'bu alan boş bırakılamaz';
  }
  // İngilizce kalmış genel "String should..." kalıpları
  if (low.startsWith('string should ')) {
    return msg.replace(/^String should /i, 'Metin ').replace(/^string should /i, 'Metin ');
  }
  return msg;
}

async function parseError(response) {
  const data = await response.json().catch(() => ({}));
  const detail = data.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        if (typeof d === "string") return localizeValidationMsg(d);
        const loc = (d.loc || []).filter((x) => x !== "body" && x !== "query" && x !== "path");
        const field = loc.length ? String(loc[loc.length - 1]) : "";
        const msg = localizeValidationMsg(d.msg || JSON.stringify(d));
        const label = fieldLabelTr(field);
        return label ? `${label}: ${msg}` : msg;
      })
      .join(" · ");
  }
  return detail ? String(detail) : `İşlem tamamlanamadı (HTTP ${response.status}).`;
}

/**
 * EİSA hata panosuna istemci raporu — döngüye girmemek için fetch kullanır (api() değil).
 */
const _reportRecent = new Set();

export function reportClientError(payload = {}) {
  try {
    const token = localStorage.getItem("isg_token");
    if (!token) return;
    const httpPath = String(payload.http_path || "").slice(0, 500);
    if (httpPath.includes("/error-reports")) return;

    const title = String(payload.title || "İstemci hatası").slice(0, 220);
    const message = String(payload.message || "").slice(0, 4000);
    const key = `${payload.source || ""}|${httpPath}|${title}|${message}`.slice(0, 240);
    if (_reportRecent.has(key)) return;
    _reportRecent.add(key);
    setTimeout(() => _reportRecent.delete(key), 30000);

    const body = {
      source: payload.source || "api_error",
      title,
      message: message || null,
      stack_trace: payload.stack_trace ? String(payload.stack_trace).slice(0, 8000) : null,
      user_note: payload.user_note ? String(payload.user_note).slice(0, 2000) : null,
      page_path: payload.page_path
        ? String(payload.page_path).slice(0, 500)
        : (typeof window !== "undefined" ? window.location.pathname.slice(0, 500) : null),
      http_method: payload.http_method ? String(payload.http_method).slice(0, 16) : null,
      http_path: httpPath || null,
      http_status: payload.http_status != null ? Number(payload.http_status) : null,
      company_id: payload.company_id != null ? Number(payload.company_id) : null,
    };

    void fetch(`${API_URL}/eisa/error-reports`, {
      method: "POST",
      mode: "cors",
      credentials: FETCH_CREDENTIALS,
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    }).catch(() => {});
  } catch (_) {
    /* ignore */
  }
}

/** Geçici / MFA token ile çağrı (localStorage isg_token kullanmaz). */
export async function apiWithBearer(bearerToken, path, options = {}) {
  const retries = options._retries ?? 2;
  const { _retries, headers: optHeaders, ...fetchOpts } = options;
  const method = (fetchOpts.method || "GET").toUpperCase();
  const headers = {
    ...(optHeaders || {}),
    Authorization: `Bearer ${bearerToken}`,
  };
  if (method !== "GET" && method !== "HEAD" && fetchOpts.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let lastErr;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      if (attempt > 0) {
        await wakeApi();
        await sleep(1200 * attempt);
      }
      const response = await fetch(`${API_URL}${path}`, {
        ...fetchOpts,
        headers,
        mode: "cors",
        credentials: FETCH_CREDENTIALS,
      });
      if (!response.ok) {
        const err = new Error(await parseError(response));
        err.httpStatus = response.status;
        throw err;
      }
      if (response.status === 204) return null;
      const text = await response.text();
      if (!text) return null;
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    } catch (e) {
      lastErr = e;
      if (!isNetworkError(e) || attempt === retries) {
        if (isNetworkError(e)) {
          throw new Error(
            "Sunucuya bağlanılamadı. API uyanıyor olabilir — 10–20 sn bekleyip tekrar deneyin.",
          );
        }
        throw e;
      }
    }
  }
  throw lastErr;
}

/**
 * API çağrısı — ağ kopmasında API uyandırıp birkaç kez dener.
 * options._retries ile deneme sayısı (varsayılan 2 ek deneme).
 * P1-01: refresh cookie modunda 401 → bir kez /auth/refresh.
 */
export async function api(path, options = {}) {
  const retries = options._retries ?? 2;
  const { _retries, _didRefresh, headers: optHeaders, ...fetchOpts } = options;
  const token = localStorage.getItem("isg_token");
  const method = (fetchOpts.method || "GET").toUpperCase();
  const headers = {...(optHeaders || {})};
  if (token) headers.Authorization = `Bearer ${token}`;
  // GET'te Content-Type gönderme (gereksiz preflight / proxy sorunlarını azaltır)
  if (method !== "GET" && method !== "HEAD" && fetchOpts.body != null && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let lastErr;
  let lastStatus = null;
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      if (attempt > 0) {
        await wakeApi();
        await sleep(1200 * attempt);
      }
      const response = await fetch(`${API_URL}${path}`, {
        ...fetchOpts,
        headers,
        mode: "cors",
        credentials: FETCH_CREDENTIALS,
      });
      if (!response.ok) {
        lastStatus = response.status;
        if (!_didRefresh && canAttemptTokenRefresh(path, response.status)) {
          const ok = await tryRefreshAccessToken();
          if (ok) {
            return api(path, {...options, _didRefresh: true, _retries: 0});
          }
        }
        const err = new Error(await parseError(response));
        err.httpStatus = response.status;
        err.httpPath = path;
        err.httpMethod = method;
        throw err;
      }
      if (response.status === 204) return null;
      const text = await response.text();
      if (!text) return null;
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    } catch (e) {
      lastErr = e;
      if (!isNetworkError(e) || attempt === retries) {
        if (isNetworkError(e)) {
          reportClientError({
            source: "api_error",
            title: "Ağ bağlantı hatası",
            message: String(e?.message || e),
            http_method: method,
            http_path: path,
          });
          throw new Error(
            "Sunucuya bağlanılamadı. API uyanıyor olabilir — 10–20 sn bekleyip Yenile’ye basın.",
          );
        }
        const status = e?.httpStatus ?? lastStatus;
        if (status >= 500) {
          reportClientError({
            source: "api_error",
            title: `API hatası HTTP ${status}`,
            message: String(e?.message || e),
            http_method: method,
            http_path: path,
            http_status: status,
          });
        }
        throw e;
      }
    }
  }
  throw lastErr;
}

/** Auth header ile blob URL üretir (önizleme görselleri için). */
export async function authBlobUrl(path) {
  await wakeApi();
  const token = localStorage.getItem("isg_token");
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? {Authorization: `Bearer ${token}`} : {},
    mode: "cors",
    credentials: FETCH_CREDENTIALS,
  });
  if (!response.ok) {
    throw new Error(`Dosya alınamadı (HTTP ${response.status}).`);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function downloadFile(path, filename) {
  await wakeApi();
  const token = localStorage.getItem("isg_token");
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: token ? {Authorization: `Bearer ${token}`} : {},
      mode: "cors",
      credentials: FETCH_CREDENTIALS,
    });
  } catch (e) {
    if (isNetworkError(e)) {
      throw new Error("Sunucuya bağlanılamadı. Birkaç saniye bekleyip tekrar deneyin.");
    }
    throw e;
  }
  if (!response.ok) {
    throw new Error(await parseError(response));
  }
  const blob = await response.blob();
  if (!blob || blob.size < 1) {
    throw new Error("Dosya boş veya bozuk geldi. Kayıt ve API sürümünü kontrol edin.");
  }
  const type = (response.headers.get("content-type") || blob.type || "").toLowerCase();
  const okType =
    !type ||
    type.includes("pdf") ||
    type.includes("octet-stream") ||
    type.includes("image/") ||
    type.includes("jpeg") ||
    type.includes("png") ||
    type.includes("spreadsheet") ||
    type.includes("excel") ||
    type.includes("ms-excel") ||
    type.includes("zip") ||
    type.includes("text/plain") ||
    type.includes("text/");
  if (!okType) {
    throw new Error("Sunucu beklenen dosya türü yerine başka içerik döndürdü. API sürümünü kontrol edin.");
  }
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function uploadFile(path, file, extraFields = null) {
  await wakeApi();
  const token = localStorage.getItem("isg_token");
  const formData = new FormData();
  formData.append("file", file);
  if (extraFields && typeof extraFields === "object") {
    for (const [k, v] of Object.entries(extraFields)) {
      if (v === undefined || v === null || v === "") continue;
      formData.append(k, String(v));
    }
  }
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: token ? {Authorization: `Bearer ${token}`} : {},
      body: formData,
      mode: "cors",
      credentials: FETCH_CREDENTIALS,
    });
  } catch (e) {
    if (isNetworkError(e)) {
      throw new Error("Sunucuya bağlanılamadı. Birkaç saniye bekleyip tekrar deneyin.");
    }
    throw e;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = data.detail;
    if (typeof detail === "string" && detail.trim()) throw new Error(detail);
    if (Array.isArray(detail)) {
      throw new Error(
        detail
          .map((d) => {
            if (typeof d === "string") return localizeValidationMsg(d);
            const loc = (d.loc || []).filter((x) => x !== "body" && x !== "query" && x !== "path");
            const field = loc.length ? String(loc[loc.length - 1]) : "";
            const msg = localizeValidationMsg(d.msg || JSON.stringify(d));
            const label = fieldLabelTr(field);
            return label ? `${label}: ${msg}` : msg;
          })
          .join(" · "),
      );
    }
    throw new Error("Dosya yüklenemedi.");
  }
  return data;
}
