"""Adds the native quick-add notification and pop-up form to the Android project that `flet build apk` generates.

Run it from the project folder AFTER `flet build apk` and BEFORE `flutter build apk --release`:
    python tools/patch_android.py
It is safe to run more than once.
"""
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
MAIN = HERE.parent / "build" / "flutter" / "android" / "app" / "src" / "main"
PACKAGE_DIR = pathlib.Path("java") / "com" / "wheremymoney" / "quickadd"

PERMISSIONS = [
    "android.permission.POST_NOTIFICATIONS",
    "android.permission.RECEIVE_BOOT_COMPLETED",
    "android.permission.USE_BIOMETRIC",  # fingerprint unlock for the app lock
]
COMPONENTS = """
        <activity
            android:name="com.wheremymoney.quickadd.QuickAddActivity"
            android:exported="false"
            android:excludeFromRecents="true"
            android:taskAffinity=""
            android:launchMode="singleTop"
            android:theme="@android:style/Theme.DeviceDefault.Light.Dialog"
            android:windowSoftInputMode="stateVisible|adjustResize" />
        <receiver
            android:name="com.wheremymoney.quickadd.QuickAddBootReceiver"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.BOOT_COMPLETED" />
            </intent-filter>
        </receiver>
"""
KOTLIN_HOOKS = """
    override fun onResume() {
        super.onResume()
        com.wheremymoney.quickadd.QuickAddHelper.onResume(this)
    }

    override fun onPause() {
        com.wheremymoney.quickadd.QuickAddHelper.onPause()
        super.onPause()
    }
"""


def fail(message):
    print("ERROR:", message)
    sys.exit(1)


def copy_java():
    target = MAIN / PACKAGE_DIR
    target.mkdir(parents=True, exist_ok=True)
    for source in sorted((HERE / "android").glob("*.java")):
        shutil.copy(source, target / source.name)
        print("  copied", source.name)


def patch_manifest():
    path = MAIN / "AndroidManifest.xml"
    if not path.exists():
        fail(f"{path} not found")
    text = path.read_text(encoding="utf-8")
    missing = [p for p in PERMISSIONS if p not in text]  # checked every run, so new permissions get added too
    if missing:
        lines = "".join(f'    <uses-permission android:name="{p}" />\n' for p in missing)
        text, count = re.subn(r"(<application\b)", lambda m: lines + "    " + m.group(1), text, count=1)
        if not count:
            fail("no <application> tag found in AndroidManifest.xml")
    if "QuickAddActivity" not in text:
        if "</application>" not in text:
            fail("no </application> tag found in AndroidManifest.xml")
        text = text.replace("</application>", COMPONENTS + "    </application>", 1)
    elif not missing:
        print("  manifest already patched")
        return
    path.write_text(text, encoding="utf-8")
    print("  manifest patched")


def patch_main_activity():
    candidates = list(MAIN.rglob("MainActivity.kt"))
    if not candidates:
        fail("MainActivity.kt not found")
    path = candidates[0]
    text = path.read_text(encoding="utf-8")
    if "QuickAddHelper" in text:
        print("  MainActivity already patched")
        return
    if "fun onResume" in text or "fun onPause" in text:
        fail(f"{path.name} already has onResume/onPause; add the QuickAddHelper calls by hand")
    # `class MainActivity : SomeActivity()` followed by a body in braces, or by nothing at all
    declaration = re.search(r"class\s+MainActivity\s*:\s*[\w.]+\s*\(\s*\)", text)
    if not declaration:
        print(f"--- contents of {path} ---\n{text}\n--- end ---")
        fail("could not find `class MainActivity : ...Activity()` in MainActivity.kt (contents printed above)")
    body = re.match(r"\s*\{", text[declaration.end():])
    if body:  # insert right after the opening brace
        position = declaration.end() + body.end()
        text = text[:position] + KOTLIN_HOOKS + text[position:]
    else:     # no body yet: add one
        text = text[:declaration.end()] + " {" + KOTLIN_HOOKS + "}" + text[declaration.end():]
    path.write_text(text, encoding="utf-8")
    print("  MainActivity patched:", path)


def main():
    if not MAIN.exists():
        fail("build/flutter/android not found. Run `flet build apk -v` first (from the project folder).")
    print("Adding the quick-add notification and pop-up form to the Android project:")
    copy_java()
    patch_manifest()
    patch_main_activity()
    print("Done. Next: cd build/flutter, then flutter build apk --release")


if __name__ == "__main__":
    main()