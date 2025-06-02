#!/usr/bin/env python3
"""
Unit tests for crawl_local_files function

Tests the file crawling functionality after removing Excel-specific handling.
"""

import os
import tempfile
import shutil
import unittest
from pathlib import Path
from utils.crawl_local_files import crawl_local_files


class TestCrawlLocalFiles(unittest.TestCase):
    """Test cases for crawl_local_files function"""
    
    def setUp(self):
        """Set up test directory structure"""
        self.test_dir = tempfile.mkdtemp(prefix="test_crawl_")
        self.test_path = Path(self.test_dir)
        
        # Create test directory structure
        (self.test_path / "src" / "main" / "java").mkdir(parents=True)
        (self.test_path / "src" / "main" / "resources").mkdir(parents=True)
        (self.test_path / "src" / "test" / "java").mkdir(parents=True)
        (self.test_path / "target").mkdir()
        (self.test_path / "node_modules").mkdir()
        
        # Create test files
        (self.test_path / "pom.xml").write_text("<?xml version='1.0'?>\n<project/>")
        (self.test_path / "README.md").write_text("# Test Project")
        (self.test_path / "src" / "main" / "java" / "App.java").write_text("public class App {}")
        (self.test_path / "src" / "main" / "resources" / "application.properties").write_text("server.port=8080")
        (self.test_path / "src" / "test" / "java" / "AppTest.java").write_text("public class AppTest {}")
        (self.test_path / "target" / "App.class").write_text("compiled code")
        (self.test_path / "node_modules" / "package.json").write_text('{"name": "test"}')
        
        # Create .gitignore
        (self.test_path / ".gitignore").write_text("target/\nnode_modules/\n*.class\n")
        
        # Create some files with different extensions (testing former Excel logic is gone)
        (self.test_path / "data.csv").write_text("name,age\nJohn,30")
        (self.test_path / "report.xlsx").write_text("fake excel content")  # This should be treated as regular file
        
    def tearDown(self):
        """Clean up test directory"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_basic_file_crawling(self):
        """Test basic file crawling without filters"""
        result = crawl_local_files(self.test_dir)
        files = result["files"]
        
        # Check that we get files
        self.assertGreater(len(files), 0)
        
        # Check specific files are included
        self.assertIn("pom.xml", files)
        self.assertIn("README.md", files)
        self.assertIn("src/main/java/App.java", files)
        
        # Check content is correct
        self.assertEqual(files["pom.xml"], "<?xml version='1.0'?>\n<project/>")
        self.assertEqual(files["README.md"], "# Test Project")
    
    def test_gitignore_exclusion(self):
        """Test that .gitignore patterns are respected"""
        result = crawl_local_files(self.test_dir)
        files = result["files"]
        
        # Should exclude target/ and node_modules/ due to .gitignore
        target_files = [f for f in files.keys() if f.startswith("target/")]
        node_files = [f for f in files.keys() if f.startswith("node_modules/")]
        
        self.assertEqual(len(target_files), 0, "target/ files should be excluded by .gitignore")
        self.assertEqual(len(node_files), 0, "node_modules/ files should be excluded by .gitignore")
    
    def test_include_patterns(self):
        """Test include patterns filtering"""
        result = crawl_local_files(
            self.test_dir,
            include_patterns={"*.java", "*.xml"}
        )
        files = result["files"]
        
        # Should only include Java and XML files
        self.assertIn("pom.xml", files)
        self.assertIn("src/main/java/App.java", files)
        self.assertIn("src/test/java/AppTest.java", files)
        
        # Should not include other file types
        self.assertNotIn("README.md", files)
        self.assertNotIn("src/main/resources/application.properties", files)
    
    def test_exclude_patterns(self):
        """Test exclude patterns filtering"""
        result = crawl_local_files(
            self.test_dir,
            exclude_patterns={"*.md"}  # Only excluding markdown files, not test files
        )
        files = result["files"]
        
        # Should exclude markdown files
        md_files = [f for f in files.keys() if f.endswith(".md")]
        self.assertEqual(len(md_files), 0, "*.md files should be excluded")
        
        # Should now INCLUDE test files (since we removed test exclusions)
        self.assertIn("src/test/java/AppTest.java", files)
        
        # Should still include other files
        self.assertIn("pom.xml", files)
        self.assertIn("src/main/java/App.java", files)
    
    def test_file_size_limit(self):
        """Test file size limiting"""
        # Create a large file
        large_content = "x" * 1000  # 1KB file
        (self.test_path / "large.txt").write_text(large_content)
        
        # Set max_file_size to 500 bytes
        result = crawl_local_files(
            self.test_dir,
            max_file_size=500
        )
        files = result["files"]
        
        # Large file should be excluded
        self.assertNotIn("large.txt", files)
        
        # Small files should still be included
        self.assertIn("pom.xml", files)
    
    def test_former_excel_handling_removed(self):
        """Test that files with Excel-like extensions are treated as regular files"""
        result = crawl_local_files(self.test_dir)
        files = result["files"]
        
        # These files should be treated normally, not with special Excel logic
        self.assertIn("data.csv", files)
        self.assertIn("report.xlsx", files)
        
        # Content should be read normally
        self.assertEqual(files["data.csv"], "name,age\nJohn,30")
        self.assertEqual(files["report.xlsx"], "fake excel content")
    
    def test_relative_vs_absolute_paths(self):
        """Test relative vs absolute path options"""
        # Test with relative paths (default)
        result_relative = crawl_local_files(self.test_dir, use_relative_paths=True)
        
        # Test with absolute paths
        result_absolute = crawl_local_files(self.test_dir, use_relative_paths=False)
        
        # Check that we get the same files but with different path formats
        self.assertEqual(len(result_relative["files"]), len(result_absolute["files"]))
        
        # Relative paths should not start with the test_dir
        relative_files = list(result_relative["files"].keys())
        for filepath in relative_files:
            self.assertFalse(filepath.startswith(self.test_dir))
        
        # Absolute paths should start with the test_dir
        absolute_files = list(result_absolute["files"].keys())
        for filepath in absolute_files:
            self.assertTrue(filepath.startswith(self.test_dir))
    
    def test_nonexistent_directory(self):
        """Test handling of nonexistent directory"""
        nonexistent_dir = "/path/that/does/not/exist"
        
        with self.assertRaises(ValueError) as cm:
            crawl_local_files(nonexistent_dir)
        
        self.assertIn("Directory does not exist", str(cm.exception))
    
    def test_empty_directory(self):
        """Test handling of empty directory"""
        empty_dir = tempfile.mkdtemp(prefix="empty_test_")
        try:
            result = crawl_local_files(empty_dir)
            self.assertEqual(len(result["files"]), 0)
        finally:
            shutil.rmtree(empty_dir)
    
    def test_complex_filtering_combination(self):
        """Test complex combination of include/exclude patterns"""
        result = crawl_local_files(
            self.test_dir,
            include_patterns={"*.java", "*.xml", "*.properties"},
            exclude_patterns={"*.md"}  # Only excluding markdown, not test files
        )
        files = result["files"]
        
        # Should include Java, XML, and properties files
        self.assertIn("pom.xml", files)
        self.assertIn("src/main/java/App.java", files)
        self.assertIn("src/main/resources/application.properties", files)
        
        # Should now INCLUDE test files (since we removed test exclusions)
        self.assertIn("src/test/java/AppTest.java", files)
        
        # Should exclude other file types
        self.assertNotIn("README.md", files)
        self.assertNotIn("data.csv", files)


class TestCrawlLocalFilesIntegration(unittest.TestCase):
    """Integration tests simulating real Spring project scenarios"""
    
    def setUp(self):
        """Create a realistic Spring project structure"""
        self.test_dir = tempfile.mkdtemp(prefix="spring_test_")
        self.test_path = Path(self.test_dir)
        
        # Create Maven structure
        (self.test_path / "src" / "main" / "java" / "com" / "example").mkdir(parents=True)
        (self.test_path / "src" / "main" / "resources").mkdir(parents=True)
        (self.test_path / "src" / "test" / "java" / "com" / "example").mkdir(parents=True)
        
        # Create Spring Boot files
        (self.test_path / "pom.xml").write_text("""<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.18</version>
    </parent>
    <groupId>com.example</groupId>
    <artifactId>spring-app</artifactId>
</project>""")
        
        (self.test_path / "src" / "main" / "java" / "com" / "example" / "Application.java").write_text("""
package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
    public static void main(String[] args) {
        SpringApplication.run(Application.class, args);
    }
}""")
        
        (self.test_path / "src" / "main" / "resources" / "application.yml").write_text("""
server:
  port: 8080
spring:
  datasource:
    url: jdbc:h2:mem:testdb""")
    
    def tearDown(self):
        """Clean up test directory"""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    def test_spring_project_crawling(self):
        """Test crawling a typical Spring Boot project"""
        result = crawl_local_files(
            self.test_dir,
            include_patterns={"*.java", "*.xml", "*.yml", "*.properties"}
        )
        files = result["files"]
        
        # Should include all Spring-related files
        self.assertIn("pom.xml", files)
        self.assertIn("src/main/java/com/example/Application.java", files)
        self.assertIn("src/main/resources/application.yml", files)
        
        # Check content is properly read
        self.assertIn("SpringBootApplication", files["src/main/java/com/example/Application.java"])
        self.assertIn("spring-boot-starter-parent", files["pom.xml"])
        self.assertIn("server:", files["src/main/resources/application.yml"])


def run_tests():
    """Run all tests"""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTest(loader.loadTestsFromTestCase(TestCrawlLocalFiles))
    suite.addTest(loader.loadTestsFromTestCase(TestCrawlLocalFilesIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Return success status
    return result.wasSuccessful()


if __name__ == "__main__":
    print("🧪 Running crawl_local_files unit tests...\n")
    
    success = run_tests()
    
    if success:
        print("\n✅ All tests passed!")
        print("📝 The crawl_local_files function works correctly after Excel handling removal.")
    else:
        print("\n❌ Some tests failed!")
        print("🔧 Please check the implementation.")
    
    print("\n📋 Test Coverage:")
    print("   ✓ Basic file crawling")
    print("   ✓ .gitignore exclusion") 
    print("   ✓ Include/exclude patterns")
    print("   ✓ File size limits")
    print("   ✓ Former Excel handling removed")
    print("   ✓ Relative vs absolute paths")
    print("   ✓ Error handling")
    print("   ✓ Spring project integration") 