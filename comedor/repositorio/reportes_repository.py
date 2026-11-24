"""Read-only data sources for the administrator reports dashboard."""

from ..modelo.database import db


# Each report is deliberately selected from a fixed catalog. The SQL is never
# assembled from user-supplied table or column names.
REPORTES = {
    "usuarios": ("Usuarios", "SELECT id, dni, nombres, correo, rol, activo, creado_en FROM usuarios ORDER BY nombres"),
    "clientes": ("Clientes", "SELECT c.id, u.nombres, u.correo, c.telefono, c.ubicacion, c.categoria, c.activo, c.creado_en FROM clientes c JOIN usuarios u ON u.id = c.usuario_id ORDER BY u.nombres"),
    "proveedores": ("Proveedores", "SELECT id, ruc, razon_social, nombre_contacto, telefono, correo, categoria, ubicacion, evaluacion, entregas_esperadas, entregas_cumplidas, activo FROM proveedores ORDER BY razon_social"),
    "productos": ("Productos y platos", "SELECT id, nombre, categoria, descripcion, precio, activo FROM productos ORDER BY categoria, nombre"),
    "insumos": ("Insumos", "SELECT i.id, i.nombre, i.unidad_medida, i.stock_minimo, i.activo, COALESCE(SUM(CASE WHEN m.tipo_movimiento = 'ENTRADA' THEN m.cantidad WHEN m.tipo_movimiento = 'SALIDA' THEN -m.cantidad ELSE m.cantidad END), 0) AS stock_calculado FROM insumos i LEFT JOIN mercaderia m ON m.insumo_id = i.id GROUP BY i.id, i.nombre, i.unidad_medida, i.stock_minimo, i.activo ORDER BY i.nombre"),
    "mercaderia": ("Movimientos de mercadería", "SELECT m.id, i.nombre AS insumo, p.razon_social AS proveedor, m.tipo_movimiento, m.cantidad, i.unidad_medida, m.costo_unitario, m.lote, m.fecha_vencimiento, m.registrado_en, m.observacion FROM mercaderia m JOIN insumos i ON i.id = m.insumo_id LEFT JOIN proveedores p ON p.id = m.proveedor_id ORDER BY m.registrado_en DESC"),
    "servicios": ("Servicios", "SELECT id, nombre, descripcion, horario_inicio, horario_fin, precio, activo FROM servicios ORDER BY nombre"),
    "solicitudes": ("Solicitudes de pedido", "SELECT id, cliente_nombre, estado, nota, es_demo, creado_en FROM solicitudes_pedido ORDER BY creado_en DESC"),
    "ventas": ("Ventas de demostración", "SELECT id, cliente_nombre, estado, forma_pago, total, es_demo, creado_en FROM ventas ORDER BY creado_en DESC"),
    "ventas_por_estado": ("Ventas agrupadas por estado", "SELECT estado, COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total FROM ventas GROUP BY estado ORDER BY estado"),
    "ventas_por_mes": ("Ventas por mes", "SELECT SUBSTR(CAST(creado_en AS TEXT), 1, 7) AS periodo, COUNT(*) AS cantidad, COALESCE(SUM(total), 0) AS total FROM ventas GROUP BY SUBSTR(CAST(creado_en AS TEXT), 1, 7) ORDER BY periodo"),
    "documentos": ("Comprobantes y guías de demostración", "SELECT tipo, numero, estado, venta_id, creado_en FROM comprobantes UNION ALL SELECT 'GUIA' AS tipo, numero, estado, venta_id, creado_en FROM guias ORDER BY creado_en DESC"),
    "reservas": ("Reservas del comedor", "SELECT r.id, u.nombres, u.dni, m.fecha, r.estado, r.codigo_qr FROM reservas r JOIN usuarios u ON u.id = r.usuario_id JOIN menus m ON m.id = r.menu_id ORDER BY m.fecha DESC"),
    "actividad": ("Accesos y actividad", "SELECT a.id, COALESCE(u.nombres, a.actor_email, 'Visitante') AS usuario, a.tipo, a.endpoint, a.metodo, a.estado_http, a.creado_en FROM actividad_sistema a LEFT JOIN usuarios u ON u.id = a.actor_user_id ORDER BY a.creado_en DESC"),
}


class ReportesRepository:
    """Fetch tabular report data for charts and spreadsheet exports."""

    def catalogo(self):
        return [(slug, titulo) for slug, (titulo, _sql) in REPORTES.items()]

    def obtener(self, slug):
        if slug not in REPORTES:
            raise KeyError(slug)
        titulo, sql = REPORTES[slug]
        with db.connection() as conn:
            filas = conn.execute(sql).fetchall()
        filas = [dict(fila) for fila in filas]
        columnas = list(filas[0].keys()) if filas else self._columnas(sql)
        return {"slug": slug, "titulo": titulo, "columnas": columnas, "filas": filas}

    @staticmethod
    def _columnas(sql):
        # Execute the fixed query with a zero-row wrapper to preserve headings
        # even when the report currently has no data.
        with db.connection() as conn:
            cursor = conn.execute(f"SELECT * FROM ({sql}) AS reporte_vacio WHERE 1 = 0")
            return [item[0] for item in cursor.description or ()]


reportes_repository = ReportesRepository()
