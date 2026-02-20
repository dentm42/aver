# Maintainer’s Integration Guide: Using Aver in Your Project

Aver is designed to be a **Git-resident** knowledge store. Integrating it into your open-source project allows you to track issues, decisions, and documentation alongside your code, ensuring your project's history stays portable and indestructible.

## 1. Repository Placement

For project-wide consistency, place the `aver.py` script in your repository (suggested in the root or ./bin).

```bash
# Example structure
my-project/
├── bin/
│   └── aver.py        # The project-sanctioned engine
├── .aver/
│   └── config.toml    # The project's schema/fields
├── records/           # The issue/knowledge store
└── updates/           # The chronological notes

```

## 2. Repository Hygiene (`.gitignore`)

Aver uses a local SQLite database (`.aver/aver.db`) as a high-speed search index. This file is a **disposable cache** reconstructed from your Markdown files; it should never be committed to Git.

Add the following to your project's **`.gitignore`**:

```ignore
# Aver Search Index (Disposable cache)
.aver/*.db

# Optional: Personal user overrides
.aver/user.toml

```

## 3. Onboarding Contributors

To ensure contributors use the correct version of Aver and the project’s specific data store, we recommend they use the `aver-wrapper.sh` found in the `helpers/` directory.

### **Suggested Language for your CONTRIBUTING.md:**

> This project uses **Aver** for knowledge and issue tracking. To ensure you are using the project-sanctioned version of the engine, please install the wrapper:
> 1. Copy `helpers/aver-wrapper.sh` to your local `~/bin/` (or anywhere in your `$PATH`).
> 2. Rename it to `aver` and make it executable: `chmod +x ~/bin/aver`.
> 3. Now, typing `aver` inside this repository will automatically find and use the local `bin/aver.py` and the project’s records.
> 
> 

## 4. Why This Matters for Maintainers

* **Version Parity**: Every contributor uses the exact same version of the engine that you have vetted for the project.
* **Schema Enforcement**: By committing `.aver/config.toml`, you ensure every record created by a contributor follows your project's specific metadata requirements (e.g., `status`, `severity`, `component`).
* **CI/CD Ready**: Because the data is plain Markdown, you can run grep, awk, or Aver's own JSON export in your CI pipelines to validate project state before merging.

---

### Next Step for you:

I've kept this focused on the "Maintainer as Steward" role. Would you like me to take a stab at consolidating those four JSON files into a single **`JSON_BRIDGE.md`** next, so the technical "engine" documentation is as clean as this integration guide?
