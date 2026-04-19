# backup_config
Automated configuration backup tool that snapshots system files into a Git repository.
Uses deterministic content hashing to detect changes, supports rsync for large trees, validates Caddyfiles before committing, and only commits when changes occur.

Features
Deterministic content hashing for files and directories
Sync configured paths into a local git repo
rsync support for large/complex trees
Caddyfile validation before commit
Minimal dependencies (pure Python + system rsync / git)
Automated commits and optional ownership fix (chown)
Requirements
Python 3.8+
git on PATH
rsync installed if you use entries with "method": "rsync"
caddy available only if you use Caddy validation
Quick Start
Copy this repository into your host or create a new repo and paste the files.
Edit backup_paths.json to list the paths you want to back up.
Run manually:
Configuration
Primary configuration: backup_paths.json — an array of objects with:

src (string): absolute path to back up
dst (string): relative destination path inside the git repo
optional method: "rsync" to use rsync instead of copy
optional validate: e.g. "caddy" to run Caddy validation on the destination file
Example:

Environment variables (optional):

BACKUP_GIT_PATH — path to local git repo (default: repository folder)
BACKUP_HASH_FILE — path to store previous hashes (default: backup_hashes.json)
BACKUP_LOG_FILE — path to log file (default: backup.log)
BACKUP_CHOWN — user:group to chown -R the repo after commit (optional)
Running as a Cron Job
Example cron that runs every 6 hours (edit with crontab -e):

Note: Backing up system paths like var or etc may require root permissions. Use sudo or a root cron if needed.

Tests
To run unit tests (optional):

Security & Best Practices
Do NOT store secrets, private keys, or passwords in the git repository.
Exclude sensitive paths using .gitignore or remove them from backup_paths.json.
For sensitive data, consider encryption (git-crypt, GPG) or secure offsite backups.
Limit who can read the git repo (permissions / private remote).
Contributing
Feel free to open issues or submit PRs. Keep changes focused and add tests for new behavior.
