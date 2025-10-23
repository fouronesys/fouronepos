import React, { useState, useEffect, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from 'react-query';
import toast from 'react-hot-toast';
import apiService from '../services/apiService';
import offlineStorage from '../services/offlineStorage';
import LoadingSpinner from '../components/LoadingSpinner';

const POSPage = ({ user, onLogout }) => {
  const [cart, setCart] = useState([]);
  const [cartLoaded, setCartLoaded] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchTerm, setSearchTerm] = useState('');
  const [paymentMethod, setPaymentMethod] = useState('cash');
  const [cashReceived, setCashReceived] = useState('');
  const [showPaymentModal, setShowPaymentModal] = useState(false);
  const [customerData, setCustomerData] = useState({ name: '', rnc: '' });
  const [selectedCustomer, setSelectedCustomer] = useState(null);
  const [showCustomerDropdown, setShowCustomerDropdown] = useState(false);
  const [customerSearchTerm, setCustomerSearchTerm] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [validationErrors, setValidationErrors] = useState({});

  const queryClient = useQueryClient();
  const dropdownRef = useRef(null);

  // Constantes de validación
  const VALIDATION_LIMITS = {
    MIN_QUANTITY: 1,
    MAX_QUANTITY: 1000,
    MAX_CART_ITEMS: 100,
    MIN_CUSTOMER_NAME_LENGTH: 3,
    MIN_CASH_AMOUNT: 0,
    MAX_CASH_AMOUNT: 1000000,
    ALLOWED_PAYMENT_METHODS: ['cash', 'card', 'transfer']
  };

  // Funciones de validación
  const validateRNC = (rnc) => {
    if (!rnc || rnc.trim() === '') {
      return { valid: true }; // RNC es opcional
    }
    
    // Eliminar guiones y espacios
    const cleanRNC = rnc.replace(/[-\s]/g, '');
    
    // Debe ser de 9 u 11 dígitos
    if (!/^\d{9}$|^\d{11}$/.test(cleanRNC)) {
      return {
        valid: false,
        error: 'El RNC/Cédula debe tener 9 u 11 dígitos'
      };
    }
    
    return { valid: true };
  };

  const validateCustomerName = (name) => {
    if (!name || name.trim() === '') {
      return { valid: true }; // Nombre es opcional
    }
    
    if (name.trim().length < VALIDATION_LIMITS.MIN_CUSTOMER_NAME_LENGTH) {
      return {
        valid: false,
        error: `El nombre debe tener al menos ${VALIDATION_LIMITS.MIN_CUSTOMER_NAME_LENGTH} caracteres`
      };
    }
    
    return { valid: true };
  };

  const validateCashReceived = (amount, total) => {
    if (!amount || amount === '') {
      return {
        valid: false,
        error: 'Debe ingresar el monto recibido'
      };
    }
    
    const cashAmount = parseFloat(amount);
    
    if (isNaN(cashAmount)) {
      return {
        valid: false,
        error: 'El monto debe ser un número válido'
      };
    }
    
    if (cashAmount < VALIDATION_LIMITS.MIN_CASH_AMOUNT) {
      return {
        valid: false,
        error: 'El monto no puede ser negativo'
      };
    }
    
    if (cashAmount > VALIDATION_LIMITS.MAX_CASH_AMOUNT) {
      return {
        valid: false,
        error: `El monto no puede exceder RD$ ${VALIDATION_LIMITS.MAX_CASH_AMOUNT.toLocaleString()}`
      };
    }
    
    if (cashAmount < total) {
      return {
        valid: false,
        error: `El monto recibido (RD$ ${cashAmount.toFixed(2)}) debe ser mayor o igual al total (RD$ ${total.toFixed(2)})`
      };
    }
    
    return { valid: true };
  };

  const validateQuantity = (quantity) => {
    const qty = parseInt(quantity);
    
    if (isNaN(qty) || qty < VALIDATION_LIMITS.MIN_QUANTITY) {
      return {
        valid: false,
        error: `La cantidad mínima es ${VALIDATION_LIMITS.MIN_QUANTITY}`
      };
    }
    
    if (qty > VALIDATION_LIMITS.MAX_QUANTITY) {
      return {
        valid: false,
        error: `La cantidad máxima es ${VALIDATION_LIMITS.MAX_QUANTITY} unidades`
      };
    }
    
    return { valid: true, quantity: qty };
  };

  const validateStock = (product, requestedQuantity) => {
    // Solo omitir validación si stock es undefined o null (no hay control de stock)
    if (product.stock === undefined || product.stock === null) {
      return { valid: true }; // Si no hay control de stock, permitir
    }
    
    // Si el stock es 0 o insuficiente, rechazar
    if (requestedQuantity > product.stock) {
      return {
        valid: false,
        error: `Stock insuficiente. Disponible: ${product.stock} unidades`
      };
    }
    
    return { valid: true };
  };

  const validatePaymentMethod = (method) => {
    if (!VALIDATION_LIMITS.ALLOWED_PAYMENT_METHODS.includes(method)) {
      return {
        valid: false,
        error: 'Método de pago inválido'
      };
    }
    return { valid: true };
  };

  // Fetch data with offline fallback
  const { data: products = [], isLoading: loadingProducts } = useQuery(
    'products',
    apiService.getProducts,
    {
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    }
  );

  const { data: categories = [], isLoading: loadingCategories } = useQuery(
    'categories', 
    apiService.getCategories,
    {
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    }
  );

  const { data: customers = [], isLoading: loadingCustomers } = useQuery(
    'customers',
    apiService.getCustomers,
    {
      staleTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
    }
  );

  const { data: taxTypes = [], isLoading: loadingTaxTypes } = useQuery(
    'taxTypes',
    apiService.getTaxTypes,
    {
      staleTime: 0,  // Forzar refetch inmediato
      cacheTime: 0,  // No cachear para forzar nueva petición
      refetchOnWindowFocus: true,
      refetchOnMount: true,
    }
  );




  // Filter products
  const filteredProducts = products.filter(product => {
    const matchesCategory = selectedCategory === 'all' || 
                           product.category_id === parseInt(selectedCategory);
    const matchesSearch = product.name.toLowerCase().includes(searchTerm.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  // Filter customers
  const filteredCustomers = customers.filter(customer => 
    customer.name.toLowerCase().includes(customerSearchTerm.toLowerCase()) ||
    customer.rnc?.toLowerCase().includes(customerSearchTerm.toLowerCase())
  );

  // Cart operations
  const addToCart = (product) => {
    console.log('[CART DEBUG] 🛒 Intentando añadir producto al carrito:', {
      product: product,
      productId: product.id,
      productName: product.name,
      productPrice: product.price,
      productTaxRate: product.tax_rate,
      productIsTaxIncluded: product.is_tax_included,
      productTaxTypes: product.tax_types,
      timestamp: new Date().toISOString()
    });

    try {
      // Validar límite de ítems en el carrito
      const existingItem = cart.find(item => item.id === product.id);
      const currentCartSize = cart.length;
      
      if (!existingItem && currentCartSize >= VALIDATION_LIMITS.MAX_CART_ITEMS) {
        toast.error(`No se pueden agregar más de ${VALIDATION_LIMITS.MAX_CART_ITEMS} productos diferentes al carrito`);
        return;
      }
      
      // Calcular la nueva cantidad
      const newQuantity = existingItem ? existingItem.quantity + 1 : 1;
      
      // Validar cantidad máxima
      const quantityValidation = validateQuantity(newQuantity);
      if (!quantityValidation.valid) {
        toast.error(quantityValidation.error);
        return;
      }
      
      // Validar stock disponible
      const stockValidation = validateStock(product, newQuantity);
      if (!stockValidation.valid) {
        toast.error(stockValidation.error);
        return;
      }

      setCart(prevCart => {
        console.log('[CART DEBUG] 📊 Estado del carrito antes de añadir:', {
          cartLength: prevCart.length,
          cartItems: prevCart.map(item => ({ id: item.id, name: item.name, quantity: item.quantity }))
        });

        const existingItem = prevCart.find(item => item.id === product.id);
        console.log('[CART DEBUG] 🔍 Producto existente en carrito:', existingItem);

        let newCart;
        if (existingItem) {
          console.log('[CART DEBUG] ➕ Incrementando cantidad de producto existente');
          newCart = prevCart.map(item =>
            item.id === product.id
              ? { ...item, quantity: item.quantity + 1 }
              : item
          );
        } else {
          console.log('[CART DEBUG] 🆕 Añadiendo nuevo producto al carrito');
          newCart = [...prevCart, { ...product, quantity: 1 }];
        }

        console.log('[CART DEBUG] ✅ Estado del carrito después de añadir:', {
          cartLength: newCart.length,
          cartItems: newCart.map(item => ({ id: item.id, name: item.name, quantity: item.quantity })),
          addedProduct: product.name
        });

        return newCart;
      });

      console.log('[CART DEBUG] 🎉 Producto añadido exitosamente, mostrando toast');
      toast.success(`${product.name} agregado al carrito`);

    } catch (error) {
      console.error('[CART DEBUG] ❌ Error al añadir producto al carrito:', {
        error: error,
        errorMessage: error.message,
        errorStack: error.stack,
        product: product
      });
      toast.error(`Error al añadir ${product.name} al carrito: ${error.message}`);
    }
  };

  const updateQuantity = (productId, newQuantity) => {
    if (newQuantity <= 0) {
      removeFromCart(productId);
      return;
    }
    
    // Validar cantidad
    const quantityValidation = validateQuantity(newQuantity);
    if (!quantityValidation.valid) {
      toast.error(quantityValidation.error);
      return;
    }
    
    // Buscar el producto para validar stock
    const product = products.find(p => p.id === productId);
    if (product) {
      const stockValidation = validateStock(product, newQuantity);
      if (!stockValidation.valid) {
        toast.error(stockValidation.error);
        return;
      }
    }
    
    setCart(prevCart =>
      prevCart.map(item =>
        item.id === productId
          ? { ...item, quantity: newQuantity }
          : item
      )
    );
  };

  const removeFromCart = (productId) => {
    setCart(prevCart => prevCart.filter(item => item.id !== productId));
  };

  const clearCart = () => {
    setCart([]);
    localStorage.removeItem('pos_cart');
    toast.success('Carrito vaciado');
  };

  // Customer selection operations
  const selectCustomer = (customer) => {
    setSelectedCustomer(customer);
    setCustomerData({ 
      name: customer.name, 
      rnc: customer.rnc || '' 
    });
    setCustomerSearchTerm(customer.name);
    setShowCustomerDropdown(false);
  };

  const clearCustomerSelection = () => {
    setSelectedCustomer(null);
    setCustomerData({ name: '', rnc: '' });
    setCustomerSearchTerm('');
  };

  const handleCustomerSearchChange = (value) => {
    setCustomerSearchTerm(value);
    setShowCustomerDropdown(true);
    
    // If manually typing, clear the selection
    if (selectedCustomer && value !== selectedCustomer.name) {
      setSelectedCustomer(null);
      setCustomerData({ name: value, rnc: customerData.rnc });
    } else if (!selectedCustomer) {
      setCustomerData({ name: value, rnc: customerData.rnc });
    }
  };

  // Close customer dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setShowCustomerDropdown(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // Load cart from localStorage on component mount
  useEffect(() => {
    const savedCart = localStorage.getItem('pos_cart');
    if (savedCart) {
      try {
        const parsedCart = JSON.parse(savedCart);
        // Force a delay to ensure React has time to render
        setTimeout(() => {
          setCart(parsedCart);
          console.log('[Cart] Loaded cart from storage:', parsedCart);
          setCartLoaded(true);
        }, 100);
      } catch (error) {
        console.error('[Cart] Error loading cart from storage:', error);
        localStorage.removeItem('pos_cart');
        setCartLoaded(true);
      }
    } else {
      setCartLoaded(true);
    }
  }, []);

  // Save cart to localStorage whenever cart changes (but only after initial load)
  useEffect(() => {
    if (cartLoaded) {
      localStorage.setItem('pos_cart', JSON.stringify(cart));
      console.log('[Cart] Saved cart to storage:', cart);
    }
  }, [cart, cartLoaded]);

  // Calculate totals (preview only - server does actual calculation)
  const subtotal = cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
  const previewTax = subtotal * 0.18; // 18% ITBIS preview
  const previewTotal = subtotal + previewTax;
  const change = cashReceived ? Math.max(0, parseFloat(cashReceived) - previewTotal) : 0;

  const handleProcessSale = () => {
    if (cart.length === 0) {
      toast.error('El carrito está vacío');
      return;
    }
    setShowPaymentModal(true);
  };

  const handleCompleteSale = async () => {
    // Limpiar errores previos
    setValidationErrors({});
    const errors = {};

    // Validar método de pago
    const paymentValidation = validatePaymentMethod(paymentMethod);
    if (!paymentValidation.valid) {
      errors.paymentMethod = paymentValidation.error;
      setValidationErrors(errors);
      toast.error(paymentValidation.error);
      return;
    }

    // Validar efectivo recibido si el método es cash
    if (paymentMethod === 'cash') {
      const cashValidation = validateCashReceived(cashReceived, previewTotal);
      if (!cashValidation.valid) {
        errors.cashReceived = cashValidation.error;
        setValidationErrors(errors);
        toast.error(cashValidation.error);
        return;
      }
    }

    // Validar nombre del cliente si se proporcionó
    if (customerData.name) {
      const nameValidation = validateCustomerName(customerData.name);
      if (!nameValidation.valid) {
        errors.customerName = nameValidation.error;
        setValidationErrors(errors);
        toast.error(nameValidation.error);
        return;
      }
    }

    // Validar RNC del cliente si se proporcionó
    if (customerData.rnc) {
      const rncValidation = validateRNC(customerData.rnc);
      if (!rncValidation.valid) {
        errors.customerRnc = rncValidation.error;
        setValidationErrors(errors);
        toast.error(rncValidation.error);
        return;
      }
    }

    // Validar stock disponible para todos los productos en el carrito
    for (const item of cart) {
      const product = products.find(p => p.id === item.id);
      if (product) {
        const stockValidation = validateStock(product, item.quantity);
        if (!stockValidation.valid) {
          toast.error(`${product.name}: ${stockValidation.error}`);
          return;
        }
      }
    }

    setIsSubmitting(true);
    try {
      // Step 1: Create empty sale
      const csrfToken = await apiService.getCsrfToken();
      const saleResponse = await apiService.axiosInstance.post('/sales', {
        description: 'Venta POS',
        csrf_token: csrfToken
      });
      
      const saleId = saleResponse.data.id;
      
      // Step 2: Add items individually (server calculates taxes per product)
      for (const item of cart) {
        await apiService.axiosInstance.post(`/sales/${saleId}/items`, {
          product_id: item.id,
          quantity: item.quantity,
          csrf_token: csrfToken
        });
      }
      
      // Step 3: Finalize sale with payment info (no tax data - server calculated)
      const finalizeData = {
        payment_method: paymentMethod,
        ncf_type: 'consumo', // Default NCF type
        csrf_token: csrfToken
      };
      
      // Add cash payment details if needed
      if (paymentMethod === 'cash') {
        finalizeData.cash_received = parseFloat(cashReceived);
        finalizeData.change_amount = change;
      }
      
      // Add customer info if provided
      if (customerData.name) {
        finalizeData.client_name = customerData.name;
      }
      if (customerData.rnc) {
        finalizeData.client_rnc = customerData.rnc;
      }
      
      const finalizeResponse = await apiService.axiosInstance.post(`/sales/${saleId}/finalize`, finalizeData);
      
      // Success - clear cart and close modal
      toast.success('Venta procesada exitosamente');
      setCart([]);
      setShowPaymentModal(false);
      setCashReceived('');
      setCustomerData({ name: '', rnc: '' });
      setSelectedCustomer(null);
      setCustomerSearchTerm('');
      setShowCustomerDropdown(false);
      setValidationErrors({});
      queryClient.invalidateQueries('sales');
      
    } catch (error) {
      console.error('Error creating sale:', error);
      
      // Manejar errores específicos del backend
      if (error.response?.data) {
        const errorData = error.response.data;
        
        // Mostrar mensaje de error específico basado en el tipo
        if (errorData.type === 'validation') {
          toast.error(`Error de validación: ${errorData.user_message || errorData.error}`);
        } else if (errorData.type === 'business') {
          toast.error(`Error de negocio: ${errorData.user_message || errorData.error}`);
        } else if (errorData.type === 'not_found') {
          toast.error(`No encontrado: ${errorData.user_message || errorData.error}`);
        } else if (errorData.type === 'permission') {
          toast.error(`Permiso denegado: ${errorData.user_message || errorData.error}`);
        } else {
          toast.error(errorData.user_message || errorData.error || 'Error al procesar la venta');
        }
        
        // Mostrar detalles específicos si hay
        if (errorData.details) {
          console.error('Detalles del error:', errorData.details);
        }
      } else if (error.message) {
        toast.error(`Error: ${error.message}`);
      } else {
        toast.error('Error desconocido al procesar la venta');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Removed global loading gate to allow cart to render immediately
  // Individual sections will show their own loading states

  return (
    <div className="pos-container">
      {/* Header */}
      <header className="pos-header">
        <div className="header-content">
          <div className="brand-section">
            <img src="/uploads/logos/logo-white.png" alt="Logo" className="header-logo" />
            <div>
              <h1 className="pos-title">Punto de Venta</h1>
              <p className="user-info">
                <i className="bi bi-person-circle"></i>
                {user.name} - {user.role}
                {!navigator.onLine && <span className="offline-indicator">📴</span>}
              </p>
            </div>
          </div>
          
          <div className="header-actions">
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

      <div className="pos-layout">
        {/* Products Section */}
        <div className="products-section">
          {/* Search and Filters */}
          <div className="filters-bar">
            <div className="search-box">
              <i className="bi bi-search"></i>
              <input
                type="text"
                placeholder="Buscar productos..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="search-input"
              />
            </div>
            
            <div className="category-filters">
              <button
                className={`category-btn ${selectedCategory === 'all' ? 'active' : ''}`}
                onClick={() => setSelectedCategory('all')}
              >
                Todos
              </button>
              {categories.map(category => (
                <button
                  key={category.id}
                  className={`category-btn ${selectedCategory === category.id.toString() ? 'active' : ''}`}
                  onClick={() => setSelectedCategory(category.id.toString())}
                >
                  {category.name}
                </button>
              ))}
            </div>
          </div>

          {/* Products Grid */}
          <div className="products-grid">
            {filteredProducts.map(product => (
              <div
                key={product.id}
                className="product-card"
                onClick={() => addToCart(product)}
              >
                <div className="product-image">
                  <i className="bi bi-box"></i>
                </div>
                <div className="product-info">
                  <h3 className="product-name">{product.name}</h3>
                  <p className="product-price">
                    ${product.price?.toFixed(2) || '0.00'}
                  </p>
                  {product.stock <= 5 && (
                    <span className="low-stock-badge">Stock bajo</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Cart Section */}
        <div className="cart-section">
          <div className="cart-header">
            <h2 className="cart-title">
              <i className="bi bi-cart"></i>
              Carrito ({cart.length})
            </h2>
            {cart.length > 0 && (
              <button 
                className="btn btn-outline-danger btn-sm"
                onClick={clearCart}
              >
                <i className="bi bi-trash"></i>
                Limpiar
              </button>
            )}
          </div>

          <div className="cart-items">
            {cart.length === 0 ? (
              <div className="empty-cart">
                <i className="bi bi-cart-x"></i>
                <p>Carrito vacío</p>
                <small>Agrega productos para continuar</small>
              </div>
            ) : (
              cart.map(item => (
                <div key={item.id} className="cart-item">
                  <div className="item-info">
                    <h4 className="item-name">{item.name}</h4>
                    <p className="item-price">${item.price?.toFixed(2)}</p>
                  </div>
                  
                  <div className="quantity-controls">
                    <button
                      className="qty-btn"
                      onClick={() => updateQuantity(item.id, item.quantity - 1)}
                    >
                      <i className="bi bi-dash"></i>
                    </button>
                    <span className="quantity">{item.quantity}</span>
                    <button
                      className="qty-btn"
                      onClick={() => updateQuantity(item.id, item.quantity + 1)}
                    >
                      <i className="bi bi-plus"></i>
                    </button>
                  </div>
                  
                  <div className="item-total">
                    ${(item.price * item.quantity).toFixed(2)}
                  </div>
                  
                  <button
                    className="remove-btn"
                    onClick={() => removeFromCart(item.id)}
                  >
                    <i className="bi bi-x"></i>
                  </button>
                </div>
              ))
            )}
          </div>


          {/* Cart Summary */}
          {cart.length > 0 && (
            <div className="cart-summary">
              <div className="summary-line">
                <span>Subtotal:</span>
                <span>${subtotal.toFixed(2)}</span>
              </div>
              <div className="summary-line">
                <span>ITBIS (18%):</span>
                <span>${previewTax.toFixed(2)}</span>
              </div>
              <div className="summary-line total-line">
                <span>Total:</span>
                <span>${previewTotal.toFixed(2)}</span>
              </div>
              
              <button
                className="btn btn-primary btn-lg checkout-btn"
                onClick={handleProcessSale}
              >
                <i className="bi bi-credit-card"></i>
                Procesar Venta
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Payment Modal */}
      {showPaymentModal && (
        <div className="payment-modal-overlay">
          <div className="payment-modal">
            <div className="modal-header">
              <h3>Procesar Pago</h3>
              <button
                className="close-btn"
                onClick={() => setShowPaymentModal(false)}
              >
                <i className="bi bi-x"></i>
              </button>
            </div>
            
            <div className="modal-body">
              <div className="payment-summary">
                <h4>Total a pagar: ${previewTotal.toFixed(2)}</h4>
              </div>
              
              <div className="payment-methods">
                <h5>Método de pago:</h5>
                <div className="payment-options">
                  <label className="payment-option">
                    <input
                      type="radio"
                      name="paymentMethod"
                      value="cash"
                      checked={paymentMethod === 'cash'}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                    />
                    <i className="bi bi-cash"></i>
                    Efectivo
                  </label>
                  <label className="payment-option">
                    <input
                      type="radio"
                      name="paymentMethod"
                      value="card"
                      checked={paymentMethod === 'card'}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                    />
                    <i className="bi bi-credit-card"></i>
                    Tarjeta
                  </label>
                  <label className="payment-option">
                    <input
                      type="radio"
                      name="paymentMethod"
                      value="transfer"
                      checked={paymentMethod === 'transfer'}
                      onChange={(e) => setPaymentMethod(e.target.value)}
                    />
                    <i className="bi bi-phone"></i>
                    Transferencia
                  </label>
                </div>
              </div>

              {paymentMethod === 'cash' && (
                <div className="cash-payment">
                  <label htmlFor="cashReceived">Efectivo recibido:</label>
                  <input
                    type="number"
                    id="cashReceived"
                    value={cashReceived}
                    onChange={(e) => {
                      setCashReceived(e.target.value);
                      // Limpiar error cuando el usuario empieza a escribir
                      if (validationErrors.cashReceived) {
                        setValidationErrors(prev => ({ ...prev, cashReceived: undefined }));
                      }
                    }}
                    className={`form-control ${validationErrors.cashReceived ? 'is-invalid' : ''}`}
                    placeholder="0.00"
                    step="0.01"
                    min={previewTotal}
                  />
                  {validationErrors.cashReceived && (
                    <div className="validation-error">
                      {validationErrors.cashReceived}
                    </div>
                  )}
                  {cashReceived && !validationErrors.cashReceived && parseFloat(cashReceived) >= previewTotal && (
                    <div className="change-amount">
                      <strong>Cambio: ${change.toFixed(2)}</strong>
                    </div>
                  )}
                </div>
              )}


              <div className="customer-info">
                <h5>Información del cliente (opcional):</h5>
                
                <div className="customer-selector" ref={dropdownRef}>
                  <div className="customer-search-container">
                    <input
                      type="text"
                      placeholder="Buscar cliente o escribir nombre"
                      value={customerSearchTerm}
                      onChange={(e) => {
                        handleCustomerSearchChange(e.target.value);
                        // Limpiar error cuando el usuario empieza a escribir
                        if (validationErrors.customerName) {
                          setValidationErrors(prev => ({ ...prev, customerName: undefined }));
                        }
                      }}
                      onFocus={() => setShowCustomerDropdown(true)}
                      className={`form-control customer-search-input ${validationErrors.customerName ? 'is-invalid' : ''}`}
                    />
                    
                    {selectedCustomer && (
                      <button
                        type="button"
                        className="clear-customer-btn"
                        onClick={clearCustomerSelection}
                        title="Limpiar selección"
                      >
                        <i className="bi bi-x"></i>
                      </button>
                    )}
                  </div>
                  
                  {validationErrors.customerName && (
                    <div className="validation-error">
                      {validationErrors.customerName}
                    </div>
                  )}
                  
                  {showCustomerDropdown && filteredCustomers.length > 0 && (
                    <div className="customer-dropdown">
                      {filteredCustomers.slice(0, 8).map(customer => (
                        <div
                          key={customer.id}
                          className="customer-dropdown-item"
                          onClick={() => selectCustomer(customer)}
                        >
                          <div className="customer-name">{customer.name}</div>
                          {customer.rnc && (
                            <div className="customer-rnc">RNC: {customer.rnc}</div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
                
                <input
                  type="text"
                  placeholder="RNC/Cédula (9 u 11 dígitos)"
                  value={customerData.rnc}
                  onChange={(e) => {
                    setCustomerData(prev => ({ ...prev, rnc: e.target.value }));
                    // Limpiar error cuando el usuario empieza a escribir
                    if (validationErrors.customerRnc) {
                      setValidationErrors(prev => ({ ...prev, customerRnc: undefined }));
                    }
                  }}
                  className={`form-control mt-2 ${validationErrors.customerRnc ? 'is-invalid' : ''}`}
                />
                {validationErrors.customerRnc && (
                  <div className="validation-error">
                    {validationErrors.customerRnc}
                  </div>
                )}
              </div>
            </div>
            
            <div className="modal-footer">
              <button
                className="btn btn-secondary"
                onClick={() => setShowPaymentModal(false)}
              >
                Cancelar
              </button>
              <button
                className="btn btn-primary"
                onClick={handleCompleteSale}
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  'Confirmar Venta'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      <style jsx>{`
        .pos-container {
          min-height: 100vh;
          background: var(--bg-primary);
          color: var(--text-primary);
        }

        .pos-header {
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

        .pos-title {
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

        .pos-layout {
          display: grid;
          grid-template-columns: 1fr 400px;
          height: calc(100vh - 80px);
          max-width: 1400px;
          margin: 0 auto;
          gap: var(--space-lg);
          padding: var(--space-lg);
        }

        .products-section {
          display: flex;
          flex-direction: column;
          gap: var(--space-lg);
        }

        .filters-bar {
          display: flex;
          flex-direction: column;
          gap: var(--space-md);
        }

        .search-box {
          position: relative;
          max-width: 400px;
        }

        .search-box i {
          position: absolute;
          left: var(--space-md);
          top: 50%;
          transform: translateY(-50%);
          color: var(--text-muted);
        }

        .search-input {
          width: 100%;
          padding: var(--space-md) var(--space-md) var(--space-md) 40px;
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          color: var(--text-primary);
          font-size: 1rem;
        }

        .search-input:focus {
          outline: none;
          border-color: var(--text-accent);
        }

        .category-filters {
          display: flex;
          gap: var(--space-sm);
          flex-wrap: wrap;
        }

        .category-btn {
          padding: var(--space-sm) var(--space-md);
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          color: var(--text-secondary);
          cursor: pointer;
          transition: all var(--transition-normal);
        }

        .category-btn:hover,
        .category-btn.active {
          background: var(--text-accent);
          color: white;
          border-color: var(--text-accent);
        }

        .products-grid {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
          gap: var(--space-lg);
          overflow-y: auto;
          padding-right: var(--space-sm);
        }

        .product-card {
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: var(--space-lg);
          cursor: pointer;
          transition: all var(--transition-normal);
          text-align: center;
        }

        .product-card:hover {
          transform: translateY(-4px);
          box-shadow: var(--shadow-lg);
          border-color: var(--text-accent);
        }

        .product-image {
          font-size: 3rem;
          color: var(--text-accent);
          margin-bottom: var(--space-md);
        }

        .product-name {
          font-size: 1rem;
          font-weight: 600;
          margin-bottom: var(--space-sm);
          color: var(--text-primary);
        }

        .product-price {
          font-size: 1.25rem;
          font-weight: 700;
          color: var(--text-accent);
          margin: 0;
        }

        .low-stock-badge {
          display: inline-block;
          background: var(--accent-warning);
          color: white;
          padding: 2px 8px;
          border-radius: var(--radius-sm);
          font-size: 0.75rem;
          margin-top: var(--space-sm);
        }

        .cart-section {
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: var(--space-lg);
          display: flex;
          flex-direction: column;
          height: fit-content;
          max-height: calc(100vh - 120px);
        }

        .cart-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          margin-bottom: var(--space-lg);
          padding-bottom: var(--space-md);
          border-bottom: 1px solid var(--glass-border);
        }

        .cart-title {
          margin: 0;
          font-size: 1.25rem;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: var(--space-sm);
        }

        .cart-items {
          flex: 1;
          overflow-y: auto;
          margin-bottom: var(--space-lg);
        }

        .empty-cart {
          text-align: center;
          padding: var(--space-2xl);
          color: var(--text-muted);
        }

        .empty-cart i {
          font-size: 3rem;
          margin-bottom: var(--space-md);
        }

        .cart-item {
          display: grid;
          grid-template-columns: 1fr auto auto auto;
          gap: var(--space-md);
          align-items: center;
          padding: var(--space-md);
          border-bottom: 1px solid var(--glass-border);
        }

        .item-name {
          font-size: 0.875rem;
          font-weight: 600;
          margin: 0;
        }

        .item-price {
          font-size: 0.75rem;
          color: var(--text-muted);
          margin: 0;
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
        }

        .remove-btn {
          width: 28px;
          height: 28px;
          border: 1px solid rgba(239, 68, 68, 0.3);
          background: rgba(239, 68, 68, 0.1);
          color: #f87171;
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          justify-content: center;
          cursor: pointer;
        }

        .cart-summary {
          border-top: 1px solid var(--glass-border);
          padding-top: var(--space-lg);
        }

        .summary-line {
          display: flex;
          justify-content: space-between;
          margin-bottom: var(--space-sm);
        }

        .total-line {
          font-size: 1.125rem;
          font-weight: 700;
          color: var(--text-accent);
          margin-bottom: var(--space-lg);
          padding-top: var(--space-sm);
          border-top: 1px solid var(--glass-border);
        }

        .checkout-btn {
          width: 100%;
          background: var(--accent-primary);
          border: none;
          border-radius: var(--radius-lg);
          padding: var(--space-md);
          font-weight: 600;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: var(--space-sm);
        }

        .payment-modal-overlay {
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

        .payment-modal {
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-xl);
          max-width: 500px;
          width: 100%;
          max-height: 90vh;
          overflow-y: auto;
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
          padding: var(--space-lg);
        }

        .payment-summary {
          text-align: center;
          margin-bottom: var(--space-xl);
          padding: var(--space-lg);
          background: var(--glass-bg);
          border-radius: var(--radius-lg);
        }

        .payment-summary h4 {
          margin: 0;
          font-size: 1.5rem;
          color: var(--text-accent);
        }

        .payment-methods {
          margin-bottom: var(--space-xl);
        }

        .payment-methods h5 {
          margin-bottom: var(--space-md);
          font-size: 1rem;
          font-weight: 600;
        }

        .payment-options {
          display: grid;
          grid-template-columns: repeat(3, 1fr);
          gap: var(--space-md);
        }

        .payment-option {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: var(--space-sm);
          padding: var(--space-lg);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          cursor: pointer;
          transition: all var(--transition-normal);
        }

        .payment-option:hover {
          border-color: var(--text-accent);
        }

        .payment-option input[type="radio"] {
          margin: 0;
        }

        .payment-option i {
          font-size: 1.5rem;
        }

        .cash-payment {
          margin-bottom: var(--space-xl);
        }

        .cash-payment label {
          display: block;
          margin-bottom: var(--space-sm);
          font-weight: 600;
        }

        .cash-payment input {
          width: 100%;
          padding: var(--space-md);
          background: var(--bg-tertiary);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          color: var(--text-primary);
          font-size: 1.125rem;
          text-align: center;
        }

        .change-amount {
          margin-top: var(--space-md);
          padding: var(--space-md);
          background: var(--accent-success);
          color: white;
          border-radius: var(--radius-lg);
          text-align: center;
        }

        .customer-info {
          margin-bottom: var(--space-xl);
        }

        .customer-info h5 {
          margin-bottom: var(--space-md);
          font-size: 1rem;
          font-weight: 600;
        }

        .customer-info input {
          width: 100%;
          padding: var(--space-md);
          background: var(--bg-tertiary);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          color: var(--text-primary);
        }

        .form-control.is-invalid {
          border-color: #ef4444;
          box-shadow: 0 0 0 2px rgba(239, 68, 68, 0.2);
        }

        .validation-error {
          color: #ef4444;
          font-size: 0.875rem;
          margin-top: var(--space-xs);
          padding: var(--space-xs) var(--space-sm);
          background: rgba(239, 68, 68, 0.1);
          border-radius: var(--radius-sm);
          display: flex;
          align-items: center;
          gap: var(--space-xs);
        }

        .validation-error::before {
          content: "⚠️";
          font-size: 1rem;
        }

        .customer-selector {
          position: relative;
          margin-bottom: var(--space-md);
        }

        .customer-search-container {
          position: relative;
        }

        .customer-search-input {
          width: 100%;
          padding: var(--space-md);
          padding-right: 40px;
          background: var(--bg-tertiary);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          color: var(--text-primary);
          font-size: 1rem;
        }

        .customer-search-input:focus {
          outline: none;
          border-color: var(--text-accent);
          box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
        }

        .clear-customer-btn {
          position: absolute;
          right: var(--space-sm);
          top: 50%;
          transform: translateY(-50%);
          background: none;
          border: none;
          color: var(--text-muted);
          cursor: pointer;
          padding: var(--space-xs);
          border-radius: 50%;
          transition: all var(--transition-fast);
        }

        .clear-customer-btn:hover {
          background: rgba(239, 68, 68, 0.1);
          color: #f87171;
        }

        .customer-dropdown {
          position: absolute;
          top: 100%;
          left: 0;
          right: 0;
          z-index: 1000;
          background: var(--bg-card);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          box-shadow: var(--shadow-lg);
          max-height: 200px;
          overflow-y: auto;
          margin-top: var(--space-xs);
        }

        .customer-dropdown-item {
          padding: var(--space-md);
          cursor: pointer;
          border-bottom: 1px solid var(--glass-border);
          transition: background var(--transition-fast);
        }

        .customer-dropdown-item:last-child {
          border-bottom: none;
        }

        .customer-dropdown-item:hover {
          background: var(--bg-tertiary);
        }

        .customer-name {
          font-weight: 600;
          color: var(--text-primary);
          margin-bottom: var(--space-xs);
        }

        .customer-rnc {
          font-size: 0.875rem;
          color: var(--text-muted);
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
        }

        @media (max-width: 1024px) {
          .pos-layout {
            grid-template-columns: 1fr;
            grid-template-rows: 1fr auto;
          }
          
          .cart-section {
            max-height: 400px;
          }
        }

        @media (max-width: 768px) {
          .pos-layout {
            padding: var(--space-md);
            gap: var(--space-md);
          }
          
          .products-grid {
            grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
          }
          
          .payment-options {
            grid-template-columns: 1fr;
          }
        }
      `}</style>
    </div>
  );
};

export default POSPage;