# JSON Interface Implementation for Aver

## Summary

Successfully integrated a comprehensive JSON interface into `aver.py` to enable scripting and programmatic integration. The interface provides 10 commands for importing, exporting, searching, and querying schema information.

## Changes Made

### 1. ArgumentParser Setup (Line ~7179)
Added a new `json` command with 10 subcommands before the admin commands section:
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

### 2. Command Routing (Line ~7340)
Added routing logic in the `run()` method to dispatch to the appropriate JSON command handler based on `parsed.json_command`.

### 3. Command Implementation Methods (Line ~8593)
Implemented 11 new methods in the `IncidentCLI` class:

#### Helper Method
- `_read_json_data(data_arg)` - Reads JSON from argument or stdin

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

### Search records
```bash
aver json search-records --ksearch "status=open" --limit 10
```

### Get schema for a template
```bash
aver json schema-record --template bug_report
```

### Generate a reply template
```bash
aver json reply-template REC123 NOTE456
```

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
- Modified file: 9,283 lines
- Lines added: ~839 lines
- New commands: 10
- New methods: 11
