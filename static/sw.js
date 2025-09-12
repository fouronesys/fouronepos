// Service Worker para Four One POS
const CACHE_NAME = 'fourone-pos-v1';
const STATIC_CACHE = 'fourone-static-v1';

// URLs to precache
const staticAssets = [
  '/static/manifest.json',
  '/static/css/logo.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// Install Service Worker
self.addEventListener('install', function(event) {
  self.skipWaiting(); // Force activation immediately
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(function(cache) {
        return cache.addAll(staticAssets);
      })
  );
});

// Activate Service Worker
self.addEventListener('activate', function(event) {
  self.clients.claim(); // Take control of all clients immediately
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (cacheName !== CACHE_NAME && cacheName !== STATIC_CACHE) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Fetch handler with network-first for navigation and cache-first for static assets
self.addEventListener('fetch', function(event) {
  const { request } = event;
  
  // Network-first for navigation requests (HTML pages)
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Don't cache authenticated responses
          if (response.ok && !request.url.includes('/auth/') && !request.url.includes('/admin/')) {
            const responseClone = response.clone();
            caches.open(CACHE_NAME).then(cache => {
              cache.put(request, responseClone);
            });
          }
          return response;
        })
        .catch(() => {
          // Offline fallback - redirect to login
          return caches.match('/auth/login') || new Response('Offline - Please check your connection');
        })
    );
    return;
  }
  
  // Cache-first for static assets
  if (request.url.includes('/static/') || request.url.includes('cdn.jsdelivr.net')) {
    event.respondWith(
      caches.match(request)
        .then(response => {
          if (response) {
            return response;
          }
          return fetch(request).then(response => {
            if (response.ok) {
              const responseClone = response.clone();
              caches.open(STATIC_CACHE).then(cache => {
                cache.put(request, responseClone);
              });
            }
            return response;
          });
        })
    );
    return;
  }
  
  // Network-first for API requests
  event.respondWith(
    fetch(request)
      .catch(() => {
        return new Response(JSON.stringify({ error: 'Offline' }), {
          headers: { 'Content-Type': 'application/json' },
          status: 503
        });
      })
  );
});