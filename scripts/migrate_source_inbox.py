#!/usr/bin/env python3
"""Safely and resumably copy an existing Source Inbox into its persistent volume."""
import argparse
import hashlib
import os
import shutil
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def inventory(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"Symlinks are not supported in Source Inbox: {path}")
        if path.is_file():
            files[path.relative_to(root).as_posix()] = path
        elif not path.is_dir():
            raise ValueError(f"Unsupported filesystem entry: {path}")
    return files


def migrate(source: Path, destination: Path, dry_run: bool = False) -> tuple[int, int]:
    source = source.resolve()
    destination = destination.resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError("Source and destination must be separate, non-overlapping directories")
    if not source.is_dir():
        raise ValueError(f"Source directory does not exist: {source}")
    destination.mkdir(parents=True, exist_ok=True)

    source_files = inventory(source)
    destination_files = inventory(destination)
    for relative, existing in destination_files.items():
        if relative not in source_files:
            raise ValueError(f"Destination contains an unrelated file: {existing}")
        if digest(existing) != digest(source_files[relative]):
            raise ValueError(f"Destination file differs from source: {relative}")

    copied = 0
    skipped = 0
    for relative, original in source_files.items():
        target = destination / relative
        if target.exists():
            skipped += 1
            continue
        if dry_run:
            copied += 1
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.migration-tmp")
        try:
            shutil.copy2(original, temporary)
            if digest(original) != digest(temporary):
                raise OSError(f"Checksum mismatch after copying: {relative}")
            os.link(temporary, target)
            temporary.unlink()
        finally:
            temporary.unlink(missing_ok=True)
        copied += 1

    if dry_run:
        return copied, skipped

    # Recheck both inventories after copying. The original directory is never deleted.
    final_files = inventory(destination)
    if set(final_files) != set(source_files):
        raise OSError("Migration verification failed: destination file inventory differs")
    for relative, original in source_files.items():
        if digest(original) != digest(final_files[relative]):
            raise OSError(f"Migration verification failed for {relative}")
    return copied, skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    copied, skipped = migrate(args.source, args.destination, args.dry_run)
    mode = "Would copy" if args.dry_run else "Copied"
    print(f"{mode} {copied} file(s); verified and skipped {skipped} existing file(s).")
    print("Original Source Inbox was left unchanged.")


if __name__ == "__main__":
    main()
