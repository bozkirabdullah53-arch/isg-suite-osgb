const isLocalHost =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

const API_URL =
  import.meta.env.VITE_API_URL ||
  (isLocalHost
    ? `${window.location.protocol}//${window.location.hostname}:8000/api/v1`
    : "https://isg-suite-api-1u9t.onrender.com/api/v1");

export async function api(path, options = {}) {
  const token = localStorage.getItem("isg_token");
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => d.msg || JSON.stringify(d)).join("; ")
      : detail || `İşlem tamamlanamadı (HTTP ${response.status}).`;
    throw new Error(typeof message === "string" ? message : JSON.stringify(message));
  }
  return data;
}

/** Auth header ile blob URL üretir (önizleme görselleri için). */
export async function authBlobUrl(path) {
  const token = localStorage.getItem("isg_token");
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    throw new Error(`Dosya alınamadı (HTTP ${response.status}).`);
  }
  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

export async function downloadFile(path, filename) {
  const token = localStorage.getItem("isg_token");
  const response = await fetch(`${API_URL}${path}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    const message = Array.isArray(detail)
      ? detail.map((d) => (typeof d === "string" ? d : d.msg || JSON.stringify(d))).join("; ")
      : detail || `Dosya indirilemedi (HTTP ${response.status}).`;
    throw new Error(message);
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
  // Önizleme yedek: yeni sekmede aç
  window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
}

export async function uploadFile(path, file) {
  const token = localStorage.getItem("isg_token");
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  });
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
