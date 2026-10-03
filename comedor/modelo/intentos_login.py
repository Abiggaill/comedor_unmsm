"""Persistent three-attempt login lockout."""

from datetime import datetime, timedelta, timezone
from math import ceil

from .database import db


class IntentosLogin:
    MAX_INTENTOS = 3
    MINUTOS_BLOQUEO = 15

    @staticmethod
    def _ahora():
        return datetime.now(timezone.utc)

    @staticmethod
    def _minutos_restantes(fecha_bloqueo, ahora):
        bloqueado_hasta = datetime.fromisoformat(fecha_bloqueo)
        segundos = (bloqueado_hasta - ahora).total_seconds()
        return max(1, ceil(segundos / 60)) if segundos > 0 else 0

    @classmethod
    def minutos_bloqueo(cls, correo):
        ahora = cls._ahora()
        with db.connection(immediate=True) as conn:
            # Retira intentos antiguos de direcciones que nunca llegaron a bloquearse.
            caducidad = (ahora - timedelta(days=1)).isoformat()
            conn.execute(
                "DELETE FROM login_intentos WHERE bloqueado_hasta IS NULL AND actualizado_en < ?",
                (caducidad,),
            )
            registro = conn.execute(
                "SELECT bloqueado_hasta FROM login_intentos WHERE correo = ?", (correo,)
            ).fetchone()
            if not registro or not registro["bloqueado_hasta"]:
                return 0

            minutos = cls._minutos_restantes(registro["bloqueado_hasta"], ahora)
            if minutos == 0:
                conn.execute("DELETE FROM login_intentos WHERE correo = ?", (correo,))
            return minutos

    @classmethod
    def registrar_fallo(cls, correo):
        ahora = cls._ahora()
        with db.connection(immediate=True) as conn:
            registro = conn.execute(
                "SELECT intentos, bloqueado_hasta FROM login_intentos WHERE correo = ?",
                (correo,),
            ).fetchone()

            if registro and registro["bloqueado_hasta"]:
                minutos = cls._minutos_restantes(registro["bloqueado_hasta"], ahora)
                if minutos:
                    return cls.MAX_INTENTOS, minutos
                intentos = 0
            else:
                intentos = registro["intentos"] if registro else 0

            intentos += 1
            bloqueado_hasta = None
            if intentos >= cls.MAX_INTENTOS:
                bloqueado_hasta = (ahora + timedelta(minutes=cls.MINUTOS_BLOQUEO)).isoformat()

            conn.execute(
                """
                INSERT INTO login_intentos (correo, intentos, bloqueado_hasta, actualizado_en)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(correo) DO UPDATE SET
                    intentos = excluded.intentos,
                    bloqueado_hasta = excluded.bloqueado_hasta,
                    actualizado_en = excluded.actualizado_en
                """,
                (correo, intentos, bloqueado_hasta, ahora.isoformat()),
            )
            minutos = (
                cls._minutos_restantes(bloqueado_hasta, ahora)
                if bloqueado_hasta
                else 0
            )
            return intentos, minutos

    @staticmethod
    def limpiar(correo):
        with db.connection() as conn:
            conn.execute("DELETE FROM login_intentos WHERE correo = ?", (correo,))
