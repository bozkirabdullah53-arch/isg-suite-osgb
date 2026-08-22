import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {uploadFile} from './api.js';
import {clearAccessToken} from './auth_session.js';

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
