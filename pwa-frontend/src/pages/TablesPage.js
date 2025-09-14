import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import apiService from '../services/apiService';
import LoadingSpinner from '../components/LoadingSpinner';

const TablesPage = ({ user, onLogout }) => {
  const [selectedTable, setSelectedTable] = useState(null);
  const [showOrderModal, setShowOrderModal] = useState(false);
  const [cart, setCart] = useState([]);

  const queryClient = useQueryClient();

  // Fetch data
  const { data: tables = [], isLoading: loadingTables } = useQuery(
    'tables',
    apiService.getTables,
    { refetchInterval: 15000 } // Refresh every 15 seconds
  );

  const { data: products = [], isLoading: loadingProducts } = useQuery(
    'products',
    apiService.getProducts
  );

  const { data: categories = [] } = useQuery(
    'categories',
    apiService.getCategories
  );

  // Table operations
  const updateTableMutation = useMutation(
    ({ tableId, updates }) => apiService.updateTable(tableId, updates),
    {
      onSuccess: () => {
        queryClient.invalidateQueries('tables');
        toast.success('Mesa actualizada');
      },
      onError: () => {
        toast.error('Error al actualizar mesa');
      }
    }
  );

  const createOrderMutation = useMutation(
    apiService.createSale,
    {
      onSuccess: () => {
        queryClient.invalidateQueries(['tables', 'sales']);
        toast.success('Orden enviada a cocina');
        setCart([]);
        setShowOrderModal(false);
        setSelectedTable(null);
      },
      onError: () => {
        toast.error('Error al enviar orden');
      }
    }
  );

  const getTableStatusColor = (status) => {
    switch (status) {
      case 'available': return 'available';
      case 'occupied': return 'occupied';
      case 'reserved': return 'reserved';
      default: return 'available';
    }
  };

  const getTableStatusText = (status) => {
    switch (status) {
      case 'available': return 'Disponible';
      case 'occupied': return 'Ocupada';
      case 'reserved': return 'Reservada';
      default: return 'Disponible';
    }
  };

  const handleTableClick = (table) => {
    setSelectedTable(table);
    if (table.status === 'available') {
      // Mark as occupied
      updateTableMutation.mutate({
        tableId: table.id,
        updates: { status: 'occupied' }
      });
    }
    setShowOrderModal(true);
  };

  const handleAddToCart = (product) => {
    setCart(prevCart => {
      const existingItem = prevCart.find(item => item.id === product.id);
      if (existingItem) {
        return prevCart.map(item =>
          item.id === product.id
            ? { ...item, quantity: item.quantity + 1 }
            : item
        );
      } else {
        return [...prevCart, { ...product, quantity: 1 }];
      }
    });
  };

  const updateCartQuantity = (productId, newQuantity) => {
    if (newQuantity <= 0) {
      setCart(prevCart => prevCart.filter(item => item.id !== productId));
      return;
    }
    
    setCart(prevCart =>
      prevCart.map(item =>
        item.id === productId
          ? { ...item, quantity: newQuantity }
          : item
      )
    );
  };

  const handleSendOrder = () => {
    if (cart.length === 0) {
      toast.error('Agrega productos a la orden');
      return;
    }

    if (!selectedTable) {
      toast.error('Selecciona una mesa');
      return;
    }

    const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    const tax = subtotal * 0.18;
    const total = subtotal + tax;

    const orderData = {
      table_id: selectedTable.id,
      table_number: selectedTable.number,
      items: cart.map(item => ({
        product_id: item.id,
        product_name: item.name,
        quantity: item.quantity,
        unit_price: item.price,
        total_price: item.price * item.quantity,
        status: 'sent_to_kitchen'
      })),
      subtotal,
      tax,
      total,
      status: 'in_preparation',
      order_type: 'table',
      waiter_id: user.id,
      created_at: new Date().toISOString()
    };

    createOrderMutation.mutate(orderData);
  };

  const handleCloseTable = () => {
    if (selectedTable) {
      updateTableMutation.mutate({
        tableId: selectedTable.id,
        updates: { status: 'available' }
      });
      setSelectedTable(null);
      setShowOrderModal(false);
      setCart([]);
    }
  };

  const totalAmount = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);

  if (loadingTables || loadingProducts) {
    return (
      <div className="min-vh-100 d-flex align-items-center justify-content-center">
        <LoadingSpinner size="lg" message="Cargando mesas..." />
      </div>
    );
  }

  return (
    <div className="tables-container">
      {/* Header */}
      <header className="tables-header">
        <div className="header-content">
          <div className="brand-section">
            <img src="/uploads/logos/logo-white.png" alt="Logo" className="header-logo" />
            <div>
              <h1 className="tables-title">Gestión de Mesas</h1>
              <p className="user-info">
                <i className="bi bi-person-badge"></i>
                {user.name} - Mesero
                {!navigator.onLine && <span className="offline-indicator">📴</span>}
              </p>
            </div>
          </div>
          
          <div className="header-actions">
            <div className="table-stats">
              <div className="stat">
                <span className="stat-number">{tables.filter(t => t.status === 'available').length}</span>
                <span className="stat-label">Disponibles</span>
              </div>
              <div className="stat">
                <span className="stat-number">{tables.filter(t => t.status === 'occupied').length}</span>
                <span className="stat-label">Ocupadas</span>
              </div>
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

      {/* Tables Grid */}
      <div className="tables-content">
        <div className="tables-grid">
          {tables.map(table => (
            <div
              key={table.id}
              className={`table-card ${getTableStatusColor(table.status)}`}
              onClick={() => handleTableClick(table)}
            >
              <div className="table-number">
                Mesa {table.number}
              </div>
              <div className="table-info">
                <div className="table-capacity">
                  <i className="bi bi-people"></i>
                  {table.capacity} personas
                </div>
                <div className="table-status">
                  {getTableStatusText(table.status)}
                </div>
              </div>
              {table.status === 'occupied' && (
                <div className="table-time">
                  <i className="bi bi-clock"></i>
                  {table.occupied_since ? 
                    `${Math.floor((new Date() - new Date(table.occupied_since)) / 60000)}min` :
                    'Activa'
                  }
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Legend */}
        <div className="table-legend">
          <div className="legend-item">
            <div className="legend-color available"></div>
            <span>Disponible</span>
          </div>
          <div className="legend-item">
            <div className="legend-color occupied"></div>
            <span>Ocupada</span>
          </div>
          <div className="legend-item">
            <div className="legend-color reserved"></div>
            <span>Reservada</span>
          </div>
        </div>
      </div>

      {/* Order Modal */}
      {showOrderModal && selectedTable && (
        <div className="order-modal-overlay">
          <div className="order-modal">
            <div className="modal-header">
              <h3>Mesa {selectedTable.number}</h3>
              <button
                className="close-btn"
                onClick={() => setShowOrderModal(false)}
              >
                <i className="bi bi-x"></i>
              </button>
            </div>
            
            <div className="modal-body">
              <div className="order-sections">
                {/* Products Section */}
                <div className="products-section">
                  <h4>Menú</h4>
                  <div className="categories">
                    {categories.map(category => (
                      <div key={category.id} className="category-section">
                        <h5>{category.name}</h5>
                        <div className="products-grid">
                          {products
                            .filter(product => product.category_id === category.id)
                            .map(product => (
                              <div
                                key={product.id}
                                className="product-item"
                                onClick={() => handleAddToCart(product)}
                              >
                                <div className="product-name">{product.name}</div>
                                <div className="product-price">${product.price?.toFixed(2)}</div>
                              </div>
                            ))
                          }
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Order Section */}
                <div className="order-section">
                  <h4>Orden de Mesa {selectedTable.number}</h4>
                  
                  {cart.length === 0 ? (
                    <div className="empty-order">
                      <i className="bi bi-clipboard"></i>
                      <p>Agrega productos al pedido</p>
                    </div>
                  ) : (
                    <>
                      <div className="order-items">
                        {cart.map(item => (
                          <div key={item.id} className="order-item">
                            <div className="item-info">
                              <div className="item-name">{item.name}</div>
                              <div className="item-price">${item.price?.toFixed(2)}</div>
                            </div>
                            <div className="quantity-controls">
                              <button
                                className="qty-btn"
                                onClick={() => updateCartQuantity(item.id, item.quantity - 1)}
                              >
                                <i className="bi bi-dash"></i>
                              </button>
                              <span className="quantity">{item.quantity}</span>
                              <button
                                className="qty-btn"
                                onClick={() => updateCartQuantity(item.id, item.quantity + 1)}
                              >
                                <i className="bi bi-plus"></i>
                              </button>
                            </div>
                            <div className="item-total">
                              ${(item.price * item.quantity).toFixed(2)}
                            </div>
                          </div>
                        ))}
                      </div>
                      
                      <div className="order-summary">
                        <div className="summary-line">
                          <span>Total:</span>
                          <span>${totalAmount.toFixed(2)}</span>
                        </div>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
            
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={handleCloseTable}
              >
                <i className="bi bi-door-closed"></i>
                Cerrar Mesa
              </button>
              
              <button
                className="btn btn-primary"
                onClick={handleSendOrder}
                disabled={cart.length === 0 || createOrderMutation.isLoading}
              >
                {createOrderMutation.isLoading ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  <>
                    <i className="bi bi-send"></i>
                    Enviar a Cocina
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .tables-container {
          min-height: 100vh;
          background: var(--bg-primary);
          color: var(--text-primary);
        }

        .tables-header {
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

        .tables-title {
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
          gap: var(--space-lg);
        }

        .table-stats {
          display: flex;
          gap: var(--space-lg);
        }

        .stat {
          text-align: center;
        }

        .stat-number {
          display: block;
          font-size: 1.5rem;
          font-weight: 700;
          color: var(--text-accent);
        }

        .stat-label {
          font-size: 0.875rem;
          color: var(--text-secondary);
        }

        .tables-content {
          max-width: 1400px;
          margin: 0 auto;
          padding: var(--space-lg);
        }

        .tables-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: var(--space-lg);
          margin-bottom: var(--space-xl);
        }

        .table-card {
          background: var(--bg-card);
          border: 2px solid var(--glass-border);
          border-radius: var(--radius-xl);
          padding: var(--space-lg);
          cursor: pointer;
          transition: all var(--transition-normal);
          text-align: center;
          position: relative;
        }

        .table-card:hover {
          transform: translateY(-4px);
          box-shadow: var(--shadow-xl);
        }

        .table-card.available {
          border-color: #22c55e;
          background: rgba(34, 197, 94, 0.1);
        }

        .table-card.occupied {
          border-color: #ef4444;
          background: rgba(239, 68, 68, 0.1);
        }

        .table-card.reserved {
          border-color: #f59e0b;
          background: rgba(245, 158, 11, 0.1);
        }

        .table-number {
          font-size: 1.5rem;
          font-weight: 700;
          margin-bottom: var(--space-md);
        }

        .table-info {
          margin-bottom: var(--space-sm);
        }

        .table-capacity {
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-xs);
          color: var(--text-secondary);
          font-size: 0.875rem;
          margin-bottom: var(--space-xs);
        }

        .table-status {
          font-weight: 600;
          font-size: 0.875rem;
        }

        .table-card.available .table-status {
          color: #22c55e;
        }

        .table-card.occupied .table-status {
          color: #ef4444;
        }

        .table-card.reserved .table-status {
          color: #f59e0b;
        }

        .table-time {
          position: absolute;
          top: var(--space-sm);
          right: var(--space-sm);
          background: rgba(239, 68, 68, 0.2);
          color: #ef4444;
          padding: var(--space-xs) var(--space-sm);
          border-radius: var(--radius-md);
          font-size: 0.75rem;
          display: flex;
          align-items: center;
          gap: var(--space-xs);
        }

        .table-legend {
          display: flex;
          justify-content: center;
          gap: var(--space-xl);
          margin-top: var(--space-xl);
        }

        .legend-item {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
          font-size: 0.875rem;
          color: var(--text-secondary);
        }

        .legend-color {
          width: 20px;
          height: 20px;
          border-radius: 50%;
          border: 2px solid;
        }

        .legend-color.available {
          background: rgba(34, 197, 94, 0.2);
          border-color: #22c55e;
        }

        .legend-color.occupied {
          background: rgba(239, 68, 68, 0.2);
          border-color: #ef4444;
        }

        .legend-color.reserved {
          background: rgba(245, 158, 11, 0.2);
          border-color: #f59e0b;
        }

        .order-modal-overlay {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          bottom: 0;
          background: rgba(0, 0, 0, 0.8);
          backdrop-filter: blur(8px);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1000;
          padding: var(--space-lg);
        }

        .order-modal {
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-xl);
          width: 100%;
          max-width: 1000px;
          max-height: 90vh;
          overflow: hidden;
          display: flex;
          flex-direction: column;
        }

        .modal-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: var(--space-lg);
          border-bottom: 1px solid var(--glass-border);
        }

        .modal-header h3 {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 700;
        }

        .close-btn {
          width: 32px;
          height: 32px;
          border: none;
          background: none;
          color: var(--text-muted);
          cursor: pointer;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .modal-body {
          flex: 1;
          overflow-y: auto;
          padding: var(--space-lg);
        }

        .order-sections {
          display: grid;
          grid-template-columns: 2fr 1fr;
          gap: var(--space-xl);
          height: 100%;
        }

        .products-section h4,
        .order-section h4 {
          margin: 0 0 var(--space-lg) 0;
          font-size: 1.125rem;
          font-weight: 600;
        }

        .category-section {
          margin-bottom: var(--space-xl);
        }

        .category-section h5 {
          margin: 0 0 var(--space-md) 0;
          font-size: 1rem;
          font-weight: 600;
          color: var(--text-accent);
        }

        .products-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          gap: var(--space-md);
        }

        .product-item {
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: var(--space-md);
          cursor: pointer;
          transition: all var(--transition-normal);
        }

        .product-item:hover {
          background: var(--bg-tertiary);
          border-color: var(--text-accent);
        }

        .product-name {
          font-weight: 600;
          margin-bottom: var(--space-xs);
          font-size: 0.875rem;
        }

        .product-price {
          color: var(--text-accent);
          font-weight: 700;
        }

        .empty-order {
          text-align: center;
          padding: var(--space-2xl);
          color: var(--text-muted);
        }

        .empty-order i {
          font-size: 3rem;
          margin-bottom: var(--space-md);
        }

        .order-items {
          margin-bottom: var(--space-lg);
        }

        .order-item {
          display: flex;
          align-items: center;
          gap: var(--space-md);
          padding: var(--space-md);
          background: var(--glass-bg);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          margin-bottom: var(--space-md);
        }

        .item-info {
          flex: 1;
        }

        .item-name {
          font-weight: 600;
          margin-bottom: var(--space-xs);
          font-size: 0.875rem;
        }

        .item-price {
          color: var(--text-muted);
          font-size: 0.875rem;
        }

        .quantity-controls {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
        }

        .qty-btn {
          width: 28px;
          height: 28px;
          border: 1px solid var(--glass-border);
          background: var(--bg-tertiary);
          color: var(--text-primary);
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
        }

        .quantity {
          min-width: 30px;
          text-align: center;
          font-weight: 600;
        }

        .item-total {
          font-weight: 700;
          color: var(--text-accent);
          min-width: 80px;
          text-align: right;
        }

        .order-summary {
          padding: var(--space-lg);
          background: var(--glass-bg);
          border-radius: var(--radius-lg);
          border: 1px solid var(--glass-border);
        }

        .summary-line {
          display: flex;
          justify-content: space-between;
          font-size: 1.125rem;
          font-weight: 700;
          color: var(--text-accent);
        }

        .modal-footer {
          display: flex;
          gap: var(--space-md);
          padding: var(--space-lg);
          border-top: 1px solid var(--glass-border);
        }

        .modal-footer button {
          flex: 1;
          padding: var(--space-md);
          border-radius: var(--radius-lg);
          font-weight: 600;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
        }

        @media (max-width: 1024px) {
          .order-sections {
            grid-template-columns: 1fr;
            gap: var(--space-lg);
          }
          
          .tables-grid {
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          }
        }

        @media (max-width: 768px) {
          .tables-content {
            padding: var(--space-md);
          }
          
          .header-content {
            flex-direction: column;
            gap: var(--space-md);
          }
          
          .table-stats {
            gap: var(--space-md);
          }
          
          .products-grid {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default TablesPage;