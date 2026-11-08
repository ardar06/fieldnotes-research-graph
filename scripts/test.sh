#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
if command -v docker >/dev/null 2>&1; then
  docker build --build-arg TEST_RUN_ID="$(date +%s)" --target test -t fieldnotes:test .
  exit 0
fi
LOCALAPPDATA_WIN="$(cd /mnt/c && cmd.exe /d /c 'echo %LOCALAPPDATA%' | tr -d '\r')"
LOCALAPPDATA_WSL="$(wslpath -u "$LOCALAPPDATA_WIN")"
DOCKER_EXE="$LOCALAPPDATA_WSL/Programs/DockerDesktop/resources/bin/docker.exe"
CONFIG_DIR="$LOCALAPPDATA_WSL/hermes/cache/scratch/fieldnotes-docker-config"
if [[ ! -x "$DOCKER_EXE" ]]; then echo "Docker CLI not found." >&2; exit 1; fi
mkdir -p "$CONFIG_DIR"
printf '{"auths": {}}\n' > "$CONFIG_DIR/config.json"
CONFIG_WIN="$(wslpath -w "$CONFIG_DIR")"
tar -C "$ROOT" --exclude='./.git' --exclude='./.env' --exclude='./frontend/node_modules' --exclude='./frontend/dist' --exclude='./backups' --exclude='./.venv' -cf - . \
  | "$DOCKER_EXE" --config "$CONFIG_WIN" build --build-arg TEST_RUN_ID="$(date +%s)" --target test -
