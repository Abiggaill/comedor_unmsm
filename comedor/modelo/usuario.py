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
    def crear(dni, nombres, correo, password, rol="Estudiante"):
        if rol not in Usuario.ROLES:
            raise ValueError("El rol seleccionado no es válido.")
        with db.connection() as conn:
            cursor = conn.execute(
                "INSERT INTO usuarios (dni, nombres, correo, password, rol) VALUES (?, ?, ?, ?, ?) RETURNING id",
                (
                    dni,
                    nombres,
                    correo,
                    generate_password_hash(password, method="scrypt"),
                    rol,
                ),
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
                """SELECT u.id, u.dni, u.nombres, u.correo, u.rol,
                          COUNT(r.id) AS total_reservas
                   FROM usuarios u
                   LEFT JOIN reservas r ON r.usuario_id = u.id
                   GROUP BY u.id, u.dni, u.nombres, u.correo, u.rol
                   ORDER BY u.nombres, u.id"""
            ).fetchall()

    @staticmethod
    def buscar_para_gestion(usuario_id):
        with db.connection() as conn:
            return conn.execute(
                "SELECT id, dni, nombres, correo, rol FROM usuarios WHERE id = ?",
                (usuario_id,),
            ).fetchone()

    @classmethod
    def actualizar_desde_admin(cls, usuario_id, dni, nombres, correo, rol, password=None):
        if rol not in cls.ROLES:
            return False, "El rol seleccionado no es válido."

        with db.connection(immediate=True) as conn:
            actual = conn.execute(
                "SELECT rol, correo FROM usuarios WHERE id = ?", (usuario_id,)
            ).fetchone()
            if not actual:
                return False, "No encontramos esa cuenta."
            if actual["rol"] == "Administrador" and rol != "Administrador":
                admins = conn.execute(
                    "SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'Administrador'"
                ).fetchone()["total"]
                if admins <= 1:
                    return False, "Debe quedar al menos una cuenta administradora."

            if password:
                conn.execute(
                    """UPDATE usuarios
                       SET dni = ?, nombres = ?, correo = ?, rol = ?, password = ?
                       WHERE id = ?""",
                    (
                        dni,
                        nombres,
                        correo,
                        rol,
                        generate_password_hash(password, method="scrypt"),
                        usuario_id,
                    ),
                )
            else:
                conn.execute(
                    """UPDATE usuarios
                       SET dni = ?, nombres = ?, correo = ?, rol = ?
                       WHERE id = ?""",
                    (dni, nombres, correo, rol, usuario_id),
                )
            if actual["correo"] != correo:
                conn.execute(
                    "DELETE FROM login_intentos WHERE correo IN (?, ?)",
                    (actual["correo"], correo),
                )
            return True, "La cuenta se actualizó correctamente."

    @classmethod
    def eliminar_desde_admin(cls, usuario_id):
        with db.connection(immediate=True) as conn:
            actual = conn.execute(
                "SELECT rol, correo FROM usuarios WHERE id = ?", (usuario_id,)
            ).fetchone()
            if not actual:
                return False, "No encontramos esa cuenta."
            if actual["rol"] == "Administrador":
                admins = conn.execute(
                    "SELECT COUNT(*) AS total FROM usuarios WHERE rol = 'Administrador'"
                ).fetchone()["total"]
                if admins <= 1:
                    return False, "No se puede eliminar al último administrador."

            reservas = conn.execute(
                "SELECT COUNT(*) AS total FROM reservas WHERE usuario_id = ?",
                (usuario_id,),
            ).fetchone()["total"]
            if reservas:
                return False, "Esta cuenta tiene reservas asociadas y se conserva para mantener su historial."

            conn.execute(
                "DELETE FROM login_intentos WHERE correo = ?", (actual["correo"],)
            )
            conn.execute("DELETE FROM usuarios WHERE id = ?", (usuario_id,))
            return True, "La cuenta se eliminó correctamente."

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
