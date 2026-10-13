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
                descripcion TEXT, imagen_url TEXT, activo {bool_type},
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
