"""Administrator-only CRUD for the dining service's stage-five records."""

from datetime import date
import math
from urllib.parse import urlparse

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..modelo.database import db
from ..repositorio.inventario_repository import inventario_repository
from .auth_controller import role_required


inventario = Blueprint("inventario", __name__)

ENTIDADES = {
    "clientes": {
        "titulo": "Clientes",
        "singular": "cliente",
        "descripcion": "Asocia estudiantes registrados con el servicio del comedor.",
        "columnas": (("cliente", "Estudiante"), ("correo", "Correo"), ("telefono", "Teléfono"), ("activo", "Estado")),
        "campos": (
            {"nombre": "usuario_id", "etiqueta": "Cuenta de estudiante", "tipo": "select", "opciones": "estudiantes", "requerido": True},
            {"nombre": "telefono", "etiqueta": "Teléfono (opcional)", "tipo": "text", "maximo": 30},
            {"nombre": "activo", "etiqueta": "Cliente activo", "tipo": "checkbox"},
        ),
    },
    "proveedores": {
        "titulo": "Proveedores",
        "singular": "proveedor",
        "descripcion": "Guarda los datos de contacto de quienes suministran alimentos e insumos.",
        "columnas": (("razon_social", "Razón social"), ("ruc", "RUC"), ("nombre_contacto", "Contacto"), ("telefono", "Teléfono"), ("correo", "Correo"), ("activo", "Estado")),
        "campos": (
            {"nombre": "razon_social", "etiqueta": "Razón social", "tipo": "text", "requerido": True, "maximo": 180},
            {"nombre": "ruc", "etiqueta": "RUC (opcional)", "tipo": "text", "maximo": 20},
            {"nombre": "nombre_contacto", "etiqueta": "Persona de contacto", "tipo": "text", "maximo": 120},
            {"nombre": "telefono", "etiqueta": "Teléfono", "tipo": "text", "maximo": 30},
            {"nombre": "correo", "etiqueta": "Correo", "tipo": "email", "maximo": 254},
            {"nombre": "direccion", "etiqueta": "Dirección", "tipo": "text", "maximo": 240},
            {"nombre": "activo", "etiqueta": "Proveedor activo", "tipo": "checkbox"},
        ),
    },
    "productos": {
        "titulo": "Productos y platos",
        "singular": "producto",
        "descripcion": "Mantiene un catálogo de platos. El menú publicado se sigue gestionando desde Gestión del menú.",
        "columnas": (("nombre", "Producto o plato"), ("categoria", "Categoría"), ("descripcion", "Descripción"), ("activo", "Estado")),
        "campos": (
            {"nombre": "nombre", "etiqueta": "Nombre del producto o plato", "tipo": "text", "requerido": True, "maximo": 180},
            {"nombre": "categoria", "etiqueta": "Categoría", "tipo": "select", "requerido": True, "opciones": (("Entrada", "Entrada"), ("Segundo", "Segundo"), ("Postre", "Postre"), ("Bebida", "Bebida"), ("Otro", "Otro"))},
            {"nombre": "descripcion", "etiqueta": "Descripción", "tipo": "textarea", "maximo": 1000},
            {"nombre": "imagen_url", "etiqueta": "Enlace de imagen (opcional)", "tipo": "url", "maximo": 2048},
            {"nombre": "activo", "etiqueta": "Producto activo", "tipo": "checkbox"},
        ),
    },
    "insumos": {
        "titulo": "Insumos",
        "singular": "insumo",
        "descripcion": "Registra los ingredientes y la cantidad mínima que se desea mantener.",
        "columnas": (("nombre", "Insumo"), ("unidad_medida", "Unidad"), ("stock_minimo", "Mínimo"), ("stock_actual", "Existencia calculada"), ("activo", "Estado")),
        "campos": (
            {"nombre": "nombre", "etiqueta": "Nombre del insumo", "tipo": "text", "requerido": True, "maximo": 180},
            {"nombre": "unidad_medida", "etiqueta": "Unidad de medida", "tipo": "select", "requerido": True, "opciones": (("kg", "Kilogramo (kg)"), ("g", "Gramo (g)"), ("L", "Litro (L)"), ("ml", "Mililitro (ml)"), ("unidad", "Unidad"), ("paquete", "Paquete"))},
            {"nombre": "stock_minimo", "etiqueta": "Stock mínimo", "tipo": "number", "requerido": True, "minimo": "0", "paso": "0.001"},
            {"nombre": "activo", "etiqueta": "Insumo activo", "tipo": "checkbox"},
        ),
    },
    "mercaderia": {
        "titulo": "Mercadería e inventario",
        "singular": "movimiento de inventario",
        "descripcion": "Registra entradas, salidas o ajustes de insumos, con proveedor, lote y vencimiento cuando corresponda.",
        "columnas": (("insumo", "Insumo"), ("proveedor", "Proveedor"), ("tipo_movimiento", "Movimiento"), ("cantidad", "Cantidad"), ("costo_unitario", "Costo por unidad"), ("lote", "Lote"), ("fecha_vencimiento", "Vencimiento")),
        "campos": (
            {"nombre": "insumo_id", "etiqueta": "Insumo", "tipo": "select", "requerido": True, "opciones": "insumos"},
            {"nombre": "proveedor_id", "etiqueta": "Proveedor (opcional)", "tipo": "select", "opciones": "proveedores"},
            {"nombre": "tipo_movimiento", "etiqueta": "Tipo de movimiento", "tipo": "select", "requerido": True, "opciones": (("ENTRADA", "Entrada al almacén"), ("SALIDA", "Salida del almacén"), ("AJUSTE", "Ajuste de inventario"))},
            {"nombre": "cantidad", "etiqueta": "Cantidad", "tipo": "number", "requerido": True, "minimo": "0.001", "paso": "0.001"},
            {"nombre": "costo_unitario", "etiqueta": "Costo por unidad (opcional)", "tipo": "number", "minimo": "0", "paso": "0.01"},
            {"nombre": "lote", "etiqueta": "Lote (opcional)", "tipo": "text", "maximo": 80},
            {"nombre": "fecha_vencimiento", "etiqueta": "Fecha de vencimiento (opcional)", "tipo": "date"},
            {"nombre": "observacion", "etiqueta": "Observación (opcional)", "tipo": "textarea", "maximo": 500},
        ),
    },
    "servicios": {
        "titulo": "Servicios de comedor",
        "singular": "servicio",
        "descripcion": "Administra tipos de atención, por ejemplo desayuno, almuerzo o cena.",
        "columnas": (("nombre", "Servicio"), ("descripcion", "Descripción"), ("horario_inicio", "Desde"), ("horario_fin", "Hasta"), ("activo", "Estado")),
        "campos": (
            {"nombre": "nombre", "etiqueta": "Nombre del servicio", "tipo": "text", "requerido": True, "maximo": 120},
            {"nombre": "descripcion", "etiqueta": "Descripción", "tipo": "textarea", "maximo": 500},
            {"nombre": "horario_inicio", "etiqueta": "Hora de inicio (opcional)", "tipo": "time"},
            {"nombre": "horario_fin", "etiqueta": "Hora de fin (opcional)", "tipo": "time"},
            {"nombre": "activo", "etiqueta": "Servicio activo", "tipo": "checkbox"},
        ),
    },
}

repo = inventario_repository


def _configuracion(recurso):
    if recurso not in ENTIDADES:
        abort(404)
    return ENTIDADES[recurso]


def _opciones_formulario(recurso, registro_id=None):
    opciones_repo = repo.opciones(recurso, registro_id)
    resultado = {}
    for campo in ENTIDADES[recurso]["campos"]:
        opciones = campo.get("opciones")
        if opciones == "estudiantes":
            resultado[campo["nombre"]] = [
                (str(row["id"]), f'{row["nombres"]} · {row["correo"]}')
                for row in opciones_repo.get("estudiantes", [])
            ]
        elif opciones == "insumos":
            resultado[campo["nombre"]] = [
                (str(row["id"]), f'{row["nombre"]} ({row["unidad_medida"]})')
                for row in opciones_repo.get("insumos", [])
            ]
        elif opciones == "proveedores":
            resultado[campo["nombre"]] = [
                (str(row["id"]), row["razon_social"])
                for row in opciones_repo.get("proveedores", [])
            ]
        elif isinstance(opciones, tuple):
            resultado[campo["nombre"]] = opciones
    return resultado


def _validar_y_convertir(recurso, registro_id=None):
    configuracion = ENTIDADES[recurso]
    datos = {}
    opciones_disponibles = _opciones_formulario(recurso, registro_id)
    for campo in configuracion["campos"]:
        nombre = campo["nombre"]
        valor = request.form.get(nombre, "").strip()
        tipo = campo["tipo"]
        if tipo == "checkbox":
            datos[nombre] = valor in ("1", "on", "true")
            continue
        if campo.get("requerido") and not valor:
            return None, f'Completa el campo «{campo["etiqueta"]}».'
        if campo.get("maximo") and len(valor) > campo["maximo"]:
            return None, f'El campo «{campo["etiqueta"]}» es demasiado largo.'
        if not valor:
            datos[nombre] = None
            continue
        if tipo == "select":
            opciones = opciones_disponibles.get(nombre, [])
            permitidos = {str(valor_opcion) for valor_opcion, _ in opciones}
            if valor not in permitidos:
                return None, f'Selecciona una opción válida para «{campo["etiqueta"]}».'
            datos[nombre] = int(valor) if nombre.endswith("_id") or nombre == "usuario_id" else valor
        elif tipo == "number":
            try:
                numero = float(valor)
            except ValueError:
                return None, f'Escribe un número válido en «{campo["etiqueta"]}».'
            if not math.isfinite(numero) or numero < float(campo.get("minimo", "0")):
                return None, f'El valor de «{campo["etiqueta"]}» está fuera del rango permitido.'
            datos[nombre] = numero
        elif tipo == "email":
            correo = valor.lower()
            if "@" not in correo or "." not in correo.rsplit("@", 1)[-1]:
                return None, "Escribe un correo válido para el proveedor."
            datos[nombre] = correo
        elif tipo == "url":
            parsed = urlparse(valor)
            if parsed.scheme != "https" or not parsed.hostname:
                return None, "El enlace de imagen debe comenzar con https://."
            datos[nombre] = valor
        elif tipo == "date":
            try:
                date.fromisoformat(valor)
            except ValueError:
                return None, "Selecciona una fecha válida."
            datos[nombre] = valor
        else:
            datos[nombre] = valor
    return datos, None


@inventario.route("/gestion/inventario")
@role_required("Administrador")
def inicio():
    return redirect(url_for("inventario.listar", recurso="clientes"))


@inventario.route("/gestion/inventario/<recurso>")
@role_required("Administrador")
def listar(recurso):
    configuracion = _configuracion(recurso)
    filas = repo.listar(recurso)
    return render_template(
        "gestion_inventario.html",
        recurso=recurso,
        configuracion=configuracion,
        filas=filas,
        entidades=ENTIDADES,
    )


@inventario.route("/gestion/inventario/<recurso>/nuevo", methods=["GET", "POST"])
@role_required("Administrador")
def crear(recurso):
    configuracion = _configuracion(recurso)
    if request.method == "POST":
        datos, error = _validar_y_convertir(recurso)
        if error:
            flash(error, "error")
        else:
            try:
                repo.crear(recurso, datos)
                flash(f'El registro de {configuracion["singular"]} se creó correctamente.', "success")
                return redirect(url_for("inventario.listar", recurso=recurso))
            except db.integrity_error:
                flash("No se pudo guardar: revisa que el registro no esté duplicado y que sus relaciones sigan disponibles.", "error")

    return render_template(
        "form_inventario.html",
        recurso=recurso,
        configuracion=configuracion,
        registro=None,
        valores=request.form if request.method == "POST" else {"activo": True},
        opciones=_opciones_formulario(recurso),
        entidades=ENTIDADES,
    )


@inventario.route("/gestion/inventario/<recurso>/<int:registro_id>/editar", methods=["GET", "POST"])
@role_required("Administrador")
def editar(recurso, registro_id):
    configuracion = _configuracion(recurso)
    registro = repo.obtener(recurso, registro_id)
    if not registro:
        flash("No encontramos ese registro.", "error")
        return redirect(url_for("inventario.listar", recurso=recurso))

    if request.method == "POST":
        datos, error = _validar_y_convertir(recurso, registro_id)
        if error:
            flash(error, "error")
        else:
            try:
                if repo.actualizar(recurso, registro_id, datos):
                    flash(f'El registro de {configuracion["singular"]} se actualizó correctamente.', "success")
                    return redirect(url_for("inventario.listar", recurso=recurso))
                flash("No encontramos ese registro.", "error")
            except db.integrity_error:
                flash("No se pudo guardar: revisa que el registro no esté duplicado y que sus relaciones sigan disponibles.", "error")

    valores = request.form if request.method == "POST" else registro
    return render_template(
        "form_inventario.html",
        recurso=recurso,
        configuracion=configuracion,
        registro=registro,
        valores=valores,
        opciones=_opciones_formulario(recurso, registro_id),
        entidades=ENTIDADES,
    )


@inventario.route("/gestion/inventario/<recurso>/<int:registro_id>/eliminar", methods=["POST"])
@role_required("Administrador")
def eliminar(recurso, registro_id):
    configuracion = _configuracion(recurso)
    try:
        if repo.eliminar(recurso, registro_id):
            flash(f'El registro de {configuracion["singular"]} se eliminó.', "success")
        else:
            flash("No encontramos ese registro.", "error")
    except db.integrity_error:
        flash("No se puede eliminar porque otros registros lo necesitan. Conserva el historial y desactiva el registro si ya no se usa.", "error")
    return redirect(url_for("inventario.listar", recurso=recurso))
