/**
 * Mobil saha denetimi offline kuyruğu.
 *
 * Ziyaret tamamlama kuyruğundan ayrı tutulur: fotoğraflı uygunsuzluk
 * kayıtları risk + DÖF + medya zincirini ağ geldiğinde sırayla senkronlar.
 */
const KEY = "isg_field_finding_queue_v1";
const MAX_ITEMS = 30;
const MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
const MAX_RETRIES = 8;
const MAX_PHOTOS = 5;
const MAX_TOTAL_DATA_URL_CHARS = 7_000_000;

function nowIso() {
  return new Date().toISOString();
}

function readRaw() {
  try {
    const raw = localStorage.getItem(KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function scopeMatches(row, scope) {
  if (!scope) return true;
  const uid = Number(scope.userId ?? scope.user_id);
  const oid = Number(scope.osgbId ?? scope.osgb_id);
  if (Number.isFinite(uid) && uid > 0 && Number(row.user_id) !== uid) return false;
  if (Number.isFinite(oid) && oid > 0 && Number(row.osgb_id) !== oid) return false;
  return true;
}

function normalizePhoto(photo, index) {
  if (!photo || typeof photo.data_url !== "string" || !photo.data_url.startsWith("data:image/")) {
    return null;
  }
  const dataUrl = photo.data_url;
  if (dataUrl.length > 1_500_000) return null;
  return {
    id: String(photo.id || `photo_${index}_${Date.now()}`),
    name: String(photo.name || `saha-fotografi-${index + 1}.jpg`).slice(0, 180),
    type: String(photo.type || "image/jpeg").slice(0, 100),
    data_url: dataUrl,
    description: String(photo.description || "Saha denetimi fotoğraf kanıtı").slice(0, 500),
    tags: Array.isArray(photo.tags) ? photo.tags.map((x) => String(x).slice(0, 60)).slice(0, 12) : [],
    captured_at: photo.captured_at || null,
    gps_lat: photo.gps_lat ?? null,
    gps_lng: photo.gps_lng ?? null,
    gps_accuracy_m: photo.gps_accuracy_m ?? null,
    client_reference: String(photo.client_reference || "").slice(0, 80) || null,
  };
}

export function normalizeFinding(item) {
  if (!item || item.type !== "field_finding") return null;
  const userId = Number(item.user_id);
  const osgbId = Number(item.osgb_id);
  const companyId = Number(item.company_id);
  if (!Number.isFinite(userId) || userId <= 0) return null;
  if (!Number.isFinite(osgbId) || osgbId <= 0) return null;
  if (!Number.isFinite(companyId) || companyId <= 0) return null;
  if (!item.payload || typeof item.payload !== "object") return null;

  const photos = (Array.isArray(item.photos) ? item.photos : [])
    .map(normalizePhoto)
    .filter(Boolean)
    .slice(0, MAX_PHOTOS);
  const uploaded = Array.isArray(item.uploaded_photo_indexes)
    ? item.uploaded_photo_indexes.map(Number).filter((x) => Number.isInteger(x) && x >= 0 && x < photos.length)
    : [];
  const attempts = Math.max(0, Number(item.attempts) || 0);
  const action = item.action && typeof item.action === "object"
    ? {
        description: String(item.action.description || "").slice(0, 2000),
        responsible_person: String(item.action.responsible_person || "").slice(0, 150) || null,
        responsible_department: String(item.action.responsible_department || "").slice(0, 150) || null,
        term_date: item.action.term_date || null,
        client_reference: String(item.action.client_reference || "").slice(0, 80) || null,
      }
    : null;
  return {
    id: String(item.id || `finding_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`),
    type: "field_finding",
    created_at: item.created_at || nowIso(),
    user_id: userId,
    osgb_id: osgbId,
    company_id: companyId,
    payload: item.payload,
    action,
    photos,
    risk_id: Number(item.risk_id) > 0 ? Number(item.risk_id) : null,
    dof_id: Number(item.dof_id) > 0 ? Number(item.dof_id) : null,
    uploaded_photo_indexes: [...new Set(uploaded)],
    attempts,
    last_error: item.last_error ? String(item.last_error).slice(0, 500) : null,
  };
}

function prune(list) {
  const now = Date.now();
  return list
    .map(normalizeFinding)
    .filter(Boolean)
    .filter((row) => {
      const created = Date.parse(row.created_at);
      return !Number.isFinite(created) || now - created <= MAX_AGE_MS;
    })
    .filter((row) => row.attempts < MAX_RETRIES)
    .slice(0, MAX_ITEMS);
}

function writeQueue(list) {
  const cleaned = prune(list);
  try {
    localStorage.setItem(KEY, JSON.stringify(cleaned));
    return cleaned;
  } catch {
    // Fotoğraflar büyükse kullanıcının metin kaydını kaybetmemek için
    // en eski kuyruğu düşürerek yeniden dene.
    try {
      const slim = cleaned.slice(0, 8);
      localStorage.setItem(KEY, JSON.stringify(slim));
      return slim;
    } catch {
      return [];
    }
  }
}

export function listOfflineFindings(scope) {
  return readQueue().filter((row) => scopeMatches(row, scope));
}

export function enqueueOfflineFinding(item) {
  const row = normalizeFinding({
    ...item,
    type: "field_finding",
    created_at: item?.created_at || nowIso(),
    attempts: 0,
    last_error: null,
  });
  if (!row) return null;
  const dataSize = row.photos.reduce((sum, photo) => sum + photo.data_url.length, 0);
  if (dataSize > MAX_TOTAL_DATA_URL_CHARS) {
    throw new Error("Fotoğraflar çevrimdışı kayıt sınırını aşıyor. Daha az veya daha küçük fotoğraf seçin.");
  }
  const list = readRaw().filter((existing) => existing.id !== row.id);
  list.unshift(row);
  writeQueue(list);
  return row;
}

export function removeOfflineFinding(id) {
  writeQueue(readRaw().filter((row) => row.id !== id));
}

export function clearOfflineFindings(scope = null) {
  if (!scope) {
    try { localStorage.removeItem(KEY); } catch { /* ignore */ }
    return;
  }
  writeQueue(readRaw().filter((row) => !scopeMatches(normalizeFinding(row), scope)));
}

function isNetworkError(error) {
  const message = String(error?.message || error || "");
  return error?.name === "TypeError" || /bağlan|network|fetch|offline|sunucuya/i.test(message);
}

function dataUrlToBlob(dataUrl) {
  const [header, body] = String(dataUrl || "").split(",");
  const mime = (header.match(/data:([^;]+)/i) || [])[1] || "image/jpeg";
  const bytes = atob(body || "");
  const buffer = new Uint8Array(bytes.length);
  for (let index = 0; index < bytes.length; index += 1) buffer[index] = bytes.charCodeAt(index);
  return new Blob([buffer], {type: mime});
}

function asUploadFile(blob, photo) {
  if (typeof File === "function") {
    return new File([blob], photo.name || "saha-fotografi.jpg", {type: photo.type || blob.type || "image/jpeg"});
  }
  return blob;
}

/**
 * apiFn ve uploadFn dışarıdan geçirilir; böylece kuyruk kodu auth/api
 * katmanına bağımlı kalmaz ve birim test edilebilir.
 */
export async function flushOfflineFindings(apiFn, uploadFn, scope) {
  const result = {synced: 0, failed: 0, photos: 0, errors: []};
  const pending = listOfflineFindings(scope);
  for (const snapshot of pending) {
    const item = normalizeFinding(snapshot);
    if (!item) continue;
    try {
      if (!item.risk_id) {
        const risk = await apiFn("/risks", {
          method: "POST",
          body: JSON.stringify(item.payload),
        });
        item.risk_id = Number(risk?.id) || null;
        if (!item.risk_id) throw new Error("Saha riski sunucudan kimlik alamadı.");
        writeQueue(readRaw().map((row) => row.id === item.id ? item : row));
      }

      if (!item.dof_id && item.action?.description) {
        const dof = await apiFn(`/risks/${item.risk_id}/dofs`, {
          method: "POST",
          body: JSON.stringify({
            description: item.action.description,
            responsible_person: item.action.responsible_person,
            responsible_department: item.action.responsible_department,
            term_date: item.action.term_date,
            client_reference: item.action.client_reference,
          }),
        });
        item.dof_id = Number(dof?.id) || null;
        if (!item.dof_id) throw new Error("DÖF sunucudan kimlik alamadı.");
        writeQueue(readRaw().map((row) => row.id === item.id ? item : row));
      }

      for (let index = 0; index < item.photos.length; index += 1) {
        if (item.uploaded_photo_indexes.includes(index)) continue;
        const photo = item.photos[index];
        const blob = dataUrlToBlob(photo.data_url);
        const file = asUploadFile(blob, photo);
        await uploadFn(`/risks/${item.risk_id}/media`, file, {
          tags: JSON.stringify(photo.tags || []),
          description: photo.description,
          dof_id: item.dof_id || undefined,
          client_reference: photo.client_reference || `${item.id}:photo:${index}`,
          captured_at: photo.captured_at || item.payload.observed_at || undefined,
          gps_lat: photo.gps_lat ?? item.payload.gps_lat ?? undefined,
          gps_lng: photo.gps_lng ?? item.payload.gps_lng ?? undefined,
          gps_accuracy_m: photo.gps_accuracy_m ?? item.payload.gps_accuracy_m ?? undefined,
        });
        item.uploaded_photo_indexes.push(index);
        result.photos += 1;
        writeQueue(readRaw().map((row) => row.id === item.id ? item : row));
      }

      removeOfflineFinding(item.id);
      result.synced += 1;
    } catch (error) {
      const message = String(error?.message || "Senkron başarısız.");
      item.attempts += 1;
      item.last_error = message;
      writeQueue(readRaw().map((row) => row.id === item.id ? item : row));
      result.failed += 1;
      result.errors.push({id: item.id, message, attempts: item.attempts});
      if (isNetworkError(error)) break;
    }
  }
  return {...result, pending: listOfflineFindings(scope).length};
}

export const _test = {
  KEY,
  MAX_ITEMS,
  MAX_AGE_MS,
  MAX_RETRIES,
  MAX_PHOTOS,
  MAX_TOTAL_DATA_URL_CHARS,
  normalizePhoto,
  prune,
  scopeMatches,
  dataUrlToBlob,
};
