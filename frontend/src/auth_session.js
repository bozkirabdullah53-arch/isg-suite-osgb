/** P1-01 refresh cookie oturum bayrağı — Vitest ile test edilebilir. */
const REFRESH_FLAG_KEY = "isg_refresh_cookie";

export function setRefreshCookieMode(enabled) {
  try {
    if (enabled) localStorage.setItem(REFRESH_FLAG_KEY, "1");
    else localStorage.removeItem(REFRESH_FLAG_KEY);
  } catch {
    /* ignore */
  }
}

export function refreshCookieMode() {
  try {
    return localStorage.getItem(REFRESH_FLAG_KEY) === "1";
  } catch {
    return false;
  }
}

/** 401 sonrası /auth/refresh denensin mi? */
export function canAttemptTokenRefresh(path, status) {
  if (status !== 401) return false;
  if (!refreshCookieMode()) return false;
  const p = String(path || "");
  if (p.startsWith("/auth/login") || p.startsWith("/auth/refresh") || p.startsWith("/auth/mfa")) {
    return false;
  }
  return true;
}
