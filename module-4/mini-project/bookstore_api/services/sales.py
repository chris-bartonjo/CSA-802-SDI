"""Mock Sales System: customer orders and payments (data/runtime/sales.json).

Payments are simulated like a gateway's test mode: any token is approved except "tok_declined".
"""
from datetime import datetime, timezone

from .store import JsonStore

PAYMENT_METHODS = {"card", "mpesa"}


class PaymentDeclined(Exception):
    pass


class OrderNotFound(Exception):
    pass


class SalesService:
    def __init__(self, path):
        self.store = JsonStore(path)

    def charge(self, amount, payment):
        """Simulate a payment-gateway charge. Returns a payment record or raises PaymentDeclined."""
        if payment.get("token") == "tok_declined":
            raise PaymentDeclined("The payment was declined by the provider")
        with self.store.lock:
            data = self.store.read()
            payment_id = f"PAY-{len(data['payments']) + 1:04d}"
            record = {"payment_id": payment_id, "method": payment["method"], "amount": amount,
                      "status": "captured", "processed_at": _now()}
            data["payments"][payment_id] = record
            self.store.write(data)
        return record

    def create_order(self, customer, lines, payment_record):
        with self.store.lock:
            data = self.store.read()
            order_id = f"ORD-{data['next_order']}"
            data["next_order"] += 1
            order = {"order_id": order_id, "customer": customer, "items": lines,
                     "total": sum(l["line_total"] for l in lines),
                     "payment_id": payment_record["payment_id"], "status": "paid", "created_at": _now()}
            data["orders"][order_id] = order
            self.store.write(data)
        return order

    def get_order(self, order_id):
        order = self.store.read()["orders"].get(order_id)
        if order is None:
            raise OrderNotFound(order_id)
        return order


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
