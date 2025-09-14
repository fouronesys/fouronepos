import React from 'react';

const LoadingSpinner = ({ message = 'Cargando...', size = 'md' }) => {
  const sizeClasses = {
    sm: 'spinner-sm',
    md: 'spinner-md',
    lg: 'spinner-lg'
  };

  return (
    <div className="loading-spinner-container">
      <div className={`loading-spinner ${sizeClasses[size]}`}>
        <div className="spinner-ring"></div>
        <div className="spinner-ring"></div>
        <div className="spinner-ring"></div>
        <div className="spinner-ring"></div>
      </div>
      {message && (
        <div className="loading-message">{message}</div>
      )}

      <style jsx>{`
        .loading-spinner-container {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          gap: var(--space-md);
        }

        .loading-spinner {
          position: relative;
          display: inline-block;
        }

        .spinner-sm {
          width: 32px;
          height: 32px;
        }

        .spinner-md {
          width: 48px;
          height: 48px;
        }

        .spinner-lg {
          width: 64px;
          height: 64px;
        }

        .spinner-ring {
          position: absolute;
          border: 3px solid transparent;
          border-top: 3px solid var(--text-accent);
          border-radius: 50%;
          animation: spin 1.2s cubic-bezier(0.5, 0, 0.5, 1) infinite;
        }

        .spinner-sm .spinner-ring {
          width: 32px;
          height: 32px;
        }

        .spinner-md .spinner-ring {
          width: 48px;
          height: 48px;
        }

        .spinner-lg .spinner-ring {
          width: 64px;
          height: 64px;
        }

        .spinner-ring:nth-child(1) {
          animation-delay: -0.45s;
          border-top-color: var(--text-accent);
        }

        .spinner-ring:nth-child(2) {
          animation-delay: -0.3s;
          border-top-color: var(--text-accent-bright);
        }

        .spinner-ring:nth-child(3) {
          animation-delay: -0.15s;
          border-top-color: rgba(96, 165, 250, 0.6);
        }

        .spinner-ring:nth-child(4) {
          border-top-color: rgba(96, 165, 250, 0.3);
        }

        @keyframes spin {
          0% {
            transform: rotate(0deg);
          }
          100% {
            transform: rotate(360deg);
          }
        }

        .loading-message {
          color: var(--text-secondary);
          font-size: 0.875rem;
          text-align: center;
          font-weight: 500;
        }

        .loading-spinner-container.inline {
          flex-direction: row;
          gap: var(--space-sm);
        }

        .loading-spinner-container.inline .loading-message {
          margin: 0;
        }
      `}</style>
    </div>
  );
};

export default LoadingSpinner;