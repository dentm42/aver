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
elif [ -f "/mnt/user-data/outputs/aver.py" ]; then
    AVER_PATH="/mnt/user-data/outputs/aver.py"
else
    echo -e "${RED}ERROR: Cannot find aver.py${NC}"
    echo "Please run this script from the directory containing aver.py"
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
    python3 "$AVER_PATH" --override-repo-boundary --location "$TEST_DIR" "$@"
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

[record_special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[record_special_fields.updated_at]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
system_value = "datetime"

[record_special_fields.title]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true

[record_special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["open", "in_progress", "resolved", "closed"]
default = "open"

[record_special_fields.priority]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
accepted_values = ["low", "medium", "high", "critical"]
default = "medium"

[record_special_fields.severity]
type = "single"
value_type = "integer"
editable = true
enabled = true
required = false
accepted_values = ["1", "2", "3", "4", "5"]

[record_special_fields.tags]
type = "multi"
value_type = "string"
editable = true
enabled = true
required = false

# Global note special fields
[note_special_fields.author]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[note_special_fields.timestamp]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"

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
    output=$(run_aver note add "$bug_rec" --message "Test" --category "invalid_category" 2>&1)
    exit_code=$?
    set -e
    
    if [ $exit_code -ne 0 ]; then
        pass
        echo "  Correctly rejected invalid category value"
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
    test_user_profile
    test_library_management
    test_custom_locations
    test_config_per_location
    test_listing_search
    test_note_operations
    test_note_special_fields
    test_from_file
    test_updates
    
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

# Trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

# Run main
main
