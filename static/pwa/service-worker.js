const CACHE_NAME = 'hrms-cache-v2';

// Extensiones que siempre deben ir a la red primero (se actualizan con deploys)
const NETWORK_FIRST_EXT = ['.css', '.js', '.html'];

self.addEventListener('install', event => {
  self.skipWaiting(); // Activa el nuevo SW de inmediato sin esperar tabs abiertos
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.add('/'))
  );
});

self.addEventListener('activate', event => {
  // Elimina cachés de versiones anteriores
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
      )
    )
  );
  self.clients.claim(); // Toma control de todos los clientes abiertos
});

self.addEventListener('fetch', event => {
  // Solo interceptar peticiones GET
  if (event.request.method !== 'GET') return;

  const url = new URL(event.request.url);
  const isNetworkFirst =
    url.pathname === '/' ||
    NETWORK_FIRST_EXT.some(ext => url.pathname.endsWith(ext));

  if (isNetworkFirst) {
    // Network-first: va a la red, actualiza caché, y solo usa caché si no hay red
    event.respondWith(
      fetch(event.request)
        .then(response => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return response;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    // Cache-first: para imágenes, fuentes, iconos (no cambian seguido)
    event.respondWith(
      caches.match(event.request).then(cached => cached || fetch(event.request))
    );
  }
});
