# Aver JSON IO Mode - Developer Guide

## Overview

The `aver json io` command provides a persistent, stream-based JSON interface for programmatic integration. Unlike the standalone JSON commands, IO mode maintains a single process that reads commands from STDIN and writes responses to STDOUT, enabling high-performance batch operations and integration with any programming language.

## Protocol Specification

### Request Format
Each request is a single line containing a JSON object:
```json
{"command": "command-name", "params": {param1: value1, param2: value2}}
```

### Response Format
Each response is a single line containing a JSON object:

**Success:**
```json
{"success": true, "result": {...}}
```

**Error:**
```json
{"success": false, "error": "error description"}
```

### Session Management
- Send commands one per line
- Read responses one per line (line-delimited JSON)
- Send an empty line or EOF to cleanly exit
- Use line buffering for real-time communication
- Each command-response pair is independent

## Supported Commands

### 1. export-record
Export a record with optional notes.

**Parameters:**
- `record_id` (required): Record identifier
- `include_notes` (optional, default: false): Include all notes

**Example:**
```json
{"command": "export-record", "params": {"record_id": "REC123", "include_notes": true}}
```

**Success Response:**
```json
{
  "success": true,
  "result": {
    "id": "REC123",
    "content": "Record content...",
    "fields": {"status": "open", "priority": "high"},
    "notes": [...]
  }
}
```

### 2. export-note
Export a single note.

**Parameters:**
- `record_id` (required): Parent record identifier
- `note_id` (required): Note identifier

**Example:**
```json
{"command": "export-note", "params": {"record_id": "REC123", "note_id": "NOTE456"}}
```

### 3. search-records
Search for records.

**Parameters:**
- `ksearch` (optional): Search expression(s) - can be a string or array of strings
- `ksort` (optional): Sort expression(s) - can be a string or array of strings  
- `limit` (optional, default: 100): Maximum results to return

**Examples:**
```json
{"command": "search-records", "params": {"ksearch": "status=open", "limit": 10}}
```

```json
{"command": "search-records", "params": {"ksearch": ["status=open", "priority=high"], "ksort": ["created_at-"], "limit": 5}}
```

**Success Response:**
```json
{
  "success": true,
  "result": {
    "count": 3,
    "records": [
      {"id": "REC123", "content": "...", "fields": {...}},
      ...
    ]
  }
}
```

### 4. search-notes
Search for notes across all records.

**Parameters:**
- `ksearch` (optional): Search query string
- `limit` (optional): Maximum results to return

**Example:**
```json
{"command": "search-notes", "params": {"ksearch": "category=bugfix", "limit": 5}}
```

### 5. import-record
Create a new record.

**Parameters:**
- `content` (required): Record content/description
- `fields` (optional): Key-value field pairs
- `template` (optional): Template identifier

**Example:**
```json
{
  "command": "import-record",
  "params": {
    "content": "New bug discovered in authentication",
    "fields": {"status": "open", "priority": "critical", "component": "auth"},
    "template": "bug_report"
  }
}
```

**Success Response:**
```json
{
  "success": true,
  "result": {
    "record_id": "REC789"
  }
}
```

### 6. import-note
Add a note to a record.

**Parameters:**
- `record_id` (required): Parent record identifier
- `content` (required): Note content
- `fields` (optional): Key-value field pairs

**Example:**
```json
{
  "command": "import-note",
  "params": {
    "record_id": "REC123",
    "content": "Investigation showed root cause in session handling",
    "fields": {"category": "investigation", "hours_spent": 2.5}
  }
}
```

**Success Response:**
```json
{
  "success": true,
  "result": {
    "note_id": "NOTE890",
    "record_id": "REC123"
  }
}
```

### 7. update-record
Update an existing record.

**Parameters:**
- `record_id` (required): Record identifier
- `content` (optional): New content (omit to keep existing)
- `fields` (optional): Fields to update

**Example:**
```json
{
  "command": "update-record",
  "params": {
    "record_id": "REC123",
    "fields": {"status": "resolved", "resolution_time": 3.5}
  }
}
```

### 8. schema-record
Get field schema for records.

**Parameters:**
- `template` (optional): Template name for template-specific schema

**Example:**
```json
{"command": "schema-record", "params": {"template": "bug_report"}}
```

**Success Response:**
```json
{
  "success": true,
  "result": {
    "template": "bug_report",
    "fields": {
      "status": {
        "type": "special",
        "value_type": "string",
        "editable": true,
        "required": true,
        "accepted_values": ["open", "in_progress", "resolved", "closed"]
      },
      ...
    }
  }
}
```

### 9. schema-note
Get field schema for notes (template-aware based on parent record).

**Parameters:**
- `record_id` (required): Record identifier

**Example:**
```json
{"command": "schema-note", "params": {"record_id": "REC123"}}
```

### 10. reply-template
Get a reply template with quoted original note text.

**Parameters:**
- `record_id` (required): Parent record identifier
- `note_id` (required): Note to reply to

**Example:**
```json
{"command": "reply-template", "params": {"record_id": "REC123", "note_id": "NOTE456"}}
```

**Success Response:**
```json
{
  "success": true,
  "result": {
    "record_id": "REC123",
    "reply_to": "NOTE456",
    "template": "bug_report",
    "quoted_content": "REPLY TO NOTE456:\n\n> Original note text...\n\n",
    "fields": {...}
  }
}
```

## Integration Examples

### Bash/Shell
```bash
#!/bin/bash

# Start io mode and execute multiple commands
{
  echo '{"command": "search-records", "params": {"limit": 5}}'
  echo '{"command": "schema-record", "params": {}}'
  echo ''  # Empty line to exit
} | aver json io
```

### Python
```python
import json
import subprocess

class AverClient:
    def __init__(self):
        self.proc = subprocess.Popen(
            ['aver', 'json', 'io'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    
    def execute(self, command, params=None):
        request = {'command': command, 'params': params or {}}
        self.proc.stdin.write(json.dumps(request) + '\n')
        self.proc.stdin.flush()
        
        response = json.loads(self.proc.stdout.readline())
        if not response['success']:
            raise RuntimeError(response['error'])
        return response['result']
    
    def close(self):
        self.proc.stdin.close()
        self.proc.wait()

# Usage
client = AverClient()
try:
    records = client.execute('search-records', {'limit': 5})
    print(f"Found {records['count']} records")
finally:
    client.close()
```

### Node.js
```javascript
const { spawn } = require('child_process');
const readline = require('readline');

class AverClient {
  constructor() {
    this.proc = spawn('aver', ['json', 'io']);
    this.rl = readline.createInterface({
      input: this.proc.stdout
    });
  }

  async execute(command, params = {}) {
    return new Promise((resolve, reject) => {
      const request = JSON.stringify({ command, params }) + '\n';
      
      const handler = (line) => {
        this.rl.off('line', handler);
        const response = JSON.parse(line);
        
        if (response.success) {
          resolve(response.result);
        } else {
          reject(new Error(response.error));
        }
      };
      
      this.rl.on('line', handler);
      this.proc.stdin.write(request);
    });
  }

  close() {
    this.proc.stdin.end();
  }
}

// Usage
(async () => {
  const client = new AverClient();
  try {
    const records = await client.execute('search-records', { limit: 5 });
    console.log(`Found ${records.count} records`);
  } finally {
    client.close();
  }
})();
```

### Ruby
```ruby
require 'json'
require 'open3'

class AverClient
  def initialize
    @stdin, @stdout, @wait_thr = Open3.popen2('aver', 'json', 'io')
  end

  def execute(command, params = {})
    request = { command: command, params: params }
    @stdin.puts(JSON.generate(request))
    
    response = JSON.parse(@stdout.gets)
    raise response['error'] unless response['success']
    
    response['result']
  end

  def close
    @stdin.close
    @wait_thr.value
  end
end

# Usage
client = AverClient.new
begin
  records = client.execute('search-records', { limit: 5 })
  puts "Found #{records['count']} records"
ensure
  client.close
end
```

## Error Handling

All errors are returned as JSON responses with `"success": false`:

```json
{
  "success": false,
  "error": "Record REC999 not found"
}
```

Common error types:
- **Missing parameters**: `"Missing required parameter: record_id"`
- **Invalid commands**: `"Unknown command: invalid-cmd"`
- **Invalid JSON**: `"Invalid JSON: Expecting value: line 1 column 1 (char 0)"`
- **Database errors**: `"Record REC123 not found"`

## Performance Considerations

1. **Reuse connections**: IO mode maintains database connection across commands
2. **Batch operations**: Group related commands in a single IO session
3. **Line buffering**: Use `bufsize=1` or equivalent for real-time responses
4. **Parallel processing**: Multiple IO processes can run simultaneously
5. **Resource cleanup**: Always close stdin and wait for process completion

## Best Practices

1. **Validate responses**: Always check `success` field before using `result`
2. **Handle errors gracefully**: Implement retry logic for transient failures
3. **Use timeouts**: Set process timeouts to prevent hangs
4. **Log requests/responses**: For debugging and audit trails
5. **Connection pooling**: Reuse IO processes for multiple operations
6. **Proper cleanup**: Close stdin and wait for process to avoid zombies

## Comparison: Direct Commands vs IO Mode

| Feature | Direct Commands | IO Mode |
|---------|----------------|---------|
| Invocation | One subprocess per command | Single persistent process |
| Overhead | High (process spawn each time) | Low (process spawned once) |
| Use Case | Single operations, scripts | Batch operations, applications |
| State | Stateless | Stateful (maintains DB connection) |
| Input | Command-line args or stdin | Line-delimited JSON over stdin |
| Output | Single JSON response | Stream of JSON responses |

## Debugging

Enable verbose output by checking stderr:
```python
proc = subprocess.Popen(
    ['aver', 'json', 'io'],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,  # Capture errors
    text=True,
    bufsize=1
)
```

Test commands manually:
```bash
# Start io mode and type commands interactively
aver json io
{"command": "search-records", "params": {"limit": 1}}
# Press Enter, see response
# Type empty line to exit
```
