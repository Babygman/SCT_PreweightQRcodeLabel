from logging.config import dictConfig
from pathlib import Path

from flask import Flask, render_template

from config import CONFIGS

from .extensions import csrf, db, login_manager, migrate


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
    csrf.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @app.get("/")
    def index():
        return render_template("index.html")

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
