import sqlite3
import threading
import os

DB_PATH = os.environ.get("DB_PATH", "data/products.db")


class Database:
    def __init__(self):
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        self._init_db()

    def _connect(self):
        """Creeaza o conexiune SQLite cu timeout pentru situatii concurente."""
        return sqlite3.connect(DB_PATH, timeout=10, check_same_thread=False)

    def _init_db(self):
        """Creeaza tabelul daca nu exista si populeaza cu date initiale."""
        with self._lock:
            conn = self._connect()
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS products (
                        id      INTEGER PRIMARY KEY,
                        name    TEXT    NOT NULL,
                        price   REAL    NOT NULL,
                        stock   INTEGER NOT NULL
                    )
                """)
                count = conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
                if count == 0:
                    sample_products = [
                        (1, "Laptop", 3500.00, 10),
                        (2, "Mouse", 120.50, 50),
                        (3, "Tastatura", 250.00, 30),
                        (4, "Monitor", 1800.00, 15),
                        (5, "Casti", 450.75, 25),
                    ]
                    conn.executemany(
                        "INSERT INTO products (id, name, price, stock) VALUES (?, ?, ?, ?)",
                        sample_products,
                    )
                conn.commit()
                print(f"[DB] Baza de date initializata: {DB_PATH}")
            finally:
                conn.close()

    def get_by_id(self, product_id: int):
        """Returneaza un produs dupa id sau None daca nu exista."""
        with self._lock:
            conn = self._connect()
            try:
                row = conn.execute(
                    "SELECT id, name, price, stock FROM products WHERE id = ?",
                    (product_id,),
                ).fetchone()
                return self._row_to_dict(row) if row else None
            finally:
                conn.close()

    def get_range(self, id_min: int, id_max: int):
        """Returneaza lista produselor cu id in intervalul [id_min, id_max]."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, name, price, stock FROM products WHERE id BETWEEN ? AND ?",
                    (id_min, id_max),
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()

    def get_all(self):
        """Returneaza toate produsele."""
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT id, name, price, stock FROM products ORDER BY id"
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()

    def update(self, product_id: int, name: str, price: float, stock: int):
        """
        Actualizeaza campurile unui produs.
        Returneaza produsul actualizat sau None daca nu exista.
        """
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "UPDATE products SET name = ?, price = ?, stock = ? WHERE id = ?",
                    (name, price, stock, product_id),
                )
                conn.commit()
                if cur.rowcount == 0:
                    return None
                row = conn.execute(
                    "SELECT id, name, price, stock FROM products WHERE id = ?",
                    (product_id,),
                ).fetchone()
                return self._row_to_dict(row)
            finally:
                conn.close()

    def delete(self, product_id: int):
        """
        Sterge un produs.
        Returneaza True daca a fost sters, False daca nu exista.
        """
        with self._lock:
            conn = self._connect()
            try:
                cur = conn.execute(
                    "DELETE FROM products WHERE id = ?", (product_id,)
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()
    @staticmethod
    def _row_to_dict(row):
        return {
            "id": row[0],
            "name": row[1],
            "price": row[2],
            "stock": row[3],
        }
