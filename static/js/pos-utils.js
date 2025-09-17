/**
 * POS Utility Functions
 * Common utilities shared across the POS system
 */

// Show notification to user
function showNotification(message, type = 'info') {
    // Create or update notification element
    let notification = document.getElementById('notification');
    if (!notification) {
        notification = document.createElement('div');
        notification.id = 'notification';
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 20px;
            border-radius: 8px;
            z-index: 9999;
            font-weight: 600;
            max-width: 300px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.15);
            transition: all 0.3s ease;
            transform: translateX(100%);
        `;
        document.body.appendChild(notification);
    }
    
    // Set notification style based on type
    const colors = {
        success: 'background: linear-gradient(135deg, #00ff88 0%, #00cc6a 100%); color: #000;',
        error: 'background: linear-gradient(135deg, #ff4757 0%, #ff3742 100%); color: #fff;',
        warning: 'background: linear-gradient(135deg, #ffa500 0%, #ff8c00 100%); color: #000;',
        info: 'background: linear-gradient(135deg, #00d4ff 0%, #0ea5e9 100%); color: #000;'
    };
    
    notification.style.cssText += colors[type] || colors.info;
    notification.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <i class="bi bi-${type === 'success' ? 'check-circle' : type === 'error' ? 'x-circle' : type === 'warning' ? 'exclamation-triangle' : 'info-circle'}"></i>
            <span>${message}</span>
        </div>
    `;
    
    // Show notification
    setTimeout(() => notification.style.transform = 'translateX(0)', 100);
    
    // Hide notification after 5 seconds
    setTimeout(() => {
        notification.style.transform = 'translateX(100%)';
        setTimeout(() => notification.remove(), 300);
    }, 5000);
}

// Get CSRF token from document
function getCsrfToken() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        return metaTag.content;
    }
    
    // Fallback: try to get from hidden input
    const hiddenInput = document.querySelector('input[name="csrf_token"]');
    if (hiddenInput) {
        return hiddenInput.value;
    }
    
    console.error('[Utils] CSRF token not found');
    return null;
}

// Centralized API request function with CSRF and proper error handling
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        credentials: 'same-origin',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        }
    };
    
    // Add CSRF token for non-GET requests
    if (options.method && options.method !== 'GET') {
        const csrfToken = getCsrfToken();
        if (csrfToken) {
            defaultOptions.headers['X-CSRFToken'] = csrfToken;
        }
    }
    
    // Merge options
    const finalOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    try {
        const response = await fetch(url, finalOptions);
        
        // Try to parse JSON response
        let data = {};
        try {
            const text = await response.text();
            if (text) {
                data = JSON.parse(text);
            }
        } catch (parseError) {
            console.error('[API] Failed to parse JSON response:', parseError);
            data = { error: 'Invalid server response' };
        }
        
        // Check if request was successful
        if (!response.ok) {
            const errorMessage = data.error || data.details || `${response.status} ${response.statusText}`;
            throw new Error(errorMessage);
        }
        
        return data;
        
    } catch (error) {
        console.error('[API] Request failed:', error.message || error);
        throw error;
    }
}

// Format currency for Dominican Republic
function formatCurrency(amount) {
    return `RD$ ${parseFloat(amount).toFixed(2)}`;
}

// Validate RNC (Dominican tax ID)
function validateRNC(rnc) {
    // Remove spaces and dashes
    rnc = rnc.replace(/[\s-]/g, '');
    
    // RNC should be 9 digits, Cedula can be 11 digits
    return /^\d{9}$/.test(rnc) || /^\d{11}$/.test(rnc);
}

// Debounce function for input handlers
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Check if element exists before accessing
function safeGetElement(id) {
    const element = document.getElementById(id);
    if (!element) {
        console.warn(`[Utils] Element with id '${id}' not found`);
    }
    return element;
}

// Safe event listener addition with null checks
function safeAddEventListener(elementId, event, handler) {
    const element = safeGetElement(elementId);
    if (element) {
        element.addEventListener(event, handler);
        return true;
    }
    return false;
}

// Format date for Dominican Republic locale
function formatDate(date) {
    if (typeof date === 'string') {
        date = new Date(date);
    }
    return date.toLocaleDateString('es-DO', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit'
    });
}


// Validate form data
function validateRequiredFields(formData, requiredFields) {
    const errors = [];
    
    for (const field of requiredFields) {
        if (!formData[field] || formData[field].toString().trim() === '') {
            errors.push(`El campo ${field} es requerido`);
        }
    }
    
    return errors;
}

// Storage utilities with error handling
const Storage = {
    set(key, value) {
        try {
            localStorage.setItem(key, JSON.stringify(value));
            return true;
        } catch (error) {
            console.error('[Utils] Error saving to storage:', error);
            return false;
        }
    },
    
    get(key, defaultValue = null) {
        try {
            const item = localStorage.getItem(key);
            return item ? JSON.parse(item) : defaultValue;
        } catch (error) {
            console.error('[Utils] Error reading from storage:', error);
            return defaultValue;
        }
    },
    
    remove(key) {
        try {
            localStorage.removeItem(key);
            return true;
        } catch (error) {
            console.error('[Utils] Error removing from storage:', error);
            return false;
        }
    }
};

// Device detection utilities
const Device = {
    isMobile() {
        return window.innerWidth <= 768;
    },
    
    isTablet() {
        return window.innerWidth > 768 && window.innerWidth <= 1024;
    },
    
    isDesktop() {
        return window.innerWidth > 1024;
    },
    
    isTouchDevice() {
        return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
    }
};

// Export utilities to global scope
window.PosUtils = {
    showNotification,
    getCsrfToken,
    formatCurrency,
    validateRNC,
    debounce,
    safeGetElement,
    safeAddEventListener,
    formatDate,
    apiRequest,
    validateRequiredFields,
    Storage,
    Device
};