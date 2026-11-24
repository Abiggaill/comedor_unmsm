"""Business rules for the non-fiscal sales workflow used in the project demo."""

from ..repositorio.ventas_repository import ventas_repository


class Venta:
    ESTADOS_VENTA = ("PENDIENTE_PAGO", "PAGADA", "ANULADA")
    ESTADOS_SOLICITUD = ("APROBADA", "RECHAZADA", "CANCELADA")
    TIPOS_DOCUMENTO = ("FACTURA", "BOLETA", "GUIA")

    repositorio = ventas_repository

    @classmethod
    def crear_solicitud(cls, cliente_id, cliente_nombre, solicitante_id, nota, items, es_demo=False):
        if not cliente_nombre or not items:
            raise ValueError("Indica el nombre del cliente e incluye al menos un producto.")
        if any(item["cantidad"] <= 0 or item["precio_unitario"] < 0 for item in items):
            raise ValueError("Las cantidades deben ser positivas y los precios no negativos.")
        return cls.repositorio.crear_solicitud(
            cliente_id, cliente_nombre, solicitante_id, nota, items, es_demo
        )
