import { describe, expect, it, beforeEach } from "vitest";
import {
  canAttemptTokenRefresh,
  clearAccessToken,
  getAccessToken,
  refreshCookieMode,
  setAccessToken,
  setRefreshCookieMode,
} from "./auth_session.js";

describe("auth_session (P1-01 / P1-09)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearAccessToken();
  });

  it("access tokenı kalıcı localStorage yerine sekme oturumunda tutar", () => {
    localStorage.setItem("isg_token", "legacy-token");
    expect(getAccessToken()).toBe("legacy-token");
    expect(sessionStorage.getItem("isg_token")).toBe("legacy-token");
    expect(localStorage.getItem("isg_token")).toBeNull();
    setAccessToken("fresh-token");
    expect(getAccessToken()).toBe("fresh-token");
    clearAccessToken();
    expect(sessionStorage.getItem("isg_token")).toBeNull();
  });

  it("setRefreshCookieMode toggles flag", () => {
    expect(refreshCookieMode()).toBe(false);
    setRefreshCookieMode(true);
    expect(refreshCookieMode()).toBe(true);
    setRefreshCookieMode(false);
    expect(refreshCookieMode()).toBe(false);
  });

  it("canAttemptTokenRefresh on 401 for non-auth paths (cookie bayrağı gerekmez)", () => {
    expect(canAttemptTokenRefresh("/companies", 401)).toBe(true);
    expect(canAttemptTokenRefresh("/companies", 403)).toBe(false);
    expect(canAttemptTokenRefresh("/auth/login", 401)).toBe(false);
    expect(canAttemptTokenRefresh("/auth/refresh", 401)).toBe(false);
  });
});
