# WhereMyMoney

Personal income and expense tracker (Python + Flet, Android).

## Run
```
python -m venv .venv
.venv\Scripts\activate        # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
flet run src/main.py
```
Phone testing: install the Flet app, same Wi-Fi, then `flet run --android src/main.py`.

## Choosing the name and icon shown on your phone
These are fixed when the APK is built:
- **Name:** change `product` under `[tool.flet]` in `pyproject.toml`.
- **Icon:** put a square PNG (1024x1024 recommended) at `src/assets/icon.png`.
Then run `flet build apk` (check flet.dev/docs for current build steps).

The in-app name (top bar) can be changed any time in Settings.

## Moving to a new phone
Settings > Data > **Export data** (save the file or copy the text), send it to the new phone, then
Settings > Data > **Import data** there. Importing replaces everything in the app with the backup.

## Build the Android APK
Needs Python 3.10 or newer, Android Studio (for the Android SDK) and JDK 17.
Use a **fresh virtual environment**, then `pip install -r requirements.txt`.

1. **Export your data first** (Mine > Export Data) if the app is already installed, and keep a copy of your
   current working APK in case you want to go back.
2. If you built before, delete the old `build` folder (it can hold outdated packages).
3. From the project folder: `python tools/build_apk.py`
4. Install the APK it prints at the end (keeps your data): `adb install -r "<path it shows>"`

`tools/build_apk.py` does three things in order: `flet build apk`, `tools/patch_android.py` (adds the native
quick-add code to the generated Android project), and `flutter build apk` with the settings Flet normally passes
(`SERIOUS_PYTHON_VERSION`, `SERIOUS_PYTHON_SITE_PACKAGES`, `SERIOUS_PYTHON_APP`). Running Flutter by hand without
those fails with "SERIOUS_PYTHON_SITE_PACKAGES environment variable is not set".

- It uses the Flutter that Flet downloads (`~/flutter/3.44.8`). A different Flutter on your PATH is not used.
- `--skip-flet` reuses the project from the last run (after the first run).
- `--dry-run` only prints the commands.
- Icon: `src/assets/icon.png`. Home screen name: `product` in `pyproject.toml`.

## How the quick-add notification works
- Turn it on in Mine > Preferences > Quick add. The app writes `quick_config.json` (categories, currency, on/off).
- The Android side (`tools/android/*.java`, added by `patch_android.py`) shows a quiet notification with
  Expense, Income and Open app buttons. Expense and Income open a small form over whatever app is open.
- The form appends the record to `quick_inbox.jsonl`; the app imports it when it is opened or comes back to the front.
- The form never opens the database itself, so it cannot damage your data.

## Moving to a new phone
Settings > Data > **Export data** (save the file or copy the text), send it to the new phone, then
Settings > Data > **Import data** there. Importing replaces everything in the app with the backup.

## Build the Android APK (3 extra steps because of the notification package)
Needs Python 3.11 or newer (3.12 or 3.13 recommended), Android Studio (for the Android SDK) and JDK 17.
Use a **fresh virtual environment**, then `pip install -r requirements.txt`.

1. **Export your data first** (Mine > Export Data) if the app is already installed.
2. In the project folder (environment active; on Windows run `set PYTHONIOENCODING=utf-8` first):
   `flet build apk -v --bundle-id com.wheremymoney`
   This is expected to **fail with a "desugaring" error**. Only that failure is OK. Any other error must be fixed first.
3. Patch the generated Android project: `flet-android-notifications-patch --project-root build/flutter`
4. Rebuild it with Flutter: `cd build/flutter`, then `flutter build apk --release`.
   Flutter was downloaded by Flet (look in `C:\Users\<you>\flutter\<version>\bin`); add that folder to `PATH` if `flutter` is not found.
5. Install over the old app: `adb install -r build\app\outputs\flutter-apk\app-release.apk`
   (`-r` keeps your data). Or copy the APK to your phone and open it.

Repeat steps 2 to 5 every time you build (the patch is lost when the project is regenerated).
Icon: `src/assets/icon.png`. Home screen name: `product` in `pyproject.toml`.

## Moving to a new phone
Settings > Data > **Export data** (save the file or copy the text), send it to the new phone, then
Settings > Data > **Import data** there. Importing replaces everything in the app with the backup.

## Build the Android APK
1. Install Android Studio (gives you the Android SDK) and a JDK 17.
2. In the project folder (virtual environment active): `flet build apk --bundle-id com.wheremymoney`
   (the app ID is also set in `pyproject.toml`; the flag makes sure it is exactly `com.wheremymoney`)
3. The APK appears in `build/apk/`. Copy it to your phone and open it
   (allow "install unknown apps" for your file manager or browser when asked).
4. Your icon is `src/assets/icon.png` (replace with your own square PNG, 1024x1024).
   Your home screen name is `product` in `pyproject.toml`.