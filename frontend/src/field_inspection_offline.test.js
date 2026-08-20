import {beforeEach, describe, expect, it} from "vitest";
import {
  _test,
  clearFieldInspectionCache,
  clearOfflineFindings,
  enqueueOfflineFinding,
  flushOfflineFindings,
  listOfflineFindings,
  normalizeFinding,
  readOfflineReference,
  saveOfflineReference,
} from "./field_inspection_offline.js";

const scope = {userId: 11, osgbId: 22};

function valid(overrides = {}) {
  return {
    id: "finding-test-1",
    type: "field_finding",
    user_id: 11,
    osgb_id: 22,
    company_id: 7,
    payload: {
      company_id: 7,
      department_name: "Saha",
      hazard_id: 3,
      activity: "Saha denetimi",
      risk_definition: "Koruyucusuz ekipman",
      record_origin: "field_inspection",
      client_reference: "risk-client-1",
    },
    action: {
      description: "Makine koruyucusu takılacak",
      client_reference: "dof-client-1",
    },
    photos: [{
      id: "photo-1",
      data_url: "data:image/jpeg;base64,AA==",
      name: "kanıt.jpg",
      type: "image/jpeg",
    }],
    ...overrides,
  };
}

describe("field inspection offline queue", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("rejects records without user, OSGB, company or payload scope", () => {
    expect(normalizeFinding({type: "field_finding", user_id: 1, osgb_id: 2, company_id: 3})).toBeNull();
    expect(enqueueOfflineFinding(valid({user_id: 0}))).toBeNull();
    expect(enqueueOfflineFinding(valid({osgb_id: 0}))).toBeNull();
  });

  it("keeps the queue isolated by user and OSGB", () => {
    enqueueOfflineFinding(valid());
    enqueueOfflineFinding(valid({id: "other-user", user_id: 99}));
    enqueueOfflineFinding(valid({id: "other-osgb", osgb_id: 88}));
    expect(listOfflineFindings(scope)).toHaveLength(1);
    expect(listOfflineFindings({userId: 11})).toHaveLength(2);
  });

  it("syncs risk, DÖF and photo in order then removes the item", async () => {
    enqueueOfflineFinding(valid());
    const calls = [];
    const fakeApi = async (path, options) => {
      calls.push([path, JSON.parse(options.body)]);
      if (path === "/risks") return {id: 101};
      if (path === "/risks/101/dofs") return {id: 202};
      throw new Error("Beklenmeyen API çağrısı");
    };
    const uploads = [];
    const fakeUpload = async (path, file, fields) => {
      uploads.push({path, file, fields});
      return {id: 303};
    };
    const result = await flushOfflineFindings(fakeApi, fakeUpload, scope);
    expect(result.synced).toBe(1);
    expect(result.photos).toBe(1);
    expect(calls.map((row) => row[0])).toEqual(["/risks", "/risks/101/dofs"]);
    expect(uploads).toHaveLength(1);
    expect(uploads[0].path).toBe("/risks/101/media");
    expect(uploads[0].fields.dof_id).toBe(202);
    expect(uploads[0].fields.client_reference).toBe("finding-test-1:photo:0");
    expect(listOfflineFindings(scope)).toHaveLength(0);
  });

  it("retains a failed item and records the error", async () => {
    enqueueOfflineFinding(valid());
    const result = await flushOfflineFindings(async () => {
      throw new Error("Sunucuya bağlanılamadı.");
    }, async () => ({}), scope);
    expect(result.failed).toBe(1);
    expect(listOfflineFindings(scope)[0].attempts).toBe(1);
    expect(listOfflineFindings(scope)[0].last_error).toContain("bağlanılamadı");
  });

  it("stores only scoped reference cache and can clear it", () => {
    saveOfflineReference(scope, {companies: [{id: 7, name: "Test"}]});
    expect(readOfflineReference(scope).companies[0].id).toBe(7);
    expect(readOfflineReference({userId: 99, osgbId: 22})).toBeNull();
    clearFieldInspectionCache();
    expect(readOfflineReference(scope)).toBeNull();
    expect(listOfflineFindings()).toHaveLength(0);
  });

  it("prunes expired and excessive photo data", () => {
    const old = normalizeFinding({
      ...valid(),
      created_at: new Date(Date.now() - _test.MAX_AGE_MS - 1000).toISOString(),
    });
    localStorage.setItem(_test.KEY, JSON.stringify([old]));
    expect(listOfflineFindings(scope)).toHaveLength(0);
    expect(() => enqueueOfflineFinding(valid({
      id: "too-large",
      photos: [{data_url: "data:image/jpeg;base64," + "a".repeat(_test.MAX_TOTAL_DATA_URL_CHARS)}],
    }))).toThrow(/sınırını/);
  });

  it("clears only the requested scope when asked", () => {
    enqueueOfflineFinding(valid());
    enqueueOfflineFinding(valid({id: "other", user_id: 99}));
    clearOfflineFindings(scope);
    expect(listOfflineFindings(scope)).toHaveLength(0);
    expect(listOfflineFindings({userId: 99, osgbId: 22})).toHaveLength(1);
  });
});
