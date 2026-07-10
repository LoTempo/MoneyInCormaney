import hmac
import secrets

from flask import Flask, abort, render_template, request, session

from app.auth import auth_bp
from app.categories import categories_bp
from app.config import Config
from app.db import init_app as init_db_app
from app.dashboard import dashboard_bp
from app.family import family_bp
from app.settings import settings_bp
from app.transactions import transactions_bp


def create_app(test_config=None):
    """Create and configure the Flask application."""

    app = Flask(__name__)
    app.config.from_object(Config)

    if test_config is not None:
        app.config.update(test_config)

    if app.config["APP_ENV"] == "production":
        unsafe_secrets = {
            "development-only-secret-key",
            "replace-this-with-a-random-secret-key",
        }
        if app.config["SECRET_KEY"] in unsafe_secrets:
            raise RuntimeError("Set a secure SECRET_KEY before production start.")

    init_db_app(app)

    def csrf_token():
        token = session.get("_csrf_token")
        if token is None:
            token = secrets.token_urlsafe(32)
            session["_csrf_token"] = token
        return token

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def protect_from_csrf():
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            expected = session.get("_csrf_token", "")
            received = request.form.get("_csrf_token", "")
            if not expected or not hmac.compare_digest(expected, received):
                abort(400)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(family_bp)
    app.register_blueprint(settings_bp)

    @app.after_request
    def add_security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self'; "
            "script-src 'self'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "form-action 'self'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        return response

    @app.errorhandler(400)
    def bad_request(error):
        return render_template("errors/400.html"), 400

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template("errors/500.html"), 500

    return app
