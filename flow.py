from pocketflow import Flow
# Import Spring migration node classes from nodes.py
from nodes import (
    FetchRepo,
    SpringMigrationAnalyzer,
    MigrationPlanGenerator,
    EnhancedFileBackupManager,
    MigrationChangeGenerator,
    MigrationFileApplicator,
    GitMigrationManager,
    MigrationReportGenerator
)

def create_spring_migration_flow():
    """Create Spring migration flow with analysis, planning and optional change application."""

    # Create nodes
    fetch_repo = FetchRepo()
    analyzer = SpringMigrationAnalyzer()
    plan_generator = MigrationPlanGenerator()
    backup_manager = EnhancedFileBackupManager()
    change_generator = MigrationChangeGenerator()
    file_applicator = MigrationFileApplicator()
    git_operations = GitMigrationManager()
    report_generator = MigrationReportGenerator()

    # Connect the analysis and application flow
    fetch_repo >> analyzer
    analyzer >> plan_generator
    plan_generator >> backup_manager
    backup_manager >> change_generator
    change_generator >> file_applicator
    file_applicator >> git_operations
    git_operations >> report_generator
    
    return Flow(start=fetch_repo)
