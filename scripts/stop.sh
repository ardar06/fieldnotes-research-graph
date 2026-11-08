#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if command -v docker >/dev/null 2>&1; then
  docker compose down
  docker rm -f fieldnotes-app fieldnotes-db >/dev/null 2>&1 || true
  exit 0
fi
LOCALAPPDATA_WIN="$(cd /mnt/c && cmd.exe /d /c 'echo %LOCALAPPDATA%' | tr -d '\r')"
LOCALAPPDATA_WSL="$(wslpath -u "$LOCALAPPDATA_WIN")"
DOCKER_EXE="$LOCALAPPDATA_WSL/Programs/DockerDesktop/resources/bin/docker.exe"
CONFIG_DIR="$LOCALAPPDATA_WSL/hermes/cache/scratch/fieldnotes-docker-config"
CONFIG_WIN="$(wslpath -w "$CONFIG_DIR")"
if [[ ! -x "$DOCKER_EXE" ]]; then echo "Docker CLI not found." >&2; exit 1; fi
"$DOCKER_EXE" --config "$CONFIG_WIN" rm -f fieldnotes-app fieldnotes-db >/dev/null 2>&1 || true
echo "Fieldnotes stopped. Database volume 'fieldnotes-db' was kept."
