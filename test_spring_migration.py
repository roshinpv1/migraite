#!/usr/bin/env python3
"""
Test script for Spring 5 to 6 Migration Analysis

This script creates a sample Spring project structure and tests the migration analysis functionality.
"""

import os
import tempfile
import shutil
from pathlib import Path


def create_sample_spring_project():
    """Create a sample Spring Boot project structure for testing"""
    
    # Create temporary directory
    temp_dir = tempfile.mkdtemp(prefix="spring_test_")
    project_root = Path(temp_dir) / "sample-spring-app"
    project_root.mkdir()
    
    # Create Maven structure
    src_main_java = project_root / "src" / "main" / "java" / "com" / "example" / "app"
    src_main_resources = project_root / "src" / "main" / "resources"
    src_test_java = project_root / "src" / "test" / "java" / "com" / "example" / "app"
    
    src_main_java.mkdir(parents=True)
    src_main_resources.mkdir(parents=True)
    src_test_java.mkdir(parents=True)
    
    # Create pom.xml with Spring Boot 2.x dependencies
    pom_xml = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.18</version>
        <relativePath/>
    </parent>
    
    <groupId>com.example</groupId>
    <artifactId>sample-spring-app</artifactId>
    <version>1.0.0</version>
    <name>Sample Spring App</name>
    
    <properties>
        <java.version>11</java.version>
    </properties>
    
    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-data-jpa</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-security</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>mysql</groupId>
            <artifactId>mysql-connector-java</artifactId>
            <scope>runtime</scope>
        </dependency>
    </dependencies>
</project>"""
    
    (project_root / "pom.xml").write_text(pom_xml)
    
    # Create main application class
    main_app = """package com.example.app;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SampleSpringApp {
    public static void main(String[] args) {
        SpringApplication.run(SampleSpringApp.class, args);
    }
}"""
    
    (src_main_java / "SampleSpringApp.java").write_text(main_app)
    
    # Create controller with javax imports
    controller = """package com.example.app.controller;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.*;
import org.springframework.http.ResponseEntity;
import com.example.app.service.UserService;
import com.example.app.model.User;

import javax.validation.Valid;
import javax.servlet.http.HttpServletRequest;
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
    
    @PostMapping
    public ResponseEntity<User> createUser(@Valid @RequestBody User user, HttpServletRequest request) {
        User savedUser = userService.save(user);
        return ResponseEntity.ok(savedUser);
    }
}"""
    
    controller_dir = src_main_java / "controller"
    controller_dir.mkdir()
    (controller_dir / "UserController.java").write_text(controller)
    
    # Create service layer
    service = """package com.example.app.service;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import com.example.app.repository.UserRepository;
import com.example.app.model.User;
import java.util.List;

@Service
public class UserService {
    
    @Autowired
    private UserRepository userRepository;
    
    public List<User> findAll() {
        return userRepository.findAll();
    }
    
    public User save(User user) {
        return userRepository.save(user);
    }
}"""
    
    service_dir = src_main_java / "service"
    service_dir.mkdir()
    (service_dir / "UserService.java").write_text(service)
    
    # Create JPA entity with javax.persistence
    entity = """package com.example.app.model;

import javax.persistence.*;
import javax.validation.constraints.NotBlank;
import javax.validation.constraints.Email;

@Entity
@Table(name = "users")
public class User {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @NotBlank(message = "Name is required")
    @Column(nullable = false)
    private String name;
    
    @Email(message = "Email should be valid")
    @Column(unique = true, nullable = false)
    private String email;
    
    // Constructors, getters, setters
    public User() {}
    
    public User(String name, String email) {
        this.name = name;
        this.email = email;
    }
    
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
}"""
    
    model_dir = src_main_java / "model"
    model_dir.mkdir()
    (model_dir / "User.java").write_text(entity)
    
    # Create repository
    repository = """package com.example.app.repository;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import com.example.app.model.User;

@Repository
public interface UserRepository extends JpaRepository<User, Long> {
    User findByEmail(String email);
}"""
    
    repo_dir = src_main_java / "repository"
    repo_dir.mkdir()
    (repo_dir / "UserRepository.java").write_text(repository)
    
    # Create security config using deprecated WebSecurityConfigurerAdapter
    security_config = """package com.example.app.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.annotation.web.configuration.EnableWebSecurity;
import org.springframework.security.config.annotation.web.configuration.WebSecurityConfigurerAdapter;

@Configuration
@EnableWebSecurity
public class SecurityConfig extends WebSecurityConfigurerAdapter {
    
    @Override
    protected void configure(HttpSecurity http) throws Exception {
        http
            .authorizeRequests()
                .antMatchers("/api/users/**").authenticated()
                .anyRequest().permitAll()
            .and()
            .httpBasic()
            .and()
            .csrf().disable();
    }
}"""
    
    config_dir = src_main_java / "config"
    config_dir.mkdir()
    (config_dir / "SecurityConfig.java").write_text(security_config)
    
    # Create application.properties
    app_properties = """# Database configuration
spring.datasource.url=jdbc:mysql://localhost:3306/sampledb
spring.datasource.username=root
spring.datasource.password=password
spring.datasource.driver-class-name=com.mysql.cj.jdbc.Driver

# JPA configuration
spring.jpa.hibernate.ddl-auto=update
spring.jpa.show-sql=true
spring.jpa.properties.hibernate.dialect=org.hibernate.dialect.MySQL8Dialect

# Server configuration
server.port=8080

# Logging
logging.level.com.example.app=DEBUG"""
    
    (src_main_resources / "application.properties").write_text(app_properties)
    
    # Create a test class
    test_class = """package com.example.app.controller;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;

@SpringBootTest
@SpringJUnitConfig
public class UserControllerTest {
    
    @Test
    public void contextLoads() {
        // Test implementation
    }
}"""
    
    test_controller_dir = src_test_java / "controller"
    test_controller_dir.mkdir()
    (test_controller_dir / "UserControllerTest.java").write_text(test_class)
    
    return str(project_root)


def main():
    """Test the Spring migration analysis"""
    print("🚀 Creating sample Spring Boot project...")
    project_path = create_sample_spring_project()
    print(f"✅ Sample project created at: {project_path}")
    
    print("\n📋 Project structure:")
    for root, dirs, files in os.walk(project_path):
        level = root.replace(project_path, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in files:
            print(f"{subindent}{file}")
    
    print(f"\n🔧 To analyze this project, run:")
    print(f"python main.py --mode spring-migration --dir {project_path}")
    
    print(f"\n🧹 To clean up the test project:")
    print(f"rm -rf {project_path}")
    
    return project_path


if __name__ == "__main__":
    main() 