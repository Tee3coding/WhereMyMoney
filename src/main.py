"""WhereMyMoney: the Flet user interface. Run with: flet run src/main.py"""
import calendar
import math
import re
from datetime import datetime

import flet as ft

import database as db
import services as sv

YELLOW = "#FFD93B"
BG_DARK, BG_LIGHT = "#000000", "#F2F2F7"
# Change any icon here and it updates everywhere in the app.
CATEGORY_ICONS = {
    "Food": ft.Icons.RESTAURANT, "Transport": ft.Icons.DIRECTIONS_BUS,
    "Bills": ft.Icons.RECEIPT_LONG, "Shopping": ft.Icons.SHOPPING_BAG,
    "Health": ft.Icons.FAVORITE, "Entertainment": ft.Icons.MOVIE,
    "Salary": ft.Icons.PAYMENTS, "Other": ft.Icons.MORE_HORIZ,
    "All": ft.Icons.APPS,
}
WALLET_ICONS = {"Bank": ft.Icons.ACCOUNT_BALANCE, "Wallet": ft.Icons.ACCOUNT_BALANCE_WALLET, "All": ft.Icons.APPS}
PIE_COLORS = [ft.Colors.BLUE, ft.Colors.ORANGE, ft.Colors.GREEN, ft.Colors.PURPLE,
              ft.Colors.TEAL, ft.Colors.PINK, ft.Colors.AMBER, ft.Colors.CYAN]
ALL = "All"
CATEGORY_COLORS = {  # soft pastel circles behind each icon
    "Food": "#FFD8A8", "Transport": "#B8E0F6", "Bills": "#D9C8F5", "Shopping": "#C8EBC6",
    "Health": "#FFC9D6", "Entertainment": "#F8D5F0", "Salary": "#FFE9A0", "Other": "#E2E2E2", "All": "#E2E2E2",
}


def badge(category, size=44, selected=False):
    return ft.Container(
        ft.Icon(CATEGORY_ICONS.get(category, ft.Icons.MORE_HORIZ), color="#5D4037", size=size * 0.5),
        width=size, height=size, border_radius=size / 2, alignment=ft.alignment.center,
        bgcolor=CATEGORY_COLORS.get(category, "#E2E2E2"),
        border=ft.border.all(3, ft.Colors.PRIMARY) if selected else None,
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

    def apply_theme():
        page.theme = ft.Theme(color_scheme=scheme(False))
        page.dark_theme = ft.Theme(color_scheme=scheme(True))
        page.bgcolor = BG_DARK if page.theme_mode == ft.ThemeMode.DARK else BG_LIGHT

    page.title = db.get_setting("app_name", "WhereMyMoney")
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK if db.get_setting("dark_mode", "1") == "1" else ft.ThemeMode.LIGHT
    apply_theme()
    app_title = ft.Text(page.title, size=20, weight=ft.FontWeight.BOLD)

    def toast(message):
        page.open(ft.SnackBar(ft.Text(message)))

    def confirm(title, text, on_yes, yes_label="Delete"):
        def yes(e):
            page.close(dialog)
            on_yes()

        dialog = ft.AlertDialog(
            title=ft.Text(title), content=ft.Text(text),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
                     ft.TextButton(yes_label, on_click=yes)],
        )
        page.open(dialog)

    def prefix():
        return f"{sv.CURRENCY} "

    # ================= MONTH HELPERS =================
    month_labels = []

    def change_month(delta):
        state["month"] = sv.shift_month(state["month"], delta)
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

    def open_entry(t=None):
        form = {
            "kind": t["type"] if t else "expense", "category": t["category"] if t else db.CATEGORIES[0],
            "wallet": t["wallet"] if t else "Wallet", "date": t["date"] if t else sv.today(),
            "text": f"{t['amount_cents'] / 100:.2f}".rstrip("0").rstrip(".") if t else "",
        }
        display = ft.Text(size=34, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT)
        date_label = ft.Text(size=13)
        memo = field(label="Memo", value=t["note"] if t else "", prefix_icon=ft.Icons.EDIT_NOTE)
        error = ft.Text(color=ft.Colors.RED)
        grid = ft.Row(wrap=True, spacing=4, run_spacing=6, alignment=ft.MainAxisAlignment.CENTER)

        def choose(c):
            form["category"] = c
            show()

        def show():
            display.value = f"{sv.CURRENCY} {form['text'] or '0'}"
            date_label.value = "Today" if form["date"] == sv.today() else form["date"][5:]
            grid.controls = [
                ft.Container(
                    ft.Column([badge(c, 50, c == form["category"]), ft.Text(c, size=11)], spacing=2,
                              horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    width=78, on_click=lambda e, c=c: choose(c))
                for c in db.CATEGORIES
            ]
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

            page.open(ft.DatePicker(first_date=datetime(2020, 1, 1), last_date=datetime(2100, 12, 31),
                                    value=datetime.strptime(form["date"], "%Y-%m-%d"), on_change=chosen))

        def key_button(key):
            content = (ft.Row([ft.Icon(ft.Icons.CALENDAR_MONTH, size=16), date_label], spacing=4,
                              alignment=ft.MainAxisAlignment.CENTER)
                       if key == "date" else ft.Text("−" if key == "-" else key, size=20))
            return ft.Container(
                content, height=50, expand=True, alignment=ft.alignment.center, border_radius=14,
                bgcolor=ft.Colors.PRIMARY_CONTAINER if key in ("+", "-", "=", "date") else ft.Colors.SURFACE,
                on_click=(lambda e: pick_date()) if key == "date" else (lambda e, k=key: press(k)))

        def save(e):
            try:
                cents = sv.parse_amount(form["text"].rstrip("+-."))
            except ValueError as problem:
                error.value = str(problem)
                page.update()
                return
            args = (cents, form["kind"], form["category"], form["wallet"], form["date"], (memo.value or "").strip())
            if t:
                db.update_transaction(t["id"], *args)
            else:
                db.add_transaction(*args)
            page.close(sheet)
            refresh()
            toast("Saved")

        def remove(e):
            confirm("Delete record?", "This can't be undone.", lambda: (
                db.delete_transaction(t["id"]), page.close(sheet), refresh(), toast("Deleted")))

        def segmented(key, options):
            return ft.SegmentedButton(
                selected={form[key]}, allow_multiple_selection=False, show_selected_icon=False,
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
                    ft.Container(display, alignment=ft.alignment.center_right, padding=ft.padding.only(right=8)),
                    memo, error,
                    ft.Column([ft.Row([key_button(k) for k in row], spacing=6) for row in KEYS], spacing=6),
                    ft.Row(buttons, spacing=8),
                ], scroll=ft.ScrollMode.AUTO, spacing=10),
                padding=16, height=(page.height or 800) * 0.92),
            is_scroll_controlled=True, show_drag_handle=True, use_safe_area=True)
        show()
        page.open(sheet)

    # ================= BUDGETS (dropdown) =================
    budget_categories = [c for c in db.CATEGORIES if c != "Salary"]
    budget_cat = dropdown("Category", budget_categories[0], icon_options(budget_categories, CATEGORY_ICONS))
    budget_amount = field(label="Monthly limit", prefix_text=prefix(), text_size=24,
                          keyboard_type=ft.KeyboardType.NUMBER)
    budget_info = ft.Text()
    budget_error = ft.Text(color=ft.Colors.RED)

    def load_budget(e=None):
        limit = db.get_budgets().get(budget_cat.value)
        budget_amount.value = f"{limit / 100:.2f}" if limit else ""
        budget_info.value = f"Current budget: {sv.money(limit)}" if limit else "No budget set for this category."
        budget_error.value = ""
        page.update()

    def save_budget(e):
        try:
            cents = sv.parse_amount(budget_amount.value)
        except ValueError as problem:
            budget_error.value = str(problem)
            page.update()
            return
        db.set_budget(budget_cat.value, cents)
        load_budget()
        refresh()
        toast("Budget saved")

    def remove_budget(e):
        db.set_budget(budget_cat.value, 0)
        load_budget()
        refresh()
        toast("Budget removed")

    budget_cat.on_change = load_budget
    budgets_view = ft.Column(
        [
            card(budget_cat, budget_info, budget_amount, budget_error),
            ft.Row([
                ft.FilledButton("Save", icon=ft.Icons.CHECK, height=50, expand=True, on_click=save_budget),
                ft.OutlinedButton("Remove", icon=ft.Icons.DELETE_OUTLINE, height=50, expand=True,
                                  on_click=remove_budget),
            ]),
        ],
        scroll=ft.ScrollMode.AUTO, spacing=16,
    )

    # ================= SETTINGS (text boxes save by themselves) =================
    def toggle_dark(e):
        page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        db.set_setting("dark_mode", "1" if e.control.value else "0")
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
        budget_amount.prefix_text = prefix()
        refresh()
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
            page.close(dialog)
            refresh_recurring()
            refresh()
            toast("Recurring entry added")

        dialog = ft.AlertDialog(
            title=ft.Text("New recurring entry"),
            content=ft.Column([amt, kind_dd, cat, wal, day, nt, err], tight=True, width=320,
                              scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.close(dialog)),
                     ft.FilledButton("Add", on_click=save_rule)],
        )
        page.open(dialog)

    # ---- export / import (backup, to move your data to a new device) ----
    def backup_text():
        return sv.dump_backup(db.export_data())

    def on_save_result(e: ft.FilePickerResultEvent):
        if not e.path:
            return
        try:
            with open(e.path, "w", encoding="utf-8") as f:
                f.write(backup_text())
            toast("Backup saved")
        except OSError as problem:
            toast(f"Could not save the file: {problem}")

    def on_pick_result(e: ft.FilePickerResultEvent):
        if not e.files:
            return
        if not e.files[0].path:
            toast("Can't read that file here. Use 'Paste text' instead.")
            return
        try:
            with open(e.files[0].path, encoding="utf-8") as f:
                text = f.read()
        except (OSError, UnicodeDecodeError) as problem:
            toast(f"Could not read the file: {problem}")
            return
        start_import(text)

    saver = ft.FilePicker(on_result=on_save_result)
    opener = ft.FilePicker(on_result=on_pick_result)
    page.overlay.extend([saver, opener])

    def apply_settings():
        """Re-reads every setting from the database (used after an import)."""
        sv.CURRENCY = db.get_setting("currency", "RM")
        dark = db.get_setting("dark_mode", "1") == "1"
        page.theme_mode = ft.ThemeMode.DARK if dark else ft.ThemeMode.LIGHT
        dark_switch.value = dark
        apply_theme()
        name = db.get_setting("app_name", "WhereMyMoney")
        page.title = app_title.value = app_name_field.value = name
        currency_field.value = sv.CURRENCY
        budget_amount.prefix_text = prefix()
        refresh_recurring()
        load_budget()
        refresh()

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
        def save_file(ev):
            page.close(dialog)
            saver.save_file(file_name=f"wheremymoney-backup-{sv.today()}.json", allowed_extensions=["json"])

        def copy_text(ev):
            page.close(dialog)
            page.set_clipboard(backup_text())
            toast("Backup copied. Paste it into a note or message to yourself.")

        dialog = ft.AlertDialog(
            title=ft.Text("Export data"),
            content=ft.Text("Creates a backup of everything: transactions, budgets, recurring entries "
                            "and settings. Save it as a file, or copy it as text."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.close(dialog)),
                     ft.OutlinedButton("Copy as text", on_click=copy_text),
                     ft.FilledButton("Save file", on_click=save_file)],
        )
        page.open(dialog)

    def open_paste():
        box = field(label="Paste backup text here", multiline=True, min_lines=4, max_lines=8)

        def go(ev):
            page.close(dialog)
            start_import(box.value)

        dialog = ft.AlertDialog(
            title=ft.Text("Paste backup"), content=ft.Container(box, width=320),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.close(dialog)),
                     ft.FilledButton("Import", on_click=go)],
        )
        page.open(dialog)

    def open_import(e):
        def choose_file(ev):
            page.close(dialog)
            opener.pick_files(dialog_title="Choose backup file", allowed_extensions=["json"])

        def paste_text(ev):
            page.close(dialog)
            open_paste()

        dialog = ft.AlertDialog(
            title=ft.Text("Import data"),
            content=ft.Text("Choose a backup file made with Export data, or paste the backup text. "
                            "Importing replaces all data currently in the app."),
            actions=[ft.TextButton("Cancel", on_click=lambda ev: page.close(dialog)),
                     ft.OutlinedButton("Paste text", on_click=paste_text),
                     ft.FilledButton("Choose file", on_click=choose_file)],
        )
        page.open(dialog)

    dark_switch = ft.Switch(label="Dark mode", value=page.theme_mode == ft.ThemeMode.DARK, on_change=toggle_dark)
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
            page.close(dialog)
            refresh()

        def build():
            year_text.value = str(pick["year"])
            grid.controls = [
                ft.Container(
                    ft.Text(MONTHS[i], color=BLACK if f"{pick['year']}-{i + 1:02d}" == state["month"] else None),
                    width=72, height=44, alignment=ft.alignment.center, border_radius=12,
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
                     ft.TextButton("Close", on_click=lambda e: page.close(dialog))])
        build()
        page.open(dialog)

    def on_swipe(e):  # swipe left = next month, swipe right = previous month
        velocity = e.velocity_x or 0
        if velocity < -300:
            change_month(1)
        elif velocity > 300:
            change_month(-1)

    def month_button(text_control):
        return ft.Container(ft.Row([text_control, ft.Icon(ft.Icons.ARROW_DROP_DOWN)], tight=True, spacing=0),
                            on_click=pick_month)

    # ---- filters ----
    search_box = field(label="Search notes or categories", prefix_icon=ft.Icons.SEARCH, visible=False,
                       on_change=lambda e: refresh())
    f_category = dropdown("Category", ALL, icon_options([ALL] + db.CATEGORIES, CATEGORY_ICONS),
                          on_change=lambda e: refresh())
    f_kind = dropdown("Type", ALL, [ft.dropdown.Option(ALL)] + kind_options(), on_change=lambda e: refresh())
    f_wallet = dropdown("Account", ALL, icon_options([ALL] + db.WALLETS, WALLET_ICONS),
                        on_change=lambda e: refresh())
    f_all_months = ft.Switch(label="All months", value=False, on_change=lambda e: refresh())

    def toggle_search(e):
        search_box.visible = not search_box.visible
        if not search_box.visible:
            search_box.value = ""
        refresh()

    def open_filters(e=None, only_account=False):
        def reset(ev):
            f_category.value = f_kind.value = f_wallet.value = ALL
            f_all_months.value = False
            page.close(dialog)
            refresh()

        controls = [f_wallet] if only_account else [f_category, f_kind, f_wallet, f_all_months]
        dialog = ft.AlertDialog(
            title=ft.Text("Filter"), content=ft.Column(controls, tight=True, width=300),
            actions=[ft.TextButton("Reset", on_click=reset), ft.TextButton("Done", on_click=lambda ev: page.close(dialog))])
        page.open(dialog)

    def wallet_filter():
        return "" if f_wallet.value == ALL else f_wallet.value

    def stat_cell(title, value, arrow=None, color=None):
        head = ([ft.Icon(arrow, color=color, size=16)] if arrow else []) + [ft.Text(title, size=14, color=ft.Colors.OUTLINE)]
        return ft.Column([ft.Row(head, alignment=ft.MainAxisAlignment.CENTER, spacing=2), value],
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2, expand=True)

    def divider():
        return ft.Container(width=1, height=36, bgcolor=ft.Colors.with_opacity(0.3, ft.Colors.OUTLINE))

    def amount_text(size=20):
        return ft.Text(size=size, weight=ft.FontWeight.W_500)

    def yellow_plus(on_click):
        return ft.Container(ft.Icon(ft.Icons.ADD, color=BLACK), width=48, height=48, border_radius=24,
                            bgcolor=YELLOW, alignment=ft.alignment.center, on_click=on_click)

    # ================= HOME =================
    home_month = ft.Text(size=26, weight=ft.FontWeight.W_500)
    h_exp, h_inc, h_bal = amount_text(), amount_text(), amount_text()
    budget_hint = ft.Text(size=15, expand=True)
    home_list = ft.Column(spacing=10)
    home_header = ft.Row(
        [ft.IconButton(ft.Icons.FILTER_LIST, on_click=open_filters), month_button(home_month),
         ft.Row([ft.IconButton(ft.Icons.SEARCH, on_click=toggle_search),
                 ft.IconButton(ft.Icons.CALENDAR_MONTH, on_click=pick_month)], spacing=0)],
        alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
    summary_card = card(
        ft.Row([stat_cell("Expenses", h_exp, ft.Icons.ARROW_UPWARD, ft.Colors.RED), divider(),
                stat_cell("Income", h_inc, ft.Icons.ARROW_DOWNWARD, ft.Colors.GREEN), divider(),
                stat_cell("Balance", h_bal)]),
        ft.Divider(height=1),
        ft.Container(ft.Row([budget_hint, ft.Icon(ft.Icons.CHEVRON_RIGHT)]), padding=ft.padding.symmetric(vertical=6),
                     on_click=lambda e: open_budget_page()))
    home_view = ft.Column([home_header, search_box, summary_card, home_list, ft.Container(height=100)],
                          scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)

    def record_tile(t):
        income = t["type"] == "income"
        return ft.Container(
            ft.Row([
                badge(t["category"]),
                ft.Column([ft.Text(t["category"], size=16),
                           ft.Text(f"{t['wallet']}  {t['note']}".strip(), size=12, color=ft.Colors.OUTLINE)],
                          spacing=0, expand=True),
                ft.Text(f"{'+' if income else '-'}{sv.money(t['amount_cents'])}", size=16,
                        color=ft.Colors.GREEN if income else None)],
                vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=12),
            padding=ft.padding.symmetric(horizontal=12, vertical=10), ink=True,
            on_click=lambda e, t=t: open_entry(t))

    def home_rows():
        month, today = state["month"], sv.today()
        rows = db.list_transactions(
            None if f_all_months.value else month, (search_box.value or "").strip(),
            "" if f_category.value == ALL else f_category.value,
            "" if f_kind.value == ALL else f_kind.value, wallet_filter())
        out = []
        if month == today[:7] and not f_all_months.value and not any(t["date"] == today for t in rows):
            out += [ft.Text(f"Today {day_label(today)}", size=18, weight=ft.FontWeight.BOLD),
                    card(ft.Row([ft.Icon(ft.Icons.EDIT_NOTE, size=44), ft.Text("No record for today", size=17, expand=True),
                                 yellow_plus(lambda e: open_entry())], vertical_alignment=ft.CrossAxisAlignment.CENTER))]
        groups = {}
        for t in rows:
            groups.setdefault(t["date"], []).append(t)
        for day, items in groups.items():
            exp = sum(t["amount_cents"] for t in items if t["type"] == "expense")
            inc = sum(t["amount_cents"] for t in items if t["type"] == "income")
            out.append(ft.Row([ft.Text(day_label(day), size=16, weight=ft.FontWeight.BOLD),
                               ft.Text(f"Expenses: {sv.money(exp)}   Income: {sv.money(inc)}", size=12,
                                       color=ft.Colors.OUTLINE)],
                              alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True))
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
                            bgcolor=YELLOW, border_radius=20, padding=ft.padding.symmetric(horizontal=14, vertical=6),
                            on_click=toggle)

    rep_month = ft.Text(size=26, weight=ft.FontWeight.W_500)
    line_total, line_avg = ft.Text(size=18), ft.Text(size=13, color=ft.Colors.OUTLINE)
    line_chart = ft.LineChart(
        data_series=[], height=220, min_x=1, max_x=31, min_y=0, max_y=100, interactive=False,
        horizontal_grid_lines=ft.ChartGridLines(interval=20, color=ft.Colors.with_opacity(0.35, YELLOW), width=1,
                                                dash_pattern=[4, 4]),
        left_axis=ft.ChartAxis(labels=[], labels_size=44), bottom_axis=ft.ChartAxis(labels=[], labels_size=26))
    pie = ft.PieChart(sections=[], sections_space=1, center_space_radius=0)
    pie_legend, top_list = ft.Column(spacing=8), ft.Column(spacing=10)
    reports_view = ft.Column(
        [ft.Row([ft.Container(width=60), month_button(rep_month),
                 ft.TextButton("Filter", on_click=lambda e: open_filters(only_account=True))],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
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
        [ft.Text("Accounts", size=24, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
         ft.Container(ft.Column([
             ft.Text("Net Assets", size=18), net_text, ft.Container(height=10),
             ft.Row([ft.Column([ft.Text("Assets", size=17), assets_text], expand=True, spacing=2),
                     ft.Column([ft.Text("Debts", size=17), debts_text], expand=True, spacing=2)]),
             ft.Divider(height=24)], spacing=4),
             bgcolor=ft.Colors.SURFACE, border_radius=20, padding=24),
         card(account_rows), ft.Container(height=100)],
        scroll=ft.ScrollMode.AUTO, spacing=14, expand=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)

    # ================= MINE =================
    m_exp, m_inc, m_count = amount_text(), amount_text(), amount_text()

    def edit_name(e):
        box = field(label="Name", value=app_title.value)

        def go(ev):
            app_name_field.value = box.value
            page.close(dialog)
            save_app_name(None)

        dialog = ft.AlertDialog(title=ft.Text("Your name"), content=ft.Container(box, width=300),
                                actions=[ft.TextButton("Cancel", on_click=lambda ev: page.close(dialog)),
                                         ft.FilledButton("Save", on_click=go)])
        page.open(dialog)

    def tile(icon, color, text, on_click):
        return ft.Container(
            ft.Column([ft.Container(ft.Icon(icon, color="#FFFFFF", size=26), width=50, height=50, border_radius=14,
                                    bgcolor=color, alignment=ft.alignment.center),
                       ft.Text(text, size=13, text_align=ft.TextAlign.CENTER)],
                      horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=6),
            width=96, padding=6, on_click=on_click)

    def tile_grid(*tiles):
        return ft.Container(ft.Row(list(tiles), wrap=True, spacing=4, run_spacing=8),
                            bgcolor=ft.Colors.SURFACE, border_radius=20, padding=12)

    mine_view = ft.Column(
        [ft.Text("Mine", size=24, weight=ft.FontWeight.W_500, text_align=ft.TextAlign.CENTER),
         card(ft.Row([ft.CircleAvatar(content=ft.Icon(ft.Icons.PERSON, size=34), radius=32,
                                      bgcolor=ft.Colors.PRIMARY_CONTAINER),
                      app_title, ft.IconButton(ft.Icons.EDIT_OUTLINED, on_click=edit_name)],
                     vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=14)),
         card(ft.Row([stat_cell("Expenses", m_exp, ft.Icons.ARROW_UPWARD, ft.Colors.RED), divider(),
                      stat_cell("Income", m_inc, ft.Icons.ARROW_DOWNWARD, ft.Colors.GREEN), divider(),
                      stat_cell("Records", m_count)])),
         ft.Text("Commonly Used", size=18),
         tile_grid(tile(ft.Icons.BAR_CHART, "#F5A623", "Budget", lambda e: open_budget_page()),
                   tile(ft.Icons.EVENT_REPEAT, "#4A90E2", "Recurring Transactions", lambda e: open_recurring_page())),
         ft.Text("Settings", size=18),
         tile_grid(tile(ft.Icons.PALETTE, "#E86AA6", "Appearance", lambda e: open_subpage("Appearance", card(dark_switch))),
                   tile(ft.Icons.MONETIZATION_ON, "#E8A33D", "Preferences",
                        lambda e: open_subpage("Preferences", card(label("NAME"), app_name_field),
                                               card(label("CURRENCY"), currency_field))),
                   tile(ft.Icons.FOLDER_OPEN, "#5AA9E6", "Export Data", open_export),
                   tile(ft.Icons.DOWNLOAD, "#4FB477", "Import Data", open_import)),
         ft.Container(height=100)],
        scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)

    # ================= SUB-PAGES + NAVIGATION =================
    body = ft.Container(expand=True, padding=16)
    swipe = lambda view: ft.GestureDetector(content=view, on_horizontal_drag_end=on_swipe, expand=True)
    tabs = [swipe(home_view), swipe(reports_view), accounts_view, mine_view]

    def open_subpage(title, *controls):
        body.content = ft.Column(
            [ft.Row([ft.IconButton(ft.Icons.ARROW_BACK, on_click=lambda e: show_tab(state["tab"])),
                     ft.Text(title, size=20, weight=ft.FontWeight.W_500)]), *controls],
            scroll=ft.ScrollMode.AUTO, spacing=12, expand=True)
        page.floating_action_button.visible = False
        page.update()

    def open_budget_page():
        load_budget()
        open_subpage("Budget", *budgets_view.controls)

    def open_recurring_page():
        refresh_recurring()
        open_subpage("Recurring Transactions", card(
            recurring_col, ft.FilledTonalButton("Add recurring entry", icon=ft.Icons.ADD, on_click=open_recurring)))

    nav_row = ft.Row(vertical_alignment=ft.CrossAxisAlignment.CENTER)
    NAV = [("Home", ft.Icons.HOME), ("Reports", ft.Icons.BAR_CHART), ("Accounts", ft.Icons.ACCOUNT_BALANCE_WALLET),
           ("Mine", ft.Icons.PERSON)]

    def build_nav():
        items = []
        for i, (name, icon) in enumerate(NAV):
            color = YELLOW if state["tab"] == i else ft.Colors.OUTLINE
            items.append(ft.Container(
                ft.Column([ft.Icon(icon, color=color, size=26), ft.Text(name, size=11, color=color)],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                expand=True, on_click=lambda e, i=i: show_tab(i)))
        nav_row.controls = items[:2] + [ft.Container(width=76)] + items[2:]

    def show_tab(index):
        state["tab"] = index
        body.content = tabs[index]
        page.floating_action_button.visible = True
        build_nav()
        refresh()

    def refresh():
        month = state["month"]
        home_month.value = rep_month.value = month_title(month)
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
        days = calendar.monthrange(int(month[:4]), int(month[5:7]))[1]
        daily = db.daily_totals(month, r_state["line"], wallet)
        total_line = sum(daily.values())
        line_total.value = f"{pill_texts['line'].value}: {sv.money(total_line)}"
        line_avg.value = f"Average: {sv.money(total_line // days)}"
        step = nice_step(max(list(daily.values()) + [0]) / 100 / 5)
        line_chart.data_series = [ft.LineChartData(
            data_points=[ft.LineChartDataPoint(d, daily.get(d, 0) / 100) for d in range(1, days + 1)],
            color=YELLOW, stroke_width=3, curved=False)]
        line_chart.min_x, line_chart.max_x, line_chart.max_y = 1, days, step * 5
        line_chart.horizontal_grid_lines.interval = step
        line_chart.left_axis.labels = [ft.ChartAxisLabel(value=i * step, label=ft.Text(f"{i * step:g}", size=11,
                                       color=ft.Colors.OUTLINE)) for i in range(6)]
        line_chart.bottom_axis.labels = [ft.ChartAxisLabel(value=d, label=ft.Text(str(d), size=11,
                                         color=ft.Colors.OUTLINE)) for d in range(1, days + 1, 3)]

        rows = db.category_totals(month, r_state["pie"], wallet)
        total = sum(r["total"] for r in rows)
        pie.sections = [ft.PieChartSection(r["total"] / 100, radius=100, color=PIE_COLORS[i % len(PIE_COLORS)],
                                           title=f"{r['total'] * 100 / total:.1f}%",
                                           title_style=ft.TextStyle(size=12, color="#FFFFFF"))
                        for i, r in enumerate(rows)]
        pie_legend.controls = [
            ft.Row([ft.Container(width=10, height=10, border_radius=5, bgcolor=PIE_COLORS[i % len(PIE_COLORS)]),
                    ft.Text(r["category"], expand=True), ft.Text(sv.money(r["total"]))], spacing=8)
            for i, r in enumerate(rows)] or [ft.Text("No data this month.", color=ft.Colors.OUTLINE)]
        top = db.top_transactions(month, r_state["top"], wallet)
        top_list.controls = [
            ft.Row([badge(t["category"], 40),
                    ft.Column([ft.Text(t["category"]), ft.Text(f"{t['date'][5:]}  {t['note']}".strip(), size=12,
                                                              color=ft.Colors.OUTLINE)], spacing=0, expand=True),
                    ft.Text(sv.money(t["amount_cents"]))], spacing=12)
            for t in top] or [ft.Container(ft.Text("Please add a bill", size=17,
                                                   style=ft.TextStyle(decoration=ft.TextDecoration.UNDERLINE)),
                                           alignment=ft.alignment.center, padding=24)]

        balances = db.wallet_balances()
        assets = sum(v for v in balances.values() if v > 0)
        debts = -sum(v for v in balances.values() if v < 0)
        net_text.value, assets_text.value, debts_text.value = sv.money(assets - debts), sv.money(assets), sv.money(debts)
        account_rows.controls = [
            ft.Row([ft.Container(ft.Icon(WALLET_ICONS[name], color=BLACK), width=44, height=44, border_radius=22,
                                 bgcolor=YELLOW, alignment=ft.alignment.center),
                    ft.Text(name, size=17, expand=True), ft.Text(sv.money(bal), size=17)], spacing=14)
            for name, bal in balances.items()]
        page.update()

    page.bottom_appbar = ft.BottomAppBar(content=nav_row, shape=ft.NotchShape.CIRCULAR, notch_margin=6,
                                         bgcolor=ft.Colors.SURFACE, height=72, padding=0)
    page.floating_action_button = ft.FloatingActionButton(
        icon=ft.Icons.ADD, bgcolor=YELLOW, foreground_color=BLACK, shape=ft.CircleBorder(),
        on_click=lambda e: open_entry())
    page.floating_action_button_location = ft.FloatingActionButtonLocation.CENTER_DOCKED
    page.add(ft.SafeArea(body, expand=True))
    refresh_recurring()
    show_tab(0)


ft.app(target=main)