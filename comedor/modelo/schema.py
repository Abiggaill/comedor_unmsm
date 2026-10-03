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
        conn.execute(
            """CREATE TABLE IF NOT EXISTS login_intentos (
                correo TEXT PRIMARY KEY, intentos INTEGER NOT NULL DEFAULT 0,
                bloqueado_hasta TEXT, actualizado_en TEXT NOT NULL)"""
        )

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
