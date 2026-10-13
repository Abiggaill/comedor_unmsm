"""Staff ticket validation and menu/account administration."""

from datetime import date
from urllib.parse import urlparse

from flask import Blueprint, current_app, flash, jsonify, redirect, render_template, request, session, url_for

from ..modelo.database import db
from ..modelo.menu import Menu
from ..modelo.reserva import Reserva
from ..modelo.usuario import Usuario
from .auth_controller import role_required


gestion = Blueprint("gestion", __name__)
MAX_MENU_IMAGE_SIZE = 5 * 1024 * 1024


@gestion.route("/gestion/menu/subir-imagen", methods=["POST"])
@role_required("Nutricionista", "Administrador")
def subir_imagen_menu():
    cloud_name = current_app.config.get("CLOUDINARY_CLOUD_NAME")
    api_key = current_app.config.get("CLOUDINARY_API_KEY")
    api_secret = current_app.config.get("CLOUDINARY_API_SECRET")
    if not all((cloud_name, api_key, api_secret)):
        return jsonify(error="Falta configurar el almacenamiento de fotos."), 503

    archivo = request.files.get("imagen")
    if not archivo or not archivo.filename:
        return jsonify(error="Selecciona una imagen desde tu computadora."), 400
    if request.content_length and request.content_length > MAX_MENU_IMAGE_SIZE + 256 * 1024:
        return jsonify(error="La foto debe pesar como máximo 5 MB."), 413

    contenido = archivo.stream.read(MAX_MENU_IMAGE_SIZE + 1)
    if len(contenido) > MAX_MENU_IMAGE_SIZE:
        return jsonify(error="La foto debe pesar como máximo 5 MB."), 413
    es_jpeg = contenido.startswith(b"\xff\xd8\xff")
    es_png = contenido.startswith(b"\x89PNG\r\n\x1a\n")
    es_webp = contenido.startswith(b"RIFF") and contenido[8:12] == b"WEBP"
    if not (es_jpeg or es_png or es_webp):
        return jsonify(error="Usa una foto JPG, PNG o WebP."), 400

    try:
        import cloudinary
        import cloudinary.uploader

        cloudinary.config(
            cloud_name=cloud_name,
            api_key=api_key,
            api_secret=api_secret,
            secure=True,
        )
        archivo.stream.seek(0)
        resultado = cloudinary.uploader.upload(
            archivo.stream,
            folder="comedor_unmsm/menus",
            resource_type="image",
            allowed_formats=["jpg", "jpeg", "png", "webp"],
            transformation=[{"width": 1200, "height": 900, "crop": "limit", "quality": "auto", "fetch_format": "auto"}],
        )
        return jsonify(url=resultado["secure_url"])
    except Exception:
        current_app.logger.exception("No se pudo subir la imagen del menú a Cloudinary")
        return jsonify(error="No se pudo subir la foto. Inténtalo nuevamente."), 502


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
    datos_formulario = {}
    try:
        date.fromisoformat(fecha)
    except ValueError:
        fecha = Menu.fecha_actual()
        flash("Selecciona una fecha válida.", "error")

    if request.method == "POST":
        entrada = request.form.get("entrada", "").strip()
        segundo = request.form.get("segundo", "").strip()
        postre_bebida = request.form.get("postre_bebida", "").strip()
        imagenes = {campo: request.form.get(campo, "").strip() for campo in Menu.CAMPOS_IMAGEN}
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
        elif any(
            url
            and (
                len(url) > 2048
                or urlparse(url).scheme != "https"
                or urlparse(url).hostname != "res.cloudinary.com"
                or len(urlparse(url).path.strip("/").split("/")) < 4
                or urlparse(url).path.strip("/").split("/")[1:3] != ["image", "upload"]
            )
            for url in imagenes.values()
        ):
            flash("Usa las fotos subidas desde el botón de Cloudinary.", "error")
        elif not 1 <= cupos_totales <= 100000:
            flash("Ingresa un total de cupos entre 1 y 100000.", "error")
        else:
            try:
                fotos_retiradas = Menu.guardar(
                    fecha, entrada, segundo, postre_bebida, cupos_totales, imagenes
                )
                flash("El menú y sus cupos quedaron guardados.", "success")
                if fotos_retiradas:
                    flash(
                        "Quitamos la foto de cada plato cuyo nombre cambió. Sube la foto nueva para que corresponda al menú.",
                        "error",
                    )
                return redirect(url_for("gestion.menu", fecha=fecha))
            except ValueError as error:
                flash(str(error), "error")

    menu_existente, reservadas = Menu.datos_edicion(fecha)
    cupos_totales = (
        menu_existente["cupos_disponibles"] + reservadas if menu_existente else 100
    )
    if request.method == "POST":
        datos_formulario = {
            "entrada": request.form.get("entrada", "").strip(),
            "segundo": request.form.get("segundo", "").strip(),
            "postre_bebida": request.form.get("postre_bebida", "").strip(),
            **{campo: request.form.get(campo, "").strip() for campo in Menu.CAMPOS_IMAGEN},
        }
        try:
            cupos_totales = int(request.form.get("cupos_totales", cupos_totales))
        except ValueError:
            pass
    return render_template(
        "gestion_menu.html",
        fecha=fecha,
        menu=menu_existente,
        cupos_totales=cupos_totales,
        reservadas=reservadas,
        datos_formulario=datos_formulario,
        cloudinary_configured=all(
            current_app.config.get(variable)
            for variable in ("CLOUDINARY_CLOUD_NAME", "CLOUDINARY_API_KEY", "CLOUDINARY_API_SECRET")
        ),
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
