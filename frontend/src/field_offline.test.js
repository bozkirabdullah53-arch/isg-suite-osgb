import {beforeEach, describe, expect, it} from "vitest";
import {
  _test,
  enqueueOfflineComplete,
  flushOfflineCompletes,
  listOfflineCompletes,
  normalizeComplete,
  removeOfflineItem,
} from "./field_offline.js";

describe("field_offline queue hardening", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("rejects invalid visit_id", () => {
    expect(enqueueOfflineComplete({visit_id: 0})).toBeNull();
    expect(enqueueOfflineComplete({visit_id: "x"})).toBeNull();
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("enqueues and lists valid complete", () => {
    const row = enqueueOfflineComplete({
      visit_id: 12,
      site_verify_code: "ABC",
      gps_lat: 41.1,
    });
    expect(row.visit_id).toBe(12);
    expect(listOfflineCompletes()).toHaveLength(1);
  });

  it("strips oversized signature", () => {
    const huge = "data:image/png;base64," + "a".repeat(_test.MAX_SIGNATURE_CHARS);
    const row = enqueueOfflineComplete({visit_id: 3, signature_data_url: huge});
    expect(row.signature_data_url).toBeNull();
    expect(row.signature_omitted).toBe(true);
  });

  it("drops items older than TTL", () => {
    const old = normalizeComplete({
      type: "complete",
      visit_id: 9,
      created_at: new Date(Date.now() - _test.MAX_AGE_MS - 1000).toISOString(),
    });
    localStorage.setItem(_test.KEY, JSON.stringify([old]));
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("increments attempts and drops after max retries", async () => {
    enqueueOfflineComplete({visit_id: 7});
    const fail = async () => {
      throw new Error("422 validation");
    };
    for (let i = 0; i < _test.MAX_RETRIES; i++) {
      const results = await flushOfflineCompletes(fail);
      expect(results[0].ok).toBe(false);
    }
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("removeOfflineItem works", () => {
    const row = enqueueOfflineComplete({visit_id: 5});
    removeOfflineItem(row.id);
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("flush success removes item", async () => {
    enqueueOfflineComplete({visit_id: 8});
    const results = await flushOfflineCompletes(async () => ({}));
    expect(results[0].ok).toBe(true);
    expect(listOfflineCompletes()).toHaveLength(0);
  });
});
