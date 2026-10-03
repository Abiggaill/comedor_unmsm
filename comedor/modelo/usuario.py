"""User model and persistence operations."""

from werkzeug.security import check_password_hash, generate_password_hash

from .database import db


class Usuario:
    ROLES = ("Estudiante", "Ventanilla", "Nutricionista", "Administrador")

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

    @staticmethod
    def rol_actual(usuario_id):
        with db.connection() as conn:
            usuario = conn.execute(
                "SELECT rol FROM usuarios WHERE id = ?", (usuario_id,)
            ).fetchone()
            return usuario["rol"] if usuario else None

    @staticmethod
    def listar_para_gestion():
        with db.connection() as conn:
            return conn.execute(
                "SELECT id, nombres, correo, rol FROM usuarios ORDER BY nombres, id"
            ).fetchall()

    @classmethod
    def cambiar_rol(cls, usuario_id, rol):
        if rol not in cls.ROLES:
            return False, "El rol seleccionado no es válido."

        with db.connection(immediate=True) as conn:
            actual = conn.execute(
                "SELECT rol FROM usuarios WHERE id = ?", (usuario_id,)
            ).fetchone()
            if not actual:
                return False, "No encontramos esa cuenta."
            if actual["rol"] == "Administrador" and rol != "Administrador":
                admins = conn.execute(
                    "SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'Administrador'"
                ).fetchone()["total"]
                if admins <= 1:
                    return False, "Debe quedar al menos una cuenta administradora."
            conn.execute("UPDATE usuarios SET rol = ? WHERE id = ?", (rol, usuario_id))
            return True, "El rol se actualizó correctamente."
