"""Persistence layer for the academic request-to-sale demonstration."""

from ..modelo.database import db


class VentasRepository:
    def listar_solicitudes(self):
        with db.connection() as conn:
            return conn.execute(
                """SELECT s.id, s.cliente_nombre, s.estado, s.es_demo, s.nota,
                          s.creado_en, COUNT(d.id) AS lineas,
                          COALESCE(SUM(d.subtotal), 0) AS total
                   FROM solicitudes_pedido s
                   LEFT JOIN solicitudes_pedido_detalle d ON d.solicitud_id = s.id
                   GROUP BY s.id, s.cliente_nombre, s.estado, s.es_demo, s.nota, s.creado_en
                   ORDER BY s.id DESC"""
            ).fetchall()

    def listar_ventas(self):
        with db.connection() as conn:
            return conn.execute(
                """SELECT v.id, v.solicitud_id, v.cliente_nombre, v.estado,
                          v.forma_pago, v.total, v.es_demo, v.creado_en,
                          COUNT(d.id) AS lineas
                   FROM ventas v LEFT JOIN ventas_detalle d ON d.venta_id = v.id
                   GROUP BY v.id, v.solicitud_id, v.cliente_nombre, v.estado,
                            v.forma_pago, v.total, v.es_demo, v.creado_en
                   ORDER BY v.id DESC"""
            ).fetchall()

    def productos(self):
        with db.connection() as conn:
            return conn.execute(
                "SELECT id, nombre, precio FROM productos WHERE activo = TRUE ORDER BY nombre"
            ).fetchall()

    def clientes(self):
        with db.connection() as conn:
            return conn.execute(
                """SELECT c.id, u.nombres, u.correo
                   FROM clientes c JOIN usuarios u ON u.id = c.usuario_id
                   WHERE c.activo = TRUE ORDER BY u.nombres"""
            ).fetchall()

    def crear_solicitud(self, cliente_id, cliente_nombre, solicitante_id, nota, items, es_demo=False):
        with db.connection(immediate=True) as conn:
            cursor = conn.execute(
                """INSERT INTO solicitudes_pedido
                   (cliente_id, cliente_nombre, solicitante_id, estado, nota, es_demo)
                   VALUES (?, ?, ?, 'BORRADOR', ?, ?) RETURNING id""",
                (cliente_id, cliente_nombre, solicitante_id, nota, es_demo),
            )
            solicitud_id = cursor.fetchone()["id"]
            for item in items:
                subtotal = round(item["cantidad"] * item["precio_unitario"], 2)
                conn.execute(
                    """INSERT INTO solicitudes_pedido_detalle
                       (solicitud_id, producto_id, cantidad, precio_unitario, subtotal)
                       VALUES (?, ?, ?, ?, ?)""",
                    (solicitud_id, item["producto_id"], item["cantidad"],
                     item["precio_unitario"], subtotal),
                )
            return solicitud_id

    def obtener_solicitud(self, solicitud_id):
        with db.connection() as conn:
            solicitud = conn.execute(
                "SELECT * FROM solicitudes_pedido WHERE id = ?", (solicitud_id,)
            ).fetchone()
            if not solicitud:
                return None, []
            detalle = conn.execute(
                """SELECT d.*, p.nombre AS producto_nombre
                   FROM solicitudes_pedido_detalle d
                   JOIN productos p ON p.id = d.producto_id
                   WHERE d.solicitud_id = ? ORDER BY d.id""",
                (solicitud_id,),
            ).fetchall()
            return solicitud, detalle

    def cambiar_estado_solicitud(self, solicitud_id, estado):
        with db.connection() as conn:
            cursor = conn.execute(
                """UPDATE solicitudes_pedido SET estado = ?
                   WHERE id = ? AND estado = 'BORRADOR'""",
                (estado, solicitud_id),
            )
            return cursor.rowcount > 0

    def eliminar_solicitud(self, solicitud_id):
        with db.connection() as conn:
            cursor = conn.execute(
                "DELETE FROM solicitudes_pedido WHERE id = ? AND estado IN ('BORRADOR','RECHAZADA','CANCELADA')",
                (solicitud_id,),
            )
            return cursor.rowcount > 0

    def convertir_en_venta(self, solicitud_id, vendedor_id):
        with db.connection(immediate=True) as conn:
            solicitud = conn.execute(
                "SELECT * FROM solicitudes_pedido WHERE id = ?", (solicitud_id,)
            ).fetchone()
            if not solicitud or solicitud["estado"] != "APROBADA":
                return None
            lineas = conn.execute(
                "SELECT * FROM solicitudes_pedido_detalle WHERE solicitud_id = ? ORDER BY id",
                (solicitud_id,),
            ).fetchall()
            if not lineas:
                return None
            total = round(sum(float(linea["subtotal"]) for linea in lineas), 2)
            cursor = conn.execute(
                """INSERT INTO ventas
                   (solicitud_id, cliente_id, cliente_nombre, vendedor_id,
                    estado, total, es_demo)
                   VALUES (?, ?, ?, ?, 'PENDIENTE_PAGO', ?, ?) RETURNING id""",
                (solicitud_id, solicitud["cliente_id"], solicitud["cliente_nombre"],
                 vendedor_id, total, solicitud["es_demo"]),
            )
            venta_id = cursor.fetchone()["id"]
            for linea in lineas:
                conn.execute(
                    """INSERT INTO ventas_detalle
                       (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                       VALUES (?, ?, ?, ?, ?)""",
                    (venta_id, linea["producto_id"], linea["cantidad"],
                     linea["precio_unitario"], linea["subtotal"]),
                )
            conn.execute(
                "UPDATE solicitudes_pedido SET estado = 'CONVERTIDA' WHERE id = ?",
                (solicitud_id,),
            )
            return venta_id

    def actualizar_venta(self, venta_id, estado, forma_pago):
        with db.connection() as conn:
            cursor = conn.execute(
                """UPDATE ventas SET estado = ?, forma_pago = ?
                   WHERE id = ? AND estado <> 'ANULADA'""",
                (estado, forma_pago or None, venta_id),
            )
            return cursor.rowcount > 0

    def eliminar_venta_borrador(self, venta_id):
        with db.connection(immediate=True) as conn:
            venta = conn.execute(
                "SELECT solicitud_id FROM ventas WHERE id = ? AND estado = 'PENDIENTE_PAGO'",
                (venta_id,),
            ).fetchone()
            if not venta:
                return False
            tiene_documentos = conn.execute(
                """SELECT 1 FROM comprobantes WHERE venta_id = ?
                   UNION ALL SELECT 1 FROM guias WHERE venta_id = ? LIMIT 1""",
                (venta_id, venta_id),
            ).fetchone()
            if tiene_documentos:
                return False
            conn.execute(
                "UPDATE solicitudes_pedido SET estado = 'APROBADA' WHERE id = ?",
                (venta["solicitud_id"],),
            )
            conn.execute("DELETE FROM ventas WHERE id = ?", (venta_id,))
            return True

    def documentos(self, venta_id=None):
        with db.connection() as conn:
            comprobantes = conn.execute(
                """SELECT id, venta_id, tipo, numero, estado, es_demo, creado_en
                   FROM comprobantes WHERE (? IS NULL OR venta_id = ?)
                   ORDER BY id DESC""",
                (venta_id, venta_id),
            ).fetchall()
            guias = conn.execute(
                """SELECT id, venta_id, 'GUIA' AS tipo, numero, estado, es_demo, creado_en
                   FROM guias WHERE (? IS NULL OR venta_id = ?)
                   ORDER BY id DESC""",
                (venta_id, venta_id),
            ).fetchall()
            return list(comprobantes) + list(guias)

    def crear_documento_demo(self, venta_id, tipo, numero):
        if tipo == "GUIA":
            query = "INSERT INTO guias (venta_id, numero, estado, es_demo) VALUES (?, ?, 'DEMO', TRUE)"
        else:
            query = "INSERT INTO comprobantes (venta_id, tipo, numero, estado, es_demo) VALUES (?, ?, ?, 'DEMO', TRUE)"
        with db.connection() as conn:
            if tipo == "GUIA":
                cursor = conn.execute(query, (venta_id, numero))
            else:
                cursor = conn.execute(query, (venta_id, tipo, numero))
            return cursor.rowcount > 0


ventas_repository = VentasRepository()
