import json
import os
import tempfile
from pathlib import Path
from typing import Any


def settings_path() -> Path:
    return Path(os.getenv("AI_SETTINGS_PATH", "/var/lib/fieldnotes/ai-settings.json"))


def read_local_ai_settings() -> dict[str, Any] | None:
    path = settings_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        value = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError("Saved AI settings are unreadable") from exc
    required = {"provider_name", "base_url", "model", "api_key", "enabled"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise ValueError("Saved AI settings are invalid")
    if not all(isinstance(value[key], str) for key in ("provider_name", "base_url", "model", "api_key")):
        raise ValueError("Saved AI settings are invalid")
    if not isinstance(value["enabled"], bool):
        raise ValueError("Saved AI settings are invalid")
    return value


def write_local_ai_settings(value: dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    fd, temporary_name = tempfile.mkstemp(prefix=".ai-settings-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        if hasattr(os, "fchmod"):
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, path)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


def delete_local_ai_settings() -> None:
    path = settings_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
