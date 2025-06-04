#!/usr/bin/env python3
"""
Test Script for Branch Support Feature

This script tests the new --source-branch functionality to ensure it works correctly
with different branch specifications when analyzing GitHub repositories.
"""

import subprocess
import sys
import os
import tempfile
from utils.crawl_github_files import crawl_github_files

def test_branch_support():
    """Test the branch support functionality."""
    print("🧪 Testing Branch Support for Spring Migration Tool")
    print("=" * 60)
    
    # Test repository with known branches
    test_repo = "https://github.com/spring-projects/spring-petclinic"
    
    # Get GitHub token
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("⚠️  No GitHub token found. Testing with public repository only.")
        print("💡 Set GITHUB_TOKEN environment variable for full testing.")
    
    test_cases = [
        {
            "name": "Default Branch",
            "branch": None,
            "description": "Test fetching default branch (should work)"
        },
        {
            "name": "Main Branch", 
            "branch": "main",
            "description": "Test fetching main branch explicitly"
        },
        {
            "name": "Invalid Branch",
            "branch": "non-existent-branch-12345",
            "description": "Test error handling for invalid branch"
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n🔍 Test Case: {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        print(f"   Branch: {test_case['branch'] or 'default'}")
        
        try:
            # Test the crawl_github_files function directly
            result = crawl_github_files(
                repo_url=test_repo,
                token=github_token,
                branch=test_case['branch'],
                include_patterns=["*.java", "*.xml", "pom.xml"],
                max_file_size=100000,  # 100KB limit for testing
                shallow_clone=True
            )
            
            file_count = len(result.get("files", {}))
            branch_info = result.get("branch", "default")
            
            print(f"   ✅ Success: {file_count} files fetched")
            print(f"   📂 Branch: {branch_info}")
            
            results.append({
                "test": test_case['name'],
                "status": "SUCCESS",
                "files": file_count,
                "branch": branch_info
            })
            
        except Exception as e:
            error_msg = str(e)
            if test_case['name'] == "Invalid Branch":
                print(f"   ✅ Expected Error: {error_msg[:100]}...")
                results.append({
                    "test": test_case['name'],
                    "status": "EXPECTED_ERROR",
                    "error": error_msg
                })
            else:
                print(f"   ❌ Unexpected Error: {error_msg}")
                results.append({
                    "test": test_case['name'],
                    "status": "ERROR",
                    "error": error_msg
                })
    
    # Test CLI integration
    print(f"\n🔧 Testing CLI Integration")
    print("=" * 40)
    
    # Create a temporary output directory
    with tempfile.TemporaryDirectory() as temp_dir:
        cli_test_cmd = [
            sys.executable, "main.py",
            "--repo", test_repo,
            "--source-branch", "main",
            "--output", temp_dir,
            "--quick-analysis",
            "--max-files", "10"
        ]
        
        if github_token:
            cli_test_cmd.extend(["--github-token", github_token])
        
        print(f"Running: {' '.join(cli_test_cmd)}")
        
        try:
            # Run with timeout to prevent hanging
            result = subprocess.run(
                cli_test_cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            if result.returncode == 0:
                print("   ✅ CLI Test: SUCCESS")
                print("   📋 Analysis completed successfully")
                
                # Check if output files were created
                output_files = os.listdir(temp_dir)
                if output_files:
                    print(f"   📄 Output files: {len(output_files)} files created")
                    for file in output_files[:3]:  # Show first 3 files
                        print(f"      - {file}")
                else:
                    print("   ⚠️  No output files found")
                    
            else:
                print("   ❌ CLI Test: FAILED")
                print(f"   Error: {result.stderr[:200]}...")
                
        except subprocess.TimeoutExpired:
            print("   ⏱️  CLI Test: TIMEOUT (analysis took too long)")
        except Exception as cli_error:
            print(f"   ❌ CLI Test: ERROR - {cli_error}")
    
    # Print summary
    print(f"\n📊 Test Summary")
    print("=" * 30)
    
    success_count = sum(1 for r in results if r['status'] in ['SUCCESS', 'EXPECTED_ERROR'])
    total_count = len(results)
    
    print(f"✅ Passed: {success_count}/{total_count}")
    
    for result in results:
        status_icon = "✅" if result['status'] in ['SUCCESS', 'EXPECTED_ERROR'] else "❌"
        print(f"   {status_icon} {result['test']}: {result['status']}")
    
    # Usage examples
    print(f"\n💡 Usage Examples")
    print("=" * 30)
    print("# Analyze main branch:")
    print("python main.py --repo https://github.com/user/repo --source-branch main")
    print("")
    print("# Analyze development branch:")
    print("python main.py --repo https://github.com/user/repo --source-branch develop")
    print("")
    print("# Analyze feature branch:")
    print("python main.py --repo https://github.com/user/repo --source-branch feature/spring-upgrade")
    print("")
    print("# Analyze release branch:")
    print("python main.py --repo https://github.com/user/repo --source-branch release/v2.0")

if __name__ == "__main__":
    test_branch_support() 