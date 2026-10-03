"""Flask application factory for the Comedor UNMSM project."""

import os
from pathlib import Path

from flask import Flask
from flask_wtf.csrf import CSRFProtect

from .controlador.auth_controller import auth
from .controlador.dashboard_controller import dashboard
from .controlador.gestion_controller import gestion
from .modelo.schema import initialize_schema


def create_app(test_config=None):
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    app = Flask(
        __name__,
        template_folder=str(package_root / "vista"),
        static_folder=str(project_root / "static"),
    )
    secret_key = os.environ.get("SECRET_KEY")
    if os.environ.get("RENDER") and not secret_key:
        raise RuntimeError("Configura SECRET_KEY como variable de entorno en Render.")

    app.config.from_mapping(
        SECRET_KEY=secret_key or os.urandom(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER")),
    )
    if test_config:
        app.config.update(test_config)

    initialize_schema()
    CSRFProtect(app)
    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(gestion)
    return app
