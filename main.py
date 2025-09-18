import os
# Configure timezone to GMT -4:00
os.environ['TZ'] = 'GMT+4'  # GMT+4 means UTC-4 (4 hours behind UTC)

from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import bcrypt
from datetime import datetime
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

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
