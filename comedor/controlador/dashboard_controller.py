"""Menu, reservation, and ticket controller."""

import uuid

import qrcode
from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from ..modelo.menu import Menu
from ..modelo.database import db
from ..modelo.reserva import ErrorReserva, Reserva
from .auth_controller import role_required


dashboard = Blueprint("dashboard", __name__)


@dashboard.route("/dashboard")
@role_required("Estudiante")
def inicio():
    menu = Menu.obtener_del_dia()
    reserva = Reserva.buscar_por_usuario_y_menu(session["user_id"], menu["id"]) if menu else None
    qr_data_uri = None
    if reserva and reserva["estado"] == "Reservado" and (
        not reserva["finalizada"] or request.args.get("ver_ticket") == "1"
    ):
        import base64
        import io

        from qrcode.image.svg import SvgPathImage

        qr_buffer = io.BytesIO()
        qrcode.make(reserva["codigo_qr"], image_factory=SvgPathImage).save(qr_buffer)
        qr_data_uri = "data:image/svg+xml;base64," + base64.b64encode(qr_buffer.getvalue()).decode("ascii")
    return render_template(
        "dashboard.html",
        nombres=session.get("nombres", "Estudiante"),
        menu=menu,
        reserva=reserva,
        opciones=Menu.opciones(menu) if menu else None,
        mostrar_ticket=request.args.get("ver_ticket") == "1",
        qr_data_uri=qr_data_uri,
    )


@dashboard.route("/reservar/<int:menu_id>", methods=["POST"])
@role_required("Estudiante")
def reservar(menu_id):
    codigo_qr = f"UNMSM-MENU{menu_id}-{uuid.uuid4().hex[:8].upper()}"

    try:
        entrada = request.form.get("entrada", "").strip()
        segundo = request.form.get("segundo", "").strip()
        postre_bebida = request.form.get("postre_bebida", "").strip()

        Reserva.crear(
            session["user_id"], menu_id, codigo_qr, entrada, segundo, postre_bebida
        )
    except ErrorReserva as error:
        flash(str(error), "error")
        return redirect(url_for("dashboard.inicio"))
    except db.database_error:
        current_app.logger.exception("No se pudo guardar la reserva")
        flash("No se pudo guardar la reserva. Inténtalo nuevamente.", "error")
    except OSError:
        current_app.logger.exception("No se pudo generar el código QR")
        flash("La reserva no pudo completarse porque falló la generación del ticket.", "error")
    else:
        flash("¡Reserva realizada con éxito! Revisa tu ticket digital.", "success")

    return redirect(url_for("dashboard.inicio"))


@dashboard.route("/finalizar/<int:reserva_id>", methods=["POST"])
@role_required("Estudiante")
def finalizar_reserva(reserva_id):
    if Reserva.finalizar(reserva_id, session["user_id"]):
        flash(
            "Listo: tu reserva quedó guardada. Puedes volver a abrir el ticket cuando lo necesites.",
            "success",
        )
    else:
        flash("No encontramos esa reserva en tu cuenta.", "error")
    return redirect(url_for("dashboard.inicio"))
