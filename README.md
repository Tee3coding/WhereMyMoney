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