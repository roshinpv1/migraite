#!/usr/bin/env python3
"""
Demo: Enhanced Dependency Compatibility Analysis

This script demonstrates the new comprehensive dependency analysis capabilities
that check both public and internal dependencies for Spring 6 compatibility.
"""

import os
import tempfile
from datetime import datetime

def create_demo_spring_project_with_dependencies():
    """Create a demo Spring project with various dependency scenarios."""
    
    demo_dir = os.path.join(tempfile.gettempdir(), f"spring-dependency-demo-{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(demo_dir, exist_ok=True)
    
    print(f"📁 Creating demo Spring project with dependency scenarios at: {demo_dir}")
    
    # Create project structure
    os.makedirs(os.path.join(demo_dir, "src/main/java/com/example/app"), exist_ok=True)
    
    # Create Maven pom.xml with various dependency scenarios
    pom_xml = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 
         http://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>

    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>2.7.5</version>
        <relativePath/>
    </parent>

    <groupId>com.example</groupId>
    <artifactId>spring-dependency-demo</artifactId>
    <version>1.0.0</version>
    <packaging>jar</packaging>

    <properties>
        <java.version>11</java.version>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
        <hibernate.version>5.6.10.Final</hibernate.version>
        <jackson.version>2.13.4</jackson.version>
    </properties>

    <dependencies>
        <!-- Spring Boot Starters -->
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

        <!-- Database -->
        <dependency>
            <groupId>com.h2database</groupId>
            <artifactId>h2</artifactId>
            <scope>runtime</scope>
        </dependency>

        <!-- Legacy javax dependencies (need Jakarta migration) -->
        <dependency>
            <groupId>javax.persistence</groupId>
            <artifactId>javax.persistence-api</artifactId>
            <version>2.2</version>
        </dependency>
        
        <dependency>
            <groupId>javax.validation</groupId>
            <artifactId>validation-api</artifactId>
            <version>2.0.1.Final</version>
        </dependency>
        
        <dependency>
            <groupId>javax.servlet</groupId>
            <artifactId>javax.servlet-api</artifactId>
            <version>4.0.1</version>
            <scope>provided</scope>
        </dependency>

        <!-- Potentially incompatible versions -->
        <dependency>
            <groupId>org.hibernate</groupId>
            <artifactId>hibernate-core</artifactId>
            <version>5.6.10.Final</version>
        </dependency>
        
        <dependency>
            <groupId>com.fasterxml.jackson.core</groupId>
            <artifactId>jackson-databind</artifactId>
            <version>2.13.4</version>
        </dependency>

        <!-- Outdated third-party libraries -->
        <dependency>
            <groupId>org.apache.commons</groupId>
            <artifactId>commons-lang3</artifactId>
            <version>3.11</version>
        </dependency>
        
        <dependency>
            <groupId>com.google.guava</groupId>
            <artifactId>guava</artifactId>
            <version>30.1-jre</version>
        </dependency>

        <!-- Internal module dependency -->
        <dependency>
            <groupId>com.example</groupId>
            <artifactId>internal-common</artifactId>
            <version>1.0.0</version>
        </dependency>

        <!-- Test dependencies -->
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        
        <dependency>
            <groupId>org.springframework.security</groupId>
            <artifactId>spring-security-test</artifactId>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
            
            <plugin>
                <groupId>org.apache.maven.plugins</groupId>
                <artifactId>maven-compiler-plugin</artifactId>
                <version>3.8.1</version>
                <configuration>
                    <source>11</source>
                    <target>11</target>
                </configuration>
            </plugin>
        </plugins>
    </build>
</project>"""

    with open(os.path.join(demo_dir, "pom.xml"), 'w') as f:
        f.write(pom_xml)

    # Create Gradle build file with similar dependencies
    build_gradle = """plugins {
    id 'org.springframework.boot' version '2.7.5'
    id 'io.spring.dependency-management' version '1.0.15.RELEASE'
    id 'java'
}

group = 'com.example'
version = '1.0.0'
sourceCompatibility = '11'

configurations {
    compileOnly {
        extendsFrom annotationProcessor
    }
}

repositories {
    mavenCentral()
}

dependencies {
    // Spring Boot starters
    implementation 'org.springframework.boot:spring-boot-starter-web'
    implementation 'org.springframework.boot:spring-boot-starter-data-jpa'
    implementation 'org.springframework.boot:spring-boot-starter-security'
    
    // Database
    runtimeOnly 'com.h2database:h2'
    
    // Legacy javax dependencies (need Jakarta migration)
    implementation 'javax.persistence:javax.persistence-api:2.2'
    implementation 'javax.validation:validation-api:2.0.1.Final'
    compileOnly 'javax.servlet:javax.servlet-api:4.0.1'
    
    // Potentially incompatible versions
    implementation 'org.hibernate:hibernate-core:5.6.10.Final'
    implementation 'com.fasterxml.jackson.core:jackson-databind:2.13.4'
    
    // Outdated third-party libraries
    implementation 'org.apache.commons:commons-lang3:3.11'
    implementation 'com.google.guava:guava:30.1-jre'
    
    // Internal module
    implementation 'com.example:internal-common:1.0.0'
    
    // Test dependencies
    testImplementation 'org.springframework.boot:spring-boot-starter-test'
    testImplementation 'org.springframework.security:spring-security-test'
}

tasks.named('test') {
    useJUnitPlatform()
}"""

    with open(os.path.join(demo_dir, "build.gradle"), 'w') as f:
        f.write(build_gradle)

    # Create a Java class with javax imports
    java_class = """package com.example.app;

import javax.persistence.Entity;
import javax.persistence.Id;
import javax.persistence.GeneratedValue;
import javax.persistence.GenerationType;
import javax.validation.constraints.NotNull;
import javax.validation.constraints.Size;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@Entity
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @NotNull
    @Size(min = 2, max = 50)
    private String name;
    
    @NotNull
    private String email;
    
    // Getters and setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }
    
    public String getName() { return name; }
    public void setName(String name) { this.name = name; }
    
    public String getEmail() { return email; }
    public void setEmail(String email) { this.email = email; }
}

@SpringBootApplication
public class DependencyDemoApplication {
    public static void main(String[] args) {
        SpringApplication.run(DependencyDemoApplication.class, args);
    }
}"""

    with open(os.path.join(demo_dir, "src/main/java/com/example/app/DependencyDemoApplication.java"), 'w') as f:
        f.write(java_class)

    # Create an internal module pom (to simulate internal dependencies)
    internal_pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
    <modelVersion>4.0.0</modelVersion>
    
    <groupId>com.example</groupId>
    <artifactId>internal-common</artifactId>
    <version>1.0.0</version>
    
    <properties>
        <maven.compiler.source>11</maven.compiler.source>
        <maven.compiler.target>11</maven.compiler.target>
    </properties>
    
    <dependencies>
        <!-- This internal module also has javax dependencies -->
        <dependency>
            <groupId>org.springframework</groupId>
            <artifactId>spring-context</artifactId>
            <version>5.3.23</version>
        </dependency>
        
        <dependency>
            <groupId>javax.persistence</groupId>
            <artifactId>javax.persistence-api</artifactId>
            <version>2.2</version>
        </dependency>
    </dependencies>
</project>"""

    internal_dir = os.path.join(demo_dir, "internal-common")
    os.makedirs(internal_dir, exist_ok=True)
    with open(os.path.join(internal_dir, "pom.xml"), 'w') as f:
        f.write(internal_pom)

    print(f"✅ Demo project created successfully!")
    print(f"📊 Dependency Scenarios Included:")
    print(f"   🔸 Spring Boot 2.7.5 (needs upgrade to 3.x)")
    print(f"   🔸 Java 11 (needs upgrade to 17+)")
    print(f"   🔸 Multiple javax.* dependencies (need Jakarta migration)")
    print(f"   🔸 Hibernate 5.x (needs upgrade to 6.x)")
    print(f"   🔸 Outdated third-party libraries")
    print(f"   🔸 Internal module with own dependencies")
    print(f"   🔸 Both Maven and Gradle build files")
    
    return demo_dir

def demonstrate_dependency_analysis_features():
    """Demonstrate the key features of dependency analysis."""
    
    print("\n" + "="*80)
    print("🔍 ENHANCED DEPENDENCY COMPATIBILITY ANALYSIS")
    print("="*80)
    
    print(f"\n🎯 New Analysis Capabilities:")
    print(f"   ✅ **Public Dependency Analysis**:")
    print(f"      • Maven/Gradle dependency parsing")
    print(f"      • Spring 6 compatibility checking")
    print(f"      • Jakarta EE migration requirements")
    print(f"      • Version conflict detection")
    print(f"   ")
    print(f"   ✅ **Internal Module Analysis**:")
    print(f"      • Internal dependency scanning")
    print(f"      • Cross-module compatibility")
    print(f"      • Version consistency checking")
    print(f"   ")
    print(f"   ✅ **Comprehensive Compatibility Matrix**:")
    print(f"      • Spring Framework 6.x compatibility")
    print(f"      • Spring Boot 3.x requirements")
    print(f"      • Java 17+ compatibility")
    print(f"      • Third-party library versions")
    print(f"   ")
    print(f"   ✅ **Migration Roadmap Generation**:")
    print(f"      • Step-by-step upgrade path")
    print(f"      • Dependency order resolution")
    print(f"      • Risk assessment and blockers")
    
    print(f"\n🛠️ Analysis Features:")
    print(f"   📊 **LLM-Powered Analysis**: Context-aware dependency understanding")
    print(f"   🔍 **Pattern Recognition**: Automatic detection of compatibility issues")
    print(f"   📋 **Detailed Reporting**: Comprehensive compatibility matrices")
    print(f"   🚨 **Blocker Identification**: Critical migration blockers flagged")
    print(f"   📈 **Version Recommendations**: Specific compatible versions suggested")
    print(f"   🔄 **Transitive Analysis**: Deep dependency tree examination")
    
    print(f"\n📋 What Gets Analyzed:")
    
    print(f"\n   🏗️ **Build Configuration Files**:")
    print(f"      • pom.xml (Maven dependencies)")
    print(f"      • build.gradle (Gradle dependencies)")
    print(f"      • gradle.properties (Gradle configuration)")
    print(f"      • Internal module definitions")
    
    print(f"\n   🔗 **Dependency Categories**:")
    print(f"      • Spring Framework components")
    print(f"      • Spring Boot starters")
    print(f"      • Jakarta EE specifications")
    print(f"      • Third-party libraries")
    print(f"      • Internal/custom modules")
    print(f"      • Test dependencies")
    
    print(f"\n   ⚠️ **Compatibility Issues**:")
    print(f"      • javax.* → jakarta.* namespace migrations")
    print(f"      • Version conflicts and mismatches")
    print(f"      • Deprecated or removed dependencies")
    print(f"      • Java version incompatibilities")
    print(f"      • Transitive dependency conflicts")
    
    print(f"\n📊 Expected Analysis Results:")
    print(f"   🔴 **Incompatible Dependencies**: Libraries that don't support Spring 6")
    print(f"   🟡 **Migration Required**: Dependencies needing version upgrades")
    print(f"   🟢 **Compatible**: Dependencies already Spring 6 ready")
    print(f"   🔄 **Jakarta Migration**: javax.* → jakarta.* transformations needed")
    print(f"   🚨 **Critical Blockers**: Issues preventing migration")

def main():
    """Main demonstration function."""
    
    print("🔍 Enhanced Dependency Compatibility Analysis Demo")
    print("=" * 60)
    
    # Create demo project
    demo_dir = create_demo_spring_project_with_dependencies()
    
    # Show analysis features
    demonstrate_dependency_analysis_features()
    
    print(f"\n" + "="*80)
    print("🚀 RUNNING ENHANCED DEPENDENCY ANALYSIS")
    print("="*80)
    
    print(f"\n🎯 Ready to run enhanced analysis:")
    print(f"   cd /Users/roshinpv/Documents/Projects/migraite")
    print(f"   python main.py --dir {demo_dir} --apply-changes -o ./dependency-analysis-results")
    
    print(f"\n📊 Expected Enhanced Output:")
    print(f"   📁 Dependency compatibility report")
    print(f"   🔍 Detailed compatibility matrix")
    print(f"   📋 Migration roadmap with dependency order")
    print(f"   🚨 Critical blocker identification")
    print(f"   📈 Version upgrade recommendations")
    print(f"   🔄 Jakarta migration requirements")
    
    print(f"\n🛡️ Safety Features:")
    print(f"   ✓ 📦 Complete backup before any changes")
    print(f"   ✓ 🔍 Dependency impact analysis")
    print(f"   ✓ ⚠️ Risk assessment and warnings")
    print(f"   ✓ 📋 Step-by-step migration guidance")
    
    print(f"\n💡 New Dependency Analysis Benefits:")
    print(f"   🎯 **Comprehensive Coverage**: All dependency types analyzed")
    print(f"   🧠 **Intelligent Detection**: LLM-powered compatibility checking")
    print(f"   📊 **Detailed Reporting**: Complete compatibility matrices")
    print(f"   🗺️ **Migration Roadmap**: Step-by-step upgrade path")
    print(f"   🚨 **Risk Assessment**: Potential issues identified early")
    print(f"   🔄 **Continuous Updates**: Analysis stays current with ecosystem")
    
    print(f"\n🧹 Cleanup:")
    print(f"   rm -rf {demo_dir}")
    
    return demo_dir

if __name__ == "__main__":
    main() 