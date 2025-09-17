// Enhanced Offline Storage for Four One POS
import { openDB } from 'idb';

const DB_NAME = 'FourOnePOSOffline';
const DB_VERSION = 2;

// Database Schema
const STORES = {
  sales: 'sales',
  products: 'products', 
  categories: 'categories',
  tables: 'tables',
  customers: 'customers',
  taxTypes: 'taxTypes',
  users: 'users',
  pendingSync: 'pendingSync',
  settings: 'settings'
};

class OfflineStorage {
  constructor() {
    this.db = null;
    this.syncQueue = [];
    this.isOnline = navigator.onLine;
    this.initializeOnlineDetection();
  }

  async init() {
    this.db = await openDB(DB_NAME, DB_VERSION, {
      upgrade(db, oldVersion, newVersion, transaction) {
        // Sales store
        if (!db.objectStoreNames.contains(STORES.sales)) {
          const salesStore = db.createObjectStore(STORES.sales, { 
            keyPath: 'id', 
            autoIncrement: true 
          });
          salesStore.createIndex('timestamp', 'timestamp');
          salesStore.createIndex('status', 'status');
          salesStore.createIndex('offline_id', 'offline_id', { unique: false });
        }

        // Products store
        if (!db.objectStoreNames.contains(STORES.products)) {
          const productsStore = db.createObjectStore(STORES.products, { keyPath: 'id' });
          productsStore.createIndex('category_id', 'category_id');
          productsStore.createIndex('name', 'name');
        }

        // Categories store
        if (!db.objectStoreNames.contains(STORES.categories)) {
          db.createObjectStore(STORES.categories, { keyPath: 'id' });
        }

        // Tables store
        if (!db.objectStoreNames.contains(STORES.tables)) {
          const tablesStore = db.createObjectStore(STORES.tables, { keyPath: 'id' });
          tablesStore.createIndex('status', 'status');
        }

        // Users store
        if (!db.objectStoreNames.contains(STORES.users)) {
          db.createObjectStore(STORES.users, { keyPath: 'id' });
        }

        // Pending sync operations
        if (!db.objectStoreNames.contains(STORES.pendingSync)) {
          const pendingSyncStore = db.createObjectStore(STORES.pendingSync, { 
            keyPath: 'id',
            autoIncrement: true 
          });
          pendingSyncStore.createIndex('operation', 'operation');
          pendingSyncStore.createIndex('timestamp', 'timestamp');
        }

        // Customers store
        if (!db.objectStoreNames.contains(STORES.customers)) {
          const customersStore = db.createObjectStore(STORES.customers, { keyPath: 'id' });
          customersStore.createIndex('name', 'name');
          customersStore.createIndex('rnc', 'rnc');
        }

        // Tax Types store
        if (!db.objectStoreNames.contains(STORES.taxTypes)) {
          const taxTypesStore = db.createObjectStore(STORES.taxTypes, { keyPath: 'id' });
          taxTypesStore.createIndex('name', 'name');
          taxTypesStore.createIndex('rate', 'rate');
        }

        // Settings store
        if (!db.objectStoreNames.contains(STORES.settings)) {
          db.createObjectStore(STORES.settings, { keyPath: 'key' });
        }
      }
    });

    console.log('✅ Offline storage initialized');
    return this.db;
  }

  initializeOnlineDetection() {
    window.addEventListener('online', () => {
      this.isOnline = true;
      this.processSyncQueue();
    });

    window.addEventListener('offline', () => {
      this.isOnline = false;
    });
  }

  // CRUD Operations with offline-first strategy
  async getAllFromStore(storeName) {
    if (!this.db) await this.init();
    const tx = this.db.transaction(storeName, 'readonly');
    return await tx.objectStore(storeName).getAll();
  }

  async getFromStore(storeName, id) {
    if (!this.db) await this.init();
    const tx = this.db.transaction(storeName, 'readonly');
    return await tx.objectStore(storeName).get(id);
  }

  async addToStore(storeName, data) {
    if (!this.db) await this.init();
    
    // Add offline timestamp and ID for sync tracking
    const itemWithMeta = {
      ...data,
      offline_created: true,
      offline_id: this.generateOfflineId(),
      offline_timestamp: Date.now()
    };

    const tx = this.db.transaction(storeName, 'readwrite');
    const result = await tx.objectStore(storeName).add(itemWithMeta);
    
    // Queue for sync when online
    await this.queueForSync('CREATE', storeName, itemWithMeta);
    
    return result;
  }

  async updateInStore(storeName, data) {
    if (!this.db) await this.init();
    
    const itemWithMeta = {
      ...data,
      offline_updated: true,
      offline_timestamp: Date.now()
    };

    const tx = this.db.transaction(storeName, 'readwrite');
    const result = await tx.objectStore(storeName).put(itemWithMeta);
    
    // Queue for sync when online
    await this.queueForSync('UPDATE', storeName, itemWithMeta);
    
    return result;
  }

  async deleteFromStore(storeName, id) {
    if (!this.db) await this.init();
    
    const tx = this.db.transaction(storeName, 'readwrite');
    const result = await tx.objectStore(storeName).delete(id);
    
    // Queue for sync when online
    await this.queueForSync('DELETE', storeName, { id });
    
    return result;
  }

  // Sync queue management
  async queueForSync(operation, storeName, data) {
    if (!this.db) await this.init();
    
    const syncItem = {
      operation,
      storeName,
      data,
      timestamp: Date.now(),
      retries: 0,
      maxRetries: 3
    };

    const tx = this.db.transaction(STORES.pendingSync, 'readwrite');
    await tx.objectStore(STORES.pendingSync).add(syncItem);
    
    console.log(`📝 Queued ${operation} operation for ${storeName}:`, data);
    
    // Try to sync immediately if online
    if (this.isOnline) {
      setTimeout(() => this.processSyncQueue(), 1000);
    }
  }

  async processSyncQueue() {
    if (!this.isOnline || !this.db) return;

    console.log('🔄 Processing sync queue...');
    
    const tx = this.db.transaction(STORES.pendingSync, 'readonly');
    const pendingItems = await tx.objectStore(STORES.pendingSync).getAll();
    
    if (pendingItems.length === 0) return;

    for (const item of pendingItems) {
      try {
        const success = await this.syncItem(item);
        if (success) {
          await this.removeFromSyncQueue(item.id);
          console.log(`✅ Synced ${item.operation} operation for ${item.storeName}`);
        } else {
          await this.incrementRetryCount(item.id);
        }
      } catch (error) {
        console.error('❌ Sync failed for item:', item, error);
        await this.incrementRetryCount(item.id);
      }
    }
  }

  async syncItem(item) {
    // This will be called by the API service to sync with server
    // Return true if sync successful, false if failed
    const event = new CustomEvent('sync-item', { 
      detail: item,
      bubbles: true 
    });
    window.dispatchEvent(event);
    
    // For now, return true to simulate successful sync
    // Real implementation will depend on API response
    return true;
  }

  async removeFromSyncQueue(id) {
    const tx = this.db.transaction(STORES.pendingSync, 'readwrite');
    await tx.objectStore(STORES.pendingSync).delete(id);
  }

  async incrementRetryCount(id) {
    const tx = this.db.transaction(STORES.pendingSync, 'readwrite');
    const store = tx.objectStore(STORES.pendingSync);
    const item = await store.get(id);
    
    if (item) {
      item.retries += 1;
      if (item.retries >= item.maxRetries) {
        console.error('❌ Max retries reached for sync item:', item);
        // Could move to failed queue or alert user
      }
      await store.put(item);
    }
  }

  generateOfflineId() {
    return `offline_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  }

  // Specific business logic methods
  async createSale(saleData) {
    const sale = {
      ...saleData,
      id: this.generateOfflineId(),
      status: 'pending_sync',
      created_at: new Date().toISOString(),
      offline_sale: true
    };
    
    return await this.addToStore(STORES.sales, sale);
  }

  async getSales() {
    return await this.getAllFromStore(STORES.sales);
  }

  async updateSaleStatus(saleId, status) {
    const sale = await this.getFromStore(STORES.sales, saleId);
    if (sale) {
      sale.status = status;
      sale.updated_at = new Date().toISOString();
      return await this.updateInStore(STORES.sales, sale);
    }
  }

  async getProducts() {
    return await this.getAllFromStore(STORES.products);
  }

  async getCategories() {
    return await this.getAllFromStore(STORES.categories);
  }

  async getTables() {
    return await this.getAllFromStore(STORES.tables);
  }

  async getCustomers() {
    return await this.getAllFromStore(STORES.customers);
  }

  async getTaxTypes() {
    return await this.getAllFromStore(STORES.taxTypes);
  }

  async cacheApiData(endpoint, data) {
    // Cache data from API calls
    const storeName = this.getStoreNameFromEndpoint(endpoint);
    if (storeName && Array.isArray(data)) {
      const tx = this.db.transaction(storeName, 'readwrite');
      const store = tx.objectStore(storeName);
      
      // Clear existing data and add new
      await store.clear();
      for (const item of data) {
        await store.add(item);
      }
      console.log(`📦 Cached ${data.length} items in ${storeName}`);
    }
  }

  getStoreNameFromEndpoint(endpoint) {
    if (endpoint.includes('/products')) return STORES.products;
    if (endpoint.includes('/categories')) return STORES.categories;
    if (endpoint.includes('/tables')) return STORES.tables;
    if (endpoint.includes('/customers')) return STORES.customers;
    if (endpoint.includes('/tax-types')) return STORES.taxTypes;
    if (endpoint.includes('/sales')) return STORES.sales;
    return null;
  }

  // Settings management
  async getSetting(key) {
    if (!this.db) await this.init();
    const tx = this.db.transaction(STORES.settings, 'readonly');
    const result = await tx.objectStore(STORES.settings).get(key);
    return result?.value;
  }

  async setSetting(key, value) {
    if (!this.db) await this.init();
    const tx = this.db.transaction(STORES.settings, 'readwrite');
    await tx.objectStore(STORES.settings).put({ key, value });
  }

  // Status and diagnostics
  getStatus() {
    return {
      isOnline: this.isOnline,
      dbReady: !!this.db,
      queueSize: this.syncQueue.length
    };
  }

  async getStorageSize() {
    if (!this.db) return 0;
    
    let totalSize = 0;
    for (const storeName of Object.values(STORES)) {
      try {
        const items = await this.getAllFromStore(storeName);
        totalSize += JSON.stringify(items).length;
      } catch (error) {
        console.warn(`Could not get size for store ${storeName}:`, error);
      }
    }
    
    return totalSize;
  }
}

// Singleton instance
const offlineStorage = new OfflineStorage();

export default offlineStorage;