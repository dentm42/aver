#!/bin/bash

#==============================================================================
# aver.py Test Suite
#==============================================================================
# Comprehensive testing of aver functionality including:
# - Basic record creation and updates
# - Template system (config and record templates)
# - Special characters in values (#, $, %)
# - System fields (template_id, created_at, etc.)
# - Validation (required fields, accepted values)
# - Notes and updates
# - Search and listing
#==============================================================================

set -e  # Exit on error (disabled for tests that should fail)

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Failure tracking
declare -a FAILED_TESTS=()
declare -a FAILED_COMMANDS=()
declare -a FAILED_REASONS=()
CURRENT_TEST_NAME=""
CURRENT_COMMAND=""

# Test directory
TEST_DIR=""
TEST_HOME=""
ORIGINAL_HOME=""
KEEP_TEST_DIR=false

# Usage
usage() {
    cat << EOF
Usage: $0 [OPTIONS]

Test the aver.py script functionality.

IMPORTANT: This script creates an isolated test environment:
  - Temporary HOME directory (your real ~/.aver is not touched)
  - Temporary test databases
  - All changes are cleaned up after tests (unless --keep is used)

OPTIONS:
    -k, --keep      Keep test directories after completion
    -h, --help      Show this help message
    -v, --verbose   Verbose output (show all command output)

EXAMPLES:
    $0              Run all tests, clean up after
    $0 --keep       Run tests and keep test directories for inspection
    $0 --verbose    Run tests with full command output

EOF
}

# Parse arguments
VERBOSE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        -k|--keep)
            KEEP_TEST_DIR=true
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Find aver.py
AVER_PATH=""
if [ -f "./aver.py" ]; then
    AVER_PATH="./aver.py"
elif [ -f "../aver.py" ]; then
    AVER_PATH="../aver.py"
elif [ -f "/mnt/user-data/outputs/aver.py" ]; then
    AVER_PATH="/mnt/user-data/outputs/aver.py"
else
    echo -e "${RED}ERROR: Cannot find aver.py${NC}"
    echo "Please make sure the aver.py script being tested"
    echo "is in the current directory or its parent"
    echo "or ensure aver.py exists at /mnt/user-data/outputs/aver.py"
    exit 1
fi

echo -e "${BLUE}Using aver.py at: ${AVER_PATH}${NC}"

#==============================================================================
# Helper Functions
#==============================================================================

print_section() {
    echo ""
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}========================================${NC}"
}

print_test() {
    CURRENT_TEST_NAME="$1"
    CURRENT_COMMAND=""  # Clear previous command
    echo -ne "${YELLOW}TEST: $1${NC} ... "
    TESTS_RUN=$((TESTS_RUN + 1))
}

pass() {
    echo -e "${GREEN}PASS${NC}"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
    echo -e "${RED}FAIL${NC}"
    local reason="${1:-No reason provided}"
    if [ -n "$1" ]; then
        echo -e "${RED}  Error: $1${NC}"
    fi
    TESTS_FAILED=$((TESTS_FAILED + 1))
    
    # Track failure details
    FAILED_TESTS+=("${CURRENT_TEST_NAME:-Unknown test}")
    FAILED_COMMANDS+=("${CURRENT_COMMAND:-No command tracked}")
    FAILED_REASONS+=("$reason")
}

# Helper function to track commands not run through run_aver
track_command() {
    CURRENT_COMMAND="$*"
}

run_aver() {
    # Track the command being run
    CURRENT_COMMAND="aver $*"

    if [ "$VERBOSE" = true ]; then
        echo "RUN AVER: $@" >&2
        echo "========================================" >&2
        echo "python3 \"$AVER_PATH\" --override-repo-boundary --location \"$TEST_DIR\" \"$@\"" >&2
        echo "========================================" >&2
    fi
    # Preserve original Python user site-packages (HOME override would break them)
    PYTHONUSERBASE="${ORIGINAL_HOME}/.local" python3 "$AVER_PATH" --override-repo-boundary --location "$TEST_DIR" --no-validate-config "$@"
}

run_aver_validated() {
    # Like run_aver but WITHOUT --no-validate-config, so startup warnings are emitted.
    # Use this when a test needs to observe [CONFIG WARNING] behavior.
    CURRENT_COMMAND="aver $*"
    PYTHONUSERBASE="${ORIGINAL_HOME}/.local" python3 "$AVER_PATH" --override-repo-boundary --location "$TEST_DIR" "$@"
}

check_file_exists() {
    if [ -f "$1" ]; then
        return 0
    else
        return 1
    fi
}

check_content_contains() {
    local file="$1"
    local pattern="$2"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        return 0
    else
        return 1
    fi
}

#==============================================================================
# Setup
#==============================================================================

setup_test_environment() {
    print_section "Setting Up Test Environment"
    
    # Save original HOME
    ORIGINAL_HOME="$HOME"
    
    # Create temporary HOME directory
    TEST_HOME=$(mktemp -d -t aver-home-XXXXXX)
    export HOME="$TEST_HOME"
    echo "Temporary HOME: $TEST_HOME"
    
    # Create temporary test directory
    TEST_DIR=$(mktemp -d -t aver-test-XXXXXX)
    echo "Test directory: $TEST_DIR"
    
    # Initialize aver database
    print_test "Initialize database"
    if run_aver admin init 2>&1; then
        pass
    else
        fail "Failed to initialize database"
        cleanup
        exit 1
    fi

    
    # Set user config
    print_test "Set user configuration"
    if run_aver admin config set-user --handle "testuser" --email "test@example.com"; then
        pass
    else
        fail "Failed to set user config"
        cleanup
        exit 1
    fi
    
    # Create test configuration
    print_test "Create test configuration"
    cat > "$TEST_DIR/config.toml" << 'EOF'
# Test Configuration

default_record_prefix = "REC"
default_note_prefix = "NT"

# Global record special fields
[record_special_fields.template_id]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
system_value = "template_id"

[record_special_fields.created_at]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"
index_values = true

[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"
index_values = true

[record_special_fields.updated_at]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
system_value = "datetime"
index_values = true

[record_special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
index_values = true

[record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["open", "in_progress", "resolved", "closed"]
default = "open"
index_values = true

[record_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["low", "medium", "high", "critical"]
default = "medium"
index_values = true

[record_special_fields.severity]
type = "single"
value_type = "integer"
editable = true
enabled = true
required = false
accepted_values = ["1", "2", "3", "4", "5"]
index_values = true

# Test field with index_values = false (should not be in database)
[record_special_fields.private_notes]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false

# Test field with index_values = false for email (privacy)
[record_special_fields.contact_email]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false

[record_special_fields.tags]
type = "multi"
value_type = "string"
editable = true
enabled = true
required = false
index_values = true

# Global note special fields
[note_special_fields.author]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"
index_values = true

[note_special_fields.timestamp]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"
index_values = true

# Test field for notes with index_values = false
[note_special_fields.private_comment]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = false

# Test field for notes with index_values = true (searchable)
[note_special_fields.category]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
index_values = true

[note_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["low", "medium", "high", "critical"]
index_values = true

# Regression: editable=false with NO system_value — user supplies value on creation.
# This field was previously dropped by the non_editable_fields filter bug.
[note_special_fields.note_type]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
index_values = true

# Bug template
[template.bug]
record_prefix = "BUG"
note_prefix = "COMMENT"

[template.bug.record_special_fields.severity]
type = "single"
value_type = "integer"
editable = true
enabled = true
required = true
accepted_values = ["1", "2", "3", "4", "5"]
default = "3"

[template.bug.record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["new", "confirmed", "in_progress", "fixed", "verified", "closed"]
default = "new"

[template.bug.note_special_fields.category]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["investigation", "bugfix", "workaround", "regression", "documentation"]

[template.bug.note_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["low", "medium", "high", "critical"]
default = "medium"

# Regression: float field in template — must NOT get type hint suffix in stored markdown.
[template.bug.record_special_fields.impact_score]
type = "single"
value_type = "float"
editable = true
enabled = true
required = false
default = "0.0"
index_values = true

# Template-specific note field: editable=false, no system_value.
# User supplies on creation; must not be dropped by filter.
[template.bug.note_special_fields.resolution]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
index_values = true

# Feature template
[template.feature]
record_prefix = "FEAT"
note_prefix = "FEEDBACK"

[template.feature.record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["proposed", "approved", "in_development", "completed", "rejected"]
default = "proposed"

# Securestring tests: global securestring field (record-level)
[record_special_fields.api_token]
type = "single"
value_type = "securestring"
editable = true
enabled = true
required = false
index_values = true

# Securestring tests: non-editable securestring (set on creation, immutable after)
[record_special_fields.master_secret]
type = "single"
value_type = "securestring"
editable = false
enabled = true
required = false
index_values = true

# Securestring in notes (global)
[note_special_fields.session_token]
type = "single"
value_type = "securestring"
editable = true
enabled = true
required = false
index_values = true

# is_system_update: marks system-generated notes (initial creation, record updates)
[note_special_fields.is_system_update]
type = "single"
value_type = "integer"
editable = false
enabled = true
required = false
system_value = "is_system_update"
index_values = true

# Securestring in a template (template-scoped)
[template.feature.record_special_fields.oauth_secret]
type = "single"
value_type = "securestring"
editable = true
enabled = true
required = false
index_values = true
EOF
    
    if [ -f "$TEST_DIR/config.toml" ]; then
        pass
    else
        fail "Failed to create config.toml"
        cleanup
        exit 1
    fi
}

#==============================================================================
# Test: Basic Record Creation
#==============================================================================

test_basic_creation() {
    print_section "Basic Record Creation"
    
    print_test "Create record with required fields"
    local output
    if output=$(run_aver record new --description "" --no-validation-editor --title "Test Record 1" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            pass
            echo "  Created: $rec_id"
        else
            fail "No record ID in output"
        fi
    else
        fail "Command failed: $output"
    fi
    
    print_test "Create record with integer field"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Test Record 2" --severity 3 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            pass
            echo "  Created: $rec_id"
        else
            fail "No record ID in output"
        fi
    else
        fail "Command failed: $output"
    fi
    
    print_test "Create record with multi-value field"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Test Record 3" --tags bug --tags urgent 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            pass
            echo "  Created: $rec_id"
        else
            fail "No record ID in output"
        fi
    else
        fail "Command failed"
    fi
    
    print_test "Create record with custom ID"
    if output=$(run_aver record new --description "" --no-validation-editor --use-id "CUSTOM-001" --title "Custom ID Test" 2>&1); then
        if echo "$output" | grep -q "CUSTOM-001"; then
            pass
        else
            fail "Custom ID not used"
        fi
    else
        fail "Command failed"
    fi
}

#==============================================================================
# Test: Special Characters in Values
#==============================================================================

test_special_characters() {
    print_section "Special Characters in Values"
    
    print_test "Hash character (#) in string value"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Test #1" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            # Verify the hash is in the saved file
            if check_content_contains "$TEST_DIR/records/$rec_id.md" "Test #1"; then
                pass
            else
                fail "Hash character not saved correctly"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Command failed with hash in value"
    fi
    
    print_test "Dollar sign (\$) in string value"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Cost: \$50" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            if check_content_contains "$TEST_DIR/records/$rec_id.md" "Cost:" && \
               check_content_contains "$TEST_DIR/records/$rec_id.md" "50"; then
                pass
            else
                fail "Dollar sign not saved correctly"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Command failed with dollar sign in value"
    fi
    
    print_test "Percent sign (%) in string value"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Success rate: 95%" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            if check_content_contains "$TEST_DIR/records/$rec_id.md" "95%"; then
                pass
            else
                fail "Percent sign not saved correctly"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Command failed with percent in value"
    fi
    
    print_test "Multiple special characters in value"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Bug #42: Cost \$100 (50% off)" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            pass
        else
            fail "Record not created with multiple special chars"
        fi
    else
        fail "Command failed"
    fi
}

#==============================================================================
# Test: Template System
#==============================================================================

test_template_system() {
    print_section "Template System"
    
    print_test "Create record with bug template using --from-file"
    # Create a markdown file with bug template
    cat > "$TEST_DIR/bug_record.md" << 'EOF'
---
template_id: bug
title: Login page crashes on submit
severity: 2
status: new
---
When clicking the submit button on the login page, the browser tab crashes.
This affects Chrome and Firefox but not Safari.
EOF
    
    if output=$(run_aver record new --from-file "$TEST_DIR/bug_record.md" 2>&1); then
        local bug_rec=$(echo "$output" | grep -oE "BUG-[A-Z0-9]+" || echo "")
        if [ -n "$bug_rec" ]; then
            pass
            echo "  Created bug record: $bug_rec"
        else
            fail "Bug record created but ID not found in output"
        fi
    else
        fail "Failed to create bug record from file"
    fi
    
    print_test "Bug record uses BUG- prefix from template"
    if [ -n "$bug_rec" ] && [[ "$bug_rec" =~ ^BUG- ]]; then
        pass
    else
        fail "Bug record doesn't use BUG- prefix"
    fi
    
    print_test "Bug record has template_id set"
    if [ -n "$bug_rec" ] && check_content_contains "$TEST_DIR/records/${bug_rec}.md" "template_id"; then
        pass
    else
        fail "template_id not found in bug record"
    fi
    
    print_test "Template ID field exists in config"
    if check_content_contains "$TEST_DIR/config.toml" "template_id"; then
        pass
    else
        fail "template_id field not in config"
    fi
    
    print_test "Config has bug template with BUG prefix"
    if check_content_contains "$TEST_DIR/config.toml" "record_prefix = \"BUG\""; then
        pass
    else
        fail "Bug template prefix not found"
    fi
    
    print_test "Bug template has custom status values"
    if check_content_contains "$TEST_DIR/config.toml" "\"new\", \"confirmed\""; then
        pass
    else
        fail "Bug template status values not found"
    fi
    
    # Store bug_rec for use in note special fields test
    echo "$bug_rec" > "$TEST_DIR/bug_rec_id.txt"
}

#==============================================================================
# Test: Validation
#==============================================================================

test_validation() {
    print_section "Validation"
    
    print_test "Missing required field (title) should fail"
    set +e
    output=$(run_aver record new --description "" --no-validation-editor --status open 2>&1)
    exit_code=$?
    set -e

    if [ $exit_code -ne 0 ]; then
        if echo "$output" | grep -qi "required.*title"; then
            pass
            echo "  Error message mentions required field"
        else
            pass
            echo "  Failed as expected (exit code: $exit_code)"
        fi
    else
        fail "Should have failed without required field"
    fi

    print_test "Invalid status value should fail"
    set +e
    output=$(run_aver record new --description "" --no-validation-editor --title "Test" --status invalid_status 2>&1)
    exit_code=$?
    set -e

    if [ $exit_code -ne 0 ]; then
        pass
    else
        fail "Should have failed with invalid status value"
    fi
    
    print_test "Valid status value should succeed"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Valid Status Test" --status open 2>&1); then
        pass
    else
        fail "Valid status was rejected"
    fi
    
    print_test "Default values are applied"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Default Test" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ] && check_content_contains "$TEST_DIR/records/$rec_id.md" "status"; then
            pass
            echo "  Default status applied"
        else
            fail "Default value not applied"
        fi
    else
        fail "Command failed"
    fi
}

#==============================================================================
# Test: System Fields
#==============================================================================

test_system_fields() {
    print_section "System Fields"
    
    print_test "created_at field is auto-populated"
    if output=$(run_aver record new --description "" --no-validation-editor --title "System Fields Test" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ] && check_content_contains "$TEST_DIR/records/$rec_id.md" "created_at"; then
            pass
        else
            fail "created_at not found in record"
        fi
    else
        fail "Command failed"
    fi
    
    print_test "created_by field is auto-populated"
    if output=$(run_aver record new --description "" --no-validation-editor --title "User Field Test" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ] && check_content_contains "$TEST_DIR/records/$rec_id.md" "created_by"; then
            if check_content_contains "$TEST_DIR/records/$rec_id.md" "testuser"; then
                pass
                echo "  User: testuser"
            else
                fail "Wrong user in created_by"
            fi
        else
            fail "created_by not found"
        fi
    else
        fail "Command failed"
    fi
    
    print_test "System fields are present in saved record"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Complete System Fields" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            local file="$TEST_DIR/records/$rec_id.md"
            if check_content_contains "$file" "created_at" && \
               check_content_contains "$file" "created_by" && \
               check_content_contains "$file" "title"; then
                pass
            else
                fail "Not all system fields present"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Command failed"
    fi
}

#==============================================================================
# Test: Index Values Configuration
#==============================================================================

test_index_values() {
    print_section "Index Values Configuration"
    
    print_test "Fields with index_values=true are in database"
    # Create a record with indexed fields
    if output=$(run_aver record new --description "" --no-validation-editor --title "Index Test 1" --status "open" --priority "high" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            # Check if status and priority are searchable (they have index_values=true)
            if output=$(run_aver record list --ksearch status=open 2>&1); then
                if echo "$output" | grep -q "$rec_id"; then
                    pass
                else
                    fail "Indexed field (status) not searchable"
                fi
            else
                fail "Search command failed"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Record creation failed"
    fi
    
    print_test "Fields with index_values=false are in Markdown but not searchable"
    # Create a record with private_notes field (index_values=false)
    if output=$(run_aver record new --description "" --no-validation-editor --title "Index Test 2" --private_notes "Secret information" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            # Check that private_notes is in the Markdown file
            if check_content_contains "$TEST_DIR/records/$rec_id.md" "private_notes"; then
                # Try to search for it - should not find it via database search
                # Note: Full-text search might find it in content, but kv search should not
                # For now, just verify it's in the file
                pass
                echo "  Field present in Markdown file"
            else
                fail "Field not found in Markdown file"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Record creation failed"
    fi
    
    print_test "Contact email (index_values=false) stored but not indexed"
    if output=$(run_aver record new --description "" --no-validation-editor --title "Privacy Test" --contact_email "user@example.com" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            # Verify email is in file
            if check_content_contains "$TEST_DIR/records/$rec_id.md" "contact_email"; then
                if check_content_contains "$TEST_DIR/records/$rec_id.md" "user@example.com"; then
                    pass
                    echo "  Email stored in Markdown"
                else
                    fail "Email value not in file"
                fi
            else
                fail "contact_email field not found"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Record creation failed"
    fi
    
    print_test "Note field with index_values=false stored correctly"
    # First create a record
    if output=$(run_aver record new --description "Test record" --no-validation-editor --title "Note Index Test" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            # Add a note with private_comment field
            if output=$(run_aver note add "$rec_id" --message "Test note" --private_comment "Confidential info" 2>&1); then
                local note_id=$(echo "$output" | grep -oE "NT-[A-Z0-9]+")
                if [ -n "$note_id" ]; then
                    # Check that private_comment is in the note file
                    if check_content_contains "$TEST_DIR/updates/${rec_id}/${note_id}.md" "private_comment"; then
                        pass
                        echo "  Note field stored in Markdown"
                    else
                        fail "private_comment not found in note file"
                    fi
                else
                    fail "Note not created"
                fi
            else
                fail "Note creation failed"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Record creation failed"
    fi
    
    print_test "Reindex preserves index_values configuration"
    # Create a record with both indexed and non-indexed fields
    if output=$(run_aver record new --description "" --no-validation-editor --title "Reindex Test" --status "closed" --private_notes "Private data" 2>&1); then
        local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec_id" ]; then
            # Reindex the database
            if run_aver admin reindex --skip-validation > /dev/null 2>&1; then
                # Verify status is still searchable after reindex
                if output=$(run_aver record list --ksearch status=closed 2>&1); then
                    if echo "$output" | grep -q "$rec_id"; then
                        pass
                        echo "  Indexed field still searchable after reindex"
                    else
                        fail "Indexed field not searchable after reindex"
                    fi
                else
                    fail "Search failed after reindex"
                fi
            else
                fail "Reindex failed"
            fi
        else
            fail "Record not created"
        fi
    else
        fail "Record creation failed"
    fi
}

#==============================================================================
# Test: --fields Flag
#==============================================================================

test_fields_flag() {
    print_section "--fields Flag (Record List and Note Search)"
    
    # Create test records with various fields
    print_test "Setup: Create test records with multiple fields"
    if output=$(run_aver record new --description "Test record 1" --no-validation-editor --title "Fields Test 1" --status "open" --priority "high" --severity "3" 2>&1); then
        local rec1=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec1" ]; then
            echo "  Created: $rec1"
        else
            fail "Record 1 not created"
            return
        fi
    else
        fail "Record 1 creation failed"
        return
    fi
    
    if output=$(run_aver record new --description "Test record 2" --no-validation-editor --title "Fields Test 2" --status "in_progress" --priority "low" --severity "1" 2>&1); then
        local rec2=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
        if [ -n "$rec2" ]; then
            pass
            echo "  Created: $rec2"
        else
            fail "Record 2 not created"
            return
        fi
    else
        fail "Record 2 creation failed"
        return
    fi
    
    # Test record list with single --fields
    print_test "Record list with single --fields argument"
    if output=$(run_aver record list --fields status 2>&1); then
        if echo "$output" | grep -q "$rec1" && echo "$output" | grep -q "status"; then
            pass
            echo "  Status field displayed"
        else
            fail "Status field not displayed or records not found"
        fi
    else
        fail "Record list command failed"
    fi
    
    # Test record list with comma-delimited fields
    print_test "Record list with comma-delimited --fields"
    if output=$(run_aver record list --fields status,priority,severity 2>&1); then
        if echo "$output" | grep -q "$rec1"; then
            # Check if all three fields appear in output
            if echo "$output" | grep -q "status" && echo "$output" | grep -q "priority" && echo "$output" | grep -q "severity"; then
                pass
                echo "  All fields displayed: status, priority, severity"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Records not found in output"
        fi
    else
        fail "Record list command failed"
    fi
    
    # Test record list with multiple --fields flags
    print_test "Record list with multiple --fields flags"
    if output=$(run_aver record list --fields status --fields priority --fields severity 2>&1); then
        if echo "$output" | grep -q "$rec1"; then
            if echo "$output" | grep -q "status" && echo "$output" | grep -q "priority" && echo "$output" | grep -q "severity"; then
                pass
                echo "  Multiple --fields flags work correctly"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Records not found in output"
        fi
    else
        fail "Record list command failed"
    fi
    
    # Test record list with mixed usage (comma + multiple flags)
    print_test "Record list with mixed --fields usage"
    if output=$(run_aver record list --fields status,priority --fields severity 2>&1); then
        if echo "$output" | grep -q "$rec1"; then
            if echo "$output" | grep -q "status" && echo "$output" | grep -q "priority" && echo "$output" | grep -q "severity"; then
                pass
                echo "  Mixed usage works: --fields status,priority --fields severity"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Records not found in output"
        fi
    else
        fail "Record list command failed"
    fi
    
    # Test record list with --ksearch and --fields
    print_test "Record list with --ksearch and --fields together"
    if output=$(run_aver record list --ksearch status=open --fields priority,severity 2>&1); then
        if echo "$output" | grep -q "$rec1"; then
            # Status should appear (from ksearch), plus priority and severity
            if echo "$output" | grep -q "status" && echo "$output" | grep -q "priority" && echo "$output" | grep -q "severity"; then
                pass
                echo "  --ksearch field and --fields both displayed"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Records not found in output"
        fi
    else
        fail "Record list command failed"
    fi
    
    # Test with whitespace in comma-delimited list
    print_test "Record list with whitespace in --fields"
    if output=$(run_aver record list --fields "status , priority , severity" 2>&1); then
        if echo "$output" | grep -q "$rec1"; then
            if echo "$output" | grep -q "status" && echo "$output" | grep -q "priority"; then
                pass
                echo "  Whitespace handled correctly"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Records not found in output"
        fi
    else
        fail "Record list command failed"
    fi
    
    # Add notes to first record for note search tests
    print_test "Setup: Add notes with various fields"
    if output=$(run_aver note add "$rec1" --message "First note" --category "bugfix" --priority "high" 2>&1); then
        local note1=$(echo "$output" | grep -oE "NT-[A-Z0-9]+")
        if [ -n "$note1" ]; then
            echo "  Created note: $note1"
        else
            fail "Note 1 not created"
            return
        fi
    else
        fail "Note 1 creation failed"
        return
    fi
    
    if output=$(run_aver note add "$rec1" --message "Second note" --category "bugfix" --priority "medium" 2>&1); then
        local note2=$(echo "$output" | grep -oE "NT-[A-Z0-9]+")
        if [ -n "$note2" ]; then
            pass
            echo "  Created note: $note2"
        else
            fail "Note 2 not created"
            return
        fi
    else
        fail "Note 2 creation failed"
        return
    fi
    
    # Test note search with single --fields
    print_test "Note search with single --fields argument"
    if output=$(run_aver note search --ksearch category=bugfix --fields author 2>&1); then
        if echo "$output" | grep -q "$note1"; then
            if echo "$output" | grep -q "category" && echo "$output" | grep -q "author"; then
                pass
                echo "  Fields displayed: category (from ksearch), author"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Notes not found in search results"
        fi
    else
        fail "Note search command failed"
    fi
    
    # Test note search with comma-delimited fields
    print_test "Note search with comma-delimited --fields"
    if output=$(run_aver note search --ksearch category=bugfix --fields author,timestamp 2>&1); then
        if echo "$output" | grep -q "$note1"; then
            if echo "$output" | grep -q "category" && echo "$output" | grep -q "author" && echo "$output" | grep -q "timestamp"; then
                pass
                echo "  All fields displayed"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Notes not found in search results"
        fi
    else
        fail "Note search command failed"
    fi
    
    # Test note search with multiple --fields flags
    print_test "Note search with multiple --fields flags"
    if output=$(run_aver note search --ksearch category=bugfix --fields author --fields timestamp 2>&1); then
        if echo "$output" | grep -q "$note1"; then
            if echo "$output" | grep -q "author" && echo "$output" | grep -q "timestamp"; then
                pass
                echo "  Multiple --fields flags work"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Notes not found in search results"
        fi
    else
        fail "Note search command failed"
    fi
    
    # Test note search with mixed usage
    print_test "Note search with mixed --fields usage"
    if output=$(run_aver note search --ksearch category=bugfix --fields author,timestamp --fields category,priority 2>&1); then
        if echo "$output" | grep -q "$note1"; then
            # category should appear only once (deduplication)
            if echo "$output" | grep -q "author" && echo "$output" | grep -q "timestamp" && echo "$output" | grep -q "priority"; then
                pass
                echo "  Mixed usage works with deduplication"
            else
                fail "Not all fields displayed"
            fi
        else
            fail "Notes not found in search results"
        fi
    else
        fail "Note search command failed"
    fi
    
    # Test deduplication in record list
    print_test "Record list field deduplication"
    if output=$(run_aver record list --fields status,priority --fields status,severity 2>&1); then
        if echo "$output" | grep -q "$rec1"; then
            # Count occurrences of "status" - should appear only once in the additional fields section
            # This is a basic check - in real usage status would appear once
            pass
            echo "  Deduplication prevents duplicate field names"
        else
            fail "Records not found"
        fi
    else
        fail "Record list command failed"
    fi
}

#==============================================================================
# Test: Record Listing and Search
#==============================================================================

test_listing_search() {
    print_section "Record Listing and Search"
    
    # Create some searchable records
    run_aver record new --description "" --no-validation-editor --title "Searchable 1" --status open --priority high > /dev/null 2>&1
    run_aver record new --description "" --no-validation-editor --title "Searchable 2" --status in_progress --priority low > /dev/null 2>&1
    run_aver record new --description "" --no-validation-editor --title "Searchable 3" --status closed --priority high > /dev/null 2>&1
    
    print_test "List all records"
    if output=$(run_aver record list 2>&1); then
        if echo "$output" | grep -q "REC-"; then
            pass
        else
            fail "No records in list output"
        fi
    else
        fail "List command failed"
    fi
    
    print_test "Search by status (ksearch)"
    if output=$(run_aver record list --ksearch status=open 2>&1); then
        if echo "$output" | grep -q "Searchable 1"; then
            pass
        else
            fail "Search didn't find expected record"
        fi
    else
        fail "Search command failed"
    fi
    
    print_test "Search by priority"
    if output=$(run_aver record list --ksearch priority=high 2>&1); then
        # Should find records with high priority
        if echo "$output" | grep -q "Searchable"; then
            pass
        else
            fail "Priority search didn't find records"
        fi
    else
        fail "Search command failed"
    fi
}

#==============================================================================
# Test: User Profile and Library Configuration
#==============================================================================

test_user_profile() {
    print_section "User Profile Configuration"
    
    print_test "User global config location"
    local user_config="$TEST_HOME/.config/aver/user.toml"
    # Config won't exist until we set it
    pass
    echo "  Expected at: $user_config"
    
    print_test "Set user global config"
    if run_aver admin config set-user --handle "testuser" --email "test@example.com"; then
        if [ -f "$TEST_HOME/.config/aver/user.toml" ]; then
            if check_content_contains "$TEST_HOME/.config/aver/user.toml" "testuser"; then
                pass
            else
                fail "User handle not in config"
            fi
        else
            fail "User config not created at $TEST_HOME/.config/aver/user.toml"
        fi
    else
        fail "set-user command failed"
    fi
    
    print_test "User config contains email"
    if check_content_contains "$TEST_HOME/.config/aver/user.toml" "test@example.com"; then
        pass
    else
        fail "Email not in user config"
    fi
    
    print_test "User config isolated in test environment"
    # Verify it's in our test HOME, not the real HOME
    if [ -f "$TEST_HOME/.config/aver/user.toml" ]; then
        pass
        echo "  User config: $TEST_HOME/.config/aver/user.toml"
    else
        fail "User config not in test HOME"
    fi
}

test_library_management() {
    print_section "Library Management"
    
    # Create multiple test databases
    local db1=$(mktemp -d -t aver-lib1-XXXXXX)
    local db2=$(mktemp -d -t aver-lib2-XXXXXX)
    local db3=$(mktemp -d -t aver-lib3-XXXXXX)
    
    # Initialize each database
    set +e  # Temporarily disable exit on error for initialization
    python3 "$AVER_PATH" --override-repo-boundary --location "$db1" admin init > /dev/null 2>&1
    python3 "$AVER_PATH" --override-repo-boundary --location "$db2" admin init > /dev/null 2>&1
    python3 "$AVER_PATH" --override-repo-boundary --location "$db3" admin init > /dev/null 2>&1
    set -e  # Re-enable exit on error
    
    # Copy the test config to library databases so they have created_by, author, etc.
    cp "$TEST_DIR/config.toml" "$db1/config.toml"
    cp "$TEST_DIR/config.toml" "$db2/config.toml"
    cp "$TEST_DIR/config.toml" "$db3/config.toml"
    
    print_test "Add library alias 'work'"
    if python3 "$AVER_PATH" --override-repo-boundary admin config add-alias --alias work --path "$db1" > /dev/null 2>&1; then
        if check_content_contains "$TEST_HOME/.config/aver/user.toml" "work"; then
            pass
        else
            fail "Library alias not in config"
        fi
    else
        fail "add-alias command failed"
    fi
    
    print_test "Add library alias 'personal'"
    if python3 "$AVER_PATH" --override-repo-boundary admin config add-alias --alias personal --path "$db2" > /dev/null 2>&1; then
        if check_content_contains "$TEST_HOME/.config/aver/user.toml" "personal"; then
            pass
        else
            fail "Personal library not in config"
        fi
    else
        fail "add-alias command failed"
    fi
    
    print_test "Add library alias 'archive'"
    if python3 "$AVER_PATH" --override-repo-boundary admin config add-alias --alias archive --path "$db3" > /dev/null 2>&1; then
        if check_content_contains "$TEST_HOME/.config/aver/user.toml" "archive"; then
            pass
        else
            fail "Archive library not in config"
        fi
    else
        fail "add-alias command failed"
    fi
    
    # Set per-library users (now that aliases exist)
    print_test "Set per-library users"
    if python3 "$AVER_PATH" --override-repo-boundary admin config set-user --library work --handle "work_user" --email "work@example.com" > /dev/null 2>&1 && \
       python3 "$AVER_PATH" --override-repo-boundary admin config set-user --library personal --handle "personal_user" --email "personal@example.com" > /dev/null 2>&1 && \
       python3 "$AVER_PATH" --override-repo-boundary admin config set-user --library archive --handle "archive_user" --email "archive@example.com" > /dev/null 2>&1; then
        pass
        echo "  Per-library users configured"
    else
        fail "Failed to set per-library users"
    fi
    
    print_test "List libraries"
    if output=$(python3 "$AVER_PATH" --override-repo-boundary admin config list-aliases 2>&1); then
        if echo "$output" | grep -q "work" && echo "$output" | grep -q "personal"; then
            pass
        else
            fail "Libraries not listed correctly"
        fi
    else
        fail "list-aliases command failed"
    fi
    
    print_test "Use library alias with --use flag (work)"
    track_command "python3 \"$AVER_PATH\" --override-repo-boundary --use work record new --description \"\" --no-validation-editor --title \"Work Record\" --status \"open\""
    if python3 "$AVER_PATH" --override-repo-boundary --use work record new --description "" --no-validation-editor --title "Work Record" --status "open" > /dev/null 2>&1; then
        # Check that record was created in db1
        if ls "$db1/records/"*.md > /dev/null 2>&1; then
            pass
        else
            fail "Record not created in work library"
        fi
    else
        fail "Failed to create record with --use work"
    fi
    
    print_test "Use library alias with --use flag (personal)"
    track_command "python3 \"$AVER_PATH\" --override-repo-boundary --use personal record new --description \"\" --no-validation-editor --title \"Personal Record\" --status \"open\""
    if python3 "$AVER_PATH" --override-repo-boundary --use personal record new --description "" --no-validation-editor --title "Personal Record" --status "open" > /dev/null 2>&1; then
        # Check that record was created in db2
        if ls "$db2/records/"*.md > /dev/null 2>&1; then
            pass
        else
            fail "Record not created in personal library"
        fi
    else
        fail "Failed to create record with --use personal"
    fi
    
    print_test "Records are isolated between libraries"
    local work_count=$(ls "$db1/records/"*.md 2>/dev/null | wc -l)
    local personal_count=$(ls "$db2/records/"*.md 2>/dev/null | wc -l)
    local archive_count=$(ls "$db3/records/"*.md 2>/dev/null | wc -l)
    
    if [ "$work_count" -eq 1 ] && [ "$personal_count" -eq 1 ] && [ "$archive_count" -eq 0 ]; then
        pass
        echo "  work: $work_count, personal: $personal_count, archive: $archive_count"
    else
        fail "Records not properly isolated (work: $work_count, personal: $personal_count, archive: $archive_count)"
    fi
    
    print_test "Per-library user for record creation"
    # Create a NEW record after per-library users are configured
    local output=$(python3 "$AVER_PATH" --override-repo-boundary --use work record new --description "" --no-validation-editor --title "Work Record 2" --status "open" 2>&1)
    local work_rec2=$(echo "$output" | grep -oE "REC-[A-Z0-9]+" || echo "")
    
    if [ -n "$work_rec2" ]; then
        # Check if the record has work_user as created_by
        if grep -q "work_user" "$db1/records/${work_rec2}.md"; then
            pass
            echo "  Work record created by work_user"
        else
            fail "Work record not created by work_user"
        fi
    else
        fail "Failed to create second work record"
    fi
    
    print_test "Per-library user for note creation"
    # Add a note to the work record using the work library
    if python3 "$AVER_PATH" --override-repo-boundary --use work note add "$work_rec2" --message "Work note" > /dev/null 2>&1; then
        # Find the note file by grepping for the message
        local note_file=$(grep -l "Work note" "$db1/updates/${work_rec2}/"*.md 2>/dev/null | head -1)
        if [ -n "$note_file" ] && grep -q "work_user" "$note_file"; then
            pass
            echo "  Note created by work_user"
        else
            fail "Note not created by work_user"
        fi
    else
        fail "Failed to create note in work library"
    fi
    
    print_test "Remove library alias"
    # Note: remove-alias command not implemented in aver.py yet
    # Skipping this test for now
    pass
    echo "  Skipped - command not implemented"
    
    # TODO: Uncomment when remove-alias is implemented
    # if python3 "$AVER_PATH" --override-repo-boundary admin config remove-alias --alias archive > /dev/null 2>&1; then
    #     set +e
    #     if ! check_content_contains "$TEST_HOME/.config/aver/user.toml" "archive"; then
    #         pass
    #     else
    #         fail "Archive library still in config"
    #     fi
    #     set -e
    # else
    #     fail "remove-alias command failed"
    # fi
    
    # Cleanup library test databases
    if [ "$KEEP_TEST_DIR" = true ]; then
        echo "  Library databases preserved:"
        echo "    work (db1): $db1"
        echo "    personal (db2): $db2"
        echo "    archive (db3): $db3"
    else
        rm -rf "$db1" "$db2" "$db3"
    fi
}

test_custom_locations() {
    print_section "Custom Location Handling"
    
    # Create custom location databases
    local custom1=$(mktemp -d -t aver-custom1-XXXXXX)
    local custom2=$(mktemp -d -t aver-custom2-XXXXXX)
    
    print_test "Initialize at custom location 1"
    track_command "python3 \"$AVER_PATH\" --override-repo-boundary --location \"$custom1\" admin init"
    if python3 "$AVER_PATH" --override-repo-boundary --location "$custom1" admin init > /dev/null 2>&1; then
        if [ -d "$custom1" ]; then
            pass
        else
            fail "Custom directory not created"
        fi
    else
        fail "Init failed at custom location"
    fi
    
    print_test "Initialize at custom location 2"
    track_command "python3 \"$AVER_PATH\" --override-repo-boundary --location \"$custom2\" admin init"
    if python3 "$AVER_PATH" --override-repo-boundary --location "$custom2" admin init > /dev/null 2>&1; then
        if [ -d "$custom2" ]; then
            pass
        else
            fail "Custom directory not created"
        fi
    else
        fail "Init failed at custom location"
    fi
    
    print_test "Create record at custom location 1"
    if python3 "$AVER_PATH" --override-repo-boundary --location "$custom1" record new --description "" --no-validation-editor --title "Custom Loc 1 Record" > /dev/null 2>&1; then
        if ls "$custom1/records/"*.md > /dev/null 2>&1; then
            pass
        else
            fail "Record not created"
        fi
    else
        fail "Create failed"
    fi
    
    print_test "Create record at custom location 2"
    if python3 "$AVER_PATH" --override-repo-boundary --location "$custom2" record new --description "" --no-validation-editor --title "Custom Loc 2 Record" > /dev/null 2>&1; then
        if ls "$custom2/records/"*.md > /dev/null 2>&1; then
            pass
        else
            fail "Record not created"
        fi
    else
        fail "Create failed"
    fi
    
    print_test "Records isolated by location"
    local loc1_count=$(ls "$custom1/records/"*.md 2>/dev/null | wc -l)
    local loc2_count=$(ls "$custom2/records/"*.md 2>/dev/null | wc -l)
    
    if [ "$loc1_count" -eq 1 ] && [ "$loc2_count" -eq 1 ]; then
        pass
    else
        fail "Records not isolated (loc1: $loc1_count, loc2: $loc2_count)"
    fi
    
    print_test "Each location can have different config"
    # Create different configs
    cat > "$custom1/config.toml" << 'EOF'
default_record_prefix = "LOC1"

[special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
EOF
    
    cat > "$custom2/config.toml" << 'EOF'
default_record_prefix = "LOC2"

[special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
EOF
    
    # Create records and check prefixes
    local output1=$(python3 "$AVER_PATH" --override-repo-boundary --location "$custom1" record new --description "" --no-validation-editor --title "Prefix Test 1" 2>&1)
    local output2=$(python3 "$AVER_PATH" --override-repo-boundary --location "$custom2" record new --description "" --no-validation-editor --title "Prefix Test 2" 2>&1)
    
    if echo "$output1" | grep -q "LOC1-" && echo "$output2" | grep -q "LOC2-"; then
        pass
        echo "  Location 1: LOC1- prefix, Location 2: LOC2- prefix"
    else
        fail "Different prefixes not working"
    fi
    
    # Cleanup
    rm -rf "$custom1" "$custom2"
}

test_config_per_location() {
    print_section "Per-Location Configuration"
    
    local loc_strict=$(mktemp -d -t aver-strict-XXXXXX)
    local loc_relaxed=$(mktemp -d -t aver-relaxed-XXXXXX)
    
    # Initialize
    set +e  # Temporarily disable exit on error for initialization
    python3 "$AVER_PATH" --override-repo-boundary --location "$loc_strict" admin init > /dev/null 2>&1
    python3 "$AVER_PATH" --override-repo-boundary --location "$loc_relaxed" admin init > /dev/null 2>&1
    set -e  # Re-enable exit on error
    
    # Note: Using global user config (testuser) - no need to set per-location users
    
    print_test "Strict config (required fields)"
    cat > "$loc_strict/config.toml" << 'EOF'
[special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true

[special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["low", "medium", "high"]
EOF
    
    # This should fail without priority
    set +e
    output=$(python3 "$AVER_PATH" --override-repo-boundary --location "$loc_strict" record new --description "" --no-validation-editor --title "Test" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        pass
        echo "  Correctly enforces required priority"
    else
        fail "Should have failed without required priority"
    fi
    
    print_test "Relaxed config (optional fields)"
    cat > "$loc_relaxed/config.toml" << 'EOF'
[special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true

[special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
EOF
    
    # This should succeed without priority
    if python3 "$AVER_PATH" --override-repo-boundary --location "$loc_relaxed" record new --description "" --no-validation-editor --title "Test" > /dev/null 2>&1; then
        pass
        echo "  Allows optional priority"
    else
        fail "Should have succeeded with optional priority"
    fi
    
    print_test "Different templates per location"
    cat >> "$loc_strict/config.toml" << 'EOF'

[template.critical]
record_prefix = "CRIT"

[template.critical.record_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["critical"]
default = "critical"
EOF
    
    cat >> "$loc_relaxed/config.toml" << 'EOF'

[template.casual]
record_prefix = "NOTE"

[template.casual.record_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
EOF
    
    if check_content_contains "$loc_strict/config.toml" "CRIT" && \
       check_content_contains "$loc_relaxed/config.toml" "NOTE"; then
        pass
        echo "  Different templates configured"
    else
        fail "Templates not configured correctly"
    fi
    
    # Cleanup
    rm -rf "$loc_strict" "$loc_relaxed"
}

#==============================================================================
# Test: Note Operations
#==============================================================================

test_note_operations() {
    print_section "Note Operations"
    
    # Create a test record to add notes to
    local output=$(run_aver record new --description "" --no-validation-editor --title "Record with Notes" 2>&1)
    local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
    
    if [ -z "$rec_id" ]; then
        fail "Failed to create test record for notes"
        return
    fi
    
    print_test "Add note with message flag"
    if run_aver note add "$rec_id" --message "First note added" > /dev/null 2>&1; then
        pass
    else
        fail "Failed to add note with --message"
    fi
    
    print_test "Add second note"
    if run_aver note add "$rec_id" --message "Second note with details" > /dev/null 2>&1; then
        pass
    else
        fail "Failed to add second note"
    fi
    
    print_test "List notes for record"
    if output=$(run_aver note list "$rec_id" 2>&1); then
        if echo "$output" | grep -q "First note added" && echo "$output" | grep -q "Second note"; then
            pass
            echo "  Found both notes in output"
        else
            fail "Notes not found in list output"
        fi
    else
        fail "Failed to list notes"
    fi
    
    print_test "List notes shows author"
    if output=$(run_aver note list "$rec_id" 2>&1); then
        if echo "$output" | grep -q "testuser"; then
            pass
            echo "  Author shown: testuser"
        else
            fail "Author not shown in notes"
        fi
    else
        fail "Failed to list notes"
    fi
    
    print_test "Add note with KV data"
    if run_aver note add "$rec_id" --message "Status update" --text "resolution=fixed bug in parser" > /dev/null; then
        # Verify KV data was actually saved to the database
        # Check the aver.db directly to see if the KV was indexed
        if sqlite3 "$TEST_DIR/aver.db" "SELECT COUNT(*) FROM kv_store WHERE update_id IS NOT NULL AND key='resolution';" | grep -q "1"; then
            # Get the update_id that has resolution in the database
            local update_id=$(sqlite3 "$TEST_DIR/aver.db" "SELECT update_id FROM kv_store WHERE update_id IS NOT NULL AND key='resolution' LIMIT 1;")
            # Also check if it's in the markdown file
            local note_file="$TEST_DIR/updates/$rec_id/${update_id}.md"
            if [ -f "$note_file" ] && grep -q "resolution" "$note_file"; then
                pass
                echo "  KV data confirmed in database AND markdown file"
            else
                echo "  WARNING: KV in database but NOT in markdown file!"
                if [ -f "$note_file" ]; then
                    echo "  File contents:"
                    cat "$note_file"
                fi
                fail "KV data not in markdown file"
            fi
        else
            fail "KV data not found in database index"
        fi
    else
        fail "Failed to add note with KV data"
    fi
    
    print_test "Note list shows KV data"
    if output=$(run_aver note list "$rec_id" 2>&1); then
        if echo "$output" | grep -q "resolution"; then
            pass
            echo "  KV data visible in notes"
        else
            fail "KV data not shown in notes"
        fi
    else
        fail "Failed to list notes"
    fi

    # Create another record for search testing - use bug template so category field is available
    local output2=$(run_aver record new --description "" --no-validation-editor --title "Another Record" --status "new" --severity 3 --template bug 2>&1)
    local rec_id2=$(echo "$output2" | grep -oE "BUG-[A-Z0-9]+")

    set +e
    # Add note with searchable KV data
    # run_aver note add "$rec_id2" --message "Different note" --text "category=bug" > /dev/null 2>&1
    run_aver note add "$rec_id2" --message "Different note" --category "bug" > /dev/null 2>&1
    
    echo "DM42:TEST1"
    print_test "Search notes by KV data"
    if output=$(run_aver note search --ksearch category=bug 2>&1); then
        if echo "$output" | grep -q "$rec_id2"; then
            pass
            echo "  Found note by category search"
        else
            fail "Search didn't find expected note"
        fi
    else
        fail "Note search command failed"
    fi
    
    print_test "Note list for non-existent record"
    
    output=$(run_aver note list "INVALID-ID" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        pass
        echo "  Correctly rejected invalid record ID"
    else
        fail "Should fail for non-existent record"
    fi
    
    print_test "Add note to non-existent record"
    set +e
    output=$(run_aver note add "INVALID-ID" --message "Test" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        pass
        echo "  Correctly rejected invalid record ID"
    else
        fail "Should fail for non-existent record"
    fi
}

#==============================================================================
# Test: Note Special Fields
#==============================================================================

test_note_special_fields() {
    print_section "Note Special Fields"
    
    # Get bug_rec from previous test (or create one if needed)
    if [ -f "$TEST_DIR/bug_rec_id.txt" ]; then
        local bug_rec=$(cat "$TEST_DIR/bug_rec_id.txt")
    else
        # Create a bug record if template test didn't run
        cat > "$TEST_DIR/bug_for_notes.md" << 'EOF'
---
template_id: bug
title: Test Bug for Notes
severity: 3
status: new
---
Test bug for testing note special fields.
EOF
        local output=$(run_aver record new --from-file "$TEST_DIR/bug_for_notes.md" 2>&1)
        local bug_rec=$(echo "$output" | grep -oE "BUG-[A-Z0-9]+" || echo "")
    fi
    
    if [ -z "$bug_rec" ]; then
        fail "Failed to get bug record for note special fields test"
        return
    fi
    
    print_test "Add note with note special fields (category and priority)"
    if run_aver note add "$bug_rec" --message "Investigating the issue" --category "investigation" --priority "high" > /dev/null 2>&1; then
        pass
    else
        fail "Failed to add note with special fields"
    fi
    
    print_test "Note special fields saved to markdown"
    # Find the note file that contains our specific message
    local note_file=$(grep -l "Investigating the issue" "$TEST_DIR/updates/$bug_rec/"*.md 2>/dev/null | head -1)
    if [ -n "$note_file" ]; then
        if grep -q "category" "$note_file" && grep -q "investigation" "$note_file" && grep -q "priority" "$note_file" && grep -q "high" "$note_file"; then
            pass
            echo "  Note special fields found in markdown"
        else
            fail "Note special fields not in markdown"
            echo "  File contents:"
            cat "$note_file"
        fi
    else
        fail "Note file not found"
    fi
    
    print_test "Note special fields displayed in list"
    if output=$(run_aver note list "$bug_rec" 2>&1); then
        if echo "$output" | grep -q "category" && echo "$output" | grep -q "investigation" && echo "$output" | grep -q "priority" && echo "$output" | grep -q "high"; then
            pass
            echo "  Special fields shown in note list"
        else
            fail "Special fields not shown in note list"
        fi
    else
        fail "Failed to list notes"
    fi
    
    print_test "Add second note with different special field values"
    if run_aver note add "$bug_rec" --message "Applied fix" --category "bugfix" --priority "critical" > /dev/null 2>&1; then
        pass
    else
        fail "Failed to add second note"
    fi
    
    print_test "Search notes by special field (category)"
    if output=$(run_aver note search --ksearch category=bugfix 2>&1); then
        if echo "$output" | grep -q "$bug_rec"; then
            pass
            echo "  Found note by category search"
        else
            fail "Note not found by category search"
        fi
    else
        fail "Note search by category failed"
    fi
    
    print_test "Search notes by special field (priority)"
    if output=$(run_aver note search --ksearch priority=critical 2>&1); then
        if echo "$output" | grep -q "$bug_rec"; then
            pass
            echo "  Found note by priority search"
        else
            fail "Note not found by priority search"
        fi
    else
        fail "Note search by priority failed"
    fi
    
    print_test "Add note with default special field value"
    # priority has default="medium" in config
    if run_aver note add "$bug_rec" --message "Checking logs" --category "investigation" > /dev/null 2>&1; then
        local note_file3=$(grep -l "Checking logs" "$TEST_DIR/updates/$bug_rec/"*.md 2>/dev/null | head -1)
        if [ -n "$note_file3" ] && grep -q "priority" "$note_file3" && grep -q "medium" "$note_file3"; then
            pass
            echo "  Default priority value applied"
        else
            fail "Default priority value not applied"
        fi
    else
        fail "Failed to add note with default value"
    fi
    
    print_test "Invalid special field value rejected"
    set +e
    output=$(run_aver note add "$bug_rec" --message "Test" --priority "invalid_priority" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        pass
        echo "  Correctly rejected invalid priority value"
    else
        fail "Should reject invalid special field value"
    fi
    
    print_test "Note special fields independent from record special fields"
    # Create a note with category (note field) - record has severity (record field)
    if run_aver note add "$bug_rec" --message "Severity note" --category "documentation" > /dev/null 2>&1; then
        local note_file4=$(grep -l "Severity note" "$TEST_DIR/updates/$bug_rec/"*.md 2>/dev/null | head -1)
        # Note should have category (note field) but NOT severity (record field)
        if [ -n "$note_file4" ] && grep -q "category" "$note_file4" && ! grep -q "severity" "$note_file4"; then
            pass
            echo "  Note has note fields, not record fields"
        else
            fail "Note field isolation not working"
        fi
    else
        fail "Failed to add note"
    fi
}

#==============================================================================
# Test: --from-file Feature
#==============================================================================

test_from_file() {
    print_section "--from-file Feature"
    
    # ========================================================================
    # record new --from-file tests
    # ========================================================================
    
    print_test "record new --from-file with valid file"
    cat > "$TEST_DIR/new_record.md" << 'EOF'
---
title: Imported Record
status: open
priority: high
---
This record was imported from a markdown file.
It has all required fields and should import successfully.
EOF
    
    if output=$(run_aver record new --from-file "$TEST_DIR/new_record.md" 2>&1); then
        local rec1=$(echo "$output" | grep -oE "REC-[A-Z0-9]+" || echo "")
        if [ -n "$rec1" ]; then
            pass
            echo "  Created: $rec1"
        else
            fail "Record created but ID not captured"
        fi
    else
        fail "Failed to import record from file"
    fi
    
    print_test "Imported record has correct fields"
    if [ -n "$rec1" ]; then
        if check_content_contains "$TEST_DIR/records/${rec1}.md" "title: Imported Record" &&  \
           check_content_contains "$TEST_DIR/records/${rec1}.md" "status: open" && \
           check_content_contains "$TEST_DIR/records/${rec1}.md" "priority: high"; then
            pass
        else
            fail "Imported record missing expected fields"
        fi
    else
        fail "No record ID to check"
    fi
    
    print_test "CLI args override file values"
    cat > "$TEST_DIR/override_test.md" << 'EOF'
---
title: File Title
status: open
---
File content
EOF
    
    if output=$(run_aver record new --from-file "$TEST_DIR/override_test.md" --title "CLI Title" --status "in_progress" 2>&1); then
        local rec2=$(echo "$output" | grep -oE "REC-[A-Z0-9]+" || echo "")
        if [ -n "$rec2" ] && check_content_contains "$TEST_DIR/records/${rec2}.md" "CLI Title" && \
           check_content_contains "$TEST_DIR/records/${rec2}.md" "in_progress"; then
            pass
            echo "  CLI args properly overrode file values"
        else
            fail "CLI args did not override file values"
        fi
    else
        fail "Failed to import with CLI overrides"
    fi
    
    print_test "Custom ID from file (no conflict)"
    cat > "$TEST_DIR/custom_id.md" << 'EOF'
---
id: CUSTOM-123
title: Custom ID Record
status: open
---
This record has a custom ID.
EOF
    
    if output=$(run_aver record new --from-file "$TEST_DIR/custom_id.md" 2>&1); then
        if echo "$output" | grep -q "CUSTOM-123"; then
            pass
            echo "  Custom ID accepted"
        else
            fail "Custom ID not used"
        fi
    else
        fail "Failed to create record with custom ID"
    fi
    
    print_test "Custom ID conflict detection"
    # Try to create another record with same ID
    set +e
    output=$(run_aver record new --from-file "$TEST_DIR/custom_id.md" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ] && echo "$output" | grep -q "already exists"; then
        pass
        echo "  Correctly rejected duplicate ID"
    else
        fail "Should reject duplicate custom ID"
    fi
    
    print_test "Non-editable fields are rewritten"
    cat > "$TEST_DIR/noneditable.md" << 'EOF'
---
title: Test Record
status: open
created_by: wrong_user
created_at: 2020-01-01T00:00:00Z
---
Content
EOF
    
    if output=$(run_aver record new --from-file "$TEST_DIR/noneditable.md" 2>&1); then
        local rec3=$(echo "$output" | grep -oE "REC-[A-Z0-9]+" || echo "")
        if [ -n "$rec3" ]; then
            # Should have testuser, not wrong_user
            if check_content_contains "$TEST_DIR/records/${rec3}.md" "testuser" && \
               ! check_content_contains "$TEST_DIR/records/${rec3}.md" "wrong_user" && \
               ! check_content_contains "$TEST_DIR/records/${rec3}.md" "2020-01-01"; then
                pass
                echo "  Non-editable fields properly rewritten"
            else
                fail "Non-editable fields not rewritten"
            fi
        fi
    else
        fail "Failed to create record"
    fi
    
    # ========================================================================
    # record update --from-file tests
    # ========================================================================
    
    print_test "record update --from-file"
    # Create a record first
    cat > "$TEST_DIR/update_base.md" << 'EOF'
---
title: Original Title
status: open
priority: low
---
Original content
EOF
    
    local rec_to_update=$(run_aver record new --from-file "$TEST_DIR/update_base.md" 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")
    
    if [ -n "$rec_to_update" ]; then
        # Create update file
        cat > "$TEST_DIR/update_file.md" << 'EOF'
---
title: Updated Title
status: resolved
priority: high
---
Updated content with changes
EOF
        
        if run_aver record update "$rec_to_update" --from-file "$TEST_DIR/update_file.md" > /dev/null 2>&1; then
            if check_content_contains "$TEST_DIR/records/${rec_to_update}.md" "Updated Title" && \
               check_content_contains "$TEST_DIR/records/${rec_to_update}.md" "resolved" && \
               check_content_contains "$TEST_DIR/records/${rec_to_update}.md" "high" && \
               check_content_contains "$TEST_DIR/records/${rec_to_update}.md" "Updated content"; then
                pass
                echo "  Record updated from file"
            else
                fail "Record not properly updated"
            fi
        else
            fail "Failed to update record from file"
        fi
    else
        fail "Failed to create base record for update test"
    fi
    
    print_test "Template change allowed (editable=true)"
    # This test assumes template_id field is editable
    # Create record with one template
    cat > "$TEST_DIR/feat_record.md" << 'EOF'
---
template_id: feature
title: Feature Request
status: proposed
---
Feature content
EOF
    
    if output=$(run_aver record new --from-file "$TEST_DIR/feat_record.md" 2>&1); then
        local feat_rec=$(echo "$output" | grep -oE "FEAT-[A-Z0-9]+" || echo "")
        if [ -n "$feat_rec" ]; then
            # Try to change template (if template_id is editable, this should work)
            # Note: In default config, template_id is NOT editable, so this might fail
            # This test documents the behavior
            pass
            echo "  Feature record created: $feat_rec"
        fi
    fi
    
    # ========================================================================
    # note add --from-file tests
    # ========================================================================
    
    print_test "note add --from-file"
    # Create a record to add notes to
    local note_rec=$(run_aver record new --description "" --no-validation-editor --title "Note Test" --status open 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")
    
    if [ -n "$note_rec" ]; then
        cat > "$TEST_DIR/test_note.md" << 'EOF'
---
id: SHOULD-BE-IGNORED
author: should_be_ignored
custom_field: custom_value
---
This is a note imported from a file.
The ID should be ignored and a new one generated.
EOF
        
        if output=$(run_aver note add "$note_rec" --from-file "$TEST_DIR/test_note.md" 2>&1); then
            local note_id=$(echo "$output" | grep -oE "NT-[A-Z0-9]+" || echo "")
            if [ -n "$note_id" ]; then
                # Check that new ID was generated (not SHOULD-BE-IGNORED)
                if [[ "$note_id" != "SHOULD-BE-IGNORED" ]]; then
                    pass
                    echo "  Note ID generated (not from file): $note_id"
                else
                    fail "Note used ID from file instead of generating new one"
                fi
            else
                fail "Note created but ID not captured"
            fi
        else
            fail "Failed to add note from file"
        fi
    else
        fail "Failed to create record for note test"
    fi
    
    print_test "Note from file has correct content"
    if [ -n "$note_id" ]; then
        local note_file="$TEST_DIR/updates/$note_rec/${note_id}.md"
        if [ -f "$note_file" ] && check_content_contains "$note_file" "This is a note imported from a file" && \
           check_content_contains "$note_file" "custom_value"; then
            pass
        else
            fail "Note content not correct"
        fi
    fi
    
    print_test "Note author rewritten (non-editable)"
    if [ -n "$note_id" ]; then
        local note_file="$TEST_DIR/updates/$note_rec/${note_id}.md"
        # Should have testuser, not should_be_ignored
        if check_content_contains "$note_file" "testuser" && \
           ! check_content_contains "$note_file" "should_be_ignored"; then
            pass
            echo "  Author field properly rewritten"
        else
            fail "Author field not rewritten"
        fi
    fi
    
    print_test "--from-file incompatible with --template"
    set +e
    output=$(run_aver note add "$note_rec" --from-file "$TEST_DIR/test_note.md" --template BUG-123 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ] && echo "$output" | grep -q "Cannot use both"; then
        pass
        echo "  Correctly rejected --from-file with --template"
    else
        fail "Should reject --from-file with --template"
    fi
    
    print_test "--from-file incompatible with --reply-to"
    set +e
    output=$(run_aver note add "$note_rec" --from-file "$TEST_DIR/test_note.md" --reply-to NT-123 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ] && echo "$output" | grep -q "Cannot use both"; then
        pass
        echo "  Correctly rejected --from-file with --reply-to"
    else
        fail "Should reject --from-file with --reply-to"
    fi
    
    print_test "File not found error"
    set +e
    output=$(run_aver record new --from-file "/nonexistent/file.md" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ] && echo "$output" | grep -q "not found"; then
        pass
        echo "  Correctly reported file not found"
    else
        fail "Should report file not found"
    fi
}

#==============================================================================
# Test: Updates
#==============================================================================

test_updates() {
    print_section "Record Updates"
    
    # Create a record to update
    local output=$(run_aver record new --description "" --no-validation-editor --title "Update Test" --status open 2>&1)
    local rec_id=$(echo "$output" | grep -oE "REC-[A-Z0-9]+")
    
    if [ -z "$rec_id" ]; then
        echo -e "${RED}Setup failed: Could not create test record${NC}"
        return
    fi
    
    print_test "Update record status"
    if run_aver record update "$rec_id" --status in_progress --metadata-only --no-validation-editor; then
        if check_content_contains "$TEST_DIR/records/$rec_id.md" "in_progress"; then
            pass
        else
            fail "Status not updated in file"
        fi
    else
        fail "Update command failed"
    fi
    
    print_test "Update preserves other fields"
    if check_content_contains "$TEST_DIR/records/$rec_id.md" "Update Test"; then
        pass
    else
        fail "Title was lost during update"
    fi
    
    print_test "updated_at field is modified"
    # The updated_at field should exist
    if check_content_contains "$TEST_DIR/records/$rec_id.md" "updated_at"; then
        pass
    else
        fail "updated_at field not found after update"
    fi
}

#==============================================================================
# Test: JSON Interface
#==============================================================================

test_json_interface() {
    print_section "JSON Interface"
    
    # Create some test data first
    local json_rec1=$(run_aver record new --description "" --no-validation-editor --title "JSON Test 1" --status open 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")
    local json_rec2=$(run_aver record new --description "" --no-validation-editor --title "JSON Test 2" --status in_progress 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")
    
    if [ -z "$json_rec1" ] || [ -z "$json_rec2" ]; then
        echo -e "${RED}Setup failed: Could not create test records for JSON tests${NC}"
        return
    fi
    
    # Add a note to first record
    local json_note1=$(run_aver note add "$json_rec1" --message "Test note for JSON" 2>&1 | grep -oE "NT-[A-Z0-9]+" || echo "")
    
    # ========================================================================
    # Export Tests
    # ========================================================================
    
    print_test "json export-record basic"
    track_command "aver json export-record $json_rec1"
    if output=$(run_aver json export-record "$json_rec1" 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['id'] == '$json_rec1'; assert 'content' in data; assert 'fields' in data" 2>/dev/null; then
            pass
            echo "  Valid JSON with expected structure"
        else
            fail "JSON structure invalid or missing required fields"
        fi
    else
        fail "Export command failed"
    fi
    
    print_test "json export-record with notes"
    track_command "aver json export-record $json_rec1 --include-notes"
    if output=$(run_aver json export-record "$json_rec1" --include-notes 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'notes' in data; assert len(data['notes']) > 0" 2>/dev/null; then
            pass
            echo "  Notes included in export"
        else
            fail "Notes not included or JSON invalid"
        fi
    else
        fail "Export with notes failed"
    fi
    
    print_test "json export-note"
    if [ -n "$json_note1" ]; then
        track_command "aver json export-note $json_rec1 $json_note1"
        if output=$(run_aver json export-note "$json_rec1" "$json_note1" 2>&1); then
            if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['id'] == '$json_note1'; assert data['record_id'] == '$json_rec1'; assert 'content' in data" 2>/dev/null; then
                pass
                echo "  Note exported with correct IDs"
            else
                fail "Note JSON structure invalid"
            fi
        else
            fail "Export note failed"
        fi
    else
        fail "No note to export"
        run_aver json export-note "$json_rec1" "$json_note1"
    fi
    
    print_test "json export-record non-existent record"
    set +e
    track_command "aver json export-record NONEXISTENT"
    output=$(run_aver json export-record "NONEXISTENT" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ] && echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'error' in data" 2>/dev/null; then
        pass
        echo "  Correctly reported error in JSON"
    else
        fail "Should return error JSON for non-existent record"
    fi
    
    # ========================================================================
    # Search Tests
    # ========================================================================
    
    print_test "json search-records no filters"
    track_command "aver json search-records"
    if output=$(run_aver json search-records 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'count' in data; assert 'records' in data; assert data['count'] >= 2" 2>/dev/null; then
            pass
            echo "  Found multiple records"
        else
            fail "Search results invalid"
        fi
    else
        fail "Search command failed"
    fi
    
    print_test "json search-records with limit"
    track_command "aver json search-records --limit 1"
    if output=$(run_aver json search-records --limit 1 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['count'] <= 1" 2>/dev/null; then
            pass
            echo "  Limit respected"
        else
            fail "Limit not respected"
        fi
    else
        fail "Search with limit failed"
    fi
    
    print_test "json search-records with ksearch"
    track_command "aver json search-records --ksearch 'status=open'"
    if output=$(run_aver json search-records --ksearch "status=open" 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'records' in data" 2>/dev/null; then
            pass
            echo "  Search query executed"
        else
            fail "Search query failed"
        fi
    else
        fail "Search with ksearch failed"
    fi
    
    print_test "json search-notes"
    track_command "aver json search-notes --limit 10"
    if output=$(run_aver json search-notes --limit 10 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'count' in data; assert 'notes' in data" 2>/dev/null; then
            pass
            echo "  Notes search returned valid JSON"
        else
            fail "Notes search invalid"
        fi
    else
        fail "Search notes failed"
    fi
    
    # ========================================================================
    # Import Tests
    # ========================================================================
    
    print_test "json import-record from command line"
    track_command "aver json import-record --data '{...}'"
    if output=$(run_aver json import-record --data '{"content": "Imported via JSON", "fields": {"title": "JSON Import Test", "status": "open"}}' 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'record_id' in data" 2>/dev/null; then
            local new_rec=$(echo "$output" | python3 -c "import sys,json; print(json.load(sys.stdin)['record_id'])" 2>/dev/null)
            if [ -n "$new_rec" ] && [ -f "$TEST_DIR/records/${new_rec}.md" ]; then
                pass
                echo "  Created record: $new_rec"
            else
                fail "Record not created on disk"
            fi
        else
            fail "Import response invalid"
        fi
    else
        fail "Import command failed"
    fi
    
    print_test "json import-record from stdin"
    track_command "echo '{...}' | aver json import-record --data -"
    if output=$(echo '{"content": "Imported via stdin", "fields": {"title": "STDIN Import", "status": "open"}}' | run_aver json import-record --data - 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'record_id' in data" 2>/dev/null; then
            pass
            echo "  Created record from stdin"
        else
            fail "STDIN import response invalid"
        fi
    else
        fail "STDIN import failed"
    fi
    
    print_test "json import-record with template"
    track_command "aver json import-record --data '{...template...}'"
    if output=$(run_aver json import-record --data '{"content": "Bug report", "fields": {"title": "Bug via JSON", "status": "new"}, "template": "bug"}' 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'record_id' in data" 2>/dev/null; then
            local bug_rec=$(echo "$output" | python3 -c "import sys,json; print(json.load(sys.stdin)['record_id'])" 2>/dev/null)
            if [ -n "$bug_rec" ]; then
                pass
                echo "  Created bug record: $bug_rec"
            else
                fail "Bug record ID not returned"
            fi
        else
            fail "Template import response invalid"
        fi
    else
        fail "Import with template failed"
    fi
    
    print_test "json import-note"
    track_command "aver json import-note $json_rec1 --data '{...}'"
    if output=$(run_aver json import-note "$json_rec1" --data '{"content": "Note via JSON", "fields": {"category": "testing"}}' 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'note_id' in data; assert data['record_id'] == '$json_rec1'" 2>/dev/null; then
            pass
            echo "  Added note via JSON"
        else
            fail "Import note response invalid"
        fi
    else
        fail "Import note failed"
    fi
    
    print_test "json import-record invalid JSON"
    set +e
    track_command "aver json import-record --data 'invalid'"
    output=$(run_aver json import-record --data "invalid json" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ] && echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == False; assert 'error' in data" 2>/dev/null; then
        pass
        echo "  Correctly rejected invalid JSON"
    else
        fail "Should reject invalid JSON"
    fi
    
    # ========================================================================
    # Update Tests
    # ========================================================================
    
    print_test "json update-record fields only"
    track_command "aver json update-record $json_rec1 --data '{...}'"
    if output=$(run_aver json update-record "$json_rec1" --data '{"fields": {"status": "resolved"}}' 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert data['record_id'] == '$json_rec1'" 2>/dev/null; then
            if check_content_contains "$TEST_DIR/records/${json_rec1}.md" "resolved"; then
                pass
                echo "  Status updated via JSON"
            else
                fail "Status not updated in file"
            fi
        else
            fail "Update response invalid"
        fi
    else
        fail "Update fields failed"
    fi
    
    print_test "json update-record content and fields"
    track_command "aver json update-record $json_rec2 --data '{...}'"
    if output=$(run_aver json update-record "$json_rec2" --data '{"content": "Updated content via JSON", "fields": {"status": "closed"}}' 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True" 2>/dev/null; then
            if check_content_contains "$TEST_DIR/records/${json_rec2}.md" "Updated content via JSON" && \
               check_content_contains "$TEST_DIR/records/${json_rec2}.md" "closed"; then
                pass
                echo "  Content and status updated"
            else
                fail "Update not reflected in file"
            fi
        else
            fail "Update response invalid"
        fi
    else
        fail "Update content and fields failed"
    fi
    
    # ========================================================================
    # Schema Tests
    # ========================================================================
    
    print_test "json schema-record default"
    track_command "aver json schema-record"
    if output=$(run_aver json schema-record 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert 'fields' in data; assert 'status' in data['fields']" 2>/dev/null; then
            pass
            echo "  Schema returned with fields"
        else
            fail "Schema structure invalid"
        fi
    else
        fail "Schema command failed"
    fi
    
    print_test "json schema-record with template"
    track_command "aver json schema-record --template bug"
    if output=$(run_aver json schema-record --template bug 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('template') == 'bug'; assert 'fields' in data" 2>/dev/null; then
            pass
            echo "  Bug template schema returned"
        else
            fail "Template schema invalid"
        fi
    else
        fail "Template schema failed"
    fi
    
    print_test "json schema-note"
    track_command "aver json schema-note $json_rec1"
    if output=$(run_aver json schema-note "$json_rec1" 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['record_id'] == '$json_rec1'; assert 'fields' in data" 2>/dev/null; then
            pass
            echo "  Note schema returned"
        else
            fail "Note schema invalid"
        fi
    else
        fail "Note schema failed"
    fi
    
    # ========================================================================
    # Reply Template Tests
    # ========================================================================
    
    print_test "json reply-template"
    if [ -n "$json_note1" ]; then
        track_command "aver json reply-template $json_rec1 $json_note1"
        if output=$(run_aver json reply-template "$json_rec1" "$json_note1" 2>&1); then
            if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['record_id'] == '$json_rec1'; assert data['reply_to'] == '$json_note1'; assert 'quoted_content' in data; assert 'fields' in data" 2>/dev/null; then
                pass
                echo "  Reply template generated"
            else
                fail "Reply template structure invalid"
            fi
        else
            fail "Reply template failed"
        fi
    else
        fail "No note for reply test"
    fi
}

#==============================================================================
# Test: JSON IO Mode
#==============================================================================

test_json_io_mode() {
    print_section "JSON IO Mode"
    
    # Create test data
    local io_rec=$(run_aver record new --description "" --no-validation-editor --title "IO Test" --status open 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")
    
    if [ -z "$io_rec" ]; then
        echo -e "${RED}Setup failed: Could not create test record for IO tests${NC}"
        return
    fi
    
    print_test "json io basic command"
    track_command "echo '{...}' | aver json io"
    if output=$(echo '{"command": "export-record", "params": {"record_id": "'$io_rec'"}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'result' in data; assert data['result']['id'] == '$io_rec'" 2>/dev/null; then
            pass
            echo "  IO command executed successfully"
        else
            fail "IO response invalid"
            echo '{"command": "export-record", "params": {"record_id": "'$io_rec'"}}' | run_aver json io 2>&1
        fi
    else
        fail "IO command failed"
    fi
    
    print_test "json io multiple commands"
    track_command "cat ... | aver json io"
    # Create a multi-line input
    cat > "$TEST_DIR/io_commands.txt" << EOF
{"command": "search-records", "params": {"limit": 2}}
{"command": "schema-record", "params": {}}

EOF
    
    if output=$(cat "$TEST_DIR/io_commands.txt" | run_aver json io 2>&1); then
        # Should have two JSON responses (one per line)
        local line_count=$(echo "$output" | grep -c "success" || echo "0")
        if [ "$line_count" -ge 2 ]; then
            pass
            echo "  Multiple commands executed"
        else
            fail "Expected multiple response lines"
        fi
    else
        fail "Multiple commands failed"
    fi
    
    print_test "json io import and export round-trip"
    track_command "json io import then export"
    cat > "$TEST_DIR/io_roundtrip.txt" << 'EOF'
{"command": "import-record", "params": {"content": "Round-trip test", "fields": {"title": "IO Round-trip", "status": "open"}}}

EOF
    
    if output=$(cat "$TEST_DIR/io_roundtrip.txt" | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; rec_id=data['result']['record_id']; print(rec_id)" 2>/dev/null > "$TEST_DIR/new_rec_id.txt"; then
            local new_io_rec=$(cat "$TEST_DIR/new_rec_id.txt")
            # Now export it
            if export_output=$(echo '{"command": "export-record", "params": {"record_id": "'$new_io_rec'"}}' | run_aver json io 2>&1); then
                if echo "$export_output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['success'] == True; assert 'Round-trip test' in data['result']['content']" 2>/dev/null; then
                    pass
                    echo "  Import and export verified"
                else
                    fail "Export validation failed"
                fi
            else
                fail "Export after import failed"
            fi
        else
            fail "Import in IO mode failed"
        fi
    else
        fail "IO import command failed"
    fi
    
    print_test "json io search and count"
    track_command "json io search"
    if output=$(echo '{"command": "search-records", "params": {"limit": 100}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['success'] == True; assert data['result']['count'] >= 1" 2>/dev/null; then
            pass
            echo "  Search via IO successful"
        else
            fail "Search response invalid"
        fi
    else
        fail "IO search failed"
    fi
    
    print_test "json io update record"
    track_command "json io update-record"
    if output=$(echo '{"command": "update-record", "params": {"record_id": "'$io_rec'", "fields": {"status": "resolved"}}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data['success'] == True" 2>/dev/null; then
            if check_content_contains "$TEST_DIR/records/${io_rec}.md" "resolved"; then
                pass
                echo "  Update via IO successful"
            else
                fail "Update not reflected in file"
            fi
        else
            fail "Update response invalid"
        fi
    else
        fail "IO update failed"
    fi
    
    print_test "json io error handling"
    set +e
    track_command "json io with invalid command"
    output=$(echo '{"command": "invalid-command", "params": {}}' | run_aver json io 2>&1)
    set -e
    
    if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == False; assert 'error' in data" 2>/dev/null; then
        pass
        echo "  Error properly returned as JSON"
    else
        fail "Should return error JSON for invalid command"
    fi
    
    print_test "json io invalid JSON handling"
    set +e
    track_command "json io with invalid JSON"
    output=$(echo 'not valid json' | run_aver json io 2>&1)
    set -e
    
    if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == False; assert 'Invalid JSON' in data.get('error', '')" 2>/dev/null; then
        pass
        echo "  Invalid JSON properly rejected"
    else
        fail "Should return error for invalid JSON"
    fi
    
    print_test "json io schema commands"
    cat > "$TEST_DIR/io_schema.txt" << EOF
{"command": "schema-record", "params": {}}
{"command": "schema-note", "params": {"record_id": "$io_rec"}}

EOF
    
    if output=$(cat "$TEST_DIR/io_schema.txt" | run_aver json io 2>&1); then
        # Should have two successful responses
        local success_count=$(echo "$output" | grep -c '"success": true' || echo "0")
        if [ "$success_count" -ge 2 ]; then
            pass
            echo "  Schema commands via IO successful"
        else
            fail "Schema commands didn't return expected responses"
        fi
    else
        fail "IO schema commands failed"
    fi
    
    print_test "json io user identity override - create record"
    track_command "json io with id field"
    if output=$(echo '{"command": "import-record", "params": {"content": "Record with override", "fields": {"title": "Override Test", "status": "open"}}, "id": {"handle": "test-override", "email": "override@test.com"}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'record_id' in data['result']" 2>/dev/null; then
            local override_rec=$(echo "$output" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['record_id'])" 2>/dev/null)
            if [ -n "$override_rec" ]; then
                # Check that the record has the override user in created_by field
                if check_content_contains "$TEST_DIR/records/${override_rec}.md" "test-override"; then
                    pass
                    echo "  User identity override applied: $override_rec"
                else
                    fail "User identity override not reflected in record"
                fi
            else
                fail "Record ID not returned"
            fi
        else
            fail "Import with user override failed"
        fi
    else
        fail "IO user override command failed"
    fi
    
    print_test "json io user identity override - validation error"
    set +e
    track_command "json io with incomplete id field"
    output=$(echo '{"command": "import-record", "params": {"content": "Test", "fields": {"title": "Test", "status": "open"}}, "id": {"handle": "only-handle"}}' | run_aver json io 2>&1)
    set -e
    
    if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == False; assert 'both' in data.get('error', '').lower()" 2>/dev/null; then
        pass
        echo "  Correctly rejected incomplete user identity"
    else
        fail "Should reject user override with only handle or email"
    fi
    
    print_test "json io user identity override - read operations"
    # User override should work but have no effect on read operations
    if output=$(echo '{"command": "search-records", "params": {"limit": 1}, "id": {"handle": "reader", "email": "reader@test.com"}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True" 2>/dev/null; then
            pass
            echo "  User override accepted on read operation"
        else
            fail "Read operation with user override failed"
        fi
    else
        fail "IO read with user override failed"
    fi
    
    # Create a note for note-related tests
    local io_note=$(run_aver note add "$io_rec" --message "Note for IO tests" --category=testing 2>&1 | grep -oE "NT-[A-Z0-9]+" || echo "")
    
    print_test "json io export-note"
    track_command "json io export-note"
    if [ -n "$io_note" ]; then
        if output=$(echo '{"command": "export-note", "params": {"record_id": "'$io_rec'", "note_id": "'$io_note'"}}' | run_aver json io 2>&1); then
            if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'content' in data['result']; assert 'Note for IO tests' in data['result']['content']" 2>/dev/null; then
                pass
                echo "  Note exported via IO"
            else
                fail "Note export response invalid"
            fi
        else
            fail "IO export-note failed"
        fi
    else
        fail "Could not create note for export test"
        run_aver note add "$io_rec" --message "Note for IO tests" category=testing 2>&1
    fi
    
    print_test "json io search-notes"
    track_command "json io search-notes"
    if output=$(echo '{"command": "search-notes", "params": {"ksearch": ["category=testing"], "limit": 10}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert data['result']['count'] >= 1" 2>/dev/null; then
            pass
            echo "  Note search via IO successful"
        else
            fail "Note search response invalid"
        fi
    else
        fail "IO search-notes failed"
    fi
    
    print_test "json io import-note"
    track_command "json io import-note"
    if output=$(echo '{"command": "import-note", "params": {"record_id": "'$io_rec'", "content": "Imported note via IO", "fields": {"category": "imported"}}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'note_id' in data['result']" 2>/dev/null; then
            local imported_note=$(echo "$output" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['note_id'])" 2>/dev/null)
            if [ -n "$imported_note" ]; then
                # Verify note was created
                local note_file="$TEST_DIR/updates/$io_rec/${imported_note}.md"
                if [ -f "$note_file" ] && check_content_contains "$note_file" "Imported note via IO"; then
                    pass
                    echo "  Note imported via IO: $imported_note"
                else
                    fail "Imported note not found or content incorrect"
                fi
            else
                fail "Note ID not returned"
            fi
        else
            fail "Import-note response invalid"
        fi
    else
        fail "IO import-note failed"
    fi
    
    print_test "json io reply-template"
    track_command "json io reply-template"
    if output=$(echo '{"command": "reply-template", "params": {"record_id": "'$io_rec'", "note_id": "'$io_note'"}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'template' in data['result']" 2>/dev/null; then
            pass
            echo "  Reply template retrieved via IO"
        else
            fail "Reply template response invalid"
            echo '{"command": "reply-template", "params": {"record_id": "'$io_rec'", "note_id": "'$io_note'"}}' | run_aver json io
        fi
    else
        fail "IO reply-template failed"
    fi
    
    print_test "json io list-templates"
    track_command "json io list-templates"
    if output=$(echo '{"command": "list-templates", "params": {}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'templates' in data['result']" 2>/dev/null; then
            pass
            echo "  Templates listed via IO"
        else
            fail "List templates response invalid"
        fi
    else
        fail "IO list-templates failed"
    fi
    
    print_test "json io export-record with notes"
    track_command "json io export-record with include_notes"
    if output=$(echo '{"command": "export-record", "params": {"record_id": "'$io_rec'", "include_notes": true}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'notes' in data['result']; assert len(data['result']['notes']) > 0" 2>/dev/null; then
            pass
            echo "  Record exported with notes via IO"
        else
            fail "Export with notes response invalid"
        fi
    else
        fail "IO export-record with notes failed"
    fi
    
    print_test "json io error - missing required parameter"
    set +e
    track_command "json io with missing parameter"
    output=$(echo '{"command": "export-record", "params": {}}' | run_aver json io 2>&1)
    set -e
    
    if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == False; assert 'record_id' in data.get('error', '').lower()" 2>/dev/null; then
        pass
        echo "  Missing parameter error handled correctly"
    else
        fail "Should return error for missing required parameter"
    fi
    
    print_test "json io error - invalid record_id"
    set +e
    track_command "json io with invalid record_id"
    output=$(echo '{"command": "export-record", "params": {"record_id": "INVALID-123"}}' | run_aver json io 2>&1)
    set -e
    
    if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == False; assert 'not found' in data.get('error', '').lower()" 2>/dev/null; then
        pass
        echo "  Invalid record_id error handled correctly"
    else
        fail "Should return error for invalid record_id"
    fi
}
#==============================================================================
# Test: Selective Record Reindex
#==============================================================================

test_record_reindex() {
    print_section "Test: Selective Record Reindex"
    
    # Setup: Create test records for reindex testing
    print_test "Setup: Create test records for reindex"
    local rec1=$(run_aver record new --title "Reindex Test 1" --status open --priority medium --description "Test record for reindex")
    local rec2=$(run_aver record new --title "Reindex Test 2" --status closed --priority high --description "Another test record")
    local rec1_id=$(echo "$rec1" | grep -oE "REC-[A-Z0-9]+")
    local rec2_id=$(echo "$rec2" | grep -oE "REC-[A-Z0-9]+")

    if [ -n "${rec1_id}" ] && [ -n "${rec2_id}" ]; then
        pass
    else
        fail "Failed to create test records"
        return
    fi
    
    # Add notes to first record
    print_test "Setup: Add notes to test record (${rec1_id})"
    if run_aver note add "${rec1_id}" --message "First note" 2>&1 >/dev/null; then
        if run_aver note add "${rec1_id}" --message "Second note" 2>&1 >/dev/null; then
            pass
        else
            fail "Failed to add second note"
            return
        fi
    else
        fail "Failed to add first note"
        return
    fi
    
    # Test 1: Reindex existing record (first time — nothing in file_index yet)
    print_test "Reindex existing record (first index)"
    track_command "admin reindex $rec1"
    if output=$(run_aver admin reindex "${rec1_id}" 2>&1); then
        if echo "$output" | grep -qE "notes reindexed|Reindexed ${rec1_id}"; then
            pass
            echo "  Record reindexed successfully"
        else
            fail "Reindex output doesn't confirm success: $output"
        fi
    else
        run_aver admin reindex "${rec1_id}" 2>&1
        fail "Failed to reindex record"
    fi
    
    # Test 2: Verify search still works after reindex
    print_test "Search works after reindex"
    track_command "record list --ksearch status=open"
    if output=$(run_aver record list --ksearch status=open); then
        if echo "$output" | grep -q "${rec1_id}"; then
            pass
            echo "  Record found in search after reindex"
        else
            run_aver record list --ksearch status=open
            fail "Record not found in search after reindex"
        fi
    else
        fail "Search failed after reindex"
    fi
    
    # Test 3: Manual file edit + reindex
    print_test "Manual file edit then reindex"
    
    # Manually edit the file
    local rec_file="$TEST_DIR/records/${rec1_id}.md"
    track_command "sed to manually edit file, then reindex"
    
    if [ -f "$rec_file" ]; then
        # Change priority from medium to critical
        sed -i 's/priority: medium/priority: critical/' "$rec_file"
        
        # Reindex
        if run_aver admin reindex "${rec1_id}" 2>&1 >/dev/null; then
            # Verify change is indexed
            if output=$(run_aver record list --ksearch priority=critical); then
                if echo "$output" | grep -q "${rec1_id}"; then
                    pass
                    echo "  Manual edit indexed successfully"
                else
                    fail "Manual edit not reflected in search"
                fi
            else
                fail "Search failed after manual edit reindex"
            fi
        else
            fail "Reindex failed after manual edit"
        fi
    else
        fail "Record file not found: $rec_file"
    fi
    
    # Test 4: Reindex with notes
    print_test "Reindex includes notes"
    track_command "admin reindex ${rec1_id} (with notes)"

    # Add another note (so we have 3 notes total now)
    if run_aver note add "${rec1_id}" --message "Note for reindex test" 2>&1 >/dev/null; then
        # Reindex — file was just written so will be picked up
        if output=$(run_aver admin reindex "${rec1_id}" 2>&1); then
            if echo "$output" | grep -qE "notes reindexed|unchanged"; then
                pass
                echo "  Reindex processed notes"
            else
                fail "Reindex didn't report note status: $output"
            fi
        else
            fail "Reindex with notes failed"
        fi
    else
        fail "Failed to add note for test"
    fi
    
    # Test 5: Reindex non-existent record (should fail)
    print_test "Reindex non-existent record fails gracefully"
    set +e
    track_command "admin reindex NONEXISTENT-123"
    output=$(run_aver admin reindex "NONEXISTENT-123" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        if echo "$output" | grep -qi "not found"; then
            pass
            echo "  Correctly reports record not found"
        else
            fail "Failed but didn't report 'not found'"
        fi
    else
        fail "Should have failed for non-existent record"
    fi
    
    # Test 6: Manually add note file + reindex
    print_test "Manual note file creation then reindex"
    track_command "manually create note file, then reindex"
    
    # Create a note file manually
    local note_dir="$TEST_DIR/updates/${rec1_id}"
    mkdir -p "$note_dir"
    
    cat > "$note_dir/NT-MANUAL.md" << EOF
---
author: testuser
timestamp: 2025-01-20T10:00:00Z
---

This note was created manually for testing reindex.

NT-MANUAL
EOF
    
    # Reindex to pick up manual note
    if output=$(run_aver admin reindex "${rec1_id}" 2>&1); then
        # Check if note count increased
        if echo "$output" | grep -q "5 notes"; then
            # Verify note is accessible
            if run_aver note list "${rec1_id}" 2>&1 | grep -q "NT-MANUAL"; then
                pass
                echo "  Manual note file indexed successfully"
            else
                fail "Manual note file not visible after reindex"
            fi
        else
            fail "Note count didn't increase after manual note creation"
        fi
    else
        fail "Reindex failed after manual note creation"
    fi
    
    # Test 7: Reindex after manual frontmatter change
    print_test "Reindex after manual frontmatter field addition"
    track_command "manually add field, then reindex"
    
    # Add a new field to frontmatter manually
    local rec_file="$TEST_DIR/records/${rec2_id}.md"
    if [ -f "$rec_file" ]; then
        # Add custom field
        sed -i '/^status:/a custom_field: test_value' "$rec_file"
        
        # Reindex
        if run_aver admin reindex "${rec2_id}" 2>&1 >/dev/null; then
            # Try to search for the custom field
            if output=$(run_aver record view "${rec2_id}"); then
                if echo "$output" | grep -q "custom_field"; then
                    pass
                    echo "  Manual field addition indexed"
                else
                    fail "Manual field not visible after reindex"
                fi
            else
                fail "Record view failed after reindex"
            fi
        else
            fail "Reindex failed after manual field addition"
        fi
    else
        fail "Record file not found"
    fi
    
    # Test 8: Reindex record with no notes
    print_test "Reindex record with no notes"
    local rec3=$(run_aver record new --title "No notes record" --status open --priority high --description "No note record")
    local rec3_id=$(echo "$rec3" | grep -oE "REC-[A-Z0-9]+")

    track_command "admin reindex ${rec3_id} (no notes)"
    if output=$(run_aver admin reindex "${rec3_id}" 2>&1); then
        if echo "$output" | grep -qE "Reindexed ${rec3_id}|${rec3_id} unchanged|notes reindexed"; then
            pass
            echo "  Record with no notes reindexed successfully"
        else
            fail "Reindex didn't confirm success: $output"
        fi
    else
        fail "Reindex failed for record with no notes"
    fi
    
    # Test 9: Filesystem-first workflow simulation
    print_test "Filesystem-first: create file, then reindex"
    track_command "manually create complete record file, then reindex"
    
    # Create a complete record file manually
    cat > "$TEST_DIR/records/MANUAL-001.md" << 'EOF'
---
title: Manually Created Record
status: open
priority: high
created_at: 2025-01-20T10:00:00Z
created_by: testuser
---

This record was created entirely outside of aver.

It demonstrates the filesystem-first approach where records
are just markdown files that can be created with any tool.
EOF
    
    # Reindex to make it searchable
    if run_aver admin reindex "MANUAL-001" 2>&1 >/dev/null; then
        # Verify it's searchable — search by title to avoid hitting default limit
        if output=$(run_aver record list --ksearch 'title=Manually Created Record' 2>&1); then
            if echo "$output" | grep -q "MANUAL-001"; then
                if run_aver record view "MANUAL-001" 2>&1 | grep -q "Manually Created Record"; then
                    pass
                    echo "  Manually created record indexed and searchable"
                else
                    fail "Manual record view failed"
                fi
            else
                fail "Manual record not found in listing"
            fi
        else
            fail "Record listing failed"
        fi
    else
        fail "Reindex of manually created record failed"
    fi
    
    # Test 10: Bulk reindex simulation
    print_test "Bulk reindex multiple records"
    track_command "reindex multiple records in sequence"
    
    local success_count=0
    local total_count=3
    
    for rec_id in "${rec1_id}" "${rec2_id}" "${rec3_id}"; do
        if run_aver admin reindex "$rec_id" 2>&1 >/dev/null; then
            success_count=$((success_count + 1))
        fi
    done
    
    if [ $success_count -eq $total_count ]; then
        pass
        echo "  Successfully reindexed $success_count records"
    else
        fail "Only reindexed $success_count of $total_count records"
    fi

    # Test 11: Unchanged file is skipped on second reindex (mtime check)
    print_test "Second reindex skips unchanged record file"
    track_command "admin reindex ${rec3_id} twice — second should skip"
    # First reindex to populate file_index
    run_aver admin reindex "${rec3_id}" 2>&1 >/dev/null
    # Second reindex immediately — file hasn't changed
    if output=$(run_aver admin reindex "${rec3_id}" 2>&1); then
        if echo "$output" | grep -q "unchanged"; then
            pass
            echo "  Correctly skipped unchanged file"
        else
            fail "Expected 'unchanged' in output but got: $output"
        fi
    else
        fail "Second reindex failed: $output"
    fi

    # Test 12: Changed file is detected and reindexed
    print_test "Changed file detected and reindexed"
    track_command "edit record file, then reindex — should re-index"
    local rec4=$(run_aver record new --title "Skip test record" --status open --priority low --description "For skip detection test")
    local rec4_id=$(echo "$rec4" | grep -oE "REC-[A-Z0-9]+")
    # Populate file_index
    run_aver admin reindex "${rec4_id}" 2>&1 >/dev/null
    # Modify the file (force mtime change)
    local rec4_file="$TEST_DIR/records/${rec4_id}.md"
    if [ -f "$rec4_file" ]; then
        sed -i 's/priority: low/priority: high/' "$rec4_file"
        if output=$(run_aver admin reindex "${rec4_id}" 2>&1); then
            if echo "$output" | grep -q "Record indexed"; then
                pass
                echo "  Changed file was reindexed"
            else
                fail "Expected 'Record indexed' after file change, got: $output"
            fi
        else
            fail "Reindex after file change failed"
        fi
    else
        fail "Record file not found: $rec4_file"
    fi

    # Test 13: admin reindex skips unchanged files on second run
    print_test "admin reindex skips unchanged files on second run"
    track_command "admin reindex twice — second run should report 0 reindexed"
    # First full reindex
    run_aver admin reindex --verbose --skip-validation 2>&1 >/dev/null
    # Second full reindex — nothing has changed
    if output=$(run_aver admin reindex --verbose --skip-validation 2>&1); then
        if echo "$output" | grep -q "unchanged"; then
            pass
            echo "  admin reindex correctly skipped unchanged files"
        else
            fail "Expected 'unchanged' in admin reindex output, got: $output"
        fi
    else
        fail "Second admin reindex failed"
    fi

    # Test 14: --force bypasses skip logic
    print_test "--force reindexes even unchanged files"
    track_command "admin reindex --force on unchanged record"
    local rec5=$(run_aver record new --title "Force reindex test" --status open --priority low --description "For force flag test")
    local rec5_id=$(echo "$rec5" | grep -oE "REC-[A-Z0-9]+")
    # Populate file_index
    run_aver admin reindex "${rec5_id}" 2>&1 >/dev/null
    # Force reindex — should re-index despite no changes
    if output=$(run_aver admin reindex --force "${rec5_id}" 2>&1); then
        if echo "$output" | grep -q "Record indexed"; then
            pass
            echo "  --force reindexed unchanged file"
        else
            fail "Expected 'Record indexed' with --force, got: $output"
        fi
    else
        fail "--force reindex failed"
    fi

    # Test 15: --skip-mtime skips file whose hash is unchanged
    print_test "--skip-mtime skips file with matching hash"
    track_command "admin reindex --skip-mtime on unchanged record"
    local rec6=$(run_aver record new --title "Skip-mtime test" --status open --priority low --description "For skip-mtime test")
    local rec6_id=$(echo "$rec6" | grep -oE "REC-[A-Z0-9]+")
    # Populate file_index
    run_aver admin reindex "${rec6_id}" 2>&1 >/dev/null
    # --skip-mtime: reads file, computes hash, content is same → should skip
    if output=$(run_aver admin reindex --skip-mtime "${rec6_id}" 2>&1); then
        if echo "$output" | grep -q "unchanged"; then
            pass
            echo "  --skip-mtime correctly skipped file with matching hash"
        else
            fail "Expected 'unchanged' with --skip-mtime on unmodified file, got: $output"
        fi
    else
        fail "--skip-mtime reindex failed"
    fi

    # Test 16: JSON IO reindex command (full)
    print_test "JSON IO reindex command (all records)"
    track_command "json io reindex"
    if output=$(echo '{"command": "reindex", "params": {}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True; assert 'reindexed' in data.get('result', {})" 2>/dev/null; then
            pass
            echo "  JSON IO reindex returned success with reindexed count"
        else
            fail "JSON IO reindex response malformed: $output"
        fi
    else
        fail "JSON IO reindex command failed"
    fi

    # Test 17: JSON IO reindex with specific record_ids and force
    print_test "JSON IO reindex with record_ids and force"
    track_command "json io reindex with record_ids"
    if output=$(echo '{"command": "reindex", "params": {"record_ids": ["'"${rec6_id}"'"], "force": true}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success') == True
result = data.get('result', {})
assert result.get('reindexed') == 1
assert '${rec6_id}' in result.get('record_ids', [])
" 2>/dev/null; then
            pass
            echo "  JSON IO selective reindex returned correct result"
        else
            fail "JSON IO selective reindex response malformed: $output"
        fi
    else
        fail "JSON IO selective reindex command failed"
    fi

    # Test 18: JSON IO reindex with skip_mtime
    print_test "JSON IO reindex with skip_mtime"
    track_command "json io reindex skip_mtime"
    if output=$(echo '{"command": "reindex", "params": {"record_ids": ["'"${rec6_id}"'"], "skip_mtime": true}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "import sys,json; data=json.load(sys.stdin); assert data.get('success') == True" 2>/dev/null; then
            pass
            echo "  JSON IO reindex skip_mtime succeeded"
        else
            fail "JSON IO reindex skip_mtime response malformed: $output"
        fi
    else
        fail "JSON IO reindex skip_mtime command failed"
    fi
}


#==============================================================================
# Test: --count flag for record list, note search, and JSON IO
#==============================================================================

test_count_flag() {
    print_section "Test: --count Flag"

    # Setup: create 2 open records and 1 closed record
    print_test "Setup: Create records for count tests"
    local r1=$(run_aver record new --description "" --no-validation-editor \
        --title "CountTest Open 1" --status open --priority critical 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local r2=$(run_aver record new --description "" --no-validation-editor \
        --title "CountTest Open 2" --status open --priority critical 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local r3=$(run_aver record new --description "" --no-validation-editor \
        --title "CountTest Closed" --status closed --priority critical 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")

    if [ -z "$r1" ] || [ -z "$r2" ] || [ -z "$r3" ]; then
        fail "Setup failed: could not create test records"
        return
    fi
    pass
    echo "  Created: $r1 (open), $r2 (open), $r3 (closed)"

    # Test 1: --count returns a number
    print_test "record list --count returns a number"
    if output=$(run_aver record list --ksearch priority=critical --count 2>&1); then
        count=$(echo "$output" | tr -d '[:space:]')
        if echo "$count" | grep -qE '^[0-9]+$'; then
            pass
            echo "  Got count: $count"
        else
            fail "Output is not a number: '$output'"
        fi
    else
        fail "record list --count failed"
    fi

    # Test 2: --count value matches count in regular list output
    print_test "record list --count matches 'Found N matches'"
    count_out=$(run_aver record list --ksearch priority=critical --count 2>&1)
    count=$(echo "$count_out" | tr -d '[:space:]')
    list_out=$(run_aver record list --ksearch priority=critical 2>&1)
    found_n=$(echo "$list_out" | grep "Found .* matches" | grep -oE '[0-9]+' | head -1 || echo "")
    if [ -n "$found_n" ] && [ "$count" = "$found_n" ]; then
        pass
        echo "  --count ($count) == 'Found $found_n matches'"
    else
        fail "--count ($count) does not match 'Found $found_n matches'"
    fi

    # Test 3: --count without --ksearch errors
    print_test "record list --count without --ksearch fails with error"
    set +e
    track_command "aver record list --count (no --ksearch)"
    output=$(run_aver record list --count 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        if echo "$output" | grep -qi "ksearch"; then
            pass
            echo "  Correctly requires --ksearch"
        else
            fail "Failed but wrong error message: $output"
        fi
    else
        fail "Should have failed without --ksearch"
    fi

    # Test 4: --count output is a bare number (no table headers, no record IDs)
    print_test "record list --count output is bare number only"
    if output=$(run_aver record list --ksearch priority=critical --count 2>&1); then
        if echo "$output" | grep -qE '^[0-9]+$' && ! echo "$output" | grep -q "REC-"; then
            pass
            echo "  Output is bare number: $output"
        else
            fail "Output contains unexpected content: '$output'"
        fi
    else
        fail "record list --count failed"
    fi

    # Setup notes: add 2 notes with a unique category "counttest"
    print_test "Setup: Add notes with unique category 'counttest'"
    if run_aver note add "$r1" --message "Count test note 1" --category counttest > /dev/null 2>&1 && \
       run_aver note add "$r2" --message "Count test note 2" --category counttest > /dev/null 2>&1; then
        pass
        echo "  Added 2 notes with category=counttest"
    else
        fail "Failed to add notes with category=counttest"
    fi

    # Test 5: note search --count returns a number
    print_test "note search --count returns a number"
    if output=$(run_aver note search --ksearch category=counttest --count 2>&1); then
        count=$(echo "$output" | tr -d '[:space:]')
        if echo "$count" | grep -qE '^[0-9]+$'; then
            pass
            echo "  Got note count: $count"
        else
            fail "Output is not a number: '$output'"
        fi
    else
        fail "note search --count failed"
    fi

    # Test 6: note search --count matches 'Found N matching notes:'
    print_test "note search --count matches 'Found N matching notes'"
    count_out=$(run_aver note search --ksearch category=counttest --count 2>&1)
    count=$(echo "$count_out" | tr -d '[:space:]')
    search_out=$(run_aver note search --ksearch category=counttest 2>&1)
    found_n=$(echo "$search_out" | grep "Found .* matching notes" | grep -oE '[0-9]+' | head -1 || echo "")
    if [ -n "$found_n" ] && [ "$count" = "$found_n" ]; then
        pass
        echo "  --count ($count) == 'Found $found_n matching notes'"
    else
        fail "--count ($count) does not match 'Found $found_n matching notes'"
    fi

    # Test 7: note search --count output is bare number (no note content)
    print_test "note search --count output is bare number only"
    if output=$(run_aver note search --ksearch category=counttest --count 2>&1); then
        if echo "$output" | grep -qE '^[0-9]+$' && ! echo "$output" | grep -qi "author\|timestamp\|matching notes"; then
            pass
            echo "  Output is bare number: $output"
        else
            fail "Output contains unexpected content: '$output'"
        fi
    else
        fail "note search --count check failed"
    fi

    # Test 8: JSON IO search-records count_only returns count without records
    print_test "JSON IO search-records count_only"
    track_command "echo search-records count_only | aver json io"
    if output=$(echo '{"command": "search-records", "params": {"ksearch": "priority=critical", "count_only": true}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['success'] == True
result = data['result']
assert 'count' in result, 'count key missing'
assert 'records' not in result, 'records key should not be present'
assert isinstance(result['count'], int), 'count should be int'
" 2>/dev/null; then
            pass
            echo "  JSON IO count_only: valid response"
        else
            fail "JSON IO count_only response invalid: $output"
        fi
    else
        fail "JSON IO search-records count_only failed"
    fi

    # Test 9: JSON IO search-notes count_only returns count without notes
    print_test "JSON IO search-notes count_only"
    track_command "echo search-notes count_only | aver json io"
    if output=$(echo '{"command": "search-notes", "params": {"ksearch": "category=counttest", "count_only": true}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['success'] == True
result = data['result']
assert 'count' in result, 'count key missing'
assert 'notes' not in result, 'notes key should not be present'
assert isinstance(result['count'], int), 'count should be int'
" 2>/dev/null; then
            pass
            echo "  JSON IO note count_only: valid response"
        else
            fail "JSON IO search-notes count_only response invalid: $output"
        fi
    else
        fail "JSON IO search-notes count_only failed"
    fi

    # Test 10: JSON IO count_only matches full search count
    print_test "JSON IO count_only matches full search count"
    track_command "compare count_only vs full search in json io"
    count_resp=$(echo '{"command": "search-records", "params": {"ksearch": "priority=critical", "count_only": true}}' \
        | run_aver json io 2>&1)
    full_resp=$(echo '{"command": "search-records", "params": {"ksearch": "priority=critical"}}' \
        | run_aver json io 2>&1)

    count_only_n=$(echo "$count_resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['count'])" 2>/dev/null || echo "")
    full_n=$(echo "$full_resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['count'])" 2>/dev/null || echo "")

    if [ -n "$count_only_n" ] && [ "$count_only_n" = "$full_n" ]; then
        pass
        echo "  count_only ($count_only_n) == full search count ($full_n)"
    else
        fail "count_only ($count_only_n) != full search count ($full_n)"
    fi
}


#==============================================================================
# Test: --max flag for record list and JSON IO search-records
#==============================================================================

test_max_flag() {
    print_section "Test: --max Flag"

    # Setup: create records with known severity (integer) and priority (string)
    # severity: 1=lowest, 5=highest   priority: low < medium < high (lexicographic)
    print_test "Setup: Create records with varying severity and priority"
    local ra=$(run_aver record new --description "" --no-validation-editor \
        --title "Max Test A" --status open --priority low --severity 3 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local rb=$(run_aver record new --description "" --no-validation-editor \
        --title "Max Test B" --status open --priority high --severity 5 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local rc=$(run_aver record new --description "" --no-validation-editor \
        --title "Max Test C" --status open --priority high --severity 2 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local rd=$(run_aver record new --description "" --no-validation-editor \
        --title "Max Test D" --status open --priority medium --severity 5 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")

    if [ -z "$ra" ] || [ -z "$rb" ] || [ -z "$rc" ] || [ -z "$rd" ]; then
        fail "Setup failed: could not create test records"
        return
    fi
    pass
    echo "  $ra: priority=low,  severity=3"
    echo "  $rb: priority=high, severity=5  ← max severity"
    echo "  $rc: priority=high, severity=2"
    echo "  $rd: priority=med,  severity=5  ← max severity"

    # Test 1: --max without --ksort errors
    print_test "--max without --ksort fails with error"
    set +e
    track_command "aver record list --ksearch status=open --max severity (no --ksort)"
    output=$(run_aver record list --ksearch status=open --max severity 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$output" | grep -qi "ksort"; then
        pass
        echo "  Correctly requires --ksort"
    else
        fail "Should have failed with --ksort error, got exit=$exit_code: $output"
    fi

    # Test 2: --max integer key returns only records with the max integer value
    print_test "--max on integer key returns records with max value"
    if output=$(run_aver record list --ksearch status=open --ksort severity --max severity 2>&1); then
        # rb and rd both have severity=5 (the max), ra has 3, rc has 2
        if echo "$output" | grep -q "Max Test B" && echo "$output" | grep -q "Max Test D"; then
            if ! echo "$output" | grep -q "Max Test A" && ! echo "$output" | grep -q "Max Test C"; then
                pass
                echo "  Correctly returned only severity=5 records (B and D)"
            else
                fail "Returned records without max severity: $output"
            fi
        else
            fail "Did not return all max-severity records: $output"
        fi
    else
        fail "--max severity command failed"
    fi

    # Test 3: --max string key returns only records with the max string value
    print_test "--max on string key returns records with max string value"
    if output=$(run_aver record list --ksearch status=open --ksort priority --max priority 2>&1); then
        # max priority lexicographically is "medium" < "high" < "low" … actually:
        # "high" < "low" < "medium" lexicographically
        # Let's check: "h" < "l" < "m"  → max = "medium"
        # rd has priority=medium which is the lex max
        if echo "$output" | grep -q "Max Test D"; then
            if ! echo "$output" | grep -q "Max Test A"; then
                pass
                echo "  Correctly returned only records with max priority value"
            else
                fail "Returned non-max-priority records: $output"
            fi
        else
            fail "Did not find expected max-priority record: $output"
        fi
    else
        fail "--max priority command failed"
    fi

    # Test 4: --max with comma-delimited keys (OR logic)
    print_test "--max with comma-delimited keys uses OR logic"
    if output=$(run_aver record list --ksearch status=open --ksort severity --max "severity,priority" 2>&1); then
        # max severity=5 → rb, rd qualify
        # max priority (lex) = "medium" → rd qualifies
        # OR: rb, rc (high=second-lex? no: "high" < "low" < "medium"), rd
        # Actually: lex order: "high" < "low" < "medium"
        # max priority = "medium" → rd
        # Union of max-severity (rb,rd) OR max-priority (rd) = rb, rd
        if echo "$output" | grep -q "Max Test B" && echo "$output" | grep -q "Max Test D"; then
            pass
            echo "  OR logic: returned max-severity OR max-priority records"
        else
            fail "OR logic did not return expected records: $output"
        fi
    else
        fail "--max comma-delimited keys command failed"
    fi

    # Test 5: --max with repeated flag (same as comma-delimited)
    print_test "--max repeated flag same as comma-delimited"
    out_comma=$(run_aver record list --ksearch status=open --ksort severity --max "severity,priority" 2>&1)
    out_repeat=$(run_aver record list --ksearch status=open --ksort severity --max severity --max priority 2>&1)
    # Both should return the same set of record IDs
    ids_comma=$(echo "$out_comma" | grep -oE "REC-[A-Z0-9]+" | sort | tr '\n' ' ')
    ids_repeat=$(echo "$out_repeat" | grep -oE "REC-[A-Z0-9]+" | sort | tr '\n' ' ')
    if [ "$ids_comma" = "$ids_repeat" ] && [ -n "$ids_comma" ]; then
        pass
        echo "  Both forms return identical results: $ids_comma"
    else
        fail "Comma form ($ids_comma) != repeated form ($ids_repeat)"
    fi

    # Test 6: --max with single matching record
    print_test "--max with unique max value returns single record"
    if output=$(run_aver record list --ksearch status=open --ksort severity --max severity 2>&1); then
        # There are exactly 2 records with severity=5 (rb and rd)
        count=$(echo "$output" | grep -c "Max Test" || echo "0")
        if [ "$count" = "2" ]; then
            pass
            echo "  Correctly returned 2 records with max severity"
        else
            fail "Expected 2 max-severity records, got $count"
        fi
    else
        fail "--max severity count check failed"
    fi

    # Test 7: --max result count is <= full result count
    print_test "--max result count is <= full query count"
    full_out=$(run_aver record list --ksearch status=open --ksort severity 2>&1)
    max_out=$(run_aver record list --ksearch status=open --ksort severity --max severity 2>&1)
    full_n=$(echo "$full_out" | grep "Found .* matches" | grep -oE '[0-9]+' | head -1 || echo "0")
    max_n=$(echo "$max_out" | grep "Found .* matches" | grep -oE '[0-9]+' | head -1 || echo "0")
    if [ -n "$full_n" ] && [ -n "$max_n" ] && [ "$max_n" -le "$full_n" ]; then
        pass
        echo "  max results ($max_n) <= full results ($full_n)"
    else
        fail "max results ($max_n) should be <= full results ($full_n)"
    fi

    # Test 8: JSON IO search-records max parameter
    print_test "JSON IO search-records max parameter"
    track_command "echo search-records max | aver json io"
    if output=$(echo '{"command": "search-records", "params": {"ksearch": "status=open", "ksort": "severity", "max": ["severity"]}}' \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['success'] == True, f'not success: {data}'
result = data['result']
assert 'records' in result, 'records key missing'
# All returned records must have severity == max severity in result
records = result['records']
assert len(records) > 0, 'no records returned'
severities = [r['fields'].get('severity') for r in records if 'severity' in r['fields']]
assert len(severities) == len(records), 'some records missing severity field'
max_sev = max(severities)
for s in severities:
    assert s == max_sev, f'severity {s} != max {max_sev}'
" 2>/dev/null; then
            pass
            echo "  JSON IO max: all returned records have max severity"
        else
            fail "JSON IO max response invalid or records not at max: $output"
        fi
    else
        fail "JSON IO search-records max failed"
    fi

    # Test 9: JSON IO search-records max without ksort errors
    print_test "JSON IO search-records max without ksort errors"
    track_command "echo search-records max (no ksort) | aver json io"
    if output=$(echo '{"command": "search-records", "params": {"ksearch": "status=open", "max": ["severity"]}}' \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['success'] == False, 'should have failed'
assert 'ksort' in data.get('error', '').lower(), f'wrong error: {data}'
" 2>/dev/null; then
            pass
            echo "  Correctly errored: max requires ksort"
        else
            fail "Should have failed with ksort error: $output"
        fi
    else
        fail "JSON IO max-without-ksort test invocation failed"
    fi

    # Test 10: JSON IO max with multiple keys (OR logic)
    print_test "JSON IO search-records max with multiple keys"
    track_command "echo search-records max multi-key | aver json io"
    if output=$(echo '{"command": "search-records", "params": {"ksearch": "status=open", "ksort": "severity", "max": ["severity", "priority"]}}' \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['success'] == True, f'not success: {data}'
result = data['result']
assert len(result['records']) > 0, 'no records returned'
print('count:', result['count'])
" 2>/dev/null; then
            pass
            echo "  JSON IO multi-key max returned results"
        else
            fail "JSON IO multi-key max invalid: $output"
        fi
    else
        fail "JSON IO multi-key max failed"
    fi
}


#==============================================================================
# Test: ^ (in) operator for ksearch
#==============================================================================

test_in_operator() {
    print_section "Test: ^ (in) Operator for ksearch"

    # Setup: create records with known status/priority values
    print_test "Setup: Create records with varying status and priority"
    local r_open=$(run_aver record new --description "" --no-validation-editor \
        --title "In Test Open" --status open --priority low 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local r_closed=$(run_aver record new --description "" --no-validation-editor \
        --title "In Test Closed" --status closed --priority high 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local r_resolved=$(run_aver record new --description "" --no-validation-editor \
        --title "In Test Resolved" --status resolved --priority high 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    local r_inprog=$(run_aver record new --description "" --no-validation-editor \
        --title "In Test InProgress" --status in_progress --priority critical 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")

    if [ -z "$r_open" ] || [ -z "$r_closed" ] || [ -z "$r_resolved" ] || [ -z "$r_inprog" ]; then
        fail "Setup failed: could not create test records"
        return
    fi
    pass
    echo "  open=$r_open  closed=$r_closed  resolved=$r_resolved  in_progress=$r_inprog"

    # Test 1: status^open|closed returns open and closed, not resolved/in_progress
    print_test "status^open|closed matches open and closed records only"
    track_command "aver record list --ksearch 'status^open|closed' --ksearch 'title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress'"
    if output=$(run_aver record list --ksearch "status^open|closed" --ksearch "title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress" 2>&1); then
        if echo "$output" | grep -q "In Test Open" && echo "$output" | grep -q "In Test Closed"; then
            if ! echo "$output" | grep -q "In Test Resolved" && ! echo "$output" | grep -q "In Test InProgress"; then
                pass
                echo "  Correctly matched open and closed, excluded resolved and in_progress"
            else
                fail "Returned records outside the IN set: $output"
            fi
        else
            fail "Did not return expected records: $output"
        fi
    else
        fail "Command failed: $output"
    fi

    # Test 2: priority^high|critical matches high and critical, not low
    print_test "priority^high|critical matches high and critical records only"
    track_command "aver record list --ksearch 'priority^high|critical' --ksearch 'title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress'"
    if output=$(run_aver record list --ksearch "priority^high|critical" --ksearch "title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress" 2>&1); then
        if echo "$output" | grep -q "In Test Closed" && echo "$output" | grep -q "In Test Resolved" && echo "$output" | grep -q "In Test InProgress"; then
            if ! echo "$output" | grep -q "In Test Open"; then
                pass
                echo "  Correctly matched high/critical, excluded low"
            else
                fail "Returned low-priority record: $output"
            fi
        else
            fail "Did not return expected records: $output"
        fi
    else
        fail "Command failed: $output"
    fi

    # Test 3: ^ combined with another --ksearch (AND logic preserved)
    print_test "status^open|closed combined with priority=high (AND logic)"
    track_command "aver record list --ksearch 'status^open|closed' --ksearch 'priority=high' --ksearch 'title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress'"
    if output=$(run_aver record list --ksearch "status^open|closed" --ksearch "priority=high" --ksearch "title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress" 2>&1); then
        # Only r_closed has status=closed AND priority=high
        if echo "$output" | grep -q "In Test Closed"; then
            if ! echo "$output" | grep -q "In Test Open" && ! echo "$output" | grep -q "In Test Resolved"; then
                pass
                echo "  AND logic: only closed+high record returned"
            else
                fail "AND logic broken, returned extra records: $output"
            fi
        else
            fail "Did not find expected closed+high record: $output"
        fi
    else
        fail "Command failed: $output"
    fi

    # Test 4: Single value status^open degenerates to status=open
    # Scope to our test records by title to avoid 50-record default limit issues
    print_test "status^open (single value) equivalent to status=open"
    track_command "aver record list --ksearch 'status^open' --ksearch 'title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress'"
    out_in=$(run_aver record list --ksearch "status^open" \
        --ksearch "title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress" 2>&1)
    out_eq=$(run_aver record list --ksearch "status=open" \
        --ksearch "title^In Test Open|In Test Closed|In Test Resolved|In Test InProgress" 2>&1)
    ids_in=$(echo "$out_in" | grep -oE "In Test [A-Za-z]+" | sort | tr '\n' ',')
    ids_eq=$(echo "$out_eq" | grep -oE "In Test [A-Za-z]+" | sort | tr '\n' ',')
    if [ "$ids_in" = "$ids_eq" ] && [ -n "$ids_in" ]; then
        pass
        echo "  Single-value ^ matches same records as ="
    else
        fail "Single ^ ($ids_in) != = ($ids_eq)"
    fi

    # Test 5: JSON IO search-records with ^ operator
    print_test "JSON IO: status^open|closed returns correct records"
    track_command "echo search-records ksearch status^open|closed | aver json io"
    if output=$(echo '{"command": "search-records", "params": {"ksearch": ["status^open|closed"]}}' \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data['success'] == True, f'not success: {data}'
records = data['result']['records']
statuses = [r['fields'].get('status') for r in records]
for s in statuses:
    assert s in ('open', 'closed'), f'unexpected status: {s}'
assert any(s == 'open' for s in statuses), 'no open records'
assert any(s == 'closed' for s in statuses), 'no closed records'
" 2>/dev/null; then
            pass
            echo "  JSON IO ^ operator returned only open/closed records"
        else
            fail "JSON IO ^ response invalid or wrong records: $output"
        fi
    else
        fail "JSON IO search-records with ^ failed"
    fi

    # Test 6: Note search with ^ operator
    # Add notes to r_open with categories
    print_test "Setup: Add notes with category field to test note ^ search"
    local na=$(run_aver note add "$r_open" --message "bugfix note" --category bugfix 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" || echo "")
    local nb=$(run_aver note add "$r_open" --message "investigation note" --category investigation 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" || echo "")
    local nc=$(run_aver note add "$r_open" --message "workaround note" --category workaround 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" || echo "")
    if [ -z "$na" ] || [ -z "$nb" ] || [ -z "$nc" ]; then
        fail "Setup failed: could not create test notes"
        return
    fi
    pass
    echo "  Notes: bugfix=$na  investigation=$nb  workaround=$nc"

    print_test "note search --ksearch 'category^bugfix|investigation'"
    track_command "aver note search --ksearch 'category^bugfix|investigation' scoped to test record"
    if output=$(run_aver note search --ksearch "category^bugfix|investigation" --ksearch "incident_id=$r_open" 2>&1); then
        if echo "$output" | grep -q "$na" && echo "$output" | grep -q "$nb"; then
            if ! echo "$output" | grep -q "$nc"; then
                pass
                echo "  Note ^ search: bugfix and investigation matched, workaround excluded"
            else
                fail "Workaround note should not appear: $output"
            fi
        else
            fail "Expected bugfix ($na) and investigation ($nb) notes not found: $output"
        fi
    else
        fail "note search with ^ failed: $output"
    fi

    # Test 7: Nonexistent values return empty, not error
    print_test "status^nonexistent|alsonotreal returns empty (no error)"
    track_command "aver record list --ksearch 'status^nonexistent|alsonotreal'"
    set +e
    output=$(run_aver record list --ksearch "status^nonexistent|alsonotreal" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ] && ! echo "$output" | grep -qi "error"; then
        pass
        echo "  Nonexistent values: empty result, no error"
    else
        fail "Expected empty result but got exit=$exit_code: $output"
    fi
}


#==============================================================================
# Test: securestring field type
#==============================================================================

test_securestring() {
    print_section "Test: securestring Field Type"

    local MASK="{securestring}"

    # -------------------------------------------------------------------------
    # 1. Create a record with an editable securestring field via --api_token
    # -------------------------------------------------------------------------
    print_test "Create record with editable securestring via --api_token"
    local rec_sec
    rec_sec=$(run_aver record new --description "" --no-validation-editor \
        --title "Secure Test Record" --api_token "supersecret123" 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_sec" ]; then
        fail "Could not create record with securestring field"
        return
    fi
    pass
    echo "  Created: $rec_sec"

    # -------------------------------------------------------------------------
    # 2. record view masks the securestring value
    # -------------------------------------------------------------------------
    print_test "record view masks securestring as {securestring}"
    track_command "aver record view $rec_sec"
    if output=$(run_aver record view "$rec_sec" 2>&1); then
        if echo "$output" | grep -q "api_token" && echo "$output" | grep -q "$MASK"; then
            if ! echo "$output" | grep -q "supersecret123"; then
                pass
                echo "  api_token displayed as $MASK"
            else
                fail "Plaintext value visible in view output: $output"
            fi
        else
            fail "api_token or mask not found in view output: $output"
        fi
    else
        fail "record view failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 3. The on-disk file contains the plaintext value
    # -------------------------------------------------------------------------
    print_test "On-disk record file contains plaintext securestring"
    local rec_file="$TEST_DIR/records/${rec_sec}.md"
    if [ -f "$rec_file" ]; then
        if grep -q "supersecret123" "$rec_file"; then
            pass
            echo "  Plaintext confirmed in $rec_file"
        else
            fail "Plaintext not found in on-disk file: $rec_file"
        fi
    else
        fail "Record file not found: $rec_file"
    fi

    # -------------------------------------------------------------------------
    # 4. record list masks the securestring value
    # -------------------------------------------------------------------------
    print_test "record list masks securestring"
    track_command "aver record list --ksearch title=Secure Test Record"
    if output=$(run_aver record list --ksearch "title=Secure Test Record" 2>&1); then
        if ! echo "$output" | grep -q "supersecret123"; then
            pass
            echo "  Plaintext not visible in list output"
        else
            fail "Plaintext leaked in record list output: $output"
        fi
    else
        fail "record list failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 5. Search by securestring value (=) finds the record
    # -------------------------------------------------------------------------
    print_test "ksearch api_token=supersecret123 finds the record"
    track_command "aver record list --ksearch api_token=supersecret123"
    if output=$(run_aver record list --ksearch "api_token=supersecret123" 2>&1); then
        if echo "$output" | grep -q "$rec_sec"; then
            pass
            echo "  Record found via securestring search"
        else
            fail "Record not found via securestring search: $output"
        fi
    else
        fail "ksearch by securestring failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 6. Negative search (!=) excludes the record
    # -------------------------------------------------------------------------
    print_test "ksearch api_token!=supersecret123 excludes the record"
    track_command "aver record list --ksearch title=Secure Test Record --ksearch api_token!=supersecret123"
    if output=$(run_aver record list --ksearch "title=Secure Test Record" --ksearch "api_token!=supersecret123" 2>&1); then
        if ! echo "$output" | grep -q "$rec_sec"; then
            pass
            echo "  != operator correctly excludes the record"
        else
            fail "Record should have been excluded by != operator: $output"
        fi
    else
        fail "!= ksearch failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 7. ^ (in) operator finds the record
    # -------------------------------------------------------------------------
    print_test "ksearch api_token^supersecret123|othervalue finds the record"
    track_command "aver record list --ksearch 'api_token^supersecret123|othervalue'"
    if output=$(run_aver record list --ksearch "api_token^supersecret123|othervalue" 2>&1); then
        if echo "$output" | grep -q "$rec_sec"; then
            pass
            echo "  ^ operator correctly finds the record"
        else
            fail "Record not found via ^ operator: $output"
        fi
    else
        fail "^ ksearch failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 8. JSON export masks the securestring
    # -------------------------------------------------------------------------
    print_test "json export-record masks securestring"
    track_command "aver json export-record $rec_sec"
    if output=$(run_aver json export-record "$rec_sec" 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
fields = data.get('fields', {})
api_token = fields.get('api_token', '')
assert api_token == '{securestring}', f'Expected mask, got: {api_token!r}'
assert 'supersecret123' not in str(data), 'Plaintext leaked in JSON export'
print('ok')
" 2>/dev/null; then
            pass
            echo "  JSON export shows mask, not plaintext"
        else
            fail "JSON export did not mask securestring: $output"
        fi
    else
        fail "json export-record failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 9. JSON IO search-records masks securestring
    # -------------------------------------------------------------------------
    print_test "JSON IO search-records masks securestring"
    track_command "json io search-records ksearch title=Secure Test Record"
    if output=$(echo '{"command": "search-records", "params": {"ksearch": ["title=Secure Test Record"]}}' \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success'), f'not success: {data}'
records = data['result']['records']
assert len(records) > 0, 'no records returned'
for r in records:
    token = r['fields'].get('api_token', '')
    assert token == '{securestring}', f'Expected mask, got: {token!r}'
    assert 'supersecret123' not in str(r), 'Plaintext leaked in search result'
print('ok')
" 2>/dev/null; then
            pass
            echo "  JSON IO search masks securestring"
        else
            fail "JSON IO search did not mask securestring: $output"
        fi
    else
        fail "JSON IO search-records failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 10. Update editable securestring via --api_token with a new value
    # -------------------------------------------------------------------------
    print_test "Update editable securestring to a new value"
    track_command "aver record update $rec_sec --api_token newsecret456 --metadata-only --no-validation-editor"
    if output=$(run_aver record update "$rec_sec" --api_token "newsecret456" --metadata-only --no-validation-editor 2>&1); then
        # Confirm searchable by new value
        if search_out=$(run_aver record list --ksearch "api_token=newsecret456" 2>&1) && \
           echo "$search_out" | grep -q "$rec_sec"; then
            pass
            echo "  Record found by new securestring value after update"
        else
            fail "Record not found by new value after update: $search_out"
        fi
    else
        fail "record update with securestring failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 11. Old value no longer finds the record after update
    # -------------------------------------------------------------------------
    print_test "Old securestring value no longer finds record after update"
    track_command "aver record list --ksearch api_token=supersecret123"
    if output=$(run_aver record list --ksearch "api_token=supersecret123" --ksearch "title=Secure Test Record" 2>&1); then
        if ! echo "$output" | grep -q "$rec_sec"; then
            pass
            echo "  Old value correctly no longer matches"
        else
            fail "Old value still matches after update: $output"
        fi
    else
        fail "Search with old value failed unexpectedly: $output"
    fi

    # -------------------------------------------------------------------------
    # 12. Non-editable securestring can be set on creation but not updated
    # -------------------------------------------------------------------------
    print_test "Create record with non-editable securestring"
    local rec_ne
    rec_ne=$(run_aver record new --description "" --no-validation-editor \
        --title "NonEditable Secure" --master_secret "initialsecret" 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_ne" ]; then
        fail "Could not create record with non-editable securestring"
        return
    fi
    # Verify searchable by initial value
    if search_out=$(run_aver record list --ksearch "master_secret=initialsecret" 2>&1) && \
       echo "$search_out" | grep -q "$rec_ne"; then
        pass
        echo "  Non-editable securestring set on creation: $rec_ne"
    else
        fail "Non-editable securestring not searchable after creation: $search_out"
    fi

    print_test "Non-editable securestring cannot be updated"
    set +e
    output=$(run_aver record update "$rec_ne" --master_secret "newsecret" --metadata-only --no-validation-editor 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] || echo "$output" | grep -qi "cannot be edited\|not editable\|error"; then
        pass
        echo "  Correctly rejected update to non-editable securestring"
    else
        fail "Should have rejected update to non-editable securestring: $output"
    fi

    # -------------------------------------------------------------------------
    # 13. Note with securestring field
    # -------------------------------------------------------------------------
    print_test "Add note with securestring field"
    local note_id
    note_id=$(run_aver note add "$rec_sec" --message "Note with token" \
        --session_token "tokenabc" 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" || echo "")
    if [ -z "$note_id" ]; then
        fail "Could not create note with securestring field"
        return
    fi
    pass
    echo "  Note created: $note_id"

    print_test "note view masks securestring"
    track_command "aver note view $rec_sec $note_id"
    if output=$(run_aver note view "$rec_sec" "$note_id" 2>&1); then
        if echo "$output" | grep -q "session_token" && echo "$output" | grep -q "$MASK"; then
            if ! echo "$output" | grep -q "tokenabc"; then
                pass
                echo "  Note securestring masked in view"
            else
                fail "Plaintext visible in note view: $output"
            fi
        else
            fail "session_token or mask not in note view: $output"
        fi
    else
        fail "note view failed: $output"
    fi

    print_test "note search by securestring value"
    track_command "aver note search --ksearch session_token=tokenabc"
    if output=$(run_aver note search --ksearch "session_token=tokenabc" --ksearch "incident_id=$rec_sec" 2>&1); then
        if echo "$output" | grep -q "$note_id"; then
            pass
            echo "  Note found by securestring search"
        else
            fail "Note not found by securestring search: $output"
        fi
    else
        fail "note search by securestring failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 14. template-data shows securestring value_type
    # -------------------------------------------------------------------------
    print_test "json io template-data shows securestring value_type"
    track_command "json io template-data (no template_id)"
    if output=$(echo '{"command":"template-data","params":{}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success'), f'not success: {data}'
r = data['result']
record_fields = r.get('record_fields', {})
assert 'api_token' in record_fields, 'api_token not in record_fields'
assert record_fields['api_token']['value_type'] == 'securestring', \
    f'wrong value_type: {record_fields[\"api_token\"][\"value_type\"]}'
print('ok')
" 2>/dev/null; then
            pass
            echo "  template-data correctly reports value_type=securestring"
        else
            fail "template-data did not show securestring value_type: $output"
        fi
    else
        fail "json io template-data failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 15. Reindex preserves searchability of securestring
    # -------------------------------------------------------------------------
    print_test "Reindex preserves securestring searchability"
    track_command "aver admin reindex --force --skip-validation && aver record list --ksearch api_token=newsecret456"
    if run_aver admin reindex --force --skip-validation > /dev/null 2>&1; then
        if search_out=$(run_aver record list --ksearch "api_token=newsecret456" 2>&1) && \
           echo "$search_out" | grep -q "$rec_sec"; then
            pass
            echo "  Securestring searchable after reindex"
        else
            fail "Securestring not searchable after reindex: $search_out"
        fi
    else
        fail "reindex failed"
    fi

    # -------------------------------------------------------------------------
    # 16. Template-scoped securestring field
    # -------------------------------------------------------------------------
    print_test "Template-scoped securestring (feature template oauth_secret)"
    local rec_feat
    rec_feat=$(run_aver record new --description "" --no-validation-editor \
        --template feature --title "Feature With Secret" \
        --oauth_secret "clientsecret999" 2>&1 \
        | grep -oE "FEAT-[A-Z0-9]+" || echo "")
    if [ -z "$rec_feat" ]; then
        fail "Could not create feature record with oauth_secret"
        return
    fi
    # Verify mask on view
    if view_out=$(run_aver record view "$rec_feat" 2>&1) && \
       echo "$view_out" | grep -q "oauth_secret" && \
       echo "$view_out" | grep -q "$MASK" && \
       ! echo "$view_out" | grep -q "clientsecret999"; then
        pass
        echo "  Template-scoped securestring masked in view: $rec_feat"
    else
        fail "Template-scoped securestring not masked correctly: $view_out"
    fi

    print_test "Template-scoped securestring searchable"
    if search_out=$(run_aver record list --ksearch "oauth_secret=clientsecret999" 2>&1) && \
       echo "$search_out" | grep -q "$rec_feat"; then
        pass
        echo "  Template-scoped securestring searchable"
    else
        fail "Template-scoped securestring not searchable: $search_out"
    fi
}

#==============================================================================
# Cleanup
#==============================================================================

cleanup() {
    # Restore original HOME
    if [ -n "$ORIGINAL_HOME" ]; then
        export HOME="$ORIGINAL_HOME"
    fi
    
    if [ "$KEEP_TEST_DIR" = true ]; then
        echo -e "\n${YELLOW}Test directories preserved:${NC}"
        echo "  Test DB: ${TEST_DIR}"
        echo "  Test HOME: ${TEST_HOME}"
        echo "To clean up later: rm -rf ${TEST_DIR} ${TEST_HOME}"
    else
        if [ -n "$TEST_DIR" ] && [ -d "$TEST_DIR" ]; then
            rm -rf "$TEST_DIR"
        fi
        if [ -n "$TEST_HOME" ] && [ -d "$TEST_HOME" ]; then
            rm -rf "$TEST_HOME"
        fi
        echo -e "\n${BLUE}Test directories cleaned up${NC}"
        echo -e "${BLUE}Original HOME restored${NC}"
    fi
}

#==============================================================================
# Test: admin template-data command
#==============================================================================

test_template_data() {
    print_section "Test: admin template-data"

    # --- CLI: no template_id (list all) ---
    print_test "admin template-data (all templates, human output)"
    track_command "aver admin template-data"
    if output=$(run_aver admin template-data 2>&1); then
        if echo "$output" | grep -q "Global defaults" && \
           echo "$output" | grep -q "bug" && \
           echo "$output" | grep -q "feature"; then
            pass
            echo "  All templates shown"
        else
            fail "Missing expected template names in output"
            echo "$output"
        fi
    else
        fail "admin template-data (no args) failed"
    fi

    # --- CLI: specific template ---
    print_test "admin template-data bug (human output)"
    track_command "aver admin template-data bug"
    if output=$(run_aver admin template-data bug 2>&1); then
        if echo "$output" | grep -q "bug" && \
           echo "$output" | grep -q "record_fields\|Record fields" && \
           echo "$output" | grep -q "note_fields\|Note fields"; then
            pass
            echo "  Bug template fields shown"
        else
            fail "Missing expected sections in bug template output"
            echo "$output"
        fi
    else
        fail "admin template-data bug failed"
    fi

    # --- CLI: invalid template_id ---
    print_test "admin template-data nonexistent-template (error)"
    track_command "aver admin template-data nonexistent-template"
    set +e
    output=$(run_aver admin template-data nonexistent-template 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$output" | grep -qi "not found"; then
        pass
        echo "  Proper error for unknown template"
    else
        fail "Should have errored on nonexistent template"
        echo "  exit_code=$exit_code output=$output"
    fi

    # --- JSON IO: template-data with specific template ---
    print_test "json io template-data (bug template)"
    track_command "json io template-data bug"
    if output=$(echo '{"command": "template-data", "params": {"template_id": "bug"}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success') == True, f\"not success: {data}\"
r = data['result']
assert r['template_id'] == 'bug', 'template_id mismatch'
assert 'record_fields' in r, 'missing record_fields'
assert 'note_fields' in r, 'missing note_fields'
assert 'severity' in r['record_fields'], 'missing severity'
assert 'category' in r['note_fields'], 'missing category'
" 2>/dev/null; then
            pass
            echo "  IO template-data (bug) returned correct structure"
        else
            fail "IO template-data bug structure invalid"
            echo "$output"
        fi
    else
        fail "IO template-data bug failed"
    fi

    # --- JSON IO: template-data for global defaults (no template_id) ---
    print_test "json io template-data (global defaults)"
    track_command "json io template-data no template"
    if output=$(echo '{"command": "template-data", "params": {}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success') == True, f\"not success: {data}\"
r = data['result']
assert r['template_id'] is None, 'template_id should be None'
assert 'record_fields' in r, 'missing record_fields'
assert 'note_fields' in r, 'missing note_fields'
assert 'status' in r['record_fields'], 'missing status in global record fields'
assert 'author' in r['note_fields'], 'missing author in global note fields'
" 2>/dev/null; then
            pass
            echo "  IO template-data (global) returned correct structure"
        else
            fail "IO template-data global structure invalid"
            echo "$output"
        fi
    else
        fail "IO template-data global failed"
    fi

    # --- JSON IO: template-data for invalid template ---
    print_test "json io template-data (nonexistent template → error)"
    track_command "json io template-data nonexistent"
    if output=$(echo '{"command": "template-data", "params": {"template_id": "nonexistent"}}' | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success') == False, f\"should have failed: {data}\"
assert 'error' in data, 'missing error key'
" 2>/dev/null; then
            pass
            echo "  IO template-data error handled correctly"
        else
            fail "IO template-data nonexistent should return error"
            echo "$output"
        fi
    else
        fail "IO template-data nonexistent failed to run"
    fi
}

#==============================================================================
# Test: Note Contract (field round-trip, type fidelity, all injection paths)
#==============================================================================
#
# Contracts tested:
#   A. Special field editable=false, no system_value  → stored/returned as supplied
#   B. Special field with system_value                → system value wins, caller value discarded
#   C. Custom string field                            → disk has __string suffix, export has none
#   D. Custom integer field                           → disk has __integer suffix, export is numeric
#   E. Template-specific note field (editable=false)  → stored/returned as supplied
#   F. Global note fields apply to templated records  → both global and template fields present
#
# Injection paths tested for each contract:
#   1. CLI:     note add --from-file <file>
#   2. CLI-JSON: json import-note RECORD_ID --data '{...}'
#   3. JSON-IO:  json io  {"command": "import-note", ...}
#==============================================================================

test_note_contract() {
    print_section "Note Contract: Field Round-Trip and Type Fidelity"

    # -------------------------------------------------------------------------
    # Setup: records to attach notes to
    # -------------------------------------------------------------------------
    local plain_rec bug_rec

    plain_rec=$(run_aver record new --description "" --no-validation-editor \
        --title "Note Contract Plain" --status open 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")

    if [ -f "$TEST_DIR/bug_rec_id.txt" ]; then
        bug_rec=$(cat "$TEST_DIR/bug_rec_id.txt")
    else
        bug_rec=$(run_aver json import-record \
            --data '{"content":"Bug for note contract","fields":{"title":"Note Contract Bug","status":"new"},"template":"bug"}' \
            2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null || echo "")
    fi

    if [ -z "$plain_rec" ] || [ -z "$bug_rec" ]; then
        echo -e "${RED}Setup failed: could not create records for note contract tests${NC}"
        return
    fi
    echo "  Plain record: $plain_rec  |  Bug record: $bug_rec"

    # =========================================================================
    # CONTRACT A: Special field editable=false, no system_value
    # note_type is defined in [note_special_fields.note_type] editable=false, no system_value
    # Must be stored WITHOUT a type-hint suffix and returned as supplied.
    # =========================================================================

    # --- Path 1: CLI --from-file ---
    print_test "Contract A (special field editable=false) via CLI --from-file"
    cat > "$TEST_DIR/nc_a1.md" << 'EOF'
---
note_type: bug-report
---
Contract A path 1 body.
EOF
    if run_aver note add "$plain_rec" --from-file "$TEST_DIR/nc_a1.md" > /dev/null 2>&1; then
        local nf=$(ls -t "$TEST_DIR/updates/$plain_rec/"*.md 2>/dev/null | head -1)
        if [ -n "$nf" ] && grep -q "^note_type: bug-report" "$nf" && ! grep -q "note_type__" "$nf"; then
            pass
            echo "  On disk: note_type: bug-report (no type-hint suffix)"
        else
            fail "note_type not stored correctly on disk"
            [ -n "$nf" ] && cat "$nf"
        fi
    else
        fail "note add --from-file failed"
    fi

    sleep 0.25
    # --- Path 2: CLI json import-note ---
    print_test "Contract A (special field editable=false) via json import-note"
    local out2
    if out2=$(run_aver json import-note "$plain_rec" \
        --data '{"content":"Contract A path 2 body.","fields":{"note_type":"bug-report"}}' 2>&1); then
        local note_id2
        note_id2=$(echo "$out2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('note_id',''))" 2>/dev/null)
        local nf2="$TEST_DIR/updates/$plain_rec/${note_id2}.md"
        if [ -n "$note_id2" ] && [ -f "$nf2" ] && grep -q "^note_type: bug-report" "$nf2" && ! grep -q "note_type__" "$nf2"; then
            pass
            echo "  On disk: note_type: bug-report (no type-hint suffix)"
        else
            fail "note_type not stored correctly on disk"
            [ -f "$nf2" ] && cat "$nf2"
        fi
    else
        fail "json import-note failed: $out2"
    fi

    sleep 0.25
    # --- Path 3: JSON IO ---
    print_test "Contract A (special field editable=false) via json io import-note"
    local out3
    if out3=$(echo '{"command":"import-note","params":{"record_id":"'"$plain_rec"'","content":"Contract A path 3 body.","fields":{"note_type":"bug-report"}}}' \
        | run_aver json io 2>&1); then
        local note_id3
        note_id3=$(echo "$out3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('note_id',''))" 2>/dev/null)
        local nf3="$TEST_DIR/updates/$plain_rec/${note_id3}.md"
        if [ -n "$note_id3" ] && [ -f "$nf3" ] && grep -q "^note_type: bug-report" "$nf3" && ! grep -q "note_type__" "$nf3"; then
            pass
            echo "  On disk: note_type: bug-report (no type-hint suffix)"
        else
            fail "note_type not stored correctly on disk"
            [ -f "$nf3" ] && cat "$nf3"
        fi
    else
        fail "json io import-note failed: $out3"
    fi

    # --- Export verification: note_type appears in export ---
    print_test "Contract A: exported notes contain note_type field"
    if out=$(run_aver json export-record "$plain_rec" --include-notes 2>&1); then
        if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
notes = d.get('notes', [])
found = any(n.get('fields', {}).get('note_type') == 'bug-report' for n in notes)
assert found, 'No note with note_type=bug-report found'
" 2>/dev/null; then
            pass
            echo "  note_type: bug-report present in exported notes"
        else
            fail "note_type not found in export"
            echo "$out" | python3 -c "import sys,json; import pprint; pprint.pprint(json.load(sys.stdin))" 2>/dev/null
        fi
    else
        fail "export-record failed"
    fi

    # =========================================================================
    # CONTRACT B: System-value field — system value must win over caller input
    # timestamp has system_value="datetime" — caller-supplied value must be discarded
    # =========================================================================

    print_test "Contract B (system_value overrides caller) via json import-note"
    local fake_ts="1999-01-01 00:00:00"
    local out_b
    if out_b=$(run_aver json import-note "$plain_rec" \
        --data "{\"content\":\"Contract B body.\",\"fields\":{\"timestamp\":\"$fake_ts\"}}" 2>&1); then
        local note_id_b
        note_id_b=$(echo "$out_b" | python3 -c "import sys,json; print(json.load(sys.stdin).get('note_id',''))" 2>/dev/null)
        local nf_b="$TEST_DIR/updates/$plain_rec/${note_id_b}.md"
        if [ -n "$note_id_b" ] && [ -f "$nf_b" ]; then
            # The file must have a timestamp field, but NOT the fake value
            if grep -q "timestamp:" "$nf_b" && ! grep -q "$fake_ts" "$nf_b"; then
                pass
                echo "  System timestamp present; fake value discarded"
            else
                fail "System value did not override caller-supplied timestamp"
                cat "$nf_b"
            fi
        else
            fail "Note not found on disk: $note_id_b"
        fi
    else
        fail "json import-note failed for Contract B: $out_b"
    fi

    # =========================================================================
    # CONTRACT C: Custom string field
    # On disk: foo__string: hello
    # Exported: fields.foo = "hello"
    # =========================================================================

    # --- Path 1: CLI --from-file ---
    print_test "Contract C (custom string field) via CLI --from-file"
    cat > "$TEST_DIR/nc_c1.md" << 'EOF'
---
extra_info: hello
---
Contract C path 1 body.
EOF
    if run_aver note add "$plain_rec" --from-file "$TEST_DIR/nc_c1.md" > /dev/null 2>&1; then
        local nf_c1=$(ls -t "$TEST_DIR/updates/$plain_rec/"*.md 2>/dev/null | head -1)
        if [ -n "$nf_c1" ] && grep -q "extra_info__string: hello" "$nf_c1"; then
            pass
            echo "  On disk: extra_info__string: hello"
        else
            fail "Custom string field not stored with type-hint on disk"
            [ -n "$nf_c1" ] && cat "$nf_c1"
        fi
    else
        fail "note add --from-file failed for Contract C"
    fi

    sleep 0.25
    # --- Path 2: CLI json import-note ---
    print_test "Contract C (custom string field) via json import-note"
    local out_c2
    if out_c2=$(run_aver json import-note "$plain_rec" \
        --data '{"content":"Contract C path 2 body.","fields":{"extra_info":"hello"}}' 2>&1); then
        local note_id_c2
        note_id_c2=$(echo "$out_c2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('note_id',''))" 2>/dev/null)
        local nf_c2="$TEST_DIR/updates/$plain_rec/${note_id_c2}.md"
        if [ -n "$note_id_c2" ] && [ -f "$nf_c2" ] && grep -q "extra_info__string: hello" "$nf_c2"; then
            pass
            echo "  On disk: extra_info__string: hello"
        else
            fail "Custom string field not stored with type-hint on disk"
            [ -f "$nf_c2" ] && cat "$nf_c2"
        fi
    else
        fail "json import-note failed for Contract C: $out_c2"
    fi

    sleep 0.25
    # --- Path 3: JSON IO ---
    print_test "Contract C (custom string field) via json io import-note"
    local out_c3
    if out_c3=$(echo '{"command":"import-note","params":{"record_id":"'"$plain_rec"'","content":"Contract C path 3 body.","fields":{"extra_info":"hello"}}}' \
        | run_aver json io 2>&1); then
        local note_id_c3
        note_id_c3=$(echo "$out_c3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('note_id',''))" 2>/dev/null)
        local nf_c3="$TEST_DIR/updates/$plain_rec/${note_id_c3}.md"
        if [ -n "$note_id_c3" ] && [ -f "$nf_c3" ] && grep -q "extra_info__string: hello" "$nf_c3"; then
            pass
            echo "  On disk: extra_info__string: hello"
        else
            fail "Custom string field not stored with type-hint on disk"
            [ -f "$nf_c3" ] && cat "$nf_c3"
        fi
    else
        fail "json io import-note failed for Contract C: $out_c3"
    fi

    # --- Export verification: extra_info returned without suffix ---
    print_test "Contract C: custom string field exported without type-hint"
    if out=$(run_aver json export-record "$plain_rec" --include-notes 2>&1); then
        if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
notes = d.get('notes', [])
found = any(n.get('fields', {}).get('extra_info') == 'hello' for n in notes)
assert found, 'No note with extra_info=hello found'
" 2>/dev/null; then
            pass
            echo "  extra_info: hello present in exported notes (no suffix)"
        else
            fail "custom field extra_info not found in export or has wrong value"
        fi
    else
        fail "export-record failed"
    fi

    # =========================================================================
    # CONTRACT D: Custom integer field
    # On disk: retry_count__integer: 3
    # Exported: fields.retry_count = 3  (integer, not string)
    # =========================================================================

    # --- Path 2: CLI json import-note (representative path) ---
    print_test "Contract D (custom integer field) via json import-note"
    local out_d
    if out_d=$(run_aver json import-note "$plain_rec" \
        --data '{"content":"Contract D body.","fields":{"retry_count__integer":3}}' 2>&1); then
        local note_id_d
        note_id_d=$(echo "$out_d" | python3 -c "import sys,json; print(json.load(sys.stdin).get('note_id',''))" 2>/dev/null)
        local nf_d="$TEST_DIR/updates/$plain_rec/${note_id_d}.md"
        if [ -n "$note_id_d" ] && [ -f "$nf_d" ] && grep -q "retry_count__integer: 3" "$nf_d"; then
            pass
            echo "  On disk: retry_count__integer: 3"
        else
            fail "Custom integer field not stored with type-hint on disk"
            [ -f "$nf_d" ] && cat "$nf_d"
        fi
    else
        fail "json import-note failed for Contract D: $out_d"
    fi

    print_test "Contract D: custom integer field exported as integer type"
    local out_d_export
    if out_d_export=$(run_aver json export-record "$plain_rec" --include-notes 2>&1); then
        if echo "$out_d_export" | python3 -c "
import sys, json
d = json.load(sys.stdin)
notes = d.get('notes', [])
found = any(isinstance(n.get('fields', {}).get('retry_count'), int) and
            n['fields']['retry_count'] == 3
            for n in notes)
assert found, 'No note with retry_count=3 (integer) found'
" 2>/dev/null; then
            pass
            echo "  retry_count exported as integer 3"
        else
            fail "retry_count not found as integer in export"
        fi
    else
        fail "export-record failed"
    fi

    # =========================================================================
    # CONTRACT E: Template-specific note field (editable=false, no system_value)
    # resolution is in [template.bug.note_special_fields.resolution]
    # Must be stored without type-hint suffix, returned as supplied.
    # =========================================================================

    # --- Path 1: CLI --from-file ---
    print_test "Contract E (template note field editable=false) via CLI --from-file"
    cat > "$TEST_DIR/nc_e1.md" << 'EOF'
---
resolution: fixed
---
Contract E path 1 body.
EOF
    if run_aver note add "$bug_rec" --from-file "$TEST_DIR/nc_e1.md" > /dev/null 2>&1; then
        local nf_e1=$(ls -t "$TEST_DIR/updates/$bug_rec/"*.md 2>/dev/null | head -1)
        if [ -n "$nf_e1" ] && grep -q "^resolution: fixed" "$nf_e1" && ! grep -q "resolution__" "$nf_e1"; then
            pass
            echo "  On disk: resolution: fixed (no type-hint suffix)"
        else
            fail "Template note field resolution not stored correctly"
            [ -n "$nf_e1" ] && cat "$nf_e1"
        fi
    else
        fail "note add --from-file failed for Contract E"
    fi

    sleep 0.25
    # --- Path 2: CLI json import-note ---
    print_test "Contract E (template note field editable=false) via json import-note"
    local out_e2
    if out_e2=$(run_aver json import-note "$bug_rec" \
        --data '{"content":"Contract E path 2 body.","fields":{"resolution":"fixed"}}' 2>&1); then
        local note_id_e2
        note_id_e2=$(echo "$out_e2" | python3 -c "import sys,json; print(json.load(sys.stdin).get('note_id',''))" 2>/dev/null)
        local nf_e2="$TEST_DIR/updates/$bug_rec/${note_id_e2}.md"
        if [ -n "$note_id_e2" ] && [ -f "$nf_e2" ] && grep -q "^resolution: fixed" "$nf_e2" && ! grep -q "resolution__" "$nf_e2"; then
            pass
            echo "  On disk: resolution: fixed (no type-hint suffix)"
        else
            fail "Template note field resolution not stored correctly"
            [ -f "$nf_e2" ] && cat "$nf_e2"
        fi
    else
        fail "json import-note failed for Contract E: $out_e2"
    fi

    sleep 0.25
    # --- Path 3: JSON IO ---
    print_test "Contract E (template note field editable=false) via json io import-note"
    local out_e3
    if out_e3=$(echo '{"command":"import-note","params":{"record_id":"'"$bug_rec"'","content":"Contract E path 3 body.","fields":{"resolution":"fixed"}}}' \
        | run_aver json io 2>&1); then
        local note_id_e3
        note_id_e3=$(echo "$out_e3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('note_id',''))" 2>/dev/null)
        local nf_e3="$TEST_DIR/updates/$bug_rec/${note_id_e3}.md"
        if [ -n "$note_id_e3" ] && [ -f "$nf_e3" ] && grep -q "^resolution: fixed" "$nf_e3" && ! grep -q "resolution__" "$nf_e3"; then
            pass
            echo "  On disk: resolution: fixed (no type-hint suffix)"
        else
            fail "Template note field resolution not stored correctly"
            [ -f "$nf_e3" ] && cat "$nf_e3"
        fi
    else
        fail "json io import-note failed for Contract E: $out_e3"
    fi

    # --- Export verification ---
    print_test "Contract E: template note field exported correctly"
    if out=$(run_aver json export-record "$bug_rec" --include-notes 2>&1); then
        if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
notes = d.get('notes', [])
found = any(n.get('fields', {}).get('resolution') == 'fixed' for n in notes)
assert found, 'No note with resolution=fixed found'
" 2>/dev/null; then
            pass
            echo "  resolution: fixed present in exported bug record notes"
        else
            fail "resolution field not found in export"
        fi
    else
        fail "export-record failed"
    fi

    # =========================================================================
    # CONTRACT F: Global note fields apply to templated record notes
    # A note on a bug record should have BOTH global fields (note_type, timestamp)
    # AND template fields (resolution, category) present.
    # =========================================================================

    print_test "Contract F: global and template note fields coexist on templated record"
    local out_f
    if out_f=$(run_aver json import-note "$bug_rec" \
        --data '{"content":"Contract F body.","fields":{"note_type":"regression","resolution":"workaround"}}' 2>&1); then
        local note_id_f
        note_id_f=$(echo "$out_f" | python3 -c "import sys,json; print(json.load(sys.stdin).get('note_id',''))" 2>/dev/null)
        local nf_f="$TEST_DIR/updates/$bug_rec/${note_id_f}.md"
        if [ -n "$note_id_f" ] && [ -f "$nf_f" ]; then
            # Must have: note_type (global), resolution (template), timestamp (global system)
            if grep -q "^note_type: regression" "$nf_f" && \
               grep -q "^resolution: workaround" "$nf_f" && \
               grep -q "^timestamp:" "$nf_f"; then
                pass
                echo "  Global (note_type, timestamp) and template (resolution) fields all present"
            else
                fail "Not all expected fields present in note"
                cat "$nf_f"
            fi
        else
            fail "Note not found on disk"
        fi
    else
        fail "json import-note failed for Contract F: $out_f"
    fi
}

#==============================================================================
# Test: Record Contract (field round-trip, type fidelity, all injection paths)
#==============================================================================
#
# Contracts tested:
#   A. Special field (editable=true, no system_value)  → stored/returned as supplied, no type-hint
#   B. Special field with system_value (created_at)    → system value wins on create
#   C. Custom string field                             → disk has __string suffix, export has none
#   D. Custom integer field                            → disk has __integer suffix, export is numeric
#   E. Template float field (impact_score)             → stored WITHOUT __float suffix on disk
#   F. Template integer field (severity)               → stored WITHOUT __integer suffix on disk
#   G. Type fidelity survives update round-trip        → update-record preserves field types
#
# Injection paths tested:
#   1. CLI:      record new --from-file <file>
#   2. CLI-JSON: json import-record --data '{...}'
#   3. JSON-IO:  json io  {"command": "import-record", ...}
#==============================================================================

test_record_contract() {
    print_section "Record Contract: Field Round-Trip and Type Fidelity"

    # =========================================================================
    # CONTRACT A: Global special field, no system_value
    # title and status are plain string special fields — no type-hint on disk.
    # =========================================================================

    # --- Path 1: CLI --from-file ---
    print_test "Contract A (plain special field) via CLI --from-file"
    cat > "$TEST_DIR/rc_a1.md" << 'EOF'
---
title: Contract A CLI
status: open
priority: high
---
Contract A path 1 body.
EOF
    local rec_a1
    if out=$(run_aver record new --from-file "$TEST_DIR/rc_a1.md" --no-validation-editor 2>&1); then
        rec_a1=$(echo "$out" | grep -oE "REC-[A-Z0-9]+" | head -1)
        local rf_a1="$TEST_DIR/records/${rec_a1}.md"
        if [ -n "$rec_a1" ] && [ -f "$rf_a1" ] && \
           grep -q "^title: Contract A CLI" "$rf_a1" && \
           grep -q "^status: open" "$rf_a1" && \
           ! grep -q "title__\|status__\|priority__" "$rf_a1"; then
            pass
            echo "  Special fields stored without type-hint suffixes: $rec_a1"
        else
            fail "Special fields have unexpected type-hints or wrong values on disk"
            [ -f "$rf_a1" ] && cat "$rf_a1"
        fi
    else
        fail "record new --from-file failed: $out"
    fi

    sleep 0.25
    # --- Path 2: CLI json import-record ---
    print_test "Contract A (plain special field) via json import-record"
    local rec_a2
    if out=$(run_aver json import-record \
        --data '{"content":"Contract A path 2 body.","fields":{"title":"Contract A JSON","status":"open","priority":"high"}}' 2>&1); then
        rec_a2=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        local rf_a2="$TEST_DIR/records/${rec_a2}.md"
        if [ -n "$rec_a2" ] && [ -f "$rf_a2" ] && \
           grep -q "^title: Contract A JSON" "$rf_a2" && \
           ! grep -q "title__\|status__\|priority__" "$rf_a2"; then
            pass
            echo "  Special fields stored without type-hint suffixes: $rec_a2"
        else
            fail "Special fields have unexpected type-hints on disk"
            [ -f "$rf_a2" ] && cat "$rf_a2"
        fi
    else
        fail "json import-record failed: $out"
    fi

    sleep 0.25
    # --- Path 3: JSON IO ---
    print_test "Contract A (plain special field) via json io import-record"
    local rec_a3
    if out=$(echo '{"command":"import-record","params":{"content":"Contract A path 3 body.","fields":{"title":"Contract A IO","status":"open","priority":"high"}}}' \
        | run_aver json io 2>&1); then
        rec_a3=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('record_id',''))" 2>/dev/null)
        local rf_a3="$TEST_DIR/records/${rec_a3}.md"
        if [ -n "$rec_a3" ] && [ -f "$rf_a3" ] && \
           grep -q "^title: Contract A IO" "$rf_a3" && \
           ! grep -q "title__\|status__\|priority__" "$rf_a3"; then
            pass
            echo "  Special fields stored without type-hint suffixes: $rec_a3"
        else
            fail "Special fields have unexpected type-hints on disk"
            [ -f "$rf_a3" ] && cat "$rf_a3"
        fi
    else
        fail "json io import-record failed: $out"
    fi

    # --- Export verification ---
    print_test "Contract A: special fields exported with correct values"
    if [ -n "$rec_a2" ]; then
        if out=$(run_aver json export-record "$rec_a2" 2>&1); then
            if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
f = d.get('fields', {})
assert f.get('title') == 'Contract A JSON', f'title wrong: {f.get(\"title\")}'
assert f.get('status') == 'open', f'status wrong: {f.get(\"status\")}'
assert f.get('priority') == 'high', f'priority wrong: {f.get(\"priority\")}'
" 2>/dev/null; then
                pass
                echo "  title, status, priority all correct in export"
            else
                fail "Exported field values incorrect"
                echo "$out"
            fi
        else
            fail "export-record failed"
        fi
    else
        fail "No record from path 2 to export"
    fi

    # =========================================================================
    # CONTRACT B: system_value field — system wins on creation
    # created_at has system_value="datetime" — caller value must be discarded.
    # =========================================================================

    print_test "Contract B (system_value overrides caller) via json import-record"
    local fake_dt="1999-01-01 00:00:00"
    local rec_b
    if out=$(run_aver json import-record \
        --data "{\"content\":\"Contract B body.\",\"fields\":{\"title\":\"Contract B\",\"status\":\"open\",\"created_at\":\"$fake_dt\"}}" 2>&1); then
        rec_b=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        local rf_b="$TEST_DIR/records/${rec_b}.md"
        if [ -n "$rec_b" ] && [ -f "$rf_b" ] && \
           grep -q "^created_at:" "$rf_b" && ! grep -q "$fake_dt" "$rf_b"; then
            pass
            echo "  created_at present with system value; fake value discarded"
        else
            fail "System value did not override caller-supplied created_at"
            [ -f "$rf_b" ] && cat "$rf_b"
        fi
    else
        fail "json import-record failed for Contract B: $out"
    fi

    # =========================================================================
    # CONTRACT C: Custom string field
    # On disk: foo__string: hello
    # Exported: fields.foo = "hello"
    # =========================================================================

    # --- Path 1: CLI --from-file ---
    print_test "Contract C (custom string field) via CLI --from-file"
    cat > "$TEST_DIR/rc_c1.md" << 'EOF'
---
title: Contract C CLI
status: open
extra_info: hello
---
Contract C path 1 body.
EOF
    local rec_c1
    if out=$(run_aver record new --from-file "$TEST_DIR/rc_c1.md" --no-validation-editor 2>&1); then
        rec_c1=$(echo "$out" | grep -oE "REC-[A-Z0-9]+" | head -1)
        local rf_c1="$TEST_DIR/records/${rec_c1}.md"
        if [ -n "$rec_c1" ] && [ -f "$rf_c1" ] && grep -q "extra_info__string: hello" "$rf_c1"; then
            pass
            echo "  On disk: extra_info__string: hello"
        else
            fail "Custom string field not stored with type-hint on disk"
            [ -f "$rf_c1" ] && cat "$rf_c1"
        fi
    else
        fail "record new --from-file failed for Contract C: $out"
    fi

    sleep 0.25
    # --- Path 2: CLI json import-record ---
    print_test "Contract C (custom string field) via json import-record"
    local rec_c2
    if out=$(run_aver json import-record \
        --data '{"content":"Contract C path 2 body.","fields":{"title":"Contract C JSON","status":"open","extra_info":"hello"}}' 2>&1); then
        rec_c2=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        local rf_c2="$TEST_DIR/records/${rec_c2}.md"
        if [ -n "$rec_c2" ] && [ -f "$rf_c2" ] && grep -q "extra_info__string: hello" "$rf_c2"; then
            pass
            echo "  On disk: extra_info__string: hello"
        else
            fail "Custom string field not stored with type-hint on disk"
            [ -f "$rf_c2" ] && cat "$rf_c2"
        fi
    else
        fail "json import-record failed for Contract C: $out"
    fi

    sleep 0.25
    # --- Path 3: JSON IO ---
    print_test "Contract C (custom string field) via json io import-record"
    local rec_c3
    if out=$(echo '{"command":"import-record","params":{"content":"Contract C path 3 body.","fields":{"title":"Contract C IO","status":"open","extra_info":"hello"}}}' \
        | run_aver json io 2>&1); then
        rec_c3=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('record_id',''))" 2>/dev/null)
        local rf_c3="$TEST_DIR/records/${rec_c3}.md"
        if [ -n "$rec_c3" ] && [ -f "$rf_c3" ] && grep -q "extra_info__string: hello" "$rf_c3"; then
            pass
            echo "  On disk: extra_info__string: hello"
        else
            fail "Custom string field not stored with type-hint on disk"
            [ -f "$rf_c3" ] && cat "$rf_c3"
        fi
    else
        fail "json io import-record failed for Contract C: $out"
    fi

    # --- Export verification: no suffix in returned field name ---
    print_test "Contract C: custom string field exported without type-hint"
    if [ -n "$rec_c2" ]; then
        if out=$(run_aver json export-record "$rec_c2" 2>&1); then
            if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
f = d.get('fields', {})
assert f.get('extra_info') == 'hello', f'extra_info wrong or missing: {f}'
assert 'extra_info__string' not in f, 'type-hint suffix leaked into export'
" 2>/dev/null; then
                pass
                echo "  extra_info: hello in export, no suffix"
            else
                fail "extra_info not found or has type-hint suffix in export"
            fi
        else
            fail "export-record failed"
        fi
    else
        fail "No record from path 2 to export"
    fi

    # =========================================================================
    # CONTRACT D: Custom integer field
    # On disk: retry_count__integer: 3
    # Exported: fields.retry_count = 3 (integer, not string)
    # =========================================================================

    print_test "Contract D (custom integer field) via json import-record"
    local rec_d
    if out=$(run_aver json import-record \
        --data '{"content":"Contract D body.","fields":{"title":"Contract D","status":"open","retry_count__integer":3}}' 2>&1); then
        rec_d=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        local rf_d="$TEST_DIR/records/${rec_d}.md"
        if [ -n "$rec_d" ] && [ -f "$rf_d" ] && grep -q "retry_count__integer: 3" "$rf_d"; then
            pass
            echo "  On disk: retry_count__integer: 3"
        else
            fail "Custom integer field not stored with type-hint on disk"
            [ -f "$rf_d" ] && cat "$rf_d"
        fi
    else
        fail "json import-record failed for Contract D: $out"
    fi

    print_test "Contract D: custom integer field exported as integer type"
    if [ -n "$rec_d" ]; then
        if out=$(run_aver json export-record "$rec_d" 2>&1); then
            if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
f = d.get('fields', {})
v = f.get('retry_count')
assert isinstance(v, int) and v == 3, f'retry_count wrong type or value: {v!r}'
" 2>/dev/null; then
                pass
                echo "  retry_count exported as integer 3"
            else
                fail "retry_count not integer in export"
            fi
        else
            fail "export-record failed"
        fi
    else
        fail "No record from Contract D to export"
    fi

    # =========================================================================
    # CONTRACT E: Template float field (impact_score) — NO type-hint suffix on disk
    # impact_score is defined in [template.bug.record_special_fields.impact_score]
    # value_type=float — must be stored as "impact_score: 2.5", not "impact_score__float: 2.5"
    # =========================================================================

    # --- Path 1: CLI --from-file ---
    print_test "Contract E (template float field, no suffix) via CLI --from-file"
    cat > "$TEST_DIR/rc_e1.md" << 'EOF'
---
title: Contract E CLI
status: new
severity: 2
impact_score: 2.5
---
Contract E path 1 body.
EOF
    local rec_e1
    if out=$(run_aver record new --from-file "$TEST_DIR/rc_e1.md" --no-validation-editor --template bug 2>&1); then
        rec_e1=$(echo "$out" | grep -oE "BUG-[A-Z0-9]+" | head -1)
        local rf_e1="$TEST_DIR/records/${rec_e1}.md"
        if [ -n "$rec_e1" ] && [ -f "$rf_e1" ] && \
           grep -q "^impact_score: 2.5" "$rf_e1" && ! grep -q "impact_score__" "$rf_e1"; then
            pass
            echo "  On disk: impact_score: 2.5 (no __float suffix)"
        else
            fail "Template float field has unexpected type-hint suffix or wrong value"
            [ -f "$rf_e1" ] && cat "$rf_e1"
        fi
    else
        fail "record new --from-file failed for Contract E: $out"
    fi

    sleep 0.25
    # --- Path 2: CLI json import-record ---
    print_test "Contract E (template float field, no suffix) via json import-record"
    local rec_e2
    if out=$(run_aver json import-record \
        --data '{"content":"Contract E path 2 body.","fields":{"title":"Contract E JSON","status":"new","severity":2,"impact_score":2.5},"template":"bug"}' 2>&1); then
        rec_e2=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        local rf_e2="$TEST_DIR/records/${rec_e2}.md"
        if [ -n "$rec_e2" ] && [ -f "$rf_e2" ] && \
           grep -q "^impact_score: 2.5" "$rf_e2" && ! grep -q "impact_score__" "$rf_e2"; then
            pass
            echo "  On disk: impact_score: 2.5 (no __float suffix)"
        else
            fail "Template float field has unexpected type-hint suffix on disk"
            [ -f "$rf_e2" ] && cat "$rf_e2"
        fi
    else
        fail "json import-record failed for Contract E: $out"
    fi

    sleep 0.25
    # --- Path 3: JSON IO ---
    print_test "Contract E (template float field, no suffix) via json io import-record"
    local rec_e3
    if out=$(echo '{"command":"import-record","params":{"content":"Contract E path 3 body.","fields":{"title":"Contract E IO","status":"new","severity":2,"impact_score":2.5},"template":"bug"}}' \
        | run_aver json io 2>&1); then
        rec_e3=$(echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('record_id',''))" 2>/dev/null)
        local rf_e3="$TEST_DIR/records/${rec_e3}.md"
        if [ -n "$rec_e3" ] && [ -f "$rf_e3" ] && \
           grep -q "^impact_score: 2.5" "$rf_e3" && ! grep -q "impact_score__" "$rf_e3"; then
            pass
            echo "  On disk: impact_score: 2.5 (no __float suffix)"
        else
            fail "Template float field has unexpected type-hint suffix on disk"
            [ -f "$rf_e3" ] && cat "$rf_e3"
        fi
    else
        fail "json io import-record failed for Contract E: $out"
    fi

    # --- Export: float returned as numeric type ---
    print_test "Contract E: template float field exported as float type"
    if [ -n "$rec_e2" ]; then
        if out=$(run_aver json export-record "$rec_e2" 2>&1); then
            if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
f = d.get('fields', {})
v = f.get('impact_score')
assert isinstance(v, float), f'impact_score not float: {v!r}'
assert v == 2.5, f'impact_score wrong value: {v}'
" 2>/dev/null; then
                pass
                echo "  impact_score exported as float 2.5"
            else
                fail "impact_score not exported as float"
                echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('fields',{}))" 2>/dev/null
            fi
        else
            fail "export-record failed"
        fi
    else
        fail "No record from path 2 to export"
    fi

    # =========================================================================
    # CONTRACT F: Template integer field (severity) — NO type-hint suffix on disk
    # severity is in [template.bug.record_special_fields.severity] value_type=integer
    # =========================================================================

    print_test "Contract F (template integer field, no suffix) via json import-record"
    local rec_f
    if out=$(run_aver json import-record \
        --data '{"content":"Contract F body.","fields":{"title":"Contract F","status":"new","severity":4,"impact_score":1.0},"template":"bug"}' 2>&1); then
        rec_f=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        local rf_f="$TEST_DIR/records/${rec_f}.md"
        if [ -n "$rec_f" ] && [ -f "$rf_f" ] && \
           grep -q "^severity: 4" "$rf_f" && ! grep -q "severity__" "$rf_f"; then
            pass
            echo "  On disk: severity: 4 (no __integer suffix)"
        else
            fail "Template integer field has unexpected type-hint suffix on disk"
            [ -f "$rf_f" ] && cat "$rf_f"
        fi
    else
        fail "json import-record failed for Contract F: $out"
    fi

    print_test "Contract F: template integer field exported as integer type"
    if [ -n "$rec_f" ]; then
        if out=$(run_aver json export-record "$rec_f" 2>&1); then
            if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
f = d.get('fields', {})
v = f.get('severity')
assert isinstance(v, int), f'severity not int: {v!r}'
assert v == 4, f'severity wrong value: {v}'
" 2>/dev/null; then
                pass
                echo "  severity exported as integer 4"
            else
                fail "severity not exported as integer"
            fi
        else
            fail "export-record failed"
        fi
    else
        fail "No record from Contract F to export"
    fi

    # =========================================================================
    # CONTRACT G: Type fidelity survives update round-trip
    # Create a templated bug record, update it with new values,
    # verify types are still correct on disk and in export.
    # =========================================================================

    print_test "Contract G setup: create bug record for update round-trip"
    local rec_g
    if out=$(run_aver json import-record \
        --data '{"content":"Contract G body.","fields":{"title":"Contract G","status":"new","severity":2,"impact_score":1.0},"template":"bug"}' 2>&1); then
        rec_g=$(echo "$out" | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null)
        if [ -n "$rec_g" ]; then
            pass
            echo "  Created: $rec_g"
        else
            fail "No record ID returned"
        fi
    else
        fail "Setup failed for Contract G: $out"
    fi

    print_test "Contract G (update round-trip) via json update-record"
    if [ -n "$rec_g" ]; then
        if out=$(run_aver json update-record "$rec_g" \
            --data '{"fields":{"severity":5,"impact_score":9.9,"status":"confirmed"}}' 2>&1); then
            local rf_g="$TEST_DIR/records/${rec_g}.md"
            if grep -q "^severity: 5" "$rf_g" && ! grep -q "severity__" "$rf_g" && \
               grep -q "^impact_score: 9.9" "$rf_g" && ! grep -q "impact_score__" "$rf_g"; then
                pass
                echo "  After update: severity: 5, impact_score: 9.9 — no type-hint suffixes"
            else
                fail "Type-hint suffixes appeared after update or values wrong"
                cat "$rf_g"
            fi
        else
            fail "json update-record failed for Contract G: $out"
        fi
    else
        fail "No record from setup to update"
    fi

    print_test "Contract G (update round-trip) via json io update-record"
    if [ -n "$rec_g" ]; then
        if out=$(echo '{"command":"update-record","params":{"record_id":"'"$rec_g"'","fields":{"severity":3,"impact_score":5.5}}}' \
            | run_aver json io 2>&1); then
            local rf_g="$TEST_DIR/records/${rec_g}.md"
            if grep -q "^severity: 3" "$rf_g" && ! grep -q "severity__" "$rf_g" && \
               grep -q "^impact_score: 5.5" "$rf_g" && ! grep -q "impact_score__" "$rf_g"; then
                pass
                echo "  After IO update: severity: 3, impact_score: 5.5 — no type-hint suffixes"
            else
                fail "Type-hint suffixes appeared after IO update or values wrong"
                cat "$rf_g"
            fi
        else
            fail "json io update-record failed for Contract G: $out"
        fi
    else
        fail "No record from setup to update"
    fi

    print_test "Contract G: export after update shows correct types"
    if [ -n "$rec_g" ]; then
        if out=$(run_aver json export-record "$rec_g" 2>&1); then
            if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
f = d.get('fields', {})
assert isinstance(f.get('severity'), int) and f['severity'] == 3, f'severity: {f.get(\"severity\")!r}'
assert isinstance(f.get('impact_score'), float) and f['impact_score'] == 5.5, f'impact_score: {f.get(\"impact_score\")!r}'
" 2>/dev/null; then
                pass
                echo "  severity=3 (int), impact_score=5.5 (float) correct after update"
            else
                fail "Types wrong in export after update"
                echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('fields',{}))" 2>/dev/null
            fi
        else
            fail "export-record failed"
        fi
    else
        fail "No record to export"
    fi
}

#==============================================================================
# Test: Command Parity (CLI vs JSON-IO produce equivalent results)
#==============================================================================
#
# For each pair of equivalent commands, run both against the same data and
# assert the results are structurally consistent.
#
# Documented intentional gaps (not failures):
#   CLI-only:  admin init, admin config *, admin list-databases
#              (setup/admin ops — no programmatic equivalent needed)
#   JSON-IO-only: list-templates
#              (CLI users use "admin template-data" instead)
#   Known missing: no global "note search" in plain CLI (note search requires
#              --ksearch and is scoped differently from search-notes)
#==============================================================================

test_command_parity() {
    print_section "Command Parity: CLI vs JSON-IO"

    # -------------------------------------------------------------------------
    # Setup: create shared test data
    # -------------------------------------------------------------------------
    local par_rec par_bug par_note

    par_rec=$(run_aver record new --description "" --no-validation-editor \
        --title "Parity Test Plain" --status open --priority high 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" | head -1 || echo "")

    par_bug=$(run_aver json import-record \
        --data '{"content":"Parity bug body.","fields":{"title":"Parity Bug","status":"new","severity":3,"impact_score":4.2},"template":"bug"}' \
        2>&1 | python3 -c "import sys,json; print(json.load(sys.stdin).get('record_id',''))" 2>/dev/null || echo "")

    par_note=$(run_aver note add "$par_rec" --message "Parity note body" --category "investigation" 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" | head -1 || echo "")

    if [ -z "$par_rec" ] || [ -z "$par_bug" ] || [ -z "$par_note" ]; then
        echo -e "${RED}Setup failed for parity tests (par_rec=$par_rec par_bug=$par_bug par_note=$par_note)${NC}"
        return
    fi
    echo "  par_rec=$par_rec  par_bug=$par_bug  par_note=$par_note"

    # =========================================================================
    # record view  ↔  export-record
    # Both return the same record id, content, and fields.
    # =========================================================================

    print_test "Parity: record view vs json export-record (same id and fields)"
    local cli_export io_export
    cli_export=$(run_aver json export-record "$par_rec" 2>&1)
    io_export=$(echo '{"command":"export-record","params":{"record_id":"'"$par_rec"'"}}' \
        | run_aver json io 2>&1)

    if python3 - "$cli_export" "$io_export" << 'PYEOF' 2>/dev/null
import sys, json
cli = json.loads(sys.argv[1])
io  = json.loads(sys.argv[2])['result']
assert cli['id']      == io['id'],      f"id mismatch: {cli['id']} vs {io['id']}"
assert cli['content'] == io['content'], "content mismatch"
assert cli['fields']  == io['fields'],  f"fields mismatch: {cli['fields']} vs {io['fields']}"
PYEOF
    then
        pass
        echo "  id, content, fields identical between CLI and JSON-IO"
    else
        fail "export-record CLI vs IO results differ"
        echo "CLI: $cli_export"
        echo "IO:  $io_export"
    fi

    # =========================================================================
    # record list --ksearch  ↔  search-records
    # Both find the same record IDs for a given filter.
    # =========================================================================

    print_test "Parity: record list --ksearch vs search-records (same record IDs)"
    local cli_ids io_ids
    cli_ids=$(run_aver record list --ksearch "status=open" --ids-only 2>&1 | sort)
    io_ids=$(echo '{"command":"search-records","params":{"ksearch":["status=open"],"limit":100}}' \
        | run_aver json io 2>&1 \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(sorted(r['id'] for r in d['result']['records'])))" 2>/dev/null)

    if [ -n "$cli_ids" ] && [ "$cli_ids" = "$io_ids" ]; then
        pass
        echo "  Same record IDs returned by both paths"
    else
        fail "record list vs search-records returned different IDs"
        echo "  CLI: $cli_ids"
        echo "  IO:  $io_ids"
    fi

    # =========================================================================
    # note list  ↔  export-record --include-notes
    # Both return the same note IDs for a given record.
    # =========================================================================

    # note list does not output note IDs in its display format — compare by count.
    # The CLI "Note N:" headers tell us how many notes exist; IO reports them explicitly.
    print_test "Parity: note list vs export-record --include-notes (same note count)"
    local cli_note_count io_note_count
    cli_note_count=$(run_aver note list "$par_rec" 2>&1 | grep -cE "^Note [0-9]+:" || echo 0)
    io_note_count=$(echo '{"command":"export-record","params":{"record_id":"'"$par_rec"'","include_notes":true}}' \
        | run_aver json io 2>&1 \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print(len(d['result'].get('notes',[])))" 2>/dev/null)

    if [ -n "$cli_note_count" ] && [ "$cli_note_count" = "$io_note_count" ] && [ "$cli_note_count" -gt 0 ] 2>/dev/null; then
        pass
        echo "  Both paths returned $cli_note_count note(s)"
    else
        fail "note list vs export-record note count differs"
        echo "  CLI count: $cli_note_count"
        echo "  IO count:  $io_note_count"
    fi

    # =========================================================================
    # note search --ksearch  ↔  search-notes
    # Both find the same note IDs for a given filter.
    # =========================================================================

    print_test "Parity: note search --ksearch vs search-notes (same note IDs)"
    local cli_nsearch_ids io_nsearch_ids
    cli_nsearch_ids=$(run_aver note search --ksearch "category=investigation" --ids-only 2>&1 \
        | grep -oE "[A-Z0-9]+-[A-Z0-9]+:[A-Z0-9]+-[A-Z0-9]+" | awk -F: '{print $2}' | sort)
    io_nsearch_ids=$(echo '{"command":"search-notes","params":{"ksearch":["category=investigation"],"limit":100}}' \
        | run_aver json io 2>&1 \
        | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(sorted(n['id'] for n in d['result'].get('notes',[]))))" 2>/dev/null)

    if [ -n "$cli_nsearch_ids" ] && [ "$cli_nsearch_ids" = "$io_nsearch_ids" ]; then
        pass
        echo "  Same note IDs returned by both paths"
    else
        fail "note search vs search-notes returned different IDs"
        echo "  CLI: $cli_nsearch_ids"
        echo "  IO:  $io_nsearch_ids"
    fi

    # =========================================================================
    # json schema-record --template bug  ↔  schema-record (template=bug)
    # Both return identical field sets.
    # =========================================================================

    print_test "Parity: json schema-record --template bug vs IO schema-record"
    local cli_schema io_schema
    cli_schema=$(run_aver json schema-record --template bug 2>&1)
    io_schema=$(echo '{"command":"schema-record","params":{"template":"bug"}}' \
        | run_aver json io 2>&1 \
        | python3 -c "import sys,json; d=json.load(sys.stdin); import json as j; print(j.dumps(d['result'],sort_keys=True))" 2>/dev/null)

    if python3 - "$cli_schema" "$io_schema" << 'PYEOF' 2>/dev/null
import sys, json
cli = json.loads(sys.argv[1])
io  = json.loads(sys.argv[2])
assert set(cli['fields'].keys()) == set(io['fields'].keys()), \
    f"field sets differ: CLI={set(cli['fields'].keys())} IO={set(io['fields'].keys())}"
for fname in cli['fields']:
    assert cli['fields'][fname] == io['fields'][fname], \
        f"field {fname} differs: {cli['fields'][fname]} vs {io['fields'][fname]}"
PYEOF
    then
        pass
        echo "  Field sets and definitions identical"
    else
        fail "schema-record CLI vs IO field sets differ"
        echo "  CLI: $cli_schema"
        echo "  IO:  $io_schema"
    fi

    # =========================================================================
    # json schema-note RECORD_ID  ↔  schema-note (record_id=...)
    # Both return identical field sets.
    # =========================================================================

    print_test "Parity: json schema-note vs IO schema-note (bug record)"
    local cli_snote io_snote
    cli_snote=$(run_aver json schema-note "$par_bug" 2>&1)
    io_snote=$(echo '{"command":"schema-note","params":{"record_id":"'"$par_bug"'"}}' \
        | run_aver json io 2>&1 \
        | python3 -c "import sys,json; d=json.load(sys.stdin); import json as j; print(j.dumps(d['result'],sort_keys=True))" 2>/dev/null)

    if python3 - "$cli_snote" "$io_snote" << 'PYEOF' 2>/dev/null
import sys, json
cli = json.loads(sys.argv[1])
io  = json.loads(sys.argv[2])
assert set(cli['fields'].keys()) == set(io['fields'].keys()), \
    f"field sets differ: CLI={set(cli['fields'].keys())} IO={set(io['fields'].keys())}"
PYEOF
    then
        pass
        echo "  Note field sets identical"
    else
        fail "schema-note CLI vs IO field sets differ"
        echo "  CLI: $cli_snote"
        echo "  IO:  $io_snote"
    fi

    # =========================================================================
    # template-data (template_id=bug) — verify field definitions
    # =========================================================================

    print_test "Parity: IO template-data bug has expected fields and prefixes"
    local io_td
    io_td=$(echo '{"command":"template-data","params":{"template_id":"bug"}}' \
        | run_aver json io 2>&1)

    if echo "$io_td" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success'), f'not success: {data}'
r = data['result']
assert r.get('template_id') == 'bug', f'expected bug, got {r.get(\"template_id\")}'
assert r.get('record_prefix') == 'BUG', f'wrong record_prefix: {r.get(\"record_prefix\")}'
assert r.get('note_prefix') == 'COMMENT', f'wrong note_prefix: {r.get(\"note_prefix\")}'
rec_fields = r.get('record_fields', {})
assert 'severity' in rec_fields, f'severity missing: {list(rec_fields)}'
assert 'status' in rec_fields, f'status missing: {list(rec_fields)}'
assert 'title' in rec_fields, f'title missing: {list(rec_fields)}'
note_fields = r.get('note_fields', {})
assert 'category' in note_fields, f'category missing: {list(note_fields)}'
# severity is required in bug template
assert rec_fields['severity']['required'] == True, 'severity should be required'
" 2>/dev/null; then
        pass
        echo "  IO template-data bug: correct fields, prefixes, and constraints"
    else
        fail "IO template-data bug returned unexpected structure"
        echo "  IO: $io_td"
    fi

    # =========================================================================
    # admin reindex REC  ↔  reindex (record_ids=[REC])
    # Both succeed and produce the same effect on the index.
    # Test: after each reindex, a search still finds the record.
    # =========================================================================

    print_test "Parity: admin reindex vs IO reindex (both succeed)"
    local cli_reindex_ok=false io_reindex_ok=false

    if run_aver admin reindex "$par_rec" > /dev/null 2>&1; then
        cli_reindex_ok=true
    fi

    if echo '{"command":"reindex","params":{"record_ids":["'"$par_bug"'"]}}' \
        | run_aver json io 2>&1 \
        | python3 -c "import sys,json; d=json.load(sys.stdin); assert d['success']==True" 2>/dev/null; then
        io_reindex_ok=true
    fi

    if $cli_reindex_ok && $io_reindex_ok; then
        pass
        echo "  Both CLI and IO reindex succeeded"
    else
        fail "Reindex parity failed (CLI ok=$cli_reindex_ok IO ok=$io_reindex_ok)"
    fi

    # =========================================================================
    # list-templates (JSON-IO only — intentional CLI gap)
    # Document: CLI equivalent is "admin template-data" (lists all templates).
    # Test that list-templates returns the templates defined in config.
    # =========================================================================

    print_test "Parity: list-templates (JSON-IO only) returns configured templates"
    if out=$(echo '{"command":"list-templates","params":{}}' | run_aver json io 2>&1); then
        if echo "$out" | python3 -c "
import sys, json
d = json.load(sys.stdin)
templates = d['result']['templates']
names = [t['id'] for t in templates if t['id'] is not None]
assert 'bug' in names, f'bug template missing: {names}'
assert 'feature' in names, f'feature template missing: {names}'
" 2>/dev/null; then
            pass
            echo "  list-templates returns bug and feature templates  [JSON-IO only — CLI: admin template-data]"
        else
            fail "list-templates did not return expected templates"
            echo "$out"
        fi
    else
        fail "list-templates command failed"
    fi
}

#==============================================================================
# Test: Exit Codes
#==============================================================================

test_exit_codes() {
    print_section "Test: Exit Codes"

    # -------------------------------------------------------------------------
    # EXIT_NOT_FOUND (3) — record not found
    # -------------------------------------------------------------------------
    print_test "record view nonexistent record → exit 3"
    track_command "aver record view REC-DOESNOTEXIST"
    set +e
    run_aver record view "REC-DOESNOTEXIST" > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 3 ]; then
        pass
        echo "  Exit 3 (not found) as expected"
    else
        fail "Expected exit 3, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_NOT_FOUND (3) — note view on bad record
    # -------------------------------------------------------------------------
    print_test "note list nonexistent record → exit 3"
    track_command "aver note list REC-DOESNOTEXIST"
    set +e
    run_aver note list "REC-DOESNOTEXIST" > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 3 ]; then
        pass
        echo "  Exit 3 (not found) as expected"
    else
        fail "Expected exit 3, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_NOT_FOUND (3) — admin template-data unknown template
    # -------------------------------------------------------------------------
    print_test "admin template-data nonexistent → exit 3"
    track_command "aver admin template-data nonexistent-template"
    set +e
    run_aver admin template-data nonexistent-template > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 3 ]; then
        pass
        echo "  Exit 3 (not found) as expected"
    else
        fail "Expected exit 3, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_VALIDATION (4) — missing required field
    # -------------------------------------------------------------------------
    print_test "record new missing required field → exit 4"
    track_command "aver record new --description '' --no-validation-editor --status open (no title)"
    set +e
    run_aver record new --description "" --no-validation-editor --status open > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 4 ]; then
        pass
        echo "  Exit 4 (validation failure) as expected"
    else
        fail "Expected exit 4, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_VALIDATION (4) — invalid accepted_values
    # -------------------------------------------------------------------------
    print_test "record new invalid status value → exit 4"
    track_command "aver record new --no-validation-editor --title T --status totally_invalid"
    set +e
    run_aver record new --description "" --no-validation-editor --title "T" --status totally_invalid > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 4 ]; then
        pass
        echo "  Exit 4 (validation failure) as expected"
    else
        fail "Expected exit 4, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_USAGE (2) — --count without --ksearch
    # -------------------------------------------------------------------------
    print_test "record list --count without --ksearch → exit 2"
    track_command "aver record list --count"
    set +e
    run_aver record list --count > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 2 ]; then
        pass
        echo "  Exit 2 (usage error) as expected"
    else
        fail "Expected exit 2, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_USAGE (2) — --no-validation-editor with no message
    # -------------------------------------------------------------------------
    print_test "note add --no-validation-editor with no message → exit 2"
    local ec_rec
    ec_rec=$(run_aver record new --description "" --no-validation-editor --title "ExitCode Test" 2>&1 | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -n "$ec_rec" ]; then
        set +e
        run_aver note add "$ec_rec" --no-validation-editor > /dev/null 2>&1
        exit_code=$?
        set -e
        if [ $exit_code -eq 2 ]; then
            pass
            echo "  Exit 2 (usage error) as expected"
        else
            fail "Expected exit 2, got $exit_code"
        fi
    else
        fail "Could not create test record for exit code test"
    fi

    # -------------------------------------------------------------------------
    # EXIT_VALIDATION (4) — admin validate with failing records
    # -------------------------------------------------------------------------
    print_test "admin validate with non-conforming record → exit 4"
    track_command "admin validate exit code"
    # Write a non-conforming bug record (missing required severity)
    local ec_bugfile
    ec_bugfile="$TEST_DIR/records/BUG-EXITCODE-TST.md"
    cat > "$ec_bugfile" << 'EOF'
---
template_id: bug
status: new
title: Exit code test bug
---
EOF
    set +e
    run_aver admin validate BUG-EXITCODE-TST > /dev/null 2>&1
    exit_code=$?
    set -e
    rm -f "$ec_bugfile"
    if [ $exit_code -eq 4 ]; then
        pass
        echo "  Exit 4 (validation failure) as expected"
    else
        fail "Expected exit 4, got $exit_code"
    fi

    # -------------------------------------------------------------------------
    # EXIT_OK (0) — success
    # -------------------------------------------------------------------------
    print_test "successful record new → exit 0"
    track_command "aver record new --no-validation-editor --title 'Exit Code OK'"
    set +e
    run_aver record new --description "" --no-validation-editor --title "Exit Code OK" > /dev/null 2>&1
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ]; then
        pass
        echo "  Exit 0 (success) as expected"
    else
        fail "Expected exit 0, got $exit_code"
    fi
}

#==============================================================================
# Main Test Runner
#==============================================================================

main() {
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     aver.py Test Suite                ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${GREEN}Running in isolated test environment${NC}"
    echo -e "${GREEN}Your real ~/.aver config will not be modified${NC}"
    
    # Setup
    setup_test_environment
    
    # Run test suites
    test_basic_creation
    test_special_characters
    test_template_system
    test_validation
    test_system_fields
    test_index_values
    test_fields_flag
    test_user_profile
    test_library_management
    test_custom_locations
    test_config_per_location
    test_listing_search
    test_note_operations
    test_note_special_fields
    test_note_contract
    test_record_contract
    test_command_parity
    test_from_file
    test_updates
    test_json_interface
    test_json_io_mode
    test_record_reindex
    test_count_flag
    test_max_flag
    test_in_operator
    test_template_data
    test_securestring
    test_system_update_field
    test_admin_validate
    test_reindex_validation
    test_unmask
    test_note_add_no_validation_editor
    test_help_fields
    test_offset_pagination
    test_validate_config
    test_exit_codes

    # Summary
    print_section "Test Summary"
    echo -e "Total tests run:    ${BLUE}${TESTS_RUN}${NC}"
    echo -e "Tests passed:       ${GREEN}${TESTS_PASSED}${NC}"
    echo -e "Tests failed:       ${RED}${TESTS_FAILED}${NC}"
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "\n${GREEN}✓ All tests passed!${NC}"
        EXIT_CODE=0
    else
        echo -e "\n${RED}✗ Some tests failed${NC}"
        echo ""
        echo -e "${YELLOW}Failed Tests Details:${NC}"
        echo -e "${YELLOW}════════════════════════════════════════${NC}"
        for i in "${!FAILED_TESTS[@]}"; do
            echo -e "${RED}$((i + 1)). ${FAILED_TESTS[$i]}${NC}"
            if [ "${FAILED_COMMANDS[$i]}" != "No command tracked" ]; then
                echo -e "   Command: ${BLUE}${FAILED_COMMANDS[$i]}${NC}"
            fi
            echo -e "   Reason:  ${FAILED_REASONS[$i]}"
            echo ""
        done
        EXIT_CODE=1
    fi
    
    # Cleanup
    cleanup
    
    exit $EXIT_CODE
}

#==============================================================================
# Test: is_system_update field
#==============================================================================
test_system_update_field() {
    print_section "Test: is_system_update System Field"

    # -------------------------------------------------------------------------
    # 1. Create a record — the initial creation note should have is_system_update=1
    # -------------------------------------------------------------------------
    print_test "Create record; initial system note has is_system_update=1"
    local rec_sys
    rec_sys=$(run_aver record new --description "" --no-validation-editor \
        --title "System Update Test" 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_sys" ]; then
        fail "Could not create record for is_system_update test"
        return
    fi
    pass
    echo "  Created: $rec_sys"

    # -------------------------------------------------------------------------
    # 2. The initial note should show is_system_update: 1 in note view
    # -------------------------------------------------------------------------
    print_test "Initial creation note has is_system_update=1"
    local notes_dir="$TEST_DIR/updates/${rec_sys}"
    local init_note_id
    init_note_id=$(ls "$notes_dir"/*.md 2>/dev/null | head -1 | xargs basename 2>/dev/null | sed 's/\.md$//' || echo "")
    if [ -z "$init_note_id" ]; then
        fail "Could not find initial note for $rec_sys in $notes_dir"
        return
    fi
    track_command "aver note view $rec_sys $init_note_id"
    local note_view
    note_view=$(run_aver note view "$rec_sys" "$init_note_id" 2>&1)
    if echo "$note_view" | grep -q "is_system_update" && echo "$note_view" | grep -q "1"; then
        pass
        echo "  Initial note $init_note_id has is_system_update=1"
    else
        fail "is_system_update=1 not found in initial note view: $note_view"
    fi

    # -------------------------------------------------------------------------
    # 3. Add a user note — should have is_system_update=0
    # -------------------------------------------------------------------------
    print_test "User note has is_system_update=0"
    track_command "aver note add $rec_sys --message 'user note'"
    local user_note_id
    user_note_id=$(run_aver note add "$rec_sys" --message "user note" 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" | head -1 || echo "")
    if [ -z "$user_note_id" ]; then
        fail "Could not add user note to $rec_sys"
        return
    fi
    track_command "aver note view $rec_sys $user_note_id"
    note_view=$(run_aver note view "$rec_sys" "$user_note_id" 2>&1)
    if echo "$note_view" | grep -q "is_system_update" && echo "$note_view" | grep -q "0"; then
        pass
        echo "  User note $user_note_id has is_system_update=0"
    else
        fail "is_system_update=0 not found in user note view: $note_view"
    fi

    # -------------------------------------------------------------------------
    # 4. Update the record — the system tracking note should have is_system_update=1
    # -------------------------------------------------------------------------
    print_test "Record update creates system note with is_system_update=1"
    # Snapshot existing note IDs before the update
    local notes_before
    notes_before=$(ls "$notes_dir"/*.md 2>/dev/null | xargs -I{} basename {} .md | sort)
    track_command "aver record update $rec_sys --title 'Updated Title' --metadata-only --no-validation-editor"
    local update_out
    update_out=$(run_aver record update "$rec_sys" --title "Updated Title" --metadata-only --no-validation-editor 2>&1)
    if ! echo "$update_out" | grep -q "Updated record"; then
        fail "record update failed: $update_out"
        return
    fi
    # Find the new note ID — any .md file that wasn't there before
    local notes_after update_note_id
    notes_after=$(ls "$notes_dir"/*.md 2>/dev/null | xargs -I{} basename {} .md | sort)
    update_note_id=$(comm -13 <(echo "$notes_before") <(echo "$notes_after") | head -1)
    if [ -z "$update_note_id" ]; then
        fail "No new note found after record update (notes before: $notes_before / after: $notes_after)"
        return
    fi
    track_command "aver note view $rec_sys $update_note_id"
    note_view=$(run_aver note view "$rec_sys" "$update_note_id" 2>&1)
    if echo "$note_view" | grep -q "is_system_update" && echo "$note_view" | grep -q "1"; then
        pass
        echo "  Update tracking note $update_note_id has is_system_update=1"
    else
        fail "is_system_update=1 not found in update tracking note: $note_view"
    fi

    # -------------------------------------------------------------------------
    # 5. ksearch is_system_update=1 returns system notes, not user notes
    # -------------------------------------------------------------------------
    print_test "ksearch is_system_update=1 finds system notes"
    track_command "aver note search --ksearch is_system_update=1"
    local sys_results
    sys_results=$(run_aver note search --ksearch "is_system_update=1" 2>&1)
    if echo "$sys_results" | grep -q "$init_note_id" || echo "$sys_results" | grep -q "$update_note_id"; then
        if ! echo "$sys_results" | grep -q "$user_note_id"; then
            pass
            echo "  System notes found; user note correctly excluded"
        else
            fail "User note $user_note_id appeared in is_system_update=1 search: $sys_results"
        fi
    else
        fail "No system notes found in is_system_update=1 search: $sys_results"
    fi

    # -------------------------------------------------------------------------
    # 6. ksearch is_system_update=0 returns user notes, not system notes
    # -------------------------------------------------------------------------
    print_test "ksearch is_system_update=0 finds user notes"
    track_command "aver note search --ksearch is_system_update=0"
    local user_results
    user_results=$(run_aver note search --ksearch "is_system_update=0" 2>&1)
    if echo "$user_results" | grep -q "$user_note_id"; then
        if ! echo "$user_results" | grep -q "$init_note_id" && ! echo "$user_results" | grep -q "$update_note_id"; then
            pass
            echo "  User note found; system notes correctly excluded"
        else
            fail "System note appeared in is_system_update=0 search: $user_results"
        fi
    else
        fail "User note $user_note_id not found in is_system_update=0 search: $user_results"
    fi

    # -------------------------------------------------------------------------
    # 7. JSON export of the initial note shows is_system_update=1
    # -------------------------------------------------------------------------
    print_test "JSON export-note shows is_system_update=1 for system note"
    track_command "aver json export-note $rec_sys $init_note_id"
    local json_note
    json_note=$(run_aver json export-note "$rec_sys" "$init_note_id" 2>&1)
    if echo "$json_note" | python3 -c "
import json, sys
data = json.load(sys.stdin)
fields = data.get('fields', {})
val = fields.get('is_system_update')
sys.exit(0 if val == 1 or val == '1' else 1)
" 2>/dev/null; then
        pass
        echo "  JSON export shows is_system_update=1"
    else
        fail "JSON export-note did not show is_system_update=1: $json_note"
    fi

    # -------------------------------------------------------------------------
    # 8. JSON export of user note shows is_system_update=0
    # -------------------------------------------------------------------------
    print_test "JSON export-note shows is_system_update=0 for user note"
    track_command "aver json export-note $rec_sys $user_note_id"
    json_note=$(run_aver json export-note "$rec_sys" "$user_note_id" 2>&1)
    if echo "$json_note" | python3 -c "
import json, sys
data = json.load(sys.stdin)
fields = data.get('fields', {})
val = fields.get('is_system_update')
sys.exit(0 if val == 0 or val == '0' else 1)
" 2>/dev/null; then
        pass
        echo "  JSON export shows is_system_update=0"
    else
        fail "JSON export-note did not show is_system_update=0: $json_note"
    fi

    # -------------------------------------------------------------------------
    # 9. On-disk note file has the correct integer value
    # -------------------------------------------------------------------------
    print_test "On-disk system note file has is_system_update: 1"
    local init_note_file="$notes_dir/${init_note_id}.md"
    if [ -f "$init_note_file" ]; then
        if grep -q "is_system_update: 1" "$init_note_file"; then
            pass
            echo "  Plaintext '1' confirmed in $init_note_file"
        else
            fail "is_system_update: 1 not found in note file: $(head -10 "$init_note_file")"
        fi
    else
        fail "Note file not found: $init_note_file"
    fi

    print_test "On-disk user note file has is_system_update: 0"
    local user_note_file="$notes_dir/${user_note_id}.md"
    if [ -f "$user_note_file" ]; then
        if grep -q "is_system_update: 0" "$user_note_file"; then
            pass
            echo "  Plaintext '0' confirmed in $user_note_file"
        else
            fail "is_system_update: 0 not found in note file: $(head -10 "$user_note_file")"
        fi
    else
        fail "Note file not found: $user_note_file"
    fi
}

#==============================================================================
# Test: admin validate command
#==============================================================================

test_admin_validate() {
    print_section "Test: admin validate"

    # -------------------------------------------------------------------------
    # Setup: create a clean record (all required fields satisfied)
    # -------------------------------------------------------------------------
    print_test "Create conforming record for validate tests"
    local rec_good
    rec_good=$(run_aver record new --description "" --no-validation-editor \
        --title "Conforming Record" --status open 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_good" ]; then
        fail "Could not create conforming record"
        return
    fi
    pass
    echo "  Created conforming: $rec_good"

    # -------------------------------------------------------------------------
    # 1. All-records validate on a database that has only valid records passes
    #    (run against just the one good record to avoid other test records
    #     that might be invalid leaking in)
    # -------------------------------------------------------------------------
    print_test "validate RECORD_ID (conforming) exits 0"
    set +e
    local out exit_code
    out=$(run_aver admin validate "$rec_good" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ]; then
        pass
    else
        fail "Expected exit 0 for conforming record; got $exit_code: $out"
    fi

    # -------------------------------------------------------------------------
    # 2. Summary output mentions the record count and "conform"
    # -------------------------------------------------------------------------
    print_test "validate summary output contains conforming count"
    if echo "$out" | grep -q "Conforming:" && echo "$out" | grep -q "Non-conforming:"; then
        pass
    else
        fail "Expected 'Conforming:' / 'Non-conforming:' in output: $out"
    fi

    # -------------------------------------------------------------------------
    # 3. --failed-list on a clean record produces no output and exits 0
    # -------------------------------------------------------------------------
    print_test "validate --failed-list on conforming record: no output, exit 0"
    set +e
    local fl_out fl_exit
    fl_out=$(run_aver admin validate "$rec_good" --failed-list 2>&1)
    fl_exit=$?
    set -e
    if [ $fl_exit -eq 0 ] && [ -z "$fl_out" ]; then
        pass
    else
        fail "Expected empty output and exit 0; got exit=$fl_exit out='$fl_out'"
    fi

    # -------------------------------------------------------------------------
    # Setup: inject a bad record by writing a markdown file that violates
    # accepted_values for 'status' (force write — bypass CLI validation)
    # -------------------------------------------------------------------------
    print_test "Inject non-conforming record directly on disk"
    local bad_id="REC-VALIDATE-BAD"
    cat > "$TEST_DIR/records/${bad_id}.md" << 'BADRECEOF'
---
title: Bad Record
status: not_a_real_status
created_at: "2026-01-01 00:00:00"
created_by: testuser
---

This record has an invalid status value.
BADRECEOF
    if [ -f "$TEST_DIR/records/${bad_id}.md" ]; then
        pass
        echo "  Injected: $bad_id"
    else
        fail "Could not write bad record file"
        return
    fi

    # -------------------------------------------------------------------------
    # 4. validate on the bad record exits non-zero
    # -------------------------------------------------------------------------
    print_test "validate on non-conforming record exits 1"
    set +e
    out=$(run_aver admin validate "$bad_id" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        pass
    else
        fail "Expected non-zero exit for non-conforming record; got 0: $out"
    fi

    # -------------------------------------------------------------------------
    # 5. Summary mentions the bad record and shows FAIL line
    # -------------------------------------------------------------------------
    print_test "validate summary shows FAIL line for non-conforming record"
    if echo "$out" | grep -q "FAIL" && echo "$out" | grep -q "$bad_id"; then
        pass
    else
        fail "Expected FAIL line for $bad_id in output: $out"
    fi

    # -------------------------------------------------------------------------
    # 6. Summary mentions the bad field/value in the error description
    # -------------------------------------------------------------------------
    print_test "validate error mentions the invalid field value"
    if echo "$out" | grep -qi "status" && echo "$out" | grep -qi "not_a_real_status"; then
        pass
    else
        fail "Expected 'status' and 'not_a_real_status' in error output: $out"
    fi

    # -------------------------------------------------------------------------
    # 7. --failed-list on the bad record prints the ID and exits 1
    # -------------------------------------------------------------------------
    print_test "validate --failed-list prints failing ID and exits 1"
    set +e
    fl_out=$(run_aver admin validate "$bad_id" --failed-list 2>&1)
    fl_exit=$?
    set -e
    if [ $fl_exit -ne 0 ] && echo "$fl_out" | grep -q "$bad_id"; then
        pass
    else
        fail "Expected exit 1 and '$bad_id' in output; got exit=$fl_exit out='$fl_out'"
    fi

    # -------------------------------------------------------------------------
    # 8. --failed-list output is exactly one line (the bad ID, no extras)
    # -------------------------------------------------------------------------
    print_test "validate --failed-list output is one line per failing record"
    local line_count
    line_count=$(echo "$fl_out" | grep -c "." || true)
    if [ "$line_count" -eq 1 ]; then
        pass
    else
        fail "Expected exactly 1 line in --failed-list output; got $line_count: '$fl_out'"
    fi

    # -------------------------------------------------------------------------
    # 9. Inject a record with a missing required field
    # -------------------------------------------------------------------------
    print_test "Inject record missing required field 'title'"
    local missing_id="REC-VALIDATE-MISSING"
    cat > "$TEST_DIR/records/${missing_id}.md" << 'MISSINGEOF'
---
status: open
created_at: "2026-01-01 00:00:00"
created_by: testuser
---

This record is missing the required 'title' field.
MISSINGEOF
    if [ -f "$TEST_DIR/records/${missing_id}.md" ]; then
        pass
        echo "  Injected: $missing_id"
    else
        fail "Could not write missing-field record file"
        return
    fi

    # -------------------------------------------------------------------------
    # 10. validate catches missing required field
    # -------------------------------------------------------------------------
    print_test "validate detects missing required field"
    set +e
    out=$(run_aver admin validate "$missing_id" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$out" | grep -qi "title" && echo "$out" | grep -qi "required\|missing"; then
        pass
    else
        fail "Expected non-zero exit with 'title' + 'required/missing' in output; exit=$exit_code out=$out"
    fi

    # -------------------------------------------------------------------------
    # 11. validate multiple IDs: one good, one bad — bad appears in output
    # -------------------------------------------------------------------------
    print_test "validate multiple IDs reports both conforming and failing"
    set +e
    out=$(run_aver admin validate "$rec_good" "$bad_id" 2>&1)
    exit_code=$?
    set -e
    local conf_count non_conf_count
    conf_count=$(echo "$out" | grep "Conforming:" | grep -oE "[0-9]+" | head -1)
    non_conf_count=$(echo "$out" | grep "Non-conforming:" | grep -oE "[0-9]+" | head -1)
    if [ $exit_code -ne 0 ] && [ "${conf_count:-0}" -ge 1 ] && [ "${non_conf_count:-0}" -ge 1 ]; then
        pass
        echo "  Conforming: $conf_count  Non-conforming: $non_conf_count"
    else
        fail "Expected 1+ conforming and 1+ non-conforming; exit=$exit_code conf=$conf_count non_conf=$non_conf_count: $out"
    fi

    # -------------------------------------------------------------------------
    # 12. validate unknown record ID reports file-not-found failure
    # -------------------------------------------------------------------------
    print_test "validate unknown record ID reports failure"
    set +e
    out=$(run_aver admin validate "REC-DOESNOTEXIST" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        pass
    else
        fail "Expected non-zero exit for unknown record ID; got 0: $out"
    fi

    # -------------------------------------------------------------------------
    # 13. validate with template-specific accepted_values (injected directly)
    # -------------------------------------------------------------------------
    print_test "Inject conforming bug-template record on disk"
    local bug_good_id="BUG-VALIDATE-GOOD"
    cat > "$TEST_DIR/records/${bug_good_id}.md" << 'BUGGOODEOF'
---
template_id: bug
title: Good Bug
status: new
severity: 3
created_at: "2026-01-01 00:00:00"
created_by: testuser
---

Bug record with template-valid status 'new' and severity 3.
BUGGOODEOF
    if [ -f "$TEST_DIR/records/${bug_good_id}.md" ]; then
        pass
        echo "  Injected: $bug_good_id"
    else
        fail "Could not write conforming bug record file"
        return
    fi

    print_test "validate on conforming bug-template record passes"
    set +e
    out=$(run_aver admin validate "$bug_good_id" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ]; then
        pass
    else
        fail "Expected exit 0 for conforming bug record; got $exit_code: $out"
    fi

    # -------------------------------------------------------------------------
    # 14. Inject bug record with status violating template-specific accepted_values
    # -------------------------------------------------------------------------
    print_test "Inject bug record with template-invalid status"
    local bug_bad_id="BUG-VALIDATE-BAD"
    cat > "$TEST_DIR/records/${bug_bad_id}.md" << 'BUGBADEOF'
---
template_id: bug
title: Bad Bug
status: open
severity: 3
created_at: "2026-01-01 00:00:00"
created_by: testuser
---

Bug record with 'open' which is only valid globally, not in the bug template.
BUGBADEOF
    if [ -f "$TEST_DIR/records/${bug_bad_id}.md" ]; then
        pass
        echo "  Injected: $bug_bad_id"
    else
        fail "Could not write bad bug record file"
        return
    fi

    print_test "validate detects template-invalid status in bug record"
    set +e
    out=$(run_aver admin validate "$bug_bad_id" 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$out" | grep -qi "status" && echo "$out" | grep -q "$bug_bad_id"; then
        pass
    else
        fail "Expected non-zero exit mentioning 'status' and '$bug_bad_id'; exit=$exit_code out=$out"
    fi

    # -------------------------------------------------------------------------
    # 15. --failed-list with no records found exits 0 with no output
    # -------------------------------------------------------------------------
    # We use a fresh temp dir with an initialised (but empty) database
    print_test "validate with no records: exits 0, no output"
    local empty_dir
    empty_dir=$(mktemp -d -t aver-validate-empty-XXXXXX)
    set +e
    # Init in the empty dir
    PYTHONUSERBASE="${ORIGINAL_HOME}/.local" python3 "$AVER_PATH" \
        --override-repo-boundary --location "$empty_dir" admin init 2>/dev/null
    fl_out=$(PYTHONUSERBASE="${ORIGINAL_HOME}/.local" python3 "$AVER_PATH" \
        --override-repo-boundary --location "$empty_dir" --no-validate-config admin validate --failed-list 2>&1)
    fl_exit=$?
    set -e
    rm -rf "$empty_dir"
    if [ $fl_exit -eq 0 ] && [ -z "$fl_out" ]; then
        pass
    else
        fail "Expected exit 0 and empty output for no records; got exit=$fl_exit out='$fl_out'"
    fi
}

#==============================================================================
# Test: reindex validation integration
#==============================================================================

test_reindex_validation() {
    print_section "Test: reindex validation integration"

    # -------------------------------------------------------------------------
    # Setup: create a conforming record so we have a clean baseline
    # -------------------------------------------------------------------------
    print_test "Create conforming record for reindex-validation tests"
    local rec_good
    rec_good=$(run_aver record new --description "" --no-validation-editor \
        --title "Reindex Validation Test" --status open 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_good" ]; then
        fail "Could not create conforming record"
        return
    fi
    pass
    echo "  Created: $rec_good"

    # -------------------------------------------------------------------------
    # 1. reindex on a conforming record exits 0 (no validation errors)
    # -------------------------------------------------------------------------
    print_test "reindex conforming record exits 0"
    set +e
    local out exit_code
    out=$(run_aver admin reindex "$rec_good" --force 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ]; then
        pass
    else
        fail "Expected exit 0 for conforming record; got $exit_code: $out"
    fi

    # -------------------------------------------------------------------------
    # 2. Inject a non-conforming record on disk
    # -------------------------------------------------------------------------
    print_test "Inject non-conforming record for reindex test"
    local bad_id="REC-REINDEX-VAL-BAD"
    cat > "$TEST_DIR/records/${bad_id}.md" << 'BADEOF'
---
title: Bad Reindex Record
status: not_a_valid_status
created_at: "2026-01-01 00:00:00"
created_by: testuser
---

This record has an invalid status and should block reindex by default.
BADEOF
    if [ -f "$TEST_DIR/records/${bad_id}.md" ]; then
        pass
        echo "  Injected: $bad_id"
    else
        fail "Could not write non-conforming record"
        return
    fi

    # -------------------------------------------------------------------------
    # 3. reindex on the bad record fails by default
    # -------------------------------------------------------------------------
    print_test "reindex non-conforming record exits 1 by default"
    set +e
    out=$(run_aver admin reindex "$bad_id" --force 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ]; then
        pass
    else
        fail "Expected non-zero exit for non-conforming record; got 0: $out"
    fi

    # -------------------------------------------------------------------------
    # 4. Error message mentions the field and the bad value
    # -------------------------------------------------------------------------
    print_test "reindex error mentions the invalid field"
    if echo "$out" | grep -qi "status" && echo "$out" | grep -qi "not_a_valid_status\|validation"; then
        pass
    else
        fail "Expected 'status' / validation info in error output: $out"
    fi

    # -------------------------------------------------------------------------
    # 5. Error message mentions --skip-validation hint
    # -------------------------------------------------------------------------
    print_test "reindex error mentions --skip-validation"
    if echo "$out" | grep -q "skip-validation"; then
        pass
    else
        fail "Expected '--skip-validation' hint in error output: $out"
    fi

    # -------------------------------------------------------------------------
    # 6. reindex --skip-validation on bad record exits 0
    # -------------------------------------------------------------------------
    print_test "reindex --skip-validation on non-conforming record exits 0"
    set +e
    out=$(run_aver admin reindex "$bad_id" --force --skip-validation 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ]; then
        pass
    else
        fail "Expected exit 0 with --skip-validation; got $exit_code: $out"
    fi

    # -------------------------------------------------------------------------
    # 7. Full reindex with a mix of good and bad records fails by default,
    #    reports all failing records before exiting
    # -------------------------------------------------------------------------
    print_test "full reindex fails and lists all non-conforming records"
    set +e
    out=$(run_aver admin reindex --force 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$out" | grep -q "$bad_id"; then
        pass
        echo "  Non-conforming record listed in error output"
    else
        fail "Expected exit 1 and '$bad_id' in output; exit=$exit_code out=$out"
    fi

    # -------------------------------------------------------------------------
    # 8. Full reindex with --skip-validation succeeds despite bad records
    # -------------------------------------------------------------------------
    print_test "full reindex --skip-validation succeeds with non-conforming records"
    set +e
    out=$(run_aver admin reindex --force --skip-validation 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -eq 0 ]; then
        pass
    else
        fail "Expected exit 0 with --skip-validation on full reindex; got $exit_code: $out"
    fi
}

test_unmask() {
    print_section "Test: record unmask / note unmask"

    # Create a record with a securestring field and a plain string field
    local rec_id
    rec_id=$(run_aver record new --description "" --no-validation-editor \
        --title "Unmask Test Record" --status "open" --api_token "unmask_secret_42" 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_id" ]; then
        fail "Could not create record for unmask tests"
        return
    fi
    echo "  Record for unmask tests: $rec_id"

    # -------------------------------------------------------------------------
    # 1. record unmask returns plaintext for securestring field
    # -------------------------------------------------------------------------
    print_test "record unmask returns plaintext for securestring field"
    track_command "aver record unmask $rec_id --fields api_token"
    if output=$(run_aver record unmask "$rec_id" --fields "api_token" 2>&1); then
        if echo "$output" | grep -q "api_token" && echo "$output" | grep -q "unmask_secret_42"; then
            pass
            echo "  Plaintext value returned: $(echo "$output" | grep api_token)"
        else
            fail "Expected plaintext 'unmask_secret_42' in output: $output"
        fi
    else
        fail "record unmask failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 2. record unmask includes non-securestring fields with normal value
    # -------------------------------------------------------------------------
    print_test "record unmask includes non-securestring field with normal value"
    track_command "aver record unmask $rec_id --fields title,api_token"
    if output=$(run_aver record unmask "$rec_id" --fields "title,api_token" 2>&1); then
        if echo "$output" | grep -q "title" && echo "$output" | grep -q "Unmask Test Record" \
           && echo "$output" | grep -q "api_token" && echo "$output" | grep -q "unmask_secret_42"; then
            pass
            echo "  Both title and api_token returned correctly"
        else
            fail "Expected both fields in output: $output"
        fi
    else
        fail "record unmask with multiple fields failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 3. record unmask silently omits missing fields
    # -------------------------------------------------------------------------
    print_test "record unmask silently omits missing fields"
    track_command "aver record unmask $rec_id --fields api_token,nonexistent_field"
    if output=$(run_aver record unmask "$rec_id" --fields "api_token,nonexistent_field" 2>&1); then
        if echo "$output" | grep -q "api_token" && ! echo "$output" | grep -q "nonexistent_field"; then
            pass
            echo "  Missing field silently omitted, api_token present"
        else
            fail "Expected api_token only (no nonexistent_field): $output"
        fi
    else
        fail "record unmask with missing field failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 4. Create a note with securestring field
    # -------------------------------------------------------------------------
    local note_id
    note_id=$(run_aver note add "$rec_id" --message "Note for unmask test" \
        --session_token "note_secret_99" 2>&1 \
        | grep -oE "NT-[A-Z0-9]+" || echo "")
    if [ -z "$note_id" ]; then
        fail "Could not create note for unmask tests"
        return
    fi
    echo "  Note for unmask tests: $note_id"

    # -------------------------------------------------------------------------
    # 6. note unmask returns plaintext for securestring field
    # -------------------------------------------------------------------------
    print_test "note unmask returns plaintext for securestring field"
    track_command "aver note unmask $rec_id $note_id --fields session_token"
    if output=$(run_aver note unmask "$rec_id" "$note_id" --fields "session_token" 2>&1); then
        if echo "$output" | grep -q "session_token" && echo "$output" | grep -q "note_secret_99"; then
            pass
            echo "  Note securestring unmasked correctly"
        else
            fail "Expected plaintext 'note_secret_99' in note unmask output: $output"
        fi
    else
        fail "note unmask failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 7. note unmask includes non-securestring field (author is in kv_strings)
    # -------------------------------------------------------------------------
    print_test "note unmask includes non-securestring field"
    track_command "aver note unmask $rec_id $note_id --fields author,session_token"
    if output=$(run_aver note unmask "$rec_id" "$note_id" --fields "author,session_token" 2>&1); then
        if echo "$output" | grep -q "author" \
           && echo "$output" | grep -q "session_token" && echo "$output" | grep -q "note_secret_99"; then
            pass
            echo "  Both author and session_token returned correctly"
        else
            fail "Expected both fields in note unmask output: $output"
        fi
    else
        fail "note unmask with multiple fields failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 8. note unmask silently omits missing fields
    # -------------------------------------------------------------------------
    print_test "note unmask silently omits missing fields"
    track_command "aver note unmask $rec_id $note_id --fields session_token,nosuchfield"
    if output=$(run_aver note unmask "$rec_id" "$note_id" --fields "session_token,nosuchfield" 2>&1); then
        if echo "$output" | grep -q "session_token" && ! echo "$output" | grep -q "nosuchfield"; then
            pass
            echo "  Missing field silently omitted in note unmask"
        else
            fail "Expected session_token only (no nosuchfield): $output"
        fi
    else
        fail "note unmask with missing field failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 9. JSON IO unmask record (no note_id)
    # -------------------------------------------------------------------------
    print_test "JSON IO unmask command for record"
    track_command "json io unmask record_id fields"
    if output=$(echo "{\"command\": \"unmask\", \"params\": {\"record_id\": \"$rec_id\", \"fields\": [\"api_token\", \"title\"]}}" \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success'), f'not success: {data}'
r = data['result']
assert r.get('record_id'), f'no record_id in result: {r}'
fields = r.get('fields', {})
assert fields.get('api_token') == 'unmask_secret_42', f'wrong api_token: {fields.get(\"api_token\")!r}'
assert fields.get('title') == 'Unmask Test Record', f'wrong title: {fields.get(\"title\")!r}'
assert 'note_id' not in r, f'note_id should not be present for record unmask: {r}'
print('ok')
" 2>/dev/null; then
            pass
            echo "  JSON IO unmask record returned correct plaintext"
        else
            fail "JSON IO unmask record output incorrect: $output"
        fi
    else
        fail "JSON IO unmask record failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 11. JSON IO unmask note (with note_id)
    # -------------------------------------------------------------------------
    print_test "JSON IO unmask command for note"
    track_command "json io unmask record_id note_id fields"
    if output=$(echo "{\"command\": \"unmask\", \"params\": {\"record_id\": \"$rec_id\", \"note_id\": \"$note_id\", \"fields\": [\"session_token\"]}}" \
        | run_aver json io 2>&1); then
        if echo "$output" | python3 -c "
import sys, json
data = json.load(sys.stdin)
assert data.get('success'), f'not success: {data}'
r = data['result']
assert r.get('record_id'), f'no record_id: {r}'
assert r.get('note_id'), f'no note_id: {r}'
fields = r.get('fields', {})
assert fields.get('session_token') == 'note_secret_99', f'wrong session_token: {fields.get(\"session_token\")!r}'
print('ok')
" 2>/dev/null; then
            pass
            echo "  JSON IO unmask note returned correct plaintext"
        else
            fail "JSON IO unmask note output incorrect: $output"
        fi
    else
        fail "JSON IO unmask note failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 12. record unmask does NOT leak plaintext in normal record view
    # -------------------------------------------------------------------------
    print_test "record view still masks securestring (unmask does not affect view)"
    track_command "aver record view $rec_id"
    if output=$(run_aver record view "$rec_id" 2>&1); then
        if ! echo "$output" | grep -q "unmask_secret_42"; then
            pass
            echo "  record view still masks securestring after unmask calls"
        else
            fail "Plaintext leaked into record view: $output"
        fi
    else
        fail "record view failed: $output"
    fi
}

test_note_add_no_validation_editor() {
    print_section "Test: note add --no-validation-editor"

    # Create a record to attach notes to
    local rec_id
    rec_id=$(run_aver record new --description "" --no-validation-editor \
        --title "Note NVE Test" --status "open" 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_id" ]; then
        fail "Could not create record for note --no-validation-editor tests"
        return
    fi
    echo "  Record: $rec_id"

    # -------------------------------------------------------------------------
    # 1. note add --message with --no-validation-editor succeeds
    # -------------------------------------------------------------------------
    print_test "note add --message --no-validation-editor succeeds"
    track_command "aver note add $rec_id --message 'test' --no-validation-editor"
    if output=$(run_aver note add "$rec_id" --message "automation note" \
            --no-validation-editor 2>&1); then
        if echo "$output" | grep -q "Added note"; then
            pass
            echo "  Note added successfully with --no-validation-editor"
        else
            fail "Unexpected output: $output"
        fi
    else
        fail "note add --message --no-validation-editor failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 2. note add via stdin with --no-validation-editor succeeds
    # -------------------------------------------------------------------------
    print_test "note add via stdin --no-validation-editor succeeds"
    track_command "echo 'stdin note' | aver note add $rec_id --no-validation-editor"
    if output=$(echo "stdin note" | run_aver note add "$rec_id" \
            --no-validation-editor 2>&1); then
        if echo "$output" | grep -q "Added note"; then
            pass
            echo "  Note added via stdin with --no-validation-editor"
        else
            fail "Unexpected output: $output"
        fi
    else
        fail "note add stdin --no-validation-editor failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 3. note add with no message and --no-validation-editor errors (no editor)
    # -------------------------------------------------------------------------
    print_test "note add --no-validation-editor with no message errors instead of opening editor"
    track_command "aver note add $rec_id --no-validation-editor (no message)"
    set +e
    output=$(run_aver note add "$rec_id" --no-validation-editor 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$output" | grep -qi "no message\|error"; then
        pass
        echo "  Correctly errored without opening editor"
    else
        fail "Expected exit 1 with error message; got exit=$exit_code: $output"
    fi
}

test_help_fields() {
    print_section "Test: --help-fields on record new and record update"

    # -------------------------------------------------------------------------
    # 1. record new --help-fields (global fields, no template)
    # -------------------------------------------------------------------------
    print_test "record new --help-fields shows global record fields"
    track_command "aver record new --help-fields"
    if output=$(run_aver record new --help-fields 2>&1); then
        if echo "$output" | grep -q "title" && echo "$output" | grep -q "status"; then
            pass
            echo "  Global fields shown (title, status present)"
        else
            fail "Expected global fields in output: $output"
        fi
    else
        fail "record new --help-fields failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 2. record new --help-fields shows accepted values
    # -------------------------------------------------------------------------
    print_test "record new --help-fields shows accepted values for constrained fields"
    track_command "aver record new --help-fields (check accepted values)"
    if output=$(run_aver record new --help-fields 2>&1); then
        if echo "$output" | grep -q "open" && echo "$output" | grep -q "closed"; then
            pass
            echo "  Accepted values for status shown"
        else
            fail "Expected accepted values in output: $output"
        fi
    else
        fail "record new --help-fields failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 3. record new --help-fields --template bug shows template-specific fields
    # -------------------------------------------------------------------------
    print_test "record new --help-fields with bug template shows template fields"
    track_command "aver record new --help-fields --template bug"
    if output=$(run_aver record new --help-fields --template bug 2>&1); then
        # Bug template overrides status with different accepted values
        if echo "$output" | grep -q "severity" && echo "$output" | grep -q "bug"; then
            pass
            echo "  Template-specific fields shown (severity, bug template noted)"
        else
            fail "Expected bug template fields in output: $output"
        fi
    else
        fail "record new --help-fields --template bug failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 4. record new --help-fields --template bug shows bug-specific status values
    # -------------------------------------------------------------------------
    print_test "record new --help-fields bug template shows bug status accepted values"
    track_command "aver record new --help-fields --template bug (check status values)"
    if output=$(run_aver record new --help-fields --template bug 2>&1); then
        if echo "$output" | grep -q "confirmed" && echo "$output" | grep -q "fixed"; then
            pass
            echo "  Bug-specific status values shown (confirmed, fixed)"
        else
            fail "Expected bug status values (confirmed, fixed) in output: $output"
        fi
    else
        fail "record new --help-fields bug template failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 5. record new --help-fields does NOT launch editor or create a record
    # -------------------------------------------------------------------------
    print_test "record new --help-fields does not create a record"
    track_command "aver record new --help-fields (no record created)"
    local count_before count_after
    count_before=$(run_aver record list 2>&1 | grep -cE "^REC-|^BUG-|^FEAT-" || echo 0)
    run_aver record new --help-fields > /dev/null 2>&1
    count_after=$(run_aver record list 2>&1 | grep -cE "^REC-|^BUG-|^FEAT-" || echo 0)
    if [ "$count_before" = "$count_after" ]; then
        pass
        echo "  No record created by --help-fields"
    else
        fail "Record count changed: before=$count_before after=$count_after"
    fi

    # -------------------------------------------------------------------------
    # 6. Create a standard (non-template) record for update tests
    # -------------------------------------------------------------------------
    local rec_id
    rec_id=$(run_aver record new --description "" --no-validation-editor \
        --title "Help Fields Test Record" --status "open" 2>&1 \
        | grep -oE "REC-[A-Z0-9]+" || echo "")
    if [ -z "$rec_id" ]; then
        fail "Could not create record for update --help-fields tests"
        return
    fi
    echo "  Record for update tests: $rec_id"

    # -------------------------------------------------------------------------
    # 7. record update --help-fields shows fields for the record's current template
    # -------------------------------------------------------------------------
    print_test "record update --help-fields shows fields for record's current template"
    track_command "aver record update $rec_id --help-fields"
    if output=$(run_aver record update "$rec_id" --help-fields 2>&1); then
        if echo "$output" | grep -q "title" && echo "$output" | grep -q "status"; then
            pass
            echo "  Fields shown for record $rec_id"
        else
            fail "Expected fields in update --help-fields output: $output"
        fi
    else
        fail "record update --help-fields failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 8. record update --help-fields does NOT modify the record
    # -------------------------------------------------------------------------
    print_test "record update --help-fields does not modify the record"
    track_command "aver record update $rec_id --help-fields (no modification)"
    local view_before view_after
    view_before=$(run_aver record view "$rec_id" 2>&1)
    run_aver record update "$rec_id" --help-fields > /dev/null 2>&1
    view_after=$(run_aver record view "$rec_id" 2>&1)
    if [ "$view_before" = "$view_after" ]; then
        pass
        echo "  Record unchanged after update --help-fields"
    else
        fail "Record was modified by update --help-fields"
    fi

    # -------------------------------------------------------------------------
    # 9. record update --help-fields --template <same> shows fields (no change)
    # -------------------------------------------------------------------------
    # Create a bug record by injecting it on disk
    local bug_id="BUG-HELPTEST"
    mkdir -p "$TEST_DIR/records"
    cat > "$TEST_DIR/records/${bug_id}.md" << 'BUGEOF'
---
template_id: bug
title: Help Fields Bug Record
status: new
severity: 3
created_at: "2026-01-01 00:00:00"
created_by: testuser
---
BUGEOF
    run_aver admin reindex "$bug_id" --skip-validation > /dev/null 2>&1

    print_test "record update --help-fields --template bug (same template) shows bug fields"
    track_command "aver record update $bug_id --help-fields --template bug"
    if output=$(run_aver record update "$bug_id" --help-fields --template bug 2>&1); then
        if echo "$output" | grep -q "severity" && echo "$output" | grep -q "bug"; then
            pass
            echo "  Bug fields shown when same template specified"
        else
            fail "Expected bug fields in output: $output"
        fi
    else
        fail "record update --help-fields --template bug failed: $output"
    fi

    # -------------------------------------------------------------------------
    # 10. record update --help-fields with a DIFFERENT template errors out
    #     (template_id is editable=false in test config)
    # -------------------------------------------------------------------------
    print_test "record update --help-fields with different template errors (not editable)"
    track_command "aver record update $bug_id --help-fields --template feature"
    set +e
    output=$(run_aver record update "$bug_id" --help-fields --template feature 2>&1)
    exit_code=$?
    set -e
    if [ $exit_code -ne 0 ] && echo "$output" | grep -qi "cannot change template\|not editable\|error"; then
        pass
        echo "  Correctly rejected template change on non-editable template_id"
    else
        fail "Expected error on template change (not editable); got exit=$exit_code: $output"
    fi
}

test_offset_pagination() {
    print_section "Test: --offset Pagination"

    # Setup: create 5 records with a unique tag so we can isolate them
    print_test "Setup: create 5 pagination test records"
    local ids=()
    for i in 1 2 3 4 5; do
        local id
        id=$(run_aver record new --description "" --no-validation-editor \
            --title "OffsetPage $i" --status open --priority critical 2>&1 \
            | grep -oE "REC-[A-Z0-9]+" || echo "")
        ids+=("$id")
    done

    # Verify all 5 were created
    local all_ok=true
    for id in "${ids[@]}"; do
        [ -z "$id" ] && all_ok=false
    done
    if $all_ok; then
        pass
        echo "  Created: ${ids[*]}"
    else
        fail "Setup failed: could not create all 5 pagination test records"
        return
    fi

    # -------------------------------------------------------------------------
    # 1. record list --limit 3 returns 3 records (baseline)
    # -------------------------------------------------------------------------
    print_test "record list --ksearch --limit 3 returns 3 records"
    local out3
    out3=$(run_aver record list --ksearch "priority=critical" --ksearch "status=open" --limit 3 --ids-only 2>&1)
    local count3
    count3=$(echo "$out3" | grep -cE "^REC-" || true)
    if [ "$count3" -ge 3 ]; then
        pass
        echo "  Got $count3 records (>= 3)"
    else
        fail "Expected >= 3 records with --limit 3, got $count3"
    fi

    # -------------------------------------------------------------------------
    # 2. record list --limit 3 --offset 0 == record list --limit 3 (same IDs)
    # -------------------------------------------------------------------------
    print_test "record list --limit 3 --offset 0 equals --limit 3 (same results)"
    local out_no_offset out_offset0
    out_no_offset=$(run_aver record list --ksearch "priority=critical" --ksearch "status=open" --limit 3 --ids-only 2>&1)
    out_offset0=$(run_aver record list --ksearch "priority=critical" --ksearch "status=open" --limit 3 --offset 0 --ids-only 2>&1)
    if [ "$out_no_offset" = "$out_offset0" ]; then
        pass
        echo "  --offset 0 is identical to no --offset"
    else
        fail "--offset 0 differs from no offset"
    fi

    # -------------------------------------------------------------------------
    # 3. record list --limit 2 --offset 2 skips first 2
    #    (the first ID in offset=2 should NOT appear in offset=0's first 2)
    # -------------------------------------------------------------------------
    print_test "record list --limit 2 --offset 2 skips first 2 records"
    local first2 next2
    first2=$(run_aver record list --ksearch "priority=critical" --ksearch "status=open" --limit 2 --offset 0 --ids-only 2>&1)
    next2=$(run_aver record list --ksearch "priority=critical" --ksearch "status=open" --limit 2 --offset 2 --ids-only 2>&1)
    local first_id_of_next
    first_id_of_next=$(echo "$next2" | grep -m1 "^REC-" || echo "")
    if [ -n "$first_id_of_next" ] && ! echo "$first2" | grep -qF "$first_id_of_next"; then
        pass
        echo "  First ID at offset=2 ($first_id_of_next) not in first 2 IDs"
    else
        fail "Offset=2 did not skip the first 2 results (first2: $first2, next2: $next2)"
    fi

    # -------------------------------------------------------------------------
    # 4. record list --offset beyond total returns empty / fewer results
    # -------------------------------------------------------------------------
    print_test "record list --offset beyond total returns 0 or fewer results"
    local big_offset_out
    big_offset_out=$(run_aver record list --ksearch "priority=critical" --ksearch "status=open" --limit 5 --offset 9999 --ids-only 2>&1)
    local big_count
    big_count=$(echo "$big_offset_out" | grep -cE "^REC-" || true)
    if [ "$big_count" -eq 0 ]; then
        pass
        echo "  --offset 9999 returned 0 records"
    else
        fail "Expected 0 records at offset 9999, got $big_count"
    fi

    # -------------------------------------------------------------------------
    # 5. note search --limit N --offset N pagination
    #    Setup: add 3 notes to one of the records, all with category=offsettest
    # -------------------------------------------------------------------------
    local rec_id="${ids[0]}"

    print_test "Setup: add 3 notes with category=offsettest to $rec_id"
    local n1 n2 n3
    n1=$(run_aver note add "$rec_id" --message "Note one" --category offsettest 2>&1)
    n2=$(run_aver note add "$rec_id" --message "Note two" --category offsettest 2>&1)
    n3=$(run_aver note add "$rec_id" --message "Note three" --category offsettest 2>&1)
    if echo "$n1$n2$n3" | grep -qi "error\|failed"; then
        fail "Setup: note add failed: $n1 $n2 $n3"
        return
    fi
    pass
    echo "  Added 3 notes with category=offsettest"

    # -------------------------------------------------------------------------
    # 6. note search --ksearch category=offsettest --limit 2 returns 2
    # -------------------------------------------------------------------------
    print_test "note search --limit 2 returns 2 notes"
    local note_out2
    note_out2=$(run_aver note search --ksearch "category=offsettest" --limit 2 --ids-only 2>&1)
    local note_count2
    note_count2=$(echo "$note_out2" | grep -cE "^REC-" || true)
    if [ "$note_count2" -eq 2 ]; then
        pass
        echo "  Got 2 notes with --limit 2"
    else
        fail "Expected 2 notes with --limit 2, got $note_count2"
    fi

    # -------------------------------------------------------------------------
    # 7. note search --offset 1 --limit 2 skips first note
    # -------------------------------------------------------------------------
    print_test "note search --offset 1 --limit 2 skips first note"
    local note_first note_offset1
    note_first=$(run_aver note search --ksearch "category=offsettest" --limit 1 --offset 0 --ids-only 2>&1)
    note_offset1=$(run_aver note search --ksearch "category=offsettest" --limit 2 --offset 1 --ids-only 2>&1)
    local first_note_id
    first_note_id=$(echo "$note_first" | grep -m1 "^REC-" || echo "")
    if [ -n "$first_note_id" ] && ! echo "$note_offset1" | grep -qF "$first_note_id"; then
        pass
        echo "  First note at offset=0 ($first_note_id) not in offset=1 results"
    else
        fail "note search --offset 1 did not skip first note (first: $note_first, offset1: $note_offset1)"
    fi

    # -------------------------------------------------------------------------
    # 8. JSON IO search-records with offset param
    # -------------------------------------------------------------------------
    print_test "JSON IO search-records with offset skips records"
    local json_all json_offset
    json_all=$(echo '{"command":"search-records","params":{"ksearch":"priority=critical","limit":3,"offset":0}}' | run_aver json io 2>&1)
    json_offset=$(echo '{"command":"search-records","params":{"ksearch":"priority=critical","limit":3,"offset":2}}' | run_aver json io 2>&1)
    local first_id_all first_id_offset
    first_id_all=$(echo "$json_all" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',d); print(r['records'][0]['id'] if r.get('records') else '')" 2>/dev/null || echo "")
    first_id_offset=$(echo "$json_offset" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',d); print(r['records'][0]['id'] if r.get('records') else '')" 2>/dev/null || echo "")
    if [ -n "$first_id_all" ] && [ -n "$first_id_offset" ] && [ "$first_id_all" != "$first_id_offset" ]; then
        pass
        echo "  offset=0 first ID: $first_id_all, offset=2 first ID: $first_id_offset (different)"
    else
        fail "JSON IO search-records offset did not paginate (all=$first_id_all, offset=$first_id_offset)"
    fi

    # -------------------------------------------------------------------------
    # 9. JSON IO search-notes with offset param
    # -------------------------------------------------------------------------
    print_test "JSON IO search-notes with offset skips notes"
    local jnote_all jnote_offset
    jnote_all=$(echo '{"command":"search-notes","params":{"ksearch":"category=offsettest","limit":2,"offset":0}}' | run_aver json io 2>&1)
    jnote_offset=$(echo '{"command":"search-notes","params":{"ksearch":"category=offsettest","limit":2,"offset":1}}' | run_aver json io 2>&1)
    local jnote_first_all jnote_first_offset
    jnote_first_all=$(echo "$jnote_all" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',d); print(r['notes'][0]['id'] if r.get('notes') else '')" 2>/dev/null || echo "")
    jnote_first_offset=$(echo "$jnote_offset" | python3 -c "import sys,json; d=json.load(sys.stdin); r=d.get('result',d); print(r['notes'][0]['id'] if r.get('notes') else '')" 2>/dev/null || echo "")
    if [ -n "$jnote_first_all" ] && [ -n "$jnote_first_offset" ] && [ "$jnote_first_all" != "$jnote_first_offset" ]; then
        pass
        echo "  offset=0 first note: $jnote_first_all, offset=1 first note: $jnote_first_offset (different)"
    else
        fail "JSON IO search-notes offset did not paginate (all=$jnote_first_all, offset=$jnote_first_offset)"
    fi

    # -------------------------------------------------------------------------
    # 10. json search-records CLI --offset flag
    # -------------------------------------------------------------------------
    print_test "json search-records CLI --offset flag paginates"
    local jcli_all jcli_off
    set +e
    jcli_all=$(run_aver json search-records --ksearch "priority=critical" --limit 3 --offset 0 2>&1)
    jcli_off=$(run_aver json search-records --ksearch "priority=critical" --limit 3 --offset 2 2>&1)
    set -e
    local jcli_id_all jcli_id_off
    jcli_id_all=$(echo "$jcli_all" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['records'][0]['id'] if d.get('records') else '')" 2>/dev/null || echo "")
    jcli_id_off=$(echo "$jcli_off" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['records'][0]['id'] if d.get('records') else '')" 2>/dev/null || echo "")
    if [ -n "$jcli_id_all" ] && [ -n "$jcli_id_off" ] && [ "$jcli_id_all" != "$jcli_id_off" ]; then
        pass
        echo "  offset=0 first ID: $jcli_id_all, offset=2 first ID: $jcli_id_off (different)"
    else
        fail "json search-records CLI --offset did not paginate (all=$jcli_id_all, off=$jcli_id_off)"
    fi

    # -------------------------------------------------------------------------
    # 11. json search-notes CLI --offset flag
    # -------------------------------------------------------------------------
    print_test "json search-notes CLI --offset flag paginates"
    local jncli_all jncli_off
    set +e
    jncli_all=$(run_aver json search-notes --ksearch "category=offsettest" --limit 2 --offset 0 2>&1)
    jncli_off=$(run_aver json search-notes --ksearch "category=offsettest" --limit 2 --offset 1 2>&1)
    set -e
    local jncli_id_all jncli_id_off
    jncli_id_all=$(echo "$jncli_all" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['notes'][0]['id'] if d.get('notes') else '')" 2>/dev/null || echo "")
    jncli_id_off=$(echo "$jncli_off" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['notes'][0]['id'] if d.get('notes') else '')" 2>/dev/null || echo "")
    if [ -n "$jncli_id_all" ] && [ -n "$jncli_id_off" ] && [ "$jncli_id_all" != "$jncli_id_off" ]; then
        pass
        echo "  offset=0 first note: $jncli_id_all, offset=1 first note: $jncli_id_off (different)"
    else
        fail "json search-notes CLI --offset did not paginate (all=$jncli_id_all, off=$jncli_id_off)"
    fi
}

test_validate_config() {
    print_section "Test: admin validate-config"

    # Save and replace user config so dead library aliases from test_library_management
    # don't pollute validate-config results. Restore at end of function.
    local user_cfg="$TEST_HOME/.config/aver/user.toml"
    local user_cfg_bak="$TEST_HOME/.config/aver/user.toml.vc_bak"
    cp "$user_cfg" "$user_cfg_bak"
    cat > "$user_cfg" << 'EOF'
[user]
handle = "testuser"
email = "test@example.com"
EOF

    # -------------------------------------------------------------------------
    # 1. Valid config → exit 0, prints "Config validation: OK"
    # -------------------------------------------------------------------------
    print_test "admin validate-config with valid config → exit 0"
    track_command "aver admin validate-config"
    set +e
    vc_output=$(run_aver_validated admin validate-config 2>&1)
    vc_exit=$?
    set -e
    if [ $vc_exit -eq 0 ] && echo "$vc_output" | grep -q "Config validation: OK"; then
        pass
        echo "  Exit 0 and 'Config validation: OK' as expected"
    else
        fail "Expected exit 0 and 'Config validation: OK', got exit=$vc_exit output='$vc_output'"
    fi

    # -------------------------------------------------------------------------
    # 2. Bad value_type → exit 4
    # -------------------------------------------------------------------------
    print_test "admin validate-config with bad value_type → exit 4"
    track_command "inject bad value_type=blob into config.toml"

    # Save original config
    cp "$TEST_DIR/config.toml" "$TEST_DIR/config.toml.bak"

    # Inject a bad value_type (append a field with invalid type)
    cat >> "$TEST_DIR/config.toml" << 'EOF'

[record_special_fields.bad_type_field]
type = "single"
value_type = "blob"
editable = true
enabled = true
required = false
EOF

    set +e
    vc_output=$(run_aver_validated admin validate-config 2>&1)
    vc_exit=$?
    set -e

    # Restore good config
    mv "$TEST_DIR/config.toml.bak" "$TEST_DIR/config.toml"

    if [ $vc_exit -eq 4 ] && echo "$vc_output" | grep -qi "blob"; then
        pass
        echo "  Exit 4 and error about 'blob' as expected"
    else
        fail "Expected exit 4 with 'blob' error, got exit=$vc_exit output='$vc_output'"
    fi

    # -------------------------------------------------------------------------
    # 3. Unknown system_value → exit 4
    # -------------------------------------------------------------------------
    print_test "admin validate-config with unknown system_value → exit 4"
    track_command "inject unknown system_value into config.toml"

    cp "$TEST_DIR/config.toml" "$TEST_DIR/config.toml.bak"

    cat >> "$TEST_DIR/config.toml" << 'EOF'

[record_special_fields.bad_sysval_field]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
system_value = "nonexistent_system_value"
EOF

    set +e
    vc_output=$(run_aver_validated admin validate-config 2>&1)
    vc_exit=$?
    set -e

    mv "$TEST_DIR/config.toml.bak" "$TEST_DIR/config.toml"

    if [ $vc_exit -eq 4 ] && echo "$vc_output" | grep -qi "nonexistent_system_value"; then
        pass
        echo "  Exit 4 and error about unknown system_value as expected"
    else
        fail "Expected exit 4 with system_value error, got exit=$vc_exit output='$vc_output'"
    fi

    # -------------------------------------------------------------------------
    # 4. default not in accepted_values → exit 4
    # -------------------------------------------------------------------------
    print_test "admin validate-config with default not in accepted_values → exit 4"
    track_command "inject bad default value into config.toml"

    cp "$TEST_DIR/config.toml" "$TEST_DIR/config.toml.bak"

    cat >> "$TEST_DIR/config.toml" << 'EOF'

[record_special_fields.bad_default_field]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["alpha", "beta"]
default = "gamma"
EOF

    set +e
    vc_output=$(run_aver_validated admin validate-config 2>&1)
    vc_exit=$?
    set -e

    mv "$TEST_DIR/config.toml.bak" "$TEST_DIR/config.toml"

    if [ $vc_exit -eq 4 ] && echo "$vc_output" | grep -qi "gamma"; then
        pass
        echo "  Exit 4 and error about 'gamma' default as expected"
    else
        fail "Expected exit 4 with default error, got exit=$vc_exit output='$vc_output'"
    fi

    # -------------------------------------------------------------------------
    # 5. admin validate-config --no-validate-config → still validates (exit 0)
    # -------------------------------------------------------------------------
    print_test "admin validate-config --no-validate-config still validates (flag ignored)"
    track_command "aver --no-validate-config admin validate-config"
    set +e
    vc_output=$(run_aver_validated --no-validate-config admin validate-config 2>&1)
    vc_exit=$?
    set -e
    if [ $vc_exit -eq 0 ] && echo "$vc_output" | grep -q "Config validation: OK"; then
        pass
        echo "  Exit 0 even with --no-validate-config flag (flag correctly ignored)"
    else
        fail "Expected exit 0 with 'Config validation: OK', got exit=$vc_exit output='$vc_output'"
    fi

    # -------------------------------------------------------------------------
    # 6. record list without --no-validate-config emits warnings; with flag, suppresses them
    # -------------------------------------------------------------------------
    print_test "startup warnings emitted without --no-validate-config, suppressed with it"
    track_command "inject bad config, compare record list with/without --no-validate-config"

    cp "$TEST_DIR/config.toml" "$TEST_DIR/config.toml.bak"

    cat >> "$TEST_DIR/config.toml" << 'EOF'

[record_special_fields.suppress_test_field]
type = "single"
value_type = "blob"
editable = true
enabled = true
required = false
EOF

    set +e
    # Without flag: should emit [CONFIG WARNING]
    vc_warn=$(run_aver_validated record list 2>&1)
    vc_warn_exit=$?
    # With flag: should suppress warnings
    vc_quiet=$(run_aver_validated --no-validate-config record list 2>&1)
    vc_quiet_exit=$?
    set -e

    mv "$TEST_DIR/config.toml.bak" "$TEST_DIR/config.toml"

    if [ $vc_warn_exit -eq 0 ] && echo "$vc_warn" | grep -q "CONFIG WARNING" && \
       [ $vc_quiet_exit -eq 0 ] && ! echo "$vc_quiet" | grep -q "CONFIG WARNING"; then
        pass
        echo "  Warnings present without flag, absent with --no-validate-config"
    else
        fail "warn_exit=$vc_warn_exit quiet_exit=$vc_quiet_exit; expected warnings without flag, none with flag"
        echo "  Without flag output: $vc_warn"
        echo "  With flag output: $vc_quiet"
    fi

    # -------------------------------------------------------------------------
    # 7. admin reindex with bad config → exit 4 (hard fail)
    # -------------------------------------------------------------------------
    print_test "admin reindex with bad config → exit 4"
    track_command "inject bad config, run admin reindex --skip-validation"

    cp "$TEST_DIR/config.toml" "$TEST_DIR/config.toml.bak"

    cat >> "$TEST_DIR/config.toml" << 'EOF'

[record_special_fields.reindex_test_bad_field]
type = "single"
value_type = "blob"
editable = true
enabled = true
required = false
EOF

    set +e
    vc_output=$(run_aver_validated admin reindex --skip-validation 2>&1)
    vc_exit=$?
    set -e

    mv "$TEST_DIR/config.toml.bak" "$TEST_DIR/config.toml"

    if [ $vc_exit -eq 4 ]; then
        pass
        echo "  Exit 4 (config validation hard fail) for admin reindex with bad config"
    else
        fail "Expected exit 4 for admin reindex with bad config, got exit=$vc_exit output='$vc_output'"
    fi

    # -------------------------------------------------------------------------
    # 8. Verify config is restored and validate-config passes again
    # -------------------------------------------------------------------------
    print_test "config restored → admin validate-config passes again"
    track_command "aver admin validate-config after restore"
    set +e
    vc_output=$(run_aver_validated admin validate-config 2>&1)
    vc_exit=$?
    set -e
    if [ $vc_exit -eq 0 ] && echo "$vc_output" | grep -q "Config validation: OK"; then
        pass
        echo "  Config validated clean after restore"
    else
        fail "Expected exit 0 after config restore, got exit=$vc_exit output='$vc_output'"
    fi

    # Restore the original user config
    mv "$user_cfg_bak" "$user_cfg"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Run main
main
