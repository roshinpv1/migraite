#!/usr/bin/env python3
"""
Demo: Timeout Handling and Large Repository Features

This script demonstrates the enhanced timeout handling and large repository
optimization features that address the issues seen in enterprise-scale codebases.
"""

import os
import tempfile
import time
from datetime import datetime


def create_large_test_project():
    """Create a test project that simulates timeout scenarios."""
    
    demo_dir = os.path.join(tempfile.gettempdir(), f"timeout-demo-{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(demo_dir, exist_ok=True)
    
    print(f"🏗️ Creating large test Spring project at: {demo_dir}")
    
    # Create a realistic large Spring project structure
    modules = ["core", "web", "api", "service", "repository", "config", "security", "dto", "util"]
    
    file_count = 0
    for module in modules:
        module_dir = os.path.join(demo_dir, f"src/main/java/com/example/{module}")
        os.makedirs(module_dir, exist_ok=True)
        
        # Create many Java files to simulate large codebase
        for i in range(150):  # 150 files per module = 1350 total files
            java_file = os.path.join(module_dir, f"{module.capitalize()}Component{i}.java")
            
            # Create Java content that includes Spring annotations and javax imports
            java_content = f"""package com.example.{module};

import javax.persistence.Entity;
import javax.persistence.Id;
import javax.servlet.http.HttpServletRequest;
import javax.validation.Valid;
import org.springframework.stereotype.Component;
import org.springframework.stereotype.Service;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;

/**
 * {module.capitalize()} component {i} - Generated for timeout testing
 * This file contains deprecated Spring Boot 2.x patterns that need migration
 */
@Component
@Service
@RestController
@RequestMapping("/{module}")
public class {module.capitalize()}Component{i} extends WebSecurityConfigurerAdapter {{
    
    @Id
    private Long id;
    
    @GetMapping("/test{i}")
    public String test{i}(@Valid HttpServletRequest request) {{
        // This method uses deprecated patterns
        return "{module} component {i} test";
    }}
    
    @Override
    protected void configure(HttpSecurity http) throws Exception {{
        // Deprecated WebSecurityConfigurerAdapter usage
        http.authorizeRequests()
            .anyRequest().authenticated()
            .and()
            .formLogin();
    }}
    
    // Simulate complex business logic that makes large prompts
    public void complexBusinessLogic{i}() {{
        // Large method to increase file size
        String complexLogic = \"\"\"
            This is a complex business method that contains:
            - Multiple javax.* imports that need Jakarta migration
            - Deprecated Spring Security configuration  
            - Spring Boot 2.x patterns
            - Complex validation logic
            - Database persistence code
            - Web layer interactions
            - Service layer orchestration
            - Repository access patterns
            - Configuration management
            - Error handling patterns
            
            All of this contributes to large LLM prompts that can cause timeouts
            in enterprise-scale repositories with 500+ files.
            \"\"\";
    }}
}}
"""
            
            with open(java_file, 'w') as f:
                f.write(java_content)
            file_count += 1
    
    # Create build files
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.5</version>
        <relativePath/>
    </parent>
    <groupId>com.example</groupId>
    <artifactId>timeout-demo</artifactId>
    <version>0.0.1-SNAPSHOT</version>
    <name>timeout-demo</name>
    <description>Demo project for timeout handling</description>
    
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>javax.validation</groupId>
            <artifactId>validation-api</artifactId>
            <version>2.0.1.Final</version>
        </dependency>
        <dependency>
            <groupId>javax.servlet</groupId>
            <artifactId>javax.servlet-api</artifactId>
            <scope>provided</scope>
        </dependency>
    </dependencies>
</project>
"""
    
    with open(os.path.join(demo_dir, "pom.xml"), 'w') as f:
        f.write(pom_content)
    
    # Create application properties
    app_props = """# Spring Boot 2.x configuration
server.port=8080
spring.datasource.url=jdbc:h2:mem:testdb
spring.datasource.username=sa
spring.datasource.password=
spring.jpa.hibernate.ddl-auto=update

# These properties will need migration in Spring Boot 3.x
spring.jpa.database-platform=org.hibernate.dialect.H2Dialect
management.endpoints.web.exposure.include=health,info
logging.level.org.springframework.security=DEBUG
"""
    
    props_dir = os.path.join(demo_dir, "src/main/resources")
    os.makedirs(props_dir, exist_ok=True)
    with open(os.path.join(props_dir, "application.properties"), 'w') as f:
        f.write(app_props)
    
    print(f"✅ Created large test project with {file_count} Java files")
    print(f"📂 Location: {demo_dir}")
    
    return demo_dir


def demo_timeout_scenarios():
    """Demonstrate different timeout handling scenarios."""
    
    print("\n" + "="*70)
    print("🚀 TIMEOUT HANDLING DEMO")
    print("="*70)
    
    # Create large test project
    test_dir = create_large_test_project()
    
    print(f"\n📊 Test Scenarios:")
    print(f"   1. Large repository auto-configuration")
    print(f"   2. Timeout handling with fallback analysis")
    print(f"   3. Verbose logging for debugging")
    print(f"   4. Performance optimizations")
    
    print(f"\n🔧 Testing Commands:")
    
    # Scenario 1: Basic large repository analysis with auto-configuration
    print(f"\n1️⃣ Auto-Configuration Test:")
    print(f"   python3 main.py --dir {test_dir} --verbose")
    print(f"   Expected: Auto-detects large repo and applies optimizations")
    
    # Scenario 2: Manual optimization settings
    print(f"\n2️⃣ Manual Optimization Test:")
    print(f"   python3 main.py --dir {test_dir} --parallel --max-files 200 --quick-analysis --verbose")
    print(f"   Expected: Uses manual settings for performance")
    
    # Scenario 3: Timeout simulation (if you want to test actual timeouts)
    print(f"\n3️⃣ Timeout Simulation Test:")
    print(f"   python3 main.py --dir {test_dir} --max-files 1000 --verbose")
    print(f"   Expected: May hit timeouts but should recover with fallback")
    
    # Scenario 4: Enterprise-scale settings
    print(f"\n4️⃣ Enterprise Scale Test:")
    print(f"   python3 main.py --dir {test_dir} --parallel --max-workers 8 --batch-size 50 --quick-analysis --verbose")
    print(f"   Expected: Optimized for enterprise-scale analysis")
    
    print(f"\n🔍 Key Features Being Tested:")
    print(f"   ✅ Auto-detection of large repositories (500+ Java files)")
    print(f"   ✅ Automatic optimization configuration")
    print(f"   ✅ LLM timeout handling with retries")
    print(f"   ✅ Fallback analysis when LLM fails")
    print(f"   ✅ Verbose logging for debugging")
    print(f"   ✅ Rate limiting for concurrent requests")
    print(f"   ✅ Context truncation for large prompts")
    print(f"   ✅ Structured error responses")
    
    print(f"\n💡 Solutions Implemented:")
    print(f"   🔧 Enhanced LLM call_llm() with timeout handling")
    print(f"   🔧 Intelligent prompt truncation for large contexts")
    print(f"   🔧 Rate limiting to prevent service overload")
    print(f"   🔧 Comprehensive fallback analysis")
    print(f"   🔧 Auto-configuration for large repositories")
    print(f"   🔧 Verbose logging for transparency")
    
    return test_dir


def test_verbose_logging():
    """Test verbose logging capabilities."""
    
    print(f"\n" + "="*70)
    print(f"🔍 VERBOSE LOGGING DEMO")
    print(f"="*70)
    
    from utils.verbose_logger import enable_verbose_logging, get_verbose_logger
    
    # Enable verbose logging
    enable_verbose_logging(show_timestamps=True)
    vlogger = get_verbose_logger()
    
    print(f"\n📋 Testing verbose logging features:")
    
    # Test different log types
    vlogger.section_header("Verbose Logging Demo")
    vlogger.step("Testing step logging")
    vlogger.debug("This is a debug message")
    vlogger.warning("This is a warning message")
    vlogger.success("This is a success message")
    
    # Test operation tracking
    op_start = vlogger.start_operation("demo_operation", "Testing operation tracking")
    time.sleep(1)
    vlogger.file_processing("demo.java", "Processing", "125 KB")
    vlogger.llm_call("Spring analysis", "demo.java", 15000, False)
    vlogger.performance_metric("Processing speed", 45.5, "files/sec")
    vlogger.end_operation("demo_operation", success=True, details="Demo completed")
    
    # Test progress tracking
    for i in range(1, 6):
        vlogger.progress(i, 5, "files", "Processing")
        time.sleep(0.2)
    
    vlogger.subsection_header("Demo Results")
    vlogger.optimization_applied("Demo optimization", "50% faster processing")
    vlogger.show_summary()
    
    print(f"\n✅ Verbose logging demo completed")


def main():
    """Run the timeout handling and large repository demo."""
    
    print("🚀 Spring Migration Tool - Timeout Handling & Large Repository Demo")
    print("=" * 80)
    
    print("\nThis demo shows how the enhanced Spring Migration Tool handles:")
    print("• Large repositories (500+ files)")
    print("• LLM request timeouts")
    print("• Automatic optimization configuration")
    print("• Verbose logging for debugging")
    print("• Fallback analysis when automation fails")
    
    try:
        # Test verbose logging first
        test_verbose_logging()
        
        # Run timeout scenarios demo
        test_dir = demo_timeout_scenarios()
        
        print(f"\n🎯 Next Steps:")
        print(f"1. Run one of the test commands above")
        print(f"2. Observe the auto-configuration messages")
        print(f"3. Watch verbose logging in action")
        print(f"4. See how timeouts are handled gracefully")
        
        print(f"\n📁 Test project created at: {test_dir}")
        print(f"🗑️  Remove with: rm -rf {test_dir}")
        
        # Ask if user wants to run a test
        print(f"\n❓ Would you like to run a test now? (y/n)")
        response = input().strip().lower()
        
        if response == 'y':
            print(f"\nRunning auto-configuration test...")
            import subprocess
            cmd = ["python3", "main.py", "--dir", test_dir, "--verbose"]
            print(f"Command: {' '.join(cmd)}")
            print(f"\n" + "="*50)
            subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print(f"\n⏹️ Demo interrupted by user")
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main() 