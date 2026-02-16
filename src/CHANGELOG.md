# JSON Interface Changelog

## 2024 Updates

### Added: User Identity Override in IO Mode

**Feature:** Commands in `json io` mode can now override the user identity on a per-command basis.

**Use Case:** 
- Multi-user systems where different commands should be attributed to different users
- Service accounts or bots creating records on behalf of users
- Automated workflows that need to attribute actions to specific users
- Testing with different user identities

**Implementation:**

Added optional `id` field to JSON IO requests:

```json
{
  "command": "import-record",
  "params": {
    "content": "Bug report",
    "fields": {"title": "Bug", "status": "open"}
  },
  "id": {
    "handle": "customer-bot",
    "email": "bot@example.com"
  }
}
```

**How It Works:**

1. `_cmd_json_io` extracts the optional `id` field from request
2. Passes it to `_execute_json_command` as `user_id` parameter
3. `_execute_json_command` creates a helper function `get_manager_with_override()` that:
   - Gets the manager instance
   - If `user_id` is provided with both `handle` and `email`, calls `manager.set_user_override()`
   - Validates that both fields are present if either is provided
4. All manager creation calls in `_execute_json_command` use the helper function

**Code Changes:**

**File:** `aver.py`

**Line ~9220:** `_cmd_json_io` updated to extract `id` field
```python
user_id = request.get('id', {})  # Optional user identity override
result = self._execute_json_command(command, params, args, user_id)
```

**Line ~9293:** `_execute_json_command` signature updated
```python
def _execute_json_command(self, command: str, params: dict, global_args, user_id: dict = None) -> dict:
```

**Line ~9305:** Helper function added
```python
def get_manager_with_override():
    manager = self._get_manager(args)
    if user_id and isinstance(user_id, dict):
        handle = user_id.get('handle')
        email = user_id.get('email')
        if handle and email:
            manager.set_user_override(handle, email)
        elif handle or email:
            raise ValueError("User identity override requires both 'handle' and 'email'")
    return manager
```

**Lines 9311-9805:** All `manager = self._get_manager(args)` calls replaced with `manager = get_manager_with_override()`

**Validation:**
- If `id` is provided, both `handle` and `email` must be present
- If only one field is provided, raises `ValueError`
- If `id` is omitted, uses default user identity from config

**Applies To:**
- All commands that create or modify data (import-record, import-note, update-record)
- Read-only commands (export, search, schema) also accept it but it has no effect

**Error Handling:**
```json
// Missing email
{"command": "import-record", "params": {...}, "id": {"handle": "user"}}
// Response:
{"success": false, "error": "User identity override requires both 'handle' and 'email'"}
```

**Examples:**

**Multi-User Bot:**
```python
# Bot creates records on behalf of different users
for user in users:
    client.execute(
        'import-record',
        {'content': f'Task for {user.name}', 'fields': {...}},
        user_id={'handle': user.handle, 'email': user.email}
    )
```

**Service Account:**
```json
{
  "command": "import-record",
  "params": {
    "content": "Automated backup completed",
    "fields": {"title": "Backup", "status": "resolved"}
  },
  "id": {
    "handle": "backup-service",
    "email": "backup@example.com"
  }
}
```

**Testing:**
```bash
# Test as different user without changing config
echo '{
  "command": "import-record",
  "params": {"content": "Test", "fields": {"title": "Test", "status": "open"}},
  "id": {"handle": "test-user", "email": "test@example.com"}
}' | aver json io
```

**Documentation Updated:**
- `IO_MODE_GUIDE.md` - Added "User Identity Override" section with examples
- `JSON_QUICK_REFERENCE.md` - Added user override examples and use cases
- Python client example updated to support `user_id` parameter

**Backward Compatibility:**
✅ Fully backward compatible - `id` field is optional
✅ Existing code continues to work without modification
✅ No changes to command-line JSON interface (only IO mode)

---

### Fixed: search-records Implementation

**Issue:** `json search-records` was using the wrong method and missing key arguments.

**Problems:**
1. Used `search_incidents()` instead of `list_incidents()`
2. Missing `--ksort` argument for sorting results
3. `--ksearch` only accepted single value instead of multiple
4. Missing default limit value
5. IO mode had same issues

**Changes Made:**

#### 1. Parser Arguments (`aver.py` line ~7200)
**Before:**
```python
json_search_records_parser.add_argument(
    "--ksearch",
    help="Search query (e.g., 'status=open')",
)
json_search_records_parser.add_argument(
    "--limit",
    type=int,
    help="Limit number of results",
)
```

**After:**
```python
json_search_records_parser.add_argument(
    "--ksearch",
    action="append",
    dest="ksearch",
    help="Search by key-value: 'key=value', 'cost>100' (can use multiple times)",
)
json_search_records_parser.add_argument(
    "--ksort",
    action="append",
    dest="ksort",
    help="Sort by key-values: 'key1', 'key2-' (- = desc, default = asc, can use multiple)",
)
json_search_records_parser.add_argument(
    "--limit",
    type=int,
    default=100,
    help="Limit number of results (default: 100)",
)
```

#### 2. Direct Command Implementation (`_cmd_json_search_records`)
**Before:**
```python
results = manager.search_incidents(
    ksearch=args.ksearch,
    limit=args.limit,
    ids_only=False,
)

records = []
for incident_id in results:
    incident = manager.get_incident(incident_id)
    if incident:
        # ... build record data
```

**After:**
```python
results = manager.list_incidents(
    ksearch_list=getattr(args, 'ksearch', None),
    ksort_list=getattr(args, 'ksort', None),
    limit=args.limit,
    ids_only=False,
)

records = []
for incident in results:  # Returns Incident objects directly
    # ... build record data
```

#### 3. IO Mode Implementation (`_execute_json_command`)
**Before:**
```python
args.ksearch = params.get('ksearch')
args.limit = params.get('limit')

results = manager.search_incidents(
    ksearch=args.ksearch,
    limit=args.limit,
    ids_only=False,
)
```

**After:**
```python
ksearch = params.get('ksearch')
ksort = params.get('ksort')

# Convert single values to lists for consistency
if ksearch is not None and not isinstance(ksearch, list):
    ksearch = [ksearch] if ksearch else None
if ksort is not None and not isinstance(ksort, list):
    ksort = [ksort] if ksort else None

args.ksearch = ksearch
args.ksort = ksort
args.limit = params.get('limit', 100)

results = manager.list_incidents(
    ksearch_list=ksearch,
    ksort_list=ksort,
    limit=args.limit,
    ids_only=False,
)
```

**Impact:**

✅ **Breaking Changes:**
- IO mode JSON format slightly different (accepts arrays for ksearch/ksort)
- However, backward compatible: single strings are auto-converted to arrays

✅ **New Functionality:**
- Can now use multiple search filters with AND logic
- Can sort results by any field (ascending or descending)
- Default limit of 100 prevents accidentally returning entire database
- More efficient: `list_incidents` returns objects directly, no second lookup needed

✅ **Documentation Updated:**
- `IO_MODE_GUIDE.md` - Updated search-records parameters and examples
- `JSON_QUICK_REFERENCE.md` - Added multi-filter and sorting examples
- `JSON_INTERFACE_SUMMARY.md` - Updated usage examples

**Usage Examples:**

**Command Line:**
```bash
# Single filter
aver json search-records --ksearch "status=open" --limit 10

# Multiple filters (AND logic)
aver json search-records --ksearch "status=open" --ksearch "priority=high"

# With sorting
aver json search-records --ksort "created_at-" --limit 20

# Complex query
aver json search-records \
  --ksearch "status=open" \
  --ksearch "priority=high" \
  --ksort "severity-" \
  --ksort "created_at" \
  --limit 50
```

**IO Mode:**
```json
// Single filter (string or array both work)
{"command": "search-records", "params": {"ksearch": "status=open", "limit": 10}}

// Multiple filters
{"command": "search-records", "params": {"ksearch": ["status=open", "priority=high"], "limit": 10}}

// With sorting
{"command": "search-records", "params": {"ksearch": ["status=open"], "ksort": ["created_at-"], "limit": 10}}
```

**Compatibility Notes:**

The fix maintains backward compatibility for IO mode:
- Single string values for `ksearch` are automatically converted to single-item arrays
- If `ksearch` is already an array, it's used as-is
- Missing `ksort` parameter defaults to `None` (no sorting)
- Missing `limit` parameter defaults to 100

**Testing:**

Existing tests in `test_aver.sh` continue to work because they use simple queries.
Consider adding new tests for:
- Multiple `--ksearch` arguments
- `--ksort` functionality
- IO mode with array parameters

**Performance:**

✅ **Improved:** `list_incidents` returns Incident objects directly instead of IDs
- Eliminates the need for `get_incident()` call for each result
- Reduces database queries from N+1 to 1
- Faster for large result sets

**Related Methods:**

The `search_incidents` method is still used by:
- `_cmd_search_updates()` - for note searching (different use case)

The `list_incidents` method is now correctly used by:
- `_cmd_list()` - record list command
- `_cmd_json_search_records()` - JSON search command
- IO mode search-records handler
