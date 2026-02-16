# Aver JSON Interface - Quick Reference

## Command Overview

| Command | Purpose | Key Options |
|---------|---------|-------------|
| `export-record` | Export record as JSON | `--include-notes` |
| `export-note` | Export single note as JSON | |
| `search-records` | Search records, return JSON array | `--ksearch`, `--limit` |
| `search-notes` | Search notes, return JSON array | `--ksearch`, `--limit` |
| `import-record` | Create record from JSON | `--data` |
| `import-note` | Add note from JSON | `--data` |
| `update-record` | Update record from JSON | `--data` |
| `schema-record` | Get record field definitions | `--template` |
| `schema-note` | Get note field definitions | |
| `reply-template` | Generate reply with quoted text | |
| `io` | Interactive STDIN/STDOUT mode | |

## Quick Examples

### Export a Record
```bash
# Basic export
aver json export-record REC123

# With notes
aver json export-record REC123 --include-notes
```

### Search Records
```bash
# Search all
aver json search-records

# With single filter
aver json search-records --ksearch "status=open" --limit 10

# With multiple filters
aver json search-records --ksearch "status=open" --ksearch "priority=high" --limit 10

# With sorting
aver json search-records --ksearch "status=open" --ksort "created_at-" --limit 10
```

### Create a Record
```bash
# From command line
aver json import-record --data '{"content": "Bug description", "fields": {"title": "Bug title", "status": "open"}}'

# From stdin
cat data.json | aver json import-record --data -

# From file
aver json import-record --data "$(cat record.json)"
```

### Update a Record
```bash
# Update fields only
aver json update-record REC123 --data '{"fields": {"status": "resolved"}}'

# Update content and fields
aver json update-record REC123 --data '{"content": "New description", "fields": {"status": "closed"}}'
```

### Get Schema
```bash
# Default record schema
aver json schema-record

# Template-specific schema
aver json schema-record --template bug

# Note schema for a record
aver json schema-note REC123
```

### IO Mode (Persistent Session)
```bash
# Single command
echo '{"command": "search-records", "params": {"limit": 5}}' | aver json io

# Multiple filters and sorting
echo '{"command": "search-records", "params": {"ksearch": ["status=open", "priority=high"], "ksort": ["created_at-"], "limit": 10}}' | aver json io

# With user identity override
echo '{"command": "import-record", "params": {"content": "New record", "fields": {"title": "Test", "status": "open"}}, "id": {"handle": "bot", "email": "bot@example.com"}}' | aver json io

# Multiple commands
cat << EOF | aver json io
{"command": "search-records", "params": {"limit": 2}}
{"command": "export-record", "params": {"record_id": "REC123"}}

EOF
```

## User Identity Override (IO Mode Only)

Commands in IO mode can optionally override the user identity by including an `id` field:

```json
{
  "command": "import-record",
  "params": {...},
  "id": {
    "handle": "username",
    "email": "user@example.com"
  }
}
```

**Requirements:**
- Both `handle` and `email` must be provided
- Only applies to that specific command
- Useful for multi-user systems and automation

**Use Cases:**
- Service accounts creating records on behalf of users
- Multi-tenant systems with different users
- Testing with different user identities
- Automated workflows attributing actions correctly

## JSON Formats

### Import Record Format
```json
{
  "content": "Main record content/description",
  "fields": {
    "title": "Record Title",
    "status": "open",
    "priority": "high",
    "tags": ["tag1", "tag2"]
  },
  "template": "bug"
}
```

### Import Note Format
```json
{
  "content": "Note text",
  "fields": {
    "category": "investigation",
    "hours": 2.5
  }
}
```

### Update Record Format
```json
{
  "fields": {
    "status": "resolved",
    "resolution": "Fixed in v2.0"
  },
  "content": "Optional updated content"
}
```

### Export Record Response
```json
{
  "id": "REC123",
  "content": "Record content",
  "fields": {
    "title": "Bug Title",
    "status": "open",
    "created_at": "2024-01-15T10:30:00",
    "priority": "high"
  },
  "notes": [
    {
      "id": "NOTE456",
      "content": "Note text",
      "fields": {...}
    }
  ]
}
```

### Search Response
```json
{
  "count": 3,
  "records": [
    {
      "id": "REC123",
      "content": "...",
      "fields": {...}
    },
    ...
  ]
}
```

### Schema Response
```json
{
  "template": "bug",
  "fields": {
    "status": {
      "type": "special",
      "value_type": "string",
      "editable": true,
      "required": true,
      "accepted_values": ["open", "in_progress", "resolved"],
      "default": "open"
    },
    "priority": {
      "type": "special",
      "value_type": "string",
      "editable": true,
      "required": false,
      "accepted_values": ["low", "medium", "high", "critical"]
    }
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": "Record REC999 not found"
}
```

### IO Mode Request
```json
{
  "command": "export-record",
  "params": {
    "record_id": "REC123",
    "include_notes": true
  }
}
```

### IO Mode Response (Success)
```json
{
  "success": true,
  "result": {
    "id": "REC123",
    "content": "...",
    "fields": {...}
  }
}
```

### IO Mode Response (Error)
```json
{
  "success": false,
  "error": "Missing required parameter: record_id"
}
```

## Integration Patterns

### Bash Pipeline
```bash
# Export all open bugs
aver json search-records --ksearch "status=open" | \
  jq -r '.records[].id' | \
  while read id; do
    aver json export-record "$id" > "exports/${id}.json"
  done
```

### Python Script
```python
import subprocess
import json

result = subprocess.run(
    ['aver', 'json', 'search-records', '--limit', '10'],
    capture_output=True,
    text=True
)
data = json.loads(result.stdout)
print(f"Found {data['count']} records")
```

### jq Processing
```bash
# Get all record IDs with high priority
aver json search-records | \
  jq -r '.records[] | select(.fields.priority == "high") | .id'

# Extract titles
aver json search-records | \
  jq -r '.records[] | "\(.id): \(.fields.title)"'
```

### Node.js
```javascript
const { execSync } = require('child_process');

const output = execSync('aver json search-records --limit 5');
const data = JSON.parse(output);
console.log(`Found ${data.count} records`);
```

## Common Workflows

### Create Record from Template
```bash
# 1. Get schema for template
aver json schema-record --template bug > schema.json

# 2. Prepare data matching schema
cat > new_bug.json << EOF
{
  "content": "Application crashes on startup",
  "fields": {
    "title": "Startup crash",
    "status": "open",
    "priority": "critical",
    "component": "core"
  },
  "template": "bug"
}
EOF

# 3. Import
aver json import-record --data "$(cat new_bug.json)"
```

### Bulk Update Status
```bash
# Find all 'in_progress' records and mark as 'resolved'
aver json search-records --ksearch "status=in_progress" | \
  jq -r '.records[].id' | \
  while read id; do
    aver json update-record "$id" --data '{"fields": {"status": "resolved"}}'
  done
```

### Generate Report
```bash
# Export all records to individual JSON files
mkdir -p export_$(date +%Y%m%d)
aver json search-records --limit 1000 | \
  jq -r '.records[].id' | \
  while read id; do
    aver json export-record "$id" --include-notes > "export_$(date +%Y%m%d)/${id}.json"
  done
```

## Tips & Best Practices

### Performance
- Use **IO mode** for multiple operations (avoids process spawn overhead)
- Set appropriate `--limit` on searches
- Export without `--include-notes` when notes aren't needed

### Error Handling
- Always check for `"success": false` in responses
- Parse JSON before processing to catch malformed data
- Use `set -e` in bash scripts for fail-fast behavior

### Data Validation
- Use `schema-record` to discover available fields
- Check `required` and `accepted_values` constraints
- Test with `--data -` during development for easier editing

### Security
- Validate input when accepting JSON from external sources
- Sanitize field values in programmatic use
- Be cautious with shell variable expansion in JSON strings

### Debugging
- Use `jq` to pretty-print and validate JSON
- Add `2>&1` to capture stderr in scripts
- Use `--verbose` flag during development (if available)

## Field Value Types

| Type | Example | Notes |
|------|---------|-------|
| Single string | `"status": "open"` | One value |
| String array | `"tags": ["bug", "critical"]` | Multiple values |
| Integer | `"count": 42` | Numeric field |
| Float | `"hours": 2.5` | Decimal values |
| Datetime | `"created_at": "2024-01-15T10:30:00"` | ISO 8601 format |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Error (validation, not found, etc.) |
| 130 | Interrupted (Ctrl-C) |

## See Also

- `IO_MODE_GUIDE.md` - Detailed IO mode documentation
- `JSON_INTERFACE_SUMMARY.md` - Implementation overview
- `JSON_TESTS_SUMMARY.md` - Test coverage details
- `aver_client_example.py` - Python client library
