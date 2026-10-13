"""Persistence operations for the dining inventory and catalog CRUD."""

from ..modelo.database import db


class InventarioRepository:
    """Keep SQL for clients, suppliers, inventory, products, inputs and services."""

    _ENTIDADES = {
        "clientes": {
            "tabla": "clientes",
            "campos": ("usuario_id", "telefono", "activo"),
            "lista": """SELECT c.id, c.usuario_id, u.nombres AS cliente,
                              u.correo, c.telefono, c.activo
                       FROM clientes c JOIN usuarios u ON u.id = c.usuario_id
                       ORDER BY u.nombres, c.id""",
        },
        "proveedores": {
            "tabla": "proveedores",
            "campos": (
                "ruc", "razon_social", "nombre_contacto", "telefono",
                "correo", "direccion", "activo",
            ),
            "lista": "SELECT id, ruc, razon_social, nombre_contacto, telefono, correo, direccion, activo FROM proveedores ORDER BY razon_social, id",
        },
        "productos": {
            "tabla": "productos",
            "campos": ("nombre", "categoria", "descripcion", "imagen_url", "activo"),
            "lista": "SELECT id, nombre, categoria, descripcion, imagen_url, activo FROM productos ORDER BY categoria, nombre, id",
        },
        "insumos": {
            "tabla": "insumos",
            "campos": ("nombre", "unidad_medida", "stock_minimo", "activo"),
            "lista": """SELECT i.id, i.nombre, i.unidad_medida, i.stock_minimo,
                              i.activo,
                              COALESCE(SUM(CASE
                                  WHEN m.tipo_movimiento = 'ENTRADA' THEN m.cantidad
                                  WHEN m.tipo_movimiento = 'SALIDA' THEN -m.cantidad
                                  ELSE m.cantidad END), 0) AS stock_actual
                       FROM insumos i LEFT JOIN mercaderia m ON m.insumo_id = i.id
                       GROUP BY i.id, i.nombre, i.unidad_medida, i.stock_minimo, i.activo
                       ORDER BY i.nombre, i.id""",
        },
        "mercaderia": {
            "tabla": "mercaderia",
            "campos": (
                "insumo_id", "proveedor_id", "tipo_movimiento", "cantidad",
                "costo_unitario", "lote", "fecha_vencimiento", "observacion",
            ),
            "lista": """SELECT m.id, i.nombre AS insumo,
                              p.razon_social AS proveedor, m.tipo_movimiento,
                              m.cantidad, m.costo_unitario, m.lote,
                              m.fecha_vencimiento, m.registrado_en
                       FROM mercaderia m
                       JOIN insumos i ON i.id = m.insumo_id
                       LEFT JOIN proveedores p ON p.id = m.proveedor_id
                       ORDER BY m.registrado_en DESC, m.id DESC""",
        },
        "servicios": {
            "tabla": "servicios",
            "campos": (
                "nombre", "descripcion", "horario_inicio", "horario_fin", "activo",
            ),
            "lista": "SELECT id, nombre, descripcion, horario_inicio, horario_fin, activo FROM servicios ORDER BY nombre, id",
        },
    }

    @classmethod
    def entidades(cls):
        return cls._ENTIDADES

    def listar(self, entidad):
        configuracion = self._ENTIDADES[entidad]
        with db.connection() as conn:
            return conn.execute(configuracion["lista"]).fetchall()

    def obtener(self, entidad, registro_id):
        configuracion = self._ENTIDADES[entidad]
        with db.connection() as conn:
            return conn.execute(
                f"SELECT * FROM {configuracion['tabla']} WHERE id = ?",
                (registro_id,),
            ).fetchone()

    def crear(self, entidad, datos):
        configuracion = self._ENTIDADES[entidad]
        campos = configuracion["campos"]
        columnas = ", ".join(campos)
        marcadores = ", ".join("?" for _ in campos)
        valores = tuple(datos[campo] for campo in campos)
        with db.connection() as conn:
            cursor = conn.execute(
                f"INSERT INTO {configuracion['tabla']} ({columnas}) "
                f"VALUES ({marcadores}) RETURNING id",
                valores,
            )
            return cursor.fetchone()["id"]

    def actualizar(self, entidad, registro_id, datos):
        configuracion = self._ENTIDADES[entidad]
        campos = configuracion["campos"]
        asignaciones = ", ".join(f"{campo} = ?" for campo in campos)
        valores = tuple(datos[campo] for campo in campos) + (registro_id,)
        with db.connection() as conn:
            cursor = conn.execute(
                f"UPDATE {configuracion['tabla']} SET {asignaciones} WHERE id = ?",
                valores,
            )
            return cursor.rowcount > 0

    def eliminar(self, entidad, registro_id):
        configuracion = self._ENTIDADES[entidad]
        with db.connection() as conn:
            cursor = conn.execute(
                f"DELETE FROM {configuracion['tabla']} WHERE id = ?",
                (registro_id,),
            )
            return cursor.rowcount > 0

    def opciones(self, entidad, registro_id=None):
        with db.connection() as conn:
            if entidad == "clientes":
                return {
                    "estudiantes": conn.execute(
                        """SELECT u.id, u.nombres, u.correo
                           FROM usuarios u
                           WHERE u.rol = 'Estudiante'
                             AND (NOT EXISTS (
                                 SELECT 1 FROM clientes c WHERE c.usuario_id = u.id
                             ) OR u.id = ?)
                           ORDER BY u.nombres, u.id""",
                        (registro_id or -1,),
                    ).fetchall(),
                }
            if entidad == "mercaderia":
                movimiento_actual = None
                if registro_id:
                    movimiento_actual = conn.execute(
                        "SELECT insumo_id, proveedor_id FROM mercaderia WHERE id = ?",
                        (registro_id,),
                    ).fetchone()
                return {
                    "insumos": conn.execute(
                        """SELECT id, nombre, unidad_medida FROM insumos
                           WHERE activo = TRUE OR id = ? ORDER BY nombre""",
                        (movimiento_actual["insumo_id"] if movimiento_actual else -1,),
                    ).fetchall(),
                    "proveedores": conn.execute(
                        """SELECT id, razon_social FROM proveedores
                           WHERE activo = TRUE OR id = ? ORDER BY razon_social""",
                        (movimiento_actual["proveedor_id"] if movimiento_actual else -1,),
                    ).fetchall(),
                }
        return {}


inventario_repository = InventarioRepository()
