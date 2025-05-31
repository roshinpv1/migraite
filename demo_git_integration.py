#!/usr/bin/env python3
"""
Demo: Git Integration for Spring Migration

This script demonstrates the complete Git integration workflow for Spring migration,
including branch creation, change application, committing, and push operations.
"""

import os
import subprocess
import tempfile
import shutil
from datetime import datetime

def create_demo_spring_project():
    """Create a demo Spring project with Git repository for testing."""
    
    # Create temporary directory for demo
    demo_dir = os.path.join(tempfile.gettempdir(), f"spring-migration-demo-{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(demo_dir, exist_ok=True)
    
    print(f"📁 Creating demo Spring project at: {demo_dir}")
    
    # Initialize Git repository
    subprocess.run(["git", "init"], cwd=demo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Demo User"], cwd=demo_dir, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "demo@example.com"], cwd=demo_dir, check=True, capture_output=True)
    
    # Create Spring project structure
    os.makedirs(os.path.join(demo_dir, "src/main/java/com/example/app/entity"), exist_ok=True)
    os.makedirs(os.path.join(demo_dir, "src/main/java/com/example/app/controller"), exist_ok=True)
    os.makedirs(os.path.join(demo_dir, "src/main/java/com/example/app/service"), exist_ok=True)
    os.makedirs(os.path.join(demo_dir, "src/main/java/com/example/app/repository"), exist_ok=True)
    os.makedirs(os.path.join(demo_dir, "src/main/resources"), exist_ok=True)
    os.makedirs(os.path.join(demo_dir, "src/test/java/com/example/app"), exist_ok=True)
    
    # Create pom.xml with Spring 5 dependencies
    pom_content = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>spring-migration-demo</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>
    
    <name>Spring Migration Demo</name>
    <description>Demo project for Spring 5 to 6 migration</description>
    
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <spring.version>5.3.23</spring.version>
        <spring.boot.version>2.7.5</spring.boot.version>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
            <version>${spring.boot.version}</version>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
            <version>${spring.boot.version}</version>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
            <version>${spring.boot.version}</version>
        </dependency>
    </dependencies>
</project>"""
    
    with open(os.path.join(demo_dir, "pom.xml"), "w") as f:
        f.write(pom_content)
    
    # Create User entity with javax imports
    user_entity = """package com.example.app.entity;

import javax.persistence.*;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Email;
import javax.validation.constraints.Size;

@Entity
@Table(name = "users")
public class User {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @NotNull
    @Size(min = 2, max = 50)
    @Column(name = "username", unique = true)
    private String username;
    
    @Email
    @NotNull
    @Column(name = "email", unique = true)
    private String email;
    
    @NotNull
    @Size(min = 6, max = 100)
    @Column(name = "password")
    private String password;
    
    // Constructors
    public User() {}
    
    public User(String username, String email, String password) {
        this.username = username;
        this.email = email;
        this.password = password;
    }
    
    // Getters and setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
    
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
}"""
    
    with open(os.path.join(demo_dir, "src/main/java/com/example/app/entity/User.java"), "w") as f:
        f.write(user_entity)
    
    # Create UserController with Spring MVC
    user_controller = """package com.example.app.controller;

import com.example.app.entity.User;
import com.example.app.service.UserService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.List;

@RestController
@RequestMapping("/api/users")
public class UserController {
    
    @Autowired
    private UserService userService;
    
    @GetMapping
    public List<User> getAllUsers() {
        return userService.findAll();
    }
    
    @GetMapping("/{id}")
    public ResponseEntity<User> getUserById(@PathVariable Long id) {
        User user = userService.findById(id);
        if (user != null) {
            return ResponseEntity.ok(user);
        }
        return ResponseEntity.notFound().build();
    }
    
    @PostMapping
    public User createUser(@Valid @RequestBody User user) {
        return userService.save(user);
    }
    
    @PutMapping("/{id}")
    public ResponseEntity<User> updateUser(@PathVariable Long id, @Valid @RequestBody User userDetails) {
        User user = userService.findById(id);
        if (user != null) {
            user.setUsername(userDetails.getUsername());
            user.setEmail(userDetails.getEmail());
            user.setPassword(userDetails.getPassword());
            return ResponseEntity.ok(userService.save(user));
        }
        return ResponseEntity.notFound().build();
    }
    
    @DeleteMapping("/{id}")
    public ResponseEntity<?> deleteUser(@PathVariable Long id) {
        User user = userService.findById(id);
        if (user != null) {
            userService.delete(id);
            return ResponseEntity.ok().build();
        }
        return ResponseEntity.notFound().build();
    }
}"""
    
    with open(os.path.join(demo_dir, "src/main/java/com/example/app/controller/UserController.java"), "w") as f:
        f.write(user_controller)
    
    # Create UserService with Spring annotations
    user_service = """package com.example.app.service;

import com.example.app.entity.User;
import com.example.app.repository.UserRepository;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import javax.transaction.Transactional;
import java.util.List;
import java.util.Optional;

@Service
@Transactional
public class UserService {
    
    @Autowired
    private UserRepository userRepository;
    
    public List<User> findAll() {
        return userRepository.findAll();
    }
    
    public User findById(Long id) {
        Optional<User> user = userRepository.findById(id);
        return user.orElse(null);
    }
    
    public User save(User user) {
        return userRepository.save(user);
    }
    
    public void delete(Long id) {
        userRepository.deleteById(id);
    }
    
    public User findByUsername(String username) {
        return userRepository.findByUsername(username);
    }
    
    public User findByEmail(String email) {
        return userRepository.findByEmail(email);
    }
}"""
    
    with open(os.path.join(demo_dir, "src/main/java/com/example/app/service/UserService.java"), "w") as f:
        f.write(user_service)
    
    # Create UserRepository with Spring Data JPA
    user_repository = """package com.example.app.repository;

import com.example.app.entity.User;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    User findByUsername(String username);
    User findByEmail(String email);
}"""
    
    with open(os.path.join(demo_dir, "src/main/java/com/example/app/repository/UserRepository.java"), "w") as f:
        f.write(user_repository)
    
    # Create application.properties
    app_properties = """spring.application.name=spring-migration-demo
spring.datasource.url=jdbc:h2:mem:testdb
spring.datasource.driverClassName=org.h2.Driver
spring.datasource.username=sa
spring.datasource.password=
spring.jpa.database-platform=org.hibernate.dialect.H2Dialect
spring.jpa.hibernate.ddl-auto=create-drop
spring.h2.console.enabled=true
server.port=8080"""
    
    with open(os.path.join(demo_dir, "src/main/resources/application.properties"), "w") as f:
        f.write(app_properties)
    
    # Create main application class
    main_app = """package com.example.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SpringMigrationDemoApplication {
    
    public static void main(String[] args) {
        SpringApplication.run(SpringMigrationDemoApplication.class, args);
    }
}"""
    
    with open(os.path.join(demo_dir, "src/main/java/com/example/app/SpringMigrationDemoApplication.java"), "w") as f:
        f.write(main_app)
    
    # Create README
    readme = """# Spring Migration Demo Project

This is a demo Spring Boot project created to demonstrate the Spring 5 to 6 migration process.

## Features
- Spring Boot 2.7.5 (needs migration to 3.x)
- Spring Security (legacy configuration)
- Spring Data JPA with javax.* annotations (needs jakarta.* migration)
- RESTful API with validation
- H2 in-memory database

## Migration Tasks
1. Update Spring Boot version from 2.7.5 to 3.x
2. Migrate javax.* imports to jakarta.*
3. Update Spring Security configuration
4. Test and validate changes

## Usage
This project is used with the AI Codebase Migration Tool for automated Spring migration.
"""
    
    with open(os.path.join(demo_dir, "README.md"), "w") as f:
        f.write(readme)
    
    # Create initial Git commit
    subprocess.run(["git", "add", "."], cwd=demo_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial Spring 5 project setup"], cwd=demo_dir, check=True, capture_output=True)
    
    print(f"✅ Demo Spring project created successfully!")
    print(f"📁 Project location: {demo_dir}")
    print(f"🔍 Features:")
    print(f"   - Spring Boot 2.7.5 with javax.* imports")
    print(f"   - JPA entities, controllers, services, repositories")
    print(f"   - Git repository with initial commit")
    print(f"   - Ready for Spring 5 → 6 migration")
    
    return demo_dir

def demonstrate_git_integration(project_dir):
    """Demonstrate the Git integration workflow."""
    
    print(f"\n" + "="*60)
    print(f"🚀 DEMONSTRATING GIT INTEGRATION WORKFLOW")
    print(f"="*60)
    
    print(f"\n1. 📋 Current Git Status:")
    result = subprocess.run(["git", "status", "--short"], cwd=project_dir, capture_output=True, text=True)
    if result.stdout.strip():
        print(f"   Changes detected: {len(result.stdout.strip().split())}")
        print(f"   {result.stdout}")
    else:
        print(f"   ✅ Working directory is clean")
    
    print(f"\n2. 🌿 Current Branch:")
    result = subprocess.run(["git", "branch", "--show-current"], cwd=project_dir, capture_output=True, text=True)
    current_branch = result.stdout.strip()
    print(f"   📍 {current_branch}")
    
    print(f"\n3. 🔗 Remote Repository:")
    result = subprocess.run(["git", "config", "--get", "remote.origin.url"], cwd=project_dir, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"   🌐 {result.stdout.strip()}")
    else:
        print(f"   📍 Local repository only (no remote configured)")
    
    print(f"\n4. 🔍 File Analysis:")
    java_files = []
    for root, dirs, files in os.walk(project_dir):
        for file in files:
            if file.endswith('.java'):
                java_files.append(os.path.relpath(os.path.join(root, file), project_dir))
    
    print(f"   📄 Java files found: {len(java_files)}")
    for java_file in java_files[:5]:  # Show first 5
        print(f"      - {java_file}")
    if len(java_files) > 5:
        print(f"      - ... and {len(java_files) - 5} more")
    
    print(f"\n🎯 Ready for migration command:")
    print(f"   python main.py spring-migration {project_dir} --apply-changes --git-integration")
    
    return project_dir

def show_expected_workflow():
    """Show what the expected Git integration workflow looks like."""
    
    print(f"\n" + "="*60)
    print(f"📋 EXPECTED GIT INTEGRATION WORKFLOW")
    print(f"="*60)
    
    workflow_steps = [
        "🔍 Analysis & LLM-powered change detection",
        "📦 Automatic backup creation (timestamped)",
        "✅ User confirmation of detected changes",
        "🔧 Apply approved automatic changes",
        "🌿 Create migration branch (spring-migration-YYYYMMDD_HHMMSS)",
        "📊 Show detailed diff summary",
        "💾 User decides to commit changes",
        "🚀 User decides to push to remote",
        "📝 Generate pull request template"
    ]
    
    for i, step in enumerate(workflow_steps, 1):
        print(f"   {i}. {step}")
    
    print(f"\n🛡️ SAFETY FEATURES:")
    safety_features = [
        "📦 Complete backup before any changes",
        "🌿 All changes on dedicated branch",
        "👥 Interactive user confirmation",
        "🔄 Easy rollback capabilities",
        "📋 Detailed commit messages",
        "📝 Auto-generated PR description"
    ]
    
    for feature in safety_features:
        print(f"   ✓ {feature}")

def main():
    """Main demonstration function."""
    
    print("🔀 Git Integration Demo for Spring Migration")
    print("=" * 50)
    
    try:
        # Check if git is available
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        print("✅ Git is available")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Git is not available. Please install Git first.")
        return
    
    print("\n📁 Creating demo Spring project...")
    project_dir = create_demo_spring_project()
    
    print("\n🔍 Analyzing project structure...")
    demonstrate_git_integration(project_dir)
    
    show_expected_workflow()
    
    print(f"\n" + "="*60)
    print(f"🎯 NEXT STEPS")
    print(f"="*60)
    print(f"1. Run the migration tool:")
    print(f"   cd {os.path.dirname(os.path.abspath(__file__))}")
    print(f"   python main.py spring-migration {project_dir} --apply-changes --git-integration")
    print(f"")
    print(f"2. Follow the interactive prompts for:")
    print(f"   - Confirming detected changes")
    print(f"   - Committing to Git")
    print(f"   - Pushing to remote (if configured)")
    print(f"")
    print(f"3. Clean up when done:")
    print(f"   rm -rf {project_dir}")
    
    print(f"\n💡 This demo shows how the Git integration seamlessly handles:")
    print(f"   🔄 Branch management")
    print(f"   📊 Change analysis and diff summaries") 
    print(f"   💾 Automated commits with detailed messages")
    print(f"   🚀 Optional remote push")
    print(f"   📝 Pull request template generation")

if __name__ == "__main__":
    main() 