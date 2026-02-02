#!/usr/bin/env python3
"""
Incident Manager - Distributed incident tracking for open-source projects

Zero external dependencies. Sin
import os
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
import select
import secrets
import time

try:gle-file deployment.
Stores incidents as Markdown files with TOML headers.
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
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List
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
    """Incident record."""

    id: str
    title: str
    created_at: str
    created_by: str
    severity: str
    status: str
    tags: List[str]
    assignees: List[str]
    description: Optional[str] = None
    updated_at: Optional[str] = None
    kv_strings: Optional[Dict[str, List[str]]] = None
    kv_integers: Optional[Dict[str, List[int]]] = None
    kv_floats: Optional[Dict[str, List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = self.__dict__.copy()
        # Remove empty KV dicts from output
        if not self.kv_strings:
            d.pop('kv_strings', None)
        if not self.kv_integers:
            d.pop('kv_integers', None)
        if not self.kv_floats:
            d.pop('kv_floats', None)
        return d

    def to_markdown(self) -> str:
        """Convert incident to Markdown with TOML header."""
    
        def dict_to_toml_inline(d):
            """Convert dict to inline TOML table format."""
            if not d:
                return "{}"
            items = []
            for key, value in d.items():
                if isinstance(value, str):
                    items.append(f'{key} = "{value}"')
                elif isinstance(value, (int, float)):
                    items.append(f'{key} = {value}')
                elif isinstance(value, list):
                    # Handle list values
                    formatted_values = [f'"{v}"' if isinstance(v, str) else str(v) for v in value]
                    items.append(f'{key} = [{", ".join(formatted_values)}]')
            return "{ " + ", ".join(items) + " }"
    
        def list_to_toml(lst):
            """Convert list to TOML array format."""
            if not lst:
                return "[]"
            formatted = [f'"{item}"' if isinstance(item, str) else str(item) for item in lst]
            return "[" + ", ".join(formatted) + "]"
    
        toml_header = f"""+++
id = "{self.id}"
title = "{self.title}"
created_at = "{self.created_at}"
created_by = "{self.created_by}"
severity = "{self.severity}"
status = "{self.status}"
tags = {list_to_toml(self.tags)}
assignees = {list_to_toml(self.assignees)}
updated_at = "{self.updated_at or self.created_at}"
kv_strings = {dict_to_toml_inline(self.kv_strings or {})}
kv_integers = {dict_to_toml_inline(self.kv_integers or {})}
kv_floats = {dict_to_toml_inline(self.kv_floats or {})}
+++

"""
        return toml_header + (self.description or "")

    @classmethod
    def from_markdown(cls, content: str, incident_id: str) -> "Incident":
        """Parse incident from Markdown with TOML header."""
        # Split on +++ delimiter
        parts = content.split("+++")
        if len(parts) < 3:
            raise ValueError("Invalid incident file format")

        toml_str = parts[1].strip()
        description = parts[2].strip() if len(parts) > 2 else ""

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
            id=data.get("id", incident_id),
            title=data.get("title", ""),
            created_at=data.get("created_at", ""),
            created_by=data.get("created_by", ""),
            severity=data.get("severity", "medium"),
            status=data.get("status", "open"),
            tags=data.get("tags", []),
            assignees=data.get("assignees", []),
            description=description if description else None,
            updated_at=data.get("updated_at"),
            kv_strings=kv_strings if kv_strings else None,
            kv_integers=kv_integers if kv_integers else None,
            kv_floats=kv_floats if kv_floats else None,
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
        """Return the path to the global user configuration file (~/.config/incident-manager/user.toml)."""
        config_dir = Path.home() / ".config" / "incident-manager"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "user.toml"

    @staticmethod
    def get_project_config_path(db_root: Path) -> Path:
        """Return the path to the project config file (.incident-manager/config.toml)."""
        return db_root / "config.toml"

    @staticmethod
    def get_user_config() -> dict:
        """Load the global user configuration from ~/.config/incident-manager/user.toml."""
        config_path = DatabaseDiscovery.get_user_config_path()
        if not config_path.exists():
            return {}
        try:
            with open(config_path, "rb") as f:
                return tomllib.load(f)
        except Exception as e:
            print(f"Warning: Failed to read user config: {e}", file=sys.stderr)
            return {}

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
        """Load the project configuration from .incident-manager/config.toml."""
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
        4. Parent directories above CWD with .incident-manager
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
            candidate = repo_root / ".incident-manager"
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
            candidate = current / ".incident-manager"
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
        3. Parent directory .incident-manager
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
        locations = config.get("locations", {})
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
        2) Git repository root (.incident-manager)
        3) User config [locations] (longest matching parent)
        4) Parent directories search for .incident-manager (closest wins)
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
            candidate = repo_root / ".incident-manager"
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
            candidate = current / ".incident-manager"
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
        kv_str = kv_str.strip()
        
        # Check for removal format: key- or key${value}-
        if kv_str.endswith('-'):
            kv_str = kv_str[:-1]  # Remove trailing dash
            is_removal = True
        else:
            is_removal = False
        
        # Find operator
        for kvtype in KVParser.VALID_OPERATORS:
            idx = kv_str.find(kvtype)
            if idx > 0:  # Must have a key before operator
                key = kv_str[:idx]
                value_str = kv_str[idx+1:]
                
                if not key:
                    raise ValueError("Key cannot be empty")
                if not value_str and not is_removal:
                    raise ValueError(f"Value cannot be empty for key '{key}'")
                
                # Convert value to appropriate type
                if kvtype == KVParser.TYPE_STRING:
                    value = value_str if value_str else None
                elif kvtype == KVParser.TYPE_INTEGER:
                    if value_str:
                        try:
                            value = int(value_str)
                        except ValueError:
                            raise ValueError(f"Invalid integer value '{value_str}' for key '{key}'")
                    else:
                        value = None
                elif kvtype == KVParser.TYPE_FLOAT:
                    if value_str:
                        try:
                            value = float(value_str)
                        except ValueError:
                            raise ValueError(f"Invalid float value '{value_str}' for key '{key}'")
                    else:
                        value = None
                
                return (key, kvtype, '+' if not is_removal else '-', value)
        
        # Check for kv mode removal (key-)
        if is_removal:
            if not kv_str:
                raise ValueError("Key cannot be empty")
            return (kv_str, None, '-', None)
        
        raise ValueError(
            f"Invalid key-value format: '{kv_str}'\n"
            f"Expected: '{{key}}${{string}}', '{{key}}#{{int}}', or '{{key}}%{{float}}'\n"
            f"For removal: '{{key}}-' (kv mode) or '{{key}}${{val}}-' (kmv mode)"
        )
    
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
            storage_root: Root directory for incident files (.incident-manager)
        """
        self.storage_root = storage_root
        self.incidents_dir = storage_root / "incidents"
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

    def save_incident(self, incident: Incident):
        """Save incident to Markdown file."""
        path = self._get_incident_path(incident.id)
        content = incident.to_markdown()
        
        with open(path, "w") as f:
            f.write(content)

    def load_incident(self, incident_id: str) -> Optional[Incident]:
        """Load incident from Markdown file."""
        path = self._get_incident_path(incident_id)
        
        if not path.exists():
            return None
        
        try:
            with open(path, "r") as f:
                content = f.read()
            return Incident.from_markdown(content, incident_id)
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
        updates_dir = self._get_updates_dir(incident_id)
        filename = IDGenerator.generate_update_filename()
        update_file = updates_dir / filename

        content = f"""# Update

**Author:** {update.author}  
**Timestamp:** {update.timestamp}

---

{update.message}
"""
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
                
                # Parse update file
                lines = content.split("\n")
                author = None
                timestamp = None
                message_start = None
                
                for i, line in enumerate(lines):
                    if line.startswith("**Author:**"):
                        author = line.replace("**Author:**", "").strip()
                    elif line.startswith("**Timestamp:**"):
                        timestamp = line.replace("**Timestamp:**", "").strip()
                    elif line.strip() == "---":
                        message_start = i + 1
                        break
                
                if author and timestamp and message_start is not None:
                    message = "\n".join(lines[message_start:]).strip()
                    updates.append(IncidentUpdate(
                        id=update_id,
                        incident_id=incident_id,
                        timestamp=timestamp,
                        author=author,
                        message=message,
                    ))
            except Exception as e:
                print(f"Warning: Failed to load update {update_file}: {e}", file=sys.stderr)
        
        return updates


# ============================================================================
# Index Database
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
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                tags TEXT NOT NULL,
                assignees TEXT NOT NULL,
                updated_at TEXT NOT NULL,
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
    
        # Key-Value tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_strings (
                incident_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, key, value)
            )
        """)
    
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_integers (
                incident_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, key, value)
            )
        """)
    
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv_floats (
                incident_id TEXT NOT NULL,
                key TEXT NOT NULL,
                value REAL NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (incident_id, key, value)
            )
        """)
    
        # Indices for KV searching and sorting
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_strings_key
            ON kv_strings(key)
        """)
    
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_strings_value
            ON kv_strings(value)
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
            CREATE INDEX IF NOT EXISTS idx_kv_floats_key
            ON kv_floats(key)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_floats_value
            ON kv_floats(value)
        """)

        conn.commit()
        conn.close()

    def index_incident(self, incident: Incident):
        """Add or update incident in index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")

        cursor.execute(
            """
            INSERT OR REPLACE INTO incidents_index
            (id, title, created_at, created_by, severity, status, tags, assignees, updated_at, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                incident.id,
                incident.title,
                incident.created_at,
                incident.created_by,
                incident.severity,
                incident.status,
                json.dumps(incident.tags),
                json.dumps(incident.assignees),
                incident.updated_at or incident.created_at,
                now,
            ),
        )

        cursor.execute("DELETE FROM incidents_fts WHERE incident_id = ?", (incident.id,))

        cursor.execute(
            "INSERT INTO incidents_fts (incident_id, source, source_id, content) VALUES (?, ?, ?, ?)",
            (
                incident.id,
                "incident",
                incident.id,
                f"{incident.title}\n\n{incident.description or ''}",
            ),
        )

        cursor.execute("DELETE FROM incident_tags WHERE incident_id = ?", (incident.id,))

        for tag in incident.tags:
            cursor.execute(
                "INSERT INTO incident_tags (incident_id, tag) VALUES (?, ?)",
                (incident.id, tag),
    	    )

        conn.commit()
        conn.close()

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
        status: Optional[str] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List incidents from index with optional filters."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        query = "SELECT * FROM incidents_index WHERE 1=1"
        params = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if severity:
            query += " AND severity = ?"
            params.append(severity)

        if tags:
            tag_placeholders = ",".join("?" for _ in tags)
            query += f"""
                AND id IN (
                    SELECT incident_id FROM incident_tags
                    WHERE tag IN ({tag_placeholders})
                    GROUP BY incident_id
                    HAVING COUNT(DISTINCT tag) = ?
                )
    		"""
            params.extend(tags)
            params.append(len(tags))

        if search:
            query += """
                AND id IN (
                    SELECT DISTINCT incident_id FROM incidents_fts
                    WHERE incidents_fts MATCH ?
                )
            """
            params.append(search)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
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
            for row in rows
        ]

    def index_update(self, update: IncidentUpdate):
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
        """Index key-value data for incident."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    
        # Clear existing KV data for this incident
        cursor.execute("DELETE FROM kv_strings WHERE incident_id = ?", (incident.id,))
        cursor.execute("DELETE FROM kv_integers WHERE incident_id = ?", (incident.id,))
        cursor.execute("DELETE FROM kv_floats WHERE incident_id = ?", (incident.id,))
    
        # Insert string KV data
        for key, values in (incident.kv_strings or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_strings (incident_id, key, value, created_at) VALUES (?, ?, ?, ?)",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass  # Duplicate, skip
    
        # Insert integer KV data
        for key, values in (incident.kv_integers or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_integers (incident_id, key, value, created_at) VALUES (?, ?, ?, ?)",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        # Insert float KV data
        for key, values in (incident.kv_floats or {}).items():
            for value in values:
                try:
                    cursor.execute(
                        "INSERT INTO kv_floats (incident_id, key, value, created_at) VALUES (?, ?, ?, ?)",
                        (incident.id, key, value, now)
                    )
                except sqlite3.IntegrityError:
                    pass
    
        conn.commit()
        conn.close()
    
    def set_kv_single(self, incident_id: str, key: str, op: str, value: Any):
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
        cursor.execute(f"DELETE FROM {table} WHERE incident_id = ? AND key = ?", (incident_id, key))
        
        # Insert new value
        cursor.execute(
            f"INSERT INTO {table} (incident_id, key, value, created_at) VALUES (?, ?, ?, ?)",
            (incident_id, key, value, now)
        )
    
        conn.commit()
        conn.close()
    
    def add_kv_multi(self, incident_id: str, key: str, op: str, value: Any):
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
                f"INSERT INTO {table} (incident_id, key, value, created_at) VALUES (?, ?, ?, ?)",
                (incident_id, key, value, now)
            )
        except sqlite3.IntegrityError:
            pass  # Value already exists
    
        conn.commit()
        conn.close()
    
    def remove_kv_key(self, incident_id: str, key: str):
        """Remove all values for a key (kv mode)."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
    
        cursor.execute("DELETE FROM kv_strings WHERE incident_id = ? AND key = ?", (incident_id, key))
        cursor.execute("DELETE FROM kv_integers WHERE incident_id = ? AND key = ?", (incident_id, key))
        cursor.execute("DELETE FROM kv_floats WHERE incident_id = ? AND key = ?", (incident_id, key))
    
        conn.commit()
        conn.close()
    
    def remove_kv_value(self, incident_id: str, key: str, op: str, value: Any):
        """Remove specific key/value pair (kmv mode)."""
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
    
        cursor.execute(
            f"DELETE FROM {table} WHERE incident_id = ? AND key = ? AND value = ?",
            (incident_id, key, value)
        )
    
        conn.commit()
        conn.close()

    def search_kv(self, ksearch_list: List[tuple]) -> List[str]:
        """
        Search incidents by key-value criteria.
        
        Args:
            ksearch_list: List of (key, operator, value) tuples
            
        Returns:
            List of matching incident IDs
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        matching_incidents = None
        
        for key, operator, value in ksearch_list:
            results = set()
            
            # Try string search
            try:
                if operator == '=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_strings WHERE key = ? AND value = ?",
                        (key, value)
                    )
                elif operator == '<':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_strings WHERE key = ? AND value < ?",
                        (key, value)
                    )
                elif operator == '>':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_strings WHERE key = ? AND value > ?",
                        (key, value)
                    )
                elif operator == '<=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_strings WHERE key = ? AND value <= ?",
                        (key, value)
                    )
                elif operator == '>=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_strings WHERE key = ? AND value >= ?",
                        (key, value)
                    )
                results.update(row[0] for row in cursor.fetchall())
            except:
                pass
            
            # Try integer search
            try:
                val = int(value)
                if operator == '=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_integers WHERE key = ? AND value = ?",
                        (key, val)
                    )
                elif operator == '<':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_integers WHERE key = ? AND value < ?",
                        (key, val)
                    )
                elif operator == '>':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_integers WHERE key = ? AND value > ?",
                        (key, val)
                    )
                elif operator == '<=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_integers WHERE key = ? AND value <= ?",
                        (key, val)
                    )
                elif operator == '>=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_integers WHERE key = ? AND value >= ?",
                        (key, val)
                    )
                results.update(row[0] for row in cursor.fetchall())
            except:
                pass
            
            # Try float search
            try:
                val = float(value)
                if operator == '=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_floats WHERE key = ? AND value = ?",
                        (key, val)
                    )
                elif operator == '<':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_floats WHERE key = ? AND value < ?",
                        (key, val)
                    )
                elif operator == '>':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_floats WHERE key = ? AND value > ?",
                        (key, val)
                    )
                elif operator == '<=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_floats WHERE key = ? AND value <= ?",
                        (key, val)
                    )
                elif operator == '>=':
                    cursor.execute(
                        "SELECT DISTINCT incident_id FROM kv_floats WHERE key = ? AND value >= ?",
                        (key, val)
                    )
                results.update(row[0] for row in cursor.fetchall())
            except:
                pass
            
            # Intersect with previous results (AND logic)
            if matching_incidents is None:
                matching_incidents = results
            else:
                matching_incidents &= results
        
        conn.close()
        return list(matching_incidents) if matching_incidents is not None else []
    
    def get_sorted_incidents(self, incident_ids: List[str], ksort_list: List[tuple]) -> List[str]:
        """
        Sort incidents by key-value criteria.
        
        Args:
            incident_ids: List of incident IDs to sort
            ksort_list: List of (key, ascending) tuples for sort order
            
        Returns:
            Sorted list of incident IDs
        """
        if not ksort_list or not incident_ids:
            return incident_ids
        
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        # Fetch all KV data for incidents
        kv_data = {}  # {incident_id: {key: [values]}}
        
        for inc_id in incident_ids:
            kv_data[inc_id] = {'strings': {}, 'integers': {}, 'floats': {}}
            
            cursor.execute(
                "SELECT key, value FROM kv_strings WHERE incident_id = ?",
                (inc_id,)
            )
            for key, value in cursor.fetchall():
                if key not in kv_data[inc_id]['strings']:
                    kv_data[inc_id]['strings'][key] = []
                kv_data[inc_id]['strings'][key].append(value)
            
            cursor.execute(
                "SELECT key, value FROM kv_integers WHERE incident_id = ?",
                (inc_id,)
            )
            for key, value in cursor.fetchall():
                if key not in kv_data[inc_id]['integers']:
                    kv_data[inc_id]['integers'][key] = []
                kv_data[inc_id]['integers'][key].append(value)
            
            cursor.execute(
                "SELECT key, value FROM kv_floats WHERE incident_id = ?",
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
                # Try to find the key value in any of the three types
                value = None
                
                if sort_key_name in kv_data[incident_id]['integers']:
                    # Use first integer value
                    value = kv_data[incident_id]['integers'][sort_key_name][0]
                elif sort_key_name in kv_data[incident_id]['floats']:
                    value = kv_data[incident_id]['floats'][sort_key_name][0]
                elif sort_key_name in kv_data[incident_id]['strings']:
                    value = kv_data[incident_id]['strings'][sort_key_name][0]
                
                # Use None (sorts to end) if not found, negate for descending
                if value is None:
                    keys.append((1, ""))  # None sorts last
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
            print(f"Reindexing {len(incident_ids)} incidents...")
        
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
            print(f"✓ Reindexed {indexed_count} incidents")
        
        return indexed_count

# ============================================================================
# High-Level Manager
# ============================================================================


class IncidentManager:
    """High-level incident management API."""

    def __init__(
        self, 
        explicit_location: Optional[Path] = None,
        interactive: bool = None,  # None = auto-detect from config
    ):
        """
        Initialize manager with smart database selection.
    
        Args:
            explicit_location: If provided, use this path directly
            interactive: Override config setting (True=always prompt, False=never prompt, None=use config)
        """
        if explicit_location:
            self.db_root = Path(explicit_location).resolve()
        else:
            candidates = DatabaseDiscovery.find_all_databases()
            
            if not candidates:
                raise RuntimeError("No incident databases found")
            
            # Determine interaction mode
            user_config = DatabaseDiscovery.get_user_config()
            behavior = user_config.get('behavior', {})
            selection_mode = behavior.get('database_selection', 'contextual')
            
            # Override if explicit interactive flag provided
            if interactive is not None:
                selection_mode = 'interactive' if interactive else 'contextual'
            # Don't prompt in non-TTY environments
            elif not sys.stdin.isatty():
                selection_mode = 'contextual'
            
            # Select database based on mode
            if selection_mode == 'interactive':
                self.db_root = DatabaseDiscovery.select_database_interactive(candidates)
            else:
                # 'contextual' mode: use sensible defaults
                self.db_root = DatabaseDiscovery.select_database_contextual(candidates)
        
        if not self.db_root.exists():
            raise RuntimeError(f"Incident database not found: {self.db_root}")
        
        # 'self.config = IncidentConfig(self.db_root)
    

    def create_incident(
        self,
        title: str,
        severity: str = "medium",
        status: Optional[str] = "open",
        tags: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        description: Optional[str] = None,
        kv_single: Optional[List[str]] = None,
        kv_multi: Optional[List[str]] = None,
    ) -> str:
        """Create new incident with optional KV data."""
        incident_id = IDGenerator.generate_incident_id()
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        
        # Parse and apply KV data
        kv_strings = {}
        kv_integers = {}
        kv_floats = {}
        
        # Process single-value KV (kv mode)
        if kv_single:
            for key, kvtype, op, value in KVParser.parse_kv_list(kv_single):
                if op == '-':
                    # Removal at creation time (no-op, nothing exists yet)
                    pass
                elif kvtype == KVParser.TYPE_STRING:
                    kv_strings[key] = [value]
                elif kvtype == KVParser.TYPE_INTEGER:
                    kv_integers[key] = [value]
                elif kvtype == KVParser.TYPE_FLOAT:
                    kv_floats[key] = [value]
        
        # Process multi-value KV (kmv mode)
        if kv_multi:
            for key, kvtype, op, value in KVParser.parse_kv_list(kv_multi):
                if op == '-':
                    # Removal at creation time (no-op)
                    pass
                elif kvtype == KVParser.TYPE_STRING:
                    if key not in kv_strings:
                        kv_strings[key] = []
                    kv_strings[key].append(value)
                elif kvtype == KVParser.TYPE_INTEGER:
                    if key not in kv_integers:
                        kv_integers[key] = []
                    kv_integers[key].append(value)
                elif kvtype == KVParser.TYPE_FLOAT:
                    if key not in kv_floats:
                        kv_floats[key] = []
                    kv_floats[key].append(value)
    
        incident = Incident(
            id=incident_id,
            title=title,
            created_at=now,
            created_by=self.user_identity.handle,
            severity=severity,
            status="open",
            tags=tags or [],
            assignees=assignees or [],
            description=description,
            updated_at=now,
            kv_strings=kv_strings if kv_strings else None,
            kv_integers=kv_integers if kv_integers else None,
            kv_floats=kv_floats if kv_floats else None,
        )
    
        # Save to file
        self.storage.save_incident(incident)
        
        # Update index
        self.index_db.index_incident(incident)
        self.index_db.index_kv_data(incident)
    
        return incident_id

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident from file storage."""
        return self.storage.load_incident(incident_id)

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None,
        limit: int = 50,
        ksearch: Optional[List[str]] = None,
        ksort: Optional[str] = None,
    ) -> List[Incident]:
        """
        List incidents using index, then load from files.
        
        Args:
            status: Filter by status
            severity: Filter by severity
            tags: Filter by tags
            search: Full-text search
            limit: Maximum results
            ksearch: List of key-value search expressions
            ksort: Comma-delimited sort keys with +/- modifiers
        """
        # Get IDs from index
        index_results = self.index_db.list_incidents_from_index(
            status=status,
            severity=severity,
            tags=tags,
            search=search,
            limit=limit * 2,  # Get extra to account for KV filtering
        )
        
        incident_ids = [result["id"] for result in index_results]
        
        # Apply KV search filters
        if ksearch:
            try:
                ksearch_parsed = [KVSearchParser.parse_ksearch(expr) for expr in ksearch]
                matching_ids = self.index_db.search_kv(ksearch_parsed)
                incident_ids = [iid for iid in incident_ids if iid in matching_ids]
            except ValueError as e:
                raise RuntimeError(f"Invalid ksearch: {e}")
        
        # Apply KV sorting
        if ksort:
            try:
                ksort_parsed = KVSearchParser.parse_ksort(ksort)
                incident_ids = self.index_db.get_sorted_incidents(incident_ids, ksort_parsed)
            except ValueError as e:
                raise RuntimeError(f"Invalid ksort: {e}")
        
        # Apply limit after sorting/searching
        incident_ids = incident_ids[:limit]
        
        # Load full incidents from files
        incidents = []
        for incident_id in incident_ids:
            incident = self.storage.load_incident(incident_id)
            if incident:
                incidents.append(incident)
        
        return incidents

    def update_incident_status(self, incident_id: str, status: str):
        """Update incident status."""
        incident = self.storage.load_incident(incident_id)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
        
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        incident.status = status
        incident.updated_at = now
        
        # Save to file
        self.storage.save_incident(incident)
        
        # Update index
        self.index_db.index_incident(incident)

    def update_incident_kv(
        self,
        incident_id: str,
        kv_single: Optional[List[str]] = None,
        kv_multi: Optional[List[str]] = None,
    ):
        """
        Update KV data on existing incident.
        
        Args:
            incident_id: Incident ID
            kv_single: Single-value KV updates (replaces keys)
            kv_multi: Multi-value KV updates (adds values)
        """
        incident = self.storage.load_incident(incident_id)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
        
        # Initialize KV dicts if needed
        if not incident.kv_strings:
            incident.kv_strings = {}
        if not incident.kv_integers:
            incident.kv_integers = {}
        if not incident.kv_floats:
            incident.kv_floats = {}
        
        # Process single-value KV (kv mode) - replaces existing
        if kv_single:
            for key, kvtype, op, value in KVParser.parse_kv_list(kv_single):
                if op == '-':
                    # Remove all values for this key
                    incident.kv_strings.pop(key, None)
                    incident.kv_integers.pop(key, None)
                    incident.kv_floats.pop(key, None)
                    self.index_db.remove_kv_key(incident_id, key)
                elif kvtype == KVParser.TYPE_STRING:
                    incident.kv_strings[key] = [value]
                    self.index_db.set_kv_single(incident_id, key, op, value)
                elif kvtype == KVParser.TYPE_INTEGER:
                    incident.kv_integers[key] = [value]
                    self.index_db.set_kv_single(incident_id, key, op, value)
                elif kvtype == KVParser.TYPE_FLOAT:
                    incident.kv_floats[key] = [value]
                    self.index_db.set_kv_single(incident_id, key, op, value)
        
        # Process multi-value KV (kmv mode) - adds values
        if kv_multi:
            for key, kvtype, op, value in KVParser.parse_kv_list(kv_multi):
                if op == '-':
                    # Remove specific key/value pair
                    incident.kv_strings[key] = [v for v in incident.kv_strings.get(key, []) if v != value]
                    incident.kv_integers[key] = [v for v in incident.kv_integers.get(key, []) if v != value]
                    incident.kv_floats[key] = [v for v in incident.kv_floats.get(key, []) if v != value]
                    self.index_db.remove_kv_value(incident_id, key, KVParser.TYPE_STRING, value)
                    self.index_db.remove_kv_value(incident_id, key, KVParser.TYPE_INTEGER, value)
                    self.index_db.remove_kv_value(incident_id, key, KVParser.TYPE_FLOAT, value)
                elif kvtype == KVParser.TYPE_STRING:
                    if key not in incident.kv_strings:
                        incident.kv_strings[key] = []
                    if value not in incident.kv_strings[key]:
                        incident.kv_strings[key].append(value)
                    self.index_db.add_kv_multi(incident_id, key, kvtype, value)
                elif kvtype == KVParser.TYPE_INTEGER:
                    if key not in incident.kv_integers:
                        incident.kv_integers[key] = []
                    if value not in incident.kv_integers[key]:
                        incident.kv_integers[key].append(value)
                    self.index_db.add_kv_multi(incident_id, key, kvtype, value)
                elif kvtype == KVParser.TYPE_FLOAT:
                    if key not in incident.kv_floats:
                        incident.kv_floats[key] = []
                    if value not in incident.kv_floats[key]:
                        incident.kv_floats[key].append(value)
                    self.index_db.add_kv_multi(incident_id, key, kvtype, value)
        
        # Save to file and update index
        self.storage.save_incident(incident)
        self.index_db.index_incident(incident)

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
        Add update/comment to incident with optional KV data inheritance.
    
        Priority for message: explicit message > STDIN > editor
    
        Args:
            incident_id: Incident ID
            message: Explicit message
            use_stdin: Try reading from STDIN
            use_editor: Open editor
            kv_single: Single-value KV updates to apply to incident
            kv_multi: Multi-value KV updates to apply to incident
    
        Returns:
            Timestamp of the update
        """
        # Verify incident exists
        if not self.storage.load_incident(incident_id):
            raise RuntimeError(f"Incident {incident_id} not found")
    
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
            # Remove comment lines
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
    
        timestamp = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        
        # Parse KV data for the update
        update_kv_strings = {}
        update_kv_integers = {}
        update_kv_floats = {}
        
        if kv_single:
            for key, kvtype, op, value in KVParser.parse_kv_list(kv_single):
                if op != '-':
                    if kvtype == KVParser.TYPE_STRING:
                        update_kv_strings[key] = [value]
                    elif kvtype == KVParser.TYPE_INTEGER:
                        update_kv_integers[key] = [value]
                    elif kvtype == KVParser.TYPE_FLOAT:
                        update_kv_floats[key] = [value]
        
        if kv_multi:
            for key, kvtype, op, value in KVParser.parse_kv_list(kv_multi):
                if op != '-':
                    if kvtype == KVParser.TYPE_STRING:
                        if key not in update_kv_strings:
                            update_kv_strings[key] = []
                        update_kv_strings[key].append(value)
                    elif kvtype == KVParser.TYPE_INTEGER:
                        if key not in update_kv_integers:
                            update_kv_integers[key] = []
                        update_kv_integers[key].append(value)
                    elif kvtype == KVParser.TYPE_FLOAT:
                        if key not in update_kv_floats:
                            update_kv_floats[key] = []
                        update_kv_floats[key].append(value)
        
        update = IncidentUpdate(
            id="auto",
            incident_id=incident_id,
            timestamp=timestamp,
            author=self.user_identity.handle,
            message=final_message,
            kv_strings=update_kv_strings if update_kv_strings else None,
            kv_integers=update_kv_integers if update_kv_integers else None,
            kv_floats=update_kv_floats if update_kv_floats else None,
        )
        
        self.storage.save_update(incident_id, update)
        self.index_db.index_update(update)
    
        # Inherit KV data from update to incident
        if kv_single or kv_multi:
            self.update_incident_kv(incident_id, kv_single=kv_single, kv_multi=kv_multi)
    
        return timestamp
    
    def get_updates(self, incident_id: str) -> List[IncidentUpdate]:
        """Get updates for incident."""
        return self.storage.load_updates(incident_id)


# ============================================================================
# CLI
# ============================================================================


class IncidentCLI:
    """Command-line interface."""

    def __init__(self):
        self.parser = argparse.ArgumentParser(
            description="Incident Manager - Distributed incident tracking",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        self.subparsers = self.parser.add_subparsers(dest="command", required=True)

    def _add_common_args(self, parser):
        """Add common incident manager arguments."""
        parser.add_argument(
            "--location",
            help="Explicit incident database path (overrides all detection)",
        )
        parser.add_argument(
            "--choose",
            action="store_true",
            help="Prompt to choose database if multiple available",
        )
        parser.add_argument(
            "--list-databases",
            action="store_true",
            help="Show all available databases and exit",
        )
    
    def _get_manager(self, args) -> IncidentManager:
        """Handle database selection."""
        interactive = getattr(args, 'choose', False)
        
        return IncidentManager(
            explicit_location=getattr(args, 'location', None),
            interactive=interactive,
        )
    
    def setup_commands(self):
        """Set up all CLI commands."""
        # init
        init_parser = self.subparsers.add_parser(
            "init",
            help="Initialize incident database",
        )
        self._add_common_args(init_parser)
    
        # config
        config_parser = self.subparsers.add_parser(
            "config",
            help="Manage configuration",
        )
        self._add_common_args(config_parser)
        config_subparsers = config_parser.add_subparsers(dest="config_command", required=True)
    
        set_user_parser = config_subparsers.add_parser(
            "set-user-global",
            help="Set global user identity",
        )
        set_user_parser.add_argument("--handle", required=True, help="User handle")
        set_user_parser.add_argument("--email", required=True, help="User email")
    
        set_editor_parser = config_subparsers.add_parser(
            "set-editor",
            help="Set user's preferred editor",
            description=(
                "Set the editor that Incident Manager uses when opening an editor.\n"
                "This is a user-global setting stored in ~/.config/incident-manager/user.toml\n"
                "Takes precedence over the EDITOR environment variable."
            )
        )
        set_editor_parser.add_argument("editor", help="Editor command (e.g., vim, nano, code, emacs")
    
        get_editor_parser = config_subparsers.add_parser(
            "get-editor",
            help="Show current editor",
        )
    
        # create
        create_parser = self.subparsers.add_parser(
            "create",
            help="Create new incident",
        )
        self._add_common_args(create_parser)
        create_parser.add_argument(
            "--override-repo-boundary",
            action="store_true",
            help="Bypass git repository boundary checks",
        )
        create_parser.add_argument("--title", required=True, help="Incident title")
        create_parser.add_argument(
            "--severity",
            choices=["low", "medium", "high", "critical"],
            default="medium",
            help="Incident severity",
        )
        create_parser.add_argument(
            "--tags",
            nargs="*",
            default=[],
            help="Tags (space-separated)",
        )
        create_parser.add_argument(
            "-kv",
            action="append",
            dest="kv_single",
            help="Single-value key-value data (replaces existing): 'key$value', 'key#123', 'key%1.5'",
        )
        create_parser.add_argument(
            "-kmv",
            action="append",
            dest="kv_multi",
            help="Multi-value key-value data (adds to existing): 'key$value', 'key#123', 'key%1.5'",
        )
        create_parser.add_argument(
            "--assignees",
            nargs="*",
            default=[],
            help="Assignees (space-separated)",
        )
        create_parser.add_argument(
            "--description",
            help="Detailed description",
        )
    
        # get
        get_parser = self.subparsers.add_parser(
            "get",
            help="View incident details",
        )
        self._add_common_args(get_parser)
        get_parser.add_argument("incident_id", help="Incident ID")
    
        # list
        list_parser = self.subparsers.add_parser(
            "list",
            help="List incidents",
        )
        self._add_common_args(list_parser)
        list_parser.add_argument(
            "--status",
            help="Filter by status",
        )
        list_parser.add_argument(
            "--severity",
            help="Filter by severity",
        )
        list_parser.add_argument(
            "--search",
            help="Full-text search in title and description",
        )
        list_parser.add_argument(
            "--ksearch",
            action="append",
            dest="ksearch",
            help="Search by key-value: 'key=value', 'cost>100', 'priority<=5' (can use multiple times)",
        )
        list_parser.add_argument(
            "--ksort",
            help="Sort by key-values: 'key1,key2-,key3+' (+ = asc, - = desc, default = asc)",
        )

        list_parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum incidents to show",
        )
        list_parser.add_argument(
            "--tag",
            action="append",
            dest="tags",
            help="Filter by tag (can be used multiple times)",
        )
    
        # update
        update_parser = self.subparsers.add_parser(
            "update",
            help="Update incident status",
        )
        self._add_common_args(update_parser)
        update_parser.add_argument("incident_id", help="Incident ID")
        update_parser.add_argument(
            "--status",
            required=True,
            choices=["open", "investigating", "mitigating", "resolved", "closed"],
            help="New status",
        )
        update_parser.add_argument(
            "-kv",
            action="append",
            dest="kv_single",
            help="Single-value KV data: 'key$value' or 'key-' to remove",
        )
        update_parser.add_argument(
            "-kmv",
            action="append",
            dest="kv_multi",
            help="Multi-value KV data: 'key$value' or 'key$value-' to remove specific value",
        )
    
        # add-update
        add_update_parser = self.subparsers.add_parser(
            "add-update",
            help="Add update to incident (message > STDIN > editor)",
            description=(
                "Add update to incident. Priority:\n"
                "  1. --message flag (explicit message)\n"
                "  2. STDIN (if piped)\n"
                "  3. Editor (if STDIN unavailable)"
            ),
        )
        self._add_common_args(add_update_parser)
        add_update_parser.add_argument("incident_id", help="Incident ID")
        add_update_parser.add_argument(
            "--message",
            help="Update message",
        )
        add_update_parser.add_argument(
            "-kv",
            action="append",
            dest="kv_single",
            help="Single-value KV data to apply to incident",
        )
        add_update_parser.add_argument(
            "-kmv",
            action="append",
            dest="kv_multi",
            help="Multi-value KV data to apply to incident",
        )

    
        # get-updates
        get_updates_parser = self.subparsers.add_parser(
            "get-updates",
            help="View all updates for an incident",
        )
        self._add_common_args(get_updates_parser)
        get_updates_parser.add_argument("incident_id", help="Incident ID")
    
        # reindex
        reindex_parser = self.subparsers.add_parser(
            "reindex",
            help="Rebuild search index from files",
        )
        self._add_common_args(reindex_parser)
        reindex_parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Verbose output",
        )

        # list-databases
        list_databases_parser = self.subparsers.add_parser(
            "list-databases",
            help="Show all available incident databases",
        )
        list_databases_parser.set_defaults(func=self._cmd_list_databases)
    
    def run(self, args: Optional[List[str]] = None):
        """Run CLI."""
        self.setup_commands()
        parsed = self.parser.parse_args(args)

        try:
            if parsed.command == "init":
                self._cmd_init(parsed)
            elif parsed.command == "config":
                self._cmd_config(parsed)
            elif parsed.command == "create":
                self._cmd_create(parsed)
            elif parsed.command == "get":
                self._cmd_get(parsed)
            elif parsed.command == "list":
                self._cmd_list(parsed)
            elif parsed.command == "update":
                self._cmd_update(parsed)
            elif parsed.command == "add-update":
                self._cmd_add_update(parsed)
            elif parsed.command == "get-updates":
                self._cmd_get_updates(parsed)
            elif parsed.command == "reindex":
                self._cmd_reindex(parsed)
            elif parsed.command == "list-databases":
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
                db_root = repo_root / ".incident-manager"
            except subprocess.CalledProcessError:
                db_root = Path.cwd() / ".incident-manager"

        # Enforce repo boundary
        if not DatabaseDiscovery.enforce_repo_boundary(db_root, override=getattr(args, 'override_repo_boundary', False)):
            print(
                f"Error: Incident database at {db_root} is outside the current git repository.\n"
                "Use --override-repo-boundary to bypass this check.",
                file=sys.stderr,
            )
            sys.exit(1)

        db_root.mkdir(parents=True, exist_ok=True)
        
        # Initialize storage and index
        storage = IncidentFileStorage(db_root)
        index_db = IncidentIndexDatabase(db_root / "incidents.db")

        print(f"✓ Incident database initialized at {db_root}")
        print(f"  Incidents: {storage.incidents_dir}")
        print(f"  Updates: {storage.updates_dir}")
        print(f"  Index: {db_root / 'incidents.db'}")
        print(f"  Config: {db_root / 'config.toml'}")

    def _cmd_config(self, args):
        """Handle config commands."""
        if args.config_command == "set-user-global":
            config = DatabaseDiscovery.get_user_config()
            config["user"] = {
                "handle": args.handle,
                "email": args.email,
            }
            DatabaseDiscovery.set_user_config(config)
            print(f"✓ User configured: {args.handle} <{args.email}>")

        elif args.config_command == "set-editor":
            # Verify editor exists
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

    def _get_manager(self,args) -> IncidentManager:
        """
        Helper to instantiate IncidentManager with standard args handling.
    
        Extracts location and override_repo_boundary from args if present.
    
        Args:
            args: Parsed arguments namespace
    
        Returns:
            Initialized IncidentManager instance
        """
        interactive = getattr(args, 'choose', False)

        return IncidentManager(
            explicit_location=getattr(args, 'location', None),
            interactive=interactive,
        )

    def _cmd_create(self, args):
        """Create incident."""
        manager = self._get_manager(args)

        incident_id = manager.create_incident(
            title=args.title,
            severity=args.severity,
            tags=args.tags if args.tags else None,
            assignees=args.assignees if args.assignees else None,
            description=args.description,
            kv_single=args.kv_single if hasattr(args, 'kv_single') and args.kv_single else None,
            kv_multi=args.kv_multi if hasattr(args, 'kv_multi') and args.kv_multi else None,
        )

        print(f"✓ Created: {incident_id}")
        print(f"  Title: {args.title}")
        print(f"  Severity: {args.severity}")


    def _cmd_get(self, args):
        """View incident."""
        #manager = IncidentManager(explicit_location=args.location)
        manager = self._get_manager(args)
        incident = manager.get_incident(args.incident_id)

        if not incident:
            print(f"Error: Incident {args.incident_id} not found", file=sys.stderr)
            sys.exit(1)

        print(f"ID:        {incident.id}")
        print(f"Title:     {incident.title}")
        print(f"Status:    {incident.status}")
        print(f"Severity:  {incident.severity}")
        print(f"Created:   {incident.created_at} by {incident.created_by}")
        if incident.updated_at and incident.updated_at != incident.created_at:
            print(f"Updated:   {incident.updated_at}")
        if incident.tags:
            print(f"Tags:      {', '.join(incident.tags)}")
        if incident.assignees:
            print(f"Assignees: {', '.join(incident.assignees)}")
        if incident.description:
            print(f"\n{incident.description}")

    def _cmd_list(self, args):
        """List incidents with KV filtering and sorting."""
        manager = self._get_manager(args)
    
        try:
            incidents = manager.list_incidents(
                status=args.status,
                severity=args.severity,
                tags=args.tags,
                search=args.search,
                limit=args.limit,
                ksearch=getattr(args, 'ksearch', None),
                ksort=getattr(args, 'ksort', None),
            )
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

        if not incidents:
            print("No incidents found")
            return

        # Print table header
        print(f"{'ID':<15} {'Title':<40} {'Status':<12} {'Severity':<10}")
        print("─" * 80)

        for inc in incidents:
            title = inc.title[:37]  # Truncate for display
            print(f"{inc.id:<15} {title:<40} {inc.status:<12} {inc.severity:<10}")

    def _cmd_update(self, args):
        """Update incident status and KV data."""
        manager = self._get_manager(args)
        manager.update_incident_status(args.incident_id, args.status)
        
        # Update KV data if provided
        if hasattr(args, 'kv_single') and args.kv_single or hasattr(args, 'kv_multi') and args.kv_multi:
            manager.update_incident_kv(
                args.incident_id,
                kv_single=getattr(args, 'kv_single', None),
                kv_multi=getattr(args, 'kv_multi', None),
            )
    
        print(f"✓ Updated {args.incident_id} to {args.status}")

    def _cmd_add_update(self, args):
        """Add update to incident with optional KV data."""
        manager = self._get_manager(args)

        # Determine input mode
        has_message = args.message is not None
        has_stdin = StdinHandler.has_stdin_data()

        if has_message:
            manager.add_update(
                args.incident_id,
                message=args.message,
                kv_single=getattr(args, 'kv_single', None),
                kv_multi=getattr(args, 'kv_multi', None),
            )
        elif has_stdin:
            manager.add_update(
                args.incident_id,
                use_stdin=True,
                kv_single=getattr(args, 'kv_single', None),
                kv_multi=getattr(args, 'kv_multi', None),
            )
        else:
            manager.add_update(
                args.incident_id,
                use_editor=True,
                kv_single=getattr(args, 'kv_single', None),
                kv_multi=getattr(args, 'kv_multi', None),
            )

        print(f"✓ Update added to {args.incident_id}")

    def _cmd_get_updates(self, args):
        """View all updates for incident."""
        #manager = IncidentManager(explicit_location=args.location)
        manager = self._get_manager(args)
        incident = manager.get_incident(args.incident_id)

        if not incident:
            print(f"Error: Incident {args.incident_id} not found", file=sys.stderr)
            sys.exit(1)

        updates = manager.get_updates(args.incident_id)

        print(f"Updates for {args.incident_id}:\n")

        if not updates:
            print("No updates yet")
            return

        for i, update in enumerate(updates, 1):
            print(f"{i}. [{update.timestamp}] {update.author}")
            # Indent message
            for line in update.message.split("\n"):
                print(f"   {line}")
            print()

    def _cmd_reindex(self, args):
        """Rebuild search index from files."""
        try:
            #manager = IncidentManager(explicit_location=args.location)
            manager = self._get_manager(args)
            reindexer = IncidentReindexer(manager.storage, manager.index_db)
            count = reindexer.reindex_all(verbose=args.verbose)
            print(f"✓ Successfully reindexed {count} incidents")
        except RuntimeError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)

    def _cmd_list_databases(self, args):
        """Show all available incident databases."""
        candidates = DatabaseDiscovery.find_all_databases()
    
        if not candidates:
            print("No incident databases found.")
            return
    
        print("\n" + "="*70)
        print("Available incident databases:")
        print("="*70)
    
        contextual = {k: v for k, v in candidates.items() if v.get('category') == 'contextual'}
        available = {k: v for k, v in candidates.items() if v.get('category') == 'available'}
        
        if contextual:
            print("\n[Contextual]")
            for key, info in contextual.items():
                marker = "→" if self._is_default_selection(candidates) == key else " "
                print(f"  {marker} {info['source']}")
                print(f"      {info['path']}")
    
        if available:
            print("\n[Available]")
            for key, info in available.items():
                print(f"    {info['source']}")
                print(f"      {info['path']}")
    
        print("\n" + "="*70)
        print("Tip: Use --choose to select interactively, --location to specify explicitly")
        print("="*70 + "\n\n")


# ============================================================================
# Main
# ============================================================================


def main():
    """Entry point."""
    cli = IncidentCLI()
    cli.run()


if __name__ == "__main__":
    main()
