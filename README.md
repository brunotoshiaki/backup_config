# backup_config

Automated configuration backup tool for saving system files into a repository snapshot.

It uses deterministic content hashing to detect changes, supports `rsync` for large directories, validates Caddyfiles before saving, and only creates a new snapshot when changes are found.

## Features

- Deterministic hashing for files and directories
- Backup of configured paths into the repository
- Optional `rsync` support for large or complex trees
- Optional Caddyfile validation before saving
- Minimal dependencies: Python and common system tools
- Optional ownership fix with `chown`

## Requirements

- Python 3.8 or newer
- `git` available on `PATH`
- `rsync` installed if you use `"method": "rsync"`
- `caddy` installed if you use Caddy validation

## Quick Start

1. Place the project files on the target machine.
2. Edit `backup_paths.json` with the paths you want to back up.
3. Run the backup script manually or with a scheduler.

## Configuration

The main configuration file is `backup_paths.json`.

Each entry should include:

- `src`: absolute path to back up
- `dst`: relative destination path inside the repository
- `method` *(optional)*: use `"rsync"` instead of a regular copy
- `validate` *(optional)*: use `"caddy"` to validate the destination file

### Example

```json
[
  {
    "src": "/etc/caddy/Caddyfile",
    "dst": "etc/caddy/Caddyfile",
    "validate": "caddy"
  },
  {
    "src": "/etc/nginx",
    "dst": "etc/nginx",
    "method": "rsync"
  }
]
```

## Optional Environment Variables

- `BACKUP_GIT_PATH`: path to the local repository (default: current repository folder)
- `BACKUP_HASH_FILE`: path to the saved hash file (default: `backup_hashes.json`)
- `BACKUP_LOG_FILE`: path to the log file (default: `backup.log`)
- `BACKUP_CHOWN`: `user:group` value used with `chown -R` after backup

## Scheduled Execution

You can run the backup with any scheduler, such as cron or a systemd timer.

> Backing up system paths like `/etc` or `/var` may require elevated permissions.

## Security Notes

- Do not store secrets, private keys, or passwords in the repository.
- Exclude sensitive paths when needed.
- Use encryption for sensitive backups when appropriate.
- Restrict access to the backup repository.

## Contributing

Keep changes focused and update documentation when behavior changes.
