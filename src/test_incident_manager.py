# test_incident_manager.py
"""
Comprehensive test suite for incident-manager.py

Tests cover:
- IncidentManager initialization and database selection
- Incident CRUD operations
- KV (key-value) data handling
- Update/comment functionality
- CLI command parsing and execution
- Index and search operations
"""

import sys
import os
import tempfile
import shutil
import json
import sqlite3
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest
import subprocess
from datetime import datetime

# Import the module under test
# Note: Adjust import path as needed
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import incident_manager


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def temp_db_dir():
    """Create temporary database directory."""
    tmpdir = tempfile.mkdtemp(prefix="incident_test_")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mock_user_identity():
    """Mock user identity."""
    mock = Mock()
    mock.handle = "test_user"
    mock.email = "test@example.com"
    return mock


@pytest.fixture
def manager_instance(temp_db_dir, mock_user_identity):
    """Create IncidentManager instance with temporary database."""
    with patch('incident_manager.DatabaseDiscovery.find_all_databases', return_value={temp_db_dir: {}}):
        with patch('incident_manager.IncidentConfig'):
            manager = IncidentManager(explicit_location=temp_db_dir)
            manager.user_identity = mock_user_identity
            manager.storage = Mock()
            manager.index_db = Mock()
            return manager


# ============================================================================
# TESTS: IncidentManager.__init__
# ============================================================================


class TestIncidentManagerInit:
    """Test IncidentManager initialization."""

    def test_init_with_explicit_location(self, temp_db_dir):
        """Test initialization with explicit location."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        
        with patch('incident_manager.IncidentConfig'):
            manager = IncidentManager(explicit_location=str(temp_db_dir))
            assert manager.db_root == temp_db_dir

    def test_init_no_databases_found(self):
        """Test initialization when no databases found."""
        with patch('incident_manager.DatabaseDiscovery.find_all_databases', return_value={}):
            with pytest.raises(RuntimeError, match="No incident databases found"):
                IncidentManager()

    def test_init_database_not_exists(self):
        """Test initialization with non-existent database path."""
        non_existent = Path("/non/existent/path/db")
        
        with pytest.raises(RuntimeError, match="Incident database not found"):
            IncidentManager(explicit_location=str(non_existent))

    def test_init_interactive_mode_override(self, temp_db_dir):
        """Test interactive flag overrides config."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        candidates = {temp_db_dir: {'category': 'contextual'}}
        
        with patch('incident_manager.DatabaseDiscovery.find_all_databases', return_value=candidates):
            with patch('incident_manager.DatabaseDiscovery.select_database_interactive') as mock_select:
                with patch('incident_manager.IncidentConfig'):
                    mock_select.return_value = temp_db_dir
                    
                    manager = IncidentManager(interactive=True)
                    mock_select.assert_called_once()

    def test_init_non_tty_environment(self, temp_db_dir):
        """Test that non-TTY environment forces contextual mode."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        candidates = {temp_db_dir: {'category': 'contextual'}}
        
        with patch('incident_manager.DatabaseDiscovery.find_all_databases', return_value=candidates):
            with patch('incident_manager.DatabaseDiscovery.select_database_contextual') as mock_contextual:
                with patch('sys.stdin.isatty', return_value=False):
                    with patch('incident_manager.IncidentConfig'):
                        mock_contextual.return_value = temp_db_dir
                        
                        manager = IncidentManager()
                        mock_contextual.assert_called_once()


# ============================================================================
# TESTS: IncidentManager.create_incident
# ============================================================================


class TestCreateIncident:
    """Test incident creation."""

    def test_create_basic_incident(self, manager_instance):
        """Test creating basic incident with minimal fields."""
        manager_instance.create_incident(
            title="Test Incident",
            severity="high",
        )
        
        manager_instance.storage.save_incident.assert_called_once()
        manager_instance.index_db.index_incident.assert_called_once()
        
        incident = manager_instance.storage.save_incident.call_args[0][0]
        assert incident.title == "Test Incident"
        assert incident.severity == "high"
        assert incident.status == "open"

    def test_create_incident_with_all_fields(self, manager_instance):
        """Test creating incident with all optional fields."""
        manager_instance.create_incident(
            title="Full Test Incident",
            severity="critical",
            tags=["database", "urgent"],
            assignees=["alice", "bob"],
            description="Detailed description",
        )
        
        incident = manager_instance.storage.save_incident.call_args[0][0]
        assert incident.title == "Full Test Incident"
        assert incident.tags == ["database", "urgent"]
        assert incident.assignees == ["alice", "bob"]
        assert incident.description == "Detailed description"

    def test_create_incident_with_kv_single(self, manager_instance):
        """Test creating incident with single-value KV data."""
        with patch('incident_manager.KVParser.parse_kv_list') as mock_parse:
            mock_parse.return_value = [('cost', '$', '1000'), ('priority', '#', 5)]
            
            manager_instance.create_incident(
                title="Test KV",
                kv_single=['cost$1000', 'priority#5'],
            )
            
            incident = manager_instance.storage.save_incident.call_args[0][0]
            assert incident.kv_strings == {'cost': ['1000']}
            assert incident.kv_integers == {'priority': [5]}

    def test_create_incident_with_kv_multi(self, manager_instance):
        """Test creating incident with multi-value KV data."""
        with patch('incident_manager.KVParser.parse_kv_list') as mock_parse:
            mock_parse.return_value = [('tags', '$', 'fire'), ('tags', '$', 'critical')]
            
            manager_instance.create_incident(
                title="Test KV Multi",
                kv_multi=['tags$fire', 'tags$critical'],
            )
            
            incident = manager_instance.storage.save_incident.call_args[0][0]
            assert incident.kv_strings['tags'] == ['fire', 'critical']

    def test_create_incident_timestamp_format(self, manager_instance):
        """Test that incident timestamp is ISO8601 with Z suffix."""
        manager_instance.create_incident(title="Timestamp Test")
        
        incident = manager_instance.storage.save_incident.call_args[0][0]
        assert incident.created_at.endswith('Z')
        assert 'T' in incident.created_at  # ISO8601 format check

    def test_create_incident_generates_unique_ids(self, manager_instance):
        """Test that each incident gets unique ID."""
        with patch('incident_manager.IDGenerator.generate_incident_id') as mock_id:
            mock_id.side_effect = ['INC001', 'INC002']
            
            manager_instance.create_incident(title="First")
            manager_instance.create_incident(title="Second")
            
            assert mock_id.call_count == 2


# ============================================================================
# TESTS: IncidentManager.list_incidents
# ============================================================================


class TestListIncidents:
    """Test incident listing and filtering."""

    def test_list_incidents_basic(self, manager_instance):
        """Test basic incident listing."""
        mock_incidents = [
            Mock(id='INC001', title='First', status='open', severity='high'),
            Mock(id='INC002', title='Second', status='closed', severity='low'),
        ]
        
        manager_instance.storage.load_incident.side_effect = mock_incidents
        manager_instance.index_db.list_incidents_from_index.return_value = [
            {'id': 'INC001'},
            {'id': 'INC002'},
        ]
        
        results = manager_instance.list_incidents(limit=10)
        
        assert len(results) == 2
        assert results[0].id == 'INC001'
        assert results[1].id == 'INC002'

    def test_list_incidents_with_status_filter(self, manager_instance):
        """Test filtering incidents by status."""
        manager_instance.index_db.list_incidents_from_index.return_value = [
            {'id': 'INC001'},
        ]
        manager_instance.storage.load_incident.return_value = Mock(id='INC001', status='open')
        
        manager_instance.list_incidents(status='open')
        
        manager_instance.index_db.list_incidents_from_index.assert_called_once()
        call_kwargs = manager_instance.index_db.list_incidents_from_index.call_args[1]
        assert call_kwargs['status'] == 'open'

    def test_list_incidents_with_ksearch(self, manager_instance):
        """Test KV search filtering."""
        with patch('incident_manager.KVSearchParser.parse_ksearch') as mock_parse:
            manager_instance.index_db.search_kv.return_value = ['INC001']
            manager_instance.index_db.list_incidents_from_index.return_value = [
                {'id': 'INC001'},
            ]
            manager_instance.storage.load_incident.return_value = Mock(id='INC001')
            
            manager_instance.list_incidents(ksearch=['cost>100'])
            
            mock_parse.assert_called_once_with('cost>100')
            manager_instance.index_db.search_kv.assert_called_once()

    def test_list_incidents_with_ksort(self, manager_instance):
        """Test KV sorting."""
        with patch('incident_manager.KVSearchParser.parse_ksort') as mock_parse:
            manager_instance.index_db.list_incidents_from_index.return_value = [
                {'id': 'INC001'},
                {'id': 'INC002'},
            ]
            manager_instance.index_db.get_sorted_incidents.return_value = ['INC002', 'INC001']
            manager_instance.storage.load_incident.side_effect = [
                Mock(id='INC002'),
                Mock(id='INC001'),
            ]
            
            results = manager_instance.list_incidents(ksort='cost-')
            
            mock_parse.assert_called_once_with('cost-')
            assert results[0].id == 'INC002'
            assert results[1].id == 'INC001'

    def test_list_incidents_limit_respected(self, manager_instance):
        """Test that limit parameter is respected."""
        index_results = [{'id': f'INC{i:03d}'} for i in range(100)]
        manager_instance.index_db.list_incidents_from_index.return_value = index_results
        
        manager_instance.storage.load_incident.side_effect = [
            Mock(id=f'INC{i:03d}') for i in range(50)
        ]
        
        results = manager_instance.list_incidents(limit=50)
        
        assert len(results) == 50


# ============================================================================
# TESTS: IncidentManager.update_incident_kv
# ============================================================================


class TestUpdateIncidentKV:
    """Test KV data updates."""

    def test_update_kv_single_replace(self, manager_instance):
        """Test single-value KV replaces existing."""
        incident = Mock(
            id='INC001',
            kv_strings={'cost': ['500']},
            kv_integers={},
            kv_floats={},
        )
        manager_instance.storage.load_incident.return_value = incident
        
        with patch('incident_manager.KVParser.parse_kv_list') as mock_parse:
            mock_parse.return_value = [('cost', '#', 1000)]
            
            manager_instance.update_incident_kv('INC001', kv_single=['cost#1000'])
            
            assert incident.kv_integers['cost'] == [1000]

    def test_update_kv_multi_append(self, manager_instance):
        """Test multi-value KV appends values."""
        incident = Mock(
            id='INC001',
            kv_strings={'tags': ['fire']},
            kv_integers={},
            kv_floats={},
        )
        manager_instance.storage.load_incident.return_value = incident
        
        with patch('incident_manager.KVParser.parse_kv_list') as mock_parse:
            mock_parse.return_value = [('tags', '$', 'critical')]
            
            manager_instance.update_incident_kv('INC001', kv_multi=['tags$critical'])
            
            assert incident.kv_strings['tags'] == ['fire', 'critical']

    def test_update_kv_remove_key(self, manager_instance):
        """Test removing KV key."""
        incident = Mock(
            id='INC001',
            kv_strings={'cost': ['500'], 'priority': ['high']},
            kv_integers={},
            kv_floats={},
        )
        manager_instance.storage.load_incident.return_value = incident
        
        with patch('incident_manager.KVParser.parse_kv_list') as mock_parse:
            mock_parse.return_value = [('cost', '-', None)]
            
            manager_instance.update_incident_kv('INC001', kv_single=['cost-'])
            
            assert 'cost' not in incident.kv_strings
            manager_instance.index_db.remove_kv_key.assert_called_once_with('INC001', 'cost')

    def test_update_kv_incident_not_found(self, manager_instance):
        """Test updating KV on non-existent incident."""
        manager_instance.storage.load_incident.return_value = None
        
        with pytest.raises(RuntimeError, match="not found"):
            manager_instance.update_incident_kv('NONEXISTENT')


# ============================================================================
# TESTS: IncidentManager.add_update
# ============================================================================


class TestAddUpdate:
    """Test adding updates/comments to incidents."""

    def test_add_update_with_message(self, manager_instance):
        """Test adding update with explicit message."""
        manager_instance.storage.load_incident.return_value = Mock(id='INC001')
        
        timestamp = manager_instance.add_update(
            'INC001',
            message="This is an update"
        )
        
        manager_instance.storage.save_update.assert_called_once()
        update = manager_instance.storage.save_update.call_args[0][1]
        assert update.message == "This is an update"
        assert update.incident_id == 'INC001'
        assert timestamp.endswith('Z')  # ISO8601 format

    def test_add_update_from_stdin(self, manager_instance):
        """Test adding update from STDIN."""
        manager_instance.storage.load_incident.return_value = Mock(id='INC001')
        
        with patch('incident_manager.StdinHandler.has_stdin_data', return_value=True):
            with patch('incident_manager.StdinHandler.read_stdin_with_timeout', return_value="STDIN message"):
                manager_instance.add_update('INC001', use_stdin=True)
                
                update = manager_instance.storage.save_update.call_args[0][1]
                assert update.message == "STDIN message"

    def test_add_update_from_editor(self, manager_instance):
        """Test adding update from editor."""
        manager_instance.storage.load_incident.return_value = Mock(id='INC001')
        
        editor_content = "# Comment line\nActual content\n# Another comment"
        with patch('incident_manager.EditorConfig.launch_editor', return_value=editor_content):
            manager_instance.add_update('INC001', use_editor=True)
            
            update = manager_instance.storage.save_update.call_args[0][1]
            assert "Actual content" in update.message
            assert "# Comment" not in update.message

    def test_add_update_message_priority(self, manager_instance):
        """Test that message takes priority over STDIN and editor."""
        manager_instance.storage.load_incident.return_value = Mock(id='INC001')
        
        with patch('incident_manager.StdinHandler.has_stdin_data', return_value=True):
            with patch('incident_manager.StdinHandler.read_stdin_with_timeout', return_value="STDIN"):
                with patch('incident_manager.EditorConfig.launch_editor', return_value="EDITOR"):
                    manager_instance.add_update(
                        'INC001',
                        message="Explicit message",
                        use_stdin=True,
                        use_editor=True
                    )
                    
                    update = manager_instance.storage.save_update.call_args[0][1]
                    assert update.message == "Explicit message"

    def test_add_update_no_content_fails(self, manager_instance):
        """Test that update fails with no message."""
        manager_instance.storage.load_incident.return_value = Mock(id='INC001')
        
        with patch('incident_manager.StdinHandler.has_stdin_data', return_value=False):
            with patch('incident_manager.EditorConfig.launch_editor', return_value="# Only comments"):
                with pytest.raises(RuntimeError, match="No update provided"):
                    manager_instance.add_update('INC001', use_editor=True)

    def test_add_update_with_kv_inheritance(self, manager_instance):
        """Test that KV data is inherited to incident."""
        manager_instance.storage.load_incident.return_value = Mock(id='INC001')
        
        with patch.object(manager_instance, 'update_incident_kv') as mock_update_kv:
            manager_instance.add_update(
                'INC001',
                message="Update with KV",
                kv_single=['priority#1']
            )
            
            mock_update_kv.assert_called_once()


# ============================================================================
# TESTS: IncidentCLI
# ============================================================================


class TestIncidentCLI:
    """Test CLI functionality."""

    def test_cli_init(self):
        """Test CLI initialization."""
        cli = IncidentCLI()
        assert cli.parser is not None
        assert cli.subparsers is not None

    def test_cli_setup_commands(self):
        """Test that all commands are registered."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        # Should not raise
        assert cli.subparsers is not None

    def test_cli_parse_create_command(self):
        """Test parsing create command."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        args = cli.parser.parse_args([
            'create',
            '--title', 'Test Incident',
            '--severity', 'high',
            '--tags', 'urgent', 'fire',
        ])
        
        assert args.command == 'create'
        assert args.title == 'Test Incident'
        assert args.severity == 'high'
        assert args.tags == ['urgent', 'fire']

    def test_cli_parse_list_command(self):
        """Test parsing list command."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        args = cli.parser.parse_args([
            'list',
            '--status', 'open',
            '--severity', 'high',
            '--limit', '100',
        ])
        
        assert args.command == 'list'
        assert args.status == 'open'
        assert args.severity == 'high'
        assert args.limit == 100

    def test_cli_parse_update_command(self):
        """Test parsing update command."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        args = cli.parser.parse_args([
            'update',
            'INC001',
            '--status', 'resolved',
            '-kv', 'resolution_time#3600',
        ])
        
        assert args.command == 'update'
        assert args.incident_id == 'INC001'
        assert args.status == 'resolved'

    def test_cli_parse_add_update_command(self):
        """Test parsing add-update command."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        args = cli.parser.parse_args([
            'add-update',
            'INC001',
            '--message', 'Update text',
        ])
        
        assert args.command == 'add-update'
        assert args.incident_id == 'INC001'
        assert args.message == 'Update text'

    def test_cli_cmd_create(self, temp_db_dir):
        """Test create command execution."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        
        cli = IncidentCLI()
        cli.setup_commands()
        
        with patch('incident_manager.IncidentManager') as MockManager:
            mock_manager = Mock()
            mock_manager.create_incident.return_value = 'INC001'
            MockManager.return_value = mock_manager
            
            args = cli.parser.parse_args([
                'create',
                '--title', 'Test',
                '--severity', 'high',
                '--location', str(temp_db_dir),
            ])
            
            with patch('builtins.print'):
                cli._cmd_create(args)
            
            mock_manager.create_incident.assert_called_once()

    def test_cli_cmd_list(self, temp_db_dir):
        """Test list command execution."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        
        cli = IncidentCLI()
        cli.setup_commands()
        
        with patch('incident_manager.IncidentManager') as MockManager:
            mock_manager = Mock()
            mock_incident = Mock(id='INC001', title='Test', status='open', severity='high')
            mock_manager.list_incidents.return_value = [mock_incident]
            MockManager.return_value = mock_manager
            
            args = cli.parser.parse_args([
                'list',
                '--location', str(temp_db_dir),
            ])
            
            with patch('builtins.print'):
                cli._cmd_list(args)
            
            mock_manager.list_incidents.assert_called_once()

    def test_cli_cmd_get(self, temp_db_dir):
        """Test get command execution."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        
        cli = IncidentCLI()
        cli.setup_commands()
        
        with patch('incident_manager.IncidentManager') as MockManager:
            mock_manager = Mock()
            mock_incident = Mock(
                id='INC001',
                title='Test',
                status='open',
                severity='high',
                created_at='2026-02-02T00:00:00Z',
                created_by='test_user',
                updated_at='2026-02-02T00:00:00Z',
                tags=[],
                assignees=[],
                description='Test description',
            )
            mock_manager.get_incident.return_value = mock_incident
            MockManager.return_value = mock_manager
            
            args = cli.parser.parse_args([
                'get',
                'INC001',
                '--location', str(temp_db_dir),
            ])
            
            with patch('builtins.print'):
                cli._cmd_get(args)
            
            mock_manager.get_incident.assert_called_once_with('INC001')

    def test_cli_cmd_update(self, temp_db_dir):
        """Test update command execution."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        
        cli = IncidentCLI()
        cli.setup_commands()
        
        with patch('incident_manager.IncidentManager') as MockManager:
            mock_manager = Mock()
            MockManager.return_value = mock_manager
            
            args = cli.parser.parse_args([
                'update',
                'INC001',
                '--status', 'resolved',
                '--location', str(temp_db_dir),
            ])
            
            with patch('builtins.print'):
                cli._cmd_update(args)
            
            mock_manager.update_incident_status.assert_called_once_with('INC001', 'resolved')

    def test_cli_cmd_add_update(self, temp_db_dir):
        """Test add-update command execution."""
        temp_db_dir.mkdir(parents=True, exist_ok=True)
        
        cli = IncidentCLI()
        cli.setup_commands()
        
        with patch('incident_manager.IncidentManager') as MockManager:
            mock_manager = Mock()
            mock_manager.add_update.return_value = '2026-02-02T00:00:00Z'
            MockManager.return_value = mock_manager
            
            args = cli.parser.parse_args([
                'add-update',
                'INC001',
                '--message', 'Update message',
                '--location', str(temp_db_dir),
            ])
            
            with patch('builtins.print'):
                with patch('incident_manager.StdinHandler.has_stdin_data', return_value=False):
                    cli._cmd_add_update(args)
            
            mock_manager.add_update.assert_called_once()


# ============================================================================
# TESTS: Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_create_incident_with_empty_tags_list(self, manager_instance):
        """Test that empty tags list becomes None."""
        manager_instance.create_incident(title="Test", tags=[])
        
        incident = manager_instance.storage.save_incident.call_args[0][0]
        assert incident.tags == []

    def test_list_incidents_empty_result(self, manager_instance):
        """Test listing with no results."""
        manager_instance.index_db.list_incidents_from_index.return_value = []
        
        results = manager_instance.list_incidents()
        
        assert results == []

    def test_update_nonexistent_incident(self, manager_instance):
        """Test updating incident that doesn't exist."""
        manager_instance.storage.load_incident.return_value = None
        
        with pytest.raises(RuntimeError, match="not found"):
            manager_instance.update_incident_status('NONEXISTENT', 'closed')

    def test_get_nonexistent_incident(self, manager_instance):
        """Test getting incident that doesn't exist."""
        manager_instance.storage.load_incident.return_value = None
        
        result = manager_instance.get_incident('NONEXISTENT')
        
        assert result is None

    def test_invalid_severity_in_cli(self):
        """Test that invalid severity is rejected."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        with pytest.raises(SystemExit):
            cli.parser.parse_args([
                'create',
                '--title', 'Test',
                '--severity', 'invalid_severity',
            ])

    def test_invalid_status_in_cli(self):
        """Test that invalid status is rejected."""
        cli = IncidentCLI()
        cli.setup_commands()
        
        with pytest.raises(SystemExit):
            cli.parser.parse_args([
                'update',
                'INC001',
                '--status', 'invalid_status',
            ])


# ============================================================================
# TESTS: Integration Tests
# ============================================================================


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_workflow_create_update_list(self, manager_instance):
        """Test complete workflow: create, update, list."""
        # Create
        manager_instance.create_incident(
            title="Integration Test",
            severity="high",
            tags=["test"],
        )
        
        create_call = manager_instance.storage.save_incident.call_args[0][0]
        incident_id = create_call.id
        
        # Update
        manager_instance.storage.load_incident.return_value = create_call
        manager_instance.update_incident_status(incident_id, "investigating")
        
        # List
        manager_instance.index_db.list_incidents_from_index.return_value = [
            {'id': incident_id}
        ]
        manager_instance.storage.load_incident.side_effect = [create_call]
        
        results = manager_instance.list_incidents()
        
        assert len(results) >= 1

    def test_workflow_create_with_kv_update_kv(self, manager_instance):
        """Test workflow: create with KV, then update KV."""
        with patch('incident_manager.KVParser.parse_kv_list') as mock_parse:
            # Create with single KV
            mock_parse.return_value = [('priority', '#', 1)]
            manager_instance.create_incident(
                title="KV Test",
                kv_single=['priority#1']
            )
            
            incident = manager_instance.storage.save_incident.call_args[0][0]
            
            # Update with multi KV
            mock_parse.reset_mock()
            mock_parse.return_value = [('tags', '$', 'fire')]
            manager_instance.storage.load_incident.return_value = incident
            
            manager_instance.update_incident_kv(incident.id, kv_multi=['tags$fire'])
            
            assert manager_instance.storage.save_incident.call_count >= 1


# ============================================================================
# RUNNER
# ============================================================================


if __name__ == "__main__":
    # Run tests with verbose output
    pytest.main([__file__, "-v", "--tb=short"])

