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
1. Install Android Studio (gives you the Android SDK) and a JDK 17.
2. In the project folder (virtual environment active): `flet build apk --bundle-id com.wheremymoney`
   (the app ID is also set in `pyproject.toml`; the flag makes sure it is exactly `com.wheremymoney`)
3. The APK appears in `build/apk/`. Copy it to your phone and open it
   (allow "install unknown apps" for your file manager or browser when asked).
4. Your icon is `src/assets/icon.png` (replace with your own square PNG, 1024x1024).
   Your home screen name is `product` in `pyproject.toml`.