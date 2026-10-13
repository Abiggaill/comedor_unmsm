"""Daily menu model and choice parsing."""

import re
from datetime import datetime, timedelta, timezone

from .database import db


class Menu:
    @staticmethod
    def imagen_opcion(menu, grupo, indice):
        if not menu or indice not in (1, 2):
            return ""
        campos = {
            "entrada": "entrada_imagen_",
            "segundo": "segundo_imagen_",
            "postre_bebida": "postre_bebida_imagen_",
        }
        return menu[campos[grupo] + str(indice)] or ""

    @staticmethod
    def fecha_actual():
        peru_time = timezone(timedelta(hours=-5))
        return datetime.now(peru_time).date().isoformat()

    @classmethod
    def obtener_del_dia(cls):
        today = cls.fecha_actual()
        with db.connection(immediate=True) as conn:
            menu = conn.execute(
                "SELECT * FROM menus WHERE fecha = ? ORDER BY id DESC LIMIT 1", (today,)
            ).fetchone()
            if menu:
                return menu

            latest = conn.execute("SELECT * FROM menus ORDER BY id DESC LIMIT 1").fetchone()
            if latest and latest["fecha"] == "Hoy":
                conn.execute(
                    "UPDATE menus SET fecha = ? WHERE id = ?", (today, latest["id"])
                )
                return conn.execute(
                    "SELECT * FROM menus WHERE id = ?", (latest["id"],)
                ).fetchone()

            if latest:
                entrada = latest["entrada"]
                segundo = latest["segundo"]
                postre_bebida = latest["postre_bebida"]
                imagenes = [latest[key] for key in Menu.CAMPOS_IMAGEN]
            else:
                entrada = "Sopa a la Minuta / Causa Rellena"
                segundo = "Seco de Pollo con Frijoles / Arroz Chaufa"
                postre_bebida = "Manzana / Chicha Morada"
                imagenes = [None] * len(Menu.CAMPOS_IMAGEN)

            cursor = conn.execute(
                """
                INSERT INTO menus
                    (fecha, entrada, segundo, postre_bebida, cupos_disponibles,
                     entrada_imagen_1, entrada_imagen_2, segundo_imagen_1,
                     segundo_imagen_2, postre_bebida_imagen_1, postre_bebida_imagen_2)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING id
                """,
                (today, entrada, segundo, postre_bebida, 100, *imagenes),
            )
            return conn.execute(
                "SELECT * FROM menus WHERE id = ?", (cursor.fetchone()["id"],)
            ).fetchone()

    @staticmethod
    def obtener_por_fecha(fecha):
        with db.connection() as conn:
            return conn.execute(
                "SELECT * FROM menus WHERE fecha = ? ORDER BY id DESC LIMIT 1",
                (fecha,),
            ).fetchone()

    @staticmethod
    def datos_edicion(fecha):
        with db.connection() as conn:
            menu = conn.execute(
                "SELECT * FROM menus WHERE fecha = ? ORDER BY id DESC LIMIT 1",
                (fecha,),
            ).fetchone()
            if not menu:
                menu = conn.execute(
                    "SELECT * FROM menus ORDER BY id DESC LIMIT 1"
                ).fetchone()
                if not menu:
                    return None, 0
                reservadas = conn.execute(
                    "SELECT COUNT(*) AS total FROM reservas WHERE menu_id = ?",
                    (menu["id"],),
                ).fetchone()["total"]
                return menu, reservadas
            reservadas = conn.execute(
                "SELECT COUNT(*) AS total FROM reservas WHERE menu_id = ?",
                (menu["id"],),
            ).fetchone()["total"]
            return menu, reservadas

    CAMPOS_IMAGEN = (
        "entrada_imagen_1",
        "entrada_imagen_2",
        "segundo_imagen_1",
        "segundo_imagen_2",
        "postre_bebida_imagen_1",
        "postre_bebida_imagen_2",
    )

    @staticmethod
    def guardar(fecha, entrada, segundo, postre_bebida, cupos_totales, imagenes=None):
        imagenes = imagenes or {}
        imagenes = {campo: imagenes.get(campo) or None for campo in Menu.CAMPOS_IMAGEN}
        fotos_retiradas = 0
        with db.connection(immediate=True) as conn:
            menu = conn.execute(
                "SELECT * FROM menus WHERE fecha = ? ORDER BY id DESC LIMIT 1",
                (fecha,),
            ).fetchone()
            referencia = menu or conn.execute(
                "SELECT * FROM menus ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if referencia:
                nuevos_platos = {
                    "entrada": entrada,
                    "segundo": segundo,
                    "postre_bebida": postre_bebida,
                }
                for grupo, nombre_nuevo in nuevos_platos.items():
                    anteriores = Menu._separar(
                        referencia[grupo], opcional=(grupo == "postre_bebida")
                    )
                    nuevos = Menu._separar(
                        nombre_nuevo, opcional=(grupo == "postre_bebida")
                    )
                    for indice in (1, 2):
                        campo = f"{grupo}_imagen_{indice}"
                        antes = anteriores[indice - 1] if len(anteriores) >= indice else ""
                        despues = nuevos[indice - 1] if len(nuevos) >= indice else ""
                        foto_anterior = referencia[campo]
                        if antes != despues and imagenes[campo] == foto_anterior and foto_anterior:
                            imagenes[campo] = None
                            fotos_retiradas += 1

            if menu:
                reservadas = conn.execute(
                    "SELECT COUNT(*) AS total FROM reservas WHERE menu_id = ?",
                    (menu["id"],),
                ).fetchone()["total"]
                if cupos_totales < reservadas:
                    raise ValueError(
                        f"Ya existen {reservadas} reservas para esa fecha; "
                        "los cupos totales no pueden ser menores."
                    )
                conn.execute(
                    """UPDATE menus SET entrada = ?, segundo = ?, postre_bebida = ?,
                       cupos_disponibles = ?, entrada_imagen_1 = ?, entrada_imagen_2 = ?,
                       segundo_imagen_1 = ?, segundo_imagen_2 = ?,
                       postre_bebida_imagen_1 = ?, postre_bebida_imagen_2 = ?
                       WHERE id = ?""",
                    (
                        entrada,
                        segundo,
                        postre_bebida,
                        cupos_totales - reservadas,
                        *(imagenes[campo] for campo in Menu.CAMPOS_IMAGEN),
                        menu["id"],
                    ),
                )
            else:
                conn.execute(
                    """INSERT INTO menus
                       (fecha, entrada, segundo, postre_bebida, cupos_disponibles,
                        entrada_imagen_1, entrada_imagen_2, segundo_imagen_1,
                        segundo_imagen_2, postre_bebida_imagen_1, postre_bebida_imagen_2)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        fecha,
                        entrada,
                        segundo,
                        postre_bebida,
                        cupos_totales,
                        *(imagenes[campo] for campo in Menu.CAMPOS_IMAGEN),
                    ),
                )
        return fotos_retiradas

    @staticmethod
    def opciones(menu):
        return {
            "entrada": Menu._separar(menu["entrada"]),
            "segundo": Menu._separar(menu["segundo"]),
            "postre_bebida": Menu._separar(menu["postre_bebida"], opcional=True),
        }

    @staticmethod
    def _separar(valor, opcional=False):
        valor = (valor or "").strip()
        if not valor:
            return []
        if "/" in valor:
            return [opcion.strip() for opcion in valor.split("/") if opcion.strip()]
        if opcional and re.search(r"\s+y\s+", valor, flags=re.IGNORECASE):
            return [
                opcion.strip()
                for opcion in re.split(r"\s+y\s+", valor, maxsplit=1, flags=re.IGNORECASE)
                if opcion.strip()
            ]
        return [valor]
