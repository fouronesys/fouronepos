// Enhanced Service Worker for Four One POS PWA - Offline-First
const CACHE_VERSION = 'v4-tax-fix';
const STATIC_CACHE = `fourone-static-${CACHE_VERSION}`;
const API_CACHE = `fourone-api-${CACHE_VERSION}`;
const RUNTIME_CACHE = `fourone-runtime-${CACHE_VERSION}`;

// URLs to precache
const staticAssets = [
  '/',
  '/static/js/bundle.js',
  '/static/css/main.css',
  '/manifest.json',
  '/uploads/logos/logo-white.png',
  '/uploads/logos/logo-black.png',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css'
];

// API endpoints to cache
const apiEndpoints = [
  '/api/products',
  '/api/categories', 
  '/api/tables',
  '/api/sales',
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
        return cache.addAll(staticAssets.filter(url => !url.startsWith('http')));
      }),
      // Cache external CDN resources
      caches.open(STATIC_CACHE).then(cache => {
        console.log('[SW] Caching CDN resources');
        const cdnResources = staticAssets.filter(url => url.startsWith('http'));
        return Promise.all(
          cdnResources.map(url => 
            fetch(url)
              .then(response => {
                if (response.ok) {
                  return cache.put(url, response);
                }
              })
              .catch(error => console.log('[SW] Failed to cache CDN resource:', url))
          )
        );
      }),
      // Initialize IndexedDB
      initializeIndexedDB()
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
});

// Enhanced Fetch handler with React Router support
self.addEventListener('fetch', function(event) {
  const { request } = event;
  const url = new URL(request.url);
  
  // Skip chrome-extension and other non-http requests
  if (!request.url.startsWith('http')) {
    return;
  }

  // Handle navigation requests (React Router)
  if (request.mode === 'navigate') {
    event.respondWith(handleNavigation(request));
    return;
  }
  
  // Handle static assets with cache-first strategy
  if (isStaticAsset(request.url)) {
    event.respondWith(handleStaticAssets(request));
    return;
  }
  
  // Handle API requests with network-first + IndexedDB fallback
  if (isApiRequest(request.url)) {
    event.respondWith(handleApiRequest(request));
    return;
  }
  
  // Default: network-first
  event.respondWith(
    fetch(request)
      .then(response => {
        // Cache successful responses in runtime cache
        if (response.ok && request.method === 'GET') {
          const responseClone = response.clone();
          caches.open(RUNTIME_CACHE).then(cache => {
            cache.put(request, responseClone);
          });
        }
        return response;
      })
      .catch(() => {
        // Try to serve from runtime cache
        return caches.match(request).then(response => {
          return response || new Response('Offline - No cached version available', { 
            status: 503,
            statusText: 'Service Unavailable'
          });
        });
      })
  );
});

// Handle navigation requests for React Router
async function handleNavigation(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(RUNTIME_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('[SW] Navigation offline, serving app shell');
    
    // Try to serve cached index.html for React Router
    const cachedResponse = await caches.match('/');
    if (cachedResponse) {
      return cachedResponse;
    }
    
    // Fallback offline page
    return new Response(`
      <!DOCTYPE html>
      <html lang="es">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Four One POS - Offline</title>
        <style>
          body {
            font-family: 'Inter', sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a1a 100%);
            color: #ffffff;
            margin: 0;
            padding: 20px;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
          }
          .offline-container {
            max-width: 400px;
            padding: 40px;
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 20px;
          }
          .icon {
            font-size: 4rem;
            margin-bottom: 20px;
          }
          h1 {
            color: #60a5fa;
            margin-bottom: 10px;
          }
          p {
            color: #e5e7eb;
            margin-bottom: 30px;
          }
          .retry-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 12px;
            cursor: pointer;
            font-weight: 600;
          }
          .retry-btn:hover {
            transform: translateY(-2px);
          }
        </style>
      </head>
      <body>
        <div class="offline-container">
          <div class="icon">📴</div>
          <h1>Modo Offline</h1>
          <p>No hay conexión a internet. El sistema funcionará con datos almacenados localmente.</p>
          <button class="retry-btn" onclick="window.location.reload()">
            Reintentar Conexión
          </button>
        </div>
        <script>
          // Auto-retry when back online
          window.addEventListener('online', () => {
            setTimeout(() => window.location.reload(), 1000);
          });
          
          // Check connection periodically
          setInterval(() => {
            fetch('/api/health')
              .then(() => window.location.reload())
              .catch(() => {});
          }, 30000);
        </script>
      </body>
      </html>
    `, {
      headers: { 
        'Content-Type': 'text/html',
        'Cache-Control': 'no-cache'
      }
    });
  }
}

// Handle static assets with cache-first
async function handleStaticAssets(request) {
  const cachedResponse = await caches.match(request);
  if (cachedResponse) {
    return cachedResponse;
  }
  
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(STATIC_CACHE);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    console.log('[SW] Static asset not available offline:', request.url);
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
        
        // Also store in IndexedDB for better offline access
        if (response.headers.get('content-type')?.includes('application/json')) {
          const data = await response.clone().json();
          await storeInIndexedDB(request.url, data);
        }
      }
      
      // Process any queued requests after successful connection
      setTimeout(() => processOfflineQueue(), 1000);
    }
    return response;
  } catch (error) {
    console.log('[SW] API request failed, trying offline strategy:', request.url);
    
    // For GET requests, try cache then IndexedDB
    if (request.method === 'GET') {
      // Try cache first
      const cachedResponse = await caches.match(request);
      if (cachedResponse) {
        console.log('[SW] Serving cached API response:', request.url);
        return cachedResponse;
      }
      
      // Try IndexedDB
      const indexedData = await getFromIndexedDB(request.url);
      if (indexedData) {
        console.log('[SW] Serving IndexedDB API response:', request.url);
        return new Response(JSON.stringify(indexedData), {
          headers: { 
            'Content-Type': 'application/json',
            'X-Served-By': 'IndexedDB'
          },
          status: 200
        });
      }
    }
    
    // For POST/PUT/DELETE, queue the request
    if (['POST', 'PUT', 'DELETE'].includes(request.method)) {
      await queueOfflineRequest(request);
      return new Response(JSON.stringify({
        success: true,
        message: 'Operación guardada para sincronizar cuando vuelva la conexión',
        offline_queued: true,
        offline_id: generateOfflineId()
      }), {
        headers: { 'Content-Type': 'application/json' },
        status: 200
      });
    }
    
    return new Response(JSON.stringify({
      error: 'No hay datos disponibles offline para esta solicitud',
      offline: true,
      url: request.url
    }), {
      headers: { 'Content-Type': 'application/json' },
      status: 503
    });
  }
}

// IndexedDB Operations
async function initializeIndexedDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('FourOnePOSCache', 2);
    
    request.onerror = () => reject(request.error);
    request.onsuccess = () => resolve(request.result);
    
    request.onupgradeneeded = (event) => {
      const db = event.target.result;
      
      // API Cache store
      if (!db.objectStoreNames.contains('apiCache')) {
        const apiStore = db.createObjectStore('apiCache', { keyPath: 'url' });
        apiStore.createIndex('timestamp', 'timestamp');
      }
      
      // Offline Queue store  
      if (!db.objectStoreNames.contains('offlineQueue')) {
        const queueStore = db.createObjectStore('offlineQueue', { 
          keyPath: 'id',
          autoIncrement: true 
        });
        queueStore.createIndex('timestamp', 'timestamp');
        queueStore.createIndex('url', 'url');
      }
      
      console.log('[SW] IndexedDB initialized');
    };
  });
}

async function storeInIndexedDB(url, data) {
  try {
    const db = await initializeIndexedDB();
    const tx = db.transaction(['apiCache'], 'readwrite');
    const store = tx.objectStore('apiCache');
    
    await store.put({
      url,
      data,
      timestamp: Date.now()
    });
    
    console.log('[SW] Stored in IndexedDB:', url);
  } catch (error) {
    console.warn('[SW] Failed to store in IndexedDB:', error);
  }
}

async function getFromIndexedDB(url) {
  try {
    const db = await initializeIndexedDB();
    const tx = db.transaction(['apiCache'], 'readonly');
    const store = tx.objectStore('apiCache');
    const result = await store.get(url);
    
    if (result) {
      // Check if data is not too old (24 hours)
      const age = Date.now() - result.timestamp;
      if (age < 24 * 60 * 60 * 1000) {
        return result.data;
      }
    }
    
    return null;
  } catch (error) {
    console.warn('[SW] Failed to get from IndexedDB:', error);
    return null;
  }
}

async function queueOfflineRequest(request) {
  try {
    const db = await initializeIndexedDB();
    const requestData = {
      url: request.url,
      method: request.method,
      headers: Object.fromEntries(request.headers.entries()),
      body: request.method !== 'GET' ? await request.text() : null,
      timestamp: Date.now()
    };
    
    const tx = db.transaction(['offlineQueue'], 'readwrite');
    const store = tx.objectStore('offlineQueue');
    await store.add(requestData);
    
    console.log('[SW] Queued offline request:', request.url);
    
    // Notify clients about queued request
    broadcastToClients('offline-request-queued', requestData);
  } catch (error) {
    console.error('[SW] Failed to queue request:', error);
  }
}

async function processOfflineQueue() {
  try {
    const db = await initializeIndexedDB();
    const tx = db.transaction(['offlineQueue'], 'readonly');
    const store = tx.objectStore('offlineQueue');
    const requests = await store.getAll();
    
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
          const deleteTx = db.transaction(['offlineQueue'], 'readwrite');
          const deleteStore = deleteTx.objectStore('offlineQueue');
          await deleteStore.delete(requestData.id);
          
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

// Utility functions
function isStaticAsset(url) {
  return url.includes('/static/') || 
         url.includes('/uploads/') ||
         url.includes('cdn.jsdelivr.net') ||
         url.includes('fonts.googleapis.com') ||
         url.includes('fonts.gstatic.com') ||
         url.endsWith('.js') ||
         url.endsWith('.css') ||
         url.endsWith('.png') ||
         url.endsWith('.jpg') ||
         url.endsWith('.svg') ||
         url.endsWith('.ico');
}

function isApiRequest(url) {
  return url.includes('/api/');
}

function generateOfflineId() {
  return `offline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

function broadcastToClients(type, data) {
  self.clients.matchAll().then(clients => {
    clients.forEach(client => {
      client.postMessage({ type, data });
    });
  });
}

// Background sync event
self.addEventListener('sync', function(event) {
  if (event.tag === 'offline-sync') {
    event.waitUntil(processOfflineQueue());
  }
});

// Periodic background sync (if supported)
self.addEventListener('periodicsync', function(event) {
  if (event.tag === 'content-sync') {
    event.waitUntil(processOfflineQueue());
  }
});

// Message handler for communication with main thread
self.addEventListener('message', function(event) {
  if (event.data && event.data.type === 'FORCE_SYNC') {
    processOfflineQueue().then(() => {
      event.ports[0]?.postMessage({ success: true });
    });
  } else if (event.data && event.data.type === 'CACHE_API_DATA') {
    // Pre-cache API data when requested
    const promises = apiEndpoints.map(endpoint => {
      return fetch(endpoint)
        .then(response => {
          if (response.ok) {
            return caches.open(API_CACHE).then(cache => {
              return cache.put(endpoint, response);
            });
          }
        })
        .catch(error => console.log('[SW] Failed to cache API data:', endpoint));
    });
    
    Promise.all(promises).then(() => {
      event.ports[0]?.postMessage({ success: true });
    });
  } else if (event.data && event.data.type === 'GET_CACHE_STATUS') {
    // Return cache status
    caches.keys().then(cacheNames => {
      event.ports[0]?.postMessage({ 
        caches: cacheNames,
        version: CACHE_VERSION
      });
    });
  }
});

// Push notification handler (for future use)
self.addEventListener('push', function(event) {
  if (event.data) {
    const data = event.data.json();
    const title = data.title || 'Four One POS';
    const options = {
      body: data.body,
      icon: '/uploads/logos/logo-white.png',
      badge: '/uploads/logos/logo-white.png',
      tag: data.tag || 'notification',
      data: data.url || '/'
    };
    
    event.waitUntil(
      self.registration.showNotification(title, options)
    );
  }
});

// Notification click handler
self.addEventListener('notificationclick', function(event) {
  event.notification.close();
  
  event.waitUntil(
    clients.openWindow(event.notification.data || '/')
  );
});

console.log('[SW] Four One POS Service Worker v3.0 loaded successfully');