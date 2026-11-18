"""Run every query in queries.sql against central.db and print aligned text results.

Run integrate.py first. Output is also written to query_results.txt for the report.
"""
import re
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent


MONEY = {"price", "total_value", "order_value", "revenue"}


def fmt(value, column):
    """Money columns get thousands separators; IDs, counts and dates are printed as they are."""
    if value is None:
        return ""
    if column in MONEY:
        return f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return str(value)


def run():
    con = sqlite3.connect(HERE / "central.db")
    blocks = re.split(r"^-- name: ", (HERE / "queries.sql").read_text(), flags=re.M)[1:]
    out = []
    for block in blocks:
        title, sql = block.split("\n", 1)
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description]
        rows = [[fmt(v, c) for v, c in zip(r, cols)] for r in cur.fetchall()]
        widths = [max(len(c), *(len(r[i]) for r in rows)) if rows else len(c) for i, c in enumerate(cols)]
        numeric = [all(re.fullmatch(r"[\d,.]+", r[i] or "0") for r in rows) for i in range(len(cols))]
        line = lambda cells: "  ".join(c.rjust(w) if n else c.ljust(w) for c, w, n in zip(cells, widths, numeric))
        out += [title.strip(), line(cols), "  ".join("-" * w for w in widths), *map(line, rows),
                f"({len(rows)} rows)", ""]
    text = "\n".join(out)
    (HERE / "query_results.txt").write_text(text)
    return text


if __name__ == "__main__":
    print(run())
