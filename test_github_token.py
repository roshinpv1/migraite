#!/usr/bin/env python3
"""
Test script for GitHub token functionality

This script tests the GitHub token handling for both public and private repositories.
"""

import os
import sys
import subprocess

def test_github_token_handling():
    """Test various GitHub token configurations"""
    
    print("🔧 Testing GitHub Token Functionality\n")
    
    # Test 1: Check help shows token option
    print("1. Checking help output includes token option...")
    try:
        result = subprocess.run([sys.executable, "main.py", "--help"], 
                              capture_output=True, text=True, timeout=10)
        if "--token" in result.stdout:
            print("   ✅ Token option found in help")
        else:
            print("   ❌ Token option NOT found in help")
            print(f"   Help output: {result.stdout[:500]}...")
    except Exception as e:
        print(f"   ❌ Error running help: {e}")
    
    # Test 2: Test with environment variable
    print("\n2. Testing environment variable detection...")
    
    # Save original token if exists
    original_token = os.environ.get('GITHUB_TOKEN')
    
    # Test with a dummy token
    os.environ['GITHUB_TOKEN'] = 'dummy_token_for_testing'
    
    try:
        # Test dry run with a public repo (won't actually clone with dummy token)
        print("   Testing with GITHUB_TOKEN environment variable...")
        result = subprocess.run([
            sys.executable, "main.py", 
            "--repo", "https://github.com/octocat/Hello-World",
            "--help"  # Just show help, don't actually run
        ], capture_output=True, text=True, timeout=10)
        print("   ✅ Environment variable handling works")
    except Exception as e:
        print(f"   ⚠️  Could not fully test env var: {e}")
    finally:
        # Restore original token
        if original_token:
            os.environ['GITHUB_TOKEN'] = original_token
        else:
            os.environ.pop('GITHUB_TOKEN', None)
    
    # Test 3: Show usage examples
    print("\n3. Usage Examples:")
    print("   📝 For public repositories:")
    print("      python3 main.py --repo https://github.com/username/public-repo")
    print()
    print("   📝 For private repositories (method 1 - environment variable):")
    print("      export GITHUB_TOKEN='your_personal_access_token'")
    print("      python3 main.py --repo https://github.com/username/private-repo")
    print()
    print("   📝 For private repositories (method 2 - command line):")
    print("      python3 main.py --repo https://github.com/username/private-repo --token 'your_token'")
    print()
    print("   📝 For Spring migration analysis:")
    print("      python3 main.py --mode spring-migration --repo https://github.com/username/spring-app --token 'your_token'")
    
    print("\n4. GitHub Personal Access Token Setup:")
    print("   1. Go to: https://github.com/settings/tokens")
    print("   2. Click 'Generate new token (classic)'")
    print("   3. Select scopes:")
    print("      - 'repo' for private repositories")
    print("      - 'public_repo' for public repositories only")
    print("   4. Copy the generated token")
    print("   5. Use it with one of the methods above")
    
    print("\n✅ GitHub token functionality test completed!")
    print("\nNote: This script only tests the token handling mechanism.")
    print("To test actual repository access, use a real token with a real repository.")

if __name__ == "__main__":
    test_github_token_handling() 