import { describe, expect, it, beforeEach } from "vitest";
import {
  canAttemptTokenRefresh,
  refreshCookieMode,
  setRefreshCookieMode,
} from "./auth_session.js";

describe("auth_session (P1-01 / P1-09)", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("setRefreshCookieMode toggles flag", () => {
    expect(refreshCookieMode()).toBe(false);
    setRefreshCookieMode(true);
    expect(refreshCookieMode()).toBe(true);
    setRefreshCookieMode(false);
    expect(refreshCookieMode()).toBe(false);
  });

  it("canAttemptTokenRefresh only when flag on and 401 on non-auth path", () => {
    expect(canAttemptTokenRefresh("/companies", 401)).toBe(false);
    setRefreshCookieMode(true);
    expect(canAttemptTokenRefresh("/companies", 401)).toBe(true);
    expect(canAttemptTokenRefresh("/companies", 403)).toBe(false);
    expect(canAttemptTokenRefresh("/auth/login", 401)).toBe(false);
    expect(canAttemptTokenRefresh("/auth/refresh", 401)).toBe(false);
  });
});
