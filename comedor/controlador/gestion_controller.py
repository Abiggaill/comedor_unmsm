"""Staff ticket validation and menu/account administration."""

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

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


@gestion.route("/gestion/usuarios", methods=["GET", "POST"])
@role_required("Administrador")
def usuarios():
    if request.method == "POST":
        usuario_id = request.form.get("usuario_id", type=int)
        rol = request.form.get("rol", "")
        if usuario_id is None:
            flash("No se identificó la cuenta seleccionada.", "error")
        else:
            ok, mensaje = Usuario.cambiar_rol(usuario_id, rol)
            self_changed = ok and usuario_id == session.get("user_id")
            if self_changed:
                session.clear()
                flash("Inicia sesión nuevamente para aplicar el cambio de rol.", "success")
                return redirect(url_for("auth.login"))
            flash(mensaje, "success" if ok else "error")
        return redirect(url_for("gestion.usuarios"))

    return render_template(
        "gestion_usuarios.html",
        usuarios=Usuario.listar_para_gestion(),
        roles=Usuario.ROLES,
        current_user_id=session.get("user_id"),
    )
