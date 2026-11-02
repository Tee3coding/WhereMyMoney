"""Database layer: everything that touches SQLite lives here."""
import calendar
import os
import sqlite3
from contextlib import contextmanager

import services as sv

# (name, icon key, colour). Icon keys are mapped to real icons in main.py.
DEFAULT_CATEGORIES = [
    ("Food", "restaurant", "#FFD8A8"), ("Transport", "bus", "#B8E0F6"), ("Bills", "receipt", "#D9C8F5"),
    ("Shopping", "shopping", "#C8EBC6"), ("Health", "health", "#FFC9D6"), ("Entertainment", "movie", "#F8D5F0"),
    ("Salary", "salary", "#FFE9A0"), ("Other", "more", "#E2E2E2"),
]
CATEGORIES = [c[0] for c in DEFAULT_CATEGORIES]  # live list: kept in sync with the categories table
WALLETS = ["Bank", "Wallet"]  # fixed choices: where the money is


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
                wallet       TEXT    NOT NULL DEFAULT 'Wallet'
            )
            """
        )
        # Upgrade databases created by earlier versions (no wallet column yet).
        columns = [r["name"] for r in conn.execute("PRAGMA table_info(transactions)")]
        if "wallet" not in columns:
            conn.execute("ALTER TABLE transactions ADD COLUMN wallet TEXT NOT NULL DEFAULT 'Wallet'")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS budgets ("
            "category TEXT PRIMARY KEY, limit_cents INTEGER NOT NULL CHECK (limit_cents > 0))"
        )
        conn.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
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
        # Older versions allowed custom wallets (e.g. "Cash"): fold them into "Wallet".
        for table in ("transactions", "recurring"):
            conn.execute(f"UPDATE {table} SET wallet = 'Wallet' WHERE wallet NOT IN ('Bank', 'Wallet')")
        conn.execute("CREATE TABLE IF NOT EXISTS categories ("
                     "name TEXT PRIMARY KEY, icon TEXT NOT NULL, color TEXT NOT NULL, position INTEGER NOT NULL)")
        if not conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]:
            conn.executemany("INSERT INTO categories (name, icon, color, position) VALUES (?, ?, ?, ?)",
                             [(n, i, c, pos) for pos, (n, i, c) in enumerate(DEFAULT_CATEGORIES)])
        _ensure_used_categories(conn)
        _sync_categories(conn)


# ---------- categories ----------
def _sync_categories(conn) -> None:
    CATEGORIES[:] = [r["name"] for r in conn.execute("SELECT name FROM categories ORDER BY position, rowid")]


def _ensure_used_categories(conn) -> None:
    """Any category name used by a record, recurring entry or budget must exist."""
    used = conn.execute("SELECT category FROM transactions UNION SELECT category FROM recurring "
                        "UNION SELECT category FROM budgets").fetchall()
    known = {r["name"] for r in conn.execute("SELECT name FROM categories")}
    pos = conn.execute("SELECT COALESCE(MAX(position), -1) FROM categories").fetchone()[0]
    for r in used:
        if r["category"] not in known:
            pos += 1
            conn.execute("INSERT INTO categories (name, icon, color, position) VALUES (?, 'more', '#E2E2E2', ?)",
                         (r["category"], pos))


def list_categories():
    with _db() as conn:
        return conn.execute("SELECT name, icon, color FROM categories ORDER BY position, rowid").fetchall()


def _check_name(conn, name: str, old: str = "") -> str:
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name can't be empty")
    if conn.execute("SELECT 1 FROM categories WHERE lower(name) = lower(?) AND name != ?", (name, old)).fetchone():
        raise ValueError("That category already exists")
    return name


def add_category(name: str, icon: str, color: str) -> None:
    with _db() as conn:
        name = _check_name(conn, name)
        pos = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM categories").fetchone()[0]
        conn.execute("INSERT INTO categories (name, icon, color, position) VALUES (?, ?, ?, ?)",
                     (name, icon, color, pos))
        _sync_categories(conn)


def update_category(old: str, name: str, icon: str, color: str) -> None:
    """Renaming also updates every record, recurring entry and budget that used the old name."""
    with _db() as conn:
        name = _check_name(conn, name, old)
        conn.execute("UPDATE categories SET name = ?, icon = ?, color = ? WHERE name = ?", (name, icon, color, old))
        if name != old:
            for table in ("transactions", "recurring", "budgets"):
                conn.execute(f"UPDATE {table} SET category = ? WHERE category = ?", (name, old))
        _sync_categories(conn)


def delete_category(name: str) -> None:
    with _db() as conn:
        used = conn.execute("SELECT (SELECT COUNT(*) FROM transactions WHERE category = ?) + "
                            "(SELECT COUNT(*) FROM recurring WHERE category = ?)", (name, name)).fetchone()[0]
        if used:
            raise ValueError(f"'{name}' is used by {used} record(s). Change or delete those first.")
        if conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] <= 1:
            raise ValueError("You need at least one category")
        conn.execute("DELETE FROM budgets WHERE category = ?", (name,))
        conn.execute("DELETE FROM categories WHERE name = ?", (name,))
        _sync_categories(conn)


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


def _month_filter(month, kind, wallet):
    # `month` can also be a year like "2026": the date prefix is compared either way
    sql, params = "WHERE type = ? AND substr(date, 1, ?) = ?", [kind, len(month), month]
    if wallet:
        sql += " AND wallet = ?"
        params.append(wallet)
    return sql, params


def category_totals(month: str, kind: str = "expense", wallet: str = ""):
    """Total per category for the month, biggest first. kind is 'expense' or 'income'."""
    where, params = _month_filter(month, kind, wallet)
    with _db() as conn:
        return conn.execute(
            f"SELECT category, SUM(amount_cents) AS total FROM transactions {where} "
            "GROUP BY category ORDER BY total DESC", params).fetchall()


def daily_totals(month: str, kind: str = "expense", wallet: str = "") -> dict[int, int]:
    """{day of month: total cents} for the line chart."""
    where, params = _month_filter(month, kind, wallet)
    with _db() as conn:
        rows = conn.execute(
            f"SELECT CAST(substr(date, 9, 2) AS INTEGER) AS day, SUM(amount_cents) AS total "
            f"FROM transactions {where} GROUP BY day", params).fetchall()
    return {r["day"]: r["total"] for r in rows}


def monthly_totals(year: str, kind: str = "expense", wallet: str = "") -> dict[int, int]:
    """{month number 1-12: total cents} for the year view of the line chart."""
    where, params = _month_filter(year, kind, wallet)
    with _db() as conn:
        rows = conn.execute(
            f"SELECT CAST(substr(date, 6, 2) AS INTEGER) AS m, SUM(amount_cents) AS total "
            f"FROM transactions {where} GROUP BY m", params).fetchall()
    return {r["m"]: r["total"] for r in rows}


def top_transactions(month: str, kind: str = "expense", wallet: str = "", limit: int = 10):
    """The biggest records of the month."""
    where, params = _month_filter(month, kind, wallet)
    with _db() as conn:
        return conn.execute(
            f"SELECT * FROM transactions {where} ORDER BY amount_cents DESC, id DESC LIMIT ?",
            params + [limit]).fetchall()


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


# ---------- wallets (fixed: Bank / Wallet) ----------
def wallet_balances() -> dict[str, int]:
    """All-time balance per wallet (income minus expenses), in cents."""
    balances = {w: 0 for w in WALLETS}
    with _db() as conn:
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


# ---------- backup: move your data to a new device ----------
def export_data() -> dict:
    with _db() as conn:
        transactions = [dict(r) for r in conn.execute(
            "SELECT amount_cents, type, category, wallet, date, note FROM transactions ORDER BY date, id")]
        recurring = [dict(r) for r in conn.execute(
            "SELECT amount_cents, type, category, wallet, note, day, start_month, last_applied "
            "FROM recurring ORDER BY id")]
        settings = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM settings")}
    return {"app": "WhereMyMoney", "version": 1, "transactions": transactions,
            "recurring": recurring, "budgets": get_budgets(), "settings": settings,
            "categories": [dict(r) for r in list_categories()]}


def _money_ok(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def validate_backup(data) -> None:
    """Raises ValueError (friendly message) if the backup can't be imported safely."""
    if not isinstance(data, dict) or data.get("app") != "WhereMyMoney":
        raise ValueError("This doesn't look like a WhereMyMoney backup")
    for key in ("transactions", "recurring", "budgets", "settings"):
        if key not in data:
            raise ValueError(f"The backup is missing its '{key}' section")
    try:
        for t in data["transactions"]:
            sv.parse_date(t["date"])
            if not (_money_ok(t["amount_cents"]) and t["type"] in ("income", "expense")
                    and isinstance(t["category"], str) and isinstance(t["note"], str)):
                raise ValueError
        for r in data["recurring"]:
            if not (_money_ok(r["amount_cents"]) and r["type"] in ("income", "expense")
                    and isinstance(r["category"], str) and isinstance(r["note"], str)
                    and isinstance(r["day"], int) and 1 <= r["day"] <= 31
                    and isinstance(r["start_month"], str) and isinstance(r["last_applied"], str)):
                raise ValueError
        if not all(isinstance(k, str) and _money_ok(v) for k, v in data["budgets"].items()):
            raise ValueError
        if not all(isinstance(k, str) and isinstance(v, str) for k, v in data["settings"].items()):
            raise ValueError
        for c in data.get("categories", []):  # older backups have none
            if not (isinstance(c["name"], str) and c["name"].strip() and isinstance(c["icon"], str)
                    and isinstance(c["color"], str)):
                raise ValueError
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("The backup file is damaged or in an unknown format")


def import_data(data: dict) -> None:
    """Replaces ALL current data with the backup. Nothing changes if the backup is invalid."""
    validate_backup(data)
    fix = lambda w: w if w in WALLETS else "Wallet"
    with _db() as conn:
        for table in ("transactions", "recurring", "budgets", "settings"):
            conn.execute(f"DELETE FROM {table}")
        conn.executemany(
            "INSERT INTO transactions (amount_cents, type, category, wallet, date, note) VALUES (?, ?, ?, ?, ?, ?)",
            [(t["amount_cents"], t["type"], t["category"], fix(t.get("wallet")), t["date"], t["note"])
             for t in data["transactions"]])
        conn.executemany(
            "INSERT INTO recurring (amount_cents, type, category, wallet, note, day, start_month, last_applied) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [(r["amount_cents"], r["type"], r["category"], fix(r.get("wallet")), r["note"], r["day"],
              r["start_month"], r["last_applied"]) for r in data["recurring"]])
        conn.executemany("INSERT INTO budgets (category, limit_cents) VALUES (?, ?)", list(data["budgets"].items()))
        conn.executemany("INSERT INTO settings (key, value) VALUES (?, ?)", list(data["settings"].items()))
        if "categories" in data:
            conn.execute("DELETE FROM categories")
            conn.executemany("INSERT OR IGNORE INTO categories (name, icon, color, position) VALUES (?, ?, ?, ?)",
                             [(c["name"].strip(), c["icon"], c["color"], i) for i, c in enumerate(data["categories"])])
        _ensure_used_categories(conn)
        _sync_categories(conn)