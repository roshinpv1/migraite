#!/usr/bin/env python3
"""
Debug script to analyze why migration changes aren't being applied.
This will step through the migration process and show detailed information
about what's happening at each stage.
"""

import os
import json
from nodes import (
    FetchRepo, SpringMigrationAnalyzer, MigrationChangeGenerator, 
    MigrationFileApplicator, EnhancedFileBackupManager
)

def debug_migration_process(directory_path):
    """Debug the migration process step by step."""
    print("🔍 DEBUGGING MIGRATION PROCESS")
    print("=" * 50)
    
    # Create shared state
    shared = {
        "local_dir": directory_path,
        "project_name": os.path.basename(os.path.abspath(directory_path)),
        "apply_changes": True,
        "verbose_mode": True,
        "use_cache": False  # Disable cache for debugging
    }
    
    print(f"📁 Analyzing directory: {directory_path}")
    print(f"📦 Project name: {shared['project_name']}")
    
    # Step 1: Fetch files
    print(f"\n🔍 STEP 1: Fetching Files")
    print("-" * 30)
    
    fetch_node = FetchRepo()
    fetch_prep = fetch_node.prep(shared)
    files = fetch_node.exec(fetch_prep)
    fetch_node.post(shared, fetch_prep, files)
    
    print(f"✅ Found {len(files)} files")
    
    # Show sample of files found
    print(f"\n📄 Sample files found:")
    for i, (path, content) in enumerate(files[:10]):
        print(f"   {i+1}. {path} ({len(content)} chars)")
        # Check for javax imports
        if 'import javax.' in content:
            javax_imports = [line.strip() for line in content.split('\n') if 'import javax.' in line]
            print(f"      🎯 Contains javax imports: {len(javax_imports)}")
            for imp in javax_imports[:3]:
                print(f"         • {imp}")
    
    if len(files) > 10:
        print(f"   ... and {len(files) - 10} more files")
    
    # Step 2: Generate Changes
    print(f"\n🔍 STEP 2: Generating Migration Changes")
    print("-" * 40)
    
    # Create minimal analysis to avoid LLM timeout issues
    shared["migration_analysis"] = {
        "executive_summary": {
            "migration_impact": "Debug analysis",
            "key_blockers": [],
            "recommended_approach": "Debug approach"
        },
        "detailed_analysis": {}
    }
    
    change_gen = MigrationChangeGenerator()
    change_prep = change_gen.prep(shared)
    print(f"   Prep successful: files={len(change_prep[0])}, analysis_keys={list(change_prep[1].keys())}")
    
    # Debug: Check how many files will be analyzed
    files_data, analysis, project_name, use_cache, optimization_settings = change_prep
    
    files_needing_analysis = []
    for file_path, content in files_data:
        if not change_gen._should_skip_file(file_path):
            if change_gen._file_needs_migration_analysis(file_path, content):
                files_needing_analysis.append((file_path, content))
    
    print(f"   📊 Files needing analysis: {len(files_needing_analysis)} out of {len(files_data)}")
    
    if files_needing_analysis:
        print(f"   📄 Files that need migration analysis:")
        for i, (path, content) in enumerate(files_needing_analysis[:5]):
            print(f"      {i+1}. {path}")
            # Show why it needs analysis
            content_lower = content.lower()
            reasons = []
            if 'import javax.' in content:
                reasons.append("contains javax imports")
            if any(pattern in content_lower for pattern in ['websecurityconfigureradapter', '@enablewebsecurity']):
                reasons.append("contains Spring Security patterns")
            if any(pattern in content_lower for pattern in ['@test', '@springboottest']):
                reasons.append("contains Spring Test patterns")
            print(f"         Reason: {', '.join(reasons)}")
    else:
        print(f"   ⚠️  NO FILES NEED MIGRATION ANALYSIS!")
        print(f"   This could be why no changes are generated.")
        
        # Let's check some files manually
        print(f"\n   🔍 Manual check of first few Java files:")
        java_files = [(p, c) for p, c in files_data if p.endswith('.java')][:5]
        for path, content in java_files:
            print(f"      📄 {path}:")
            lines = content.split('\n')
            imports = [line.strip() for line in lines if line.strip().startswith('import')]
            javax_imports = [line for line in imports if 'javax.' in line]
            print(f"         Total imports: {len(imports)}")
            print(f"         javax imports: {len(javax_imports)}")
            if javax_imports:
                for imp in javax_imports[:3]:
                    print(f"           • {imp}")
        
        # Also check build files
        build_files = [(p, c) for p, c in files_data if p.endswith(('pom.xml', '.gradle'))]
        print(f"\n   🔍 Build files found: {len(build_files)}")
        for path, content in build_files:
            print(f"      📄 {path}:")
            if 'spring-boot' in content.lower():
                # Look for version
                lines = content.split('\n')
                spring_lines = [line.strip() for line in lines if 'spring' in line.lower() and 'version' in line.lower()]
                for line in spring_lines[:3]:
                    print(f"         • {line}")
    
    # Try generating changes anyway
    print(f"\n   🔧 Attempting to generate changes...")
    try:
        generated_changes = change_gen.exec(change_prep)
        change_gen.post(shared, change_prep, generated_changes)
        
        print(f"   ✅ Changes generated successfully!")
        
        # Analyze the generated changes
        total_changes = sum(len(changes) for changes in generated_changes.values() if changes)
        print(f"   📊 Total changes generated: {total_changes}")
        
        for category, changes in generated_changes.items():
            if changes:
                print(f"      📋 {category}: {len(changes)} changes")
                for i, change in enumerate(changes[:3]):
                    file_path = change.get('file', 'unknown')
                    change_type = change.get('type', 'unknown')
                    automatic = change.get('automatic', False)
                    print(f"         {i+1}. {file_path} - {change_type} (auto: {automatic})")
                if len(changes) > 3:
                    print(f"         ... and {len(changes) - 3} more changes")
        
        if total_changes == 0:
            print(f"   ⚠️  NO CHANGES GENERATED!")
            print(f"   This means the LLM didn't find any migration needs.")
            return
        
    except Exception as e:
        print(f"   ❌ Error generating changes: {e}")
        return
    
    # Step 3: Create Backup
    print(f"\n🔍 STEP 3: Creating Backup and Workspace")
    print("-" * 40)
    
    shared["output_dir"] = "./debug_migration_output"
    os.makedirs(shared["output_dir"], exist_ok=True)
    
    backup_manager = EnhancedFileBackupManager()
    backup_prep = backup_manager.prep(shared)
    backup_result = backup_manager.exec(backup_prep)
    backup_manager.post(shared, backup_prep, backup_result)
    
    print(f"   ✅ Backup and workspace created")
    print(f"   📁 Workspace: {backup_result['migration_workspace']}")
    
    # Step 4: Apply Changes
    print(f"\n🔍 STEP 4: Applying Changes")
    print("-" * 30)
    
    applicator = MigrationFileApplicator()
    apply_prep = applicator.prep(shared)
    
    if apply_prep[0] is None:
        print(f"   ⚠️  Application prep failed - likely no changes to apply")
        return
    
    print(f"   📊 Ready to apply changes to workspace")
    
    try:
        apply_result = applicator.exec(apply_prep)
        applicator.post(shared, apply_prep, apply_result)
        
        print(f"   ✅ Application completed!")
        print(f"   📊 Results:")
        print(f"      • Successful: {len(apply_result.get('successful', []))}")
        print(f"      • Skipped: {len(apply_result.get('skipped', []))}")
        print(f"      • Failed: {len(apply_result.get('failed', []))}")
        print(f"      • Files modified: {len(apply_result.get('files_modified', set()))}")
        
        # Show details of what was applied
        for success in apply_result.get('successful', [])[:5]:
            print(f"         ✅ {success.get('description', 'Unknown')}")
        
        for skip in apply_result.get('skipped', [])[:3]:
            print(f"         ⏭️  {skip.get('reason', 'Unknown reason')}")
        
        for fail in apply_result.get('failed', [])[:3]:
            print(f"         ❌ {fail.get('error', 'Unknown error')}")
        
    except Exception as e:
        print(f"   ❌ Error applying changes: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = "./migration_analysis/piggymetrics_migration_20250604_225511"
    
    if not os.path.exists(directory):
        print(f"❌ Directory not found: {directory}")
        sys.exit(1)
    
    debug_migration_process(directory) 