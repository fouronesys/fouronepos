"""
Simple production entry point for Render deployment
"""
import os
import sys

# Ensure all dependencies are available
try:
    from main import app
except ImportError as e:
    print(f"Error importing main app: {e}")
    # Create minimal fallback app
    from flask import Flask
    
    app = Flask(__name__)
    app.secret_key = os.environ.get("SESSION_SECRET", "fallback-secret")
    
    @app.route('/')
    def health_check():
        return "Application is starting...", 503
    
    @app.route('/health')
    def health():
        return "OK", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))