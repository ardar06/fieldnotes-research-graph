#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  printf 'POSTGRES_PASSWORD=%s\n' "$(python3 -c 'import secrets; print(secrets.token_hex(32))')" > .env
  chmod 600 .env
  echo "Created a private local database password in .env"
fi

if command -v docker >/dev/null 2>&1; then
  # If WSL integration was enabled after a direct-CLI run, stop the old containers
  # before Compose attaches the same persistent volume.
  docker rm -f fieldnotes-app fieldnotes-db >/dev/null 2>&1 || true
  docker compose up --build -d
  echo "Fieldnotes is available at http://127.0.0.1:8000"
  exit 0
fi

LOCALAPPDATA_WIN="$(cd /mnt/c && cmd.exe /d /c 'echo %LOCALAPPDATA%' | tr -d '\r')"
LOCALAPPDATA_WSL="$(wslpath -u "$LOCALAPPDATA_WIN")"
DOCKER_EXE="$LOCALAPPDATA_WSL/Programs/DockerDesktop/resources/bin/docker.exe"
if [[ ! -x "$DOCKER_EXE" ]]; then
  echo "Docker CLI was not found. Enable Docker Desktop WSL integration or add docker to PATH." >&2
  exit 1
fi

# Use an isolated anonymous-pull config so the Windows Docker CLI does not need
# the desktop credential helper in WSL and does not modify the user's config.
CONFIG_DIR="$LOCALAPPDATA_WSL/hermes/cache/scratch/fieldnotes-docker-config"
mkdir -p "$CONFIG_DIR"
printf '{"auths": {}}\n' > "$CONFIG_DIR/config.json"
CONFIG_WIN="$(wslpath -w "$CONFIG_DIR")"
docker_cli() { "$DOCKER_EXE" --config "$CONFIG_WIN" "$@"; }
DB_ENV_FILE="$CONFIG_DIR/fieldnotes-db.env"
APP_ENV_FILE="$CONFIG_DIR/fieldnotes-app.env"
python3 "$ROOT/scripts/write-container-env.py" "$ROOT/.env" "$DB_ENV_FILE" "$APP_ENV_FILE"
DB_ENV_WIN="$(wslpath -w "$DB_ENV_FILE")"
APP_ENV_WIN="$(wslpath -w "$APP_ENV_FILE")"
cleanup_env_files() { rm -f "$DB_ENV_FILE" "$APP_ENV_FILE"; }
trap cleanup_env_files EXIT

# Stream the WSL project into Docker as a build archive; no WSL bind mount needed.
tar -C "$ROOT" \
  --exclude='./.git' --exclude='./.env' --exclude='./frontend/node_modules' \
  --exclude='./frontend/dist' --exclude='./backups' --exclude='./.venv' \
  -cf - . | docker_cli build --target runtime -t fieldnotes:local -

docker_cli network inspect fieldnotes-net >/dev/null 2>&1 || docker_cli network create fieldnotes-net >/dev/null
docker_cli volume inspect fieldnotes-db >/dev/null 2>&1 || docker_cli volume create fieldnotes-db >/dev/null
docker_cli volume inspect fieldnotes-settings >/dev/null 2>&1 || docker_cli volume create fieldnotes-settings >/dev/null
docker_cli rm -f fieldnotes-app >/dev/null 2>&1 || true
docker_cli rm -f fieldnotes-db >/dev/null 2>&1 || true

docker_cli run -d --name fieldnotes-db --restart unless-stopped --network fieldnotes-net \
  --env-file "$DB_ENV_WIN" \
  -v fieldnotes-db:/var/lib/postgresql/data \
  --health-cmd='pg_isready -U fieldnotes -d fieldnotes' --health-interval=3s --health-timeout=3s --health-retries=30 \
  postgres:17-alpine >/dev/null

ready=0
for attempt in $(seq 1 40); do
  if docker_cli exec fieldnotes-db pg_isready -U fieldnotes -d fieldnotes >/dev/null 2>&1; then ready=1; break; fi
  sleep 1
done
if [[ "$ready" != 1 ]]; then
  docker_cli logs --tail 80 fieldnotes-db >&2
  echo "PostgreSQL did not become ready." >&2
  exit 1
fi

docker_cli run -d --name fieldnotes-app --restart unless-stopped --network fieldnotes-net \
  --env-file "$APP_ENV_WIN" \
  -v fieldnotes-settings:/var/lib/fieldnotes \
  -p 127.0.0.1:8000:8000 fieldnotes:local >/dev/null

for attempt in $(seq 1 30); do
  if curl --silent --fail http://127.0.0.1:8000/api/health >/dev/null; then
    echo "Fieldnotes is running at http://127.0.0.1:8000"
    echo "API documentation: http://127.0.0.1:8000/docs"
    echo "Persistent database volume: fieldnotes-db"
    exit 0
  fi
  sleep 1
done
docker_cli logs --tail 100 fieldnotes-app >&2
echo "The app container did not become healthy." >&2
exit 1
