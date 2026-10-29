"""Small helpers: input validation and formatting. No UI, no database."""
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

CURRENCY = "RM"


def parse_amount(text: str) -> int:
    """'12.50' -> 1250 (cents). Raises ValueError with a friendly message."""
    try:
        value = Decimal((text or "").replace(",", "").strip())
    except InvalidOperation:
        raise ValueError("Please enter a valid amount, e.g. 12.50")
    if value <= 0:
        raise ValueError("Amount must be greater than 0")
    return int((value * 100).to_integral_value())


def parse_date(text: str) -> str:
    """Checks the date is YYYY-MM-DD and returns it unchanged."""
    try:
        datetime.strptime((text or "").strip(), "%Y-%m-%d")
    except ValueError:
        raise ValueError("Date must look like 2026-10-29")
    return text.strip()


def money(cents: int) -> str:
    return f"{CURRENCY} {cents / 100:,.2f}"


def today() -> str:
    return date.today().strftime("%Y-%m-%d")


def shift_month(month: str, delta: int) -> str:
    """'2026-10' + 1 -> '2026-11'."""
    year, mon = int(month[:4]), int(month[5:7])
    index = year * 12 + (mon - 1) + delta
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def parse_day(text: str) -> int:
    """Day of month for recurring entries (1 to 31)."""
    try:
        day = int((text or "").strip())
    except ValueError:
        raise ValueError("Day must be a number from 1 to 31")
    if not 1 <= day <= 31:
        raise ValueError("Day must be a number from 1 to 31")
    return day


def dump_backup(data: dict) -> str:
    """Backup dictionary -> JSON text."""
    import json
    return json.dumps(data, indent=2, ensure_ascii=False)


def load_backup(text: str) -> dict:
    """JSON text -> backup dictionary. Raises ValueError with a friendly message."""
    import json
    try:
        return json.loads((text or "").strip())
    except ValueError:
        raise ValueError("That isn't a valid backup (the text is incomplete or damaged)")