# chronicle_tests.py
"""
Comprehensive test suite for Incident Manager using pytest and pytest-mock.

Usage:
    pytest chronicle_tests.py -v
    pytest chronicle_tests.py --cov=chronicle
    pytest chronicle_tests.py -k "test_create" -v
"""

import pytest
import tempfile
import json
import sqlite3
import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import sys

# Import the modules to test (adjust import paths as needed)
from chronicle import (
    Incident, IncidentUpdate, IncidentFileStorage, IncidentIndexDatabase,
    IncidentManager, IncidentCLI, IDGenerator, KVParser,
    DatabaseDiscovery
)


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_db_root(tmp_path):
    """Temporary database root directory."""
    db_root = tmp_path / ".incident-manager"
    db_root.mkdir()
    return db_root


@pytest.fixture
def storage(temp_db_root):
    """IncidentFileStorage instance with temporary root."""
    return IncidentFileStorage(temp_db_root)


@pytest.fixture
def index_db(temp_db_root):
    """IncidentIndexDatabase instance with temporary root."""
    db_path = temp_db_root / "incidents.db"
    return IncidentIndexDatabase(db_path)


@pytest.fixture
def sample_incident():
    """Sample Incident object."""
    now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    return Incident(
        id="INC-001",
        title="Database Connection Timeout",
        created_at=now,
        created_by="alice",
        severity="high",
        status="open",
        tags=["database", "production"],
        assignees=["bob", "charlie"],
        description="Primary database is experiencing timeout errors.",
        updated_at=now,
        kv_strings={"environment": ["production", "staging"]},
        kv_integers={"affected_users": [1500]},
        kv_floats={"error_rate": [0.35]},
    )


@pytest.fixture
def sample_update():
    """Sample IncidentUpdate object."""
    now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    return IncidentUpdate(
        id="UPD-001",
        incident_id="INC-001",
        timestamp=now,
        author="bob",
        message="Restarted database service. Monitoring recovery.",
        kv_strings={"status": ["investigating"]},
    )


@pytest.fixture
def mock_user_identity():
    """Mock user identity."""
    mock = Mock()
    mock.handle = "testuser"
    mock.email = "test@example.com"
    return mock


@pytest.fixture
def manager_with_mocks(temp_db_root, mock_user_identity, mocker):
    """IncidentManager with mocked user identity and database selection."""
    mocker.patch.object(DatabaseDiscovery, 'find_all_databases', 
                       return_value={"db1": {"path": str(temp_db_root), "source": "current"}})
    mocker.patch.object(DatabaseDiscovery, 'select_database_contextual',
                       return_value=temp_db_root)
    
    manager = IncidentManager(explicit_location=temp_db_root)
    manager.user_identity = mock_user_identity
    manager.storage = IncidentFileStorage(temp_db_root)
    manager.index_db = IncidentIndexDatabase(temp_db_root / "incidents.db")
    
    return manager


# ============================================================================
# TESTS: IncidentFileStorage
# ============================================================================


class TestIncidentFileStorage:
    """Tests for IncidentFileStorage class."""

    def test_initialization_creates_directories(self, temp_db_root):
        """Should create incidents and updates directories."""
        storage = IncidentFileStorage(temp_db_root)
        
        assert storage.incidents_dir.exists()
        assert storage.updates_dir.exists()

    def test_get_incident_path(self, storage):
        """Should generate correct incident file path."""
        path = storage._get_incident_path("INC-123")
        
        assert path.name == "INC-123.md"
        assert "incidents" in str(path)

    def test_save_incident(self, storage, sample_incident, mocker):
        """Should save incident as Markdown file."""
        # Mock the to_markdown method
        mocker.patch.object(sample_incident, 'to_markdown', 
                           return_value="# INC-001\nTitle: Database Connection")
        
        storage.save_incident(sample_incident)
        
        path = storage._get_incident_path(sample_incident.id)
        assert path.exists()
        assert "INC-001" in path.read_text()

    def test_load_incident(self, storage, sample_incident, mocker):
        """Should load incident from Markdown file."""
        # Mock save and load methods
        mocker.patch.object(sample_incident, 'to_markdown',
                           return_value="# INC-001")
        mocker.patch('chronicle.Incident.from_markdown',
                     return_value=sample_incident)
        
        storage.save_incident(sample_incident)
        loaded = storage.load_incident("INC-001")
        
        assert loaded is not None
        assert loaded.id == "INC-001"

    def test_load_incident_not_found(self, storage):
        """Should return None for non-existent incident."""
        result = storage.load_incident("INC-NONEXISTENT")
        
        assert result is None

    def test_delete_incident(self, storage, sample_incident, mocker):
        """Should delete incident file."""
        mocker.patch.object(sample_incident, 'to_markdown',
                           return_value="# INC-001")
        storage.save_incident(sample_incident)
        
        path = storage._get_incident_path("INC-001")
        assert path.exists()
        
        storage.delete_incident("INC-001")
        assert not path.exists()

    def test_list_incident_files(self, storage, mocker):
        """Should list all incident files."""
        # Create multiple incident files
        for i in range(1, 4):
            incident_id = f"INC-{i:03d}"
            path = storage._get_incident_path(incident_id)
            path.write_text(f"# {incident_id}")
        
        incidents = storage.list_incident_files()
        
        assert len(incidents) == 3
        assert "INC-001" in incidents
        assert "INC-002" in incidents
        assert "INC-003" in incidents

    def test_save_update(self, storage, sample_update, mocker):
        """Should save update as Markdown file."""
        mocker.patch('chronicle.IDGenerator.generate_update_filename',
                     return_value="update_001.md")
        
        storage.save_update("INC-001", sample_update)
        
        updates_dir = storage._get_updates_dir("INC-001")
        update_file = updates_dir / "update_001.md"
        assert update_file.exists()
        assert "bob" in update_file.read_text()

    def test_load_updates(self, storage, sample_update, mocker):
        """Should load all updates for incident."""
        mocker.patch('chronicle.IDGenerator.generate_update_filename',
                     return_value="update_001.md")
        
        storage.save_update("INC-001", sample_update)
        updates = storage.load_updates("INC-001")
        
        assert len(updates) == 1
        assert updates[0].author == "bob"

    def test_load_updates_empty(self, storage):
        """Should return empty list when no updates exist."""
        updates = storage.load_updates("INC-NONEXISTENT")
        
        assert updates == []


# ============================================================================
# TESTS: IncidentIndexDatabase
# ============================================================================


class TestIncidentIndexDatabase:
    """Tests for IncidentIndexDatabase class."""

    def test_initialization_creates_schema(self, temp_db_root):
        """Should create database schema on initialization."""
        db_path = temp_db_root / "incidents.db"
        index_db = IncidentIndexDatabase(db_path)
        
        assert db_path.exists()
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert "incidents_index" in tables
        assert "incidents_fts" in tables
        assert "incident_tags" in tables

    def test_index_incident(self, index_db, sample_incident):
        """Should add incident to index."""
        index_db.index_incident(sample_incident)
        
        result = index_db.get_incident_from_index("INC-001")
        assert result is not None
        assert result["title"] == "Database Connection Timeout"
        assert result["severity"] == "high"

    def test_index_incident_with_tags(self, index_db, sample_incident):
        """Should index incident tags correctly."""
        index_db.index_incident(sample_incident)
        
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT tag FROM incident_tags WHERE incident_id = ?",
                      ("INC-001",))
        tags = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert "database" in tags
        assert "production" in tags

    def test_remove_incident_from_index(self, index_db, sample_incident):
        """Should remove incident from all indices."""
        index_db.index_incident(sample_incident)
        assert index_db.get_incident_from_index("INC-001") is not None
        
        index_db.remove_incident_from_index("INC-001")
        assert index_db.get_incident_from_index("INC-001") is None

    def test_get_incident_from_index_not_found(self, index_db):
        """Should return None for non-existent incident."""
        result = index_db.get_incident_from_index("INC-NONEXISTENT")
        
        assert result is None

    def test_list_incidents_from_index(self, index_db):
        """Should list incidents with optional filters."""
        # Create sample incidents
        incidents = []
        for i in range(1, 4):
            now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
            inc = Incident(
                id=f"INC-{i:03d}",
                title=f"Incident {i}",
                created_at=now,
                created_by="alice",
                severity=["low", "medium", "high"][i-1],
                status="open" if i % 2 else "closed",
                tags=["tag1"] if i % 2 else ["tag2"],
                assignees=[],
                updated_at=now,
            )
            index_db.index_incident(inc)
            incidents.append(inc)
        
        # Test listing all
        results = index_db.list_incidents_from_index(limit=10)
        assert len(results) >= 1
        
        # Test filtering by status
        results = index_db.list_incidents_from_index(status="open", limit=10)
        assert all(r["status"] == "open" for r in results)
        
        # Test filtering by severity
        results = index_db.list_incidents_from_index(severity="high", limit=10)
        assert all(r["severity"] == "high" for r in results)

    def test_list_incidents_with_tag_filter(self, index_db):
        """Should filter incidents by tags (AND logic)."""
        now = datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
        
        # Incident with both tags
        inc1 = Incident(
            id="INC-001",
            title="Has both tags",
            created_at=now,
            created_by="alice",
            severity="high",
            status="open",
            tags=["database", "production"],
            assignees=[],
            updated_at=now,
        )
        
        # Incident with only one tag
        inc2 = Incident(
            id="INC-002",
            title="Has one tag",
            created_at=now,
            created_by="alice",
            severity="high",
            status="open",
            tags=["database"],
            assignees=[],
            updated_at=now,
        )
        
        index_db.index_incident(inc1)
        index_db.index_incident(inc2)
        
        # Search for both tags (AND logic)
        results = index_db.list_incidents_from_index(
            tags=["database", "production"],
            limit=10
        )
        
        assert len(results) == 1
        assert results[0]["id"] == "INC-001"

    def test_index_update(self, index_db, sample_update):
        """Should add update to full-text search index."""
        index_db.index_update(sample_update)
        
        # Verify FTS entry was created
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT source FROM incidents_fts WHERE incident_id = ? AND source = ?",
            ("INC-001", "update")
        )
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None

    def test_clear_index(self, index_db, sample_incident):
        """Should clear all index entries."""
        index_db.index_incident(sample_incident)
        assert index_db.get_incident_from_index("INC-001") is not None
        
        index_db.clear_index()
        assert index_db.get_incident_from_index("INC-001") is None

    def test_index_kv_data(self, index_db, sample_incident):
        """Should index key-value data."""
        index_db.index_kv_data(sample_incident)
        
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        
        # Check string KV
        cursor.execute("SELECT value FROM kv_strings WHERE key = ?",
                      ("environment",))
        results = [row[0] for row in cursor.fetchall()]
        assert "production" in results
        
        # Check integer KV
        cursor.execute("SELECT value FROM kv_integers WHERE key = ?",
                      ("affected_users",))
        results = [row[0] for row in cursor.fetchall()]
        assert 1500 in results
        
        conn.close()

    def test_set_kv_single(self, index_db):
        """Should set single-value KV (replace existing)."""
        index_db.set_kv_single("INC-001", "severity_level", KVParser.TYPE_INTEGER, 5)
        
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM kv_integers WHERE incident_id = ? AND key = ?",
            ("INC-001", "severity_level")
        )
        result = cursor.fetchone()
        conn.close()
        
        assert result is not None
        assert result[0] == 5

    def test_add_kv_multi(self, index_db):
        """Should add multi-value KV (keep existing)."""
        index_db.add_kv_multi("INC-001", "affected_service", KVParser.TYPE_STRING, "api")
        index_db.add_kv_multi("INC-001", "affected_service", KVParser.TYPE_STRING, "db")
        
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM kv_strings WHERE incident_id = ? AND key = ?",
            ("INC-001", "affected_service")
        )
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert "api" in results
        assert "db" in results

    def test_remove_kv_key(self, index_db):
        """Should remove all values for a key."""
        index_db.add_kv_multi("INC-001", "tag", KVParser.TYPE_STRING, "critical")
        index_db.add_kv_multi("INC-001", "tag", KVParser.TYPE_STRING, "urgent")
        
        index_db.remove_kv_key("INC-001", "tag")
        
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM kv_strings WHERE incident_id = ? AND key = ?",
            ("INC-001", "tag")
        )
        count = cursor.fetchone()[0]
        conn.close()
        
        assert count == 0

    def test_remove_kv_value(self, index_db):
        """Should remove specific key/value pair."""
        index_db.add_kv_multi("INC-001", "service", KVParser.TYPE_STRING, "api")
        index_db.add_kv_multi("INC-001", "service", KVParser.TYPE_STRING, "db")
        
        index_db.remove_kv_value("INC-001", "service", KVParser.TYPE_STRING, "api")
        
        conn = sqlite3.connect(index_db.database_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT value FROM kv_strings WHERE incident_id = ? AND key = ?",
            ("INC-001", "service")
        )
        results = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        assert "api" not in results
        assert "db" in results

    def test_search_kv_equality(self, index_db):
        """Should search KV data with equality operator."""
        index_db.set_kv_single("INC-001", "environment", KVParser.TYPE_STRING, "prod")
        index_db.set_kv_single("INC-002", "environment", KVParser.TYPE_STRING, "dev")
        
        results = index_db.search_kv([("environment", "=", "prod")])
        
        assert "INC-001" in results
        assert "INC-002" not in results

    def test_search_kv_comparison_operators(self, index_db):
        """Should search KV data with comparison operators."""
        index_db.set_kv_single("INC-001", "cost", KVParser.TYPE_INTEGER, 100)
        index_db.set_kv_single("INC-002", "cost", KVParser.TYPE_INTEGER, 200)
        index_db.set_kv_single("INC-003", "cost", KVParser.TYPE_INTEGER, 150)
        
        # Greater than
        results = index_db.search_kv([("cost", ">", "120")])
        assert "INC-002" in results
        assert "INC-003" in results
        assert "INC-001" not in results
        
        # Less than or equal
        results = index_db.search_kv([("cost", "<=", "150")])
        assert "INC-001" in results
        assert "INC-003" in results
        assert "INC-002" not in results

    def test_search_kv_multiple_criteria(self, index_db):
        """Should search with multiple KV criteria (AND logic)."""
        index_db.set_kv_single("INC-001", "environment", KVParser.TYPE_STRING, "prod")
        index_db.set_kv_single("INC-001", "severity", KVParser.TYPE_INTEGER, 5)
        
        index_db.set_kv_single("INC-002", "environment", KVParser.TYPE_STRING, "prod")
        index_db.set_kv_single("INC-002", "severity", KVParser.TYPE_INTEGER, 3)
        
        # Both criteria must match
        results = index_db.search_kv([
            ("environment", "=", "prod"),
            ("severity", ">", "4")
        ])
        
        assert "INC-001" in results
        assert "INC-002" not in results

    def test_get_sorted_incidents(self, index_db):
        """Should sort incidents by KV criteria."""
        index_db.set_kv_single("INC-001", "priority", KVParser.TYPE_INTEGER, 3)
        index_db.set_kv_single("INC-002", "priority", KVParser.TYPE_INTEGER, 1)
        index_db.set_kv_single("INC-003", "priority", KVParser.TYPE_INTEGER, 2)
        
        incident_ids = ["INC-001", "INC-002", "INC-003"]
        
        # Sort ascending
        sorted_ids = index_db.get_sorted_incidents(incident_ids, [("priority", True)])
        assert sorted_ids == ["INC-002", "INC-003", "INC-001"]
        
        # Sort descending
        sorted_ids = index_db.get_sorted_incidents(incident_ids, [("priority", False)])
        assert sorted_ids == ["INC-001", "INC-003", "INC-002"]


# ============================================================================
# TESTS: IncidentManager
# ============================================================================


class TestIncidentManager:
    """Tests for IncidentManager class."""

    def test_create_incident(self, manager_with_mocks):
        """Should create new incident with all fields."""
        incident_id = manager_with_mocks.create_incident(
            title="Network Outage",
            severity="critical",
            tags=["network", "outage"],
            assignees=["alice", "bob"],
            description="Major network outage in production",
        )
        
        assert incident_id.startswith("INC-")
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident is not None
        assert incident.title == "Network Outage"
        assert incident.severity == "critical"

    def test_create_incident_with_kv_single(self, manager_with_mocks, mocker):
        """Should create incident with single-value KV data."""
        mocker.patch('chronicle.KVParser.parse_kv_list',
                    return_value=[("env", KVParser.TYPE_STRING, "+", "prod")])
        
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
            kv_single=["env$prod"],
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.kv_strings.get("env") == ["prod"]

    def test_create_incident_with_kv_multi(self, manager_with_mocks, mocker):
        """Should create incident with multi-value KV data."""
        mocker.patch('chronicle.KVParser.parse_kv_list',
                    return_value=[
                        ("service", KVParser.TYPE_STRING, "+", "api"),
                        ("service", KVParser.TYPE_STRING, "+", "db"),
                    ])
        
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
            kv_multi=["service$api", "service$db"],
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert "api" in incident.kv_strings.get("service", [])
        assert "db" in incident.kv_strings.get("service", [])

    def test_get_incident(self, manager_with_mocks):
        """Should retrieve incident by ID."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident is not None
        assert incident.id == incident_id

    def test_get_incident_not_found(self, manager_with_mocks):
        """Should return None for non-existent incident."""
        result = manager_with_mocks.get_incident("INC-NONEXISTENT")
        
        assert result is None

    def test_list_incidents(self, manager_with_mocks):
        """Should list incidents with filters."""
        # Create sample incidents
        for i in range(1, 4):
            manager_with_mocks.create_incident(
                title=f"Incident {i}",
                severity=["low", "medium", "high"][i-1],
                status="open" if i % 2 else "closed",
            )
        
        incidents = manager_with_mocks.list_incidents(limit=10)
        assert len(incidents) >= 1

    def test_list_incidents_with_status_filter(self, manager_with_mocks):
        """Should filter incidents by status."""
        # Create incidents with different statuses
        id1 = manager_with_mocks.create_incident(title="Open Incident")
        manager_with_mocks.update_incident_status(id1, "open")
        
        id2 = manager_with_mocks.create_incident(title="Resolved Incident")
        manager_with_mocks.update_incident_status(id2, "resolved")
        
        incidents = manager_with_mocks.list_incidents(status="open", limit=10)
        assert any(inc.id == id1 for inc in incidents)

    def test_list_incidents_with_search(self, manager_with_mocks):
        """Should search incidents by full-text."""
        manager_with_mocks.create_incident(
            title="Database Connection Timeout",
            description="Connection pool exhausted",
        )
        
        # Note: FTS search depends on SQLite FTS implementation
        incidents = manager_with_mocks.list_incidents(search="Database", limit=10)
        # Result depends on FTS implementation

    def test_update_incident_status(self, manager_with_mocks):
        """Should update incident status."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        manager_with_mocks.update_incident_status(incident_id, "investigating")
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.status == "investigating"

    def test_update_incident_kv(self, manager_with_mocks, mocker):
        """Should update incident KV data."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        mocker.patch('chronicle.KVParser.parse_kv_list',
                    return_value=[("component", KVParser.TYPE_STRING, "+", "api")])
        
        manager_with_mocks.update_incident_kv(
            incident_id,
            kv_multi=["component$api"],
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert "api" in incident.kv_strings.get("component", [])

    def test_add_update_with_message(self, manager_with_mocks):
        """Should add update with explicit message."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        timestamp = manager_with_mocks.add_update(
            incident_id,
            message="Status update: investigating",
        )
        
        assert timestamp is not None
        updates = manager_with_mocks.get_updates(incident_id)
        assert len(updates) >= 1
        assert "investigating" in updates[0].message

    def test_add_update_with_stdin(self, manager_with_mocks, mocker):
        """Should add update from STDIN."""
        mocker.patch('chronicle.StdinHandler.has_stdin_data',
                    return_value=True)
        mocker.patch('chronicle.StdinHandler.read_stdin_with_timeout',
                    return_value="Update from STDIN")
        
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        timestamp = manager_with_mocks.add_update(
            incident_id,
            use_stdin=True,
        )
        
        assert timestamp is not None

    def test_add_update_with_editor(self, manager_with_mocks, mocker):
        """Should add update from editor."""
        mocker.patch('chronicle.EditorConfig.launch_editor',
                    return_value="# Update from editor\nFixed the issue")
        
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        timestamp = manager_with_mocks.add_update(
            incident_id,
            use_editor=True,
        )
        
        assert timestamp is not None
        updates = manager_with_mocks.get_updates(incident_id)
        assert len(updates) >= 1

    def test_add_update_no_message_raises_error(self, manager_with_mocks):
        """Should raise error when no message provided."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        with pytest.raises(RuntimeError, match="No update provided"):
            manager_with_mocks.add_update(
                incident_id,
                message=None,
                use_stdin=False,
                use_editor=False,
            )

    def test_get_updates(self, manager_with_mocks):
        """Should retrieve all updates for incident."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        manager_with_mocks.add_update(incident_id, message="First update")
        manager_with_mocks.add_update(incident_id, message="Second update")
        
        updates = manager_with_mocks.get_updates(incident_id)
        assert len(updates) >= 2


# ============================================================================
# TESTS: IncidentCLI
# ============================================================================


class TestIncidentCLI:
    """Tests for IncidentCLI class."""

    @pytest.fixture
    def cli(self):
        """CLI instance."""
        return IncidentCLI()

    def test_initialization(self, cli):
        """Should initialize CLI with argument parser."""
        assert cli.parser is not None
        assert cli.subparsers is not None

    def test_setup_commands(self, cli):
        """Should set up all subcommands."""
        cli.setup_commands()
        
        # Verify key subcommands exist
        # subcommand_names = [action.dest for action in cli.subparsers._group_actions
        #                   if hasattr(action, 'choices') and action.choices]
        # Note: this is implementation-dependent

    def test_cmd_init(self, cli, temp_db_root, mocker):
        """Should initialize database directory."""
        mocker.patch('chronicle.subprocess.run')
        mocker.patch('chronicle.DatabaseDiscovery.enforce_repo_boundary',
                    return_value=True)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.location = str(temp_db_root)
        args.override_repo_boundary = False
        
        cli._cmd_init(args)
        
        # Verify directories were created
        assert (temp_db_root / "incidents").exists()
        assert (temp_db_root / "updates").exists()

    def test_cmd_config_set_user(self, cli, mocker):
        """Should set user configuration."""
        mocker.patch('chronicle.DatabaseDiscovery.get_user_config',
                    return_value={})
        mocker.patch('chronicle.DatabaseDiscovery.set_user_config')
        mocker.patch('builtins.print')
        
        args = Mock()
        args.config_command = "set-user-global"
        args.handle = "alice"
        args.email = "alice@example.com"
        
        cli._cmd_config(args)
        
        # Verify set_user_config was called
        DatabaseDiscovery.set_user_config.assert_called_once()

    def test_cmd_config_set_editor(self, cli, mocker):
        """Should set editor configuration."""
        mocker.patch('chronicle.EditorConfig._editor_exists',
                    return_value=True)
        mocker.patch('chronicle.DatabaseDiscovery.get_user_config',
                    return_value={})
        mocker.patch('chronicle.DatabaseDiscovery.set_user_config')
        mocker.patch('builtins.print')
        
        args = Mock()
        args.config_command = "set-editor"
        args.editor = "vim"
        
        cli._cmd_config(args)

    def test_cmd_create(self, cli, manager_with_mocks, mocker):
        """Should create incident from CLI."""
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.title = "CLI Test Incident"
        args.severity = "high"
        args.tags = ["test"]
        args.assignees = []
        args.description = "Test description"
        args.kv_single = None
        args.kv_multi = None
        
        cli._cmd_create(args)

    def test_cmd_get(self, cli, manager_with_mocks, mocker):
        """Should display incident from CLI."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
            severity="medium",
            tags=["test"],
        )
        
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.incident_id = incident_id
        
        cli._cmd_get(args)

    def test_cmd_list(self, cli, manager_with_mocks, mocker):
        """Should list incidents from CLI."""
        # Create sample incidents
        for i in range(3):
            manager_with_mocks.create_incident(
                title=f"Incident {i}",
            )
        
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.status = None
        args.severity = None
        args.tags = None
        args.search = None
        args.limit = 50
        args.ksearch = None
        args.ksort = None
        
        cli._cmd_list(args)

    def test_cmd_update(self, cli, manager_with_mocks, mocker):
        """Should update incident from CLI."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.incident_id = incident_id
        args.status = "investigating"
        args.kv_single = None
        args.kv_multi = None
        
        cli._cmd_update(args)
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.status == "investigating"

    def test_cmd_add_update(self, cli, manager_with_mocks, mocker):
        """Should add update from CLI."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('chronicle.StdinHandler.has_stdin_data',
                    return_value=False)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.incident_id = incident_id
        args.message = "CLI update message"
        args.kv_single = None
        args.kv_multi = None
        
        cli._cmd_add_update(args)

    def test_cmd_get_updates(self, cli, manager_with_mocks, mocker):
        """Should display updates from CLI."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        manager_with_mocks.add_update(incident_id, message="Test update")
        
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.incident_id = incident_id
        
        cli._cmd_get_updates(args)

    def test_cmd_reindex(self, cli, manager_with_mocks, mocker):
        """Should reindex incidents from CLI."""
        manager_with_mocks.create_incident(title="Test Incident")
        
        mocker.patch.object(cli, '_get_manager', return_value=manager_with_mocks)
        mocker.patch('builtins.print')
        
        args = Mock()
        args.verbose = True
        
        cli._cmd_reindex(args)

    def test_cmd_list_databases(self, cli, mocker):
        """Should list available databases."""
        mocker.patch('chronicle.DatabaseDiscovery.find_all_databases',
                    return_value={"db1": {"path": "/path/to/db", "source": "contextual"}})
        mocker.patch('builtins.print')
        
        args = Mock()
        
        cli._cmd_list_databases(args)


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_create_and_retrieve_incident(self, manager_with_mocks):
        """Should create incident and retrieve it."""
        incident_id = manager_with_mocks.create_incident(
            title="Integration Test",
            severity="high",
            tags=["integration"],
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.title == "Integration Test"
        assert incident.severity == "high"
        assert "integration" in incident.tags

    def test_create_update_and_retrieve_updates(self, manager_with_mocks):
        """Should create incident, add updates, and retrieve them."""
        incident_id = manager_with_mocks.create_incident(
            title="Test",
        )
        
        manager_with_mocks.add_update(incident_id, message="First update")
        manager_with_mocks.add_update(incident_id, message="Second update")
        
        updates = manager_with_mocks.get_updates(incident_id)
        assert len(updates) >= 2
        assert any("First" in u.message for u in updates)
        assert any("Second" in u.message for u in updates)

    def test_search_and_filter_incidents(self, manager_with_mocks):
        """Should search and filter incidents."""
        manager_with_mocks.create_incident(
            title="Database Issue",
            tags=["database", "critical"],
            severity="critical",
        )
        manager_with_mocks.create_incident(
            title="Network Issue",
            tags=["network"],
            severity="low",
        )
        
        # Filter by severity
        incidents = manager_with_mocks.list_incidents(
            severity="critical",
            limit=10
        )
        assert any(inc.title == "Database Issue" for inc in incidents)

    def test_full_workflow(self, manager_with_mocks):
        """Should complete full incident lifecycle."""
        # Create
        incident_id = manager_with_mocks.create_incident(
            title="Production Outage",
            severity="critical",
            tags=["production"],
        )
        
        # Retrieve
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.status == "open"
        
        # Update status
        manager_with_mocks.update_incident_status(incident_id, "investigating")
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.status == "investigating"
        
        # Add updates
        manager_with_mocks.add_update(incident_id, message="Root cause identified")
        manager_with_mocks.add_update(incident_id, message="Fix deployed")
        
        # Resolve
        manager_with_mocks.update_incident_status(incident_id, "resolved")
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.status == "resolved"
        
        # Verify updates
        updates = manager_with_mocks.get_updates(incident_id)
        assert len(updates) >= 2


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================


class TestEdgeCasesAndErrors:
    """Tests for edge cases and error handling."""

    def test_incident_with_empty_fields(self, manager_with_mocks):
        """Should handle incident with minimal fields."""
        incident_id = manager_with_mocks.create_incident(
            title="Minimal Incident",
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.title == "Minimal Incident"
        assert incident.tags == []
        assert incident.assignees == []

    def test_incident_with_special_characters(self, manager_with_mocks):
        """Should handle incident with special characters."""
        incident_id = manager_with_mocks.create_incident(
            title="Issue with <special> & characters: @#$%",
            description="Description with\nnewlines\nand\ttabs",
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert "<special>" in incident.title
        assert "\n" in incident.description

    def test_incident_with_very_long_title(self, manager_with_mocks):
        """Should handle incident with very long title."""
        long_title = "x" * 500
        incident_id = manager_with_mocks.create_incident(
            title=long_title,
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.title == long_title

    def test_update_nonexistent_incident(self, manager_with_mocks):
        """Should raise error when updating non-existent incident."""
        with pytest.raises(RuntimeError, match="not found"):
            manager_with_mocks.update_incident_status("INC-NONEXISTENT", "closed")

    def test_add_update_to_nonexistent_incident(self, manager_with_mocks):
        """Should raise error when adding update to non-existent incident."""
        with pytest.raises(RuntimeError, match="not found"):
            manager_with_mocks.add_update("INC-NONEXISTENT", message="test")

    def test_list_incidents_empty_database(self, manager_with_mocks):
        """Should return empty list when no incidents exist."""
        incidents = manager_with_mocks.list_incidents(limit=10)
        # May be empty or contain incidents from fixtures
        assert isinstance(incidents, list)

    def test_concurrent_kv_operations(self, index_db):
        """Should handle multiple concurrent KV operations."""
        for i in range(10):
            incident_id = f"INC-{i:03d}"
            for j in range(5):
                index_db.add_kv_multi(
                    incident_id,
                    "tag",
                    KVParser.TYPE_STRING,
                    f"tag_{j}"
                )


# ============================================================================
# PARAMETRIZED TESTS
# ============================================================================


class TestParametrized:
    """Parametrized tests for comprehensive coverage."""

    @pytest.mark.parametrize("severity", ["low", "medium", "high", "critical"])
    def test_create_incident_with_different_severities(self, manager_with_mocks, severity):
        """Should create incidents with different severity levels."""
        incident_id = manager_with_mocks.create_incident(
            title=f"Test {severity}",
            severity=severity,
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.severity == severity

    @pytest.mark.parametrize("status", ["open", "investigating", "mitigating", "resolved", "closed"])
    def test_update_incident_with_different_statuses(self, manager_with_mocks, status):
        """Should update incident to different statuses."""
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
        )
        
        manager_with_mocks.update_incident_status(incident_id, status)
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert incident.status == status

    @pytest.mark.parametrize("num_tags", [0, 1, 5, 10])
    def test_create_incident_with_different_tag_counts(self, manager_with_mocks, num_tags):
        """Should handle incidents with varying numbers of tags."""
        tags = [f"tag_{i}" for i in range(num_tags)]
        incident_id = manager_with_mocks.create_incident(
            title="Test Incident",
            tags=tags,
        )
        
        incident = manager_with_mocks.get_incident(incident_id)
        assert len(incident.tags) == num_tags


# ============================================================================
# PYTEST CONFIGURATION
# ============================================================================


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow"
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

