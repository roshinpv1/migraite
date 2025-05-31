from pocketflow import Flow
# Import Spring migration node classes from nodes.py
from nodes import (
    FetchRepo,
    SpringMigrationAnalyzer,
    DependencyCompatibilityAnalyzer,
    MigrationPlanGenerator,
    MigrationReportGenerator,
    FileBackupManager,
    MigrationChangeGenerator,
    ChangeConfirmationNode,
    MigrationChangeApplicator,
    GitOperationsManager
)

def create_spring_migration_flow():
    """Create Spring migration flow with analysis, planning and optional change application."""

    # Create nodes
    fetch_repo = FetchRepo()
    analyzer = SpringMigrationAnalyzer()
    dependency_analyzer = DependencyCompatibilityAnalyzer()
    plan_generator = MigrationPlanGenerator()
    backup_manager = FileBackupManager()
    change_generator = MigrationChangeGenerator()
    confirmation_node = ChangeConfirmationNode()
    change_applicator = MigrationChangeApplicator()
    git_operations = GitOperationsManager()
    report_generator = MigrationReportGenerator()
    
    # Connect the basic analysis flow
    fetch_repo >> analyzer
    analyzer >> dependency_analyzer
    dependency_analyzer >> plan_generator
    plan_generator >> backup_manager
    backup_manager >> change_generator
    change_generator >> confirmation_node
    
    # Branch based on user confirmation
    confirmation_node - "apply_changes" >> change_applicator
    confirmation_node - "skip_changes" >> report_generator
    
    # After applying changes, run Git operations then report
    change_applicator >> git_operations
    git_operations >> report_generator
    
    return Flow(start=fetch_repo)
