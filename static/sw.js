// Service Worker para Four One POS - Enhanced Offline Support
const CACHE_VERSION = 'v4-tax-fix';
const STATIC_CACHE = `fourone-static-${CACHE_VERSION}`;
const API_CACHE = `fourone-api-${CACHE_VERSION}`;
const OFFLINE_QUEUE = `fourone-queue-${CACHE_VERSION}`;

// URLs to precache
const staticAssets = [
  '/static/manifest.json',
  '/static/css/pos-style.css',
  '/static/css/logo.png',
  '/static/favicon.ico',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js'
];

// API endpoints to cache
const apiEndpoints = [
  '/api/products',
  '/api/categories', 
  '/api/tables',
  '/api/tax-types',
  '/api/customers'
];

// Install Service Worker
self.addEventListener('install', function(event) {
  console.log('[SW] Installing service worker v4-tax-fix');
  self.skipWaiting();
  
  event.waitUntil(
    Promise.all([
      // Cache static assets
      caches.open(STATIC_CACHE).then(cache => {
        console.log('[SW] Caching static assets');
        return cache.addAll(staticAssets);
      }),
      // Initialize offline queue
      initializeOfflineQueue()
    ])
  );
});

// Activate Service Worker
self.addEventListener('activate', function(event) {
  console.log('[SW] Activating service worker v4-tax-fix');
  self.clients.claim();
  
  event.waitUntil(
    caches.keys().then(function(cacheNames) {
      return Promise.all(
        cacheNames.map(function(cacheName) {
          if (!cacheName.includes(CACHE_VERSION)) {
            console.log('[SW] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  
  // Start periodic sync
  startPeriodicSync();
});

// Enhanced Fetch handler
self.addEventListener('fetch', function(event) {
  const { request } = event;
  const url = new URL(request.url);
  
  // Handle navigation requests (HTML pages)
  if (request.mode === 'navigate') {
    event.respondWith(handleNavigation(request));
    return;
  }
  
  // Handle static assets with cache-first strategy
  if (isStaticAsset(request.url)) {
    event.respondWith(handleStaticAssets(request));
    return;
  }
  
  // Handle API requests with network-first + cache fallback
  if (isApiRequest(request.url)) {
    event.respondWith(handleApiRequest(request));
    return;
  }
  
  // Default: network-first
  event.respondWith(
    fetch(request).catch(() => {
      return new Response('Offline', { status: 503 });
    })
  );
});

// Handle navigation requests
async function handleNavigation(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      // Cache successful navigation
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    // Offline fallback
    const cachedResponse = await caches.match(request);
    if (cachedResponse) return cachedResponse;
    
    // Return offline page or cached POS page
    const posPage = await caches.match('/admin/pos');
    if (posPage) return posPage;
    
    return new Response(`
      <!DOCTYPE html>
      <html>
      <head><title>Offline - Four One POS</title></head>
      <body>
        <h1>Sistema Offline</h1>
        <p>No hay conexión a internet. El sistema funcionará con datos en caché.</p>
        <script>
          setTimeout(() => window.location.reload(), 5000);
        </script>
      </body>
      </html>
    `, {
      headers: { 'Content-Type': 'text/html' }
    });
  }
}

// Handle static assets with cache-first
async function handleStaticAssets(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) return cachedResponse;
  
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    return new Response('Asset not available offline', { status: 503 });
  }
}

// Handle API requests with enhanced offline support
async function handleApiRequest(request) {
  const url = new URL(request.url);
  
  try {
    // Try network first
    const response = await fetch(request);
    if (response.ok) {
      // Cache successful GET requests
      if (request.method === 'GET') {
        const cache = await caches.open(API_CACHE);
        cache.put(request, response.clone());
      }
      
      // Process any queued requests after successful connection
      processOfflineQueue();
    }
    return response;
  } catch (error) {
    console.log('[SW] Network failed for API request:', request.url);
    
    // For GET requests, try cache
    if (request.method === 'GET') {
      const cachedResponse = await caches.match(request);
      if (cachedResponse) {
        console.log('[SW] Serving cached API response:', request.url);
        return cachedResponse;
      }
    }
    
    // For POST/PUT/DELETE, queue the request
    if (['POST', 'PUT', 'DELETE'].includes(request.method)) {
      await queueOfflineRequest(request);
      return new Response(JSON.stringify({
        success: true,
        message: 'Operación guardada para cuando vuelva la conexión',
        offline_queued: true
      }), {
        headers: { 'Content-Type': 'application/json' },
        status: 200
      });
    }
    
    return new Response(JSON.stringify({
      error: 'No hay datos disponibles offline',
      offline: true
    }), {
      headers: { 'Content-Type': 'application/json' },
      status: 503
    });
  }
}

// Initialize offline queue
async function initializeOfflineQueue() {
  const db = await openIndexedDB();
  // Queue is now ready
  console.log('[SW] Offline queue initialized');
}

// Queue offline request
async function queueOfflineRequest(request) {
  try {
    const db = await openIndexedDB();
    const requestData = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: request.method !== 'GET' ? await request.text() : null,
      timestamp: Date.now()
    };
    
    const tx = db.transaction(['requests'], 'readwrite');
    await tx.objectStore('requests').add(requestData);
    console.log('[SW] Queued offline request:', request.url);
    
    // Notify client about queued request
    broadcastToClients('offline-request-queued', requestData);
  } catch (error) {
    console.error('[SW] Failed to queue request:', error);
  }
}

// Process offline queue
async function processOfflineQueue() {
  try {
    const db = await openIndexedDB();
    const tx = db.transaction(['requests'], 'readonly');
    const requests = await tx.objectStore('requests').getAll();
    
    if (requests.length === 0) return;
    
    console.log(`[SW] Processing ${requests.length} queued requests`);
    
    for (const requestData of requests) {
      try {
        const response = await fetch(requestData.url, {
          method: requestData.method,
          headers: requestData.headers,
          body: requestData.body
        });
        
        if (response.ok) {
          // Remove from queue after successful sync
          const deleteTx = db.transaction(['requests'], 'readwrite');
          await deleteTx.objectStore('requests').delete(requestData.timestamp);
          
          console.log('[SW] Synced queued request:', requestData.url);
          broadcastToClients('offline-request-synced', requestData);
        }
      } catch (error) {
        console.log('[SW] Failed to sync request:', requestData.url, error);
      }
    }
  } catch (error) {
    console.error('[SW] Error processing offline queue:', error);
  }
}

// Open IndexedDB
function openIndexedDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('FourOnePOSOffline', 1);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('requests')) {
        const store = db.createObjectStore('requests', { keyPath: 'timestamp' });
        store.createIndex('url', 'url', { unique: false });
      }
    };
  });
}

// Broadcast message to all clients
function broadcastToClients(type, data) {
  self.clients.matchAll().then(clients => {
    clients.forEach(client => {
      client.postMessage({ type, data });
    });
  });
}

// Start periodic sync
function startPeriodicSync() {
  // Process queue every 30 seconds when online
  setInterval(() => {
    if (navigator.onLine) {
      processOfflineQueue();
    }
  }, 30000);
}

// Utility functions
function isStaticAsset(url) {
  return url.includes('/static/') || 
         url.includes('cdn.jsdelivr.net') ||
         url.includes('fonts.googleapis.com') ||
         url.includes('fonts.gstatic.com');
}

function isApiRequest(url) {
  return url.includes('/api/');
}

// Background sync event
self.addEventListener('sync', function(event) {
  if (event.tag === 'offline-sync') {
    event.waitUntil(processOfflineQueue());
  }
});

// Message handler for communication with main thread
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'FORCE_SYNC') {
    processOfflineQueue();
  } else if (event.data && event.data.type === 'CACHE_API_DATA') {
    // Pre-cache API data when requested
    const promises = apiEndpoints.map(endpoint => {
      return fetch(endpoint).then(response => {
        if (response.ok) {
          return caches.open(API_CACHE).then(cache => {
            return cache.put(endpoint, response);
          });
        }
      }).catch(error => console.log('[SW] Failed to cache API data:', endpoint));
    });
    
    Promise.all(promises).then(() => {
      event.ports[0].postMessage({ success: true });
    });
  }
});