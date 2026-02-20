# System Fields Update - Documentation

## Overview

The aver system has been updated to make ALL system field behavior configurable through the project's `config.toml` file. The system no longer automatically adds any fields - administrators must explicitly define all desired system fields in the configuration.

## Breaking Change

**IMPORTANT**: The system no longer automatically adds `created_at`, `created_by`, or `updated_at` fields. If you want these fields, you must define them in your project's `.aver/config.toml` file.

## New Special Field Attributes

Each field in `[special_fields]` can now have these attributes:

### Core Attributes (existing)
- `type`: "single" or "multi" (required)
- `value_type`: "string", "integer", or "float" (default: "string")
- `accepted_values`: List of allowed values (optional)

### New Attributes

#### `editable` (boolean, default: true)
- **`editable = false`**: Field is set once and never updated
  - Hidden from editor view
  - Cannot be modified via command line (will error)
  - Value is set by system_value or default, then locked
  - Used for: created_at, created_by, record_id
  
- **`editable = true`**: Field can be modified
  - Appears in editor
  - Can be updated via command line
  - If `system_value` is set, auto-updates on every edit
  - Used for: updated_at, user-editable fields

#### `enabled` (boolean, default: true)
- **`enabled = true`**: Field is treated as a special field
  - System enforces type, validation, defaults, etc.
  
- **`enabled = false`**: Field is treated as a regular field
  - No special handling or validation
  - Allows deprecation of old fields without breaking existing records
  - User can manually edit if desired

#### `required` (boolean, default: false)
- **`required = true`**: Field must have a non-empty value
  - Validated on every save (create and update)
  - Errors if missing or empty
  
- **`required = false`**: Field is optional

#### `system_value` (string, optional)
- Specifies that the field should be auto-populated with a system-derived value
- Can use plain syntax: `system_value = "datetime"`
- Or template syntax: `system_value = "${datetime}"`
- Available system values:
  - `datetime` - Full timestamp: YYYY-MM-DD HH:MM:SS
  - `datestamp` - Date only: YYYY-MM-DD
  - `user_email` - User's email from identity
  - `user_name` - User's handle/username from identity
  - `recordid` - The incident/record ID
  - `updateid` - The update ID (for update notes)

**Behavior with `editable`:**
- `editable = false` + `system_value`: Set once on creation, never updated
- `editable = true` + `system_value`: Auto-update on every edit

#### `default` (string, optional)
- Provides a default value if field is empty at creation time
- Can be static: `default = "pending"`
- Or reference system values: `default = "${datetime}"`
- Only applied on creation, not updates
- Only applied if field is empty

## System Value Types Reference

| System Value | Description | Example Output |
|-------------|-------------|----------------|
| `datetime` | Current date and time | `2025-02-13 14:30:45` |
| `datestamp` | Current date only | `2025-02-13` |
| `user_name` | User's handle/username | `alice` |
| `user_email` | User's email address | `alice@example.com` |
| `recordid` | The incident/record ID | `REC-A1B2C3` |
| `updateid` | The update/note ID | `NT-X7Y8Z9` |

## Common Configuration Patterns

### Pattern 1: Timestamp Fields (Created/Updated)

```toml
# Set once on creation, never updated
[special_fields.created_at]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"

# Auto-update on every edit
[special_fields.updated_at]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
system_value = "datetime"
```

### Pattern 2: User Identity Fields

```toml
[special_fields.created_by_username]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[special_fields.created_by_email]
type = "single"
value_type = "string"
editable = false
enabled = true
required = false
system_value = "user_email"
```

### Pattern 3: Status Field with Default

```toml
[special_fields.status]
type = "single"
value_type = "string"
editable = true
enabled = true
required = true
accepted_values = ["open", "in_progress", "resolved", "closed"]
default = "open"
```

### Pattern 4: Date Field with System Default

```toml
[special_fields.reported_date]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
default = "${datestamp}"  # Defaults to current date if not provided
```

### Pattern 5: Record ID Storage

```toml
[special_fields.record_id]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "recordid"
```

### Pattern 6: Deprecated Field

```toml
[special_fields.old_category]
type = "single"
value_type = "string"
editable = true
enabled = false  # Treated as regular field, no special handling
required = false
```

## Behavior Summary

### On Record Creation

1. User provides data via CLI/editor
2. System applies defaults to empty fields
3. System applies `system_value` fields (both editable and non-editable)
4. System validates required fields
5. System validates accepted_values
6. Record is saved

### On Record Update

1. User provides changes via CLI/editor
2. Non-editable fields are hidden from editor
3. Any user attempts to modify non-editable fields are silently overwritten
4. System applies `system_value` fields with `editable = true` (auto-update)
5. System validates required fields
6. System validates accepted_values
7. Record is saved

### Command-Line Editing Restrictions

When editing via command line (e.g., `aver update <id> field$value`):
- **Non-editable fields**: Error message "field cannot be edited"
- **Editable fields**: Updates allowed, subject to validation
- **Disabled fields**: Treated as regular custom fields

### Editor View

When editing in YAML editor:
- **Non-editable fields**: Hidden (not shown in frontmatter)
- **Editable fields**: Shown and editable
- **Disabled fields**: Shown if present, treated as custom fields

## Migration Guide

If you have existing records with `created_at`, `created_by`, or `updated_at`, you need to add these to your config:

```toml
[special_fields.created_at]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "datetime"

[special_fields.created_by]
type = "single"
value_type = "string"
editable = false
enabled = true
required = true
system_value = "user_name"

[special_fields.updated_at]
type = "single"
value_type = "string"
editable = true
enabled = true
required = false
system_value = "datetime"
```

**Note**: Existing records will keep their old values. New records will use the configured system values.

## Validation Behavior

### Required Field Validation
- Happens on every save (create and update)
- Field must exist and be non-empty
- Applies only to enabled fields
- Error shown if validation fails

### Accepted Values Validation
- Happens on every save
- Value must be in the accepted_values list
- Applies to all special fields with accepted_values defined
- Error shown if validation fails

### Non-Editable Field Protection
- Command-line: Immediate error if user tries to edit
- Editor: Field not shown (automatically filtered out)
- After editing: System silently overwrites any attempted changes

## Examples

See `config.toml.sample` for a comprehensive example configuration demonstrating all features.

## Developer Notes

### Key Functions

- `SystemValueDeriver.derive_value()`: Derives system values
- `SystemValueDeriver.resolve_default_value()`: Resolves default values
- `IncidentManager._apply_system_fields()`: Applies system fields to incidents
- `ProjectConfig.validate_required_fields()`: Validates required fields
- `ProjectConfig.get_enabled_special_fields()`: Gets only enabled fields

### Code Changes

1. **SpecialField class**: Added `enabled`, `required`, `system_value`, `default` attributes
2. **SystemValueDeriver class**: New class for deriving system values
3. **ProjectConfig**: Added validation methods and enabled field filtering
4. **IncidentManager**: Removed hardcoded field insertion, added `_apply_system_fields()`
5. **Incident.to_markdown()**: Only serializes enabled fields
6. **Removed automatic field insertion**: All system fields must be configured

### Testing Recommendations

1. Test required field validation on create and update
2. Test non-editable field protection (CLI and editor)
3. Test system value derivation for all types
4. Test default value application
5. Test accepted_values validation
6. Test disabled field behavior (should act like custom fields)
7. Test auto-update fields (editable + system_value)
