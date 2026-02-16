# Aver Quick Start Guide

## What is Aver?

Aver is a lightweight knowledge tracking tool that stores structured data in **plain Markdown files**. Think of it as a flexible issue tracker, note-taking system, or knowledge base where your data stays readable and portable.

**Key Concept**: Aver manages **records** (the things you're tracking) and **notes** (chronological updates to those records). Everything is stored as text files with YAML frontmatter for metadata.

---

## Installation

```bash
# Install dependencies
pip install pyyaml tomli tomli_w

# Make executable and add to PATH
chmod +x aver.py
sudo ln -s /path/to/aver.py /usr/local/bin/aver
```

---

## Basic Workflow

### 1. Initialize a Database

```bash
cd /path/to/your/project
aver admin init
```

This creates:
- `.aver/` directory with config and SQLite index
- `records/` directory for your data
- `updates/` directory for notes

### 2. Set Your User Info

```bash
aver admin config set-user --handle yourname --email you@example.com
```

### 3. Create Your First Record

```bash
aver record new --title "Fix login bug" --status open
```

This opens your editor (set via `$EDITOR`) with a template. Save and close to create the record.

### 4. Add a Note to the Record

```bash
aver note add REC-001 --message "Investigated - issue is in auth module"
```

### 5. Search and List

```bash
# List all records
aver record list

# Search by field
aver record search --ksearch status=open

# View a specific record
aver record view REC-001

# List notes for a record
aver note list REC-001
```

---

## Understanding Fields

Aver has two types of fields:

### Special Fields (Configured)
- Defined in your `config.toml`
- Validated and can be auto-populated
- Appear in YAML without type hints
- Can be required, have defaults, or be auto-generated

**Example**: `title`, `status`, `created_by`, `author`

### Custom Fields (Ad-hoc)
- Created on-the-fly
- No validation
- Appear in YAML with type hints like `myfield__string`

**Example**: `--text server=web-01 --number port=8080`

---

## Common Commands

### Records

```bash
# Create with editor
aver record new

# Create with fields
aver record new --title "Task name" --status open --priority high

# See available fields for your config
aver record new --help-fields

# Update a record
aver record update REC-001 --status closed

# Import from file
aver record new --from-file record.md
```

### Notes

```bash
# Add with editor
aver note add REC-001

# Add with message
aver note add REC-001 --message "Fixed and tested"

# See available fields for this record's notes
aver note add REC-001 --help-fields

# Search notes
aver note search --ksearch category=bugfix
```

---

## Templates (Optional but Powerful)

Templates let you define different field sets for different record types. For example:

**Bug Template** (`config.toml`):
```toml
[template.bug]
record_prefix = "BUG"
note_prefix = "COMMENT"

[template.bug.record_special_fields.severity]
type = "single"
value_type = "integer"
accepted_values = ["1", "2", "3", "4", "5"]
default = "3"

[template.bug.note_special_fields.category]
type = "single"
value_type = "string"
accepted_values = ["investigation", "bugfix", "workaround"]
```

**Usage**:
```bash
# Create bug with custom ID prefix
aver record new --template bug --title "App crashes on login" --severity 2

# Add categorized note
aver note add BUG-001 --message "Root cause found" --category investigation
```

---

## File Structure

```
project/
├── .aver/
│   ├── aver.db          # SQLite index (ignore in Git)
│   └── config.toml      # Your field definitions
├── records/
│   ├── REC-001.md       # A record
│   └── BUG-042.md       # Another record
└── updates/
    ├── REC-001/
    │   ├── NT-001.md    # A note
    │   └── NT-002.md    # Another note
    └── BUG-042/
        └── COMMENT-001.md
```

**Record file** (`REC-001.md`):
```markdown
---
title: Fix login bug
status: open
priority: high
created_by: alice
created_at: 2024-02-15 10:30:00
---
Users cannot log in when using special characters in password.
Affects approximately 5% of users.
```

**Note file** (`NT-001.md`):
```markdown
---
author: alice
timestamp: 2024-02-15 11:00:00
category: investigation
---
Investigated the issue. Found that password validation
is incorrectly escaping special characters.
```

---

## Configuration Basics

Edit `.aver/config.toml` to define your special fields:

```toml
# Default ID prefixes
default_record_prefix = "REC"
default_note_prefix = "NT"

# Global record fields (apply to ALL records)
[record_special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true

[record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["open", "in_progress", "closed"]
default = "open"

[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"  # Auto-populated

# Global note fields (apply to ALL notes)
[note_special_fields.author]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"  # Auto-populated

[note_special_fields.timestamp]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"  # Auto-populated
```

---

## Key Tips

1. **Use `--help-fields`** to discover what fields are available:
   ```bash
   aver record new --help-fields
   aver note add REC-001 --help-fields
   ```

2. **Records and notes have different fields** - Notes can track different information than their parent records.

3. **Special fields are validated** - The system won't let you set `status=invalid` if it's not in `accepted_values`.

4. **System values are automatic** - Fields like `author`, `timestamp`, `created_by` are auto-populated.

5. **Everything is plain text** - You can edit files directly, use `grep`, and version control with Git.

6. **Reindex after manual edits**:
   ```bash
   aver admin reindex
   ```

---

## Multiple Projects (Libraries)

Work with multiple databases:

```bash
# Add library aliases
aver admin config add-alias --alias work --path ~/work/aver-db
aver admin config add-alias --alias personal --path ~/personal/aver-db

# Use them
aver --use work record list
aver --use personal record new --title "Personal task"
```

---

## Next Steps

- **Read the full manual** for comprehensive coverage of templates, search, and advanced features
- **Experiment** with a test database to understand the workflow
- **Configure special fields** in `config.toml` for your specific use case
- **Set up templates** for different record types (bugs, features, tasks)
- **Integrate with Git** for version control and collaboration

---

## Quick Reference

| Task | Command |
|------|---------|
| Initialize database | `aver admin init` |
| Set user | `aver admin config set-user --handle name --email email` |
| Create record | `aver record new --title "..." --status open` |
| List records | `aver record list` |
| Search records | `aver record search --ksearch status=open` |
| Add note | `aver note add REC-001 --message "..."` |
| List notes | `aver note list REC-001` |
| Search notes | `aver note search --ksearch category=bugfix` |
| Show available fields | `aver record new --help-fields` |
| Show note fields | `aver note add REC-001 --help-fields` |
| Reindex | `aver admin reindex` |

---

**Remember**: Your data is just Markdown files. You can always read, edit, or process them with any text tool. Aver just adds structure, validation, and fast searching on top.
