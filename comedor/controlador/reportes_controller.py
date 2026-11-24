"""Administrator reports with interactive charts and XLSX download."""

from io import BytesIO

from flask import Blueprint, abort, jsonify, render_template, send_file

from ..repositorio.reportes_repository import reportes_repository
from .auth_controller import role_required


reportes = Blueprint("reportes", __name__)


@reportes.get("/gestion/reportes")
@role_required("Administrador")
def inicio():
    return render_template("gestion_reportes.html", reportes=reportes_repository.catalogo())


@reportes.get("/gestion/reportes/<slug>")
@role_required("Administrador")
def datos(slug):
    try:
        return jsonify(reportes_repository.obtener(slug))
    except KeyError:
        abort(404)


@reportes.get("/gestion/reportes/<slug>/excel")
@role_required("Administrador")
def descargar(slug):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    try:
        reporte = reportes_repository.obtener(slug)
    except KeyError:
        abort(404)

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Reporte"
    hoja.append([reporte["titulo"]])
    hoja["A1"].font = Font(bold=True, size=14, color="FFFFFF")
    hoja["A1"].fill = PatternFill("solid", fgColor="234B36")
    hoja.append(reporte["columnas"])
    for celda in hoja[2]:
        celda.font = Font(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor="397A57")
    for fila in reporte["filas"]:
        valores = []
        for columna in reporte["columnas"]:
            valor = fila.get(columna)
            if isinstance(valor, str) and valor.startswith(("=", "+", "-", "@")):
                valor = "'" + valor
            valores.append(valor)
        hoja.append(valores)
    hoja.freeze_panes = "A3"
    hoja.auto_filter.ref = hoja.dimensions
    for columna in hoja.columns:
        letra = columna[0].column_letter
        ancho = min(40, max(12, max(len(str(c.value or "")) for c in columna) + 2))
        hoja.column_dimensions[letra].width = ancho

    salida = BytesIO()
    libro.save(salida)
    salida.seek(0)
    return send_file(
        salida,
        as_attachment=True,
        download_name=f"reporte_{slug}.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
