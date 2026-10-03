"""Daily menu model and choice parsing."""

import re
from datetime import datetime, timedelta, timezone

from .database import db


class Menu:
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
            else:
                entrada = "Sopa a la Minuta / Causa Rellena"
                segundo = "Seco de Pollo con Frijoles / Arroz Chaufa"
                postre_bebida = "Manzana / Chicha Morada"

            cursor = conn.execute(
                """
                INSERT INTO menus (fecha, entrada, segundo, postre_bebida, cupos_disponibles)
                VALUES (?, ?, ?, ?, ?) RETURNING id
                """,
                (today, entrada, segundo, postre_bebida, 100),
            )
            return conn.execute(
                "SELECT * FROM menus WHERE id = ?", (cursor.fetchone()["id"],)
            ).fetchone()

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
