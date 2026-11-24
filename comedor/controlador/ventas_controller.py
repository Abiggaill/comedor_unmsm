"""Administrator screens for the dining service's order and sales workflow."""

from decimal import Decimal, InvalidOperation
import re

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..modelo.database import db
from ..modelo.venta import Venta
from ..repositorio.ventas_repository import ventas_repository
from .auth_controller import role_required


ventas = Blueprint("ventas", __name__)


@ventas.get("/gestion/ventas")
@role_required("Administrador")
def inicio():
    return render_template(
        "gestion_ventas.html",
        solicitudes=ventas_repository.listar_solicitudes(),
        ventas=ventas_repository.listar_ventas(),
        productos=ventas_repository.productos(),
        clientes=ventas_repository.clientes(),
        documentos=ventas_repository.documentos(),
        formas_pago=Venta.FORMAS_PAGO,
    )


@ventas.post("/gestion/ventas/solicitudes/nueva")
@role_required("Administrador")
def nueva_solicitud():
    cliente_id = request.form.get("cliente_id", "").strip() or None
    cliente_nombre = request.form.get("cliente_nombre", "").strip()
    nota = request.form.get("nota", "").strip()
    if cliente_id:
        try:
            cliente_id = int(cliente_id)
        except ValueError:
            flash("Selecciona un cliente válido.", "error")
            return redirect(url_for("ventas.inicio"))
        with db.connection() as conn:
            cliente = conn.execute(
                """SELECT u.nombres FROM clientes c JOIN usuarios u ON u.id = c.usuario_id
                   WHERE c.id = ? AND c.activo = TRUE""",
                (cliente_id,),
            ).fetchone()
        if not cliente:
            flash("El cliente seleccionado no está disponible.", "error")
            return redirect(url_for("ventas.inicio"))
        cliente_nombre = cliente["nombres"]

    if not cliente_nombre or len(cliente_nombre) > 180 or len(nota) > 500:
        flash("Escribe el nombre del cliente (máximo 180 caracteres) y una nota breve.", "error")
        return redirect(url_for("ventas.inicio"))

    items = []
    productos_ids = request.form.getlist("producto_id")
    cantidades = request.form.getlist("cantidad")
    if len(productos_ids) != len(cantidades) or not productos_ids or len(productos_ids) > 20:
        flash("Agrega entre 1 y 20 productos a la solicitud.", "error")
        return redirect(url_for("ventas.inicio"))

    try:
        with db.connection() as conn:
            for producto_id, cantidad_texto in zip(productos_ids, cantidades):
                producto = conn.execute(
                    "SELECT id, precio FROM productos WHERE id = ? AND activo = TRUE",
                    (int(producto_id),),
                ).fetchone()
                cantidad = Decimal(cantidad_texto)
                if not producto or not cantidad.is_finite() or cantidad <= 0 or cantidad > 100000:
                    raise ValueError
                precio = Decimal(str(producto["precio"] or 0))
                items.append({
                    "producto_id": producto["id"],
                    "cantidad": float(cantidad),
                    "precio_unitario": float(precio),
                })
    except (ValueError, InvalidOperation, TypeError):
        flash("Revisa que cada producto exista y sus cantidades sean positivas.", "error")
        return redirect(url_for("ventas.inicio"))

    try:
        solicitud_id = Venta.crear_solicitud(
            cliente_id, cliente_nombre, session.get("user_id"), nota, items,
        )
    except (ValueError, db.database_error):
        flash("No se pudo guardar la solicitud. Revisa los datos e inténtalo otra vez.", "error")
        return redirect(url_for("ventas.inicio"))
    flash(f"Pedido #{solicitud_id} registrado.", "success")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/solicitudes/<int:solicitud_id>/estado")
@role_required("Administrador")
def cambiar_estado_solicitud(solicitud_id):
    estado = request.form.get("estado", "")
    if estado not in Venta.ESTADOS_SOLICITUD:
        flash("Selecciona un estado válido para la solicitud.", "error")
    elif ventas_repository.cambiar_estado_solicitud(solicitud_id, estado):
        flash("El estado de la solicitud se actualizó.", "success")
    else:
        flash("Solo se puede cambiar una solicitud que todavía está en borrador.", "error")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/solicitudes/<int:solicitud_id>/eliminar")
@role_required("Administrador")
def eliminar_solicitud(solicitud_id):
    if ventas_repository.eliminar_solicitud(solicitud_id):
        flash("Solicitud eliminada.", "success")
    else:
        flash("Solo se eliminan solicitudes en borrador, rechazadas o canceladas.", "error")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/solicitudes/<int:solicitud_id>/convertir")
@role_required("Administrador")
def convertir_solicitud(solicitud_id):
    try:
        venta_id = ventas_repository.convertir_en_venta(
            solicitud_id, session.get("user_id")
        )
    except db.integrity_error:
        venta_id = None
    if venta_id:
        flash(f"Pedido convertido en venta #{venta_id}.", "success")
    else:
        flash("Solo una solicitud aprobada con productos puede convertirse en venta.", "error")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/<int:venta_id>/actualizar")
@role_required("Administrador")
def actualizar_venta(venta_id):
    estado = request.form.get("estado", "")
    forma_pago = request.form.get("forma_pago", "").strip()
    if (
        estado not in Venta.ESTADOS_VENTA
        or len(forma_pago) > 40
        or (estado == "PAGADA" and forma_pago not in Venta.FORMAS_PAGO)
    ):
        flash("Revisa el estado o el nombre de la forma de pago.", "error")
    elif ventas_repository.actualizar_venta(venta_id, estado, forma_pago):
        flash("La venta se actualizó.", "success")
    else:
        flash("No se encontró la venta o ya está anulada.", "error")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/<int:venta_id>/eliminar")
@role_required("Administrador")
def eliminar_venta(venta_id):
    if ventas_repository.eliminar_venta_borrador(venta_id):
        flash("Venta pendiente eliminada; la solicitud volvió a aprobada.", "success")
    else:
        flash("Solo puedes eliminar una venta pendiente sin documentos asociados.", "error")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/<int:venta_id>/documento")
@role_required("Administrador")
def agregar_documento(venta_id):
    tipo = request.form.get("tipo", "")
    numero = request.form.get("numero", "").strip().upper()
    numero = numero.upper()
    if (
        tipo not in Venta.TIPOS_DOCUMENTO
        or len(numero) > 60
        or not re.fullmatch(r"(?!DEMO-)[A-Z0-9]+(?:-[A-Z0-9]+)*", numero)
    ):
        flash("Ingresa un tipo y número de documento emitido en tu sistema autorizado.", "error")
    else:
        try:
            if ventas_repository.crear_documento(venta_id, tipo, numero):
                flash("Número del documento registrado.", "success")
            else:
                flash("Registra la venta como pagada antes de asociar su documento.", "error")
        except db.integrity_error:
            flash("El número ya existe o la venta no es válida.", "error")
    return redirect(url_for("ventas.inicio"))


@ventas.post("/gestion/ventas/documentos/<tipo>/<int:documento_id>/estado")
@role_required("Administrador")
def actualizar_estado_documento(tipo, documento_id):
    tipo = tipo.upper()
    estado = request.form.get("estado", "")
    if tipo not in Venta.ESTADOS_DOCUMENTO or estado not in Venta.ESTADOS_DOCUMENTO[tipo]:
        flash("El tipo o estado del documento no es válido.", "error")
    elif ventas_repository.actualizar_estado_documento(tipo, documento_id, estado):
        flash("El estado del documento se actualizó. Verifica también el sistema que lo emitió.", "success")
    else:
        flash("No se encontró el documento.", "error")
    return redirect(url_for("ventas.inicio"))
