const CACHE_VERSION = "metropole-verte-v7";
const APP_SHELL = [
  "/",
  "/index.html",
  "/login.html",
  "/register.html",
  "/offline.html",
  "/manifest.webmanifest",
  "/icons/pwa-icon.svg",
  "/icons/pwa-icon-192.png",
  "/icons/pwa-icon-512.png",
  "/icons/pwa-maskable-512.png"
];
const PRIVATE_NAVIGATION_PATHS = new Set([
  "/admin-dashboard.html",
  "/admin-form.html",
  "/admin-station.html",
  "/dashboard.html",
  "/mobile-session.html",
  "/profile.html",
  "/reservation.html",
  "/technician-dashboard.html"
]);

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_VERSION)
      .then((cache) => Promise.allSettled(
        APP_SHELL.map((url) => fetch(url).then((response) => {
          if (response.ok) {
            return cache.put(url, response);
          }
          return null;
        }))
      ))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== CACHE_VERSION).map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.pathname.startsWith("/api/")) {
    return;
  }

  if (url.pathname.startsWith("/assets/")) {
    event.respondWith(
      caches.match(request)
        .then((cached) => cached || fetch(request).then((response) => {
          if (!response || response.status !== 200) {
            return response;
          }
          const copy = response.clone();
          caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          return response;
        }))
    );
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          if (!PRIVATE_NAVIGATION_PATHS.has(url.pathname) && response.ok) {
            const copy = response.clone();
            caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
          }
          return response;
        })
        .catch(() => {
          if (PRIVATE_NAVIGATION_PATHS.has(url.pathname)) {
            return caches.match("/offline.html");
          }
          return caches.match(request).then((cached) => cached || caches.match("/offline.html"));
        })
    );
    return;
  }

  event.respondWith(
    caches.match(request)
      .then((cached) => cached || fetch(request).then((response) => {
        if (!response || response.status !== 200 || response.type === "opaque") {
          return response;
        }
        const copy = response.clone();
        caches.open(CACHE_VERSION).then((cache) => cache.put(request, copy));
        return response;
      }))
  );
});
