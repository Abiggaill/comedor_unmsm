"""Portable database schema creation and small backward-compatible migrations."""

from .database import db


def initialize_schema():
    if db.is_postgres:
        id_type = "BIGSERIAL PRIMARY KEY"
        bool_type = "BOOLEAN NOT NULL DEFAULT FALSE"
    else:
        id_type = "INTEGER PRIMARY KEY AUTOINCREMENT"
        bool_type = "INTEGER NOT NULL DEFAULT 0"

    with db.connection() as conn:
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS usuarios (
                id {id_type}, dni TEXT UNIQUE NOT NULL, nombres TEXT NOT NULL,
                correo TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                rol TEXT DEFAULT 'Estudiante')"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS menus (
                id {id_type}, fecha TEXT NOT NULL, entrada TEXT NOT NULL,
                segundo TEXT NOT NULL, postre_bebida TEXT NOT NULL,
                cupos_disponibles INTEGER NOT NULL)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS reservas (
                id {id_type}, usuario_id BIGINT NOT NULL, menu_id BIGINT NOT NULL,
                codigo_qr TEXT UNIQUE NOT NULL, estado TEXT DEFAULT 'Reservado',
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
                FOREIGN KEY (menu_id) REFERENCES menus (id))"""
        )
        # Stage 5: purchasing, inventory, catalog, dining-service and client tables.
        # A client is linked to an existing user account to avoid duplicating
        # login details or storing a second password.
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS clientes (
                id {id_type}, usuario_id BIGINT NOT NULL UNIQUE,
                telefono TEXT, activo {bool_type},
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (usuario_id) REFERENCES usuarios (id) ON DELETE CASCADE)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS proveedores (
                id {id_type}, ruc TEXT UNIQUE, razon_social TEXT NOT NULL,
                nombre_contacto TEXT, telefono TEXT, correo TEXT, direccion TEXT,
                activo {bool_type},
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS productos (
                id {id_type}, nombre TEXT NOT NULL, categoria TEXT,
                descripcion TEXT, imagen_url TEXT,
                precio NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (precio >= 0),
                activo {bool_type},
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE (nombre, categoria))"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS insumos (
                id {id_type}, nombre TEXT NOT NULL UNIQUE,
                unidad_medida TEXT NOT NULL,
                stock_minimo NUMERIC(12, 3) NOT NULL DEFAULT 0
                    CHECK (stock_minimo >= 0),
                activo {bool_type},
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )
        # Inventory is recorded as movements so that deliveries and use of
        # ingredients can be traced instead of silently overwriting stock.
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS mercaderia (
                id {id_type}, insumo_id BIGINT NOT NULL,
                proveedor_id BIGINT, tipo_movimiento TEXT NOT NULL
                    CHECK (tipo_movimiento IN ('ENTRADA', 'SALIDA', 'AJUSTE')),
                cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
                costo_unitario NUMERIC(12, 2) CHECK (costo_unitario IS NULL OR costo_unitario >= 0),
                lote TEXT, fecha_vencimiento DATE,
                registrado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                observacion TEXT,
                FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE RESTRICT,
                FOREIGN KEY (proveedor_id) REFERENCES proveedores (id) ON DELETE RESTRICT)"""
        )
        # A dish can use several ingredients, and an ingredient can be used
        # by several dishes; this junction stores the recipe quantities.
        conn.execute(
            """CREATE TABLE IF NOT EXISTS producto_insumos (
                producto_id BIGINT NOT NULL, insumo_id BIGINT NOT NULL,
                cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
                unidad_medida TEXT NOT NULL,
                PRIMARY KEY (producto_id, insumo_id),
                FOREIGN KEY (producto_id) REFERENCES productos (id) ON DELETE CASCADE,
                FOREIGN KEY (insumo_id) REFERENCES insumos (id) ON DELETE RESTRICT)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS servicios (
                id {id_type}, nombre TEXT NOT NULL UNIQUE,
                descripcion TEXT, horario_inicio TEXT, horario_fin TEXT,
                activo {bool_type},
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP)"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS login_intentos (
                correo TEXT PRIMARY KEY, intentos INTEGER NOT NULL DEFAULT 0,
                bloqueado_hasta TEXT, actualizado_en TEXT NOT NULL)"""
        )

        # Stage 6: academic order-to-sale workflow. Documents created by this
        # module are marked as demonstrations and are not tax documents.
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS solicitudes_pedido (
                id {id_type}, cliente_id BIGINT,
                cliente_nombre TEXT NOT NULL,
                solicitante_id BIGINT,
                estado TEXT NOT NULL DEFAULT 'BORRADOR'
                    CHECK (estado IN ('BORRADOR','APROBADA','RECHAZADA','CONVERTIDA','CANCELADA')),
                nota TEXT, es_demo {bool_type},
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON DELETE SET NULL,
                FOREIGN KEY (solicitante_id) REFERENCES usuarios (id) ON DELETE SET NULL)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS solicitudes_pedido_detalle (
                id {id_type}, solicitud_id BIGINT NOT NULL, producto_id BIGINT NOT NULL,
                cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
                precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
                subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
                FOREIGN KEY (solicitud_id) REFERENCES solicitudes_pedido (id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos (id) ON DELETE RESTRICT)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS ventas (
                id {id_type}, solicitud_id BIGINT UNIQUE,
                cliente_id BIGINT, cliente_nombre TEXT NOT NULL,
                vendedor_id BIGINT,
                estado TEXT NOT NULL DEFAULT 'PENDIENTE_PAGO'
                    CHECK (estado IN ('PENDIENTE_PAGO','PAGADA','ANULADA')),
                forma_pago TEXT, total NUMERIC(12, 2) NOT NULL DEFAULT 0 CHECK (total >= 0),
                es_demo {bool_type}, creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (solicitud_id) REFERENCES solicitudes_pedido (id) ON DELETE SET NULL,
                FOREIGN KEY (cliente_id) REFERENCES clientes (id) ON DELETE SET NULL,
                FOREIGN KEY (vendedor_id) REFERENCES usuarios (id) ON DELETE SET NULL)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS ventas_detalle (
                id {id_type}, venta_id BIGINT NOT NULL, producto_id BIGINT NOT NULL,
                cantidad NUMERIC(12, 3) NOT NULL CHECK (cantidad > 0),
                precio_unitario NUMERIC(12, 2) NOT NULL CHECK (precio_unitario >= 0),
                subtotal NUMERIC(12, 2) NOT NULL CHECK (subtotal >= 0),
                FOREIGN KEY (venta_id) REFERENCES ventas (id) ON DELETE CASCADE,
                FOREIGN KEY (producto_id) REFERENCES productos (id) ON DELETE RESTRICT)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS comprobantes (
                id {id_type}, venta_id BIGINT NOT NULL, tipo TEXT NOT NULL
                    CHECK (tipo IN ('FACTURA','BOLETA')),
                numero TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'DEMO'
                    CHECK (estado IN ('DEMO','ANULADO')),
                es_demo {bool_type}, creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (venta_id) REFERENCES ventas (id) ON DELETE CASCADE)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS guias (
                id {id_type}, venta_id BIGINT NOT NULL,
                numero TEXT NOT NULL UNIQUE,
                estado TEXT NOT NULL DEFAULT 'DEMO'
                    CHECK (estado IN ('DEMO','DESPACHADA','ANULADA')),
                es_demo {bool_type}, creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (venta_id) REFERENCES ventas (id) ON DELETE CASCADE)"""
        )
        conn.execute(
            f"""CREATE TABLE IF NOT EXISTS actividad_sistema (
                id {id_type}, actor_user_id BIGINT, actor_email TEXT,
                tipo TEXT NOT NULL, endpoint TEXT, metodo TEXT,
                estado_http INTEGER, descripcion TEXT,
                creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (actor_user_id) REFERENCES usuarios (id) ON DELETE SET NULL)"""
        )

        # Add reporting fields to databases already created by earlier versions.
        reporting_columns = {
            "usuarios": {
                "activo": "BOOLEAN NOT NULL DEFAULT TRUE" if db.is_postgres else "INTEGER NOT NULL DEFAULT 1",
                "area": "TEXT",
                "creado_en": "TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
            },
            "clientes": {"ubicacion": "TEXT", "categoria": "TEXT"},
            "proveedores": {"categoria": "TEXT", "ubicacion": "TEXT", "evaluacion": "NUMERIC(3, 2)", "entregas_esperadas": "INTEGER NOT NULL DEFAULT 0", "entregas_cumplidas": "INTEGER NOT NULL DEFAULT 0"},
            "productos": {"precio": "NUMERIC(12, 2) NOT NULL DEFAULT 0"},
            "servicios": {"precio": "NUMERIC(12, 2) NOT NULL DEFAULT 0"},
        }
        for table_name, columns in reporting_columns.items():
            if db.is_postgres:
                rows = conn.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = current_schema() AND table_name = ?",
                    (table_name,),
                ).fetchall()
                existing_columns = {row["column_name"] for row in rows}
            else:
                existing_columns = {
                    row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})")
                }
            for column_name, column_type in columns.items():
                if column_name not in existing_columns:
                    conn.execute(
                        f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
                    )

        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mercaderia_insumo_fecha "
            "ON mercaderia (insumo_id, registrado_en)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_mercaderia_proveedor "
            "ON mercaderia (proveedor_id)"
        )
        # These indexes make the labelled demonstration records idempotent
        # when Render starts several application workers at deployment time.
        if db.is_postgres:
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_proveedores_razon_social "
                "ON proveedores (razon_social)"
            )
            conn.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS idx_mercaderia_demo_lote "
                "ON mercaderia (lote) WHERE lote = 'DEMO-ETAPA5-001'"
            )

            conn.execute(
                """INSERT INTO proveedores
                       (razon_social, nombre_contacto, telefono, correo, direccion, activo)
                   VALUES (?, ?, ?, ?, ?, TRUE)
                   ON CONFLICT (razon_social) DO NOTHING""",
                (
                    "DEMO - Proveedor de alimentos",
                    "Contacto de prueba",
                    "999000001",
                    "proveedor.demo@example.com",
                    "Dirección ficticia - Lima",
                ),
            )
            conn.execute(
                """INSERT INTO servicios
                       (nombre, descripcion, horario_inicio, horario_fin, activo)
                   VALUES (?, ?, ?, ?, TRUE)
                   ON CONFLICT (nombre) DO NOTHING""",
                (
                    "DEMO - Almuerzo",
                    "Servicio de ejemplo para probar la tabla servicios",
                    "12:00",
                    "15:00",
                ),
            )
            conn.execute(
                """INSERT INTO productos (nombre, categoria, descripcion, activo)
                   VALUES (?, ?, ?, TRUE)
                   ON CONFLICT (nombre, categoria) DO NOTHING""",
                (
                    "DEMO - Arroz con pollo",
                    "Segundo",
                    "Plato ficticio de demostración",
                ),
            )
            conn.execute(
                """INSERT INTO insumos (nombre, unidad_medida, stock_minimo, activo)
                   VALUES (?, ?, ?, TRUE)
                   ON CONFLICT (nombre) DO NOTHING""",
                ("DEMO - Arroz", "kg", 2.000),
            )

            # Clients belong to existing student accounts; do not invent a
            # login or attach the demo profile to an administrator account.
            conn.execute(
                """INSERT INTO clientes (usuario_id, telefono, activo)
                   SELECT u.id, ?, TRUE
                   FROM usuarios AS u
                   WHERE u.rol = 'Estudiante'
                     AND NOT EXISTS (
                         SELECT 1 FROM clientes AS demo
                         WHERE demo.telefono = '999000002'
                     )
                     AND NOT EXISTS (
                         SELECT 1 FROM clientes AS c WHERE c.usuario_id = u.id
                     )
                   ORDER BY u.id
                   LIMIT 1
                   ON CONFLICT (usuario_id) DO NOTHING""",
                ("999000002",),
            )
            conn.execute(
                """INSERT INTO mercaderia
                       (insumo_id, proveedor_id, tipo_movimiento, cantidad,
                        costo_unitario, lote, observacion)
                   SELECT i.id, p.id, 'ENTRADA', ?, ?, ?, ?
                   FROM insumos AS i
                   CROSS JOIN proveedores AS p
                   WHERE i.nombre = ? AND p.razon_social = ?
                   ON CONFLICT DO NOTHING""",
                (
                    10.000,
                    4.50,
                    "DEMO-ETAPA5-001",
                    "Movimiento ficticio de demostración",
                    "DEMO - Arroz",
                    "DEMO - Proveedor de alimentos",
                ),
            )
            conn.execute(
                """INSERT INTO producto_insumos
                       (producto_id, insumo_id, cantidad, unidad_medida)
                   SELECT p.id, i.id, ?, ?
                   FROM productos AS p
                   CROSS JOIN insumos AS i
                   WHERE p.nombre = ? AND p.categoria = ? AND i.nombre = ?
                   ON CONFLICT (producto_id, insumo_id) DO NOTHING""",
                (
                    0.150,
                    "kg",
                    "DEMO - Arroz con pollo",
                    "Segundo",
                    "DEMO - Arroz",
                ),
            )

            # One clearly labelled example row for the academic sales demo.
            conn.execute(
                """INSERT INTO solicitudes_pedido
                       (cliente_nombre, estado, nota, es_demo)
                   SELECT 'Cliente de demostración', 'APROBADA',
                          'Registro académico ficticio; no representa una operación real.', TRUE
                   WHERE NOT EXISTS (
                       SELECT 1 FROM solicitudes_pedido WHERE nota LIKE 'Registro académico ficticio%'
                   )"""
            )
            conn.execute(
                """INSERT INTO solicitudes_pedido_detalle
                       (solicitud_id, producto_id, cantidad, precio_unitario, subtotal)
                   SELECT s.id, p.id, 1, 12.50, 12.50
                   FROM solicitudes_pedido s CROSS JOIN productos p
                   WHERE s.nota LIKE 'Registro académico ficticio%'
                     AND p.nombre = 'DEMO - Arroz con pollo'
                     AND NOT EXISTS (
                         SELECT 1 FROM solicitudes_pedido_detalle d WHERE d.solicitud_id = s.id
                     )"""
            )
            conn.execute(
                """INSERT INTO ventas (solicitud_id, cliente_nombre, estado, forma_pago, total, es_demo)
                   SELECT s.id, s.cliente_nombre, 'PAGADA', 'EFECTIVO (DEMO)', 12.50, TRUE
                   FROM solicitudes_pedido s
                   WHERE s.nota LIKE 'Registro académico ficticio%'
                     AND NOT EXISTS (SELECT 1 FROM ventas v WHERE v.solicitud_id = s.id)"""
            )
            conn.execute(
                """INSERT INTO ventas_detalle (venta_id, producto_id, cantidad, precio_unitario, subtotal)
                   SELECT v.id, p.id, 1, 12.50, 12.50
                   FROM ventas v CROSS JOIN productos p
                   WHERE v.es_demo = TRUE AND p.nombre = 'DEMO - Arroz con pollo'
                     AND NOT EXISTS (SELECT 1 FROM ventas_detalle d WHERE d.venta_id = v.id)"""
            )
            conn.execute(
                """INSERT INTO comprobantes (venta_id, tipo, numero, estado, es_demo)
                   SELECT v.id, 'BOLETA', 'DEMO-BOLETA-001', 'DEMO', TRUE
                   FROM ventas v WHERE v.es_demo = TRUE
                   ON CONFLICT (numero) DO NOTHING"""
            )
            conn.execute(
                """INSERT INTO guias (venta_id, numero, estado, es_demo)
                   SELECT v.id, 'DEMO-GUIA-001', 'DEMO', TRUE
                   FROM ventas v WHERE v.es_demo = TRUE
                   ON CONFLICT (numero) DO NOTHING"""
            )

        if db.is_postgres:
            rows = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'menus'"
            ).fetchall()
            menu_columns = {row["column_name"] for row in rows}
        else:
            menu_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(menus)")
            }

        menu_image_columns = (
            "entrada_imagen_1",
            "entrada_imagen_2",
            "segundo_imagen_1",
            "segundo_imagen_2",
            "postre_bebida_imagen_1",
            "postre_bebida_imagen_2",
        )
        for column in menu_image_columns:
            if column not in menu_columns:
                conn.execute(f"ALTER TABLE menus ADD COLUMN {column} TEXT")

        if db.is_postgres:
            rows = conn.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = current_schema() AND table_name = 'reservas'"
            ).fetchall()
            reservation_columns = {row["column_name"] for row in rows}
        else:
            reservation_columns = {
                row["name"] for row in conn.execute("PRAGMA table_info(reservas)")
            }

        migrations = {
            "entrada_elegida": "TEXT",
            "segundo_elegido": "TEXT",
            "postre_bebida_elegido": "TEXT",
            "finalizada": bool_type,
        }
        for column, sql_type in migrations.items():
            if column not in reservation_columns:
                conn.execute(f"ALTER TABLE reservas ADD COLUMN {column} {sql_type}")

        menu_count = conn.execute("SELECT COUNT(*) AS total FROM menus").fetchone()["total"]
        if menu_count == 0:
            conn.execute(
                """INSERT INTO menus (fecha, entrada, segundo, postre_bebida, cupos_disponibles)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    "Hoy",
                    "Sopa a la Minuta / Causa Rellena",
                    "Seco de Pollo con Frijoles / Arroz Chaufa",
                    "Manzana y Chicha Morada",
                    100,
                ),
            )
