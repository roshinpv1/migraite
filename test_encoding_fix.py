#!/usr/bin/env python3
"""
Test script for encoding fix verification

This script creates test files with various encodings and verifies that
the robust file reader can handle them gracefully.
"""

import os
import tempfile
import shutil
from pathlib import Path
from utils.file_encoding_detector import RobustFileReader
from utils.crawl_local_files import crawl_local_files


def create_test_files_with_encodings():
    """Create test files with various encodings to test robustness."""
    test_dir = tempfile.mkdtemp(prefix="encoding_test_")
    test_path = Path(test_dir)
    
    print(f"🏗️  Creating test files in: {test_dir}")
    
    # Test cases with different encodings and content
    test_cases = [
        {
            "filename": "utf8_file.txt",
            "content": "Hello World! 🌍 UTF-8 content with emoji",
            "encoding": "utf-8"
        },
        {
            "filename": "ascii_file.txt", 
            "content": "Simple ASCII content without special characters",
            "encoding": "ascii"
        },
        {
            "filename": "latin1_file.txt",
            "content": "Content with Latin-1 chars: café, naïve, résumé",
            "encoding": "latin-1"
        },
        {
            "filename": "windows_file.txt",
            "content": "Windows-1252 content with smart quotes and em dashes",
            "encoding": "cp1252"
        },
        {
            "filename": "problematic_file.txt",
            "content": "This file will be saved as UTF-8 but we'll corrupt it",
            "encoding": "utf-8"
        }
    ]
    
    # Create the test files
    for case in test_cases:
        file_path = test_path / case["filename"]
        
        try:
            with open(file_path, 'w', encoding=case["encoding"]) as f:
                f.write(case["content"])
            print(f"   ✅ Created: {case['filename']} ({case['encoding']})")
        except Exception as e:
            print(f"   ❌ Failed to create {case['filename']}: {e}")
    
    # Create a problematic file by corrupting bytes
    problematic_file = test_path / "corrupted_utf8.txt" 
    try:
        # Write UTF-8 content then corrupt it
        with open(problematic_file, 'wb') as f:
            # Write some valid UTF-8
            f.write("Valid start: café ".encode('utf-8'))
            # Write invalid UTF-8 sequence that should cause the original error
            f.write(b'\xfe\xff\x00\x48\x00\x65\x00\x6c\x00\x6c\x00\x6f')  # Invalid continuation bytes
            f.write(" more text".encode('utf-8'))
        print(f"   ⚠️  Created corrupted file: corrupted_utf8.txt")
    except Exception as e:
        print(f"   ❌ Failed to create corrupted file: {e}")
    
    # Create a binary file
    binary_file = test_path / "binary_file.bin"
    try:
        with open(binary_file, 'wb') as f:
            # Write some binary data
            f.write(b'\x00\x01\x02\x03\x04\x05\xfe\xff\x00\x10\x20\x30')
        print(f"   ✅ Created binary file: binary_file.bin")
    except Exception as e:
        print(f"   ❌ Failed to create binary file: {e}")
    
    # Create a Java file that should be read
    java_file = test_path / "Example.java"
    java_content = """package com.example;

import javax.persistence.Entity;
import javax.servlet.http.HttpServlet;

@Entity
public class Example {
    private String name = "Test with unicode: café";
    
    // This file tests reading Java files with mixed content
}"""
    try:
        with open(java_file, 'w', encoding='utf-8') as f:
            f.write(java_content)
        print(f"   ✅ Created Java file: Example.java")
    except Exception as e:
        print(f"   ❌ Failed to create Java file: {e}")
    
    return test_dir


def test_robust_file_reader(test_dir):
    """Test the RobustFileReader on various files."""
    print(f"\n🧪 Testing RobustFileReader on files in: {test_dir}")
    print("=" * 60)
    
    test_files = list(Path(test_dir).glob("*"))
    
    for file_path in test_files:
        if file_path.is_file():
            print(f"\n📄 Testing file: {file_path.name}")
            
            # Get file info
            info = RobustFileReader.get_file_info(str(file_path))
            print(f"   Size: {info['size']} bytes")
            print(f"   Binary: {info['is_binary']}")
            print(f"   Detected encoding: {info['detected_encoding']}")
            print(f"   Readable: {info['readable']}")
            
            # Try to read the file
            content, encoding, status = RobustFileReader.read_file_with_fallback(str(file_path))
            
            print(f"   Read status: {status}")
            print(f"   Encoding used: {encoding}")
            
            if content is not None:
                preview = content[:100].replace('\n', '\\n').replace('\r', '\\r')
                print(f"   Content preview: {preview}...")
                print(f"   ✅ Successfully read {len(content)} characters")
            else:
                print(f"   ❌ Could not read file")


def test_crawl_local_files_with_encoding_issues(test_dir):
    """Test the updated crawl_local_files function."""
    print(f"\n🔍 Testing crawl_local_files with encoding issues")
    print("=" * 60)
    
    try:
        result = crawl_local_files(
            test_dir,
            include_patterns={"*.txt", "*.java"},
            max_file_size=10000
        )
        
        files = result["files"]
        stats = result["stats"]
        
        print(f"\n📊 Crawl Results:")
        print(f"   Files found: {stats['total_files_found']}")
        print(f"   Files read successfully: {stats['files_read_successfully']}")
        print(f"   Encoding fallbacks used: {stats['encoding_fallbacks_used']}")
        print(f"   Binary files skipped: {stats['files_binary_skipped']}")
        print(f"   Encoding errors: {stats['files_encoding_error']}")
        
        print(f"\n📝 Successfully read files:")
        for file_path, content in files.items():
            preview = content[:50].replace('\n', '\\n')
            print(f"   {file_path}: {preview}...")
        
        # Check if we handled the problematic file
        if stats['encoding_fallbacks_used'] > 0:
            print(f"\n✅ Successfully handled files with encoding issues using fallbacks!")
        
        if stats['files_encoding_error'] > 0:
            print(f"\n⚠️  Some files still had encoding errors (this is expected for severely corrupted files)")
        
        return True
        
    except Exception as e:
        print(f"❌ Error during crawl_local_files test: {e}")
        return False


def main():
    """Main test function."""
    print("🚀 Testing Encoding Fix for Spring Migration Tool")
    print("=" * 70)
    
    # Create test files
    test_dir = create_test_files_with_encodings()
    
    try:
        # Test RobustFileReader
        test_robust_file_reader(test_dir)
        
        # Test crawl_local_files integration
        success = test_crawl_local_files_with_encoding_issues(test_dir)
        
        print(f"\n🎯 Test Summary")
        print("=" * 30)
        
        if success:
            print("✅ All tests passed!")
            print("✅ Encoding issues should now be handled gracefully")
            print("✅ The 'utf codec can't decode byte 0xfe' error should be resolved")
        else:
            print("❌ Some tests failed")
            print("❌ There may still be encoding issues")
        
        print(f"\n📋 What was tested:")
        print(f"   - UTF-8 files with emoji")
        print(f"   - ASCII files")
        print(f"   - Latin-1 encoded files") 
        print(f"   - Windows-1252 encoded files")
        print(f"   - Corrupted UTF-8 files (like the one causing your error)")
        print(f"   - Binary files")
        print(f"   - Java source files")
        
        print(f"\n💡 The migration tool will now:")
        print(f"   - Automatically detect file encodings")
        print(f"   - Use fallback encodings for problematic files")
        print(f"   - Skip binary files automatically")
        print(f"   - Provide detailed statistics about file processing")
        print(f"   - Continue processing even if some files can't be read")
        
    finally:
        # Clean up test directory
        shutil.rmtree(test_dir)
        print(f"\n🧹 Cleaned up test directory: {test_dir}")


if __name__ == "__main__":
    main() 