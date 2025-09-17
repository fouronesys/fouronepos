// API Service with offline-first strategy
import axios from 'axios';
import offlineStorage from './offlineStorage';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

class ApiService {
  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
      timeout: 10000,
      withCredentials: true,
      headers: {
        'Content-Type': 'application/json'
      }
    });

    this.csrfToken = null;
    this.setupInterceptors();
    this.setupOfflineSync();
  }

  setupInterceptors() {
    // Request interceptor
    this.axiosInstance.interceptors.request.use(
      async (config) => {
        // No need to add Bearer token, Flask uses session cookies
        
        // Add CSRF token for POST/PUT/DELETE requests
        if (['post', 'put', 'delete'].includes(config.method?.toLowerCase())) {
          // Skip CSRF for login endpoint
          if (!config.url?.includes('/auth/login')) {
            try {
              if (!this.csrfToken) {
                this.csrfToken = await this.getCsrfToken();
              }
              if (this.csrfToken) {
                config.headers['X-CSRFToken'] = this.csrfToken;
              }
            } catch (error) {
              console.warn('Failed to get CSRF token for request:', error);
            }
          }
        }
        
        return config;
      },
      (error) => Promise.reject(error)
    );

    // Response interceptor
    this.axiosInstance.interceptors.response.use(
      (response) => {
        // Cache successful GET responses
        if (response.config.method === 'get' && response.data) {
          this.cacheApiResponse(response.config.url, response.data);
        }
        return response;
      },
      async (error) => {
        // Handle CSRF token errors
        if (error.response && (error.response.status === 400 || error.response.status === 403)) {
          const errorMessage = error.response.data?.error || '';
          if (errorMessage.includes('Token de seguridad') || errorMessage.includes('CSRF')) {
            console.log('🔄 CSRF token expired, clearing cache');
            this.clearCsrfToken();
          }
        }
        
        // Handle offline scenarios
        if (!navigator.onLine || error.code === 'NETWORK_ERROR') {
          return this.handleOfflineRequest(error.config);
        }
        
        return Promise.reject(error);
      }
    );
  }

  setupOfflineSync() {
    // Listen for sync events from offline storage
    window.addEventListener('sync-item', async (event) => {
      const item = event.detail;
      try {
        await this.syncOfflineItem(item);
      } catch (error) {
        console.error('Failed to sync item:', error);
      }
    });

    // Auto-sync when coming back online
    window.addEventListener('online', () => {
      setTimeout(() => this.syncPendingOperations(), 2000);
    });
  }

  async handleOfflineRequest(config) {
    console.log('📴 Handling offline request:', config.url);
    
    if (config.method === 'get') {
      // Try to serve from cache
      const cachedData = await this.getCachedData(config.url);
      if (cachedData) {
        return {
          data: cachedData,
          status: 200,
          statusText: 'OK (Cached)',
          headers: {},
          config,
          fromCache: true
        };
      }
    }

    // For POST/PUT/DELETE, queue for later sync
    if (['post', 'put', 'delete'].includes(config.method)) {
      await this.queueOfflineOperation(config);
      
      // Return optimistic response for better UX
      return {
        data: { 
          success: true, 
          message: 'Operación guardada para sincronizar',
          offline: true,
          offline_id: offlineStorage.generateOfflineId()
        },
        status: 200,
        statusText: 'OK (Queued)',
        headers: {},
        config,
        fromCache: false,
        offline: true
      };
    }

    throw new Error('No hay conexión y no hay datos en caché');
  }

  async cacheApiResponse(url, data) {
    try {
      await offlineStorage.cacheApiData(url, data);
    } catch (error) {
      console.warn('Failed to cache API response:', error);
    }
  }

  async getCachedData(url) {
    const storeName = offlineStorage.getStoreNameFromEndpoint(url);
    if (storeName) {
      return await offlineStorage.getAllFromStore(storeName);
    }
    return null;
  }

  async queueOfflineOperation(config) {
    // Include CSRF token for offline operations that will be synced later
    const headers = { ...config.headers };
    if (['POST', 'PUT', 'DELETE'].includes(config.method?.toUpperCase())) {
      if (this.csrfToken) {
        headers['X-CSRFToken'] = this.csrfToken;
      }
    }

    const operation = {
      method: config.method.toUpperCase(),
      url: config.url,
      data: config.data,
      headers: headers,
      timestamp: Date.now()
    };

    await offlineStorage.queueForSync(
      operation.method,
      'api_operations',
      operation
    );
  }

  async syncOfflineItem(item) {
    const { operation, data } = item;
    
    switch (operation) {
      case 'CREATE':
        return await this.syncCreate(data);
      case 'UPDATE':
        return await this.syncUpdate(data);
      case 'DELETE':
        return await this.syncDelete(data);
      default:
        console.warn('Unknown sync operation:', operation);
        return false;
    }
  }

  async syncCreate(data) {
    try {
      const endpoint = this.getEndpointForStore(data.storeName);
      const response = await this.axiosInstance.post(endpoint, data.data);
      
      // Update local data with server ID
      if (response.data && response.data.id) {
        await offlineStorage.updateInStore(data.storeName, {
          ...data.data,
          id: response.data.id,
          offline_created: false,
          synced: true
        });
      }
      
      return true;
    } catch (error) {
      console.error('Sync create failed:', error);
      return false;
    }
  }

  async syncUpdate(data) {
    try {
      const endpoint = this.getEndpointForStore(data.storeName);
      await this.axiosInstance.put(`${endpoint}/${data.data.id}`, data.data);
      
      // Mark as synced in local storage
      await offlineStorage.updateInStore(data.storeName, {
        ...data.data,
        offline_updated: false,
        synced: true
      });
      
      return true;
    } catch (error) {
      console.error('Sync update failed:', error);
      return false;
    }
  }

  async syncDelete(data) {
    try {
      const endpoint = this.getEndpointForStore(data.storeName);
      await this.axiosInstance.delete(`${endpoint}/${data.data.id}`);
      return true;
    } catch (error) {
      console.error('Sync delete failed:', error);
      return false;
    }
  }

  getEndpointForStore(storeName) {
    const endpoints = {
      sales: '/sales',
      products: '/products',
      categories: '/categories',
      tables: '/tables',
      users: '/users'
    };
    return endpoints[storeName] || '/data';
  }

  async syncPendingOperations() {
    if (!navigator.onLine) return;
    
    console.log('🔄 Starting sync of pending operations...');
    await offlineStorage.processSyncQueue();
  }

  // CSRF Token management
  async getCsrfToken() {
    try {
      const response = await this.axiosInstance.get('/csrf');
      this.csrfToken = response.data.csrf_token;
      return this.csrfToken;
    } catch (error) {
      console.warn('Failed to get CSRF token:', error);
      this.csrfToken = null;
      return null;
    }
  }

  // Clear cached CSRF token (useful when session expires)
  clearCsrfToken() {
    this.csrfToken = null;
  }

  // Specific API methods
  async login(credentials) {
    try {
      const response = await this.axiosInstance.post('/auth/login', credentials);
      if (response.data.success && response.data.user) {
        // Store user data locally (session cookies handle authentication)
        localStorage.setItem('user_data', JSON.stringify(response.data.user));
      }
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        // Offline login with cached credentials
        const cachedUser = localStorage.getItem('user_data');
        if (cachedUser) {
          return {
            success: true,
            user: JSON.parse(cachedUser),
            offline: true,
            message: 'Sesión iniciada offline'
          };
        }
      }
      throw error;
    }
  }

  async logout() {
    try {
      await this.axiosInstance.post('/auth/logout');
      localStorage.removeItem('user_data');
      this.clearCsrfToken();
      return { success: true };
    } catch (error) {
      // Clear local data even if API call fails
      localStorage.removeItem('user_data');
      this.clearCsrfToken();
      throw error;
    }
  }

  async getCurrentUser() {
    try {
      const response = await this.axiosInstance.get('/auth/user');
      return response.data;
    } catch (error) {
      throw error;
    }
  }

  async getProducts() {
    try {
      const response = await this.axiosInstance.get('/products');
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        const cachedProducts = await offlineStorage.getProducts();
        return cachedProducts;
      }
      throw error;
    }
  }

  async getCategories() {
    try {
      const response = await this.axiosInstance.get('/categories');
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        const cachedCategories = await offlineStorage.getCategories();
        return cachedCategories;
      }
      throw error;
    }
  }

  async getSales() {
    try {
      const response = await this.axiosInstance.get('/sales');
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        const cachedSales = await offlineStorage.getSales();
        return cachedSales;
      }
      throw error;
    }
  }

  async createSale(saleData) {
    try {
      // Get CSRF token for the sale creation
      const csrfToken = await this.getCsrfToken();
      if (csrfToken) {
        // Add CSRF token to the sale data
        saleData.csrf_token = csrfToken;
      }
      
      const response = await this.axiosInstance.post('/sales', saleData);
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        // Create sale offline
        const offlineSale = await offlineStorage.createSale(saleData);
        return {
          success: true,
          sale: offlineSale,
          offline: true,
          message: 'Venta guardada offline'
        };
      }
      throw error;
    }
  }

  async getTables() {
    try {
      const response = await this.axiosInstance.get('/tables');
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        const cachedTables = await offlineStorage.getTables();
        return cachedTables;
      }
      throw error;
    }
  }

  async getCustomers() {
    try {
      const response = await this.axiosInstance.get('/customers');
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        const cachedCustomers = await offlineStorage.getCustomers();
        return cachedCustomers;
      }
      throw error;
    }
  }

  async getTaxTypes() {
    try {
      const response = await this.axiosInstance.get('/tax-types');
      return response.data;
    } catch (error) {
      if (!navigator.onLine) {
        const cachedTaxTypes = await offlineStorage.getTaxTypes();
        return cachedTaxTypes;
      }
      throw error;
    }
  }

  // Utility methods
  isOnline() {
    return navigator.onLine;
  }

  async getOfflineStatus() {
    const status = offlineStorage.getStatus();
    const storageSize = await offlineStorage.getStorageSize();
    return {
      ...status,
      storageSize: `${(storageSize / 1024 / 1024).toFixed(2)} MB`
    };
  }
}

const apiService = new ApiService();

export default apiService;