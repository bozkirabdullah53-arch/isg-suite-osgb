import {beforeEach, describe, expect, it} from "vitest";
import {
  enqueueOfflineComplete,
  flushOfflineCompletes,
  listOfflineCompletes,
} from "./field_offline.js";
import {
  clearFieldInspectionCache,
  enqueueOfflineFinding,
  flushOfflineFindings,
  listOfflineFindings,
} from "./field_inspection_offline.js";
import {buildMobileSyncStatus} from "./mobile_sync_status.js";

const SCOPE = {userId: 11, osgbId: 22};
const MOBILE_DEVICES = [
  {name: "Android küçük ekran", width: 360, height: 800},
  {name: "Android saha telefonu", width: 412, height: 915},
  {name: "iPhone saha telefonu", width: 390, height: 844},
];

function finding() {
  return {
    id: "mobile-regression-finding",
    type: "field_finding",
    user_id: 11,
    osgb_id: 22,
    company_id: 7,
    payload: {
      company_id: 7,
      activity: "Mobil saha regresyonu",
      risk_definition: "Kayıt bağlantı yokken oluşturuldu",
      record_origin: "field_inspection",
    },
    photos: [],
  };
}

describe("mobile cihaz / offline / saha regresyon sözleşmesi", () => {
  beforeEach(() => {
    localStorage.clear();
    clearFieldInspectionCache();
  });

  it.each(MOBILE_DEVICES)("$name ekranında çevrimdışı bekleyen durumunu korur", ({width, height}) => {
    expect(width).toBeGreaterThanOrEqual(360);
    expect(height).toBeGreaterThan(700);
    expect(buildMobileSyncStatus({online: false, pendingCount: 1})).toMatchObject({
      state: "offline_pending",
      pendingCount: 1,
    });
  });

  it("ziyaret tamamlama kuyruğu ile fotoğraflı saha kuyruğunu birbirine karıştırmaz", () => {
    enqueueOfflineFinding(finding());
    enqueueOfflineComplete({visit_id: 41, user_id: 11, osgb_id: 22});

    expect(listOfflineFindings(SCOPE)).toHaveLength(1);
    expect(listOfflineCompletes(SCOPE)).toHaveLength(1);
    expect(listOfflineFindings({userId: 99, osgbId: 22})).toHaveLength(0);
    expect(listOfflineCompletes({userId: 99, osgbId: 22})).toHaveLength(0);
  });

  it("bağlantı geldiğinde saha kaydı ve ziyaret tamamlamasını ayrı ayrı sırayla senkronlar", async () => {
    enqueueOfflineFinding(finding());
    enqueueOfflineComplete({visit_id: 41, user_id: 11, osgb_id: 22});
    const calls = [];
    const apiFn = async (path) => {
      calls.push(path);
      if (path === "/risks") return {id: 501};
      return {};
    };
    const uploadFn = async () => ({});

    const findingResult = await flushOfflineFindings(apiFn, uploadFn, SCOPE);
    const completeResult = await flushOfflineCompletes(async (path) => {
      calls.push(path);
      return {};
    }, SCOPE);

    expect(findingResult.synced).toBe(1);
    expect(completeResult[0].ok).toBe(true);
    expect(calls).toEqual(["/risks", "/operations/visits/41/complete"]);
    expect(listOfflineFindings(SCOPE)).toHaveLength(0);
    expect(listOfflineCompletes(SCOPE)).toHaveLength(0);
  });

  it("ağ hatasında iki kuyruğu da korur ve sonraki denemeye bırakır", async () => {
    enqueueOfflineFinding(finding());
    enqueueOfflineComplete({visit_id: 41, user_id: 11, osgb_id: 22});

    const failedFinding = await flushOfflineFindings(
      async () => { throw new TypeError("network offline"); },
      async () => ({}),
      SCOPE,
    );
    const failedComplete = await flushOfflineCompletes(async () => {
      throw new Error("sunucuya bağlanılamadı");
    }, SCOPE);

    expect(failedFinding.failed).toBe(1);
    expect(failedComplete[0].ok).toBe(false);
    expect(listOfflineFindings(SCOPE)).toHaveLength(1);
    expect(listOfflineCompletes(SCOPE)).toHaveLength(1);
  });
});
