"""WhereMyMoney: the Flet user interface. Run with: flet run src/main.py"""
import asyncio
import calendar
import math
import re
import socket
import time
from datetime import datetime

import flet as ft
import flet_charts as fch

import database as db
import services as sv

YELLOW = "#FFD93B"
BG_DARK, BG_LIGHT = "#000000", "#F2F2F7"
# Icons a category can use (the database stores the key on the left).
I = ft.Icons
ICON_CHOICES = {
    "restaurant": I.RESTAURANT, "bus": I.DIRECTIONS_BUS, "receipt": I.RECEIPT_LONG, "shopping": I.SHOPPING_BAG,
    "health": I.FAVORITE, "movie": I.MOVIE, "salary": I.PAYMENTS, "more": I.MORE_HORIZ, "coffee": I.LOCAL_CAFE,
    "car": I.DIRECTIONS_CAR, "home": I.HOME, "phone": I.PHONE_ANDROID, "school": I.SCHOOL, "pets": I.PETS,
    "flight": I.FLIGHT, "gift": I.CARD_GIFTCARD, "fitness": I.FITNESS_CENTER, "game": I.SPORTS_ESPORTS,
    "savings": I.SAVINGS, "work": I.WORK, "child": I.CHILD_CARE, "beauty": I.FACE, "fuel": I.LOCAL_GAS_STATION,
    "groceries": I.LOCAL_GROCERY_STORE,
}
COLOR_CHOICES = ["#FFD8A8", "#B8E0F6", "#D9C8F5", "#C8EBC6", "#FFC9D6", "#F8D5F0", "#FFE9A0", "#E2E2E2",
                 "#BFE9E4", "#FFC4B0"]
CATEGORY_ICONS = {"All": I.APPS}      # filled by load_categories()
CATEGORY_COLORS = {"All": "#E2E2E2"}


def load_categories():
    """Copies the categories table into the icon/colour lookups used all over the UI."""
    CATEGORY_ICONS.clear()
    CATEGORY_COLORS.clear()
    CATEGORY_ICONS["All"], CATEGORY_COLORS["All"] = I.APPS, "#E2E2E2"
    for r in db.list_categories():
        CATEGORY_ICONS[r["name"]] = ICON_CHOICES.get(r["icon"], I.MORE_HORIZ)
        CATEGORY_COLORS[r["name"]] = r["color"]


WALLET_ICONS = {"Bank": ft.Icons.ACCOUNT_BALANCE, "Wallet": ft.Icons.ACCOUNT_BALANCE_WALLET, "All": ft.Icons.APPS}
PIE_COLORS = [ft.Colors.BLUE, ft.Colors.ORANGE, ft.Colors.GREEN, ft.Colors.PURPLE,
              ft.Colors.TEAL, ft.Colors.PINK, ft.Colors.AMBER, ft.Colors.CYAN]
ALL = "All"

THEME_MODES = {"system": ft.ThemeMode.SYSTEM, "light": ft.ThemeMode.LIGHT, "dark": ft.ThemeMode.DARK}


def saved_theme():
    """'system' (follow the phone) unless the user picked light or dark before."""
    value = db.get_setting("theme", "")
    if value in THEME_MODES:
        return value
    old = db.get_setting("dark_mode", "")  # setting used by earlier versions
    return "system" if old == "" else ("dark" if old == "1" else "light")


def badge(category, size=44, selected=False):
    return ft.Container(
        ft.Icon(CATEGORY_ICONS.get(category, ft.Icons.MORE_HORIZ), color="#5D4037", size=size * 0.5),
        width=size, height=size, border_radius=size / 2, alignment=ft.Alignment.CENTER,
        bgcolor=CATEGORY_COLORS.get(category, "#E2E2E2"),
        border=ft.Border.all(3, ft.Colors.PRIMARY) if selected else None,
    )


# ---------- small design helpers ----------
def heading(text):
    return ft.Text(text, size=24, weight=ft.FontWeight.BOLD)


def label(text):
    return ft.Text(text, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)


def card(*controls):
    return ft.Container(ft.Column(list(controls), spacing=12), bgcolor=ft.Colors.SURFACE,
                        border_radius=20, padding=16)


def field(**kwargs):
    if "prefix_text" in kwargs:  # Flet 1.0 takes a control here
        kwargs["prefix"] = ft.Text(kwargs.pop("prefix_text"))
    return ft.TextField(filled=True, border_radius=12, border_width=0, **kwargs)


def icon_options(names, icons):
    return [ft.dropdown.Option(key=n, text=n, leading_icon=icons.get(n, ft.Icons.MORE_HORIZ)) for n in names]


def dropdown(label_text, value, options, **kwargs):
    return ft.Dropdown(label=label_text, value=value, options=options, filled=True,
                       border_radius=12, border_width=0, **kwargs)


def kind_options():
    return [ft.dropdown.Option(key="expense", text="Expense", leading_icon=ft.Icons.ARROW_DOWNWARD),
            ft.dropdown.Option(key="income", text="Income", leading_icon=ft.Icons.ARROW_UPWARD)]


def main(page: ft.Page):
    db.init_db()
    load_categories()
    sv.CURRENCY = db.get_setting("currency", "RM")
    db.apply_recurring(sv.today())
    state = {"month": sv.today()[:7], "tab": 0}

    def scheme(dark):
        return ft.ColorScheme(
            primary=YELLOW, on_primary="#000000",
            primary_container="#3B3410" if dark else "#FFF1B8", on_primary_container="#FFE680" if dark else "#3A3000",
            surface="#1C1C1E" if dark else "#FFFFFF", on_surface="#FFFFFF" if dark else "#111111",
            outline="#8E8E93", secondary_container="#2A2A2D" if dark else "#E8E8ED",
            on_secondary_container="#FFFFFF" if dark else "#111111")

    def is_dark():
        mode = page.theme_mode
        return mode == ft.ThemeMode.DARK or (mode == ft.ThemeMode.SYSTEM
                                             and page.platform_brightness == ft.Brightness.DARK)

    def apply_theme():
        page.theme = ft.Theme(color_scheme=scheme(False))
        page.dark_theme = ft.Theme(color_scheme=scheme(True))
        page.bgcolor = BG_DARK if is_dark() else BG_LIGHT

    page.title = db.get_setting("app_name", "WhereMyMoney")
    page.padding = 0
    page.theme_mode = THEME_MODES[saved_theme()]
    apply_theme()

    def on_phone_theme_change(e):  # phone switched between light and dark while the app is open
        apply_theme()
        page.update()

    page.on_platform_brightness_change = on_phone_theme_change
    app_title = ft.Text(page.title, size=20, weight=ft.FontWeight.BOLD)

    def toast(message):
        page.show_dialog(ft.SnackBar(ft.Text(message)))

    def confirm(title, text, on_yes, yes_label="Delete"):
        def yes(e):
            buzz("heavy")
            page.pop_dialog()
            on_yes()

        dialog = ft.AlertDialog(
            title=ft.Text(title), content=ft.Text(text),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                     ft.TextButton(yes_label, on_click=yes)],
        )
        page.show_dialog(dialog)

    def prefix():
        return f"{sv.CURRENCY} "

    # ================= TOUCH FEEDBACK (optional vibration + press animation) =================
    haptic = ft.HapticFeedback()
    page.services.append(haptic)
    state["haptics"] = db.get_setting("device_haptics", "1") == "1"

    def buzz(kind="light"):
        """A short vibration: light (taps), select (choices), medium (saved), heavy (errors/deletes)."""
        if not state["haptics"] or page.platform not in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):
            return
        if page.platform == ft.PagePlatform.ANDROID and time.time() > state.get("native_retry", 0):
            try:  # preferred: the native motor buzz (tools/android/HapticReceiver.java), not tied to touch-feedback settings
                if "buzz_socket" not in state:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    sock.setblocking(False)
                    sock.connect(("127.0.0.1", 47831))
                    state["buzz_socket"] = sock
                state["buzz_socket"].send(kind[0].encode())
                return
            except OSError:  # nothing is listening (old APK / patch step skipped): use Flutter's haptics for a while
                state.pop("buzz_socket", None)
                state["native_retry"] = time.time() + 30
        action = {"light": haptic.light_impact, "select": haptic.selection_click,
                  "medium": haptic.medium_impact, "heavy": haptic.heavy_impact}[kind]
        try:
            page.run_task(action)
        except Exception:  # a phone without a vibration motor must never break typing
            pass

    async def release(box):
        await asyncio.sleep(0.12)
        try:
            box.scale = 1
            box.update()
        except Exception:  # the control was replaced or closed in the meantime
            pass

    def feel(box, kind="light"):
        """Press feedback for a tappable Container: ripple, a quick squash-and-spring animation, vibration."""
        box.ink = True
        box.scale = 1
        box.animate_scale = ft.Animation(100, ft.AnimationCurve.EASE_OUT)

        def down(e):
            buzz(kind)
            box.scale = 0.92
            box.update()
            page.run_task(release, box)

        box.on_tap_down = down
        return box

    # ================= MONTH HELPERS =================
    month_labels = []

    def change_month(delta):
        step = 12 if state["tab"] == 1 and fl["period"] == "year" else 1  # Reports in Year view moves by a year
        state["month"] = sv.shift_month(state["month"], delta * step)
        refresh()

    def month_bar():
        month_label = ft.Text(size=18, weight=ft.FontWeight.BOLD)
        month_labels.append(month_label)
        row = ft.Row(
            [ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda e: change_month(-1)), month_label,
             ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda e: change_month(1))],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        return row, month_label

    # ================= ENTRY SHEET (add + edit, category grid + keypad) =================
    KEYS = [["7", "8", "9", "date"], ["4", "5", "6", "+"], ["1", "2", "3", "-"], [".", "0", "⌫", "="]]

    def open_entry(t=None, kind="expense", date=None):
        form = {
            "kind": t["type"] if t else kind, "category": t["category"] if t else db.CATEGORIES[0],
            "wallet": t["wallet"] if t else "Wallet", "date": t["date"] if t else (date or sv.today()),
            "text": f"{t['amount_cents'] / 100:.2f}".rstrip("0").rstrip(".") if t else "",
        }
        display = field(  # the amount is entered with the keypad below only (read-only, no phone keyboard)
            prefix_text=prefix(), hint_text="0", text_size=34, text_align=ft.TextAlign.RIGHT,
            text_style=ft.TextStyle(weight=ft.FontWeight.BOLD), read_only=True)
        date_label = ft.Text(size=13)
        memo = field(label="Memo", value=t["note"] if t else "", prefix_icon=ft.Icons.EDIT_NOTE)
        error = ft.Text(color=ft.Colors.RED)
        grid = ft.Column(spacing=14)  # rows of 4 equal columns, so names never wrap on narrow phones

        def choose(c):
            form["category"] = c
            show()

        def show():
            display.value = form["text"]
            date_label.value = "Today" if form["date"] == sv.today() else form["date"][5:]
            cells = [
                feel(ft.Container(
                    ft.Column([badge(c, 50, c == form["category"]),
                               ft.Text(c, size=11, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                                       text_align=ft.TextAlign.CENTER)], spacing=2,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    expand=True, border_radius=12, on_click=lambda e, c=c: choose(c)), "select")
                for c in db.CATEGORIES
            ]
            grid.controls = [
                ft.Row(cells[i:i + 4] + [ft.Container(expand=True) for _ in range(4 - len(cells[i:i + 4]))],
                       spacing=0, vertical_alignment=ft.CrossAxisAlignment.START)
                for i in range(0, len(cells), 4)]
            page.update()

        def press(key):
            text = form["text"]
            if key == "⌫":
                text = text[:-1]
            elif key == "=":
                try:
                    text = f"{sv.calc(text.rstrip('+-.')):.2f}".rstrip("0").rstrip(".")
                except ValueError:
                    pass
            elif key in ("+", "-"):
                text = text + key if text and text[-1] not in "+-" else text
            elif key == ".":
                last = re.split(r"[+-]", text)[-1]
                text = text if "." in last else text + ("." if last else "0.")
            else:
                text += key
            form["text"] = text
            show()

        def pick_date():
            def chosen(ev):
                form["date"] = ev.control.value.strftime("%Y-%m-%d")
                show()

            page.show_dialog(ft.DatePicker(first_date=datetime(2020, 1, 1), last_date=datetime(2100, 12, 31),
                                    value=datetime.strptime(form["date"], "%Y-%m-%d"), on_change=chosen))

        def key_button(key):
            content = (ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH, size=16), date_label], spacing=4,
                              alignment=ft.MainAxisAlignment.CENTER)
                       if key == "date" else ft.Text("−" if key == "-" else key, size=20))
            return feel(ft.Container(
                content, height=50, expand=True, alignment=ft.Alignment.CENTER, border_radius=14,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if key in ("+", "-", "=", "date") else ft.Colors.SURFACE,
                on_click=(lambda e: pick_date()) if key == "date" else (lambda e, k=key: press(k))))

        def save(e):
            try:
                cents = sv.parse_amount(form["text"].rstrip("+-."))
            except ValueError as problem:
                buzz("heavy")
                error.value = str(problem)
                page.update()
                return
            args = (cents, form["kind"], form["category"], form["wallet"], form["date"], (memo.value or "").strip())
            if t:
                db.update_transaction(t["id"], *args)
            else:
                db.add_transaction(*args)
            buzz("medium")
            page.pop_dialog()
            refresh()
            toast("Saved")

        def remove(e):
            confirm("Delete record?", "This can't be undone.", lambda: (
                db.delete_transaction(t["id"]), page.pop_dialog(), refresh(), toast("Deleted")))

        def segmented(key, options):
            return ft.SegmentedButton(
                selected=[form[key]], allow_multiple_selection=False, show_selected_icon=False,
                on_change=lambda e: form.update({key: next(iter(e.control.selected))}),
                segments=[ft.Segment(value=v, label=ft.Text(lbl), icon=ft.Icon(ic)) for v, lbl, ic in options])

        buttons = [ft.FilledButton("Save", icon=ft.Icons.CHECK, height=50, expand=True, on_click=save)]
        if t:
            buttons.insert(0, ft.OutlinedButton("Delete", icon=ft.Icons.DELETE_OUTLINE, height=50, on_click=remove))
        sheet = ft.BottomSheet(
            ft.Container(
                ft.Column([
                    ft.Row([segmented("kind", [("expense", "Expense", ft.Icons.ARROW_DOWNWARD),
                                               ("income", "Income", ft.Icons.ARROW_UPWARD)])],
                           alignment=ft.MainAxisAlignment.CENTER),
                    grid,
                    ft.Row([segmented("wallet", [(w, w, WALLET_ICONS[w]) for w in db.WALLETS])],
                           alignment=ft.MainAxisAlignment.CENTER),
                    display, memo, error,
                    ft.Column([ft.Row([key_button(k) for k in row], spacing=6) for row in KEYS], spacing=6),
                    ft.Row(buttons, spacing=8),
                ], scroll=ft.ScrollMode.AUTO, spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                padding=16, height=(page.height or 800) * 0.92),
            scrollable=True, show_drag_handle=True, use_safe_area=True)
        show()
        page.show_dialog(sheet)

    # ================= SETTINGS (text boxes save by themselves) =================
    def set_theme(e):
        choice = next(iter(e.control.selected))
        db.set_setting("theme", choice)
        page.theme_mode = THEME_MODES[choice]
        apply_theme()
        page.update()

    def save_app_name(e):
        name = (app_name_field.value or "").strip() or "WhereMyMoney"
        app_name_field.value = name
        if name == db.get_setting("app_name", "WhereMyMoney"):
            page.update()
            return  # nothing changed (Enter and tapping away both call this)
        db.set_setting("app_name", name)
        app_title.value = name
        page.title = name
        sync_quick_config()
        page.update()
        toast("Name saved")

    def save_currency(e):
        symbol = (currency_field.value or "").strip() or "RM"
        currency_field.value = symbol
        if symbol == sv.CURRENCY:
            page.update()
            return
        sv.CURRENCY = symbol
        db.set_setting("currency", symbol)
        refresh()
        sync_quick_config()
        toast("Currency saved")

    app_name_field = field(label="Name", value=page.title,
                           on_submit=save_app_name, on_blur=save_app_name)
    currency_field = field(label="Currency symbol (e.g. RM, $, S$)", value=sv.CURRENCY,
                           on_submit=save_currency, on_blur=save_currency)

    # ---- recurring ----
    recurring_col = ft.Column(spacing=0)

    def refresh_recurring():
        recurring_col.controls = [
            ft.ListTile(
                dense=True, leading=ft.Icon(ft.Icons.EVENT_REPEAT),
                title=ft.Text(f"{'+' if r['type'] == 'income' else '-'}{sv.money(r['amount_cents'])}  {r['category']}"),
                subtitle=ft.Text(f"Day {r['day']} each month, {r['wallet']}  {r['note']}".strip()),
                trailing=ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, i=r["id"]: remove_recurring(i)),
            )
            for r in db.list_recurring()
        ] or [ft.Text("No recurring entries yet.", size=12)]

    def remove_recurring(rule_id):
        confirm("Delete recurring entry?", "Entries already created stay in your history.", lambda: (
            db.delete_recurring(rule_id), refresh_recurring(), page.update()))

    def open_recurring(e):
        amt = field(label="Amount", prefix_text=prefix(), keyboard_type=ft.KeyboardType.NUMBER)
        kind_dd = dropdown("Type", "expense", kind_options())
        cat = dropdown("Category", db.CATEGORIES[0], icon_options(db.CATEGORIES, CATEGORY_ICONS))
        wal = dropdown("Account", db.WALLETS[-1], icon_options(db.WALLETS, WALLET_ICONS))
        day = field(label="Day of month (1-31)", value=sv.today()[8:10].lstrip("0") or "1",
                    keyboard_type=ft.KeyboardType.NUMBER)
        nt = field(label="Note (e.g. Rent, Netflix)")
        err = ft.Text(color=ft.Colors.RED)

        def save_rule(ev):
            try:
                cents = sv.parse_amount(amt.value)
                day_ = sv.parse_day(day.value)
            except ValueError as problem:
                err.value = str(problem)
                page.update()
                return
            db.add_recurring(cents, kind_dd.value, cat.value, wal.value, (nt.value or "").strip(),
                             day_, sv.today())
            db.apply_recurring(sv.today())
            page.pop_dialog()
            refresh_recurring()
            refresh()
            toast("Recurring entry added")

        dialog = ft.AlertDialog(
            title=ft.Text("New recurring entry"),
            content=ft.Column([amt, kind_dd, cat, wal, day, nt, err], tight=True, width=320,
                              scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                     ft.FilledButton("Add", on_click=save_rule)],
        )
        page.show_dialog(dialog)

    # ---- export / import (backup, to move your data to a new device) ----
    def backup_text():
        return sv.dump_backup(db.export_data())

    saver, opener, clipboard = ft.FilePicker(), ft.FilePicker(), ft.Clipboard()
    page.services.extend([saver, opener, clipboard])

    def apply_settings():
        """Re-reads every setting from the database (used after an import)."""
        sv.CURRENCY = db.get_setting("currency", "RM")
        theme_seg.selected = [saved_theme()]
        page.theme_mode = THEME_MODES[saved_theme()]
        open_add_switch.value = db.get_setting("open_add", "0") == "1"
        apply_theme()
        name = db.get_setting("app_name", "WhereMyMoney")
        page.title = app_title.value = app_name_field.value = name
        currency_field.value = sv.CURRENCY
        refresh_category_controls()
        refresh_recurring()
        refresh()
        sync_quick_config()

    def start_import(text):
        try:
            data = sv.load_backup(text)
            db.validate_backup(data)
        except ValueError as problem:
            toast(str(problem))
            return

        def do_import():
            db.import_data(data)
            apply_settings()
            toast(f"Imported {len(data['transactions'])} transactions")

        confirm("Replace all data?",
                f"This replaces everything in the app with the backup "
                f"({len(data['transactions'])} transactions). It can't be undone.",
                do_import, yes_label="Replace")

    def open_export(e):
        async def save_file(ev):
            page.pop_dialog()
            state["skip_lock"] = True  # the system file dialog pauses the app: don't lock for that
            data = backup_text()
            path = await saver.save_file(file_name=f"wheremymoney-backup-{sv.today()}.json",
                                         allowed_extensions=["json"], src_bytes=data.encode("utf-8"))
            if not path:
                return
            if page.platform not in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS):  # computers: we write the file
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        f.write(data)
                except OSError as problem:
                    toast(f"Could not save the file: {problem}")
                    return
            toast("Backup saved")

        async def copy_text(ev):
            page.pop_dialog()
            await clipboard.set(backup_text())
            toast("Backup copied. Paste it into a note or message to yourself.")

        dialog = ft.AlertDialog(
            title=ft.Text("Export data"),
            content=ft.Text("Creates a backup of everything: transactions, budgets, recurring entries "
                            "and settings. Save it as a file, or copy it as text."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                     ft.OutlinedButton("Copy as text", on_click=copy_text),
                     ft.FilledButton("Save file", on_click=save_file)],
        )
        page.show_dialog(dialog)

    def open_paste():
        box = field(label="Paste backup text here", multiline=True, min_lines=4, max_lines=8)

        def go(ev):
            page.pop_dialog()
            start_import(box.value)

        dialog = ft.AlertDialog(
            title=ft.Text("Paste backup"), content=ft.Container(box, width=320),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                     ft.FilledButton("Import", on_click=go)],
        )
        page.show_dialog(dialog)

    def open_import(e):
        async def choose_file(ev):
            page.pop_dialog()
            state["skip_lock"] = True
            files = await opener.pick_files(dialog_title="Choose backup file", allowed_extensions=["json"],
                                            with_data=True)
            if not files:
                return
            picked = files[0]
            try:
                if picked.path:
                    with open(picked.path, encoding="utf-8") as f:
                        text = f.read()
                else:
                    text = bytes(picked.bytes).decode("utf-8")
            except (OSError, UnicodeDecodeError, TypeError) as problem:
                toast(f"Could not read the file: {problem}. Use 'Paste text' instead.")
                return
            start_import(text)

        def paste_text(ev):
            page.pop_dialog()
            open_paste()

        dialog = ft.AlertDialog(
            title=ft.Text("Import data"),
            content=ft.Text("Choose a backup file made with Export data, or paste the backup text. "
                            "Importing replaces all data currently in the app."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                     ft.OutlinedButton("Paste text", on_click=paste_text),
                     ft.FilledButton("Choose file", on_click=choose_file)],
        )
        page.show_dialog(dialog)

    theme_seg = ft.SegmentedButton(
        selected=[saved_theme()], allow_multiple_selection=False, show_selected_icon=False, on_change=set_theme,
        segments=[ft.Segment(value="system", label=ft.Text("Phone"), icon=ft.Icon(ft.Icons.BRIGHTNESS_AUTO)),
                  ft.Segment(value="light", label=ft.Text("Light"), icon=ft.Icon(ft.Icons.LIGHT_MODE)),
                  ft.Segment(value="dark", label=ft.Text("Dark"), icon=ft.Icon(ft.Icons.DARK_MODE))])
    # ================= PAGES =================
    MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    BLACK = "#000000"

    def month_title(month):
        name = MONTHS[int(month[5:7]) - 1]
        return name if month[:4] == sv.today()[:4] else f"{name} {month[:4]}"

    def day_label(day):
        return datetime.strptime(day, "%Y-%m-%d").strftime("%b %d %a")

    def nice_step(x):
        if x <= 0:
            return 1
        mag = 10 ** math.floor(math.log10(x))
        return next(m * mag for m in (1, 2, 5, 10) if x <= m * mag)

    def pick_month(e=None):
        pick = {"year": int(state["month"][:4])}
        year_text = ft.Text(size=18, weight=ft.FontWeight.BOLD)
        grid = ft.Row(wrap=True, spacing=8, run_spacing=8, alignment=ft.MainAxisAlignment.CENTER)

        def choose(month):
            state["month"] = month
            page.pop_dialog()
            refresh()

        def build():
            year_text.value = str(pick["year"])
            grid.controls = [
                ft.Container(
                    ft.Text(MONTHS[i], color=BLACK if f"{pick['year']}-{i + 1:02d}" == state["month"] else None),
                    width=72, height=44, alignment=ft.Alignment.CENTER, border_radius=12,
                    bgcolor=YELLOW if f"{pick['year']}-{i + 1:02d}" == state["month"]
                    else ft.Colors.with_opacity(0.1, ft.Colors.ON_SURFACE),
                    on_click=lambda e, m=f"{pick['year']}-{i + 1:02d}": choose(m))
                for i in range(12)
            ]
            page.update()

        def shift_year(delta):
            pick["year"] += delta
            build()

        dialog = ft.AlertDialog(
            content=ft.Column([
                ft.Row([ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda e: shift_year(-1)), year_text,
                        ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda e: shift_year(1))],
                       alignment=ft.MainAxisAlignment.CENTER), grid], tight=True, width=300),
            actions=[ft.TextButton("This month", on_click=lambda e: choose(sv.today()[:7])),
                     ft.TextButton("Close", on_click=lambda e: page.pop_dialog())])
        build()
        page.show_dialog(dialog)

    def on_swipe(e):  # swipe left = next month, swipe right = previous month
        velocity = e.primary_velocity or 0
        if velocity < -300:
            change_month(1)
        elif velocity > 300:
            change_month(-1)

    def month_button(text_control):
        return ft.Container(ft.Row([text_control, ft.Icon(ft.Icons.ARROW_DROP_DOWN)], tight=True, spacing=0),
                            on_click=pick_month)

    # ---- filters: tap to filter, tap again to clear ----
    fl = {"wallet": "", "kind": "", "category": "", "period": "month"}
    GROUPS = {
        "wallet": [("Bank", I.ACCOUNT_BALANCE, "Bank", None), ("Wallet", I.ACCOUNT_BALANCE_WALLET, "Wallet", None)],
        "period": [("month", I.CALENDAR_VIEW_MONTH, "Month", None), ("year", I.CALENDAR_MONTH, "Year", None)],
        "kind": [("expense", I.ARROW_UPWARD, "Expenses", ft.Colors.RED), ("income", I.ARROW_DOWNWARD, "Income", ft.Colors.GREEN)],
    }
    group_rows = []

    def toggle_filter(key, value):
        fl[key] = value if key == "period" else ("" if fl[key] == value else value)  # Month/Year: one is always on
        refresh()

    def make_group(key):
        """Two round buttons joined in one capsule."""
        row = ft.Row(spacing=0)
        group_rows.append((row, key))
        return ft.Container(row, padding=2, border_radius=24, bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE))

    def draw_groups():
        """The chosen option grows into a yellow pill with its word; the others stay as plain round icons."""
        def option(key, value, icon, tip, color):
            on = fl[key] == value
            content = (ft.Row([ft.Icon(icon, size=20, color=BLACK),
                               ft.Text(tip, size=14, color=BLACK, weight=ft.FontWeight.W_500)], tight=True, spacing=6)
                       if on else ft.Icon(icon, size=20, color=color or ft.Colors.ON_SURFACE))
            return feel(ft.Container(content, width=None if on else 40, height=40, border_radius=20,
                                     alignment=ft.Alignment.CENTER, tooltip=tip,
                                     padding=ft.Padding.symmetric(horizontal=14) if on else None,
                                     bgcolor=YELLOW if on else None,
                                     on_click=lambda e, k=key, v=value: toggle_filter(k, v)), "select")

        for row, key in group_rows:
            row.controls = [option(key, value, icon, tip, color) for value, icon, tip, color in GROUPS[key]]

    chip_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)

    def draw_chips():
        def chip(name):
            value = "" if name == ALL else name
            on = fl["category"] == value
            return feel(ft.Container(
                ft.Row([ft.Icon(CATEGORY_ICONS.get(name, I.MORE_HORIZ), size=16, color=BLACK if on else None),
                        ft.Text(name, size=13, color=BLACK if on else None)], tight=True, spacing=6),
                padding=ft.Padding.symmetric(horizontal=12, vertical=8), border_radius=20,
                bgcolor=YELLOW if on else ft.Colors.SURFACE,
                on_click=lambda e, v=value: toggle_filter("category", v)), "select")
        chip_row.controls = [chip(n) for n in [ALL] + db.CATEGORIES]

    def wallet_filter():
        return fl["wallet"]

    def stat_cell(title, value, arrow=None, color=None):
        head = ([ft.Icon(arrow, color=color, size=16)] if arrow else []) + [ft.Text(title, size=14, color=ft.Colors.OUTLINE)]
        return ft.Column([ft.Row(head, alignment=ft.MainAxisAlignment.CENTER, spacing=2), value],
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, expand=True)

    def divider():
        return ft.Container(width=1, height=36, bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE))

    def amount_text(size=18):  # one line only; too-long numbers end in "..." instead of wrapping
        return ft.Text(size=size, weight=ft.FontWeight.W_500, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS,
                       text_align=ft.TextAlign.CENTER)

    def yellow_plus(on_click):
        return feel(ft.Container(ft.Icon(ft.Icons.ADD, color=BLACK), width=48, height=48, border_radius=24,
                                 bgcolor=YELLOW, alignment=ft.Alignment.CENTER, on_click=on_click), "medium")

    # ================= HOME =================
    home_month = ft.Text(size=26, weight=ft.FontWeight.W_500)
    h_exp, h_inc, h_bal = amount_text(), amount_text(), amount_text()
    budget_hint = ft.Text(size=15, expand=True)
    home_list = ft.Column(spacing=10)
    home_header = ft.Row(
        [month_button(home_month),
         ft.Row([ft.IconButton(ft.Icons.SEARCH, tooltip="Search", on_click=lambda e: open_search_page()),
                 ft.IconButton(ft.Icons.CALENDAR_MONTH, tooltip="Calendar",
                               on_click=lambda e: open_calendar_page())], spacing=0)],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    home_filters = ft.Column([ft.Row([make_group("wallet"), make_group("kind")], spacing=12), chip_row], spacing=10)
    summary_card = card(
        ft.Row([stat_cell("Expenses", h_exp, ft.Icons.ARROW_UPWARD, ft.Colors.RED), divider(),
                stat_cell("Income", h_inc, ft.Icons.ARROW_DOWNWARD, ft.Colors.GREEN), divider(),
                stat_cell("Balance", h_bal)]),
        ft.Divider(height=1),
        ft.Container(ft.Row([budget_hint, ft.Icon(ft.Icons.CHEVRON_RIGHT)]), padding=ft.Padding.symmetric(vertical=6),
                     on_click=lambda e: open_budget_page()))
    home_view = ft.Column([home_header, home_filters, summary_card, home_list, ft.Container(height=100)],
                          scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)

    def record_tile(t):
        income = t["type"] == "income"
        return ft.Container(
            ft.Row([
                badge(t["category"]),
                ft.Column([ft.Text(t["category"], size=16, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                           ft.Text(f"{t['wallet']}  {t['note']}".strip(), size=12, color=ft.Colors.OUTLINE,
                                   max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)],
                          spacing=0, expand=True),
                ft.Text(f"{'+' if income else '-'}{sv.money(t['amount_cents'])}", size=16, no_wrap=True,
                        color=ft.Colors.GREEN if income else None)],  # tap the row to edit
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10), ink=True,
            on_click=lambda e, t=t: open_entry(t))

    def home_rows():
        month, today = state["month"], sv.today()
        rows = db.list_transactions(month, "", fl["category"], fl["kind"], fl["wallet"])
        out = []
        if month == today[:7] and not any(t["date"] == today for t in rows):
            out += [ft.Text(f"Today {day_label(today)}", size=18, weight=ft.FontWeight.BOLD),
                    card(ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, size=44), ft.Text("No record for today", size=17, expand=True),
                                 yellow_plus(lambda e: open_entry())], vertical_alignment=ft.CrossAxisAlignment.CENTER))]
        groups = {}
        for t in rows:
            groups.setdefault(t["date"], []).append(t)
        for day, items in groups.items():
            exp = sum(t["amount_cents"] for t in items if t["type"] == "expense")
            inc = sum(t["amount_cents"] for t in items if t["type"] == "income")
            totals = [ft.Row([ft.Icon(arrow, size=14, color=color),
                              ft.Text(sv.money(amount), size=13, color=ft.Colors.OUTLINE, no_wrap=True)],
                             tight=True, spacing=2)
                      for arrow, color, amount in ((ft.Icons.ARROW_UPWARD, ft.Colors.RED, exp),
                                                   (ft.Icons.ARROW_DOWNWARD, ft.Colors.GREEN, inc)) if amount]
            out.append(ft.Row([ft.Text(day_label(day), size=16, weight=ft.FontWeight.BOLD, no_wrap=True),
                               ft.Row(totals, tight=True, spacing=10)],
                              alignment=ft.MainAxisAlignment.SPACE_BETWEEN))
            out.append(ft.Container(ft.Column([record_tile(t) for t in items], spacing=0),
                                    bgcolor=ft.Colors.SURFACE, border_radius=20, padding=4))
        return out

    # ================= REPORTS =================
    r_state = {"line": "expense", "pie": "expense", "top": "expense"}
    pill_texts = {}

    def make_pill(key):
        text = ft.Text("Expenses", size=14, color=BLACK, weight=ft.FontWeight.W_500)
        pill_texts[key] = text

        def toggle(e):
            r_state[key] = "income" if r_state[key] == "expense" else "expense"
            refresh()

        return ft.Container(ft.Row([text, ft.Icon(ft.Icons.SWAP_HORIZ, size=16, color=BLACK)], tight=True, spacing=4),
                            bgcolor=YELLOW, border_radius=20, padding=ft.Padding.symmetric(horizontal=14, vertical=6),
                            on_click=toggle)

    rep_month = ft.Text(size=26, weight=ft.FontWeight.W_500)
    line_total, line_avg = ft.Text(size=18), ft.Text(size=13, color=ft.Colors.OUTLINE)
    line_chart = fch.LineChart(
        data_series=[], height=220, min_x=1, max_x=31, min_y=0, max_y=100, interactive=False,
        horizontal_grid_lines=fch.ChartGridLines(interval=20, color=ft.Colors.with_opacity(0.35, YELLOW), width=1,
                                                dash_pattern=[4, 4]),
        left_axis=fch.ChartAxis(labels=[], label_size=44), bottom_axis=fch.ChartAxis(labels=[], label_size=26))
    pie = fch.PieChart(sections=[], sections_space=1, center_space_radius=0)
    pie_legend, top_list = ft.Column(spacing=8), ft.Column(spacing=10)
    reports_view = ft.Column(
        [ft.Row([month_button(rep_month)], alignment=ft.MainAxisAlignment.START),
         ft.Row([make_group("wallet"), make_group("period")], alignment=ft.MainAxisAlignment.START, spacing=12),
         card(ft.Row([ft.Column([line_total, line_avg], spacing=2, expand=True), make_pill("line")],
                     vertical_alignment=ft.CrossAxisAlignment.START), line_chart),
         card(ft.Row([ft.Text("Category Ranking", size=18, expand=True), make_pill("pie")]),
              ft.Container(pie, height=240), pie_legend),
         card(ft.Row([ft.Text("Bill Amount Ranking TOP 10", size=18, expand=True), make_pill("top")]), top_list),
         ft.Container(height=100)],
        scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)

    # ================= ACCOUNTS =================
    net_text, assets_text, debts_text = ft.Text(size=40, weight=ft.FontWeight.BOLD), amount_text(26), amount_text(26)
    account_rows = ft.Column(spacing=14)
    accounts_view = ft.Column(
        [ft.Text("Accounts", size=24, weight=ft.FontWeight.W_500),
         ft.Container(ft.Column([
             ft.Text("Net Assets", size=18), net_text, ft.Container(height=10),
             ft.Row([ft.Column([ft.Text("Assets", size=17), assets_text], expand=True, spacing=2),
                     ft.Column([ft.Text("Debts", size=17), debts_text], expand=True, spacing=2)]),
             ft.Divider(height=24)], spacing=4),
             bgcolor=ft.Colors.SURFACE, border_radius=20, padding=24),
         card(account_rows), ft.Container(height=100)],
        scroll=ft.ScrollMode.AUTO, spacing=14, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ================= CATEGORIES (add / edit / delete) =================
    category_rows = ft.Column(spacing=0)

    def refresh_category_controls():
        load_categories()
        if fl["category"] not in db.CATEGORIES:
            fl["category"] = ""

    def build_category_rows():
        category_rows.controls = [
            ft.Container(
                ft.Row([badge(r["name"], 40), ft.Text(r["name"], size=16, expand=True),
                        ft.Icon(ft.Icons.EDIT_OUTLINED, color=ft.Colors.OUTLINE)],
                       spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=8, vertical=8), ink=True,
                on_click=lambda e, n=r["name"]: edit_category(n))
            for r in db.list_categories()]

    def after_category_change():
        sync_quick_config()
        refresh_category_controls()
        build_category_rows()
        refresh()
        toast("Saved")

    def edit_category(name=None):
        current = next((r for r in db.list_categories() if r["name"] == name), None) if name else None
        pick = {"icon": current["icon"] if current else "more", "color": current["color"] if current else COLOR_CHOICES[0]}
        name_box = field(label="Name", value=name or "")
        error = ft.Text(color=ft.Colors.RED)
        preview = ft.Row(alignment=ft.MainAxisAlignment.CENTER)
        icon_row = ft.Row(wrap=True, spacing=6, run_spacing=6, alignment=ft.MainAxisAlignment.CENTER)
        color_row = ft.Row(wrap=True, spacing=8, run_spacing=8, alignment=ft.MainAxisAlignment.CENTER)

        def choose(key, value):
            pick[key] = value
            draw()

        def draw():
            preview.controls = [ft.Container(
                ft.Icon(ICON_CHOICES.get(pick["icon"], I.MORE_HORIZ), color="#5D4037", size=30), width=60, height=60,
                border_radius=30, bgcolor=pick["color"], alignment=ft.Alignment.CENTER)]
            icon_row.controls = [
                ft.Container(ft.Icon(icon, size=22), width=42, height=42, border_radius=10,
                             alignment=ft.Alignment.CENTER,
                             bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                             border=ft.Border.all(2, YELLOW) if key == pick["icon"] else None,
                             on_click=lambda e, k=key: choose("icon", k))
                for key, icon in ICON_CHOICES.items()]
            color_row.controls = [
                ft.Container(width=32, height=32, border_radius=16, bgcolor=c,
                             border=ft.Border.all(3, ft.Colors.ON_SURFACE) if c == pick["color"] else None,
                             on_click=lambda e, c=c: choose("color", c))
                for c in COLOR_CHOICES]
            page.update()

        def run(action):
            try:
                action()
            except ValueError as problem:
                error.value = str(problem)
                page.update()
                return
            page.pop_dialog()
            after_category_change()

        actions = [ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                   ft.FilledButton("Save", on_click=lambda e: run(
                       (lambda: db.update_category(name, name_box.value, pick["icon"], pick["color"])) if current
                       else (lambda: db.add_category(name_box.value, pick["icon"], pick["color"]))))]
        if current:
            actions.insert(0, ft.TextButton("Delete", on_click=lambda e: run(lambda: db.delete_category(name))))
        dialog = ft.AlertDialog(
            title=ft.Text("Edit category" if current else "New category"),
            content=ft.Column([preview, name_box, ft.Text("Icon", size=12), icon_row, ft.Text("Colour", size=12),
                               color_row, error], tight=True, width=320, scroll=ft.ScrollMode.AUTO),
            actions=actions)
        draw()
        page.show_dialog(dialog)

    def open_category_page():
        build_category_rows()
        open_subpage("Category", card(category_rows, ft.FilledTonalButton(
            "Add category", icon=ft.Icons.ADD, on_click=lambda e: edit_category())))

    # ================= MINE =================
    m_exp, m_inc, m_count = amount_text(), amount_text(), amount_text()

    def on_haptics_switch(e):
        state["haptics"] = bool(e.control.value)
        db.set_setting("device_haptics", "1" if state["haptics"] else "0")
        buzz("medium")  # a sample, so you feel what you just switched on

    haptics_switch = ft.Switch(label="Vibrate when tapping", value=state["haptics"], on_change=on_haptics_switch,
                               disabled=page.platform not in (ft.PagePlatform.ANDROID, ft.PagePlatform.IOS))
    open_add_switch = ft.Switch(
        label="Open on the Add screen at launch", value=db.get_setting("open_add", "0") == "1",
        on_change=lambda e: db.set_setting("open_add", "1" if e.control.value else "0"))

    def edit_name(e):
        box = field(label="Name", value=app_title.value)

        def go(ev):
            app_name_field.value = box.value
            page.pop_dialog()
            save_app_name(None)

        dialog = ft.AlertDialog(title=ft.Text("Your name"), content=ft.Container(box, width=300),
                                actions=[ft.TextButton("Cancel", on_click=lambda ev: page.pop_dialog()),
                                         ft.FilledButton("Save", on_click=go)])
        page.show_dialog(dialog)

    def tile(icon, color, text, on_click):
        return ft.Container(
            ft.Column([ft.Container(ft.Icon(icon, color="#FFFFFF", size=26), width=50, height=50, border_radius=14,
                                    bgcolor=color, alignment=ft.Alignment.CENTER),
                       ft.Text(text, size=13, text_align=ft.TextAlign.CENTER)],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            width=96, padding=6, on_click=on_click)

    def tile_grid(*tiles):
        return ft.Container(ft.Row(list(tiles), wrap=True, spacing=4, run_spacing=8),
                            bgcolor=ft.Colors.SURFACE, border_radius=20, padding=12)

    mine_view = ft.Column(
        [card(ft.Row([ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON, size=34), radius=32,
                                      bgcolor=ft.Colors.PRIMARY_CONTAINER),
                      app_title, ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=edit_name)],
                     vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)),
         card(ft.Row([stat_cell("Expenses", m_exp, ft.Icons.ARROW_UPWARD, ft.Colors.RED), divider(),
                      stat_cell("Income", m_inc, ft.Icons.ARROW_DOWNWARD, ft.Colors.GREEN), divider(),
                      stat_cell("Records", m_count)])),
         ft.Text("Commonly Used", size=18),
         tile_grid(tile(ft.Icons.BAR_CHART, "#F5A623", "Budget", lambda e: open_budget_page()),
                   tile(ft.Icons.GRID_VIEW, "#E8704A", "Category", lambda e: open_category_page())),
         ft.Text("Settings", size=18),
         tile_grid(tile(ft.Icons.LOCK, "#7E57C2", "App Lock", lambda e: open_lock_page()),
                   tile(ft.Icons.PALETTE, "#E86AA6", "Appearance", lambda e: open_subpage("Appearance", card(label("THEME"), theme_seg,
                                                                    ft.Text("Phone = follow your phone's light or dark setting.", size=12)))),
                   tile(ft.Icons.MONETIZATION_ON, "#E8A33D", "Preferences",
                        lambda e: open_subpage("Preferences", card(label("NAME"), app_name_field),
                                               card(label("CURRENCY"), currency_field),
                                               card(label("LAUNCH"), open_add_switch,
                                                    ft.Text("Opens the new-record panel straight away, so one tap "
                                                            "on the app icon is enough to add a record.", size=12)),
                                               card(label("QUICK ADD"), notify_switch, notify_note),
                                               card(label("FEEDBACK"), haptics_switch,
                                                    ft.Text("A short vibration on keypad taps, choices and "
                                                            "when something is saved. Phones with touch "
                                                            "vibration turned off in system settings stay silent.",
                                                            size=12)))),
                   tile(ft.Icons.FOLDER_OPEN, "#5AA9E6", "Export Data", open_export),
                   tile(ft.Icons.DOWNLOAD, "#4FB477", "Import Data", open_import)),
         ft.Container(height=100)],
        scroll=ft.ScrollMode.AUTO, spacing=12, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ================= APP LOCK (optional 4-digit PIN) =================
    lock_state = {"pin": ""}
    lock_dots = ft.Row(alignment=ft.MainAxisAlignment.CENTER, spacing=14)
    lock_msg = ft.Text(color=ft.Colors.RED, size=13, height=20)

    def lock_enabled():
        return bool(db.get_setting("lock", ""))

    def draw_dots():
        lock_dots.controls = [
            ft.Container(width=16, height=16, border_radius=8,
                         bgcolor=YELLOW if i < len(lock_state["pin"]) else ft.Colors.with_opacity(0.25, ft.Colors.ON_SURFACE))
            for i in range(4)]

    def lock_key(k):
        if k == "":
            return ft.Container(width=72, height=72)
        return feel(ft.Container(ft.Text(k, size=26), width=72, height=72, border_radius=36,
                                 alignment=ft.Alignment.CENTER, bgcolor=None if k == "⌫" else ft.Colors.SURFACE,
                                 on_click=lambda e, k=k: lock_press(k)))

    def lock_press(k):
        pin = lock_state["pin"]
        lock_state["pin"] = pin[:-1] if k == "⌫" else (pin + k if len(pin) < 4 else pin)
        draw_dots()
        if len(lock_state["pin"]) == 4:
            try_unlock()
        page.update()

    def try_unlock():
        pin, lock_state["pin"] = lock_state["pin"], ""
        wait = float(db.get_setting("lock_until", "0") or 0) - time.time()
        if wait > 0:
            lock_msg.value = f"Too many tries. Wait {int(wait) + 1} seconds."
        elif sv.check_pin(pin, db.get_setting("lock", "")):
            db.set_setting("lock_fails", "0")
            buzz("medium")
            unlock()
            return
        else:
            fails = int(db.get_setting("lock_fails", "0") or 0) + 1
            db.set_setting("lock_fails", str(fails))
            lock_msg.value = "Wrong PIN"
            buzz("heavy")
            if fails % 5 == 0:  # every 5 wrong tries the wait grows: 30s, 60s, 90s...
                db.set_setting("lock_until", str(time.time() + 30 * (fails // 5)))
                lock_msg.value = f"Too many tries. Wait {30 * (fails // 5)} seconds."
        draw_dots()

    bio_button = ft.TextButton("Use fingerprint", icon=ft.Icons.FINGERPRINT, visible=False,
                               on_click=lambda e: ask_fingerprint())

    lock_screen = ft.SafeArea(
        ft.Container(
            ft.Column([
                ft.Icon(ft.Icons.LOCK, size=44, color=YELLOW), ft.Text("Enter your PIN", size=20), lock_dots, lock_msg,
                ft.Column([ft.Row([lock_key(k) for k in row], alignment=ft.MainAxisAlignment.CENTER, spacing=18)
                           for row in (["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], ["", "0", "⌫"])], spacing=14),
                bio_button,
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, alignment=ft.MainAxisAlignment.CENTER, spacing=16),
            alignment=ft.Alignment.CENTER, expand=True),
        expand=True, visible=False)

    def lock():
        was_locked = lock_screen.visible
        lock_state["pin"] = ""
        lock_msg.value = ""
        draw_dots()
        while page.pop_dialog():  # close open dialogs/sheets so nothing stays visible over the lock screen
            pass
        main_area.visible = False
        lock_screen.visible = True
        page.bottom_appbar.visible = False
        page.floating_action_button.visible = False
        bio_button.visible = fingerprint_enabled()
        page.update()
        if fingerprint_enabled() and not was_locked:  # already locked: don't stack up a second prompt
            ask_fingerprint()

    def fingerprint_enabled():
        return (page.platform == ft.PagePlatform.ANDROID and lock_enabled()
                and db.get_setting("lock_bio", "0") == "1" and db.biometric_available())

    def ask_fingerprint():
        """Android shows its fingerprint prompt; a success comes back as a signed file that we poll for."""
        token = db.request_biometric()
        state["bio_token"] = token
        if token:
            page.run_task(wait_fingerprint, token)

    async def wait_fingerprint(token):
        while lock_screen.visible and state.get("bio_token") == token:
            await asyncio.sleep(0.4)
            if db.biometric_succeeded(token):
                state["bio_token"] = ""
                # The system prompt can send late "app paused" events right after it closes; don't re-lock on those.
                state["bio_grace"] = time.time() + 3
                db.set_setting("lock_fails", "0")
                unlock()
                return

    def unlock():
        lock_screen.visible = False
        main_area.visible = True
        page.bottom_appbar.visible = True
        build_nav()
        refresh()
        kind = state.pop("open_after_unlock", None)
        if kind:
            open_entry(kind=kind)

    def on_lifecycle(e):  # lock again whenever the app goes to the background
        if e.state == ft.AppLifecycleState.RESUME:
            state["skip_lock"] = False
            import_quick_records(True)
        elif e.state in (ft.AppLifecycleState.PAUSE, ft.AppLifecycleState.HIDE):
            if lock_enabled() and not state.get("skip_lock") and time.time() > state.get("bio_grace", 0):
                lock()

    def pin_field(text):
        return field(label=text, password=True, can_reveal_password=True, max_length=4,
                     keyboard_type=ft.KeyboardType.NUMBER,
                     input_filter=ft.InputFilter(allow=True, regex_string=r"[0-9]", replacement_string=""))

    def pin_dialog(mode):  # mode: "create", "change" or "disable"
        old, new, again = pin_field("Current PIN"), pin_field("New PIN (4 digits)"), pin_field("Repeat new PIN")
        error = ft.Text(color=ft.Colors.RED)
        fields = ([old] if mode != "create" else []) + ([new, again] if mode != "disable" else [])

        def cancel(e=None):
            page.pop_dialog()
            sync_lock_controls()

        def ok(e):
            if mode != "create" and not sv.check_pin(old.value or "", db.get_setting("lock", "")):
                error.value = "Wrong current PIN"
            elif mode != "disable" and not re.fullmatch(r"\d{4}", new.value or ""):
                error.value = "The PIN must be exactly 4 digits"
            elif mode != "disable" and new.value != again.value:
                error.value = "The two PINs don't match"
            else:
                db.set_setting("lock", "" if mode == "disable" else sv.hash_pin(new.value))
                db.set_setting("lock_fails", "0")
                if mode == "disable":
                    db.set_setting("lock_bio", "0")
                page.pop_dialog()
                sync_lock_controls()
                toast("App lock turned off" if mode == "disable" else "PIN saved")
                return
            page.update()

        dialog = ft.AlertDialog(
            title=ft.Text({"create": "Create a PIN", "change": "Change PIN", "disable": "Turn off App Lock"}[mode]),
            content=ft.Column(fields + [error], tight=True, width=300), on_dismiss=lambda e: sync_lock_controls(),
            actions=[ft.TextButton("Cancel", on_click=cancel), ft.FilledButton("OK", on_click=ok)])
        page.show_dialog(dialog)

    lock_switch = ft.Switch(label="Ask for a PIN when opening the app", value=lock_enabled(),
                            on_change=lambda e: pin_dialog("create" if e.control.value else "disable"))
    change_pin_btn = ft.FilledTonalButton("Change PIN", icon=ft.Icons.EDIT, visible=lock_enabled(),
                                          on_click=lambda e: pin_dialog("change"))

    def on_bio_switch(e):
        db.set_setting("lock_bio", "1" if e.control.value else "0")
        toast("Fingerprint unlock on" if e.control.value else "Fingerprint unlock off")

    bio_switch = ft.Switch(label="Unlock with fingerprint", value=False, on_change=on_bio_switch)
    bio_note = ft.Text(size=12)

    def sync_lock_controls():
        lock_switch.value = lock_enabled()
        change_pin_btn.visible = lock_enabled()
        on_android = page.platform == ft.PagePlatform.ANDROID
        can_bio = on_android and db.biometric_available()
        bio_switch.visible = bio_note.visible = lock_enabled()
        bio_switch.value = can_bio and db.get_setting("lock_bio", "0") == "1"
        bio_switch.disabled = not can_bio
        bio_note.value = ("The PIN keypad stays available as a backup." if can_bio else
                          "Not available: it needs Android 9 or newer, a fingerprint set up in your phone's "
                          "settings, and the installed app (not the computer version).")
        page.update()

    def open_lock_page():
        sync_lock_controls()
        open_subpage("App Lock", card(
            label("APP LOCK"), lock_switch, change_pin_btn, bio_switch, bio_note,
            ft.Text("The app asks for your 4-digit PIN when you open it and each time you come back to it. "
                    "If you forget the PIN, the only way in is to clear the app's data, which erases your records, "
                    "so use Export Data regularly. The lock keeps other people out of the app; "
                    "it does not encrypt the data file.", size=12)))

    # ================= QUICK-ADD (Android notification + pop-up form) =================
    def sync_quick_config():
        """Tells the Android side whether to show the notification and what the pop-up form offers."""
        try:
            db.write_quick_config(db.get_setting("device_quick_notify", "0") == "1", sv.CURRENCY,
                                  app_title.value, db.CATEGORIES)
        except OSError:
            pass

    def import_quick_records(announce=False):
        """Records typed into the pop-up form while the app was closed are waiting in a file."""
        added = db.import_quick_inbox()
        if added:
            refresh()
            if announce:
                toast(f"Added {added} record(s) from the quick-add form")
        return added

    def on_notify_switch(e):
        db.set_setting("device_quick_notify", "1" if e.control.value else "0")
        sync_quick_config()
        page.update()

    notify_switch = ft.Switch(label="Notification shortcut", value=db.get_setting("device_quick_notify", "0") == "1",
                              disabled=page.platform != ft.PagePlatform.ANDROID, on_change=on_notify_switch)
    notify_note = ft.Text(
        "Android only. Keeps a quiet notification with Expense, Income and Open app buttons. Expense and Income "
        "open a small form over whatever app you are using (category, account and memo included) without opening "
        "WhereMyMoney. The new records show up here the next time you open the app. It needs the Android patch "
        "step when building (see README).", size=12)

    # ================= SUB-PAGES + NAVIGATION =================
    body = ft.Container(expand=True, padding=16)
    swipe = lambda view: ft.GestureDetector(content=view, on_horizontal_drag_end=on_swipe, expand=True)
    tabs = [swipe(home_view), swipe(reports_view), accounts_view, mine_view]

    def open_subpage(title, *controls, back=None):
        """title is text, or a control (the Search page puts its search box there). back = page to return to."""
        state["redraw"] = None
        head = title if isinstance(title, ft.Control) else ft.Text(title, size=20, weight=ft.FontWeight.W_500)
        body.content = ft.Column(
            [ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: back() if back else show_tab(state["tab"])),
                     head],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER), *controls],
            scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)
        state["sub"] = True
        build_nav()
        page.update()

    def edit_budget(category, on_done=None):
        """Set, change or remove the monthly limit of one category (on_done runs after saving/removing)."""
        budgets = db.get_budgets()
        cat = ft.Row([badge(category, 40), ft.Text(category, size=18)], spacing=12)
        amount = field(label="Monthly limit", prefix_text=prefix(), text_size=24, autofocus=True,
                       keyboard_type=ft.KeyboardType.NUMBER,
                       value=f"{budgets[category] / 100:.2f}" if category in budgets else "")
        error = ft.Text(color=ft.Colors.RED)

        def save(e):
            try:
                cents = sv.parse_amount(amount.value)
            except ValueError as problem:
                error.value = str(problem)
                page.update()
                return
            db.set_budget(category, cents)
            page.pop_dialog()
            refresh()
            toast("Budget saved")
            if on_done:
                on_done()

        def remove(e):
            db.set_budget(category, 0)
            page.pop_dialog()
            refresh()
            toast("Budget removed")
            if on_done:
                on_done()

        actions = [ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                   ft.FilledButton("Save", on_click=save)]
        if category in budgets:
            actions.insert(1, ft.TextButton("Remove", on_click=remove))
        page.show_dialog(ft.AlertDialog(title=ft.Text("Monthly budget"),
                                        content=ft.Column([cat, amount, error], tight=True, width=320),
                                        actions=actions))

    def open_category_budget_page():
        """Pick which category to budget: a grid of all categories (the ones with a budget have a yellow ring)."""
        budgets = db.get_budgets()
        items = [ft.Container(
            ft.Column([badge(c, 64, c in budgets),
                       ft.Text(c, size=11, text_align=ft.TextAlign.CENTER, max_lines=2)],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=4),
            width=78, on_click=lambda e, c=c: edit_budget(c, on_done=open_budget_page)) for c in db.CATEGORIES]
        open_subpage("Category Budget", ft.Row(items, wrap=True, spacing=0, run_spacing=16,
                                               alignment=ft.MainAxisAlignment.CENTER),
                     ft.Container(height=60), back=open_budget_page)

    def open_budget_page():
        track = ft.Colors.with_opacity(0.12, ft.Colors.ON_SURFACE)
        month_text = ft.Text(size=22, weight=ft.FontWeight.W_500)
        ring = ft.ProgressRing(value=1, width=112, height=112, stroke_width=16, color=YELLOW, bgcolor=track)
        ring_text = ft.Text(size=22, weight=ft.FontWeight.W_500)
        total_t, left_t, avg_t = (ft.Text(size=17) for _ in range(3))
        rows = ft.Column(spacing=16)
        rows_card = ft.Container(rows, bgcolor=ft.Colors.SURFACE, border_radius=20, padding=16)

        def stat(name, value):
            return ft.Row([ft.Text(name, size=15, color=ft.Colors.OUTLINE, expand=True), value])

        def draw():
            month, today = state["month"], sv.today()
            month_text.value = month_title(month)
            budgets = db.get_budgets()
            spent = {r["category"]: r["total"] for r in db.category_totals(month, "expense")}
            total = sum(budgets.values())
            left = total - sum(spent.get(c, 0) for c in budgets)
            days = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
            days_left = days - int(today[8:]) + 1 if month == today[:7] else (days if month > today[:7] else 0)
            over = bool(total) and left < 0
            pct = max(0, left) / total if total else 1
            ring.value, ring.color = pct, ft.Colors.RED if over else YELLOW
            ring_text.value = "Over" if over else f"{pct * 100:.0f}%"
            total_t.value, left_t.value = sv.money(total), sv.money(left)
            left_t.color = ft.Colors.RED if over else None
            avg_t.value = sv.money(max(left, 0) // days_left if days_left else 0)

            def row(c):
                limit, used = budgets[c], spent.get(c, 0)
                is_over = used > limit
                return ft.Container(
                    ft.Column([
                        ft.Row([badge(c, 40),
                                ft.Column([ft.Text(c, size=16),
                                           ft.Text(f"{sv.money(used)} of {sv.money(limit)}", size=12,
                                                   color=ft.Colors.OUTLINE)], spacing=0, expand=True),
                                ft.Text(f"Over {sv.money(used - limit)}" if is_over else f"{sv.money(limit - used)} left",
                                        size=13, color=ft.Colors.RED if is_over else ft.Colors.OUTLINE)],
                               spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        ft.ProgressBar(value=min(used / limit, 1), color=ft.Colors.RED if is_over else YELLOW,
                                       bgcolor=track, bar_height=8, border_radius=4)], spacing=8),
                    on_click=lambda e, c=c: edit_budget(c))  # stays on this page: refresh() redraws it

            rows.controls = [row(c) for c in db.CATEGORIES if c in budgets]
            rows_card.visible = bool(budgets)
            page.update()

        open_subpage(
            "Budget",
            ft.Container(ft.Column([
                month_button(month_text),
                ft.Row([ft.Stack([ring, ft.Container(ring_text, width=112, height=112, alignment=ft.Alignment.CENTER)],
                                 width=112, height=112),
                        ft.Column([stat("Budget", total_t), stat("Remaining", left_t), stat("Daily avg", avg_t)],
                                  spacing=10, expand=True)],
                       spacing=24, vertical_alignment=ft.CrossAxisAlignment.CENTER)], spacing=16),
                bgcolor=ft.Colors.SURFACE, border_radius=20, padding=20),
            rows_card,
            ft.Container(ft.Text("Add new category budget", size=17, color=ft.Colors.OUTLINE,
                                 style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE)),
                         alignment=ft.Alignment.CENTER, padding=24, on_click=lambda e: open_category_budget_page()),
            ft.Container(height=60))
        state["redraw"] = draw
        draw()

    def open_recurring_page():
        refresh_recurring()
        open_subpage("Recurring Transactions", card(
            recurring_col, ft.FilledTonalButton("Add recurring entry", icon=ft.Icons.ADD, on_click=open_recurring)))

    # ---- Calendar page: month grid with daily totals, plus the records of the chosen day ----
    def open_calendar_page():
        cal = {"date": ""}
        month_text = ft.Text(size=22, weight=ft.FontWeight.W_500)
        weeks = ft.Column(spacing=0)
        summary = ft.Row(wrap=True, spacing=16, run_spacing=4)
        day_title = ft.Text(size=18, weight=ft.FontWeight.BOLD)
        day_list = ft.Column(spacing=10)

        def round_arrow(icon, delta):
            return ft.Container(ft.Icon(icon, size=18, color=ft.Colors.SURFACE), width=32, height=32,
                                border_radius=16, bgcolor=ft.Colors.ON_SURFACE, alignment=ft.Alignment.CENTER,
                                on_click=lambda e: change_month(delta))

        def pick(iso):
            cal["date"] = iso
            draw()

        def draw():
            month, today = state["month"], sv.today()
            if not cal["date"].startswith(month):  # month changed: select today, or the 1st
                cal["date"] = today if today.startswith(month) else month + "-01"
            year, mon = int(month[:4]), int(month[5:7])
            month_text.value = f"{calendar.month_name[mon]} {year}"
            rows = db.list_transactions(month)
            per_day = {}
            for t in rows:
                totals = per_day.setdefault(t["date"], [0, 0])  # [income, expense] in cents
                totals[0 if t["type"] == "income" else 1] += t["amount_cents"]

            def cell(day):
                if not day:
                    return ft.Container(expand=True, height=62)
                iso = f"{month}-{day:02d}"
                inc, exp = per_day.get(iso, (0, 0))
                net = inc - exp
                items = [ft.Text(str(day), size=16, weight=ft.FontWeight.BOLD if iso == today else None,
                                 color=ft.Colors.OUTLINE if iso > today else None)]
                if inc or exp:
                    items.append(ft.Text(f"{net / 100:+,.2f}".replace(".00", ""), size=10,
                                         color=ft.Colors.GREEN if net >= 0 else ft.Colors.RED))
                return ft.Container(
                    ft.Column(items, spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    expand=True, height=62, border_radius=10, padding=ft.Padding.only(top=6),
                    bgcolor=ft.Colors.PRIMARY_CONTAINER if iso == today else None,
                    border=ft.Border.all(2, YELLOW) if iso == cal["date"] else None,
                    on_click=lambda e, i=iso: pick(i))

            weeks.controls = [ft.Row([cell(d) for d in week], spacing=0)
                              for week in calendar.Calendar(firstweekday=6).monthdayscalendar(year, mon)]
            income, expense = db.month_totals(month)
            summary.controls = [ft.Text(f"Expenses: {sv.money(expense)}", size=13),
                                ft.Text(f"Income: {sv.money(income)}", size=13),
                                ft.Text(f"Balance: {sv.money(income - expense)}", size=13)]
            items = [t for t in rows if t["date"] == cal["date"]]
            day_title.value = ("Today " if cal["date"] == today else "") + day_label(cal["date"])
            day_list.controls = [
                ft.Container(ft.Column([record_tile(t) for t in items], spacing=0), bgcolor=ft.Colors.SURFACE,
                             border_radius=20, padding=4)
            ] if items else [ft.Container(ft.Text("No history records", size=16, color=ft.Colors.OUTLINE),
                                          alignment=ft.Alignment.CENTER, padding=24)]
            page.update()

        header = ft.Container(
            ft.Row([ft.Text(d, size=15, weight=ft.FontWeight.W_500, color=BLACK, expand=True,
                            text_align=ft.TextAlign.CENTER) for d in ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")],
                   spacing=0),
            bgcolor=YELLOW, border_radius=14, padding=ft.Padding.symmetric(vertical=12))
        open_subpage(
            "Calendar",
            ft.Row([round_arrow(ft.Icons.CHEVRON_LEFT, -1), ft.Container(month_text, on_click=pick_month),
                    round_arrow(ft.Icons.CHEVRON_RIGHT, 1)], alignment=ft.MainAxisAlignment.CENTER, spacing=16),
            ft.Container(ft.Column([header, weeks, summary], spacing=8), bgcolor=ft.Colors.SURFACE,
                         border_radius=20, padding=ft.Padding.only(left=4, right=4, bottom=14)),
            day_title, day_list,
            ft.Row([yellow_plus(lambda e: open_entry(date=cal["date"]))], alignment=ft.MainAxisAlignment.CENTER),
            ft.Container(height=60))
        state["redraw"] = draw
        draw()

    # ---- Search page: search box + Type / Category / Account filters, across all months ----
    def open_search_page():
        s = {"q": "", "kind": "", "category": "", "wallet": "", "open": "", "draft": ""}
        TITLES = {"kind": "Type", "category": "Category", "wallet": "Account"}

        def options_for(key):
            if key == "kind":
                return [("expense", "Expense"), ("income", "Income")]
            return [(c, c) for c in (db.CATEGORIES if key == "category" else db.WALLETS)]

        box = field(hint_text="Search notes or categories", prefix_icon=ft.Icons.SEARCH, expand=True, autofocus=True,
                    on_change=lambda e: (s.update(q=(e.control.value or "").strip()), draw()))
        filter_row = ft.Row(scroll=ft.ScrollMode.AUTO, spacing=8)
        panel = ft.Container(visible=False, bgcolor=ft.Colors.SURFACE, border_radius=20, padding=16)
        n_text, exp_text, inc_text = amount_text(), amount_text(), amount_text()
        summary = card(ft.Row([stat_cell("Records", n_text), divider(),
                               stat_cell("Expenses", exp_text, ft.Icons.ARROW_UPWARD, ft.Colors.RED), divider(),
                               stat_cell("Income", inc_text, ft.Icons.ARROW_DOWNWARD, ft.Colors.GREEN)]))
        results = ft.Column(spacing=10)

        def toggle_panel(key):
            s["open"] = "" if s["open"] == key else key
            s["draft"] = s[key] if s["open"] else ""
            draw()

        def pick_option(value):
            s["draft"] = "" if s["draft"] == value else value
            draw()

        def confirm_panel(e):
            s[s["open"]], s["open"] = s["draft"], ""
            draw()

        def reset_panel(e):
            s[s["open"]], s["open"] = "", ""
            draw()

        def filter_button(key):
            chosen = dict(options_for(key)).get(s[key], "")
            opened = s["open"] == key
            return ft.Container(
                ft.Row([ft.Text(chosen or TITLES[key], size=14),
                        ft.Icon(ft.Icons.ARROW_DROP_UP if opened else ft.Icons.ARROW_DROP_DOWN, size=20)],
                       tight=True, spacing=2),
                padding=ft.Padding.symmetric(horizontal=14, vertical=8), border_radius=10, bgcolor=ft.Colors.SURFACE,
                border=ft.Border.all(1.5, YELLOW) if (chosen or opened) else None,
                on_click=lambda e, k=key: toggle_panel(k))

        def option_chip(value, text):
            on = s["draft"] == value
            return ft.Container(ft.Text(text, size=14, color=BLACK if on else None),
                                padding=ft.Padding.symmetric(horizontal=14, vertical=8), border_radius=20,
                                bgcolor=YELLOW if on else ft.Colors.with_opacity(0.08, ft.Colors.ON_SURFACE),
                                on_click=lambda e, v=value: pick_option(v))

        def draw():
            filter_row.controls = [filter_button(k) for k in TITLES]
            panel.visible = bool(s["open"])
            if s["open"]:
                panel.content = ft.Column([
                    ft.Row([option_chip(v, t) for v, t in options_for(s["open"])], wrap=True, spacing=8, run_spacing=8),
                    ft.Row([ft.OutlinedButton("Reset", height=46, expand=True, on_click=reset_panel),
                            ft.FilledButton("Confirm", height=46, expand=True, on_click=confirm_panel)], spacing=12),
                ], spacing=16)
            searching = any(s[k] for k in ("q", "kind", "category", "wallet"))
            rows = db.list_transactions(None, s["q"], s["category"], s["kind"], s["wallet"]) if searching else []
            n_text.value = str(len(rows))
            exp_text.value = sv.money(sum(t["amount_cents"] for t in rows if t["type"] == "expense"))
            inc_text.value = sv.money(sum(t["amount_cents"] for t in rows if t["type"] == "income"))
            out, groups = [], {}
            for t in rows:
                groups.setdefault(t["date"], []).append(t)
            for day, items in groups.items():
                out.append(ft.Text(day_label(day) + f"  {day[:4]}", size=15, weight=ft.FontWeight.BOLD))
                out.append(ft.Container(ft.Column([record_tile(t) for t in items], spacing=0),
                                        bgcolor=ft.Colors.SURFACE, border_radius=20, padding=4))
            if not rows:
                out = [ft.Container(ft.Column([
                    ft.Icon(ft.Icons.SEARCH if not searching else ft.Icons.SEARCH_OFF, size=64,
                            color=ft.Colors.OUTLINE),
                    ft.Text("No records found" if searching else "Type a keyword or pick a filter",
                            size=16, color=ft.Colors.OUTLINE)],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    alignment=ft.Alignment.CENTER, padding=48)]
            results.controls = out
            page.update()

        open_subpage(box, filter_row, panel, summary, results, ft.Container(height=60))
        state["redraw"] = draw
        draw()

    nav_row = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER)
    NAV = [("Home", ft.Icons.HOME), ("Reports", ft.Icons.BAR_CHART), ("Accounts", ft.Icons.ACCOUNT_BALANCE_WALLET),
           ("Mine", ft.Icons.PERSON)]

    def build_nav():
        items = []
        for i, (name, icon) in enumerate(NAV):
            color = YELLOW if state["tab"] == i else ft.Colors.OUTLINE
            items.append(feel(ft.Container(
                ft.Column([ft.Icon(icon, color=color, size=26), ft.Text(name, size=11, color=color)],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                expand=True, on_click=lambda e, i=i: show_tab(i)), "select"))
        plus_visible = state["tab"] == 0 and not state.get("sub")  # the + button lives on Home only
        nav_row.controls = items[:2] + ([ft.Container(width=76)] if plus_visible else []) + items[2:]
        page.floating_action_button.visible = plus_visible

    def show_tab(index):
        state["tab"] = index
        state["redraw"] = None
        body.content = tabs[index]
        state["sub"] = False
        build_nav()
        refresh()

    def refresh():
        month = state["month"]
        draw_groups()
        draw_chips()
        home_month.value = month_title(month)
        rep_month.value = month[:4] if fl["period"] == "year" else month_title(month)
        income, expense = db.month_totals(month)
        h_exp.value, h_inc.value, h_bal.value = sv.money(expense), sv.money(income), sv.money(income - expense)
        m_exp.value, m_inc.value = sv.money(expense), sv.money(income)
        m_count.value = str(len(db.list_transactions(month)))
        budgets = db.get_budgets()
        if budgets:
            spent = {r["category"]: r["total"] for r in db.category_totals(month, "expense")}
            left = sum(budgets.values()) - sum(spent.get(c, 0) for c in budgets)
            budget_hint.value = f"Budget left: {sv.money(left)}" if left >= 0 else f"Over budget by {sv.money(-left)}"
        else:
            budget_hint.value = "Create a budget to reduce impulse spending"
        home_list.controls = home_rows()

        wallet = wallet_filter()
        for key, text in pill_texts.items():
            text.value = "Expenses" if r_state[key] == "expense" else "Income"
        year_mode = fl["period"] == "year"
        period = month[:4] if year_mode else month
        if year_mode:
            days, daily = 12, db.monthly_totals(period, r_state["line"], wallet)
            divisor = int(sv.today()[5:7]) if period == sv.today()[:4] else 12  # this year: months so far
        else:
            days = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
            daily, divisor = db.daily_totals(month, r_state["line"], wallet), days
        total_line = sum(daily.values())
        line_total.value = f"{pill_texts['line'].value}: {sv.money(total_line)}"
        line_avg.value = f"Average per {'month' if year_mode else 'day'}: {sv.money(total_line // divisor)}"
        step = nice_step(max(list(daily.values()) + [0]) / 100 / 5)
        line_chart.data_series = [fch.LineChartData(
            points=[fch.LineChartDataPoint(d, daily.get(d, 0) / 100) for d in range(1, days + 1)],
            color=YELLOW, stroke_width=3, curved=False)]
        line_chart.min_x, line_chart.max_x, line_chart.max_y = 1, days, step * 5
        line_chart.horizontal_grid_lines.interval = step
        line_chart.left_axis.labels = [fch.ChartAxisLabel(value=i * step, label=ft.Text(f"{i * step:g}", size=11,
                                       color=ft.Colors.OUTLINE)) for i in range(6)]
        line_chart.bottom_axis.labels = [fch.ChartAxisLabel(value=d, label=ft.Text(MONTHS[d - 1] if year_mode else str(d), size=11,
                                         color=ft.Colors.OUTLINE)) for d in range(1, days + 1, 2 if year_mode else 3)]

        rows = db.category_totals(period, r_state["pie"], wallet)
        total = sum(r["total"] for r in rows)
        pie.sections = [fch.PieChartSection(r["total"] / 100, radius=100, color=PIE_COLORS[i % len(PIE_COLORS)],
                                           title=f"{r['total'] * 100 / total:.1f}%",
                                           title_style=ft.TextStyle(size=12, color="#FFFFFF"))
                        for i, r in enumerate(rows)]
        pie_legend.controls = [
            ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=PIE_COLORS[i % len(PIE_COLORS)]),
                    ft.Text(r["category"], expand=True), ft.Text(sv.money(r["total"]))], spacing=8)
            for i, r in enumerate(rows)] or [ft.Text("No data this month.", color=ft.Colors.OUTLINE)]
        top = db.top_transactions(period, r_state["top"], wallet)
        top_list.controls = [
            ft.Row([badge(t["category"], 40),
                    ft.Column([ft.Text(t["category"]), ft.Text(f"{t['date'][5:]}  {t['note']}".strip(), size=12,
                                                              color=ft.Colors.OUTLINE)], spacing=0, expand=True),
                    ft.Text(sv.money(t["amount_cents"]))], spacing=12)
            for t in top] or [ft.Container(ft.Text("Please add a bill", size=17,
                                                   style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE)),
                                           alignment=ft.Alignment.CENTER, padding=24)]

        balances = db.wallet_balances()
        assets = sum(v for v in balances.values() if v > 0)
        debts = -sum(v for v in balances.values() if v < 0)
        net_text.value, assets_text.value, debts_text.value = sv.money(assets - debts), sv.money(assets), sv.money(debts)
        account_rows.controls = [
            ft.Row([ft.Container(ft.Icon(WALLET_ICONS[name], color=BLACK), width=44, height=44, border_radius=22,
                                 bgcolor=YELLOW, alignment=ft.Alignment.CENTER),
                    ft.Text(name, size=17, expand=True), ft.Text(sv.money(bal), size=17)], spacing=14)
            for name, bal in balances.items()]
        if state.get("redraw"):  # a Calendar/Search page is open: keep it in step with edits
            state["redraw"]()
        page.update()

    page.bottom_appbar = ft.BottomAppBar(content=nav_row, shape=ft.CircularRectangleNotchShape(), notch_margin=6,
                                         bgcolor=ft.Colors.SURFACE, height=72, padding=0)
    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor=YELLOW, foreground_color=BLACK, shape=ft.CircleBorder(),
        on_click=lambda e: (buzz("medium"), open_entry()))
    page.floating_action_button_location = ft.FloatingActionButtonLocation.CENTER_DOCKED
    main_area = ft.SafeArea(body, expand=True)
    page.add(main_area, lock_screen)
    page.on_app_lifecycle_state_change = on_lifecycle
    refresh_recurring()
    sync_quick_config()
    import_quick_records()
    show_tab(0)
    draw_dots()
    if lock_enabled():
        lock()
        state["open_after_unlock"] = "expense" if open_add_switch.value else None
    elif open_add_switch.value:
        open_entry()



ft.run(main)