import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from 'react-query';
import { Toaster } from 'react-hot-toast';

// Services
import offlineStorage from './services/offlineStorage';
import apiService from './services/apiService';

// Components
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import POSPage from './pages/POSPage';
import TablesPage from './pages/TablesPage';
import OfflineIndicator from './components/OfflineIndicator';
import LoadingSpinner from './components/LoadingSpinner';

// Styles
import './css/enhanced-design.css';
import './css/pos-style.css';
import './css/theme-system.css';

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry if offline
        if (!navigator.onLine) return false;
        return failureCount < 3;
      },
      staleTime: 5 * 60 * 1000, // 5 minutes
      cacheTime: 10 * 60 * 1000, // 10 minutes
    },
  },
});

function App() {
  const [isInitialized, setIsInitialized] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [user, setUser] = useState(null);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);

  useEffect(() => {
    initializeApp();
    setupOfflineDetection();
    setupServiceWorker();
  }, []);

  const initializeApp = async () => {
    try {
      // Initialize offline storage
      await offlineStorage.init();
      
      // Check for existing authentication
      const token = localStorage.getItem('auth_token');
      const userData = localStorage.getItem('user_data');
      
      if (token && userData) {
        setIsAuthenticated(true);
        setUser(JSON.parse(userData));
      }
      
      setIsInitialized(true);
    } catch (error) {
      console.error('Failed to initialize app:', error);
      setIsInitialized(true);
    }
  };

  const setupOfflineDetection = () => {
    const handleOnline = () => {
      setIsOffline(false);
      console.log('🌐 App is back online');
      // Trigger sync
      setTimeout(() => apiService.syncPendingOperations(), 1000);
    };

    const handleOffline = () => {
      setIsOffline(true);
      console.log('📴 App is now offline');
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  };

  const setupServiceWorker = () => {
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
          .then((registration) => {
            console.log('✅ SW registered: ', registration);
          })
          .catch((registrationError) => {
            console.log('❌ SW registration failed: ', registrationError);
          });
      });
    }
  };

  const handleLogin = (userData) => {
    setIsAuthenticated(true);
    setUser(userData);
  };

  const handleLogout = () => {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    setIsAuthenticated(false);
    setUser(null);
  };

  // Protected Route Component
  const ProtectedRoute = ({ children }) => {
    if (!isAuthenticated) {
      return <Navigate to="/login" replace />;
    }
    return children;
  };

  // Role-based redirects
  const getDefaultRoute = () => {
    if (!user) return '/login';
    
    switch (user.role) {
      case 'ADMINISTRADOR':
        return '/dashboard';
      case 'CAJERO':
        return '/pos';
      case 'MESERO':
        return '/tables';
      default:
        return '/login';
    }
  };

  if (!isInitialized) {
    return (
      <div className="min-vh-100 d-flex align-items-center justify-content-center">
        <LoadingSpinner message="Inicializando aplicación..." />
      </div>
    );
  }

  return (
    <QueryClientProvider client={queryClient}>
      <Router>
        <div className="App">
          {/* Offline Indicator */}
          <OfflineIndicator isOffline={isOffline} />
          
          {/* Toast Notifications */}
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 4000,
              style: {
                background: 'var(--bg-card)',
                color: 'var(--text-primary)',
                border: '1px solid var(--glass-border)',
              },
            }}
          />

          {/* Routes */}
          <Routes>
            {/* Login Route */}
            <Route 
              path="/login" 
              element={
                isAuthenticated ? 
                <Navigate to={getDefaultRoute()} replace /> :
                <LoginPage onLogin={handleLogin} />
              } 
            />

            {/* Dashboard Route */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <DashboardPage user={user} onLogout={handleLogout} />
                </ProtectedRoute>
              } 
            />

            {/* POS Route */}
            <Route 
              path="/pos" 
              element={
                <ProtectedRoute>
                  <POSPage user={user} onLogout={handleLogout} />
                </ProtectedRoute>
              } 
            />

            {/* Tables Route */}
            <Route 
              path="/tables" 
              element={
                <ProtectedRoute>
                  <TablesPage user={user} onLogout={handleLogout} />
                </ProtectedRoute>
              } 
            />

            {/* Default Route */}
            <Route 
              path="/" 
              element={<Navigate to={getDefaultRoute()} replace />} 
            />

            {/* Catch all route */}
            <Route 
              path="*" 
              element={<Navigate to={getDefaultRoute()} replace />} 
            />
          </Routes>
        </div>
      </Router>
    </QueryClientProvider>
  );
}

export default App;