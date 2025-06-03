#!/usr/bin/env python3
"""
Test script for improved JSON extraction and cleaning functionality

Tests the enhanced JSON handling in MigrationChangeGenerator to ensure it can handle various LLM response formats.
"""

import json
import os
import tempfile
from nodes import MigrationChangeGenerator


def test_json_extraction_scenarios():
    """Test various JSON extraction scenarios that commonly fail."""
    
    # Create a migration change generator for testing
    generator = MigrationChangeGenerator()
    
    test_cases = [
        {
            "name": "Perfect JSON in markdown",
            "response": """```json
{
  "javax_to_jakarta": [
    {
      "file": "test.java",
      "type": "import_replacement",
      "from": "javax.persistence.Entity",
      "to": "jakarta.persistence.Entity",
      "description": "Replace javax import",
      "line_numbers": [3],
      "automatic": true,
      "explanation": "Standard migration"
    }
  ],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}
```""",
            "should_work": True
        },
        {
            "name": "JSON with unescaped quotes",
            "response": """{
  "javax_to_jakarta": [
    {
      "file": "test.java",
      "description": "Replace "javax" imports with "jakarta"",
      "explanation": "This has "quotes" inside"
    }
  ],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}""",
            "should_work": True
        },
        {
            "name": "JSON with missing closing braces",
            "response": """{
  "javax_to_jakarta": [
    {
      "file": "test.java",
      "type": "import_replacement"
    }
  ],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []""",
            "should_work": True
        },
        {
            "name": "JSON with trailing commas",
            "response": """{
  "javax_to_jakarta": [
    {
      "file": "test.java",
      "type": "import_replacement",
    },
  ],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": [],
}""",
            "should_work": True
        },
        {
            "name": "JSON mixed with text",
            "response": """Here's the analysis for your file:

{
  "javax_to_jakarta": [],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}

Let me know if you need more details!""",
            "should_work": True
        },
        {
            "name": "Completely invalid response",
            "response": "I couldn't analyze this file properly. Please try again.",
            "should_work": False
        },
        {
            "name": "Empty response",
            "response": "",
            "should_work": False
        }
    ]
    
    print("🧪 Testing JSON Extraction and Cleaning")
    print("=" * 50)
    
    passed = 0
    total = len(test_cases)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n🔬 Test {i}: {test_case['name']}")
        
        try:
            json_str = generator._extract_and_clean_json(test_case['response'], "test.java")
            
            if json_str:
                # Try to parse the extracted JSON
                parsed = json.loads(json_str)
                
                # Verify it has the expected structure
                expected_keys = ["javax_to_jakarta", "spring_security_updates", "dependency_updates", "configuration_updates", "other_changes"]
                has_structure = all(key in parsed for key in expected_keys)
                
                if test_case['should_work']:
                    if has_structure:
                        print(f"   ✅ SUCCESS: JSON extracted and parsed correctly")
                        passed += 1
                    else:
                        print(f"   ⚠️  WARNING: JSON parsed but missing expected structure")
                        print(f"      Keys found: {list(parsed.keys())}")
                else:
                    print(f"   🤔 UNEXPECTED: JSON extracted when it shouldn't have worked")
                    print(f"      Extracted: {json_str[:100]}...")
            
            else:
                if test_case['should_work']:
                    print(f"   ❌ FAILED: Could not extract JSON when it should have worked")
                    print(f"      Response preview: {test_case['response'][:100]}...")
                else:
                    print(f"   ✅ SUCCESS: Correctly rejected invalid response")
                    passed += 1
                    
        except Exception as e:
            print(f"   ❌ ERROR: Exception during testing: {e}")
    
    print(f"\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    return passed == total


def test_json_repair_strategies():
    """Test specific JSON repair strategies."""
    
    print(f"\n🔧 Testing JSON Repair Strategies")
    print("=" * 40)
    
    generator = MigrationChangeGenerator()
    
    repair_tests = [
        {
            "name": "Trailing comma removal",
            "broken_json": '{"key": "value",}',
            "should_fix": True
        },
        {
            "name": "Missing comma between objects",
            "broken_json": '{"a": 1}{"b": 2}',
            "should_fix": True
        },
        {
            "name": "Odd number of quotes",
            "broken_json": '{"key": "value without closing quote}',
            "should_fix": True
        },
        {
            "name": "Comments removal",
            "broken_json": '{"key": "value" /* comment */}',
            "should_fix": True
        }
    ]
    
    passed = 0
    total = len(repair_tests)
    
    for test in repair_tests:
        print(f"\n🔧 Repair Test: {test['name']}")
        try:
            repaired = generator._attempt_json_repair(test['broken_json'], "test.java")
            
            if repaired:
                # Try to parse the repaired JSON
                json.loads(repaired)
                print(f"   ✅ SUCCESS: JSON repaired and valid")
                print(f"      Before: {test['broken_json']}")
                print(f"      After:  {repaired}")
                passed += 1
            else:
                print(f"   ❌ FAILED: Could not repair JSON")
                
        except json.JSONDecodeError:
            print(f"   ❌ FAILED: Repaired JSON is still invalid")
        except Exception as e:
            print(f"   ❌ ERROR: Exception during repair: {e}")
    
    print(f"\n📊 Repair Results: {passed}/{total} repairs successful")
    return passed == total


def run_all_tests():
    """Run all JSON extraction and cleaning tests."""
    
    print("🧪 Running Enhanced JSON Extraction Tests")
    print("=" * 60)
    
    extraction_pass = test_json_extraction_scenarios()
    repair_pass = test_json_repair_strategies()
    
    print(f"\n" + "=" * 60)
    
    if extraction_pass and repair_pass:
        print("🎉 All JSON extraction and repair tests passed!")
        print("   The enhanced JSON handling should significantly reduce")
        print("   'No valid JSON found' errors in migration analysis.")
        return True
    else:
        print("⚠️ Some tests failed. JSON extraction may still have issues.")
        if not extraction_pass:
            print("   - JSON extraction tests failed")
        if not repair_pass:
            print("   - JSON repair tests failed")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1) 