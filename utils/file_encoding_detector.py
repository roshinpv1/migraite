#!/usr/bin/env python3
"""
File Encoding Detection and Robust Reading Utilities

This module provides utilities to detect file encodings and read files with
multiple encoding fallbacks to handle various file types gracefully.
"""

import os
import chardet
import codecs
from typing import Optional, Tuple, Union


class RobustFileReader:
    """
    Robust file reader that can handle various encodings and problematic files.
    """
    
    # Common encodings to try in order of preference
    ENCODING_CANDIDATES = [
        'utf-8',
        'utf-8-sig',  # UTF-8 with BOM
        'latin-1',    # ISO-8859-1 (very permissive)
        'cp1252',     # Windows-1252 (common on Windows)
        'ascii',      # Basic ASCII
        'iso-8859-1', # Alternative Latin-1
        'cp850',      # IBM Code Page 850
        'utf-16',     # UTF-16 with BOM detection
        'utf-16le',   # UTF-16 Little Endian
        'utf-16be',   # UTF-16 Big Endian
    ]
    
    @staticmethod
    def detect_encoding(file_path: str, sample_size: int = 8192) -> Optional[str]:
        """
        Detect file encoding using chardet library.
        
        Args:
            file_path: Path to the file
            sample_size: Number of bytes to read for detection
            
        Returns:
            Detected encoding or None if detection fails
        """
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read(sample_size)
                
            if not raw_data:
                return 'utf-8'  # Default for empty files
                
            result = chardet.detect(raw_data)
            
            if result and result['encoding']:
                confidence = result.get('confidence', 0)
                encoding = result['encoding'].lower()
                
                # Only trust high confidence detections
                if confidence > 0.7:
                    return encoding
                elif confidence > 0.5:
                    # Medium confidence - validate with known good encodings
                    if encoding in ['utf-8', 'ascii', 'windows-1252', 'iso-8859-1']:
                        return encoding
            
            return None
            
        except Exception:
            return None
    
    @staticmethod
    def is_binary_file(file_path: str, sample_size: int = 1024) -> bool:
        """
        Check if a file appears to be binary by looking for null bytes.
        
        Args:
            file_path: Path to the file
            sample_size: Number of bytes to check
            
        Returns:
            True if file appears to be binary
        """
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(sample_size)
                
            # Check for null bytes (common in binary files)
            if b'\x00' in chunk:
                return True
                
            # Check for high ratio of non-printable characters
            if len(chunk) > 0:
                printable_chars = sum(1 for byte in chunk if 32 <= byte <= 126 or byte in [9, 10, 13])
                printable_ratio = printable_chars / len(chunk)
                
                # If less than 70% printable characters, likely binary
                if printable_ratio < 0.7:
                    return True
            
            return False
            
        except Exception:
            return True  # Assume binary if we can't read it
    
    @staticmethod
    def read_file_with_fallback(file_path: str, max_file_size: int = None) -> Tuple[Optional[str], str, str]:
        """
        Read a file with multiple encoding fallbacks.
        
        Args:
            file_path: Path to the file to read
            max_file_size: Maximum file size in bytes (None for no limit)
            
        Returns:
            Tuple of (content, encoding_used, status)
            - content: File content as string or None if failed
            - encoding_used: The encoding that worked
            - status: Status message ('success', 'binary_skipped', 'size_skipped', 'encoding_error', 'other_error')
        """
        try:
            # Check if file exists
            if not os.path.exists(file_path):
                return None, '', 'file_not_found'
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if max_file_size and file_size > max_file_size:
                return None, '', 'size_skipped'
            
            # Check if file is binary
            if RobustFileReader.is_binary_file(file_path):
                return None, '', 'binary_skipped'
            
            # Try to detect encoding
            detected_encoding = RobustFileReader.detect_encoding(file_path)
            
            # Create list of encodings to try
            encodings_to_try = []
            
            if detected_encoding:
                encodings_to_try.append(detected_encoding)
            
            # Add standard candidates
            for encoding in RobustFileReader.ENCODING_CANDIDATES:
                if encoding not in encodings_to_try:
                    encodings_to_try.append(encoding)
            
            # Try each encoding
            for encoding in encodings_to_try:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='strict') as f:
                        content = f.read()
                    return content, encoding, 'success'
                    
                except UnicodeDecodeError:
                    continue
                except LookupError:
                    # Invalid encoding name
                    continue
                except Exception:
                    continue
            
            # If all encodings failed, try with error handling
            for encoding in ['utf-8', 'latin-1']:
                try:
                    with open(file_path, 'r', encoding=encoding, errors='replace') as f:
                        content = f.read()
                    return content, f"{encoding}_with_replacement", 'success_with_replacement'
                except Exception:
                    continue
            
            return None, '', 'encoding_error'
            
        except Exception as e:
            return None, '', f'other_error: {str(e)}'
    
    @staticmethod
    def get_file_info(file_path: str) -> dict:
        """
        Get comprehensive information about a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dictionary with file information
        """
        info = {
            'path': file_path,
            'exists': False,
            'size': 0,
            'is_binary': None,
            'detected_encoding': None,
            'readable': False,
            'error': None
        }
        
        try:
            if os.path.exists(file_path):
                info['exists'] = True
                info['size'] = os.path.getsize(file_path)
                info['is_binary'] = RobustFileReader.is_binary_file(file_path)
                
                if not info['is_binary']:
                    info['detected_encoding'] = RobustFileReader.detect_encoding(file_path)
                    
                    # Test if file is readable
                    content, encoding, status = RobustFileReader.read_file_with_fallback(file_path, max_file_size=1024)
                    info['readable'] = (content is not None)
                    info['test_encoding'] = encoding
                    info['test_status'] = status
                else:
                    info['readable'] = False
                    
        except Exception as e:
            info['error'] = str(e)
        
        return info


def test_robust_file_reader():
    """Test function for the robust file reader."""
    print("🧪 Testing Robust File Reader")
    print("=" * 50)
    
    # Test with a known file
    test_files = [
        __file__,  # This Python file
        '/etc/passwd',  # Unix system file (if exists)
        'nonexistent.txt',  # Non-existent file
    ]
    
    for file_path in test_files:
        print(f"\n📄 Testing: {file_path}")
        
        # Get file info
        info = RobustFileReader.get_file_info(file_path)
        print(f"   Exists: {info['exists']}")
        if info['exists']:
            print(f"   Size: {info['size']} bytes")
            print(f"   Binary: {info['is_binary']}")
            print(f"   Detected encoding: {info['detected_encoding']}")
            print(f"   Readable: {info['readable']}")
            
        # Try to read
        content, encoding, status = RobustFileReader.read_file_with_fallback(file_path, max_file_size=1024)
        print(f"   Read status: {status}")
        print(f"   Encoding used: {encoding}")
        if content:
            print(f"   Content preview: {content[:100]}...")


if __name__ == "__main__":
    test_robust_file_reader() 