# Implementation: aver record reindex RECORD_ID

## Code Changes Required

### 1. Add to IncidentIndexManager class (after reindex_all method, around line 3765)

```python
def reindex_one(self, incident_id: str, verbose: bool = False) -> bool:
    """
    Reindex a single incident and all its notes from files.
    
    Args:
        incident_id: The record ID to reindex
        verbose: Print progress messages
    
    Returns:
        True if successful, False if record not found
    """
    # Check if record exists
    incident = self.storage.load_incident(incident_id, self.project_config)
    if not incident:
        if verbose:
            print(f"Record {incident_id} not found")
        return False
    
    if verbose:
        print(f"Reindexing {incident_id}...")
    
    # Remove existing index entries for this record
    self.index_db.remove_incident_from_index(incident_id)
    
    # Reindex the incident
    self.index_db.index_incident(incident, self.project_config)
    self.index_db.index_kv_data(incident, self.project_config)
    
    if verbose:
        print(f"  ✓ Record indexed")
    
    # Reindex all notes for this incident
    updates = self.storage.load_updates(incident_id)
    
    if verbose and updates:
        print(f"  Reindexing {len(updates)} notes...", end="")
    
    for update in updates:
        self.index_db.index_update(update)
        if verbose:
            print(".", end="", flush=True)
    
    if verbose and updates:
        print()  # Newline after dots
    
    if verbose:
        print(f"✓ Reindexed {incident_id} ({len(updates)} notes)")
    
    return True
```

### 2. Add CLI command handler (after _cmd_record_update, around line 5600)

```python
def _cmd_record_reindex(self, args):
    """Reindex a specific record and its notes."""
    manager = self._get_manager(args)
    
    success = manager.index_manager.reindex_one(
        args.record_id,
        verbose=True
    )
    
    if not success:
        print(f"Error: Record {args.record_id} not found", file=sys.stderr)
        sys.exit(1)
```

### 3. Add CLI parser (in setup_commands, after record_update_parser, around line 7150)

```python
# record reindex
record_reindex_parser = record_subparsers.add_parser(
    "reindex",
    help="Reindex a specific record and all its notes from disk files",
)

record_reindex_parser.add_argument(
    "record_id",
    help="Record ID to reindex"
)
```

---

## Complete Diff

### Location 1: IncidentIndexManager class (~line 3765)

```python
# After the reindex_all method, add:

    def reindex_one(self, incident_id: str, verbose: bool = False) -> bool:
        """
        Reindex a single incident and all its notes from files.
        
        Args:
            incident_id: The record ID to reindex
            verbose: Print progress messages
        
        Returns:
            True if successful, False if record not found
        """
        # Check if record exists
        incident = self.storage.load_incident(incident_id, self.project_config)
        if not incident:
            if verbose:
                print(f"Record {incident_id} not found")
            return False
        
        if verbose:
            print(f"Reindexing {incident_id}...")
        
        # Remove existing index entries for this record
        self.index_db.remove_incident_from_index(incident_id)
        
        # Reindex the incident
        self.index_db.index_incident(incident, self.project_config)
        self.index_db.index_kv_data(incident, self.project_config)
        
        if verbose:
            print(f"  ✓ Record indexed")
        
        # Reindex all notes for this incident
        updates = self.storage.load_updates(incident_id)
        
        if verbose and updates:
            print(f"  Reindexing {len(updates)} notes...", end="")
        
        for update in updates:
            self.index_db.index_update(update)
            if verbose:
                print(".", end="", flush=True)
        
        if verbose and updates:
            print()  # Newline after dots
        
        if verbose:
            print(f"✓ Reindexed {incident_id} ({len(updates)} notes)")
        
        return True
```

### Location 2: Add command handler (~line 5600, after _cmd_record_update)

```python
    def _cmd_record_reindex(self, args):
        """Reindex a specific record and its notes."""
        manager = self._get_manager(args)
        
        success = manager.index_manager.reindex_one(
            args.record_id,
            verbose=True
        )
        
        if not success:
            print(f"Error: Record {args.record_id} not found", file=sys.stderr)
            sys.exit(1)
```

### Location 3: Add CLI parser (~line 7150, after record_update_parser setup)

```python
        # record reindex
        record_reindex_parser = record_subparsers.add_parser(
            "reindex",
            help="Reindex a specific record and all its notes from disk files",
        )
        
        record_reindex_parser.add_argument(
            "record_id",
            help="Record ID to reindex"
        )
```

---

## Usage Examples

### Basic Usage

```bash
# Reindex a single record
aver record reindex ISS-042

# Output:
# Reindexing ISS-042...
#   ✓ Record indexed
#   Reindexing 5 notes........
# ✓ Reindexed ISS-042 (5 notes)
```

### Use Cases

#### 1. Manual File Edit

```bash
# Edit file directly
vim records/ISS-042.md
# Change: priority: medium → priority: high

# Reindex to update search
aver record reindex ISS-042

# Now searchable
aver record list --ksearch priority=high
# ISS-042
```

#### 2. Bulk Script Modification

```bash
#!/bin/bash
# Bulk update all "backend" labels to "server"

for record in records/*.md; do
    sed -i 's/labels:.*backend/labels: server/' "$record"
    
    # Extract record ID
    record_id=$(basename "$record" .md)
    
    # Reindex
    aver record reindex "$record_id"
done
```

#### 3. Import from External System

```bash
# Create record file manually
cat > records/IMPORT-001.md << 'EOF'
---
title: Imported from Jira
status: open
priority: high
external_id: JIRA-12345
---

Issue description imported from external system.
EOF

# Reindex to make searchable
aver record reindex IMPORT-001

# Verify
aver record view IMPORT-001
```

#### 4. Fix Corrupted Index

```bash
# If search results are stale
aver record list --ksearch status=open
# (doesn't show recently edited ISS-042)

# Reindex specific record
aver record reindex ISS-042

# Now appears in search
aver record list --ksearch status=open
# ISS-042
```

#### 5. Note Recovery

```bash
# Manually restore deleted note from backup
cp backup/updates/ISS-042/NT-003.md updates/ISS-042/

# Reindex to make note searchable
aver record reindex ISS-042

# Note now appears
aver note list ISS-042
# NT-001
# NT-002
# NT-003  ← restored
```

---

## Implementation Benefits

### 1. Filesystem-First Philosophy ✅

Emphasizes that files are the source of truth:
- Edit files directly with any tool
- Reindex brings search index in sync
- No need to go through aver commands

### 2. Efficient

Only reindexes one record instead of entire database:
- Fast: ~10-50ms for typical record
- Doesn't touch other records
- No downtime

### 3. Non-Destructive

Doesn't modify files, only index:
- Safe to run repeatedly
- Can't corrupt data
- Easy to script

### 4. Composable

Works well with other tools:
```bash
# Edit in vim
vim records/ISS-042.md

# Validate with jq
cat records/ISS-042.md | python3 -c "import yaml; yaml.safe_load(input())"

# Reindex
aver record reindex ISS-042
```

### 5. Scriptable

Easy to use in automation:
```bash
# Watch for file changes and auto-reindex
fswatch -0 records/ | while read -d "" file; do
    record_id=$(basename "$file" .md)
    aver record reindex "$record_id"
done
```

---

## Testing

### Test Cases

1. **Valid record exists:**
```bash
aver record reindex ISS-042
# Should succeed with verbose output
```

2. **Record doesn't exist:**
```bash
aver record reindex NONEXISTENT
# Should print error and exit 1
```

3. **Record with no notes:**
```bash
aver record reindex ISS-099
# Should reindex record only (no notes message)
```

4. **After manual edit:**
```bash
# Edit file
sed -i 's/priority: low/priority: critical/' records/ISS-042.md

# Reindex
aver record reindex ISS-042

# Verify change
aver record list --ksearch priority=critical
# Should show ISS-042
```

5. **Special characters in fields:**
```bash
# File has: title: "Issue with \"quotes\""
aver record reindex ISS-042
# Should handle correctly
```

---

## Documentation Update

### Help Text

```bash
$ aver record reindex --help

usage: aver record reindex [-h] record_id

Reindex a specific record and all its notes from disk files

positional arguments:
  record_id   Record ID to reindex

options:
  -h, --help  show this help message and exit

Examples:
  # Reindex after manual file edit
  aver record reindex ISS-042
  
  # Reindex imported record
  aver record reindex IMPORT-001
  
  # Reindex in script
  for rec in records/*.md; do
      aver record reindex "$(basename "$rec" .md)"
  done
```

### Manual Entry

```markdown
## aver record reindex

**Synopsis:**
    aver record reindex RECORD_ID

**Description:**
    Reindex a single record and all its notes from disk files into the 
    search index. Use this after manually editing record files outside 
    of aver commands.

**Arguments:**
    RECORD_ID       The record ID to reindex

**Exit Status:**
    0   Success
    1   Record not found or error

**Examples:**
    # After manual file edit
    vim records/ISS-042.md
    aver record reindex ISS-042
    
    # Import record from external source
    cp external/issue.md records/IMPORT-001.md
    aver record reindex IMPORT-001
    
    # Bulk reindex after script modifications
    ./update-fields.sh
    for id in $(ls records/*.md | xargs -n1 basename -s .md); do
        aver record reindex "$id"
    done

**See Also:**
    aver admin reindex - Reindex all records
    aver record update - Update record via aver
```

---

## Comparison to Full Reindex

| Feature | `aver admin reindex` | `aver record reindex RECORD_ID` |
|---------|---------------------|----------------------------------|
| Scope | All records | Single record |
| Speed | Minutes (large repos) | Milliseconds |
| Use case | Database rebuild | After manual edit |
| Clears index | Yes (full rebuild) | No (selective update) |
| Risk | None | None |

Both are safe operations that only affect the index, not the source files.

---

## Alternative Considered: Auto-Reindex on View

**Idea:** Automatically reindex when viewing if file is newer than index.

**Rejected because:**
- Adds complexity to view command
- Slower view operations
- Hidden behavior (surprising)
- Manual reindex is more explicit

**Better:** Explicit `reindex` command that user controls.

---

## Summary

This feature:

✅ **Aligns with aver's philosophy** - Files are source of truth
✅ **Enables manual workflows** - Edit files with any tool
✅ **Keeps index in sync** - Easy reintegration
✅ **Fast and efficient** - Only touches one record
✅ **Safe and simple** - Can't corrupt data
✅ **Easy to implement** - ~50 lines of code

Perfect for power users who want to work directly with files!
