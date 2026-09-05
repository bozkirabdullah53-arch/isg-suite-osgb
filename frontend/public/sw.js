const CACHE = "isg-suite-v14";
const CORE = [
  "/manifest.webmanifest",
  "/icon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

function isCacheableAsset(request) {
  if (request.method !== "GET") return false;
  const url = new URL(request.url);
  if (/\/api(\/|$)/i.test(url.pathname)) return false;
  if (/\/(health|docs|openapi|redoc)(\/|$)/i.test(url.pathname)) return false;
  if (url.searchParams.has("token") || url.searchParams.has("access_token")) return false;
  const dest = request.destination;
  if (dest === "document" || dest === "empty") return false;
  if (url.origin !== self.location.origin) return false;
  return (
    CORE.includes(url.pathname) ||
    url.pathname.startsWith("/assets/") ||
    /\.(js|css|svg|png|jpg|jpeg|webp|woff2?)$/i.test(url.pathname)
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function isTransientGateway(status) {
  return status === 502 || status === 503 || status === 504;
}

function isApiRead(request) {
  const method = request.method.toUpperCase();
  return (method === "GET" || method === "HEAD") && /\/api(\/|$)/i.test(new URL(request.url).pathname);
}

async function fetchSafeRead(request) {
  const maxRetries = 2;
  let lastError;
  for (let attempt = 0; attempt <= maxRetries; attempt += 1) {
    if (request.signal?.aborted) {
      throw new DOMException("The request was aborted.", "AbortError");
    }
    try {
      const response = await fetch(request);
      if (!isTransientGateway(response.status) || attempt === maxRetries) return response;
    } catch (error) {
      lastError = error;
      if (request.signal?.aborted || attempt === maxRetries) throw error;
    }
    await sleep(Math.min(700 * (attempt + 1), 1800));
  }
  throw lastError;
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
  const method = event.request.method.toUpperCase();
  if (method !== "GET" && method !== "HEAD") return;

  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;

  if (isApiRead(event.request) || url.pathname === "/health") {
    event.respondWith(fetchSafeRead(event.request));
    return;
  }

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
