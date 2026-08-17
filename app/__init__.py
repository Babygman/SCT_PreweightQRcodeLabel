from logging.config import dictConfig
from pathlib import Path

from flask import Flask, render_template, session
from flask_login import current_user, login_required

from config import CONFIGS

from .extensions import csrf, db, login_manager, migrate
from .presentation import format_local_datetime


def create_app(config_name="development"):
    config_class = CONFIGS.get(config_name)
    if config_class is None:
        raise RuntimeError(f"Unknown APP_ENV: {config_name}")
    config_class.validate()

    dictConfig(
        {
            "version": 1,
            "formatters": {
                "default": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}
            },
            "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
            "root": {"level": "INFO", "handlers": ["console"]},
        }
    )

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    csrf.init_app(app)

    @app.template_filter("local_datetime")
    def local_datetime_filter(value):
        return format_local_datetime(value, app.config["APP_TIMEZONE"])

    from .models import Station, User

    @login_manager.user_loader
    def load_user(user_id):
        user = db.session.get(User, int(user_id))
        return user if user is not None and user.is_active else None

    from .auth import bp as auth_bp
    from .auth.decorators import roles_required, station_required
    from .auth.uat_bypass import register_uat_bypass
    from .master_data import bp as master_data_bp
    from .mock_erp import bp as mock_erp_bp
    from .preparation import bp as preparation_bp
    from .weighing import bp as weighing_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(master_data_bp)
    app.register_blueprint(mock_erp_bp)
    app.register_blueprint(preparation_bp)
    app.register_blueprint(weighing_bp)
    register_uat_bypass(app)

    @app.context_processor
    def application_context():
        station = None
        if current_user.is_authenticated and session.get("station_id"):
            station = db.session.get(Station, session["station_id"])
        return {"selected_station": station}

    @app.get("/")
    @login_required
    @station_required
    @roles_required("OPERATOR", "PRODUCTION", "SUPERVISOR", "ADMIN")
    def index():
        return render_template("index.html")

    @app.errorhandler(403)
    def forbidden(_error):
        return render_template("errors/403.html"), 403

    @app.errorhandler(404)
    def not_found(_error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        app.logger.exception("Unhandled application error", exc_info=error)
        return render_template("errors/500.html"), 500

    from .cli import register_commands

    register_commands(app)
    app.logger.info("Application initialized with environment=%s", config_name)
    return app
