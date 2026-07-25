/** Saha offline kuyruk — ziyaret tamamlama taslakları (localStorage). */
const KEY = "isg_field_offline_queue_v1";
const MAX_ITEMS = 40;
const MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000;
const MAX_SIGNATURE_CHARS = 400_000;
const MAX_RETRIES = 5;

function readQueue() {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(list)) return [];
    return pruneQueue(list);
  } catch {
    return [];
  }
}

function pruneQueue(list) {
  const now = Date.now();
  const cleaned = [];
  for (const raw of list) {
    const row = normalizeComplete(raw);
    if (!row) continue;
    const created = Date.parse(row.created_at || "");
    if (Number.isFinite(created) && now - created > MAX_AGE_MS) continue;
    if ((row.attempts || 0) >= MAX_RETRIES) continue;
    cleaned.push(row);
  }
  return cleaned.slice(0, MAX_ITEMS);
}

function matchesScope(row, scope) {
  if (!scope) return true;
  const uid = Number(scope.userId ?? scope.user_id);
  const oid = Number(scope.osgbId ?? scope.osgb_id);
  if (Number.isFinite(uid) && uid > 0 && row.user_id !== uid) return false;
  if (Number.isFinite(oid) && oid > 0 && row.osgb_id !== oid) return false;
  return true;
}

/** @returns {object|null} */
export function normalizeComplete(item) {
  if (!item || item.type !== "complete") return null;
  const visitId = Number(item.visit_id);
  const userId = Number(item.user_id);
  const osgbId = Number(item.osgb_id);
  if (!Number.isFinite(visitId) || visitId <= 0) return null;
  if (!Number.isFinite(userId) || userId <= 0) return null;
  if (!Number.isFinite(osgbId) || osgbId <= 0) return null;

  let signature = typeof item.signature_data_url === "string" ? item.signature_data_url : null;
  let signatureOmitted = Boolean(item.signature_omitted);
  if (signature && signature.length > MAX_SIGNATURE_CHARS) {
    signature = null;
    signatureOmitted = true;
  }

  const attempts = Math.max(0, Number(item.attempts) || 0);
  return {
    id: typeof item.id === "string" && item.id ? item.id : `oc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    type: "complete",
    created_at: item.created_at || new Date().toISOString(),
    visit_id: visitId,
    user_id: userId,
    osgb_id: osgbId,
    gps_lat: item.gps_lat ?? null,
    gps_lng: item.gps_lng ?? null,
    gps_accuracy_m: item.gps_accuracy_m ?? null,
    site_verify_code: item.site_verify_code || null,
    signature_data_url: signature,
    signature_omitted: signatureOmitted || undefined,
    attempts,
  };
}

function writeQueue(list) {
  const trimmed = pruneQueue(list).slice(0, MAX_ITEMS);
  try {
    localStorage.setItem(KEY, JSON.stringify(trimmed));
    return;
  } catch {
    // Quota: imzaları düşür, yeniden dene
    const slim = trimmed.map((row) =>
      row.signature_data_url
        ? {...row, signature_data_url: null, signature_omitted: true}
        : row,
    );
    try {
      localStorage.setItem(KEY, JSON.stringify(slim));
    } catch {
      try {
        localStorage.setItem(KEY, JSON.stringify(slim.slice(0, 5)));
      } catch {
        /* ignore */
      }
    }
  }
}

export function listOfflineCompletes(scope) {
  return readQueue().filter((x) => x?.type === "complete" && matchesScope(x, scope));
}

export function enqueueOfflineComplete(item) {
  const list = readQueue();
  const row = normalizeComplete({
    ...item,
    type: "complete",
    created_at: new Date().toISOString(),
    attempts: 0,
  });
  if (!row) return null;
  list.unshift(row);
  writeQueue(list);
  return row;
}

export function removeOfflineItem(id) {
  writeQueue(readQueue().filter((x) => x.id !== id));
}

export function clearOfflineQueue() {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export async function flushOfflineCompletes(apiFn, scope) {
  const pending = listOfflineCompletes(scope);
  const results = [];
  for (const item of pending) {
    try {
      await apiFn(`/operations/visits/${item.visit_id}/complete`, {
        method: "PATCH",
        body: JSON.stringify({
          gps_lat: item.gps_lat ?? null,
          gps_lng: item.gps_lng ?? null,
          gps_accuracy_m: item.gps_accuracy_m ?? null,
          site_verify_code: item.site_verify_code || null,
          signature_data_url: item.signature_data_url || null,
        }),
      });
      removeOfflineItem(item.id);
      results.push({id: item.id, ok: true});
    } catch (ex) {
      const attempts = (item.attempts || 0) + 1;
      const next = {...item, attempts};
      const rest = readQueue().map((x) => (x.id === item.id ? next : x));
      writeQueue(rest);
      results.push({
        id: item.id,
        ok: false,
        error: ex.message || "Senkron başarısız",
        attempts,
        dropped: attempts >= MAX_RETRIES,
      });
      if (/bağlan|network|fetch|sunucu/i.test(String(ex.message || ""))) break;
    }
  }
  return results;
}

export const _test = {
  KEY,
  MAX_ITEMS,
  MAX_AGE_MS,
  MAX_SIGNATURE_CHARS,
  MAX_RETRIES,
  pruneQueue,
  matchesScope,
};
