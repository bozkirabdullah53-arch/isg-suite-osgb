const CACHE = "isg-suite-v2";
const CORE = ["/", "/manifest.webmanifest", "/icon.svg"];

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
