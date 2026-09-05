import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api, uploadFile} from './api.js';
import {clearAccessToken, getAccessToken} from './auth_session.js';

function tokenWithExpiry(exp) {
  const payload = btoa(JSON.stringify({exp})).replace(/=/g, '');
  return 'header.' + payload + '.signature';
}

function jsonResponse(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {'Content-Type': 'application/json'},
  });
}

describe('uploadFile oturum sürekliliği', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearAccessToken();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('uzun arka arkaya yüklemelerde süresi yaklaşan tokenı önceden yeniler', async () => {
    localStorage.setItem('isg_token', tokenWithExpiry(Math.floor(Date.now() / 1000) + 30));
    const fetchMock = vi.fn(async (url, options = {}) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/health')) return jsonResponse({status: 'ok'});
      if (requestUrl.endsWith('/auth/refresh')) return jsonResponse({access_token: 'fresh-token'});
      expect(options.headers.Authorization).toBe('Bearer fresh-token');
      expect(options.body).toBeInstanceOf(FormData);
      return jsonResponse({id: 3}, 201);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      uploadFile('/trainings/remote/catalog/sections/3/videos', new File(['video'], 'Ders_03.mp4'), {title: 'Ders_03'}),
    ).resolves.toMatchObject({id: 3});
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/auth/refresh'))).toBe(true);
  });

  it('401 sonrasında FormData’yı yeniden kurup yenilenen tokenla tek kez dener', async () => {
    const initialToken = tokenWithExpiry(Math.floor(Date.now() / 1000) + 3600);
    localStorage.setItem('isg_token', initialToken);
    let uploadAttempts = 0;
    const uploadHeaders = [];
    const fetchMock = vi.fn(async (url, options = {}) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/health')) return jsonResponse({status: 'ok'});
      if (requestUrl.endsWith('/auth/refresh')) return jsonResponse({access_token: 'fresh-token'});
      uploadAttempts += 1;
      uploadHeaders.push(options.headers.Authorization);
      expect(options.body).toBeInstanceOf(FormData);
      return uploadAttempts === 1 ? jsonResponse({detail: 'Not authenticated'}, 401) : jsonResponse({id: 4}, 201);
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(
      uploadFile('/trainings/remote/catalog/sections/3/videos', new File(['video'], 'Ders_03.mp4'), {title: 'Ders_03'}),
    ).resolves.toMatchObject({id: 4});
    expect(uploadAttempts).toBe(2);
    expect(uploadHeaders).toEqual(['Bearer ' + initialToken, 'Bearer fresh-token']);
  });
});

describe('api güvenli yeniden deneme politikası', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearAccessToken();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('GET isteğini geçici gateway hatasından sonra yeniden dener', async () => {
    let readAttempts = 0;
    const fetchMock = vi.fn(async (url) => {
      if (String(url).endsWith('/health')) return jsonResponse({status: 'ok'});
      readAttempts += 1;
      return readAttempts === 1 ? jsonResponse({detail: 'temporary'}, 502) : jsonResponse({ok: true});
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/trainings/meta', {_retries: 1})).resolves.toEqual({ok: true});
    expect(readAttempts).toBe(2);
  });

  it.each(['POST', 'PATCH', 'DELETE'])('%s ağ hatasında yazma isteğini yeniden göndermez', async (method) => {
    const fetchMock = vi.fn(async () => {
      throw new TypeError('Failed to fetch');
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/osgb/assignments/189/end', {method, _retries: 3})).rejects.toThrow();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('kullanıcının iptal ettiği GET isteğini yeniden denemez', async () => {
    const controller = new AbortController();
    controller.abort();
    const fetchMock = vi.fn(async (_url, options) => {
      if (options.signal?.aborted) throw new DOMException('Aborted', 'AbortError');
      return jsonResponse({ok: true});
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/trainings/meta', {signal: controller.signal, _retries: 3})).rejects.toMatchObject({name: 'AbortError'});
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('/auth/me geçici 502 sonrasında oturum tokenını korur', async () => {
    const token = tokenWithExpiry(Math.floor(Date.now() / 1000) + 3600);
    sessionStorage.setItem('isg_token', token);
    let authAttempts = 0;
    const fetchMock = vi.fn(async (url) => {
      if (String(url).endsWith('/health')) return jsonResponse({status: 'ok'});
      authAttempts += 1;
      return authAttempts === 1 ? jsonResponse({detail: 'temporary'}, 502) : jsonResponse({id: 1});
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/auth/me', {_retries: 1})).resolves.toEqual({id: 1});
    expect(getAccessToken()).toBe(token);
  });
});
