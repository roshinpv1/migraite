#!/usr/bin/env python3
"""
Test script for migration plan generation

Tests the migration plan generation functionality to ensure all required keys are handled properly.
"""

import json
import tempfile
import os
from nodes import MigrationPlanGenerator


def test_migration_plan_with_missing_keys():
    """Test migration plan generation when LLM response has missing keys."""
    
    # Create a mock analysis
    mock_analysis = {
        "executive_summary": {
            "migration_impact": "Medium complexity migration required",
            "key_challenges": ["Dependency updates", "Jakarta migration"]
        },
        "files": ["file1.java", "file2.java"],
        "effort_estimation": {
            "total_effort": "4-6 weeks"
        }
    }
    
    # Create migration plan generator
    plan_generator = MigrationPlanGenerator()
    
    # Test with incomplete LLM response (missing required keys)
    incomplete_response = """
    {
        "migration_strategy": {
            "approach": "Phased",
            "rationale": "Safer migration approach"
        }
    }
    """
    
    print("🧪 Testing migration plan generation with incomplete LLM response...")
    plan = plan_generator._parse_plan_response(incomplete_response, mock_analysis, "test-project")
    
    # Verify all required keys are present
    required_keys = ["migration_strategy", "phase_breakdown", "automation_recommendations", "testing_strategy"]
    
    print(f"\n✅ Testing required keys presence:")
    all_keys_present = True
    for key in required_keys:
        if key in plan:
            print(f"   ✓ {key}: Present")
        else:
            print(f"   ❌ {key}: Missing")
            all_keys_present = False
    
    if all_keys_present:
        print(f"\n🎉 Success! All required keys are present in the migration plan")
        
        # Show some details of the generated plan
        print(f"\n📋 Migration Plan Summary:")
        print(f"   Strategy: {plan['migration_strategy']['approach']}")
        print(f"   Timeline: {plan['migration_strategy']['estimated_timeline']}")
        print(f"   Phases: {len(plan['phase_breakdown'])}")
        print(f"   Automation tools: {len(plan['automation_recommendations'])}")
        
        return True
    else:
        print(f"\n❌ Test failed: Some required keys are missing")
        return False


def test_migration_plan_structure_validation():
    """Test structure validation of migration plan components."""
    
    print(f"\n🔍 Testing migration plan structure validation...")
    
    # Create migration plan generator
    plan_generator = MigrationPlanGenerator()
    
    # Test with malformed structures
    malformed_plan = {
        "migration_strategy": "should be object not string",  # Wrong type
        "phase_breakdown": {},  # Should be array
        "automation_recommendations": "should be array",  # Wrong type
        "testing_strategy": []  # Should be object
    }
    
    print("   Testing structure validation with malformed data...")
    plan_generator._validate_plan_structure(malformed_plan)
    
    # Check if structures were fixed
    checks = [
        ("migration_strategy", dict, "object"),
        ("phase_breakdown", list, "array"),
        ("automation_recommendations", list, "array"),
        ("testing_strategy", dict, "object")
    ]
    
    all_fixed = True
    for key, expected_type, type_name in checks:
        if isinstance(malformed_plan[key], expected_type):
            print(f"   ✓ {key}: Fixed to {type_name}")
        else:
            print(f"   ❌ {key}: Still wrong type")
            all_fixed = False
    
    return all_fixed


def test_fallback_plan_generation():
    """Test fallback plan generation when parsing completely fails."""
    
    print(f"\n🛡️ Testing fallback plan generation...")
    
    # Create migration plan generator
    plan_generator = MigrationPlanGenerator()
    
    # Mock analysis
    mock_analysis = {
        "executive_summary": {
            "migration_impact": "High complexity"
        },
        "effort_estimation": {
            "total_effort": "8-12 weeks"
        }
    }
    
    # Generate fallback plan
    fallback_plan = plan_generator._get_fallback_plan(mock_analysis, "test-project")
    
    # Verify fallback plan has all required keys
    required_keys = ["migration_strategy", "phase_breakdown", "automation_recommendations", "testing_strategy"]
    
    all_present = True
    for key in required_keys:
        if key in fallback_plan:
            print(f"   ✓ {key}: Present in fallback plan")
        else:
            print(f"   ❌ {key}: Missing from fallback plan")
            all_present = False
    
    if all_present:
        print(f"   🎉 Fallback plan contains all required sections")
        
        # Verify fallback plan has useful content
        phases = fallback_plan["phase_breakdown"]
        print(f"   📋 Fallback plan has {len(phases)} phases")
        
        for i, phase in enumerate(phases[:2], 1):  # Show first 2 phases
            print(f"      Phase {i}: {phase['name']}")
            
        return True
    else:
        print(f"   ❌ Fallback plan is incomplete")
        return False


def run_all_tests():
    """Run all migration plan generation tests."""
    
    print("🧪 Running Migration Plan Generation Tests")
    print("=" * 50)
    
    tests = [
        ("Missing Keys Handling", test_migration_plan_with_missing_keys),
        ("Structure Validation", test_migration_plan_structure_validation), 
        ("Fallback Plan Generation", test_fallback_plan_generation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔬 Running: {test_name}")
        try:
            if test_func():
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n" + "=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Migration plan generation is working correctly.")
        return True
    else:
        print("⚠️ Some tests failed. Migration plan generation needs attention.")
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1) 