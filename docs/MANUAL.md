# Aver: A Verified Knowledge Tracking Tool

**User Manual - Updated Edition**

---

## Table of Contents

### 1. Introduction
- [What is Aver?](#what-is-aver)
- [Why Use Aver?](#why-use-aver)
- [Use Cases](#use-cases)
- [Key Features](#key-features)
- [How It Works](#how-it-works)

### 2. Getting Started
- [Installation](#installation)
- [System Requirements](#system-requirements)
- [Creating Your First Database](#creating-your-first-database)
- [Understanding Database Locations](#understanding-database-locations)
- [Configuration Files](#configuration-files)

### 3. Core Concepts
- [Records vs Notes (Updates)](#records-vs-notes-updates)
- [Special Fields vs Custom Fields](#special-fields-vs-custom-fields)
- [Templates](#templates)
- [The Markdown Storage Model](#the-markdown-storage-model)

### 4. Working with Records
- [Creating a New Record](#creating-a-new-record)
- [Viewing Records](#viewing-records)
- [Searching for Records](#searching-for-records)
- [Updating Record Information](#updating-record-information)
- [Using --help-fields](#using---help-fields-for-records)

### 5. Working with Notes (Updates)
- [Adding a Note](#adding-a-note)
- [Viewing Notes](#viewing-notes)
- [Searching Notes](#searching-notes)
- [Using --help-fields for Notes](#using---help-fields-for-notes)
- [Note Templates](#note-templates)

### 6. Special Fields System
- [Understanding Special Fields](#understanding-special-fields)
- [Record Special Fields](#record-special-fields)
- [Note Special Fields](#note-special-fields)
- [System Values](#system-values)
- [Field Properties](#field-properties)
- [Default Values](#default-values)
- [Secure Fields (securestring)](#secure-fields-securestring)
- [System-Generated Notes (is_system_update)](#system-generated-notes-is_system_update)

### 7. Configuration and Templates
- [Global Configuration](#global-configuration)
- [Record Special Fields Configuration](#record-special-fields-configuration)
- [Note Special Fields Configuration](#note-special-fields-configuration)
- [Template System](#template-system)
- [Template Special Fields](#template-special-fields)

### 8. Advanced Features
- [Search Queries](#search-queries)
- [Database Management](#database-management)
- [Library Aliases](#library-aliases)
- [Importing from Files](#importing-from-files)
- [Reindexing](#reindexing)

### 9. Command Reference
- [admin init](#admin-init)
- [admin config](#admin-config)
- [admin reindex](#admin-reindex)
- [admin template-data](#admin-template-data)
- [admin validate](#admin-validate)
- [record new](#record-new)
- [record unmask](#record-unmask)
- [record update](#record-update)
- [record list](#record-list)
- [record search](#record-search)
- [note add](#note-add)
- [note list](#note-list)
- [note search](#note-search)
- [note unmask](#note-unmask)

### 10. Administrator's Guide
- [Setting Up Special Fields](#setting-up-special-fields)
- [Designing Templates](#designing-templates)
- [Managing Multiple Databases](#managing-multiple-databases)
- [User Configuration](#user-configuration)
- [Best Practices](#best-practices)

---

## 1. Introduction

### What is Aver?

Aver (pronounced "AH-ver") is a lightweight, flexible knowledge tracking tool designed to help you organize, track, and search through structured information. At its core, Aver manages **records** (primary items you're tracking) and **notes** (chronological updates to those records).

Unlike traditional database systems that lock your data away in proprietary formats, Aver stores everything in plain **Markdown files** with **YAML frontmatter**. This means your data is always readable, portable, and easy to work with using standard text tools. SQLite is used only for indexing and searching—your actual data lives in files you can read, edit, and version control.

### Why Use Aver?

**Human-Readable Storage**: Every record and note is stored as a Markdown file. You can read them with any text editor, search them with `grep`, and track changes with Git.

**Flexible Metadata**: Aver supports two types of fields:
- **Special Fields**: Predefined, validated fields with automatic population (like author, timestamps)
- **Custom Fields**: Ad-hoc key-value pairs for any data you need

**Fast Searching**: Despite using plain text files, Aver maintains a SQLite index that enables lightning-fast searches across thousands of records.

**Template System**: Define record and note templates with their own special fields, enabling different workflows for different types of records (bugs, features, experiments, etc.).

**Git-Friendly**: Because everything is text files, your entire database works beautifully with version control.

**Offline-First**: No internet required. No cloud dependencies. Your data stays on your machine.

### Key Features

- **Dual Storage Model**: Records for primary entities, notes for chronological changes
- **Special Fields System**: Define validated, auto-populated fields at global and template levels
- **Template System**: Configure different field sets for different record types
- **Flexible Search**: Query by any field with support for ranges, wildcards, and combinations
- **Multiple Databases**: Work with different databases (called "libraries") for different projects
- **Editor Integration**: Write in your favorite text editor
- **File Import**: Import records and notes from Markdown files
- **Auto-Discovery**: Automatically finds databases in your working directory or home folder

### How It Works

Aver uses a three-layer architecture:

**1. Storage Layer (Markdown Files)**
- Records stored as `{record-id}.md` in a `records/` directory
- Notes stored as `{note-id}.md` in `updates/{record-id}/` directories
- All files use YAML frontmatter for structured data

**2. Index Layer (SQLite)**
- A `.aver/aver.db` file maintains searchable indexes
- Tracks all metadata fields for fast queries
- Automatically updated when you create or modify records

**3. Application Layer (Python CLI)**
- Provides a friendly command-line interface
- Validates special fields
- Manages templates and configuration

---

## 3. Core Concepts

### Records vs Notes (Updates)

**Records** are the primary entities you're tracking. Each record represents one "thing" in your system:
- A bug report
- A feature request
- An experiment
- A D&D character
- A maintenance log entry

**Notes** (also called updates) are chronological entries attached to a record. They represent changes, observations, or progress:
- Status updates
- Comments
- Test results
- Investigation notes

Records and notes can have completely different sets of special fields, allowing notes to track different information than their parent records.

### Special Fields vs Custom Fields

**Special Fields** are predefined in your configuration:
- Validated against allowed values
- Can be automatically populated (like `author`, `timestamp`)
- Can be required or optional
- Can be editable or read-only
- Appear in YAML frontmatter without type hints
- Can be different for records vs notes
- Can be overridden by templates

**Custom Fields** are ad-hoc key-value pairs:
- Created on-the-fly with `--text`, `--number`, `--decimal` flags
- No validation
- Always editable
- Appear in YAML frontmatter with type hints (e.g., `myfield__string`)

**Example:**

```yaml
---
# Special fields (no type hints)
title: Database Connection Error
status: open
priority: high
created_by: alice
created_at: 2024-02-15 10:30:00

# Custom fields (with type hints)
server_ip__string: 192.168.1.100
retry_count__integer: 5
---
```

### Templates

Templates define:
1. **ID Prefixes**: Custom prefixes for records (BUG-, FEAT-) and notes (COMMENT-, FEEDBACK-)
2. **Special Fields**: Template-specific fields that add to or override global fields
3. **Content Templates**: Pre-filled text for records and notes

Templates allow you to have different field sets for different types of records. For example:
- Bug template: `severity`, `reproducible`, `component`
- Feature template: `priority`, `effort_estimate`, `stakeholder`
- Notes in bug records: `category` (investigation, bugfix, etc.), `priority`
- Notes in feature records: `feedback_type`, `implementation_status`

---

## 4. Working with Records

### Creating a New Record

**Basic creation** (opens editor):
```bash
aver record new
```

**With special fields** (if defined in config):
```bash
aver record new --title "Cannot connect to database" --status open --priority high
```

**Using a template**:
```bash
aver record new --template bug --title "Login fails" --severity 3
```

**With custom fields**:
```bash
aver record new --title "Server down" --text location=us-west-2 --number error_code=500
```

**From a file**:
```bash
aver record new --from-file bug-report.md
```

**With a custom record ID**:
```bash
aver record new --use-id MY-CUSTOM-ID --title "Custom ID record"
```
The ID must use only A-Z, a-z, 0-9, `_`, and `-`, and must be unique. If omitted, an ID is auto-generated.

### Using --help-fields for Records

To see what special fields are available for records:

**Global fields**:
```bash
aver record new --help-fields
```

**Template-specific fields**:
```bash
aver record new --template bug --help-fields
```

This shows:
- Field names
- Field types (single/multi, string/integer/float)
- Accepted values (if constrained)
- Default values
- Required vs optional

**Example output**:
```
Available fields for record creation (template: bug):

  title (single, string)
    Required

  status (single, string)
    Required
    Accepted: new, confirmed, in_progress, fixed, verified, closed
    Default: new

  severity (single, integer)
    Required
    Accepted: 1, 2, 3, 4, 5
    Default: 3

  priority (single, string)
    Accepted: low, medium, high, critical
    Default: medium

  tags (multi, string)

Usage:
  aver record new --template bug --title "..." --status new --severity 3
```

---

## 5. Working with Notes (Updates)

### Adding a Note

**Basic note** (opens editor):
```bash
aver note add REC-001
```

**With message**:
```bash
aver note add REC-001 --message "Investigated issue, found root cause in auth module"
```

**With special fields** (if note fields defined):
```bash
aver note add BUG-042 --message "Applied fix" --category bugfix --priority critical
```

**From a file**:
```bash
aver note add BUG-042 --from-file investigation-notes.md
```

### Using --help-fields for Notes

Notes can have their own special fields, different from records. To see available note fields for a specific record:

```bash
aver note add BUG-042 --help-fields
```

**Example output**:
```
Available fields for BUG-042 (template: bug):

  category (single, string)
    Accepted: investigation, bugfix, workaround, regression, documentation

  priority (single, string)
    Accepted: low, medium, high, critical
    Default: medium

Usage:
  aver note add BUG-042 --category=investigation --priority=high
  aver note add BUG-042 --message 'Found it' --category=bugfix
```

**Important**: Note fields are template-specific and inherit from:
1. Global `note_special_fields` (like `author`, `timestamp`)
2. Template's `note_special_fields` (like `category`, `priority`)

### Viewing Notes

```bash
aver note list BUG-042
```

### Searching Notes

Search notes by their special fields:
```bash
# Search by note field
aver note search --ksearch category=bugfix

# Search by priority
aver note search --ksearch priority=critical
```

---

## 6. Special Fields System

### Understanding Special Fields

Special fields are the heart of Aver's structured data system. They provide:
- **Validation**: Ensure data consistency
- **Automation**: Auto-populate timestamps, authors, etc.
- **Structure**: Define what information belongs in records and notes
- **Templates**: Different field sets for different record types

### Record Special Fields

Record special fields are defined globally and can be overridden by templates. Common examples:

**System-populated fields**:
- `created_by`: Auto-set to current user (non-editable)
- `created_at`: Auto-set to current timestamp (non-editable)
- `template_id`: Auto-set when using templates (non-editable)
- `updated_at`: Auto-updated on changes (editable)

**User-defined fields**:
- `title`: Record title (required)
- `status`: Workflow status with constrained values
- `priority`: Priority level
- `tags`: Multi-value categorization

### Note Special Fields

Notes have their own special fields, completely independent from record fields:

**Global note fields** (apply to all notes):
- `author`: Who created the note (auto-populated)
- `timestamp`: When the note was created (auto-populated)

**Template-specific note fields** (only for notes in templated records):
- `category`: Type of note (investigation, bugfix, etc.)
- `priority`: Note urgency
- `status`: Note-specific status

**Key insight**: When you add a note to a bug record, the note gets:
- Global note fields (author, timestamp)
- Bug template note fields (category, priority)
- Does NOT get record fields (severity, reproducible)

### System Values

System values automatically populate special fields:

| System Value | Description | Example |
|--------------|-------------|---------|
| `datetime` | Full timestamp | `2024-02-15 10:30:00` |
| `datestamp` | Date only | `2024-02-15` |
| `user_name` | User handle | `alice` |
| `user_email` | User email | `alice@example.com` |
| `recordid` | Record ID | `BUG-042` |
| `updateid` | Note ID | `COMMENT-001` |
| `template_id` | Template name | `bug` |
| `is_system_update` | `1` for system-generated notes, `0` for user notes | `1` |

**Configuration example**:
```toml
[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"
index_values = true
```

### Field Properties

Each special field has these properties:

**type**: `single` or `multi`
- `single`: One value per field
- `multi`: Multiple values allowed (like tags)

**value_type**: `string`, `integer`, `float`, or `securestring`
- Determines storage and search behavior
- `securestring`: Stores plaintext on disk but is **masked** as `{securestring}` in all user-facing output (view, list, JSON export, editor). Supports `=`, `!=`, and `^` search operators only. Use for passwords, API keys, tokens, and other sensitive values.

**editable**: `true` or `false`
- `false`: Field is set once on creation and locked thereafter
  - If `system_value` is set: system auto-populates; user-supplied value is discarded
  - If `system_value` is not set: user supplies the value at creation; it is then immutable
- `true`: Users can edit; if `system_value` is set, auto-updates on every edit

**enabled**: `true` or `false`
- Disabled fields are ignored

**required**: `true` or `false`
- Required fields must have a value

**index_values**: `true` or `false` (default: `true`)
- `true`: Field values are indexed in the database and searchable
- `false`: Field values stored only in Markdown files, not searchable via database
- Note: `securestring` fields are always indexed for search (regardless of `index_values`), but the plaintext is stored in a separate secure column never exposed in output

**system_value**: System value source (optional)
- If set, field is auto-populated
- Non-editable system fields only set on creation
- Editable system fields update on every edit

**accepted_values**: List of valid values (optional)
- Constrains field to specific choices
- Example: `["open", "closed", "in_progress"]`

**default**: Default value (optional)
- Used if field is empty on creation
- Can reference system values

### Default Values

Defaults can be static or dynamic:

**Static default**:
```toml
[record_special_fields.priority]
type = "single"
value_type = "string"
default = "medium"
```

**Dynamic default** (references system value):
```toml
[note_special_fields.created_date]
type = "single"
value_type = "string"
default = "${datestamp}"
```

### Secure Fields (`securestring`)

Aver supports a special `value_type = "securestring"` for fields that contain sensitive data like passwords, API keys, and authentication tokens.

**How it works:**
- Values are stored **plaintext** in Markdown files on disk (source of truth, under your control)
- Values are **masked** as `{securestring}` everywhere they surface to the user:
  - `record view` and `note view` output
  - `record list` / `note search` output
  - JSON export and JSON IO search results
  - The YAML editor (when editing a record)
- Values are **fully searchable** via `=`, `!=`, and `^` operators (exact match and IN-list)

**Configuration example**:
```toml
[record_special_fields.api_token]
type = "single"
value_type = "securestring"
editable = true
enabled = true
required = false
```

**Usage**:
```bash
# Set a secure field value on creation
aver record new --text api_token=mysecretkey123

# View record — secure field shown as mask
aver record view REC-001
# Output:  api_token: {securestring}

# Search by exact value (works even though display is masked)
aver record list --ksearch api_token=mysecretkey123

# Search using IN-list
aver record list --ksearch 'api_token^key1|key2|key3'

# Search excluding a value
aver record list --ksearch api_token!=mysecretkey123
```

**Editor behavior for editable securestring fields:**
When you open a record with an editable securestring field in the YAML editor, the field appears as `{securestring}`. If you leave it unchanged, the original value is preserved. To update it, replace the mask with the new value.

**Non-editable securestring fields:**
Fields with `editable = false` are never shown in the editor. They can be set at creation time and cannot be changed afterward (same as any non-editable field).

**Security note**: Plaintext values are stored in Markdown files and indexed in SQLite. Aver's masking is a display-layer feature to prevent accidental exposure in terminal output, logs, and exports. If you need true encryption at rest, consider encrypting the database directory.

### System-Generated Notes (`is_system_update`)

Aver automatically creates notes on your behalf in two situations:

1. **Record creation** — an initial note is created when a new record is saved, capturing the full initial state.
2. **Record updates** — when you update a record's content or metadata, aver appends a note recording what changed and what the previous values were.

These system-generated notes are functionally identical to user notes, but it can be useful to distinguish them in searches and integrations. The `is_system_update` system value enables this.

**Configuration**:
```toml
[note_special_fields.is_system_update]
type = "single"
value_type = "integer"
editable = false
enabled = true
required = false
system_value = "is_system_update"
index_values = true
```

When this field is defined, every note receives the value automatically:
- `1` — system-generated note (record creation or update tracking)
- `0` — user-created note (`note add`)

**Filtering system notes out of search results**:
```bash
# Show only user-authored notes
aver note search --ksearch is_system_update=0

# Show only system-generated tracking notes
aver note search --ksearch is_system_update=1

# Combine with other filters
aver note search --ksearch is_system_update=0 --ksearch category=investigation
```

**JSON IO**:
```json
{"command": "search-notes", "params": {"ksearch": ["is_system_update=0"]}}
```

---

## 7. Configuration and Templates

### Global Configuration

Aver uses a `config.toml` file in the database directory (`.aver/config.toml`).

**Basic structure**:
```toml
default_record_prefix = "REC"
default_note_prefix = "NT"

# Global record fields (apply to ALL records)
[record_special_fields.FIELDNAME]
# ... field definition

# Global note fields (apply to ALL notes)
[note_special_fields.FIELDNAME]
# ... field definition

# Templates
[template.TEMPLATENAME]
# ... template definition
```

### Record Special Fields Configuration

Define fields that apply to all records:

```toml
[record_special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
index_values = true

[record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["open", "in_progress", "resolved", "closed"]
default = "open"
index_values = true

[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"
index_values = true

[record_special_fields.created_at]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"
index_values = true

[record_special_fields.tags]
type = "multi"
value_type = "string"
editable = true
enabled = true
required = false
```

### Note Special Fields Configuration

Define fields that apply to all notes:

```toml
[note_special_fields.author]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"
index_values = true

[note_special_fields.timestamp]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"
index_values = true
```

These global note fields appear in EVERY note, regardless of template.

### Template System

Templates define:
1. Custom ID prefixes
2. Record-specific special fields (add to or override global record fields)
3. Note-specific special fields (add to or override global note fields)
4. Template record IDs (for content templates)

#### Connecting Content Templates with Field Enforcement

`record new --template bug` does two things at once:

1. **Field enforcement** — the new record is validated against the `bug` template's field rules.
2. **Content import** — if a record file named `bug.md` (matching the template ID) exists in the `records/` directory, its body text is copied into the new record as initial content.

Admins can create a `bug.md` record file to provide a standard starting document (checklists, instructions, boilerplate) that gets pre-filled whenever someone creates a new bug record. This is an optional convention — if no such file exists, `record new --template bug` still works normally with an empty body.

`record update --template` is **field-scope only**: it scopes validation to the named template's field rules but never imports content from any record file.

**Complete template example**:
```toml
[template.bug]
record_prefix = "BUG"
note_prefix = "COMMENT"

# Template record special fields (adds to global record fields)
[template.bug.record_special_fields.severity]
type = "single"
value_type = "integer"
editable = true
enabled = true
required = true
accepted_values = ["1", "2", "3", "4", "5"]
default = "3"
index_values = true

[template.bug.record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["new", "confirmed", "in_progress", "fixed", "verified", "closed"]
default = "new"
index_values = true

# Template note special fields (adds to global note fields)
[template.bug.note_special_fields.category]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["investigation", "bugfix", "workaround", "regression", "documentation"]
index_values = true

[template.bug.note_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["low", "medium", "high", "critical"]
default = "medium"
index_values = true
```

### Template Special Fields

**How template fields work**:

For **records**: **Additive + Override**
- Starts with global `record_special_fields`
- Adds template's `record_special_fields`
- Template fields override global fields with same name

For **notes**: **Additive + Override**
- Starts with global `note_special_fields`
- Adds template's `note_special_fields`
- Template fields override global note fields with same name

**Example**: Bug template records have:
- Global fields: `title`, `created_by`, `created_at`, `tags`
- Bug-specific fields: `severity`, `status` (bug version overrides global)

**Example**: Notes in bug records have:
- Global note fields: `author`, `timestamp`
- Bug note fields: `category`, `priority`

---

## 8. Advanced Features

### Search Queries

Search by special fields:
```bash
# Record search
aver record search --ksearch status=open
aver record search --ksearch "priority=high"
aver record search --ksearch "severity#>2"

# Note search
aver note search --ksearch category=bugfix
aver note search --ksearch priority=critical
```

#### Search Operators

| Operator | Description | Example |
|----------|-------------|---------|
| `=`  | Equals | `status=open` |
| `!=` | Not equals | `status!=closed` |
| `>`  | Greater than | `severity>2` |
| `<`  | Less than | `severity<4` |
| `>=` | Greater or equal | `severity>=3` |
| `<=` | Less or equal | `severity<=3` |
| `^`  | In (matches any of a pipe-delimited list) | `status^open\|in_progress` |

#### The `^` (In) Operator

The `^` operator matches records or notes where the field value is any one of a pipe-delimited list of values. It is equivalent to a SQL `IN(...)` clause.

```bash
# Match records where status is open OR closed
aver record list --ksearch 'status^open|closed'

# Match records where priority is high OR critical
aver record list --ksearch 'priority^high|critical'

# Combine with other filters (AND logic between different --ksearch flags)
aver record list --ksearch 'status^open|in_progress' --ksearch priority=high

# Works with note search too
aver note search --ksearch 'category^bugfix|investigation'
```

A single-value `^` expression (`status^open`) is equivalent to `status=open`.

Multiple `--ksearch` flags are always combined with AND logic; the `^` operator provides OR logic **within a single field**.

### Database Management

**Initialize a new database**:
```bash
aver admin init
```

**Reindex after manual changes**:
```bash
aver admin reindex
```

#### The `file_index` Table

Every time a record or note is indexed, Aver records three pieces of file metadata in the `file_index` SQLite table (`.aver/aver.db`):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `file_path` | TEXT | Absolute path to the Markdown file |
| `file_hash` | TEXT | MD5 hex digest of the file's UTF-8 content |
| `file_mtime` | TEXT | File modification time (ISO 8601 UTC) at index time |

When **indexing from existing files** (e.g., `admin reindex`), `file_mtime` is read from the filesystem. When a file is indexed **immediately after being written** (e.g., `record new`, `note add`), `file_mtime` reflects the mtime of the newly written file.

This table is useful for:
- Detecting files that have changed since the last index (`file_hash` mismatch)
- Auditing when files were last indexed (`file_mtime`)
- Building external tools that need to track file provenance

`admin reindex` uses this table to skip unchanged files. Entries are updated each time a file is reindexed. Use `--force` to bypass the table entirely and reindex everything unconditionally.

### Library Aliases

Work with multiple databases using library aliases:

**Add a library**:
```bash
aver admin config add-alias --alias work --path /path/to/work/database
```

**Use a library**:
```bash
aver --use work record list
aver --use work record new --title "Work task"
```

**Set per-library user**:
```bash
aver admin config set-user --library work --handle work_user --email work@example.com
```

### Importing from Files

**Import a record from Markdown**:
```bash
aver record new --from-file record.md
```

**File format**:
```markdown
---
title: Imported Record
status: open
priority: high
custom_field: custom_value
---
This is the record description.
```

**Important notes**:
- Non-editable special fields (like `author`, `created_by`) are filtered out
- They will be automatically generated based on current user
- Custom fields can be included with or without type hints

**Import a note**:
```bash
aver note add REC-001 --from-file note.md
```

**Note file format**:
```markdown
---
category: investigation
priority: high
---
Investigation findings...
```

---

## 9. Command Reference

### admin init

Initialize a new database in the current directory.

```bash
aver admin init
```

Creates:
- `.aver/` directory
- `records/` directory
- `updates/` directory
- `.aver/aver.db` (SQLite index)

### admin config

Manage configuration and user settings.

**Set global user**:
```bash
aver admin config set-user --handle alice --email alice@example.com
```

**Set library-specific user**:
```bash
aver admin config set-user --library work --handle work_alice --email work.alice@example.com
```

**Add library alias**:
```bash
aver admin config add-alias --alias project1 --path /path/to/database
```

**List library aliases**:
```bash
aver admin config list-aliases
```

### record new

Create a new record.

**Basic**:
```bash
aver record new
```

**With fields**:
```bash
aver record new --title "Fix login" --status open --priority high
```

**With template**:
```bash
aver record new --template bug --title "App crashes" --severity 3
```

**Show available fields**:
```bash
aver record new --help-fields
aver record new --template bug --help-fields
```

**From file**:
```bash
aver record new --from-file record.md
```

**With custom record ID**:
```bash
aver record new --use-id MY-CUSTOM-ID --title "Custom ID record"
```

### record unmask

Show the plaintext values of one or more fields on a record. Securestring fields are returned unmasked; all other field types are returned with their normal value. Fields that do not exist on the record are silently omitted.

```bash
aver record unmask REC-001 --fields "api_token"
aver record unmask REC-001 --fields "api_token,title,status"
```

**Example output**:
```
api_token: s3cr3t-v4lu3
title: My Record
```

For programmatic use, the `unmask` command is available via **JSON IO**:
```json
{"command": "unmask", "params": {"record_id": "REC-001", "fields": ["api_token", "title"]}}
```

### record update

Update an existing record.

```bash
aver record update REC-001 --status closed
aver record update BUG-042 --priority critical --description "Updated description"
```

**With template scope** — restrict field enforcement to a specific template without importing any content:
```bash
aver record update REC-001 --template bug --severity 3
```

> Note: `--template` on `record update` is field-scope enforcement only. It does **not** copy any content from a template record. This differs from `record new --template`, which also copies initial content if a record named after the template exists.

**Show available fields for this record** (template-aware):
```bash
aver record update REC-001 --help-fields
aver record update REC-001 --help-fields --template bug
```

### record list

List records.

```bash
aver record list
aver record list --limit 10
```

**Paginate with `--offset`**:

```bash
# First page: records 1–10
aver record list --limit 10 --offset 0

# Second page: records 11–20
aver record list --limit 10 --offset 10

# With search filters
aver record list --ksearch status=open --limit 25 --offset 25
```

`--offset` skips the first N results. Use with `--limit` for cursor-style pagination. Default is `0`.

**Count matching records** (requires `--ksearch`):

```bash
aver record list --ksearch status=open --count
aver record list --ksearch "priority=high" --count
```

Returns only the integer count of matching records with no other output.

**Return records with the maximum value of a key** (requires `--ksort`):

```bash
aver record list --ksort severity --max severity
aver record list --ksearch status=open --ksort severity --max severity
aver record list --ksort priority --max priority,severity
aver record list --ksort priority --max priority --max severity
```

`--max` runs the full query (ksearch + ksort + limit) as a working set, then
post-filters to return only records that hold the **maximum value** for any of
the specified keys (keys are evaluated independently; OR logic).  `--ksort` is
required to ensure the relevant records are within the result window.

- `--max KEY` accepts a single key or a comma-delimited list.
- `--max` may be specified more than once.
- Keys are evaluated independently — a record is included if it has the max
  for **any** of the keys.

The `max` parameter is also available via **JSON IO** as a `search-records` parameter:

```json
{"command": "search-records", "params": {"ksort": "severity", "max": "severity"}}
{"command": "search-records", "params": {"ksearch": "status=open", "ksort": "severity", "max": ["severity", "priority"]}}
```

`--offset` is also available via **JSON IO** for both `search-records` and `search-notes`:

```json
{"command": "search-records", "params": {"ksearch": "status=open", "limit": 25, "offset": 25}}
{"command": "search-notes", "params": {"ksearch": "category=bugfix", "limit": 20, "offset": 20}}
```

### record search

Search for records.

```bash
aver record search --ksearch status=open
aver record search --ksearch "priority=high"
aver record search --ksearch "severity#>=3"
```

### note add

Add a note to a record.

**Basic**:
```bash
aver note add REC-001
```

**With message**:
```bash
aver note add REC-001 --message "Investigation complete"
```

**With note fields**:
```bash
aver note add BUG-042 --message "Applied fix" --category bugfix --priority high
```

**Show available fields**:
```bash
aver note add BUG-042 --help-fields
```

**For automation (suppress editor)**:
```bash
aver note add REC-001 --message "Automated check complete" --no-validation-editor
echo "Note text" | aver note add REC-001 --no-validation-editor
```

`--no-validation-editor` prevents the editor from opening on validation failure. If no `--message` and no stdin are provided, the command errors immediately rather than prompting.

**From file**:
```bash
aver note add REC-001 --from-file note.md
```

### note list

List notes for a record.

```bash
aver note list REC-001
aver note list BUG-042
```

### note search

Search notes across all records.

```bash
aver note search --ksearch category=bugfix
aver note search --ksearch priority=critical
```

**Paginate with `--offset`**:

```bash
# First page: notes 1–20
aver note search --ksearch category=bugfix --limit 20 --offset 0

# Next page: notes 21–40
aver note search --ksearch category=bugfix --limit 20 --offset 20
```

**Count matching notes**:

```bash
aver note search --ksearch category=bugfix --count
aver note search --ksearch priority=critical --count
```

Returns only the integer count of matching notes with no other output.

### note unmask

Show the plaintext values of one or more fields on a specific note. Securestring fields are returned unmasked; all other field types are returned with their normal value. Fields that do not exist on the note are silently omitted.

```bash
aver note unmask REC-001 NT-001 --fields "session_token"
aver note unmask REC-001 NT-001 --fields "session_token,author,timestamp"
```

For programmatic use, the `unmask` command is available via **JSON IO** (include `note_id` to target a note):
```json
{"command": "unmask", "params": {"record_id": "REC-001", "note_id": "NT-001", "fields": ["session_token"]}}
```

### admin reindex

Rebuild the search index — all records, or a specific set of records.

```bash
# Full reindex (all records)
aver admin reindex

# Selective reindex (one or more records)
aver admin reindex REC-001
aver admin reindex REC-001 BUG-042 FEAT-007

# Verbose progress output
aver admin reindex --verbose

# Force reindex even if files appear unchanged
aver admin reindex --force
aver admin reindex REC-001 --force

# Skip mtime shortcut; always compare MD5 hash
aver admin reindex --skip-mtime
aver admin reindex REC-001 --skip-mtime

# Skip field validation (index records even if they violate template rules)
aver admin reindex --skip-validation
```

#### Validation during reindex

By default, `admin reindex` validates each record against its template field rules before indexing it. Records that fail validation are **not indexed** and the command exits with an error listing every violation. This prevents non-conforming data from silently entering the search index.

The same rules as `admin validate` apply: required-field presence and `accepted_values` constraints, using the template-specific field set for records that carry a `template_id`.

Use `--skip-validation` to bypass this check and index all records regardless of conformance — useful when intentionally importing legacy data or working with records that pre-date a schema change.

#### How change detection works

`admin reindex` is optimised to skip files that have not changed, making repeated full reindexes fast on large record sets. The check proceeds in two steps:

1. **mtime check** (fast): If the file's modification time matches the value stored in `file_index`, the file is assumed unchanged and skipped.
2. **MD5 hash check** (slower, only if mtime differs): If the mtime has changed, the file is read and its MD5 hash is compared against the stored value. If the hash matches the file is still skipped; if it differs, the file is reindexed.

| Flag | Behaviour |
|------|-----------|
| _(none)_ | mtime check → hash check on mtime miss → skip if match |
| `--skip-mtime` | Skip mtime check; always read file and compare MD5 hash |
| `--force` | Skip all change detection; always reindex every file |
| `--skip-validation` | Skip template field validation before indexing |

Use `--skip-mtime` when files may have been copied with preserved timestamps (e.g. `cp -p`, `rsync -a`, `git checkout`). Use `--force` after schema changes or to recover from a corrupted index.

### admin template-data

Show field definitions for a template — record fields and note fields — as defined in `config.toml`. Useful for building UIs or validating data before submission.

**Show all templates (human-readable)**:
```bash
aver admin template-data
```

**Show a specific template**:
```bash
aver admin template-data bug
```

When no `template_id` is given, global defaults (no template) are also included.

**Example human-readable output**:
```
======================================================================
Template: bug
  Record prefix: BUG
  Note prefix:   COMMENT
======================================================================

  Record fields:
    created_at  (single, string)  [read-only, system:datetime]
    created_by  (single, string)  [required, read-only, system:user_name]
    severity    (single, integer)  [required]
      Accepted: 1, 2, 3, 4, 5
      Default:  3
    status      (single, string)  [required]
      Accepted: new, confirmed, in_progress, fixed, verified, closed
      Default:  new
    title       (single, string)  [required]

  Note fields:
    author      (single, string)  [required, read-only, system:user_name]
    category    (single, string)
      Accepted: investigation, bugfix, workaround, regression, documentation
    timestamp   (single, string)  [required, read-only, system:datetime]
```

**Example JSON output** (single template):
```json
{
  "template_id": "bug",
  "record_prefix": "BUG",
  "note_prefix": "COMMENT",
  "record_fields": {
    "title":      {"type": "single", "value_type": "string", "editable": true, "required": true},
    "status":     {"type": "single", "value_type": "string", "editable": true, "required": true,
                   "accepted_values": ["new","confirmed","in_progress","fixed","verified","closed"],
                   "default": "new"},
    "severity":   {"type": "single", "value_type": "integer", "editable": true, "required": true,
                   "accepted_values": ["1","2","3","4","5"], "default": "3"},
    "created_by": {"type": "single", "value_type": "string", "editable": false, "required": true,
                   "system_value": "user_name"},
    "created_at": {"type": "single", "value_type": "string", "editable": false, "required": false,
                   "system_value": "datetime"}
  },
  "note_fields": {
    "author":    {"type": "single", "value_type": "string", "editable": false, "required": true,
                  "system_value": "user_name"},
    "timestamp": {"type": "single", "value_type": "string", "editable": false, "required": true,
                  "system_value": "datetime"},
    "category":  {"type": "single", "value_type": "string", "editable": true, "required": false,
                  "accepted_values": ["investigation","bugfix","workaround","regression","documentation"]}
  }
}
```

This command is also available via **JSON IO** as the `template-data` command (see JSON IO documentation).

### admin validate

Check that on-disk record files conform to template field rules. Validation covers:

- **Required fields** — every field marked `required = true` must be present and non-empty.
- **Accepted values** — every field with an `accepted_values` list must contain only listed values. Template-specific `accepted_values` override global ones for records that carry a `template_id`.

**Validate all records**:
```bash
aver admin validate
```

**Validate specific records**:
```bash
aver admin validate REC-001
aver admin validate REC-001 BUG-042 FEAT-007
```

**List only failing record IDs** (one per line, useful in scripts):
```bash
aver admin validate --failed-list
aver admin validate REC-001 BUG-042 --failed-list
```

**Exit codes**:
- `0` — all checked records conform (or no records found).
- `1` — one or more records failed validation.

**Example summary output** (default mode):
```
Validation summary: 42 record(s) checked
  Conforming:     39
  Non-conforming: 3

  FAIL  REC-KPZZ17D: field 'status': invalid value 'invalid' (accepted: open, in_progress, resolved, closed)
  FAIL  REC-KSDJO4D: required field 'title' is missing or empty
  FAIL  BUG-0042AB: field 'severity': invalid value '9' (accepted: 1, 2, 3, 4, 5)

Use --failed-list to get a plain list of failing record IDs.
```

**Example `--failed-list` output**:
```
REC-KPZZ17D
REC-KSDJO4D
BUG-0042AB
```

`admin validate` only checks record files; it does not validate note files.

### Reindexing

Use `admin reindex` to reindex records after manually editing Markdown files. Pass one or more record IDs to reindex only those records; omit them for a full reindex. See [admin reindex](#admin-reindex) for the full reference including `--force` and `--skip-mtime`.

---

## 10. Administrator's Guide

### Setting Up Special Fields

**Planning your field structure**:

1. **Identify record types**: What are you tracking? (bugs, features, tasks, experiments)
2. **Define global fields**: Fields that apply to ALL records and notes
3. **Define template fields**: Fields specific to each record type

**Global fields** (all records):
- `title`: Every record needs a title
- `created_by`, `created_at`: Tracking who and when
- `status`: Most workflows have status
- `tags`: General categorization

**Global note fields** (all notes):
- `author`: Who wrote the note
- `timestamp`: When the note was created

**Template-specific fields**:
- Bug records: `severity`, `reproducible`, `component`
- Feature records: `effort`, `stakeholder`, `milestone`
- Bug notes: `category` (investigation, bugfix, etc.)
- Feature notes: `feedback_type`, `implementation_status`

### Designing Templates

**Best practices**:

1. **Start simple**: Begin with a few templates (bug, feature)
2. **Use clear prefixes**: BUG-, FEAT-, TASK- for records; COMMENT-, FEEDBACK- for notes
3. **Inherit smartly**: Let templates add to global fields, not replace them
4. **Constrain carefully**: Use `accepted_values` for fields with clear options
5. **Default wisely**: Set defaults for common values to reduce typing

**Example workflow**:

```toml
# Global fields apply to everything
[record_special_fields.created_by]
system_value = "user_name"
editable = false
required = true

[note_special_fields.author]
system_value = "user_name"
editable = false
required = true

# Bug template adds severity and specific status values
[template.bug]
record_prefix = "BUG"
note_prefix = "COMMENT"

[template.bug.record_special_fields.severity]
type = "single"
value_type = "integer"
accepted_values = ["1", "2", "3", "4", "5"]
default = "3"

[template.bug.note_special_fields.category]
accepted_values = ["investigation", "bugfix", "workaround"]
```

### Managing Multiple Databases

**Use library aliases** for different projects:

```bash
# Set up libraries
aver admin config add-alias --alias personal --path ~/Documents/aver-personal
aver admin config add-alias --alias work --path ~/Work/aver-work

# Configure different users per library
aver admin config set-user --library personal --handle myhandle --email personal@example.com
aver admin config set-user --library work --handle work.name --email work@company.com

# Use them
aver --use personal record new --title "Personal task"
aver --use work record new --template bug --title "Work bug"
```

### Best Practices

1. **Define system fields early**: `created_by`, `created_at`, `author`, `timestamp` should be in every config

2. **Use templates for workflows**: Different record types need different fields

3. **Make non-editable fields clear**: System-populated fields should be `editable = false`

4. **Provide defaults**: Reduce typing with sensible defaults

5. **Document your fields**: Use clear field names and constrained values

6. **Test with small data first**: Set up your config, create test records, iterate

7. **Version control your config**: Keep `config.toml` in Git to track changes

8. **Don't over-constrain**: Only use `accepted_values` when truly necessary

---

## Conclusion

Aver's special fields system provides structure and validation while maintaining the flexibility of plain text storage. By understanding the distinction between global and template-specific fields, and between record and note fields, you can create powerful, type-safe workflows for any tracking need.

**Key takeaways**:
- Special fields define structure, custom fields provide flexibility
- Records and notes have independent field sets
- Templates add fields on top of global fields
- System values automate common fields
- The `--help-fields` flag shows available fields for any context

**Getting help**:
- Use `aver COMMAND --help` for command-specific help
- Use `aver record new --help-fields` to see record fields
- Use `aver note add RECORD --help-fields` to see note fields for that record
- Check your `config.toml` to see all defined fields

**Next steps**:
- Set up your global special fields in `config.toml`
- Define templates for your main workflows
- Use `--help-fields` to discover available fields
- Integrate with Git for version control

Happy tracking!
