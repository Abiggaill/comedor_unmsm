"""User model and persistence operations."""

from werkzeug.security import check_password_hash, generate_password_hash

from .database import db


class Usuario:
    @staticmethod
    def buscar_por_correo(correo):
        with db.connection() as conn:
            return conn.execute(
                "SELECT * FROM usuarios WHERE correo = ?", (correo,)
            ).fetchone()

    @staticmethod
    def crear(dni, nombres, correo, password):
        with db.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (dni, nombres, correo, password) VALUES (?, ?, ?, ?) RETURNING id",
                (dni, nombres, correo, generate_password_hash(password, method="scrypt")),
            )
            return cursor.fetchone()["id"]

    @staticmethod
    def verificar_password(usuario, password):
        return bool(usuario) and check_password_hash(usuario["password"], password)
