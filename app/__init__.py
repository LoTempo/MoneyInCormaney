from flask import Flask, render_template

from app.auth import auth_bp
from app.categories import categories_bp
from app.config import Config
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

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(transactions_bp)
    app.register_blueprint(categories_bp)
    app.register_blueprint(family_bp)
    app.register_blueprint(settings_bp)

    @app.errorhandler(404)
    def page_not_found(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_server_error(error):
        return render_template("errors/500.html"), 500

    return app
