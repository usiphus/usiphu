#!/usr/bin/env bash
# Encrypted off-VM backup for the single-instance Oracle pilot.
set -Eeuo pipefail
umask 077

CONFIG_FILE="${USIPHU_BACKUP_CONFIG:-/etc/usiphu/backup.env}"
COMPOSE_FILE="${USIPHU_COMPOSE_FILE:-/opt/usiphu/docker-compose.oracle.yml}"
PROJECT_DIR="${USIPHU_PROJECT_DIR:-/opt/usiphu}"
RUNTIME_DIR="${USIPHU_RUNTIME_DIR:-$PROJECT_DIR/runtime}"
LOCK_FILE="${USIPHU_BACKUP_LOCK:-/run/lock/usiphu-backup.lock}"

log() { printf '[%s] %s\n' "$(date -u +'%Y-%m-%dT%H:%M:%SZ')" "$*"; }
fail_ping() {
  if [[ -n "${HEALTHCHECKS_PING_URL:-}" ]]; then
    curl --fail --silent --show-error --max-time 10 "${HEALTHCHECKS_PING_URL%/}/fail" >/dev/null || true
  fi
}
on_error() {
  status=$?
  fail_ping
  log "Backup failed (exit $status)."
  exit "$status"
}
trap on_error ERR

if [[ $EUID -ne 0 ]]; then
  echo "Run as root (for example through a root-owned cron job)." >&2
  exit 1
fi
if [[ ! -r "$CONFIG_FILE" ]]; then
  echo "Missing root-protected backup config: $CONFIG_FILE" >&2
  exit 1
fi
# This file must be owned by root and mode 0600; it contains backup credentials.
if [[ "$(stat -c '%U:%a' "$CONFIG_FILE")" != "root:600" ]]; then
  echo "Backup config must be root-owned with mode 0600: $CONFIG_FILE" >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

: "${AGE_RECIPIENT:?Set AGE_RECIPIENT to the age public recipient}"
: "${RCLONE_REMOTE:?Set RCLONE_REMOTE, e.g. r2:usiphu-backups}"
command -v age >/dev/null
command -v rclone >/dev/null
command -v docker >/dev/null
command -v flock >/dev/null

exec 9>"$LOCK_FILE"
flock -n 9 || { log "Another backup is already running; exiting."; exit 0; }

cd "$PROJECT_DIR"
mkdir -p "$RUNTIME_DIR/backups"
chmod 700 "$RUNTIME_DIR" "$RUNTIME_DIR/backups"

log "Creating a consistent SQLite and Source Inbox snapshot."
docker compose -f "$COMPOSE_FILE" exec -T app python /app/scripts/backup_sqlite.py

db_file="$(find "$RUNTIME_DIR/backups" -maxdepth 1 -type f -name 'usiphu-*.sqlite3' -printf '%T@ %p\n' | sort -nr | head -1 | cut -d' ' -f2-)"
[[ -n "$db_file" && -f "$db_file" ]]
stamp="$(basename "$db_file" .sqlite3 | sed 's/^usiphu-//')"
source_file="$RUNTIME_DIR/backups/usiphu-sources-$stamp.tar.gz"
source_checksum="$source_file.sha256"
[[ -f "$source_file" && -f "$source_checksum" ]]

work_dir="$(mktemp -d)"
trap 'rm -rf "$work_dir"' EXIT
base="usiphu-$stamp"
sha256sum "$db_file" > "$work_dir/$base.sqlite3.sha256"
cp "$source_checksum" "$work_dir/$base.sources.tar.gz.sha256"
age -r "$AGE_RECIPIENT" -o "$work_dir/$base.sqlite3.age" "$db_file"
age -r "$AGE_RECIPIENT" -o "$work_dir/$base.sources.tar.gz.age" "$source_file"
age -r "$AGE_RECIPIENT" -o "$work_dir/$base.sqlite3.sha256.age" "$work_dir/$base.sqlite3.sha256"
age -r "$AGE_RECIPIENT" -o "$work_dir/$base.sources.tar.gz.sha256.age" "$work_dir/$base.sources.tar.gz.sha256"

remote_dir="${RCLONE_REMOTE%/}/$stamp"
log "Uploading encrypted backup set to $remote_dir."
rclone copy "$work_dir" "$remote_dir" --include '*.age' --transfers 2 --checkers 2
rclone check "$work_dir" "$remote_dir" --one-way --download --include '*.age'

# Remove only the just-uploaded plaintext snapshot after remote verification.
rm -f -- "$db_file" "$source_file" "$source_checksum"
rm -f -- "$work_dir/$base.sqlite3.sha256" "$work_dir/$base.sources.tar.gz.sha256"

if [[ -n "${HEALTHCHECKS_PING_URL:-}" ]]; then
  curl --fail --silent --show-error --max-time 10 "$HEALTHCHECKS_PING_URL" >/dev/null
fi
log "Encrypted backup uploaded and verified successfully: $remote_dir"
