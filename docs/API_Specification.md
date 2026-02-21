# Aver API Specification & Configuration Reference

**Version:** 1.0  
**Purpose:** Complete technical reference for building tools and integrations with Aver

---

## Overview

Aver is a file-based knowledge tracking system that stores records as Markdown files with YAML frontmatter, indexed by SQLite for fast searching. All data lives in plain text files; the SQLite database is a rebuildable index.

**Core Concepts:**
- **Records**: Primary entities being tracked (bugs, tasks, experiments, etc.)
- **Notes**: Chronological updates attached to records
- **Special Fields**: Configured, validated metadata fields
- **Custom Fields**: Ad-hoc key-value data
- **Templates**: Record type configurations with custom ID prefixes and field sets
- **Libraries**: Named database locations (aliases)

---

## File System Structure

```
project/
├── .aver/
│   ├── aver.db              # SQLite index (rebuildable, gitignore recommended)
│   └── config.toml          # Database-specific configuration
├── records/
│   ├── REC-001.md           # Record files
│   ├── BUG-042.md
│   └── FEAT-123.md
└── updates/
    ├── REC-001/
    │   ├── NT-001.md        # Note files
    │   └── NT-002.md
    └── BUG-042/
        └── COMMENT-001.md

~/.config/aver/
└── user.toml                # Global user configuration
```

---

## Configuration Files

### User Configuration (`~/.config/aver/user.toml`)

Global settings that follow the user across all databases.

```toml
[user]
handle = "username"                    # Required: user identifier
email = "user@example.com"             # Required: user email
editor = "vim"                         # Optional: default editor for long-form content
prefer_git_identity = false            # Optional: auto-resolve git identity mismatches

# Library aliases - named database locations
[libraries]
[libraries.work]
path = "/home/user/work/.aver"
prefer_git_identity = true             # Optional: per-library override

[libraries.personal]
path = "/home/user/personal/.aver"

# Per-library user identity (optional)
[libraries.work.user]
handle = "work_user"
email = "work@company.com"

# Optional: database discovery behavior
[behavior]
database_selection = "contextual"      # "contextual" or "interactive"

# Optional: known database locations for auto-discovery
[locations]
"/home/user/project1" = "/home/user/project1/.aver"
"/home/user/project2" = "/home/user/project2/.aver"
```

### Database Configuration (`.aver/config.toml`)

Database-specific field definitions and templates.

```toml
# Default ID prefixes (optional, defaults to "REC" and "NT")
default_record_prefix = "REC"
default_note_prefix = "NT"

# Global record special fields (apply to ALL records unless template overrides)
[record_special_fields.title]
type = "single"                        # "single" or "multi"
value_type = "string"                  # "string", "integer", or "float"
editable = true                        # Can users edit after creation?
enabled = true                         # Is field active?
required = true                        # Must be provided?

[record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["open", "investigating", "resolved", "closed"]
default = "open"                       # Default value if not provided

[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false                       # Read-only after creation
enabled = true
required = true
system_value = "user_name"             # Auto-populated from user config

[record_special_fields.created_at]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"              # Auto-populated with current timestamp

[record_special_fields.tags]
type = "multi"                         # Can have multiple values
value_type = "string"
editable = true
enabled = true
required = false

# Global note special fields (apply to ALL notes unless template overrides)
[note_special_fields.author]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[note_special_fields.timestamp]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"

# Template definitions
[template.bug]
record_prefix = "BUG"                  # Custom ID prefix for records
note_prefix = "COMMENT"                # Custom ID prefix for notes

# Template-specific record fields (add to or override global fields)
[template.bug.record_special_fields.severity]
type = "single"
value_type = "integer"
editable = true
enabled = true
required = true
accepted_values = ["1", "2", "3", "4", "5"]
default = "3"

[template.bug.record_special_fields.reproducible]
type = "single"
value_type = "string"
editable = true
enabled = true
accepted_values = ["yes", "no", "sometimes"]

# Template-specific note fields
[template.bug.note_special_fields.category]
type = "single"
value_type = "string"
editable = true
enabled = true
accepted_values = ["investigation", "bugfix", "workaround", "duplicate"]

# Additional template example
[template.feature]
record_prefix = "FEAT"
note_prefix = "FEEDBACK"

[template.feature.record_special_fields.priority]
type = "single"
value_type = "integer"
accepted_values = ["1", "2", "3", "4", "5"]

[template.feature.record_special_fields.effort_estimate]
type = "single"
value_type = "integer"
```

**Field Property Reference:**

| Property | Values | Description |
|----------|--------|-------------|
| `type` | `single`, `multi` | Single value or array of values |
| `value_type` | `string`, `integer`, `float` | Data type of the value(s) |
| `editable` | `true`, `false` | Can be modified after creation |
| `enabled` | `true`, `false` | Field is active |
| `required` | `true`, `false` | Must be provided on creation |
| `accepted_values` | `["a", "b", "c"]` | Restricted to specific values (optional) |
| `default` | any value | Default if not provided (optional) |
| `system_value` | `user_name`, `user_email`, `datetime` | Auto-populated (optional) |

**System Values:**
- `user_name`: User's handle from config
- `user_email`: User's email from config
- `datetime`: Current timestamp in ISO 8601 format

---

## File Format Specification

### Record File Format

Records are stored as Markdown files with YAML frontmatter (using `---` delimiters).

**File naming:** `{record-id}.md` (e.g., `REC-001.md`, `BUG-042.md`)

```yaml
---
# Special fields (no type suffix)
title: Database Connection Error
status: open
priority: high
created_by: alice
created_at: 2024-02-15T10:30:00Z
tags:
  - backend
  - database

# Custom fields (with type suffix)
server_ip__string:
  - 192.168.1.100
retry_count__integer:
  - 5
cost_estimate__float:
  - 150.50
---

Body content goes here. This is the description or main content
of the record. It can be multiple paragraphs, code blocks, etc.

Any Markdown formatting is preserved.
```

**Field Storage Rules:**

| Field Type | YAML Format | Example |
|------------|-------------|---------|
| Special field, single value | `field: value` | `status: open` |
| Special field, multi value | `field: [v1, v2]` or YAML list | `tags: [a, b]` |
| Custom string | `field__string: [value]` | `note__string: ["text"]` |
| Custom integer | `field__integer: [value]` | `count__integer: [42]` |
| Custom float | `field__float: [value]` | `cost__float: [99.95]` |

**Important:** All custom fields are stored as single-element arrays even if they have one value.

### Note File Format

Notes use the same Markdown + YAML frontmatter format.

**File naming:** `{note-id}.md` in `updates/{record-id}/` directory

```yaml
---
id: NT-001
record_id: REC-001
author: alice
timestamp: 2024-02-15T11:00:00Z
category: investigation

# Custom fields
hours_spent__integer:
  - 2
---

Investigation notes go here.

Found that the connection pool is exhausted under high load.
```

---

## Command Line Interface

### General Command Structure

```bash
aver [global-options] <command> <subcommand> [options] [arguments]
```

**Global Options:**

| Option | Description |
|--------|-------------|
| `--location PATH` | Specify database path explicitly |
| `--use ALIAS` | Use named library alias |
| `--choose` | Interactive selection when multiple databases found |

### Database Discovery

Aver searches for `.aver` directories in this order:
1. `--location` flag (explicit path)
2. `--use` flag (library alias from user.toml)
3. Current directory
4. Git repository root (if in a git repo)
5. Parent directories (ascending)
6. Known locations from user.toml `[locations]`

---

## Command Reference

### Admin Commands

#### `aver admin init`

Initialize a new database.

```bash
aver admin init [--location PATH]
```

Creates:
- `.aver/` directory with `config.toml` and `aver.db`
- `records/` directory
- `updates/` directory

#### `aver admin config set-user`

Set user identity.

```bash
# Global user
aver admin config set-user --handle NAME --email EMAIL

# Library-specific user
aver admin config set-user --library ALIAS --handle NAME --email EMAIL
```

#### `aver admin config add-alias`

Add a library alias.

```bash
aver admin config add-alias --alias NAME --path PATH
```

#### `aver admin config list-aliases`

List all library aliases.

```bash
aver admin config list-aliases
```

#### `aver admin reindex`

Rebuild the SQLite index from Markdown files.

```bash
aver admin reindex [--verbose]
```

---

### Record Commands

#### `aver record new`

Create a new record.

**Options:**

| Option | Description |
|--------|-------------|
| `--title TEXT` | Record title (if title is a special field) |
| `--template NAME` | Use template (e.g., `bug`, `feature`) |
| `--text KEY=VALUE`, `-t` | Add custom text field (repeatable) |
| `--number KEY=VALUE`, `-n` | Add custom integer field (repeatable) |
| `--decimal KEY=VALUE`, `-d` | Add custom float field (repeatable) |
| `--text-multi KEY=VALUE`, `--tm` | Add to multi-value text field (repeatable) |
| `--number-multi KEY=VALUE`, `--nm` | Add to multi-value integer field (repeatable) |
| `--decimal-multi KEY=VALUE`, `--dm` | Add to multi-value float field (repeatable) |
| `--description TEXT` | Body content |
| `--from-file PATH` | Import from Markdown file |
| `--help-fields` | Show available fields for this template |
| `--use-git-id` | Use git identity instead of aver config (one-time) |
| `--no-use-git-id` | Use aver config identity (one-time) |

**Examples:**

```bash
# Basic creation (opens editor)
aver record new

# With special fields
aver record new --title "Fix login bug" --status open --priority high

# Using template
aver record new --template bug --title "App crashes" --severity 3

# With custom fields
aver record new --title "Issue" --text server=web-01 --number port=8080

# Multiple values
aver record new --title "Multi-tag" --text-multi tags=backend --text-multi tags=urgent

# From file
aver record new --from-file bug-report.md

# Show available fields
aver record new --help-fields
aver record new --template bug --help-fields
```

#### `aver record view`

View a specific record.

```bash
aver record view <record-id>
```

#### `aver record list`

List records with optional filtering and sorting.

**Options:**

| Option | Description |
|--------|-------------|
| `--ksearch EXPR` | Filter by field (repeatable, combined with AND) |
| `--ksort EXPR` | Sort by field (repeatable for tiebreakers) |
| `--limit N` | Maximum results (default: 50) |

**Search Operators:**

| Operator | Meaning | Example |
|----------|---------|---------|
| `=` | Exact match | `status=open` |
| `>` | Greater than | `priority>2` |
| `<` | Less than | `severity<5` |
| `>=` | Greater or equal | `cost>=100` |
| `<=` | Less or equal | `priority<=3` |

**Sort Syntax:**
- `field` or `field+`: Ascending
- `field-`: Descending

**Examples:**

```bash
# List all
aver record list

# Filter by status
aver record list --ksearch "status=open"

# Multiple filters (AND)
aver record list --ksearch "status=open" --ksearch "priority>2"

# Sort by priority
aver record list --ksort "priority-"

# Complex query
aver record list --ksearch "status=open" --ksearch "severity>=3" --ksort "priority-" --limit 10
```

#### `aver record update`

Update an existing record's fields.

```bash
aver record update <record-id> [options]

# Same field options as record new
aver record update REC-001 --status closed --text resolution="Fixed in v2.1"
```

#### `aver record search`

Search records (alias for `record list` with filters).

```bash
aver record search --ksearch "status=open"
```

---

### Note Commands

#### `aver note add`

Add a note to a record.

**Options:** Same as `record new` plus:

| Option | Description |
|--------|-------------|
| `--message TEXT` | Note message/body |

**Examples:**

```bash
# Basic (opens editor)
aver note add REC-001

# With message
aver note add REC-001 --message "Investigation complete"

# With note fields (if configured in template)
aver note add BUG-042 --message "Applied fix" --category bugfix

# Show available fields
aver note add REC-001 --help-fields
```

**Note:** The available fields for notes depend on:
1. Global note special fields
2. Template-specific note fields (if record was created with a template)

#### `aver note list`

List notes for a specific record.

```bash
aver note list <record-id>
```

#### `aver note search`

Search notes across all records.

```bash
aver note search --ksearch "category=bugfix"
aver note search --ksearch "hours>0"
```

---

## Git Integration

### Identity Verification

When performing write operations (`record new`, `record update`, `note add`) inside a git repository, Aver checks if the aver config identity matches the git identity.

**Git Identity:**
- `git config user.name`
- `git config user.email`

**Aver Identity:**
- From `~/.config/aver/user.toml` (or library-specific override)

**Resolution Options:**

1. **Per-invocation flags:**
   ```bash
   aver record new --use-git-id --title "Use git identity"
   aver record new --no-use-git-id --title "Use aver identity"
   ```

2. **Persistent configuration:**
   ```toml
   # In user.toml - global
   [user]
   prefer_git_identity = true  # or false
   
   # In user.toml - per-library
   [libraries.work]
   path = "/path/to/.aver"
   prefer_git_identity = true
   ```

**Resolution Order:**
1. Per-library `prefer_git_identity` setting
2. Global `prefer_git_identity` setting
3. CLI flag (`--use-git-id` or `--no-use-git-id`)
4. Error with instructions if unresolved

---

## SQLite Database Schema

The `.aver/aver.db` file is a SQLite database used for indexing and searching. It is rebuildable from the Markdown files via `aver admin reindex`.

### Core Tables

#### `incidents_index`
Tracks which records have been indexed and when.

```sql
CREATE TABLE incidents_index (
    id TEXT PRIMARY KEY,           -- Record ID (e.g., "REC-001", "BUG-042")
    indexed_at TEXT NOT NULL       -- ISO 8601 timestamp of last indexing
)
```

#### `incidents_fts` (FTS5 Virtual Table)
Full-text search index for record and note content.

```sql
CREATE VIRTUAL TABLE incidents_fts
USING fts5(
    incident_id UNINDEXED,         -- Record ID (not searchable, for retrieval only)
    source,                        -- "record" or "note"
    source_id UNINDEXED,           -- ID of the source (record or note ID)
    content                        -- Searchable text content (body + fields)
)
```

**Usage:** This table enables fast full-text searches across all record and note content.

#### `kv_store`
Unified key-value storage for all metadata fields (both special and custom fields).

```sql
CREATE TABLE kv_store (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,     -- Record ID this belongs to
    update_id TEXT,                -- Note ID (NULL for record fields)
    key TEXT NOT NULL,             -- Field name
    value_string TEXT,             -- String value (NULL if not string type)
    value_integer INTEGER,         -- Integer value (NULL if not integer type)
    value_float REAL,              -- Float value (NULL if not float type)
    created_at TEXT NOT NULL       -- ISO 8601 timestamp
)
```

**Field Storage:**
- Each field value is stored in exactly one of the three value columns
- The other two value columns are NULL
- Multi-value fields have multiple rows with the same `incident_id` and `key`
- Record fields: `update_id` is NULL
- Note fields: `update_id` contains the note ID

**Examples:**

```sql
-- Record field: title="Fix login bug"
INSERT INTO kv_store (incident_id, update_id, key, value_string, value_integer, value_float, created_at)
VALUES ('REC-001', NULL, 'title', 'Fix login bug', NULL, NULL, '2024-02-15T10:30:00Z');

-- Record field: priority=3
INSERT INTO kv_store (incident_id, update_id, key, value_string, value_integer, value_float, created_at)
VALUES ('REC-001', NULL, 'priority', NULL, 3, NULL, '2024-02-15T10:30:00Z');

-- Multi-value field: tags=["backend", "urgent"]
INSERT INTO kv_store (incident_id, update_id, key, value_string, value_integer, value_float, created_at)
VALUES ('REC-001', NULL, 'tags', 'backend', NULL, NULL, '2024-02-15T10:30:00Z');
INSERT INTO kv_store (incident_id, update_id, key, value_string, value_integer, value_float, created_at)
VALUES ('REC-001', NULL, 'tags', 'urgent', NULL, NULL, '2024-02-15T10:30:00Z');

-- Note field: category="bugfix"
INSERT INTO kv_store (incident_id, update_id, key, value_string, value_integer, value_float, created_at)
VALUES ('REC-001', 'NT-001', 'category', 'bugfix', NULL, NULL, '2024-02-15T11:00:00Z');
```

### Indexes

The database includes indexes optimized for common query patterns:

- `idx_kv_incident_key` - Fast lookup of all fields for a record
- `idx_kv_update_key` - Fast lookup of all fields for a note
- `idx_kv_key` - Fast lookup across all records for a specific field name
- `idx_kv_string_value` - Efficient string value searches (partial index, NULL excluded)
- `idx_kv_integer_value` - Efficient integer value searches (partial index, NULL excluded)
- `idx_kv_float_value` - Efficient float value searches (partial index, NULL excluded)

### Important Notes

**Source of Truth:** The Markdown files are authoritative. The database is a rebuildable cache.

**Rebuilding:** Run `aver admin reindex` to rebuild the entire database from files. This is fast and safe.

**Git:** Add `.aver/aver.db` to `.gitignore` - it can be regenerated from the files.

**Two Valid Integration Approaches:**

1. **CLI-based** (Recommended for most use cases):
   - Use `aver` commands for all operations
   - Automatic validation, formatting, and indexing
   - Parse CLI output for data retrieval

2. **File-based** (Valid for bulk operations, custom workflows):
   - Read Markdown files directly anytime
   - Write/modify Markdown files following format spec
   - **Must run `aver admin reindex` after any file changes**
   - Good for batch processing and integration with file-based tools

**Never Do:**
- Write directly to `.aver/aver.db` (database is just a cache)
- Modify files without reindexing (causes database to be out of sync)
- Modify the database schema

**Database Schema Use:**
- Documented here for transparency and understanding
- Not intended for direct manipulation
- If you need to query the database, consider requesting a CLI feature instead

**Type Detection:** Search operations attempt to find values in all three type columns, so you don't need to know the type beforehand when searching.

### Working with the Database

**Important:** The database schema is documented here for transparency and understanding, but **all operations should go through the `aver` CLI**.

**Recommended Approaches:**

1. **Use the CLI** - All standard operations are supported via commands
2. **File manipulation + reindex** - Edit Markdown files directly, then run `aver admin reindex`
3. **Request features** - If you need functionality not available via the CLI:
   - Submit a pull request: https://github.com/dentm42/aver
   - Open an issue to discuss your use case
   - Contact the developers to evaluate the need

**Why avoid direct database access:**
- Schema may change between versions
- Index consistency requires careful handling
- CLI ensures proper validation and file synchronization
- Direct writes bypass field validation and can corrupt the index

**Read-only queries** for advanced analysis or integration might seem tempting, but even these should ideally be requested as CLI features so they benefit the entire community and remain compatible with future versions.

---

## Field Name Conventions

### Special Fields
- Defined in `config.toml`
- No type suffix in YAML
- Validated against configuration
- Can be auto-populated with system values

### Custom Fields
- Created ad-hoc via CLI
- Type suffix required: `__string`, `__integer`, `__float`
- No validation
- Always stored as arrays in YAML

**Reserved Field Names:**
- `id` (auto-generated)
- `record_id` (for notes, references parent record)
- Field names cannot contain: whitespace, `__` (double underscore, reserved for type hints)

---

## ID Generation

IDs are generated as: `{PREFIX}-{UNIQUE_SUFFIX}`

**Prefix Sources:**
1. Template `record_prefix` or `note_prefix`
2. Global `default_record_prefix` or `default_note_prefix`
3. Fallback: `"REC"` or `"NT"`

**Unique Suffix:**
- Generated to ensure uniqueness
- Format not guaranteed (implementation-specific)
- Example formats: `001`, `1A2B3C4D5E`, etc.

---

## Error Handling

### Common Errors

**"No record vault can be found"**
- Cause: No `.aver` directory detected
- Solution: Run `aver admin init` or use `--location`

**"User identity has not been declared"**
- Cause: No user configured
- Solution: Run `aver admin config set-user --handle NAME --email EMAIL`

**"Identity mismatch between aver config and git"**
- Cause: Aver and git identities differ
- Solution: Use `--use-git-id` / `--no-use-git-id` or configure `prefer_git_identity`

**"Field validation failed"**
- Cause: Value not in `accepted_values` or wrong type
- Solution: Check field configuration with `--help-fields`

**"Search results incorrect"**
- Cause: Index out of sync
- Solution: Run `aver admin reindex`

---

## Integration Guidelines

### Building Tools

When building tools that interface with Aver, you have two valid approaches:

**Approach 1: Use the CLI (Recommended for most cases)**
- Automatic validation
- Proper ID generation
- Correct formatting guaranteed
- Git identity handling
- Template support

**Approach 2: Direct File Manipulation (Valid for bulk operations, custom workflows)**
- Full control over file format
- Efficient for batch operations
- Good for integration with other file-based tools
- **Must run `aver admin reindex` after any changes**

### Integration Checklist

1. **Read Configuration:**
   - Parse `~/.config/aver/user.toml` for user settings
   - Parse `.aver/config.toml` for field definitions
   - Respect template configurations

2. **Choose Your Integration Method:**
   
   **Using CLI:**
   - All operations invoke `aver` commands
   - Parse CLI output for data retrieval
   - Let aver handle validation and formatting
   
   **Direct File Manipulation:**
   - Write valid YAML frontmatter (see File Format Specification)
   - Use correct type suffixes for custom fields
   - Store custom values as single-element arrays
   - **Always run `aver admin reindex` after file changes**
   - Validate against field configs if you want enforcement

3. **Never Do These Things:**
   - Write directly to `.aver/aver.db` (database is a cache)
   - Modify files without reindexing (causes sync issues)
   - Bypass field validation without good reason
   - Ignore the file format specification

4. **Request Features When Needed:**
   - If CLI lacks functionality: https://github.com/dentm42/aver/issues
   - Submit pull requests: https://github.com/dentm42/aver
   - File manipulation is a workaround, but feature requests help everyone

### CLI Wrappers and Scripts

When creating CLI wrappers or scripts, always invoke `aver` commands:

```python
import subprocess
import json

# Example: Create record with Python
def create_record(title, status, tags=None):
    """Create a record using the aver CLI."""
    cmd = ['aver', 'record', 'new', '--title', title, '--status', status]
    if tags:
        for tag in tags:
            cmd.extend(['--text-multi', f'tags={tag}'])
    
    result = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return result.stdout

# Example: Search records
def search_records(status):
    """Search for records by status."""
    result = subprocess.run(
        ['aver', 'record', 'list', '--ksearch', f'status={status}'],
        capture_output=True,
        text=True,
        check=True
    )
    return result.stdout

# Example: Add note
def add_note(record_id, message, category=None):
    """Add a note to a record."""
    cmd = ['aver', 'note', 'add', record_id, '--message', message]
    if category:
        cmd.extend(['--text', f'category={category}'])
    
    subprocess.run(cmd, check=True)
```

**Best Practices:**
- Always use `check=True` to catch errors
- Parse `stdout` for data extraction
- Handle `stderr` for error messages
- Never bypass the CLI by writing to files without reindexing

### Direct File Access

Direct file manipulation is fully supported as long as you reindex afterward. This is a valid integration pattern.

**For read operations** - Parse Markdown files directly (no reindex needed):

```python
import yaml

def read_record(filepath):
    """Read a record file and parse its metadata and body."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Split frontmatter and body
    parts = content.split('---', 2)
    if len(parts) >= 2:
        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip() if len(parts) > 2 else ''
    else:
        frontmatter = {}
        body = content
    
    return {'metadata': frontmatter, 'body': body}
```

**For write operations** - Direct file manipulation is acceptable:

```python
import yaml
import subprocess

def create_record_file(filepath, metadata, body):
    """Create a record file directly.
    
    This is a valid approach - just remember to reindex!
    """
    # Create YAML frontmatter
    frontmatter = yaml.dump(metadata, default_flow_style=False)
    
    # Write file
    with open(filepath, 'w') as f:
        f.write('---\n')
        f.write(frontmatter)
        f.write('---\n\n')
        f.write(body)
    
    # CRITICAL: Reindex after file manipulation
    subprocess.run(['aver', 'admin', 'reindex'], check=True)

def update_record_field(filepath, field, value):
    """Update a field in a record file."""
    # Read existing file
    record = read_record(filepath)
    
    # Modify metadata
    record['metadata'][field] = value
    
    # Write back
    frontmatter = yaml.dump(record['metadata'], default_flow_style=False)
    with open(filepath, 'w') as f:
        f.write('---\n')
        f.write(frontmatter)
        f.write('---\n\n')
        f.write(record['body'])
    
    # CRITICAL: Reindex after modification
    subprocess.run(['aver', 'admin', 'reindex'], check=True)
```

**Requirements for direct file manipulation:**
1. Use proper YAML frontmatter format (`---` delimiters)
2. Store custom fields with type suffixes (`field__string`, `field__integer`, `field__float`)
3. Store custom field values as single-element arrays
4. **Always run `aver admin reindex` after any file changes**
5. Validate against field configurations if you want to enforce rules

**When to use direct file access vs CLI:**
- **CLI:** When you want automatic validation, ID generation, and proper formatting
- **Direct files:** When you need bulk operations, custom formats, or integration with other file-based tools
- **Both are valid** as long as you reindex after file changes

---

## Best Practices

1. **Version Control:**
   - Keep `.aver/config.toml` in version control
   - Add `.aver/aver.db` to `.gitignore`
   - Commit record and note files

2. **Field Design:**
   - Use special fields for validated, structured data
   - Use custom fields for ad-hoc metadata
   - Define templates for different record types

3. **Templates:**
   - Create templates for common workflows (bugs, features, tasks)
   - Use descriptive ID prefixes
   - Keep template-specific fields focused

4. **Search Performance:**
   - Index rebuilds are fast but avoid constant reindexing
   - Use `--ksearch` for metadata queries
   - Keep body content reasonably sized

5. **Multi-User:**
   - Use library aliases for different projects
   - Configure per-library identities
   - Coordinate git identity settings in team environments

---

## Example Workflows

### Bug Tracking

```bash
# Initialize
aver admin init
aver admin config set-user --handle alice --email alice@example.com

# Create bug
aver record new --template bug --title "Login fails" --severity 3

# Add investigation note
aver note add BUG-001 --message "Checked logs" --category investigation

# Update status
aver record update BUG-001 --status investigating

# Add fix note
aver note add BUG-001 --message "Applied fix in PR #123" --category bugfix

# Close bug
aver record update BUG-001 --status resolved

# Search open bugs
aver record list --ksearch "status=open" --ksort "severity-"
```

### Knowledge Base

```bash
# Create how-to article
aver record new --title "Password Reset Procedure" \
  --text-multi tags=admin \
  --text-multi tags=security \
  --text type=howto

# Find all security articles
aver record list --ksearch "tags=security"

# Find all how-tos
aver record list --ksearch "type=howto"
```

### Time Tracking

```bash
# Log work
aver note add REC-001 \
  --message "Refactored auth module" \
  --number hours=4 \
  --text work_type=development

# Find all time entries
aver note search --ksearch "hours>0"
```

---

## Appendix: Complete Configuration Example

```toml
# ~/.config/aver/user.toml
[user]
handle = "johndoe"
email = "john@example.com"
editor = "vim"
prefer_git_identity = false

[libraries]
[libraries.work]
path = "/home/john/work/.aver"
prefer_git_identity = true

[libraries.work.user]
handle = "jdoe"
email = "jdoe@company.com"

[libraries.personal]
path = "/home/john/personal/.aver"

[behavior]
database_selection = "contextual"

[locations]
"/home/john/project1" = "/home/john/project1/.aver"
```

```toml
# .aver/config.toml
default_record_prefix = "REC"
default_note_prefix = "NT"

# Global record fields
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
accepted_values = ["open", "investigating", "resolved", "closed"]
default = "open"

[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[record_special_fields.created_at]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"

[record_special_fields.tags]
type = "multi"
value_type = "string"
editable = true
enabled = true

# Global note fields
[note_special_fields.author]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[note_special_fields.timestamp]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"

# Bug template
[template.bug]
record_prefix = "BUG"
note_prefix = "COMMENT"

[template.bug.record_special_fields.severity]
type = "single"
value_type = "integer"
editable = true
enabled = true
required = true
accepted_values = ["1", "2", "3", "4", "5"]
default = "3"

[template.bug.record_special_fields.reproducible]
type = "single"
value_type = "string"
editable = true
enabled = true
accepted_values = ["yes", "no", "sometimes"]

[template.bug.note_special_fields.category]
type = "single"
value_type = "string"
editable = true
enabled = true
accepted_values = ["investigation", "bugfix", "workaround", "duplicate"]

# Feature template
[template.feature]
record_prefix = "FEAT"
note_prefix = "FEEDBACK"

[template.feature.record_special_fields.priority]
type = "single"
value_type = "integer"
editable = true
enabled = true
accepted_values = ["1", "2", "3", "4", "5"]

[template.feature.record_special_fields.effort_estimate]
type = "single"
value_type = "integer"
editable = true
enabled = true
```

---

**End of Specification**

This document provides complete technical reference for integrating with Aver. For narrative examples and user-facing documentation, see the full user manual.
