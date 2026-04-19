#!/usr/bin/env python3
"""
Automated backup module for configuration files.

This script monitors changes using content hashes, synchronizes files to a
Git repository, validates Caddy configurations, and performs automatic commits.
"""
import hashlib
import json
import logging
import logging.handlers
import shutil
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path

# --- CONFIG ---
BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"


def load_env_file(path: Path):
    """Load KEY=VALUE pairs from a .env file into os.environ without overwriting."""
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if (val.startswith('"') and val.endswith('"')) or (
                val.startswith("'") and val.endswith("'")
            ):
                val = val[1:-1]
            os.environ.setdefault(key, val)


load_env_file(ENV_FILE)
CONFIG_FILE = BASE_DIR / "backup_paths.json"
GIT_PATH = Path(os.environ.get("BACKUP_GIT_PATH", str(BASE_DIR / "raspberry-config-server")))
HASH_FILE = Path(os.environ.get("BACKUP_HASH_FILE", str(BASE_DIR / "backup_hashes.json")))
LOG_FILE = Path(os.environ.get("BACKUP_LOG_FILE", str(BASE_DIR / "backup.log")))
CHOWN_USER = os.environ.get("BACKUP_CHOWN", "")


class JsonFormatter(logging.Formatter):
    """
    JSON log formatter that emits structured log records.

    Adds fields like UTC timestamp, severity level, message and optional extra data.
    """

    def format(self, record):
        """
        Converte o registro de log em uma string JSON formatada.
        """
        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "extra": getattr(record, "extra", {}),
        }
        return json.dumps(log_record)


def setup_logger():
    """
    Configure and return the structured logger with file rotation.
    """
    logger = logging.getLogger("backup_system")
    logger.setLevel(logging.INFO)
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3
    )
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    return logger


def get_hash(path):
    """Deterministic content hash; includes untracked files and directories."""
    p = Path(path)
    if not p.exists():
        return None
    if p.is_file():
        return _hash_file(p)
    return _hash_dir(p)


def _hash_file(path: Path) -> str:
    """Return the SHA256 hexdigest of a file by reading in chunks.

    Keeps the chunked-read logic for large files.
    """
    hasher = hashlib.sha256()
    for chunk in _iter_file_chunks(path):
        hasher.update(chunk)
    return hasher.hexdigest()


def _hash_dir(path: Path) -> str:
    """Compute a deterministic SHA256 hash for a directory.

    Entry order is normalized; the hash includes relative paths, file names
    and their contents to detect any change.
    """
    hasher = hashlib.sha256()
    for root, dirs, files in os.walk(str(path)):
        dirs.sort()
        files.sort()
        rel_root = os.path.relpath(root, str(path))
        hasher.update(rel_root.encode("utf-8"))
        for fname in files:
            fpath = os.path.join(root, fname)
            hasher.update(fname.encode("utf-8"))
            for chunk in _iter_file_chunks(Path(fpath)):
                hasher.update(chunk)
    return hasher.hexdigest()


def _iter_file_chunks(path: Path, chunk_size: int = 8192):
    """Iterator that reads a file in byte chunks.

    Usage: for chunk in _iter_file_chunks(path):
    """
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            yield chunk


def validate_caddy(path, logger):
    """
    Validate a Caddyfile before committing.

    Returns True if valid, False on syntax error or if caddy is not available.
    """
    try:
        subprocess.run(
            ["caddy", "fmt", "--overwrite", str(path)], check=True, capture_output=True
        )

        subprocess.run(
            ["caddy", "validate", "--config", str(path), "--adapter", "caddyfile"],
            check=True,
            capture_output=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        logger.error(f"Invalid file or Caddy not installed: {path}")
        return False


def load_data(logger):
    """Load configuration paths and the previous hash history."""
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)

        old_hashes = {}
        if os.path.exists(HASH_FILE):
            with open(HASH_FILE, "r", encoding="utf-8") as f:
                old_hashes = json.load(f)

        return config, old_hashes
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Error loading base files: {e}")
        return None, None


def sync_files(config, logger):
    """Copy files into the repository and validate when required."""
    for item in config:
        src, dst = Path(item["src"]), GIT_PATH / item["dst"]
        try:
            method = item.get("method", "copy")
            if method == "rsync":
                _run_rsync(src, dst)
            else:
                _copy_path(src, dst)

            if item.get("validate") == "caddy" and not validate_caddy(dst, logger):
                return False
        except (OSError, subprocess.CalledProcessError) as e:
            logger.error(f"Error processing {src}: {e}")
            return False
    return True


def _run_rsync(src: Path, dst: Path):
    """Run `rsync` preserving attributes and removing obsolete files.

    Raises subprocess.CalledProcessError on failure to be handled by the caller.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    rsync_src = str(src) + ("/" if src.is_dir() else "")
    subprocess.run(
        [
            "rsync",
            "-aHAXx",
            "--numeric-ids",
            "--delete",
            rsync_src,
            str(dst),
        ],
        check=True,
        capture_output=True,
    )


def _copy_path(src: Path, dst: Path):
    """Copy a file or directory preserving symlinks.

    If `dst` exists as a directory it is removed before copying to keep the
    destination clean.
    """
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, symlinks=True)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def commit_changes(logger, new_hashes):
    """Realiza o commit no Git e limpa permissões."""
    try:
        status = subprocess.run(
            ["git", "-C", str(GIT_PATH), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        if not status.stdout.strip():
            logger.info("No real changes detected by Git.")
            return

        subprocess.run(["git", "-C", str(GIT_PATH), "add", "."], check=True)
        msg = f"Backup {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "-C", str(GIT_PATH), "commit", "-m", msg], check=True)

        if CHOWN_USER:
            subprocess.run(["chown", "-R", CHOWN_USER, str(GIT_PATH)], check=True)
        with open(HASH_FILE, "w", encoding="utf-8") as f:
            json.dump(new_hashes, f)

        logger.info("Backup and commit completed successfully.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error during Git operation: {e}")


def main():
    """Main backup flow."""
    logger = setup_logger()
    config, old_hashes = load_data(logger)
    if not config:
        return

    new_hashes = {item["src"]: get_hash(item["src"]) for item in config}
    if new_hashes == old_hashes:
        logger.info("No changes detected in hashes.")
        return

    logger.info("Starting synchronization...")
    if sync_files(config, logger):
        commit_changes(logger, new_hashes)


if __name__ == "__main__":
    main()
