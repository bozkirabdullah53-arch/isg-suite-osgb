/** Saha offline kuyruk — ziyaret tamamlama taslakları (localStorage). */
const KEY = "isg_field_offline_queue_v1";

function readQueue() {
  try {
    const raw = localStorage.getItem(KEY);
    const list = raw ? JSON.parse(raw) : [];
    return Array.isArray(list) ? list : [];
  } catch (_) {
    return [];
  }
}

function writeQueue(list) {
  localStorage.setItem(KEY, JSON.stringify(list.slice(0, 40)));
}

export function listOfflineCompletes() {
  return readQueue().filter((x) => x?.type === "complete");
}

export function enqueueOfflineComplete(item) {
  const list = readQueue();
  const row = {
    id: `oc_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    type: "complete",
    created_at: new Date().toISOString(),
    ...item,
  };
  list.unshift(row);
  writeQueue(list);
  return row;
}

export function removeOfflineItem(id) {
  writeQueue(readQueue().filter((x) => x.id !== id));
}

export async function flushOfflineCompletes(apiFn) {
  const pending = listOfflineCompletes();
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
      results.push({id: item.id, ok: false, error: ex.message || "Senkron başarısız"});
      // Ağ hatasında dur; diğerlerini deneme
      if (/bağlan|network|fetch|sunucu/i.test(String(ex.message || ""))) break;
    }
  }
  return results;
}
