"""User domain operations, delegating all persistence to UsuarioRepository."""

from werkzeug.security import check_password_hash, generate_password_hash

from ..repositorio.usuario_repository import UsuarioRepository


class Usuario:
    ROLES = ("Estudiante", "Ventanilla", "Nutricionista", "Administrador")
    repositorio = UsuarioRepository()

    @classmethod
    def buscar_por_correo(cls, correo):
        return cls.repositorio.buscar_por_correo(correo)

    @classmethod
    def crear(cls, dni, nombres, correo, password, rol="Estudiante"):
        if rol not in cls.ROLES:
            raise ValueError("El rol seleccionado no es válido.")
        password_hash = generate_password_hash(password, method="scrypt")
        return cls.repositorio.crear(dni, nombres, correo, password_hash, rol)

    @staticmethod
    def verificar_password(usuario, password):
        return bool(usuario) and check_password_hash(usuario["password"], password)

    @classmethod
    def rol_actual(cls, usuario_id):
        return cls.repositorio.obtener_rol(usuario_id)

    @classmethod
    def listar_para_gestion(cls):
        return cls.repositorio.listar_para_gestion()

    @classmethod
    def buscar_para_gestion(cls, usuario_id):
        return cls.repositorio.buscar_para_gestion(usuario_id)

    @classmethod
    def actualizar_desde_admin(
        cls, usuario_id, dni, nombres, correo, rol, password=None
    ):
        if rol not in cls.ROLES:
            return False, "El rol seleccionado no es válido."

        password_hash = (
            generate_password_hash(password, method="scrypt") if password else None
        )
        with cls.repositorio.transaccion(immediate=True) as conn:
            actual = cls.repositorio.buscar_datos_administracion(conn, usuario_id)
            if not actual:
                return False, "No encontramos esa cuenta."
            if actual["rol"] == "Administrador" and rol != "Administrador":
                if cls.repositorio.contar_administradores(conn) <= 1:
                    return False, "Debe quedar al menos una cuenta administradora."

            cls.repositorio.actualizar(
                conn, usuario_id, dni, nombres, correo, rol, password_hash
            )
            if actual["correo"] != correo:
                cls.repositorio.limpiar_intentos(conn, actual["correo"], correo)
            return True, "La cuenta se actualizó correctamente."

    @classmethod
    def eliminar_desde_admin(cls, usuario_id):
        with cls.repositorio.transaccion(immediate=True) as conn:
            actual = cls.repositorio.buscar_datos_administracion(conn, usuario_id)
            if not actual:
                return False, "No encontramos esa cuenta."
            if actual["rol"] == "Administrador":
                if cls.repositorio.contar_administradores(conn) <= 1:
                    return False, "No se puede eliminar al último administrador."

            if cls.repositorio.contar_reservas(conn, usuario_id):
                return False, "Esta cuenta tiene reservas asociadas y se conserva para mantener su historial."

            cls.repositorio.eliminar_por_correo_intentos(conn, actual["correo"])
            cls.repositorio.eliminar(conn, usuario_id)
            return True, "La cuenta se eliminó correctamente."

    @classmethod
    def cambiar_rol(cls, usuario_id, rol):
        if rol not in cls.ROLES:
            return False, "El rol seleccionado no es válido."

        with cls.repositorio.transaccion(immediate=True) as conn:
            actual = cls.repositorio.buscar_datos_administracion(conn, usuario_id)
            if not actual:
                return False, "No encontramos esa cuenta."
            if actual["rol"] == "Administrador" and rol != "Administrador":
                if cls.repositorio.contar_administradores(conn) <= 1:
                    return False, "Debe quedar al menos una cuenta administradora."
            cls.repositorio.actualizar_rol(conn, usuario_id, rol)
            return True, "El rol se actualizó correctamente."
