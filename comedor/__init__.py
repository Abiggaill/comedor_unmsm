"""Flask application factory for the Comedor UNMSM project."""

import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, request, session
from flask_wtf.csrf import CSRFProtect

from .controlador.auth_controller import auth
from .controlador.dashboard_controller import dashboard
from .controlador.gestion_controller import gestion
from .controlador.inventario_controller import inventario
from .controlador.reportes_controller import reportes
from .controlador.ventas_controller import ventas
from .modelo.schema import initialize_schema
from .modelo.observer import event_subject


def create_app(test_config=None):
    package_root = Path(__file__).resolve().parent
    project_root = package_root.parent
    load_dotenv(project_root / ".env", override=False)
    app = Flask(
        __name__,
        template_folder=str(package_root / "vista"),
        static_folder=str(project_root / "static"),
    )
    secret_key = os.environ.get("SECRET_KEY")
    is_production = bool(
        os.environ.get("RENDER")
        or os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        or os.environ.get("RAILWAY_SERVICE_ID")
    )
    if is_production and not secret_key:
        raise RuntimeError("Configura SECRET_KEY como variable de entorno en la plataforma de hosting.")

    app.config.from_mapping(
        SECRET_KEY=secret_key or os.urandom(32),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=is_production,
        CLOUDINARY_CLOUD_NAME=os.environ.get("CLOUDINARY_CLOUD_NAME", "").strip(),
        CLOUDINARY_API_KEY=os.environ.get("CLOUDINARY_API_KEY", "").strip(),
        CLOUDINARY_API_SECRET=os.environ.get("CLOUDINARY_API_SECRET", "").strip(),
        MAX_CONTENT_LENGTH=5 * 1024 * 1024 + 256 * 1024,
    )
    if test_config:
        app.config.update(test_config)

    initialize_schema()
    CSRFProtect(app)

    @app.after_request
    def registrar_actividad(response):
        if request.endpoint != "static" and request.path != "/health":
            metodo = request.method
            es_operacion = metodo in {"POST", "PUT", "PATCH", "DELETE"}
            try:
                event_subject.publish(
                    {
                        "actor_user_id": session.get("user_id"),
                        "actor_email": (
                            session.get("correo")
                            or request.form.get("correo", "").strip().lower()[:254]
                            or None
                        ),
                        "tipo": "operacion" if es_operacion else "acceso",
                        "endpoint": request.endpoint or "desconocido",
                        "metodo": metodo,
                        "estado_http": response.status_code,
                        "descripcion": "Solicitud web registrada por Observer.",
                    }
                )
            except Exception:
                app.logger.exception("No se pudo registrar la actividad web")
        return response

    @app.get("/health")
    def health():
        return {"status": "ok"}, 200

    app.register_blueprint(auth)
    app.register_blueprint(dashboard)
    app.register_blueprint(gestion)
    app.register_blueprint(inventario)
    app.register_blueprint(reportes)
    app.register_blueprint(ventas)
    return app
