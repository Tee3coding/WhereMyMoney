# WhereMyMoney

Personal income and expense tracker for Android, written in Python with [Flet](https://flet.dev).
Records, budgets, reports, calendar, search, PIN lock, and a quick-add notification. All data stays on your phone.

## Run on your computer
```
python -m venv .venv
.venv\Scripts\activate        # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
flet run src/main.py
```

## Build the Android APK
Needs Python 3.11+, Android Studio (for the Android SDK) and JDK 17. Use a fresh virtual environment.

1. Export your data first if the app is already installed (Mine > Export Data).
2. `python tools/build_apk.py` (add `--skip-flet` to reuse the last generated project, `--dry-run` to only print the steps).
3. Install the APK it prints at the end. `-r` keeps your data:
   ```
   adb install -r "build/flutter/build/app/outputs/flutter-apk/app-release.apk"
   ```
   If `adb` is not found, it is in `%LOCALAPPDATA%\Android\Sdk\platform-tools`. Or copy the APK to your phone and open it.

If the build misbehaves, delete the `build` folder and run it again.

The script runs `flet build apk`, then `tools/patch_android.py` (adds the native quick-add code), then `flutter build apk`.
It uses the Flutter that Flet downloads to `~/flutter/<version>`.

## Name and icon
- Home screen name: `product` under `[tool.flet]` in `pyproject.toml`.
- Icon: `src/assets/icon.png` (square PNG, 1024x1024 recommended).

The name shown inside the app can be changed any time in Mine.

## Quick-add notification
Turn it on in Mine > Preferences > Quick add. It shows a notification with Expense, Income and Open app buttons;
Expense and Income open a small form over whatever app you are using. Records typed there are saved to a file and
imported the next time you open WhereMyMoney. The form never touches the database. Android only, and it needs the
patch step in the build above.

## Move to a new phone
Mine > Export Data, send the file to the new phone, then Mine > Import Data. Importing replaces everything in the app.

## Project layout
```
src/main.py        UI (Flet)
src/database.py    SQLite storage
src/services.py    Parsing, formatting, PIN hashing, backup JSON
src/assets/        App icon
tools/             APK build script, Android patch and native quick-add Java code
```
