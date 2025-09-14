import React, { useState, useEffect } from 'react';
import apiService from '../services/apiService';

const OfflineIndicator = ({ isOffline }) => {
  const [syncStatus, setSyncStatus] = useState({ queueSize: 0 });
  const [showDetails, setShowDetails] = useState(false);

  useEffect(() => {
    const updateSyncStatus = async () => {
      try {
        const status = await apiService.getOfflineStatus();
        setSyncStatus(status);
      } catch (error) {
        console.warn('Could not get offline status:', error);
      }
    };

    if (isOffline) {
      updateSyncStatus();
      const interval = setInterval(updateSyncStatus, 5000);
      return () => clearInterval(interval);
    }
  }, [isOffline]);

  if (!isOffline && syncStatus.queueSize === 0) return null;

  return (
    <div className={`offline-indicator ${isOffline ? 'offline' : 'syncing'}`}>
      <div className="offline-indicator-content" onClick={() => setShowDetails(!showDetails)}>
        <div className="status-icon">
          {isOffline ? '📴' : '🔄'}
        </div>
        <div className="status-text">
          {isOffline ? 'Modo Offline' : 'Sincronizando...'}
        </div>
        {syncStatus.queueSize > 0 && (
          <div className="queue-badge">
            {syncStatus.queueSize}
          </div>
        )}
      </div>
      
      {showDetails && (
        <div className="offline-details">
          <div className="detail-item">
            <span>Estado:</span>
            <span>{isOffline ? 'Sin conexión' : 'Conectado'}</span>
          </div>
          {syncStatus.queueSize > 0 && (
            <div className="detail-item">
              <span>Pendientes:</span>
              <span>{syncStatus.queueSize} operaciones</span>
            </div>
          )}
          {syncStatus.storageSize && (
            <div className="detail-item">
              <span>Almacenado:</span>
              <span>{syncStatus.storageSize}</span>
            </div>
          )}
        </div>
      )}

      <style jsx>{`
        .offline-indicator {
          position: fixed;
          top: 10px;
          right: 10px;
          z-index: 9999;
          background: var(--glass-bg);
          backdrop-filter: blur(20px);
          border: 1px solid var(--glass-border);
          border-radius: var(--radius-lg);
          padding: var(--space-sm) var(--space-md);
          color: var(--text-primary);
          font-size: 0.875rem;
          box-shadow: var(--shadow-lg);
          cursor: pointer;
          transition: all var(--transition-normal);
        }

        .offline-indicator.offline {
          background: rgba(239, 68, 68, 0.1);
          border-color: rgba(239, 68, 68, 0.3);
        }

        .offline-indicator.syncing {
          background: rgba(34, 197, 94, 0.1);
          border-color: rgba(34, 197, 94, 0.3);
        }

        .offline-indicator:hover {
          transform: translateY(-2px);
          box-shadow: var(--shadow-xl);
        }

        .offline-indicator-content {
          display: flex;
          align-items: center;
          gap: var(--space-sm);
        }

        .status-icon {
          font-size: 1rem;
        }

        .status-text {
          font-weight: 500;
        }

        .queue-badge {
          background: var(--accent-warning);
          color: white;
          border-radius: 50%;
          width: 20px;
          height: 20px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 0.75rem;
          font-weight: bold;
        }

        .offline-details {
          margin-top: var(--space-sm);
          padding-top: var(--space-sm);
          border-top: 1px solid var(--glass-border);
        }

        .detail-item {
          display: flex;
          justify-content: space-between;
          margin-bottom: var(--space-xs);
          font-size: 0.8rem;
        }

        .detail-item span:first-child {
          opacity: 0.7;
        }

        @media (max-width: 768px) {
          .offline-indicator {
            position: fixed;
            bottom: 10px;
            right: 10px;
            top: auto;
          }
        }
      `}</style>
    </div>
  );
};

export default OfflineIndicator;