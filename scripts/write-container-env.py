#!/usr/bin/env python3
"""Create temporary Docker env files without putting provider keys on the CLI."""

import os
import shlex
import sys
from pathlib import Path
from urllib.parse import quote

ALLOWED = {"POSTGRES_PASSWORD", "AI_ENABLED", "AI_PROVIDER_NAME", "AI_BASE_URL", "AI_MODEL", "AI_API_KEY"}


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or key not in ALLOWED:
            continue
        parsed = shlex.split(value, comments=True, posix=True)
        if len(parsed) > 1:
            raise ValueError(f"{path}:{line_number}: values containing spaces must be quoted")
        result = parsed[0] if parsed else ""
        if "\n" in result or "\r" in result:
            raise ValueError(f"{path}:{line_number}: multiline values are not supported")
        values[key] = result
    if not values.get("POSTGRES_PASSWORD"):
        raise ValueError("POSTGRES_PASSWORD is required in .env")
    return values


def write_env(path: Path, values: dict[str, str]) -> None:
    for key, value in values.items():
        if "\n" in value or "\r" in value:
            raise ValueError(f"Multiline value rejected for {key}")
    path.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: write-container-env.py .env db.env app.env", file=sys.stderr)
        return 2
    source, db_path, app_path = map(Path, sys.argv[1:])
    values = read_env(source)
    db_values = {
        "POSTGRES_DB": "fieldnotes",
        "POSTGRES_USER": "fieldnotes",
        "POSTGRES_PASSWORD": values["POSTGRES_PASSWORD"],
    }
    encoded_password = quote(values["POSTGRES_PASSWORD"], safe="")
    app_values = {
        "DATABASE_URL": f"postgresql+psycopg://fieldnotes:{encoded_password}@fieldnotes-db:5432/fieldnotes",
        "AI_ENABLED": values.get("AI_ENABLED", "false") or "false",
        "AI_PROVIDER_NAME": values.get("AI_PROVIDER_NAME", "OpenAI-compatible provider") or "OpenAI-compatible provider",
        "AI_BASE_URL": values.get("AI_BASE_URL", ""),
        "AI_MODEL": values.get("AI_MODEL", ""),
        "AI_API_KEY": values.get("AI_API_KEY", ""),
        "AI_SETTINGS_PATH": "/var/lib/fieldnotes/ai-settings.json",
    }
    write_env(db_path, db_values)
    write_env(app_path, app_values)
    print("Temporary container environment files prepared; provider keys are not added to the Docker command line.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
