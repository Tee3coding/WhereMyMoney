"""WhereMyMoney: the Flet user interface. Run with: flet run src/main.py"""
from datetime import datetime

import flet as ft

import database as db
import services as sv

ACCENTS = {
    "Teal": "#00897B", "Blue": "#1E88E5", "Purple": "#8E24AA",
    "Orange": "#FB8C00", "Pink": "#D81B60", "Green": "#43A047",
}
CATEGORY_ICONS = {
    "Food": ft.Icons.RESTAURANT, "Transport": ft.Icons.DIRECTIONS_BUS,
    "Bills": ft.Icons.RECEIPT_LONG, "Shopping": ft.Icons.SHOPPING_BAG,
    "Health": ft.Icons.FAVORITE, "Entertainment": ft.Icons.MOVIE,
    "Salary": ft.Icons.PAYMENTS, "Other": ft.Icons.MORE_HORIZ,
}
PIE_COLORS = [ft.Colors.BLUE, ft.Colors.ORANGE, ft.Colors.GREEN, ft.Colors.PURPLE,
              ft.Colors.TEAL, ft.Colors.PINK, ft.Colors.AMBER, ft.Colors.CYAN]
ALL = "All"


# ---------- small design helpers ----------
def heading(text):
    return ft.Text(text, size=24, weight=ft.FontWeight.BOLD)


def label(text):
    return ft.Text(text, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.PRIMARY)


def card(*controls):
    return ft.Card(content=ft.Container(ft.Column(list(controls), spacing=12), padding=16))


def field(**kwargs):
    return ft.TextField(filled=True, border_radius=12, border_width=0, **kwargs)


def dropdown(label_text, value, options, **kwargs):
    return ft.Dropdown(label=label_text, value=value, filled=True, border_radius=12, border_width=0,
                       options=[ft.dropdown.Option(o) for o in options], **kwargs)


def main(page: ft.Page):
    db.init_db()
    sv.CURRENCY = db.get_setting("currency", "RM")
    db.apply_recurring(sv.today())
    accent = {"value": db.get_setting("accent", ACCENTS["Teal"])}
    state = {"month": sv.today()[:7], "kind": "expense"}

    def apply_theme():
        page.theme = ft.Theme(color_scheme_seed=accent["value"])
        page.dark_theme = ft.Theme(color_scheme_seed=accent["value"])

    page.title = db.get_setting("app_name", "WhereMyMoney")
    page.padding = 0
    page.theme_mode = ft.ThemeMode.DARK if db.get_setting("dark_mode", "0") == "1" else ft.ThemeMode.LIGHT
    apply_theme()

    app_title = ft.Text(page.title, size=20, weight=ft.FontWeight.BOLD)
    page.appbar = ft.AppBar(title=app_title, center_title=False, bgcolor=ft.Colors.PRIMARY_CONTAINER)

    def toast(message):
        page.open(ft.SnackBar(ft.Text(message)))

    def confirm(title, text, on_yes):
        def yes(e):
            page.close(dialog)
            on_yes()

        dialog = ft.AlertDialog(
            title=ft.Text(title), content=ft.Text(text),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
                     ft.TextButton("Delete", on_click=yes)],
        )
        page.open(dialog)

    def prefix():
        return f"{sv.CURRENCY} "

    # ================= ADD =================
    def on_kind(e):
        state["kind"] = next(iter(e.control.selected))

    kind = ft.SegmentedButton(
        selected={"expense"}, allow_multiple_selection=False, show_selected_icon=False, on_change=on_kind,
        segments=[
            ft.Segment(value="expense", label=ft.Text("Expense"), icon=ft.Icon(ft.Icons.ARROW_DOWNWARD)),
            ft.Segment(value="income", label=ft.Text("Income"), icon=ft.Icon(ft.Icons.ARROW_UPWARD)),
        ],
    )
    amount = field(label="Amount", prefix_text=prefix(), text_size=28, keyboard_type=ft.KeyboardType.NUMBER)
    category = dropdown("Category", db.CATEGORIES[0], db.CATEGORIES)
    wallet_dd = dropdown("Wallet", db.list_wallets()[0], db.list_wallets())
    date_field = field(label="Date", value=sv.today(), read_only=True, suffix_icon=ft.Icons.CALENDAR_MONTH)
    note = field(label="Note (optional)")
    error = ft.Text(color=ft.Colors.RED)

    def pick_date(e):
        def chosen(ev):
            date_field.value = ev.control.value.strftime("%Y-%m-%d")
            page.update()

        page.open(ft.DatePicker(
            first_date=datetime(2020, 1, 1), last_date=datetime(2100, 12, 31),
            value=datetime.strptime(date_field.value, "%Y-%m-%d"), on_change=chosen,
        ))

    date_field.on_click = pick_date

    def save(e):
        try:
            cents = sv.parse_amount(amount.value)
            day = sv.parse_date(date_field.value)
        except ValueError as problem:
            error.value = str(problem)
            page.update()
            return
        db.add_transaction(cents, state["kind"], category.value, wallet_dd.value, day,
                           (note.value or "").strip())
        amount.value = ""
        note.value = ""
        error.value = ""
        refresh()
        toast("Saved")
        amount.focus()

    add_view = ft.Column(
        [
            heading("Add transaction"),
            ft.Row([kind], alignment=ft.MainAxisAlignment.CENTER),
            card(amount, category, wallet_dd, date_field, note, error),
            ft.Row([ft.FilledButton("Save transaction", icon=ft.Icons.CHECK, height=50, expand=True,
                                    on_click=save)]),
        ],
        scroll=ft.ScrollMode.AUTO, spacing=16,
    )

    # ================= EDIT DIALOG =================
    def open_edit(t):
        amt = field(label="Amount", value=f"{t['amount_cents'] / 100:.2f}", prefix_text=prefix(),
                    keyboard_type=ft.KeyboardType.NUMBER)
        kind_dd = ft.Dropdown(label="Type", value=t["type"], filled=True, border_radius=12, border_width=0,
                              options=[ft.dropdown.Option(key="expense", text="Expense"),
                                       ft.dropdown.Option(key="income", text="Income")])
        cat = dropdown("Category", t["category"], db.CATEGORIES)
        wal = dropdown("Wallet", t["wallet"], db.list_wallets())
        day = field(label="Date (YYYY-MM-DD)", value=t["date"])
        nt = field(label="Note", value=t["note"])
        err = ft.Text(color=ft.Colors.RED)

        def save_edit(e):
            try:
                cents = sv.parse_amount(amt.value)
                date_ = sv.parse_date(day.value)
            except ValueError as problem:
                err.value = str(problem)
                page.update()
                return
            db.update_transaction(t["id"], cents, kind_dd.value, cat.value, wal.value, date_,
                                  (nt.value or "").strip())
            page.close(dialog)
            refresh()
            toast("Updated")

        dialog = ft.AlertDialog(
            title=ft.Text("Edit transaction"),
            content=ft.Column([amt, kind_dd, cat, wal, day, nt, err], tight=True, width=320,
                              scroll=ft.ScrollMode.AUTO),
            actions=[ft.TextButton("Cancel", on_click=lambda e: page.close(dialog)),
                     ft.FilledButton("Save", on_click=save_edit)],
        )
        page.open(dialog)

    # ================= HISTORY (search + filters) =================
    month_labels = []

    def change_month(delta):
        state["month"] = sv.shift_month(state["month"], delta)
        refresh()

    def month_bar():
        month_label = ft.Text(size=18, weight=ft.FontWeight.BOLD)
        month_labels.append(month_label)
        row = ft.Row(
            [ft.IconButton(ft.Icons.CHEVRON_LEFT, on_click=lambda e: change_month(-1)),
             month_label,
             ft.IconButton(ft.Icons.CHEVRON_RIGHT, on_click=lambda e: change_month(1))],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        return row, month_label

    def delete(transaction_id):
        confirm("Delete transaction?", "This can't be undone.", lambda: (
            db.delete_transaction(transaction_id), refresh(), toast("Deleted")))

    f_search = field(label="Search notes or categories", prefix_icon=ft.Icons.SEARCH, on_change=lambda e: refresh())
    f_category = dropdown("Category", ALL, [ALL] + db.CATEGORIES, width=150, on_change=lambda e: refresh())
    f_kind = ft.Dropdown(label="Type", value=ALL, filled=True, border_radius=12, border_width=0, width=130,
                         on_change=lambda e: refresh(),
                         options=[ft.dropdown.Option(ALL), ft.dropdown.Option(key="expense", text="Expense"),
                                  ft.dropdown.Option(key="income", text="Income")])
    f_wallet = dropdown("Wallet", ALL, [ALL] + db.list_wallets(), width=140, on_change=lambda e: refresh())
    f_all_months = ft.Switch(label="All months", value=False, on_change=lambda e: refresh())
    history_list = ft.ListView(expand=True, spacing=4)
    history_bar, history_month_label = month_bar()
    history_view = ft.Column(
        [heading("History"), f_search,
         ft.Row([f_category, f_kind, f_wallet], wrap=True, spacing=8),
         ft.Row([history_bar, f_all_months], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
         history_list],
        expand=True,
    )

    def history_rows():
        rows = db.list_transactions(
            None if f_all_months.value else state["month"],
            (f_search.value or "").strip(),
            "" if f_category.value == ALL else f_category.value,
            "" if f_kind.value == ALL else f_kind.value,
            "" if f_wallet.value == ALL else f_wallet.value,
        )
        return [
            ft.Card(content=ft.ListTile(
                on_click=lambda e, t=t: open_edit(t),
                leading=ft.CircleAvatar(content=ft.Icon(CATEGORY_ICONS.get(t["category"], ft.Icons.MORE_HORIZ)),
                                        bgcolor=ft.Colors.PRIMARY_CONTAINER),
                title=ft.Text(t["category"], weight=ft.FontWeight.BOLD),
                subtitle=ft.Text(f"{t['date']}  {t['wallet']}  {t['note']}".strip()),
                trailing=ft.Row([
                    ft.Text(f"{'+' if t['type'] == 'income' else '-'}{sv.money(t['amount_cents'])}",
                            weight=ft.FontWeight.BOLD,
                            color=ft.Colors.GREEN_700 if t["type"] == "income" else ft.Colors.RED_700),
                    ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, i=t["id"]: delete(i)),
                ], tight=True, spacing=0),
            ))
            for t in rows
        ] or [ft.Text("No matching transactions.")]

    # ================= SUMMARY =================
    balance_text = ft.Text(size=34, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_PRIMARY_CONTAINER)
    income_text = ft.Text(color=ft.Colors.GREEN_700, weight=ft.FontWeight.BOLD)
    expense_text = ft.Text(color=ft.Colors.RED_700, weight=ft.FontWeight.BOLD)
    budget_list = ft.Column(spacing=6)
    wallet_list = ft.Column(spacing=4)
    category_list = ft.Column(spacing=4)
    pie = ft.PieChart(sections=[], sections_space=2, center_space_radius=30)
    summary_bar, _ = month_bar()

    balance_card = ft.Container(
        ft.Column([
            ft.Text("Balance this month", color=ft.Colors.ON_PRIMARY_CONTAINER),
            balance_text,
            ft.Row([ft.Icon(ft.Icons.ARROW_UPWARD, color=ft.Colors.GREEN_700, size=18), income_text,
                    ft.Icon(ft.Icons.ARROW_DOWNWARD, color=ft.Colors.RED_700, size=18), expense_text],
                   spacing=6, wrap=True),
        ], spacing=6),
        bgcolor=ft.Colors.PRIMARY_CONTAINER, border_radius=16, padding=20,
    )
    summary_view = ft.Column(
        [
            heading("Summary"), summary_bar, balance_card,
            card(label("WALLETS (ALL TIME)"), wallet_list),
            card(label("BUDGETS"), budget_list),
            card(label("SPENDING BY CATEGORY"), ft.Container(content=pie, height=240), category_list),
        ],
        scroll=ft.ScrollMode.AUTO, spacing=12,
    )

    def refresh():
        month = state["month"]
        for month_label in month_labels:
            month_label.value = month
        history_month_label.value = "All months" if f_all_months.value else month
        history_list.controls = history_rows()

        income, expense = db.month_totals(month)
        balance_text.value = sv.money(income - expense)
        income_text.value = sv.money(income)
        expense_text.value = sv.money(expense)

        wallet_list.controls = [ft.Text(f"{name}: {sv.money(bal)}") for name, bal in db.wallet_balances().items()]

        by_category = db.expense_by_category(month)
        category_list.controls = [
            ft.Text(f"{r['category']}: {sv.money(r['total'])}") for r in by_category
        ] or [ft.Text("No expenses this month.")]
        pie.sections = [
            ft.PieChartSection(
                r["total"] / 100, title=r["category"], radius=80, color=PIE_COLORS[i % len(PIE_COLORS)],
                title_style=ft.TextStyle(size=11, color=ft.Colors.WHITE),
            )
            for i, r in enumerate(by_category)
        ]

        spent = {r["category"]: r["total"] for r in by_category}
        budget_list.controls = []
        for cat, limit in db.get_budgets().items():
            used = spent.get(cat, 0)
            left = limit - used
            color = ft.Colors.RED if left < 0 else ft.Colors.ORANGE if used >= 0.8 * limit else ft.Colors.GREEN
            status = f"{sv.money(left)} left" if left >= 0 else f"over by {sv.money(-left)}"
            budget_list.controls += [
                ft.Text(f"{cat}: {sv.money(used)} of {sv.money(limit)} ({status})"),
                ft.ProgressBar(value=min(used / limit, 1), color=color),
            ]
        if not budget_list.controls:
            budget_list.controls = [ft.Text("No budgets set. Add some in the Budgets tab.")]
        page.update()

    # ================= BUDGETS (dropdown) =================
    budget_categories = [c for c in db.CATEGORIES if c != "Salary"]
    budget_cat = dropdown("Category", budget_categories[0], budget_categories)
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
            heading("Monthly budgets"),
            card(budget_cat, budget_info, budget_amount, budget_error),
            ft.Row([
                ft.FilledButton("Save", icon=ft.Icons.CHECK, height=50, expand=True, on_click=save_budget),
                ft.OutlinedButton("Remove", icon=ft.Icons.DELETE_OUTLINE, height=50, expand=True,
                                  on_click=remove_budget),
            ]),
        ],
        scroll=ft.ScrollMode.AUTO, spacing=16,
    )

    # ================= SETTINGS =================
    def toggle_dark(e):
        page.theme_mode = ft.ThemeMode.DARK if e.control.value else ft.ThemeMode.LIGHT
        db.set_setting("dark_mode", "1" if e.control.value else "0")
        page.update()

    swatches = ft.Row(wrap=True, spacing=10)

    def build_swatches():
        swatches.controls = [
            ft.Container(
                width=40, height=40, border_radius=20, bgcolor=hex_color, tooltip=name,
                border=ft.border.all(3, ft.Colors.ON_SURFACE) if hex_color == accent["value"] else None,
                on_click=lambda e, c=hex_color: pick_accent(c),
            )
            for name, hex_color in ACCENTS.items()
        ]

    def pick_accent(hex_color):
        accent["value"] = hex_color
        db.set_setting("accent", hex_color)
        apply_theme()
        build_swatches()
        page.update()

    app_name_field = field(label="App name (shown at the top)", value=page.title)

    def save_app_name(e):
        name = (app_name_field.value or "").strip() or "WhereMyMoney"
        db.set_setting("app_name", name)
        app_title.value = name
        page.title = name
        page.update()
        toast("Name saved")

    currency_field = field(label="Currency symbol (e.g. RM, $, S$)", value=sv.CURRENCY)

    def save_currency(e):
        sv.CURRENCY = (currency_field.value or "").strip() or "RM"
        db.set_setting("currency", sv.CURRENCY)
        for f in (amount, budget_amount):
            f.prefix_text = prefix()
        refresh()
        toast("Currency saved")

    # ---- wallets ----
    wallet_col = ft.Column(spacing=0)
    new_wallet = field(label="New wallet name (e.g. Bank, E-wallet)")

    def refresh_wallet_controls():
        names = db.list_wallets()
        wallet_dd.options = [ft.dropdown.Option(n) for n in names]
        if wallet_dd.value not in names:
            wallet_dd.value = names[0]
        f_wallet.options = [ft.dropdown.Option(n) for n in [ALL] + names]
        if f_wallet.value not in [ALL] + names:
            f_wallet.value = ALL
        wallet_col.controls = [
            ft.ListTile(title=ft.Text(n), dense=True, leading=ft.Icon(ft.Icons.ACCOUNT_BALANCE_WALLET_OUTLINED),
                        trailing=ft.IconButton(ft.Icons.DELETE_OUTLINE, on_click=lambda e, n=n: remove_wallet(n)))
            for n in names
        ]

    def add_wallet(e):
        try:
            db.add_wallet(new_wallet.value)
        except ValueError as problem:
            toast(str(problem))
            return
        new_wallet.value = ""
        refresh_wallet_controls()
        refresh()

    def remove_wallet(name):
        try:
            db.delete_wallet(name)
        except ValueError as problem:
            toast(str(problem))
            return
        refresh_wallet_controls()
        refresh()

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
        kind_dd = ft.Dropdown(label="Type", value="expense", filled=True, border_radius=12, border_width=0,
                              options=[ft.dropdown.Option(key="expense", text="Expense"),
                                       ft.dropdown.Option(key="income", text="Income")])
        cat = dropdown("Category", db.CATEGORIES[0], db.CATEGORIES)
        wal = dropdown("Wallet", db.list_wallets()[0], db.list_wallets())
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

    # ---- export ----
    def on_export_result(e: ft.FilePickerResultEvent):
        if not e.path:
            return
        try:
            with open(e.path, "w", encoding="utf-8", newline="") as f:
                f.write(sv.build_csv(db.all_transactions()))
            toast("Exported")
        except OSError as problem:
            toast(f"Could not save the file: {problem}")

    exporter = ft.FilePicker(on_result=on_export_result)
    page.overlay.append(exporter)

    def export_file(e):
        exporter.save_file(file_name="wheremymoney.csv", allowed_extensions=["csv"])

    def copy_csv(e):
        page.set_clipboard(sv.build_csv(db.all_transactions()))
        toast("CSV copied to clipboard")

    build_swatches()
    refresh_wallet_controls()
    refresh_recurring()
    settings_view = ft.Column(
        [
            heading("Settings"),
            card(label("APPEARANCE"),
                 ft.Switch(label="Dark mode", value=page.theme_mode == ft.ThemeMode.DARK, on_change=toggle_dark),
                 ft.Text("Accent colour"), swatches),
            card(label("APP NAME"), app_name_field,
                 ft.FilledTonalButton("Save name", icon=ft.Icons.CHECK, on_click=save_app_name),
                 ft.Text("The name and icon under the app on your phone's home screen are set when the "
                         "APK is built. See README.md.", size=12)),
            card(label("CURRENCY"), currency_field,
                 ft.FilledTonalButton("Save currency", icon=ft.Icons.CHECK, on_click=save_currency)),
            card(label("WALLETS"), wallet_col, new_wallet,
                 ft.FilledTonalButton("Add wallet", icon=ft.Icons.ADD, on_click=add_wallet)),
            card(label("RECURRING (RENT, SUBSCRIPTIONS, SALARY)"), recurring_col,
                 ft.FilledTonalButton("Add recurring entry", icon=ft.Icons.ADD, on_click=open_recurring)),
            card(label("DATA"),
                 ft.FilledTonalButton("Export all to CSV file", icon=ft.Icons.FILE_DOWNLOAD, on_click=export_file),
                 ft.OutlinedButton("Copy CSV to clipboard", icon=ft.Icons.CONTENT_COPY, on_click=copy_csv)),
            card(label("QUICK ADD (COMING LATER)"),
                 ft.Switch(label="Notification shortcut", value=False, disabled=True),
                 ft.Switch(label="Floating bubble", value=False, disabled=True),
                 ft.Text("These need native Android code and will be added in a later stage.", size=12)),
            ft.Text("WhereMyMoney v0.3", size=12, text_align=ft.TextAlign.CENTER),
        ],
        scroll=ft.ScrollMode.AUTO, spacing=12,
    )

    # ================= NAVIGATION =================
    views = [add_view, history_view, summary_view, budgets_view, settings_view]
    body = ft.Container(content=add_view, expand=True, padding=16)

    def on_nav(e):
        index = e.control.selected_index
        body.content = views[index]
        db.apply_recurring(sv.today())
        if index == 3:
            load_budget()
        refresh()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0, on_change=on_nav,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.ADD_CIRCLE_OUTLINE, label="Add"),
            ft.NavigationBarDestination(icon=ft.Icons.LIST_ALT, label="History"),
            ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART_OUTLINE, label="Summary"),
            ft.NavigationBarDestination(icon=ft.Icons.SAVINGS_OUTLINED, label="Budgets"),
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS_OUTLINED, label="Settings"),
        ],
    )
    page.add(ft.SafeArea(body, expand=True))
    refresh()


ft.app(target=main)