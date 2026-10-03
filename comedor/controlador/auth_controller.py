"""Authentication and account registration controller."""

from functools import wraps

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from ..modelo.intentos_login import IntentosLogin
from ..modelo.database import db
from ..modelo.usuario import Usuario


auth = Blueprint("auth", __name__)


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


def role_required(*roles):
    def decorate(view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            user_id = session.get("user_id")
            if user_id is None:
                return redirect(url_for("auth.login"))
            rol = Usuario.rol_actual(user_id)
            if rol is None:
                session.clear()
                return redirect(url_for("auth.login"))
            session["rol"] = rol
            if rol not in roles:
                abort(403)
            return view(*args, **kwargs)

        return wrapped_view

    return decorate


@auth.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")

        minutos = IntentosLogin.minutos_bloqueo(correo)
        if minutos:
            flash(
                f"Has agotado los 3 intentos. Vuelve a probar en {minutos} min.",
                "error",
            )
            return render_template("login.html")

        usuario = Usuario.buscar_por_correo(correo)

        if Usuario.verificar_password(usuario, password):
            IntentosLogin.limpiar(correo)
            session.clear()
            session["user_id"] = usuario["id"]
            session["nombres"] = usuario["nombres"]
            session["dni"] = usuario["dni"]
            session["rol"] = usuario["rol"]
            if usuario["rol"] == "Ventanilla":
                return redirect(url_for("gestion.ventanilla"))
            if usuario["rol"] in ("Nutricionista", "Administrador"):
                return redirect(url_for("gestion.menu"))
            return redirect(url_for("dashboard.inicio"))

        intentos, minutos = IntentosLogin.registrar_fallo(correo)
        if minutos:
            flash(
                "Has agotado los 3 intentos. El acceso quedó bloqueado por 15 minutos.",
                "error",
            )
        else:
            restantes = IntentosLogin.MAX_INTENTOS - intentos
            palabra = "intento" if restantes == 1 else "intentos"
            flash(
                f"Correo o contraseña incorrectos. Te quedan {restantes} {palabra}.",
                "error",
            )

    return render_template("login.html")


@auth.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        dni = request.form.get("dni", "").strip()
        nombres = request.form.get("nombres", "").strip()
        correo = request.form.get("correo", "").strip().lower()
        password = request.form.get("password", "")

        if not all((dni, nombres, correo, password)):
            flash("Completa todos los campos para crear tu cuenta.", "error")
            return render_template("registro.html")

        try:
            Usuario.crear(dni, nombres, correo, password)
            IntentosLogin.limpiar(correo)
            flash("¡Cuenta creada con éxito! Inicia sesión.", "success")
            return redirect(url_for("auth.login"))
        except db.integrity_error:
            flash("El DNI o correo ya está registrado.", "error")

    return render_template("registro.html")


@auth.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Sesión cerrada correctamente.", "success")
    return redirect(url_for("auth.login"))
