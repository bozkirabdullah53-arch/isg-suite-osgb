import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';

function tokenWithExpiry(seconds = 3600) {
  return `header.${btoa(JSON.stringify({exp: Math.floor(Date.now() / 1000) + seconds}))}.signature`;
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {'Content-Type': 'application/json'},
  });
}

describe('API temporary outage recovery', () => {
  let api;
  let apiWithBearer;
  let auth;

  beforeEach(async () => {
    vi.resetModules();
    vi.useFakeTimers();
    localStorage.clear();
    sessionStorage.clear();
    auth = await import('./auth_session.js');
    auth.setAccessToken(tokenWithExpiry());
    auth.setRefreshCookieMode(true);
    ({api, apiWithBearer} = await import('./api.js'));
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it.each([502, 503, 504])('recovers a read after HTTP %s without reporting a resolved error', async (status) => {
    let attempts = 0;
    const fetchMock = vi.fn(async (url, options) => {
      if (String(url).endsWith('/health')) {
        expect(options.signal).toBeDefined();
        return jsonResponse({status: 'ok'});
      }
      expect(String(url)).toMatch(/\/trainings\/meta$/);
      attempts += 1;
      return attempts === 1 ? jsonResponse({}, status) : jsonResponse({sectors: []});
    });
    vi.stubGlobal('fetch', fetchMock);
    const result = expect(api('/trainings/meta', {_retries: 1})).resolves.toEqual({sectors: []});
    await Promise.all([result, vi.runAllTimersAsync()]);
    expect(attempts).toBe(2);
  });

  it('recovers an explicit bearer read after a gateway error', async () => {
    let attempts = 0;
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (String(url).endsWith('/health')) return jsonResponse({status: 'ok'});
      attempts += 1;
      return attempts === 1 ? jsonResponse({}, 502) : jsonResponse({id: 7});
    }));
    const result = expect(apiWithBearer('temporary-token', '/auth/me', {_retries: 1})).resolves.toEqual({id: 7});
    await Promise.all([result, vi.runAllTimersAsync()]);
    expect(attempts).toBe(2);
  });

  it.each([
    ['POST', '/trainings/remote/assignments/184/videos/1/progress', 502],
    ['PATCH', '/osgb/assignments/189/end', 502],
    ['POST', '/osgb/assignments', 503],
    ['GET', '/osgb/assignments', 500],
    ['GET', '/trainings/meta', 403],
  ])('does not replay %s %s after HTTP %s', async (method, path, status) => {
    const fetchMock = vi.fn(async () => jsonResponse({}, status));
    vi.stubGlobal('fetch', fetchMock);
    await expect(api(path, {method, _retries: 3})).rejects.toMatchObject({httpStatus: status});
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith(path))).toHaveLength(1);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/health'))).toBe(false);
  });

  it('reports a persistent gateway error once after exhausting the read retry budget', async () => {
    const fetchMock = vi.fn(async (url) => (
      String(url).endsWith('/health') ? jsonResponse({status: 'ok'}) : jsonResponse({}, 502)
    ));
    vi.stubGlobal('fetch', fetchMock);
    const result = expect(api('/auth/me', {_retries: 1})).rejects.toMatchObject({httpStatus: 502});
    await Promise.all([result, vi.runAllTimersAsync()]);
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/me'))).toHaveLength(2);
    const reports = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/eisa/error-reports'));
    expect(reports).toHaveLength(1);
    expect(JSON.parse(reports[0][1].body)).toMatchObject({http_status: 502, http_path: '/auth/me'});
    expect(auth.getAccessToken()).toBeTruthy();
  });

  it('respects an explicit zero retry budget', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({}, 502));
    vi.stubGlobal('fetch', fetchMock);
    await expect(api('/auth/me', {_retries: 0})).rejects.toMatchObject({httpStatus: 502});
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/me'))).toHaveLength(1);
  });

  it('does not retry or report a request cancelled by the caller', async () => {
    const controller = new AbortController();
    const cancelled = new DOMException('Aborted', 'AbortError');
    const fetchMock = vi.fn(async () => {
      controller.abort();
      throw cancelled;
    });
    vi.stubGlobal('fetch', fetchMock);
    await expect(api('/trainings/meta', {signal: controller.signal})).rejects.toBe(cancelled);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it.each(['gateway', 'network'])('preserves the session when refresh has a temporary %s failure after a 401', async (failure) => {
    const token = auth.getAccessToken();
    const lost = vi.fn();
    window.addEventListener('isg:auth-lost', lost);
    const fetchMock = vi.fn(async (url) => {
      if (String(url).endsWith('/auth/refresh')) {
        if (failure === 'network') throw new TypeError('Failed to fetch');
        return jsonResponse({}, 502);
      }
      return jsonResponse({}, 401);
    });
    vi.stubGlobal('fetch', fetchMock);
    const result = expect(api('/auth/me', {_retries: 1})).rejects.toBeInstanceOf(Error);
    await Promise.all([result, vi.runAllTimersAsync()]);
    expect(auth.getAccessToken()).toBe(token);
    expect(auth.refreshCookieMode()).toBe(true);
    expect(lost).not.toHaveBeenCalled();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/auth/refresh'))).toHaveLength(1);
    const reports = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/eisa/error-reports'));
    expect(reports).toHaveLength(1);
    expect(JSON.parse(reports[0][1].body)).toMatchObject({http_method: 'POST', http_path: '/auth/refresh'});
    window.removeEventListener('isg:auth-lost', lost);
  });

  it('keeps a near-expiry session on a refresh outage and can refresh on the next request', async () => {
    const token = tokenWithExpiry(30);
    const freshToken = tokenWithExpiry(3600);
    auth.setAccessToken(token);
    let refreshAttempts = 0;
    vi.stubGlobal('fetch', vi.fn(async (url, options) => {
      if (String(url).endsWith('/auth/refresh')) {
        expect(options.signal).toBeDefined();
        refreshAttempts += 1;
        return refreshAttempts === 1 ? jsonResponse({}, 502) : jsonResponse({access_token: freshToken});
      }
      expect(options.headers.Authorization).toBe(`Bearer ${freshToken}`);
      return jsonResponse({id: 7});
    }));
    await expect(api('/auth/me')).rejects.toMatchObject({httpStatus: 502});
    expect(auth.getAccessToken()).toBe(token);
    expect(auth.refreshCookieMode()).toBe(true);
    await expect(api('/auth/me')).resolves.toEqual({id: 7});
    expect(auth.getAccessToken()).toBe(freshToken);
  });

  it('still clears the session when refresh credentials are rejected', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({}, 401)));
    await expect(api('/auth/me', {_retries: 0})).rejects.toMatchObject({httpStatus: 401});
    expect(auth.getAccessToken()).toBeNull();
    expect(auth.refreshCookieMode()).toBe(false);
  });
});
