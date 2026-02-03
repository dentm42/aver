#!/usr/bin/env python3
"""
aver: a verified knowledge tracking tool

Minimal external dependencies. 
Stores records and updates as Markdown files with TOML headers.
Uses SQLite for indexing and searching only.
"""

import argparse
import datetime
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
from types import SimpleNamespace
import select
import secrets
import time

try:
    import tomllib
except ImportError:
    import tomli as tomllib

try:
    import tomli_w as toml_writer
except ImportError:
    toml_writer = None

# ============================================================================
# Data Models
# ============================================================================


@dataclass
class UserIdentity:
    """User identity configuration."""

    handle: str
    email: str

    def to_dict(self) -> Dict[str, str]:
        return {"handle": self.handle, "email": self.email}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "UserIdentity":
        return cls(handle=data["handle"], email=data["email"])


@dataclass
class Incident:
    """Incident with all metadata stored in KV."""
    
    # Type hint suffixes
    TYPE_HINT_STRING = "$"
    TYPE_HINT_INTEGER = "#"
    TYPE_HINT_FLOAT = "%"
    
    TYPE_HINTS = {
        TYPE_HINT_STRING: "string",
        TYPE_HINT_INTEGER: "integer",
        TYPE_HINT_FLOAT: "float",
    }
    
    def __init__(
        self,
        id: str,
        kv_strings: Optional[Dict[str, List[str]]] = None,
        kv_integers: Optional[Dict[str, List[int]]] = None,
        kv_floats: Optional[Dict[str, List[float]]] = None,
    ):
        self.id = id
        self.kv_strings = kv_strings or {}
        self.kv_integers = kv_integers or {}
        self.kv_floats = kv_floats or {}
    
    @staticmethod
    def _add_type_hint(key: str, value_type: str) -> str:
        """Add type hint suffix to key."""
        if value_type == "string":
            return f"{key}{Incident.TYPE_HINT_STRING}"
        elif value_type == "integer":
            return f"{key}{Incident.TYPE_HINT_INTEGER}"
        elif value_type == "float":
            return f"{key}{Incident.TYPE_HINT_FLOAT}"
        return key
    
    @staticmethod
    def _strip_type_hint(key: str) -> tuple[str, Optional[str]]:
        """
        Strip type hint suffix from key.
        
        Returns:
            (clean_key, type_hint) where type_hint is "string", "integer", "float", or None
        """
        if key.endswith(Incident.TYPE_HINT_STRING):
            return key[:-1], "string"
        elif key.endswith(Incident.TYPE_HINT_INTEGER):
            return key[:-1], "integer"
        elif key.endswith(Incident.TYPE_HINT_FLOAT):
            return key[:-1], "float"
        return key, None
    
    def get_value(
        self,
        field_name: str,
        project_config: ProjectConfig,
        default: Any = None,
    ) -> Any:
        """Get field value, respecting config type."""
        field = project_config.get_special_field(field_name)
        if not field:
            return default
        
        if field.value_type == "string":
            values = self.kv_strings.get(field_name, [default])
        elif field.value_type == "integer":
            values = self.kv_integers.get(field_name, [default])
        elif field.value_type == "float":
            values = self.kv_floats.get(field_name, [default])
        else:
            return default
        
        return values[0] if field.field_type == "single" else values
    
    def set_value(
        self,
        field_name: str,
        value: Any,
        project_config: ProjectConfig,
    ) -> None:
        """Set field value, respecting config type."""
        field = project_config.get_special_field(field_name)
        if not field:
            raise ValueError(f"Unknown field: {field_name}")
        
        if not field.editable:
            raise ValueError(f"Field '{field_name}' is not editable")
        
        if field.value_type == "string":
            self.kv_strings[field_name] = [value] if field.field_type == "single" else value
        elif field.value_type == "integer":
            self.kv_integers[field_name] = [int(value)] if field.field_type == "single" else [int(v) for v in value]
        elif field.value_type == "float":
            self.kv_floats[field_name] = [float(value)] if field.field_type == "single" else [float(v) for v in value]
    
    def to_markdown(self, project_config: ProjectConfig) -> str:
        """Serialize to Markdown with TOML frontmatter."""
        toml_dict = {}
        
        # Extract special fields for TOML section (in order they're defined)
        for field_name in project_config.get_special_fields().keys():
            field = project_config.get_special_field(field_name)
            
            if field.field_type == "single":
                if field.value_type == "string":
                    value = self.kv_strings.get(field_name, [''])[0]
                elif field.value_type == "integer":
                    value = self.kv_integers.get(field_name, [0])[0]
                elif field.value_type == "float":
                    value = self.kv_floats.get(field_name, [0.0])[0]
            else:  # multi
                if field.value_type == "string":
                    value = self.kv_strings.get(field_name, [])
                elif field.value_type == "integer":
                    value = self.kv_integers.get(field_name, [])
                elif field.value_type == "float":
                    value = self.kv_floats.get(field_name, [])
            
            toml_dict[field_name] = value
        
        toml_str = toml_w.dumps(toml_dict)
        
        # Any OTHER KV data (custom fields not in special_fields)
        other_kv = self._get_other_kv(project_config)
        other_section = ""
        if other_kv:
            # Add type hints to custom field keys
            hinted_kv = {}
            for key, val in other_kv.items():
                # Determine type from which dict it came from
                if key in self.kv_strings:
                    hinted_key = self._add_type_hint(key, "string")
                elif key in self.kv_integers:
                    hinted_key = self._add_type_hint(key, "integer")
                elif key in self.kv_floats:
                    hinted_key = self._add_type_hint(key, "float")
                else:
                    hinted_key = key
                hinted_kv[hinted_key] = val
            
            other_section = f"\n## Custom Fields\n\n{toml_w.dumps(hinted_kv)}"
        
        return f"+++\n{toml_str}+++\n\n{other_section}"
    
    def _get_other_kv(self, project_config: ProjectConfig) -> dict:
        """Get KV data that's NOT special fields."""
        special_names = set(project_config.get_special_fields().keys())
        
        other = {}
        for key in self.kv_strings.keys():
            if key not in special_names:
                other[key] = self.kv_strings[key]
        for key in self.kv_integers.keys():
            if key not in special_names:
                other[key] = self.kv_integers[key]
        for key in self.kv_floats.keys():
            if key not in special_names:
                other[key] = self.kv_floats[key]
        
        return other
    
    @classmethod
    def from_markdown(
        cls,
        content: str,
        incident_id: str,
        project_config: ProjectConfig,
    ) -> "Incident":
        """Deserialize from Markdown."""
        # Parse TOML frontmatter
        match = re.match(r'^\+\+\+\n(.*?)\n\+\+\+', content, re.DOTALL)
        if not match:
            raise ValueError("Invalid Markdown format: missing TOML frontmatter")
        
        toml_dict = tomli.loads(match.group(1))
        
        # Rebuild KV from special fields
        kv_strings = {}
        kv_integers = {}
        kv_floats = {}
        
        special_fields = project_config.get_special_fields()
        special_field_names = set(special_fields.keys())
        
        # Process items in frontmatter TOML
        for field_name, value in toml_dict.items():
            if field_name in special_field_names:
                # Handle as special field
                field = special_fields[field_name]
                
                if field.field_type == "single":
                    if field.value_type == "string":
                        kv_strings[field_name] = [value]
                    elif field.value_type == "integer":
                        kv_integers[field_name] = [int(value)]
                    elif field.value_type == "float":
                        kv_floats[field_name] = [float(value)]
                else:  # multi
                    if not isinstance(value, list):
                        value = [value]
                    if field.value_type == "string":
                        kv_strings[field_name] = value
                    elif field.value_type == "integer":
                        kv_integers[field_name] = [int(v) for v in value]
                    elif field.value_type == "float":
                        kv_floats[field_name] = [float(v) for v in value]
            else:
                # Handle as custom field - should be in "Custom Fields" section
                # Skip frontmatter items not in special_fields
                pass
        
        # Parse "Custom Fields" section if present
        rest = content[match.end():].strip()
        if rest.startswith("## Custom Fields"):
            custom_match = re.search(r'## Custom Fields\n\n(.*)', rest, re.DOTALL)
            if custom_match:
                try:
                    custom_toml = toml.loads(custom_match.group(1))
                    for key_with_hint, val in custom_toml.items():
                        # Strip type hint from key
                        clean_key, value_type = cls._strip_type_hint(key_with_hint)
                        
                        # Store in appropriate KV dictionary
                        if value_type == "string":
                            if isinstance(val, list):
                                kv_strings[clean_key] = val
                            else:
                                kv_strings[clean_key] = [str(val)]
                        elif value_type == "integer":
                            if isinstance(val, list):
                                kv_integers[clean_key] = [int(v) for v in val]
                            else:
                                kv_integers[clean_key] = [int(val)]
                        elif value_type == "float":
                            if isinstance(val, list):
                                kv_floats[clean_key] = [float(v) for v in val]
                            else:
                                kv_floats[clean_key] = [float(val)]
                        else:
                            # No type hint - shouldn't happen, but fallback to string
                            if isinstance(val, list):
                                kv_strings[clean_key] = [str(v) for v in val]
                            else:
                                kv_strings[clean_key] = [str(val)]
                except Exception as e:
                    print(f"Warning: Failed to parse custom fields: {e}", file=sys.stderr)
        
        return cls(
            id=incident_id,
            kv_strings=kv_strings or None,
            kv_integers=kv_integers or None,
            kv_floats=kv_floats or None,
        )


@dataclass
class IncidentUpdate:
    """Update/comment on an incident."""

    id: str
    incident_id: str
    timestamp: str
    author: str
    message: str
    kv_strings: Optional[Dict[str, List[str]]] = None
    kv_integers: Optional[Dict[str, List[int]]] = None
    kv_floats: Optional[Dict[str, List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "author": self.author,
            "message": self.message,
        }
        if self.kv_strings:
            d["kv_strings"] = self.kv_strings
        if self.kv_integers:
            d["kv_integers"] = self.kv_integers
        if self.kv_floats:
            d["kv_floats"] = self.kv_floats
        return d
        
    def to_markdown(self) -> str:
        """Convert update to Markdown with TOML header."""
        
        def dict_to_toml_inline(d):
            """Convert dict to inline TOML table format."""
            if not d:
                return "{}"
            items = []
            for key, value in d.items():
                if isinstance(value, str):
                    items.append(f'"{key}" = "{value}"')
                elif isinstance(value, (int, float)):
                    items.append(f'"{key}" = {value}')
                elif isinstance(value, list):
                    # Handle list values
                    formatted_values = [f'"{v}"' if isinstance(v, str) else str(v) for v in value]
                    items.append(f'"{key}" = [{", ".join(formatted_values)}]')
            return "{ " + ", ".join(items) + " }"
        
        toml_header = f"""+++
id = "{self.id}"
incident_id = "{self.incident_id}"
timestamp = "{self.timestamp}"
author = "{self.author}"
kv_strings = {dict_to_toml_inline(self.kv_strings or {})}
kv_integers = {dict_to_toml_inline(self.kv_integers or {})}
kv_floats = {dict_to_toml_inline(self.kv_floats or {})}
+++

"""
        return toml_header + self.message

    @classmethod
    def from_markdown(cls, content: str, update_id: str, incident_id: str) -> "IncidentUpdate":
        """Parse update from Markdown with TOML header."""
        # Split on +++ delimiter
        parts = content.split("+++")
        if len(parts) < 3:
            raise ValueError("Invalid update file format")

        toml_str = parts[1].strip()
        message = parts[2].strip() if len(parts) > 2 else ""

        try:
            data = tomllib.loads(toml_str)
        except Exception as e:
            raise ValueError(f"Failed to parse TOML header: {e}")

        # Parse KV data with type conversions
        kv_strings = data.get("kv_strings", {})
        kv_integers = {}
        kv_floats = {}
        
        # Convert integer strings to integers
        for key, values in data.get("kv_integers", {}).items():
            kv_integers[key] = [int(v) if isinstance(v, str) else v for v in values]
        
        # Convert float strings to floats
        for key, values in data.get("kv_floats", {}).items():
            kv_floats[key] = [float(v) if isinstance(v, str) else v for v in values]

        return cls(
            id=data.get("id", update_id),
            incident_id=data.get("incident_id", incident_id),
            timestamp=data.get("timestamp", ""),
            author=data.get("author", ""),
            message=message if message else "",
            kv_strings=kv_strings if kv_strings else None,
            kv_integers=kv_integers if kv_integers else None,
            kv_floats=kv_floats if kv_floats else None,
        )


# ============================================================================
# ID Generation
# ============================================================================

class IDGenerator:

    @staticmethod
    def to_base36(num: int) -> str:
        """Convert a positive integer to Base36 (0-9, A-Z)."""
        if num < 0:
            raise ValueError("Base36 conversion requires non-negative integer")
 
        chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        if num == 0:
            return "0"

        result = []
        while num:
            num, rem = divmod(num, 36)
            result.append(chars[rem])
        return "".join(reversed(result))
    
    @staticmethod
    def generate_incident_id() -> str:
        """
        Generate a distributed-safe incident ID based on epoch time.
        Format: INC-<base36 epoch nanoseconds>
        """
        epoch_ns = time.time_ns()
        return f"INC-{IDGenerator.to_base36(epoch_ns)}"

    @staticmethod
    def generate_update_filename() -> str:
        epoch_ns = time.time_ns()
        rand = secrets.token_hex(2)  # small entropy bump
        return f"UPD-{IDGenerator.to_base36(epoch_ns)}-{rand}.md"

    @staticmethod
    def generate_update_id() -> str:
        return IDGenerator.generate_update_filename().removesuffix(".md")


# ============================================================================
# DICTIONARY HELPER
# ============================================================================

class ConfigDict(dict):
    """Dict that also supports dot notation for attribute access"""
    
    def __getattr__(self, key):
        try:
            value = self[key]
            # Recursively wrap nested dicts
            if isinstance(value, dict) and not isinstance(value, ConfigDict):
                value = ConfigDict(value)
                self[key] = value
            return value
        except KeyError:
            raise AttributeError(f"No attribute '{key}'")
    
    def __setattr__(self, key, value):
        self[key] = value
    
    def __delattr__(self, key):
        try:
            del self[key]
        except KeyError:
            raise AttributeError(f"No attribute '{key}'")

# ============================================================================
# Project Configuration
# ============================================================================

class SpecialField:
    """Definition of a special (meta) field."""
    
    def __init__(
        self,
        name: str,
        field_type: str,  # "single" or "multi"
        value_type: str = "string",  # "string", "integer", "float"
        accepted_values: Optional[List[str]] = None,
        editable: bool = True,
    ):
        self.name = name
        self.field_type = field_type  # single vs multi-value
        self.value_type = value_type
        self.accepted_values = accepted_values or []
        self.editable = editable
    
    def validate(self, value: Any) -> bool:
        """Check if value is acceptable."""
        if self.accepted_values and str(value) not in self.accepted_values:
            return False
        return True


class ProjectConfig:
    """Project-level configuration (stored in .aver/config.toml)."""
    
    def __init__(self, db_root: Path):
        self.db_root = db_root
        self.config_path = db_root / "config.toml"
        self._raw_config = {}
        self._special_fields: Dict[str, SpecialField] = {}
        self.load()
    
    def load(self):
        """Load and parse project config."""
        if not self.config_path.exists():
            self._init_defaults()
            return
        
        try:
            with open(self.config_path, "rb") as f:
                self._raw_config = tomllib.load(f)
        except Exception as e:
            print(f"Warning: Failed to read project config: {e}", file=sys.stderr)
            self._init_defaults()
            return
        
        self._parse_special_fields()
    
    def _init_defaults(self):
        """Initialize with sensible defaults."""
        self._raw_config = {
            "special_fields": {
                "title": {
                    "type": "single",
                    "value_type": "string",
                    "editable": True,
                },
            }
        }
        self._parse_special_fields()
    
    def _parse_special_fields(self):
        """Parse special_fields section into SpecialField objects."""
        self._special_fields = {}
        
        special_fields_config = self._raw_config.get("special_fields", {})
        
        for field_name, field_def in special_fields_config.items():
            field_type = field_def.get("type", "single")
            value_type = field_def.get("value_type", "string")
            accepted_values = field_def.get("accepted_values", [])
            editable = field_def.get("editable", True)
            
            self._special_fields[field_name] = SpecialField(
                name=field_name,
                field_type=field_type,
                value_type=value_type,
                accepted_values=accepted_values,
                editable=editable,
            )
    
    def get_special_fields(self) -> Dict[str, SpecialField]:
        """Get all special field definitions."""
        return self._special_fields
    
    def get_special_field(self, name: str) -> Optional[SpecialField]:
        """Get specific special field definition."""
        return self._special_fields.get(name)
    
    def is_special_field(self, name: str) -> bool:
        """Check if field is a special field."""
        return name in self._special_fields
    
    def validate_field(self, name: str, value: Any) -> tuple[bool, Optional[str]]:
        """
        Validate a field value.
        
        Returns:
            (is_valid, error_message)
        """
        field = self._special_fields.get(name)
        if not field:
            return False, f"Unknown field: {name}"
        
        if field.accepted_values and str(value) not in field.accepted_values:
            return False, f"Invalid {name}: {value}. Accepted: {field.accepted_values}"
        
        return True, None
    
    def save(self):
        """Save config back to file."""
        if not toml_writer:
            raise RuntimeError(
                "tomli_w not available. Cannot write TOML config.\n"
                "Install with: pip install tomli_w"
            )
        with open(self.config_path, "wb") as f:
            toml_writer.dump(self._raw_config, f)


# ============================================================================
# Database Discovery & Configuration
# ============================================================================


class DatabaseDiscovery:
    """Find and manage the incident database location."""

    # =========================================================================
    # User/Project Config Paths
    # =========================================================================

    @staticmethod
    def get_user_config_path() -> Path:
        """Return the path to the global user configuration file (~/.config/aver/user.toml)."""
        config_dir = Path.home() / ".config" / "aver"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "user.toml"

    @staticmethod
    def get_project_config_path(db_root: Path) -> Path:
        """Return the path to the project config file (.aver/config.toml)."""
        return db_root / "config.toml"

    @staticmethod
    def get_user_config() -> dict:
        """
        Wrapper function to load and validate user configuration.
        
        Handles errors gracefully and provides actionable error messages.
        
        Returns:
            Configuration dictionary with validated required fields, or empty dict if file missing
        """
        try:
            return DatabaseDiscovery._do_get_user_config()
        except ValueError as e:
            print(f"Configuration error: {e}", file=sys.stderr)
            sys.exit(1)
        except PermissionError as e:
            print(f"Permission error: {e}", file=sys.stderr)
            sys.exit(1)

    def dict_to_namespace(d):
        """
        Recursively convert a dictionary to SimpleNamespace for dot notation access.
    
        Handles nested dicts, lists of dicts, and preserves other types.
        """
        if isinstance(d, dict):
            return SimpleNamespace(**{k: DatabaseDiscovery.dict_to_namespace(v) for k, v in d.items()})
        elif isinstance(d, list):
            return [dict_to_namespace(item) for item in d]
        else:
            return d

    @staticmethod
    def _do_get_user_config() -> dict:
        """
        Load the global user configuration from ~/.config/aver/user.toml.
        
        Required fields (if file exists):
        - handle: User identifier/name
        - email_address: User email
        
        Returns:
            Configuration dictionary with validated required fields, or empty dict if file missing
            
        Raises:
            ValueError: If required fields are missing or invalid
            PermissionError: If config file cannot be read due to permissions
        """
        config_path = DatabaseDiscovery.get_user_config_path()
        
        # No config file is acceptable; return empty dict
        if not config_path.exists():
            return {}
        
        try:
            with open(config_path, "rb") as f:
                config = tomllib.load(f)
        except tomllib.TOMLDecodeError as e:
            raise ValueError(
                f"Invalid TOML syntax in {config_path}: {e}\n"
                f"To reset your configuration, run:\n\n"
                f"  aver config set-user-global --handle <your-handle> --email <your-email>"
            )
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied reading {config_path}: {e}"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to read user config from {config_path}: {e}"
            )
        
        
        # Validate required fields exist
        required_user_fields = ["handle", "email"]
        missing_user_fields = [field for field in required_user_fields if field not in config["user"]]
        
        if missing_user_fields:
            raise ValueError(
                f"User configuration at {config_path} is missing required fields: "
                f"{', '.join(missing_fields)}\n\n"
                f"Please configure your user identity:\n\n"
                f"  aver config set-user-global --handle <your-handle> --email <your-email>\n\n"
            )
        
        # Validate required fields are not empty
        for field in required_user_fields:
            value = config["user"][field]
            if not isinstance(value, str):
                raise ValueError(
                    f"Field '{field}' in {config_path} must be a string, "
                    f"got {type(value).__name__}\n\n"
                    f"To fix this, run:\n\n"
                    f"  aver config set-user-global --handle <your-handle> --email <your-email>"
                )
            if not value.strip():
                raise ValueError(
                    f"Field '{field}' in {config_path} cannot be empty\n\n"
                    f"To fix this, run:\n\n"
                    f"  aver config set-user-global --handle <your-handle> --email <your-email>"
                )
        
        # Validate email_address format (basic check)
        email = config["user"]["email"].strip()
        if "@" not in email or "." not in email.split("@")[-1]:
            raise ValueError(
                f"Field 'email_address' in {config_path} appears invalid: '{email}'\n"
                f"Expected format: user@example.com\n\n"
                f"To fix this, run:\n\n"
                f"  aver config set-user-global --handle <your-handle> --email <your-email>\n\n"
                f"Example:\n"
                f"  aver config set-user-global --handle mattd --email dentm42@gmail.com"
            )
        
        # Store trimmed versions to remove accidental whitespace
        config["user"]["handle"] = config["user"]["handle"].strip()
        config["user"]["email"] = email
        
        def dict_to_configdict(d):
            if isinstance(d, dict):
                return ConfigDict({k: dict_to_configdict(v) for k, v in d.items()})
            elif isinstance(d, list):
                return [dict_to_configdict(item) for item in d]
            else:
                return d
        
        # return DatabaseDiscovery.dict_to_namespace(config)
        return dict_to_configdict(config)
    @staticmethod
    def set_user_config(config: dict):
        """Save the global user configuration."""
        if not toml_writer:
            raise RuntimeError(
                "tomli_w not available. Cannot write TOML config.\n"
                "Install with: pip install tomli_w"
            )
        config_path = DatabaseDiscovery.get_user_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "wb") as f:
            toml_writer.dump(config, f)

    @staticmethod
    def get_project_config(db_root: Path) -> dict:
        """Load the project configuration from .aver/config.toml."""
        config_path = DatabaseDiscovery.get_project_config_path(db_root)
        if not config_path.exists():
            return {}
        try:
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Warning: Failed to read project config: {e}", file=sys.stderr)
            return {}

    @staticmethod
    def set_project_config(db_root: Path, config: dict):
        """Save the project configuration."""
        if not toml_writer:
            raise RuntimeError(
                "tomli_w not available. Cannot write TOML config.\n"
                "Install with: pip install tomli_w"
            )
        config_path = DatabaseDiscovery.get_project_config_path(db_root)
        with open(config_path, "wb") as f:
            toml_writer.dump(config, f)

    # =========================================================================
    # Database Discovery
    # =========================================================================

    @staticmethod
    def find_all_databases(explicit_location: Optional[Path] = None) -> Dict[str, Dict]:
        """
        Find all possible incident databases in scope.
    
        Returns databases in priority order:
        1. Explicit location (if provided)
        2. Git repository at/above CWD
        3. User config [locations] matching CWD (contextually relevant)
        4. Parent directories above CWD with .aver
        5. All other user config [locations] entries (secondary options)
    
        Returns:
            Dict mapping source_name -> {path, source_description, category}
        """
        candidates = {}
        cwd = Path.cwd()
    
        # 1) Explicit location (if provided, this is the only option)
        if explicit_location:
            db_path = Path(explicit_location).resolve()
            candidates['explicit'] = {
                'path': db_path,
                'source': f'Explicit: {explicit_location}',
                'category': 'explicit',
            }
            return candidates
        
        # 2) Git repository (contextually relevant)
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip()).resolve()
            candidate = repo_root / ".aver"
            if candidate.exists():
                candidates['git_repo'] = {
                    'path': candidate,
                    'source': f'Git repo: {repo_root}',
                    'category': 'contextual',
                }
        except subprocess.CalledProcessError:
            pass
    
        # 3) User config [locations] matching CWD (contextually relevant)
        matched_location = None
        user_db = DatabaseDiscovery.lookup_user_locations(cwd)
        if user_db:
            matched_location = user_db.resolve()
            candidates['user_locations_matched'] = {
                'path': matched_location,
                'source': f'User config [locations] (matched): {user_db}',
                'category': 'contextual',
            }
    
        # 4) Parent directory traversal (contextually relevant)
        current = cwd
        while True:
            candidate = current / ".aver"
            if candidate.exists():
                candidates['parent_dir'] = {
                    'path': candidate.resolve(),
                    'source': f'Parent directory: {current}',
                    'category': 'contextual',
                }
                break
            if current.parent == current:
                break
            current = current.parent
    
        # 5) All other user config [locations] entries (secondary options)
        user_config = DatabaseDiscovery.get_user_config()
        if 'locations' in user_config:
            for path_prefix, db_path in user_config['locations'].items():
                db_path_obj = Path(db_path).resolve()
                
                # Skip if already added (matched location or parent)
                if db_path_obj == matched_location or any(
                    c['path'] == db_path_obj for c in candidates.values()
                ):
                    continue
                
                # Only add if it exists
                if db_path_obj.exists():
                    key = f"user_locations_{path_prefix.replace('/', '_')}"
                    candidates[key] = {
                        'path': db_path_obj,
                        'source': f'User config [locations]: {path_prefix} → {db_path}',
                        'category': 'available',
                    }
    
        return candidates

        @staticmethod
        def select_database_interactive(candidates: Dict[str, Dict]) -> Path:
            """
            Present user with database choices grouped by category.
        
            Groups:
            - Contextual (closest match to current directory)
            - Available (other configured locations)
            """
            if not candidates:
                raise RuntimeError("No incident databases found")
        
            if len(candidates) == 1:
                selected = list(candidates.values())[0]
                print(f"Using: {selected['source']}")
                return selected['path']
        
            # Organize by category
            contextual = [(k, v) for k, v in candidates.items() if v.get('category') == 'contextual']
            available = [(k, v) for k, v in candidates.items() if v.get('category') == 'available']
            
            print("\n" + "="*70)
            print("Incident databases available:")
            print("="*70)
        
            all_items = []
    
            # Show contextual options first
            if contextual:
                print("\n[Contextual - closest match to current directory]")
                for idx, (key, info) in enumerate(contextual, 1):
                    all_items.append((key, info))
                    print(f"  [{idx}] {info['source']}")
                    print(f"      {info['path']}")
        
            # Show other available options
            if available:
                start_idx = len(contextual) + 1
                print(f"\n[Available - other configured locations]")
                for idx, (key, info) in enumerate(available, start_idx):
                    all_items.append((key, info))
                    print(f"  [{idx}] {info['source']}")
                    print(f"      {info['path']}")
        
            print("\n" + "="*70)
            while True:
                try:
                    choice = input(f"Select database (1-{len(all_items)}): ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(all_items):
                        selected = all_items[idx][1]
                        print(f"✓ Using: {selected['source']}\n")
                        return selected['path']
                except ValueError:
                    pass
                print("Invalid selection. Please try again.")
    
    @staticmethod
    def select_database_contextual(candidates: Dict[str, Dict]) -> Path:
        """
        Select database using contextual heuristics (no prompting).
        
        Priority order:
        1. Git repository (if in a git repo, that's usually what you want)
        2. User config [locations] matching CWD (closest contextual match)
        3. Parent directory .aver
        4. First available [locations] entry (fallback)
        
        Args:
            candidates: Dict from find_all_databases()
        
        Returns:
            Path to selected incident database
        
        Raises:
            RuntimeError: If no suitable database found
        """
        # Priority order of candidate keys
        priority = ['git_repo', 'user_locations_matched', 'parent_dir']
        
        # Try each priority level
        for key in priority:
            if key in candidates:
                selected = candidates[key]
                print(f"Using: {selected['source']}")
                return selected['path']
        
        # Fallback: use first available [locations] entry
        for key, info in candidates.items():
            if info.get('category') == 'available':
                print(f"Using: {info['source']}")
                return info['path']
        
        # Last resort: use any remaining candidate
        if candidates:
            selected = list(candidates.values())[0]
            print(f"Using: {selected['source']}")
            return selected['path']
        
        raise RuntimeError("No suitable incident database found")
 

    @staticmethod
    def lookup_user_locations(cwd: Path) -> Optional[Path]:
        """
        Check user-configured locations mapping for the current working directory.

        Longest matching parent key is used.
        Returns the mapped path if found, else None.

        Example user.toml:
        [locations]
        "/root/path" = "/path/to/data"
        "/root/path/longer" = "/other/path/to/data"
        """
        config = DatabaseDiscovery.get_user_config()
        locations = config.locations.items() if hasattr(config,"locations") else []
        cwd_resolved = cwd.resolve()

        matches = [
            (Path(key).resolve(), Path(value).resolve())
            for key, value in locations.items()
            if cwd_resolved.is_relative_to(Path(key).resolve())  # Python 3.9+
        ]

        if not matches:
            return None

        # Pick the longest matching prefix (most specific parent)
        longest_match = max(matches, key=lambda t: len(str(t[0])))
        return longest_match[1]

    @staticmethod
    def find_database(explicit_location: Optional[Path] = None, verbose: bool = False) -> Optional[Path]:
        """
        Determine the incident database location.

        Priority:
        1) Explicit --location
        2) Git repository root (.aver)
        3) User config [locations] (longest matching parent)
        4) Parent directories search for .aver (closest wins)
        5) None if not found

        Args:
            explicit_location: Optional explicit database path
            verbose: If True, prints which source was used

        Returns:
            Path to incident database, or None if not found
        """
        cwd = Path.cwd()

        # 1) Explicit location
        if explicit_location:
            db_path = Path(explicit_location).resolve()
            if verbose:
                print(f"[DatabaseDiscovery] Using explicit location: {db_path}")
            return db_path

        # 2) Git repository detection
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip()).resolve()
            candidate = repo_root / ".aver"
            if candidate.exists():
                if verbose:
                    print(f"[DatabaseDiscovery] Using git repo location: {candidate}")
                return candidate
        except subprocess.CalledProcessError:
            pass

        # 3) User config [locations] lookup
        user_db = DatabaseDiscovery.lookup_user_locations(cwd)
        if user_db:
            if verbose:
                print(f"[DatabaseDiscovery] Using user-config location: {user_db}")
            return user_db.resolve()

        # 4) Parent directory search
        current = cwd
        while True:
            candidate = current / ".aver"
            if candidate.exists():
                if verbose:
                    print(f"[DatabaseDiscovery] Using parent directory location: {candidate}")
                return candidate.resolve()
            if current.parent == current:
                break
            current = current.parent

        # 5) Not found
        if verbose:
            print("[DatabaseDiscovery] No incident database found")
        return None

    @staticmethod
    def find_database_or_fail(explicit_location: Optional[Path] = None, verbose: bool = False) -> Path:
        """Return the database path, or raise RuntimeError if not found."""
        db = DatabaseDiscovery.find_database(explicit_location=explicit_location, verbose=verbose)
        if not db:
            raise RuntimeError(
                "No incident database found.\n"
                "Initialize with: incident init\n"
                "Or: incident init --location /path/to/db"
            )
        return db

    @staticmethod
    def enforce_repo_boundary(db_root: Path, override: bool = False) -> bool:
        """
        Enforce that if running inside a git repo, db_root must be within that repo.
    
        Returns:
            True if check passes (not in repo, or db is in repo, or override is set)
            False if check fails (in repo, but db is outside repo)
        """
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip()).resolve()
            db_resolved = db_root.resolve()
        
            # Check if db_root is within repo_root
            try:
                db_resolved.relative_to(repo_root)
                return True  # db is within repo
            except ValueError:
                # db is NOT within repo
                if override:
                    return True
                return False
        except subprocess.CalledProcessError:
            # Not in a git repo, so check doesn't apply
            return True


# ============================================================================
# Editor Management
# ============================================================================


class EditorConfig:
    """Manage editor configuration and launching."""

    @staticmethod
    def get_editor() -> str:
        """
        Get configured editor in order of precedence:
        1. User-global config (~/.config/incident-manater/user.toml)
        2. EDITOR environment variable
        3. System defaults (vim, nano, vi, emacs)
        """
        # Check user config
        user_config = DatabaseDiscovery.get_user_config()
        if "editor" in user_config:
            return user_config["editor"]

        # Check environment variable
        editor = os.environ.get("EDITOR")
        if editor:
            return editor

        # Try common editors
        for editor_name in ["vim", "nano", "vi", "emacs"]:
            if EditorConfig._editor_exists(editor_name):
                return editor_name

        raise RuntimeError(
            "No editor found. Set EDITOR environment variable or run:\n"
            "  incident config set-editor <editor>"
        )

    @staticmethod
    def _editor_exists(editor_name: str) -> bool:
        """Check if editor is available in PATH."""
        result = subprocess.run(
            ["which", editor_name],
            capture_output=True,
        )
        return result.returncode == 0

    @staticmethod
    def launch_editor(initial_content: str = "") -> str:
        """
        Launch editor for user input.

        Args:
            initial_content: Pre-fill editor with this content

        Returns:
            User-edited content

        Raises:
            RuntimeError: If editor not found or user cancels
        """
        editor = EditorConfig.get_editor()

        # Create temp file
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".txt",
            delete=False,
        ) as f:
            temp_file = f.name
            if initial_content:
                f.write(initial_content)

        try:
            # Launch editor
            subprocess.run(
                [editor, temp_file],
                check=True,
            )

            # Read result
            with open(temp_file, "r") as f:
                content = f.read()

            # Strip trailing whitespace
            content = content.strip()

            if not content:
                raise RuntimeError("No content provided (file was empty)")

            return content

        finally:
            # Clean up
            try:
                os.unlink(temp_file)
            except:
                pass


# ============================================================================
# STDIN Handler
# ============================================================================


class StdinHandler:
    """Handle reading from STDIN with detection."""

    @staticmethod
    def has_stdin_data() -> bool:
        """
        Check if data is available on STDIN without blocking.

        Returns:
            True if STDIN has data ready to read
        """
        # Check if we're in a TTY (interactive terminal)
        if sys.stdin.isatty():
            return False

        # Use select to check for available data (Unix/Linux/macOS)
        try:
            ready, _, _ = select.select([sys.stdin], [], [], 0)
            return bool(ready)
        except Exception:
            # Fallback: on Windows or if select fails
            return not sys.stdin.isatty()

    @staticmethod
    def read_stdin_with_timeout(timeout: float = 2.0) -> Optional[str]:
        """
        Read STDIN if available, with optional timeout.

        Args:
            timeout: Seconds to wait for input (0 = no wait, -1 = infinite)

        Returns:
            Content from STDIN or None if no data available

        Raises:
            RuntimeError: If STDIN read fails
        """
        if sys.stdin.isatty():
            return None

        try:
            # Use select for non-blocking read (Unix/Linux/macOS)
            if hasattr(select, "select"):
                ready, _, _ = select.select([sys.stdin], [], [], timeout)
                if not ready:
                    return None

            content = sys.stdin.read()
            return content.strip() if content else None

        except Exception as e:
            raise RuntimeError(f"Failed to read from STDIN: {e}")

# ============================================================================
# Key-Value Store Support
# ============================================================================

class KVParser:
    """Parse and validate key-value format strings."""
    
    # Type indicators
    TYPE_STRING = '$'
    TYPE_INTEGER = '#'
    TYPE_FLOAT = '%'
    VALID_OPERATORS = {TYPE_STRING, TYPE_INTEGER, TYPE_FLOAT}
    
    @staticmethod
    def parse_kv_string(kv_str: str) -> tuple:
        """
        Parse a key-value format string.
        
        Format: {key}{type}{value}
        - $ = string
        - # = integer  
        - % = float
        
        Removal formats:
        - {key}- (for -kv mode)
        - {key}{type}{value}- (for -kmv mode)
        
        Args:
            kv_str: Key-value string to parse
            
        Returns:
            (key, type, '+', value) tuple or (key, type, '-', value) for removal
            
        Raises:
            ValueError: If format is invalid
        """
        # Pre-validation: check input is a string
        if not isinstance(kv_str, str):
            raise ValueError(f"Input must be a string, got {type(kv_str).__name__}")
        
        kv_str = kv_str.strip()
        
        # Pre-validation: check string is not empty after stripping
        if not kv_str:
            raise ValueError("Key-value string cannot be empty")
        
        # Pre-validation: check for invalid characters at start
        if kv_str[0] in (KVParser.TYPE_STRING, KVParser.TYPE_INTEGER, KVParser.TYPE_FLOAT):
            raise ValueError(f"Key-value string cannot start with operator '{kv_str[0]}'")
        
        # Pre-validation: check for multiple operators (except trailing dash)
        kv_check = kv_str.rstrip('-')
        operator_count = sum(kv_check.count(op) for op in KVParser.VALID_OPERATORS)
        if operator_count > 1:
            raise ValueError(f"Key-value string contains multiple operators: '{kv_str}'")
        
        # Pre-validation: check for operator immediately followed by dash (invalid pattern)
        for kvtype in KVParser.VALID_OPERATORS:
            if kvtype + '-' in kv_str:
                raise ValueError(f"Invalid pattern '{kvtype}-': operator cannot be immediately followed by dash")
        
        # Check for removal format: key- or key${value}-
        if kv_str.endswith('-'):
            kv_str = kv_str[:-1]  # Remove trailing dash
            is_removal = True
            
            # Validate: after removing dash, string should not be empty
            if not kv_str:
                raise ValueError("Key cannot be empty in removal format")
        else:
            is_removal = False
        
        # Find operator
        for kvtype in KVParser.VALID_OPERATORS:
            idx = kv_str.find(kvtype)
            if idx > 0:  # Must have a key before operator
                key = kv_str[:idx]
                value_str = kv_str[idx+1:]
                
                # Validate key format
                if not key:
                    raise ValueError("Key cannot be empty")
                if not KVParser._is_valid_key(key):
                    raise ValueError(
                        f"Invalid key '{key}': keys must contain only alphanumeric characters, "
                        f"underscores, and hyphens"
                    )
                
                # Validate value presence
                if not value_str and not is_removal:
                    raise ValueError(f"Value cannot be empty for key '{key}'")
                
                # Validate that there are no extra operators in value
                for other_op in KVParser.VALID_OPERATORS:
                    if other_op in value_str:
                        raise ValueError(
                            f"Value for key '{key}' contains invalid operator '{other_op}': "
                            f"'{value_str}'"
                        )
                
                # Convert value to appropriate type
                if kvtype == KVParser.TYPE_STRING:
                    # String values can be empty in removal mode
                    value = value_str if value_str else None
                elif kvtype == KVParser.TYPE_INTEGER:
                    if value_str:
                        # Check for leading zeros (optional validation)
                        if value_str.startswith('0') and len(value_str) > 1:
                            raise ValueError(
                                f"Invalid integer value '{value_str}' for key '{key}': "
                                f"leading zeros are not allowed"
                            )
                        try:
                            value = int(value_str)
                        except ValueError:
                            raise ValueError(
                                f"Invalid integer value '{value_str}' for key '{key}': "
                                f"not a valid integer"
                            )
                    else:
                        value = None
                elif kvtype == KVParser.TYPE_FLOAT:
                    if value_str:
                        try:
                            value = float(value_str)
                            # Check for special float values if needed
                            if value_str.lower() in ('inf', '-inf', 'nan'):
                                raise ValueError(
                                    f"Invalid float value '{value_str}' for key '{key}': "
                                    f"special values (inf, nan) are not allowed"
                                )
                        except ValueError:
                            raise ValueError(
                                f"Invalid float value '{value_str}' for key '{key}': "
                                f"not a valid float"
                            )
                    else:
                        value = None
                
                return (key, kvtype, '+' if not is_removal else '-', value)
        
        # Check for kv mode removal (key-)
        if is_removal:
            if not kv_str:
                raise ValueError("Key cannot be empty in removal format")
            if not self._is_valid_key(kv_str):
                raise ValueError(
                    f"Invalid key '{kv_str}': keys must contain only alphanumeric characters, "
                    f"underscores, and hyphens"
                )
            return (kv_str, None, '-', None)
        
        # No operator found
        raise ValueError(
            f"Invalid key-value format: '{kv_str}'\n"
            f"Expected: '{{key}}${{string}}', '{{key}}#{{int}}', or '{{key}}%{{float}}'\n"
            f"For removal: '{{key}}-' (kv mode) or '{{key}}${{val}}-' (kmv mode)\n"
            f"Keys must contain only alphanumeric characters, underscores, and hyphens"
        )
    
    @staticmethod
    def _is_valid_key(key: str) -> bool:
        """
        Validate that a key conforms to allowed format.
        
        Args:
            key: Key string to validate
            
        Returns:
            True if key is valid, False otherwise
        """
        if not key:
            return False
        # Allow alphanumeric, underscores, and hyphens
        return all(c.isalnum() or c in ('_', '-') for c in key)
    
    @staticmethod
    def parse_kv_list(kv_list: List[str]) -> List[tuple]:
        """Parse list of key-value strings."""
        result = []
        for kv_str in kv_list:
            result.append(KVParser.parse_kv_string(kv_str))
        return result


class KVSearchParser:
    """Parse key-value search and sort expressions."""
    
    VALID_OPERATORS = {'<', '>', '=', '<=', '>='}
    
    @staticmethod
    def parse_ksearch(search_expr: str) -> tuple:
        """
        Parse key-value search expression.
        
        Format: {key} {operator} {value}
        Operators: <, >, =, <=, >=
        
        Examples:
        - "cost > 12.49"
        - "priority=high"
        - "count<=100"
        
        Args:
            search_expr: Search expression string
            
        Returns:
            (key, operator, value) tuple
            
        Raises:
            ValueError: If format is invalid
        """
        search_expr = search_expr.strip()
        
        # Try to find operators (check longer ones first)
        for op in ['<=', '>=', '<', '>', '=']:
            if op in search_expr:
                parts = search_expr.split(op, 1)
                if len(parts) == 2:
                    key = parts[0].strip()
                    value_str = parts[1].strip()
                    
                    if not key or not value_str:
                        raise ValueError(f"Invalid search format: '{search_expr}'")
                    
                    return (key, op, value_str)
        
        raise ValueError(
            f"Invalid ksearch format: '{search_expr}'\n"
            f"Expected: '{{key}} {{operator}} {{value}}'\n"
            f"Operators: <, >, =, <=, >="
        )
    
    @staticmethod
    def parse_ksort(sort_expr: str) -> List[tuple]:
        """
        Parse key-value sort expression.
        
        Format: key1,key2+,key3-
        - No suffix or + = ascending
        - - = descending
        
        Args:
            sort_expr: Sort expression string (comma-delimited)
            
        Returns:
            List of (key, ascending) tuples
            
        Raises:
            ValueError: If format is invalid
        """
        if not sort_expr:
            return []
        
        result = []
        for key_spec in sort_expr.split(','):
            key_spec = key_spec.strip()
            if not key_spec:
                continue
            
            if key_spec.endswith('-'):
                key = key_spec[:-1]
                ascending = False
            elif key_spec.endswith('+'):
                key = key_spec[:-1]
                ascending = True
            else:
                key = key_spec
                ascending = True
            
            if not key:
                raise ValueError(f"Invalid ksort format: '{sort_expr}'")
            
            result.append((key, ascending))
        
        return result


# ============================================================================
# File Storage
# ============================================================================


class IncidentFileStorage:
    """Store incidents as Markdown files."""

    def __init__(self, storage_root: Path):
        """Initialize file storage.
        
        Args:
            storage_root: Root directory for incident files (.aver)
        """
        self.storage_root = storage_root
        self.incidents_dir = storage_root / "records"
        self.updates_dir = storage_root / "updates"
        
        # Create directories
        self.incidents_dir.mkdir(parents=True, exist_ok=True)
        self.updates_dir.mkdir(parents=True, exist_ok=True)

    def _get_incident_path(self, incident_id: str) -> Path:
        """Get file path for incident."""
        return self.incidents_dir / f"{incident_id}.md"

    def _get_updates_dir(self, incident_id: str) -> Path:
        """Get directory path for incident updates."""
        updates_dir = self.updates_dir / incident_id
        updates_dir.mkdir(parents=True, exist_ok=True)
        return updates_dir
            
    def save_incident(self, incident: Incident, project_config: ProjectConfig):
        """Save incident to Markdown file."""
        path = self._get_incident_path(incident.id)
        content = incident.to_markdown(project_config)
        
        with open(path, "w") as f:
            f.write(content)
    
    def load_incident(
        self,
        incident_id: str,
        project_config: ProjectConfig,
    ) -> Optional[Incident]:
        """Load incident from Markdown file."""
        path = self._get_incident_path(incident_id)
        
        if not path.exists():
            return None
        
        try:
            with open(path, "r") as f:
                content = f.read()
            return Incident.from_markdown(content, incident_id, project_config)
        except Exception as e:
            print(f"Warning: Failed to load incident {incident_id}: {e}", file=sys.stderr)
            return None

    def delete_incident(self, incident_id: str):
        """Delete incident file."""
        path = self._get_incident_path(incident_id)
        if path.exists():
            path.unlink()

    def list_incident_files(self) -> List[str]:
        """List all incident IDs from files."""
        incident_ids = []
        for file_path in self.incidents_dir.glob("INC-*.md"):
            incident_ids.append(file_path.stem)
        return sorted(incident_ids)

    def save_update(self, incident_id: str, update: IncidentUpdate):
        """Save update to Markdown file with TOML header."""
        updates_dir = self._get_updates_dir(incident_id)
        filename = IDGenerator.generate_update_filename()
        update_file = updates_dir / filename

        content = update.to_markdown()
        update_file.write_text(content)
    

    def load_updates(self, incident_id: str) -> List[IncidentUpdate]:
        """Load all updates for incident."""
        updates_dir = self._get_updates_dir(incident_id)
        updates = []
    
        for update_file in sorted(updates_dir.glob("*.md")):
            try:
                update_id = update_file.stem
                with open(update_file, "r") as f:
                    content = f.read()
            
                update = IncidentUpdate.from_markdown(content, update_id, incident_id)
                updates.append(update)
            except Exception as e:
                print(f"Warning: Failed to load update {update_file}: {e}", file=sys.stderr)
    
        return updates
 

# ============================================================================
# Index Database (UPDATED)
# ============================================================================

class IncidentIndexDatabase:
    """SQLite-based index for incidents (search and filtering only)."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self._ensure_schema()

    def _ensure_schema(self):
        """Create tables if they don't exist."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        # Incidents index table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents_index (
                id TEXT PRIMARY KEY,
                indexed_at TEXT NOT NULL
            )
            """
        )    
        # Full-text search index
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS incidents_fts
            USING fts5(incident_id UNINDEXED, source, source_id UNINDEXED, content)
            """
        )
    
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS incident_tags (
                incident_id TEXT NOT NULL,
                tag TEXT NOT NULL,
                PRIMARY KEY (incident_id, tag)
            )
        """)
    
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_incident_tags_tag
            ON incident_tags(tag)
        """)
    
        # Key-Value tables - NOW WITH update_id SUPPORT
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_strings (
                incident_id TEXT NOT NULL,
                update_id TEXT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, update_id, key, value)
            )
        """)
    
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_integers (
                incident_id TEXT NOT NULL,
                update_id TEXT,
                key TEXT NOT NULL,
                value INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, update_id, key, value)
            )
        """)
    
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_floats (
                incident_id TEXT NOT NULL,
                update_id TEXT,
                key TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, update_id, key, value)
            )
        """)
    
        # Indices for KV searching and sorting
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_strings_incident
            ON kv_strings(incident_id, update_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_strings_key
            ON kv_strings(key)
        """)
    
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_strings_value
            ON kv_strings(value)
        """)
    
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_integers_incident
            ON kv_integers(incident_id, update_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_integers_key
            ON kv_integers(key)
        """)
    
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_integers_value
            ON kv_integers(value)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_floats_incident
            ON kv_floats(incident_id, update_id)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_floats_key
            ON kv_floats(key)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_floats_value
            ON kv_floats(value)
        """)

        conn.commit()
        conn.close()

    def index_incident(self, incident: Incident, project_config: ProjectConfig):
        """Add or update incident in index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
        # Update minimal index entry
        cursor.execute(
            "INSERT OR REPLACE INTO incidents_index (id, indexed_at) VALUES (?, ?)",
            (incident.id, now),
        )
    
        # Index FTS for description and other content
        cursor.execute(
            "DELETE FROM incidents_fts WHERE incident_id = ? AND source = 'incident'",
            (incident.id,)
        )
    
        content = f"{incident.title}\n\n{incident.description or ''}"
        cursor.execute(
            "INSERT INTO incidents_fts (incident_id, source, source_id, content) VALUES (?, ?, ?, ?)",
            (incident.id, "incident", incident.id, content),
        )
    
        conn.commit()

    def remove_incident_from_index(self, incident_id: str):
        """Remove incident from index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM incidents_index WHERE id = ?", (incident_id,))
        cursor.execute("DELETE FROM incidents_fts WHERE incident_id = ?", (incident_id,))
        cursor.execute("DELETE FROM incident_tags WHERE incident_id = ?", (incident_id,))
        conn.commit()
        conn.close()

    def get_incident_from_index(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get incident data from index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM incidents_index WHERE id = ?", (incident_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            "id": row[0],
            "title": row[1],
            "created_at": row[2],
            "created_by": row[3],
            "severity": row[4],
            "status": row[5],
            "tags": json.loads(row[6]),
            "assignees": json.loads(row[7]),
            "updated_at": row[8],
        }

    def list_incidents_from_index(
        self,
        project_config: ProjectConfig,
        filters: Optional[Dict[str, Any]] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[str]:
        """List incident IDs from index with filters."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        # Start with all incidents
        incident_ids_query = "SELECT id FROM incidents_index"
        params = []
    
        # Apply special field filters
        if filters:
            for field_name, value in filters.items():
                field = project_config.get_special_field(field_name)
                if not field:
                    continue  # Skip unknown fields
            
                if field.value_type == "string":
                    table = "kv_strings"
                elif field.value_type == "integer":
                    table = "kv_integers"
                elif field.value_type == "float":
                    table = "kv_floats"
                else:
                    continue
            
                if field.field_type == "single":
                    incident_ids_query += f"""
                        AND id IN (
                            SELECT incident_id FROM {table}
                            WHERE key = ? AND value = ? AND update_id IS NULL
                        )
                    """
                    params.extend([field_name, value])
                else:  # multi - value must be in the list
                    incident_ids_query += f"""
                        AND id IN (
                            SELECT incident_id FROM {table}
                            WHERE key = ? AND value = ? AND update_id IS NULL
                        )
                    """
                    if isinstance(value, list):
                        # Match ANY value in the list
                        value_placeholders = ",".join("?" * len(value))
                        incident_ids_query = incident_ids_query.replace(
                            "AND value = ?",
                            f"AND value IN ({value_placeholders})"
                        )
                        params = params[:-1]  # Remove the last value
                        params.extend(value)
                    else:
                        params = params[:-1]
                        params.append(value)
     
        # Apply FTS search
        if search:
            incident_ids_query += """
                AND id IN (
                    SELECT DISTINCT incident_id FROM incidents_fts
                    WHERE incidents_fts MATCH ?
                )
            """
            params.append(search)
    
        incident_ids_query += f" ORDER BY id DESC LIMIT ?"
        params.append(limit)
    
        cursor.execute(incident_ids_query, params)
        incident_ids = [row[0] for row in cursor.fetchall()]
    
        conn.close()
        return incident_ids

    def index_update(self, update: IncidentUpdate):
        """Index update in FTS and store KV data."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO incidents_fts (incident_id, source, source_id, content) VALUES (?, ?, ?, ?)",
            (
                update.incident_id,
                "update",
                update.id,
                update.message,
            ),
        )

        conn.commit()
        conn.close()

    def clear_index(self):
        """Clear all entries from index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM incidents_index")
        cursor.execute("DELETE FROM incidents_fts")
        cursor.execute("DELETE FROM incident_tags")
        cursor.execute("DELETE FROM kv_strings")
        cursor.execute("DELETE FROM kv_integers")
        cursor.execute("DELETE FROM kv_floats")
        conn.commit()
        conn.close()

    def index_kv_data(self, incident: Incident):
        """Index key-value data for incident (update_id = NULL)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
        # Clear existing KV data for this incident (incident-level only)
        cursor.execute("DELETE FROM kv_strings WHERE incident_id = ? AND update_id IS NULL", (incident.id,))
        cursor.execute("DELETE FROM kv_integers WHERE incident_id = ? AND update_id IS NULL", (incident.id,))
        cursor.execute("DELETE FROM kv_floats WHERE incident_id = ? AND update_id IS NULL", (incident.id,))
    
        # Insert string KV data
        for key, values in (incident.kv_strings or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_strings (incident_id, update_id, key, value, created_at) VALUES (?, NULL, ?, ?, ?)",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass  # Duplicate, skip
    
        # Insert integer KV data
        for key, values in (incident.kv_integers or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_integers (incident_id, update_id, key, value, created_at) VALUES (?, NULL, ?, ?, ?)",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert float KV data
        for key, values in (incident.kv_floats or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_floats (incident_id, update_id, key, value, created_at) VALUES (?, NULL, ?, ?, ?)",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        conn.commit()
        conn.close()

    def index_update_kv_data(self, incident_id: str, update_id: str, 
                            kv_strings: Optional[Dict] = None,
                            kv_integers: Optional[Dict] = None,
                            kv_floats: Optional[Dict] = None):
        """Index key-value data for update (update_id is NOT NULL)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
        # Insert string KV data for update
        for key, values in (kv_strings or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_strings (incident_id, update_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
                        (incident_id, update_id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert integer KV data for update
        for key, values in (kv_integers or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_integers (incident_id, update_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
                        (incident_id, update_id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert float KV data for update
        for key, values in (kv_floats or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_floats (incident_id, update_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
                        (incident_id, update_id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        conn.commit()
        conn.close()
    
    def set_kv_single(self, incident_id: str, key: str, op: str, value: Any, update_id: Optional[str] = None):
        """Set single-value KV (replaces existing)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
        if op == KVParser.TYPE_STRING:
            table = "kv_strings"
        elif op == KVParser.TYPE_INTEGER:
            table = "kv_integers"
        elif op == KVParser.TYPE_FLOAT:
            table = "kv_floats"
        else:
            raise ValueError(f"Invalid operator: {op}")
    
        # Delete existing values for this key
        if update_id:
            cursor.execute(f"DELETE FROM {table} WHERE incident_id = ? AND update_id = ? AND key = ?", 
                          (incident_id, update_id, key))
        else:
            cursor.execute(f"DELETE FROM {table} WHERE incident_id = ? AND update_id IS NULL AND key = ?", 
                          (incident_id, key))
        
        # Insert new value
        cursor.execute(
            f"INSERT INTO {table} (incident_id, update_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
            (incident_id, update_id, key, value, now)
        )
    
        conn.commit()
        conn.close()
    
    def add_kv_multi(self, incident_id: str, key: str, op: str, value: Any, update_id: Optional[str] = None):
        """Add multi-value KV (keeps existing)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
        if op == KVParser.TYPE_STRING:
            table = "kv_strings"
        elif op == KVParser.TYPE_INTEGER:
            table = "kv_integers"
        elif op == KVParser.TYPE_FLOAT:
            table = "kv_floats"
        else:
            raise ValueError(f"Invalid operator: {op}")
    
        # Insert value (PRIMARY KEY prevents true duplication)
        try:
            cursor.execute(
                f"INSERT INTO {table} (incident_id, update_id, key, value, created_at) VALUES (?, ?, ?, ?, ?)",
                (incident_id, update_id, key, value, now)
            )
        except sqlite3.IntegrityError:
            pass  # Value already exists
    
        conn.commit()
        conn.close()
    
    def remove_kv_key(self, incident_id: str, key: str, update_id: Optional[str] = None):
        """Remove all values for a key."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        if update_id:
            cursor.execute("DELETE FROM kv_strings WHERE incident_id = ? AND update_id = ? AND key = ?", 
                          (incident_id, update_id, key))
            cursor.execute("DELETE FROM kv_integers WHERE incident_id = ? AND update_id = ? AND key = ?", 
                          (incident_id, update_id, key))
            cursor.execute("DELETE FROM kv_floats WHERE incident_id = ? AND update_id = ? AND key = ?", 
                          (incident_id, update_id, key))
        else:
            cursor.execute("DELETE FROM kv_strings WHERE incident_id = ? AND update_id IS NULL AND key = ?", 
                          (incident_id, key))
            cursor.execute("DELETE FROM kv_integers WHERE incident_id = ? AND update_id IS NULL AND key = ?", 
                          (incident_id, key))
            cursor.execute("DELETE FROM kv_floats WHERE incident_id = ? AND update_id IS NULL AND key = ?", 
                          (incident_id, key))
    
        conn.commit()
        conn.close()
    
    def remove_kv_value(self, incident_id: str, key: str, op: str, value: Any, update_id: Optional[str] = None):
        """Remove specific key/value pair."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        if op == KVParser.TYPE_STRING:
            table = "kv_strings"
        elif op == KVParser.TYPE_INTEGER:
            table = "kv_integers"
        elif op == KVParser.TYPE_FLOAT:
            table = "kv_floats"
        else:
            raise ValueError(f"Invalid operator: {op}")
    
        if update_id:
            cursor.execute(
                f"DELETE FROM {table} WHERE incident_id = ? AND update_id = ? AND key = ? AND value = ?",
                (incident_id, update_id, key, value)
            )
        else:
            cursor.execute(
                f"DELETE FROM {table} WHERE incident_id = ? AND update_id IS NULL AND key = ? AND value = ?",
                (incident_id, key, value)
            )
    
        conn.commit()
        conn.close()

    def search_kv(
        self, 
        ksearch_list: List[tuple], 
        incident_ids: Optional[List[str]] = None,
        update_ids: Optional[List[str]] = None,
        return_updates: bool = False
    ) -> List[str]:
        """
        Search by key-value criteria.
        
        Args:
            ksearch_list: List of (key, operator, value) tuples
            incident_ids: If provided, search only within these incidents (None = search all)
            update_ids: If provided, search only within these updates
            return_updates: If True, return update IDs; if False, return incident IDs
            
        Returns:
            List of matching incident IDs or update IDs (depending on return_updates)
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        matching_results = None
        
        # Determine which column to return
        return_column = "update_id" if return_updates else "incident_id"
        
        for key, operator, value in ksearch_list:
            results = set()
            
            # Build WHERE clause
            where_parts = []
            params = [key, value]
            
            if return_updates:
                # Must have update_id when searching for updates
                where_parts.append("update_id IS NOT NULL")
            
            if incident_ids:
                placeholders = ",".join("?" * len(incident_ids))
                where_parts.append(f"incident_id IN ({placeholders})")
                params.extend(incident_ids)
            
            if update_ids:
                placeholders = ",".join("?" * len(update_ids))
                where_parts.append(f"update_id IN ({placeholders})")
                params.extend(update_ids)
            elif not return_updates and incident_ids and not update_ids:
                # If searching for incidents and incident_ids specified but update_ids is None,
                # only search incident-level KV
                where_parts.append("update_id IS NULL")
            
            where_clause = " AND ".join(where_parts)
            where_clause = f"WHERE {where_clause}" if where_clause else ""
            
            # Try string search
            try:
                if operator == '=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_strings WHERE key = ? AND value = ? {where_clause}"
                elif operator == '<':
                    query = f"SELECT DISTINCT {return_column} FROM kv_strings WHERE key = ? AND value < ? {where_clause}"
                elif operator == '>':
                    query = f"SELECT DISTINCT {return_column} FROM kv_strings WHERE key = ? AND value > ? {where_clause}"
                elif operator == '<=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_strings WHERE key = ? AND value <= ? {where_clause}"
                elif operator == '>=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_strings WHERE key = ? AND value >= ? {where_clause}"
                else:
                    continue
                
                cursor.execute(query, params)
                results.update(row[0] for row in cursor.fetchall() if row[0] is not None)
            except:
                pass
            
            # Try integer search
            try:
                val = int(value)
                int_params = [key, val]
                if incident_ids:
                    int_params.extend(incident_ids)
                if update_ids:
                    int_params.extend(update_ids)
                
                if operator == '=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_integers WHERE key = ? AND value = ? {where_clause}"
                elif operator == '<':
                    query = f"SELECT DISTINCT {return_column} FROM kv_integers WHERE key = ? AND value < ? {where_clause}"
                elif operator == '>':
                    query = f"SELECT DISTINCT {return_column} FROM kv_integers WHERE key = ? AND value > ? {where_clause}"
                elif operator == '<=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_integers WHERE key = ? AND value <= ? {where_clause}"
                elif operator == '>=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_integers WHERE key = ? AND value >= ? {where_clause}"
                else:
                    continue
                
                cursor.execute(query, int_params)
                results.update(row[0] for row in cursor.fetchall() if row[0] is not None)
            except:
                pass
            
            # Try float search
            try:
                val = float(value)
                float_params = [key, val]
                if incident_ids:
                    float_params.extend(incident_ids)
                if update_ids:
                    float_params.extend(update_ids)
                
                if operator == '=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_floats WHERE key = ? AND value = ? {where_clause}"
                elif operator == '<':
                    query = f"SELECT DISTINCT {return_column} FROM kv_floats WHERE key = ? AND value < ? {where_clause}"
                elif operator == '>':
                    query = f"SELECT DISTINCT {return_column} FROM kv_floats WHERE key = ? AND value > ? {where_clause}"
                elif operator == '<=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_floats WHERE key = ? AND value <= ? {where_clause}"
                elif operator == '>=':
                    query = f"SELECT DISTINCT {return_column} FROM kv_floats WHERE key = ? AND value >= ? {where_clause}"
                else:
                    continue
                
                cursor.execute(query, float_params)
                results.update(row[0] for row in cursor.fetchall() if row[0] is not None)
            except:
                pass
            
            # Intersect with previous results (AND logic)
            if matching_results is None:
                matching_results = results
            else:
                matching_results &= results
        
        conn.close()
        return list(matching_results) if matching_results is not None else []
    
    
    def get_sorted_incidents(self, incident_ids: List[str], ksort_list: List[tuple], update_id: Optional[str] = None) -> List[str]:
        """
        Sort by key-value criteria.
        
        Args:
            incident_ids: List of IDs to sort
            ksort_list: List of (key, ascending) tuples
            update_id: If provided, sort by update KV; if None, sort by incident KV
            
        Returns:
            Sorted list of IDs
        """
        if not ksort_list or not incident_ids:
            return incident_ids
        
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Fetch all KV data for incidents
        kv_data = {}
        
        for inc_id in incident_ids:
            kv_data[inc_id] = {'strings': {}, 'integers': {}, 'floats': {}}
            
            if update_id:
                cursor.execute(
                    "SELECT key, value FROM kv_strings WHERE incident_id = ? AND update_id = ?",
                    (inc_id, update_id)
                )
            else:
                cursor.execute(
                    "SELECT key, value FROM kv_strings WHERE incident_id = ? AND update_id IS NULL",
                    (inc_id,)
                )
            for key, value in cursor.fetchall():
                if key not in kv_data[inc_id]['strings']:
                    kv_data[inc_id]['strings'][key] = []
                kv_data[inc_id]['strings'][key].append(value)
            
            if update_id:
                cursor.execute(
                    "SELECT key, value FROM kv_integers WHERE incident_id = ? AND update_id = ?",
                    (inc_id, update_id)
                )
            else:
                cursor.execute(
                    "SELECT key, value FROM kv_integers WHERE incident_id = ? AND update_id IS NULL",
                    (inc_id,)
                )
            for key, value in cursor.fetchall():
                if key not in kv_data[inc_id]['integers']:
                    kv_data[inc_id]['integers'][key] = []
                kv_data[inc_id]['integers'][key].append(value)
            
            if update_id:
                cursor.execute(
                    "SELECT key, value FROM kv_floats WHERE incident_id = ? AND update_id = ?",
                    (inc_id, update_id)
                )
            else:
                cursor.execute(
                    "SELECT key, value FROM kv_floats WHERE incident_id = ? AND update_id IS NULL",
                    (inc_id,)
                )
            for key, value in cursor.fetchall():
                if key not in kv_data[inc_id]['floats']:
                    kv_data[inc_id]['floats'][key] = []
                kv_data[inc_id]['floats'][key].append(value)
        
        conn.close()
        
        # Sort using custom key function
        def sort_key(incident_id):
            keys = []
            for sort_key_name, ascending in ksort_list:
                value = None
                
                if sort_key_name in kv_data[incident_id]['integers']:
                    value = kv_data[incident_id]['integers'][sort_key_name][0]
                elif sort_key_name in kv_data[incident_id]['floats']:
                    value = kv_data[incident_id]['floats'][sort_key_name][0]
                elif sort_key_name in kv_data[incident_id]['strings']:
                    value = kv_data[incident_id]['strings'][sort_key_name][0]
                
                if value is None:
                    keys.append((1, ""))
                else:
                    if isinstance(value, (int, float)):
                        sort_val = value if ascending else -value
                    else:
                        sort_val = value if ascending else ''.join(chr(255 - ord(c)) for c in value)
                    keys.append((0, sort_val))
            return tuple(keys)
        
        sorted_ids = sorted(incident_ids, key=sort_key)
        return sorted_ids



# ============================================================================
# Reindexing
# ============================================================================


class IncidentReindexer:
    """Rebuild index from files."""

    def __init__(self, storage: IncidentFileStorage, index_db: IncidentIndexDatabase):
        self.storage = storage
        self.index_db = index_db

    def reindex_all(self, verbose: bool = False) -> int:
        """
        Reindex all incidents from files.
        
        Returns:
            Number of incidents indexed
        """
        # Clear existing index
        self.index_db.clear_index()
        
        # Get all incident files
        incident_ids = self.storage.list_incident_files()
        
        if verbose:
            print(f"Reindexing {len(incident_ids)} records...")
        
        indexed_count = 0
        for incident_id in incident_ids:
            incident = self.storage.load_incident(incident_id)
            if incident:
                self.index_db.index_incident(incident)
                indexed_count += 1
                if verbose:
                    print(f"  ✓ {incident_id}")
            else:
                if verbose:
                    print(f"  ✗ {incident_id} (failed to load)")
            updates = self.storage.load_updates(incident_id)

        for update in updates:
            self.index_db.index_update(update)

        if verbose:
            print(f"✓ Reindexed {indexed_count} records")
        
        return indexed_count

# ============================================================================
# High-Level Manager
# ============================================================================


class IncidentManager:
    """High-level incident management API."""
    
    def __init__(
        self,
        explicit_location: Optional[Path] = None,
        interactive: bool = None,
    ):
        """Initialize manager with database and project config."""
        if explicit_location:
            self.db_root = Path(explicit_location).resolve()
        else:
            candidates = DatabaseDiscovery.find_all_databases()
            if not candidates:
                raise RuntimeError("No incident databases found")
            
            user_config = DatabaseDiscovery.get_user_config()
            behavior = user_config.get('behavior', {})
            selection_mode = behavior.get('database_selection', 'contextual')
            
            if interactive is not None:
                selection_mode = 'interactive' if interactive else 'contextual'
            elif not sys.stdin.isatty():
                selection_mode = 'contextual'
            
            if selection_mode == 'interactive':
                self.db_root = DatabaseDiscovery.select_database_interactive(candidates)
            else:
                self.db_root = DatabaseDiscovery.select_database_contextual(candidates)
        
        if not self.db_root.exists():
            raise RuntimeError(f"Incident database not found: {self.db_root}")
        
        self.storage = IncidentFileStorage(self.db_root)
        self.index_db = IncidentIndexDatabase(self.db_root / "aver.db")
        self.project_config = ProjectConfig(self.db_root)
    
    def _validate_and_store_kv(
        self,
        key: str,
        kvtype: Optional[str],
        value: Any,
        incident: Incident,
    ) -> None:
        """
        Validate and store a KV pair.
        
        If key is special (config-defined), validates based on config.
        Otherwise stores with provided type hint (or as string if no hint).
        Validation only happens on write, so old values remain searchable
        if config changes.
        
        Args:
            key: Field name
            kvtype: Type hint from KVParser ($ for string, # for int, % for float, None for untyped)
            value: Value to store
            incident: Incident to store in
        """
        field = self.project_config.get_special_field(key)
        
        if field:
            # Special field - validate against config, ignore type hint
            if not field.editable:
                raise ValueError(f"'{key}' cannot be edited")
            
            if field.field_type == "single":
                is_valid, error = self.project_config.validate_field(key, value)
                if not is_valid:
                    raise ValueError(error)
            
            # Store with config-defined type
            if field.value_type == "string":
                if field.field_type == "single":
                    incident.kv_strings[key] = [value]
                else:
                    if not isinstance(value, list):
                        value = [value]
                    incident.kv_strings[key] = value
            elif field.value_type == "integer":
                if field.field_type == "single":
                    incident.kv_integers[key] = [int(value)]
                else:
                    if not isinstance(value, list):
                        value = [value]
                    incident.kv_integers[key] = [int(v) for v in value]
            elif field.value_type == "float":
                if field.field_type == "single":
                    incident.kv_floats[key] = [float(value)]
                else:
                    if not isinstance(value, list):
                        value = [value]
                    incident.kv_floats[key] = [float(v) for v in value]
        else:
            # Non-special field - use type hint
            if kvtype == KVParser.TYPE_STRING or kvtype is None:
                # Default to string if no type hint
                if isinstance(value, list):
                    incident.kv_strings[key] = [str(v) for v in value]
                else:
                    incident.kv_strings[key] = [str(value)] if value is not None else []
            elif kvtype == KVParser.TYPE_INTEGER:
                if isinstance(value, list):
                    incident.kv_integers[key] = [int(v) for v in value]
                else:
                    incident.kv_integers[key] = [int(value)] if value is not None else []
            elif kvtype == KVParser.TYPE_FLOAT:
                if isinstance(value, list):
                    incident.kv_floats[key] = [float(v) for v in value]
                else:
                    incident.kv_floats[key] = [float(value)] if value is not None else []
    
    def create_incident(
        self,
        kv_list: List[str],
        description: Optional[str] = None,
    ) -> str:
        """
        Create new incident from KV list.
        
        Args:
            kv_list: List of KV strings in format "key${value}", "key#{value}", "key%{value}"
            description: Optional incident description
        
        Example:
            manager.create_incident(
                kv_list=[
                    "title$Database error",
                    "severity$high",
                    "status$open",
                    "tags$backend",
                    "tags$database",
                ]
            )
        """
        user_config = DatabaseDiscovery.get_user_config()
        incident_id = IDGenerator.generate_incident_id()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        
        # Initialize empty incident
        incident = Incident(id=incident_id)
        
        # Parse and apply all KV updates
        parsed_kv = KVParser.parse_kv_list(kv_list)
        for key, kvtype, op, value in parsed_kv:
            if op == '-':
                raise ValueError(f"Cannot use removal operator '-' when creating incident")
            self._validate_and_store_kv(key, kvtype, value, incident)
        
        # Add system fields (no type hints, will validate if special)
        self._validate_and_store_kv('created_at', KVParser.TYPE_STRING, now, incident)
        self._validate_and_store_kv('created_by', KVParser.TYPE_STRING, user_config["user"]["handle"], incident)
        self._validate_and_store_kv('updated_at', KVParser.TYPE_STRING, now, incident)
        
        if description:
            self._validate_and_store_kv('description', KVParser.TYPE_STRING, description, incident)
        
        # Save to file
        self.storage.save_incident(incident, self.project_config)
        
        # Update index
        self.index_db.index_incident(incident, self.project_config)
        self.index_db.index_kv_data(incident)
        
        # Create initial update
        initial_message = self._format_initial_update(incident)
        initial_update = IncidentUpdate(
            id="auto",
            incident_id=incident_id,
            timestamp=now,
            author=user_config["user"]["handle"],
            message=initial_message,
        )
        
        self.storage.save_update(incident_id, initial_update)
        self.index_db.index_update(initial_update)
        
        return incident_id
    
    def _format_initial_update(self, incident: Incident) -> str:
        """Format initial update message from all KV data."""
        lines = ["## Incident Created"]
        lines.append("")
        
        # System fields to skip
        skip_fields = {'title', 'created_at', 'created_by', 'updated_at', 'description'}
        
        # Format all string KV that isn't in skip list
        for key, values in incident.kv_strings.items():
            if key not in skip_fields and values:
                values_str = ', '.join(str(v) for v in values)
                lines.append(f"**{key}:** {values_str}")
        
        # Format all integer KV
        for key, values in incident.kv_integers.items():
            if values:
                values_str = ', '.join(str(v) for v in values)
                lines.append(f"**{key}:** {values_str}")
        
        # Format all float KV
        for key, values in incident.kv_floats.items():
            if values:
                values_str = ', '.join(str(v) for v in values)
                lines.append(f"**{key}:** {values_str}")
        
        # Add description if present
        if 'description' in incident.kv_strings:
            description = incident.kv_strings['description'][0] if incident.kv_strings['description'] else None
            if description:
                lines.append("")
                lines.append("### Description")
                lines.append("")
                lines.append(description)
        
        return "\n".join(lines)
    
    def update_incident_info(
        self,
        incident_id: str,
        kv_list: List[str],
    ) -> bool:
        """
        Update incident fields from KV list.
        
        Args:
            incident_id: Incident ID
            kv_list: List of KV strings to update/remove
        
        Example:
            manager.update_incident_info(
                incident_id,
                ["status$resolved", "assignees$alice"]
            )
        """
        incident = self.storage.load_incident(incident_id, self.project_config)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
        
        user_config = DatabaseDiscovery.get_user_config()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        
        updated_fields = []
        
        # Parse KV updates
        parsed_kv = KVParser.parse_kv_list(kv_list)
        for key, kvtype, op, value in parsed_kv:
            if op == '-':
                # Removal
                if key in incident.kv_strings:
                    del incident.kv_strings[key]
                if key in incident.kv_integers:
                    del incident.kv_integers[key]
                if key in incident.kv_floats:
                    del incident.kv_floats[key]
                updated_fields.append(f"removed {key}")
            else:
                # Update
                self._validate_and_store_kv(key, kvtype, value, incident)
                updated_fields.append(key)
        
        # Update timestamp
        incident.kv_strings['updated_at'] = [now]
        
        # Save and reindex
        self.storage.save_incident(incident, self.project_config)
        self.index_db.index_incident(incident, self.project_config)
        self.index_db.index_kv_data(incident)
        
        # Log update
        update_msg = f"Updated: {', '.join(updated_fields)}"
        incident_update = IncidentUpdate(
            id="auto",
            incident_id=incident_id,
            timestamp=now,
            author=user_config["user"]["handle"],
            message=update_msg,
        )
        self.storage.save_update(incident_id, incident_update)
        self.index_db.index_update(incident_update)
        
        return True
    
    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident from file storage."""
        return self.storage.load_incident(incident_id, self.project_config)
    
    def get_updates(self, incident_id: str) -> List[IncidentUpdate]:
        """
        Get all updates for an incident.
        
        Args:
            incident_id: Incident ID
            
        Returns:
            List of updates in chronological order
        """
        return self.storage.load_updates(incident_id)
    
    def add_update(
        self,
        incident_id: str,
        message: Optional[str] = None,
        use_stdin: bool = False,
        use_editor: bool = False,
        kv_single: Optional[List[str]] = None,
        kv_multi: Optional[List[str]] = None,
    ) -> str:
        """
        Add update with optional independent KV data.
        
        Args:
            incident_id: Incident ID
            message: Update message
            use_stdin: Read from STDIN
            use_editor: Open editor
            kv_single: Single-value KV for UPDATE only (replaces keys)
            kv_multi: Multi-value KV for UPDATE only (adds values)
        
        Returns:
            Update ID
        """
        incident = self.get_incident(incident_id)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
        
        user_config = DatabaseDiscovery.get_user_config()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        
        # Determine message source
        final_message = None
        
        if message:
            final_message = message
        elif use_stdin and StdinHandler.has_stdin_data():
            final_message = StdinHandler.read_stdin_with_timeout(timeout=2.0)
        elif use_editor:
            final_message = EditorConfig.launch_editor(
                initial_content=(
                    "# Add your update below\n"
                    "# Lines starting with # are ignored\n"
                    "\n"
                ),
            )
            final_message = "\n".join(
                line
                for line in final_message.split("\n")
                if not line.strip().startswith("#")
            ).strip()
        
        if not final_message:
            raise RuntimeError(
                "No update provided.\n"
                "\nUsage:\n"
                "  incident add-update <id> --message \"text\"\n"
                "  echo \"text\" | incident add-update <id>\n"
                "  incident add-update <id>  # opens editor"
            )
        
        # Parse KV data for the UPDATE ONLY
        update_kv_strings = {}
        update_kv_integers = {}
        update_kv_floats = {}
        
        if kv_single:
            parsed_kv = KVParser.parse_kv_list(kv_single)
            for key, kvtype, op, value in parsed_kv:
                if op != '-':
                    if kvtype == KVParser.TYPE_STRING or kvtype is None:
                        update_kv_strings[key] = [str(value)]
                    elif kvtype == KVParser.TYPE_INTEGER:
                        update_kv_integers[key] = [int(value)]
                    elif kvtype == KVParser.TYPE_FLOAT:
                        update_kv_floats[key] = [float(value)]
        
        if kv_multi:
            parsed_kv = KVParser.parse_kv_list(kv_multi)
            for key, kvtype, op, value in parsed_kv:
                if op != '-':
                    if kvtype == KVParser.TYPE_STRING or kvtype is None:
                        if key not in update_kv_strings:
                            update_kv_strings[key] = []
                        update_kv_strings[key].append(str(value))
                    elif kvtype == KVParser.TYPE_INTEGER:
                        if key not in update_kv_integers:
                            update_kv_integers[key] = []
                        update_kv_integers[key].append(int(value))
                    elif kvtype == KVParser.TYPE_FLOAT:
                        if key not in update_kv_floats:
                            update_kv_floats[key] = []
                        update_kv_floats[key].append(float(value))
        
        # Generate update ID
        update_id = IDGenerator.generate_update_id()
        
        update = IncidentUpdate(
            id=update_id,
            incident_id=incident_id,
            timestamp=now,
            author=user_config["user"]["handle"],
            message=final_message,
            kv_strings=update_kv_strings if update_kv_strings else None,
            kv_integers=update_kv_integers if update_kv_integers else None,
            kv_floats=update_kv_floats if update_kv_floats else None,
        )
        
        # Save update
        self.storage.save_update(incident_id, update)
        self.index_db.index_update(update)
        
        # Index update KV data (completely independent from incident KV)
        self.index_db.index_update_kv_data(
            incident_id,
            update_id,
            kv_strings=update_kv_strings or None,
            kv_integers=update_kv_integers or None,
            kv_floats=update_kv_floats or None,
        )
        
        # Update incident's updated_at
        incident.kv_strings['updated_at'] = [now]
        self.storage.save_incident(incident, self.project_config)
        
        return update_id
    
    def list_incidents(
        self,
        ksearch_list: Optional[List[str]] = None,
        ksort_list: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[Incident]:
        """
        List incidents with optional KV search and sort.
        
        Args:
            ksearch_list: List of search expressions like ["status=open", "severity>low"]
            ksort_list: List of sort expressions like ["severity", "created_at-"]
            limit: Max results
        
        Raises:
            RuntimeError: If search/sort expressions are invalid
        """
        # Search (returns all if ksearch_list is None/empty)
        parsed_ksearch = []
        if ksearch_list:
            try:
                parsed_ksearch = [KVSearchParser.parse_ksearch(expr) for expr in ksearch_list]
            except ValueError as e:
                raise RuntimeError(f"Invalid ksearch expression: {e}")
        
        incident_ids = self.index_db.search_kv(parsed_ksearch, return_updates=False)
        
        if not incident_ids:
            return []
        
        # Sort if requested
        if ksort_list:
            try:
                parsed_ksort = [KVSearchParser.parse_ksort(expr) for expr in ksort_list]
                incident_ids = self.index_db.get_sorted_incidents(incident_ids, parsed_ksort)
            except ValueError as e:
                raise RuntimeError(f"Invalid ksort expression: {e}")
        
        # Load incident objects from file storage
        incidents = []
        for incident_id in incident_ids[:limit]:
            incident = self.storage.load_incident(incident_id, self.project_config)
            if incident:
                incidents.append(incident)
        
        return incidents
    
    def search_updates(
        self,
        ksearch: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[tuple]:
        """
        Search updates by key-value filters.
        
        Args:
            ksearch: List of key-value search expressions for update KV
            limit: Maximum results
        
        Returns:
            List of (update, incident_id, incident_title) tuples
        
        Raises:
            RuntimeError: If ksearch expressions are invalid
        """
        if not ksearch:
            return []
        
        try:
            ksearch_parsed = [KVSearchParser.parse_ksearch(expr) for expr in ksearch]
        except ValueError as e:
            raise RuntimeError(f"Invalid ksearch expression: {e}")
        
        # Search for updates with KV data
        matching_update_ids = self.index_db.search_kv(
            ksearch_parsed,
            return_updates=True
        )
        
        if not matching_update_ids:
            return []
        
        # Load updates and their parent incidents
        results = []
        seen_updates = set()
        
        for update_id in matching_update_ids[:limit * 2]:
            if update_id in seen_updates:
                continue
            
            # Find which incident this update belongs to
            # (need to search incident KV index for incident_id references)
            for incident_id in self.index_db.list_all_incident_ids_with_update(update_id):
                updates = self.storage.load_updates(incident_id)
                matching_update = next(
                    (u for u in updates if u.id == update_id),
                    None
                )
                
                if matching_update:
                    incident = self.get_incident(incident_id)
                    if incident:
                        incident_title = (
                            incident.kv_strings.get('title', ['Unknown'])[0]
                            if incident.kv_strings else 'Unknown'
                        )
                        results.append((matching_update, incident_id, incident_title))
                        seen_updates.add(update_id)
                        break
        
        return results[:limit]


# ============================================================================
# CLI
# ============================================================================
class IncidentCLI:
    """Command-line interface for record management."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="aver: record tracking and management",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.subparsers = self.parser.add_subparsers(dest="command", required=True)

    def _add_common_args(self, parser):
        """Add common database selection arguments."""
        parser.add_argument(
            "--location",
            help="Explicit database path (overrides all detection)",
        )
        parser.add_argument(
            "--choose",
            action="store_true",
            help="Prompt to choose database if multiple available",
        )

    def _get_manager(self, args) -> IncidentManager:
        """Handle database selection and return manager."""
        interactive = getattr(args, 'choose', False)
        
        return IncidentManager(
            explicit_location=getattr(args, 'location', None),
            interactive=interactive,
        )

    def _build_kv_list(self, manager: IncidentManager, args) -> List[str]:
        """
        Build KV list from special field arguments and generic KV options.
        
        Processes special fields defined in ProjectConfig as well as
        generic --kv and --kmv arguments.
        """
        kv_list = []
        
        # Process special fields from config
        special_fields = manager.project_config.get_special_fields()
        
        for field_name, field_def in special_fields.items():
            # Check if this special field was provided as an argument
            if hasattr(args, field_name) and getattr(args, field_name) is not None:
                value = getattr(args, field_name)
                
                # Determine type prefix based on field definition
                if field_def.value_type == "integer":
                    type_prefix = "#"
                elif field_def.value_type == "float":
                    type_prefix = "%"
                else:
                    type_prefix = "$"
                
                # Handle single vs multi-value fields
                if field_def.field_type == "single":
                    kv_list.append(f"{field_name}{type_prefix}{value}")
                else:
                    # Multi-value: value could be a list
                    if isinstance(value, list):
                        for v in value:
                            kv_list.append(f"{field_name}{type_prefix}{v}")
                    else:
                        kv_list.append(f"{field_name}{type_prefix}{value}")
        
        # Add generic single-value KV arguments
        if hasattr(args, 'kv_single') and args.kv_single:
            kv_list.extend(args.kv_single)
        
        # Add generic multi-value KV arguments
        if hasattr(args, 'kv_multi') and args.kv_multi:
            kv_list.extend(args.kv_multi)
        
        return kv_list

    def _add_special_field_args(self, parser, manager: IncidentManager):
        """
        Dynamically add arguments for special fields defined in ProjectConfig.
        
        This allows admins to define custom fields like --severity, --assignees,
        etc. in their config, and they become available as CLI arguments.
        """
        special_fields = manager.project_config.get_special_fields()
        
        for field_name, field_def in special_fields.items():
            if not field_def.editable:
                continue
            
            # Build argument name
            arg_name = f"--{field_name}"
            
            # Determine argument type and properties
            kwargs = {
                "help": f"{field_name} ({field_def.field_type}, {field_def.value_type})",
                "dest": field_name,
            }
            
            if field_def.field_type == "multi":
                kwargs["nargs"] = "*"
            
            if field_def.accepted_values:
                kwargs["choices"] = field_def.accepted_values
            
            if field_def.value_type == "integer":
                kwargs["type"] = int
            elif field_def.value_type == "float":
                kwargs["type"] = float
            
            parser.add_argument(arg_name, **kwargs)

    def setup_commands(self):
        """Set up all CLI commands."""
        
        # ====================================================================
        # RECORD COMMANDS
        # ====================================================================
        record_parser = self.subparsers.add_parser(
            "record",
            help="Record Management",
        )
        record_subparsers = record_parser.add_subparsers(
            dest="record_command",
            required=True,
        )
        
        # record new
        record_new_parser = record_subparsers.add_parser(
            "new",
            help="Create a new record",
        )
        self._add_common_args(record_new_parser)
        
        # We'll add special fields dynamically in _cmd_create
        record_new_parser.add_argument(
            "--kv",
            action="append",
            dest="kv_single",
            help="Single-value KV data: 'key$value', 'key#123', 'key%1.5'",
        )
        record_new_parser.add_argument(
            "--kmv",
            action="append",
            dest="kv_multi",
            help="Multi-value KV data: 'key$value', 'key#123', 'key%1.5'",
        )
        record_new_parser.add_argument(
            "--description",
            help="Detailed description",
        )
        
        # Store parser reference for dynamic arg addition
        record_new_parser._special_fields_parser = True
        
        # record view
        record_view_parser = record_subparsers.add_parser(
            "view",
            help="View a specific record's details",
        )
        self._add_common_args(record_view_parser)
        record_view_parser.add_argument("record_id", help="Record ID")
        
        # record list
        record_list_parser = record_subparsers.add_parser(
            "list",
            help="List/search records with filters",
        )
        self._add_common_args(record_list_parser)
        record_list_parser.add_argument(
            "--ksearch",
            action="append",
            dest="ksearch",
            help="Search by key-value: 'key=value', 'cost>100' (can use multiple times)",
        )
        record_list_parser.add_argument(
            "--ksort",
            action="append",
            dest="ksort",
            help="Sort by key-values: 'key1', 'key2-' (- = desc, default = asc, can use multiple)",
        )
        record_list_parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum records to show",
        )
        
        # record update
        record_update_parser = record_subparsers.add_parser(
            "update",
            help="Update record status and metadata",
        )
        self._add_common_args(record_update_parser)
        record_update_parser.add_argument("record_id", help="Record ID")
        record_update_parser._special_fields_parser = True
        record_update_parser.add_argument(
            "--kv",
            action="append",
            dest="kv_single",
            help="Single-value KV data: 'key$value' or 'key-' to remove",
        )
        record_update_parser.add_argument(
            "--kmv",
            action="append",
            dest="kv_multi",
            help="Multi-value KV data: 'key$value' or 'key$value-' to remove",
        )
        
        # ====================================================================
        # NOTE COMMANDS
        # ====================================================================
        note_parser = self.subparsers.add_parser(
            "note",
            help="Note Management",
        )
        note_subparsers = note_parser.add_subparsers(
            dest="note_command",
            required=True,
        )
        
        # note add
        note_add_parser = note_subparsers.add_parser(
            "add",
            help="Add a note to a record",
            description=(
                "Add note to record. Message source priority:\n"
                "  1. --message flag (explicit message)\n"
                "  2. STDIN (if piped)\n"
                "  3. Editor (if STDIN unavailable)"
            ),
        )
        self._add_common_args(note_add_parser)
        note_add_parser.add_argument("record_id", help="Record ID")
        note_add_parser.add_argument(
            "--message",
            help="Note message text",
        )
        note_add_parser.add_argument(
            "--kv",
            action="append",
            dest="kv_single",
            help="Single-value KV data for note only: 'key$value'",
        )
        note_add_parser.add_argument(
            "--kmv",
            action="append",
            dest="kv_multi",
            help="Multi-value KV data for note only: 'key$value'",
        )
        
        # note list
        note_list_parser = note_subparsers.add_parser(
            "list",
            help="View all notes for a specific record",
        )
        self._add_common_args(note_list_parser)
        note_list_parser.add_argument("record_id", help="Record ID")
        
        # note search
        note_search_parser = note_subparsers.add_parser(
            "search",
            help="Search notes by KV data",
        )
        self._add_common_args(note_search_parser)
        note_search_parser.add_argument(
            "--ksearch",
            action="append",
            dest="ksearch",
            required=True,
            help="Search by note KV: 'key=value' (required, can use multiple times)",
        )
        note_search_parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum results",
        )
        
        # ====================================================================
        # ADMIN COMMANDS
        # ====================================================================
        admin_parser = self.subparsers.add_parser(
            "admin",
            help="Administrative Operations",
        )
        admin_subparsers = admin_parser.add_subparsers(
            dest="admin_command",
            required=True,
        )
        
        # admin init
        admin_init_parser = admin_subparsers.add_parser(
            "init",
            help="Initialize a new database",
        )
        admin_init_parser.add_argument(
            "--location",
            help="Database location (default: .aver in git root or current directory)",
        )
        admin_init_parser.add_argument(
            "--override-repo-boundary",
            action="store_true",
            help="Bypass git repository boundary checks",
        )
        
        # admin config
        admin_config_parser = admin_subparsers.add_parser(
            "config",
            help="Configuration subcommands",
        )
        config_subparsers = admin_config_parser.add_subparsers(
            dest="config_command",
            required=True,
        )
        
        set_user_parser = config_subparsers.add_parser(
            "set-user",
            help="Set global user identity",
        )
        set_user_parser.add_argument("--handle", required=True, help="User handle")
        set_user_parser.add_argument("--email", required=True, help="User email")
        
        set_editor_parser = config_subparsers.add_parser(
            "set-editor",
            help="Set preferred editor",
            description=(
                "Set the editor for opening in aver.\n"
                "Stored in ~/.config/aver/user.toml\n"
                "Takes precedence over EDITOR environment variable."
            )
        )
        set_editor_parser.add_argument("editor", help="Editor command (vim, nano, code, etc.)")
        
        get_editor_parser = config_subparsers.add_parser(
            "get-editor",
            help="Show current editor",
        )
        
        # admin reindex
        admin_reindex_parser = admin_subparsers.add_parser(
            "reindex",
            help="Rebuild search index",
        )
        self._add_common_args(admin_reindex_parser)
        admin_reindex_parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Verbose output",
        )
        
        # admin list-databases
        admin_list_databases_parser = admin_subparsers.add_parser(
            "list-databases",
            help="Show all available databases",
        )

    def run(self, args: Optional[List[str]] = None):
        """Run CLI."""
        self.setup_commands()
        parsed = self.parser.parse_args(args)

        try:
            if parsed.command == "record":
                if parsed.record_command == "new":
                    self._cmd_create(parsed)
                elif parsed.record_command == "view":
                    self._cmd_view(parsed)
                elif parsed.record_command == "list":
                    self._cmd_list(parsed)
                elif parsed.record_command == "update":
                    self._cmd_update(parsed)
                    
            elif parsed.command == "note":
                if parsed.note_command == "add":
                    self._cmd_add_update(parsed)
                elif parsed.note_command == "list":
                    self._cmd_list_updates(parsed)
                elif parsed.note_command == "search":
                    self._cmd_search_updates(parsed)
                    
            elif parsed.command == "admin":
                if parsed.admin_command == "init":
                    self._cmd_init(parsed)
                elif parsed.admin_command == "config":
                    self._cmd_config(parsed)
                elif parsed.admin_command == "reindex":
                    self._cmd_reindex(parsed)
                elif parsed.admin_command == "list-databases":
                    self._cmd_list_databases(parsed)
                    
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except KeyboardInterrupt:
            print("\nCancelled", file=sys.stderr)
            sys.exit(130)

    def _cmd_init(self, args):
        """Initialize database."""
        if args.location:
            db_root = Path(args.location)
        else:
            # Try to find git repo root
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                repo_root = Path(result.stdout.strip())
                db_root = repo_root / ".aver"
            except subprocess.CalledProcessError:
                db_root = Path.cwd() / ".aver"

        # Enforce repo boundary
        if not DatabaseDiscovery.enforce_repo_boundary(
            db_root,
            override=getattr(args, 'override_repo_boundary', False),
        ):
            print(
                f"Error: Database at {db_root} is outside git repository.\n"
                "Use --override-repo-boundary to bypass.",
                file=sys.stderr,
            )
            sys.exit(1)

        db_root.mkdir(parents=True, exist_ok=True)
        
        # Initialize storage and index
        storage = IncidentFileStorage(db_root)
        index_db = IncidentIndexDatabase(db_root / "aver.db")

        print(f"✓ Database initialized at {db_root}")
        print(f"  Records: {storage.incidents_dir}")
        print(f"  Notes: {storage.updates_dir}")
        print(f"  Index: {db_root / 'aver.db'}")
        print(f"  Config: {db_root / 'config.toml'}")

    def _cmd_config(self, args):
        """Handle config commands."""
        if args.config_command == "set-user":
            config = DatabaseDiscovery.get_user_config()
            config["user"] = {
                "handle": args.handle,
                "email": args.email,
            }
            DatabaseDiscovery.set_user_config(config)
            print(f"✓ User configured: {args.handle} <{args.email}>")

        elif args.config_command == "set-editor":
            if not EditorConfig._editor_exists(args.editor):
                print(f"Error: Editor '{args.editor}' not found in PATH", file=sys.stderr)
                sys.exit(1)

            config = DatabaseDiscovery.get_user_config()
            config["editor"] = args.editor
            DatabaseDiscovery.set_user_config(config)
            print(f"✓ Set editor to {args.editor}")

        elif args.config_command == "get-editor":
            try:
                editor = EditorConfig.get_editor()
                print(f"Current editor: {editor}")
            except RuntimeError as e:
                print(f"Error: {e}", file=sys.stderr)
                sys.exit(1)

    def _cmd_create(self, args):
        """Create record."""
        manager = self._get_manager(args)
        
        # Dynamically add special field arguments
        self._add_special_field_args(args._parser, manager)
        
        # Build KV list from special fields and generic KV arguments
        kv_list = self._build_kv_list(manager, args)
        
        # Create record
        record_id = manager.create_incident(
            kv_list=kv_list,
            description=args.description,
        )

        print(f"✓ Created record: {record_id}")
        
        # Show summary from KV data
        record = manager.get_incident(record_id)
        if record:
            if 'title' in record.kv_strings:
                title = record.kv_strings['title'][0]
                print(f"  Title: {title}")
            for key, values in record.kv_strings.items():
                if key not in ('title', 'description', 'created_at', 'created_by', 'updated_at'):
                    print(f"  {key}: {', '.join(values)}")

    def _cmd_view(self, args):
        """View record details."""
        manager = self._get_manager(args)
        record = manager.get_incident(args.record_id)

        if not record:
            print(f"Error: Record {args.record_id} not found", file=sys.stderr)
            sys.exit(1)

        # Format and display record
        print(f"\n{'='*70}")
        print(f"Record: {record.id}")
        print(f"{'='*70}\n")
        
        # Display all KV data
        if record.kv_strings:
            print("String Fields:")
            for key, values in record.kv_strings.items():
                values_str = ', '.join(str(v) for v in values)
                print(f"  {key}: {values_str}")
        
        if record.kv_integers:
            print("\nInteger Fields:")
            for key, values in record.kv_integers.items():
                values_str = ', '.join(str(v) for v in values)
                print(f"  {key}: {values_str}")
        
        if record.kv_floats:
            print("\nFloat Fields:")
            for key, values in record.kv_floats.items():
                values_str = ', '.join(str(v) for v in values)
                print(f"  {key}: {values_str}")
        
        print(f"\n{'='*70}\n")

    def _cmd_list(self, args):
        """List records with KV search and sort."""
        manager = self._get_manager(args)
        
        try:
            records = manager.list_incidents(
                ksearch_list=getattr(args, 'ksearch', None),
                ksort_list=getattr(args, 'ksort', None),
                limit=args.limit,
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not records:
            print("No records found")
            return

        # Print table header
        print(f"\n{'ID':<15} {'Title':<40} {'Updated':<20}")
        print("─" * 80)

        for rec in records:
            title = rec.kv_strings.get('title', ['Unknown'])[0] if rec.kv_strings else 'Unknown'
            title = title[:37] if len(title) > 37 else title
            updated = rec.kv_strings.get('updated_at', ['Unknown'])[0] if rec.kv_strings else 'Unknown'
            print(f"{rec.id:<15} {title:<40} {updated:<20}")
        
        print()

    def _cmd_update(self, args):
        """Update record metadata."""
        manager = self._get_manager(args)
        
        # Dynamically add special field arguments
        self._add_special_field_args(args._parser, manager)
        
        # Build KV list from special fields and generic KV arguments
        kv_list = self._build_kv_list(manager, args)
        
        if not kv_list:
            print("Error: No fields to update", file=sys.stderr)
            sys.exit(1)
        
        # Update record
        manager.update_incident_info(
            args.record_id,
            kv_list=kv_list,
        )
        
        print(f"✓ Updated record: {args.record_id}")

    def _cmd_add_update(self, args):
        """Add note to record."""
        manager = self._get_manager(args)

        # Determine message source
        has_message = args.message is not None
        has_stdin = StdinHandler.has_stdin_data()

        try:
            note_id = manager.add_update(
                args.record_id,
                message=args.message if has_message else None,
                use_stdin=has_stdin and not has_message,
                use_editor=not (has_message or has_stdin),
                kv_single=getattr(args, 'kv_single', None),
                kv_multi=getattr(args, 'kv_multi', None),
            )
            print(f"✓ Added note: {note_id}")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def _cmd_list_updates(self, args):
        """View all notes for record."""
        manager = self._get_manager(args)
        record = manager.get_incident(args.record_id)

        if not record:
            print(f"Error: Record {args.record_id} not found", file=sys.stderr)
            sys.exit(1)

        notes = manager.get_updates(args.record_id)

        print(f"\nNotes for {args.record_id}:\n")

        if not notes:
            print("No notes yet")
            return

        for i, note in enumerate(notes, 1):
            print("─" * 70)
            print(f"Note {i}: [{note.timestamp}] by {note.author}")
            print("─" * 70)
            print(note.message)
            
            # Show note KV data if present
            if note.kv_strings or note.kv_integers or note.kv_floats:
                print("\nNote KV Data:")
                if note.kv_strings:
                    for key, values in note.kv_strings.items():
                        print(f"  {key}: {', '.join(str(v) for v in values)}")
                if note.kv_integers:
                    for key, values in note.kv_integers.items():
                        print(f"  {key}: {', '.join(str(v) for v in values)}")
                if note.kv_floats:
                    for key, values in note.kv_floats.items():
                        print(f"  {key}: {', '.join(str(v) for v in values)}")
            
            print()

    def _cmd_search_updates(self, args):
        """Search notes by KV data."""
        manager = self._get_manager(args)
        
        try:
            results = manager.search_updates(
                ksearch=args.ksearch,
                limit=args.limit,
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not results:
            print("No matching notes found")
            return

        print(f"\nFound {len(results)} matching notes:\n")

        for note, record_id, record_title in results:
            print("─" * 70)
            print(f"Record: {record_id} - {record_title}")
            print(f"Note: {note.id} [{note.timestamp}] by {note.author}")
            print("─" * 70)
            print(note.message[:200] + ("..." if len(note.message) > 200 else ""))
            print()

    def _cmd_reindex(self, args):
        """Rebuild search index."""
        try:
            manager = self._get_manager(args)
            # Assuming IncidentReindexer exists or we need to implement it
            reindexer = IncidentReindexer(manager.storage, manager.index_db, manager.project_config)
            count = reindexer.reindex_all(verbose=args.verbose)
            print(f"✓ Reindexed {count} records")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def _cmd_list_databases(self, args):
        """Show available databases."""
        candidates = DatabaseDiscovery.find_all_databases()
    
        if not candidates:
            print("No databases found.")
            return
    
        print("\n" + "="*70)
        print("Available Databases")
        print("="*70)
    
        contextual = {k: v for k, v in candidates.items() if v.get('category') == 'contextual'}
        available = {k: v for k, v in candidates.items() if v.get('category') == 'available'}
        
        if contextual:
            print("\n[Contextual (will be used by default)]")
            for key, info in contextual.items():
                print(f"  → {info['source']}")
                print(f"    {info['path']}")
    
        if available:
            print("\n[Available]")
            for key, info in available.items():
                print(f"    {info['source']}")
                print(f"    {info['path']}")
    
        print("\n" + "="*70)
        print("Use: --choose to select interactively")
        print("     --location PATH to specify explicitly")
        print("="*70 + "\n")


# ============================================================================
# Main
# ============================================================================


def main():
    """Entry point."""
    cli = IncidentCLI()
    cli.run()


if __name__ == "__main__":
    main()
