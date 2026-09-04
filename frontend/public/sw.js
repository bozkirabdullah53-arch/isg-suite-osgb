const CACHE = "isg-suite-v12-qr-proxy";
// "/" cache'leme — eski index.html / eski bundle'a kilitlenmeyi önler
const CORE = [
  "/manifest.webmanifest",
  "/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

const QR_SERVER_HOST = "api.qrserver.com";
const QR_API_ORIGIN = "https://isg-suite-api-1u9t.onrender.com";

function isCacheableAsset(request) {
  if (request.method !== "GET") return false;
  const url = new URL(request.url);
  // API, auth, dosya, blob — asla cache'leme (token/PII sızıntısı riski)
  if (/\/api(\/|$)/i.test(url.pathname)) return false;
  if (/\/(health|docs|openapi|redoc)(\/|$)/i.test(url.pathname)) return false;
  if (url.searchParams.has("token") || url.searchParams.has("access_token")) return false;
  const dest = request.destination;
  if (dest === "document" || dest === "empty") {
    // Navigasyon: network-first, cache'e yazma
    return false;
  }
  // Yalnızca aynı origin statik çekirdek + build asset'leri
  if (url.origin !== self.location.origin) return false;
  return (
    CORE.includes(url.pathname) ||
    url.pathname.startsWith("/assets/") ||
    /\.(js|css|svg|png|jpg|jpeg|webp|woff2?)$/i.test(url.pathname)
  );
}

function qrProxyRequest(requestUrl) {
  try {
    const url = new URL(requestUrl);
    if (url.hostname.toLowerCase() !== QR_SERVER_HOST) return null;
    if (!/\/v1\/create-qr-code\//i.test(url.pathname)) return null;
    const data = url.searchParams.get("data");
    if (!data) return null;

    const target = new URL("/api/v1/companies/qr-render", QR_API_ORIGIN);
    target.searchParams.set("data", data);
    return target.toString();
  } catch {
    return null;
  }
}

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(CORE)));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== CACHE).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const qrTarget = qrProxyRequest(event.request.url);
  if (qrTarget) {
    // The QR request is normally a cross-origin <img> request (no-cors).
    // Fetch the first-party API image with the same safe, credential-free mode.
    event.respondWith(
      fetch(qrTarget, {
        method: "GET",
        mode: "no-cors",
        credentials: "omit",
        cache: "no-store",
      })
    );
    return;
  }

  const url = new URL(event.request.url);
  // Cross-origin (Render API vb.): SW'ye hiç dokunma — CORS/credentials bozulmasın
  if (url.origin !== self.location.origin) return;
  // Same-origin API / health proxy — SW bypass (body/method bozulmasın)
  if (/\/api(\/|$)/i.test(url.pathname) || url.pathname === "/health") return;

  // API / hassas istekler: yalnızca network, cache yok
  if (!isCacheableAsset(event.request)) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() => caches.match(event.request))
  );
});
