# Aver Integration & Adoption Guide

Aver is built on a singular strategic claim: **Issues ARE Code.** In modern software development, we treat our source code as a sovereign asset—versioned, branched, and portable via Git. Yet, we often allow our project’s "why" (its issues, decisions, and history) to be held hostage by proprietary SaaS platforms. If you move your repository, your history stays behind.

Aver restores digital stewardship by keeping your records inside your repository. This guide explains how to integrate Aver into your project as a first-class citizen.

## 1. The Strategy: Why Reside with the Code?

* **Zero-Migration Sovereignty**: When your issues reside with the code, your "Issues Home" is wherever your code lives. If you move from GitHub to a private Gitea instance or a local server, your full history moves with a simple `git push`.
* **Atomic History**: Because Aver is Git-native, a "Fixed" status can be committed in the same transaction as the code that fixed it. Your issue tracker and your codebase never drift apart.
* **Offline Truth**: Developers can query, update, and search the full project history while offline. The "Authority" is always on your local disk.

## 2. Repository Placement
For project-wide consistency, place the `aver.py` engine in a directory within your repository (e.g., `./bin/` or `./tools/`). 

```bash
# Recommended structure
my-project/
├── bin/
│   └── aver.py        # The project-sanctioned engine
├── .aver/
│   └── config.toml    # The project's schema and field definitions
├── records/           # The indestructible knowledge store
└── updates/           # The chronological notes

```

## 3. Repository Hygiene (`.gitignore`)

Aver uses a local SQLite database (`.aver/aver.db`) as a high-speed search "Lens." This file is a **disposable cache** reconstructed from your Markdown files; it should never be committed to Git.

Add the following to your project's **`.gitignore`**:

```ignore
# Aver Search Index (Disposable cache - The Authority is the Markdown)
.aver/*.db

```

## 4. Onboarding Contributors

To ensure every contributor uses the project-sanctioned version of the engine, encourage the use of the `aver-wrapper.sh` helper.

### **Suggested Language for your CONTRIBUTING.md:**

> **Digital Stewardship**: This project treats issues as code. Our records are stored as Markdown artifacts within this repository using **Aver**.
> To interact with the project records, we recommend installing the Aver wrapper:
> 1. Copy `helpers/aver-wrapper.sh` from this repo to your local `~/bin/` (or your `$PATH`).
> 2. Rename it to `aver` and run `chmod +x ~/bin/aver`.
> 3. Typing `aver` anywhere in this repo will now automatically use the project's local engine and data store.
> 
> 

## 5. CI/CD Integration

Since your issues are just Markdown and YAML, you can use the **JSON Bridge** in your CI pipelines to enforce project standards:

```bash
# Example: Fail the build if any record is marked 'blocker'
aver json search-records --ksearch "status=blocker" | jq -e '.count == 0'

```

---

*Aver: What matters should be recorded. What is recorded should be searchable. What is searchable should endure.*
