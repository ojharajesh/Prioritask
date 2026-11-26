const CACHE_NAME = 'prioritask-shell-v1';
const ASSETS = [
  '/',
  'https://cdn.tailwindcss.com',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(ASSETS).catch(() => {});
    })
  );
  self.skipWaiting();
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) return caches.delete(k);
        })
      );
    })
  );
  self.clients.claim();
});

// Stale-While-Revalidate for app shell (Opens instantly in 0.1s!)
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Never cache API requests - always network for fresh live data
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  if (e.request.method === 'GET') {
    e.respondWith(
      caches.match(e.request).then((cached) => {
        const networkFetch = fetch(e.request)
          .then((response) => {
            if (response && response.status === 200) {
              const resClone = response.clone();
              caches.open(CACHE_NAME).then((cache) => cache.put(e.request, resClone));
            }
            return response;
          })
          .catch(() => cached);

        // Return cached shell immediately if available (0.1s launch!), else network
        return cached || networkFetch;
      })
    );
  }
});
