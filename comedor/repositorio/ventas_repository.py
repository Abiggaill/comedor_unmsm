"""Persistence layer for operational orders, sales, and document records."""

from decimal import Decimal, ROUND_HALF_UP

from ..modelo.database import db


class VentasRepository:
    def listar_solicitudes(self):
        with db.connection() as conn:
            return conn.execute(
                """SELECT s.id, s.cliente_nombre, s.estado, s.nota,
                          s.creado_en, COUNT(d.id) AS lineas,
                          COALESCE(SUM(d.subtotal), 0) AS total
                   FROM solicitudes_pedido s
                   LEFT JOIN solicitudes_pedido_detalle d ON d.solicitud_id = s.id
                   WHERE s.es_demo = FALSE
                   GROUP BY s.id, s.cliente_nombre, s.estado, s.nota, s.creado_en
                   ORDER BY s.id DESC"""
            ).fetchall()

    def listar_ventas(self):
        with db.connection() as conn:
            return conn.execute(
                """SELECT v.id, v.solicitud_id, v.cliente_nombre, v.estado,
                          v.forma_pago, v.total, v.creado_en,
                          COUNT(d.id) AS lineas
                   FROM ventas v LEFT JOIN ventas_detalle d ON d.venta_id = v.id
                   WHERE v.es_demo = FALSE
                   GROUP BY v.id, v.solicitud_id, v.cliente_nombre, v.estado,
                            v.forma_pago, v.total, v.creado_en
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

    def crear_solicitud(self, cliente_id, cliente_nombre, solicitante_id, nota, items):
        with db.connection(immediate=True) as conn:
            cursor = conn.execute(
                """INSERT INTO solicitudes_pedido
                   (cliente_id, cliente_nombre, solicitante_id, estado, nota, es_demo)
                   VALUES (?, ?, ?, 'BORRADOR', ?, FALSE) RETURNING id""",
                (cliente_id, cliente_nombre, solicitante_id, nota),
            )
            solicitud_id = cursor.fetchone()["id"]
            for item in items:
                subtotal = (Decimal(str(item["cantidad"])) * Decimal(str(item["precio_unitario"])))
                subtotal = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                conn.execute(
                    """INSERT INTO solicitudes_pedido_detalle
                       (solicitud_id, producto_id, cantidad, precio_unitario, subtotal)
                       VALUES (?, ?, ?, ?, ?)""",
                    (solicitud_id, item["producto_id"], item["cantidad"],
                     item["precio_unitario"], str(subtotal)),
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
            if not solicitud or solicitud["estado"] != "APROBADA" or solicitud["es_demo"]:
                return None
            lineas = conn.execute(
                "SELECT * FROM solicitudes_pedido_detalle WHERE solicitud_id = ? ORDER BY id",
                (solicitud_id,),
            ).fetchall()
            if not lineas:
                return None
            total = sum((Decimal(str(linea["subtotal"])) for linea in lineas), Decimal("0.00"))
            total = total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            cursor = conn.execute(
                    """INSERT INTO ventas
                   (solicitud_id, cliente_id, cliente_nombre, vendedor_id,
                    estado, total, es_demo)
                   VALUES (?, ?, ?, ?, 'PENDIENTE_PAGO', ?, FALSE) RETURNING id""",
                (solicitud_id, solicitud["cliente_id"], solicitud["cliente_nombre"],
                 vendedor_id, str(total)),
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
            filtro_comprobante = "AND venta_id = ?" if venta_id is not None else ""
            filtro_guia = "AND venta_id = ?" if venta_id is not None else ""
            parametros = (venta_id,) if venta_id is not None else ()
            comprobantes = conn.execute(
                f"""SELECT id, venta_id, tipo, numero, estado, creado_en
                    FROM comprobantes WHERE es_demo = FALSE {filtro_comprobante}
                    ORDER BY id DESC""",
                parametros,
            ).fetchall()
            guias = conn.execute(
                f"""SELECT id, venta_id, 'GUIA' AS tipo, numero, estado, creado_en
                    FROM guias WHERE es_demo = FALSE {filtro_guia}
                    ORDER BY id DESC""",
                parametros,
            ).fetchall()
            return list(comprobantes) + list(guias)

    def crear_documento(self, venta_id, tipo, numero):
        if tipo == "GUIA":
            query = """INSERT INTO guias (venta_id, numero, estado, es_demo)
                        SELECT id, ?, 'REGISTRADO', FALSE FROM ventas
                        WHERE id = ? AND estado = 'PAGADA' AND es_demo = FALSE"""
            parameters = (numero, venta_id)
        else:
            query = """INSERT INTO comprobantes (venta_id, tipo, numero, estado, es_demo)
                        SELECT id, ?, ?, 'REGISTRADO', FALSE FROM ventas
                        WHERE id = ? AND estado = 'PAGADA' AND es_demo = FALSE"""
            parameters = (tipo, numero, venta_id)
        with db.connection() as conn:
            cursor = conn.execute(query, parameters)
            return cursor.rowcount > 0

    def actualizar_estado_documento(self, tipo, documento_id, estado):
        if tipo == "GUIA":
            query = "UPDATE guias SET estado = ? WHERE id = ? AND es_demo = FALSE"
        else:
            query = "UPDATE comprobantes SET estado = ? WHERE id = ? AND es_demo = FALSE"
        with db.connection() as conn:
            cursor = conn.execute(query, (estado, documento_id))
            return cursor.rowcount > 0


ventas_repository = VentasRepository()
