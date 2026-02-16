# JSON Interface Tests - Summary

## Overview

Added comprehensive test coverage for the JSON interface functionality to `test_aver.sh`. The tests verify all JSON commands work correctly and handle both success and error cases properly.

## Test Suites Added

### 1. `test_json_interface()` - Direct JSON Commands
Tests all individual JSON commands that can be invoked directly from the command line.

#### Export Tests (5 tests)
- ✓ `json export-record basic` - Export a record as JSON
- ✓ `json export-record with notes` - Export with `--include-notes` flag
- ✓ `json export-note` - Export a single note
- ✓ `json export-record non-existent record` - Error handling for missing records
- ✓ `json export-note` - Verify correct IDs in output

#### Search Tests (4 tests)
- ✓ `json search-records no filters` - Search all records
- ✓ `json search-records with limit` - Verify limit parameter works
- ✓ `json search-records with ksearch` - Search with query filter
- ✓ `json search-notes` - Search notes across all records

#### Import Tests (5 tests)
- ✓ `json import-record from command line` - Create record from JSON string
- ✓ `json import-record from stdin` - Create record reading from stdin with `-`
- ✓ `json import-record with template` - Create record with template specified
- ✓ `json import-note` - Add note via JSON
- ✓ `json import-record invalid JSON` - Error handling for malformed JSON

#### Update Tests (2 tests)
- ✓ `json update-record fields only` - Update metadata without content
- ✓ `json update-record content and fields` - Update both content and fields

#### Schema Tests (3 tests)
- ✓ `json schema-record default` - Get default record schema
- ✓ `json schema-record with template` - Get template-specific schema
- ✓ `json schema-note` - Get note schema for a record

#### Reply Template Tests (1 test)
- ✓ `json reply-template` - Generate reply template with quoted content

**Subtotal: 20 tests**

### 2. `test_json_io_mode()` - Interactive IO Interface
Tests the persistent JSON IO mode that reads commands from STDIN and writes responses to STDOUT.

#### Basic IO Tests (2 tests)
- ✓ `json io basic command` - Single command via IO mode
- ✓ `json io multiple commands` - Multiple commands in one session

#### Round-trip Tests (1 test)
- ✓ `json io import and export round-trip` - Create record and verify by exporting it

#### Operation Tests (3 tests)
- ✓ `json io search and count` - Search via IO mode
- ✓ `json io update record` - Update via IO mode
- ✓ `json io schema commands` - Get schemas via IO mode

#### Error Handling Tests (2 tests)
- ✓ `json io error handling` - Invalid command returns proper error JSON
- ✓ `json io invalid JSON handling` - Malformed JSON returns error

**Subtotal: 8 tests**

## Total JSON Tests Added

**28 new tests** covering:
- All 10 direct JSON commands
- JSON IO mode functionality
- Error handling and edge cases
- Round-trip data integrity
- STDIN input handling
- Template support
- Multi-value field handling

## Test Methodology

### Data Validation
All tests validate JSON structure using Python's `json` module:
```bash
echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert condition"
```

### Error Testing
Error cases use `set +e` / `set -e` to allow failures and verify error responses:
```bash
set +e
output=$(run_aver json export-record "NONEXISTENT" 2>&1)
exit_code=$?
set -e

if [ $exit_code -ne 0 ] && echo "$output" | python3 -c "...assert 'error' in data..."; then
    pass
fi
```

### File Verification
Import/update tests verify changes are persisted to disk:
```bash
if check_content_contains "$TEST_DIR/records/${rec_id}.md" "expected_content"; then
    pass
fi
```

## Test Coverage

### Commands Tested
- ✅ `json export-record`
- ✅ `json export-note`
- ✅ `json search-records`
- ✅ `json search-notes`
- ✅ `json import-record`
- ✅ `json import-note`
- ✅ `json update-record`
- ✅ `json schema-record`
- ✅ `json schema-note`
- ✅ `json reply-template`
- ✅ `json io`

### Scenarios Tested
- ✅ Valid inputs produce valid JSON
- ✅ Required fields are present in outputs
- ✅ IDs are correctly assigned and returned
- ✅ Content is properly encoded/decoded
- ✅ Fields are properly structured (single vs array values)
- ✅ STDIN input works (`--data -`)
- ✅ Command-line JSON works (`--data '{...}'`)
- ✅ Templates are handled correctly
- ✅ Invalid JSON is rejected
- ✅ Non-existent records return errors
- ✅ Error responses have proper structure
- ✅ Multiple IO commands work in sequence
- ✅ File system changes are verified
- ✅ Round-trip data integrity

## Running the Tests

### Run all tests including JSON tests:
```bash
./test_aver.sh
```

### Run tests with verbose output:
```bash
./test_aver.sh --verbose
```

### Keep test directories for inspection:
```bash
./test_aver.sh --keep
```

## Test Output Example

```
========================================
JSON Interface
========================================
TEST: json export-record basic ... PASS
  Valid JSON with expected structure
TEST: json export-record with notes ... PASS
  Notes included in export
TEST: json export-note ... PASS
  Note exported with correct IDs
TEST: json export-record non-existent record ... PASS
  Correctly reported error in JSON
...

========================================
JSON IO Mode
========================================
TEST: json io basic command ... PASS
  IO command executed successfully
TEST: json io multiple commands ... PASS
  Multiple commands executed
...
```

## Integration with Existing Tests

The JSON tests integrate seamlessly with the existing test framework:
- Use the same `print_test()`, `pass()`, `fail()` functions
- Track commands with `track_command()` for failure reporting
- Use the same test environment and cleanup mechanisms
- Follow the same naming conventions
- Contribute to the overall test count and summary

## Test File Changes

**File:** `test_aver.sh`
- **Lines added:** ~450 lines
- **Functions added:** 2 (`test_json_interface`, `test_json_io_mode`)
- **Total tests added:** 28
- **Test categories:** 2 new sections

## Dependencies

Tests require:
- Python 3 with `json` module (standard library)
- `grep`, `echo`, `cat` (standard Unix tools)
- Working `aver.py` with JSON interface implemented
- Bash shell

## Future Enhancements

Potential additional tests to consider:
- Large data sets (performance testing)
- Concurrent IO sessions
- Unicode and special character handling in JSON
- Field type coercion and validation
- Multi-value field handling
- Template inheritance and override testing
- More complex ksearch queries
- Pagination with large result sets
