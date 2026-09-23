"""Rebuild ILAW_TeacherTools_Setup.bat from the current project files.

Run from the project root:  py work/rebuild_installer.py
"""
import base64
import io
import os
import re
import zipfile
from datetime import date

FILES = [
    "app.py",
    "requirements.txt",
    "README.md",
    "SAMPLE ILAW FORMAT_WIDE.xlsx",
    "LESSON IMPLEMENTATION LOG TEMPLATE.xlsx",
    "ilaw-icon.ico",
    "launch_ilaw.bat",
    "launch_ilaw_hidden.vbs",
    "feedback_webhook.txt",
]
TEMPLATE = "work/installer_template.bat"
OUTPUT = "ILAW_TeacherTools_Setup.bat"


def build_payload() -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in FILES:
            archive.write(path, path)
    return base64.b64encode(buffer.getvalue()).decode()


def app_version() -> str:
    """Read _APP_VERSION from app.py so the installer banner always matches."""
    with open("app.py", encoding="utf-8") as handle:
        match = re.search(r'_APP_VERSION\s*=\s*"([^"]+)"', handle.read())
    assert match, "app.py is missing its _APP_VERSION constant"
    return match.group(1)


def main() -> None:
    with open(TEMPLATE, encoding="utf-8") as handle:
        template = handle.read()
    assert "@@PAYLOAD@@" in template, "installer template is missing its payload marker"
    version = app_version()
    installer = template.replace("@@APP_VERSION@@", version)
    installer = installer.replace("@@BUILD_DATE@@", f"{date.today():%B %d, %Y}")
    installer = installer.replace("@@PAYLOAD@@", build_payload())
    with open(OUTPUT, "w", encoding="utf-8", newline="\r\n") as handle:
        handle.write(installer)
    print(f"{OUTPUT}: {os.path.getsize(OUTPUT):,} bytes ({date.today():%Y-%m-%d})")


if __name__ == "__main__":
    main()
