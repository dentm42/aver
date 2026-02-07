#!/usr/bin/env bash
set -euo pipefail

echo "== Aver Integration Test =="

# -------- Config --------
# Allow override:  AVER_BIN=/path/to/aver ./test_aver.sh
AVER_BIN="${AVER_BIN:-aver}"

if ! command -v "$AVER_BIN" >/dev/null 2>&1; then
  echo "❌ Cannot find aver executable at '$AVER_BIN'"
  echo "   Set AVER_BIN=/full/path/to/aver"
  exit 1
fi

# ---------- Helpers ----------
fail() {
  echo "❌ TEST FAILED: $1"
  exit 1
}

pass() {
  echo "✅ $1"
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  if ! grep -q "$needle" <<<"$haystack"; then
    fail "Expected to find '$needle'"
  fi
}

assert_file_exists() {
  [[ -e "$1" ]] || fail "Expected $1 to exist"
}

# ---------- Setup ----------
WORKDIR="$(mktemp -d)"
DBDIR="$WORKDIR/.aver"

echo "Working in $WORKDIR"
cd "$WORKDIR"

# Fake HOME so we don't pollute real config
export HOME="$WORKDIR/home"
mkdir -p "$HOME"

# ---------- User Config ----------
"$AVER_BIN" admin config set-user --handle "tester" --email "tester@example.com"
pass "User config set"

# ---------- Init Database ----------
"$AVER_BIN" admin init --location "$DBDIR"
echo "INIT: location ($DBDIR)"
#assert_file_exists "$DBDIR/config.toml"
assert_file_exists "$DBDIR/records"
pass "Database initialized"

# ---------- Create Record ----------
REC_OUTPUT=$("$AVER_BIN" record new \
  --location "$DBDIR" \
  --text "title=Test Incident" \
  --text "status=open" \
  --text "severity=high" \
  --number "priority=2" \
  --decimal "cost=10.5" \
  --text-multi "tags=backend" \
  --text-multi "tags=urgent" \
  --description "This is a test incident")

echo "$REC_OUTPUT"

REC_ID=$(grep -oE 'INC-[A-Z0-9]+' <<<"$REC_OUTPUT" | head -n1)
[[ -n "$REC_ID" ]] || fail "Record ID not found in output"
pass "Record created: $REC_ID"

# ---------- View Record ----------
VIEW_OUTPUT=$("$AVER_BIN" record view "$REC_ID" --location "$DBDIR")
assert_contains "$VIEW_OUTPUT" "Test Incident"
assert_contains "$VIEW_OUTPUT" "open"
pass "Record view works"

# ---------- List + Search ----------
LIST_OUTPUT=$("$AVER_BIN" record list --location "$DBDIR" --ksearch "status=open")
assert_contains "$LIST_OUTPUT" "$REC_ID"
pass "Record search by status works"

LIST_OUTPUT=$("$AVER_BIN" record list --location "$DBDIR" --ksearch "priority>=2")
assert_contains "$LIST_OUTPUT" "$REC_ID"
pass "Numeric search works"

# ---------- Update Record ----------
"$AVER_BIN" record update "$REC_ID" --location "$DBDIR" --text "status=resolved"
UPDATED_VIEW=$("$AVER_BIN" record view "$REC_ID" --location "$DBDIR")
assert_contains "$UPDATED_VIEW" "resolved"
pass "Record update works"

# ---------- Add Notes ----------
"$AVER_BIN" note add "$REC_ID" --location "$DBDIR" \
  --message "Initial investigation" \
  --text "category=investigation" \
  --number "time_spent=15"

echo "Second note via pipe" | "$AVER_BIN" note add "$REC_ID" --location "$DBDIR"

NOTES_OUTPUT=$("$AVER_BIN" note list "$REC_ID" --location "$DBDIR")
assert_contains "$NOTES_OUTPUT" "Initial investigation"
assert_contains "$NOTES_OUTPUT" "Second note via pipe"
pass "Notes added and listed"

# ---------- Note Search ----------
echo "DO: \"$AVER_BIN\" note search --location \"$DBDIR\" --ksearch \"time_spent>=15\""
SEARCH_NOTES=$("$AVER_BIN" note search --location "$DBDIR" --ksearch "time_spent>=15")
assert_contains "$SEARCH_NOTES" "$REC_ID"
pass "Note KV search works"

# ---------- Reindex ----------
"$AVER_BIN" admin reindex --location "$DBDIR" --verbose
pass "Reindex completed"

# ---------- Filesystem Checks ----------
RECORD_FILE_COUNT=$(find "$DBDIR/records" -name '*.md' | wc -l)
[[ "$RECORD_FILE_COUNT" -ge 1 ]] || fail "No record files found"

NOTE_FILE_COUNT=$(find "$DBDIR/updates" -name '*.md' | wc -l)
[[ "$NOTE_FILE_COUNT" -ge 2 ]] || fail "Expected at least 2 note files"

pass "Filesystem structure looks correct"

# ---------- Sorting ----------
SORT_OUTPUT=$("$AVER_BIN" record list --location "$DBDIR" --ksort "priority-")
assert_contains "$SORT_OUTPUT" "$REC_ID"
pass "Sorting works"

# ---------- Database Discovery ----------
"$AVER_BIN" admin list-databases >/dev/null || fail "Database listing failed"
pass "Database listing ran"

echo
echo "🎉 ALL TESTS PASSED"
echo "Temp data left in: $WORKDIR"

