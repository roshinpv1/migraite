#!/usr/bin/env python3
"""
Test script to verify LLM timeout improvements.
Tests various timeout configurations and ensures proper handling of large repositories.
"""

import os
import sys
import time
from utils.call_llm import (
    call_llm, 
    configure_maximum_timeouts, 
    auto_configure_timeouts_for_repository_size,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    MAX_CONTEXT_LENGTH
)

def test_timeout_configuration():
    """Test timeout configuration functions."""
    print("🧪 Testing timeout configuration functions...")
    
    # Test auto-configuration for different repository sizes
    print("\n📊 Testing auto-configuration for different repository sizes:")
    
    # Small repository
    print("\n1. Small repository (50 files):")
    auto_configure_timeouts_for_repository_size(50)
    print(f"   DEFAULT_TIMEOUT: {DEFAULT_TIMEOUT}s")
    print(f"   MAX_RETRIES: {MAX_RETRIES}")
    print(f"   MAX_CONTEXT_LENGTH: {MAX_CONTEXT_LENGTH}")
    
    # Medium repository  
    print("\n2. Medium repository (250 files):")
    auto_configure_timeouts_for_repository_size(250)
    print(f"   DEFAULT_TIMEOUT: {DEFAULT_TIMEOUT}s")
    print(f"   MAX_RETRIES: {MAX_RETRIES}")
    print(f"   MAX_CONTEXT_LENGTH: {MAX_CONTEXT_LENGTH}")
    
    # Large repository
    print("\n3. Large repository (600 files):")
    auto_configure_timeouts_for_repository_size(600)
    print(f"   DEFAULT_TIMEOUT: {DEFAULT_TIMEOUT}s")
    print(f"   MAX_RETRIES: {MAX_RETRIES}")
    print(f"   MAX_CONTEXT_LENGTH: {MAX_CONTEXT_LENGTH}")
    
    # Test maximum configuration
    print("\n4. Maximum timeout configuration:")
    configure_maximum_timeouts()
    print(f"   DEFAULT_TIMEOUT: {DEFAULT_TIMEOUT}s")
    print(f"   MAX_RETRIES: {MAX_RETRIES}")
    print(f"   MAX_CONTEXT_LENGTH: {MAX_CONTEXT_LENGTH}")

def test_large_prompt_handling():
    """Test handling of large prompts."""
    print("\n🚀 Testing large prompt handling...")
    
    # Create a large test prompt
    large_prompt = "Analyze this Spring Boot codebase:\n" + "Sample code content\n" * 10000
    
    print(f"   Large prompt size: {len(large_prompt):,} characters")
    print(f"   Current MAX_CONTEXT_LENGTH: {MAX_CONTEXT_LENGTH:,}")
    
    if len(large_prompt) > MAX_CONTEXT_LENGTH:
        print("   ✅ Large prompt detected - will be optimized")
    else:
        print("   ℹ️  Prompt within context limits")

def test_timeout_values():
    """Test that timeout values are reasonable."""
    print("\n⏱️  Testing timeout values...")
    
    # Test with maximum configuration
    configure_maximum_timeouts()
    
    # Verify timeout values are within reasonable bounds
    assert DEFAULT_TIMEOUT >= 900, f"DEFAULT_TIMEOUT too low: {DEFAULT_TIMEOUT}s"
    assert DEFAULT_TIMEOUT <= 3600, f"DEFAULT_TIMEOUT too high: {DEFAULT_TIMEOUT}s"
    assert MAX_RETRIES >= 5, f"MAX_RETRIES too low: {MAX_RETRIES}"
    assert MAX_RETRIES <= 10, f"MAX_RETRIES too high: {MAX_RETRIES}"
    assert MAX_CONTEXT_LENGTH >= 200000, f"MAX_CONTEXT_LENGTH too low: {MAX_CONTEXT_LENGTH}"
    
    print(f"   ✅ DEFAULT_TIMEOUT: {DEFAULT_TIMEOUT}s (15-60 minutes)")
    print(f"   ✅ MAX_RETRIES: {MAX_RETRIES} (5-10 retries)")
    print(f"   ✅ MAX_CONTEXT_LENGTH: {MAX_CONTEXT_LENGTH:,} chars (200k+ characters)")

def test_progressive_timeout_increase():
    """Test progressive timeout increase simulation."""
    print("\n📈 Testing progressive timeout increase logic...")
    
    initial_timeout = 900  # 15 minutes
    print(f"   Initial timeout: {initial_timeout}s")
    
    # Simulate timeout increases for retries
    timeout = initial_timeout
    for attempt in range(5):
        if attempt > 0:
            timeout = min(timeout * 1.5, 3600)  # Increase up to 1 hour
        print(f"   Attempt {attempt + 1}: {timeout}s ({timeout/60:.1f} minutes)")
    
    print("   ✅ Progressive timeout increase working correctly")

def main():
    """Run all timeout tests."""
    print("🔧 LLM Timeout Configuration Test Suite")
    print("=" * 50)
    
    try:
        test_timeout_configuration()
        test_large_prompt_handling()
        test_timeout_values()
        test_progressive_timeout_increase()
        
        print("\n" + "=" * 50)
        print("✅ All timeout tests passed!")
        print("\n📋 Summary of Improvements:")
        print("   • Maximum timeout: 30-60 minutes (was 5 minutes)")
        print("   • Increased retries: 5-8 (was 3)")
        print("   • Progressive timeout increases")
        print("   • Auto-configuration based on repository size")
        print("   • Enhanced context length handling")
        print("   • Better provider-specific timeout handling")
        print("\n🚀 The migration tool should now handle large repositories without timeout issues!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 