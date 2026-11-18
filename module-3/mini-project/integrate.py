"""ETL: integrate the customer database and the product CSV (plus the orders feed) into central.db.

Run from anywhere:  python integrate.py
Extract  -> read sources/customers_source.db (built from customers_source.sql) and the CSV files
Transform-> clean, validate, de-duplicate; every rejected row is logged with a reason
Load     -> insert into the central schema (schema.sql), which enforces keys and CHECK constraints
"""
import csv
import re
import sqlite3
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
SRC = HERE / "sources"
CENTRAL = HERE / "central.db"


def build_customer_source():
    """Create the relational source database from its SQL dump (stands in for the live CRM)."""
    db = SRC / "customers_source.db"
    db.unlink(missing_ok=True)
    con = sqlite3.connect(db)
    con.executescript((SRC / "customers_source.sql").read_text())
    con.commit()
    return con


def clean_text(value):
    value = (value or "").strip()
    return re.sub(r"\s+", " ", value) or None


def normalise_phone(raw):
    """Return +2547XXXXXXXX for a valid Kenyan mobile number, else None."""
    digits = re.sub(r"\D", "", raw or "")
    if digits.startswith("254"):
        digits = "0" + digits[3:]
    return "+254" + digits[1:] if re.fullmatch(r"07\d{8}", digits) else None


def parse_price(raw):
    """Accept '1,250.00', 'KES 6500' or '3500'. Return a float, or None if missing or invalid."""
    cleaned = re.sub(r"(?i)kes|,|\s", "", raw or "")
    try:
        price = float(cleaned)
    except ValueError:
        return None
    return price if price > 0 else None


def valid_iso_date(raw):
    try:
        return date.fromisoformat(raw).isoformat()
    except (TypeError, ValueError):
        return None


def main():
    CENTRAL.unlink(missing_ok=True)            # rebuild from scratch: same output on every run
    central = sqlite3.connect(CENTRAL)
    central.execute("PRAGMA foreign_keys = ON")
    central.executescript((HERE / "schema.sql").read_text())
    reject = lambda source, record, reason: central.execute(
        "INSERT INTO rejected_records VALUES (?, ?, ?)", (source, str(record), reason))
    notes = []  # warnings: data fixed rather than rejected

    # ---- Customers: extract from the relational source ----
    src = build_customer_source()
    rows = src.execute("SELECT cust_id, first_name, last_name, address, city, phone, email "
                       "FROM crm_customers ORDER BY cust_id").fetchall()
    by_email = {}
    for cid, first, last, address, city, phone, email in rows:
        first, last = clean_text(first), clean_text(last)
        if not first or not last:
            reject("customers", cid, "missing first or last name")
            continue
        first, last = first.title(), last.title()
        email = (clean_text(email) or "").lower() or None
        phone_clean = normalise_phone(phone)
        if phone and not phone_clean:
            notes.append(f"customer {cid}: invalid phone '{phone}' stored as NULL")
        if email is None:
            notes.append(f"customer {cid}: no email on record")
        if email and email in by_email:                      # duplicate person -> merge
            survivor = by_email[email]
            central.execute("INSERT INTO customer_id_map VALUES (?, ?)", (cid, survivor))
            notes.append(f"customer {cid}: duplicate of {survivor} (same email), merged")
            continue
        central.execute("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (cid, first, last, clean_text(address), clean_text(city), phone_clean, email))
        central.execute("INSERT INTO customer_id_map VALUES (?, ?)", (cid, cid))
        if email:
            by_email[email] = cid

    # ---- Products: extract from the CSV feed ----
    seen = set()
    with open(SRC / "products.csv", newline="") as f:
        for row in csv.DictReader(f):
            pid = clean_text(row["product_id"])
            if pid in seen:
                reject("products", dict(row), "duplicate product_id (first row kept)")
                continue
            price = parse_price(row["price"])
            if price is None:
                reject("products", dict(row), "missing or invalid price")
                continue
            stock = int(row["stock_qty"])
            if stock < 0:
                notes.append(f"product {pid}: negative stock {stock} set to 0 for review")
                stock = 0
            central.execute("INSERT INTO products VALUES (?, ?, ?, ?)",
                            (pid, clean_text(row["name"]), price, stock))
            seen.add(pid)

    # ---- Orders: link through the ID map and the product list ----
    id_map = dict(central.execute("SELECT source_cust_id, surviving_cust_id FROM customer_id_map"))
    with open(SRC / "orders.csv", newline="") as f:
        for row in csv.DictReader(f):
            cid, pid = int(row["customer_id"]), row["product_id"].strip()
            qty, when = int(row["quantity"]), valid_iso_date(row["order_date"])
            if cid not in id_map:
                reject("orders", dict(row), "unknown customer_id")
            elif pid not in seen:
                reject("orders", dict(row), "unknown or rejected product_id")
            elif qty <= 0:
                reject("orders", dict(row), "quantity must be greater than 0")
            elif when is None:
                reject("orders", dict(row), "invalid order_date")
            else:
                if id_map[cid] != cid:
                    notes.append(f"order {row['order_id']}: customer {cid} remapped to {id_map[cid]}")
                central.execute("INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
                                (int(row["order_id"]), id_map[cid], pid, when, qty))

    central.commit()

    # ---- Integrity checks after loading ----
    assert central.execute("PRAGMA foreign_key_check").fetchall() == [], "foreign key violation"
    assert central.execute("PRAGMA integrity_check").fetchone()[0] == "ok"

    counts = {t: central.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("customers", "products", "orders", "rejected_records")}
    print("Loaded:", counts)
    print("\nRejected records:")
    for source, record, reason in central.execute("SELECT * FROM rejected_records"):
        print(f"  [{source}] {reason}: {record}")
    print("\nFixed and flagged (not rejected):")
    for n in notes:
        print("  " + n)


if __name__ == "__main__":
    main()
