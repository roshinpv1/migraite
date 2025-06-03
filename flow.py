from pocketflow import Flow
# Import Spring migration node classes from nodes.py
from nodes import (
    FetchRepo,
    SpringMigrationAnalyzer,
    MigrationPlanGenerator,
    EnhancedFileBackupManager,
    MigrationChangeGenerator,
    GitMigrationManager
)

def create_spring_migration_flow():
    """Create Spring migration flow with analysis, planning and optional change application."""

    # Create nodes
    fetch_repo = FetchRepo()
    analyzer = SpringMigrationAnalyzer()
    plan_generator = MigrationPlanGenerator()
    backup_manager = EnhancedFileBackupManager()
    change_generator = MigrationChangeGenerator()
    git_operations = GitMigrationManager()
    
    # Connect the basic analysis flow
    fetch_repo >> analyzer
    analyzer >> plan_generator
    plan_generator >> backup_manager
    backup_manager >> change_generator
    change_generator >> git_operations
    
    return Flow(start=fetch_repo)
