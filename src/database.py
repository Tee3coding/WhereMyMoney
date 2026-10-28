"""Database layer: everything that touches SQLite lives here."""
import calendar
import os
import sqlite3
from contextlib import contextmanager

import services as sv

CATEGORIES = [
    "Food", "Transport", "Bills", "Shopping",
    "Health", "Entertainment", "Salary", "Other",
]
DEFAULT_WALLET = "Cash"


def _db_path() -> str:
    # On Android, Flet gives us a private writable folder via this variable.
    # On your computer we just store the file next to this script.
    folder = os.getenv("FLET_APP_STORAGE_DATA", os.path.dirname(os.path.abspath(__file__)))
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, "wheremymoney.db")


@contextmanager
def _db():
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with _db() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                type         TEXT    NOT NULL CHECK (type IN ('income', 'expense')),
                category     TEXT    NOT NULL,
                date         TEXT    NOT NULL,
                note         TEXT    NOT NULL DEFAULT '',
                wallet       TEXT    NOT NULL DEFAULT 'Cash'
            )
            """
        )
        # Upgrade databases created by earlier versions (no wallet column yet).
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(transactions)")]
        if "wallet" not in columns:
            conn.execute("ALTER TABLE transactions ADD COLUMN wallet TEXT NOT NULL DEFAULT 'Cash'")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS budgets ("
            "category TEXT PRIMARY KEY, limit_cents INTEGER NOT NULL CHECK (limit_cents > 0))"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        conn.execute("CREATE TABLE IF NOT EXISTS wallets (name TEXT PRIMARY KEY)")
        conn.execute("INSERT OR IGNORE INTO wallets (name) VALUES (?)", (DEFAULT_WALLET,))
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recurring (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
                type         TEXT    NOT NULL CHECK (type IN ('income', 'expense')),
                category     TEXT    NOT NULL,
                wallet       TEXT    NOT NULL,
                note         TEXT    NOT NULL DEFAULT '',
                day          INTEGER NOT NULL CHECK (day BETWEEN 1 AND 31),
                start_month  TEXT    NOT NULL,
                last_applied TEXT    NOT NULL DEFAULT ''
            )
            """
        )


# ---------- transactions ----------
def add_transaction(amount_cents, type_, category, wallet, date_, note="") -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO transactions (amount_cents, type, category, wallet, date, note) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (amount_cents, type_, category, wallet, date_, note),
        )


def update_transaction(transaction_id, amount_cents, type_, category, wallet, date_, note="") -> None:
    with _db() as conn:
        conn.execute(
            "UPDATE transactions SET amount_cents=?, type=?, category=?, wallet=?, date=?, note=? WHERE id=?",
            (amount_cents, type_, category, wallet, date_, note, transaction_id),
        )


def delete_transaction(transaction_id: int) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM transactions WHERE id = ?", (transaction_id,))


def list_transactions(month=None, search="", category="", kind="", wallet=""):
    """Newest first. month is 'YYYY-MM' (None = all months). Empty filters are ignored."""
    sql, params = "SELECT * FROM transactions WHERE 1=1", []
    if month:
        sql += " AND substr(date, 1, 7) = ?"
        params.append(month)
    if search:
        sql += " AND (note LIKE ? OR category LIKE ?)"
        params += [f"%{search}%", f"%{search}%"]
    for column, value in (("category", category), ("type", kind), ("wallet", wallet)):
        if value:
            sql += f" AND {column} = ?"
            params.append(value)
    sql += " ORDER BY date DESC, id DESC"
    with _db() as conn:
        return conn.execute(sql, params).fetchall()


def all_transactions():
    with _db() as conn:
        return conn.execute("SELECT * FROM transactions ORDER BY date, id").fetchall()


def month_totals(month: str) -> tuple[int, int]:
    """Returns (income_cents, expense_cents) for the month."""
    with _db() as conn:
        rows = conn.execute(
            "SELECT type, SUM(amount_cents) AS total FROM transactions "
            "WHERE substr(date, 1, 7) = ? GROUP BY type",
            (month,),
        ).fetchall()
    totals = {r["type"]: r["total"] for r in rows}
    return totals.get("income", 0), totals.get("expense", 0)


def expense_by_category(month: str):
    with _db() as conn:
        return conn.execute(
            "SELECT category, SUM(amount_cents) AS total FROM transactions "
            "WHERE type = 'expense' AND substr(date, 1, 7) = ? "
            "GROUP BY category ORDER BY total DESC",
            (month,),
        ).fetchall()


# ---------- budgets ----------
def get_budgets() -> dict[str, int]:
    with _db() as conn:
        rows = conn.execute("SELECT category, limit_cents FROM budgets").fetchall()
    return {r["category"]: r["limit_cents"] for r in rows}


def set_budget(category: str, limit_cents: int) -> None:
    """A limit of 0 removes the budget for that category."""
    with _db() as conn:
        if limit_cents <= 0:
            conn.execute("DELETE FROM budgets WHERE category = ?", (category,))
        else:
            conn.execute(
                "INSERT INTO budgets (category, limit_cents) VALUES (?, ?) "
                "ON CONFLICT(category) DO UPDATE SET limit_cents = excluded.limit_cents",
                (category, limit_cents),
            )


# ---------- settings ----------
def get_setting(key: str, default: str = "") -> str:
    with _db() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with _db() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ---------- wallets ----------
def list_wallets() -> list[str]:
    with _db() as conn:
        return [r["name"] for r in conn.execute("SELECT name FROM wallets ORDER BY rowid")]


def add_wallet(name: str) -> None:
    name = (name or "").strip()
    if not name:
        raise ValueError("Wallet name can't be empty")
    try:
        with _db() as conn:
            conn.execute("INSERT INTO wallets (name) VALUES (?)", (name,))
    except sqlite3.IntegrityError:
        raise ValueError("That wallet already exists")


def delete_wallet(name: str) -> None:
    with _db() as conn:
        used = conn.execute("SELECT COUNT(*) FROM transactions WHERE wallet = ?", (name,)).fetchone()[0]
        used += conn.execute("SELECT COUNT(*) FROM recurring WHERE wallet = ?", (name,)).fetchone()[0]
        if used:
            raise ValueError(f"'{name}' is still used by transactions or recurring entries")
        if conn.execute("SELECT COUNT(*) FROM wallets").fetchone()[0] <= 1:
            raise ValueError("You need at least one wallet")
        conn.execute("DELETE FROM wallets WHERE name = ?", (name,))


def wallet_balances() -> dict[str, int]:
    """All-time balance per wallet (income minus expenses), in cents."""
    with _db() as conn:
        balances = {r["name"]: 0 for r in conn.execute("SELECT name FROM wallets ORDER BY rowid")}
        for r in conn.execute(
            "SELECT wallet, SUM(CASE WHEN type='income' THEN amount_cents ELSE -amount_cents END) AS bal "
            "FROM transactions GROUP BY wallet"
        ):
            balances[r["wallet"]] = r["bal"]
    return balances


# ---------- recurring ----------
def add_recurring(amount_cents, type_, category, wallet, note, day, today) -> None:
    """The first entry is created on the next occurrence of `day` (today counts)."""
    start = today[:7] if day >= int(today[8:10]) else sv.shift_month(today[:7], 1)
    with _db() as conn:
        conn.execute(
            "INSERT INTO recurring (amount_cents, type, category, wallet, note, day, start_month) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (amount_cents, type_, category, wallet, note, day, start),
        )


def list_recurring():
    with _db() as conn:
        return conn.execute("SELECT * FROM recurring ORDER BY day, id").fetchall()


def delete_recurring(rule_id: int) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM recurring WHERE id = ?", (rule_id,))


def apply_recurring(today: str) -> int:
    """Creates every recurring entry that has come due. Safe to call repeatedly."""
    created = 0
    with _db() as conn:
        for r in conn.execute("SELECT * FROM recurring").fetchall():
            month = sv.shift_month(r["last_applied"], 1) if r["last_applied"] else r["start_month"]
            while month <= today[:7]:
                last_day = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
                due = f"{month}-{min(r['day'], last_day):02d}"
                if due > today:
                    break
                conn.execute(
                    "INSERT INTO transactions (amount_cents, type, category, wallet, date, note) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (r["amount_cents"], r["type"], r["category"], r["wallet"], due, r["note"]),
                )
                conn.execute("UPDATE recurring SET last_applied = ? WHERE id = ?", (month, r["id"]))
                created += 1
                month = sv.shift_month(month, 1)
    return created