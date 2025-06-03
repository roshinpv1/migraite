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
                f.write(staged_result.stdout)
                print("   ✅ Patch created from staged changes")
            else:
                unstaged_result = subprocess.run(
                    ["git", "diff"], 
                    capture_output=True, text=True
                )
                f.write(unstaged_result.stdout)
                print("   ✅ Patch created from unstaged changes")
        
        return os.path.abspath(patch_file)
    
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
        """Run an interactive workflow."""
        while True:
            print("\n🔄 Spring Migration Git Workflow")
            print("=" * 40)
            
            self.show_status()
            
            print("\n🔧 Available Operations:")
            print("  1. Review changes              (r)")
            print("  2. Review specific file        (rf)")
            print("  3. Stage all changes           (s)")
            print("  4. Stage specific file         (sf)")
            print("  5. Commit changes              (c)")
            print("  6. Create patch file           (p)")
            print("  7. Copy to original project    (copy)")
            print("  8. Show git log                (log)")
            print("  9. Exit                        (q)")
            
            choice = input("\n🤔 What would you like to do? ").strip().lower()
            
            if choice in ['1', 'r', 'review']:
                self.review_changes()
            
            elif choice in ['2', 'rf', 'reviewfile']:
                file_path = input("📁 Enter file path: ").strip()
                if file_path:
                    self.review_changes(file_path)
            
            elif choice in ['3', 's', 'stage']:
                self.stage_changes()
            
            elif choice in ['4', 'sf', 'stagefile']:
                file_path = input("📁 Enter file path: ").strip()
                if file_path:
                    self.stage_changes(file_path)
            
            elif choice in ['5', 'c', 'commit']:
                message = input("💬 Commit message (or press Enter for auto-generated): ").strip()
                self.commit_changes(message if message else None)
            
            elif choice in ['6', 'p', 'patch']:
                patch_name = input("📋 Patch filename (migration.patch): ").strip()
                patch_file = self.create_patch(patch_name if patch_name else "migration.patch")
                print(f"   Patch saved to: {patch_file}")
            
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


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Spring Migration Git Helper")
    parser.add_argument(
        "--workspace", 
        help="Path to migration workspace directory"
    )
    parser.add_argument(
        "--interactive", "-i", 
        action="store_true", 
        help="Run interactive workflow"
    )
    parser.add_argument(
        "--status", 
        action="store_true", 
        help="Show git status"
    )
    parser.add_argument(
        "--commit", 
        action="store_true", 
        help="Commit all staged changes"
    )
    parser.add_argument(
        "--patch", 
        help="Create patch file with specified name"
    )
    
    args = parser.parse_args()
    
    try:
        helper = MigrationGitHelper(args.workspace)
        
        if args.interactive:
            helper.interactive_workflow()
        elif args.status:
            helper.show_status()
        elif args.commit:
            helper.stage_changes()
            helper.commit_changes()
        elif args.patch:
            helper.create_patch(args.patch)
        else:
            # Default to interactive mode
            helper.interactive_workflow()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 