/**
 * Feature-flagged mobile sync status adapter.
 *
 * This module is intentionally pure and additive: it reads the existing queue
 * count/state but does not write queue data or change any API contract.
 */
const FLAG_NAME = "VITE_MOBILE_SYNC_STATUS_V1";

export function isMobileSyncStatusEnabled() {
  try {
    return String(import.meta.env?.[FLAG_NAME] || "").toLowerCase() === "true";
  } catch {
    return false;
  }
}

function countOf(value) {
  const count = Number(value);
  return Number.isFinite(count) && count > 0 ? Math.floor(count) : 0;
}

export function buildMobileSyncStatus({online = true, pendingCount = 0, syncBusy = false} = {}) {
  const pending = countOf(pendingCount);
  if (syncBusy) {
    return {
      state: "syncing",
      tone: "info",
      pendingCount: pending,
      label: pending ? `Senkronlanıyor · ${pending} kayıt` : "Senkronlanıyor",
    };
  }
  if (!online && pending > 0) {
    return {
      state: "offline_pending",
      tone: "warning",
      pendingCount: pending,
      label: `Çevrimdışı · ${pending} kayıt bekliyor`,
    };
  }
  if (!online) {
    return {state: "offline", tone: "warning", pendingCount: 0, label: "Çevrimdışı"};
  }
  if (pending > 0) {
    return {
      state: "pending",
      tone: "warning",
      pendingCount: pending,
      label: `${pending} kayıt senkron bekliyor`,
    };
  }
  return {state: "ready", tone: "success", pendingCount: 0, label: "Senkronizasyon hazır"};
}

export const _test = {countOf, FLAG_NAME};
