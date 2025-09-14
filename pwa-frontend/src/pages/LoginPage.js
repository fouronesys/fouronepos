import React, { useState } from 'react';
import toast from 'react-hot-toast';
import apiService from '../services/apiService';
import LoadingSpinner from '../components/LoadingSpinner';

const LoginPage = ({ onLogin }) => {
  const [formData, setFormData] = useState({
    username: '',
    password: ''
  });
  const [isLoading, setIsLoading] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.username || !formData.password) {
      toast.error('Por favor ingresa usuario y contraseña');
      return;
    }

    setIsLoading(true);
    
    try {
      const response = await apiService.login(formData);
      
      if (response.success) {
        toast.success(response.offline ? 
          'Sesión iniciada offline' : 
          `Bienvenido ${response.user.name}`
        );
        onLogin(response.user);
      } else {
        toast.error(response.message || 'Error al iniciar sesión');
      }
    } catch (error) {
      console.error('Login error:', error);
      toast.error('Error de conexión. Verifica tus credenciales.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDemoLogin = async (role) => {
    const demoCredentials = {
      admin: { username: 'admin', password: 'admin123' },
      cajero: { username: 'cajero1', password: 'cajero123' },
      mesero: { username: 'mesero1', password: 'mesero123' }
    };

    setFormData(demoCredentials[role]);
    
    // Auto-submit after a brief delay
    setTimeout(() => {
      handleSubmit({ preventDefault: () => {} });
    }, 500);
  };

  return (
    <div className="login-container">
      <div className="login-background"></div>
      
      <div className="login-card">
        <div className="login-header">
          <div className="brand-logo">
            <img 
              src="/uploads/logos/logo-white.png" 
              alt="Four One POS" 
              className="logo-image"
            />
          </div>
          <h1 className="brand-title">Four One POS</h1>
          <p className="brand-subtitle">
            Sistema de Punto de Venta
            {!navigator.onLine && (
              <span className="offline-badge">📴 Modo Offline</span>
            )}
          </p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="form-group">
            <label htmlFor="username" className="form-label">
              <i className="bi bi-person"></i>
              Usuario
            </label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleInputChange}
              className="form-control modern-input"
              placeholder="Ingresa tu usuario"
              autoComplete="username"
              disabled={isLoading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="password" className="form-label">
              <i className="bi bi-lock"></i>
              Contraseña
            </label>
            <div className="password-input-group">
              <input
                type={showPassword ? 'text' : 'password'}
                id="password"
                name="password"
                value={formData.password}
                onChange={handleInputChange}
                className="form-control modern-input"
                placeholder="Ingresa tu contraseña"
                autoComplete="current-password"
                disabled={isLoading}
              />
              <button
                type="button"
                className="password-toggle"
                onClick={() => setShowPassword(!showPassword)}
                disabled={isLoading}
              >
                <i className={`bi bi-eye${showPassword ? '-slash' : ''}`}></i>
              </button>
            </div>
          </div>

          <button 
            type="submit" 
            className="btn btn-primary btn-login"
            disabled={isLoading}
          >
            {isLoading ? (
              <LoadingSpinner size="sm" message="Iniciando sesión..." />
            ) : (
              <>
                <i className="bi bi-box-arrow-in-right"></i>
                Iniciar Sesión
              </>
            )}
          </button>
        </form>

        {/* Demo Login Buttons */}
        <div className="demo-section">
          <p className="demo-title">Acceso rápido de prueba:</p>
          <div className="demo-buttons">
            <button 
              onClick={() => handleDemoLogin('admin')}
              className="btn btn-outline-secondary btn-demo"
              disabled={isLoading}
            >
              <i className="bi bi-shield-check"></i>
              Administrador
            </button>
            <button 
              onClick={() => handleDemoLogin('cajero')}
              className="btn btn-outline-secondary btn-demo"
              disabled={isLoading}
            >
              <i className="bi bi-cash-coin"></i>
              Cajero
            </button>
            <button 
              onClick={() => handleDemoLogin('mesero')}
              className="btn btn-outline-secondary btn-demo"
              disabled={isLoading}
            >
              <i className="bi bi-person-badge"></i>
              Mesero
            </button>
          </div>
        </div>

        {/* Offline Info */}
        {!navigator.onLine && (
          <div className="offline-info">
            <i className="bi bi-wifi-off"></i>
            <span>Trabajando offline. Los datos se sincronizarán cuando vuelva la conexión.</span>
          </div>
        )}
      </div>

      <style jsx>{`
        .login-container {
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding: var(--space-md);
          position: relative;
          background: linear-gradient(135deg, var(--bg-primary) 0%, var(--bg-secondary) 100%);
        }

        .login-background {
          position: absolute;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: 
            radial-gradient(circle at 20% 80%, rgba(120, 119, 198, 0.3) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(118, 75, 162, 0.3) 0%, transparent 50%);
          filter: blur(40px);
        }

        .login-card {
          background: var(--glass-bg);
          backdrop-filter: blur(20px);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-2xl);
          padding: var(--space-2xl);
          width: 100%;
          max-width: 400px;
          box-shadow: var(--shadow-xl);
          position: relative;
          z-index: 1;
        }

        .login-header {
          text-align: center;
          margin-bottom: var(--space-xl);
        }

        .brand-logo {
          margin-bottom: var(--space-md);
        }

        .logo-image {
          width: 80px;
          height: 80px;
          object-fit: contain;
          border-radius: var(--radius-lg);
          background: var(--glass-bg);
          padding: var(--space-sm);
        }

        .brand-title {
          color: var(--text-primary);
          font-size: 2rem;
          font-weight: 700;
          margin-bottom: var(--space-sm);
          background: var(--accent-primary);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
          background-clip: text;
        }

        .brand-subtitle {
          color: var(--text-secondary);
          font-size: 0.875rem;
          margin: 0;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
        }

        .offline-badge {
          background: rgba(239, 68, 68, 0.2);
          color: #f87171;
          padding: 2px 8px;
          border-radius: var(--radius-sm);
          font-size: 0.75rem;
          border: 1px solid rgba(239, 68, 68, 0.3);
        }

        .login-form {
          margin-bottom: var(--space-xl);
        }

        .form-group {
          margin-bottom: var(--space-lg);
        }

        .form-label {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          color: var(--text-secondary);
          font-weight: 500;
          margin-bottom: var(--space-sm);
          font-size: 0.875rem;
        }

        .modern-input {
          background: rgba(255, 255, 255, 0.05);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: var(--space-md);
          color: var(--text-primary);
          font-size: 1rem;
          transition: all var(--transition-normal);
          width: 100%;
        }

        .modern-input:focus {
          outline: none;
          border-color: var(--text-accent);
          box-shadow: 0 0 0 3px rgba(96, 165, 250, 0.1);
          background: rgba(255, 255, 255, 0.08);
        }

        .modern-input::placeholder {
          color: var(--text-muted);
        }

        .password-input-group {
          position: relative;
        }

        .password-toggle {
          position: absolute;
          right: var(--space-md);
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: var(--space-xs);
          border-radius: var(--radius-sm);
          transition: color var(--transition-fast);
        }

        .password-toggle:hover {
          color: var(--text-accent);
        }

        .btn-login {
          width: 100%;
          padding: var(--space-md) var(--space-lg);
          background: var(--accent-primary);
          border: none;
          border-radius: var(--radius-lg);
          color: white;
          font-weight: 600;
          font-size: 1rem;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
          transition: all var(--transition-normal);
          box-shadow: var(--shadow-lg);
        }

        .btn-login:hover:not(:disabled) {
          transform: translateY(-2px);
          box-shadow: var(--shadow-xl);
        }

        .btn-login:disabled {
          opacity: 0.6;
          cursor: not-allowed;
        }

        .demo-section {
          text-align: center;
          margin-bottom: var(--space-lg);
        }

        .demo-title {
          color: var(--text-muted);
          font-size: 0.875rem;
          margin-bottom: var(--space-md);
        }

        .demo-buttons {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: var(--space-sm);
        }

        .btn-demo {
          padding: var(--space-sm);
          border: 1px solid var(--glass-border);
          background: rgba(255, 255, 255, 0.03);
          color: var(--text-secondary);
          border-radius: var(--radius-md);
          font-size: 0.75rem;
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 2px;
          transition: all var(--transition-normal);
        }

        .btn-demo:hover:not(:disabled) {
          border-color: var(--text-accent);
          color: var(--text-accent);
          background: rgba(96, 165, 250, 0.1);
        }

        .btn-demo i {
          font-size: 1rem;
        }

        .offline-info {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
          padding: var(--space-md);
          background: rgba(239, 68, 68, 0.1);
          border: 1px solid rgba(239, 68, 68, 0.2);
          border-radius: var(--radius-md);
          color: #f87171;
          font-size: 0.875rem;
          text-align: center;
        }

        @media (max-width: 768px) {
          .login-container {
            padding: var(--space-sm);
          }

          .login-card {
            padding: var(--space-xl);
          }

          .demo-buttons {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default LoginPage;