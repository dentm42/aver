---
title__string: Specs for aver-inbox
incident_id__string: REC-LE34O40
---

# Aver Notification Middleware - Personal Repo Design

## Overview

**Concept:** External tool that bridges TWO aver databases:
1. **Project repo** (team's issue tracker) - READ ONLY via JSON IO
2. **Personal repo** (user's notification tracker) - READ/WRITE

**Key insights:**
- Middleware script, not part of aver core
- Uses `--location` flag to work with both repos
- Personal repo can use git for sync (portable across machines)
- Branch awareness not needed (last_seen timestamp handles it)
- Specialized REPO template: one record per monitored project

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│               Project Repo (Team)                            │
│  ~/work/myproject/.aver/                                     │
│    ├── index.db (SQLite)                                     │
│    ├── records/ISS-*.md                                      │
│    └── updates/ISS-*/NT-*.md                                 │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ JSON IO (read only)
                          │ aver --location ~/work/myproject
                          ↓
┌─────────────────────────────────────────────────────────────┐
│           aver-notify-sync (middleware script)               │
│  - Queries project repo via JSON IO                         │
│  - Detects new activity                                      │
│  - Updates personal repo                                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ aver commands
                          │ aver --location ~/.aver-personal
                          ↓
┌─────────────────────────────────────────────────────────────┐
│           Personal Repo (User's Notification DB)             │
│  ~/.aver-personal/.aver/                                     │
│    ├── index.db (SQLite)                                     │
│    ├── records/                                              │
│    │   ├── REPO-myproject.md      # One record per project  │
│    │   └── REPO-otherproject.md                             │
│    └── updates/                                              │
│        └── REPO-myproject/                                   │
│            ├── NT-001.md  # "3 new comments on ISS-042"     │
│            └── NT-002.md  # "ISS-103 assigned to you"       │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ git push/pull (optional)
                          │ Sync personal repo across machines
                          ↓
┌─────────────────────────────────────────────────────────────┐
│                     Other Machines                           │
│  Laptop: ~/.aver-personal                                    │
│  Desktop: ~/.aver-personal                                   │
│  Same repo, synced via git                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## Personal Repo Structure

### REPO Record Template

One record per monitored project repository. **Notifications stored as multi-value field.**

**Record ID:** `REPO-{project_name}`

**Template configuration for personal repo:**

**`~/.aver-personal/.aver/config.toml`:**
```toml
[template.repo]
record_prefix = "REPO"
note_prefix = "NOTE"
description = "Repository notification tracking"

record_template = """## Repository
Project being monitored

## Location
File path to the repository

## Last Synced
When notifications were last checked
"""

[template.repo.record_special_fields.repo_path]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = true
# Full path to project repo: /home/alice/work/myproject

[template.repo.record_special_fields.repo_name]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = true
# Short name: myproject

[template.repo.record_special_fields.last_synced]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false
# Timestamp of last sync: 2025-01-20T14:30:00Z

[template.repo.record_special_fields.user_handle]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = true
# Username in project repo: alice

[template.repo.record_special_fields.notifications]
type = "multi"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false
# Format: record_id:note_id:timestamp:author:summary
# Example: ISS-042:NT-005:2025-01-20T14:30:00Z:bob:commented on cache issue
```

### Example Personal Repo Content

**`~/.aver-personal/records/REPO-myproject.md`:**
```markdown
---
title: myproject
repo_path: /home/alice/work/myproject
repo_name: myproject
last_synced: 2025-01-20T14:30:00Z
user_handle: alice
created_timestamp: 2025-01-15T09:00:00Z
last_modified_timestamp: 2025-01-20T14:30:00Z
notifications:
  - ISS-042:NT-005:2025-01-20T14:30:00Z:bob:commented on cache issue
  - ISS-103:NT-012:2025-01-20T12:15:00Z:charlie:updated status to in_progress
  - ISS-088::2025-01-20T09:00:00Z:dave:changed priority to high
---

## Repository
Main project issue tracker

## Location
/home/alice/work/myproject

## Last Synced
2025-01-20T14:30:00Z
```

**Notes remain immutable** - only used for personal commentary if user wants:

**`~/.aver-personal/updates/REPO-myproject/NOTE-001.md`:**
```markdown
---
author: alice
timestamp: 2025-01-20T15:00:00Z
---

Reminder: Need to follow up on ISS-042 tomorrow
```

---

## Middleware Script

### File: `aver-notify-sync`

```bash
#!/bin/bash
#
# Aver notification sync middleware
# Bridges project repo → personal notification repo

set -e

# Configuration
PROJECT_REPO="${1:-.}"  # Default to current directory
PERSONAL_REPO="${AVER_PERSONAL_REPO:-$HOME/.aver-personal}"

# Ensure personal repo exists
if [ ! -d "$PERSONAL_REPO/.aver" ]; then
    echo "Initializing personal notification repo at $PERSONAL_REPO"
    mkdir -p "$PERSONAL_REPO"
    cd "$PERSONAL_REPO"
    git init
    aver admin init
fi

# Get absolute paths
PROJECT_REPO=$(cd "$PROJECT_REPO" && pwd)

# Get project name from path
PROJECT_NAME=$(basename "$PROJECT_REPO")

# Get user handle from project repo
USER_HANDLE=$(aver --location "$PROJECT_REPO" admin get-id --format handle 2>/dev/null)

if [ -z "$USER_HANDLE" ]; then
    echo "Error: Could not determine user handle in $PROJECT_REPO"
    exit 1
fi

# Run sync script
python3 "$(dirname "$0")/aver-notify-sync.py" \
    --project-repo "$PROJECT_REPO" \
    --personal-repo "$PERSONAL_REPO" \
    --project-name "$PROJECT_NAME" \
    --username "$USER_HANDLE"
```

### File: `aver-notify-sync.py`

```python
#!/usr/bin/env python3
"""
Aver notification sync middleware.
Queries project repo (via JSON IO) and updates personal notification repo.
Stores notifications as multi-value field in REPO record.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class AverNotifySync:
    """Sync notifications from project repo to personal repo."""
    
    def __init__(self, project_repo, personal_repo, project_name, username):
        self.project_repo = Path(project_repo)
        self.personal_repo = Path(personal_repo)
        self.project_name = project_name
        self.username = username
        self.repo_id = f"REPO-{project_name}"
        
        # Start JSON IO for project repo
        self.project_io = self._start_io(self.project_repo)
    
    def _start_io(self, repo_path):
        """Start persistent JSON IO process for a repo."""
        return subprocess.Popen(
            ["aver", "--location", str(repo_path), "json", "io"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    
    def _send_command(self, process, command, params):
        """Send command to JSON IO process."""
        request = {"command": command, "params": params}
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        
        response = json.loads(process.stdout.readline())
        return response.get("result") if response.get("success") else None
    
    def _run_aver_personal(self, *args, capture=True):
        """Run aver command on personal repo."""
        cmd = ["aver", "--location", str(self.personal_repo), *args]
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, check=True)
        else:
            return subprocess.run(cmd, check=True)
    
    def ensure_repo_record(self):
        """Ensure REPO record exists in personal repo."""
        # Check if exists using JSON IO on personal repo
        personal_io = self._start_io(self.personal_repo)
        result = self._send_command(personal_io, "export-record", {"record_id": self.repo_id})
        personal_io.terminate()
        
        if not result:
            # Create REPO record
            self._run_aver_personal(
                "record", "new",
                "--template", "repo",
                "--title", self.project_name,
                "--text", f"repo_path={self.project_repo}",
                "--text", f"repo_name={self.project_name}",
                "--text", f"user_handle={self.username}",
                "--text", f"last_synced=1970-01-01T00:00:00Z",
                "--description", f"Tracking notifications for {self.project_name}"
            )
            print(f"Created {self.repo_id} in personal repo")
    
    def get_last_synced(self):
        """Get last sync timestamp from REPO record."""
        personal_io = self._start_io(self.personal_repo)
        result = self._send_command(personal_io, "export-record", {"record_id": self.repo_id})
        personal_io.terminate()
        
        if result:
            return result.get("fields", {}).get("last_synced", "1970-01-01T00:00:00Z")
        
        return "1970-01-01T00:00:00Z"
    
    def get_existing_notifications(self):
        """Get existing notification entries to avoid duplicates."""
        personal_io = self._start_io(self.personal_repo)
        result = self._send_command(personal_io, "export-record", {"record_id": self.repo_id})
        personal_io.terminate()
        
        if result:
            notifications = result.get("fields", {}).get("notifications", [])
            if not isinstance(notifications, list):
                notifications = [notifications] if notifications else []
            
            # Extract record:note pairs
            existing = set()
            for notif in notifications:
                parts = notif.split(":", 2)  # record_id:note_id:...
                if len(parts) >= 2:
                    existing.add(f"{parts[0]}:{parts[1]}")
            
            return existing
        
        return set()
    
    def update_last_synced(self):
        """Update last_synced timestamp in REPO record."""
        now = datetime.now().isoformat() + "Z"
        self._run_aver_personal(
            "record", "update", self.repo_id,
            "--text", f"last_synced={now}"
        )
    
    def get_watched_records(self):
        """Get records user should be notified about."""
        watched = set()
        
        # Search for records assigned to user
        result = self._send_command(
            self.project_io,
            "search-records",
            {"ksearch": [f"assignee={self.username}"], "limit": 1000}
        )
        
        if result and result.get("records"):
            for record in result["records"]:
                watched.add(record["id"])
        
        # Search for records created by user
        result = self._send_command(
            self.project_io,
            "search-records",
            {"ksearch": [f"created_by={self.username}"], "limit": 1000}
        )
        
        if result and result.get("records"):
            for record in result["records"]:
                watched.add(record["id"])
        
        return watched
    
    def get_new_notes(self, last_synced, watched_records, existing_notifications):
        """Find new notes since last sync on watched records."""
        new_notes = []
        
        for record_id in watched_records:
            # Get record with notes
            result = self._send_command(
                self.project_io,
                "export-record",
                {"record_id": record_id, "include_notes": True}
            )
            
            if not result:
                continue
            
            record_title = result.get("fields", {}).get("title", record_id)
            notes = result.get("notes", [])
            
            for note in notes:
                note_timestamp = note.get("fields", {}).get("timestamp", "")
                note_id = note.get("id", "")
                
                # Check if note is newer than last sync
                # AND not already in notifications (first update wins)
                notification_key = f"{record_id}:{note_id}"
                
                if note_timestamp > last_synced and notification_key not in existing_notifications:
                    author = note.get("fields", {}).get("author", "unknown")
                    content = note.get("content", "")
                    
                    # Create summary (first line or first 50 chars)
                    summary = content.split('\n')[0][:50]
                    if len(content) > 50:
                        summary += "..."
                    
                    new_notes.append({
                        "record_id": record_id,
                        "record_title": record_title,
                        "note_id": note_id,
                        "author": author,
                        "summary": summary,
                        "timestamp": note_timestamp
                    })
        
        return new_notes
    
    def add_notifications(self, new_notes):
        """Add notifications to REPO record as multi-value field."""
        if not new_notes:
            return
        
        # Build notification entries
        # Format: record_id:note_id:timestamp:author:summary
        for notif in new_notes:
            entry = (
                f"{notif['record_id']}:"
                f"{notif['note_id']}:"
                f"{notif['timestamp']}:"
                f"{notif['author']}:"
                f"{notif['summary']}"
            )
            
            # Add to notifications field
            self._run_aver_personal(
                "record", "update", self.repo_id,
                "--text-multi", f"notifications+{entry}"
            )
    
    def sync(self):
        """Main sync process."""
        print(f"Syncing notifications from {self.project_name}...")
        
        # Ensure REPO record exists
        self.ensure_repo_record()
        
        # Get last sync time
        last_synced = self.get_last_synced()
        print(f"Last synced: {last_synced}")
        
        # Get existing notifications (to avoid duplicates)
        existing = self.get_existing_notifications()
        
        # Get watched records
        watched = self.get_watched_records()
        print(f"Watching {len(watched)} records")
        
        if not watched:
            print("Not watching any records (not assigned to any issues)")
            self.project_io.terminate()
            return
        
        # Get new notes
        new_notes = self.get_new_notes(last_synced, watched, existing)
        
        if not new_notes:
            print("No new notifications")
        else:
            print(f"Found {len(new_notes)} new notifications")
            
            # Add notifications to personal repo
            self.add_notifications(new_notes)
            
            # Show summary
            for notif in new_notes:
                print(f"  • {notif['record_id']}:{notif['note_id']} - {notif['author']}: {notif['summary']}")
        
        # Update last_synced
        self.update_last_synced()
        
        # Clean up
        self.project_io.terminate()
        
        print(f"\nRun 'aver --location {self.personal_repo} inbox' to view notifications")


def main():
    parser = argparse.ArgumentParser(
        description="Sync aver notifications from project repo to personal repo"
    )
    parser.add_argument(
        "--project-repo",
        required=True,
        help="Path to project repository"
    )
    parser.add_argument(
        "--personal-repo",
        required=True,
        help="Path to personal notification repository"
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Short name for project"
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Username in project repo"
    )
    
    args = parser.parse_args()
    
    syncer = AverNotifySync(
        args.project_repo,
        args.personal_repo,
        args.project_name,
        args.username
    )
    
    syncer.sync()


if __name__ == "__main__":
    main()
```

---

## Inbox Viewer Script

**Completely external tool - not part of aver core.**

### File: `aver-inbox`

```bash
#!/bin/bash
#
# View notifications from personal aver repo
# External tool - uses aver with --location flag

set -e

PERSONAL_REPO="${AVER_PERSONAL_REPO:-$HOME/.aver-personal}"

# Check if personal repo exists
if [ ! -d "$PERSONAL_REPO/.aver" ]; then
    echo "Personal repo not found at $PERSONAL_REPO"
    echo "Run 'aver-notify-sync' first to initialize"
    exit 1
fi

# Run inbox viewer
python3 "$(dirname "$0")/aver-inbox.py" --personal-repo "$PERSONAL_REPO" "$@"
```

### File: `aver-inbox.py`

```python
#!/usr/bin/env python3
"""
Aver inbox viewer - external tool
Displays and manages notifications from personal aver repo
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


class AverInbox:
    """Inbox viewer for personal aver notification repo."""
    
    def __init__(self, personal_repo):
        self.personal_repo = Path(personal_repo)
        self.io_process = None
    
    def _start_io(self):
        """Start JSON IO for personal repo."""
        self.io_process = subprocess.Popen(
            ["aver", "--location", str(self.personal_repo), "json", "io"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    
    def _send_command(self, command, params):
        """Send command to JSON IO."""
        if not self.io_process:
            self._start_io()
        
        request = {"command": command, "params": params}
        self.io_process.stdin.write(json.dumps(request) + "\n")
        self.io_process.stdin.flush()
        
        response = json.loads(self.io_process.stdout.readline())
        return response.get("result") if response.get("success") else None
    
    def _run_aver(self, *args):
        """Run aver command on personal repo."""
        return subprocess.run(
            ["aver", "--location", str(self.personal_repo), *args],
            capture_output=True,
            text=True,
            check=True
        )
    
    def get_all_notifications(self):
        """Get all notifications from all REPO records."""
        # Search for all REPO records
        result = self._send_command("search-records", {"limit": 1000})
        
        if not result or not result.get("records"):
            return []
        
        all_notifications = []
        
        for record_summary in result["records"]:
            record_id = record_summary["id"]
            
            # Only process REPO- records
            if not record_id.startswith("REPO-"):
                continue
            
            # Get full record with fields
            record = self._send_command("export-record", {"record_id": record_id})
            if not record:
                continue
            
            fields = record.get("fields", {})
            repo_name = fields.get("repo_name", record_id)
            repo_path = fields.get("repo_path", "")
            notifications = fields.get("notifications", [])
            
            # Handle single value or list
            if not isinstance(notifications, list):
                notifications = [notifications] if notifications else []
            
            # Parse each notification
            for notif_str in notifications:
                # Format: record_id:note_id:timestamp:author:summary
                parts = notif_str.split(":", 4)
                if len(parts) == 5:
                    all_notifications.append({
                        "repo": repo_name,
                        "repo_id": record_id,
                        "repo_path": repo_path,
                        "record_id": parts[0],
                        "note_id": parts[1],
                        "timestamp": parts[2],
                        "author": parts[3],
                        "summary": parts[4],
                        "raw": notif_str
                    })
        
        # Sort by timestamp (newest first)
        all_notifications.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return all_notifications
    
    def display_notifications(self, notifications):
        """Display notifications."""
        if not notifications:
            print("No notifications")
            return
        
        print(f"\n{'='*70}")
        print(f"  Notifications ({len(notifications)} unread)")
        print(f"{'='*70}\n")
        
        for i, notif in enumerate(notifications[:20], 1):
            print(f"[{i}] {notif['repo']}: {notif['record_id']}:{notif['note_id']}")
            print(f"    {notif['author']}: {notif['summary']}")
            print()
        
        if len(notifications) > 20:
            print(f"  ... and {len(notifications) - 20} more")
            print()
    
    def interactive_mode(self, notifications):
        """Interactive notification management."""
        print("Commands:")
        print("  [number] - View in project repo")
        print("  c [number] - Clear notification")
        print("  a - Clear all")
        print("  q - Quit")
        print()
        
        while notifications:
            try:
                cmd = input("> ").strip()
                
                if cmd == 'q':
                    break
                
                elif cmd == 'a':
                    # Clear all
                    for notif in notifications:
                        self.clear_notification(notif['repo_id'], notif['raw'])
                    print("All notifications cleared")
                    break
                
                elif cmd.startswith('c '):
                    # Clear specific
                    idx = int(cmd.split()[1]) - 1
                    if 0 <= idx < len(notifications):
                        notif = notifications[idx]
                        self.clear_notification(notif['repo_id'], notif['raw'])
                        print("Notification cleared")
                        notifications.pop(idx)
                        
                        # Redisplay
                        if notifications:
                            self.display_notifications(notifications[:10])
                        else:
                            print("No more notifications")
                            break
                
                elif cmd.isdigit():
                    # View in project repo
                    idx = int(cmd) - 1
                    if 0 <= idx < len(notifications):
                        notif = notifications[idx]
                        self.view_in_project(notif)
                        
                        # Auto-clear after viewing
                        self.clear_notification(notif['repo_id'], notif['raw'])
                        notifications.pop(idx)
            
            except (ValueError, IndexError):
                print("Invalid command")
            except KeyboardInterrupt:
                break
    
    def view_in_project(self, notif):
        """Open record/note in project repo."""
        repo_path = notif['repo_path']
        
        if not repo_path or not Path(repo_path).exists():
            print(f"Project repo not found: {repo_path}")
            return
        
        if notif['note_id']:
            # View specific note
            subprocess.run([
                "aver", "--location", repo_path,
                "note", "view", notif['record_id'], notif['note_id']
            ])
        else:
            # View record
            subprocess.run([
                "aver", "--location", repo_path,
                "record", "view", notif['record_id']
            ])
    
    def clear_notification(self, repo_id, notification_entry):
        """Remove notification from REPO record."""
        subprocess.run([
            "aver", "--location", str(self.personal_repo),
            "record", "update", repo_id,
            "--text-multi", f"notifications-{notification_entry}"
        ], check=True, capture_output=True)
    
    def run(self, list_only=False):
        """Main run method."""
        notifications = self.get_all_notifications()
        
        self.display_notifications(notifications)
        
        if notifications and not list_only:
            self.interactive_mode(notifications)
        
        # Clean up
        if self.io_process:
            self.io_process.terminate()


def main():
    parser = argparse.ArgumentParser(
        description="View aver notifications from personal repo"
    )
    parser.add_argument(
        "--personal-repo",
        default=os.path.expanduser("~/.aver-personal"),
        help="Path to personal notification repo"
    )
    parser.add_argument(
        "--list-only",
        action="store_true",
        help="List notifications only (no interactive mode)"
    )
    
    args = parser.parse_args()
    
    inbox = AverInbox(args.personal_repo)
    inbox.run(args.list_only)


if __name__ == "__main__":
    main()
```

---

## Clear Notifications Script

### File: `aver-inbox-clear`

```bash
#!/bin/bash
#
# Clear notifications from personal repo
# External tool - uses aver with --location flag

PERSONAL_REPO="${AVER_PERSONAL_REPO:-$HOME/.aver-personal}"

if [ "$1" = "--all" ]; then
    # Clear all notifications from all REPO records
    for repo_record in "$PERSONAL_REPO"/records/REPO-*.md; do
        if [ -f "$repo_record" ]; then
            repo_id=$(basename "$repo_record" .md)
            aver --location "$PERSONAL_REPO" record update "$repo_id" --text notifications=
            echo "Cleared notifications for $repo_id"
        fi
    done
else
    echo "Usage: aver-inbox-clear --all"
    echo "       (or use 'aver-inbox' interactive mode)"
fi
```

---

## Usage Examples

### View Inbox

```bash
$ aver-inbox

======================================================================
  Notifications (3 unread)
======================================================================

[1] myproject: ISS-042:NT-005
    bob: I've traced this to the LRU eviction...

[2] myproject: ISS-103:NT-012
    charlie: Updated status to in_progress

[3] otherproject: BUG-088:
    dave: Changed priority to high

Commands:
  [number] - View in project repo
  c [number] - Clear notification
  a - Clear all
  q - Quit

> 1
# Opens aver --location ~/work/myproject note view ISS-042 NT-005
# Auto-clears notification after viewing
```

### List Only (Non-Interactive)

```bash
$ aver-inbox --list-only

======================================================================
  Notifications (3 unread)
======================================================================

[1] myproject: ISS-042:NT-005
    bob: I've traced this to the LRU eviction...

[2] myproject: ISS-103:NT-012
    charlie: Updated status to in_progress

[3] otherproject: BUG-088:
    dave: Changed priority to high
```

### Clear All

```bash
$ aver-inbox-clear --all
Cleared notifications for REPO-myproject
Cleared notifications for REPO-otherproject
```

### Manual Clearing

```bash
# View REPO record (using aver directly)
aver --location ~/.aver-personal record view REPO-myproject

# Clear specific notification (using aver directly)
aver --location ~/.aver-personal record update REPO-myproject \
  --text-multi "notifications-ISS-042:NT-005:2025-01-20T14:30:00Z:bob:traced..."

# Clear all for a project (using aver directly)
aver --location ~/.aver-personal record update REPO-myproject \
  --text notifications=
```

---

## Middleware Script

### File: `aver-notify-sync`

```bash
#!/bin/bash
#
# Aver notification sync middleware
# Bridges project repo → personal notification repo

set -e

# Configuration
PROJECT_REPO="${1:-.}"  # Default to current directory
PERSONAL_REPO="${AVER_PERSONAL_REPO:-$HOME/.aver-personal}"

# Ensure personal repo exists
if [ ! -d "$PERSONAL_REPO/.aver" ]; then
    echo "Initializing personal notification repo at $PERSONAL_REPO"
    mkdir -p "$PERSONAL_REPO"
    cd "$PERSONAL_REPO"
    git init
    aver admin init
fi

# Get absolute paths
PROJECT_REPO=$(cd "$PROJECT_REPO" && pwd)

# Get project name from path
PROJECT_NAME=$(basename "$PROJECT_REPO")

# Get user handle from project repo
USER_HANDLE=$(aver --location "$PROJECT_REPO" admin get-id --format handle 2>/dev/null)

if [ -z "$USER_HANDLE" ]; then
    echo "Error: Could not determine user handle in $PROJECT_REPO"
    exit 1
fi

# Run sync script
python3 "$(dirname "$0")/aver-notify-sync.py" \
    --project-repo "$PROJECT_REPO" \
    --personal-repo "$PERSONAL_REPO" \
    --project-name "$PROJECT_NAME" \
    --username "$USER_HANDLE"
```

### File: `aver-notify-sync.py`

```python
#!/usr/bin/env python3
"""
Aver notification sync middleware.
Queries project repo (via JSON IO) and updates personal notification repo.
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


class AverNotifySync:
    """Sync notifications from project repo to personal repo."""
    
    def __init__(self, project_repo, personal_repo, project_name, username):
        self.project_repo = Path(project_repo)
        self.personal_repo = Path(personal_repo)
        self.project_name = project_name
        self.username = username
        self.repo_id = f"REPO-{project_name}"
        
        # Start JSON IO for project repo
        self.project_io = self._start_io(self.project_repo)
    
    def _start_io(self, repo_path):
        """Start persistent JSON IO process for a repo."""
        return subprocess.Popen(
            ["aver", "--location", str(repo_path), "json", "io"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    
    def _send_command(self, process, command, params):
        """Send command to JSON IO process."""
        request = {"command": command, "params": params}
        process.stdin.write(json.dumps(request) + "\n")
        process.stdin.flush()
        
        response = json.loads(process.stdout.readline())
        return response.get("result") if response.get("success") else None
    
    def _run_aver_personal(self, *args, capture=True):
        """Run aver command on personal repo."""
        cmd = ["aver", "--location", str(self.personal_repo), *args]
        if capture:
            return subprocess.run(cmd, capture_output=True, text=True, check=True)
        else:
            return subprocess.run(cmd, check=True)
    
    def ensure_repo_record(self):
        """Ensure REPO record exists in personal repo."""
        # Check if exists
        result = self._run_aver_personal("record", "view", self.repo_id)
        
        if result.returncode != 0:
            # Create REPO record
            self._run_aver_personal(
                "record", "new",
                "--template", "repo",
                "--title", self.project_name,
                "--text", f"repo_path={self.project_repo}",
                "--text", f"repo_name={self.project_name}",
                "--text", f"user_handle={self.username}",
                "--text", f"last_synced=1970-01-01T00:00:00Z",
                "--description", f"Tracking notifications for {self.project_name}"
            )
            print(f"Created {self.repo_id} in personal repo")
    
    def get_last_synced(self):
        """Get last sync timestamp from REPO record."""
        result = self._send_command(
            self.project_io,
            "export-record",
            {"record_id": self.repo_id}
        )
        
        if result:
            return result.get("fields", {}).get("last_synced", "1970-01-01T00:00:00Z")
        
        return "1970-01-01T00:00:00Z"
    
    def update_last_synced(self):
        """Update last_synced timestamp in REPO record."""
        now = datetime.now().isoformat() + "Z"
        self._run_aver_personal(
            "record", "update", self.repo_id,
            "--text", f"last_synced={now}"
        )
    
    def get_watched_records(self):
        """Get records user should be notified about."""
        watched = set()
        
        # Search for records assigned to user
        result = self._send_command(
            self.project_io,
            "search-records",
            {"ksearch": [f"assignee={self.username}"], "limit": 1000}
        )
        
        if result and result.get("records"):
            for record in result["records"]:
                watched.add(record["id"])
        
        # Search for records created by user
        result = self._send_command(
            self.project_io,
            "search-records",
            {"ksearch": [f"created_by={self.username}"], "limit": 1000}
        )
        
        if result and result.get("records"):
            for record in result["records"]:
                watched.add(record["id"])
        
        return watched
    
    def get_new_notes(self, last_synced, watched_records):
        """Find new notes since last sync on watched records."""
        new_notes = []
        
        for record_id in watched_records:
            # Get record with notes
            result = self._send_command(
                self.project_io,
                "export-record",
                {"record_id": record_id, "include_notes": True}
            )
            
            if not result:
                continue
            
            record_title = result.get("fields", {}).get("title", record_id)
            notes = result.get("notes", [])
            
            for note in notes:
                note_timestamp = note.get("fields", {}).get("timestamp", "")
                
                # Check if note is newer than last sync
                if note_timestamp > last_synced:
                    note_id = note.get("id")
                    author = note.get("fields", {}).get("author", "unknown")
                    content = note.get("content", "")
                    
                    new_notes.append({
                        "record_id": record_id,
                        "record_title": record_title,
                        "note_id": note_id,
                        "author": author,
                        "content": content[:200],  # First 200 chars
                        "timestamp": note_timestamp
                    })
        
        return new_notes
    
    def add_notification(self, notif):
        """Add notification to personal repo."""
        # Build notification message
        message = f"**{notif['author']}** commented on {notif['record_id']}: {notif['record_title']}\n\n"
        message += f"{notif['content']}\n\n"
        message += f"[View in project](file://{self.project_repo}/records/{notif['record_id']}.md)"
        
        # Add note to REPO record
        self._run_aver_personal(
            "note", "add", self.repo_id,
            "--message", message,
            "--text", f"source_record={notif['record_id']}",
            "--text", f"source_note={notif['note_id']}",
            "--text", "notification_type=new_comment",
            "--text", "read=false"
        )
    
    def sync(self):
        """Main sync process."""
        print(f"Syncing notifications from {self.project_name}...")
        
        # Ensure REPO record exists
        self.ensure_repo_record()
        
        # Get last sync time (from personal repo, not project)
        # We need to read from personal repo directly
        result = subprocess.run(
            ["aver", "--location", str(self.personal_repo), 
             "record", "view", self.repo_id],
            capture_output=True, text=True
        )
        
        # Parse last_synced from output (quick and dirty)
        last_synced = "1970-01-01T00:00:00Z"
        for line in result.stdout.split('\n'):
            if 'last_synced:' in line:
                last_synced = line.split(':', 1)[1].strip()
                break
        
        print(f"Last synced: {last_synced}")
        
        # Get watched records
        watched = self.get_watched_records()
        print(f"Watching {len(watched)} records")
        
        if not watched:
            print("Not watching any records (not assigned to any issues)")
            self.project_io.terminate()
            return
        
        # Get new notes
        new_notes = self.get_new_notes(last_synced, watched)
        
        if not new_notes:
            print("No new notifications")
        else:
            print(f"Found {len(new_notes)} new notifications")
            
            # Add notifications to personal repo
            for notif in new_notes:
                self.add_notification(notif)
                print(f"  • {notif['record_id']}:{notif['note_id']} - {notif['author']}")
        
        # Update last_synced
        self.update_last_synced()
        
        # Clean up
        self.project_io.terminate()
        
        print(f"\nRun 'aver --location {self.personal_repo} inbox' to view notifications")


def main():
    parser = argparse.ArgumentParser(
        description="Sync aver notifications from project repo to personal repo"
    )
    parser.add_argument(
        "--project-repo",
        required=True,
        help="Path to project repository"
    )
    parser.add_argument(
        "--personal-repo",
        required=True,
        help="Path to personal notification repository"
    )
    parser.add_argument(
        "--project-name",
        required=True,
        help="Short name for project"
    )
    parser.add_argument(
        "--username",
        required=True,
        help="Username in project repo"
    )
    
    args = parser.parse_args()
    
    syncer = AverNotifySync(
        args.project_repo,
        args.personal_repo,
        args.project_name,
        args.username
    )
    
    syncer.sync()


if __name__ == "__main__":
    main()
```

---

## Git Hook Integration

**`.git/hooks/post-checkout`** (in project repo):

```bash
#!/bin/bash
#
# After checkout/pull, sync notifications to personal repo

# Only run on branch checkout
if [ "$3" = "0" ]; then
    exit 0
fi

# Run notification sync
if command -v aver-notify-sync >/dev/null 2>&1; then
    aver-notify-sync "$(pwd)" 2>&1 | head -5
fi
```

---

## Personal Repo Setup

### Initialize Once

```bash
# Create personal notification repo
mkdir -p ~/.aver-personal
cd ~/.aver-personal

# Initialize git (optional, for syncing across machines)
git init
git remote add origin git@github.com:alice/aver-personal.git

# Initialize aver
aver admin init

# Add REPO template config
cat > .aver/config.toml << 'EOF'
[template.repo]
record_prefix = "REPO"
note_prefix = "NOTIF"
description = "Repository notification tracking"

# ... (template config from above)
EOF

# Initial commit
git add .
git commit -m "Initialize personal notification repo"
git push -u origin main
```

### Sync Across Machines

```bash
# On laptop
cd ~/.aver-personal
git pull  # Get notifications from other machines
git push  # Share notifications

# On desktop
cd ~/.aver-personal  
git pull  # Get notifications from laptop
```

---

## Usage Workflow

### Day-to-Day Use

```bash
# Work on project
cd ~/work/myproject

# Pull latest changes (hook runs sync automatically)
git pull
# → Syncing notifications from myproject...
# → Found 3 new notifications
# →   • ISS-042:NT-005 - bob
# →   • ISS-103:NT-012 - charlie
# →   • ISS-088:NT-003 - dave
# → Run 'aver --location ~/.aver-personal inbox' to view

# View notifications
aver --location ~/.aver-personal inbox
# Shows list of unread notifications

# Or use alias
alias aver-inbox='aver --location ~/.aver-personal inbox'
aver-inbox
```

### Manual Sync

```bash
# Sync specific project
aver-notify-sync ~/work/myproject

# Sync all projects (if you track multiple)
for proj in ~/work/*/; do
    if [ -d "$proj/.aver" ]; then
        aver-notify-sync "$proj"
    fi
done
```

### View Notifications

```bash
# List all notifications across all projects
aver --location ~/.aver-personal record list

# View specific project notifications
aver --location ~/.aver-personal note list REPO-myproject

# Search unread
aver --location ~/.aver-personal note search --ksearch read=false

# Mark as read
aver --location ~/.aver-personal note update REPO-myproject NT-005 --text read=true
```

---

## Branch Awareness Analysis

### Your Insight: "We probably don't even really need to worry about which branch we are in"

**You're absolutely right!** Here's why:

1. **last_synced timestamp handles it:**
   ```
   If on older branch:
     last_synced = 2025-01-20T14:30:00Z
     Current branch timestamp = 2025-01-19 (older)
     No new notifications (timestamp filter)
   
   If rebase to master:
     New notes appear with timestamp > 2025-01-20
     Notifications triggered
   ```

2. **Each rebase brings in new notes:**
   ```bash
   git rebase master  # Pulls in new ISS-*/NT-* files
   # Hook runs sync
   # Detects new notes with timestamp > last_synced
   ```

3. **Working on feature branch:**
   ```bash
   # You're on feature-branch
   git rebase master  # Every few hours
   # Sync detects new notes from master
   # You stay current without switching branches
   ```

4. **Even if you don't rebase often:**
   ```
   Eventually you merge/rebase:
     New notes appear
     Sync catches up
     Notifications might be "late" but they arrive
   ```

**Conclusion:** Branch is irrelevant. Timestamp-based sync handles everything correctly.

---

## Benefits of This Design

### 1. Zero Repository Pollution ✅
- Project repo stays clean
- No USER records
- No merge conflicts
- Team doesn't see your notification state

### 2. Portable Notification State ✅
- Personal repo is full git repository
- Sync across machines via `git push/pull`
- Backup via git remote
- Can be private (GitHub/GitLab private repo)

### 3. External to Aver Core ✅
- Middleware script, not aver modification
- Uses public JSON IO interface
- Can evolve independently
- Users opt-in

### 4. Multi-Project Support ✅
- One personal repo tracks many project repos
- `REPO-project1`, `REPO-project2`, etc.
- All notifications in one place
- Single `aver inbox` command

### 5. Flexible Storage ✅
- Personal repo can be anywhere
- Default: `~/.aver-personal`
- Environment variable: `AVER_PERSONAL_REPO`
- Or specify explicitly

### 6. Read-Only Access to Project ✅
- Only uses JSON IO (read operations)
- Never modifies project repo
- Safe to run automatically
- No permission issues

---

## Advanced Features

### Watch Management (Future)

Could add explicit watch tracking in REPO record:

```toml
[template.repo.record_special_fields.explicit_watches]
type = "multi"
value_type = "string"
editable = true
enabled = true
# Manual watches: ISS-042, ISS-088, etc.
```

```bash
# Add explicit watch
aver --location ~/.aver-personal record update REPO-myproject \
    --text-multi "explicit_watches+ISS-042"

# Sync respects explicit watches
```

### @Mention Detection (Future)

```python
def check_mentions(self, record_id):
    """Check if user is @mentioned in notes."""
    result = self._send_command(
        self.project_io,
        "export-record",
        {"record_id": record_id, "include_notes": True}
    )
    
    mention_pattern = f"@{self.username}"
    
    for note in result.get("notes", []):
        if mention_pattern in note.get("content", ""):
            return True
    
    return False
```

### Notification Digest (Future)

```bash
# Daily digest email
aver --location ~/.aver-personal note search --ksearch read=false \
    | mail -s "Daily Aver Notifications" alice@example.com
```

---

## Installation

### One-Time Setup

```bash
# Install middleware script
sudo cp aver-notify-sync /usr/local/bin/
sudo cp aver-notify-sync.py /usr/local/bin/
sudo chmod +x /usr/local/bin/aver-notify-sync*

# Initialize personal repo
mkdir -p ~/.aver-personal
cd ~/.aver-personal
git init
aver admin init

# Add template config
# (copy REPO template config to .aver/config.toml)

# Optional: Add git remote for sync
git remote add origin git@github.com:alice/aver-personal.git
git push -u origin main

# Install hooks in each project repo
cd ~/work/myproject
cp /path/to/post-checkout .git/hooks/
chmod +x .git/hooks/post-checkout
```

### Alias for Convenience

```bash
# Add to ~/.bashrc or ~/.zshrc
alias aver-inbox='aver --location ~/.aver-personal inbox'
alias aver-sync='aver-notify-sync $(pwd)'
```

---

## Summary

This design gives you:

✅ **Clean project repo** - No notification pollution
✅ **Portable state** - Personal repo syncs via git
✅ **No merge conflicts** - Personal repo is yours alone
✅ **External tool** - Not part of aver core
✅ **Branch agnostic** - Timestamp-based sync just works
✅ **Multi-project** - One personal repo for all projects
✅ **Simple** - Uses aver's existing features (JSON IO, templates)

The middleware pattern is brilliant because it:
- Keeps aver simple (no notification features needed)
- Gives users full control (personal repo, their rules)
- Enables git-based sync (portable across machines)
- Avoids merge conflicts (separate repos)

This is exactly what you described: "middleware script that references two different aver databases."
