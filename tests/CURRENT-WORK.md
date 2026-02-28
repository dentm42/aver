# Current Work: Contract Tests for Notes and Records

## Context

Several bugs were fixed in session around Feb 2026 that should have been caught by tests:

1. **Note fields dropped with config.toml** — `add_update()` filtered out note special fields
   with `editable=false` but no `system_value` (e.g. `type: vote`) because the filter used
   `not field.editable` instead of `field.system_value`. Fix: `aver.py` ~line 6138.

2. **Template record fields got type-hint suffixes** (`impact_score__float`) — `args.template`
   was not set before `_process_from_file()` in JSON IO paths, so template-specific fields
   were not recognized as special fields and got treated as custom fields.

3. **Command parity gap** — some capabilities existed in CLI but not JSON IO (e.g. `--use-id`).

## Contracts Being Tested

### CONTRACT A: Note Field Round-Trip
Every field supplied to a note creation call must survive to export intact, with correct typing.

- Special field, `editable=false`, no `system_value` (e.g. `note_type: bug-report`) →
  stored without type-hint suffix, returned as supplied
- Special field with `system_value` (e.g. `timestamp`) →
  returned with SYSTEM value (caller-supplied value discarded)
- Custom field, string (e.g. `foo: bar`) →
  stored ON DISK as `foo__string: bar`, returned as `foo: bar`
- Custom field, integer (e.g. `count: 5`) →
  stored ON DISK as `count__integer: 5`, returned as `count: 5` (integer type)
- Template-specific note field, `editable=false`, no `system_value` (e.g. `resolution: fixed`) →
  stored without type-hint, returned as supplied when note is on a templated record
- Global note special field from config carries into templated record notes (inheritance)

### CONTRACT B: Note Injection Paths
All injection paths must honour Contract A equally. Paths to test:

1. `note add --from-file <file>` (CLI stdin/file path)
2. `json import-note RECORD_ID --data '{...}'` (CLI JSON path)
3. `json io` with `{"command": "import-note", ...}` (JSON IO protocol)

### CONTRACT C: Record Field Type Fidelity
*(Do records after notes are complete)*

Template-defined float/integer fields must never get type-hint suffixes on disk,
and must be returned with correct numeric types on export.

Same three injection paths: `record new --from-file`, `json import-record`, `json io`.

### CONTRACT D: CLI / JSON-IO Command Parity
*(Do after A, B, C)*

Equivalent commands must produce structurally consistent output for the same data.
See parity table below.

---

## Parity Table (as reviewed in code)

| CLI command                          | JSON-IO equivalent         | Notes |
|--------------------------------------|----------------------------|-------|
| `record new --from-file / stdin`     | `import-record`            | Both call `_process_from_file` |
| `record view REC-X`                  | `export-record`            | |
| `record list --ksearch ...`          | `search-records`           | JSON IO adds: ksort, count_only, max |
| `record update REC-X`                | `update-record`            | |
| `note add --from-file / stdin`       | `import-note`              | Both call `_process_from_file` |
| `note list REC-X`                    | `export-record --include-notes` | |
| `note search --ksearch ...`          | `search-notes`             | JSON IO: no `--fields` display flag |
| `json schema-record --template X`    | `schema-record`            | Same handler |
| `json schema-note REC-X`             | `schema-note`              | Same handler |
| `json reply-template REC NOTE`       | `reply-template`           | Same handler |
| `admin template-data [TMPL]`         | `template-data`            | Same handler |
| `admin reindex REC-X`                | `reindex`                  | Same handler |
| `admin list-databases`               | *(intentionally absent)*   | Admin-only |
| `admin init`                         | *(intentionally absent)*   | Admin-only |
| `admin config *`                     | *(intentionally absent)*   | Admin-only |
| *(no global CLI equivalent)*         | `list-templates`           | KNOWN GAP — document, consider adding |
| *(no global CLI note search)*        | `search-notes` (global)    | KNOWN GAP — `note search` requires `--ksearch`, no cross-record browsing |

---

## Test Config Fields Added (in test_aver.sh setup)

These were added to the test config so the regression tests have what they need:

```toml
# Global note field: editable=false, no system_value (the regression field)
[note_special_fields.note_type]
editable = false, enabled = true, value_type = "string", index_values = true

# Template bug: float record field (type fidelity)
[template.bug.record_special_fields.impact_score]
value_type = "float", editable = true, default = "0.0"

# Template bug: note field editable=false, no system_value (template note inheritance)
[template.bug.note_special_fields.resolution]
editable = false, enabled = true, value_type = "string"
```

---

## Implementation Plan

### STEP 1 (CURRENT): Add `test_note_contract()` to test_aver.sh

Location: Insert before `main()` at line ~4140 (after `test_template_data`).
Add call in `main()` after `test_note_special_fields`.

**Tests to write inside `test_note_contract()`:**

#### A. Setup
- Create a plain record (no template) → `$plain_rec`
- Create a bug-template record → `$bug_rec` (reuse `$TEST_DIR/bug_rec_id.txt` if available)

#### B. Global special field, editable=false, no system_value (regression)
For each of the 3 injection paths:
- Inject note with `note_type: bug-report`
- Assert: on-disk file contains `note_type: bug-report` (no `__string` suffix)
- Assert: `json export-record --include-notes` returns `note_type: bug-report`

#### C. System-value field overrides caller input
For each injection path:
- Inject note with `timestamp: 1999-01-01 00:00:00` (fake value)
- Assert: exported `timestamp` is NOT `1999-01-01 00:00:00` (system overwrote it)
- Assert: `timestamp` is present and non-empty

#### D. Custom string field (type hint on disk, clean on export)
For each injection path:
- Inject note with custom field `extra_info: hello`
- Assert: on-disk file contains `extra_info__string: hello`
- Assert: export returns `extra_info: hello`

#### E. Custom integer field (type hint on disk, numeric on export)
For each injection path:
- Inject note with custom field `retry_count: 3`
- Assert: on-disk file contains `retry_count__integer: 3`
- Assert: export returns `retry_count` as integer 3 (check via python3 json parse)

#### F. Template-specific note field (editable=false, no system_value)
For each injection path using `$bug_rec`:
- Inject note with `resolution: fixed`
- Assert: on-disk file contains `resolution: fixed` (no suffix)
- Assert: export returns `resolution: fixed`

#### G. Global note fields inherited in templated record notes
For each injection path using `$bug_rec`:
- Inject note with `note_type: regression`
- Assert: exported note has both `note_type: regression` AND `timestamp` (global fields apply)

### STEP 2 (DONE): `test_record_contract()` added

Contracts:
- A: Plain special field (title, status, priority) — no type-hint on disk, correct values on export
- B: system_value field (created_at) — system wins over caller-supplied value
- C: Custom string field — __string suffix on disk, clean on export (all 3 paths)
- D: Custom integer field — __integer suffix on disk, numeric type on export
- E: Template float field (impact_score) — NO __float suffix on disk, float type on export (all 3 paths)
- F: Template integer field (severity) — NO __integer suffix on disk, int type on export
- G: Type fidelity survives update round-trip (json update-record + json io update-record)

### STEP 3 (DONE): `test_command_parity()` added

Tests (9 total):
- record view ↔ export-record: same id, content, fields
- record list --ksearch ↔ search-records: same record IDs for same filter
- note list ↔ export-record --include-notes: same note IDs
- note search --ksearch ↔ search-notes: same note IDs for same filter
- json schema-record --template X ↔ schema-record: identical field sets
- json schema-note RECORD ↔ schema-note: identical field sets
- admin template-data --json ↔ template-data: identical template_id + record fields
- admin reindex ↔ reindex: both succeed
- list-templates (IO only): returns configured templates; documented gap noted inline

---

## DONE: Fix _build_kv_list template scoping for records (and notes)

Same structural issue as the note fix below, but different symptom:

- For records, `_build_kv_list` calls `get_special_fields()` which returns only
  **global** record special fields — template-specific record fields (e.g. `impact_score`
  on the `bug` template) are not included in the conflict check.
- Consequence: passing `--text impact_score=2.5` on a bug record does NOT raise an error
  (no conflict detected), so the value is treated as a custom field and written to disk
  with a `__float` type-hint suffix instead of as the proper template field.
- Silent wrong behavior, not a noisy error.
- Fix will follow same pattern as the note fix: fetch the record early in
  `_cmd_new_incident` / `_cmd_update_incident`, set `args.record_template_id`, and use
  `get_special_fields_for_template(template_id, for_record=True)` in `_build_kv_list`.
- For `record new` there is no existing record to fetch — template comes from `args.template`
  directly, which is already available.
- For `record update` the record must be fetched (same pattern as note fix).

---

## Key Code Locations (aver.py)

| What | Where |
|------|-------|
| `add_update()` filter (the bug) | ~line 6138 |
| `_process_from_file()` | ~line 6640 |
| `get_special_fields_for_template()` | ~line 1109 |
| `_apply_special_fields()` | ~line 4230 |
| `IncidentUpdate.to_markdown()` | ~line 628 |
| `IncidentUpdate.from_markdown()` | ~line 702 |
| `_cmd_json_import_note()` | ~line 9579 |
| `_execute_json_command()` import-note | ~line 10455 |
| `_cmd_add_update()` (CLI note add) | (search: def _cmd_add_update) |

## IMPORTANT: json io is a Persistent Process

`aver json io` reads newline-delimited JSON commands from stdin in a loop and exits
when stdin closes. **Always pipe input** — never call it without a stdin source or it
will block waiting for input and hang the test suite.

Safe patterns (stdin closes, process exits):
```bash
echo '{"command": "...", "params": {...}}' | run_aver json io
cat "$TEST_DIR/commands.txt" | run_aver json io
```

Unsafe (will hang):
```bash
run_aver json io                         # no stdin = blocks forever
run_aver json io < /dev/null             # EOF immediately, but returns no output
```

All existing and new tests use the `echo '...' | run_aver json io` pattern correctly.

## Helper Pattern for Injection Path Testing

The test will loop conceptually over 3 injection methods. In bash, easiest to
write each as a separate named test rather than a loop, since error messages need
to identify which path failed.

```bash
# Path 1: CLI --from-file
cat > "$TEST_DIR/note_input.md" << EOF
---
note_type: bug-report
extra_info: hello
---
Note body text.
EOF
run_aver note add "$plain_rec" --from-file "$TEST_DIR/note_input.md"

# Path 2: json import-note --data
run_aver json import-note "$plain_rec" --data \
  '{"content": "Note body text.", "fields": {"note_type": "bug-report", "extra_info": "hello"}}'

# Path 3: json io
echo '{"command": "import-note", "params": {"record_id": "'$plain_rec'",
  "content": "Note body text.", "fields": {"note_type": "bug-report", "extra_info": "hello"}}}' \
  | run_aver json io
```

For retrieval, always use `json export-record --include-notes` and parse with python3.
Also check the raw on-disk file for type-hint assertions.

## Finding the note file on disk

```bash
# After adding a note, find the most recently written file:
local note_file=$(ls -t "$TEST_DIR/updates/$rec_id/"*.md 2>/dev/null | head -1)
```
