"""Web package initializer.

Expose the Flask application instance at package level so tests and imports
like `from web import app` return the Flask app object (not the module).
"""

from .app import app  # re-export Flask app instance

__all__ = ["app"]
