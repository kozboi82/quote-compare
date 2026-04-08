"""SQLite DB 관리."""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "quote_compare.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """테이블 생성 (없으면)."""
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name TEXT,
            doc_date DATE,
            parsed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            parse_tool TEXT,
            source_type TEXT DEFAULT 'upload'
        );

        CREATE TABLE IF NOT EXISTS quotes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doc_id INTEGER REFERENCES documents(id),
            supplier TEXT,
            supplier_biz TEXT,
            subtotal INTEGER,
            vat INTEGER,
            total INTEGER
        );

        CREATE TABLE IF NOT EXISTS line_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quote_id INTEGER REFERENCES quotes(id),
            item_type TEXT DEFAULT 'product',
            raw_name TEXT,
            normalized_name TEXT,
            brand TEXT,
            model TEXT,
            spec TEXT,
            unit TEXT,
            quantity INTEGER,
            unit_price INTEGER,
            supply_amount INTEGER
        );
    """)
    conn.commit()
    conn.close()


def insert_document(file_name: str, doc_date: str, parse_tool: str,
                    source_type: str = "upload") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO documents (file_name, doc_date, parse_tool, source_type) "
        "VALUES (?, ?, ?, ?)",
        (file_name, doc_date, parse_tool, source_type),
    )
    doc_id = cur.lastrowid
    conn.commit()
    conn.close()
    return doc_id


def insert_quote(doc_id: int, supplier: str, supplier_biz: str = "",
                 subtotal: int = 0, vat: int = 0, total: int = 0) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO quotes (doc_id, supplier, supplier_biz, subtotal, vat, total) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (doc_id, supplier, supplier_biz, subtotal, vat, total),
    )
    quote_id = cur.lastrowid
    conn.commit()
    conn.close()
    return quote_id


def insert_line_item(quote_id: int, item: dict) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO line_items "
        "(quote_id, item_type, raw_name, normalized_name, brand, model, "
        "spec, unit, quantity, unit_price, supply_amount) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            quote_id,
            item.get("item_type", "product"),
            item.get("raw_name", ""),
            item.get("normalized_name", ""),
            item.get("brand", ""),
            item.get("model", ""),
            item.get("spec", ""),
            item.get("unit", ""),
            item.get("quantity", 0),
            item.get("unit_price", 0),
            item.get("supply_amount", 0),
        ),
    )
    item_id = cur.lastrowid
    conn.commit()
    conn.close()
    return item_id


def search_similar_items(name: str, limit: int = 20) -> list[dict]:
    """품명으로 유사 품목 검색."""
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT li.*, q.supplier, q.total as quote_total,
               d.file_name, d.doc_date
        FROM line_items li
        JOIN quotes q ON li.quote_id = q.id
        JOIN documents d ON q.doc_id = d.id
        WHERE li.normalized_name LIKE ? OR li.raw_name LIKE ?
        ORDER BY d.doc_date DESC
        LIMIT ?
        """,
        (f"%{name}%", f"%{name}%", limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    init_db()
    print(f"DB 초기화 완료: {DB_PATH}")
