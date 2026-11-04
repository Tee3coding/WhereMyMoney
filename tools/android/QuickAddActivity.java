package com.wheremymoney.quickadd;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.os.Bundle;
import android.text.InputType;
import android.util.TypedValue;
import android.view.Gravity;
import android.view.ViewGroup;
import android.widget.EditText;
import android.widget.HorizontalScrollView;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.io.FileOutputStream;
import java.math.BigDecimal;
import java.math.RoundingMode;
import java.nio.charset.StandardCharsets;
import java.text.SimpleDateFormat;
import java.util.ArrayList;
import java.util.Date;
import java.util.List;
import java.util.Locale;

/**
 * Small pop-up form shown over whatever app is open. It never starts the main app:
 * the record is appended to quick_inbox.jsonl and the Python app imports it the next time it runs.
 */
public class QuickAddActivity extends Activity {
    private static final int YELLOW = 0xFFFFD93B;
    private static final int GREY = 0xFFE8E8ED;

    private final List<String> categories = new ArrayList<>();
    private final List<TextView> categoryPills = new ArrayList<>();
    private String kind = "expense";
    private String category;
    private String wallet = "Wallet";
    private String currency = "RM";
    private File inbox;

    private TextView expensePill;
    private TextView incomePill;
    private TextView bankPill;
    private TextView walletPill;
    private EditText amount;
    private EditText memo;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setFinishOnTouchOutside(true);
        JSONObject config = QuickAddHelper.readConfig(this);
        File configFile = QuickAddHelper.findConfig(this);
        if (config == null || configFile == null) {
            Toast.makeText(this, "Open WhereMyMoney once first, then try again.", Toast.LENGTH_LONG).show();
            finish();
            return;
        }
        inbox = new File(configFile.getParentFile(), QuickAddHelper.INBOX_NAME);
        currency = config.optString("currency", "RM");
        JSONArray names = config.optJSONArray("categories");
        if (names != null) {
            for (int i = 0; i < names.length(); i++) {
                categories.add(names.optString(i));
            }
        }
        if (categories.isEmpty()) {
            categories.add("Other");
        }
        SharedPreferences prefs = getSharedPreferences("quickadd", MODE_PRIVATE);
        String savedCategory = prefs.getString("category", null);
        category = savedCategory != null && categories.contains(savedCategory) ? savedCategory : categories.get(0);
        wallet = prefs.getString("wallet", "Wallet");
        readKind(getIntent());
        buildUi();
        refreshStyles();
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        setIntent(intent);
        readKind(intent);
        if (expensePill != null) {
            refreshStyles();
        }
    }

    private void readKind(Intent intent) {
        kind = "income".equals(intent.getStringExtra("kind")) ? "income" : "expense";
    }

    private int dp(int value) {
        return (int) (value * getResources().getDisplayMetrics().density + 0.5f);
    }

    private TextView pill(String text, final Runnable onClick) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(TypedValue.COMPLEX_UNIT_SP, 15);
        view.setTextColor(Color.BLACK);
        view.setGravity(Gravity.CENTER);
        view.setPadding(dp(14), dp(9), dp(14), dp(9));
        view.setOnClickListener(v -> onClick.run());
        return view;
    }

    private void style(TextView view, boolean selected) {
        GradientDrawable shape = new GradientDrawable();
        shape.setCornerRadius(dp(20));
        shape.setColor(selected ? YELLOW : GREY);
        view.setBackground(shape);
        view.setTypeface(null, selected ? Typeface.BOLD : Typeface.NORMAL);
    }

    private LinearLayout.LayoutParams weight() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(0, ViewGroup.LayoutParams.WRAP_CONTENT, 1f);
        params.setMargins(dp(3), 0, dp(3), 0);
        return params;
    }

    private void buildUi() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(20), dp(18), dp(20), dp(14));

        TextView title = new TextView(this);
        title.setText("Add record");
        title.setTextSize(TypedValue.COMPLEX_UNIT_SP, 20);
        title.setTypeface(null, Typeface.BOLD);
        root.addView(title);

        LinearLayout kindRow = new LinearLayout(this);
        kindRow.setPadding(0, dp(12), 0, dp(4));
        expensePill = pill("Expense", () -> { kind = "expense"; refreshStyles(); });
        incomePill = pill("Income", () -> { kind = "income"; refreshStyles(); });
        kindRow.addView(expensePill, weight());
        kindRow.addView(incomePill, weight());
        root.addView(kindRow);

        amount = new EditText(this);
        amount.setInputType(InputType.TYPE_CLASS_NUMBER | InputType.TYPE_NUMBER_FLAG_DECIMAL);
        amount.setHint(currency + " 0.00");
        amount.setTextSize(TypedValue.COMPLEX_UNIT_SP, 28);
        amount.setSingleLine(true);
        root.addView(amount);

        HorizontalScrollView scroll = new HorizontalScrollView(this);
        scroll.setHorizontalScrollBarEnabled(false);
        LinearLayout chips = new LinearLayout(this);
        chips.setPadding(0, dp(8), 0, dp(8));
        for (final String name : categories) {
            TextView chip = pill(name, () -> { category = name; refreshStyles(); });
            categoryPills.add(chip);
            LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                    ViewGroup.LayoutParams.WRAP_CONTENT, ViewGroup.LayoutParams.WRAP_CONTENT);
            params.setMargins(dp(3), 0, dp(3), 0);
            chips.addView(chip, params);
        }
        scroll.addView(chips);
        root.addView(scroll);

        LinearLayout walletRow = new LinearLayout(this);
        bankPill = pill("Bank", () -> { wallet = "Bank"; refreshStyles(); });
        walletPill = pill("Wallet", () -> { wallet = "Wallet"; refreshStyles(); });
        walletRow.addView(bankPill, weight());
        walletRow.addView(walletPill, weight());
        root.addView(walletRow);

        memo = new EditText(this);
        memo.setHint("Memo (optional)");
        memo.setSingleLine(true);
        root.addView(memo);

        LinearLayout buttons = new LinearLayout(this);
        buttons.setPadding(0, dp(12), 0, 0);
        TextView cancel = pill("Cancel", this::finish);
        style(cancel, false);
        TextView save = pill("Save", this::save);
        style(save, true);
        buttons.addView(cancel, weight());
        buttons.addView(save, weight());
        root.addView(buttons);

        setContentView(root);
        amount.requestFocus();
    }

    private void refreshStyles() {
        style(expensePill, kind.equals("expense"));
        style(incomePill, kind.equals("income"));
        style(bankPill, wallet.equals("Bank"));
        style(walletPill, !wallet.equals("Bank"));
        for (int i = 0; i < categoryPills.size(); i++) {
            style(categoryPills.get(i), categories.get(i).equals(category));
        }
    }

    private void save() {
        long cents;
        try {
            BigDecimal value = new BigDecimal(amount.getText().toString().trim().replace(",", "."));
            if (value.signum() <= 0) {
                throw new NumberFormatException();
            }
            cents = value.multiply(BigDecimal.valueOf(100)).setScale(0, RoundingMode.HALF_UP).longValueExact();
        } catch (Exception e) {
            amount.setError("Enter an amount above 0");
            return;
        }
        try {
            JSONObject row = new JSONObject();
            row.put("amount_cents", cents);
            row.put("type", kind);
            row.put("category", category);
            row.put("wallet", wallet);
            row.put("date", new SimpleDateFormat("yyyy-MM-dd", Locale.US).format(new Date()));
            row.put("note", memo.getText().toString().trim());
            try (FileOutputStream out = new FileOutputStream(inbox, true)) {
                out.write((row.toString() + "\n").getBytes(StandardCharsets.UTF_8));
            }
        } catch (Exception e) {
            Toast.makeText(this, "Could not save: " + e.getMessage(), Toast.LENGTH_LONG).show();
            return;
        }
        getSharedPreferences("quickadd", MODE_PRIVATE).edit()
                .putString("category", category).putString("wallet", wallet).apply();
        String sign = kind.equals("income") ? "+" : "-";
        Toast.makeText(this, "Saved " + sign + currency + " " + new BigDecimal(cents).movePointLeft(2).toPlainString()
                + " \u00b7 " + category, Toast.LENGTH_SHORT).show();
        finish();
    }
}