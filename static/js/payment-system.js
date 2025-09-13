/**
 * Payment System for Four One POS
 * Handles payment processing, change calculation, and modal interactions
 */

class PaymentSystem {
    constructor(csrfToken, cartManager) {
        this.csrfToken = csrfToken;
        this.cartManager = cartManager;
        this.currentOrderId = null;
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Payment method change handler
        const paymentMethodSelect = document.getElementById('payment-method-select');
        if (paymentMethodSelect) {
            paymentMethodSelect.addEventListener('change', () => this.toggleCashFields());
        }

        // Cash received input handler
        const cashReceivedInput = document.getElementById('cash-received');
        if (cashReceivedInput) {
            cashReceivedInput.addEventListener('input', () => this.calculateChange());
            cashReceivedInput.addEventListener('change', () => this.calculateChange());
        }

        // NCF type change handler
        const ncfTypeSelect = document.getElementById('ncf-type-select');
        if (ncfTypeSelect) {
            ncfTypeSelect.addEventListener('change', () => this.toggleClientInfo());
        }

        console.log('[Payment] Event listeners setup completed');
    }

    // Toggle cash payment fields based on payment method
    toggleCashFields() {
        const paymentMethod = document.getElementById('payment-method-select')?.value;
        const cashSection = document.getElementById('cash-payment-section');
        
        if (!cashSection) {
            console.warn('[Payment] Cash payment section not found');
            return;
        }

        if (paymentMethod === 'cash') {
            cashSection.style.display = 'block';
            // Auto-fill cash received with total amount
            const total = this.cartManager.getTotals().total;
            const cashReceivedInput = document.getElementById('cash-received');
            if (cashReceivedInput) {
                cashReceivedInput.value = total.toFixed(2);
                this.calculateChange();
            }
        } else {
            cashSection.style.display = 'none';
            const cashReceivedInput = document.getElementById('cash-received');
            const changeDisplay = document.getElementById('change-display');
            if (cashReceivedInput) cashReceivedInput.value = '';
            if (changeDisplay) changeDisplay.textContent = 'RD$ 0.00';
        }
    }

    // Calculate change to be given
    calculateChange() {
        const cashReceivedInput = document.getElementById('cash-received');
        const changeDisplay = document.getElementById('change-display');
        
        if (!cashReceivedInput || !changeDisplay) {
            console.warn('[Payment] Cash input or change display not found');
            return;
        }

        const cashReceived = parseFloat(cashReceivedInput.value) || 0;
        const total = this.cartManager.getTotals().total;
        const change = Math.max(0, cashReceived - total);
        
        changeDisplay.textContent = `RD$ ${change.toFixed(2)}`;
        
        // Add visual feedback for insufficient cash
        if (cashReceived > 0 && cashReceived < total) {
            changeDisplay.style.color = '#dc3545';
            changeDisplay.innerHTML = `<i class="bi bi-exclamation-triangle"></i> RD$ ${change.toFixed(2)} (Insuficiente)`;
        } else if (change > 0) {
            changeDisplay.style.color = '#28a745';
            changeDisplay.innerHTML = `<i class="bi bi-check-circle"></i> RD$ ${change.toFixed(2)}`;
        } else {
            changeDisplay.style.color = '#6c757d';
        }
    }

    // Toggle client information fields based on NCF type
    toggleClientInfo() {
        const ncfType = document.getElementById('ncf-type-select')?.value;
        const clientInfoSection = document.getElementById('client-info-section');
        
        if (!clientInfoSection) {
            console.warn('[Payment] Client info section not found');
            return;
        }

        if (ncfType === 'credito_fiscal' || ncfType === 'gubernamental') {
            clientInfoSection.style.display = 'block';
            // Make fields required
            const clientNameInput = document.getElementById('client-name');
            const clientRncInput = document.getElementById('client-rnc');
            if (clientNameInput) clientNameInput.required = true;
            if (clientRncInput) clientRncInput.required = true;
        } else {
            clientInfoSection.style.display = 'none';
            // Remove required attribute and clear values
            const clientNameInput = document.getElementById('client-name');
            const clientRncInput = document.getElementById('client-rnc');
            if (clientNameInput) {
                clientNameInput.required = false;
                clientNameInput.value = '';
            }
            if (clientRncInput) {
                clientRncInput.required = false;
                clientRncInput.value = '';
            }
        }
    }

    // Validate payment data before processing
    validatePaymentData() {
        const items = this.cartManager.getItems();
        if (items.length === 0) {
            this.showNotification('El carrito está vacío', 'warning');
            return false;
        }

        const ncfType = document.getElementById('ncf-type-select')?.value;
        
        // Validate client info for fiscal/government invoices
        if (ncfType === 'credito_fiscal' || ncfType === 'gubernamental') {
            const clientName = document.getElementById('client-name')?.value.trim();
            const clientRnc = document.getElementById('client-rnc')?.value.trim();
            
            if (!clientName || !clientRnc) {
                this.showNotification('Para comprobantes fiscales y gubernamentales debe completar el nombre/empresa y RNC/cédula', 'error');
                return false;
            }
        }

        // Validate cash payment
        const paymentMethod = document.getElementById('payment-method-select')?.value;
        if (paymentMethod === 'cash') {
            const cashReceived = parseFloat(document.getElementById('cash-received')?.value) || 0;
            const total = this.cartManager.getTotals().total;
            
            if (cashReceived < total) {
                this.showNotification('El efectivo recibido debe ser mayor o igual al total', 'error');
                return false;
            }
        }

        return true;
    }

    // Get payment data for sale finalization
    getPaymentData() {
        const ncfType = document.getElementById('ncf-type-select')?.value || 'consumo';
        const paymentMethod = document.getElementById('payment-method-select')?.value || 'cash';
        
        const paymentData = {
            payment_method: paymentMethod,
            ncf_type: ncfType,
            csrf_token: this.csrfToken
        };

        // Add cash payment details if paying with cash
        if (paymentMethod === 'cash') {
            const cashReceived = parseFloat(document.getElementById('cash-received')?.value) || 0;
            const total = this.cartManager.getTotals().total;
            
            paymentData.cash_received = cashReceived;
            paymentData.change_amount = cashReceived - total;
        }

        // Add client info for fiscal/government invoices
        if (ncfType === 'credito_fiscal' || ncfType === 'gubernamental') {
            paymentData.client_name = document.getElementById('client-name')?.value.trim();
            paymentData.client_rnc = document.getElementById('client-rnc')?.value.trim();
        }

        return paymentData;
    }

    // Process payment for a finalized sale
    async finalizeSale(saleId) {
        if (!this.validatePaymentData()) {
            return false;
        }

        const paymentData = this.getPaymentData();

        try {
            const response = await fetch(`/api/sales/${saleId}/finalize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                credentials: 'same-origin',
                body: JSON.stringify(paymentData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error al finalizar venta');
            }

            const result = await response.json();
            
            if (result.error) {
                throw new Error(result.error);
            }

            return result;

        } catch (error) {
            console.error('[Payment] Error finalizing sale:', error);
            this.showNotification('Error al finalizar venta: ' + error.message, 'error');
            return false;
        }
    }

    // Process table billing
    async processTableBilling(saleId, billingData) {
        try {
            const response = await fetch(`/api/sales/${saleId}/table-finalize`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': this.csrfToken
                },
                body: JSON.stringify({
                    ...billingData,
                    csrf_token: this.csrfToken
                })
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Error procesando factura');
            }

            const result = await response.json();
            return result;

        } catch (error) {
            console.error('[Payment] Error processing table billing:', error);
            throw error;
        }
    }

    // Show notification helper
    showNotification(message, type = 'info') {
        // Check if showNotification function exists globally
        if (typeof showNotification === 'function') {
            showNotification(message, type);
        } else {
            // Fallback to alert
            alert(message);
            console.log(`[Payment] ${type.toUpperCase()}: ${message}`);
        }
    }

    // Initialize payment method on page load
    initializePaymentMethod() {
        // Set default payment method to cash
        const paymentMethodSelect = document.getElementById('payment-method-select');
        if (paymentMethodSelect && !paymentMethodSelect.value) {
            paymentMethodSelect.value = 'cash';
            this.toggleCashFields();
        }

        // Set default NCF type
        const ncfTypeSelect = document.getElementById('ncf-type-select');
        if (ncfTypeSelect && !ncfTypeSelect.value) {
            ncfTypeSelect.value = 'consumo';
            this.toggleClientInfo();
        }
    }
}

// Export for global use
window.PaymentSystem = PaymentSystem;