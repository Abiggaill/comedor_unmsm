"""Staff ticket validation and menu/account administration."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..modelo.database import db
from ..modelo.menu import Menu
from ..modelo.reserva import Reserva
from ..modelo.usuario import Usuario
from .auth_controller import role_required


gestion = Blueprint("gestion", __name__)


@gestion.route("/ventanilla", methods=["GET", "POST"])
@role_required("Ventanilla", "Administrador")
def ventanilla():
    resultado = None
    codigo = ""
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        estado, reserva = Reserva.validar_ticket(codigo)
        resultado = {
            "estado": estado,
            "reserva": reserva,
        }
    return render_template("ventanilla.html", resultado=resultado, codigo=codigo)


@gestion.route("/gestion/menu", methods=["GET", "POST"])
@role_required("Nutricionista", "Administrador")
def menu():
    fecha = request.values.get("fecha", "").strip() or Menu.fecha_actual()
    try:
        date.fromisoformat(fecha)
    except ValueError:
        fecha = Menu.fecha_actual()
        flash("Selecciona una fecha válida.", "error")

    if request.method == "POST":
        entrada = request.form.get("entrada", "").strip()
        segundo = request.form.get("segundo", "").strip()
        postre_bebida = request.form.get("postre_bebida", "").strip()
        try:
            cupos_totales = int(request.form.get("cupos_totales", ""))
        except ValueError:
            cupos_totales = 0

        if date.fromisoformat(fecha) < date.fromisoformat(Menu.fecha_actual()):
            flash("No se puede modificar un menú de una fecha pasada.", "error")
        elif not all((entrada, segundo, postre_bebida)):
            flash("Completa las opciones de entrada, segundo y postre o bebida.", "error")
        elif len(entrada) > 500 or len(segundo) > 500 or len(postre_bebida) > 500:
            flash("Cada campo del menú debe tener como máximo 500 caracteres.", "error")
        elif not 1 <= cupos_totales <= 100000:
            flash("Ingresa un total de cupos entre 1 y 100000.", "error")
        else:
            try:
                Menu.guardar(fecha, entrada, segundo, postre_bebida, cupos_totales)
                flash("El menú y sus cupos quedaron guardados.", "success")
                return redirect(url_for("gestion.menu", fecha=fecha))
            except ValueError as error:
                flash(str(error), "error")

    menu_existente, reservadas = Menu.datos_edicion(fecha)
    cupos_totales = (
        menu_existente["cupos_disponibles"] + reservadas if menu_existente else 100
    )
    return render_template(
        "gestion_menu.html",
        fecha=fecha,
        menu=menu_existente,
        cupos_totales=cupos_totales,
        reservadas=reservadas,
    )


@gestion.route("/gestion/usuarios", methods=["GET"])
@role_required("Administrador")
def usuarios():
    lista_usuarios = Usuario.listar_para_gestion()
    return render_template(
        "gestion_usuarios.html",
        usuarios=lista_usuarios,
        roles=Usuario.ROLES,
        current_user_id=session.get("user_id"),
        total_usuarios=len(lista_usuarios),
        total_estudiantes=sum(usuario["rol"] == "Estudiante" for usuario in lista_usuarios),
        total_personal=sum(usuario["rol"] != "Estudiante" for usuario in lista_usuarios),
    )


def _datos_formulario_usuario():
    return {
        "dni": request.form.get("dni", "").strip(),
        "nombres": request.form.get("nombres", "").strip(),
        "correo": request.form.get("correo", "").strip().lower(),
        "rol": request.form.get("rol", "").strip(),
    }


def _validar_datos_usuario(datos, password=None, password_requerido=False):
    if not all(datos.values()):
        return "Completa todos los campos obligatorios."
    if len(datos["dni"]) > 20:
        return "El DNI o código estudiantil no puede superar 20 caracteres."
    if len(datos["nombres"]) > 120:
        return "El nombre no puede superar 120 caracteres."
    partes_correo = datos["correo"].split("@")
    if (
        len(datos["correo"]) > 254
        or len(partes_correo) != 2
        or not partes_correo[0]
        or "." not in partes_correo[1]
        or any(not parte for parte in partes_correo[1].split("."))
        or any(caracter.isspace() for caracter in datos["correo"])
    ):
        return "Escribe un correo válido."
    if datos["rol"] not in Usuario.ROLES:
        return "Selecciona un rol válido."
    if password_requerido and not password:
        return "Escribe una contraseña inicial."
    if password and len(password) < 8:
        return "La contraseña debe tener al menos 8 caracteres."
    if password and len(password) > 128:
        return "La contraseña no puede superar 128 caracteres."
    return None


@gestion.route("/gestion/usuarios/nuevo", methods=["GET", "POST"])
@role_required("Administrador")
def nuevo_usuario():
    if request.method == "POST":
        datos = _datos_formulario_usuario()
        password = request.form.get("password", "")
        error = _validar_datos_usuario(datos, password, password_requerido=True)
        if error:
            flash(error, "error")
        else:
            try:
                Usuario.crear(
                    datos["dni"], datos["nombres"], datos["correo"], password, datos["rol"]
                )
                flash("La cuenta se creó correctamente.", "success")
                return redirect(url_for("gestion.usuarios"))
            except db.integrity_error:
                flash("Ese DNI o correo ya está registrado.", "error")

    return render_template(
        "form_usuario.html",
        usuario=None,
        roles=Usuario.ROLES,
        datos=_datos_formulario_usuario() if request.method == "POST" else {},
    )


@gestion.route("/gestion/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@role_required("Administrador")
def editar_usuario(usuario_id):
    usuario = Usuario.buscar_para_gestion(usuario_id)
    if not usuario:
        flash("No encontramos esa cuenta.", "error")
        return redirect(url_for("gestion.usuarios"))

    if request.method == "POST":
        datos = _datos_formulario_usuario()
        password = request.form.get("password", "")
        error = _validar_datos_usuario(datos, password)
        if error:
            flash(error, "error")
        else:
            try:
                ok, mensaje = Usuario.actualizar_desde_admin(
                    usuario_id,
                    datos["dni"],
                    datos["nombres"],
                    datos["correo"],
                    datos["rol"],
                    password or None,
                )
                flash(mensaje, "success" if ok else "error")
                if ok:
                    if usuario_id == session.get("user_id"):
                        if datos["rol"] != "Administrador":
                            session.clear()
                            flash(
                                "Inicia sesión nuevamente para aplicar el cambio de rol.",
                                "success",
                            )
                            return redirect(url_for("auth.login"))
                        session["nombres"] = datos["nombres"]
                    return redirect(url_for("gestion.usuarios"))
            except db.integrity_error:
                flash("Ese DNI o correo ya pertenece a otra cuenta.", "error")

        usuario = {**usuario, **datos}

    return render_template(
        "form_usuario.html",
        usuario=usuario,
        roles=Usuario.ROLES,
        datos={},
    )


@gestion.route("/gestion/usuarios/<int:usuario_id>/eliminar", methods=["POST"])
@role_required("Administrador")
def eliminar_usuario(usuario_id):
    if usuario_id == session.get("user_id"):
        flash("No puedes eliminar la cuenta con la que tienes abierta esta sesión.", "error")
        return redirect(url_for("gestion.usuarios"))

    try:
        ok, mensaje = Usuario.eliminar_desde_admin(usuario_id)
        flash(mensaje, "success" if ok else "error")
    except db.integrity_error:
        flash("No se pudo eliminar: la cuenta tiene información relacionada que debe conservarse.", "error")
    return redirect(url_for("gestion.usuarios"))
