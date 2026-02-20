# JSON Interface Implementation for Aver

## Summary

Successfully integrated a comprehensive JSON interface into `aver.py` to enable scripting and programmatic integration. The interface provides 11 commands including an interactive IO mode for stream-based communication.

## Changes Made

### 1. ArgumentParser Setup (Line ~7179)
Added a new `json` command with 11 subcommands before the admin commands section:
- `import-record` - Import a record from JSON
- `import-note` - Import a note from JSON  
- `update-record` - Update a record from JSON
- `export-record` - Export a record as JSON
- `export-note` - Export a note as JSON
- `search-records` - Search records and output as JSON array
- `search-notes` - Search notes and output as JSON array
- `schema-record` - Get field schema for records as JSON
- `schema-note` - Get field schema for notes as JSON
- `reply-template` - Get a reply template with quoted note text as JSON
- **`io`** - Interactive JSON interface via STDIN/STDOUT (NEW)

### 2. Command Routing (Line ~7340)
Added routing logic in the `run()` method to dispatch to the appropriate JSON command handler based on `parsed.json_command`.

### 3. Command Implementation Methods (Line ~8593)
Implemented 13 new methods in the `IncidentCLI` class:

#### Helper Methods
- `_read_json_data(data_arg)` - Reads JSON from argument or stdin
- **`_execute_json_command(command, params, global_args)`** - Execute commands in io mode (NEW)

#### Command Methods
- `_cmd_json_import_record(args)` - Creates a new record from JSON data
- `_cmd_json_import_note(args)` - Adds a note to a record from JSON data
- `_cmd_json_update_record(args)` - Updates an existing record from JSON data
- `_cmd_json_export_record(args)` - Exports a record as JSON (optionally with notes)
- `_cmd_json_export_note(args)` - Exports a single note as JSON
- `_cmd_json_search_records(args)` - Searches records and returns JSON array
- `_cmd_json_search_notes(args)` - Searches notes and returns JSON array
- `_cmd_json_schema_record(args)` - Returns field schema for records
- `_cmd_json_schema_note(args)` - Returns field schema for notes (template-aware)
- `_cmd_json_reply_template(args)` - Generates reply template with quoted content
- **`_cmd_json_io(args)`** - Interactive JSON interface over STDIN/STDOUT (NEW)

## JSON Format

### Import/Update Format
```json
{
  "template": "optional_template_id",
  "fields": {
    "field_name": "value",
    "multi_field": ["value1", "value2"]
  },
  "content": "The main content text"
}
```

### Export Format
```json
{
  "id": "record_id",
  "content": "The main content",
  "fields": {
    "field_name": "value"
  },
  "notes": [
    {
      "id": "note_id",
      "content": "Note content",
      "fields": {}
    }
  ]
}
```

### Schema Format
```json
{
  "template": "template_id",
  "record_id": "record_id",
  "fields": {
    "field_name": {
      "type": "special|custom",
      "value_type": "string|integer|float",
      "editable": true,
      "required": false,
      "accepted_values": ["option1", "option2"],
      "default": "value"
    }
  }
}
```

## Usage Examples

### Import a record from JSON
```bash
# From command line argument
aver json import-record --data '{"content": "Bug report", "fields": {"status": "open"}}'

# From stdin
echo '{"content": "Bug report", "fields": {"status": "open"}}' | aver json import-record --data -
```

### Export a record with notes
```bash
aver json export-record REC123 --include-notes
```

### Search Records
```bash
# Search all records (default limit: 100)
aver json search-records

# With single filter
aver json search-records --ksearch "status=open" --limit 10

# With multiple filters (AND logic)
aver json search-records --ksearch "status=open" --ksearch "priority=high"

# With sorting (descending by created_at)
aver json search-records --ksort "created_at-" --limit 20
```

### Get schema for a template
```bash
aver json schema-record --template bug_report
```

### Generate a reply template
```bash
aver json reply-template REC123 NOTE456
```

## Interactive IO Mode

The `json io` command provides a persistent, stream-based interface for high-performance integrations. Commands are sent as JSON objects via STDIN, with responses returned via STDOUT.

### IO Protocol

Each request is a single-line JSON object with two fields:
```json
{"command": "command-name", "params": {...}}
```

Each response is a single-line JSON object:
```json
{"success": true, "result": {...}}
```
or
```json
{"success": false, "error": "error message"}
```

### IO Usage Examples

#### Shell Script Example
```bash
# Single command
echo '{"command": "search-records", "params": {"limit": 5}}' | aver json io

# Multiple commands
cat << 'EOF' | aver json io
{"command": "search-records", "params": {"limit": 2}}
{"command": "schema-record", "params": {}}
{"command": "export-record", "params": {"record_id": "REC123"}}

EOF
```

#### Python Client Example
```python
import json
import subprocess

# Start the io process
proc = subprocess.Popen(
    ['aver', 'json', 'io'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    text=True,
    bufsize=1
)

# Send a command
request = {"command": "search-records", "params": {"limit": 5}}
proc.stdin.write(json.dumps(request) + '\n')
proc.stdin.flush()

# Read response
response = json.loads(proc.stdout.readline())
if response['success']:
    print(f"Found {response['result']['count']} records")
else:
    print(f"Error: {response['error']}")

# Close when done
proc.stdin.close()
proc.wait()
```

### Supported IO Commands

All standard JSON commands are supported in IO mode:
- `export-record` - params: `{record_id, include_notes?}`
- `export-note` - params: `{record_id, note_id}`
- `search-records` - params: `{ksearch?, limit?}`
- `search-notes` - params: `{ksearch?, limit?}`
- `import-record` - params: `{content, fields?, template?}`
- `import-note` - params: `{record_id, content, fields?}`
- `update-record` - params: `{record_id, content?, fields?}`
- `schema-record` - params: `{template?}`
- `schema-note` - params: `{record_id}`
- `reply-template` - params: `{record_id, note_id}`

### IO Mode Benefits

1. **Performance** - No subprocess overhead per command
2. **Stateful** - Maintain database connection across operations
3. **Streaming** - Process commands as they arrive
4. **Simple Protocol** - Line-delimited JSON for easy parsing
5. **Language Agnostic** - Works with any language that can spawn processes

## Error Handling

All JSON commands follow a consistent error handling pattern:
- Success responses include `"success": true` and relevant data
- Error responses include `"success": false` or `"error"` field with error message
- Exit code 1 on errors, 0 on success
- All output is valid JSON for easy parsing

## Integration Benefits

1. **Scriptability** - Easy to integrate with shell scripts and automation tools
2. **Consistency** - Uniform JSON input/output format
3. **Composability** - Commands can be chained using standard UNIX pipes
4. **Language Agnostic** - Any language that can parse JSON can interact with aver
5. **Machine Readable** - No need to parse human-readable output formats

## Testing

The implementation has been verified:
- ✓ Python syntax validation passed
- ✓ Help text displays correctly for all commands
- ✓ Command structure matches the specification
- ✓ All 10 JSON subcommands are registered and routable

## File Statistics

- Original file: 8,444 lines
- Modified file: 9,786 lines
- Lines added: ~1,342 lines
- New commands: 11 (10 direct + 1 io mode)
- New methods: 13

## Example Files Included

- `test_json_io.sh` - Shell script demonstrating io mode usage
- `aver_client_example.py` - Python client library and examples
