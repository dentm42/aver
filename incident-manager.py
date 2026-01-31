#!/usr/bin/env python3
"""
Incident Manager - Distributed incident tracking for open-source projects

Zero external dependencies. Single-file deployment.
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

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__

    def to_markdown(self) -> str:
        """Convert incident to Markdown with TOML header."""
        toml_header = f"""+++
id = "{self.id}"
title = "{self.title}"
created_at = "{self.created_at}"
created_by = "{self.created_by}"
severity = "{self.severity}"
status = "{self.status}"
tags = {json.dumps(self.tags)}
assignees = {json.dumps(self.assignees)}
updated_at = "{self.updated_at or self.created_at}"
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
        )


@dataclass
class IncidentUpdate:
    """Update/comment on an incident."""

    id: str
    incident_id: str
    timestamp: str
    author: str
    message: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "incident_id": self.incident_id,
            "timestamp": self.timestamp,
            "author": self.author,
            "message": self.message,
        }

# ============================================================================
# ID Generation
# ============================================================================

class IDGenerator:
    @staticmethod
    def generate_incident_id() -> str:
        import hashlib
        data = f"{time.time()}{os.urandom(8)}".encode()
        return f"INC-{hashlib.sha256(data).hexdigest()[:8].upper()}"

    @staticmethod
    def generate_update_filename() -> str:
        epoch_ns = time.time_ns()
        rand = secrets.token_hex(3)
        return f"{epoch_ns}-{rand}.md"

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
# ID Generation
# ============================================================================


class IDGenerator:
    """Generate incident IDs."""

    @staticmethod
    def generate_incident_id() -> str:
        """Generate a unique incident ID like INC-a1b2c3d4"""
        import hashlib
        import time

        # Use timestamp + random data
        data = f"{time.time()}{os.urandom(8)}".encode()
        hash_digest = hashlib.sha256(data).hexdigest()[:8]
        return f"INC-{hash_digest.upper()}"

    @staticmethod
    def generate_update_id(incident_id: str) -> str:
        """Generate update ID."""
        import hashlib
        import time

        data = f"{incident_id}{time.time()}{os.urandom(4)}".encode()
        hash_digest = hashlib.sha256(data).hexdigest()[:8]
        return f"UPD-{hash_digest.upper()}"


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

        conn.commit()
        conn.close()

    def index_incident(self, incident: Incident):
        """Add or update incident in index."""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()

        now = datetime.datetime.utcnow().isoformat() + "Z"

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
            "INSERT INTO incidents_fts (incident_id, title, description) VALUES (?, ?, ?)",
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
        cursor.execute("DELETE FROM incidents_fts WHERE id = ?", (incident_id,))
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
        conn.commit()
        conn.close()


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

    def __init__(self, explicit_location: Optional[Path] = None):
        """
        Initialize manager with discovered database.

        Args:
            explicit_location: Optional explicit database path
            override_repo_boundary: If True, bypass git repo boundary checks
    
        Raises:
            RuntimeError: If database is outside git repo and override is False
        """

        self.db_root = DatabaseDiscovery.find_database_or_fail(explicit_location=explicit_location)

        # Enforce repo boundary
        if not DatabaseDiscovery.enforce_repo_boundary(self.db_root, override=override_repo_boundary):
            raise RuntimeError(
                f"Incident database at {self.db_root} is outside the current git repository.\n"
                "Use --override-repo-boundary to bypass this check."
            )

        self.index_db_path = self.db_root / "incidents.db"
        
        # Initialize storage and index
        self.storage = IncidentFileStorage(self.db_root)
        self.index_db = IncidentIndexDatabase(self.index_db_path)

        # Load user identity
        user_config = DatabaseDiscovery.get_user_config()
        if "user" not in user_config:
            raise RuntimeError(
                "User identity not configured.\n"
                "Set with: incident config set-user-global --handle <handle> --email <email>"
            )
        self.user_identity = UserIdentity.from_dict(user_config["user"])

    def create_incident(
        self,
        title: str,
        severity: str = "medium",
        tags: Optional[List[str]] = None,
        assignees: Optional[List[str]] = None,
        description: Optional[str] = None,
    ) -> str:
        """Create new incident."""
        incident_id = IDGenerator.generate_incident_id()
        now = datetime.datetime.utcnow().isoformat() + "Z"

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
        )

        # Save to file
        self.storage.save_incident(incident)
        
        # Update index
        self.index_db.index_incident(incident)

        return incident_id

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident from file storage."""
        return self.storage.load_incident(incident_id)

    def list_incidents(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        tags: Optional[List[str]] = None,
        search: Optional[str] = None
        limit: int = 50,
    ) -> List[Incident]:
        """List incidents using index, then load from files."""
        # Get IDs from index
        index_results = self.index_db.list_incidents_from_index(
            status=status,
            severity=severity,
            tags=tags,
            search=search,
            limit=limit,
        )
        
        # Load full incidents from files
        incidents = []
        for result in index_results:
            incident = self.storage.load_incident(result["id"])
            if incident:
                incidents.append(incident)
        
        return incidents

    def update_incident_status(self, incident_id: str, status: str):
        """Update incident status."""
        incident = self.storage.load_incident(incident_id)
        if not incident:
            raise RuntimeError(f"Incident {incident_id} not found")
        
        now = datetime.datetime.utcnow().isoformat() + "Z"
        incident.status = status
        incident.updated_at = now
        
        # Save to file
        self.storage.save_incident(incident)
        
        # Update index
        self.index_db.index_incident(incident)

    def add_update(
        self,
        incident_id: str,
        message: Optional[str] = None,
        use_stdin: bool = False,
        use_editor: bool = False,
    ) -> str:
        """
        Add update/comment to incident.

        Priority: explicit message > STDIN > editor

        Args:
            incident_id: Incident ID
            message: Explicit message (highest priority)
            use_stdin: Try reading from STDIN (if message is None)
            use_editor: Open editor (lowest priority, if message and STDIN are None)

        Returns:
            Timestamp of the update

        Raises:
            RuntimeError: If no valid input method produces content
        """
        # Verify incident exists
        if not self.storage.load_incident(incident_id):
            raise RuntimeError(f"Incident {incident_id} not found")

        # Determine message source
        final_message = None

        # 1. Explicit message (highest priority)
        if message:
            final_message = message
        # 2. STDIN (if available)
        elif use_stdin and StdinHandler.has_stdin_data():
            final_message = StdinHandler.read_stdin_with_timeout(timeout=2.0)
        # 3. Editor (lowest priority)
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

        timestamp = datetime.datetime.utcnow().isoformat() + "Z"
        
        update = IncidentUpdate(
            id="auto",
            incident_id=incident_id,
            timestamp=timestamp,
            author=self.user_identity.handle,
            message=final_message,
        )
        
        self.storage.save_update(incident_id, update)
        self.index_db.index_update(update)

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

    def setup_commands(self):
        """Set up all CLI commands."""
        # init
        init_parser = self.subparsers.add_parser(
            "init",
            help="Initialize incident database",
        )
        init_parser.add_argument(
            "--location",
            help="Database location (default: .incident-manager in current repo)",
        )

        create_parser.add_argument(
            "--override-repo-boundary",
            action="store_true",
            help="Bypass git repository boundary checks",
        )

        # config
        config_parser = self.subparsers.add_parser(
            "config",
            help="Manage configuration",
        )
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
        get_parser.add_argument("incident_id", help="Incident ID")

        # list
        list_parser = self.subparsers.add_parser(
            "list",
            help="List incidents",
        )
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
        update_parser.add_argument("incident_id", help="Incident ID")
        update_parser.add_argument(
            "--status",
            required=True,
            choices=["open", "investigating", "mitigating", "resolved", "closed"],
            help="New status",
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
        add_update_parser.add_argument("incident_id", help="Incident ID")
        add_update_parser.add_argument(
            "--message",
            help="Update message",
        )

        # get-updates
        get_updates_parser = self.subparsers.add_parser(
            "get-updates",
            help="View all updates for an incident",
        )
        get_updates_parser.add_argument("incident_id", help="Incident ID")

        # reindex
        reindex_parser = self.subparsers.add_parser(
            "reindex",
            help="Rebuild search index from files",
        )
        reindex_parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Verbose output",
        )

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
        return IncidentManager(
            explicit_location=getattr(args, 'location', None),
            override_repo_boundary=getattr(args, 'override_repo_boundary', False),
        )

    def _cmd_create(self, args):
        """Create incident."""
        #manager = IncidentManager(explicit_location=args.location)
        manager = self._get_manager(args)

        incident_id = manager.create_incident(
            title=args.title,
            severity=args.severity,
            tags=args.tags if args.tags else None,
            assignees=args.assignees if args.assignees else None,
            description=args.description,
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
        """List incidents."""
        #manager = IncidentManager(explicit_location=args.location)
        manager = self._get_manager(args)
        incidents = manager.list_incidents(
            status=args.status,
            severity=args.severity,
            tags=args.tags,
            search=args.search,
            limit=args.limit,
        )

        if not incidents:
            print("No incidents found")
            return

        # Print table header
        print(f"{'ID':<15} {'Title':<40} {'Status':<12} {'Severity':<10}")
        print("─" * 80)

        for inc in incidents:
            title = inc.title[: 38 - 1]  # Truncate for display
            print(f"{inc.id:<15} {title:<40} {inc.status:<12} {inc.severity:<10}")

    def _cmd_update(self, args):
        """Update incident status."""
        #manager = IncidentManager(explicit_location=args.location)
        manager = self._get_manager(args)
        manager.update_incident_status(args.incident_id, args.status)
        print(f"✓ Updated {args.incident_id} to {args.status}")

    def _cmd_add_update(self, args):
        """Add update to incident."""
        #manager = IncidentManager(explicit_location=args.location)
        manager = self._get_manager(args)

        # Determine input mode
        has_message = args.message is not None
        has_stdin = StdinHandler.has_stdin_data()

        if has_message:
            # Explicit message: use it
            manager.add_update(args.incident_id, message=args.message)
        elif has_stdin:
            # STDIN: read it
            manager.add_update(args.incident_id, use_stdin=True)
        else:
            # Default: open editor
            manager.add_update(args.incident_id, use_editor=True)

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


# ============================================================================
# Main
# ============================================================================


def main():
    """Entry point."""
    cli = IncidentCLI()
    cli.run()


if __name__ == "__main__":
    main()
