import React, { useState, useEffect } from 'react';
import { useQuery } from 'react-query';
import toast from 'react-hot-toast';
import apiService from '../services/apiService';
import LoadingSpinner from '../components/LoadingSpinner';

const DashboardPage = ({ user, onLogout }) => {
  const [dashboardStats, setDashboardStats] = useState({
    totalSales: 0,
    dailyRevenue: 0,
    totalProducts: 0,
    lowStockItems: 0,
    activeTables: 0
  });

  // Fetch dashboard data
  const { data: sales = [], isLoading: loadingSales } = useQuery(
    'sales',
    apiService.getSales,
    { refetchInterval: 30000 } // Refresh every 30 seconds
  );

  const { data: products = [], isLoading: loadingProducts } = useQuery(
    'products',
    apiService.getProducts
  );

  const { data: tables = [], isLoading: loadingTables } = useQuery(
    'tables',
    apiService.getTables
  );

  useEffect(() => {
    calculateStats();
  }, [sales, products, tables]);

  const calculateStats = () => {
    const today = new Date().toDateString();
    const todaySales = sales.filter(sale => 
      new Date(sale.created_at).toDateString() === today
    );

    const dailyRevenue = todaySales.reduce((sum, sale) => sum + (sale.total || 0), 0);
    const lowStockItems = products.filter(product => product.stock <= 5).length;
    const activeTables = tables.filter(table => table.status === 'occupied').length;

    setDashboardStats({
      totalSales: sales.length,
      dailyRevenue,
      totalProducts: products.length,
      lowStockItems,
      activeTables
    });
  };

  const getRecentSales = () => {
    return sales
      .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
      .slice(0, 10);
  };

  const getLowStockProducts = () => {
    return products
      .filter(product => product.stock <= 5)
      .sort((a, b) => a.stock - b.stock);
  };

  const isLoading = loadingSales || loadingProducts || loadingTables;

  if (isLoading) {
    return (
      <div className="min-vh-100 d-flex align-items-center justify-content-center">
        <LoadingSpinner size="lg" message="Cargando dashboard..." />
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-content">
          <div className="brand-section">
            <img src="/uploads/logos/logo-white.png" alt="Logo" className="header-logo" />
            <div>
              <h1 className="dashboard-title">Dashboard</h1>
              <p className="user-info">
                <i className="bi bi-person-circle"></i>
                {user.name} - {user.role}
                {!navigator.onLine && <span className="offline-indicator">📴</span>}
              </p>
            </div>
          </div>
          
          <div className="header-actions">
            <div className="quick-actions">
              <button 
                className="btn btn-outline-light btn-sm"
                onClick={() => window.location.href = '/pos'}
              >
                <i className="bi bi-cash-coin"></i>
                POS
              </button>
              <button 
                className="btn btn-outline-light btn-sm"
                onClick={() => window.location.href = '/tables'}
              >
                <i className="bi bi-grid-3x3"></i>
                Mesas
              </button>
            </div>
            <button 
              className="btn btn-outline-light btn-sm"
              onClick={onLogout}
            >
              <i className="bi bi-box-arrow-right"></i>
              Salir
            </button>
          </div>
        </div>
      </header>

      <div className="dashboard-content">
        {/* Stats Cards */}
        <div className="stats-grid">
          <div className="stat-card revenue">
            <div className="stat-icon">
              <i className="bi bi-currency-dollar"></i>
            </div>
            <div className="stat-content">
              <h3>${dashboardStats.dailyRevenue.toFixed(2)}</h3>
              <p>Ingresos Hoy</p>
              <small className="stat-trend positive">
                <i className="bi bi-arrow-up"></i>
                +12% vs ayer
              </small>
            </div>
          </div>

          <div className="stat-card sales">
            <div className="stat-icon">
              <i className="bi bi-receipt"></i>
            </div>
            <div className="stat-content">
              <h3>{dashboardStats.totalSales}</h3>
              <p>Ventas Totales</p>
              <small className="stat-trend positive">
                <i className="bi bi-arrow-up"></i>
                +8% esta semana
              </small>
            </div>
          </div>

          <div className="stat-card products">
            <div className="stat-icon">
              <i className="bi bi-box-seam"></i>
            </div>
            <div className="stat-content">
              <h3>{dashboardStats.totalProducts}</h3>
              <p>Productos</p>
              <small className="stat-info">
                {dashboardStats.lowStockItems} con stock bajo
              </small>
            </div>
          </div>

          <div className="stat-card tables">
            <div className="stat-icon">
              <i className="bi bi-grid-3x3"></i>
            </div>
            <div className="stat-content">
              <h3>{dashboardStats.activeTables}</h3>
              <p>Mesas Activas</p>
              <small className="stat-info">
                de {tables.length} totales
              </small>
            </div>
          </div>
        </div>

        <div className="dashboard-grid">
          {/* Recent Sales */}
          <div className="dashboard-widget">
            <div className="widget-header">
              <h2 className="widget-title">
                <i className="bi bi-clock-history"></i>
                Ventas Recientes
              </h2>
              <button className="btn btn-outline-primary btn-sm">
                Ver Todas
              </button>
            </div>
            <div className="widget-content">
              {getRecentSales().length === 0 ? (
                <div className="empty-state">
                  <i className="bi bi-receipt"></i>
                  <p>No hay ventas recientes</p>
                </div>
              ) : (
                <div className="sales-list">
                  {getRecentSales().map(sale => (
                    <div key={sale.id} className="sale-item">
                      <div className="sale-info">
                        <div className="sale-id">#{sale.id}</div>
                        <div className="sale-time">
                          {new Date(sale.created_at).toLocaleTimeString()}
                        </div>
                      </div>
                      <div className="sale-details">
                        <div className="sale-amount">${sale.total?.toFixed(2)}</div>
                        <div className="sale-method">
                          <i className={`bi bi-${sale.payment_method === 'cash' ? 'cash' : 
                                      sale.payment_method === 'card' ? 'credit-card' : 'phone'}`}></i>
                          {sale.payment_method}
                        </div>
                      </div>
                      <div className="sale-status">
                        <span className={`status-badge ${sale.status}`}>
                          {sale.status === 'completed' ? 'Completada' : 
                           sale.status === 'pending' ? 'Pendiente' : 'Procesando'}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Low Stock Products */}
          <div className="dashboard-widget">
            <div className="widget-header">
              <h2 className="widget-title">
                <i className="bi bi-exclamation-triangle"></i>
                Stock Bajo
              </h2>
              <button className="btn btn-outline-warning btn-sm">
                Gestionar Inventario
              </button>
            </div>
            <div className="widget-content">
              {getLowStockProducts().length === 0 ? (
                <div className="empty-state good">
                  <i className="bi bi-check-circle"></i>
                  <p>Stock en buen estado</p>
                </div>
              ) : (
                <div className="stock-list">
                  {getLowStockProducts().map(product => (
                    <div key={product.id} className="stock-item">
                      <div className="product-info">
                        <div className="product-name">{product.name}</div>
                        <div className="product-category">{product.category_name}</div>
                      </div>
                      <div className="stock-info">
                        <div className={`stock-amount ${product.stock <= 2 ? 'critical' : 'low'}`}>
                          {product.stock} unidades
                        </div>
                        <div className="stock-price">${product.price}</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="dashboard-widget">
            <div className="widget-header">
              <h2 className="widget-title">
                <i className="bi bi-lightning"></i>
                Acciones Rápidas
              </h2>
            </div>
            <div className="widget-content">
              <div className="quick-actions-grid">
                <button className="action-btn">
                  <i className="bi bi-plus-circle"></i>
                  <span>Nueva Venta</span>
                </button>
                <button className="action-btn">
                  <i className="bi bi-box-arrow-in-down"></i>
                  <span>Recibir Inventario</span>
                </button>
                <button className="action-btn">
                  <i className="bi bi-file-earmark-text"></i>
                  <span>Generar Reporte</span>
                </button>
                <button className="action-btn">
                  <i className="bi bi-gear"></i>
                  <span>Configuración</span>
                </button>
                <button className="action-btn">
                  <i className="bi bi-people"></i>
                  <span>Gestionar Usuarios</span>
                </button>
                <button className="action-btn">
                  <i className="bi bi-cloud-sync"></i>
                  <span>Sincronizar Datos</span>
                </button>
              </div>
            </div>
          </div>

          {/* System Status */}
          <div className="dashboard-widget">
            <div className="widget-header">
              <h2 className="widget-title">
                <i className="bi bi-activity"></i>
                Estado del Sistema
              </h2>
            </div>
            <div className="widget-content">
              <div className="status-list">
                <div className="status-item">
                  <div className="status-label">
                    <i className="bi bi-wifi"></i>
                    Conexión
                  </div>
                  <div className={`status-value ${navigator.onLine ? 'online' : 'offline'}`}>
                    {navigator.onLine ? 'Conectado' : 'Offline'}
                  </div>
                </div>
                
                <div className="status-item">
                  <div className="status-label">
                    <i className="bi bi-database"></i>
                    Base de Datos
                  </div>
                  <div className="status-value online">
                    Operacional
                  </div>
                </div>
                
                <div className="status-item">
                  <div className="status-label">
                    <i className="bi bi-cloud-check"></i>
                    Sincronización
                  </div>
                  <div className="status-value online">
                    Actualizado
                  </div>
                </div>
                
                <div className="status-item">
                  <div className="status-label">
                    <i className="bi bi-shield-check"></i>
                    Seguridad
                  </div>
                  <div className="status-value online">
                    Protegido
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <style jsx>{`
        .dashboard-container {
          min-height: 100vh;
          background: var(--bg-primary);
          color: var(--text-primary);
        }

        .dashboard-header {
          background: var(--glass-bg);
          backdrop-filter: blur(20px);
          border-bottom: 1px solid var(--glass-border);
          padding: var(--space-md);
        }

        .header-content {
          display: flex;
          justify-content: space-between;
          align-items: center;
          max-width: 1400px;
          margin: 0 auto;
        }

        .brand-section {
          display: flex;
          align-items: center;
          gap: var(--space-md);
        }

        .header-logo {
          width: 48px;
          height: 48px;
          border-radius: var(--radius-lg);
        }

        .dashboard-title {
          margin: 0;
          font-size: 1.5rem;
          font-weight: 700;
        }

        .user-info {
          margin: 0;
          color: var(--text-secondary);
          font-size: 0.875rem;
          display: flex;
          align-items: center;
          gap: var(--space-sm);
        }

        .offline-indicator {
          background: rgba(239, 68, 68, 0.2);
          color: #f87171;
          padding: 2px 6px;
          border-radius: var(--radius-sm);
          font-size: 0.75rem;
        }

        .header-actions {
          display: flex;
          align-items: center;
          gap: var(--space-md);
        }

        .quick-actions {
          display: flex;
          gap: var(--space-sm);
        }

        .dashboard-content {
          max-width: 1400px;
          margin: 0 auto;
          padding: var(--space-lg);
        }

        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
          gap: var(--space-lg);
          margin-bottom: var(--space-2xl);
        }

        .stat-card {
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-xl);
          padding: var(--space-lg);
          display: flex;
          align-items: center;
          gap: var(--space-lg);
          transition: all var(--transition-normal);
        }

        .stat-card:hover {
          transform: translateY(-4px);
          box-shadow: var(--shadow-xl);
        }

        .stat-icon {
          width: 60px;
          height: 60px;
          border-radius: var(--radius-lg);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 1.5rem;
        }

        .stat-card.revenue .stat-icon {
          background: var(--accent-success);
          color: white;
        }

        .stat-card.sales .stat-icon {
          background: var(--accent-primary);
          color: white;
        }

        .stat-card.products .stat-icon {
          background: var(--accent-info);
          color: white;
        }

        .stat-card.tables .stat-icon {
          background: var(--accent-warning);
          color: white;
        }

        .stat-content h3 {
          margin: 0 0 var(--space-xs) 0;
          font-size: 2rem;
          font-weight: 700;
          color: var(--text-primary);
        }

        .stat-content p {
          margin: 0 0 var(--space-xs) 0;
          color: var(--text-secondary);
          font-weight: 500;
        }

        .stat-trend {
          font-size: 0.875rem;
          display: flex;
          align-items: center;
          gap: var(--space-xs);
        }

        .stat-trend.positive {
          color: #22c55e;
        }

        .stat-info {
          color: var(--text-muted);
          font-size: 0.875rem;
        }

        .dashboard-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
          gap: var(--space-lg);
        }

        .dashboard-widget {
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-xl);
          overflow: hidden;
        }

        .widget-header {
          padding: var(--space-lg);
          border-bottom: 1px solid var(--glass-border);
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .widget-title {
          margin: 0;
          font-size: 1.125rem;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: var(--space-sm);
        }

        .widget-content {
          padding: var(--space-lg);
        }

        .empty-state {
          text-align: center;
          padding: var(--space-2xl);
          color: var(--text-muted);
        }

        .empty-state.good {
          color: #22c55e;
        }

        .empty-state i {
          font-size: 3rem;
          margin-bottom: var(--space-md);
        }

        .sales-list,
        .stock-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
        }

        .sale-item,
        .stock-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-md);
          background: var(--glass-bg);
          border-radius: var(--radius-lg);
          border: 1px solid var(--glass-border);
        }

        .sale-info,
        .product-info {
          flex: 1;
        }

        .sale-id,
        .product-name {
          font-weight: 600;
          margin-bottom: var(--space-xs);
        }

        .sale-time,
        .product-category {
          font-size: 0.875rem;
          color: var(--text-muted);
        }

        .sale-details,
        .stock-info {
          text-align: right;
        }

        .sale-amount,
        .stock-price {
          font-weight: 700;
          color: var(--text-accent);
        }

        .sale-method {
          font-size: 0.875rem;
          color: var(--text-muted);
          display: flex;
          align-items: center;
          gap: var(--space-xs);
        }

        .stock-amount {
          font-weight: 600;
          margin-bottom: var(--space-xs);
        }

        .stock-amount.critical {
          color: #ef4444;
        }

        .stock-amount.low {
          color: #f59e0b;
        }

        .status-badge {
          padding: var(--space-xs) var(--space-sm);
          border-radius: var(--radius-md);
          font-size: 0.75rem;
          font-weight: 600;
        }

        .status-badge.completed {
          background: rgba(34, 197, 94, 0.2);
          color: #22c55e;
        }

        .status-badge.pending {
          background: rgba(251, 191, 36, 0.2);
          color: #f59e0b;
        }

        .quick-actions-grid {
          display: grid;
          grid-template-columns: repeat(2, 1fr);
          gap: var(--space-md);
        }

        .action-btn {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-lg);
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          color: var(--text-primary);
          cursor: pointer;
          transition: all var(--transition-normal);
        }

        .action-btn:hover {
          background: var(--bg-tertiary);
          border-color: var(--text-accent);
          transform: translateY(-2px);
        }

        .action-btn i {
          font-size: 1.5rem;
        }

        .action-btn span {
          font-size: 0.875rem;
          font-weight: 500;
        }

        .status-list {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
        }

        .status-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }

        .status-label {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          color: var(--text-secondary);
        }

        .status-value {
          font-weight: 600;
        }

        .status-value.online {
          color: #22c55e;
        }

        .status-value.offline {
          color: #ef4444;
        }

        @media (max-width: 1024px) {
          .dashboard-grid {
            grid-template-columns: 1fr;
          }
          
          .stats-grid {
            grid-template-columns: repeat(2, 1fr);
          }
        }

        @media (max-width: 768px) {
          .dashboard-content {
            padding: var(--space-md);
          }
          
          .stats-grid {
            grid-template-columns: 1fr;
          }
          
          .header-content {
            flex-direction: column;
            gap: var(--space-md);
          }
          
          .quick-actions-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default DashboardPage;