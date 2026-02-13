#!/usr/bin/env python3
"""
aver: a verified knowledge tracking tool

Minimal external dependencies. 
Stores records and updates as Markdown files with yaml headers.
Uses SQLite for indexing and searching only.
"""

from __future__ import annotations

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
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from types import SimpleNamespace
import select
import secrets
import time
from string import Template
try:
    import tomllib
except ImportError:
    import tomli as tomllib
import tomli_w 


"""
YAMLSerializer
"""

import yaml
from typing import Optional, Any


class YAMLSerializer:
    """
    Centralized YAML serialization with type hints.
    
    Handles all YAML formatting for both Incident and IncidentUpdate classes.
    """
    
    # Type hint suffixes for custom fields
    TYPE_HINT_STRING = "$"
    TYPE_HINT_INTEGER = "#"
    TYPE_HINT_FLOAT = "%"
    
    TYPE_HINTS = {
        TYPE_HINT_STRING: "string",
        TYPE_HINT_INTEGER: "integer",
        TYPE_HINT_FLOAT: "float",
    }
    
    TYPE_HINT_SUFFIX = "__"  # e.g., my_field__string
    
    @staticmethod
    def add_type_hint(key: str, value_type: str) -> str:
        """Add type hint suffix to key. e.g., 'foo' + 'string' -> 'foo__string'"""
        return f"{key}{YAMLSerializer.TYPE_HINT_SUFFIX}{value_type}"
    
    @staticmethod
    def strip_type_hint(key: str) -> tuple[str, Optional[str]]:
        """Remove type hint suffix from key. Returns (clean_key, type_or_none)."""
        for vtype in ("string", "integer", "float"):
            suffix = f"{YAMLSerializer.TYPE_HINT_SUFFIX}{vtype}"
            if key.endswith(suffix):
                return key[:-len(suffix)], vtype
        return key, None
    
    @staticmethod
    def normalize_dict_values(data):
        """
        Walks through first-level keys and converts single-element lists to single values.
        Leaves lists with multiple elements and dictionaries unchanged.
        """
        result = {}
        for key, value in data.items():
            if isinstance(value, list) and len(value) == 1:
                # Single-element list -> unwrap to single value
                result[key] = value[0]
            else:
                # Keep as-is (multi-element list, dict, or single value)
                result[key] = value
        return result
    
    @staticmethod
    def dumps(d: dict) -> str:
        """
        Serialize a dict to YAML string.
        
        Uses PyYAML with explicit settings for clean, readable output.
        """
        # Debug output (can be removed in production)
        # print(f"DUMP DICT: {d}")
        
        # Normalize single-element lists
        normalized = YAMLSerializer.normalize_dict_values(d)
        
        # Use yaml.safe_dump for security and clean output
        yaml_str = yaml.safe_dump(
            normalized,
            default_flow_style=False,  # Use block style (multi-line) not flow style
            sort_keys=False,           # Preserve insertion order (Python 3.7+)
            allow_unicode=True,        # Support Unicode characters natively
            width=1000,                # Prevent unwanted line wrapping
            default_style=None,        # Let YAML choose appropriate quoting
        )
        
        return yaml_str
    
    @staticmethod
    def loads(s: str) -> dict:
        """
        Parse a YAML string into a dict.
        
        Uses safe_load for security (doesn't execute arbitrary Python code).
        Returns empty dict if string is empty or contains only whitespace.
        """
        result = yaml.safe_load(s)
        # yaml.safe_load returns None for empty strings
        return result if result is not None else {}


class MarkdownDocument:
    """
    Handles Markdown documents with YAML frontmatter.
    
    Format:
        ---
        key: value
        list:
          - item1
          - item2
        ---
        
        Document body text here.
    """
    
    DELIMITER = "---" 
    
    @staticmethod
    def create(metadata: dict, body: str) -> str:
        """Create a markdown document with YAML frontmatter."""
        yaml_str = YAMLSerializer.dumps(metadata)
        return f"{MarkdownDocument.DELIMITER}\n{yaml_str}{MarkdownDocument.DELIMITER}\n\n{body}\n"
    
    @staticmethod
    def parse(content: str) -> tuple[dict, str]:
        """
        Parse a markdown document with YAML frontmatter.
        
        Returns:
            (metadata: dict, body: str)
            
        Raises:
            ValueError: If document is malformed
        """
        if not content.startswith(MarkdownDocument.DELIMITER):
            raise ValueError(f"Document must start with {MarkdownDocument.DELIMITER}")
        
        parts = content.split(MarkdownDocument.DELIMITER, 2)
        
        if len(parts) < 3:
            raise ValueError("Malformed frontmatter: couldn't find closing delimiter")
        
        yaml_str = parts[1].strip()
        body = parts[2].lstrip()
        
        try:
            metadata = YAMLSerializer.loads(yaml_str)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in frontmatter: {e}")
        
        return metadata, body
    
    @staticmethod
    def update_metadata(content: str, updates: dict) -> str:
        """
        Update metadata in a markdown document.
        
        Preserves body, updates only the specified metadata fields.
        """
        metadata, body = MarkdownDocument.parse(content)
        metadata.update(updates)
        return MarkdownDocument.create(metadata, body)

class KVStore:
    """
    Mixin/helper for classes that store typed key-value data.
    
    Provides common KV operations for both Incident and IncidentUpdate.
    """
    
    @staticmethod
    def parse_kv_from_dict(
        data: dict,
        string_key: str = "kv_strings",
        integer_key: str = "kv_integers", 
        float_key: str = "kv_floats"
    ) -> tuple[Dict[str, List[str]], Dict[str, List[int]], Dict[str, List[float]]]:
        """
        Parse KV data from a dict (e.g., parsed YAML).
        
        Handles type conversions for integers and floats.
        
        Returns:
            (kv_strings, kv_integers, kv_floats)
        """
        kv_strings = data.get(string_key, {})
        if kv_strings is None:
            kv_strings = {}
            
        kv_integers = {}
        for key, values in data.get(integer_key, {}).items():
            if values is None:
                continue
            if isinstance(values, list):
                kv_integers[key] = [int(v) if isinstance(v, str) else v for v in values]
            else:
                kv_integers[key] = [int(values) if isinstance(values, str) else values]
        
        kv_floats = {}
        for key, values in data.get(float_key, {}).items():
            if values is None:
                continue
            if isinstance(values, list):
                kv_floats[key] = [float(v) if isinstance(v, str) else v for v in values]
            else:
                kv_floats[key] = [float(values) if isinstance(values, str) else values]
        
        return kv_strings, kv_integers, kv_floats

    @staticmethod
    def format_kv_for_frontmatter(
        kv_strings: Optional[Dict[str, List[str]]],
        kv_integers: Optional[Dict[str, List[int]]],
        kv_floats: Optional[Dict[str, List[float]]]
    ) -> str:
        """
        Format KV data as YAML lines for frontmatter.
        
        Returns:
            String with kv_strings, kv_integers, kv_floats lines
        """
        lines = []
        lines.append(f"kv_strings = {YAMLSerializer.dict_to_inline_table(kv_strings or {})}")
        lines.append(f"kv_integers = {YAMLSerializer.dict_to_inline_table(kv_integers or {})}")
        lines.append(f"kv_floats = {YAMLSerializer.dict_to_inline_table(kv_floats or {})}")
        return '\n'.join(lines)


# Convenience aliases for backward compatibility
def escape_toml_string(s: str) -> str:
    """Escape a string for TOML. Alias for TOMLSerializer.escape_string()."""
    return TOMLSerializer.escape_string(s)

def escape_toml_key(key: str) -> str:
    """Escape a key for TOML. Alias for TOMLSerializer.escape_key()."""
    return TOMLSerializer.escape_key(key)

def toml_dumps(d: dict) -> str:
    """Serialize dict to TOML. Alias for TOMLSerializer.dumps()."""
    return TOMLSerializer.dumps(d)

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
    
    def __init__(
        self,
        id: str,
        kv_strings: Optional[Dict[str, List[str]]] = None,
        kv_integers: Optional[Dict[str, List[int]]] = None,
        kv_floats: Optional[Dict[str, List[float]]] = None,
        content: Optional[str] = None,
    ):
        self.id = id
        self.kv_strings = kv_strings or {}
        self.kv_integers = kv_integers or {}
        self.kv_floats = kv_floats or {}
        self.content = content or ""
    
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
    
    def to_markdown(self, project_config: ProjectConfig) -> str:
        """Serialize to Markdown with yaml frontmatter."""
        # Build frontmatter from special fields

        #body = self.kv_strings.pop("description", None)
        #if body is not None:
        #    body = body[0]
        
        frontmatter = {}
        for field_name in project_config.get_special_fields().keys():
            field = project_config.get_special_field(field_name)
            
            if field.field_type == "single":
                if field.value_type == "string":
                    value = self.kv_strings.get(field_name, [''])[0]
                    if value == "":
                        continue
                elif field.value_type == "integer":
                    value = self.kv_integers.get(field_name, [0])[0]
                    if value == 0:
                        continue
                elif field.value_type == "float":
                    value = self.kv_floats.get(field_name, [0.0])[0]
                    if value == 0.0:
                        continue
            else:  # multi
                if field.value_type == "string":
                    value = self.kv_strings.get(field_name, [])
                elif field.value_type == "integer":
                    value = self.kv_integers.get(field_name, [])
                elif field.value_type == "float":
                    value = self.kv_floats.get(field_name, [])
            
            if value == []:
                continue
                
            frontmatter[field_name] = value
        
        # Build custom fields section (non-special fields with type hints)
        other_kv = self._get_other_kv(project_config)
        custom_fields = {}
        # print (f"OTHER_KV: {other_kv}")
        if other_kv:
            custom_fields = {}
            for key, val in other_kv.items():
                if key in self.kv_strings:
                    hinted_key = YAMLSerializer.add_type_hint(key, "string")
                elif key in self.kv_integers:
                    hinted_key = YAMLSerializer.add_type_hint(key, "integer")
                elif key in self.kv_floats:
                    hinted_key = YAMLSerializer.add_type_hint(key, "float")
                else:
                    hinted_key = key
                custom_fields[hinted_key] = val
                # print (f"{hinted_key} = {val}")
        
        all_frontmatter = custom_fields | frontmatter
        return MarkdownDocument.create( all_frontmatter, body = self.content )
        
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
        # Use MarkdownDocument for parsing
        try:
            frontmatter, body = MarkdownDocument.parse(content)
        except ValueError:
            # Fallback to original regex parsing for compatibility
            print ("Markdown Parse failed, falling back")
            match = re.match(r'^\-\-\-\n(.*?)\n\-\-\-', content, re.DOTALL)
            if not match:
                raise ValueError("Invalid Markdown format: missing yaml frontmatter")
            frontmatter = YAMLSerializer.loads(match.group(1))
            body = content[match.end():].strip()


        # Rebuild KV from frontmatter
        kv_strings = {}
        kv_integers = {}
        kv_floats = {}
        
        special_fields = project_config.get_special_fields()
        special_field_names = set(special_fields.keys())
        
        # Process all items in frontmatter yaml
        for key_with_hint, value in frontmatter.items():
            # Check if this is a special field (by raw key name)
            if key_with_hint in special_field_names:
                # Special field - use config to determine type
                field = special_fields[key_with_hint]
                
                if field.field_type == "single":
                    if field.value_type == "string":
                        kv_strings[key_with_hint] = [value]
                    elif field.value_type == "integer":
                        kv_integers[key_with_hint] = [int(value)]
                    elif field.value_type == "float":
                        kv_floats[key_with_hint] = [float(value)]
                else:  # multi
                    if not isinstance(value, list):
                        value = [value]
                    if field.value_type == "string":
                        kv_strings[key_with_hint] = value
                    elif field.value_type == "integer":
                        kv_integers[key_with_hint] = [int(v) for v in value]
                    elif field.value_type == "float":
                        kv_floats[key_with_hint] = [float(v) for v in value]
            else:
                # Custom field - check for type hint
                clean_key, value_type = YAMLSerializer.strip_type_hint(key_with_hint)
                
                # Also check if clean_key is a special field (in case hint was added erroneously)
                if clean_key in special_field_names:
                    field = special_fields[clean_key]
                    if field.field_type == "single":
                        if field.value_type == "string":
                            kv_strings[clean_key] = [value]
                        elif field.value_type == "integer":
                            kv_integers[clean_key] = [int(value)]
                        elif field.value_type == "float":
                            kv_floats[clean_key] = [float(value)]
                    else:  # multi
                        if not isinstance(value, list):
                            value = [value]
                        if field.value_type == "string":
                            kv_strings[clean_key] = value
                        elif field.value_type == "integer":
                            kv_integers[clean_key] = [int(v) for v in value]
                        elif field.value_type == "float":
                            kv_floats[clean_key] = [float(v) for v in value]
                else:
                    # True custom field - use type hint or default to string
                    if value_type == "integer":
                        kv_integers[clean_key] = [int(v) for v in value] if isinstance(value, list) else [int(value)]
                    elif value_type == "float":
                        kv_floats[clean_key] = [float(v) for v in value] if isinstance(value, list) else [float(value)]
                    else:
                        # No hint or string hint - treat as string
                        kv_strings[clean_key] = [str(v) for v in value] if isinstance(value, list) else [str(value)]
        
        return cls(
            id=incident_id,
            kv_strings=kv_strings or None,
            kv_integers=kv_integers or None,
            kv_floats=kv_floats or None,
            content=body,
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
        """Convert update to Markdown with yaml header including KV data."""
        # System fields
        frontmatter = {
            "id": self.id,
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "author": self.author,
        }
        
        # Add KV data with type hints
        custom_fields = {}
        
        if self.kv_strings:
            for key, values in self.kv_strings.items():
                hinted_key = YAMLSerializer.add_type_hint(key, "string")
                custom_fields[hinted_key] = values[0] if len(values) == 1 else values
        
        if self.kv_integers:
            for key, values in self.kv_integers.items():
                hinted_key = YAMLSerializer.add_type_hint(key, "integer")
                custom_fields[hinted_key] = values[0] if len(values) == 1 else values
        
        if self.kv_floats:
            for key, values in self.kv_floats.items():
                hinted_key = YAMLSerializer.add_type_hint(key, "float")
                custom_fields[hinted_key] = values[0] if len(values) == 1 else values
        
        # Merge and serialize
        all_frontmatter = frontmatter | custom_fields
        return MarkdownDocument.create(all_frontmatter, body=self.message)

    @classmethod
    def from_markdown(cls, content: str, update_id: str, incident_id: str) -> "IncidentUpdate":
        """Parse update from Markdown with yaml header."""
        # Use MarkdownDocument for parsing
        try:
            frontmatter, message = MarkdownDocument.parse(content)
        except ValueError as e:
            raise ValueError(f"Invalid update file format: {e}")

        # Parse KV data using KVStore helper
        kv_strings, kv_integers, kv_floats = KVStore.parse_kv_from_dict(frontmatter)

        return cls(
            id=frontmatter.get("id", update_id),
            incident_id=frontmatter.get("incident_id", incident_id),
            timestamp=frontmatter.get("timestamp", ""),
            author=frontmatter.get("author", ""),
            message=message,
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
        num = int(num)
        while num:
            num, rem = divmod(num, 36)
            result.append(chars[rem])
        return "".join(reversed(result))
    
    @staticmethod
    def generate_incident_id() -> str:
        """
        Generate a distributed-safe incident ID based on epoch time.
        Format: REC-<base36 epoch seconds - 1735689600>    # Since Jan 1, 2026
        """
        epochtime = time.time() - 1735689600  # Time 0 = Jan 1, 2026
        rand = secrets.token_hex(1)
        recid = f"REC-{IDGenerator.to_base36(epochtime)}{rand}"
        return recid.upper()

    @staticmethod
    def generate_update_filename(id:Optional [str] = None) -> str:
        
        if id is not None:
            return f"{id}.md"
        else:
            raise ValueError(
                f"Invalid yaml syntax in {config_path}: {e}\n"
                f"To reset your configuration, run:\n\n"
                f"  aver config set-user-global --handle <your-handle> --email <your-email>"
            )
            

    @staticmethod
    def generate_update_id() -> str:
        epochtime = time.time() - 1770300000
        rand = secrets.token_hex(1)  # small entropy bump
        notefn = f"NT-{IDGenerator.to_base36(epochtime)}{rand}"
        return notefn.upper()

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
                "recordname": {
                    "type": "single",
                    "value_type": "string",
                    "editable": True,
                },
                "created_at": {
                    "type": "single",
                    "value_type": "string",
                    "editable": True,
                },
                "created_by": {
                    "type": "single",
                    "value_type": "string",
                    "editable": True,
                },
                "updated_at": {
                    "type": "single",
                    "value_type": "string",
                    "editable": True,
                },
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
        yaml.dump(self._raw_config, f)


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

    @staticmethod
    def dict_to_namespace(d):
        """
        Recursively convert a dictionary to SimpleNamespace for dot notation access.
    
        Handles nested dicts, lists of dicts, and preserves other types.
        """
        if isinstance(d, dict):
            return SimpleNamespace(**{k: DatabaseDiscovery.dict_to_namespace(v) for k, v in d.items()})
        elif isinstance(d, list):
            return [DatabaseDiscovery.dict_to_namespace(item) for item in d]
        else:
            return d

    @staticmethod
    def _do_get_user_config() -> dict:
        """
        Load the global user configuration from ~/.config/aver/user.toml.
        
        Required fields (if file exists):
        - user.handle: User identifier/name
        - user.email: User email
        
        Optional sections:
        - [libraries.<alias>]: Library aliases with optional per-library identity
          - path (required): Filesystem path to the .aver database
          - handle (optional): Override user handle for this library
          - email (optional): Override user email for this library
        
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
                f"  aver admin config set-user --handle <your-handle> --email <your-email>"
            )
        except PermissionError as e:
            raise PermissionError(
                f"Permission denied reading {config_path}: {e}"
            )
        except Exception as e:
            raise ValueError(
                f"Failed to read user config from {config_path}: {e}"
            )
        
        # Validate required [user] fields exist
        if "user" in config:
            required_user_fields = ["handle", "email"]
            missing_user_fields = [field for field in required_user_fields if field not in config["user"]]
            
            if missing_user_fields:
                raise ValueError(
                    f"User configuration at {config_path} is missing required fields: "
                    f"{', '.join(missing_user_fields)}\n\n"
                    f"Please configure your user identity:\n\n"
                    f"  aver admin config set-user --handle <your-handle> --email <your-email>\n\n"
                )
            
            # Validate required fields are not empty
            for field in required_user_fields:
                value = config["user"][field]
                if not isinstance(value, str):
                    raise ValueError(
                        f"Field '{field}' in {config_path} must be a string, "
                        f"got {type(value).__name__}\n\n"
                        f"To fix this, run:\n\n"
                        f"  aver admin config set-user --handle <your-handle> --email <your-email>"
                    )
                if not value.strip():
                    raise ValueError(
                        f"Field '{field}' in {config_path} cannot be empty\n\n"
                        f"To fix this, run:\n\n"
                        f"  aver admin config set-user --handle <your-handle> --email <your-email>"
                    )
            
            # Validate email format (basic check)
            email = config["user"]["email"].strip()
            if "@" not in email or "." not in email.split("@")[-1]:
                raise ValueError(
                    f"Field 'email' in {config_path} appears invalid: '{email}'\n"
                    f"Expected format: user@example.com\n\n"
                    f"To fix this, run:\n\n"
                    f"  aver admin config set-user --handle <your-handle> --email <your-email>\n\n"
                    f"Example:\n"
                    f"  aver admin config set-user --handle mattd --email dentm42@gmail.com"
                )
            
            # Store trimmed versions to remove accidental whitespace
            config["user"]["handle"] = config["user"]["handle"].strip()
            config["user"]["email"] = email
        
        # Validate [libraries] section if present
        if "libraries" in config:
            if not isinstance(config["libraries"], dict):
                raise ValueError(
                    f"[libraries] section in {config_path} must be a table of aliases.\n\n"
                    f"Expected format:\n"
                    f"  [libraries.myalias]\n"
                    f"  path = \"/path/to/.aver\"\n"
                )
            
            for alias, lib_config in config["libraries"].items():
                if not isinstance(lib_config, dict):
                    raise ValueError(
                        f"Library alias '{alias}' in {config_path} must be a table.\n\n"
                        f"Expected format:\n"
                        f"  [libraries.{alias}]\n"
                        f"  path = \"/path/to/.aver\"\n"
                    )
                
                if "path" not in lib_config:
                    raise ValueError(
                        f"Library alias '{alias}' in {config_path} is missing required 'path' field.\n\n"
                        f"Expected format:\n"
                        f"  [libraries.{alias}]\n"
                        f"  path = \"/path/to/.aver\"\n"
                    )
                
                # Validate per-library email if present
                if "email" in lib_config:
                    lib_email = lib_config["email"].strip()
                    if "@" not in lib_email or "." not in lib_email.split("@")[-1]:
                        raise ValueError(
                            f"Library '{alias}' email appears invalid: '{lib_email}'\n"
                            f"Expected format: user@example.com"
                        )
                    config["libraries"][alias]["email"] = lib_email
                
                if "handle" in lib_config:
                    config["libraries"][alias]["handle"] = lib_config["handle"].strip()
        
        # Validate [locations] values if present
        if "locations" in config:
            if not isinstance(config["locations"], dict):
                raise ValueError(
                    f"[locations] section in {config_path} must be a table.\n\n"
                    f"Expected format:\n"
                    f"  [locations]\n"
                    f'  "/some/path" = "/path/to/.aver"\n'
                    f'  "/other/path" = "myalias"'
                )
            
            for loc_key, loc_value in config["locations"].items():
                if not isinstance(loc_value, str):
                    raise ValueError(
                        f"[locations] value for '{loc_key}' must be a string, "
                        f"got {type(loc_value).__name__}"
                    )
                # Validate format: absolute path or bare alias (no relative paths)
                if not loc_value.startswith('/') and '/' in loc_value:
                    raise ValueError(
                        f"[locations] value for '{loc_key}' is invalid: '{loc_value}'\n"
                        f"Values must be either an absolute path (starting with '/') "
                        f"or a library alias name (no slashes).\n\n"
                        f"Examples:\n"
                        f'  "/my/path" = "/path/to/.aver"   # absolute path\n'
                        f'  "/my/path" = "myalias"          # library alias'
                    )
        
        def dict_to_configdict(d):
            if isinstance(d, dict):
                return ConfigDict({k: dict_to_configdict(v) for k, v in d.items()})
            elif isinstance(d, list):
                return [dict_to_configdict(item) for item in d]
            else:
                return d
        
        return dict_to_configdict(config)

    @staticmethod
    def _to_plain_dict(d):
        """
        Recursively convert ConfigDict (or any dict subclass) back to plain dict.
        """
        if isinstance(d, dict):
            return {k: DatabaseDiscovery._to_plain_dict(v) for k, v in d.items()}
        elif isinstance(d, list):
            return [DatabaseDiscovery._to_plain_dict(item) for item in d]
        else:
            return d

    @staticmethod
    def set_user_config(config: dict):
        """Save the global user configuration."""
        if not tomli_w:
            raise RuntimeError(
                "tomli_w not available. Cannot write TOML config.\n"
                "Install with: pip install tomli_w"
            )
        config_path = DatabaseDiscovery.get_user_config_path()
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Deep-convert to plain dict to ensure clean serialization
        plain_config = DatabaseDiscovery._to_plain_dict(config)
        
        with open(config_path, "wb") as f:
            yaml.dump(plain_config, f)

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
        if not tomli_w:
            raise RuntimeError(
                "tomli_w not available. Cannot write TOML config.\n"
                "Install with: pip install tomli_w"
            )
        config_path = DatabaseDiscovery.get_project_config_path(db_root)
        with open(config_path, "wb") as f:
            tomli_w.dump(config, f)

    # =========================================================================
    # Git Identity
    # =========================================================================

    @staticmethod
    def get_git_identity() -> Optional[dict]:
        """
        Read the current git user identity (user.name and user.email).
        
        Returns:
            Dict with 'handle' and 'email' keys, or None if not in a git repo
            or git identity is not configured.
        """
        try:
            name_result = subprocess.run(
                ["git", "config", "user.name"],
                capture_output=True, text=True, check=True,
            )
            email_result = subprocess.run(
                ["git", "config", "user.email"],
                capture_output=True, text=True, check=True,
            )
            name = name_result.stdout.strip()
            email = email_result.stdout.strip()
            
            if name and email:
                return {"handle": name, "email": email}
            return None
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

    @staticmethod
    def get_prefer_git_identity(db_path: Optional[Path] = None) -> Optional[bool]:
        """
        Check if prefer_git_identity is set for the given database path.
        
        Checks (in priority order):
        1. Matching [libraries.<alias>] entry for prefer_git_identity
        2. Global [user] prefer_git_identity
        
        Args:
            db_path: Path to the .aver database directory.
        
        Returns:
            True if prefer_git_identity is enabled (use git identity silently).
            False if prefer_git_identity is explicitly disabled (use config identity silently).
            None if prefer_git_identity is not set at any level (fall through to flags/error).
        """
        config = DatabaseDiscovery.get_user_config()
        
        # Check library-level setting first
        if db_path is not None:
            db_path_resolved = Path(db_path).resolve()
            libraries = config.get("libraries", {})
            
            for alias, lib_config in libraries.items():
                lib_path = Path(lib_config.get("path", ""))
                try:
                    lib_path = lib_path.resolve()
                except Exception:
                    continue
                if lib_path == db_path_resolved:
                    if "prefer_git_identity" in lib_config:
                        return bool(lib_config["prefer_git_identity"])
                    break
        
        # Check global-level setting
        global_user = config.get("user", {})
        if "prefer_git_identity" in global_user:
            return bool(global_user["prefer_git_identity"])
        
        return None

    # =========================================================================
    # Library Alias Resolution
    # =========================================================================

    @staticmethod
    def _resolve_location_value(value: str, config: Optional[dict] = None) -> Path:
        """
        Resolve a [locations] value to a filesystem path.
        
        Rules:
        - Starts with '/': literal absolute path, returned as-is
        - Does not start with '/' but contains '/': invalid format, raise error
        - Otherwise: treated as a library alias handle, resolved via [libraries.<handle>].path
        
        Args:
            value: The raw value string from [locations]
            config: Optional pre-loaded config dict (avoids re-reading). If None, loads config.
        
        Returns:
            Resolved Path
        
        Raises:
            ValueError: If format is invalid or alias doesn't exist
        """
        if value.startswith('/'):
            return Path(value).resolve()
        
        if '/' in value:
            raise ValueError(
                f"Invalid [locations] value: '{value}'\n"
                f"Values must be either an absolute path (starting with '/') "
                f"or a library alias name (no slashes)."
            )
        
        # It's a library alias handle
        if config is None:
            config = DatabaseDiscovery.get_user_config()
        
        libraries = config.get("libraries", {})
        if value not in libraries:
            raise ValueError(
                f"[locations] references unknown library alias: '{value}'\n"
                f"Add it first with: aver admin config add-alias --alias {value} --path /path/to/.aver"
            )
        
        lib_path = libraries[value].get("path")
        if not lib_path:
            raise ValueError(
                f"Library alias '{value}' has no 'path' defined."
            )
        
        return Path(lib_path).resolve()

    @staticmethod
    def resolve_alias(alias: str) -> Path:
        """
        Resolve a library alias to its filesystem path.
        
        Looks up the alias in [libraries.<alias>] of user config.
        
        Args:
            alias: Library alias name (e.g. "myproject")
        
        Returns:
            Resolved Path to the .aver database directory
        
        Raises:
            RuntimeError: If alias not found or path doesn't exist
        """
        config = DatabaseDiscovery.get_user_config()
        libraries = config.get("libraries", {})
        
        if not libraries:
            raise RuntimeError(
                f"No library aliases configured.\n"
                f"Add one with: aver admin config add-alias --alias {alias} --path /path/to/.aver"
            )
        
        if alias not in libraries:
            available = ', '.join(sorted(libraries.keys()))
            raise RuntimeError(
                f"Unknown library alias: '{alias}'\n"
                f"Available aliases: {available}\n\n"
                f"Add it with: aver admin config add-alias --alias {alias} --path /path/to/.aver"
            )
        
        lib_config = libraries[alias]
        db_path = Path(lib_config["path"]).resolve()
        
        if not db_path.exists():
            raise RuntimeError(
                f"Library alias '{alias}' points to non-existent path: {db_path}\n"
                f"Update it with: aver admin config add-alias --alias {alias} --path /correct/path"
            )
        
        return db_path

    @staticmethod
    def get_effective_user(db_path: Optional[Path] = None) -> dict:
        """
        Get the effective user identity for a given database path.
        
        Resolution order:
        1. If db_path matches a library alias with handle/email overrides, use those
        2. Fall back to global [user] config
        
        For partial overrides (e.g. library defines handle but not email),
        the missing fields fall back to global.
        
        Args:
            db_path: Path to the .aver database directory. If None, returns global user.
        
        Returns:
            Dict with 'handle' and 'email' keys
        
        Raises:
            RuntimeError: If no user identity is configured (neither global nor per-library)
        """
        config = DatabaseDiscovery.get_user_config()
        
        # Start with global defaults
        global_user = config.get("user", {})
        effective = {
            "handle": global_user.get("handle"),
            "email": global_user.get("email"),
        }
        
        # Check library overrides if we have a db_path
        if db_path is not None:
            db_path_resolved = Path(db_path).resolve()
            libraries = config.get("libraries", {})
            
            for alias, lib_config in libraries.items():
                lib_path = Path(lib_config["path"]).resolve()
                if lib_path == db_path_resolved:
                    # Found matching library — apply overrides
                    if "handle" in lib_config:
                        effective["handle"] = lib_config["handle"]
                    if "email" in lib_config:
                        effective["email"] = lib_config["email"]
                    break
        
        # Validate we have both required fields
        if not effective.get("handle") or not effective.get("email"):
            missing = [k for k in ("handle", "email") if not effective.get(k)]
            raise RuntimeError(
                f"User identity incomplete (missing: {', '.join(missing)}).\n"
                f"Set global identity: aver admin config set-user --handle <handle> --email <email>\n"
                f"Or per-library:      aver admin config set-user --library <alias> --handle <handle> --email <email>"
            )
        
        return effective

    @staticmethod
    def get_all_aliases() -> dict:
        """
        Get all configured library aliases.
        
        Returns:
            Dict mapping alias -> {path, handle (optional), email (optional)}
        """
        config = DatabaseDiscovery.get_user_config()
        return dict(config.get("libraries", {}))

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
        6. Library aliases (secondary options)
    
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
            for path_prefix, db_path_raw in user_config['locations'].items():
                try:
                    db_path_obj = DatabaseDiscovery._resolve_location_value(
                        db_path_raw, config=user_config
                    )
                except ValueError as e:
                    # Skip invalid entries with a warning (don't crash discovery)
                    print(f"Warning: Skipping [locations] entry '{path_prefix}': {e}", file=sys.stderr)
                    continue
                
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
                        'source': f'User config [locations]: {path_prefix} → {db_path_raw}',
                        'category': 'available',
                    }
    
        # 6) Library aliases (secondary options, skip duplicates)
        libraries = user_config.get("libraries", {})
        for alias, lib_config in libraries.items():
            lib_path = Path(lib_config["path"]).resolve()
            
            # Skip if already present from another discovery method
            if any(c['path'] == lib_path for c in candidates.values()):
                continue
            
            if lib_path.exists():
                key = f"library_alias_{alias}"
                candidates[key] = {
                    'path': lib_path,
                    'source': f'Library alias: {alias} → {lib_config["path"]}',
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
                return selected['path']
        
        # Fallback: use first available [locations] entry
        for key, info in candidates.items():
            if info.get('category') == 'available':
                return info['path']
        
        # Last resort: use any remaining candidate
        if candidates:
            selected = list(candidates.values())[0]
            return selected['path']
        
        raise RuntimeError("No suitable incident database found")
 

    @staticmethod
    def lookup_user_locations(cwd: Path) -> Optional[Path]:
        """
        Check user-configured locations mapping for the current working directory.

        Longest matching parent key is used.
        Returns the mapped path if found, else None.

        Location values can be:
        - Absolute paths: "/path/to/.aver"
        - Library alias handles: "myproject" (resolved via [libraries.myproject].path)

        Example user.toml:
        [locations]
        "/root/path" = "/path/to/data"
        "/root/path/longer" = "myproject"
        """
        config = DatabaseDiscovery.get_user_config()
        locations = config.get('locations', {})
        if not locations:
            return None
        cwd_resolved = cwd.resolve()

        matches = []
        for key, value in locations.items():
            if cwd_resolved.is_relative_to(Path(key).resolve()):  # Python 3.9+
                try:
                    resolved = DatabaseDiscovery._resolve_location_value(value, config=config)
                    matches.append((Path(key).resolve(), resolved))
                except ValueError as e:
                    print(f"Warning: Skipping [locations] entry '{key}': {e}", file=sys.stderr)
                    continue

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
                "Initialize with: aver admin init\n"
                "Or: aver admin init --location /path/to/db"
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
        1. User-global config (~/.config/incident-manager/user.toml)
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
            if not KVParser._is_valid_key(kv_str):
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
        Operators: <, >, =, <=, >=, <>, !=
        
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
        # NOTE: If you add more, make sure none of the PREVIOUS
        #       items in the list will match.
        for op in ['<=', '>=', '!=', '<>', '=', '<', '>']:
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
            f"Operators: <, >, =, <=, >=, <>, !="
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
            print(f"Warning: Failed to load incident {incident_id}: path: {path} {e}", file=sys.stderr)
            return None

    def delete_incident(self, incident_id: str):
        """Delete incident file."""
        path = self._get_incident_path(incident_id)
        if path.exists():
            path.unlink()

    def list_incident_files(self) -> List[str]:
        """List all incident IDs from files."""
        incident_ids = []
        for file_path in self.incidents_dir.glob("REC-*.md"):
            incident_ids.append(file_path.stem)
        return sorted(incident_ids)

    def save_update(self, incident_id: str, update: IncidentUpdate):
        """Save update to Markdown file with yaml header."""
        updates_dir = self._get_updates_dir(incident_id)
        filename = IDGenerator.generate_update_filename(update.id)
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
        
    def validate_custom_id(custom_id: str) -> bool:
        """
        Validate custom record ID contains only allowed characters.
    
        Allowed: A-Z, a-z, 0-9, underscore (_), hyphen (-)
    
        Args:
            custom_id: The custom ID to validate
        
        Returns:
            True if valid, False otherwise
        """
        pattern = r'^[A-Za-z0-9_-]+$'
        return bool(re.match(pattern, custom_id))
 
# ============================================================================
# Index Database (OPTIMIZED - Single KV Table, Flat Keyspace)
# ============================================================================

class IncidentIndexDatabase:
    """SQLite-based index for incidents (search and filtering only)."""

    def __init__(self, database_path: Path):
        self.database_path = database_path
        self._ensure_schema()
    
    @staticmethod
    def _generate_timestamp() -> str:
        """Generate ISO 8601 timestamp with Z suffix."""
        return datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

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
    
        # Unified Key-Value table
        # No type column needed - searches attempt all types naturally
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_store (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                incident_id TEXT NOT NULL,
                update_id TEXT,
                key TEXT NOT NULL,
                value_string TEXT,
                value_integer INTEGER,
                value_float REAL,
                created_at TEXT NOT NULL
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_incident_key 
            ON kv_store(incident_id, key)
        """)
 
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_update_key 
            ON kv_store(update_id, key)
        """)    

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_key
            ON kv_store(key)
        """)
    
        # Partial indexes for value searches (only include non-NULL values)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_string_value
            ON kv_store(incident_id, key, value_string)
            WHERE value_string IS NOT NULL
        """)
    
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_integer_value
            ON kv_store(incident_id, key, value_integer)
            WHERE value_integer IS NOT NULL
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_float_value
            ON kv_store(incident_id, key, value_float)
            WHERE value_float IS NOT NULL
        """)

        conn.commit()
        conn.close()

    def index_incident(self, incident: Incident, project_config: ProjectConfig):
        """Add or update incident in index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        now = self._generate_timestamp()
    
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
    
        # Get title and description from kv_store
        title = incident.kv_strings.get('title', [''])[0] if incident.kv_strings else ''
        description = incident.content
        content = f"{title}\n\n{description}"
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
        cursor.execute("DELETE FROM kv_store WHERE incident_id = ?", (incident_id,))
        conn.commit()
        conn.close()

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
            
                if field.field_type == "single":
                    incident_ids_query += f"""
                        AND id IN (
                            SELECT incident_id FROM kv_store
                            WHERE key = ? AND (
                                value_string = ? OR 
                                value_integer = ? OR 
                                value_float = ?
                            ) AND update_id IS NULL
                        )
                    """
                    params.extend([field_name, value, value, value])
                else:  # multi - value must be in the list
                    if isinstance(value, list):
                        # Match ANY value in the list
                        value_placeholders = ",".join("?" * len(value))
                        incident_ids_query += f"""
                            AND id IN (
                                SELECT incident_id FROM kv_store
                                WHERE key = ? AND (
                                    value_string IN ({value_placeholders}) OR 
                                    value_integer IN ({value_placeholders}) OR 
                                    value_float IN ({value_placeholders})
                                ) AND update_id IS NULL
                            )
                        """
                        params.append(field_name)
                        params.extend(value)
                        params.extend(value)
                        params.extend(value)
                    else:
                        incident_ids_query += f"""
                            AND id IN (
                                SELECT incident_id FROM kv_store
                                WHERE key = ? AND (
                                    value_string = ? OR 
                                    value_integer = ? OR 
                                    value_float = ?
                                ) AND update_id IS NULL
                            )
                        """
                        params.extend([field_name, value, value, value])
     
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
        cursor.execute("DELETE FROM kv_store")
        conn.commit()
        conn.close()

    def index_kv_data(self, incident: Incident):
        """Index key-value data for incident (update_id = NULL)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = self._generate_timestamp()
    
        # Clear existing KV data for this incident (incident-level only)
        cursor.execute("DELETE FROM kv_store WHERE incident_id = ? AND update_id IS NULL", (incident.id,))
    
        # Insert string KV data
        for key, values in (incident.kv_strings or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        """INSERT INTO kv_store 
                           (incident_id, update_id, key, value_string, created_at) 
                           VALUES (?, NULL, ?, ?, ?)""",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass  # Duplicate, skip
    
        # Insert integer KV data
        for key, values in (incident.kv_integers or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        """INSERT INTO kv_store 
                           (incident_id, update_id, key, value_integer, created_at) 
                           VALUES (?, NULL, ?, ?, ?)""",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert float KV data
        for key, values in (incident.kv_floats or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        """INSERT INTO kv_store 
                           (incident_id, update_id, key, value_float, created_at) 
                           VALUES (?, NULL, ?, ?, ?)""",
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
        now = self._generate_timestamp()
    
        # Insert string KV data for update
        for key, values in (kv_strings or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        """INSERT INTO kv_store 
                           (incident_id, update_id, key, value_string, created_at) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (incident_id, update_id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert integer KV data for update
        for key, values in (kv_integers or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        """INSERT INTO kv_store 
                           (incident_id, update_id, key, value_integer, created_at) 
                           VALUES (?, ?, ?, ?, ?)""",
                        (incident_id, update_id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert float KV data for update
        for key, values in (kv_floats or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        """INSERT INTO kv_store 
                           (incident_id, update_id, key, value_float, created_at) 
                           VALUES (?, ?, ?, ?, ?)""",
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
        now = self._generate_timestamp()
    
        if op == KVParser.TYPE_STRING:
            value_column = "value_string"
        elif op == KVParser.TYPE_INTEGER:
            value_column = "value_integer"
        elif op == KVParser.TYPE_FLOAT:
            value_column = "value_float"
        else:
            raise ValueError(f"Invalid operator: {op}")
    
        # Delete existing values for this key
        if update_id:
            cursor.execute(
                "DELETE FROM kv_store WHERE incident_id = ? AND update_id = ? AND key = ?", 
                (incident_id, update_id, key)
            )
        else:
            cursor.execute(
                "DELETE FROM kv_store WHERE incident_id = ? AND update_id IS NULL AND key = ?", 
                (incident_id, key)
            )
        
        # Insert new value
        cursor.execute(
            f"""INSERT INTO kv_store 
               (incident_id, update_id, key, {value_column}, created_at) 
               VALUES (?, ?, ?, ?, ?)""",
            (incident_id, update_id, key, value, now)
        )
    
        conn.commit()
        conn.close()
    
    def add_kv_multi(self, incident_id: str, key: str, op: str, value: Any, update_id: Optional[str] = None):
        """Add multi-value KV (keeps existing)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = self._generate_timestamp()
    
        if op == KVParser.TYPE_STRING:
            value_column = "value_string"
        elif op == KVParser.TYPE_INTEGER:
            value_column = "value_integer"
        elif op == KVParser.TYPE_FLOAT:
            value_column = "value_float"
        else:
            raise ValueError(f"Invalid operator: {op}")
    
        # Insert value (PRIMARY KEY prevents true duplication)
        try:
            cursor.execute(
                f"""INSERT INTO kv_store 
                   (incident_id, update_id, key, {value_column}, created_at) 
                   VALUES (?, ?, ?, ?, ?)""",
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
            cursor.execute(
                "DELETE FROM kv_store WHERE incident_id = ? AND update_id = ? AND key = ?", 
                (incident_id, update_id, key)
            )
        else:
            cursor.execute(
                "DELETE FROM kv_store WHERE incident_id = ? AND update_id IS NULL AND key = ?", 
                (incident_id, key)
            )
    
        conn.commit()
        conn.close()
    
    def remove_kv_value(self, incident_id: str, key: str, op: str, value: Any, update_id: Optional[str] = None):
        """Remove specific key/value pair."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        if op == KVParser.TYPE_STRING:
            value_column = "value_string"
        elif op == KVParser.TYPE_INTEGER:
            value_column = "value_integer"
        elif op == KVParser.TYPE_FLOAT:
            value_column = "value_float"
        else:
            raise ValueError(f"Invalid operator: {op}")
    
        if update_id:
            cursor.execute(
                f"""DELETE FROM kv_store 
                   WHERE incident_id = ? AND update_id = ? AND key = ? 
                   AND {value_column} = ?""",
                (incident_id, update_id, key, value)
            )
        else:
            cursor.execute(
                f"""DELETE FROM kv_store 
                   WHERE incident_id = ? AND update_id IS NULL AND key = ? 
                   AND {value_column} = ?""",
                (incident_id, key, value)
            )
    
        conn.commit()
        conn.close()

    def search_kv(
        self, 
        ksearch_list: List[tuple], 
        incident_ids: Optional[List[str]] = None,
        update_ids: Optional[List[str]] = None,
        return_updates: bool = False,
        search_updates: bool = False
    ) -> List[str]:
        """
        Search by key-value criteria with AND logic (all criteria must match).

        Args:
            ksearch_list: List of (key, operator, value) tuples - ALL must match
                operator must be one of: '=', '<', '>', '<=', '>=', "!=", "<>"
                If empty, returns all incident_ids/update_ids matching other filters
            incident_ids: If provided, search only within these incidents (None = search all)
            update_ids: If provided, search only within these updates
            return_updates: If True, return update IDs; if False, return incident IDs
            search_updates: If True, search for updates; if False, search only incidents
            
        Returns:
            List of matching incident IDs or update IDs (depending on return_updates)
            
        Raises:
            ValueError: If operator is not in the allowed set
        """
        # Whitelist of allowed operators
        ALLOWED_OPERATORS = {'=', '<', '>', '<=', '>=', "<>", "!="}
        
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Separate equality and inequality conditions
        equality_conditions = []
        inequality_conditions = []
        
        for key, operator, value in ksearch_list:
            # Validate operator
            if operator not in ALLOWED_OPERATORS:
                raise ValueError(f"Invalid operator '{operator}'. Must be one of: {ALLOWED_OPERATORS}")
            
            if operator in ('!=', '<>'):
                inequality_conditions.append((key, operator, value))
            else:
                equality_conditions.append((key, operator, value))
        
        # Start with base table for equality conditions
        select_clause = "SELECT DISTINCT base.incident_id, base.update_id"
        from_clause = "FROM kv_store base"
        joins = []
        where_parts = ["1=1"]
        params = []
        join_counter = 0
        
        # Add update_id filter based on search_updates
        if search_updates:
            where_parts.append("base.update_id IS NOT NULL")
        else:
            where_parts.append("base.update_id IS NULL")
        
        # Add incident_ids filter
        if incident_ids:
            placeholders = ",".join("?" * len(incident_ids))
            where_parts.append(f"base.incident_id IN ({placeholders})")
            params.extend(incident_ids)
        
        # Add update_ids filter
        if update_ids:
            placeholders = ",".join("?" * len(update_ids))
            where_parts.append(f"base.update_id IN ({placeholders})")
            params.extend(update_ids)
        
        # Add each EQUALITY/COMPARISON search criterion as an INNER JOIN
        for key, operator, value in equality_conditions:
            # Create alias for this join
            alias = f"kv{join_counter}"
            join_counter += 1
            
            # Build JOIN condition for this criterion
            join = f"""INNER JOIN kv_store {alias} ON 
                base.incident_id = {alias}.incident_id 
                AND (base.update_id = {alias}.update_id OR (base.update_id IS NULL AND {alias}.update_id IS NULL))
                AND (
                    ({alias}.key = ? AND {alias}.value_float {operator} ?)
                    OR ({alias}.key = ? AND {alias}.value_integer {operator} ?)
                    OR ({alias}.key = ? AND {alias}.value_string {operator} ?)
                )"""
            joins.append(join)
            
            # Add parameters for type attempts
            try:
                float_val = float(value)
            except (ValueError, TypeError):
                float_val = None
            
            try:
                int_val = int(value)
            except (ValueError, TypeError):
                int_val = None
            
            str_val = str(value)
            
            # Add parameters: key and values for each type
            params.extend([
                key, float_val,
                key, int_val,
                key, str_val
            ])
        
        # Build query for equality conditions
        query_with_joins = select_clause + " " + from_clause
        for join in joins:
            query_with_joins += " " + join
        query_with_joins += " WHERE " + " AND ".join(where_parts)

        cursor.execute(query_with_joins, params)
        results = cursor.fetchall()
        
        # If no inequality conditions, we're done
        if not inequality_conditions:
            conn.close()
            return [row[1] if return_updates else row[0] for row in results]
        
        # Handle inequality conditions by EXCLUSION
        # Start with the results from equality conditions (or all records if no equality conditions)
        if equality_conditions:
            # Use results from equality search as starting set
            candidate_set = set((row[0], row[1]) for row in results)
        else:
            # No equality conditions - start with all records matching base filters
            cursor.execute(query_with_joins, params)
            candidate_set = set((row[0], row[1]) for row in cursor.fetchall())
        
        # For each inequality condition, exclude records that match the EQUALITY
        for key, operator, value in inequality_conditions:
            # Find records where key = value (these should be excluded)
            exclude_query = """
                SELECT DISTINCT incident_id, update_id
                FROM kv_store
                WHERE (
                    (key = ? AND value_float = ?)
                    OR (key = ? AND value_integer = ?)
                    OR (key = ? AND value_string = ?)
                )
            """
            
            # Add search_updates filter
            if search_updates:
                exclude_query += " AND update_id IS NOT NULL"
            else:
                exclude_query += " AND update_id IS NULL"
            
            # Add incident_ids filter if provided
            if incident_ids:
                placeholders = ",".join("?" * len(incident_ids))
                exclude_query += f" AND incident_id IN ({placeholders})"
            
            # Add update_ids filter if provided
            if update_ids:
                placeholders = ",".join("?" * len(update_ids))
                exclude_query += f" AND update_id IN ({placeholders})"
            
            exclude_params = []
            
            # Add parameters for type attempts
            try:
                float_val = float(value)
            except (ValueError, TypeError):
                float_val = None
            
            try:
                int_val = int(value)
            except (ValueError, TypeError):
                int_val = None
            
            str_val = str(value)
            
            exclude_params.extend([
                key, float_val,
                key, int_val,
                key, str_val
            ])
            
            # Add incident_ids to params if needed
            if incident_ids:
                exclude_params.extend(incident_ids)
            
            # Add update_ids to params if needed
            if update_ids:
                exclude_params.extend(update_ids)
            
            cursor.execute(exclude_query, exclude_params)
            exclude_set = set((row[0], row[1]) for row in cursor.fetchall())
            
            # Remove excluded records from candidate set
            candidate_set -= exclude_set
        
        conn.close()
        
        # Extract the appropriate column based on return_updates
        return [row[1] if return_updates else row[0] for row in sorted(candidate_set)]
    
    
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
            kv_data[inc_id] = {}
            
            query = """
                SELECT key, value_string, value_integer, value_float 
                FROM kv_store 
                WHERE incident_id = ? AND update_id {}
            """.format("= ?" if update_id else "IS NULL")
            
            params = [inc_id]
            if update_id:
                params.append(update_id)
            
            cursor.execute(query, params)
            
            for key, v_str, v_int, v_float in cursor.fetchall():
                if key not in kv_data[inc_id]:
                    kv_data[inc_id][key] = []
                
                # Store the actual value (whichever is not NULL)
                value = v_str if v_str is not None else (v_int if v_int is not None else v_float)
                kv_data[inc_id][key].append(value)
        
        conn.close()
        
        # Sort using custom key function
        def sort_key(incident_id):
            keys = []
            for sort_key_name, ascending in ksort_list:
                value = None
                
                if sort_key_name in kv_data[incident_id] and kv_data[incident_id][sort_key_name]:
                    value = kv_data[incident_id][sort_key_name][0]
                
                if value is None:
                    keys.append((1, ""))
                else:
                    if isinstance(value, (int, float)):
                        sort_val = value if ascending else -value
                    else:
                        sort_val = value if ascending else ''.join(chr(255 - ord(c)) for c in str(value))
                    keys.append((0, sort_val))
            return tuple(keys)
        
        sorted_ids = sorted(incident_ids, key=sort_key)
        return sorted_ids


# ============================================================================
# Reindexing
# ============================================================================


class IncidentReindexer:
    """Rebuild index from files."""

    def __init__(self, storage: IncidentFileStorage, index_db: IncidentIndexDatabase, project_config: ProjectConfig):
        self.storage = storage
        self.index_db = index_db
        self.project_config = project_config

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
        indexed_updates = 0
        for incident_id in incident_ids:
            incident = self.storage.load_incident(incident_id, self.project_config)
            if incident:
                self.index_db.index_incident(incident, self.project_config)
                self.index_db.index_kv_data(incident)
                indexed_count += 1
                if verbose:
                    print(f"  ✓ {incident_id}",end=":")
            else:
                if verbose:
                    print(f"  ✗ {incident_id} (failed to load)")
            
            # Index updates for this incident (moved inside the loop)
            updates = self.storage.load_updates(incident_id)

            for update in updates:
                self.index_db.index_update(update)
                if verbose:
                    print(f".",end="")
                indexed_updates += 1
            print()
        if verbose:
            print(f"✓ Reindexed {indexed_count} records, {indexed_updates} updates")
        
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
        
        # Resolve effective user identity (per-library override → global fallback)
        self.effective_user = DatabaseDiscovery.get_effective_user(self.db_root)

    def _strip_type_suffix(self, key: str) -> str:
        """
        Strip type suffix from key name.
        
        Keys may have suffixes like __string, __integer, __float appended.
        This strips them to get the base field name for comparison with
        special_fields configuration.
        
        Args:
            key: Key name, possibly with suffix
            
        Returns:
            Base key name without suffix
        """
        for suffix in ['__string', '__integer', '__float']:
            if key.endswith(suffix):
                return key[:-len(suffix)]
        return key
    
    def set_user_override(self, handle: str, email: str):
        """
        Override the effective user identity for this manager instance.
        
        Used by the CLI to inject a resolved identity (e.g. git identity)
        after construction. This is ephemeral — it does not persist to config.
        
        Args:
            handle: User handle to use for authoring
            email: User email to use for authoring
        """
        self.effective_user = {"handle": handle, "email": email}
    
    @staticmethod
    def _generate_timestamp() -> str:
        """Generate ISO 8601 timestamp with Z suffix."""
        return datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
    def _remove_kv(self, incident: Incident, key: str, value: Optional[Any] = None) -> None:
        """
        Remove KV entry from incident.
        
        If value is None, removes the entire key from all KV stores.
        If value is provided, removes only that specific value from the appropriate store.
        
        Args:
            incident: Incident to modify
            key: Key to remove
            value: Optional specific value to remove (for multi-value fields)
        """
        if value is None:
            # Remove entire key
            if key in incident.kv_strings:
                del incident.kv_strings[key]
            if key in incident.kv_integers:
                del incident.kv_integers[key]
            if key in incident.kv_floats:
                del incident.kv_floats[key]
        else:
            # Remove specific value
            if key in incident.kv_strings:
                incident.kv_strings[key] = [v for v in incident.kv_strings[key] if v != str(value)]
            if key in incident.kv_integers:
                incident.kv_integers[key] = [v for v in incident.kv_integers[key] if v != int(value)]
            if key in incident.kv_floats:
                incident.kv_floats[key] = [v for v in incident.kv_floats[key] if v != float(value)]
    
    def _get_kv_store_for_type(
        self,
        kvtype: Optional[str],
        incident: Incident,
    ) -> tuple[dict, callable]:
        """
        Get the appropriate KV store and conversion function for a type.
        
        Args:
            kvtype: Type marker ($ for string, # for int, % for float, None for default)
            incident: Incident containing the KV stores
        
        Returns:
            (kv_store_dict, conversion_function)
        """
        if kvtype == KVParser.TYPE_INTEGER:
            return incident.kv_integers, int
        elif kvtype == KVParser.TYPE_FLOAT:
            return incident.kv_floats, float
        else:  # STRING or None - default to string
            return incident.kv_strings, str
    
    def _apply_kv_changes_with_validation(
        self,
        incident: Incident,
        kv_single: List[str],
        kv_multi: List[str],
        allow_validation_editor: bool,
        processor_fn: callable,
    ) -> tuple[Incident, bool]:
        """
        Apply KV changes with validation retry loop.
        
        This method handles the common pattern of:
        1. Parsing KV lists
        2. Processing them via a callback
        3. Handling validation errors with editor retry
        4. Managing the already_edited_in_validation flag
        
        Args:
            incident: Incident to modify
            kv_single: List of single-value KV strings
            kv_multi: List of multi-value KV strings
            allow_validation_editor: Whether to offer editor on validation failure
            processor_fn: Callback to process the parsed KV entries.
                         Signature: (incident, parsed_single, parsed_multi) -> None
        
        Returns:
            (updated_incident, already_edited_in_validation)
        
        Raises:
            ValueError: If validation fails and user abandons
            RuntimeError: If validation fails and user abandons (from callback)
        """
        parsed_single = KVParser.parse_kv_list(kv_single) if kv_single else []
        parsed_multi = KVParser.parse_kv_list(kv_multi) if kv_multi else []
        already_edited_in_validation = False
        
        while True:
            try:
                # Call processor function (different for update vs create)
                processor_fn(incident, parsed_single, parsed_multi)
                break
                
            except ValueError as e:
                # Validation failed - offer to edit
                corrected = self._handle_validation_error(incident, e, allow_validation_editor)
                
                if corrected:
                    # User edited - validate the edited incident
                    incident = corrected
                    already_edited_in_validation = True
                    
                    try:
                        # Validate all fields in edited incident
                        self._validate_incident_fields(incident)
                        # Validation passed - clear CLI KV so we don't re-apply
                        parsed_single = []
                        parsed_multi = []
                        break
                        
                    except ValueError as e2:
                        # Editor result still invalid - show error and loop
                        print(f"\nValidation error in edited record: {e2}", file=sys.stderr)
                        # Clear parsed KV so we only validate the edited incident on retry
                        parsed_single = []
                        parsed_multi = []
                        continue
                else:
                    # User abandoned - let the caller handle this
                    raise
        
        return incident, already_edited_in_validation
    
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

    def _validate_and_store_kv_single(
        self,
        key: str,
        kvtype: Optional[str],
        value: Any,
        incident: Incident,
    ) -> None:
        """
        Validate and store a single-value KV pair (replaces existing values).
        
        Validates that we're not trying to replace a multi-value field.
        If key is special (config-defined), validates based on config.
        Otherwise stores with provided type hint (or as string if no hint).
        
        Args:
            key: Field name
            kvtype: Type hint from KVParser ($ for string, # for int, % for float, None for untyped)
            value: Value to store
            incident: Incident to store in
            
        Raises:
            ValueError: If attempting to use single-value operator on existing multi-value field
        """
        # Check if field already has multiple values (non-special fields only)
        field = self.project_config.get_special_field(key)
        
        if not field:  # Not a special field
            # Check existing values
            existing_values = None
            if key in incident.kv_strings:
                existing_values = incident.kv_strings[key]
            elif key in incident.kv_integers:
                existing_values = incident.kv_integers[key]
            elif key in incident.kv_floats:
                existing_values = incident.kv_floats[key]
            
            if existing_values and len(existing_values) > 1:
                # Determine the type for the error message
                if kvtype == KVParser.TYPE_STRING or kvtype is None:
                    flag_hint = "--text-multi/--tm"
                elif kvtype == KVParser.TYPE_INTEGER:
                    flag_hint = "--number-multi/--nm"
                elif kvtype == KVParser.TYPE_FLOAT:
                    flag_hint = "--decimal-multi/--dm"
                else:
                    flag_hint = "--kmv (legacy)"
                
                raise ValueError(
                    f"Cannot use single-value operator on multi-value field '{key}' "
                    f"(current values: {existing_values}). Use {flag_hint} instead."
                )
        
        # Proceed with validation and storage (replaces all existing values)
        self._validate_and_store_kv_impl(key, kvtype, value, incident, replace=True)

    def _validate_and_store_kv_multi(
        self,
        key: str,
        kvtype: Optional[str],
        value: Any,
        incident: Incident,
    ) -> None:
        """
        Validate and store a multi-value KV pair (appends to existing values).
        
        If key is special (config-defined), validates based on config.
        Otherwise stores with provided type hint (or as string if no hint).
        
        Args:
            key: Field name
            kvtype: Type hint from KVParser ($ for string, # for int, % for float, None for untyped)
            value: Value to store
            incident: Incident to store in
        """
        # For multi-value, we append rather than replace
        self._validate_and_store_kv_impl(key, kvtype, value, incident, replace=False)

    def _validate_and_store_kv_impl(
        self,
        key: str,
        kvtype: Optional[str],
        value: Any,
        incident: Incident,
        replace: bool = True,
    ) -> None:
        """
        Internal implementation for validating and storing KV pairs.
        
        Args:
            key: Field name
            kvtype: Type hint
            value: Value to store
            incident: Incident to store in
            replace: If True, replace existing values; if False, append
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
            else:  # multi
                # Validate each value
                values_to_validate = [value] if not isinstance(value, list) else value
                for v in values_to_validate:
                    is_valid, error = self.project_config.validate_field(key, v)
                    if not is_valid:
                        raise ValueError(error)
            
            # Store with config-defined type
            if field.value_type == "string":
                if field.field_type == "single":
                    incident.kv_strings[key] = [value]
                else:  # multi
                    if not isinstance(value, list):
                        value = [value]
                    if replace or key not in incident.kv_strings:
                        incident.kv_strings[key] = value
                    else:
                        incident.kv_strings[key].extend(value)
            elif field.value_type == "integer":
                if field.field_type == "single":
                    incident.kv_integers[key] = [int(value)]
                else:  # multi
                    if not isinstance(value, list):
                        value = [value]
                    int_values = [int(v) for v in value]
                    if replace or key not in incident.kv_integers:
                        incident.kv_integers[key] = int_values
                    else:
                        incident.kv_integers[key].extend(int_values)
            elif field.value_type == "float":
                if field.field_type == "single":
                    incident.kv_floats[key] = [float(value)]
                else:  # multi
                    if not isinstance(value, list):
                        value = [value]
                    float_values = [float(v) for v in value]
                    if replace or key not in incident.kv_floats:
                        incident.kv_floats[key] = float_values
                    else:
                        incident.kv_floats[key].extend(float_values)
        else:
            # Non-special field - use type hint
            kv_store, converter = self._get_kv_store_for_type(kvtype, incident)
            
            if replace or key not in kv_store:
                # Replace mode or new key
                if isinstance(value, list):
                    kv_store[key] = [converter(v) for v in value]
                else:
                    kv_store[key] = [converter(value)] if value is not None else []
            else:
                # Append mode
                if isinstance(value, list):
                    kv_store[key].extend([converter(v) for v in value])
                else:
                    kv_store[key].append(converter(value))

    def _create_incident_with_yaml(
        self,
        initial_incident: Incident,
    ) -> Optional[Incident]:
        """
        Launch editor with incident template in yaml frontmatter format.
        
        Used when creating new records. Similar to _edit_incident_with_yaml but
        for new records that don't exist yet.
        
        Flow:
        1. Filter out non-editable special fields
        2. Write template to temp file using to_markdown()
        3. Launch editor
        4. Read back using from_markdown()
        5. Handle parsing errors with retry logic
        6. Return new incident or None if cancelled
        
        Args:
            initial_incident: Template incident with CLI args applied
            
        Returns:
            Edited incident ready to save, or None if cancelled
        """
        import tempfile
        import os
        
        while True:
            # Prepare incident for editing (filter non-editable fields)
            editable_incident = self._prepare_incident_for_editing(initial_incident)
            
            # Generate markdown with yaml frontmatter
            markdown_content = editable_incident.to_markdown(self.project_config)
            
            # Create temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.md',
                delete=False,
                encoding='utf-8',
            ) as tmp_file:
                tmp_file.write(markdown_content)
                tmp_path = tmp_file.name
            
            try:
                # Launch editor
                editor_result = EditorConfig.launch_editor(
                    initial_content=markdown_content,
                )
                
                # User cancelled in editor
                if editor_result is None or editor_result.strip() == markdown_content.strip():
                    os.unlink(tmp_path)
                    return None
                
                # Try to parse the edited content
                try:
                    edited_incident = Incident.from_markdown(
                        editor_result,
                        initial_incident.id,
                        self.project_config,
                    )
                    
                    # Success!
                    os.unlink(tmp_path)
                    return edited_incident
                    
                except Exception as parse_error:
                    # Parsing failed - ask user what to do
                    print(f"\n{'='*70}", file=sys.stderr)
                    print(f"ERROR: Failed to parse edited markdown", file=sys.stderr)
                    print(f"{'='*70}", file=sys.stderr)
                    print(f"{str(parse_error)}", file=sys.stderr)
                    print(f"{'='*70}\n", file=sys.stderr)
                    
                    print("Options:", file=sys.stderr)
                    print("  [r] Retry - reopen editor with your changes", file=sys.stderr)
                    print("  [f] Fresh - restart with template", file=sys.stderr)
                    print("  [c] Cancel - abort creation", file=sys.stderr)
                    
                    choice = input("\nChoice (r/f/c): ").strip().lower()
                    
                    if choice == 'c':
                        # Cancel
                        os.unlink(tmp_path)
                        return None
                    elif choice == 'f':
                        # Start fresh - reset to initial template
                        continue
                    else:
                        # Retry with user's edits (default)
                        # Try to preserve at least the content
                        try:
                            if '+++' in editor_result:
                                parts = editor_result.split('+++', 2)
                                if len(parts) >= 3:
                                    initial_incident.content = parts[2].strip()
                        except:
                            pass
                        continue
                        
            except Exception as e:
                # Editor launch failed or other unexpected error
                print(f"Error during editing: {e}", file=sys.stderr)
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return None
     
    def _format_incident_update(self, id: str) -> str:
        """Format initial update message from all KV data."""

        incident = self.storage.load_incident(id, self.project_config)
        lines = ["## Record Data"]
        lines.append("")

        # Add description if present
        if incident.content:
            lines.append("### Content")
            lines.append("")
            lines.append(incident.content)
            lines.append("")
            lines.append("---")
            lines.append("")
        
        # System fields to skip
        skip_fields = {}
        
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

        lines.append("\n\n")

        return "\n".join(lines)

    def _prepare_incident_for_editing(
        self,
        incident: Incident,
    ) -> Incident:
        """
        Prepare incident for yaml editing by filtering out non-editable special fields.
        
        Creates a copy of the incident with only editable fields in the KV stores.
        Non-editable special fields will be preserved from the original and restored
        after editing.
        
        Args:
            incident: Original incident to prepare
            
        Returns:
            New incident object with non-editable fields removed
        """
        # Create a copy of the incident
        editable_incident = Incident(id=incident.id)
        editable_incident.content = incident.content
        
        # Get special fields configuration
        special_fields = self.project_config.get_special_fields()
        non_editable_fields = {
            name for name, field_def in special_fields.items()
            if not field_def.editable
        }

        # Copy only editable string fields
        for key, values in incident.kv_strings.items():
            base_key = self._strip_type_suffix(key)  # FIXED: Strip suffix before checking
            if base_key not in non_editable_fields:
                editable_incident.kv_strings[key] = values.copy()
        
        # Copy only editable integer fields
        for key, values in incident.kv_integers.items():
            base_key = self._strip_type_suffix(key)  # FIXED: Strip suffix before checking
            if base_key not in non_editable_fields:
                editable_incident.kv_integers[key] = values.copy()
        
        # Copy only editable float fields
        for key, values in incident.kv_floats.items():
            base_key = self._strip_type_suffix(key)  # FIXED: Strip suffix before checking
            if base_key not in non_editable_fields:
                editable_incident.kv_floats[key] = values.copy()
        
        return editable_incident
        
    def _restore_non_editable_fields(
        self,
        original_incident: Incident,
        edited_incident: Incident,
    ) -> None:
        """
        Restore non-editable special fields from original incident to edited incident.
        
        Modifies edited_incident in-place by copying non-editable fields from
        original_incident.
        
        Args:
            original_incident: Original incident with all fields
            edited_incident: Edited incident to restore fields to
        """
        special_fields = self.project_config.get_special_fields()
        non_editable_fields = {
            name for name, field_def in special_fields.items()
            if not field_def.editable
        }
        
        # Restore non-editable string fields
        for key in original_incident.kv_strings.keys():
            base_key = self._strip_type_suffix(key)  # FIXED: Strip suffix before checking
            if base_key in non_editable_fields:
                edited_incident.kv_strings[key] = original_incident.kv_strings[key].copy()
        
        # Restore non-editable integer fields
        for key in original_incident.kv_integers.keys():
            base_key = self._strip_type_suffix(key)  # FIXED: Strip suffix before checking
            if base_key in non_editable_fields:
                edited_incident.kv_integers[key] = original_incident.kv_integers[key].copy()
        
        # Restore non-editable float fields
        for key in original_incident.kv_floats.keys():
            base_key = self._strip_type_suffix(key)  # FIXED: Strip suffix before checking
            if base_key in non_editable_fields:
                edited_incident.kv_floats[key] = original_incident.kv_floats[key].copy()
       
    def update_incident_info(
        self,
        incident_id: str,
        kv_single: List[str],
        kv_multi: List[str],
        description: Optional[str] = None,
        use_stdin: bool = False,
        use_editor: bool = False,
        use_yaml_editor: bool = True,
        metadata_only: bool = False,
        allow_validation_editor: bool = True,
    ) -> bool:
        """
        Update incident fields from KV list and/or description.
        
        When use_editor=True and use_yaml_editor=True (default), presents the full
        incident with yaml frontmatter for editing. Non-editable special fields are
        filtered out during editing and restored afterwards.
    
        Args:
            incident_id: Incident ID
            kv_single: List of single-value KV strings to update/remove (replaces)
            kv_multi: List of multi-value KV strings to update/remove (appends)
            description: Optional new description
            use_stdin: Read description from STDIN
            use_editor: Launch editor for description
            use_yaml_editor: If True with use_editor, edit full record with yaml (default)
    
        Example:
            manager.update_incident_info(
                incident_id,
                kv_single=["status$resolved"],
                kv_multi=["assignees$alice"],
                description="Fixed the issue"
            )
        """
        incident = self.storage.load_incident(incident_id, self.project_config)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
    
        author = self.effective_user["handle"]
        now = self._generate_timestamp()
    
        updated_fields = []
        previous_content = None
        orig_kv_strings=incident.kv_strings;
        orig_kv_integers=incident.kv_integers;        
        orig_kv_floats=incident.kv_floats;
        
        # Define processor for update operations
        def process_update_kv(inc, parsed_single, parsed_multi):
            # Process single-value KV (replaces)
            for key, kvtype, op, value in parsed_single:
                if op == '-':
                    # Removal
                    self._remove_kv(inc, key)
                    updated_fields.append(f"removed {key}")
                else:
                    # Update
                    updated_fields.append(f"Set {key}: {value}")
                    self._validate_and_store_kv_single(key, kvtype, value, inc)
            
            # Process multi-value KV (appends)
            for key, kvtype, op, value in parsed_multi:
                if op == '-':
                    # Removal for multi-value
                    self._remove_kv(inc, key, value)
                    updated_fields.append(f"Removed {key}: {value}")
                else:
                    updated_fields.append(f"Add {key}: {value}")
                    self._validate_and_store_kv_multi(key, kvtype, value, inc)
        
        # Apply KV changes with validation retry loop
        try:
            incident, already_edited_in_validation = self._apply_kv_changes_with_validation(
                incident,
                kv_single,
                kv_multi,
                allow_validation_editor,
                process_update_kv,
            )
            if already_edited_in_validation:
                updated_fields = ["full record (edited to fix validation)"]
        except ValueError:
            # User abandoned validation
            return False
                
        # Handle description/full record updates
        if (not metadata_only) and (description or use_stdin or use_editor):
            # Save previous content before updating
            if incident.content:
                previous_content = incident.content
            else:
                previous_content = None
            
            # Determine how to get new content
            final_description = None
            
            # Skip editor if user already edited during validation
            if already_edited_in_validation:
                # User already edited the full record during validation error handling
                # No need to open editor again - the incident is already updated
                pass
            elif use_editor and use_yaml_editor:
                # NEW BEHAVIOR: Edit full record with yaml frontmatter
                while True:  # ← NEW: Validation loop
                    final_incident = self._edit_incident_with_yaml(incident)
                    
                    if not final_incident:
                        # User cancelled
                        return False
                    
                    # NEW: Validate the edited incident
                    try:
                        self._validate_incident_fields(final_incident)
                        # Validation passed - accept it
                        incident = final_incident
                        # updated_fields.append("full record (yaml edit)")
                        break
                        
                    except ValueError as e:
                        # Validation failed - ask user
                        print(f"\n{'='*70}", file=sys.stderr)
                        print(f"VALIDATION ERROR in edited record", file=sys.stderr)
                        print(f"{'='*70}", file=sys.stderr)
                        print(f"{str(e)}", file=sys.stderr)
                        print(f"{'='*70}\n", file=sys.stderr)
                        
                        print("Options:", file=sys.stderr)
                        print("  [e] Edit - reopen editor to correct the error", file=sys.stderr)
                        print("  [a] Abandon - cancel this update", file=sys.stderr)
                        
                        choice = input("\nChoice (e/a): ").strip().lower()
                        
                        if choice != 'e':
                            # Abandon
                            return False
                        
                        # Loop back and reopen editor with the invalid incident
                        incident = final_incident
                        continue                    
            elif description:
                final_description = description
            elif use_stdin and StdinHandler.has_stdin_data():
                final_description = StdinHandler.read_stdin_with_timeout(timeout=2.0)
            elif use_editor:
                # OLD BEHAVIOR (when use_yaml_editor=False): Edit description only
                final_description = EditorConfig.launch_editor(
                    initial_content=previous_content or "",
                )
            
            if final_description is not None:
                incident.content = final_description
                updated_fields.append("description")
    
        # Update timestamp
        incident.kv_strings['updated_at'] = [now]
    
        # Save and reindex
        self.storage.save_incident(incident, self.project_config)
        self.index_db.index_incident(incident, self.project_config)
        self.index_db.index_kv_data(incident)
    
        update_msg = ""
            
        # Append previous content to update message if it was changed
        if previous_content and incident.content != previous_content:
            update_msg += f"\n\n## Previous Content\n\n{previous_content}"
        # Log update

        if updated_fields:
            update_msg += f"\n\n## Updated Fields: \n{'\n * '.join(updated_fields)}"
            update_msg += f"\n\n"

        update_msg += f"\n\n## Previous Key/Vals\n"
        
        # System fields to skip
        skip_fields = {}
        
        # Format all string KV that isn't in skip list
        for key, values in orig_kv_strings.items():
            if key not in skip_fields and values:
                values_str = ', '.join(str(v) for v in values)
                update_msg += f"{key}: {values_str}\n"
        
        # Format all integer KV
        for key, values in orig_kv_integers.items():
            if values:
                values_str = ', '.join(str(v) for v in values)
                update_msg += f"{key}: {values_str}\n"
        
        # Format all float KV
        for key, values in orig_kv_floats.items():
            if values:
                values_str = ', '.join(str(v) for v in values)
                update_msg += f"{key}: {values_str}\n"

        
        update_id = IDGenerator.generate_update_id()
        incident_update = IncidentUpdate(
            id=update_id,
            incident_id=incident_id,
            timestamp=now,
            author=author,
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
                
    def _edit_incident_with_yaml(
        self,
        incident: Incident,
    ) -> Optional[Incident]:
        """
        Launch editor with full incident in yaml frontmatter format.
        
        Flow:
        1. Filter out non-editable special fields
        2. Write to temp file using to_markdown()
        3. Launch editor
        4. Read back using from_markdown()
        5. Handle parsing errors with retry logic
        6. Restore non-editable fields from original
        7. Return edited incident or None if cancelled
        
        Args:
            incident: Incident to edit (with CLI updates already applied)
            
        Returns:
            Edited incident with non-editable fields restored, or None if cancelled
        """
        import tempfile
        import os
        
        # Keep original for field restoration
        original_incident = self.storage.load_incident(incident.id, self.project_config)
        
        while True:
            # Prepare incident for editing (filter non-editable fields)
            editable_incident = self._prepare_incident_for_editing(incident)
            
            # Generate markdown with yaml frontmatter
            markdown_content = editable_incident.to_markdown(self.project_config)
            
            # Create temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.md',
                delete=False,
                encoding='utf-8',
            ) as tmp_file:
                tmp_file.write(markdown_content)
                tmp_path = tmp_file.name
            
            try:
                # Launch editor
                editor_result = EditorConfig.launch_editor(
                    initial_content=markdown_content,
                )
                
                # User cancelled in editor
                if editor_result is None or editor_result.strip() == markdown_content.strip():
                    os.unlink(tmp_path)
                    return None
                
                # Try to parse the edited content
                try:
                    edited_incident = Incident.from_markdown(
                        editor_result,
                        incident.id,
                        self.project_config,
                    )
                    
                    # Restore non-editable fields
                    self._restore_non_editable_fields(original_incident, edited_incident)
                    
                    # Success!
                    os.unlink(tmp_path)
                    return edited_incident
                    
                except Exception as parse_error:
                    # Parsing failed - ask user what to do
                    print(f"\n{'='*70}", file=sys.stderr)
                    print(f"ERROR: Failed to parse edited markdown", file=sys.stderr)
                    print(f"{'='*70}", file=sys.stderr)
                    print(f"{str(parse_error)}", file=sys.stderr)
                    print(f"{'='*70}\n", file=sys.stderr)
                    
                    print("Options:", file=sys.stderr)
                    print("  [r] Retry - reopen editor with your changes", file=sys.stderr)
                    print("  [f] Fresh - restart with original content", file=sys.stderr)
                    print("  [c] Cancel - abort this update", file=sys.stderr)
                    
                    choice = input("\nChoice (r/f/c): ").strip().lower()
                    
                    if choice == 'c':
                        # Cancel
                        os.unlink(tmp_path)
                        return None
                    elif choice == 'f':
                        # Start fresh with original
                        incident = original_incident
                        continue
                    else:
                        # Retry with user's edits (default)
                        # Update incident with the corrupted content so it shows in next iteration
                        # We need to at least preserve the content part even if KV is broken
                        try:
                            # Try to extract just the content portion
                            if '+++' in editor_result:
                                parts = editor_result.split('+++', 2)
                                if len(parts) >= 3:
                                    incident.content = parts[2].strip()
                        except:
                            pass
                        continue
                        
            except Exception as e:
                # Editor launch failed or other unexpected error
                print(f"Error during editing: {e}", file=sys.stderr)
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return None
                
    def _validate_incident_fields(self, incident: Incident) -> None:
        """
        Validate all KV fields in an incident against special field definitions.
        
        Args:
            incident: Incident to validate
            
        Raises:
            ValueError: If any field fails validation
        """
        special_fields = self.project_config.get_special_fields()
        
        # Validate string fields
        for key, values in incident.kv_strings.items():
            base_key = self._strip_type_suffix(key)
            if base_key in special_fields:
                field = special_fields[base_key]
                if field.accepted_values:
                    for value in values:
                        if value not in field.accepted_values:
                            raise ValueError(
                                f"Invalid value '{value}' for field '{base_key}'. "
                                f"Accepted values: {', '.join(field.accepted_values)}"
                            )
        
        # Validate integer fields
        for key, values in incident.kv_integers.items():
            base_key = self._strip_type_suffix(key)
            if base_key in special_fields:
                field = special_fields[base_key]
                if field.accepted_values:
                    for value in values:
                        if str(value) not in field.accepted_values:
                            raise ValueError(
                                f"Invalid value '{value}' for field '{base_key}'. "
                                f"Accepted values: {', '.join(field.accepted_values)}"
                            )
        
        # Validate float fields
        for key, values in incident.kv_floats.items():
            base_key = self._strip_type_suffix(key)
            if base_key in special_fields:
                field = special_fields[base_key]
                if field.accepted_values:
                    for value in values:
                        if str(value) not in field.accepted_values:
                            raise ValueError(
                                f"Invalid value '{value}' for field '{base_key}'. "
                                f"Accepted values: {', '.join(field.accepted_values)}"
                            )
    def create_incident(
        self,
        kv_single: List[str],
        kv_multi: List[str],
        description: Optional[str] = None,
        use_stdin: bool = False,
        use_editor: bool = False,
        use_yaml_editor: bool = True,
        custom_id: Optional[str] = None,
        template_id: Optional[str] = None,
        allow_validation_editor: bool = True,
    ) -> str:
        """
        Create new incident from KV lists.
        
        When use_editor=True and use_yaml_editor=True (default), presents a 
        template with yaml frontmatter for editing.
        
        Args:
            kv_single: List of single-value KV strings (replaces)
            kv_multi: List of multi-value KV strings (appends)
            description: Optional incident description
            use_stdin: Read description from STDIN
            use_editor: Launch editor
            use_yaml_editor: If True with use_editor, edit full record with yaml (default)
            custom_id: Optional custom incident ID
        
        Example:
            manager.create_incident(
                kv_single=[
                    "title$Database error",
                    "severity$high",
                    "status$open",
                ],
                kv_multi=["tags$bug", "tags$urgent"],
                use_editor=True,
                use_yaml_editor=True,
            )
        """
        author = self.effective_user["handle"]

        # Validate and use custom ID or generate new one
        if custom_id:
            if not IncidentFileStorage.validate_custom_id(custom_id):
                raise ValueError(
                    f"Invalid custom ID '{custom_id}'. "
                    "Only A-Z, a-z, 0-9, underscore (_), and hyphen (-) are allowed."
                )
        
            incident_path = self.storage._get_incident_path(custom_id)
            if incident_path.exists():
                raise ValueError(
                    f"Record with ID '{custom_id}' already exists at {incident_path}"
                )
        
            incident_id = custom_id
        else:
            incident_id = IDGenerator.generate_incident_id()

        now = self._generate_timestamp()
        
        # Load template if specified
        if template_id:
            template = self.storage.load_incident(template_id, self.project_config)
            if not template:
                raise RuntimeError(f"Template record {template_id} not found")
            
            # Start with template's editable data
            incident = Incident(id=incident_id)
            editable_template = self._prepare_incident_for_editing(template)
            incident.kv_strings = editable_template.kv_strings.copy()
            incident.kv_integers = editable_template.kv_integers.copy()
            incident.kv_floats = editable_template.kv_floats.copy()
            incident.content = editable_template.content
        else:
            # Initialize empty incident
            incident = Incident(id=incident_id)
        
        # Define processor for create operations
        def process_create_kv(inc, parsed_single, parsed_multi):
            # Process single-value KV (replaces)
            for key, kvtype, op, value in parsed_single:
                if op == '-':
                    raise ValueError(f"Cannot use removal operator '-' when creating incident")
                self._validate_and_store_kv_single(key, kvtype, value, inc)
            
            # Process multi-value KV (appends)
            for key, kvtype, op, value in parsed_multi:
                if op == '-':
                    raise ValueError(f"Cannot use removal operator '-' when creating incident")
                self._validate_and_store_kv_multi(key, kvtype, value, inc)
        
        # Apply KV changes with validation retry loop
        try:
            incident, already_edited_in_validation = self._apply_kv_changes_with_validation(
                incident,
                kv_single,
                kv_multi,
                allow_validation_editor,
                process_create_kv,
            )
        except (ValueError, RuntimeError):
            # User abandoned - re-raise for CLI handler
            raise RuntimeError("Record creation abandoned due to validation error")
        
        # Add system fields
        self._validate_and_store_kv('created_at', KVParser.TYPE_STRING, now, incident)
        self._validate_and_store_kv('created_by', KVParser.TYPE_STRING, author, incident)
        self._validate_and_store_kv('updated_at', KVParser.TYPE_STRING, now, incident)
        
        # Determine description source
        final_description = None
        final_incident = None
        
        # Skip editor if user already edited during validation
        if already_edited_in_validation:
            # User already edited the full record during validation error handling
            # No need to open editor again - the incident is already complete
            pass
        elif use_editor and use_yaml_editor:
            # NEW BEHAVIOR: Edit full record with yaml
            while True:  # ← NEW: Validation loop
                final_incident = self._create_incident_with_yaml(incident)
                
                if not final_incident:
                    # User cancelled
                    raise RuntimeError("Record creation cancelled")
                
                # Restore system fields (in case user tried to modify them)
                final_incident.kv_strings['created_at'] = [now]
                final_incident.kv_strings['created_by'] = [author]
                final_incident.kv_strings['updated_at'] = [now]
                
                # NEW: Validate the edited incident
                try:
                    self._validate_incident_fields(final_incident)
                    # Validation passed - accept it
                    incident = final_incident
                    break
                    
                except ValueError as e:
                    # Validation failed - ask user
                    print(f"\n{'='*70}", file=sys.stderr)
                    print(f"VALIDATION ERROR in edited record", file=sys.stderr)
                    print(f"{'='*70}", file=sys.stderr)
                    print(f"{str(e)}", file=sys.stderr)
                    print(f"{'='*70}\n", file=sys.stderr)
                    
                    print("Options:", file=sys.stderr)
                    print("  [e] Edit - reopen editor to correct the error", file=sys.stderr)
                    print("  [a] Abandon - cancel this creation", file=sys.stderr)
                    
                    choice = input("\nChoice (e/a): ").strip().lower()
                    
                    if choice != 'e':
                        # Abandon
                        raise RuntimeError("Record creation abandoned due to validation error")
                    
                    # Loop back and reopen editor with the invalid incident
                    incident = final_incident
                    # Restore ID (it might have been changed in editor)
                    incident.id = incident_id
                    continue
            
        elif description:
            final_description = description
        elif use_stdin and StdinHandler.has_stdin_data():
            final_description = StdinHandler.read_stdin_with_timeout(timeout=2.0)
        elif use_editor:
            # OLD BEHAVIOR (when use_yaml_editor=False): Edit description only
            final_description = EditorConfig.launch_editor(
                initial_content=(
                    "# Add your description below\n"
                    "# Lines starting with # are ignored\n"
                    "\n"
                ),
            )
        
        if final_description:
            incident.content = final_description

        # Save to file
        self.storage.save_incident(incident, self.project_config)
        
        # Update index
        self.index_db.index_incident(incident, self.project_config)
        self.index_db.index_kv_data(incident)
        
        # Create initial update
        initial_message = self._format_incident_update(incident.id)
        update_id = IDGenerator.generate_update_id()
        initial_update = IncidentUpdate(
            id=update_id,
            incident_id=incident_id,
            timestamp=now,
            author=author,
            message=initial_message,
        )
        
        self.storage.save_update(incident_id, initial_update)
        self.index_db.index_update(initial_update)
        
        return incident_id
    
    def list_incidents(
        self,
        ksearch_list: Optional[List[str]] = None,
        ksort_list: Optional[List[str]] = None,
        limit: int = 100,
        ids_only: bool = False,
    ) -> Union[List[Incident], List[str]]:
        """
        List incidents with optional KV search and sort.
    
        Args:
            ksearch_list: List of search expressions like ["status=open", "severity>low"]
            ksort_list: List of sort expressions like ["severity", "created_at-"]
            limit: Max results
            ids_only: If True, return only incident IDs as strings
     
        Returns:
            List of Incident objects or list of incident ID strings if ids_only=True
    
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
    
        # Apply limit
        incident_ids = incident_ids[:limit]
    
        # Return IDs only if requested
        if ids_only:
            return incident_ids
    
        # Load incident objects from file storage
        incidents = []
        for incident_id in incident_ids:
             incident = self.storage.load_incident(incident_id, self.project_config)
             if incident:
                 incidents.append(incident)
    
        return incidents

    def _create_update_with_yaml(
        self,
        incident_id: str,
        initial_message: str,
        initial_kv_strings: dict,
        initial_kv_integers: dict,
        initial_kv_floats: dict,
    ) -> Optional[tuple]:
        """
        Launch editor with note template including yaml frontmatter for KV data.
        
        Used when adding notes with KV data. The note can have its own independent
        KV data that doesn't affect the incident.
        
        Flow:
        1. Create a temporary incident-like structure with the KV data
        2. Generate markdown with yaml frontmatter
        3. Launch editor
        4. Parse back
        5. Handle errors with retry
        6. Return (message, kv_strings, kv_integers, kv_floats) or None if cancelled
        
        Args:
            incident_id: Parent incident ID (for context)
            initial_message: Initial note message
            initial_kv_strings: Initial string KV data
            initial_kv_integers: Initial integer KV data
            initial_kv_floats: Initial float KV data
            
        Returns:
            Tuple of (message, kv_strings, kv_integers, kv_floats) or None if cancelled
        """
        import tempfile
        import os
        
        while True:
            # Create a temporary incident to use the to_markdown/from_markdown infrastructure
            temp_incident = Incident(id="temp")
            temp_incident.content = initial_message
            temp_incident.kv_strings = initial_kv_strings.copy()
            temp_incident.kv_integers = initial_kv_integers.copy()
            temp_incident.kv_floats = initial_kv_floats.copy()
            
            # Generate markdown with yaml frontmatter
            markdown_content = temp_incident.to_markdown(self.project_config)
            
            # Create temp file
            with tempfile.NamedTemporaryFile(
                mode='w',
                suffix='.md',
                delete=False,
                encoding='utf-8',
            ) as tmp_file:
                tmp_file.write(markdown_content)
                tmp_path = tmp_file.name
            
            try:
                # Launch editor
                editor_result = EditorConfig.launch_editor(
                    initial_content=markdown_content,
                )
                
                # User cancelled in editor
                if editor_result is None or editor_result.strip() == markdown_content.strip():
                    os.unlink(tmp_path)
                    return None
                
                # Try to parse the edited content
                try:
                    edited_incident = Incident.from_markdown(
                        editor_result,
                        "temp",
                        self.project_config,
                    )
                    
                    # Extract results
                    message = edited_incident.content
                    kv_strings = edited_incident.kv_strings
                    kv_integers = edited_incident.kv_integers
                    kv_floats = edited_incident.kv_floats
                    
                    # Success!
                    os.unlink(tmp_path)
                    return (message, kv_strings, kv_integers, kv_floats)
                    
                except Exception as parse_error:
                    # Parsing failed - ask user what to do
                    print(f"\n{'='*70}", file=sys.stderr)
                    print(f"ERROR: Failed to parse edited markdown", file=sys.stderr)
                    print(f"{'='*70}", file=sys.stderr)
                    print(f"{str(parse_error)}", file=sys.stderr)
                    print(f"{'='*70}\n", file=sys.stderr)
                    
                    print("Options:", file=sys.stderr)
                    print("  [r] Retry - reopen editor with your changes", file=sys.stderr)
                    print("  [f] Fresh - restart with template", file=sys.stderr)
                    print("  [c] Cancel - abort note creation", file=sys.stderr)
                    
                    choice = input("\nChoice (r/f/c): ").strip().lower()
                    
                    if choice == 'c':
                        # Cancel
                        os.unlink(tmp_path)
                        return None
                    elif choice == 'f':
                        # Start fresh
                        continue
                    else:
                        # Retry with user's edits
                        try:
                            if '+++' in editor_result:
                                parts = editor_result.split('+++', 2)
                                if len(parts) >= 3:
                                    initial_message = parts[2].strip()
                        except:
                            pass
                        continue
                        
            except Exception as e:
                # Editor launch failed or other unexpected error
                print(f"Error during editing: {e}", file=sys.stderr)
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return None

    def add_update(
        self,
        incident_id: str,
        message: Optional[str] = None,
        use_stdin: bool = False,
        use_editor: bool = False,
        use_yaml_editor: bool = True,
        kv_single: Optional[List[str]] = None,
        kv_multi: Optional[List[str]] = None,
        template_id: Optional[str] = None,
    ) -> str:
        """
        Add update with optional independent KV data.
        
        When use_editor=True and use_yaml_editor=True (default), presents the
        note with yaml frontmatter for editing KV data.
        
        Args:
            incident_id: Incident ID
            message: Update message
            use_stdin: Read from STDIN
            use_editor: Open editor
            use_yaml_editor: If True with use_editor, edit note with yaml (default)
            kv_single: Single-value KV for UPDATE only (replaces keys)
            kv_multi: Multi-value KV for UPDATE only (adds values)
        
        Returns:
            Update ID
        """
        incident = self.get_incident(incident_id)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
        
        author = self.effective_user["handle"]
        now = self._generate_timestamp()
        
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
 
        # Load template if specified
        if template_id:
            template = self.storage.load_incident(template_id, self.project_config)
            if not template:
                raise RuntimeError(f"Template record {template_id} not found")
            
            # Start with template's editable KV data (CLI KV overrides)
            editable_template = self._prepare_incident_for_editing(template)
            
            # Merge template KV with CLI KV (CLI takes precedence)
            for key, values in editable_template.kv_strings.items():
                if key not in update_kv_strings:
                    update_kv_strings[key] = values.copy()
            
            for key, values in editable_template.kv_integers.items():
                if key not in update_kv_integers:
                    update_kv_integers[key] = values.copy()
            
            for key, values in editable_template.kv_floats.items():
                if key not in update_kv_floats:
                    update_kv_floats[key] = values.copy()
            
            # Use template content if no message provided
            if not message and editable_template.content:
                message = editable_template.content
        
        # Determine message source
        final_message = None        
        if use_editor and use_yaml_editor:
            # NEW BEHAVIOR: Edit note with yaml frontmatter
            initial_message = message or "# Add your note below\n# Lines starting with # are ignored\n\n"
            
            result = self._create_update_with_yaml(
                incident_id,
                initial_message,
                update_kv_strings,
                update_kv_integers,
                update_kv_floats,
            )
            
            if not result:
                # User cancelled
                raise RuntimeError("Note creation cancelled")
            
            final_message, update_kv_strings, update_kv_integers, update_kv_floats = result
            
        elif message:
            final_message = message
        elif use_stdin and StdinHandler.has_stdin_data():
            final_message = StdinHandler.read_stdin_with_timeout(timeout=2.0)
        elif use_editor:
            # OLD BEHAVIOR (when use_yaml_editor=False): Edit message only
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
                "  aver note add <id> --message \"text\"\n"
                "  echo \"text\" | aver note add <id>\n"
                "  aver note add <id>  # opens editor"
            )
        
        # Generate update ID
        update_id = IDGenerator.generate_update_id()
        
        update = IncidentUpdate(
            id=update_id,
            incident_id=incident_id,
            timestamp=now,
            author=author,
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

    def search_updates(
        self,
        ksearch: Optional[List[str]] = None,
        limit: int = 50,
        ids_only: bool = False,
    ) -> Union[List[tuple], List[str]]:
        """
        Search updates by key-value filters.
    
        Args:
            ksearch: List of key-value search expressions for update KV
            limit: Maximum results
            ids_only: If True, return only "incident_id:update_id" strings
    
        Returns:
            List of (update, incident_id, incident_title) tuples, or
            list of "incident_id:update_id" strings if ids_only=True
    
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
        matching_ids = self.index_db.search_kv(
            ksearch_parsed,
            return_updates=True,
            search_updates=True,
        )
    
        if not matching_ids:
            return []
    
        matching_ids = matching_ids[:limit]
    
        # Return IDs only if requested
        if ids_only:
            return [f"{incident_id}:{update.id}" for update, incident_id, _ in matching_ids]
    
        return matching_ids

    def _handle_validation_error(
        self,
        incident: Incident,
        validation_error: ValueError,
        allow_editor: bool = True,
    ) -> Optional[Incident]:
        """
        Handle validation errors with user interaction.
        
        Args:
            incident: The incident that failed validation
            validation_error: The validation error that occurred
            allow_editor: If False, re-raise error immediately (for automation)
            
        Returns:
            Corrected incident from editor, or None if user abandons
            
        Raises:
            ValueError: If allow_editor=False or user chooses to abandon
        """
        if not allow_editor:
            # No editor allowed - re-raise for automation
            raise validation_error
        
        # Interactive mode - offer choices
        print(f"\n{'='*70}", file=sys.stderr)
        print(f"VALIDATION ERROR", file=sys.stderr)
        print(f"{'='*70}", file=sys.stderr)
        print(f"{str(validation_error)}", file=sys.stderr)
        print(f"{'='*70}\n", file=sys.stderr)
        
        print("Options:", file=sys.stderr)
        print("  [e] Edit - open editor to correct the error", file=sys.stderr)
        print("  [a] Abandon - cancel this operation", file=sys.stderr)
        
        choice = input("\nChoice (e/a): ").strip().lower()
        
        if choice != 'e':
            # Abandon - re-raise the error
            raise validation_error
        
        # Launch editor to fix
        print("\nOpening editor to correct validation error...", file=sys.stderr)
        return self._edit_incident_with_yaml(incident)

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
        self._add_common_args(self.parser)
        self.subparsers = self.parser.add_subparsers(dest="command", required=True)

    def _add_common_args(self, parser):
        """Add common database selection arguments."""
        db_group = parser.add_mutually_exclusive_group()
        db_group.add_argument(
            "--location",
            help="Explicit database path (overrides all detection)",
        )
        db_group.add_argument(
            "--use",
            dest="use_alias",
            metavar="ALIAS",
            help="Select database by library alias (defined in user config)",
        )
        db_group.add_argument(
            "--choose",
            action="store_true",
            help="Prompt to choose database if multiple available",
        )
        
        # Git identity resolution flags
        git_id_group = parser.add_mutually_exclusive_group()
        git_id_group.add_argument(
            "--use-git-id",
            action="store_const",
            const=True,
            dest="use_git_id",
            default=None,
            help="Use git user identity instead of aver config identity",
        )
        git_id_group.add_argument(
            "--no-use-git-id",
            action="store_const",
            const=True,
            dest="no_use_git_id",
            default=None,
            help="Use aver config identity even if it differs from git",
        )

    def _add_kv_options(self, parser, include_old_style=True):
        """
        Add key-value options to a parser.
        
        Includes both new intuitive options and legacy options for tech-heads.
        """
        # New intuitive single-value options
        parser.add_argument(
            "--text", "-t",
            action="append",
            dest="text",
            help="Single-value text data: 'key=value' (can use multiple times)",
        )
        parser.add_argument(
            "--number", "-n",
            action="append",
            dest="number",
            help="Single-value numeric data: 'key=123' (can use multiple times)",
        )
        parser.add_argument(
            "--decimal", "-d",
            action="append",
            dest="decimal",
            help="Single-value decimal data: 'key=1.5' (can use multiple times)",
        )
        
        # New intuitive multi-value options
        parser.add_argument(
            "--text-multi", "--tm",
            action="append",
            dest="text_multi",
            help="Multi-value text data: 'key=value' (can use multiple times)",
        )
        parser.add_argument(
            "--number-multi", "--nm",
            action="append",
            dest="number_multi",
            help="Multi-value numeric data: 'key=123' (can use multiple times)",
        )
        parser.add_argument(
            "--decimal-multi", "--dm",
            action="append",
            dest="decimal_multi",
            help="Multi-value decimal data: 'key=1.5' (can use multiple times)",
        )
        
        # Legacy options (for tech-heads)
        if include_old_style:
            parser.add_argument(
                "--kv",
                action="append",
                dest="kv_single",
                help="[Legacy] Single-value KV data: 'key$value', 'key#123', 'key%%1.5'",
            )
            parser.add_argument(
                "--kmv",
                action="append",
                dest="kv_multi",
                help="[Legacy] Multi-value KV data: 'key$value', 'key#123', 'key%%1.5'",
            )

    def _get_manager(self, args) -> IncidentManager:
        """
        Handle database selection and return manager.
        
        Resolves --use alias to an explicit location before constructing the manager.
        """
        interactive = getattr(args, 'choose', False)
        explicit_location = getattr(args, 'location', None)
        use_alias = getattr(args, 'use_alias', None)
        
        # Resolve alias to explicit path
        if use_alias:
            explicit_location = str(DatabaseDiscovery.resolve_alias(use_alias))
        
        return IncidentManager(
            explicit_location=explicit_location,
            interactive=interactive,
        )
    
    def _setup_write_command(self, args) -> tuple[IncidentManager, tuple[List[str], List[str]]]:
        """
        Common setup for write commands (create, update, add_update).
        
        Handles:
        - Manager initialization
        - Git identity checking and override
        - KV list building
        
        Returns:
            (manager, (kv_single, kv_multi))
        """
        manager = self._get_manager(args)
        
        # Check git identity and apply override if needed
        identity_override = self._check_git_identity(args, manager)
        if identity_override:
            manager.set_user_override(identity_override["handle"], identity_override["email"])
        
        # Build KV lists
        kv_lists = self._build_kv_list(manager, args)
        
        return manager, kv_lists

    def _check_git_identity(self, args, manager: IncidentManager):
        """
        Verify that the aver user identity matches the git identity for write operations.
        
        Called before write operations (record new, record update, note add).
        
        If inside a git repo and identities differ:
        - If prefer_git_identity = true (config): return git identity
        - If prefer_git_identity = false (config): return None (use aver config)
        - If --use-git-id flag: return git identity, print notice about prefer_git_identity
        - If --no-use-git-id flag: return None (use aver config)
        - Otherwise: raise RuntimeError with instructions
        
        The caller is responsible for applying the returned identity via
        manager.set_user_override() if non-None.
        
        Returns:
            Dict with 'handle' and 'email' if git identity should be used,
            or None if aver config identity should be used.
        
        Raises:
            RuntimeError: If identities differ and no resolution is provided
        """
        use_git_id = getattr(args, 'use_git_id', None)
        no_use_git_id = getattr(args, 'no_use_git_id', None)
        
        # Get git identity — if not in a git repo, nothing to check
        git_identity = DatabaseDiscovery.get_git_identity()
        if git_identity is None:
            if use_git_id:
                print(
                    "Warning: --use-git-id specified but not in a git repo "
                    "or git identity not configured. Using aver config identity.",
                    file=sys.stderr,
                )
            return None
        
        # Get effective aver identity
        db_path = getattr(manager, 'db_root', None)
        try:
            aver_identity = DatabaseDiscovery.get_effective_user(db_path)
        except RuntimeError:
            # No aver identity configured at all — can't compare
            if use_git_id:
                return git_identity
            return None
        
        # Compare identities
        handle_match = aver_identity["handle"] == git_identity["handle"]
        email_match = aver_identity["email"] == git_identity["email"]
        
        if handle_match and email_match:
            return None
        
        # Identities differ — determine resolution
        
        # Check for persistent prefer_git_identity setting
        prefer_git = DatabaseDiscovery.get_prefer_git_identity(db_path)
        if prefer_git is True:
            return git_identity
        if prefer_git is False:
            return None
        
        # Check for explicit flags
        if use_git_id:
            # Determine the best config hint for the notice
            config = DatabaseDiscovery.get_user_config()
            libraries = config.get("libraries", {})
            matched_alias = None
            if db_path:
                db_path_resolved = Path(db_path).resolve()
                for alias, lib_config in libraries.items():
                    try:
                        if Path(lib_config["path"]).resolve() == db_path_resolved:
                            matched_alias = alias
                            break
                    except Exception:
                        continue
            
            print(
                f"\nNotice: Using git identity: {git_identity['handle']} <{git_identity['email']}>",
                file=sys.stderr,
            )
            print(
                f"  To avoid this flag in the future, add 'prefer_git_identity = true' to your config:",
                file=sys.stderr,
            )
            if matched_alias:
                print(
                    f"\n  Per-library (in ~/.config/aver/user.toml):\n"
                    f"    [libraries.{matched_alias}]\n"
                    f"    prefer_git_identity = true\n",
                    file=sys.stderr,
                )
            else:
                print(
                    f"\n  Global (in ~/.config/aver/user.toml):\n"
                    f"    [user]\n"
                    f"    prefer_git_identity = true\n",
                    file=sys.stderr,
                )
            return git_identity
        
        if no_use_git_id:
            return None
        
        # No flag, no config setting — error out
        mismatch_details = []
        if not handle_match:
            mismatch_details.append(
                f"  handle: aver='{aver_identity['handle']}' vs git='{git_identity['handle']}'"
            )
        if not email_match:
            mismatch_details.append(
                f"  email:  aver='{aver_identity['email']}' vs git='{git_identity['email']}'"
            )
        
        raise RuntimeError(
            f"Identity mismatch between aver config and git:\n"
            + "\n".join(mismatch_details) + "\n\n"
            f"Resolve with one of:\n"
            f"  --use-git-id       Use git identity for this operation\n"
            f"  --no-use-git-id    Use aver config identity for this operation\n\n"
            f"To always resolve this automatically, add to ~/.config/aver/user.toml:\n"
            f"  prefer_git_identity = true    # always use git identity\n"
            f"  prefer_git_identity = false   # always use aver config identity\n"
            f"(under the appropriate [libraries.<alias>] or [user] section)"
        )

    def _parse_and_convert_kv(self, raw_values: List[str], type_marker: str) -> List[str]:
        """
        Parse key=value pairs and convert to internal kv format.
        
        Args:
            raw_values: List of "key=value" strings
            type_marker: "$" for string, "#" for int, "%" for float
        
        Returns:
            List of "key<marker>value" strings
        
        Raises:
            ValueError: If format is invalid
        """
        result = []
        if not raw_values:
            return result
        
        for item in raw_values:
            if "=" not in item:
                raise ValueError(f"Invalid format: {item}. Expected 'key=value'")
            key, value = item.split("=", 1)
            if not key:
                raise ValueError(f"Empty key in: {item}")
            if not value:
                raise ValueError(f"Empty value in: {item}")
            result.append(f"{key}{type_marker}{value}")
        
        return result

    def _build_kv_list(self, manager: IncidentManager, args) -> tuple[List[str], List[str]]:
        """
        Build KV lists from special field arguments and generic KV options.
        
        Processes special fields defined in ProjectConfig, new intuitive options,
        and legacy --kv/--kmv arguments. Prevents mixing special keys with new-style options.
        
        Returns:
            (kv_single_list, kv_multi_list) - Two separate lists for single and multi-value operations
        """
        kv_single = []
        kv_multi = []
        special_fields = manager.project_config.get_special_fields()
        special_field_names = set(special_fields.keys())
        
        # Check if any new-style options were used
        new_style_used = (
            getattr(args, 'text', None) or 
            getattr(args, 'number', None) or 
            getattr(args, 'decimal', None) or
            getattr(args, 'text_multi', None) or
            getattr(args, 'number_multi', None) or
            getattr(args, 'decimal_multi', None)
        )
        
        # If new-style options are used, check for conflicts with special keys
        if new_style_used:
            used_keys = set()
            for opt in [
                getattr(args, 'text', None),
                getattr(args, 'number', None),
                getattr(args, 'decimal', None),
                getattr(args, 'text_multi', None),
                getattr(args, 'number_multi', None),
                getattr(args, 'decimal_multi', None),
            ]:
                if opt:
                    for item in opt:
                        key = item.split("=", 1)[0]
                        used_keys.add(key)
            
            # Check for intersection with special keys
            conflicts = used_keys & special_field_names
            if conflicts:
                raise ValueError(
                    f"Cannot use special keys with new-style options: {', '.join(sorted(conflicts))}. "
                    f"Use special field arguments instead: --{' --'.join(sorted(conflicts))}"
                )
        
        # Process special fields from config
        for field_name, field_def in special_fields.items():
            if hasattr(args, field_name) and getattr(args, field_name) is not None:
                value = getattr(args, field_name)
                
                # Determine type prefix based on field definition
                if field_def.value_type == "integer":
                    type_prefix = "#"
                elif field_def.value_type == "float":
                    type_prefix = "%"
                else:
                    type_prefix = "$"
                
                # Route to single or multi based on field definition
                target_list = kv_single if field_def.field_type == "single" else kv_multi
                
                # Handle single vs multi-value fields
                if isinstance(value, list):
                    for v in value:
                        target_list.append(f"{field_name}{type_prefix}{v}")
                else:
                    target_list.append(f"{field_name}{type_prefix}{value}")
        
        # Process new-style options (with key=value parsing)
        try:
            # Single-value options
            if getattr(args, 'text', None):
                kv_single.extend(self._parse_and_convert_kv(args.text, "$"))
            
            if getattr(args, 'number', None):
                kv_single.extend(self._parse_and_convert_kv(args.number, "#"))
            
            if getattr(args, 'decimal', None):
                kv_single.extend(self._parse_and_convert_kv(args.decimal, "%"))
            
            # Multi-value options
            if getattr(args, 'text_multi', None):
                kv_multi.extend(self._parse_and_convert_kv(args.text_multi, "$"))
            
            if getattr(args, 'number_multi', None):
                kv_multi.extend(self._parse_and_convert_kv(args.number_multi, "#"))
            
            if getattr(args, 'decimal_multi', None):
                kv_multi.extend(self._parse_and_convert_kv(args.decimal_multi, "%"))
        
        except ValueError as e:
            raise RuntimeError(str(e))
        
        # Add legacy single-value KV arguments
        if hasattr(args, 'kv_single') and args.kv_single:
            kv_single.extend(args.kv_single)
        
        # Add legacy multi-value KV arguments
        if hasattr(args, 'kv_multi') and args.kv_multi:
            kv_multi.extend(args.kv_multi)
        
        return kv_single, kv_multi

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
            
            arg_name = f"--{field_name}"
            
            help_text = f"{field_name} ({field_def.field_type}, {field_def.value_type})"
            if field_def.accepted_values:
                help_text += f" - Accepted: {', '.join(field_def.accepted_values)}"

            kwargs = {
                "help": help_text,
                "dest": field_name,
            }
            
            if field_def.field_type == "multi":
                kwargs["nargs"] = "*"
            
            #if field_def.accepted_values:
                #kwargs["choices"] = field_def.accepted_values
            
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

        self._add_kv_options(record_new_parser)

        record_new_parser.add_argument(
            "--description",
            help="Detailed description",
        )
        record_new_parser._special_fields_parser = True
        
        record_new_parser.add_argument(
            "--use-id",
            dest="custom_id",
            help="Use custom record ID (A-Z, a-z, 0-9, _, - only). Must be unique.",
        )

        record_new_parser.add_argument(
            "--no-yaml",
            action="store_true",
            help="Edit description only (without yaml frontmatter)",
        )
        
        record_new_parser.add_argument(
            "--template",
            metavar="RECORD_ID",
            help="Use existing record as template (editor mode only)",
        )

        record_new_parser.add_argument(
            "--no-validation-editor",
            action="store_true",
            help="Don't launch editor on validation errors (for automation)",
        )

        self.record_new_parser = record_new_parser
        
        # record view
        record_view_parser = record_subparsers.add_parser(
            "view",
            help="View a specific record's details",
        )

        record_view_parser.add_argument("record_id", help="Record ID")
        
        # record list
        record_list_parser = record_subparsers.add_parser(
            "list",
            help="List/search records with filters",
        )

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
        record_list_parser.add_argument(
            "--ids-only",
            action="store_true",
            help="Show only IDs in simple list format",
        )

        # record update
        record_update_parser = record_subparsers.add_parser(
            "update",
            help="Update record status and metadata",
        )

        record_update_parser.add_argument("record_id", help="Record ID")
        self._add_kv_options(record_update_parser)
        
        # NEW: Add --no-yaml flag
        record_update_parser.add_argument(
            "--no-yaml",
            action="store_true",
            help="Edit description only (without yaml frontmatter)",
        )
        
        record_update_parser.add_argument(
            "--no-validation-editor",
            action="store_true",
            help="Don't launch editor on validation errors (for automation)",
        )
        
        record_update_parser.add_argument(
            "--metadata-only",
            action="store_true",
            help="Update only metadata fields, skip content changes",
        )

        self.record_update_parser = record_update_parser

        
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

        note_add_parser.add_argument("record_id", help="Record ID")
        note_add_parser.add_argument(
            "--message",
            help="Note message text",
        )
        
        note_add_parser.add_argument(
            "--no-yaml",
            action="store_true",
            help="Edit message only (without yaml frontmatter)",
        )
        note_add_parser.add_argument(
            "--template",
            metavar="RECORD_ID",
            help="Use existing record as template (editor mode only)",
        )        
        self._add_kv_options(note_add_parser, include_old_style=True)
        
        # note list
        note_list_parser = note_subparsers.add_parser(
            "list",
            help="View all notes for a specific record",
        )

        note_list_parser.add_argument("record_id", help="Record ID")
        
        # note search
        note_search_parser = note_subparsers.add_parser(
            "search",
            help="Search notes by KV data",
        )

        note_search_parser.add_argument(
            "--ksearch",
            action="append",
            dest="ksearch",
            required=True,
            help="Search by note KV: 'key=value' (required, can use multiple times)",
        )
        note_search_parser.add_argument(
            "--ids-only",
            action="store_true",
            help="Show only incident_id:update_id pairs",
        )
        note_search_parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum records to show",
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
        
        # admin config set-user
        set_user_parser = config_subparsers.add_parser(
            "set-user",
            help="Set user identity (global or per-library)",
            description=(
                "Set user identity. Without --library, sets the global fallback identity.\n"
                "With --library <alias>, sets identity for a specific library.\n\n"
                "Examples:\n"
                "  aver admin config set-user --handle alice --email alice@example.com\n"
                "  aver admin config set-user --library myproject --handle alice-work --email alice@work.com"
            ),
        )
        set_user_parser.add_argument("--handle", required=True, help="User handle")
        set_user_parser.add_argument("--email", required=True, help="User email")
        set_user_parser.add_argument(
            "--library",
            dest="set_user_library",
            metavar="ALIAS",
            help="Set identity for a specific library alias (omit for global)",
        )
        
        # admin config add-alias
        add_alias_parser = config_subparsers.add_parser(
            "add-alias",
            help="Add or update a library alias",
            description=(
                "Register a library alias for convenient access.\n\n"
                "Examples:\n"
                "  aver admin config add-alias --alias myproject --path /home/alice/projects/myproject/.aver\n"
                "  aver admin config add-alias --alias myproject --path .  # uses current directory"
            ),
        )
        add_alias_parser.add_argument(
            "--alias", required=True,
            help="Short alias name for the library",
        )
        add_alias_parser.add_argument(
            "--path", required=True,
            help="Filesystem path to the .aver database directory",
        )
        
        # admin config list-aliases
        list_aliases_parser = config_subparsers.add_parser(
            "list-aliases",
            help="Show all configured library aliases",
        )
        
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
        parsed,remaining = self.parser.parse_known_args(args)

        try:
            if parsed.command == "record":
                if parsed.record_command == "new":
                    manager = self._get_manager(parsed)
                    self._add_special_field_args(self.record_new_parser, manager)
                    parsed = self.parser.parse_args(args)
                    self._cmd_create(parsed)
                elif parsed.record_command == "view":
                    self._cmd_view(parsed)
                elif parsed.record_command == "list":
                    self._cmd_list(parsed)
                elif parsed.record_command == "update":
                    manager = self._get_manager(args)
                    self._add_special_field_args(self.record_update_parser, manager)
                    parsed = self.parser.parse_args(args)
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

    # ====================================================================
    # DEFAULT TEMPLATES
    # ====================================================================
    
    TEMPLATE_VIEW = Template("""\
────────────────────────────────────────────────────────────────────────────────
Record: $id
────────────────────────────────────────────────────────────────────────────────

$incident_content

─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
$kv_all
================================================================================
""")

    TEMPLATE_LIST_ITEM = Template("""\
$id | $title | $updated_at
""")

    TEMPLATE_LIST_UPDATES_ITEM = Template("""\
────────────────────────────────────────────────────────────────────────────────
Note $note_number: [$timestamp] by $author
────────────────────────────────────────────────────────────────────────────────
$message

$kv_all
""")

    TEMPLATE_SEARCH_UPDATES_HEADER = Template("""\
Found $count matching notes:

""")

    TEMPLATE_SEARCH_UPDATES_ITEM = Template("""\
################################################################################
Record: $incident_id
################################################################################
$incident_content

─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
$incident_kv
────────────────────────────────────────────────────────────────────────────────
Note: $update_id
─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
$update_content

─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
$update_kv
""")

        # ====================================================================
        # Command Helpers
        # ====================================================================

    def _flatten_kv_data(self, kv_strings: dict, kv_integers: dict, kv_floats: dict) -> dict:
        """
        Flatten kv_strings, kv_integers, and kv_floats into a single dictionary.
        
        Multi-value fields are joined with commas. Single-value fields are unwrapped.
        
        Args:
            kv_strings: Dictionary of string key-value pairs
            kv_integers: Dictionary of integer key-value pairs
            kv_floats: Dictionary of float key-value pairs
        
        Returns:
            Flattened dictionary safe for Template.safe_substitute()
        """
        kv_all = {}
        
        # Process strings
        if kv_strings:
            for key, values in kv_strings.items():
                if isinstance(values, list):
                    kv_all[key] = ', '.join(str(v) for v in values)
                else:
                    kv_all[key] = str(values)
        
        # Process integers
        if kv_integers:
            for key, values in kv_integers.items():
                if isinstance(values, list):
                    kv_all[key] = ', '.join(str(v) for v in values)
                else:
                    kv_all[key] = str(values)
        
        # Process floats
        if kv_floats:
            for key, values in kv_floats.items():
                if isinstance(values, list):
                    kv_all[key] = ', '.join(str(v) for v in values)
                else:
                    kv_all[key] = str(values)
        
        return kv_all

    def _format_kv_section(self, kv_all: dict) -> str:
        """
        Format flattened KV data into a readable section.
        
        Args:
            kv_all: Flattened KV dictionary
        
        Returns:
            Formatted string with key-value pairs
        """
        if not kv_all:
            return ""
        
        lines = []
        for key, value in sorted(kv_all.items()):
            lines.append(f"  {key}: {value}")
        
        return "Fields:\n" + "\n".join(lines)



        # ====================================================================
        # Command Functions
        # ====================================================================


    def _cmd_init(self, args):
        """Initialize database."""
        if args.location:
            db_root = Path(args.location)
        else:
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
            self._cmd_config_set_user(args)
        elif args.config_command == "add-alias":
            self._cmd_config_add_alias(args)
        elif args.config_command == "list-aliases":
            self._cmd_config_list_aliases(args)
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

    def _cmd_config_set_user(self, args):
        """
        Set user identity — global or per-library.
        
        Without --library: sets/updates [user] section (global fallback).
        With --library <alias>: sets/updates handle and email within [libraries.<alias>].
        The alias must already exist (use add-alias first).
        """
        target_library = getattr(args, 'set_user_library', None)
        config = DatabaseDiscovery.get_user_config()
        
        if target_library:
            # Per-library identity
            if "libraries" not in config:
                config["libraries"] = {}
            
            if target_library not in config["libraries"]:
                print(
                    f"Error: Library alias '{target_library}' not found.\n"
                    f"Add it first with: aver admin config add-alias --alias {target_library} --path /path/to/.aver",
                    file=sys.stderr,
                )
                sys.exit(1)
            
            # Update the library entry (preserve existing path and other fields)
            config["libraries"][target_library]["handle"] = args.handle
            config["libraries"][target_library]["email"] = args.email
            
            DatabaseDiscovery.set_user_config(config)
            print(f"✓ User configured for library '{target_library}': {args.handle} <{args.email}>")
        else:
            # Global identity — preserve existing [user] fields (e.g. prefer_git_identity)
            if "user" not in config:
                config["user"] = {}
            config["user"]["handle"] = args.handle
            config["user"]["email"] = args.email
            
            DatabaseDiscovery.set_user_config(config)
            print(f"✓ Global user configured: {args.handle} <{args.email}>")

    def _cmd_config_add_alias(self, args):
        """
        Add or update a library alias.
        
        Resolves the path to an absolute path. If path is "." or a relative path,
        it's resolved relative to CWD. Validates the path exists and looks like
        an aver database (or at least a directory).
        """
        alias = args.alias
        raw_path = args.path
        
        # Resolve the path
        resolved_path = Path(raw_path).resolve()
        
        # Basic validation
        if not resolved_path.exists():
            print(
                f"Warning: Path does not exist yet: {resolved_path}\n"
                f"The alias will be saved, but it won't be usable until the path exists.",
                file=sys.stderr,
            )
        elif not resolved_path.is_dir():
            print(f"Error: Path is not a directory: {resolved_path}", file=sys.stderr)
            sys.exit(1)
        
        config = DatabaseDiscovery.get_user_config()
        
        if "libraries" not in config:
            config["libraries"] = {}
        
        is_update = alias in config["libraries"]
        
        if is_update:
            # Preserve existing per-library identity fields
            config["libraries"][alias]["path"] = str(resolved_path)
        else:
            config["libraries"][alias] = {
                "path": str(resolved_path),
            }
        
        DatabaseDiscovery.set_user_config(config)
        
        action = "Updated" if is_update else "Added"
        print(f"✓ {action} library alias: {alias} → {resolved_path}")

    def _cmd_config_list_aliases(self, args):
        """Show all configured library aliases with their details."""
        aliases = DatabaseDiscovery.get_all_aliases()
        
        if not aliases:
            print("No library aliases configured.")
            print(f"\nAdd one with: aver admin config add-alias --alias <name> --path /path/to/.aver")
            return
        
        print("\n" + "=" * 70)
        print("Library Aliases")
        print("=" * 70)
        
        for alias, lib_config in sorted(aliases.items()):
            lib_path = Path(lib_config["path"])
            exists = lib_path.exists()
            status = "✓" if exists else "✗ (missing)"
            
            print(f"\n  {alias}")
            print(f"    Path:   {lib_config['path']}  {status}")
            
            if "handle" in lib_config or "email" in lib_config:
                handle = lib_config.get("handle", "(global fallback)")
                email = lib_config.get("email", "(global fallback)")
                print(f"    User:   {handle} <{email}>")
            else:
                print(f"    User:   (uses global fallback)")
            
            if "prefer_git_identity" in lib_config:
                pref = lib_config["prefer_git_identity"]
                print(f"    Git ID: {'preferred' if pref else 'not preferred'}")
        
        print("\n" + "=" * 70)
        print(f"  {len(aliases)} alias(es) configured")
        print("=" * 70 + "\n")

    def _cmd_create(self, args):
        """Create record."""
        manager, (kv_single, kv_multi) = self._setup_write_command(args)
        
        has_description = args.description is not None
        has_stdin = StdinHandler.has_stdin_data()
        use_editor = not (has_description or has_stdin)
        use_yaml_editor = not getattr(args, 'no_yaml', False)
        template_id = getattr(args, 'template', None)
        allow_validation_editor = not getattr(args, 'no_validation_editor', False)
        
        # Validate template usage
        if template_id and not use_editor:
            print(
                "Error: --template can only be used in editor mode\n"
                "Remove --description flag or stdin input to use editor",
                file=sys.stderr
            )
            sys.exit(1)

        try:
            record_id = manager.create_incident(
                kv_single=kv_single,
                kv_multi=kv_multi,
                description=args.description,
                use_stdin=has_stdin and not has_description,
                use_editor=use_editor,
                use_yaml_editor=use_yaml_editor,
                custom_id=getattr(args, 'custom_id', None),
                template_id=template_id,
                allow_validation_editor=allow_validation_editor,
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

        except ValueError as e:
            # Only happens if allow_validation_editor=False or non-validation ValueError
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except RuntimeError as e:
            # User cancelled
            print(f"{e}", file=sys.stderr)
            sys.exit(1)

    def _cmd_view(self, args):
        """View record details."""
        manager = self._get_manager(args)
        record = manager.get_incident(args.record_id)

        if not record:
            print(f"Error: Record {args.record_id} not found", file=sys.stderr)
            sys.exit(1)

        kv_all = self._flatten_kv_data(record.kv_strings, record.kv_integers, record.kv_floats)
        kv_section = self._format_kv_section(kv_all)
        
        output = self.TEMPLATE_VIEW.safe_substitute(
            id=record.id,
            kv_all=kv_section,
            incident_content=record.content,
        )
        
        print(output)

    def _cmd_list(self, args):
        """List records with KV search and sort."""
        manager = self._get_manager(args)
        
        try:
            results = manager.list_incidents(
                ksearch_list=getattr(args, 'ksearch', None),
                ksort_list=getattr(args, 'ksort', None),
                limit=args.limit,
                ids_only=args.ids_only,
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not results:
            print("No records found")
            return

        # Handle IDs-only output
        if args.ids_only:
            for record_id in results:
                print(record_id)
            return

        # Handle full output
        print(f"\n{'ID':<20} {'Title':<40} {'Updated':<20}")
        print("─" * 80)

        for rec in results:
            kv_all = self._flatten_kv_data(rec.kv_strings, rec.kv_integers, rec.kv_floats)
            
            output = self.TEMPLATE_LIST_ITEM.safe_substitute(
                id=rec.id,
                title=kv_all.get('title', 'Unknown')[:37],
                updated_at=kv_all.get('updated_at', 'Unknown'),
            )
            print(output)
        print("─" * 80)
        print()
        
    def _cmd_update(self, args):
        """Update record metadata and/or description."""
        manager, (kv_single, kv_multi) = self._setup_write_command(args)
    
        has_description = True if (hasattr(args, 'description') and args.description is not None) else False
        has_stdin = StdinHandler.has_stdin_data()
        use_editor = True if (hasattr(args, 'use_editor') or (not has_description and not has_stdin)) else False
        
        use_yaml_editor = not getattr(args, 'no_yaml', False)
        metadata_only = getattr(args, 'metadata_only', False)
        allow_validation_editor = not getattr(args, 'no_validation_editor', False)
        
        # Validate metadata_only usage
        if metadata_only:
            if not kv_single and not kv_multi:
                print("Error: --metadata-only requires at least one metadata field to update", file=sys.stderr)
                sys.exit(1)
            if has_description:
                print("Error: --metadata-only cannot be used with --description", file=sys.stderr)
                sys.exit(1)

        if not kv_single and not kv_multi and not (has_description or has_stdin or use_editor):
            print("Error: No fields to update", file=sys.stderr)
            sys.exit(1)
            
        # NEW: Only catch errors if validation editor is NOT allowed
        try:
            result = manager.update_incident_info(
                args.record_id,
                kv_single=kv_single,
                kv_multi=kv_multi,
                description=args.description if has_description else None,
                use_stdin=has_stdin and not has_description,
                use_editor=use_editor,
                use_yaml_editor=use_yaml_editor,
                metadata_only=metadata_only,
                allow_validation_editor=allow_validation_editor,
            )
            
            if result:
                print(f"✓ Updated record: {args.record_id}")
            else:
                print(f"Update cancelled", file=sys.stderr)
                sys.exit(1)
                
        except ValueError as e:
            # Only happens if allow_validation_editor=False (--no-validation-editor flag)
            # or if it's a non-validation ValueError (like custom_id format)
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        except RuntimeError as e:
            # User cancelled after being offered editor
            print(f"{e}", file=sys.stderr)
            sys.exit(1)            
            
    def _cmd_add_update(self, args):
        """Add note to record."""
        manager, (kv_single, kv_multi) = self._setup_write_command(args)

        has_message = args.message is not None
        has_stdin = StdinHandler.has_stdin_data()
        use_editor = not (has_message or has_stdin)
        use_yaml_editor = not getattr(args, 'no_yaml', False)
        template_id = getattr(args, 'template', None)
        
        # Validate template usage
        if template_id and not use_editor:
            print(
                "Error: --template can only be used in editor mode\n"
                "Remove --message flag or stdin input to use editor",
                file=sys.stderr
            )
            sys.exit(1)

        try:
            # For notes, combine both into kv_single parameter (legacy behavior preserved)
            combined_kv = kv_single + kv_multi
            
            note_id = manager.add_update(
                args.record_id,
                message=args.message if has_message else None,
                use_stdin=has_stdin and not has_message,
                use_editor=use_editor,
                use_yaml_editor=use_yaml_editor,
                kv_single=combined_kv,
                kv_multi=None,
                template_id=template_id,
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
            kv_all = self._flatten_kv_data(note.kv_strings, note.kv_integers, note.kv_floats)
            kv_section = self._format_kv_section(kv_all)
            
            output = self.TEMPLATE_LIST_UPDATES_ITEM.safe_substitute(
                note_number=i,
                timestamp=note.timestamp,
                author=note.author,
                message=note.message,
                kv_all=kv_section,
            )
            print(output)
            
    def _cmd_search_updates(self, args):
        """Search notes by KV data."""
        manager = self._get_manager(args)
    
        try:
            results = manager.search_updates(
                ksearch=args.ksearch,
                limit=args.limit,
                ids_only=args.ids_only,
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not results:
            print("No matching notes found")
            return

        # Handle IDs-only output
        if args.ids_only:
            for result_id in results:
                print(result_id)
            return

        # Handle full output
        header = self.TEMPLATE_SEARCH_UPDATES_HEADER.safe_substitute(
            count=len(results),
        )
        print(header)

        manager = self._get_manager(args)
        db_root = manager.db_root
        filestore = IncidentFileStorage(db_root)
        
        for incident_id, update_id in results:
            incident_path = filestore._get_incident_path(incident_id)
            update_path = f"{filestore._get_updates_dir(incident_id)}/{update_id}.md"
            
            try:
                with open(incident_path, "r") as f:
                    incident_content = f.read()
            except Exception as e:
                print(f"Warning: Failed to load incident {incident_id}: {e}", file=sys.stderr)
                continue
                
            try:
                with open(update_path, "r") as f:
                    update_content = f.read()
            except Exception as e:
                print(f"Warning: Failed to load update {update_id}: {e}", file=sys.stderr)
                continue

            incident_info = Incident.from_markdown(incident_content, incident_id, manager.project_config)
            
            output = self.TEMPLATE_SEARCH_UPDATES_ITEM.safe_substitute(
                incident_id=incident_id,
                update_id=update_id,
                incident_content=incident_content,
                update_content=update_content,
                incident_info=str(incident_info),
            )
            print(output)
            
    def _cmd_reindex(self, args):
        """Rebuild search index."""
        try:
            manager = self._get_manager(args)
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
        print("Use: --use ALIAS to select by library alias")
        print("     --choose to select interactively")
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
