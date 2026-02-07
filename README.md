# aver: A Versioned Knowledge Tracking Tool

aver is a file-native system for keeping structured records with full history and fast search — built on plain text and Git.

aver helps you track issues, observations, decisions, and evolving knowledge in a way that is:

- Human-readable
- Version-controlled
- Searchable
- Portable
- Independent of any server or SaaS platform

**If it matters over time, it belongs in aver.**

## What Is aver?

aver is a lightweight tracking system where each record is stored as a Markdown file with structured metadata, and every note adds to that record's history. A local SQLite index provides fast search and filtering, but all source data lives in plain text.

You can use aver for:

- Software issues and technical problem tracking
- Research logs and experimental anomalies
- Engineering deviations and field reports
- Editorial and publishing workflows
- Project knowledge tracking
- Campaign or worldbuilding logs

aver is not tied to any one field. It is a general system for structured records that evolve over time.

---

## Design Invariants

The following design invariants define what aver is and, just as importantly, what it is not. They describe boundaries that shape all features, extensions, and contributions to the project. aver is designed to preserve recorded history and make it navigable over time, not to judge correctness, enforce meaning, or automate workflows. These invariants are intentional constraints: they limit scope, prevent feature creep, and ensure that aver remains a durable, file-native tool whose behavior can always be understood by inspecting its records.

#### 1. Plain-text files are the source of truth

- All authoritative data exists as human-readable files on disk. Tools and indexes derive from files, not the other way around.

#### 2. Versioning is guaranteed; correctness is not

- aver preserves the history of changes but does not attempt to validate or verify the truth of recorded information.

#### 3. The index is a rebuildable performance layer

- The SQLite index is non-authoritative and disposable. All information in the index must be derivable from plain-text files.

#### 4. aver provides structure, not semantics

- Field names and values carry no intrinsic meaning to aver beyond type and comparability. Semantic meaning is defined by repository convention.

#### 5. Records summarize the present; notes preserve the past

- Records may change to reflect current understanding. Notes exist to preserve historical context.

#### 6. aver operates without required services

- aver does not require a server, daemon, or background process. All operations are explicit and user-initiated.

---

## Core Concepts

### Records

A record is the primary unit of information. It can represent an issue, event, observation, task, or any item you want to track over time.

Each record:

- Lives as a Markdown file
- Contains structured fields (metadata)
- Has a unique ID
- Includes a main description

### Notes

A note is a time-stamped addition to a record. Notes capture progress, discoveries, decisions, and historical context.

Notes are stored separately from the main record, preserving a clean structure and a clear timeline.

### Fields

Fields are structured key–value attributes attached to records or notes. They can be used for filtering, sorting, and reporting.

Examples:

```
status = "open"
priority = 2
temperature = 37.5
chapter = 12
```

Fields make aver more than a text log — they make it a queryable knowledge system.

### aver Index

aver uses a local SQLite database as a search index. It enables fast full-text search and structured queries across records and notes.

The index is always rebuildable from the plain-text files.

---

## Key Features

### Plain-Text First

All records and notes are stored as Markdown files. Your data remains readable and usable without aver.

This is fundamental to aver's design philosophy: **your records should outlive any tool**. A text editor and a copy of your repository is sufficient to access everything. No proprietary formats. No vendor dependencies. No API calls required to read what you have written.

### Git-Native Workflow

Because everything is file-based:

- Records can be versioned in Git
- Changes can be reviewed in pull requests
- Branching and merging work naturally
- History is transparent and durable

Your record history becomes part of your project's history. Version control serves dual purpose: both tracking your knowledge and auditing its evolution.

### Structured + Searchable

aver combines freeform text with structured fields, allowing you to:

- Filter by status, tags, or other attributes
- Sort by numeric or textual fields
- Perform full-text search across descriptions and notes

Structure enables traceability of important information — you can ask precise questions of your records and receive consistent, reproducible answers based on recorded history.

### No Server Required

aver runs locally. There is no required web service, database server, or cloud platform.

You can work:

- Offline
- In restricted environments
- Across distributed teams via Git

This independence is not a convenience feature—it is a core design principle. Your ability to access your records should never depend on a third party's availability, business model, or infrastructure decisions.

### Rebuildable Index

If the search index is lost or corrupted, it can be rebuilt entirely from the record and note files.

Your data does not depend on a database. The index is a performance layer, not a storage layer. This distinction matters: it means you can always recover complete functionality from the source files alone.

---

## Example Use Cases

aver is designed to be domain-neutral. Common uses include:

### Software & Technical Work

Track bugs, investigations, and technical decisions alongside your codebase. Each record becomes part of your project's documented knowledge.

### Research & Scientific Work

Maintain a searchable lab log of anomalies, observations, and experiment notes with structured metadata. Verify experimental conditions and trace discoveries to their source.

### Engineering & Field Operations

Record equipment issues, deviations, and field reports in environments with limited connectivity. Sync when you return to the network; work offline without loss of function.

### Publishing & Editorial

Track continuity issues, fact checks, revisions, and production notes across manuscripts and drafts. Verify editorial history and resolve ambiguities through structured notes.

### Long-Term Knowledge Tracking

Use aver as a durable log of decisions, findings, and evolving information for any project. Build a searchable history that remains accessible and understandable years later.

---

## When aver Is Not the Right Tool

aver is intentionally simple and file-based. It may not be a good fit when you need:

- Real-time dashboards and live alerting
- Complex workflow automation or approvals
- Large-scale reporting and business intelligence tools
- A polished, full-featured web UI out of the box

aver focuses on durable records and traceable history, not enterprise workflow management. It is optimized for version tracking and longevity, not for orchestration and real-time operations.

---

## How aver Stores Data

Inside your project or chosen directory:

```
.aver/
  records/        # One Markdown file per record
  notes/          # Time-stamped notes per record
  aver.db         # Rebuildable SQLite search index
  config.toml     # Optional configuration
```

Plain-text files are the source of truth. The index is a performance layer.

---

## Philosophy

### The Core Idea

aver is built on a principle that has outlasted every technology trend: **important knowledge should be recorded in a form that is human-readable, versioned, searchable, and independent of any single platform.**

The underlying belief is simple but radical: your records belong to you, not to a vendor. They should be accessible, readable without special tools, and preserved regardless of business decisions or platform failures.

### What aver Favors

**Longevity over trend**

Technologies come and go. Platforms die. But a plain-text file in a Git repository will be readable in 20 years. aver optimizes for the decades-long view, not the quarterly feature cycle.

**Transparency over abstraction**

You can open any record file in any text editor. You can examine the exact structure. You can understand the data format without consulting documentation or API references. What you see is what exists.

**Portability over platform lock-in**

Your records are not locked in a database or a SaaS service. They live in your repository, under your control. You can move them, fork them, merge them, or process them with other tools. The format is yours to extend and modify.

**Traceability over convenience**

Convenience often comes at a cost: vendor lock-in, data fragility, or loss of control. aver prioritizes the ability to trace how records change over time—to reconstruct history, review evolution, and understand when and how information was recorded.

**Structure over noise**

Freeform notes are easy to create but hard to query. Rigid databases are queryable but fragile. aver balances both: you add structure where it matters (fields for verification and filtering) and preserve the freeform narrative where it belongs (descriptions and notes). The result is both human-readable and machine-queryable.

### Who aver Is For

aver is for people and teams who:

- Work with knowledge that matters beyond the current quarter
- Need to trace decisions and recorded facts to their source
- Operate in environments where external services are unavailable or undesirable
- Want their records to remain usable years from now with nothing more than a text editor and a copy of their repository
- Trust their own infrastructure and version control systems more than third-party platforms

If your records need to live longer than the tools that track them, aver is designed for you.
