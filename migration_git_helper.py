#!/usr/bin/env python3
"""
Spring Migration Git Helper

This script helps you manage git operations for your Spring migration changes.
It provides an easy way to review, commit, and apply migration changes.
"""

import os
import sys
import subprocess
import json
import shutil
from pathlib import Path


class MigrationGitHelper:
    def __init__(self, migration_workspace_path=None):
        """Initialize the git helper."""
        if migration_workspace_path:
            self.workspace = Path(migration_workspace_path)
        else:
            # Auto-detect migration workspace
            self.workspace = self._find_migration_workspace()
        
        if not self.workspace or not self.workspace.exists():
            raise ValueError("Migration workspace not found. Please specify the path.")
        
        print(f"🏠 Using migration workspace: {self.workspace}")
    
    def _find_migration_workspace(self):
        """Auto-detect the most recent migration workspace."""
        current_dir = Path.cwd()
        
        # Look for directories ending with _migration_<timestamp>
        migration_dirs = []
        for item in current_dir.iterdir():
            if item.is_dir() and "_migration_" in item.name:
                migration_dirs.append(item)
        
        if migration_dirs:
            # Return the most recent one
            migration_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return migration_dirs[0]
        
        return None
    
    def show_status(self):
        """Show current git status and change summary."""
        print("\n📊 Git Status")
        print("=" * 50)
        
        os.chdir(self.workspace)
        
        # Show git status
        result = subprocess.run(["git", "status", "--short"], capture_output=True, text=True)
        if result.returncode == 0:
            if result.stdout.strip():
                print("Modified files:")
                print(result.stdout)
            else:
                print("✅ No changes detected")
        
        # Show change statistics
        diff_result = subprocess.run(["git", "diff", "--stat"], capture_output=True, text=True)
        if diff_result.returncode == 0 and diff_result.stdout.strip():
            print("\n📈 Change Summary:")
            print(diff_result.stdout)
    
    def review_changes(self, file_path=None):
        """Review changes in detail."""
        os.chdir(self.workspace)
        
        if file_path:
            print(f"\n📖 Reviewing changes in: {file_path}")
            print("=" * 60)
            subprocess.run(["git", "diff", file_path])
        else:
            print("\n📖 Reviewing all changes")
            print("=" * 40)
            
            # Show file list first
            result = subprocess.run(["git", "diff", "--name-status"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                print("Changed files:")
                print(result.stdout)
                
                response = input("\n🤔 Show detailed diff for all files? [y/N]: ")
                if response.lower() in ['y', 'yes']:
                    subprocess.run(["git", "diff"])
            else:
                print("No changes to review")
    
    def stage_changes(self, file_path=None):
        """Stage changes for commit."""
        os.chdir(self.workspace)
        
        if file_path:
            print(f"📦 Staging file: {file_path}")
            result = subprocess.run(["git", "add", file_path], capture_output=True, text=True)
        else:
            print("📦 Staging all changes...")
            result = subprocess.run(["git", "add", "."], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✅ Changes staged successfully")
        else:
            print(f"❌ Error staging changes: {result.stderr}")
    
    def commit_changes(self, message=None):
        """Commit staged changes."""
        os.chdir(self.workspace)
        
        # Check if there are staged changes
        result = subprocess.run(["git", "diff", "--cached", "--quiet"], capture_output=True)
        if result.returncode == 0:
            print("❌ No staged changes to commit")
            return False
        
        if not message:
            # Generate a default commit message
            message = self._generate_commit_message()
        
        print(f"💾 Committing changes with message: {message[:50]}...")
        
        result = subprocess.run(
            ["git", "commit", "-m", message], 
            capture_output=True, text=True
        )
        
        if result.returncode == 0:
            print("✅ Changes committed successfully!")
            
            # Show commit hash
            hash_result = subprocess.run(
                ["git", "rev-parse", "HEAD"], 
                capture_output=True, text=True
            )
            if hash_result.returncode == 0:
                commit_hash = hash_result.stdout.strip()
                print(f"   Commit hash: {commit_hash[:8]}")
            
            return True
        else:
            print(f"❌ Error committing changes: {result.stderr}")
            return False
    
    def _generate_commit_message(self):
        """Generate a smart commit message based on changes."""
        os.chdir(self.workspace)
        
        # Get change statistics
        stat_result = subprocess.run(
            ["git", "diff", "--cached", "--stat"], 
            capture_output=True, text=True
        )
        
        # Get list of changed files
        files_result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"], 
            capture_output=True, text=True
        )
        
        changed_files = files_result.stdout.strip().split('\n') if files_result.stdout.strip() else []
        
        # Analyze change types
        has_java_files = any(f.endswith('.java') for f in changed_files)
        has_pom_files = any('pom.xml' in f for f in changed_files)
        has_gradle_files = any(f.endswith(('.gradle', '.gradle.kts')) for f in changed_files)
        has_config_files = any(f.endswith(('.properties', '.yml', '.yaml')) for f in changed_files)
        
        # Generate message based on file types
        message_parts = ["Spring 5 to 6 migration - Automated changes", ""]
        
        if has_java_files:
            message_parts.append("- Updated Java source files (javax → jakarta)")
        if has_pom_files or has_gradle_files:
            message_parts.append("- Updated build files and dependencies")
        if has_config_files:
            message_parts.append("- Updated configuration files")
        
        message_parts.extend([
            "",
            f"📊 Files changed: {len(changed_files)}",
            "🤖 Generated by Spring Migration Tool"
        ])
        
        return "\n".join(message_parts)
    
    def create_patch(self, patch_file="migration.patch"):
        """Create a patch file of all changes."""
        os.chdir(self.workspace)
        
        print(f"📋 Creating patch file: {patch_file}")
        
        with open(patch_file, 'w') as f:
            # Write staged changes if any, otherwise unstaged changes
            staged_result = subprocess.run(
                ["git", "diff", "--cached"], 
                capture_output=True, text=True
            )
            
            if staged_result.stdout.strip():
                f.write("# Staged Changes\n")
                f.write(staged_result.stdout)
                f.write("\n\n")
            
            # Write unstaged changes
            unstaged_result = subprocess.run(
                ["git", "diff"], 
                capture_output=True, text=True
            )
            
            if unstaged_result.stdout.strip():
                f.write("# Unstaged Changes\n")
                f.write(unstaged_result.stdout)
        
        print(f"✅ Patch file created: {patch_file}")
        return patch_file
    
    def copy_to_original_project(self, original_project_path, dry_run=False):
        """Copy migration changes back to the original project."""
        original_path = Path(original_project_path)
        
        if not original_path.exists():
            print(f"❌ Original project path does not exist: {original_path}")
            return False
        
        print(f"🔄 Copying changes to original project: {original_path}")
        
        if dry_run:
            print("🧪 DRY RUN - No files will be copied")
        
        os.chdir(self.workspace)
        
        # Get list of changed files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"], 
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            print("❌ Error getting changed files")
            return False
        
        changed_files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        
        if not changed_files:
            print("❌ No changed files to copy")
            return False
        
        copied_count = 0
        skipped_count = 0
        
        for file_path in changed_files:
            if not file_path:  # Skip empty lines
                continue
                
            source_file = self.workspace / file_path
            target_file = original_path / file_path
            
            if not source_file.exists():
                print(f"   ⚠️  Source file not found: {file_path}")
                skipped_count += 1
                continue
            
            # Create target directory if needed
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            if dry_run:
                print(f"   📄 Would copy: {file_path}")
            else:
                try:
                    shutil.copy2(source_file, target_file)
                    print(f"   ✅ Copied: {file_path}")
                    copied_count += 1
                except Exception as e:
                    print(f"   ❌ Error copying {file_path}: {e}")
                    skipped_count += 1
        
        if not dry_run:
            print(f"\n📊 Copy Summary:")
            print(f"   ✅ Copied: {copied_count} files")
            if skipped_count > 0:
                print(f"   ⚠️  Skipped: {skipped_count} files")
        
        return copied_count > 0
    
    def interactive_workflow(self):
        """Interactive git workflow for migration changes."""
        print("\n🎯 Spring Migration Git Helper")
        print("=" * 40)
        print(f"Working with: {self.workspace.name}")
        
        while True:
            print("\n📋 Available actions:")
            print("1. [s] Show status")
            print("2. [r] Review changes")
            print("3. [l] Show line-by-line analysis")
            print("4. [a] Stage all changes")
            print("5. [c] Commit changes")
            print("6. [p] Create patch file")
            print("7. [compare] Compare git diff vs analysis")
            print("8. [export] Export line changes report")
            print("9. [branch] Create migration branch")
            print("")
            print("Advanced:")
            print("- [copy] Copy changes to original project")
            print("- [log] Show commit history")
            print("- [q] Quit")
            
            choice = input("\n🤔 Choose an action: ").strip().lower()
            
            if choice in ['1', 's', 'status']:
                self.show_status()
            
            elif choice in ['2', 'r', 'review']:
                file_path = input("📄 Specific file (or Enter for all): ").strip()
                self.review_changes(file_path if file_path else None)
            
            elif choice in ['3', 'l', 'line']:
                file_path = input("📄 Specific file (or Enter for summary): ").strip()
                if file_path:
                    self.show_file_line_changes(file_path)
                else:
                    self.show_line_by_line_changes()
            
            elif choice in ['4', 'a', 'stage', 'add']:
                file_path = input("📄 Specific file (or Enter for all): ").strip()
                self.stage_changes(file_path if file_path else None)
            
            elif choice in ['5', 'c', 'commit']:
                message = input("💬 Commit message (or press Enter for auto-generated): ").strip()
                self.commit_changes(message if message else None)
            
            elif choice in ['6', 'p', 'patch']:
                patch_name = input("📋 Patch filename (migration.patch): ").strip()
                patch_file = self.create_patch(patch_name if patch_name else "migration.patch")
                print(f"   Patch saved to: {patch_file}")
            
            elif choice in ['7', 'compare']:
                file_path = input("📄 Specific file (or Enter for overview): ").strip()
                self.compare_with_git_diff(file_path if file_path else None)
            
            elif choice in ['8', 'export']:
                filename = input("📄 Report filename (line_changes_report.md): ").strip()
                self.export_line_changes_report(filename if filename else "line_changes_report.md")
            
            elif choice in ['branch', 'b']:
                branch_name = input("🌿 Branch name (or Enter for auto-generated): ").strip()
                self.create_migration_branch(branch_name if branch_name else None)
            
            elif choice in ['copy']:
                original_path = input("📂 Original project path: ").strip()
                if original_path:
                    dry_run = input("🧪 Dry run first? [Y/n]: ").strip().lower() != 'n'
                    if dry_run:
                        self.copy_to_original_project(original_path, dry_run=True)
                        if input("   Proceed with actual copy? [y/N]: ").strip().lower() == 'y':
                            self.copy_to_original_project(original_path, dry_run=False)
                    else:
                        self.copy_to_original_project(original_path, dry_run=False)
            
            elif choice in ['log']:
                os.chdir(self.workspace)
                subprocess.run(["git", "log", "--oneline", "-10"])
            
            elif choice in ['9', 'q', 'quit', 'exit']:
                print("👋 Goodbye!")
                break
            
            else:
                print("❓ Invalid choice. Please try again.")

    def show_line_by_line_changes(self):
        """Show detailed line-by-line changes from migration analysis."""
        try:
            # Look for line change report in analysis
            analysis_dir = self._find_analysis_dir()
            if not analysis_dir:
                print("❌ Migration analysis directory not found")
                print("💡 This requires running the migration analysis first")
                return
            
            # Import the line change viewer
            sys.path.insert(0, str(Path(__file__).parent))
            from view_line_changes import LineChangeViewer
            
            viewer = LineChangeViewer(str(analysis_dir))
            line_report = viewer.load_line_change_report()
            viewer.show_summary(line_report)
            
            print(f"\n💡 For detailed view: python view_line_changes.py --detailed")
            print(f"💡 For specific file: python view_line_changes.py --file <path>")
            
        except Exception as e:
            print(f"❌ Error loading line change report: {e}")
            print(f"💡 Try running: python view_line_changes.py --summary")

    def show_file_line_changes(self, file_path):
        """Show line-by-line changes for a specific file."""
        try:
            analysis_dir = self._find_analysis_dir()
            if not analysis_dir:
                print("❌ Migration analysis directory not found")
                return
            
            sys.path.insert(0, str(Path(__file__).parent))
            from view_line_changes import LineChangeViewer
            
            viewer = LineChangeViewer(str(analysis_dir))
            line_report = viewer.load_line_change_report()
            viewer.show_file_changes(line_report, file_path)
            
        except Exception as e:
            print(f"❌ Error showing file changes: {e}")

    def _find_analysis_dir(self):
        """Find the migration analysis directory."""
        # Look for migration_analysis in current directory
        current_dir = Path.cwd()
        analysis_dir = current_dir / "migration_analysis"
        if analysis_dir.exists():
            return analysis_dir
        
        # Look for analysis directories in current directory
        analysis_dirs = [d for d in current_dir.iterdir() 
                        if d.is_dir() and "migration" in d.name.lower() and "analysis" in d.name.lower()]
        
        if analysis_dirs:
            # Return the most recent one
            analysis_dirs.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            return analysis_dirs[0]
        
        return None

    def compare_with_git_diff(self, file_path=None):
        """Compare migration changes with git diff for the same file."""
        os.chdir(self.workspace)
        
        print(f"\n🔄 Git Diff vs Migration Analysis Comparison")
        print("=" * 60)
        
        if file_path:
            print(f"📄 File: {file_path}")
            
            # Show git diff first
            print(f"\n🔧 Git Changes:")
            git_result = subprocess.run(["git", "diff", file_path], capture_output=True, text=True)
            if git_result.stdout.strip():
                print(git_result.stdout)
            else:
                print("No git changes detected")
            
            # Show line-by-line analysis
            print(f"\n📊 Migration Analysis:")
            self.show_file_line_changes(file_path)
        else:
            # Show overview comparison
            print(f"\n🔧 Git Status:")
            subprocess.run(["git", "status", "--short"])
            
            print(f"\n📊 Migration Analysis Summary:")
            self.show_line_by_line_changes()

    def export_line_changes_report(self, output_file="line_changes_report.md"):
        """Export detailed line changes to a markdown file."""
        try:
            analysis_dir = self._find_analysis_dir()
            if not analysis_dir:
                print("❌ Migration analysis directory not found")
                return
            
            sys.path.insert(0, str(Path(__file__).parent))
            from view_line_changes import LineChangeViewer
            
            viewer = LineChangeViewer(str(analysis_dir))
            line_report = viewer.load_line_change_report()
            
            # Export to file in the workspace
            os.chdir(self.workspace)
            viewer.export_to_file(line_report, output_file)
            
            print(f"✅ Line changes report exported to: {self.workspace / output_file}")
            
        except Exception as e:
            print(f"❌ Error exporting report: {e}")

    def create_migration_branch(self, branch_name=None):
        """Create a git branch for migration changes with optional custom name."""
        os.chdir(self.workspace)
        
        if not (self.workspace / ".git").exists():
            print("❌ No git repository found. Initializing...")
            subprocess.run(["git", "init"], check=True)
            subprocess.run(["git", "config", "user.name", "Spring Migration Tool"], check=True)
            subprocess.run(["git", "config", "user.email", "migration-tool@localhost"], check=True)
            
            # Add and commit existing files first
            subprocess.run(["git", "add", "."], check=True)
            subprocess.run(["git", "commit", "-m", "Initial commit - pre-migration source"], check=True)
            print("   ✅ Git repository initialized")
        
        # Generate branch name if not provided
        if not branch_name:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            branch_name = f"spring-6-migration-{timestamp}"
        
        print(f"🌿 Creating migration branch: {branch_name}")
        
        try:
            # Create and checkout new branch
            result = subprocess.run(["git", "checkout", "-b", branch_name], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ Created and switched to branch: {branch_name}")
                
                # Show current status
                print(f"\n📊 Current status:")
                subprocess.run(["git", "status", "--short"])
                
                print(f"\n💡 Next steps:")
                print(f"   1. Make your migration changes")
                print(f"   2. Stage changes: git add .")
                print(f"   3. Commit changes: git commit -m 'Spring migration changes'")
                print(f"   4. Push branch: git push -u origin {branch_name}")
                
                return branch_name
            else:
                print(f"❌ Failed to create branch: {result.stderr}")
                return None
                
        except subprocess.CalledProcessError as e:
            print(f"❌ Git command failed: {e}")
            return None


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Spring Migration Git Helper - Manage git operations for Spring migration changes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Interactive mode (default)
  python migration_git_helper.py

  # Show git status
  python migration_git_helper.py --status

  # Show line-by-line analysis summary
  python migration_git_helper.py --line-summary

  # Show line changes for specific file
  python migration_git_helper.py --line-file src/main/java/User.java

  # Compare git diff with migration analysis
  python migration_git_helper.py --compare

  # Export line changes report
  python migration_git_helper.py --export-report line_changes.md

  # Create patch file
  python migration_git_helper.py --patch migration.patch

  # Commit all changes with auto-generated message
  python migration_git_helper.py --commit

  # Use specific workspace
  python migration_git_helper.py --workspace ./my_project_migration_20241225
        """
    )
    
    parser.add_argument(
        "--workspace", 
        help="Path to migration workspace directory"
    )
    parser.add_argument(
        "--interactive", "-i", 
        action="store_true", 
        help="Run interactive workflow (default)"
    )
    parser.add_argument(
        "--status", 
        action="store_true", 
        help="Show git status"
    )
    parser.add_argument(
        "--line-summary", "-ls",
        action="store_true",
        help="Show line-by-line change summary"
    )
    parser.add_argument(
        "--line-file", "-lf",
        help="Show line changes for specific file"
    )
    parser.add_argument(
        "--compare", 
        action="store_true", 
        help="Compare git diff with migration analysis"
    )
    parser.add_argument(
        "--export-report", "-e",
        help="Export line changes report to specified file"
    )
    parser.add_argument(
        "--commit", 
        action="store_true", 
        help="Commit all staged changes with auto-generated message"
    )
    parser.add_argument(
        "--patch", 
        help="Create patch file with specified name"
    )
    parser.add_argument(
        "--branch", "-b",
        help="Specify git branch name for migration (default: auto-generated)"
    )
    
    args = parser.parse_args()
    
    try:
        helper = MigrationGitHelper(args.workspace)
        
        # Execute specific action if requested
        if args.status:
            helper.show_status()
        elif args.line_summary:
            helper.show_line_by_line_changes()
        elif args.line_file:
            helper.show_file_line_changes(args.line_file)
        elif args.compare:
            helper.compare_with_git_diff()
        elif args.export_report:
            helper.export_line_changes_report(args.export_report)
        elif args.commit:
            helper.stage_changes()
            helper.commit_changes()
        elif args.patch:
            helper.create_patch(args.patch)
        elif args.branch:
            helper.create_migration_branch(args.branch)
        else:
            # Default to interactive mode
            helper.interactive_workflow()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print(f"\n💡 Make sure you have run the Spring migration analysis first")
        print(f"💡 Run 'python main.py <project_path>' to generate migration changes")
        sys.exit(1)


if __name__ == "__main__":
    main() 