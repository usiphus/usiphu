# Local setup, backup and restore

USIPHU is currently designed to run directly on one computer with Python and SQLite. It does not require Docker, Docker Compose, a public server or a domain.

## 1. Install and run

Requirements: Python 3.11 or newer.

**Windows PowerShell**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
streamlit run app/Home.py
```

**macOS / Linux**

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
streamlit run app/Home.py
```

Open the local URL printed by Streamlit, normally http://localhost:8501. Keep the terminal open while the app is running. Press Ctrl+C to stop it.

Optional AI authoring uses Ollama installed directly on the same computer. Pull the model with `ollama pull qwen2.5:7b`, then set `OLLAMA_BASE_URL=http://localhost:11434` and `USIPHU_OLLAMA_MODEL=qwen2.5:7b` before launching Streamlit. The core app does not require Ollama.

## 2. Local data locations

Default paths when launched from the repository root:

- SQLite learner database: `usiphu_data.sqlite3`.
- Uploaded papers, source manifest, extraction JSON and review history: `data/source_inbox/`.
- Paired backup files: `data/backups/`.

You can override these locations with `USIPHU_DB_PATH`, `USIPHU_SOURCE_DIR` and `USIPHU_BACKUP_DIR`. Use absolute paths for custom locations. Keep the database and Source Inbox on a reliable local disk, not a temporary folder or removable drive that may disconnect while the app is running.

## 3. Create a backup

Stop USIPHU before making a coordinated backup so uploads and reviews cannot change during the snapshot. With the Python environment activated, run:

```bash
python scripts/backup_sqlite.py
```

By default, the script creates:
- `data/backups/usiphu-<timestamp>.sqlite3`: a SQLite online backup checked with `PRAGMA integrity_check`.
- `data/backups/usiphu-sources-<timestamp>.tar.gz`: the complete Source Inbox, including uploaded originals, manifest, extraction outputs and review history.
- A matching `.sha256` checksum file for the Source Inbox archive.

Copy all three files to a second, encrypted location (external drive or trusted cloud storage). A backup on the same computer is not protection against disk failure or theft. Restart USIPHU after the backup is complete.

## 4. Restore a backup

Restore into a new, empty directory. Do not overwrite the live database or current Source Inbox.

```bash
mkdir -p restore-drill
python scripts/restore_backup.py \
  --database-backup data/backups/usiphu-TIMESTAMP.sqlite3 \
  --source-archive data/backups/usiphu-sources-TIMESTAMP.tar.gz \
  --checksum data/backups/usiphu-sources-TIMESTAMP.tar.gz.sha256 \
  --database-target restore-drill/usiphu_data.sqlite3 \
  --source-target restore-drill/source-inbox
```

Replace `TIMESTAMP` in all three paths with the same timestamp. The restore utility checks SQLite integrity and the archive SHA-256, rejects unsafe archive paths and symlinks, and refuses to overwrite a database or non-empty Source Inbox. Inspect the restored manifest, open several original papers, and review extracted candidate JSON before relying on the restored copy.

## 5. Move USIPHU to another computer

1. Stop USIPHU on the old computer.
2. Create a fresh backup using the procedure above.
3. Copy the three backup files to the new computer.
4. Install the same USIPHU version and Python dependencies on the new computer.
5. Restore into a clean directory and verify the files and database.
6. Set `USIPHU_DB_PATH` and `USIPHU_SOURCE_DIR` to the restored paths before launching the app.

The migration utility can also copy an existing Source Inbox without deleting the original:

```bash
python scripts/migrate_source_inbox.py --source OLD_SOURCE_INBOX --destination NEW_SOURCE_INBOX --dry-run
python scripts/migrate_source_inbox.py --source OLD_SOURCE_INBOX --destination NEW_SOURCE_INBOX
```

It verifies SHA-256 for every copied file, supports safe reruns and refuses conflicting destination files or symlinks.

## 6. Privacy and future hosting

The default app is a local single-operator workspace. Keep the computer account protected, enable full-disk encryption, install operating-system security updates and store backups encrypted. Do not expose Streamlit's local port directly to the public internet or use real patient-identifiable information without institutional privacy approval.

If you later want remote access or multiple learners, hosting must be designed separately. It will need persistent storage, HTTPS, authentication, access controls, monitored backups and a tested restore process. The current learner data layer uses SQLite; PostgreSQL is not yet wired into the application. A free host with an ephemeral filesystem is not suitable for uploaded papers or learner records.
