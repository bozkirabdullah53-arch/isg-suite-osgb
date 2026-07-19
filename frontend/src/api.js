const isLocalHost =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

const API_URL =
  import.meta.env.VITE_API_URL ||
  (isLocalHost
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : "https://isg-suite-api-1u9t.onrender.com/api/v1");

const API_ROOT = API_URL.replace(/\/api\/v1\/?$/, "");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isNetworkError(e) {
  const msg = String(e?.message || e || "").toLowerCase();
  return e instanceof TypeError || msg.includes("failed to fetch") || msg.includes("networkerror") || msg.includes("load failed");
}

/** Render cold-start: kimlik doğrulamasız /health ile API'yi uyandır. */
export async function wakeApi() {
  try {
    await fetch(`${API_ROOT}/health`, {method: "GET", cache: "no-store", mode: "cors"});
  } catch (_) {
    /* ignore */
  }
}

async function parseError(response) {
  const data = await response.json().catch(() => ({}));
  const detail = data.detail;
  const message = Array.isArray(detail)
    ? detail.map((d) => (typeof d === "string" ? d : d.msg || JSON.stringify(d))).join("; ")
    : detail || `İşlem tamamlanamadı (HTTP ${response.status}).`;
  return typeof message === "string" ? message : JSON.stringify(message);
}

/**
 * API çağrısı — ağ kopmasında API uyandırıp birkaç kez dener.
 * options._retries ile deneme sayısı (varsayılan 2 ek deneme).
 */
export async function api(path, options = {}) {
  const retries = options._retries ?? 2;
  const { _retries, headers: optHeaders, ...fetchOpts } = options;
  const token = localStorage.getItem("isg_token");
  const method = (fetchOpts.method || "GET").toUpperCase();
  const headers = {...(optHeaders || {})};
  if (token) headers.Authorization = `Bearer ${token}`;
  // GET'te Content-Type gönderme (gereksiz preflight / proxy sorunlarını azaltır)
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
      const response = await fetch(`${API_URL}${path}`, {...fetchOpts, headers, mode: "cors"});
      if (!response.ok) {
        throw new Error(await parseError(response));
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
            "Sunucuya bağlanılamadı. API uyanıyor olabilir — 10–20 sn bekleyip Yenile’ye basın.",
          );
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

export async function uploadFile(path, file) {
  await wakeApi();
  const token = localStorage.getItem("isg_token");
  const formData = new FormData();
  formData.append("file", file);
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method: "POST",
      headers: token ? {Authorization: `Bearer ${token}`} : {},
      body: formData,
      mode: "cors",
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
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
      : detail || "Dosya yüklenemedi.";
    throw new Error(message);
  }
  return data;
}
