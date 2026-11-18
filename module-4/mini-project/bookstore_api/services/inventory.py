"""Mock Inventory System: book details and stock levels (data/runtime/inventory.json)."""
from .store import JsonStore


class BookNotFound(Exception):
    pass


class InsufficientStock(Exception):
    def __init__(self, book_id, requested, available):
        super().__init__(f"Only {available} of {book_id} in stock, {requested} requested")
        self.book_id, self.requested, self.available = book_id, requested, available


class InventoryService:
    def __init__(self, path):
        self.store = JsonStore(path)

    def list_books(self):
        return list(self.store.read()["books"].values())

    def get_book(self, book_id):
        book = self.store.read()["books"].get(book_id)
        if book is None:
            raise BookNotFound(book_id)
        return book

    def quote(self, items):
        """Price the requested items and check stock without changing anything."""
        books = self.store.read()["books"]
        lines = []
        for item in items:
            book = books.get(item["book_id"])
            if book is None:
                raise BookNotFound(item["book_id"])
            if book["stock"] < item["quantity"]:
                raise InsufficientStock(book["book_id"], item["quantity"], book["stock"])
            lines.append({"book_id": book["book_id"], "title": book["title"], "unit_price": book["price"],
                          "quantity": item["quantity"], "line_total": book["price"] * item["quantity"]})
        return lines

    def reserve(self, items):
        """Decrease stock for a confirmed order. Re-checks stock under the lock."""
        with self.store.lock:
            data = self.store.read()
            for item in items:
                book = data["books"][item["book_id"]]
                if book["stock"] < item["quantity"]:
                    raise InsufficientStock(book["book_id"], item["quantity"], book["stock"])
            for item in items:
                data["books"][item["book_id"]]["stock"] -= item["quantity"]
            self.store.write(data)
