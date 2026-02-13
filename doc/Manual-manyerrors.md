# Aver: A Verified Knowledge Tracking Tool

**User Manual**

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
- [Records vs Updates](#records-vs-updates)
- [Metadata and Key-Value Data](#metadata-and-key-value-data)
- [Templates](#templates)
- [Projects and Custom IDs](#projects-and-custom-ids)
- [The Markdown Storage Model](#the-markdown-storage-model)

### 4. Working with Records
- [Creating a New Record](#creating-a-new-record)
- [Viewing Records](#viewing-records)
- [Searching for Records](#searching-for-records)
- [Updating Record Information](#updating-record-information)
- [Understanding Record IDs](#understanding-record-ids)

### 5. Working with Updates (Notes)
- [Adding an Update](#adding-an-update)
- [Viewing Updates](#viewing-updates)
- [Searching Updates](#searching-updates)
- [Update Templates](#update-templates)

### 6. Metadata and Custom Fields
- [Understanding Key-Value Data](#understanding-key-value-data)
- [String Fields](#string-fields)
- [Integer Fields](#integer-fields)
- [Float Fields](#float-fields)
- [Single vs Multi-Value Fields](#single-vs-multi-value-fields)
- [Using the --kv Flag](#using-the---kv-flag)
- [Using the --multi Flag](#using-the---multi-flag)

### 7. Advanced Features
- [Search Queries](#search-queries)
- [Combining Search Criteria](#combining-search-criteria)
- [Search Operators](#search-operators)
- [Database Discovery](#database-discovery)
- [Reindexing](#reindexing)
- [Working with Multiple Databases](#working-with-multiple-databases)

### 8. Templates
- [What are Templates?](#what-are-templates)
- [Creating Record Templates](#creating-record-templates)
- [Creating Update Templates](#creating-update-templates)
- [Using Templates](#using-templates)
- [Template Variables](#template-variables)

### 9. Configuration
- [The .averconfig File](#the-averconfig-file)
- [Project Configuration](#project-configuration)
- [Setting Default Values](#setting-default-values)
- [Configuring Custom ID Patterns](#configuring-custom-id-patterns)
- [Template Configuration](#template-configuration)

### 10. Input Methods
- [Interactive Editor Mode](#interactive-editor-mode)
- [Command Line Input](#command-line-input)
- [Standard Input (Piping)](#standard-input-piping)
- [Metadata-Only Updates](#metadata-only-updates)

### 11. File Format Reference
- [Record File Structure](#record-file-structure)
- [Update File Structure](#update-file-structure)
- [YAML Frontmatter](#yaml-frontmatter)
- [Markdown Body](#markdown-body)

### 12. Command Reference
- [aver init](#aver-init)
- [aver create](#aver-create)
- [aver info](#aver-info)
- [aver list](#aver-list)
- [aver search](#aver-search)
- [aver update](#aver-update)
- [aver note](#aver-note)
- [aver notes](#aver-notes)
- [aver search-notes](#aver-search-notes)
- [aver reindex](#aver-reindex)
- [aver databases](#aver-databases)

### 13. Workflow Examples
- [Bug Tracking Workflow](#bug-tracking-workflow)
- [Field Technician Workflow](#field-technician-workflow)
- [Research Lab Workflow](#research-lab-workflow)
- [Campaign Management for RPGs](#campaign-management-for-rpgs)

### 14. Integration and Collaboration
- [Version Control with Git](#version-control-with-git)
- [Sync Workflows](#sync-workflows)
- [Review and Approval Processes](#review-and-approval-processes)
- [Offline Usage](#offline-usage)

### 15. Tips and Best Practices
- [Organizing Your Database](#organizing-your-database)
- [Naming Conventions](#naming-conventions)
- [Search Optimization](#search-optimization)
- [Template Design](#template-design)
- [Backup Strategies](#backup-strategies)

### 16. Troubleshooting
- [Common Errors](#common-errors)
- [Database Issues](#database-issues)
- [Search Problems](#search-problems)
- [File Permission Issues](#file-permission-issues)

### 17. Appendix
- [Environment Variables](#environment-variables)
- [Editor Configuration](#editor-configuration)
- [Database File Structure](#database-file-structure)
- [Technical Details](#technical-details)

---

## 1. Introduction

### What is Aver?

Aver (pronounced "AH-ver") is a lightweight, flexible knowledge tracking tool designed to help you organize, track, and search through structured information. At its core, Aver manages **records** (primary items you're tracking) and **updates** (chronological notes or changes to those records).

Unlike traditional database systems or issue trackers that lock your data away in proprietary formats, Aver stores everything in plain **Markdown files** with **YAML frontmatter**. This means your data is always readable, portable, and easy to work with using standard text tools. SQLite is used only for indexing and searching—your actual data lives in files you can read, edit, and version control.

### Why Use Aver?

**Human-Readable Storage**: Every record and update is stored as a Markdown file. You can read them with any text editor, search them with `grep`, and track changes with Git.

**Fast Searching**: Despite using plain text files, Aver maintains a SQLite index that enables lightning-fast searches across thousands of records.

**Flexible Metadata**: Add any custom fields you need using key-value pairs. Track priorities, categories, dates, measurements—whatever makes sense for your use case.

**Git-Friendly**: Because everything is text files, your entire database works beautifully with version control. Collaborate with others, track history, and merge changes using standard Git workflows.

**Offline-First**: No internet required. No cloud dependencies. Your data stays on your machine (or wherever you put it).

**Template-Driven**: Create templates for common record types or update patterns to ensure consistency and save time.

### Use Cases

Aver's flexibility makes it suitable for a wide range of applications:

**Software Development**
- Issue and bug tracking that lives alongside your codebase
- Feature request management
- Technical debt tracking
- Sprint planning and task management

**Field Work**
- Equipment maintenance logs for technicians
- Site inspection reports
- Service call documentation
- Offline incident tracking (sync when you're back online)

**Research and Lab Work**
- Experiment tracking and results
- Sample cataloging
- Equipment usage logs
- Research notes and observations

**Creative Projects**
- Story and world-building notes for writers
- Campaign management for tabletop RPGs
- Character development tracking
- Plot thread management

**Personal Organization**
- Project tracking
- Reading lists and notes
- Personal knowledge management
- Learning journals

**Business Operations**
- Customer support ticket tracking
- Vendor issue tracking
- Quality control documentation
- Audit trail maintenance

### Key Features

- **Dual Storage Model**: Records for primary entities, updates for chronological changes
- **Flexible Metadata**: String, integer, and float fields with single or multi-value support
- **Powerful Search**: Query by any metadata field with support for ranges, wildcards, and combinations
- **Templates**: Pre-defined structures for records and updates
- **Custom IDs**: Define your own ID patterns (e.g., BUG-001, FEAT-042)
- **Multiple Databases**: Work with different databases for different projects
- **Editor Integration**: Write in your favorite text editor
- **Pipeline Support**: Integrate with shell scripts via stdin/stdout
- **Auto-Discovery**: Automatically finds databases in your working directory or home folder

### How It Works

Aver uses a simple but powerful three-layer architecture:

**1. Storage Layer (Markdown Files)**
- Records stored as `{record-id}.md` in a `records/` directory
- Updates stored as `{update-id}.md` in `records/{record-id}/updates/` directories
- All files use YAML frontmatter for structured data and Markdown for descriptions

**2. Index Layer (SQLite)**
- A `.aver.db` file maintains searchable indexes
- Tracks all metadata fields for fast queries
- Automatically updated when you create or modify records

**3. Application Layer (Python CLI)**
- Provides a friendly command-line interface
- Handles validation and consistency
- Manages templates and configuration

When you create a record, Aver:
1. Generates a unique ID (or uses your custom ID)
2. Creates a Markdown file with your data
3. Updates the SQLite index for searchability
4. Returns immediately—everything is local

This architecture means you get the speed of a database with the portability of text files.

---

## 2. Getting Started

### Installation

Aver is a Python 3 script with minimal dependencies. To install:

**Prerequisites**:
- Python 3.7 or later
- pip (Python package installer)

**Required Python packages**:
```bash
pip install pyyaml tomli tomli_w
```

**Optional but recommended**:
```bash
# For Python 3.10 and earlier (tomllib is built-in for 3.11+)
pip install tomli
```

**Make the script executable**:
```bash
chmod +x aver.py
```

**For system-wide access**, you can either:

Create a symbolic link:
```bash
sudo ln -s /path/to/aver.py /usr/local/bin/aver
```

Or add an alias to your shell configuration:
```bash
# Add to ~/.bashrc or ~/.zshrc
alias aver='/path/to/aver.py'
```

### System Requirements

- **Operating System**: Linux, macOS, or Windows (with Python installed)
- **Python**: Version 3.7 or later
- **Disk Space**: Minimal (a few MB for the script and dependencies)
- **Editor**: Any text editor (configurable via `$EDITOR` environment variable)

### Creating Your First Database

The easiest way to start is to initialize a database in your current directory:

```bash
# Navigate to your project directory
cd ~/my-project

# Initialize a new Aver database
aver init

# Or initialize with a specific name
aver init --name "Project Bugs"
```

This creates:
- `.aver.db` - The SQLite index file
- `records/` - Directory for record files
- `.averconfig` - Configuration file (optional)

**What gets created**:

```
my-project/
├── .aver.db           # SQLite index (auto-managed)
├── .averconfig        # Configuration (optional)
└── records/           # Your data files
    └── (empty initially)
```

### Understanding Database Locations

Aver can automatically find databases in several locations:

**1. Current Directory**: Aver first looks for `.aver.db` in your current directory.

**2. Parent Directories**: If not found, it walks up the directory tree (like Git).

**3. Home Directory Library**: Checks `~/.local/share/aver/` for named databases.

**4. XDG Data Directory**: On Linux, checks `$XDG_DATA_HOME/aver/`.

You can also explicitly specify a database:

```bash
# Use a specific location
aver --location /path/to/project list

# Use a named database from your library
aver --use my-project list

# Interactively choose from available databases
aver --choose list
```

See available databases:
```bash
aver databases
```

### Configuration Files

Aver uses a `.averconfig` file in TOML format for project-specific settings. This is optional—Aver works fine with defaults.

**Example `.averconfig`**:
```toml
[project]
name = "Bug Tracker"
custom_id_pattern = "BUG-{:03d}"

[templates.record.bug]
kv_strings = { priority = "medium", status = "open" }
body = "## Steps to Reproduce\n\n## Expected Behavior\n\n## Actual Behavior\n"

[templates.update.resolution]
body = "## Resolution\n\n## Root Cause\n\n## Prevention\n"
```

The configuration file lives alongside your `.aver.db` file and travels with your database.

---

## 3. Core Concepts

### Records vs Updates

Understanding the distinction between records and updates is fundamental to using Aver effectively.

**Records** are the primary entities you're tracking:
- Each record has a unique ID (e.g., `001`, `BUG-042`, `npc-gandalf`)
- Records have metadata (key-value fields) and a description
- Records are the "what" you're tracking (a bug, a character, an equipment item)
- Stored in `records/{record-id}.md`

**Updates** (also called "notes") are chronological entries about a record:
- Each update belongs to exactly one record
- Updates have their own ID (timestamp-based by default)
- Updates track changes, observations, or progress over time
- Updates are the "when and how" (status changes, comments, measurements)
- Stored in `records/{record-id}/updates/{update-id}.md`

**Example Relationship**:
```
Record: BUG-042 "Login page timeout"
├─ Update 1: "Confirmed on production, priority raised to high"
├─ Update 2: "Root cause identified: database connection pool"
└─ Update 3: "Fixed in v2.1.0, closing"
```

### Metadata and Key-Value Data

Aver stores structured data using **key-value (KV) fields**. These are like database columns but more flexible.

**Three types of KV fields**:

1. **String fields** (`kv_strings`)
   - Text values: names, categories, status codes
   - Example: `status=open`, `priority=high`, `assignee=alice`

2. **Integer fields** (`kv_integers`)
   - Whole numbers: counts, IDs, years
   - Example: `issue_number=42`, `count=5`, `year=2024`

3. **Float fields** (`kv_floats`)
   - Decimal numbers: measurements, percentages
   - Example: `temperature=98.6`, `completion=0.85`

Each field can be **single-value** or **multi-value**:
- Single: `status=open`
- Multi: `tags=[bug,urgent,security]`

**Why typed fields?**: Different types enable different search operations. You can do range searches on numbers (`priority>5`) but not on strings.

### Templates

Templates provide pre-filled structures for common record or update types. They save time and ensure consistency.

**Record templates** define:
- Default metadata fields and values
- A starting description/body structure

**Update templates** provide:
- Standard note formats (e.g., "status change", "resolution notes")
- Guided structure for documentation

Templates are defined in your `.averconfig` file and invoked by name when creating records or updates.

### Projects and Custom IDs

By default, Aver generates numeric IDs (001, 002, 003...). But you can define your own ID pattern:

**In `.averconfig`**:
```toml
[project]
custom_id_pattern = "TASK-{:03d}"
```

Now records get IDs like `TASK-001`, `TASK-002`, etc.

You can even create multiple ID patterns for different templates:
```toml
[templates.record.bug]
custom_id_pattern = "BUG-{:03d}"

[templates.record.feature]
custom_id_pattern = "FEAT-{:03d}"
```

Or specify custom IDs manually:
```bash
aver create --custom-id "URGENT-001" "Critical issue"
```

### The Markdown Storage Model

Every record and update is a **Markdown file** with **YAML frontmatter**. This format is human-readable and widely supported.

**Structure**:
```markdown
---
timestamp: '2024-02-13T10:30:00'
author: alice
kv_strings:
  status: open
  priority: high
kv_integers:
  issue_number: 42
---

## Description

This is the Markdown body where you write free-form text.

- You can use lists
- **Bold** and *italic*
- Code blocks
- Whatever Markdown supports
```

**Benefits**:
- **Readable**: Open any file in a text editor and understand it
- **Editable**: Make changes directly if needed (then reindex)
- **Portable**: Copy files anywhere, no export/import needed
- **Versionable**: Perfect for Git—text-based diffs work beautifully

---

## 4. Working with Records

### Creating a New Record

The most basic operation is creating a record:

```bash
# Simple creation (opens editor)
aver create

# With a description from command line
aver create --description "Fix the login bug"

# With metadata
aver create --kv priority=high --kv status=open --description "Critical bug"

# From stdin (great for scripting)
echo "Automated alert triggered" | aver create --kv source=monitoring

# Using a template
aver create --template bug
```

**What happens**:
1. Aver generates a unique ID (e.g., `001`)
2. Opens your editor if no description was provided
3. Creates `records/001.md`
4. Updates the search index
5. Prints the new record ID

**Editor mode**: If you don't provide `--description` or pipe in content, Aver opens an editor with:
- A YAML section for metadata (pre-filled if you used `--kv`)
- A Markdown section for the description
- Instructions at the top (removed when saved)

### Viewing Records

View a specific record:

```bash
# Show full details
aver info 001

# Just the description
aver info 001 --description-only
```

**Output includes**:
- Record ID
- Creation timestamp
- Author
- All metadata fields
- Description text

List all records:

```bash
# Brief list
aver list

# Show all metadata
aver list --full
```

**List output**:
```
001 [priority=high status=open] Fix the login bug
002 [priority=medium status=pending] Update documentation
003 [priority=low status=closed] Typo in help text
```

### Searching for Records

Search by metadata fields:

```bash
# Find all open bugs
aver search status=open

# Find high or critical priority items
aver search priority=high,critical

# Combine criteria (AND logic)
aver search status=open priority=high

# Range searches on numbers
aver search "priority>3"

# Just show IDs (for scripting)
aver search status=open --ids-only
```

**Search syntax**:
- `key=value` - Exact match
- `key=val1,val2` - Match any value (OR)
- `key>value` - Greater than (numbers)
- `key>=value` - Greater than or equal
- `key<value` - Less than
- `key<=value` - Less than or equal

Multiple search terms are combined with AND:
```bash
# Open AND high priority
aver search status=open priority=high
```

### Updating Record Information

Modify a record's metadata or description:

```bash
# Update metadata only
aver update 001 --kv status=closed

# Change description (opens editor)
aver update 001 --description "Updated description"

# Add to description via stdin
echo "Additional info" | aver update 001

# Metadata-only update (don't touch description)
aver update 001 --kv priority=urgent --metadata-only
```

**YAML editor mode**: By default, updating a record opens a YAML editor where you can modify fields directly. To skip the editor:

```bash
# No YAML editor, just command-line changes
aver update 001 --kv status=closed --no-yaml
```

**Important**: Updates to records modify the original file. If you want to preserve history, use Git or add an update/note instead.

### Understanding Record IDs

Record IDs are unique identifiers within a database. They can be:

**Numeric (default)**:
- Format: `001`, `002`, `003`, etc.
- Auto-incremented
- Zero-padded to 3 digits

**Custom pattern**:
- Format: Defined in `.averconfig`
- Example: `BUG-001`, `FEAT-042`, `TASK-999`
- Uses Python format strings

**Fully custom**:
- Format: Anything you want
- Specified with `--custom-id` flag
- Example: `urgent-login-issue`, `2024-Q1-report`

**ID requirements**:
- Must be unique within the database
- Can contain letters, numbers, hyphens, underscores
- No slashes or special characters that conflict with file paths

---

## 5. Working with Updates (Notes)

### Adding an Update

Add a chronological note to a record:

```bash
# Opens editor for note
aver note 001

# Quick note from command line
aver note 001 --message "Changed status to in-progress"

# Note with metadata
aver note 001 --kv hours_worked=3 --message "Fixed database query"

# From stdin
echo "Automated deployment successful" | aver note 001 --kv deployed_by=jenkins

# Using a template
aver note 001 --template status-change
```

**Update IDs**: By default, updates get timestamp-based IDs like `20240213_103045_a1b2c3`. This ensures chronological ordering and uniqueness.

**Use cases for updates**:
- Status changes
- Progress reports
- Comments and observations
- Measurements taken at different times
- Resolution notes

### Viewing Updates

See all updates for a record:

```bash
# List all notes
aver notes 001
```

**Output format**:
```
Notes for 001:

[1] 2024-02-13 10:30:45
Author: alice
[hours_worked=3]

Fixed database query by adding an index.

---

[2] 2024-02-13 14:20:00
Author: bob
[status=testing]

Deployed to staging environment for testing.
```

### Searching Updates

Search across all updates in the database:

```bash
# Find updates with specific metadata
aver search-notes hours_worked>5

# Find updates by a specific author
aver search-notes author=alice

# Combine search criteria
aver search-notes status=deployed environment=production

# Just show IDs
aver search-notes status=deployed --ids-only
```

**Search-notes output** shows:
- Parent record ID
- Update ID
- Update content
- Metadata

This is useful for finding when something happened across many records.

### Update Templates

Templates for updates work like record templates but focus on note structure:

**In `.averconfig`**:
```toml
[templates.update.status-change]
kv_strings = { action = "status_change" }
body = """
## Previous Status
old_status

## New Status
new_status

## Reason
reason
"""
```

**Use it**:
```bash
aver note 001 --template status-change
```

The editor opens with the template body pre-filled, ready for you to customize.

---

## 6. Metadata and Custom Fields

### Understanding Key-Value Data

Key-value (KV) fields are Aver's way of storing structured, searchable data alongside your text descriptions.

**Why KV fields?**
- **Search**: Find records by any field (status, priority, assignee, etc.)
- **Type safety**: Numbers are validated and support range searches
- **Flexibility**: Add fields as you need them, no schema required
- **Multi-value support**: One field can have multiple values

**Where KV fields appear**:
- In YAML frontmatter of each file
- In search results and list output
- In the SQLite index for fast queries

### String Fields

String fields store text values.

**Common uses**:
- Status codes (`open`, `closed`, `in-progress`)
- Categories or types (`bug`, `feature`, `documentation`)
- Names (`assignee`, `reporter`, `location`)
- Short labels or tags

**Setting string fields**:
```bash
# Command line
aver create --kv status=open --kv priority=high

# Multiple values
aver create --multi tags=bug,urgent,security
```

**In the file**:
```yaml
kv_strings:
  status: open
  priority: high
  tags:
    - bug
    - urgent
    - security
```

**Searching**:
```bash
# Exact match
aver search status=open

# Match any value (OR)
aver search status=open,closed

# Multi-value field (matches if ANY tag matches)
aver search tags=urgent
```

### Integer Fields

Integer fields store whole numbers.

**Common uses**:
- Counts (`bug_count`, `attempts`, `retries`)
- Version numbers (`version=2`)
- Priority levels (`priority=1` through `5`)
- Reference IDs (`issue_number=42`)

**Setting integer fields**:
```bash
aver create --kv priority#=1 --kv issue_number#=42
```

**Note the `#` suffix**: It tells Aver this is an integer, not a string.

**In the file**:
```yaml
kv_integers:
  priority: 1
  issue_number: 42
```

**Searching with ranges**:
```bash
# Exact match
aver search priority#=1

# Greater than
aver search priority#>3

# Less than or equal
aver search issue_number#<=100

# Between (combine conditions)
aver search priority#>=2 priority#<=4
```

### Float Fields

Float fields store decimal numbers.

**Common uses**:
- Measurements (`temperature=98.6`, `voltage=3.3`)
- Percentages (`completion=0.85`, `confidence=0.95`)
- Rates (`error_rate=0.02`)
- Coordinates (`latitude=47.6062`, `longitude=-122.3321`)

**Setting float fields**:
```bash
aver create --kv temperature%=98.6 --kv completion%=0.85
```

**Note the `%` suffix**: It tells Aver this is a float.

**In the file**:
```yaml
kv_floats:
  temperature: 98.6
  completion: 0.85
```

**Searching**:
```bash
# Range searches work like integers
aver search temperature%>100
aver search completion%>=0.8
```

### Single vs Multi-Value Fields

Fields can have one value or many:

**Single value**:
```yaml
kv_strings:
  status: open
```

**Multiple values**:
```yaml
kv_strings:
  tags:
    - bug
    - urgent
    - security
```

**When to use multi-value**:
- Tags or categories (one item can have multiple tags)
- Affected components (a bug might affect multiple modules)
- Assignments (shared responsibility)
- Related items (cross-references)

### Using the --kv Flag

The `--kv` flag sets single-value fields:

```bash
# String (default)
aver create --kv status=open

# Integer (note the # suffix)
aver create --kv priority#=5

# Float (note the % suffix)
aver create --kv temperature%=98.6

# Multiple fields
aver create --kv status=open --kv priority#=3 --kv assigned=alice
```

**Type suffixes**:
- No suffix or `$` = string
- `#` = integer
- `%` = float

### Using the --multi Flag

The `--multi` flag sets multi-value fields:

```bash
# Multiple strings (comma-separated)
aver create --multi tags=bug,urgent,security

# Multiple integers
aver create --multi related_issues#=42,43,44

# Can combine with --kv
aver create --kv status=open --multi tags=bug,high-priority
```

**In the file**, multi-value fields become lists:
```yaml
kv_strings:
  tags:
    - bug
    - urgent
    - security
```

---

## 7. Advanced Features

### Search Queries

Aver's search system is powerful and flexible.

**Basic syntax**:
```
field_name OPERATOR value
```

**Operators**:
- `=` - Exact match
- `>` - Greater than (numbers only)
- `>=` - Greater than or equal
- `<` - Less than
- `<=` - Less than or equal

**Examples**:
```bash
# Exact match
aver search status=open

# Multiple values (OR logic)
aver search status=open,in-progress,pending

# Number range
aver search priority#>3
aver search priority#>=1 priority#<=3

# String match (any field)
aver search assignee=alice
```

### Combining Search Criteria

Multiple search terms are combined with AND logic:

```bash
# Open AND high priority
aver search status=open priority#=5

# Open AND assigned to Alice AND tagged as bug
aver search status=open assignee=alice tags=bug

# Complex example
aver search status=open,in-progress priority#>3 assignee=alice,bob
# Means: (status is open OR in-progress) AND (priority > 3) AND (assignee is alice OR bob)
```

**Search term format**:
```
field_name=value1,value2  # Any value matches (OR within field)
field1=val field2=val     # All fields must match (AND between fields)
```

### Search Operators

**String operators**:
- `=` - Exact match (case-sensitive)
- `,` - Match any value (OR)

**Number operators**:
- `=` - Exact match
- `>` - Greater than
- `>=` - Greater than or equal
- `<` - Less than
- `<=` - Less than or equal

**Special fields**:
- `author` - Who created the record/update
- `timestamp` - When it was created (searchable as integer timestamp)

**Examples**:
```bash
# All records by Alice
aver search author=alice

# All records created after a certain time (timestamp as integer)
aver search timestamp#>1707840000
```

### Database Discovery

Aver can work with multiple databases and automatically finds them:

**Discovery order**:
1. Current directory (`.aver.db`)
2. Parent directories (walks up like Git)
3. Named databases in `~/.local/share/aver/`
4. XDG data directory on Linux

**List available databases**:
```bash
aver databases
```

**Output shows**:
- **Contextual databases**: In your current path (used by default)
- **Available databases**: In your library folder (use with `--use` flag)

**Using a specific database**:
```bash
# By library name
aver --use my-project list

# By explicit path
aver --location /path/to/.aver.db list

# Interactive selection
aver --choose list
```

**Why multiple databases?**: Separate projects, different contexts, different teams—each can have its own database.

### Reindexing

If you manually edit files or the index gets out of sync, rebuild it:

```bash
# Rebuild the entire index
aver reindex

# Verbose output (shows progress)
aver reindex --verbose
```

**When to reindex**:
- After manually editing `.md` files
- After moving or renaming files
- If search results seem wrong
- After upgrading Aver to a new version

**What it does**:
- Scans all files in `records/`
- Rebuilds SQLite tables
- Re-indexes all metadata
- Validates file integrity

### Working with Multiple Databases

You can maintain separate databases for different projects:

**Create a named database**:
```bash
# In your library folder
mkdir -p ~/.local/share/aver/my-project
aver --location ~/.local/share/aver/my-project init
```

**Or use project-specific databases**:
```bash
# One database per project directory
cd ~/projects/website
aver init

cd ~/projects/mobile-app
aver init

# Each project automatically uses its own database
```

**Switch between databases**:
```bash
# In project directory (auto-discovers)
cd ~/projects/website
aver list

# By name
aver --use my-project list

# By path
aver --location ~/projects/mobile-app/.aver.db list
```

---

## 8. Templates

### What are Templates?

Templates provide pre-filled structures for records and updates. They ensure consistency and save time by providing:
- Default metadata values
- Standard document structures
- Guided prompts for common information

**Two types**:
- **Record templates**: For creating new records
- **Update templates**: For adding notes to records

### Creating Record Templates

Templates are defined in `.averconfig`:

```toml
[templates.record.bug]
kv_strings = { priority = "medium", status = "open", type = "bug" }
kv_integers = { severity = 3 }
custom_id_pattern = "BUG-{:03d}"
body = """
## Steps to Reproduce
1. 
2. 
3. 

## Expected Behavior


## Actual Behavior


## Environment
- OS: 
- Version: 
"""

[templates.record.feature]
kv_strings = { priority = "low", status = "proposed", type = "feature" }
custom_id_pattern = "FEAT-{:03d}"
body = """
## User Story
As a [user type]
I want [goal]
So that [benefit]

## Acceptance Criteria
- [ ] 
- [ ] 
- [ ] 

## Additional Notes

"""
```

**Template structure**:
- `kv_strings` - Default string metadata
- `kv_integers` - Default integer metadata
- `kv_floats` - Default float metadata
- `custom_id_pattern` - Custom ID format for this template
- `body` - Pre-filled Markdown content

### Creating Update Templates

Update templates work similarly but focus on note structure:

```toml
[templates.update.status-change]
kv_strings = { action = "status_change" }
body = """
## Status Change

**Previous Status**: 

**New Status**: 

**Reason**: 


**Next Steps**: 

"""

[templates.update.resolution]
kv_strings = { action = "resolution" }
body = """
## Resolution Summary


## Root Cause


## Fix Applied


## Verification


## Prevention Measures

"""
```

### Using Templates

**Create a record from a template**:
```bash
# Opens editor with template pre-filled
aver create --template bug

# Override template defaults
aver create --template bug --kv priority=high
```

**Add an update from a template**:
```bash
# Opens editor with template structure
aver note 001 --template status-change
```

**What happens**:
1. Template fields are pre-filled in the editor
2. You fill in the blanks
3. Template defaults are merged with your command-line args
4. Command-line args override template defaults

### Template Variables

Templates support basic variable substitution:

```toml
[templates.record.daily-log]
body = """
# Daily Log - $date

## Tasks Completed

## Issues Encountered

## Tomorrow's Plan

"""
```

**Available variables**:
- `$date` - Current date (YYYY-MM-DD)
- `$time` - Current time (HH:MM:SS)
- `$datetime` - Full timestamp
- `$author` - Current user

**Note**: Variable substitution is basic. For complex logic, use editor macros or post-processing scripts.

---

## 9. Configuration

### The .averconfig File

Configuration is stored in `.averconfig` using TOML format. This file is optional—defaults work fine for simple uses.

**Basic structure**:
```toml
[project]
name = "My Project"
custom_id_pattern = "ITEM-{:03d}"

[templates.record.example]
kv_strings = { field = "value" }
body = "Template content"

[templates.update.example]
body = "Update template content"
```

**Location**: The `.averconfig` file lives in the same directory as your `.aver.db` file.

### Project Configuration

The `[project]` section sets database-wide defaults:

```toml
[project]
# Human-readable database name
name = "Website Bug Tracker"

# Default ID pattern for new records
custom_id_pattern = "BUG-{:04d}"

# Default author (if not set, uses system username)
default_author = "team@example.com"
```

**Common settings**:
- `name` - Displayed in prompts and help
- `custom_id_pattern` - Python format string for IDs
- `default_author` - Fallback if `$USER` or `$LOGNAME` isn't set

### Setting Default Values

You can set default metadata for all records:

```toml
[project]
name = "Task Tracker"

[project.defaults.kv_strings]
status = "todo"
priority = "medium"
assignee = "unassigned"

[project.defaults.kv_integers]
estimated_hours = 0
```

**Defaults can be overridden**:
- By templates (template values override project defaults)
- By command-line args (command-line overrides template and defaults)

**Override hierarchy** (highest priority first):
1. Command-line arguments (`--kv`, `--multi`)
2. Template values
3. Project defaults
4. Built-in defaults

### Configuring Custom ID Patterns

Custom ID patterns use Python format strings:

**Simple counter**:
```toml
custom_id_pattern = "TASK-{:03d}"
# Produces: TASK-001, TASK-002, TASK-003
```

**Four-digit padding**:
```toml
custom_id_pattern = "BUG-{:04d}"
# Produces: BUG-0001, BUG-0002, BUG-9999
```

**Year prefix**:
```toml
custom_id_pattern = "2024-{:03d}"
# Produces: 2024-001, 2024-002, 2024-999
```

**Per-template patterns**:
```toml
[templates.record.bug]
custom_id_pattern = "BUG-{:03d}"

[templates.record.feature]
custom_id_pattern = "FEAT-{:03d}"

[templates.record.task]
custom_id_pattern = "TASK-{:03d}"
```

**Format string syntax**:
- `{}` - Insert counter value
- `{:03d}` - Zero-pad to 3 digits
- `{:04d}` - Zero-pad to 4 digits
- Any text around `{}` is literal

### Template Configuration

Templates are defined in dedicated sections:

**Record template format**:
```toml
[templates.record.TEMPLATE_NAME]
kv_strings = { key = "value", ... }
kv_integers = { key = 123, ... }
kv_floats = { key = 1.5, ... }
custom_id_pattern = "PREFIX-{:03d}"
body = """
Multi-line template body
with Markdown content
"""
```

**Update template format**:
```toml
[templates.update.TEMPLATE_NAME]
kv_strings = { key = "value" }
body = """
Template body
"""
```

**Example configuration**:
```toml
[project]
name = "Software Project Tracker"
custom_id_pattern = "ITEM-{:04d}"

[templates.record.bug]
kv_strings = { type = "bug", status = "open", priority = "medium" }
kv_integers = { severity = 3 }
custom_id_pattern = "BUG-{:04d}"
body = """
## Description

## Steps to Reproduce

## Expected vs Actual

"""

[templates.record.feature]
kv_strings = { type = "feature", status = "proposed" }
custom_id_pattern = "FEAT-{:04d}"
body = """
## Feature Request

## Use Case

## Proposed Implementation

"""

[templates.update.daily-update]
kv_strings = { type = "daily" }
body = """
## Progress Today

## Blockers

## Plan for Tomorrow

"""
```

---

## 10. Input Methods

Aver supports multiple ways to provide content, making it flexible for different workflows.

### Interactive Editor Mode

When you don't provide content via command-line or stdin, Aver opens your text editor:

```bash
# Opens editor for record
aver create

# Opens editor for update
aver note 001
```

**What you'll see**:
```markdown
# Edit below this line. Lines starting with # at the top will be removed.
# Save and close to continue, or close without saving to cancel.

---
kv_strings:
  status: open
kv_integers: {}
kv_floats: {}
---

Write your description here.
```

**YAML editor mode**: For updating records, Aver can open a YAML-only editor:

```bash
# Edit metadata in YAML format
aver update 001
```

**YAML editor shows**:
```yaml
# Edit the YAML below, then save and close
kv_strings:
  status: open
  priority: high
kv_integers:
  issue_number: 42
kv_floats: {}
```

**Disable YAML editor**:
```bash
aver update 001 --no-yaml --kv status=closed
```

**Editor selection**:
1. `$EDITOR` environment variable
2. `nano` (fallback)
3. `vi` (last resort)

**Setting your editor**:
```bash
# In ~/.bashrc or ~/.zshrc
export EDITOR=vim
# or
export EDITOR=code  # VS Code
# or
export EDITOR="subl -w"  # Sublime Text
```

### Command Line Input

Provide content directly in the command:

```bash
# With --description
aver create --description "Fix the login timeout issue"

# With --message (for updates)
aver note 001 --message "Changed status to in-progress"

# Include metadata
aver create --kv status=open --kv priority=high --description "Bug found in auth"
```

**Benefits**:
- Fast for short entries
- Scriptable
- No editor launch delay

**Limitations**:
- Hard to write multi-line content
- No spell-check or syntax highlighting
- Less convenient for long descriptions

### Standard Input (Piping)

Feed content from other programs:

```bash
# From a file
cat issue-description.txt | aver create --kv type=bug

# From another command
curl -s https://api.example.com/alerts/latest | aver create --kv source=api

# From a here-doc
aver create --kv status=open <<EOF
## Multi-line Description

Details here...
EOF

# Add metadata too
echo "Deployment completed" | aver note 001 --kv deployed_at=$(date +%s)
```

**Benefits**:
- Perfect for automation and scripts
- Integrate with pipelines
- Process external data sources

**Note**: Stdin overrides `--description` or `--message`. If stdin has data, it's used instead.

### Metadata-Only Updates

Sometimes you only want to change metadata without touching the description:

```bash
# Update fields without opening editor or changing description
aver update 001 --kv status=closed --kv priority=low --metadata-only
```

**Without --metadata-only**:
- Opens editor to change description
- Or requires `--description` or stdin

**With --metadata-only**:
- Changes only the specified fields
- No editor, no description change
- Fast and surgical

**Common use case**:
```bash
# Mark as closed without adding commentary
aver update BUG-042 --kv status=closed --metadata-only

# Change priority
aver update TASK-123 --kv priority=urgent --metadata-only
```

---

## 11. File Format Reference

### Record File Structure

Every record is stored as a Markdown file with YAML frontmatter.

**File path**: `records/{record-id}.md`

**Example file** (`records/001.md`):
```markdown
---
timestamp: '2024-02-13T10:30:00'
author: alice
custom_id: '001'
kv_strings:
  status: open
  priority: high
  assignee: alice
  tags:
    - bug
    - urgent
kv_integers:
  issue_number: 42
  estimated_hours: 8
kv_floats:
  completion: 0.0
---

# Login Timeout Bug

## Description

Users are experiencing timeouts when attempting to log in during peak hours.

## Steps to Reproduce

1. Navigate to /login
2. Enter credentials
3. Click submit
4. Wait for ~30 seconds

## Expected Behavior

Login should complete within 2-3 seconds.

## Actual Behavior

Login times out after 30 seconds with error "Request timeout".

## Environment

- Browser: Chrome 121
- OS: Windows 11
- Time: Between 8-9 AM EST
```

### Update File Structure

Updates are also Markdown files with YAML frontmatter, stored in subdirectories.

**File path**: `records/{record-id}/updates/{update-id}.md`

**Example file** (`records/001/updates/20240213_143000_a1b2c3.md`):
```markdown
---
timestamp: '2024-02-13T14:30:00'
author: bob
kv_strings:
  action: status_change
  old_status: open
  new_status: in-progress
kv_integers:
  hours_worked: 2
kv_floats: {}
---

## Status Update

Changed status from open to in-progress.

## Work Done

- Identified root cause: database connection pool exhaustion
- Implemented connection pooling with max 50 connections
- Added timeout handling for slow queries

## Next Steps

- Deploy to staging for testing
- Monitor connection pool metrics
- Test under load
```

### YAML Frontmatter

The YAML section (between `---` delimiters) contains structured metadata.

**Required fields**:
```yaml
timestamp: '2024-02-13T10:30:00'  # ISO 8601 format
author: username                   # Who created it
```

**For records only**:
```yaml
custom_id: '001'  # The record's ID
```

**Optional metadata fields**:
```yaml
kv_strings:
  field_name: value
  multi_field:
    - value1
    - value2

kv_integers:
  number_field: 42
  multi_numbers:
    - 1
    - 2
    - 3

kv_floats:
  decimal_field: 3.14
  measurements:
    - 1.5
    - 2.5
```

**YAML rules**:
- Use single quotes around strings with special chars
- Timestamps in ISO 8601 format
- Lists use hyphen syntax
- Empty sections can be `{}` or omitted

### Markdown Body

Everything after the second `---` is Markdown content.

**Supported features**:
- Headers (`#`, `##`, `###`)
- **Bold** and *italic* text
- Lists (ordered and unordered)
- Code blocks (fenced with ```)
- Links `[text](url)`
- Images `![alt](path)`
- Blockquotes `>`
- Horizontal rules `---`
- Tables (if your viewer supports them)

**Recommendations**:
- Use headers to organize content
- Include reproducible details for bugs
- Add checklists for tasks
- Link to related records or external resources
- Keep formatting simple for cross-platform compatibility

**Example structure for bugs**:
```markdown
# Bug Title

## Description
Brief overview of the issue.

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen.

## Actual Behavior
What actually happens.

## Additional Context
- Environment details
- Screenshots or logs
- Related issues
```

---

## 12. Command Reference

### aver init

Initialize a new database in the current directory.

**Usage**:
```bash
aver init [--name NAME]
```

**Options**:
- `--name NAME` - Human-readable database name

**Examples**:
```bash
# Simple init
aver init

# With name
aver init --name "Project Bug Tracker"
```

**Creates**:
- `.aver.db` - SQLite index
- `records/` - Storage directory
- `.averconfig` - If you create one later

### aver create

Create a new record.

**Usage**:
```bash
aver create [OPTIONS]
```

**Options**:
- `--kv KEY=VALUE` - Set single-value metadata (repeatable)
- `--multi KEY=VAL1,VAL2` - Set multi-value metadata (repeatable)
- `--description TEXT` - Record description
- `--template NAME` - Use a template
- `--custom-id ID` - Specify custom ID
- `--no-yaml` - Skip YAML editor

**Examples**:
```bash
# Opens editor
aver create

# Quick creation
aver create --description "Fix login bug"

# With metadata
aver create --kv status=open --kv priority=high --description "Critical bug"

# Multi-value field
aver create --multi tags=bug,urgent,security --description "Security issue"

# From template
aver create --template bug

# Custom ID
aver create --custom-id URGENT-001 --description "Emergency fix needed"

# From stdin
echo "Automated alert" | aver create --kv source=monitoring
```

**Returns**: The new record ID

### aver info

View detailed information about a record.

**Usage**:
```bash
aver info RECORD_ID [OPTIONS]
```

**Options**:
- `--description-only` - Show only the description

**Examples**:
```bash
# Full details
aver info 001

# Just description
aver info BUG-042 --description-only
```

**Output includes**:
- Record ID
- Timestamp
- Author
- All metadata fields
- Description

### aver list

List all records.

**Usage**:
```bash
aver list [OPTIONS]
```

**Options**:
- `--full` - Show all metadata (not just IDs and descriptions)
- `--limit N` - Limit output to N records

**Examples**:
```bash
# Brief list
aver list

# With all metadata
aver list --full

# First 10 records
aver list --limit 10
```

**Output format**:
```
001 [status=open priority=high] Fix login bug
002 [status=closed] Update docs
```

### aver search

Search for records by metadata.

**Usage**:
```bash
aver search QUERY... [OPTIONS]
```

**Options**:
- `--limit N` - Limit results to N records
- `--ids-only` - Output only record IDs

**Examples**:
```bash
# By status
aver search status=open

# Multiple values (OR)
aver search status=open,in-progress

# Combined criteria (AND)
aver search status=open priority=high

# Number ranges
aver search priority#>3
aver search priority#>=2 priority#<=4

# Just IDs for scripting
aver search status=open --ids-only
```

**Query syntax**:
- `field=value` - Exact match
- `field=val1,val2` - Match any (OR)
- `field>value` - Greater than
- `field>=value` - Greater than or equal
- `field<value` - Less than
- `field<=value` - Less than or equal

### aver update

Update a record's metadata or description.

**Usage**:
```bash
aver update RECORD_ID [OPTIONS]
```

**Options**:
- `--kv KEY=VALUE` - Update metadata (repeatable)
- `--multi KEY=VAL1,VAL2` - Update multi-value field (repeatable)
- `--description TEXT` - New description
- `--metadata-only` - Update only metadata, not description
- `--no-yaml` - Skip YAML editor
- `--no-validation-editor` - Don't offer editor on validation errors

**Examples**:
```bash
# Update metadata (opens YAML editor)
aver update 001

# Change specific field
aver update 001 --kv status=closed

# Update description
aver update 001 --description "Updated description"

# Metadata only (no editor)
aver update 001 --kv priority=urgent --metadata-only

# Multiple changes
aver update 001 --kv status=closed --kv priority=low --metadata-only

# From stdin
echo "New description" | aver update 001 --no-yaml
```

### aver note

Add an update/note to a record.

**Usage**:
```bash
aver note RECORD_ID [OPTIONS]
```

**Options**:
- `--message TEXT` - Note content
- `--kv KEY=VALUE` - Add metadata to note
- `--multi KEY=VAL1,VAL2` - Multi-value metadata
- `--template NAME` - Use update template
- `--no-yaml` - Skip YAML editor

**Examples**:
```bash
# Opens editor
aver note 001

# Quick note
aver note 001 --message "Changed status to in-progress"

# With metadata
aver note 001 --kv hours_worked#=3 --message "Fixed database query"

# From template
aver note 001 --template status-change

# From stdin
echo "Deployment completed" | aver note 001 --kv deployed_at=$(date +%s)
```

**Returns**: The new update ID

### aver notes

View all updates for a record.

**Usage**:
```bash
aver notes RECORD_ID
```

**Examples**:
```bash
# Show all notes
aver notes 001
aver notes BUG-042
```

**Output format**:
```
Notes for 001:

[1] 2024-02-13 10:30:45
Author: alice
[hours_worked=3]

Fixed database query.

---

[2] 2024-02-13 14:20:00
Author: bob

Deployed to staging.
```

### aver search-notes

Search across all updates.

**Usage**:
```bash
aver search-notes QUERY... [OPTIONS]
```

**Options**:
- `--limit N` - Limit results
- `--ids-only` - Output only IDs (format: `record_id:update_id`)

**Examples**:
```bash
# By author
aver search-notes author=alice

# By metadata
aver search-notes hours_worked#>5

# Combined search
aver search-notes status=deployed environment=production

# Just IDs
aver search-notes status=deployed --ids-only
```

**Output shows**:
- Record ID
- Update ID
- Update content and metadata

### aver reindex

Rebuild the search index.

**Usage**:
```bash
aver reindex [OPTIONS]
```

**Options**:
- `--verbose` - Show progress

**Examples**:
```bash
# Silent reindex
aver reindex

# With progress output
aver reindex --verbose
```

**Use when**:
- Files were manually edited
- Index seems out of sync
- After upgrading Aver

### aver databases

List available databases.

**Usage**:
```bash
aver databases
```

**Shows**:
- Contextual databases (in current path)
- Available databases (in library)
- How to select each database

**Example output**:
```
======================================================================
Available Databases
======================================================================

[Contextual (will be used by default)]
  → Current directory
    /home/user/project/.aver.db

[Available]
    Named database: my-project
    /home/user/.local/share/aver/my-project/.aver.db

======================================================================
Use: --use ALIAS to select by library alias
     --choose to select interactively
     --location PATH to specify explicitly
======================================================================
```

---

## 13. Workflow Examples

### Bug Tracking Workflow

**Setup**:
```bash
cd ~/projects/myapp
aver init --name "MyApp Bug Tracker"
```

**Configure** `.averconfig`:
```toml
[project]
name = "MyApp Bug Tracker"
custom_id_pattern = "BUG-{:04d}"

[templates.record.bug]
kv_strings = { status = "open", priority = "medium", type = "bug" }
kv_integers = { severity = 3 }
body = """
## Description

## Steps to Reproduce
1. 
2. 
3. 

## Expected Behavior

## Actual Behavior

## Environment
"""
```

**Daily workflow**:

1. **Report a bug**:
```bash
aver create --template bug
# Opens editor with bug template
```

2. **List open bugs**:
```bash
aver search status=open type=bug
```

3. **Find high-priority bugs**:
```bash
aver search status=open priority=high,critical
```

4. **Start working on a bug**:
```bash
aver update BUG-0042 --kv status=in-progress --metadata-only
aver note BUG-0042 --message "Started investigating, suspect database connection issue"
```

5. **Log progress**:
```bash
aver note BUG-0042 --kv hours_worked#=2 --message "Found root cause in connection pooling"
```

6. **Close the bug**:
```bash
aver update BUG-0042 --kv status=closed --metadata-only
aver note BUG-0042 --template resolution
```

7. **Track your work**:
```bash
# All bugs you worked on today
aver search-notes author=$(whoami)
```

### Field Technician Workflow

**Scenario**: Traveling technician needs to track equipment issues offline.

**Setup**:
```bash
# Create portable database in a cloud-synced folder
cd ~/Dropbox/work-tracker
aver init --name "Field Service Tracker"
```

**Configure** `.averconfig`:
```toml
[project]
name = "Field Service Tracker"
custom_id_pattern = "SVC-{:05d}"

[templates.record.service-call]
kv_strings = { status = "scheduled", type = "service", priority = "normal" }
body = """
## Customer Information
- Name: 
- Location: 
- Contact: 

## Equipment
- Model: 
- Serial: 
- Issue: 

## Notes

"""

[templates.update.work-performed]
kv_strings = { action = "work" }
kv_integers = { duration_minutes = 0 }
body = """
## Work Performed

## Parts Used

## Resolution Status

## Follow-up Required

"""
```

**In the field**:

1. **Record a new service call**:
```bash
aver create --template service-call
```

2. **Log work**:
```bash
aver note SVC-00042 --template work-performed
```

3. **Quick status update** (no internet needed):
```bash
aver update SVC-00042 --kv status=completed --metadata-only
echo "Replaced faulty power supply. Customer signed off." | aver note SVC-00042
```

4. **Find pending work**:
```bash
aver search status=scheduled,in-progress
```

**Back at the office**:
```bash
# Sync with Git
git add .
git commit -m "Week of Feb 12 service calls"
git push

# Generate weekly report
aver search-notes author=$(whoami) --limit 50
```

### Research Lab Workflow

**Scenario**: Track experiments and results.

**Setup**:
```bash
cd ~/research/protein-study
aver init --name "Protein Folding Experiments"
```

**Configure** `.averconfig`:
```toml
[project]
name = "Protein Folding Experiments"
custom_id_pattern = "EXP-{:04d}"

[templates.record.experiment]
kv_strings = { status = "planned", category = "folding" }
kv_integers = { replications = 3 }
kv_floats = { target_temperature = 37.0 }
body = """
## Hypothesis

## Materials
- 
- 

## Procedure
1. 
2. 
3. 

## Expected Outcomes

"""

[templates.update.observation]
kv_strings = { type = "observation" }
kv_floats = {}
body = """
## Observation

**Date/Time**: 
**Temperature**: 
**pH**: 

## Data

## Notes

"""

[templates.update.result]
kv_strings = { type = "result", outcome = "" }
body = """
## Results Summary

## Data Analysis

## Conclusions

## Next Steps

"""
```

**Running experiments**:

1. **Plan experiment**:
```bash
aver create --template experiment
```

2. **Log observations**:
```bash
aver note EXP-0001 --template observation
# Or quick entry:
aver note EXP-0001 --kv temperature%=36.8 --kv ph%=7.2 <<EOF
Sample showed increased folding rate at T+2h.
Fluorescence intensity: 450nm peak.
EOF
```

3. **Record final results**:
```bash
aver note EXP-0001 --template result
aver update EXP-0001 --kv status=completed --metadata-only
```

4. **Find all completed experiments**:
```bash
aver search status=completed category=folding
```

5. **Temperature-range analysis**:
```bash
aver search-notes temperature%>=35 temperature%<=40
```

### Campaign Management for RPGs

**Scenario**: Dungeon Master tracking a D&D campaign.

**Setup**:
```bash
cd ~/dnd/forgotten-realms
aver init --name "Forgotten Realms Campaign"
```

**Configure** `.averconfig`:
```toml
[project]
name = "Forgotten Realms Campaign"

[templates.record.npc]
kv_strings = { type = "npc", status = "active", alignment = "neutral" }
kv_integers = { level = 1 }
custom_id_pattern = "NPC-{:03d}"
body = """
## Description

## Personality

## Appearance

## Background

## Motivations

## Relationships

"""

[templates.record.location]
kv_strings = { type = "location", status = "undiscovered" }
custom_id_pattern = "LOC-{:03d}"
body = """
## Description

## Notable Features

## Inhabitants

## Secrets

## Connections

"""

[templates.record.quest]
kv_strings = { type = "quest", status = "active", difficulty = "medium" }
custom_id_pattern = "QUEST-{:03d}"
body = """
## Quest Giver

## Objective

## Rewards

## Complications

## Outcomes

"""

[templates.update.session-note]
kv_strings = { type = "session" }
kv_integers = { session_number = 0 }
body = """
## Session Summary

## Player Actions

## DM Notes

## Consequences

## Next Session Setup

"""
```

**Running the campaign**:

1. **Create NPCs**:
```bash
aver create --template npc
```

2. **Track quests**:
```bash
aver create --template quest --kv status=active --kv difficulty=hard
```

3. **Session notes**:
```bash
aver note QUEST-001 --template session-note --kv session_number#=5
```

4. **Quick NPC interaction note**:
```bash
echo "Players negotiated with Thorin, agreed to help defend village." | \
  aver note NPC-007
```

5. **Find active quests**:
```bash
aver search type=quest status=active
```

6. **Find all NPCs in a location**:
```bash
aver search type=npc location=waterdeep
```

7. **Review session history**:
```bash
aver search-notes type=session
```

---

## 14. Integration and Collaboration

### Version Control with Git

Aver's file-based storage is perfect for Git:

**Initialize Git**:
```bash
cd ~/projects/myapp
aver init
git init
```

**Create `.gitignore`**:
```
# Ignore SQLite index (it's rebuilt from files)
.aver.db

# Optionally ignore SQLite temp files
.aver.db-journal
.aver.db-wal
.aver.db-shm
```

**Why ignore `.aver.db`**:
- It's a binary file (bad for Git)
- It can be regenerated with `aver reindex`
- Markdown files are the source of truth

**Daily workflow**:
```bash
# Create and modify records
aver create --template bug
aver note BUG-001 --message "Fixed in v2.1.0"

# Commit changes
git add records/
git commit -m "Added bug reports and updates"
git push
```

**Collaborating**:
```bash
# Pull changes from team
git pull

# Rebuild index from updated files
aver reindex

# Now search works with latest data
aver search status=open
```

### Sync Workflows

**Dropbox/Google Drive sync**:
```bash
# Create database in synced folder
cd ~/Dropbox/work-tracker
aver init

# Work normally—Dropbox syncs files automatically
aver create --description "New issue"

# On another machine:
cd ~/Dropbox/work-tracker
aver reindex  # Rebuild index from synced files
aver list
```

**USB drive for offline work**:
```bash
# On office computer
cd /media/usb/work-db
aver create --description "Site inspection needed"

# In the field (laptop, no internet)
cd /media/usb/work-db
aver note 001 --message "Inspection completed"

# Back at office
aver reindex
# Optionally sync to central Git repo
git push origin main
```

### Review and Approval Processes

Aver + Git enables code-review-style workflows:

**Workflow**:

1. **Technician creates records**:
```bash
git checkout -b technician-week-7
aver create --template service-call
# ... create multiple records ...
git add records/
git commit -m "Week 7 service calls"
git push origin technician-week-7
```

2. **Supervisor reviews**:
```bash
git checkout technician-week-7
aver list
aver info SVC-00042
# Review content in GitHub/GitLab web interface
```

3. **Supervisor approves**:
```bash
# Add approval note
aver note SVC-00042 --message "Approved by supervisor" --kv approved=true

git add .
git commit -m "Approved service calls"
git checkout main
git merge technician-week-7
git push origin main
```

**Benefits**:
- All standard Git tools work (pull requests, code review)
- Diffs show exactly what changed
- History is preserved
- Easy to audit and rollback

### Offline Usage

Aver is fully functional offline:

**Offline features**:
- Create and modify records
- Search existing data
- Add updates
- Full CRUD operations

**Offline workflow**:
```bash
# Before going offline, ensure you have latest data
git pull
aver reindex

# Work offline
aver create --description "Field observation"
aver search status=pending
aver note 001 --message "Completed"

# When back online, sync
git add records/
git commit -m "Offline work - Feb 13"
git push
```

**Conflict resolution**:
If two people edit the same file offline:

```bash
# After git pull shows conflicts
git status  # Shows conflicted files

# Manually resolve in editor, or:
# 1. Keep one version
# 2. Reindex
aver reindex

git add records/
git commit -m "Resolved conflicts"
```

**Tip**: Use different custom ID ranges for different users to avoid conflicts:
```toml
# User A
custom_id_pattern = "A-{:03d}"

# User B  
custom_id_pattern = "B-{:03d}"
```

---

## 15. Tips and Best Practices

### Organizing Your Database

**Use meaningful metadata fields**:
```bash
# Good: Descriptive, searchable
aver create --kv status=open --kv priority=high --kv component=auth

# Less useful: Vague or redundant
aver create --kv thing=stuff
```

**Choose appropriate field types**:
```bash
# Numbers that you'll search by range -> integers or floats
aver create --kv priority#=5  # Can search: priority#>3

# Categories -> strings
aver create --kv status=open  # Can search: status=open,closed
```

**Use multi-value fields for tags**:
```bash
# One tag system, not multiple fields
aver create --multi tags=urgent,security,customer-facing

# Not: --kv urgent=true --kv security=true --kv customer_facing=true
```

### Naming Conventions

**Field names**:
- Use lowercase with underscores: `issue_number`, `assigned_to`
- Be consistent across records
- Avoid special characters

**Custom IDs**:
- Keep them short and readable: `BUG-001`, not `INTERNAL-CRITICAL-SECURITY-BUG-001`
- Use consistent patterns within a database
- Include context if useful: `2024-Q1-001`

**Template names**:
- Descriptive: `bug`, `feature-request`, `daily-log`
- Not cryptic: `tmpl1`, `x`, `temp`

### Search Optimization

**Index-friendly searches**:
```bash
# Specific field matches are fast
aver search status=open

# Multiple criteria narrow results quickly
aver search status=open priority=high component=database

# Range searches on indexed fields are fast
aver search priority#>3
```

**Avoid**:
- Searching on non-existent fields (no results, but not an error)
- Too-broad searches that return everything

**Use --ids-only for scripting**:
```bash
# Efficient pipeline
aver search status=open --ids-only | while read id; do
  aver note "$id" --message "Reminder: please update"
done
```

### Template Design

**Good templates are**:
- **Focused**: One template per record/update type
- **Structured**: Use headers and sections
- **Prompting**: Include placeholders that guide users

**Example good template**:
```toml
[templates.record.bug]
body = """
## Description
[What is the bug?]

## Steps to Reproduce
1. 
2. 
3. 

## Expected vs Actual
- Expected: 
- Actual: 

## Additional Context
- Browser/OS: 
- Version: 
- Screenshot/Logs: 
"""
```

**Example poor template**:
```toml
[templates.record.bug]
body = "Bug description goes here"
```

**Use metadata in templates**:
```toml
# Pre-fill common values
[templates.record.bug]
kv_strings = { status = "open", priority = "medium", type = "bug" }

# Users override as needed
aver create --template bug --kv priority=high
```

### Backup Strategies

**Option 1: Git (recommended)**:
```bash
# Regular commits = automatic backups
git add records/
git commit -m "Daily updates"
git push  # Remote = off-site backup
```

**Option 2: Periodic snapshots**:
```bash
# Zip entire database
cd ~/projects/myapp
tar czf backups/myapp-$(date +%Y%m%d).tar.gz .aver* records/ .averconfig

# Or rsync to backup drive
rsync -av ~/projects/myapp/ /backup/myapp/
```

**Option 3: Cloud sync**:
- Store database in Dropbox/Google Drive/OneDrive
- Automatic sync and versioning
- `aver reindex` after sync to update index

**What to backup**:
- `records/` directory (essential)
- `.averconfig` (if you have one)
- NOT `.aver.db` (rebuilt with `aver reindex`)

---

## 16. Troubleshooting

### Common Errors

**"Error: Record not found"**:
```bash
aver info 999
# Error: Record 999 not found
```
**Solution**: Check ID with `aver list` or `aver search`.

**"Error: No fields to update"**:
```bash
aver update 001
# Error: No fields to update
```
**Solution**: Provide `--kv`, `--multi`, `--description`, or content via stdin.

**"Error: No database found"**:
```bash
aver list
# Error: No database found
```
**Solution**:
- Run `aver init` first
- Or use `--location` to specify database path
- Or `--choose` to select from available databases

**"Error: Invalid custom_id format"**:
```bash
aver create --custom-id "my/id"
# Error: Invalid custom_id format
```
**Solution**: Avoid slashes and special chars. Use hyphens and underscores.

### Database Issues

**Search returns wrong results**:

**Cause**: Index out of sync with files.

**Solution**:
```bash
aver reindex
```

**Database corrupted**:

**Cause**: Interrupted write, disk error, manual file damage.

**Solution**:
```bash
# Try reindex first
aver reindex --verbose

# If that fails, restore from backup
# Delete .aver.db
rm .aver.db

# Reinitialize
aver init

# Reindex from files
aver reindex
```

**Can't find database**:

**Symptom**: `aver list` says "No database found" but you know it exists.

**Solution**:
```bash
# Explicitly specify location
aver --location /path/to/.aver.db list

# Or check available databases
aver databases

# Make sure you're in the right directory
pwd
ls -la .aver.db
```

### Search Problems

**Search returns nothing but records exist**:

**Possible causes**:
1. **Wrong field name**: Check exact field names in records
2. **Type mismatch**: Searching `priority=5` (string) vs `priority#=5` (integer)
3. **Index out of sync**: Run `aver reindex`

**Check record structure**:
```bash
aver info 001
# Look at kv_strings, kv_integers, kv_floats sections
```

**Search is slow**:

**Cause**: Database hasn't been reindexed recently with many new records.

**Solution**:
```bash
aver reindex
```

**Search with special characters fails**:

**Issue**: Shell interprets special chars.

**Solution**: Quote your search:
```bash
aver search "priority#>3"
aver search "tags=bug,urgent"
```

### File Permission Issues

**"Permission denied" when creating records**:

**Cause**: No write permission on `records/` directory.

**Solution**:
```bash
# Check permissions
ls -ld records/

# Fix permissions
chmod u+w records/
```

**"Permission denied" on `.aver.db`**:

**Cause**: Database file is read-only.

**Solution**:
```bash
chmod u+w .aver.db
```

**Multiple users, permission conflicts**:

**Setup shared database**:
```bash
# Create group
sudo groupadd aver-users
sudo usermod -a -G aver-users alice
sudo usermod -a -G aver-users bob

# Set permissions
sudo chgrp -R aver-users /path/to/database/
sudo chmod -R g+w /path/to/database/
sudo chmod g+s /path/to/database/records/  # New files inherit group
```

---

## 17. Appendix

### Environment Variables

**EDITOR**:
- Sets default text editor
- Example: `export EDITOR=vim`
- Used when Aver opens editor for input

**XDG_DATA_HOME**:
- Base directory for user data (Linux)
- Aver looks in `$XDG_DATA_HOME/aver/` for named databases
- Default: `~/.local/share`

**USER / LOGNAME**:
- Determines default author name
- Usually set by your system

**AVER_DATABASE** (if supported in future):
- Could override database location
- Not currently implemented

### Editor Configuration

Aver respects your `$EDITOR` setting:

**Vim users** (`.bashrc` / `.zshrc`):
```bash
export EDITOR=vim
```

**Emacs users**:
```bash
export EDITOR=emacs
```

**VS Code** (waits for window to close):
```bash
export EDITOR="code --wait"
```

**Sublime Text**:
```bash
export EDITOR="subl -w"
```

**Nano** (default if $EDITOR not set):
```bash
export EDITOR=nano
```

**Testing your editor**:
```bash
echo $EDITOR
aver create  # Should open your preferred editor
```

### Database File Structure

**Directory layout**:
```
project/
├── .aver.db              # SQLite index (ignore in Git)
├── .averconfig           # Configuration (optional)
└── records/              # All record files
    ├── 001.md            # Record 001
    ├── 001/              # Updates for record 001
    │   └── updates/
    │       ├── 20240213_103000_abc123.md
    │       └── 20240213_140000_def456.md
    ├── 002.md            # Record 002
    ├── 002/
    │   └── updates/
    │       └── 20240213_150000_ghi789.md
    └── BUG-042.md        # Custom ID record
        └── updates/
            └── 20240214_090000_jkl012.md
```

**File naming**:
- Records: `{record-id}.md`
- Updates: `{timestamp}_{random-suffix}.md`
- Directories: `{record-id}/updates/`

**SQLite schema** (for reference):
- `incidents` table: Stores record metadata
- `updates` table: Stores update metadata
- Indexes on common search fields

### Technical Details

**Dependencies**:
- Python 3.7+
- PyYAML: YAML parsing
- tomllib/tomli: TOML parsing (config files)
- tomli_w: TOML writing
- sqlite3: Built-in Python library

**Performance characteristics**:
- **File operations**: Fast for small to medium databases (<10,000 records)
- **Search**: Fast via SQLite indexes (milliseconds for most queries)
- **Reindexing**: Scales linearly with number of records (seconds for thousands)

**Limitations**:
- Not designed for massive scale (100,000+ records might be slow)
- No built-in concurrency control (use Git for collaboration)
- No rich media support (text and metadata only)
- No built-in attachment handling (reference files by path in Markdown)

**Platform support**:
- Linux: Fully supported
- macOS: Fully supported
- Windows: Supported (use Git Bash or WSL for best experience)
- All platforms with Python 3.7+

**Storage overhead**:
- Markdown files: ~1-10 KB each (mostly text)
- SQLite index: ~10-100 KB for typical databases
- Very lightweight compared to traditional databases

---

## Conclusion

Aver is a flexible, powerful tool for tracking structured knowledge in a portable, future-proof format. Whether you're managing bugs, tracking experiments, organizing research, or running a D&D campaign, Aver gives you the power of a database with the simplicity of text files.

**Key takeaways**:
- Records and updates provide a simple but powerful model
- Markdown + YAML = human-readable, version-controllable storage
- SQLite indexing = fast searches without sacrificing portability
- Templates = consistency and time savings
- Git integration = collaboration and history tracking

**Getting help**:
- Read this manual for comprehensive coverage
- Use `aver COMMAND --help` for command-specific help
- Check file examples in `records/` to see the format
- Experiment with small databases first

**Next steps**:
- Initialize your first database: `aver init`
- Create a few test records: `aver create`
- Search and explore: `aver search`, `aver list`
- Set up templates for your use case
- Integrate with Git for collaboration

Happy tracking!
