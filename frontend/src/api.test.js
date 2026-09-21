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
    // Oturumlu isteklerin yeniden deneme politikası geçerli tokenla test edilir.
    sessionStorage.setItem('isg_token', tokenWithExpiry(Math.floor(Date.now() / 1000) + 3600));
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
    const fetchMock = vi.fn(async (url) => {
      // Token'lı oturumda ağ hatası EİSA istemci raporu da tetikler (ayrı fetch);
      // sayım yalnız hedef yazma isteği üzerinden yapılır.
      if (String(url).endsWith('/eisa/error-reports') || String(url).endsWith('/health')) {
        return jsonResponse({});
      }
      throw new TypeError('Failed to fetch');
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/osgb/assignments/189/end', {method, _retries: 3})).rejects.toThrow();
    const writeCalls = fetchMock.mock.calls.filter(([url]) => String(url).endsWith('/osgb/assignments/189/end'));
    expect(writeCalls).toHaveLength(1);
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

describe('anonim oturum davranışı', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    clearAccessToken();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('anonimken veri uçlarını ister ama boşuna refresh denemez', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({}, 401));
    vi.stubGlobal('fetch', fetchMock);

    // Çerezle doğrulanan oturumlar ve mock'lu akışlar token'sız da meşru yanıt
    // alabildiği için istek engellenmez; 401 kararını sunucu verir.
    await expect(api('/dashboard/summary', {_retries: 0})).rejects.toMatchObject({httpStatus: 401});
    await expect(api('/trainings/premium-policy', {_retries: 0})).rejects.toMatchObject({httpStatus: 401});

    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls.some((url) => url.endsWith('/dashboard/summary'))).toBe(true);
    expect(urls.some((url) => url.endsWith('/trainings/premium-policy'))).toBe(true);
    // Gönderilecek token/çerez işareti yokken refresh her zaman 401 döner.
    expect(urls.some((url) => url.endsWith('/auth/refresh'))).toBe(false);
  });

  it('anonimken genel auth/legal yollarına izin verir', async () => {
    const fetchMock = vi.fn(async (url) => {
      if (String(url).endsWith('/health')) return jsonResponse({status: 'ok'});
      return jsonResponse({access_token: tokenWithExpiry(Math.floor(Date.now() / 1000) + 3600)});
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/auth/login', {method: 'POST', body: '{}'})).resolves.toMatchObject({access_token: expect.any(String)});
    await expect(api('/legal/documents', {_retries: 0})).resolves.toMatchObject({access_token: expect.any(String)});
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('refresh cookie modunda 401 sonrası yenileyip isteği tekrarlar', async () => {
    localStorage.setItem('isg_refresh_cookie', '1');
    let meCalls = 0;
    const fetchMock = vi.fn(async (url) => {
      const requestUrl = String(url);
      if (requestUrl.endsWith('/health')) return jsonResponse({status: 'ok'});
      if (requestUrl.endsWith('/auth/refresh')) {
        return jsonResponse({access_token: tokenWithExpiry(Math.floor(Date.now() / 1000) + 3600)});
      }
      meCalls += 1;
      if (meCalls === 1) return jsonResponse({}, 401);
      return jsonResponse({id: 9});
    });
    vi.stubGlobal('fetch', fetchMock);

    await expect(api('/auth/me', {_retries: 0})).resolves.toEqual({id: 9});
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls.some((url) => url.endsWith('/auth/refresh'))).toBe(true);
    expect(meCalls).toBe(2);
  });
});
