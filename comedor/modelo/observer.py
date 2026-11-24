"""Small Observer implementation used to audit application activity."""

from ..modelo.database import db


class EventSubject:
    """Publishes activity events to the observers registered by the app."""

    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        if observer not in self._observers:
            self._observers.append(observer)

    def publish(self, event):
        for observer in tuple(self._observers):
            observer.update(event)


class AuditLogObserver:
    """Persists a safe summary of an activity without storing form contents."""

    def update(self, event):
        with db.connection() as conn:
            conn.execute(
                """INSERT INTO actividad_sistema
                   (actor_user_id, actor_email, tipo, endpoint, metodo,
                    estado_http, descripcion)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    event.get("actor_user_id"),
                    event.get("actor_email"),
                    event.get("tipo", "actividad"),
                    event.get("endpoint"),
                    event.get("metodo"),
                    event.get("estado_http"),
                    event.get("descripcion"),
                ),
            )


event_subject = EventSubject()
audit_log_observer = AuditLogObserver()
event_subject.subscribe(audit_log_observer)
