import {describe, expect, it} from "vitest";
import {buildMobileSyncStatus} from "./mobile_sync_status";

describe("mobile sync status adapter", () => {
  it("reports a ready online state without pending records", () => {
    expect(buildMobileSyncStatus({online: true, pendingCount: 0, syncBusy: false})).toMatchObject({
      state: "ready",
      tone: "success",
      pendingCount: 0,
      label: "Senkronizasyon hazır",
    });
  });

  it("keeps pending records visible while offline", () => {
    expect(buildMobileSyncStatus({online: false, pendingCount: 3, syncBusy: false})).toMatchObject({
      state: "offline_pending",
      tone: "warning",
      pendingCount: 3,
      label: "Çevrimdışı · 3 kayıt bekliyor",
    });
  });

  it("prioritizes active synchronization over the queue count", () => {
    expect(buildMobileSyncStatus({online: true, pendingCount: 2, syncBusy: true})).toMatchObject({
      state: "syncing",
      tone: "info",
      pendingCount: 2,
    });
  });

  it("normalizes invalid queue counts without changing the queue", () => {
    expect(buildMobileSyncStatus({online: true, pendingCount: "nope", syncBusy: false})).toMatchObject({
      state: "ready",
      pendingCount: 0,
    });
  });
});
