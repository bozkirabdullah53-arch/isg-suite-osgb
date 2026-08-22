/** P1-01 refresh cookie oturum bayrağı — Vitest ile test edilebilir. */
const REFRESH_FLAG_KEY = "isg_refresh_cookie";
const ACCESS_TOKEN_KEY = "isg_token";
const MFA_SETUP_TOKEN_KEY = "isg_mfa_setup_token";
let accessTokenMemory = null;

function readSessionValue(key) {
  try {
    return sessionStorage.getItem(key);
  } catch {
    return null;
  }
}

function migrateLegacyValue(key) {
  try {
    const legacy = localStorage.getItem(key);
    if (!legacy) return null;
    try {
      sessionStorage.setItem(key, legacy);
      localStorage.removeItem(key);
      return legacy;
    } catch {
      return legacy;
    }
  } catch {
    return null;
  }
}

function writeSessionValue(key, value) {
  try {
    if (value) sessionStorage.setItem(key, value);
    else sessionStorage.removeItem(key);
  } catch {
    return;
  }
}

export function getAccessToken() {
  if (accessTokenMemory) return accessTokenMemory;
  accessTokenMemory = readSessionValue(ACCESS_TOKEN_KEY) || migrateLegacyValue(ACCESS_TOKEN_KEY);
  return accessTokenMemory;
}

export function setAccessToken(value) {
  const token = String(value || "").trim();
  accessTokenMemory = token || null;
  writeSessionValue(ACCESS_TOKEN_KEY, accessTokenMemory);
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  } catch {
    return;
  }
}

export function clearAccessToken() {
  accessTokenMemory = null;
  writeSessionValue(ACCESS_TOKEN_KEY, null);
  try {
    localStorage.removeItem(ACCESS_TOKEN_KEY);
  } catch {
    return;
  }
}

export function getMfaSetupToken() {
  return readSessionValue(MFA_SETUP_TOKEN_KEY) || migrateLegacyValue(MFA_SETUP_TOKEN_KEY);
}

export function setMfaSetupToken(value) {
  const token = String(value || "").trim();
  writeSessionValue(MFA_SETUP_TOKEN_KEY, token || null);
  try {
    localStorage.removeItem(MFA_SETUP_TOKEN_KEY);
  } catch {
    return;
  }
}

export function clearMfaSetupToken() {
  writeSessionValue(MFA_SETUP_TOKEN_KEY, null);
  try {
    localStorage.removeItem(MFA_SETUP_TOKEN_KEY);
  } catch {
    return;
  }
}

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

/** 401 sonrası /auth/refresh denensin mi? (bayrak olmasa da cookie denensin) */
export function canAttemptTokenRefresh(path, status) {
  if (status !== 401) return false;
  const p = String(path || "");
  if (p.startsWith("/auth/login") || p.startsWith("/auth/refresh") || p.startsWith("/auth/mfa")) {
    return false;
  }
  return true;
}
