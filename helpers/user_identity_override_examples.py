#!/usr/bin/env python3
"""
Example: User Identity Override in JSON IO Mode

Demonstrates how to use the 'id' field to override user identity
on a per-command basis in aver JSON IO mode.
"""

import subprocess
import json
import sys


class AverIOClient:
    """Client for aver JSON IO mode with user identity override support."""
    
    def __init__(self, aver_path='aver', location=None):
        """
        Initialize the client.
        
        Args:
            aver_path: Path to aver executable
            location: Optional database location
        """
        cmd = [aver_path, 'json', 'io']
        if location:
            cmd.extend(['--location', location])
        
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
    
    def execute(self, command, params=None, user_id=None):
        """
        Execute a command with optional user identity override.
        
        Args:
            command: Command name
            params: Command parameters dict
            user_id: Optional dict with 'handle' and 'email' keys
            
        Returns:
            Result dict from command
            
        Raises:
            RuntimeError: If command fails
        """
        request = {
            'command': command,
            'params': params or {}
        }
        
        # Add user identity override if provided
        if user_id:
            if not isinstance(user_id, dict):
                raise ValueError("user_id must be a dict")
            if 'handle' not in user_id or 'email' not in user_id:
                raise ValueError("user_id must have 'handle' and 'email' keys")
            request['id'] = user_id
        
        # Send request
        self.process.stdin.write(json.dumps(request) + '\n')
        self.process.stdin.flush()
        
        # Read response
        response_line = self.process.stdout.readline()
        if not response_line:
            raise RuntimeError("No response from aver")
        
        response = json.loads(response_line)
        
        if not response.get('success'):
            raise RuntimeError(response.get('error', 'Unknown error'))
        
        return response.get('result')
    
    def close(self):
        """Close the connection."""
        self.process.stdin.close()
        self.process.wait()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def example_multi_user_workflow():
    """
    Example: Multi-user workflow where different users create records.
    
    Useful for:
    - Customer support systems
    - Issue tracking across teams
    - Automated systems acting on behalf of users
    """
    print("=== Multi-User Workflow Example ===\n")
    
    users = [
        {'handle': 'alice', 'email': 'alice@example.com'},
        {'handle': 'bob', 'email': 'bob@example.com'},
        {'handle': 'charlie', 'email': 'charlie@example.com'}
    ]
    
    tasks = [
        {'title': 'Fix login bug', 'priority': 'high', 'component': 'auth'},
        {'title': 'Update docs', 'priority': 'low', 'component': 'docs'},
        {'title': 'Add tests', 'priority': 'medium', 'component': 'testing'}
    ]
    
    with AverIOClient() as client:
        created_records = []
        
        for user, task in zip(users, tasks):
            print(f"Creating task for {user['handle']}: {task['title']}")
            
            result = client.execute(
                'import-record',
                {
                    'content': f"Task assigned to {user['handle']}",
                    'fields': {
                        'title': task['title'],
                        'status': 'open',
                        'priority': task['priority'],
                        'component': task['component']
                    }
                },
                user_id=user
            )
            
            record_id = result['record_id']
            created_records.append(record_id)
            print(f"  ✓ Created {record_id} as {user['handle']}\n")
        
        print(f"Created {len(created_records)} records with different user identities")
        return created_records


def example_service_account():
    """
    Example: Service account creating automated records.
    
    Useful for:
    - Scheduled tasks
    - Monitoring systems
    - Backup processes
    - CI/CD pipelines
    """
    print("\n=== Service Account Example ===\n")
    
    service_identity = {
        'handle': 'backup-service',
        'email': 'backup@example.com'
    }
    
    with AverIOClient() as client:
        # Service creates a status record
        result = client.execute(
            'import-record',
            {
                'content': 'Daily backup completed successfully\n\n- 1000 files backed up\n- 5GB total size\n- Duration: 2m 15s',
                'fields': {
                    'title': 'Daily Backup - 2024-01-15',
                    'status': 'resolved',
                    'category': 'automation'
                }
            },
            user_id=service_identity
        )
        
        print(f"Service account created record: {result['record_id']}")
        print(f"  Author: {service_identity['handle']}")
        return result['record_id']


def example_customer_support_bot():
    """
    Example: Support bot creating records on behalf of customers.
    
    Useful for:
    - Chatbots
    - Support ticket systems
    - Email-to-ticket automation
    """
    print("\n=== Customer Support Bot Example ===\n")
    
    # Simulate tickets from different customers
    tickets = [
        {
            'customer': {'handle': 'customer1', 'email': 'customer1@external.com'},
            'issue': 'Cannot reset password',
            'priority': 'high'
        },
        {
            'customer': {'handle': 'customer2', 'email': 'customer2@external.com'},
            'issue': 'Feature request: dark mode',
            'priority': 'low'
        }
    ]
    
    with AverIOClient() as client:
        for ticket in tickets:
            print(f"Creating ticket for {ticket['customer']['handle']}")
            
            result = client.execute(
                'import-record',
                {
                    'content': f"Customer reported: {ticket['issue']}",
                    'fields': {
                        'title': ticket['issue'],
                        'status': 'open',
                        'priority': ticket['priority'],
                        'source': 'customer_portal'
                    }
                },
                user_id=ticket['customer']
            )
            
            print(f"  ✓ Ticket {result['record_id']} created\n")


def example_testing_different_users():
    """
    Example: Testing with different user identities.
    
    Useful for:
    - Integration tests
    - Permission testing
    - User flow testing
    """
    print("\n=== Testing Example ===\n")
    
    test_users = [
        {'handle': 'admin-test', 'email': 'admin@test.com'},
        {'handle': 'user-test', 'email': 'user@test.com'},
        {'handle': 'guest-test', 'email': 'guest@test.com'}
    ]
    
    with AverIOClient() as client:
        for user in test_users:
            print(f"Testing as {user['handle']}")
            
            # Create test record
            result = client.execute(
                'import-record',
                {
                    'content': f"Test record for {user['handle']}",
                    'fields': {
                        'title': f"Test - {user['handle']}",
                        'status': 'open',
                        'test_run': 'integration_test_001'
                    }
                },
                user_id=user
            )
            
            record_id = result['record_id']
            
            # Verify we can read it back
            exported = client.execute('export-record', {'record_id': record_id})
            
            created_by = exported['fields'].get('created_by')
            print(f"  ✓ Record {record_id} created_by: {created_by}\n")


def example_mixed_usage():
    """
    Example: Mix of default identity and overrides.
    
    Shows that you can use both default and override in the same session.
    """
    print("\n=== Mixed Usage Example ===\n")
    
    special_user = {'handle': 'special-user', 'email': 'special@example.com'}
    
    with AverIOClient() as client:
        # Create with default identity
        print("Creating record with default identity...")
        default_result = client.execute(
            'import-record',
            {
                'content': 'Regular record with default user',
                'fields': {
                    'title': 'Default User Record',
                    'status': 'open'
                }
            }
        )
        print(f"  ✓ Created {default_result['record_id']} (default identity)\n")
        
        # Create with override
        print("Creating record with identity override...")
        override_result = client.execute(
            'import-record',
            {
                'content': 'Special record with override',
                'fields': {
                    'title': 'Override User Record',
                    'status': 'open'
                }
            },
            user_id=special_user
        )
        print(f"  ✓ Created {override_result['record_id']} (as {special_user['handle']})\n")
        
        # Create another with default
        print("Creating another record with default identity...")
        default_result2 = client.execute(
            'import-record',
            {
                'content': 'Back to default',
                'fields': {
                    'title': 'Back to Default',
                    'status': 'open'
                }
            }
        )
        print(f"  ✓ Created {default_result2['record_id']} (default identity)\n")
        
        print("Mix of default and override identities works seamlessly!")


def main():
    """Run all examples."""
    print("╔════════════════════════════════════════════════════════╗")
    print("║  Aver JSON IO - User Identity Override Examples       ║")
    print("╚════════════════════════════════════════════════════════╝\n")
    
    try:
        # Run examples
        example_multi_user_workflow()
        example_service_account()
        example_customer_support_bot()
        example_testing_different_users()
        example_mixed_usage()
        
        print("\n✓ All examples completed successfully!")
        
    except RuntimeError as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        print("\nNote: These examples require an initialized aver database.", file=sys.stderr)
        print("Run 'aver admin init' first if you haven't already.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
