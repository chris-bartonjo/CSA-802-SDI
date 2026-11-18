"""Mock Delivery System: deliveries for paid orders (data/runtime/deliveries.json)."""
from datetime import datetime, timezone

from .store import JsonStore

STATUSES = ["pending", "dispatched", "in_transit", "delivered", "cancelled"]
UPDATABLE = {"status", "courier", "tracking_number", "address"}


class DeliveryNotFound(Exception):
    pass


class InvalidDeliveryUpdate(Exception):
    pass


class DeliveryService:
    def __init__(self, path):
        self.store = JsonStore(path)

    def create(self, order_id, address):
        with self.store.lock:
            data = self.store.read()
            delivery_id = f"DEL-{data['next_delivery']:04d}"
            data["next_delivery"] += 1
            delivery = {"delivery_id": delivery_id, "order_id": order_id, "address": address,
                        "status": "pending", "courier": None, "tracking_number": None, "updated_at": _now()}
            data["deliveries"][delivery_id] = delivery
            self.store.write(data)
        return delivery

    def get(self, delivery_id):
        delivery = self.store.read()["deliveries"].get(delivery_id)
        if delivery is None:
            raise DeliveryNotFound(delivery_id)
        return delivery

    def update(self, delivery_id, changes):
        unknown = set(changes) - UPDATABLE
        if unknown:
            raise InvalidDeliveryUpdate(f"Fields cannot be updated: {', '.join(sorted(unknown))}")
        if "status" in changes and changes["status"] not in STATUSES:
            raise InvalidDeliveryUpdate(f"status must be one of {', '.join(STATUSES)}")
        with self.store.lock:
            data = self.store.read()
            delivery = data["deliveries"].get(delivery_id)
            if delivery is None:
                raise DeliveryNotFound(delivery_id)
            if delivery["status"] in ("delivered", "cancelled"):
                raise InvalidDeliveryUpdate(f"Delivery is already {delivery['status']}")
            delivery.update(changes)
            delivery["updated_at"] = _now()
            self.store.write(data)
        return delivery


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
