import os
import logging
from logging.handlers import RotatingFileHandler
import sys

# Configure timezone to GMT -4:00
os.environ['TZ'] = 'GMT+4'  # GMT+4 means UTC-4 (4 hours behind UTC)

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
from datetime import datetime
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

# Configure logging with rotation
def setup_logging():
    """
    Configura logging centralizado con rotación de archivos
    
    Niveles de log:
    - DEBUG: Información detallada para debugging
    - INFO: Operaciones exitosas y flujo normal
    - WARNING: Validaciones fallidas, errores esperados
    - ERROR: Errores inesperados del servidor
    - CRITICAL: Errores críticos del sistema
    """
    # Crear directorio de logs si no existe
    log_dir = 'logs'
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configurar formato de log detallado
    log_format = logging.Formatter(
        '[%(asctime)s] %(levelname)s [%(name)s:%(lineno)d] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler para archivo con rotación (10 MB por archivo, mantener 10 archivos)
    file_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, 'pos_app.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setFormatter(log_format)
    file_handler.setLevel(logging.INFO)
    
    # Handler para archivo de errores separado
    error_handler = RotatingFileHandler(
        filename=os.path.join(log_dir, 'pos_errors.log'),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=10,
        encoding='utf-8'
    )
    error_handler.setFormatter(log_format)
    error_handler.setLevel(logging.ERROR)
    
    # Handler para consola (solo en desarrollo)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(log_format)
    console_handler.setLevel(logging.DEBUG if os.environ.get("ENVIRONMENT") != "production" else logging.INFO)
    
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Limpiar handlers existentes
    root_logger.handlers.clear()
    
    # Añadir handlers
    root_logger.addHandler(file_handler)
    root_logger.addHandler(error_handler)
    root_logger.addHandler(console_handler)
    
    # Reducir verbosidad de librerías externas
    logging.getLogger('werkzeug').setLevel(logging.WARNING)
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    
    logging.info("Sistema de logging configurado correctamente")

# Inicializar logging al arrancar la aplicación
setup_logging()

# create the app
app = Flask(__name__)

# Add ProxyFix middleware for proper reverse proxy handling (needed for HTTPS url_for)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
# setup a secret key, required by sessions - MUST be set in production
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    if os.environ.get("ENVIRONMENT") == "production":
        raise RuntimeError("SESSION_SECRET environment variable must be set in production")
    else:
        app.secret_key = "dev-secret-key-change-in-production"

# CSRF protection enabled for production security
csrf = CSRFProtect(app)
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # 1 hour token lifetime

# Rate limiting configuration for security
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per hour"],  # Default rate limit for all routes
    storage_uri="memory://"  # Use memory storage for rate limiting
)

# Secure session configuration for production
app.config['SESSION_COOKIE_SECURE'] = os.environ.get("ENVIRONMENT") == "production"
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # Better UX than 'Strict' while still secure

# Make csrf_token available in all templates
@app.context_processor
def inject_csrf_token():
    from flask_wtf.csrf import generate_csrf
    return dict(csrf_token=generate_csrf)
    
# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# Import models and get db instance
import models  # noqa: F401
from models import db

# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

# Database initialization - use proper migration tools for production
# with app.app_context():
#     # Create all database tables - DISABLED for production
#     # Use flask db upgrade or proper migration tools instead
#     db.create_all()

# Printer settings are no longer synced to environment variables
# The system now uses native browser print dialogs exclusively

# Import routes after app initialization
from routes import auth, admin, waiter, api, inventory, dgii, test_api, fiscal_audit


# Register blueprints
app.register_blueprint(auth.bp)
app.register_blueprint(admin.bp)
app.register_blueprint(waiter.bp)
app.register_blueprint(api.bp)
app.register_blueprint(inventory.bp)
app.register_blueprint(dgii.bp)
app.register_blueprint(test_api.bp)
app.register_blueprint(fiscal_audit.bp)


# Main application routes

@app.route('/')
def index():
    """Redirect root to login page"""
    return redirect(url_for('auth.login'))


@app.route('/sw.js')
@limiter.exempt
def service_worker():
    """Serve service worker from root to control entire app scope"""
    from flask import send_from_directory
    return send_from_directory('static', 'sw.js', mimetype='application/javascript')


@app.route('/favicon.ico')
@limiter.exempt
def favicon():
    """Simple favicon endpoint to prevent 404 errors"""
    from flask import send_from_directory
    return send_from_directory('static', 'favicon.ico', mimetype='image/x-icon')

@app.after_request
def add_cache_headers(response):
    """Add proper cache control headers for static vs dynamic content"""
    if request.endpoint in ('static', 'favicon', 'service_worker'):
        # Allow caching for static assets in production, but force reload in development
        if os.environ.get("ENVIRONMENT") == "production":
            # Cache static assets for 1 hour in production
            response.headers['Cache-Control'] = 'public, max-age=3600'
        else:
            # Force reload of static files in development
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
    return response


@app.after_request
def add_security_headers(response):
    """Add security headers for production"""
    
    # Only add security headers in production
    if os.environ.get("ENVIRONMENT") == "production":
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Only disable caching for dynamic content (not static files)
    if request.endpoint not in ('static', 'favicon', 'service_worker'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    return response


# Run the application in development mode
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
