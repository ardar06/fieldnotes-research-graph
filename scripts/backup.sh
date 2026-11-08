#!/usr/bin/env bash
set -euo pipefail
umask 077
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p backups
FILE="backups/fieldnotes-$(date +%Y%m%d-%H%M%S).sql"
if command -v docker >/dev/null 2>&1; then
  if docker exec fieldnotes-db pg_isready -U fieldnotes -d fieldnotes >/dev/null 2>&1; then
    docker exec fieldnotes-db pg_dump -U fieldnotes fieldnotes > "$FILE"
  else
    docker compose exec -T db pg_dump -U fieldnotes fieldnotes > "$FILE"
  fi
else
  LOCALAPPDATA_WIN="$(cd /mnt/c && cmd.exe /d /c 'echo %LOCALAPPDATA%' | tr -d '\r')"
  LOCALAPPDATA_WSL="$(wslpath -u "$LOCALAPPDATA_WIN")"
  DOCKER_EXE="$LOCALAPPDATA_WSL/Programs/DockerDesktop/resources/bin/docker.exe"
  CONFIG_DIR="$LOCALAPPDATA_WSL/hermes/cache/scratch/fieldnotes-docker-config"
  CONFIG_WIN="$(wslpath -w "$CONFIG_DIR")"
  "$DOCKER_EXE" --config "$CONFIG_WIN" exec fieldnotes-db pg_dump -U fieldnotes fieldnotes > "$FILE"
fi
chmod 600 "$FILE"
printf 'Backup written to %s (protect it as sensitive research data).\n' "$FILE"
