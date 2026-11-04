"""Builds the finished APK, including the native quick-add notification and pop-up form, in one command:

    python tools/build_apk.py

Run it from the project folder with your virtual environment active. What it does:
  1. flet build apk          (makes the Android project and a first APK)
  2. patch_android.py        (adds the quick-add Java code to that project)
  3. flutter build apk       (compiles the patched project, with the settings Flet normally supplies)
Useful options:  --skip-flet  (reuse the project from an earlier run)   --dry-run  (only show what would run)
"""
import argparse
import os
import pathlib
import re
import shutil
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
PROJECT = HERE.parent
sys.path.insert(0, str(HERE))
import patch_android  # noqa: E402

BUNDLE_ID = "com.wheremymoney"
PYTHON_VERSION = "3.12"      # the Python bundled inside the app (steps 1 and 3 must agree)
FLUTTER_VERSION = "3.44.8"   # the Flutter that Flet 1.0.5 downloads to ~/flutter/<version>


def say(text):
    print(f"\n=== {text}")


def run(command, dry_run, **kwargs):
    print("> " + " ".join(str(part) for part in command))
    if dry_run:
        return 0
    return subprocess.run([str(part) for part in command], **kwargs).returncode


def flet_command():
    found = shutil.which("flet")
    if found:
        return found
    return str(pathlib.Path(sys.executable).parent / ("flet.exe" if os.name == "nt" else "flet"))


def flutter_exe():
    name = "flutter.bat" if os.name == "nt" else "flutter"
    path = pathlib.Path.home() / "flutter" / FLUTTER_VERSION / "bin" / name
    if path.exists():
        return path
    sys.exit(f"ERROR: Flutter {FLUTTER_VERSION} not found at {path}.\n"
             "Run `flet build apk` once (it downloads Flutter), or look in your ~/flutter folder and change "
             "FLUTTER_VERSION at the top of this script.")


def project_version():
    match = re.search(r'^version\s*=\s*"([^"]+)"', (PROJECT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return match.group(1) if match else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--skip-flet", action="store_true", help="do not run `flet build apk` again")
    parser.add_argument("--dry-run", action="store_true", help="show the commands without running them")
    parser.add_argument("--build-number", help="Android versionCode (raise it if an install is refused as a downgrade)")
    args = parser.parse_args()
    os.chdir(PROJECT)

    if not args.skip_flet:
        say("1/3  flet build apk")
        code = run([flet_command(), "build", "apk", "-v", "--bundle-id", BUNDLE_ID, "--python-version", PYTHON_VERSION],
                   args.dry_run, cwd=PROJECT)
        if code:
            sys.exit(f"ERROR: `flet build apk` failed (exit code {code}). Fix that first; the message above says why.")
    else:
        say("1/3  flet build apk  (skipped)")

    say("2/3  adding the quick-add notification and pop-up form")
    if args.dry_run:
        print("> python tools/patch_android.py")
    else:
        patch_android.main()

    say("3/3  flutter build apk")
    build_dir = PROJECT / "build"
    env = dict(os.environ)
    env.update({
        # the settings `flet build` normally gives Flutter; without them the Python app is not packed into the APK
        "SERIOUS_PYTHON_VERSION": PYTHON_VERSION,
        "SERIOUS_PYTHON_SITE_PACKAGES": str(build_dir / "site-packages"),
        "SERIOUS_PYTHON_APP": str(build_dir / "python-app"),
        "SERIOUS_PYTHON_BUNDLE_ID": BUNDLE_ID,
    })
    if not args.dry_run:
        for name in ("site-packages", "python-app"):
            if not (build_dir / name).exists():
                sys.exit(f"ERROR: build/{name} is missing. Run this script without --skip-flet first.")
    command = [flutter_exe(), "build", "apk", "--release", "--no-version-check", "--suppress-analytics"]
    if project_version():
        command += ["--build-name", project_version()]
    if args.build_number:
        command += ["--build-number", args.build_number]
    code = run(command, args.dry_run, cwd=build_dir / "flutter", env=env)
    if code:
        sys.exit(f"ERROR: `flutter build apk` failed (exit code {code}). Send me the first error line above.")

    apks = sorted((build_dir / "flutter" / "build" / "app" / "outputs" / "flutter-apk").glob("*.apk"))
    say("Done")
    for apk in apks:
        print("APK:", apk)
    first = apks[0] if apks else "build\\flutter\\build\\app\\outputs\\flutter-apk\\app-release.apk"
    print(f"\nInstall it with:\n  adb install -r \"{first}\"")


if __name__ == "__main__":
    main()