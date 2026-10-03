"""Reservation model and transactional cup/duplicate checks."""

from .database import db
from .menu import Menu


class ErrorReserva(ValueError):
    """Expected reservation validation failure shown to the user."""


class Reserva:
    @staticmethod
    def buscar_por_usuario_y_menu(usuario_id, menu_id):
        with db.connection() as conn:
            return conn.execute(
                """
                SELECT * FROM reservas
                WHERE usuario_id = ? AND menu_id = ?
                ORDER BY id DESC LIMIT 1
                """,
                (usuario_id, menu_id),
            ).fetchone()

    @staticmethod
    def crear(usuario_id, menu_id, codigo_qr, entrada, segundo, postre_bebida):
        menu_actual = Menu.obtener_del_dia()
        if not menu_actual or menu_actual["id"] != menu_id:
            raise ErrorReserva("Ese menú ya no corresponde al día de hoy. Revisa el menú vigente.")

        opciones = Menu.opciones(menu_actual)
        if entrada not in opciones["entrada"] or segundo not in opciones["segundo"]:
            raise ErrorReserva("Selecciona una entrada y un segundo antes de reservar.")
        if postre_bebida and postre_bebida not in opciones["postre_bebida"]:
            raise ErrorReserva("La opción de postre o bebida no es válida.")

        with db.connection(immediate=True) as conn:
            menu = conn.execute("SELECT * FROM menus WHERE id = ?", (menu_id,)).fetchone()
            if not menu:
                raise ErrorReserva("El menú seleccionado ya no está disponible.")
            existing = conn.execute(
                "SELECT id FROM reservas WHERE usuario_id = ? AND menu_id = ?",
                (usuario_id, menu_id),
            ).fetchone()
            if existing:
                raise ErrorReserva("Ya tienes una reserva para este menú.")
            if menu["cupos_disponibles"] <= 0:
                raise ErrorReserva("Lamentablemente ya no quedan cupos disponibles para hoy.")

            cursor = conn.execute(
                """
                INSERT INTO reservas (
                    usuario_id, menu_id, codigo_qr, entrada_elegida,
                    segundo_elegido, postre_bebida_elegido
                ) VALUES (?, ?, ?, ?, ?, ?) RETURNING id
                """,
                (usuario_id, menu_id, codigo_qr, entrada, segundo, postre_bebida or None),
            )
            conn.execute(
                "UPDATE menus SET cupos_disponibles = cupos_disponibles - 1 WHERE id = ?",
                (menu_id,),
            )
            return cursor.fetchone()["id"]

    @staticmethod
    def finalizar(reserva_id, usuario_id):
        with db.connection() as conn:
            cursor = conn.execute(
                "UPDATE reservas SET finalizada = TRUE WHERE id = ? AND usuario_id = ?",
                (reserva_id, usuario_id),
            )
            return cursor.rowcount > 0
