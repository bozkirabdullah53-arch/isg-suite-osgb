import {beforeEach, describe, expect, it} from "vitest";
import {
  _test,
  clearOfflineQueue,
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

  it("rejects invalid visit_id or missing tenant binding", () => {
    expect(enqueueOfflineComplete({visit_id: 0, user_id: 1, osgb_id: 2})).toBeNull();
    expect(enqueueOfflineComplete({visit_id: 12, user_id: 1})).toBeNull();
    expect(enqueueOfflineComplete({visit_id: 12, osgb_id: 2})).toBeNull();
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("enqueues and lists valid complete", () => {
    const row = enqueueOfflineComplete({
      visit_id: 12,
      user_id: 3,
      osgb_id: 7,
      site_verify_code: "ABC",
      gps_lat: 41.1,
    });
    expect(row.visit_id).toBe(12);
    expect(row.user_id).toBe(3);
    expect(row.osgb_id).toBe(7);
    expect(listOfflineCompletes({userId: 3, osgbId: 7})).toHaveLength(1);
  });

  it("filters by user/osgb scope", () => {
    enqueueOfflineComplete({visit_id: 1, user_id: 3, osgb_id: 7});
    enqueueOfflineComplete({visit_id: 2, user_id: 9, osgb_id: 7});
    enqueueOfflineComplete({visit_id: 3, user_id: 3, osgb_id: 8});
    expect(listOfflineCompletes({userId: 3, osgbId: 7})).toHaveLength(1);
    expect(listOfflineCompletes({userId: 3})).toHaveLength(2);
  });

  it("strips oversized signature", () => {
    const huge = "data:image/png;base64," + "a".repeat(_test.MAX_SIGNATURE_CHARS);
    const row = enqueueOfflineComplete({
      visit_id: 3,
      user_id: 1,
      osgb_id: 2,
      signature_data_url: huge,
    });
    expect(row.signature_data_url).toBeNull();
    expect(row.signature_omitted).toBe(true);
  });

  it("drops items older than TTL", () => {
    const old = normalizeComplete({
      type: "complete",
      visit_id: 9,
      user_id: 1,
      osgb_id: 2,
      created_at: new Date(Date.now() - _test.MAX_AGE_MS - 1000).toISOString(),
    });
    localStorage.setItem(_test.KEY, JSON.stringify([old]));
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("increments attempts and drops after max retries", async () => {
    enqueueOfflineComplete({visit_id: 7, user_id: 1, osgb_id: 2});
    const fail = async () => {
      throw new Error("422 validation");
    };
    for (let i = 0; i < _test.MAX_RETRIES; i++) {
      const results = await flushOfflineCompletes(fail, {userId: 1, osgbId: 2});
      expect(results[0].ok).toBe(false);
    }
    expect(listOfflineCompletes({userId: 1, osgbId: 2})).toHaveLength(0);
  });

  it("removeOfflineItem and clearOfflineQueue work", () => {
    const row = enqueueOfflineComplete({visit_id: 5, user_id: 1, osgb_id: 2});
    removeOfflineItem(row.id);
    expect(listOfflineCompletes()).toHaveLength(0);
    enqueueOfflineComplete({visit_id: 6, user_id: 1, osgb_id: 2});
    clearOfflineQueue();
    expect(listOfflineCompletes()).toHaveLength(0);
  });

  it("flush success removes item", async () => {
    enqueueOfflineComplete({visit_id: 8, user_id: 1, osgb_id: 2});
    const results = await flushOfflineCompletes(async () => ({}), {userId: 1, osgbId: 2});
    expect(results[0].ok).toBe(true);
    expect(listOfflineCompletes({userId: 1, osgbId: 2})).toHaveLength(0);
  });
});
