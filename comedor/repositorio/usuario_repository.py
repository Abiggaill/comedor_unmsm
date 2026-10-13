"""Database access for user records and related account data."""

from ..modelo.database import db


class UsuarioRepository:
    """Encapsulate all SQL queries that read or change user records."""

    def __init__(self, database=db):
        self._database = database

    def transaccion(self, immediate=False):
        """Return a database transaction for operations that must be atomic."""
        return self._database.connection(immediate=immediate)

    def buscar_por_correo(self, correo):
        with self._database.connection() as conn:
            return conn.execute(
                "SELECT * FROM usuarios WHERE correo = ?", (correo,)
            ).fetchone()

    def obtener_rol(self, usuario_id):
        with self._database.connection() as conn:
            usuario = conn.execute(
                "SELECT rol FROM usuarios WHERE id = ?", (usuario_id,)
            ).fetchone()
            return usuario["rol"] if usuario else None

    def crear(self, dni, nombres, correo, password_hash, rol):
        with self._database.connection() as conn:
            cursor = conn.execute(
                """INSERT INTO usuarios (dni, nombres, correo, password, rol)
                   VALUES (?, ?, ?, ?, ?) RETURNING id""",
                (dni, nombres, correo, password_hash, rol),
            )
            return cursor.fetchone()["id"]

    def listar_para_gestion(self):
        with self._database.connection() as conn:
            return conn.execute(
                """SELECT u.id, u.dni, u.nombres, u.correo, u.rol,
                          COUNT(r.id) AS total_reservas
                   FROM usuarios u
                   LEFT JOIN reservas r ON r.usuario_id = u.id
                   GROUP BY u.id, u.dni, u.nombres, u.correo, u.rol
                   ORDER BY u.nombres, u.id"""
            ).fetchall()

    def buscar_para_gestion(self, usuario_id):
        with self._database.connection() as conn:
            return conn.execute(
                "SELECT id, dni, nombres, correo, rol FROM usuarios WHERE id = ?",
                (usuario_id,),
            ).fetchone()

    @staticmethod
    def buscar_datos_administracion(conn, usuario_id):
        return conn.execute(
            "SELECT rol, correo FROM usuarios WHERE id = ?", (usuario_id,)
        ).fetchone()

    @staticmethod
    def contar_administradores(conn):
        return conn.execute(
            "SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'Administrador'"
        ).fetchone()["total"]

    @staticmethod
    def actualizar(conn, usuario_id, dni, nombres, correo, rol, password_hash=None):
        if password_hash:
            conn.execute(
                """UPDATE usuarios
                   SET dni = ?, nombres = ?, correo = ?, rol = ?, password = ?
                   WHERE id = ?""",
                (dni, nombres, correo, rol, password_hash, usuario_id),
            )
        else:
            conn.execute(
                """UPDATE usuarios
                   SET dni = ?, nombres = ?, correo = ?, rol = ?
                   WHERE id = ?""",
                (dni, nombres, correo, rol, usuario_id),
            )

    @staticmethod
    def limpiar_intentos(conn, *correos):
        conn.execute(
            "DELETE FROM login_intentos WHERE correo IN (?, ?)",
            correos,
        )

    @staticmethod
    def contar_reservas(conn, usuario_id):
        return conn.execute(
            "SELECT COUNT(*) AS total FROM reservas WHERE usuario_id = ?",
            (usuario_id,),
        ).fetchone()["total"]

    @staticmethod
    def eliminar_por_correo_intentos(conn, correo):
        conn.execute("DELETE FROM login_intentos WHERE correo = ?", (correo,))

    @staticmethod
    def eliminar(conn, usuario_id):
        conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))

    @staticmethod
    def actualizar_rol(conn, usuario_id, rol):
        conn.execute("UPDATE usuarios SET rol = ? WHERE id = ?", (rol, usuario_id))
