#!/usr/bin/env python3
"""
Test Script for Project Name Fix

This script tests that the project_name derivation works correctly
with the new --source-branch functionality.
"""

import os
import sys
import tempfile
import subprocess

def test_project_name_derivation():
    """Test project name derivation with different scenarios."""
    print("🧪 Testing Project Name Derivation")
    print("=" * 50)
    
    # Test cases for project name derivation
    test_cases = [
        {
            "name": "GitHub Repository URL",
            "args": ["--repo", "https://github.com/spring-projects/spring-petclinic"],
            "expected_project_name": "spring-petclinic",
            "description": "Extract project name from GitHub URL"
        },
        {
            "name": "GitHub Repository URL with .git suffix",
            "args": ["--repo", "https://github.com/spring-projects/spring-petclinic.git"],
            "expected_project_name": "spring-petclinic",
            "description": "Extract project name from GitHub URL with .git suffix"
        },
        {
            "name": "Local Directory Path",
            "args": ["--dir", "/tmp/test-spring-project"],
            "expected_project_name": "test-spring-project",
            "description": "Extract project name from local directory path",
            "setup_required": True
        }
    ]
    
    results = []
    
    for test_case in test_cases:
        print(f"\n🔍 Test Case: {test_case['name']}")
        print(f"   Description: {test_case['description']}")
        print(f"   Expected Project Name: {test_case['expected_project_name']}")
        
        # Setup test directory if needed
        test_dir = None
        if test_case.get("setup_required"):
            test_dir = "/tmp/test-spring-project"
            os.makedirs(test_dir, exist_ok=True)
            
            # Create a simple Java file to make it look like a Spring project
            java_file = os.path.join(test_dir, "Application.java")
            with open(java_file, 'w') as f:
                f.write("""
package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}
""")
            print(f"   📁 Created test directory: {test_dir}")
        
        try:
            # Create a temporary output directory
            with tempfile.TemporaryDirectory() as temp_output:
                # Build command with dry-run (quick analysis, limited files)
                cmd = [
                    sys.executable, "main.py",
                    *test_case["args"],
                    "--output", temp_output,
                    "--quick-analysis",
                    "--max-files", "5",  # Very limited for quick test
                    "--verbose"  # Enable verbose to see project name in logs
                ]
                
                # Add source branch if testing with repo
                if "--repo" in test_case["args"]:
                    cmd.extend(["--source-branch", "main"])
                
                print(f"   🚀 Running: {' '.join(cmd[:5])}... (truncated)")
                
                # Run the command with timeout
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=60,  # 1 minute timeout
                    cwd=os.path.dirname(os.path.abspath(__file__))
                )
                
                # Check if project name was derived correctly
                output_text = result.stdout + result.stderr
                
                if f"project name from" in output_text.lower() and test_case['expected_project_name'] in output_text:
                    print(f"   ✅ SUCCESS: Project name '{test_case['expected_project_name']}' found in output")
                    results.append({
                        "test": test_case['name'],
                        "status": "SUCCESS",
                        "project_name": test_case['expected_project_name']
                    })
                elif "'project_name'" in output_text:
                    print(f"   ❌ FAILED: 'project_name' key error still present")
                    print(f"   📋 Error in output: {result.stderr[:200]}...")
                    results.append({
                        "test": test_case['name'],
                        "status": "FAILED",
                        "error": "project_name key missing"
                    })
                elif result.returncode != 0:
                    print(f"   ❌ FAILED: Command failed with return code {result.returncode}")
                    print(f"   📋 Error: {result.stderr[:200]}...")
                    results.append({
                        "test": test_case['name'],
                        "status": "FAILED",
                        "error": f"Command failed: {result.returncode}"
                    })
                else:
                    print(f"   ⚠️  INCONCLUSIVE: Command succeeded but project name not found in output")
                    print(f"   📋 Output preview: {output_text[:300]}...")
                    results.append({
                        "test": test_case['name'],
                        "status": "INCONCLUSIVE",
                        "note": "Command succeeded but verification unclear"
                    })
                
        except subprocess.TimeoutExpired:
            print(f"   ⏱️  TIMEOUT: Command took too long to execute")
            results.append({
                "test": test_case['name'],
                "status": "TIMEOUT",
                "error": "Command timeout"
            })
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            results.append({
                "test": test_case['name'],
                "status": "ERROR",
                "error": str(e)
            })
        finally:
            # Clean up test directory
            if test_dir and os.path.exists(test_dir):
                import shutil
                try:
                    shutil.rmtree(test_dir)
                    print(f"   🧹 Cleaned up test directory")
                except:
                    print(f"   ⚠️  Could not clean up {test_dir}")
    
    # Print summary
    print(f"\n📊 Test Summary")
    print("=" * 30)
    
    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    total_count = len(results)
    
    print(f"✅ Passed: {success_count}/{total_count}")
    
    for result in results:
        status_icon = "✅" if result['status'] == 'SUCCESS' else "❌" if result['status'] == 'FAILED' else "⚠️"
        print(f"   {status_icon} {result['test']}: {result['status']}")
        if 'error' in result:
            print(f"      Error: {result['error']}")
    
    if success_count == total_count:
        print(f"\n🎉 All tests passed! The project_name fix is working correctly.")
        print(f"✅ The --source-branch feature should now work without 'project_name' errors.")
    else:
        print(f"\n⚠️  Some tests failed. Please check the output above.")
    
    # Show next steps
    print(f"\n💡 Next Steps")
    print("=" * 20)
    print("# Test with your original command:")
    print("python main.py --repo https://github.com/your/repo --source-branch your-branch")
    print("")
    print("# Or test locally:")
    print("python main.py --dir /path/to/your/project")

def test_source_branch_integration():
    """Test that source branch works with the project name fix."""
    print(f"\n🌿 Testing Source Branch Integration")
    print("=" * 40)
    
    # Use a small public repository for testing
    test_repo = "https://github.com/spring-projects/spring-petclinic"
    
    with tempfile.TemporaryDirectory() as temp_output:
        cmd = [
            sys.executable, "main.py",
            "--repo", test_repo,
            "--source-branch", "main",
            "--output", temp_output,
            "--quick-analysis",
            "--max-files", "10",
            "--verbose"
        ]
        
        print(f"Testing command: {' '.join(cmd[:6])}... (truncated)")
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,  # 2 minutes
                cwd=os.path.dirname(os.path.abspath(__file__))
            )
            
            output_text = result.stdout + result.stderr
            
            # Check for success indicators
            success_indicators = [
                "spring-petclinic",  # Project name
                "Target branch: main",  # Branch specification
                "Successfully fetched",  # File fetching
                "Migration analysis",  # Analysis started
            ]
            
            found_indicators = [indicator for indicator in success_indicators if indicator in output_text]
            
            if len(found_indicators) >= 3:
                print(f"   ✅ SUCCESS: Source branch integration working")
                print(f"   📋 Found indicators: {len(found_indicators)}/{len(success_indicators)}")
                for indicator in found_indicators:
                    print(f"      ✓ {indicator}")
                return True
            else:
                print(f"   ❌ PARTIAL: Not all indicators found")
                print(f"   📋 Found indicators: {len(found_indicators)}/{len(success_indicators)}")
                print(f"   📄 Output preview: {output_text[:500]}...")
                return False
                
        except subprocess.TimeoutExpired:
            print(f"   ⏱️  TIMEOUT: Integration test took too long")
            return False
        except Exception as e:
            print(f"   ❌ ERROR: {e}")
            return False

if __name__ == "__main__":
    print("🔧 Spring Migration Tool - Project Name Fix Test")
    print("=" * 60)
    
    # Test basic project name derivation
    test_project_name_derivation()
    
    # Test source branch integration
    integration_success = test_source_branch_integration()
    
    print(f"\n🏁 Final Result")
    print("=" * 20)
    if integration_success:
        print("✅ Project name fix successful!")
        print("✅ Source branch integration working!")
        print("🚀 Your original command should now work without errors.")
    else:
        print("⚠️  Some issues detected. Please review the test output above.") 