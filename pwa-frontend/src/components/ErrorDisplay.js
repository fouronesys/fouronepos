import React from 'react';

const ErrorDisplay = ({ 
  error, 
  type = 'validation', 
  details = null, 
  suggestion = null,
  onRetry = null,
  onDismiss = null,
  className = ''
}) => {
  // Configuración de íconos y colores por tipo de error
  const errorConfig = {
    validation: {
      icon: '⚠️',
      color: '#f59e0b',
      bgColor: '#fef3c7',
      borderColor: '#fbbf24',
      title: 'Error de Validación'
    },
    business: {
      icon: '⚠️',
      color: '#f59e0b',
      bgColor: '#fef3c7',
      borderColor: '#fbbf24',
      title: 'Acción No Permitida'
    },
    permission: {
      icon: '🔒',
      color: '#dc2626',
      bgColor: '#fee2e2',
      borderColor: '#f87171',
      title: 'Acceso Denegado'
    },
    not_found: {
      icon: '🔍',
      color: '#6b7280',
      bgColor: '#f3f4f6',
      borderColor: '#9ca3af',
      title: 'No Encontrado'
    },
    server: {
      icon: '❌',
      color: '#dc2626',
      bgColor: '#fee2e2',
      borderColor: '#f87171',
      title: 'Error del Servidor'
    },
    network: {
      icon: '📡',
      color: '#dc2626',
      bgColor: '#fee2e2',
      borderColor: '#f87171',
      title: 'Error de Conexión'
    }
  };

  const config = errorConfig[type] || errorConfig.validation;

  // Generar sugerencia automática basada en el tipo de error
  const getAutoSuggestion = () => {
    if (suggestion) return suggestion;

    switch (type) {
      case 'validation':
        return 'Por favor, revisa los datos ingresados y corrige los campos marcados en rojo.';
      case 'business':
        return 'Verifica que se cumplan todas las condiciones necesarias para realizar esta operación.';
      case 'permission':
        return 'Contacta al administrador si necesitas realizar esta acción.';
      case 'not_found':
        return 'El recurso solicitado no existe. Intenta buscar nuevamente.';
      case 'server':
        return 'Si el problema persiste, contacta al soporte técnico.';
      case 'network':
        return 'Verifica tu conexión a internet e intenta nuevamente.';
      default:
        return null;
    }
  };

  const autoSuggestion = getAutoSuggestion();

  return (
    <div className={`error-display error-display-${type} ${className}`}>
      <div className="error-header">
        <span className="error-icon">{config.icon}</span>
        <div className="error-content">
          <h4 className="error-title">{config.title}</h4>
          <p className="error-message">{error}</p>
        </div>
        {onDismiss && (
          <button 
            className="error-dismiss" 
            onClick={onDismiss}
            aria-label="Cerrar"
          >
            ×
          </button>
        )}
      </div>

      {details && (
        <div className="error-details">
          <strong>Detalles:</strong> {details}
        </div>
      )}

      {autoSuggestion && (
        <div className="error-suggestion">
          <strong>💡 Sugerencia:</strong> {autoSuggestion}
        </div>
      )}

      {onRetry && type === 'network' && (
        <div className="error-actions">
          <button 
            className="retry-button" 
            onClick={onRetry}
          >
            🔄 Reintentar
          </button>
        </div>
      )}

      <style jsx>{`
        .error-display {
          border-radius: 8px;
          padding: 1rem;
          margin: 1rem 0;
          border-left: 4px solid ${config.borderColor};
          background-color: ${config.bgColor};
          box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
          animation: slideIn 0.3s ease-out;
        }

        @keyframes slideIn {
          from {
            opacity: 0;
            transform: translateY(-10px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }

        .error-header {
          display: flex;
          align-items: flex-start;
          gap: 0.75rem;
        }

        .error-icon {
          font-size: 1.5rem;
          flex-shrink: 0;
          line-height: 1;
        }

        .error-content {
          flex: 1;
        }

        .error-title {
          margin: 0 0 0.25rem 0;
          font-size: 0.95rem;
          font-weight: 600;
          color: ${config.color};
        }

        .error-message {
          margin: 0;
          font-size: 0.9rem;
          color: #374151;
          line-height: 1.5;
        }

        .error-dismiss {
          background: none;
          border: none;
          font-size: 1.5rem;
          color: #6b7280;
          cursor: pointer;
          padding: 0;
          width: 24px;
          height: 24px;
          display: flex;
          align-items: center;
          justify-content: center;
          border-radius: 4px;
          transition: background-color 0.2s;
          flex-shrink: 0;
        }

        .error-dismiss:hover {
          background-color: rgba(0, 0, 0, 0.1);
        }

        .error-details {
          margin-top: 0.75rem;
          padding-top: 0.75rem;
          border-top: 1px solid rgba(0, 0, 0, 0.1);
          font-size: 0.85rem;
          color: #4b5563;
          line-height: 1.5;
        }

        .error-details strong {
          color: #374151;
        }

        .error-suggestion {
          margin-top: 0.75rem;
          padding: 0.75rem;
          background-color: rgba(255, 255, 255, 0.5);
          border-radius: 6px;
          font-size: 0.85rem;
          color: #4b5563;
          line-height: 1.5;
        }

        .error-suggestion strong {
          color: #374151;
        }

        .error-actions {
          margin-top: 0.75rem;
          display: flex;
          gap: 0.5rem;
        }

        .retry-button {
          background-color: ${config.color};
          color: white;
          border: none;
          padding: 0.5rem 1rem;
          border-radius: 6px;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: opacity 0.2s;
        }

        .retry-button:hover {
          opacity: 0.9;
        }

        .retry-button:active {
          transform: scale(0.98);
        }

        /* Variantes compactas */
        .error-display.compact {
          padding: 0.75rem;
          margin: 0.5rem 0;
        }

        .error-display.compact .error-title {
          font-size: 0.875rem;
        }

        .error-display.compact .error-message {
          font-size: 0.875rem;
        }

        /* Variante inline para campos de formulario */
        .error-display.inline {
          padding: 0.5rem 0.75rem;
          margin: 0.25rem 0;
          border-left-width: 3px;
          box-shadow: none;
        }

        .error-display.inline .error-header {
          gap: 0.5rem;
        }

        .error-display.inline .error-icon {
          font-size: 1.25rem;
        }

        .error-display.inline .error-title {
          font-size: 0.875rem;
        }

        .error-display.inline .error-message {
          font-size: 0.85rem;
        }
      `}</style>
    </div>
  );
};

export default ErrorDisplay;
