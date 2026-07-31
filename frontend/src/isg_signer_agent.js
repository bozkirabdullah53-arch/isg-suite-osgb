/** Frontend: OSGB Signer local agent + sunucu e-imza hattı. */

export const OSGB_SIGNER_BASE = 'https://127.0.0.1:17000';

function bytesToBase64(pdfBytes) {
  const bytes = pdfBytes instanceof Uint8Array ? pdfBytes : new Uint8Array(pdfBytes);
  let binary = '';
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

export async function probeIsgSigner(timeoutMs = 2500) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(`${OSGB_SIGNER_BASE}/health`, {
      method: 'GET',
      signal: ctrl.signal,
      credentials: 'omit',
    });
    if (!res.ok) return {ok: false, error: `HTTP ${res.status}`};
    const data = await res.json();
    return {ok: data.status === 'healthy', data};
  } catch (e) {
    return {ok: false, error: e.name === 'AbortError' ? 'zaman aşımı' : (e.message || 'ulaşılamadı')};
  } finally {
    clearTimeout(t);
  }
}

export async function listIsgSignerCerts() {
  const res = await fetch(`${OSGB_SIGNER_BASE}/v1/certs`, {credentials: 'omit'});
  if (!res.ok) throw new Error(`Sertifika listesi alınamadı (${res.status})`);
  return res.json();
}

/** Yerel agent ile PAdES imza (PIN sunucuya gitmez). */
export async function signPdfWithIsgSigner(pdfBytes, opts = {}) {
  const pdf_base64 = bytesToBase64(pdfBytes);
  const body = {
    pdf_base64,
    cert_id: opts.certId || (opts.pin ? 'pkcs11' : 'demo'),
    reason: opts.reason || 'OSGB belge imzası',
    location: opts.location || 'Türkiye',
    document_title: opts.documentTitle || null,
    request_token: opts.requestToken || null,
    expected_sha256: opts.expectedSha256 || null,
  };
  if (opts.pin) body.pin = opts.pin;

  const res = await fetch(`${OSGB_SIGNER_BASE}/v1/sign`, {
    method: 'POST',
    credentials: 'omit',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `İmza başarısız (${res.status})`);
  return data;
}

export function downloadBase64Pdf(b64, filename) {
  const bin = atob(b64);
  const arr = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i += 1) arr[i] = bin.charCodeAt(i);
  const blob = new Blob([arr], {type: 'application/pdf'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename || 'imzali.pdf';
  a.click();
  URL.revokeObjectURL(url);
}

/** SHA-256 hex (Web Crypto). */
export async function sha256Hex(buf) {
  const hash = await crypto.subtle.digest('SHA-256', buf);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('');
}
