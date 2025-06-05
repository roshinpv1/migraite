#!/usr/bin/env python3
"""
Recovery script for Spring Migration Tool
Restores files from backup when migration corrupts the working directory.
"""

import os
import json
import shutil
import argparse
from pathlib import Path

def find_latest_backup():
    """Find the most recent backup directory."""
    migration_dir = Path("migration_analysis")
    if not migration_dir.exists():
        return None, None
    
    backup_dirs = [d for d in migration_dir.iterdir() if d.name.startswith("piggymetrics_backup_")]
    if not backup_dirs:
        return None, None
    
    # Sort by timestamp in directory name
    backup_dirs.sort(key=lambda x: x.name.split("_")[-2:], reverse=True)
    latest_backup = backup_dirs[0]
    
    # Find corresponding migration directory
    timestamp = "_".join(latest_backup.name.split("_")[-2:])
    migration_workspace = migration_dir / f"piggymetrics_migration_{timestamp}"
    
    return latest_backup, migration_workspace

def restore_from_backup(backup_dir, target_dir, dry_run=False):
    """Restore files from backup to target directory."""
    backup_path = Path(backup_dir)
    target_path = Path(target_dir)
    
    if not backup_path.exists():
        print(f"❌ Backup directory not found: {backup_path}")
        return False
    
    # Read backup manifest
    manifest_file = backup_path / "backup_manifest.json"
    if not manifest_file.exists():
        print(f"❌ Backup manifest not found: {manifest_file}")
        return False
    
    with open(manifest_file, 'r') as f:
        backup_info = json.load(f)
    
    print(f"📦 Restoring from backup: {backup_path}")
    print(f"🎯 Target directory: {target_path}")
    
    if dry_run:
        print("🔍 DRY RUN - showing what would be restored:")
    
    restored_count = 0
    
    # Create target directory
    if not dry_run:
        target_path.mkdir(parents=True, exist_ok=True)
    
    # Restore each file
    for file_info in backup_info.get("migration_files", []):
        original_path = file_info["original_path"]
        
        # Find corresponding backup file (flattened name)
        backup_filename = original_path.replace("/", "_").replace("\\", "_")
        backup_file_path = backup_path / backup_filename
        
        if not backup_file_path.exists():
            print(f"⚠️  Backup file not found: {backup_filename}")
            continue
        
        # Target file path (restore directory structure)
        target_file_path = target_path / original_path
        
        if dry_run:
            print(f"   Would restore: {original_path}")
        else:
            # Create directories if needed
            target_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file from backup
            shutil.copy2(backup_file_path, target_file_path)
            print(f"   ✅ Restored: {original_path}")
        
        restored_count += 1
    
    if dry_run:
        print(f"\n🔍 Would restore {restored_count} files")
    else:
        print(f"\n✅ Successfully restored {restored_count} files")
        
        # Copy backup manifest to target for reference
        shutil.copy2(manifest_file, target_path / "restored_from_backup.json")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Recover from Spring Migration Tool backup")
    parser.add_argument("--backup", help="Specific backup directory to restore from")
    parser.add_argument("--target", help="Target directory to restore to")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be restored without actually doing it")
    parser.add_argument("--list-backups", action="store_true", help="List available backups")
    
    args = parser.parse_args()
    
    if args.list_backups:
        print("📂 Available backups:")
        migration_dir = Path("migration_analysis")
        if migration_dir.exists():
            backup_dirs = [d for d in migration_dir.iterdir() if d.name.startswith("piggymetrics_backup_")]
            backup_dirs.sort(key=lambda x: x.name.split("_")[-2:], reverse=True)
            
            for i, backup_dir in enumerate(backup_dirs):
                timestamp = "_".join(backup_dir.name.split("_")[-2:])
                marker = "🕒 LATEST" if i == 0 else ""
                print(f"   {backup_dir.name} {marker}")
        else:
            print("   No migration_analysis directory found")
        return
    
    # Auto-detect latest backup if not specified
    if not args.backup:
        latest_backup, migration_workspace = find_latest_backup()
        if not latest_backup:
            print("❌ No backups found. Run migration analysis first.")
            return
        
        backup_dir = latest_backup
        target_dir = migration_workspace if not args.target else args.target
        
        print(f"🔍 Auto-detected latest backup: {latest_backup.name}")
    else:
        backup_dir = Path(args.backup)
        target_dir = Path(args.target) if args.target else backup_dir.parent / backup_dir.name.replace("backup", "migration")
    
    print(f"📦 Backup: {backup_dir}")
    print(f"🎯 Target: {target_dir}")
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No files will be modified")
    
    # Confirm before proceeding (unless dry run)
    if not args.dry_run:
        confirm = input("\n❓ Proceed with restoration? [y/N]: ").lower().strip()
        if confirm != 'y':
            print("❌ Restoration cancelled")
            return
    
    # Perform restoration
    success = restore_from_backup(backup_dir, target_dir, args.dry_run)
    
    if success and not args.dry_run:
        print(f"\n🎉 Recovery completed!")
        print(f"📁 Files restored to: {target_dir}")
        print(f"💡 You can now re-run the migration tool or manually review the files")
    elif success and args.dry_run:
        print(f"\n✅ Dry run completed - backup appears intact and recoverable")

if __name__ == "__main__":
    main() 