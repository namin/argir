"""
WSGI entry point for production deployment of ARGIR web frontend.

This module provides the WSGI application object that production servers
like Gunicorn, uWSGI, or mod_wsgi can use to serve the application.

Usage with Gunicorn:
    gunicorn wsgi:application

Usage with uWSGI:
    uwsgi --http :8000 --wsgi-file wsgi.py --callable application

Usage with mod_wsgi:
    Add to Apache configuration:
    WSGIScriptAlias / /path/to/wsgi.py
"""

import os
import sys

# Add the current directory to Python path if needed
if __name__ != '__main__':
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.insert(0, current_dir)

# Import the Flask application
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from web_frontend import app

# The WSGI application object
application = app

# Configure for production
if not app.debug:
    # Disable Flask's development server warning
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)

if __name__ == "__main__":
    # This allows running the WSGI file directly for testing
    # but in production, use a proper WSGI server
    print("⚠️  Running WSGI application directly (development mode)")
    print("   For production, use: gunicorn wsgi:application")
    application.run(host='0.0.0.0', port=8000, debug=False)
