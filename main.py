import os
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
import bcrypt
from datetime import datetime


class Base(DeclarativeBase):
    pass


db = SQLAlchemy(model_class=Base)

# create the app
app = Flask(__name__)
# setup a secret key, required by sessions - MUST be set in production
app.secret_key = os.environ.get("SESSION_SECRET")
if not app.secret_key:
    if os.environ.get("ENVIRONMENT") == "production":
        raise RuntimeError("SESSION_SECRET environment variable must be set in production")
    else:
        app.secret_key = "dev-secret-key-change-in-production"
# configure the database, relative to the app instance folder
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}

# initialize the app with the extension, flask-sqlalchemy >= 3.0.x
db.init_app(app)

with app.app_context():
    # Make sure to import the models here or their tables won't be created
    import models  # noqa: F401
    db.create_all()


# Import routes after app initialization
from routes import auth, admin, waiter, api


# Register blueprints
app.register_blueprint(auth.bp)
app.register_blueprint(admin.bp)
app.register_blueprint(waiter.bp)
app.register_blueprint(api.bp)


@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    user = models.User.query.get(session['user_id'])
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    
    # Redirect based on user role
    if user.role.value == 'administrador':
        return redirect(url_for('admin.dashboard'))
    elif user.role.value == 'cajero':
        return redirect(url_for('admin.pos'))
    elif user.role.value == 'mesero':
        return redirect(url_for('waiter.tables'))
    
    return redirect(url_for('auth.login'))


# Add security headers for production
@app.after_request
def after_request(response):
    # Only add security headers in production
    if os.environ.get("ENVIRONMENT") == "production":
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    
    # Always disable caching for dynamic content
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


if __name__ == '__main__':
    # Debug mode should only be enabled in development
    debug_mode = os.environ.get("ENVIRONMENT") != "production"
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)