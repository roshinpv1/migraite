#!/usr/bin/env python3
"""
Test Script for File Modification Verification

This script creates a simple Spring project and verifies that the migration tool
actually modifies the source files when --apply-changes is used.
"""

import os
import sys
import tempfile
import shutil
import subprocess
from pathlib import Path

def create_test_spring_project():
    """Create a minimal Spring project with javax imports for testing."""
    
    # Create temporary directory
    test_dir = tempfile.mkdtemp(prefix="spring_migration_test_")
    print(f"📁 Created test project directory: {test_dir}")
    
    # Create project structure
    src_dir = os.path.join(test_dir, "src", "main", "java", "com", "example")
    os.makedirs(src_dir, exist_ok=True)
    
    # Create a Java file with javax imports
    java_content = """package com.example;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.persistence.Entity;
import javax.persistence.Table;
import javax.validation.constraints.NotNull;

import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;

@RestController
public class TestController {
    
    @GetMapping("/test")
    public String test(HttpServletRequest request, HttpServletResponse response) {
        return "Hello World";
    }
}
"""
    
    java_file = os.path.join(src_dir, "TestController.java")
    with open(java_file, 'w') as f:
        f.write(java_content)
    
    # Create a simple pom.xml
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <groupId>com.example</groupId>
    <artifactId>spring-migration-test</artifactId>
    <version>1.0.0</version>
    <properties>
        <java.version>11</java.version>
        <spring-boot.version>2.7.0</spring-boot.version>
    </properties>
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>${spring-boot.version}</version>
        </dependency>
    </dependencies>
</project>
"""
    
    pom_file = os.path.join(test_dir, "pom.xml")
    with open(pom_file, 'w') as f:
        f.write(pom_content)
    
    print(f"✅ Created test project with javax imports")
    print(f"   📄 Java file: {java_file}")
    print(f"   📄 POM file: {pom_file}")
    
    return test_dir, java_file

def run_migration_tool(test_dir, apply_changes=False):
    """Run the migration tool on the test project."""
    
    print(f"\n🚀 Running migration tool...")
    print(f"   📁 Project: {test_dir}")
    print(f"   🔧 Apply changes: {'Yes' if apply_changes else 'No'}")
    
    # Build command
    cmd = [
        sys.executable, "main.py",
        "--dir", test_dir,
        "--output", os.path.join(test_dir, "migration_results"),
        "--quick-analysis",
        "--max-files", "10",
        "--verbose"
    ]
    
    if apply_changes:
        cmd.append("--apply-changes")
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,  # 2 minutes timeout
            cwd=os.path.dirname(os.path.abspath(__file__))
        )
        
        return result
        
    except subprocess.TimeoutExpired:
        print("⏱️  Migration tool timed out")
        return None
    except Exception as e:
        print(f"❌ Error running migration tool: {e}")
        return None

def check_file_changes(original_file, migration_workspace):
    """Check if the file was actually modified in the migration workspace."""
    
    # Find the corresponding file in migration workspace
    workspace_files = []
    for root, dirs, files in os.walk(migration_workspace):
        for file in files:
            if file.endswith('.java'):
                workspace_files.append(os.path.join(root, file))
    
    if not workspace_files:
        print("❌ No Java files found in migration workspace")
        return False
    
    # Read original file
    try:
        with open(original_file, 'r') as f:
            original_content = f.read()
    except Exception as e:
        print(f"❌ Error reading original file: {e}")
        return False
    
    # Check migration workspace file
    workspace_file = workspace_files[0]  # Take the first Java file
    try:
        with open(workspace_file, 'r') as f:
            workspace_content = f.read()
    except Exception as e:
        print(f"❌ Error reading workspace file: {e}")
        return False
    
    print(f"\n📄 Comparing files:")
    print(f"   📝 Original: {original_file}")
    print(f"   📝 Workspace: {workspace_file}")
    
    # Check for javax vs jakarta
    original_javax_count = original_content.count('javax.')
    workspace_javax_count = workspace_content.count('javax.')
    workspace_jakarta_count = workspace_content.count('jakarta.')
    
    print(f"\n🔍 Import Analysis:")
    print(f"   📊 Original javax imports: {original_javax_count}")
    print(f"   📊 Workspace javax imports: {workspace_javax_count}")
    print(f"   📊 Workspace jakarta imports: {workspace_jakarta_count}")
    
    # Check if changes were made
    changes_made = original_content != workspace_content
    javax_to_jakarta = original_javax_count > workspace_javax_count and workspace_jakarta_count > 0
    
    if changes_made:
        print(f"✅ File content changed!")
        if javax_to_jakarta:
            print(f"✅ javax → jakarta migration detected!")
            print(f"   🔄 Converted {original_javax_count - workspace_javax_count} javax imports")
        else:
            print(f"ℹ️  File changed but no javax → jakarta conversion detected")
    else:
        print(f"❌ No changes detected in file content")
    
    # Show a sample of differences
    if changes_made:
        print(f"\n📋 Sample differences:")
        original_lines = original_content.split('\n')
        workspace_lines = workspace_content.split('\n')
        
        for i, (orig, work) in enumerate(zip(original_lines, workspace_lines)):
            if orig != work:
                print(f"   Line {i+1}:")
                print(f"     - {orig}")
                print(f"     + {work}")
                break
    
    return changes_made and javax_to_jakarta

def main():
    """Main test function."""
    print("🧪 Testing Spring Migration Tool File Modification")
    print("=" * 60)
    
    test_dir = None
    try:
        # Step 1: Create test project
        test_dir, java_file = create_test_spring_project()
        
        # Step 2: Run migration tool with --apply-changes
        result = run_migration_tool(test_dir, apply_changes=True)
        
        if result is None:
            print("❌ Failed to run migration tool")
            return False
        
        if result.returncode != 0:
            print(f"❌ Migration tool failed with return code: {result.returncode}")
            print(f"Error output: {result.stderr}")
            return False
        
        print("✅ Migration tool completed successfully")
        
        # Step 3: Look for migration workspace
        migration_results = os.path.join(test_dir, "migration_results")
        workspace_dirs = [d for d in os.listdir(migration_results) if d.endswith('_migration_')]
        
        if not workspace_dirs:
            print("❌ No migration workspace found")
            return False
        
        migration_workspace = os.path.join(migration_results, workspace_dirs[0])
        print(f"📁 Found migration workspace: {migration_workspace}")
        
        # Step 4: Check if files were actually modified
        files_changed = check_file_changes(java_file, migration_workspace)
        
        if files_changed:
            print(f"\n🎉 SUCCESS: Migration tool successfully modified files!")
            print(f"✅ javax → jakarta conversion confirmed")
            return True
        else:
            print(f"\n❌ FAILURE: No file modifications detected")
            return False
            
    except Exception as e:
        print(f"❌ Test error: {e}")
        return False
        
    finally:
        # Cleanup
        if test_dir and os.path.exists(test_dir):
            try:
                shutil.rmtree(test_dir)
                print(f"🧹 Cleaned up test directory")
            except:
                print(f"⚠️  Could not clean up {test_dir}")

if __name__ == "__main__":
    success = main()
    if success:
        print(f"\n✅ Test PASSED: File modifications are working!")
        sys.exit(0)
    else:
        print(f"\n❌ Test FAILED: File modifications are not working!")
        sys.exit(1) 