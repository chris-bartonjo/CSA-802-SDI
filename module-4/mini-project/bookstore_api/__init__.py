"""Bookstore integration API: one REST front door over the Inventory, Sales and Delivery mock systems.

Order flow for POST /api/orders (the integration):
  1. Inventory.quote   -> price the items and check stock       (404 unknown book, 409 not enough stock)
  2. Sales.charge      -> process the payment                   (402 declined)
  3. Inventory.reserve -> decrease stock
  4. Sales.create_order
  5. Delivery.create   -> a pending delivery for the order
"""
import hmac
import os
import shutil
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, request, send_file

from .services.delivery import STATUSES, DeliveryNotFound, DeliveryService, InvalidDeliveryUpdate
from .services.inventory import BookNotFound, InsufficientStock, InventoryService
from .services.sales import PAYMENT_METHODS, OrderNotFound, PaymentDeclined, SalesService

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_API_KEY = "dev-key-123"  # test value for local use; set BOOKSTORE_API_KEY in any real deployment

SWAGGER_PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>Bookstore API docs</title>
<link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui.css"></head>
<body><div id="ui"></div><script src="https://unpkg.com/swagger-ui-dist@5.17.14/swagger-ui-bundle.js"></script>
<script>SwaggerUIBundle({url: "/openapi.yaml", dom_id: "#ui"});</script></body></html>"""


def error(status, code, message):
    return jsonify({"error": {"code": code, "message": message}}), status


def fresh_runtime_data(data_dir: Path):
    """Copy the seed JSON files into a runtime folder so every run starts from the same data."""
    data_dir.mkdir(parents=True, exist_ok=True)
    for seed in (ROOT / "data" / "seed").glob("*.json"):
        shutil.copy(seed, data_dir / seed.name)


def validate_order(body):
    """Return an error message for a bad order body, or None if it is valid."""
    if not isinstance(body, dict):
        return "Request body must be a JSON object"
    customer = body.get("customer")
    if not isinstance(customer, dict) or not customer.get("name") or not customer.get("email"):
        return "customer.name and customer.email are required"
    items = body.get("items")
    if not isinstance(items, list) or not items:
        return "items must be a non-empty list"
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("book_id"), str):
            return "each item needs a book_id"
        qty = item.get("quantity")
        if not isinstance(qty, int) or isinstance(qty, bool) or qty < 1:
            return "each item needs a whole-number quantity of at least 1"
    if len({i["book_id"] for i in items}) != len(items):
        return "each book_id may appear only once"
    payment = body.get("payment")
    if not isinstance(payment, dict) or payment.get("method") not in PAYMENT_METHODS:
        return f"payment.method must be one of {', '.join(sorted(PAYMENT_METHODS))}"
    if not payment.get("token"):
        return "payment.token is required"
    if not body.get("delivery_address"):
        return "delivery_address is required"
    return None


def create_app(data_dir=None, api_key=None):
    app = Flask(__name__)
    data_dir = Path(data_dir or ROOT / "data" / "runtime")
    fresh_runtime_data(data_dir)
    inventory = InventoryService(data_dir / "inventory.json")
    sales = SalesService(data_dir / "sales.json")
    delivery = DeliveryService(data_dir / "deliveries.json")
    key = api_key or os.environ.get("BOOKSTORE_API_KEY", DEFAULT_API_KEY)

    def require_api_key(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            supplied = request.headers.get("X-API-Key", "")
            if not hmac.compare_digest(supplied, key):  # constant-time compare
                return error(401, "unauthorized", "A valid X-API-Key header is required")
            return view(*args, **kwargs)
        return wrapped

    # ---- Public endpoints ----
    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/openapi.yaml")
    def openapi_spec():
        return send_file(ROOT / "openapi.yaml", mimetype="application/yaml")

    @app.get("/docs")
    def docs():
        return SWAGGER_PAGE

    # ---- Inventory ----
    @app.get("/api/books")
    @require_api_key
    def list_books():
        return jsonify({"books": inventory.list_books()})

    @app.get("/api/books/<book_id>")
    @require_api_key
    def get_book(book_id):
        try:
            return jsonify(inventory.get_book(book_id))
        except BookNotFound:
            return error(404, "book_not_found", f"No book with id {book_id}")

    # ---- Sales: place an order and pay (the integration flow) ----
    @app.post("/api/orders")
    @require_api_key
    def place_order():
        body = request.get_json(silent=True)
        problem = validate_order(body)
        if problem:
            return error(400, "invalid_request", problem)
        try:
            lines = inventory.quote(body["items"])
            total = sum(l["line_total"] for l in lines)
            payment = sales.charge(total, body["payment"])
            inventory.reserve(body["items"])
        except BookNotFound as e:
            return error(404, "book_not_found", f"No book with id {e}")
        except InsufficientStock as e:
            return error(409, "insufficient_stock", str(e))
        except PaymentDeclined as e:
            return error(402, "payment_declined", str(e))
        order = sales.create_order(body["customer"], lines, payment)
        new_delivery = delivery.create(order["order_id"], body["delivery_address"])
        return jsonify({"order": order, "payment": payment, "delivery": new_delivery}), 201

    @app.get("/api/orders/<order_id>")
    @require_api_key
    def get_order(order_id):
        try:
            return jsonify(sales.get_order(order_id))
        except OrderNotFound:
            return error(404, "order_not_found", f"No order with id {order_id}")

    # ---- Delivery ----
    @app.get("/api/deliveries/<delivery_id>")
    @require_api_key
    def get_delivery(delivery_id):
        try:
            return jsonify(delivery.get(delivery_id))
        except DeliveryNotFound:
            return error(404, "delivery_not_found", f"No delivery with id {delivery_id}")

    @app.put("/api/deliveries/<delivery_id>")
    @require_api_key
    def update_delivery(delivery_id):
        body = request.get_json(silent=True)
        if not isinstance(body, dict) or not body:
            return error(400, "invalid_request", f"Send at least one of status ({'/'.join(STATUSES)}), courier, tracking_number, address")
        try:
            return jsonify(delivery.update(delivery_id, body))
        except DeliveryNotFound:
            return error(404, "delivery_not_found", f"No delivery with id {delivery_id}")
        except InvalidDeliveryUpdate as e:
            return error(400, "invalid_update", str(e))

    @app.errorhandler(404)
    def not_found(_):
        return error(404, "not_found", "No such endpoint")

    @app.errorhandler(405)
    def method_not_allowed(_):
        return error(405, "method_not_allowed", "Method not allowed on this endpoint")

    return app
