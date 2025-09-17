// Script para limpiar completamente todas las cachés del POS
console.log('🧹 Limpiando todas las cachés del POS...');

// 1. Limpiar Service Worker Cache
if ('serviceWorker' in navigator && 'caches' in window) {
  caches.keys().then(function(cacheNames) {
    console.log('💾 Cachés encontradas:', cacheNames);
    return Promise.all(
      cacheNames.map(function(cacheName) {
        console.log('🗑️ Eliminando caché:', cacheName);
        return caches.delete(cacheName);
      })
    );
  }).then(function() {
    console.log('✅ Service Worker caches limpiadas');
  });
}

// 2. Limpiar LocalStorage
try {
  localStorage.clear();
  console.log('✅ LocalStorage limpiado');
} catch (e) {
  console.log('⚠️ No se pudo limpiar LocalStorage:', e);
}

// 3. Limpiar SessionStorage  
try {
  sessionStorage.clear();
  console.log('✅ SessionStorage limpiado');
} catch (e) {
  console.log('⚠️ No se pudo limpiar SessionStorage:', e);
}

// 4. Limpiar IndexedDB (para PWA)
if ('indexedDB' in window) {
  // Limpiar base de datos del POS offline
  const deleteDB = indexedDB.deleteDatabase('FourOnePOSOffline');
  deleteDB.onsuccess = function() {
    console.log('✅ IndexedDB (FourOnePOSOffline) limpiada');
  };
  deleteDB.onerror = function() {
    console.log('⚠️ Error limpiando IndexedDB');
  };
}

// 5. Unregister Service Workers
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.getRegistrations().then(function(registrations) {
    for(let registration of registrations) {
      registration.unregister().then(function() {
        console.log('✅ Service Worker desregistrado');
      });
    }
  });
}

// 6. Forzar reload después de limpiar
setTimeout(() => {
  console.log('🔄 Recargando página para aplicar cambios...');
  window.location.reload(true); // Hard reload
}, 1000);