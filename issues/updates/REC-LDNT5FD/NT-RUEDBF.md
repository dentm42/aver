---
incident_id__string: REC-LDNT5FD
---

## Record Data

### Content

* FEATURE - addon scripting
* NOTE: requires no_note field config variable and ```admin get-id``` command

# Git Hook-Based Notification System for Aver

## Executive Summary

**Even simpler:** Run notification updates as a **git post-checkout hook** that updates only the current user's record. No daemon, no polling, no filesystem watching. Just a hook that runs after `git pull` or `git checkout`.

**Key simplifications:**
1. **Git hook** - Runs automatically after checkout/pull
2. **Current user only** - Only update my own USER record
3. **Last check timestamp** - Store in USER record itself
4. **New command** - `aver admin get-id` returns current user handle

---

## Architecture

```
Developer pulls changes:
    $ git pull
         ↓
    Git runs post-checkout hook
         ↓
    .git/hooks/post-checkout
         ↓
    1. Get current user: aver admin get-id
    2. Get last check time from USER-{user} record
    3. Query SQLite for changes since then
    4. Update USER-{user}.notifications field
    5. Save current timestamp to USER-{user}.last_updated
         ↓
    Developer sees: "You have 3 new notifications"
         ↓
    Developer checks inbox:
    $ aver inbox
```

**That's it!** No background processes, no daemon, no complexity.

---

## New Aver Command: `admin get-id`

### Purpose

Return the current user's handle for use in scripts.

### Implementation in aver.py

```python
def _cmd_admin_get_id(self, args):
    """Get current user identity."""
    user = self.effective_user
    
    if args.format == "json":
        print(json.dumps({
            "handle": user["handle"],
            "email": user["email"]
        }))
    elif args.format == "handle":
        print(user["handle"])
    elif args.format == "email":
        print(user["email"])
    else:
        # Default: both
        print(f"{user['handle']} <{user['email']}>")
```

### CLI Setup

```python
# In setup_commands()
admin_get_id_parser = admin_subparsers.add_parser(
    "get-id",
    help="Get current user identity"
)
admin_get_id_parser.add_argument(
    "--format",
    choices=["default", "handle", "email", "json"],
    default="default",
    help="Output format"
)
```

### Usage

```bash
# Get handle only
$ aver admin get-id --format handle
alice

# Get email only
$ aver admin get-id --format email
alice@company.com

# Get both (default)
$ aver admin get-id
alice <alice@company.com>

# Get JSON (for scripts)
$ aver admin get-id --format json
{"handle": "alice", "email": "alice@company.com"}
```

---

## User Record Structure

### USER Record with Last Updated Timestamp

**`records/USER-alice.md`:**
```markdown
---
title: alice
record_type: user
user_handle: alice
email: alice@company.com
created_timestamp: 2025-01-15T10:00:00Z
last_modified_timestamp: 2025-01-20T14:30:00Z
last_updated: 2025-01-20T14:30:00Z
notifications:
  - ISS-042:NT-001:eve updated priority to high
  - ISS-103::New issue assigned to you
  - ISS-201:NT-005:bob commented
---

User profile for alice.
The last_updated field tracks when notifications were last checked.
```

### Field Configuration

**In `.aver/config.toml`:**
```toml
[record_special_fields.record_type]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
accepted_values = ["issue", "user", "template"]
default = "issue"
index_values = true

[record_special_fields.user_handle]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
index_values = true

[record_special_fields.last_updated]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false
no_note = true  # Changes don't create update notes

[record_special_fields.notifications]
type = "multi"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false
no_note = true  # Changes don't create update notes
```

---

## Git Post-Checkout Hook

### File: `.git/hooks/post-checkout`

```bash
#!/bin/bash
#
# Git post-checkout hook for aver notifications
# Runs after: git pull, git checkout
#
# This hook updates the current user's notification list based on
# changes pulled from the remote repository.

# Exit if not moving to a branch (e.g., during rebase)
if [ "$3" = "0" ]; then
    exit 0
fi

# Change to repo root
cd "$(git rev-parse --show-toplevel)"

# Only run if .aver directory exists
if [ ! -d ".aver" ]; then
    exit 0
fi

# Only run if aver.py exists
if [ ! -f "aver.py" ]; then
    exit 0
fi

# Get current user handle
USER_HANDLE=$(python3 aver.py admin get-id --format handle 2>/dev/null)

if [ -z "$USER_HANDLE" ]; then
    # Can't determine user, skip
    exit 0
fi

# Run notification updater script
python3 .git/hooks/aver-update-notifications.py "$USER_HANDLE" 2>&1 | grep -v "^$"

exit 0
```

### File: `.git/hooks/aver-update-notifications.py`

```python
#!/usr/bin/env python3
"""
Update notifications for current user after git pull.
Called by post-checkout hook.
"""

import sys
import json
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from typing import List, Tuple, Set


def send_json_command(command: str, params: dict) -> dict:
    """Send command to aver via JSON IO."""
    proc = subprocess.Popen(
        ["python3", "aver.py", "json", "io"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    request = {"command": command, "params": params}
    proc.stdin.write(json.dumps(request) + "\n")
    proc.stdin.flush()
    
    response_line = proc.stdout.readline()
    proc.terminate()
    
    if not response_line:
        return None
    
    response = json.loads(response_line)
    return response.get("result") if response.get("success") else None


def get_last_updated(user_handle: str) -> str:
    """Get last_updated timestamp from user record."""
    user_record_id = f"USER-{user_handle}"
    
    result = send_json_command("export-record", {"record_id": user_record_id})
    
    if not result:
        # User record doesn't exist yet
        return "1970-01-01T00:00:00Z"
    
    return result["fields"].get("last_updated", "1970-01-01T00:00:00Z")


def ensure_user_record_exists(user_handle: str):
    """Create user record if it doesn't exist."""
    user_record_id = f"USER-{user_handle}"
    
    # Check if exists
    result = send_json_command("export-record", {"record_id": user_record_id})
    if result:
        return  # Already exists
    
    # Create user record
    subprocess.run([
        "python3", "aver.py",
        "record", "new",
        "--title", user_handle,
        "--text", f"record_type=user",
        "--text", f"user_handle={user_handle}",
        "--description", f"User profile for {user_handle}"
    ], check=True, capture_output=True)


def get_changes_since(last_updated: str) -> List[Tuple[str, str, str]]:
    """
    Query SQLite for changes since last_updated.
    Returns: List of (record_id, note_id or '', description)
    """
    db_path = Path(".aver/index.db")
    if not db_path.exists():
        return []
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    changes = []
    
    # Find new/updated records (excluding USER- records)
    cursor.execute("""
        SELECT id, last_modified_timestamp 
        FROM incidents 
        WHERE last_modified_timestamp > ? 
          AND id NOT LIKE 'USER-%'
        ORDER BY last_modified_timestamp
    """, (last_updated,))
    
    records = cursor.fetchall()
    
    for record_id, _ in records:
        # Check for new notes on this record
        cursor.execute("""
            SELECT id, created_timestamp
            FROM updates
            WHERE incident_id = ?
              AND created_timestamp > ?
            ORDER BY created_timestamp DESC
            LIMIT 1
        """, (record_id, last_updated))
        
        note_row = cursor.fetchone()
        
        if note_row:
            note_id = note_row[0]
            
            # Get note author
            cursor.execute("""
                SELECT value_string 
                FROM kv_store 
                WHERE incident_id = ? 
                  AND update_id = ? 
                  AND key = 'author'
            """, (record_id, note_id))
            
            author_row = cursor.fetchone()
            author = author_row[0] if author_row else "unknown"
            description = f"{author} commented"
            
            changes.append((record_id, note_id, description))
        else:
            # Record modified without new note (metadata change)
            cursor.execute("""
                SELECT value_string 
                FROM kv_store 
                WHERE incident_id = ? 
                  AND update_id IS NULL 
                  AND key = 'last_modified_by'
            """, (record_id,))
            
            author_row = cursor.fetchone()
            author = author_row[0] if author_row else "unknown"
            description = f"{author} updated"
            
            changes.append((record_id, "", description))
    
    conn.close()
    return changes


def get_interested_records(user_handle: str) -> Set[str]:
    """
    Get list of record IDs that this user is interested in.
    Returns: Set of record_ids where user is assignee, watcher, or creator
    """
    db_path = Path(".aver/index.db")
    if not db_path.exists():
        return set()
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    record_ids = set()
    
    # Records where user is assignee
    cursor.execute("""
        SELECT incident_id 
        FROM kv_store 
        WHERE key = 'assignee' 
          AND update_id IS NULL
          AND value_string = ?
    """, (user_handle,))
    record_ids.update(row[0] for row in cursor.fetchall())
    
    # Records where user is a watcher
    cursor.execute("""
        SELECT incident_id 
        FROM kv_store 
        WHERE key = 'watchers' 
          AND update_id IS NULL
          AND value_string = ?
    """, (user_handle,))
    record_ids.update(row[0] for row in cursor.fetchall())
    
    # Records created by user
    cursor.execute("""
        SELECT id 
        FROM incidents 
        WHERE created_by = ?
    """, (user_handle,))
    record_ids.update(row[0] for row in cursor.fetchall())
    
    conn.close()
    return record_ids


def get_existing_notifications(user_handle: str) -> Set[str]:
    """Get set of record IDs already in notifications."""
    user_record_id = f"USER-{user_handle}"
    
    result = send_json_command("export-record", {"record_id": user_record_id})
    
    if not result:
        return set()
    
    notifications = result["fields"].get("notifications", [])
    if not isinstance(notifications, list):
        notifications = [notifications] if notifications else []
    
    # Extract record IDs (before first colon)
    return {n.split(":")[0] for n in notifications}


def add_notifications(user_handle: str, new_notifications: List[Tuple[str, str, str]]):
    """Add new notifications to user record."""
    if not new_notifications:
        return
    
    user_record_id = f"USER-{user_handle}"
    
    # Build notification entries
    for record_id, note_id, description in new_notifications:
        entry = f"{record_id}:{note_id}:{description}"
        
        # Add to notifications field
        subprocess.run([
            "python3", "aver.py",
            "record", "update", user_record_id,
            "--text-multi", f"notifications+{entry}"
        ], check=True, capture_output=True)


def update_last_updated(user_handle: str):
    """Update last_updated timestamp in user record."""
    user_record_id = f"USER-{user_handle}"
    current_time = datetime.now().isoformat() + "Z"
    
    subprocess.run([
        "python3", "aver.py",
        "record", "update", user_record_id,
        "--text", f"last_updated={current_time}"
    ], check=True, capture_output=True)


def main():
    if len(sys.argv) != 2:
        print("Usage: aver-update-notifications.py <user_handle>")
        sys.exit(1)
    
    user_handle = sys.argv[1]
    
    # Ensure user record exists
    ensure_user_record_exists(user_handle)
    
    # Get last check time
    last_updated = get_last_updated(user_handle)
    
    # Get changes since then
    all_changes = get_changes_since(last_updated)
    
    if not all_changes:
        # No changes, just update timestamp
        update_last_updated(user_handle)
        return
    
    # Get records user is interested in
    interested_records = get_interested_records(user_handle)
    
    # Filter changes to only interested records
    relevant_changes = [
        (record_id, note_id, desc)
        for record_id, note_id, desc in all_changes
        if record_id in interested_records
    ]
    
    if not relevant_changes:
        # No relevant changes
        update_last_updated(user_handle)
        return
    
    # Get existing notifications to implement "first update wins"
    existing_record_ids = get_existing_notifications(user_handle)
    
    # Filter out records that already have notifications
    new_notifications = [
        (record_id, note_id, desc)
        for record_id, note_id, desc in relevant_changes
        if record_id not in existing_record_ids
    ]
    
    if new_notifications:
        # Add new notifications
        add_notifications(user_handle, new_notifications)
        
        # Print summary
        print(f"✓ {len(new_notifications)} new notification(s) for {user_handle}")
        print("  Run 'aver inbox' to view")
    
    # Update last_updated timestamp
    update_last_updated(user_handle)


if __name__ == "__main__":
    main()
```

---

## Inbox Command

### New Command: `aver inbox`

Add to aver.py:

```python
def _cmd_inbox(self, args):
    """View and manage notifications."""
    user_handle = self.effective_user["handle"]
    user_record_id = f"USER-{user_handle}"
    
    # Get user record
    user_record = self.get_incident(user_record_id)
    if not user_record:
        print(f"No notifications for {user_handle}")
        return
    
    # Get notifications
    notifications = user_record.get_values("notifications") or []
    
    if not notifications:
        print(f"No notifications for {user_handle}")
        return
    
    # Display notifications
    print(f"\n{'='*70}")
    print(f"  Notifications for {user_handle} ({len(notifications)} unread)")
    print(f"{'='*70}\n")
    
    for i, notif in enumerate(notifications, 1):
        parts = notif.split(":", 2)
        if len(parts) == 3:
            record_id, note_id, description = parts
            note_part = f":{note_id}" if note_id else ""
            
            print(f"[{i}] {record_id}{note_part}")
            print(f"    {description}")
            print()
    
    # Interactive mode if not --list-only
    if not args.list_only:
        self._inbox_interactive(user_record_id, notifications)


def _inbox_interactive(self, user_record_id: str, notifications: List[str]):
    """Interactive inbox management."""
    print("Commands:")
    print("  [number] - View record/note")
    print("  c [number] - Clear notification")
    print("  a - Clear all")
    print("  q - Quit")
    print()
    
    while True:
        try:
            cmd = input("> ").strip()
            
            if cmd == 'q':
                break
            elif cmd == 'a':
                # Clear all
                for notif in notifications:
                    self._clear_notification(user_record_id, notif)
                print("All notifications cleared")
                break
            elif cmd.startswith('c '):
                # Clear specific
                idx = int(cmd.split()[1]) - 1
                if 0 <= idx < len(notifications):
                    self._clear_notification(user_record_id, notifications[idx])
                    print("Notification cleared")
                    notifications.pop(idx)
                    if notifications:
                        self._display_notifications_compact(notifications)
                    else:
                        print("No more notifications")
                        break
            elif cmd.isdigit():
                # View
                idx = int(cmd) - 1
                if 0 <= idx < len(notifications):
                    parts = notifications[idx].split(":", 2)
                    record_id = parts[0]
                    note_id = parts[1] if len(parts) > 1 and parts[1] else None
                    
                    if note_id:
                        # View note
                        subprocess.run([
                            sys.executable, __file__,
                            "note", "view", record_id, note_id
                        ])
                    else:
                        # View record
                        subprocess.run([
                            sys.executable, __file__,
                            "record", "view", record_id
                        ])
        except (ValueError, IndexError):
            print("Invalid command")
        except KeyboardInterrupt:
            break


def _clear_notification(self, user_record_id: str, notification: str):
    """Remove notification from user record."""
    # Use multi-value remove operation
    subprocess.run([
        sys.executable, __file__,
        "record", "update", user_record_id,
        "--text-multi", f"notifications-{notification}"
    ], check=True, capture_output=True)
```

### CLI Setup

```python
# In setup_commands()
inbox_parser = self.subparsers.add_parser(
    "inbox",
    help="View and manage notifications"
)
inbox_parser.add_argument(
    "--list-only",
    action="store_true",
    help="List notifications only (no interactive mode)"
)
```

---

## Installation

### 1. Configure Aver

Add to `.aver/config.toml`:
```toml
[record_special_fields.record_type]
type = "single"
value_type = "string"
editable = false
enabled = true
accepted_values = ["issue", "user"]
default = "issue"
index_values = true

[record_special_fields.last_updated]
type = "single"
value_type = "string"
editable = true
enabled = true
no_note = true

[record_special_fields.notifications]
type = "multi"
value_type = "string"
editable = true
enabled = true
no_note = true
```

### 2. Install Git Hook

```bash
# Copy post-checkout hook
cp post-checkout .git/hooks/post-checkout
chmod +x .git/hooks/post-checkout

# Copy notification updater
cp aver-update-notifications.py .git/hooks/
chmod +x .git/hooks/aver-update-notifications.py
```

### 3. Initialize Your User Record

```bash
# First time: create your user record
aver admin get-id  # Verify it works

# Hook will create USER record on first pull
```

---

## Usage Workflow

### Daily Workflow

```bash
# Pull changes (hook runs automatically)
$ git pull
remote: Counting objects: 5, done.
remote: Compressing objects: 100% (5/5), done.
remote: Total 5 (delta 2), reused 0 (delta 0)
Unpacking objects: 100% (5/5), done.
From github.com:company/project
   abc1234..def5678  main       -> origin/main
Updating abc1234..def5678
Fast-forward
 records/ISS-042.md | 2 +-
 updates/ISS-042/NT-005.md | 12 ++++++++++++
 2 files changed, 13 insertions(+), 1 deletion(-)
 create mode 100644 updates/ISS-042/NT-005.md

✓ 2 new notification(s) for alice
  Run 'aver inbox' to view

# Check inbox
$ aver inbox

======================================================================
  Notifications for alice (2 unread)
======================================================================

[1] ISS-042:NT-005
    bob commented

[2] ISS-103:
    eve updated priority

Commands:
  [number] - View record/note
  c [number] - Clear notification
  a - Clear all
  q - Quit

> 1
# Opens ISS-042/NT-005 for viewing

> c 1
Notification cleared

[1] ISS-103:
    eve updated priority

> c 1
Notification cleared

No more notifications
```

### Checking Notifications (Non-Interactive)

```bash
# Just list
$ aver inbox --list-only

======================================================================
  Notifications for alice (2 unread)
======================================================================

[1] ISS-042:NT-005
    bob commented

[2] ISS-103:
    eve updated priority
```

### Script Usage

```bash
# Get current user
USER=$(aver admin get-id --format handle)
echo "Current user: $USER"

# Check if notifications exist
if aver inbox --list-only 2>&1 | grep -q "unread"; then
    echo "You have notifications!"
fi
```

---

## Benefits

### ✅ **No Daemon Required**
- Runs only when needed (after git pull)
- No background processes
- No system resources when idle

### ✅ **Automatic**
- Hook runs transparently
- Developer doesn't need to remember
- Always up-to-date after pulls

### ✅ **Per-User**
- Each developer sees their own notifications
- No shared state to manage
- Works offline (no network needed)

### ✅ **Efficient**
- Only checks since last update
- Uses SQLite indexes for fast queries
- Minimal overhead

### ✅ **Simple**
- One hook script
- One Python helper
- One aver command

### ✅ **Git-Friendly**
- USER records versioned like any record
- Merge conflicts rare (per-user data)
- Easy to inspect/debug

### ✅ **Easy to Disable**
```bash
# Just remove the hook
rm .git/hooks/post-checkout
```

---

## Advanced Features

### Team Setup Script

**`scripts/setup-notifications.sh`:**
```bash
#!/bin/bash
#
# Setup aver notifications for your local repo

echo "Setting up aver notifications..."

# Check if aver.py exists
if [ ! -f "aver.py" ]; then
    echo "Error: aver.py not found"
    exit 1
fi

# Check if .aver exists
if [ ! -d ".aver" ]; then
    echo "Error: .aver directory not found. Initialize aver first."
    exit 1
fi

# Copy hooks
echo "Installing git hooks..."
cp scripts/git-hooks/post-checkout .git/hooks/
cp scripts/git-hooks/aver-update-notifications.py .git/hooks/
chmod +x .git/hooks/post-checkout
chmod +x .git/hooks/aver-update-notifications.py

# Verify user ID
USER_HANDLE=$(python3 aver.py admin get-id --format handle 2>/dev/null)

if [ -z "$USER_HANDLE" ]; then
    echo "Error: Could not determine user handle"
    exit 1
fi

echo "✓ Notifications configured for: $USER_HANDLE"
echo ""
echo "The post-checkout hook will automatically run after 'git pull'"
echo "to update your notifications."
echo ""
echo "Check your inbox: aver inbox"
```

### Notification Count in Prompt

**Add to `~/.bashrc` or `~/.zshrc`:**
```bash
# Show aver notification count in prompt
aver_notifications() {
    if [ -f "aver.py" ] && [ -d ".aver" ]; then
        COUNT=$(aver inbox --list-only 2>/dev/null | grep -oE '[0-9]+ unread' | grep -oE '[0-9]+')
        if [ -n "$COUNT" ] && [ "$COUNT" -gt 0 ]; then
            echo " [📫 $COUNT]"
        fi
    fi
}

# Add to PS1
PS1='$(aver_notifications)'$PS1
```

### Desktop Notification (Optional)

**Enhance hook to show desktop notification:**
```bash
# At end of .git/hooks/post-checkout

NOTIF_COUNT=$(python3 .git/hooks/aver-update-notifications.py "$USER_HANDLE" 2>&1 | grep -oE '[0-9]+ new' | grep -oE '[0-9]+')

if [ -n "$NOTIF_COUNT" ] && [ "$NOTIF_COUNT" -gt 0 ]; then
    # macOS
    if command -v osascript >/dev/null; then
        osascript -e "display notification \"$NOTIF_COUNT new notification(s)\" with title \"Aver\""
    fi
    
    # Linux
    if command -v notify-send >/dev/null; then
        notify-send "Aver" "$NOTIF_COUNT new notification(s)"
    fi
fi
```

---

## Comparison with Daemon Approach

| Feature | Git Hook | Daemon |
|---------|----------|--------|
| Background process | ❌ No | ✅ Yes |
| Real-time updates | ❌ On pull only | ✅ Immediate |
| Setup complexity | ✅ Simple | ❌ Complex |
| System resources | ✅ Minimal | ❌ Continuous |
| Reliability | ✅ No failure modes | ❌ Can crash |
| Multi-user | ✅ Automatic | ❌ Need config |
| Debugging | ✅ Easy | ❌ Hard |

**Recommendation:** Git hook is simpler and sufficient for most teams. Daemon only needed for real-time requirements.

---

## Summary

This approach is **dramatically simpler** than a daemon:

✅ **One git hook** - Runs after `git pull`
✅ **One Python script** - Updates notifications
✅ **One aver command** - `aver inbox` to view
✅ **New admin command** - `aver admin get-id` for scripts
✅ **No background process** - Only runs when needed
✅ **Per-user automatic** - Just works after pulling
✅ **Easy to install** - Copy two files
✅ **Easy to disable** - Remove one file

Perfect for teams using git to sync their aver repository!1


---

**title:** aver inbox / notifications addon scripting
**type:** feature
**status:** new
**created_at:** 2026-02-20 09:51:49
**created_by_username:** mattd
**updated_at:** 2026-02-20 09:51:49



