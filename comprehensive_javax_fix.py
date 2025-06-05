#!/usr/bin/env python3
"""
Comprehensive javax → jakarta migration fix script
Fixes all missed javax imports that the main migration tool missed
"""

import os
import re
import glob

def fix_javax_imports_comprehensive(workspace_path):
    """Fix all javax imports in all Java files comprehensively."""
    
    # Comprehensive javax → jakarta mappings
    javax_to_jakarta_mappings = {
        "javax.persistence": "jakarta.persistence",
        "javax.validation": "jakarta.validation", 
        "javax.servlet": "jakarta.servlet",
        "javax.annotation": "jakarta.annotation",
        "javax.ejb": "jakarta.ejb",
        "javax.jms": "jakarta.jms",
        "javax.enterprise": "jakarta.enterprise",
        "javax.inject": "jakarta.inject",
        "javax.interceptor": "jakarta.interceptor",
        "javax.decorator": "jakarta.decorator",
        "javax.transaction": "jakarta.transaction",
        "javax.ws.rs": "jakarta.ws.rs",
        "javax.json": "jakarta.json",
        "javax.jsonb": "jakarta.jsonb",
        "javax.mail": "jakarta.mail",
        "javax.faces": "jakarta.faces",
        "javax.websocket": "jakarta.websocket",
        "javax.security.enterprise": "jakarta.security.enterprise",
        "javax.security.auth.message": "jakarta.security.auth.message",
        "javax.xml.bind": "jakarta.xml.bind",
        "javax.xml.soap": "jakarta.xml.soap",
        "javax.xml.ws": "jakarta.xml.ws",
        "javax.batch": "jakarta.batch",
        "javax.enterprise.concurrent": "jakarta.enterprise.concurrent",
        "javax.security.jacc": "jakarta.security.jacc",
    }
    
    print("🔍 Scanning for missed javax imports...")
    
    # Find all Java files
    java_files = glob.glob(os.path.join(workspace_path, "**", "*.java"), recursive=True)
    
    total_files_processed = 0
    total_imports_fixed = 0
    
    for java_file in java_files:
        try:
            with open(java_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            file_imports_fixed = 0
            
            # Find all javax imports
            javax_imports = re.findall(r'import\s+(javax\.[a-zA-Z][a-zA-Z0-9_.]*)', content)
            
            for javax_import in javax_imports:
                # Find the correct jakarta mapping
                jakarta_import = None
                for javax_pkg, jakarta_pkg in javax_to_jakarta_mappings.items():
                    if javax_import.startswith(javax_pkg):
                        jakarta_import = javax_import.replace(javax_pkg, jakarta_pkg, 1)
                        break
                
                if jakarta_import:
                    # Replace the import statement
                    import_pattern = rf'import\s+{re.escape(javax_import)}\s*;'
                    replacement = f'import {jakarta_import};'
                    
                    if re.search(import_pattern, content):
                        content = re.sub(import_pattern, replacement, content)
                        print(f"  ✅ {java_file}: {javax_import} → {jakarta_import}")
                        file_imports_fixed += 1
                        total_imports_fixed += 1
            
            # Save if changes were made
            if content != original_content:
                with open(java_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                total_files_processed += 1
                print(f"    💾 Updated {java_file} ({file_imports_fixed} imports fixed)")
        
        except Exception as e:
            print(f"❌ Error processing {java_file}: {e}")
    
    print(f"\n📊 Comprehensive javax fix results:")
    print(f"   • Files updated: {total_files_processed}")
    print(f"   • Total imports fixed: {total_imports_fixed}")
    
    return total_files_processed, total_imports_fixed

if __name__ == "__main__":
    # Target the migration workspace
    workspace = "migration_analysis/piggymetrics_migration_20250605_110921_migration_20250605_123245"
    
    if os.path.exists(workspace):
        print(f"🚀 Starting comprehensive javax → jakarta fix for {workspace}")
        files_updated, imports_fixed = fix_javax_imports_comprehensive(workspace)
        
        if imports_fixed > 0:
            print(f"\n🎉 SUCCESS! Fixed {imports_fixed} missed javax imports in {files_updated} files")
        else:
            print("\n✅ No javax imports found - migration appears complete")
    else:
        print(f"❌ Workspace not found: {workspace}")

# LLM finds what needs changing
analysis = llm.analyze_spring_migration_needs(project) 