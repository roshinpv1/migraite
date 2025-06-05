import os
import re
import yaml
import json
from pocketflow import Node, BatchNode
from utils.crawl_github_files import crawl_github_files
from utils.call_llm import call_llm, auto_configure_timeouts_for_repository_size, configure_maximum_timeouts
from utils.crawl_local_files import crawl_local_files
from utils.performance_monitor import (
    get_performance_monitor,
    ResourceOptimizer,
    ConcurrentAnalysisManager
)
from utils.verbose_logger import get_verbose_logger


# Helper to get content for specific file indices
def get_content_for_indices(files_data, indices):
    content_map = {}
    for i in indices:
        if 0 <= i < len(files_data):
            path, content = files_data[i]
            content_map[f"{i} # {path}"] = (
                content  # Use index + path as key for context
            )
    return content_map


class FetchRepo(Node):
    def prep(self, shared):
        vlogger = get_verbose_logger()
        
        if shared.get("verbose_mode"):
            vlogger.step("Preparing repository fetch operation")
        
        prep_data = {
            "repo_url": shared.get("repo_url"),
            "local_dir": shared.get("local_dir"),
            "token": shared.get("github_token") or os.environ.get("GITHUB_TOKEN"),
            "source_branch": shared.get("source_branch"),
            "include_patterns": shared.get("include_patterns", []),
            "exclude_patterns": shared.get("exclude_patterns", []),
            "max_file_size": shared.get("max_file_size", 1024 * 1024),  # 1MB default
            "use_relative_paths": True,
            "enable_optimization": shared.get("enable_optimization", True),
            "max_files_for_analysis": shared.get("max_files_for_analysis"),
            "verbose_mode": shared.get("verbose_mode", False)
        }
        
        return prep_data

    def exec(self, prep_res):
        monitor = get_performance_monitor()
        vlogger = get_verbose_logger()
        
        monitor.start_operation("fetch_repository")
        
        if prep_res["verbose_mode"]:
            vlogger.start_operation("fetch_repository", "Fetching and processing repository files")
        
        if prep_res["repo_url"]:
            print(f"Crawling repository: {prep_res['repo_url']}...")
            if prep_res["verbose_mode"]:
                vlogger.debug(f"Fetching from GitHub: {prep_res['repo_url']}")
                if prep_res["source_branch"]:
                    vlogger.debug(f"Target branch: {prep_res['source_branch']}")
                if prep_res["token"]:
                    vlogger.debug("Using authentication token")
                else:
                    vlogger.warning("No GitHub token provided - may hit rate limits")
            
            result = crawl_github_files(
                repo_url=prep_res["repo_url"],
                token=prep_res["token"],
                branch=prep_res["source_branch"],
                include_patterns=prep_res["include_patterns"],
                exclude_patterns=prep_res["exclude_patterns"],
                max_file_size=prep_res["max_file_size"],
                use_relative_paths=prep_res["use_relative_paths"],
            )
        else:
            print(f"Crawling directory: {prep_res['local_dir']}...")
            if prep_res["verbose_mode"]:
                vlogger.debug(f"Processing local directory: {prep_res['local_dir']}")

            result = crawl_local_files(
                directory=prep_res["local_dir"],
                include_patterns=prep_res["include_patterns"],
                exclude_patterns=prep_res["exclude_patterns"],
                max_file_size=prep_res["max_file_size"],
                use_relative_paths=prep_res["use_relative_paths"]
            )

        # Convert dict to list of tuples: [(path, content), ...]
        result_data = result.get("files", {})
        files_list = list(result_data.items())
        
        # Extract statistics if available
        crawl_stats = result.get("stats", {})
        
        if len(files_list) == 0:
            if prep_res["verbose_mode"]:
                vlogger.error("No files found matching criteria")
            raise ValueError("Failed to fetch files")
        
        if prep_res["verbose_mode"]:
            vlogger.debug(f"Initial file count: {len(files_list)}")
            
            # Show detailed statistics if available
            if crawl_stats:
                vlogger.debug("File processing statistics:")
                for key, value in crawl_stats.items():
                    vlogger.debug(f"  {key}: {value}")
            
            # Show sample of files found
            sample_files = files_list[:5]
            for path, content in sample_files:
                file_size = len(content) / 1024  # KB
                vlogger.file_processing(path, "Found", f"{file_size:.1f} KB")
            if len(files_list) > 5:
                vlogger.debug(f"... and {len(files_list) - 5} more files")
        
        # Show encoding statistics
        if crawl_stats.get("encoding_fallbacks_used", 0) > 0:
            print(f"⚠️  {crawl_stats['encoding_fallbacks_used']} files read with encoding fallbacks")
            if prep_res["verbose_mode"]:
                vlogger.warning(f"{crawl_stats['encoding_fallbacks_used']} files required encoding fallbacks")
        
        if crawl_stats.get("files_encoding_error", 0) > 0:
            print(f"⚠️  {crawl_stats['files_encoding_error']} files skipped due to encoding errors")
            if prep_res["verbose_mode"]:
                vlogger.warning(f"{crawl_stats['files_encoding_error']} files had encoding errors")
        
        # Performance optimization: filter files if enabled
        if prep_res["enable_optimization"] and prep_res["max_files_for_analysis"]:
            if prep_res["verbose_mode"]:
                vlogger.step("Applying file filtering optimization")
            
            original_count = len(files_list)
            files_list = ResourceOptimizer.filter_files_for_analysis(
                files_list, 
                max_files=prep_res["max_files_for_analysis"],
                prioritize_spring_files=True
            )
            
            if prep_res["verbose_mode"]:
                filtered_count = len(files_list)
                vlogger.optimization_applied(
                    f"File filtering: {original_count} → {filtered_count} files",
                    f"Reduced by {original_count - filtered_count} files"
                )
        
        print(f"Fetched {len(files_list)} files.")
        if prep_res["verbose_mode"]:
            vlogger.success(f"Successfully fetched {len(files_list)} files")
        
        # Generate analysis estimates
        if prep_res["enable_optimization"]:
            if prep_res["verbose_mode"]:
                vlogger.step("Generating analysis estimates")
            
            estimates = ResourceOptimizer.estimate_analysis_requirements(files_list)
            print(f"📊 Analysis Estimates:")
            print(f"   Files: {estimates['total_files']} ({estimates['total_size_mb']:.1f} MB)")
            print(f"   Estimated Duration: {estimates['estimated_duration_minutes']:.1f} minutes")
            print(f"   Estimated Memory: {estimates['estimated_memory_mb']:.1f} MB")
            
            if prep_res["verbose_mode"]:
                vlogger.performance_metric("Estimated files", estimates['total_files'])
                vlogger.performance_metric("Estimated size", estimates['total_size_mb'], "MB")
                vlogger.performance_metric("Estimated duration", estimates['estimated_duration_minutes'], "minutes")
                vlogger.performance_metric("Estimated memory", estimates['estimated_memory_mb'], "MB")
        
        monitor.end_operation("fetch_repository", files_processed=len(files_list))
        
        if prep_res["verbose_mode"]:
            vlogger.end_operation("fetch_repository", details=f"{len(files_list)} files processed")
        
        return files_list

    def post(self, shared, prep_res, exec_res):
        vlogger = get_verbose_logger()
        
        shared["files"] = exec_res  # List of (path, content) tuples

        # Automatically configure timeouts based on repository size
        file_count = len(exec_res)
        auto_configure_timeouts_for_repository_size(file_count)

        # Store optimization settings for downstream nodes
        shared["optimization_settings"] = ResourceOptimizer.get_recommended_settings(
            total_files=len(exec_res),
            total_size=sum(len(content) for _, content in exec_res)
        )
        
        if shared.get("verbose_mode"):
            vlogger.debug(f"Stored {len(exec_res)} files in shared state")
            optimization_settings = shared["optimization_settings"]
            vlogger.debug(f"Optimization settings: parallel={optimization_settings.get('enable_parallel_processing')}")
            vlogger.debug(f"Timeout auto-configuration applied for {file_count} files")


# ==========================================
# SPRING MIGRATION NODES
# ==========================================

class SpringMigrationAnalyzer(Node):
    """
    Analyzes a Spring codebase for migration from Spring 5 to Spring 6.
    Enhanced with concurrent analysis and performance optimization.
    """
    
    def prep(self, shared):
        vlogger = get_verbose_logger()
        
        if shared.get("verbose_mode"):
            vlogger.step("Preparing Spring migration analysis")
        
        files_data = shared["files"]
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        optimization_settings = shared.get("optimization_settings", {})
        
        # Apply optimization settings
        enable_parallel = optimization_settings.get("enable_parallel_processing", False)
        max_content_length = optimization_settings.get("max_content_length", 10000)
        
        # Filter for Spring-relevant files and create context
        def create_spring_context(files_data):
            context = ""
            file_summary = []
            
            for i, (path, content) in enumerate(files_data):
                # Apply content length optimization
                if len(content) > max_content_length:
                    content = content[:max_content_length] + "...[truncated for performance]"
                
                # Prioritize key Spring files
                if any(pattern in path.lower() for pattern in ['pom.xml', 'build.gradle', 'application.', 'config', 'controller', 'service', 'repository', 'security']):
                    entry = f"--- File {i}: {path} ---\n{content[:5000]}{'...[truncated]' if len(content) > 5000 else ''}\n\n"
                else:
                    # For other Java files, show just the structure
                    lines = content.split('\n')
                    imports = [line for line in lines if line.strip().startswith('import')]
                    class_annotations = [line for line in lines if '@' in line and any(anno in line for anno in ['@Component', '@Service', '@Controller', '@Repository', '@Configuration', '@Entity'])]
                    
                    entry = f"--- File {i}: {path} ---\n"
                    entry += "IMPORTS:\n" + "\n".join(imports[:10]) + "\n"
                    entry += "KEY ANNOTATIONS:\n" + "\n".join(class_annotations[:5]) + "\n"
                    if len(content) > 1000:
                        entry += f"[File size: {len(content)} chars - showing structure only]\n\n"
                    else:
                        entry += content + "\n\n"
                
                context += entry
                file_summary.append(f"- {i}: {path}")
                
                # Limit total context size for performance
                if len(context) > 50000:
                    context += "... [Additional files truncated for context length] ...\n"
                    break
            
            return context, file_summary
        
        context, file_summary = create_spring_context(files_data)
        file_listing = "\n".join(file_summary)
        
        return context, file_listing, project_name, use_cache, optimization_settings

    def exec(self, prep_res):
        monitor = get_performance_monitor()
        monitor.start_operation("spring_migration_analysis")
        
        context, file_listing, project_name, use_cache, optimization_settings = prep_res
        print(f"Analyzing Spring codebase for migration...")
        
        # Check if we should use fallback for very large contexts
        enable_fallback_for_large_repos = len(context) > 100000
        
        # Use maximum timeout for large repositories
        use_max_timeout = len(context) > 50000 or len(file_listing.split('\n')) > 200
        if use_max_timeout:
            print("⚡ Large repository detected - using maximum timeout settings...")
            configure_maximum_timeouts()
        
        if enable_fallback_for_large_repos:
            print("⚡ Large repository detected - using optimized analysis...")
            # Use a more focused prompt for very large repositories
            analysis = self._analyze_large_repository(context, file_listing, project_name, use_cache)
        else:
            # Use the full comprehensive prompt for smaller repositories
            analysis = self._analyze_standard_repository(context, file_listing, project_name, use_cache)
        
        monitor.end_operation("spring_migration_analysis", 
                            files_processed=len(file_listing.split('\n')),
                            llm_calls=1)
        return analysis
    
    def _analyze_large_repository(self, context, file_listing, project_name, use_cache):
        """Optimized analysis for large repositories."""
        prompt = f"""# Spring 6 Migration – Large Repository Analysis

You are analyzing a large Spring codebase for project `{project_name}` for Spring 5 to 6 migration.

## Repository Overview:
- Large codebase requiring optimized analysis
- Focus on high-impact migration issues
- Provide realistic effort estimates

## Sample Files (truncated for performance):
{context[:20000]}... [Additional content available]

## Available Files:
{file_listing[:5000]}... [Additional files not shown]

## CRITICAL: Provide a focused analysis in JSON format for large repositories:

```json
{{
  "executive_summary": {{
    "migration_impact": "High-level assessment of migration complexity",
    "key_blockers": ["Top 3 critical blockers"],
    "recommended_approach": "Phased migration strategy for large repository"
  }},
  "detailed_analysis": {{
    "framework_audit": {{}},
    "jakarta_migration": {{}},
    "security_migration": {{}},
    "estimated_scope": {{
      "total_files_analyzed": "approximate number",
      "high_priority_files": "files requiring immediate attention",
      "complexity_assessment": "Low|Medium|High|Very High"
    }}
  }},
  "effort_estimation": {{
    "total_effort": "X person-weeks (adjusted for large repository)",
    "team_size_recommendation": "3-8 developers",
    "timeline": "X months",
    "priority_levels": {{
      "critical": ["items blocking migration"],
      "high": ["items requiring early attention"],
      "medium": ["items for later phases"]
    }}
  }},
  "migration_roadmap": [
    {{
      "step": 1,
      "title": "Foundation Phase",
      "description": "Core infrastructure updates",
      "estimated_effort": "X person-weeks"
    }}
  ]
}}
```

Focus on providing actionable insights for large-scale migration planning."""

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            return self._parse_analysis_response(response, file_listing)
        except Exception as e:
            print(f"Large repository analysis failed: {e}")
            return self._get_fallback_analysis((context, file_listing, project_name, use_cache), file_listing)
    
    def _analyze_standard_repository(self, context, file_listing, project_name, use_cache):
        """Standard comprehensive analysis for normal-sized repositories."""
        # Store prep_res for fallback use
        prep_res = (context, file_listing, project_name, use_cache)
        
        # Use the existing comprehensive prompt
        prompt = """# System Prompt: Spring 6 Migration – Full Codebase Analysis

You are an expert in Java, Spring Framework, Jakarta EE, and enterprise application modernization. Analyze the Java codebase for project `{project_name}` to determine what changes are needed for Spring Framework 6 migration.

## Codebase Context:
{context}

## Available Files:
{file_listing}

## Analysis Requirements:

Analyze the ACTUAL codebase and provide REALISTIC recommendations based on what you observe. Do not make assumptions about versions or provide generic recommendations.

## 1. Framework and Dependency Audit
- Identify the ACTUAL current Spring and Spring Boot versions from the build files
- Detect deprecated or removed Spring modules and APIs that are actually present in the code
- Audit third-party libraries based on what is actually declared in build files
- Flag any actual usage of `javax.*` APIs found in the codebase

## 2. Jakarta Namespace Impact
- Search and list all ACTUAL usages of `javax.*` packages found in the code
- Map these to their `jakarta.*` counterparts based on what's actually used
- Assess classes, annotations, XML, and configuration files that actually exist
- Identify incompatible external libraries based on actual dependencies

## 3. Configuration and Component Analysis
- Analyze the actual Java-based and XML-based Spring configurations present
- Evaluate actual usage of `@Configuration`, `@ComponentScan`, `@Profile`, `@Conditional`
- Identify deprecated constructs that are actually present in the codebase

## 4. **JAVAX TO JAKARTA MIGRATION - TOP PRIORITY**

⚠️ **CRITICAL MIGRATION REQUIREMENT**: ALL javax.* imports MUST be updated to jakarta.* equivalents

### Primary javax.* packages requiring immediate update:
- **javax.persistence.*** → **jakarta.persistence.*** (JPA/Hibernate)
- **javax.validation.*** → **jakarta.validation.*** (Bean Validation)
- **javax.servlet.*** → **jakarta.servlet.*** (Servlet API)
- **javax.jms.*** → **jakarta.jms.*** (Java Message Service)
- **javax.ejb.*** → **jakarta.ejb.*** (Enterprise JavaBeans)
- **javax.inject.*** → **jakarta.inject.*** (Dependency Injection)
- **javax.ws.rs.*** → **jakarta.ws.rs.*** (JAX-RS)
- **javax.json.*** → **jakarta.json.*** (JSON-B)
- **javax.security.*** → **jakarta.security.*** (Security)

### MANDATORY javax scanning requirements:
1. **Scan ALL .java files** for javax.* imports
2. **Scan ALL XML configuration** for javax references
3. **Scan ALL annotation usage** with javax packages
4. **Check ALL test files** for javax.* imports
5. **Verify ALL third-party dependencies** for javax compatibility

## 5. Jakarta Namespace Impact Analysis

REQUIRED: Provide comprehensive javax→jakarta mapping for ALL actual usages found:

```json
"jakarta_migration": {{
  "javax_usages": [
    "List ALL actual javax.* imports found in codebase",
    "Include file paths and line numbers where possible"
  ],
  "mapping_required": {{
    "javax.persistence.Entity": "jakarta.persistence.Entity",
    "javax.validation.constraints.NotNull": "jakarta.validation.constraints.NotNull",
    "javax.servlet.http.HttpServletRequest": "jakarta.servlet.http.HttpServletRequest"
  }},
  "incompatible_libraries": [
    "List dependencies that still use javax and need updates"
  ]
}}
```

**SCAN PRIORITY**: Focus heavily on javax.* usage detection - this is the most common breaking change

## Analysis Requirements:

Analyze the ACTUAL codebase and provide REALISTIC recommendations based on what you observe. Do not make assumptions about versions or provide generic recommendations.

## 1. Framework and Dependency Audit
- Identify the ACTUAL current Spring and Spring Boot versions from the build files
- Detect deprecated or removed Spring modules and APIs that are actually present in the code
- Audit third-party libraries based on what is actually declared in build files
- **⚠️ FLAG ALL ACTUAL javax.* API USAGE found in the codebase** - THIS IS CRITICAL

## 2. **COMPREHENSIVE JAVAX TO JAKARTA ANALYSIS** ⭐
- **Search exhaustively** for ALL javax.* packages in the entire codebase
- Map EVERY javax.* usage to its jakarta.* equivalent based on actual findings
- Assess classes, annotations, XML configs, and property files for javax references
- Identify incompatible external libraries that still use javax
- **This is typically 60-80% of migration effort - be thorough**

## 6. Spring Security Migration
- Detect actual usage of `WebSecurityConfigurerAdapter` in the codebase
- Identify how authentication, authorization, CORS, CSRF are actually implemented
- Recommend changes based on the actual security configuration found

## 7. Spring Data and JPA
- Audit actual use of `javax.persistence.*` and related annotations in the code
- Review actual repository interfaces and custom queries present
- Check actual Hibernate usage and version from build files

## 8. Web Layer (Spring MVC / WebFlux)
- Identify actual controllers, `@RequestMapping` methods, interceptors found in code
- Detect actual servlet-based components in the codebase
- Highlight APIs that are actually used and need migration

## 9. Testing Analysis
- Review actual tests using Spring Test, JUnit that exist in the codebase
- Detect actual `javax.*` usage in test code
- Identify actual testing patterns that need updates

## 10. Build Tooling
- Audit actual Maven or Gradle setup from the build files provided
- Validate actual plugin versions and compiler settings
- Check actual build configuration compatibility

## 11. Output Requirements

Your output must be in valid JSON format. Base all recommendations on the ACTUAL codebase analysis:

```json
{{
  "executive_summary": {{
    "migration_impact": "Assessment based on actual code analysis",
    "key_blockers": ["Actual blockers found in the codebase"],
    "recommended_approach": "Approach based on what was actually found"
  }},
  "detailed_analysis": {{
    "framework_audit": {{
      "current_versions": {{"actual_versions_found": "from_build_files"}},
      "deprecated_apis": ["actual_deprecated_usage_found"],
      "third_party_compatibility": ["actual_dependencies_analyzed"]
    }},
    "jakarta_migration": {{
      "javax_usages": ["actual_javax_imports_found"],
      "mapping_required": {{"actual_mappings": "needed"}},
      "incompatible_libraries": ["actual_incompatible_deps_found"]
    }},
    "configuration_analysis": {{
      "java_config_issues": ["actual_config_issues_found"],
      "xml_config_issues": ["actual_xml_issues_found"],
      "deprecated_patterns": ["actual_deprecated_patterns_found"]
    }},
    "security_migration": {{
      "websecurity_adapter_usage": ["actual_usage_found"],
      "auth_config_changes": ["actual_changes_needed"],
      "deprecated_security_features": ["actual_deprecated_features_found"]
    }},
    "data_layer": {{
      "jpa_issues": ["actual_jpa_issues_found"],
      "repository_issues": ["actual_repository_issues_found"],
      "hibernate_compatibility": ["actual_hibernate_issues_found"]
    }},
    "web_layer": {{
      "controller_issues": ["actual_controller_issues_found"],
      "servlet_issues": ["actual_servlet_issues_found"],
      "deprecated_web_features": ["actual_deprecated_web_found"]
    }},
    "testing": {{
      "test_framework_issues": ["actual_test_issues_found"],
      "deprecated_test_patterns": ["actual_deprecated_test_patterns_found"]
    }},
    "build_tooling": {{
      "build_file_issues": ["actual_build_issues_found"],
      "plugin_compatibility": ["actual_plugin_issues_found"],
      "cicd_considerations": ["actual_cicd_issues_found"]
    }}
  }},
  "module_breakdown": [
    {{
      "module_name": "actual_module_name",
      "complexity": "Based on actual analysis",
      "refactor_type": "Based on actual needs",
      "issues": ["Actual issues found"],
      "effort_estimate": "Based on actual complexity found"
    }}
  ],
  "effort_estimation": {{
    "total_effort": "Based on actual analysis findings",
    "by_category": {{
      "jakarta_migration": "Based on actual javax usage found",
      "security_updates": "Based on actual security config found", 
      "dependency_updates": "Based on actual dependencies found",
      "testing": "Based on actual test code found",
      "build_config": "Based on actual build files found"
    }},
    "priority_levels": {{
      "high": ["High priority items based on actual findings"],
      "medium": ["Medium priority items based on actual findings"],
      "low": ["Low priority items based on actual findings"]
    }}
  }},
  "code_samples": {{
    "jakarta_namespace": {{
      "before": "Actual javax code found",
      "after": "Corresponding jakarta replacement"
    }},
    "security_config": {{
      "before": "Actual security config found", 
      "after": "Recommended updated config"
    }},
    "spring_config": {{
      "before": "Actual config found",
      "after": "Recommended updated config"
    }}
  }},
  "migration_roadmap": [
    {{
      "step": 1,
      "title": "Based on actual priority findings",
      "description": "Based on actual codebase needs",
      "estimated_effort": "Based on actual complexity analysis",
      "dependencies": []
    }}
  ]
}}
```

IMPORTANT: 
- Base ALL recommendations on what you ACTUALLY find in the codebase
- Do NOT provide generic migration advice
- Do NOT assume version numbers - only use versions actually found in build files
- Do NOT recommend specific versions unless you can determine current versions
- If current versions cannot be determined, state "version_not_determinable"
- Focus on actual code patterns, imports, and configurations found
- Provide specific line-by-line analysis where possible

Analyze the codebase thoroughly and provide the complete JSON response based on actual findings.""".format(
            project_name=project_name,
            context=context,
            file_listing=file_listing
        )

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            return self._parse_analysis_response(response, file_listing)
        except Exception as e:
            print(f"Standard repository analysis failed: {e}")
            return self._get_fallback_analysis(prep_res, file_listing)
    
    def _parse_analysis_response(self, response, file_listing):
        """Parse the LLM analysis response with enhanced error handling."""
        try:
            # Clean the response
            response = response.strip()
            
            # Try to find JSON block in response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif response.startswith("{") and response.endswith("}"):
                json_str = response
            else:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON content found in response")
            
            # Clean up common JSON issues
            json_str = self._clean_json_string(json_str)
            
            # Try to parse JSON
            analysis = json.loads(json_str)
            
            # Basic validation
            required_keys = ["executive_summary", "detailed_analysis", "effort_estimation"]
            for key in required_keys:
                if key not in analysis:
                    print(f"Warning: Missing required key: {key}")
                    analysis[key] = self._get_default_value(key)
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response content (first 500 chars): {response[:500]}")
            return self._get_fallback_analysis(None, file_listing)
        except Exception as e:
            print(f"Error processing LLM response: {e}")
            return self._get_fallback_analysis(None, file_listing)
    
    def _clean_json_string(self, json_str):
        """Clean common JSON formatting issues."""
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        
        # Fix common issues with unescaped quotes in strings
        import re
        
        # Fix unescaped quotes within string values (simple heuristic)
        # This is a basic fix - for production, you'd want more sophisticated handling
        lines = json_str.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # If line contains a string value with unescaped quotes, try to fix
            if ':' in line and '"' in line:
                # Simple fix for common case: "key": "value with "quotes" inside"
                if line.count('"') > 2:  # More than just key-value quotes
                    # Find the value part after the colon
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key_part = parts[0]
                        value_part = parts[1].strip()
                        # If value part has quotes, escape internal quotes
                        if value_part.startswith('"') and value_part.endswith('"'):
                            # Extract the content and escape internal quotes
                            content = value_part[1:-1]
                            content = content.replace('"', '\\"')
                            value_part = f'"{content}"'
                            line = f"{key_part}: {value_part}"
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _attempt_json_fix(self, response):
        """Attempt to fix malformed JSON."""
        try:
            # Extract potential JSON content
            if "```json" in response:
                json_part = response.split("```json")[1].split("```")[0].strip()
            else:
                # Try to find JSON-like content
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_part = json_match.group(0)
                else:
                    return None
            
            # Try to fix truncated JSON by closing brackets/braces
            open_braces = json_part.count('{')
            close_braces = json_part.count('}')
            open_brackets = json_part.count('[')
            close_brackets = json_part.count(']')
            
            # Add missing closing braces/brackets
            missing_braces = open_braces - close_braces
            missing_brackets = open_brackets - close_brackets
            
            if missing_braces > 0 or missing_brackets > 0:
                # Remove any trailing incomplete content
                json_part = json_part.rstrip(',\n\r\t ')
                
                # Add missing closing brackets/braces
                json_part += ']' * missing_brackets
                json_part += '}' * missing_braces
                
                # Try to parse the fixed JSON
                test_parse = json.loads(json_part)
                return json_part
            
            return json_part
            
        except:
            return None
    
    def _get_default_value(self, key):
        """Get default value for missing JSON keys."""
        defaults = {
            "executive_summary": {
                "migration_impact": "Manual analysis required due to parsing issues",
                "key_blockers": ["LLM response parsing failed"],
                "recommended_approach": "Manual code review recommended"
            },
            "detailed_analysis": {
                "framework_audit": {"current_versions": {}, "deprecated_apis": [], "third_party_compatibility": []},
                "jakarta_migration": {"javax_usages": [], "mapping_required": {}, "incompatible_libraries": []},
                "configuration_analysis": {"java_config_issues": [], "xml_config_issues": [], "deprecated_patterns": []},
                "security_migration": {"websecurity_adapter_usage": [], "auth_config_changes": [], "deprecated_security_features": []},
                "data_layer": {"jpa_issues": [], "repository_issues": [], "hibernate_compatibility": []},
                "web_layer": {"controller_issues": [], "servlet_issues": [], "deprecated_web_features": []},
                "testing": {"test_framework_issues": [], "deprecated_test_patterns": []},
                "build_tooling": {"build_file_issues": [], "plugin_compatibility": [], "cicd_considerations": []}
            },
            "module_breakdown": [],
            "effort_estimation": {
                "total_effort": "Manual estimation required",
                "by_category": {},
                "priority_levels": {"high": [], "medium": [], "low": []}
            },
            "migration_roadmap": []
        }
        return defaults.get(key, {})
    
    def _get_fallback_analysis(self, prep_res, file_listing, verbose_mode=False):
        """Generate a fallback analysis when LLM parsing fails."""
        vlogger = get_verbose_logger()
        
        if verbose_mode:
            vlogger.step("Generating fallback analysis due to LLM parsing failure")
        
        # Safely extract data from prep_res - handle the case where it might be None
        if prep_res is None:
            context = ""
            project_name = "unknown_project"
            use_cache = True
            file_count = 0
        else:
            try:
                if isinstance(prep_res, tuple) and len(prep_res) >= 4:
                    context, file_listing_from_prep, project_name, use_cache = prep_res[:4]
                else:
                    # Handle unexpected prep_res format
                    context = str(prep_res) if prep_res else ""
                    project_name = "unknown_project"
                    use_cache = True
                
                # Count files from file listing
                file_count = len(file_listing.split('\n')) if file_listing else 0
                
            except Exception as e:
                if verbose_mode:
                    vlogger.error("Error extracting data from prep_res", e)
                # Use safe defaults
                context = ""
                project_name = "unknown_project"
                use_cache = True
                file_count = 0
        
        if verbose_mode:
            vlogger.debug(f"Fallback analysis for {file_count} files in project: {project_name}")
        
        # Determine project size and base estimates
        if file_count < 10:
            project_size = "Small"
            base_effort = "8-12 person-days"
            team_size = "1-2 developers"
            timeline = "2-3 weeks"
        elif file_count < 50:
            project_size = "Medium" 
            base_effort = "15-25 person-days"
            team_size = "2-3 developers"
            timeline = "4-8 weeks"
        elif file_count < 200:
            project_size = "Large"
            base_effort = "30-45 person-days"
            team_size = "3-4 developers" 
            timeline = "2-3 months"
        else:
            # Very large repository
            project_size = "Very Large"
            base_effort = "60-120 person-days"
            team_size = "4-8 developers"
            timeline = "3-6 months"
        
        if verbose_mode:
            vlogger.debug(f"Classified as {project_size} project: {base_effort}, {team_size}, {timeline}")
        
        # Enhanced fallback analysis for large repositories
        if file_count > 500:
            # Special handling for very large repositories
            fallback_reason = f"LLM timeout on large repository ({file_count} files) - automated analysis not feasible"
            recommendations = [
                f"Break down analysis into smaller modules (recommend max 100 files per analysis)",
                "Use incremental migration approach by module/package",
                "Consider parallel team analysis of different modules",
                f"Estimated {file_count} files requires enterprise migration planning",
                "Manual review of critical paths recommended before automated changes"
            ]
        else:
            fallback_reason = f"LLM response parsing failed for {file_count} files - manual review recommended"
            recommendations = [
                "Manual code review recommended due to analysis parsing issues",
                "Check Spring Boot compatibility matrix",
                "Review dependency versions manually",
                "Consider using smaller file batches for analysis"
            ]
        
        # Create a comprehensive fallback response
        fallback_analysis = {
            "executive_summary": {
                "migration_impact": f"Analysis of {file_count} files in {project_name} indicates a {project_size.lower()} Spring migration project. {fallback_reason}",
                "key_blockers": [
                    fallback_reason,
                    "Potential javax.* to jakarta.* namespace changes",
                    "Spring Security configuration updates may be needed",
                    f"Large codebase ({file_count} files) requires structured approach"
                ],
                "recommended_approach": f"Phased migration approach recommended for {project_size.lower()} projects. Start with dependency updates, then tackle deprecated APIs systematically. Manual planning required due to analysis issues."
            },
            "detailed_analysis": {
                "framework_audit": {
                    "current_versions": {"analysis_status": "failed", "reason": "LLM timeout"},
                    "deprecated_apis": [],
                    "third_party_compatibility": []
                },
                "jakarta_migration": {
                    "javax_usages": [],
                    "mapping_required": {"analysis_status": "manual_review_required"},
                    "incompatible_libraries": []
                },
                "configuration_analysis": {
                    "java_config_issues": [],
                    "xml_config_issues": [],
                    "deprecated_patterns": []
                },
                "security_migration": {
                    "websecurity_adapter_usage": [],
                    "auth_config_changes": [],
                    "deprecated_security_features": []
                },
                "data_layer": {
                    "jpa_issues": [],
                    "repository_issues": [],
                    "hibernate_compatibility": []
                },
                "web_layer": {
                    "controller_issues": [],
                    "servlet_issues": [],
                    "deprecated_web_features": []
                },
                "testing": {
                    "test_framework_issues": [],
                    "deprecated_test_patterns": []
                },
                "build_tooling": {
                    "build_file_issues": [],
                    "plugin_compatibility": [],
                    "cicd_considerations": []
                }
            },
            "module_breakdown": [
                {
                    "module_name": "main_application",
                    "complexity": project_size,
                    "refactor_type": "Manual-review-required",
                    "issues": [fallback_reason],
                    "effort_estimate": base_effort
                }
            ],
            "effort_estimation": {
                "total_effort": base_effort,
                "by_category": {
                    "manual_analysis": f"{int(base_effort.split('-')[0]) // 2} person-days",
                    "jakarta_migration": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "security_updates": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "dependency_updates": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "testing": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "build_config": f"{int(base_effort.split('-')[0]) // 6} person-days"
                },
                "priority_levels": {
                    "high": recommendations[:2],
                    "medium": recommendations[2:4] if len(recommendations) > 3 else [],
                    "low": recommendations[4:] if len(recommendations) > 4 else ["Documentation updates", "Code style improvements"]
                },
                "large_repository_considerations": {
                    "file_count": file_count,
                    "recommended_batch_size": min(100, max(20, file_count // 10)),
                    "parallel_analysis_recommended": file_count > 200,
                    "enterprise_planning_required": file_count > 500
                }
            },
            "code_samples": {
                "jakarta_namespace": {"before": "import javax.persistence.Entity;", "after": "import jakarta.persistence.Entity;"}, 
                "security_config": {"before": "extends WebSecurityConfigurerAdapter", "after": "SecurityFilterChain filterChain(HttpSecurity http)"}, 
                "spring_config": {"before": "Spring Boot 2.x config", "after": "Spring Boot 3.x config"}
            },
            "migration_roadmap": [
                {
                    "step": 1,
                    "title": "Manual Planning & Analysis",
                    "description": f"Perform manual analysis of {project_size.lower()} codebase due to automated analysis limitations",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "dependencies": []
                },
                {
                    "step": 2,
                    "title": "Module-by-Module Analysis",
                    "description": "Break down large codebase into manageable modules for incremental analysis",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "dependencies": ["step-1"]
                },
                {
                    "step": 3,
                    "title": "Dependency Updates",
                    "description": "Update Spring Boot to 3.x and related dependencies module by module",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "dependencies": ["step-2"]
                },
                {
                    "step": 4,
                    "title": "Jakarta Migration",
                    "description": "Replace javax.* imports with jakarta.* equivalents incrementally",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "dependencies": ["step-3"]
                },
                {
                    "step": 5,
                    "title": "Testing and Validation",
                    "description": "Comprehensive testing of migrated application modules",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "dependencies": ["step-4"]
                }
            ],
            "large_repository_recommendations": recommendations if file_count > 200 else [],
            "analysis_metadata": {
                "fallback_reason": fallback_reason,
                "project_size_classification": project_size,
                "file_count": file_count,
                "requires_manual_review": True,
                "automated_analysis_feasible": file_count < 200
            }
        }
        
        if verbose_mode:
            vlogger.success(f"Generated comprehensive fallback analysis for {project_size} project ({file_count} files)")
        
        return fallback_analysis

    def post(self, shared, prep_res, exec_res):
        shared["migration_analysis"] = exec_res
        print("✅ Migration analysis completed")
        return "default"


class MigrationPlanGenerator(Node):
    """
    Generates a detailed migration plan based on the analysis results.
    """
    
    def prep(self, shared):
        analysis = shared["migration_analysis"]
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        
        return analysis, project_name, use_cache
    
    def exec(self, prep_res):
        import json
        analysis, project_name, use_cache = prep_res
        print(f"Generating detailed migration plan...")
        
        prompt = f"""
You are analyzing a Spring Boot project for migration from version 2.x to 3.x.

## 🚨 **CRITICAL JAVAX TO JAKARTA MIGRATION PRIORITY** 🚨

**The #1 migration priority is javax.* → jakarta.* namespace changes. This affects 60-80% of Spring 6 migration effort.**

Based on the following analysis results, create a comprehensive, actionable migration plan:

**Project:** {project_name}
**Analysis Results:**
{json.dumps(analysis, indent=2)}

## **JAVAX TO JAKARTA MIGRATION REQUIREMENTS**

### **Top Priority javax→jakarta mappings that MUST be in your plan:**
- **javax.persistence.*** → **jakarta.persistence.*** (JPA/Hibernate)
- **javax.validation.*** → **jakarta.validation.*** (Bean Validation)
- **javax.servlet.*** → **jakarta.servlet.*** (Servlet API)
- **javax.inject.*** → **jakarta.inject.*** (Dependency Injection)
- **javax.jms.*** → **jakarta.jms.*** (Java Message Service)
- **javax.ejb.*** → **jakarta.ejb.*** (Enterprise JavaBeans)
- **javax.ws.rs.*** → **jakarta.ws.rs.*** (JAX-RS)
- **javax.json.*** → **jakarta.json.*** (JSON-B)

### **MANDATORY javax→jakarta migration phases:**
1. **Phase 1: Comprehensive javax.* Scan** - Identify ALL javax imports in codebase
2. **Phase 2: javax→jakarta Import Replacement** - Systematic replacement of imports
3. **Phase 3: javax→jakarta Testing** - Verify all replacements work correctly

**IMPORTANT:** You MUST include ALL required fields in your JSON response AND prioritize javax→jakarta migration in your phase breakdown.

Generate a detailed migration plan based on the actual findings from the analysis.

**Migration Complexity Guidelines:**
- Simple projects (< 50 files): 1-2 phases, 2-4 weeks
- Medium projects (50-200 files): 3-4 phases, 1-2 months  
- Large projects (200+ files): 4-6 phases, 2-4 months

**Timeline Guidelines:**
- Include time for testing, validation, and deployment
- Account for parallel development work
- Consider team availability and other project commitments
- **javax→jakarta changes typically require 30-50% of migration time**

**REQUIRED JSON OUTPUT FORMAT - Include ALL sections with javax→jakarta focus:**
```json
{{
  "migration_strategy": {{
    "approach": "Big Bang|Phased|Hybrid",
    "rationale": "Explanation focusing on javax→jakarta migration complexity and approach",
    "estimated_timeline": "X weeks|X months (be specific and realistic)",
    "team_size_recommendation": "X developers (1-5 max)",
    "javax_migration_priority": "HIGH - 60-80% of migration effort"
  }},
  "phase_breakdown": [
    {{
      "phase": 1,
      "name": "javax→jakarta Comprehensive Scan and Analysis",
      "description": "Identify all javax.* imports and dependencies requiring migration",
      "duration": "X days/weeks",
      "deliverables": ["Complete javax.* inventory", "jakarta.* mapping plan"],
      "tasks": [
        {{
          "task_id": "javax-scan",
          "title": "Comprehensive javax.* Import Scan", 
          "description": "Scan ALL Java files for javax.* imports and create mapping to jakarta.*",
          "complexity": "Medium",
          "estimated_hours": "8-16 hours per 100 files",
          "dependencies": [],
          "automation_potential": "High",
          "tools_required": ["Migration scripts", "IDE find/replace"]
        }},
        {{
          "task_id": "jakarta-dependency-analysis",
          "title": "Jakarta EE Dependency Analysis",
          "description": "Analyze third-party dependencies for javax vs jakarta compatibility",
          "complexity": "High",
          "estimated_hours": "16-24 hours",
          "dependencies": ["javax-scan"],
          "automation_potential": "Medium",
          "tools_required": ["Dependency analysis tools"]
        }}
      ],
      "risks": ["Missing javax imports", "Incompatible dependencies"],
      "success_criteria": ["100% javax imports identified", "jakarta mapping complete"]
    }},
    {{
      "phase": 2,
      "name": "javax→jakarta Import Migration",
      "description": "Systematic replacement of javax.* imports with jakarta.* equivalents",
      "duration": "X days/weeks", 
      "deliverables": ["All javax imports replaced", "Compilation success"],
      "tasks": [
        {{
          "task_id": "javax-to-jakarta-replacement",
          "title": "Automated javax→jakarta Import Replacement",
          "description": "Replace all javax.* imports with jakarta.* using automated tools",
          "complexity": "Medium",
          "estimated_hours": "4-8 hours per 100 files",
          "dependencies": ["javax-scan"],
          "automation_potential": "High",
          "tools_required": ["Migration scripts", "Find/replace tools"]
        }}
      ],
      "risks": ["Breaking changes", "Runtime errors"],
      "success_criteria": ["All imports replaced", "Clean compilation"]
    }}
  ],
  "automation_recommendations": [
    {{
      "tool": "javax→jakarta Migration Scripts",
      "purpose": "Automate javax.* to jakarta.* import replacements",
      "setup_instructions": "Use IDE find/replace or custom scripts for bulk replacement",
      "coverage": "95% of javax→jakarta import changes can be automated"
    }},
    {{
      "tool": "Spring Boot 3.x Migration Plugin",
      "purpose": "Handle dependency updates and configuration changes", 
      "setup_instructions": "Configure Maven/Gradle plugins for automated dependency updates",
      "coverage": "80% of dependency and configuration updates"
    }}
  ],
  "manual_changes": [
    {{
      "category": "javax→jakarta Migration",
      "changes": ["Complex annotation usages", "Third-party library integrations"],
      "rationale": "Some javax→jakarta changes require manual review for context-specific updates"
    }}
  ],
  "testing_strategy": {{
    "unit_tests": "Update test imports from javax.* to jakarta.*, verify all test annotations work",
    "integration_tests": "Test jakarta.* integrations thoroughly, especially JPA and validation", 
    "regression_testing": "Comprehensive testing to ensure javax→jakarta changes don't break functionality"
  }},
  "rollback_plan": {{
    "triggers": ["javax→jakarta breaking changes", "Runtime failures", "Performance issues"],
    "steps": ["Revert javax→jakarta changes", "Restore original dependencies", "Validate rollback"],
    "data_considerations": "Ensure javax→jakarta changes don't affect data persistence"
  }},
  "success_metrics": [
    {{
      "metric": "javax→jakarta Import Migration",
      "target": "100% of javax.* imports replaced with jakarta.*",
      "measurement_method": "Code scan for remaining javax.* imports"
    }},
    {{
      "metric": "Application Functionality",
      "target": "All features work with jakarta.* dependencies",
      "measurement_method": "Comprehensive test suite execution"
    }}
  ]
}}
```

**CRITICAL:** Return ONLY the JSON object. Do not include any explanatory text before or after the JSON. Ensure javax→jakarta migration is prominently featured in phases and tasks."""

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            return self._parse_plan_response(response, analysis, project_name)
            
        except Exception as e:
            print(f"Migration plan generation failed: {e}")
            return self._get_fallback_plan(analysis, project_name)
    
    def _parse_plan_response(self, response, analysis, project_name):
        """Parse the LLM plan response with enhanced error handling."""
        try:
            # Clean the response
            response = response.strip()
            
            # Try to find JSON block in response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif response.startswith("{") and response.endswith("}"):
                json_str = response
            else:
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    raise ValueError("No JSON content found in response")
            
            # Clean up common JSON issues (reuse cleaning logic from SpringMigrationAnalyzer)
            json_str = self._clean_plan_json_string(json_str)
            
            # Try to parse JSON
            plan = json.loads(json_str)
            
            # Enhanced validation with better error handling
            required_keys = ["migration_strategy", "phase_breakdown", "automation_recommendations", "testing_strategy"]
            missing_keys = []
            
            for key in required_keys:
                if key not in plan:
                    missing_keys.append(key)
                    
            if missing_keys:
                print(f"Warning: Missing required keys in migration plan: {', '.join(missing_keys)}")
                print("         Using fallback values for missing sections...")
                
                # Add missing keys with appropriate defaults
                for key in missing_keys:
                    plan[key] = self._get_default_plan_value(key)
                    
                # Log the issue for debugging
                if "files" in analysis:
                    file_count = len(analysis["files"])
                    print(f"         Plan generated for {file_count} files, but LLM response was incomplete")
            
            # Validate structure of included keys
            self._validate_plan_structure(plan)
            
            return plan
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error in migration plan: {e}")
            print(f"Response content (first 500 chars): {response[:500]}")
            print("Falling back to structured default plan...")
            return self._get_fallback_plan(analysis, project_name)
        except Exception as e:
            print(f"Error processing migration plan LLM response: {e}")
            print("Falling back to structured default plan...")
            return self._get_fallback_plan(analysis, project_name)
    
    def _validate_plan_structure(self, plan):
        """Validate the structure of migration plan components."""
        try:
            # Validate migration_strategy structure
            if "migration_strategy" in plan:
                strategy = plan["migration_strategy"]
                if not isinstance(strategy, dict):
                    print("Warning: migration_strategy should be an object, fixing structure...")
                    plan["migration_strategy"] = self._get_default_plan_value("migration_strategy")
                else:
                    # Ensure required strategy fields exist
                    required_strategy_fields = ["approach", "rationale", "estimated_timeline", "team_size_recommendation"]
                    for field in required_strategy_fields:
                        if field not in strategy:
                            strategy[field] = f"Not specified - requires manual planning"
            
            # Validate phase_breakdown structure
            if "phase_breakdown" in plan:
                phases = plan["phase_breakdown"]
                if not isinstance(phases, list):
                    print("Warning: phase_breakdown should be an array, fixing structure...")
                    plan["phase_breakdown"] = self._get_default_plan_value("phase_breakdown")
                elif len(phases) == 0:
                    print("Warning: phase_breakdown is empty, adding default phase...")
                    plan["phase_breakdown"] = self._get_default_plan_value("phase_breakdown")
            
            # Validate automation_recommendations structure
            if "automation_recommendations" in plan:
                recommendations = plan["automation_recommendations"]
                if not isinstance(recommendations, list):
                    print("Warning: automation_recommendations should be an array, fixing structure...")
                    plan["automation_recommendations"] = self._get_default_plan_value("automation_recommendations")
            
            # Validate testing_strategy structure
            if "testing_strategy" in plan:
                testing = plan["testing_strategy"]
                if not isinstance(testing, dict):
                    print("Warning: testing_strategy should be an object, fixing structure...")
                    plan["testing_strategy"] = self._get_default_plan_value("testing_strategy")
                    
        except Exception as e:
            print(f"Warning: Error validating plan structure: {e}")
            # Structure validation failed, but don't break the entire process
    
    def _clean_plan_json_string(self, json_str):
        """Clean common JSON formatting issues in migration plan."""
        # Remove any leading/trailing whitespace
        json_str = json_str.strip()
        
        # Fix common issues with unescaped quotes in strings
        import re
        
        lines = json_str.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # If line contains a string value with unescaped quotes, try to fix
            if ':' in line and '"' in line:
                if line.count('"') > 2:  # More than just key-value quotes
                    # Find the value part after the colon
                    parts = line.split(':', 1)
                    if len(parts) == 2:
                        key_part = parts[0]
                        value_part = parts[1].strip()
                        # If value part has quotes, escape internal quotes
                        if value_part.startswith('"') and value_part.endswith('"'):
                            # Extract the content and escape internal quotes
                            content = value_part[1:-1]
                            content = content.replace('"', '\\"')
                            value_part = f'"{content}"'
                            line = f"{key_part}: {value_part}"
            
            cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines)
    
    def _get_default_plan_value(self, key):
        """Get default value for missing migration plan JSON keys."""
        defaults = {
            "migration_strategy": {
                "approach": "Phased",
                "rationale": "Using phased approach for safer migration. LLM plan generation incomplete - manual review recommended.",
                "estimated_timeline": "4-8 weeks (requires manual estimation based on project complexity)",
                "team_size_recommendation": "2-3 developers"
            },
            "phase_breakdown": [
                {
                    "phase": 1,
                    "name": "Preparation and Assessment",
                    "description": "Complete manual assessment and prepare for migration",
                    "duration": "1 week",
                    "deliverables": ["Migration plan", "Team training", "Environment setup"],
                    "tasks": [
                        {
                            "task_id": "manual-assessment",
                            "title": "Complete Migration Assessment",
                            "description": "Review automated analysis results and create detailed migration plan",
                            "complexity": "Medium",
                            "estimated_hours": "16-24 hours",
                            "dependencies": [],
                            "automation_potential": "Low",
                            "tools_required": ["Manual review", "Analysis results"]
                        }
                    ],
                    "risks": ["Incomplete automated analysis", "Missing migration details"],
                    "success_criteria": ["Detailed plan created", "Team understands migration scope"]
                },
                {
                    "phase": 2,
                    "name": "Spring Boot and Dependency Updates",
                    "description": "Update Spring Boot version and related dependencies",
                    "duration": "1-2 weeks",
                    "deliverables": ["Updated build files", "Resolved dependency conflicts"],
                    "tasks": [
                        {
                            "task_id": "spring-boot-upgrade",
                            "title": "Upgrade Spring Boot to 3.x",
                            "description": "Update Spring Boot version in build files and resolve conflicts",
                            "complexity": "Medium",
                            "estimated_hours": "12-20 hours",
                            "dependencies": ["manual-assessment"],
                            "automation_potential": "Medium",
                            "tools_required": ["Build tools", "Dependency management"]
                        }
                    ],
                    "risks": ["Version conflicts", "Breaking dependency changes"],
                    "success_criteria": ["Application builds successfully", "No dependency conflicts"]
                },
                {
                    "phase": 3,
                    "name": "Jakarta EE Migration",
                    "description": "Migrate from javax.* to jakarta.* imports and references",
                    "duration": "1-2 weeks",
                    "deliverables": ["Updated imports", "Migrated code", "Configuration updates"],
                    "tasks": [
                        {
                            "task_id": "jakarta-migration",
                            "title": "Convert javax to jakarta imports",
                            "description": "Replace all javax.* imports and references with jakarta.* equivalents",
                            "complexity": "Medium",
                            "estimated_hours": "20-30 hours",
                            "dependencies": ["spring-boot-upgrade"],
                            "automation_potential": "High",
                            "tools_required": ["IDE refactoring", "Search and replace tools"]
                        }
                    ],
                    "risks": ["Missed references", "Configuration issues"],
                    "success_criteria": ["All javax references updated", "Application compiles"]
                },
                {
                    "phase": 4,
                    "name": "Testing and Validation",
                    "description": "Comprehensive testing of migrated application",
                    "duration": "1-2 weeks",
                    "deliverables": ["Test results", "Performance validation", "Deployment verification"],
                    "tasks": [
                        {
                            "task_id": "comprehensive-testing",
                            "title": "Execute Full Test Suite",
                            "description": "Run all tests and validate application functionality",
                            "complexity": "High",
                            "estimated_hours": "24-40 hours",
                            "dependencies": ["jakarta-migration"],
                            "automation_potential": "High",
                            "tools_required": ["Test frameworks", "Performance monitoring"]
                        }
                    ],
                    "risks": ["Test failures", "Performance regression"],
                    "success_criteria": ["All tests pass", "Performance meets requirements"]
                }
            ],
            "automation_recommendations": [
                {
                    "tool": "IDE Refactoring Tools",
                    "purpose": "Automate javax to jakarta import replacements",
                    "setup_instructions": "Use IDE find/replace or refactoring tools to update imports systematically",
                    "coverage": "80-90% of import changes"
                },
                {
                    "tool": "OpenRewrite",
                    "purpose": "Automated code transformation for Spring Boot migration",
                    "setup_instructions": "Add OpenRewrite plugin to build file and configure Spring Boot 3 migration recipes",
                    "coverage": "60-70% of code changes"
                },
                {
                    "tool": "Spring Boot Migrator",
                    "purpose": "Comprehensive migration analysis and code transformation",
                    "setup_instructions": "Install and run Spring Boot Migrator tool against codebase",
                    "coverage": "50-60% of migration tasks"
                }
            ],
            "manual_changes": [
                {
                    "category": "Configuration Updates",
                    "changes": ["Review and update application.properties/yml files", "Update Spring Security configuration", "Verify actuator endpoint configurations"],
                    "rationale": "Configuration changes require manual review to ensure compatibility"
                },
                {
                    "category": "Custom Code Review",
                    "changes": ["Review custom Spring components", "Update deprecated API usage", "Validate third-party integrations"],
                    "rationale": "Custom code requires manual analysis for migration compatibility"
                }
            ],
            "testing_strategy": {
                "unit_tests": "Update test frameworks (JUnit 4 to 5), review test annotations, validate mock configurations",
                "integration_tests": "Update Spring test slices, verify test container configurations, validate security test setup",
                "regression_testing": "Execute full test suite, perform smoke testing, validate critical user journeys"
            },
            "rollback_plan": {
                "triggers": ["Critical test failures", "Performance degradation", "Production issues"],
                "steps": ["Stop deployment", "Restore from backup/previous version", "Verify system stability", "Document issues"],
                "data_considerations": "Ensure javax→jakarta changes don't affect data persistence"
            },
            "success_metrics": [
                {
                    "metric": "Build Success Rate",
                    "target": "100% successful builds",
                    "measurement_method": "CI/CD pipeline execution"
                },
                {
                    "metric": "Test Coverage",
                    "target": "Maintain or improve existing coverage",
                    "measurement_method": "Test coverage tools"
                },
                {
                    "metric": "Performance Baseline",
                    "target": "No degradation from current performance",
                    "measurement_method": "Performance testing and monitoring"
                }
            ]
        }
        return defaults.get(key, {})
    
    def _get_fallback_plan(self, analysis, project_name):
        """Generate a fallback migration plan when LLM parsing fails."""
        
        # Extract effort estimation from analysis if available
        effort_estimation = analysis.get("effort_estimation", {})
        total_effort = effort_estimation.get("total_effort", "Manual estimation required")
        
        # Determine project complexity from analysis
        executive_summary = analysis.get("executive_summary", {})
        migration_impact = executive_summary.get("migration_impact", "Unknown impact")
        
        # Create a basic fallback plan
        fallback_plan = {
            "migration_strategy": {
                "approach": "Phased",
                "rationale": f"Fallback plan for {project_name}. LLM plan generation encountered parsing issues. Estimated effort: {total_effort}. Manual planning recommended.",
                "estimated_timeline": "Manual estimation required due to plan generation issues",
                "team_size_recommendation": "2-3 developers (adjust based on project complexity)"
            },
            "phase_breakdown": [
                {
                    "phase": 1,
                    "name": "Assessment and Planning",
                    "description": "Manual assessment due to automated plan generation failure",
                    "duration": "3-5 days",
                    "deliverables": ["Manual migration plan", "Risk assessment", "Resource allocation"],
                    "tasks": [
                        {
                            "task_id": "manual-assessment",
                            "title": "Manual Migration Assessment",
                            "description": "Review automated analysis and create detailed migration plan",
                            "complexity": "Medium",
                            "estimated_hours": "16-24 hours",
                            "dependencies": [],
                            "automation_potential": "Low",
                            "tools_required": ["Manual review", "Migration analysis results"]
                        }
                    ],
                    "risks": ["Incomplete automated analysis", "Manual planning overhead"],
                    "success_criteria": ["Detailed migration plan created", "Team aligned on approach"]
                },
                {
                    "phase": 2,
                    "name": "Dependency and Build Updates",
                    "description": "Update Spring Boot and related dependencies",
                    "duration": "1-2 weeks",
                    "deliverables": ["Updated build files", "Dependency compatibility verification"],
                    "tasks": [
                        {
                            "task_id": "dependency-updates",
                            "title": "Update Spring Boot and Dependencies",
                            "description": "Upgrade to Spring Boot 3.x and compatible versions",
                            "complexity": "Medium",
                            "estimated_hours": "8-16 hours",
                            "dependencies": ["manual-assessment"],
                            "automation_potential": "Medium",
                            "tools_required": ["Build tools", "Dependency analysis"]
                        }
                    ],
                    "risks": ["Version conflicts", "Breaking changes"],
                    "success_criteria": ["Application builds successfully", "Tests pass with new dependencies"]
                },
                {
                    "phase": 3,
                    "name": "Code Migration",
                    "description": "Apply javax to jakarta migrations and code updates",
                    "duration": "1-3 weeks",
                    "deliverables": ["Migrated source code", "Updated imports", "Configuration updates"],
                    "tasks": [
                        {
                            "task_id": "jakarta-migration",
                            "title": "Jakarta Namespace Migration",
                            "description": "Replace javax.* with jakarta.* imports and references",
                            "complexity": "Medium",
                            "estimated_hours": "16-32 hours",
                            "dependencies": ["dependency-updates"],
                            "automation_potential": "High",
                            "tools_required": ["IDE refactoring", "Find/replace tools"]
                        }
                    ],
                    "risks": ["Missed references", "Configuration issues"],
                    "success_criteria": ["All javax references updated", "Application compiles successfully"]
                },
                {
                    "phase": 4,
                    "name": "Testing and Validation",
                    "description": "Comprehensive testing of migrated application",
                    "duration": "1-2 weeks",
                    "deliverables": ["Test results", "Performance validation", "Deployment verification"],
                    "tasks": [
                        {
                            "task_id": "testing-validation",
                            "title": "Comprehensive Testing",
                            "description": "Run all tests and validate functionality",
                            "complexity": "High",
                            "estimated_hours": "24-40 hours",
                            "dependencies": ["jakarta-migration"],
                            "automation_potential": "High",
                            "tools_required": ["Test frameworks", "CI/CD pipeline"]
                        }
                    ],
                    "risks": ["Functionality regressions", "Performance issues"],
                    "success_criteria": ["All tests pass", "Performance acceptable", "Ready for deployment"]
                }
            ],
            "automation_recommendations": [
                {
                    "tool": "OpenRewrite",
                    "purpose": "Automated Spring Boot 3 migration recipes",
                    "setup_instructions": "Add OpenRewrite plugin and apply Spring Boot 3 recipes",
                    "coverage": "60-80% of common migration patterns"
                },
                {
                    "tool": "IDE Refactoring",
                    "purpose": "Find and replace javax.* with jakarta.*",
                    "setup_instructions": "Use IDE global find/replace with regex patterns",
                    "coverage": "90% of import statement updates"
                }
            ],
            "manual_changes": [
                {
                    "category": "Complex Configurations",
                    "changes": ["Security configuration updates", "Custom auto-configurations", "Integration configurations"],
                    "rationale": "Complex configurations require manual review and testing"
                },
                {
                    "category": "Third-party Integrations",
                    "changes": ["External API integrations", "Legacy library compatibility"],
                    "rationale": "Third-party integrations need case-by-case assessment"
                }
            ],
            "testing_strategy": {
                "unit_tests": "Update test dependencies and run all unit tests to verify functionality",
                "integration_tests": "Run integration tests with new Spring version and validate external integrations",
                "regression_testing": "Comprehensive regression testing to ensure no functionality is broken"
            },
            "rollback_plan": {
                "triggers": ["Critical functionality failure", "Performance degradation", "Deployment issues"],
                "steps": [
                    "Stop deployment process",
                    "Restore previous Spring Boot version",
                    "Revert dependency changes",
                    "Restore from backup if necessary",
                    "Investigate and address root cause"
                ],
                "data_considerations": "Ensure database compatibility between Spring versions"
            },
            "success_metrics": [
                {
                    "metric": "Application Functionality",
                    "target": "100% of existing features working",
                    "measurement_method": "Comprehensive test suite execution"
                },
                {
                    "metric": "Performance",
                    "target": "No significant performance degradation",
                    "measurement_method": "Performance testing and monitoring"
                },
                {
                    "metric": "Dependency Security",
                    "target": "No high-risk vulnerabilities",
                    "measurement_method": "Security scanning tools"
                }
            ]
        }
        
        return fallback_plan

    def post(self, shared, prep_res, exec_res):
        shared["migration_plan"] = exec_res
        print("✅ Migration plan generated")
        return "default"


class EnhancedFileBackupManager(Node):
    """
    Creates backups with proper directory structure preservation for git integration.
    """
    
    def prep(self, shared):
        files_data = shared["files"]
        output_dir = shared["output_dir"]
        project_name = shared["project_name"]
        
        return files_data, output_dir, project_name
    
    def exec(self, prep_res):
        import os
        import shutil
        from datetime import datetime
        
        files_data, output_dir, project_name = prep_res
        
        # Create backup directory with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(output_dir, f"{project_name}_backup_{timestamp}")
        
        # Create migration workspace with proper directory structure
        migration_workspace = os.path.join(output_dir, f"{project_name}_migration_{timestamp}")
        
        os.makedirs(backup_dir, exist_ok=True)
        os.makedirs(migration_workspace, exist_ok=True)
        
        print(f"📦 Creating structured backup and migration workspace...")
        
        backup_info = {
            "backup_dir": backup_dir,
            "migration_workspace": migration_workspace,
            "timestamp": timestamp,
            "files_backed_up": [],
            "migration_files": []
        }
        
        for i, (file_path, content) in enumerate(files_data):
            # Create backup with flattened names (for safety)
            backup_file_path = os.path.join(backup_dir, file_path.replace("/", "_").replace("\\", "_"))
            
            # Create migration file with proper directory structure
            migration_file_path = os.path.join(migration_workspace, file_path)
            migration_dir = os.path.dirname(migration_file_path)
            
            # Ensure directory exists for migration file
            if migration_dir:
                os.makedirs(migration_dir, exist_ok=True)
            
            # Write backup file (flattened)
            with open(backup_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Write migration file (structured)
            with open(migration_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            backup_info["files_backed_up"].append({
                "original_path": file_path,
                "backup_path": backup_file_path
            })
            
            backup_info["migration_files"].append({
                "original_path": file_path,
                "migration_path": migration_file_path
            })
            
            if (i + 1) % 10 == 0:
                print(f"   Processed {i + 1}/{len(files_data)} files...")
        
        # Create backup manifest
        manifest_path = os.path.join(backup_dir, "backup_manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2)
        
        # Create migration workspace README
        readme_path = os.path.join(migration_workspace, "MIGRATION_README.md")
        with open(readme_path, 'w', encoding='utf-8') as f:
            f.write(self._create_migration_readme(project_name, timestamp))
        
        print(f"✅ Backup completed: {backup_dir}")
        print(f"✅ Migration workspace created: {migration_workspace}")
        return backup_info
    
    def _create_migration_readme(self, project_name, timestamp):
        """Create a README for the migration workspace."""
        return f"""# Spring Migration Workspace - {project_name}

**Created:** {timestamp}
**Purpose:** Spring 5 → Spring 6 Migration

## Directory Structure

This directory contains the source files from your project with preserved directory structure, ready for git operations.

## Git Workflow

### 1. Initialize git repository (if not already)
```bash
cd {project_name}_migration_{timestamp}
git init
git add .
git commit -m "Initial commit - Pre-migration source code"
```

### 2. Apply migration changes
After running the migration tool, you'll have modified files in this directory.

### 3. Review changes
```bash
git diff                    # See all changes
git status                  # See modified files
git diff src/main/java/     # See specific directory changes
```

### 4. Commit changes
```bash
git add .
git commit -m "Spring 5 to 6 migration - Automated changes

- Updated javax.* to jakarta.* imports
- Migrated Spring Security configuration
- Updated dependency versions
- Fixed deprecated API usage
"
```

### 5. Create branch (recommended)
```bash
git checkout -b spring-6-migration
git commit -m "Spring 6 migration changes"
```

## Files Included

This workspace contains all source files from your original project with the same directory structure, allowing you to:

1. Track changes with git
2. Review modifications line by line
3. Selectively apply changes
4. Create commits with proper change history
5. Merge back to your main project

## Safety Notes

- Original files are backed up separately in the backup directory
- This workspace is a copy - your original project is unchanged
- Use git to track and manage migration changes
- Test thoroughly before applying to your main project
"""
    
    def post(self, shared, prep_res, exec_res):
        shared["backup_info"] = exec_res
        return "default"


class GitMigrationManager(Node):
    """
    Manages git operations for migration changes with proper workflow.
    """
    
    def prep(self, shared):
        backup_info = shared.get("backup_info", {})
        applied_changes = shared.get("applied_changes", {})
        project_name = shared["project_name"]
        
        return backup_info, applied_changes, project_name
    
    def exec(self, prep_res):
        import os
        import subprocess
        from datetime import datetime
        
        backup_info, applied_changes, project_name = prep_res
        migration_workspace = backup_info.get("migration_workspace")
        
        if not migration_workspace or not os.path.exists(migration_workspace):
            print("❌ Migration workspace not found - skipping git operations")
            return {"status": "skipped", "reason": "No migration workspace"}
        
        print(f"🔧 Setting up git workflow in migration workspace...")
        
        # Change to migration workspace
        original_cwd = os.getcwd()
        os.chdir(migration_workspace)
        
        try:
            git_info = {
                "workspace_path": migration_workspace,
                "operations": [],
                "branch_name": None,
                "commit_hash": None
            }
            
            # Initialize git if not exists
            if not os.path.exists(".git"):
                result = subprocess.run(["git", "init"], capture_output=True, text=True)
                if result.returncode == 0:
                    git_info["operations"].append("✅ Git repository initialized")
                    print("   Git repository initialized")
                else:
                    print(f"   Warning: Git init failed: {result.stderr}")
            
            # Configure git user if not set (for CI environments)
            self._ensure_git_config()
            
            # Add all files and create initial commit
            subprocess.run(["git", "add", "."], capture_output=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            initial_commit_msg = f"Initial commit - {project_name} pre-migration source"
            
            result = subprocess.run(
                ["git", "commit", "-m", initial_commit_msg], 
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                git_info["operations"].append("✅ Initial commit created")
                print("   Initial commit created")
                
                # Get commit hash
                commit_result = subprocess.run(
                    ["git", "rev-parse", "HEAD"], 
                    capture_output=True, text=True
                )
                if commit_result.returncode == 0:
                    git_info["commit_hash"] = commit_result.stdout.strip()
            
            # Create migration branch
            branch_name = f"spring-6-migration-{timestamp}"
            result = subprocess.run(
                ["git", "checkout", "-b", branch_name], 
                capture_output=True, text=True
            )
            
            if result.returncode == 0:
                git_info["branch_name"] = branch_name
                git_info["operations"].append(f"✅ Created branch: {branch_name}")
                print(f"   Created migration branch: {branch_name}")
            
            # Create git workflow script
            self._create_git_workflow_script(migration_workspace, project_name, applied_changes)
            
            return git_info
            
        except Exception as e:
            print(f"   Error setting up git: {e}")
            return {"status": "error", "error": str(e)}
        
        finally:
            # Return to original directory
            os.chdir(original_cwd)
    
    def _ensure_git_config(self):
        """Ensure git user is configured for commits."""
        import subprocess
        
        # Check if user.name is set
        result = subprocess.run(
            ["git", "config", "user.name"], 
            capture_output=True, text=True
        )
        
        if result.returncode != 0:
            # Set default user for migration commits
            subprocess.run(
                ["git", "config", "user.name", "Spring Migration Tool"], 
                capture_output=True
            )
            subprocess.run(
                ["git", "config", "user.email", "migration-tool@localhost"], 
                capture_output=True
            )
            print("   Configured git user for migration commits")
    
    def _create_git_workflow_script(self, workspace, project_name, applied_changes):
        """Create a script to help with the git workflow."""
        script_content = f"""#!/bin/bash
# Git Workflow Script for {project_name} Spring Migration

echo "🔄 Spring Migration Git Workflow"
echo "================================="
echo ""

# Show current status
echo "📊 Current Git Status:"
git status --short
echo ""

# Show change summary
echo "📈 Change Summary:"
echo "  Modified files: $(git diff --name-only --cached | wc -l)"
echo "  Total changes: $(git diff --cached --stat | tail -1)"
echo ""

# Offer common operations
echo "🔧 Available Operations:"
echo "  1. Review all changes:     git diff --cached"
echo "  2. Review specific file:   git diff --cached <filename>"
echo "  3. Unstage changes:       git reset HEAD <filename>"
echo "  4. Commit changes:        git commit -m 'Spring 6 migration changes'"
echo "  5. Create patch:          git diff --cached > migration.patch"
echo "  6. Show branch info:      git branch -v"
echo ""

# Interactive options
read -p "🤔 What would you like to do? [review/commit/status/help]: " action

case $action in
    "review"|"r")
        echo "📖 Reviewing changes..."
        git diff --cached --name-status
        echo ""
        read -p "See detailed diff? [y/N]: " show_diff
        if [[ $show_diff =~ ^[Yy]$ ]]; then
            git diff --cached
        fi
        ;;
    "commit"|"c")
        echo "💾 Committing changes..."
        git commit -m "Spring 5 to 6 migration - Automated changes

✅ Migration completed for {project_name}
📊 Changes applied: $(git diff --cached --stat | tail -1)

Changes include:
- javax.* → jakarta.* namespace migration
- Spring Security configuration updates  
- Dependency version updates
- Deprecated API replacements

Generated by Spring Migration Tool"
        echo "✅ Changes committed!"
        ;;
    "status"|"s")
        git status
        git log --oneline -5
        ;;
    "help"|"h")
        echo ""
        echo "📚 Git Migration Help:"
        echo "======================"
        echo ""
        echo "Common Commands:"
        echo "  git diff --cached              # Review all staged changes"
        echo "  git diff --cached <file>       # Review specific file"
        echo "  git status                     # See current status"
        echo "  git commit -m 'message'        # Commit changes"
        echo "  git reset HEAD <file>          # Unstage specific file"
        echo "  git reset HEAD                 # Unstage all changes"
        echo ""
        echo "Migration Workflow:"
        echo "  1. Review changes with 'git diff --cached'"
        echo "  2. Test the changes in your development environment"
        echo "  3. Commit with 'git commit -m \"Spring 6 migration\"'"
        echo "  4. Copy changes back to your main project"
        echo ""
        ;;
    *)
        echo "ℹ️  Run this script again or use git commands directly"
        ;;
esac
"""
        
        script_path = os.path.join(workspace, "git-migration-workflow.sh")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        # Make script executable
        import stat
        os.chmod(script_path, stat.S_IRWXU | stat.S_IRGRP | stat.S_IROTH)
        
        print(f"   Created git workflow script: git-migration-workflow.sh")

    def post(self, shared, prep_res, exec_res):
        shared["git_info"] = exec_res
        return "default"


class MigrationChangeGenerator(Node):
    """
    Enhanced change generator with concurrent file processing capabilities.
    """
    
    def prep(self, shared):
        vlogger = get_verbose_logger()
        
        if shared.get("verbose_mode"):
            vlogger.step("Preparing migration change generation")
        
        files_data = shared["files"]
        analysis = shared.get("migration_analysis", {})
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        optimization_settings = shared.get("optimization_settings", {})
        
        # Defensive check: ensure analysis has required structure
        if not isinstance(analysis, dict):
            if shared.get("verbose_mode"):
                vlogger.warning("Analysis is not a dictionary, using empty analysis")
            analysis = {}
        
        # Ensure critical keys exist with safe defaults
        if "executive_summary" not in analysis:
            if shared.get("verbose_mode"):
                vlogger.warning("Missing executive_summary in analysis, adding default")
            analysis["executive_summary"] = {
                "migration_impact": "Unknown - analysis incomplete",
                "key_blockers": [],
                "recommended_approach": "Manual review required"
            }
        
        if "detailed_analysis" not in analysis:
            if shared.get("verbose_mode"):
                vlogger.warning("Missing detailed_analysis in analysis, adding default")
            analysis["detailed_analysis"] = {}
        
        if shared.get("verbose_mode"):
            vlogger.debug(f"Analysis validated with keys: {list(analysis.keys())}")
        
        return files_data, analysis, project_name, use_cache, optimization_settings
    
    def exec(self, prep_res):
        files_data, analysis, project_name, use_cache, optimization_settings = prep_res
        
        vlogger = get_verbose_logger()
        if optimization_settings.get("verbose_mode"):
            vlogger.debug(f"Starting change generation for {len(files_data)} files")
            vlogger.debug(f"Analysis object type: {type(analysis)}")
            vlogger.debug(f"Analysis keys: {list(analysis.keys()) if isinstance(analysis, dict) else 'Not a dict'}")
        
        # Double-check analysis object integrity before proceeding
        if not isinstance(analysis, dict):
            if optimization_settings.get("verbose_mode"):
                vlogger.error("Analysis is not a dictionary! Creating empty analysis.")
            analysis = {
                "executive_summary": {"migration_impact": "Unknown", "key_blockers": []},
                "detailed_analysis": {}
            }
        
        monitor = get_performance_monitor()
        monitor.start_operation("migration_change_generation")
        
        print(f"🔧 Generating specific migration changes using LLM analysis...")
        
        # Initialize changes structure
        changes = {
            "javax_to_jakarta": [],
            "spring_security_updates": [],
            "dependency_updates": [],
            "configuration_updates": [],
            "other_changes": []
        }
        
        # Optimization: Use concurrent analysis if enabled
        batch_size = optimization_settings.get("batch_size", 10)
        max_workers = optimization_settings.get("max_workers", 4)
        parallel_enabled = optimization_settings.get("parallel", False)
        
        if parallel_enabled and len(files_data) > 5:
            from utils.concurrent_manager import ConcurrentAnalysisManager
            concurrent_manager = ConcurrentAnalysisManager(max_workers=max_workers)
            
            try:
                def analyze_file_wrapper(file_path, content):
                    return self._analyze_file_with_llm(file_path, content, analysis, project_name, use_cache)
                
                results = concurrent_manager.process_files_concurrently(
                    files_data, 
                    analyze_file_wrapper,
                    batch_size=batch_size
                )
                
                # Merge all results
                for file_changes in results:
                    for change_type, file_change_list in file_changes.items():
                        changes[change_type].extend(file_change_list)
            
            finally:
                concurrent_manager.shutdown()
        else:
            # Process sequentially
            for i, (file_path, content) in enumerate(files_data):
                if i % 10 == 0:
                    print(f"   Analyzing {file_path} ({i+1}/{len(files_data)})...")
                
                try:
                    file_changes = self._analyze_file_with_llm(file_path, content, analysis, project_name, use_cache)
                    
                    for change_type, file_change_list in file_changes.items():
                        changes[change_type].extend(file_change_list)
                        
                except Exception as e:
                    if optimization_settings.get("verbose_mode"):
                        vlogger.error(f"Error analyzing {file_path}: {e}")
                    print(f"     Error analyzing {file_path}: {e}")
                    # Continue with next file
                    continue
        
        monitor.end_operation("migration_change_generation", 
                            files_processed=len(files_data),
                            llm_calls=len([f for f, c in files_data if not self._should_skip_file(f)]))
        
        return changes
    
    def _analyze_file_with_llm(self, file_path, content, analysis, project_name, use_cache):
        """Use LLM to analyze a single file and generate specific changes needed."""
        
        # Skip analysis for very large files or binary-like content
        if len(content) > 20000:
            print(f"     Skipping large file: {file_path}")
            return self._get_empty_changes()
        
        if not self._is_text_file(file_path, content):
            print(f"     Skipping non-text file: {file_path}")
            return self._get_empty_changes()
        
        # Skip files that are unlikely to need Spring migration changes
        if self._should_skip_file(file_path):
            print(f"     Skipping non-migration-relevant file: {file_path}")
            return self._get_empty_changes()
        
        # **NEW: Check Java version compatibility FIRST**
        if file_path.endswith(('pom.xml', '.gradle', '.gradle.kts')):
            java_version_issues = self._check_java_version_compatibility(content, file_path)
            if java_version_issues:
                # Return Java version issues as high-priority changes
                return java_version_issues
        
        # **NEW: Pre-filter files that don't actually need changes**
        if not self._file_needs_migration_analysis(file_path, content):
            # Silently skip - no need to report files that don't need changes
            return self._get_empty_changes()
        
        # Create context from the migration analysis
        analysis_context = self._create_analysis_context(analysis)
        
        # Prepare file content for LLM (limit size and clean it)
        clean_content = self._prepare_file_content_for_llm(content, file_path)
        
        # Enhanced prompt with better JSON guidance
        prompt = f"""# Spring Migration Change Analysis - JAVAX TO JAKARTA PRIORITY

You are analyzing a file from project `{project_name}` for Spring 6 migration. **PRIMARY FOCUS: JAVAX TO JAKARTA MIGRATION**

## Overall Migration Analysis Context:
{analysis_context}

## File to Analyze:
**File Path:** {file_path}
**File Type:** {self._get_file_type(file_path)}
**File Content:**
```
{clean_content}
```

## 🚨 **CRITICAL JAVAX TO JAKARTA REQUIREMENTS** 🚨

### **HIGHEST PRIORITY: javax.* → jakarta.* Migration**

**YOU MUST SCAN FOR AND UPDATE ALL javax.* IMPORTS**

#### **Required javax→jakarta mappings (scan for these exactly):**

**JPA/Persistence (Most Common):**
- `javax.persistence.Entity` → `jakarta.persistence.Entity`
- `javax.persistence.Id` → `jakarta.persistence.Id`
- `javax.persistence.GeneratedValue` → `jakarta.persistence.GeneratedValue`
- `javax.persistence.Column` → `jakarta.persistence.Column`
- `javax.persistence.Table` → `jakarta.persistence.Table`
- `javax.persistence.JoinColumn` → `jakarta.persistence.JoinColumn`
- `javax.persistence.OneToMany` → `jakarta.persistence.OneToMany`
- `javax.persistence.ManyToOne` → `jakarta.persistence.ManyToOne`
- `javax.persistence.OneToOne` → `jakarta.persistence.OneToOne`
- `javax.persistence.ManyToMany` → `jakarta.persistence.ManyToMany`

**Validation (Very Common):**
- `javax.validation.constraints.NotNull` → `jakarta.validation.constraints.NotNull`
- `javax.validation.constraints.NotEmpty` → `jakarta.validation.constraints.NotEmpty`
- `javax.validation.constraints.NotBlank` → `jakarta.validation.constraints.NotBlank`
- `javax.validation.constraints.Size` → `jakarta.validation.constraints.Size`
- `javax.validation.constraints.Email` → `jakarta.validation.constraints.Email`
- `javax.validation.Valid` → `jakarta.validation.Valid`

**Servlet API (Common in Controllers):**
- `javax.servlet.http.HttpServletRequest` → `jakarta.servlet.http.HttpServletRequest`
- `javax.servlet.http.HttpServletResponse` → `jakarta.servlet.http.HttpServletResponse`
- `javax.servlet.ServletException` → `jakarta.servlet.ServletException`

**Dependency Injection:**
- `javax.inject.Inject` → `jakarta.inject.Inject`
- `javax.inject.Named` → `jakarta.inject.Named`

**⚠️ SCAN THE ACTUAL FILE CONTENT FOR THESE EXACT IMPORT PATTERNS ⚠️**

### **Step 1: MANDATORY javax.* Scan**
1. Look for ANY line starting with `import javax.`
2. For EACH javax.* import found, add it to javax_to_jakarta array
3. Map it to corresponding jakarta.* package
4. Mark as "automatic": true (safe replacement)

### **Step 2: Look for javax.* in annotations and code**
1. Check for javax.* references in annotations like `@javax.persistence.Entity`
2. Check for javax.* in fully qualified class names in code
3. Check for javax.* in comments or strings (for reference updates)

## CRITICAL VALIDATION RULES - You MUST follow these:

### Rule 1: File Type Restrictions
- **Java source files (.java)**: FOCUS ON javax→jakarta imports, Spring annotations, code changes
- **Build files (pom.xml, .gradle)**: ONLY dependency versions, plugin versions, properties
- **Config files (.properties, .yml)**: ONLY configuration property changes
- **NEVER suggest version updates for Java source files**
- **NEVER suggest import changes for build files**

### Rule 2: Content Verification Required
- **ONLY suggest changes for content that ACTUALLY EXISTS in the file**
- **Before suggesting javax.* → jakarta.* change, VERIFY the javax import exists in the file content above**
- **Before suggesting version updates, VERIFY the version number exists in the file**
- **Do NOT make assumptions about content not shown**

### Rule 3: Change Type Validation
- **javax_to_jakarta**: For .java files with actual javax.* imports (TOP PRIORITY)
- **spring_security_version_update**: ONLY for pom.xml/build.gradle files with actual Spring Security dependencies
- **import_replacement**: ONLY for .java files with actual imports
- **dependency_updates**: ONLY for build files (pom.xml, .gradle)

## ENHANCED Migration Guidelines:

### For Java Source Files ONLY:

#### 1. **🎯 PRIORITY #1: Jakarta EE Migration (javax.* → jakarta.*)**
**SCAN EXHAUSTIVELY FOR THESE javax.* IMPORTS:**
- **JPA/Hibernate**: javax.persistence.* → jakarta.persistence.*
- **Validation**: javax.validation.* → jakarta.validation.*
- **Servlet API**: javax.servlet.* → jakarta.servlet.*
- **JMS**: javax.jms.* → jakarta.jms.*
- **EJB**: javax.ejb.* → jakarta.ejb.*
- **CDI**: javax.inject.* → jakarta.inject.*
- **JAX-RS**: javax.ws.rs.* → jakarta.ws.rs.*
- **JSON-B**: javax.json.* → jakarta.json.*
- **Security**: javax.security.* → jakarta.security.*

**⚠️ EVERY javax.* import MUST be replaced - this is not optional**

#### 2. JUnit 4 → JUnit 5 Migration
- **@Test**: Usually stays the same, but import changes
- **@Before** → **@BeforeEach**
- **@After** → **@AfterEach**
- **@BeforeClass** → **@BeforeAll**
- **@AfterClass** → **@AfterAll**
- **@Ignore** → **@Disabled**
- **@RunWith** → **@ExtendWith**
- **@Rule** → **@RegisterExtension** (context-dependent)

#### 3. Spring Test Framework Updates
- **@RunWith(SpringRunner.class)** → **@ExtendWith(SpringExtension.class)**
- **@TestMethodOrder**, **@TestInstance** may need updates
- **MockitoJUnitRunner** → **MockitoExtension**

#### 4. Spring Security Configuration Updates
- **WebSecurityConfigurerAdapter** → **SecurityFilterChain** bean
- **authorizeRequests()** → **authorizeHttpRequests()**
- **antMatchers()** → **requestMatchers()**
- **@EnableGlobalMethodSecurity** → **@EnableMethodSecurity**

### For Build Files (pom.xml, .gradle) ONLY:
- Update Spring Boot/Security dependency versions (ONLY if they exist in file)
- Update Java version if specified
- Update JUnit version: 4.x → 5.x
- Update Mockito version for compatibility
- **DO NOT suggest import changes in build files**

### For Configuration Files ONLY:
- Update property names/values
- Spring Security property updates
- **DO NOT suggest code or dependency changes**

## **EXAMPLE CORRECT javax.* MIGRATION:**

**If you find this in the file:**
```java
import javax.persistence.Entity;
import javax.persistence.Id;
import javax.validation.constraints.NotNull;
```

**YOU MUST INCLUDE THESE CHANGES:**
```json
{{
  "javax_to_jakarta": [
    {{
      "file": "{{file_path}}",
      "type": "import_replacement",
      "from": "javax.persistence.Entity",
      "to": "jakarta.persistence.Entity",
      "automatic": true,
      "description": "JPA: javax.persistence → jakarta.persistence"
    }},
    {{
      "file": "{{file_path}}",
      "type": "import_replacement", 
      "from": "javax.persistence.Id",
      "to": "jakarta.persistence.Id",
      "automatic": true,
      "description": "JPA: javax.persistence → jakarta.persistence"
    }},
    {{
      "file": "{{file_path}}",
      "type": "import_replacement",
      "from": "javax.validation.constraints.NotNull", 
      "to": "jakarta.validation.constraints.NotNull",
      "automatic": true,
      "description": "Bean Validation: javax.validation → jakarta.validation"
    }}
  ]
}}
```

## CRITICAL: You MUST respond with ONLY valid JSON - no additional text or explanations

Your response must be ONLY a JSON object with this exact structure:

{{
  "javax_to_jakarta": [],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}}

## JSON Response Rules:
1. Return ONLY the JSON object - no markdown, no explanation text
2. **SCAN THE FILE CONTENT ABOVE FOR javax.* imports - INCLUDE ALL OF THEM**
3. **javax_to_jakarta array is HIGHEST PRIORITY - never leave it empty if javax.* imports exist**
4. **Verify file type matches change type (Java=imports, Build=versions)**
5. Use only basic ASCII characters in strings
6. If no changes needed in a category, use empty array: []
7. **Mark javax→jakarta changes as automatic:true** (they are safe replacements)
8. Use "automatic": false only for complex changes requiring manual review
9. **Double-check: Did I scan for ALL javax.* imports in the file content?**

**SCAN THE FILE CONTENT NOW FOR javax.* IMPORTS AND RETURN THE JSON RESPONSE:**"""

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            
            # Enhanced debugging
            if len(response) < 50:
                print(f"     Warning: Very short LLM response for {file_path}: {len(response)} chars")
                return self._get_empty_changes()
            
            # Clean and extract JSON from response
            json_str = self._extract_and_clean_json(response, file_path)
            if not json_str:
                print(f"     Failed to extract JSON from LLM response for {file_path}")
                return self._get_empty_changes()
            
            # Parse JSON
            file_changes = json.loads(json_str)
            
            # Validate structure
            expected_keys = ["javax_to_jakarta", "spring_security_updates", "dependency_updates", "configuration_updates", "other_changes"]
            for key in expected_keys:
                if key not in file_changes:
                    file_changes[key] = []
            
            # **NEW: Enhanced validation that verifies changes against actual file content**
            validated_changes = self._validate_and_filter_changes(file_changes, content, file_path)
            
            # Report success only if there are real validated changes
            total_changes = sum(len(changes) for changes in validated_changes.values())
            if total_changes > 0:
                print(f"     ✅ Found {total_changes} validated changes for {file_path}")
                return validated_changes
            else:
                # No real changes found after validation - return empty 
                return self._get_empty_changes()
            
        except json.JSONDecodeError as e:
            print(f"     JSON parsing error for {file_path}: {e}")
            return self._get_empty_changes()
        except Exception as e:
            print(f"     Error analyzing {file_path}: {e}")
            return self._get_empty_changes()
    
    def _file_needs_migration_analysis(self, file_path, content):
        """Check if a file actually needs migration analysis by looking for relevant patterns."""
        content_lower = content.lower()
        
        # **ENHANCED: Check for javax imports that need migration**
        if 'import javax.' in content:
            return True
        
        # **ENHANCED: JPA/Hibernate specific patterns**
        jpa_hibernate_patterns = [
            'import javax.persistence.',
            '@entity',
            '@table',
            '@column',
            '@id',
            '@generatedvalue',
            '@onetomany',
            '@manytoone',
            '@joincolumn',
            '@embeddable',
            '@entitylisteners',
            'hibernatetemplate',
            'sessionfactory',
            'jpatemplate'
        ]
        
        if any(pattern in content_lower for pattern in jpa_hibernate_patterns):
            return True
        
        # **ENHANCED: Spring Security patterns that might need updates**
        spring_security_patterns = [
            'websecurityconfigureradapter',
            'authorizeequests()',
            'antmatchers(',
            'spring.security.',
            '@enablewebsecurity',
            '@enableglobalmethodsecurity',
            'httpsecurity',
            'authenticationmanager',
            'userdetailsservice',
            'passwordencoder',
            'csrf()',
            'cors()',
            'oauth2',
            'jwt'
        ]
        
        if any(pattern in content_lower for pattern in spring_security_patterns):
            return True
        
        # **NEW: JUnit 4→5 migration patterns**
        junit_patterns = [
            '@test',
            '@before',
            '@after',
            '@beforeclass',
            '@afterclass',
            '@runwith',
            '@rule',
            '@ignore',
            'import org.junit.test',
            'import org.junit.before',
            'import org.junit.after',
            'import org.junit.assert',
            'runner.class',
            'springrunner',
            'mockitojunitrunner'
        ]
        
        if any(pattern in content_lower for pattern in junit_patterns):
            return True
        
        # **NEW: Mockito annotation patterns**
        mockito_patterns = [
            '@mock',
            '@injectmocks',
            '@spy',
            '@captor',
            '@mockbean',
            '@spybean',
            'mockitoannotations',
            'mockito.when',
            'mockito.verify',
            'argumentcaptor'
        ]
        
        if any(pattern in content_lower for pattern in mockito_patterns):
            return True
        
        # **ENHANCED: Spring Test patterns that need migration**
        spring_test_patterns = [
            '@springboottest',
            '@datajpatest',
            '@webmvctest',
            '@jsontest',
            '@restclienttest',
            '@mockmvctest',
            'mockmvc',
            'testresttemplate',
            'webapplicationcontext',
            '@testconfiguration',
            '@testpropertysource',
            '@activeprofiles',
            '@sql',
            '@transactional',
            'import org.springframework.test',
            'import org.springframework.boot.test',
            '@testmethodorder',
            '@testinstance',
            '@parametrizedtest'
        ]
        
        if any(pattern in content_lower for pattern in spring_test_patterns):
            return True
        
        # **ENHANCED: Configuration files that might need updates**
        if file_path.endswith(('.xml', '.properties', '.yml', '.yaml')):
            config_patterns = [
                'javax.',
                'spring.security',
                'hibernate.ddl',
                'spring.jpa',
                'spring.test',
                'junit.',
                'logging.level.org.springframework',
                'management.endpoints',
                'spring.datasource'
            ]
            if any(pattern in content_lower for pattern in config_patterns):
                return True
        
        # **ENHANCED: Build files (always analyze, but with enhanced patterns)**
        if file_path.endswith(('pom.xml', '.gradle', '.gradle.kts', 'build.gradle.kts')):
            return True
        
        # If no relevant patterns found, skip analysis
        return False
    
    def _validate_and_filter_changes(self, file_changes, content, file_path):
        """Validate that suggested changes actually apply to the file content."""
        validated_changes = {
            "javax_to_jakarta": [],
            "spring_security_updates": [],
            "dependency_updates": [],
            "configuration_updates": [],
            "other_changes": []
        }
        
        for category, changes_list in file_changes.items():
            for change in changes_list:
                if self._validate_change_against_content(change, content, file_path, category):
                    validated_changes[category].append(change)
        
        return validated_changes
    
    def _validate_change_against_content(self, change, content, file_path, category):
        """Validate that a specific change actually applies to the file content."""
        if not isinstance(change, dict):
            return False
        
        # **NEW: Enhanced validation to catch false positives**
        if not self._validate_change_logic(change, content, file_path, category):
            return False
        
        # Validate javax to jakarta changes
        if category == "javax_to_jakarta":
            from_import = change.get("from", "")
            if not from_import:
                return False
            
            # **CRITICAL VALIDATION: Only allow actual javax.* package changes**
            if not from_import.startswith("javax."):
                print(f"     🚨 REJECTED: '{from_import}' is not a javax.* package in {file_path}")
                return False
            
            # **NEW: Detect when LLM incorrectly suggests custom package changes**
            # Check if this is trying to change a custom application package
            if any(custom_indicator in from_import.lower() for custom_indicator in [
                'piggymetrics', 'service.security', 'service.jakarta',  # Your specific app packages
                'com.example', 'org.mycompany', 'net.company'  # Common custom package prefixes
            ]):
                print(f"     🚨 REJECTED: '{from_import}' appears to be a custom package, not javax.* in {file_path}")
                return False
            
            # Check if the file actually contains this import
            import_patterns = [
                f"import {from_import}",
                f"import {from_import};",
                f"{from_import}",  # For qualified references
            ]
            
            if not any(pattern in content for pattern in import_patterns):
                print(f"     🔍 Skipping false positive: {from_import} not found in {file_path}")
                return False
        
        # Validate Spring Security changes
        elif category == "spring_security_updates":
            change_type = change.get("type", "")
            if change_type == "websecurity_adapter_replacement":
                if "WebSecurityConfigurerAdapter" not in content:
                    return False
        
        # Validate dependency changes
        elif category == "dependency_updates":
            # For build files, be more permissive
            if not file_path.endswith(('pom.xml', '.gradle', '.gradle.kts')):
                print(f"     🚨 REJECTED: Dependency update suggested for non-build file: {file_path}")
                return False
        
        # Basic validation that change has required fields
        required_fields = ["file", "type", "description"]
        if not all(field in change for field in required_fields):
            return False
        
        return True
    
    def _validate_change_logic(self, change, content, file_path, category):
        """Validate that the change makes logical sense for the file type and content."""
        change_type = change.get("type", "")
        from_value = change.get("from", "")
        to_value = change.get("to", "")
        
        # **Rule 1: Version updates should only be in build files**
        if any(keyword in change_type.lower() for keyword in ["version", "dependency", "spring_boot"]):
            if not file_path.endswith(('pom.xml', '.gradle', '.gradle.kts', 'build.gradle')):
                print(f"     🚨 LOGIC ERROR: Version/dependency change '{change_type}' suggested for Java file: {file_path}")
                return False
            
            # Verify version numbers actually exist in build file content
            if from_value and not any(version_pattern in content for version_pattern in [from_value, f"<version>{from_value}</version>", f'version "{from_value}"']):
                print(f"     🚨 LOGIC ERROR: Version '{from_value}' not found in build file: {file_path}")
                return False
        
        # **Rule 2: Import changes should only be in source files**
        if change_type in ["import_replacement", "import_update"]:
            if not file_path.endswith(('.java', '.kt', '.scala')):
                print(f"     🚨 LOGIC ERROR: Import change suggested for non-source file: {file_path}")
                return False
            
            # Verify import actually exists
            if from_value and f"import {from_value}" not in content:
                print(f"     🚨 LOGIC ERROR: Import '{from_value}' not found in source file: {file_path}")
                return False
        
        # **NEW: Rule 3: JUnit migration validation**
        if change_type in ["junit_migration", "junit_update"]:
            if not file_path.endswith(('.java', '.kt')):
                print(f"     🚨 LOGIC ERROR: JUnit migration suggested for non-source file: {file_path}")
                return False
            
            # Verify test-related content exists
            test_indicators = ['@test', 'test', '@before', '@after', '@runwith']
            if not any(indicator in content.lower() for indicator in test_indicators):
                print(f"     🚨 LOGIC ERROR: JUnit migration suggested for non-test file: {file_path}")
                return False
            
            # Validate JUnit 4→5 specific patterns
            junit4_to_5_mappings = {
                '@before': '@beforeeach',
                '@after': '@aftereach', 
                '@beforeclass': '@beforeall',
                '@afterclass': '@afterall',
                '@ignore': '@disabled',
                '@runwith': '@extendwith'
            }
            
            if from_value.lower() in junit4_to_5_mappings:
                expected_to = junit4_to_5_mappings[from_value.lower()]
                if to_value.lower() != expected_to:
                    print(f"     🚨 LOGIC ERROR: Invalid JUnit mapping '{from_value}' → '{to_value}', expected '{expected_to}'")
                    return False
        
        # **NEW: Rule 4: JPA/Hibernate validation**
        if change_type in ["jpa_migration", "hibernate_update"] or (category == "javax_to_jakarta" and "persistence" in from_value.lower()):
            if not file_path.endswith(('.java', '.kt')):
                print(f"     🚨 LOGIC ERROR: JPA change suggested for non-source file: {file_path}")
                return False
            
            # Verify JPA-related content exists
            jpa_indicators = ['@entity', '@table', '@column', '@id', 'import javax.persistence', 'persistence']
            if not any(indicator in content.lower() for indicator in jpa_indicators):
                print(f"     🚨 LOGIC ERROR: JPA change suggested for non-JPA file: {file_path}")
                return False
        
        # **NEW: Rule 5: Spring Security specific validation**
        if category == "spring_security_updates":
            # Security config changes should be in config classes or security-related files
            security_indicators = ['security', 'config', 'auth', '@configuration', '@enablewebsecurity', 'websecurityconfigureradapter']
            file_has_security = (any(indicator in file_path.lower() for indicator in ['security', 'config', 'auth']) or 
                               any(indicator in content.lower() for indicator in security_indicators))
            
            if not file_has_security:
                print(f"     🚨 LOGIC ERROR: Spring Security change suggested for non-security file: {file_path}")
                return False
            
            # Validate WebSecurityConfigurerAdapter replacement
            if change_type == "websecurity_adapter_replacement":
                if "websecurityconfigureradapter" not in content.lower():
                    print(f"     🚨 LOGIC ERROR: WebSecurityConfigurerAdapter replacement suggested but class not found in {file_path}")
                    return False
        
        # **Rule 6: Check for nonsensical version patterns**
        if from_value and to_value:
            # Check if "from" and "to" values make sense
            if from_value == to_value:
                print(f"     🚨 LOGIC ERROR: Identical from/to values: {from_value} in {file_path}")
                return False
            
            # Check for realistic version patterns
            if any(keyword in change_type.lower() for keyword in ["version", "spring", "boot", "junit", "mockito"]):
                import re
                version_pattern = r'^\d+\.\d+'
                if from_value and not re.match(version_pattern, from_value) and not from_value.endswith('.RELEASE'):
                    if not any(from_value in content for content in [content]):  # Quick content check
                        print(f"     🚨 LOGIC ERROR: Invalid version format '{from_value}' in {file_path}")
                        return False
        
        # **Rule 7: Validate change category consistency**
        if category == "javax_to_jakarta" and not from_value.startswith("javax."):
            print(f"     🚨 LOGIC ERROR: javax_to_jakarta category but from_value is '{from_value}' in {file_path}")
            return False
        
        if category == "dependency_updates" and change_type == "import_replacement":
            print(f"     🚨 LOGIC ERROR: Import replacement in dependency_updates category for {file_path}")
            return False
        
        # **Rule 8: Validate file path consistency**
        change_file = change.get("file", "")
        if change_file and change_file != file_path:
            print(f"     🚨 LOGIC ERROR: Change file path '{change_file}' doesn't match actual file '{file_path}'")
            return False
        
        return True
    
    def _save_debug_response(self, file_path, response):
        """Save problematic LLM responses for debugging."""
        try:
            import os
            debug_dir = "./debug_responses"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Clean filename for filesystem
            safe_filename = file_path.replace("/", "_").replace("\\", "_").replace(".", "_")
            debug_file = os.path.join(debug_dir, f"{safe_filename}_response.txt")
            
            with open(debug_file, 'w', encoding='utf-8') as f:
                f.write(f"File: {file_path}\n")
                f.write(f"Response Length: {len(response)}\n")
                f.write("="*50 + "\n")
                f.write(response)
            
            print(f"     💾 Debug response saved to: {debug_file}")
        except Exception as e:
            print(f"     Warning: Could not save debug response: {e}")
    
    def _should_skip_file(self, file_path):
        """Check if file should be skipped for migration analysis."""
        # Skip certain file types that are unlikely to need Spring migration changes
        skip_extensions = {'.md', '.txt', '.log', '.json', '.csv', '.sql', '.sh', '.bat', '.png', '.jpg', '.gif'}
        skip_patterns = {
            'readme', 'changelog', 'license', 
            'docker', 'target/', 'build/', 'node_modules/', '.git/', '.idea/'
        }
        
        # Check extension
        file_lower = file_path.lower()
        if any(file_lower.endswith(ext) for ext in skip_extensions):
            return True
        
        # Check patterns (using more specific patterns to avoid false positives)
        if any(pattern in file_lower for pattern in skip_patterns):
            return True
        
        # Skip large non-Java files (properties files with many entries)
        if file_path.endswith('.properties') and len(file_path.split('/')) > 4:
            # Skip deeply nested properties files which are likely translations/configs
            return True
        
        return False
    
    def _get_file_type(self, file_path):
        """Get a simple description of file type for LLM context."""
        file_lower = file_path.lower()
        
        # Check if it's a test file
        if ('/test/' in file_lower or 
            file_lower.endswith('test.java') or 
            file_lower.endswith('tests.java') or
            'test' in os.path.basename(file_lower)):
            return "Java test file"
        elif file_path.endswith('.java'):
            return "Java source file"
        elif file_path.endswith('.xml'):
            return "XML configuration file"
        elif file_path.endswith('.properties'):
            return "Properties configuration file"
        elif file_path.endswith(('.yml', '.yaml')):
            return "YAML configuration file"
        elif file_path.endswith(('.gradle', '.gradle.kts')):
            return "Gradle build file"
        elif file_path.endswith('pom.xml'):
            return "Maven POM file"
        else:
            return "Configuration file"
    
    def _prepare_file_content_for_llm(self, content, file_path):
        """Prepare file content for LLM analysis by cleaning and limiting size."""
        # Limit content size for LLM
        max_content_length = 5000
        
        if len(content) > max_content_length:
            # For Java files, try to keep imports and class declarations
            if file_path.endswith('.java'):
                lines = content.split('\n')
                imports = [line for line in lines[:50] if line.strip().startswith('import') or line.strip().startswith('package')]
                class_lines = [line for line in lines if any(keyword in line for keyword in ['class ', 'interface ', '@', 'public ', 'private ', 'protected '])]
                
                # Combine imports + key class lines + truncation notice
                key_content = '\n'.join(imports[:20] + class_lines[:30])
                content = key_content + f"\n\n... [File truncated - original length: {len(content)} chars] ..."
            else:
                # For other files, just truncate with notice
                content = content[:max_content_length] + f"\n\n... [File truncated - original length: {len(content)} chars] ..."
        
        # Clean content for JSON safety
        # Remove or escape problematic characters
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # For properties files, limit to first few lines to avoid parsing issues
        if file_path.endswith('.properties'):
            lines = content.split('\n')
            if len(lines) > 50:
                content = '\n'.join(lines[:50]) + f"\n\n... [Properties file truncated - {len(lines)} total lines] ..."
        
        return content
    
    def _extract_and_clean_json(self, response, file_path):
        """Extract and clean JSON from LLM response with enhanced error handling."""
        try:
            # Clean the response
            response = response.strip()
            
            if not response:
                print(f"     Empty response from LLM for {file_path}")
                return None
            
            json_str = None
            
            # Method 1: Try to find JSON block in markdown format
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
                if json_str:
                    print(f"     Found JSON in markdown block for {file_path}")
                
            # Method 2: Check if entire response is JSON
            elif response.startswith("{") and response.endswith("}"):
                json_str = response
                print(f"     Using entire response as JSON for {file_path}")
                
            # Method 3: Try to find JSON-like content with regex
            else:
                import re
                # Look for JSON objects that might have text before/after
                json_patterns = [
                    r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # Simple nested JSON
                    r'\{(?:[^{}]|\\.|\"[^\"]*\")*\}',     # JSON with escaped quotes
                    r'\{.*?\}(?=\s*(?:\n|$))',           # JSON ending at line boundary
                    r'\{.*?\}(?=\s*[^\w])',              # JSON followed by non-word chars
                ]
                
                for pattern in json_patterns:
                    json_match = re.search(pattern, response, re.DOTALL)
                    if json_match:
                        potential_json = json_match.group(0)
                        # Quick validation - try to count braces
                        if potential_json.count('{') == potential_json.count('}'):
                            json_str = potential_json
                            print(f"     Found JSON with pattern match for {file_path}")
                            break
                
            if not json_str:
                print(f"     No JSON structure found in response for {file_path}")
                print(f"     Response preview: {response[:200]}...")
                return None
            
            # Clean up JSON string
            json_str = json_str.strip()
            
            # Remove any trailing incomplete content (commas, etc.)
            json_str = json_str.rstrip(',\n\r\t ')
            
            # Advanced JSON cleaning
            json_str = self._advanced_json_cleaning(json_str, file_path)
            
            if not json_str:
                print(f"     JSON cleaning failed for {file_path}")
                return None
            
            # Test parse to validate
            try:
                test_parse = json.loads(json_str)
                print(f"     Successfully parsed JSON for {file_path}")
                return json_str
            except json.JSONDecodeError as e:
                print(f"     JSON validation failed for {file_path}: {e}")
                
                # Try to fix common JSON issues
                fixed_json = self._attempt_json_repair(json_str, file_path)
                if fixed_json:
                    try:
                        json.loads(fixed_json)
                        print(f"     Successfully repaired JSON for {file_path}")
                        return fixed_json
                    except:
                        pass
                
                print(f"     Could not repair JSON for {file_path}")
                print(f"     JSON preview: {json_str[:200]}...")
                return None
            
        except Exception as e:
            print(f"     JSON extraction error for {file_path}: {e}")
            return None
    
    def _advanced_json_cleaning(self, json_str, file_path):
        """Advanced JSON cleaning with multiple repair strategies."""
        try:
            # Remove common problematic patterns
            import re
            
            # 1. Fix unescaped quotes in strings - much simpler approach
            lines = json_str.split('\n')
            cleaned_lines = []
            
            for line in lines:
                # Skip empty lines
                if not line.strip():
                    cleaned_lines.append(line)
                    continue
                
                # Only process lines that look like JSON key-value pairs
                if ':' in line and '"' in line:
                    # Look for pattern: "key": "value with "internal quotes""
                    # We need to be careful not to escape the structural quotes
                    
                    # Find the colon that separates key from value
                    colon_pos = line.find(':')
                    if colon_pos > 0:
                        key_part = line[:colon_pos + 1]
                        value_part = line[colon_pos + 1:].strip()
                        
                        # Only fix if we have a string value (starts with quote)
                        if value_part.startswith('"'):
                            # More careful approach: find matching closing quote
                            # Look for the pattern: "text with "quotes" inside",
                            if value_part.count('"') > 2:  # More than just opening and closing
                                # Use regex to find and fix only internal quotes
                                # Pattern: "anything with "quotes" inside"
                                import re
                                # This pattern captures: "start_text "quoted_text" end_text"
                                pattern = r'^"([^"]*)"([^"]*)"([^"]*)"(.*)$'
                                match = re.match(pattern, value_part)
                                if match:
                                    start, quoted, end, suffix = match.groups()
                                    # Reconstruct with escaped internal quotes
                                    fixed_value = f'"{start}\\"{quoted}\\"{end}"{suffix}'
                                    line = key_part + ' ' + fixed_value
                
                cleaned_lines.append(line)
            
            cleaned_json = '\n'.join(cleaned_lines)
            
            # 2. Balance brackets and braces
            open_braces = cleaned_json.count('{')
            close_braces = cleaned_json.count('}')
            open_brackets = cleaned_json.count('[')
            close_brackets = cleaned_json.count(']')
            
            if open_braces > close_braces:
                cleaned_json += '}' * (open_braces - close_braces)
            elif close_braces > open_braces:
                # Remove extra closing braces from the end
                extra_braces = close_braces - open_braces
                for _ in range(extra_braces):
                    last_brace = cleaned_json.rfind('}')
                    if last_brace != -1:
                        cleaned_json = cleaned_json[:last_brace] + cleaned_json[last_brace + 1:]
            
            if open_brackets > close_brackets:
                cleaned_json += ']' * (open_brackets - close_brackets)
            elif close_brackets > open_brackets:
                # Remove extra closing brackets from the end
                extra_brackets = close_brackets - open_brackets
                for _ in range(extra_brackets):
                    last_bracket = cleaned_json.rfind(']')
                    if last_bracket != -1:
                        cleaned_json = cleaned_json[:last_bracket] + cleaned_json[last_bracket + 1:]
            
            return cleaned_json
            
        except Exception as e:
            print(f"     Advanced JSON cleaning failed for {file_path}: {e}")
            return json_str
    
    def _attempt_json_repair(self, json_str, file_path):
        """Attempt to repair malformed JSON with specific strategies."""
        try:
            import re
            
            # Strategy 1: Remove trailing commas
            json_str = re.sub(r',(\s*[}\]])', r'\1', json_str)
            
            # Strategy 2: Fix missing commas between array/object elements
            json_str = re.sub(r'(\}|\])\s*(\{|\[)', r'\1,\2', json_str)
            
            # Strategy 3: Fix line breaks in string values
            json_str = re.sub(r'"\s*\n\s*"', r'" "', json_str)
            
            # Strategy 4: Remove comments (if any)
            json_str = re.sub(r'//.*$', '', json_str, flags=re.MULTILINE)
            json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)
            
            # Strategy 5: Fix common typos in JSON structure
            json_str = json_str.replace('}{', '},{')  # Missing comma between objects
            json_str = json_str.replace(']]', ']')     # Double closing brackets
            json_str = json_str.replace('}}', '}')     # Double closing braces
            
            # Strategy 6: More aggressive quote fixing
            # Replace problematic quote patterns
            json_str = re.sub(r'(["\s:])\s*"([^"]*)"([^"]*)"([^"]*?)"\s*([,}\]])', r'\1"\2\\"\3\\"\4"\5', json_str)
            
            # Strategy 7: Ensure proper string termination
            quote_count = json_str.count('"')
            if quote_count % 2 != 0:
                # Odd number of quotes - try to fix by adding a closing quote at the end
                if not json_str.rstrip().endswith('"'):
                    json_str = json_str.rstrip() + '"'
            
            # Strategy 8: Fix malformed object structures that break between matching braces
            # Try to handle cases where the JSON structure itself is broken
            if json_str.count('{') != json_str.count('}'):
                diff = json_str.count('{') - json_str.count('}')
                if diff > 0:
                    json_str += '}' * diff
            
            return json_str
            
        except Exception:
            return None
    
    def _is_text_file(self, file_path, content):
        """Check if a file appears to be a text file suitable for analysis."""
        # Use the same logic as RobustFileReader for consistency
        try:
            # Check for null bytes (common in binary files)
            if b'\x00' in content.encode('utf-8', errors='ignore'):
                return False
                
            # Check for high ratio of non-printable characters
            if len(content) > 0:
                printable_chars = sum(1 for char in content if char.isprintable() or char in ['\n', '\r', '\t'])
                printable_ratio = printable_chars / len(content)
                
                # If less than 70% printable characters, likely binary
                if printable_ratio < 0.7:
                    return False
            
            return True
            
        except Exception:
            return False  # Assume binary if we can't analyze it
    
    def _create_analysis_context(self, analysis):
        """Create a concise analysis context for file-level LLM analysis."""
        try:
            if not isinstance(analysis, dict):
                return "Analysis data unavailable - using file-level analysis only"
            
            # Extract key findings from the overall analysis
            context_parts = []
            
            # Executive summary
            executive_summary = analysis.get("executive_summary", {})
            if executive_summary:
                context_parts.append(f"Migration Impact: {executive_summary.get('migration_impact', 'Unknown')}")
                key_blockers = executive_summary.get('key_blockers', [])
                if key_blockers:
                    context_parts.append(f"Key Issues: {', '.join(key_blockers[:3])}")
            
            # Jakarta migration findings
            detailed_analysis = analysis.get("detailed_analysis", {})
            jakarta_migration = detailed_analysis.get("jakarta_migration", {})
            if jakarta_migration:
                javax_usages = jakarta_migration.get('javax_usages', [])
                if javax_usages:
                    context_parts.append(f"javax imports found: {len(javax_usages)} occurrences")
            
            # Security migration findings  
            security_migration = detailed_analysis.get("security_migration", {})
            if security_migration:
                websecurity_usage = security_migration.get('websecurity_adapter_usage', [])
                if websecurity_usage:
                    context_parts.append("Spring Security updates needed")
            
            # Build context string
            if context_parts:
                context = "Overall Migration Analysis Context:\n" + "\n".join(f"- {part}" for part in context_parts)
            else:
                context = "Limited analysis context available - performing file-level analysis"
            
            return context
            
        except Exception as e:
            return f"Analysis context error: {str(e)} - using file-level analysis only"
    
    def _get_empty_changes(self):
        """Return an empty changes structure when no changes are needed."""
        return {
            "javax_to_jakarta": [],
            "spring_security_updates": [],
            "dependency_updates": [],
            "configuration_updates": [],
            "other_changes": []
        }
    
    def _validate_change(self, change, file_path):
        """Validate that a change object has the required fields."""
        try:
            if not isinstance(change, dict):
                print(f"     Warning: Change for {file_path} is not a dictionary")
                return False
            
            # Required fields for all changes
            required_fields = ["file", "type", "description"]
            for field in required_fields:
                if field not in change:
                    print(f"     Warning: Change for {file_path} missing required field: {field}")
                    return False
            
            # Ensure file path is correct
            if change.get("file") != file_path:
                change["file"] = file_path  # Fix the file path
            
            # Add default values for optional fields
            if "automatic" not in change:
                change["automatic"] = False
            
            if "explanation" not in change:
                change["explanation"] = "Migration change required"
            
            if "line_numbers" not in change:
                change["line_numbers"] = []
            
            return True
            
        except Exception as e:
            print(f"     Warning: Error validating change for {file_path}: {e}")
            return False
    
    def _check_java_version_compatibility(self, content, file_path):
        """Check if the Java version meets Spring 6 requirements (Java 17+)."""
        import re
        
        java_version = None
        
        # Detect Java version in build files
        if file_path.endswith('pom.xml'):
            # Maven patterns
            java_patterns = [
                r'<java\.version>([^<]+)</java\.version>',
                r'<maven\.compiler\.source>([^<]+)</maven\.compiler\.source>',
                r'<source>([^<]+)</source>'
            ]
            
            for pattern in java_patterns:
                match = re.search(pattern, content)
                if match:
                    java_version = match.group(1).strip()
                    break
        
        elif file_path.endswith(('.gradle', '.gradle.kts')):
            # Gradle patterns
            java_patterns = [
                r'sourceCompatibility\s*=\s*[\'"]?(\d+)[\'"]?',
                r'toolchain.*?languageVersion.*?of\((\d+)\)'
            ]
            
            for pattern in java_patterns:
                match = re.search(pattern, content)
                if match:
                    java_version = match.group(1).strip()
                    break
        
        # Check if Java version is compatible with Spring 6
        if java_version:
            try:
                # Parse Java version (handle 1.8, 11, 17, etc.)
                if java_version.startswith("1."):
                    java_major = int(java_version.split(".")[1])
                else:
                    java_major = int(java_version.split(".")[0])
                
                # Spring 6 requires Java 17+
                if java_major < 17:
                    print(f"     🚨 Java {java_version} detected - Spring 6 requires Java 17+")
                    return {
                        "javax_to_jakarta": [],
                        "spring_security_updates": [],
                        "dependency_updates": [{
                            "file": file_path,
                            "type": "java_version_upgrade_required",
                            "from": f"Java {java_version}",
                            "to": "Java 17+",
                            "description": f"CRITICAL: Upgrade Java {java_version} to 17+ for Spring 6",
                            "automatic": False,
                            "explanation": "Spring 6 requires minimum Java 17"
                        }],
                        "configuration_updates": [],
                        "other_changes": []
                    }
                else:
                    print(f"     ✅ Java {java_version} is compatible with Spring 6")
            except (ValueError, IndexError):
                print(f"     ⚠️ Could not parse Java version: {java_version}")
        
        return None
    
    def _analyze_java_spring_compatibility(self, java_version, spring_version, file_path):
        """Analyze Java and Spring version compatibility for Spring 6 migration."""
        issues = []
        
        # Parse Java version
        java_major_version = None
        if java_version:
            try:
                # Handle versions like "11", "1.8", "17", "21"
                if java_version.startswith("1."):
                    # Java 1.8 = Java 8
                    java_major_version = int(java_version.split(".")[1])
                else:
                    java_major_version = int(java_version.split(".")[0])
            except (ValueError, IndexError):
                # Couldn't parse version
                pass
        
        # Parse Spring version
        spring_major_version = None
        if spring_version:
            try:
                if spring_version.startswith(("2.", "1.")):
                    spring_major_version = 2  # Spring Boot 2.x
                elif spring_version.startswith("3."):
                    spring_major_version = 3  # Spring Boot 3.x
            except:
                pass
        
        # Critical Issue: Java version too low for Spring 6
        if java_major_version and java_major_version < 17:
            issues.append({
                "file": file_path,
                "type": "java_version_upgrade_required",
                "from": f"Java {java_version}",
                "to": "Java 17+",
                "description": f"🚨 CRITICAL: Spring 6 requires Java 17+, found Java {java_version}",
                "automatic": False,
                "explanation": f"Spring 6 and Spring Boot 3.x require minimum Java 17. Current Java {java_version} is not supported.",
                "priority": "BLOCKING",
                "migration_impact": "HIGH"
            })
        
        # Issue: Currently on Spring Boot 2.x, needs upgrade
        if spring_major_version == 2:
            target_spring_version = "3.2.0"
            issues.append({
                "file": file_path,
                "type": "spring_boot_major_version_upgrade",
                "from": spring_version,
                "to": target_spring_version,
                "description": f"Spring Boot upgrade: {spring_version} → {target_spring_version}",
                "automatic": java_major_version and java_major_version >= 17,  # Only automatic if Java is compatible
                "explanation": f"Spring Boot 2.x → 3.x migration required for Spring 6 compatibility",
                "priority": "HIGH" if java_major_version and java_major_version >= 17 else "BLOCKED",
                "migration_impact": "HIGH"
            })
        
        # Warning: Unknown Java version
        if not java_version:
            issues.append({
                "file": file_path,
                "type": "java_version_detection_failed",
                "from": "Unknown Java version",
                "to": "Java 17+",
                "description": "⚠️ Could not detect Java version - manual verification required",
                "automatic": False,
                "explanation": "Unable to detect Java version from build file. Ensure Java 17+ before Spring 6 migration.",
                "priority": "MEDIUM",
                "migration_impact": "MEDIUM"
            })
        
        # Success: Compatible versions
        if java_major_version and java_major_version >= 17 and spring_major_version in [None, 2]:
            issues.append({
                "file": file_path,
                "type": "java_version_compatible",
                "from": f"Java {java_version}",
                "to": f"Java {java_version} (compatible)",
                "description": f"✅ Java {java_version} is compatible with Spring 6",
                "automatic": True,
                "explanation": f"Java {java_version} meets Spring 6 minimum requirements (Java 17+)",
                "priority": "INFO",
                "migration_impact": "LOW"
            })
        
        return issues

    def post(self, shared, prep_res, exec_res):
        """Store the generated changes and provide enhanced reporting."""
        shared["generated_changes"] = exec_res
        
        vlogger = get_verbose_logger()
        
        # Calculate accurate statistics (only count files with actual changes)
        total_changes = 0
        files_with_changes = set()
        change_by_category = {}
        
        for category, changes_list in exec_res.items():
            if changes_list:  # Only count non-empty categories
                change_by_category[category] = len(changes_list)
                total_changes += len(changes_list)
                
                # Track unique files in this category
                for change in changes_list:
                    if change.get('file'):
                        files_with_changes.add(change['file'])
        
        # Enhanced reporting
        print(f"\n📊 Migration Change Generation Summary:")
        if total_changes > 0:
            print(f"   ✅ Total changes identified: {total_changes}")
            print(f"   📁 Files requiring changes: {len(files_with_changes)}")
            print(f"   📋 Change breakdown:")
            
            for category, count in change_by_category.items():
                category_name = category.replace('_', ' ').title()
                print(f"      • {category_name}: {count} changes")
        else:
            print(f"   ℹ️  No migration changes needed - all files are already compatible!")
        
        if shared.get("verbose_mode"):
            vlogger.step(f"Generated {total_changes} changes across {len(files_with_changes)} files")
            for category, count in change_by_category.items():
                vlogger.debug(f"{category}: {count} changes")
        
        # Store enhanced summary
        shared["migration_changes_summary"] = {
            "total_changes": total_changes,
            "files_with_changes": len(files_with_changes),
            "changes_by_category": change_by_category
        }
        
        # Generate detailed line-by-line change report
        if total_changes > 0:
            line_report = self._generate_enhanced_line_change_report(exec_res)
            self._print_enhanced_line_change_summary(line_report)
            shared["line_change_report"] = line_report
        
        return "default"

    def _generate_enhanced_line_change_report(self, changes):
        """Generate enhanced line-by-line analysis of changes with file verification."""
        report = {
            "summary": {
                "total_files": 0,
                "total_changes": 0,
                "automatic_changes": 0,
                "manual_review_changes": 0
            },
            "by_category": {},
            "by_file": {}
        }
        
        files_processed = set()
        
        for category, changes_list in changes.items():
            if not changes_list:
                continue
                
            category_report = {
                "total_changes": len(changes_list),
                "files": set(),
                "automatic": 0,
                "manual": 0
            }
            
            for change in changes_list:
                file_path = change.get("file", "unknown")
                is_automatic = change.get("automatic", False)
                line_numbers = change.get("line_numbers", [])
                
                # Track file-level stats
                files_processed.add(file_path)
                category_report["files"].add(file_path)
                
                if is_automatic:
                    category_report["automatic"] += 1
                    report["summary"]["automatic_changes"] += 1
                else:
                    category_report["manual"] += 1  
                    report["summary"]["manual_review_changes"] += 1
                
                # Build per-file report
                if file_path not in report["by_file"]:
                    report["by_file"][file_path] = {
                        "changes": [],
                        "total_lines_affected": 0,
                        "categories": set()
                    }
                
                report["by_file"][file_path]["changes"].append({
                    "category": category,
                    "type": change.get("type", "unknown"),
                    "description": change.get("description", ""),
                    "line_numbers": line_numbers,
                    "automatic": is_automatic,
                    "from": change.get("from", ""),
                    "to": change.get("to", "")
                })
                
                report["by_file"][file_path]["total_lines_affected"] += len(line_numbers) if line_numbers else 1
                report["by_file"][file_path]["categories"].add(category)
            
            # Convert sets to counts for JSON serialization
            category_report["file_count"] = len(category_report["files"])
            del category_report["files"]  # Remove set for JSON compatibility
            report["by_category"][category] = category_report
        
        # Finalize summary
        report["summary"]["total_files"] = len(files_processed)
        report["summary"]["total_changes"] = sum(len(changes) for changes in changes.values() if changes)
        
        # Convert sets to lists for JSON compatibility
        for file_path, file_report in report["by_file"].items():
            file_report["categories"] = list(file_report["categories"])
        
        return report

    def _print_enhanced_line_change_summary(self, line_report):
        """Print enhanced summary of line changes with clear metrics."""
        print(f"\n📋 Detailed Change Analysis:")
        
        summary = line_report["summary"]
        print(f"   📁 Files to modify: {summary['total_files']}")
        print(f"   📝 Total changes: {summary['total_changes']}")
        print(f"   🤖 Automatic: {summary['automatic_changes']}")
        print(f"   👥 Manual review: {summary['manual_review_changes']}")
        
        # Show category breakdown
        if line_report["by_category"]:
            print(f"\n   📊 By Category:")
            for category, details in line_report["by_category"].items():
                category_name = category.replace('_', ' ').title()
                print(f"      • {category_name}: {details['total_changes']} changes in {details['file_count']} files")
        
        # Show files requiring changes
        if line_report["by_file"]:
            print(f"\n   📄 Files Requiring Changes:")
            
            # Sort files by number of changes
            sorted_files = sorted(
                line_report["by_file"].items(),
                key=lambda x: len(x[1]["changes"]),
                reverse=True
            )
            
            for file_path, file_info in sorted_files[:10]:  # Show top 10
                change_count = len(file_info["changes"])
                lines_affected = file_info["total_lines_affected"]
                categories = ", ".join(cat.replace('_', ' ').title() for cat in file_info["categories"])
                
                print(f"      📄 {file_path}")
                print(f"         📝 {change_count} changes, ~{lines_affected} lines affected")
                print(f"         🏷️  Categories: {categories}")
                
                # Show specific changes for this file
                for change in file_info["changes"][:3]:  # Show first 3 changes
                    change_type = change["type"].replace('_', ' ').title()
                    line_info = ""
                    if change["line_numbers"]:
                        line_info = f"lines {self._format_line_range(change['line_numbers'])}"
                    auto_marker = "🤖" if change["automatic"] else "👥"
                    print(f"         {auto_marker} {change_type}: {line_info}")
                
                if len(file_info["changes"]) > 3:
                    remaining = len(file_info["changes"]) - 3
                    print(f"         ... and {remaining} more changes")
            
            if len(sorted_files) > 10:
                remaining_files = len(sorted_files) - 10
                print(f"      ... and {remaining_files} more files")

    def _format_line_range(self, line_numbers):
        """Format line numbers into a readable range string."""
        if not line_numbers:
            return "unknown"
        
        if len(line_numbers) == 1:
            return str(line_numbers[0])
        
        # Sort and group consecutive numbers
        sorted_lines = sorted(set(line_numbers))
        if len(sorted_lines) <= 3:
            return ", ".join(map(str, sorted_lines))
        
        # For many lines, show range
        return f"{min(sorted_lines)}-{max(sorted_lines)} ({len(sorted_lines)} lines)"

    def _comprehensive_javax_scan(self, files_data, project_name):
        """
        Perform comprehensive scan for ALL javax imports and generate complete javax→jakarta changes.
        This catches any imports that the LLM might have missed.
        """
        vlogger = get_verbose_logger()
        vlogger.step("🔍 Performing comprehensive javax import scan")
        
        comprehensive_changes = {}
        javax_pattern = re.compile(r'import\s+(javax\.[a-zA-Z][a-zA-Z0-9_.]*)')
        
        # Comprehensive javax→jakarta mappings
        javax_to_jakarta_mappings = {
            # Core EE packages  
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
        
        total_javax_found = 0
        total_files_scanned = 0
        
        for file_path, file_data in files_data.items():
            if not file_path.endswith(('.java', '.kt')):
                continue
                
            content = file_data.get('content', '')
            if not content:
                continue
                
            total_files_scanned += 1
            javax_imports = javax_pattern.findall(content)
            
            if javax_imports:
                file_changes = []
                print(f"      📁 {file_path}: Found {len(javax_imports)} javax imports")
                
                for javax_import in javax_imports:
                    total_javax_found += 1
                    
                    # Find matching jakarta equivalent
                    jakarta_import = None
                    for javax_pkg, jakarta_pkg in javax_to_jakarta_mappings.items():
                        if javax_import.startswith(javax_pkg):
                            jakarta_import = javax_import.replace(javax_pkg, jakarta_pkg, 1)
                            break
                    
                    if jakarta_import:
                        change = {
                            "type": "javax_to_jakarta_import", 
                            "file": file_path,
                            "from": javax_import,
                            "to": jakarta_import,
                            "line_number": self._find_import_line_number(content, javax_import),
                            "description": f"Migrate {javax_import} to {jakarta_import}",
                            "automatic": True,  # These are safe automatic changes
                            "confidence": "high"
                        }
                        file_changes.append(change)
                        print(f"        ✅ {javax_import} → {jakarta_import}")
                    else:
                        print(f"        ⚠️  No mapping found for {javax_import}")
                
                if file_changes:
                    comprehensive_changes[file_path] = {
                        "javax_to_jakarta": file_changes
                    }
        
        print(f"      📊 Comprehensive scan results:")
        print(f"         • Files scanned: {total_files_scanned}")
        print(f"         • Total javax imports found: {total_javax_found}")
        print(f"         • Files with javax imports: {len(comprehensive_changes)}")
        
        return comprehensive_changes
    
    def _find_import_line_number(self, content, import_statement):
        """Find the line number of an import statement."""
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            if f"import {import_statement}" in line:
                return i
        return None


class MigrationFileApplicator(Node):
    """
    Actually applies the generated migration changes to files in the migration workspace.
    This node takes the changes generated by MigrationChangeGenerator and applies them to the actual files.
    """
    
    def prep(self, shared):
        vlogger = get_verbose_logger()
        
        if shared.get("verbose_mode"):
            vlogger.step("Preparing migration file application")
        
        # Check if changes should be applied
        apply_changes = shared.get("apply_changes", False)
        if not apply_changes:
            if shared.get("verbose_mode"):
                vlogger.debug("apply_changes is False - skipping file modifications")
            print("⏭️  Skipping file modifications (use --apply-changes to enable)")
            return None, None, None
        
        generated_changes = shared.get("generated_changes", {})
        backup_info = shared.get("backup_info", {})
        project_name = shared["project_name"]
        
        if not generated_changes:
            if shared.get("verbose_mode"):
                vlogger.warning("No generated changes found to apply")
            print("⏭️  No generated changes found to apply")
            return None, None, None
        
        if not backup_info:
            if shared.get("verbose_mode"):
                vlogger.warning("No backup info found - cannot apply changes safely")
            print("❌ No backup info found - cannot apply changes safely")
            return None, None, None
        
        migration_workspace = backup_info.get("migration_workspace")
        if not migration_workspace or not os.path.exists(migration_workspace):
            if shared.get("verbose_mode"):
                vlogger.error(f"Migration workspace not found: {migration_workspace}")
            print(f"❌ Migration workspace not found: {migration_workspace}")
            return None, None, None
        
        if shared.get("verbose_mode"):
            vlogger.debug(f"Applying changes to workspace: {migration_workspace}")
            vlogger.debug(f"Change categories: {list(generated_changes.keys())}")
        
        return generated_changes, migration_workspace, project_name
    
    def exec(self, prep_res):
        if prep_res is None or prep_res[0] is None:
            return {"success": True, "skipped": True, "reason": "No changes to apply or changes disabled"}
        
        generated_changes, migration_workspace, project_name = prep_res
        vlogger = get_verbose_logger()
        
        monitor = get_performance_monitor()
        monitor.start_operation("apply_migration_changes")
        
        print(f"🔧 Applying migration changes to files in workspace...")
        print(f"📁 Workspace: {migration_workspace}")
        
        # Track application results
        results = {
            "successful": [],
            "skipped": [],
            "failed": [],
            "files_modified": set(),
            "total_changes_applied": 0
        }
        
        # **NEW: Force Spring Boot version updates in build files**
        self._force_spring_boot_updates(migration_workspace, results)
        
        # Process each category of changes
        for category, changes in generated_changes.items():
            if not isinstance(changes, list):
                continue
            
            print(f"\n📋 Processing {category.replace('_', ' ').title()}: {len(changes)} changes")
            
            for change in changes:
                if not isinstance(change, dict):
                    continue
                
                try:
                    result = self._apply_single_change(change, migration_workspace, category)
                    
                    if result["success"]:
                        results["successful"].append(result)
                        results["files_modified"].add(change.get("file", "unknown"))
                        results["total_changes_applied"] += 1
                        print(f"   ✅ {result['description']}")
                    elif result.get("skipped", False):
                        results["skipped"].append(result)
                        print(f"   ⏭️  {result['reason']}")
                    else:
                        results["failed"].append(result)
                        print(f"   ❌ {result['error']}")
                        
                except Exception as e:
                    error_result = {
                        "success": False,
                        "file": change.get("file", "unknown"),
                        "type": change.get("type", "unknown"),
                        "error": str(e)
                    }
                    results["failed"].append(error_result)
                    print(f"   ❌ Error applying change to {change.get('file', 'unknown')}: {e}")
        
        # Summary
        total_successful = len(results["successful"])
        total_skipped = len(results["skipped"])
        total_failed = len(results["failed"])
        files_modified = len(results["files_modified"])
        
        print(f"\n📊 Application Summary:")
        print(f"   ✅ Applied: {total_successful}")
        print(f"   ⏭️  Skipped: {total_skipped}")
        print(f"   ❌ Failed: {total_failed}")
        print(f"   📁 Files Modified: {files_modified}")
        
        monitor.end_operation("apply_migration_changes", 
                            files_processed=files_modified)
        
        results["success"] = total_successful > 0 or total_skipped > 0
        return results
    
    def _force_spring_boot_updates(self, migration_workspace, results):
        """Force Spring Boot version updates in build files regardless of LLM detection."""
        import os
        import re
        
        print(f"\n🔍 Checking for Spring Boot version updates...")
        
        # Find all build files
        build_files = []
        for root, dirs, files in os.walk(migration_workspace):
            for file in files:
                if file in ['pom.xml'] or file.endswith(('.gradle', '.gradle.kts')):
                    build_files.append(os.path.join(root, file))
        
        for build_file in build_files:
            relative_path = os.path.relpath(build_file, migration_workspace)
            
            try:
                with open(build_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Check for Spring Boot 2.x versions and update them
                if build_file.endswith('pom.xml'):
                    # Look for Spring Boot 2.x parent
                    if re.search(r'<version>2\.\d+\.\d+(?:\.RELEASE)?</version>', content):
                        # Update Spring Boot parent version
                        content = re.sub(
                            r'(<parent>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-parent</artifactId>\s*<version>)2\.\d+\.\d+(?:\.RELEASE)?(</version>)',
                            r'\g<1>3.2.0\g<2>',
                            content,
                            flags=re.DOTALL
                        )
                        
                        if content != original_content:
                            with open(build_file, 'w', encoding='utf-8') as f:
                                f.write(content)
                            
                            results["successful"].append({
                                "success": True,
                                "file": relative_path,
                                "type": "spring_boot_version_update",
                                "description": f"Force updated Spring Boot version in {relative_path}"
                            })
                            results["files_modified"].add(relative_path)
                            results["total_changes_applied"] += 1
                            print(f"   🔄 Force updated Spring Boot version in {relative_path}")
                
            except Exception as e:
                print(f"   ⚠️  Error checking {relative_path}: {e}")
                continue
    
    def _apply_single_change(self, change, migration_workspace, category):
        """Apply a single change to a file."""
        file_path = change.get("file", "")
        change_type = change.get("type", "")
        automatic = change.get("automatic", False)
        
        if not file_path:
            return {"success": False, "error": "No file path specified"}
 
        can_apply_automatically = (
            automatic or  # Original automatic flag
            # javax→jakarta import replacements are generally safe
            (category == "javax_to_jakarta" and change_type == "import_replacement") or
            # Spring Boot version updates are safe
            (category == "dependency_updates" and "spring" in change_type.lower()) or
            # Simple configuration property updates
            (category == "configuration_updates" and change_type in ["property_update", "update"])
        )
        
        if not can_apply_automatically:
            return {
                "success": False,
                "skipped": True,
                "file": file_path,
                "type": change_type,
                "reason": f"Manual review required for {category}/{change_type} - not applied automatically"
            }
        
        full_file_path = os.path.join(migration_workspace, file_path)
        
        if not os.path.exists(full_file_path):
            return {
                "success": False,
                "file": file_path,
                "type": change_type,
                "error": f"File not found in workspace: {full_file_path}"
            }
        
        try:
            # Read the file
            with open(full_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            original_lines = len(original_content.split('\n'))
            
            # **NEW: Try Spring Boot version update first for dependency changes**
            if category == "dependency_updates" and ("spring" in change_type.lower() or "boot" in change_type.lower()):
                content, updated = self._apply_spring_boot_version_update(content, file_path)
                if not updated:
                    # Fall back to generic dependency change
                    content = self._apply_dependency_change(content, change)
            elif category == "javax_to_jakarta":
                content = self._apply_javax_to_jakarta_change(content, change)
            elif category == "dependency_updates":
                content = self._apply_dependency_change(content, change)
            elif category == "configuration_updates":
                content = self._apply_configuration_change(content, change)
            else:
                # Generic replacement for other types
                content = self._apply_generic_change(content, change)
            
            # Check if content actually changed
            if content == original_content:
                return {
                    "success": False,
                    "skipped": True,
                    "file": file_path,
                    "type": change_type,
                    "reason": "No changes needed - content already correct"
                }
            
            # Write the modified content back
            with open(full_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Calculate lines changed (approximate)
            new_lines = len(content.split('\n'))
            lines_changed = abs(new_lines - original_lines)
            
            return {
                "success": True,
                "file": file_path,
                "type": change_type,
                "description": f"Applied {change_type} in {file_path}",
                "lines_changed": lines_changed
            }
            
        except Exception as e:
            return {
                "success": False,
                "file": file_path,
                "type": change_type,
                "error": f"Error modifying file: {str(e)}"
            }
    
    def _apply_javax_to_jakarta_change(self, content, change):
        """Apply javax to jakarta import changes with comprehensive mapping."""
        from_import = change.get("from", "")
        to_import = change.get("to", "")
        
        if not from_import or not to_import:
            print(f"      ❌ Missing from/to values in change: {change}")
            return content, False

        # **CRITICAL: Only allow javax.* imports**
        if not from_import.startswith("javax."):
            print(f"      🚨 BLOCKED: Attempted to change non-javax import '{from_import}' - this would corrupt custom code!")
            return content, False
        
        # **NEW: Comprehensive javax→jakarta mapping validation**
        javax_to_jakarta_mappings = {
            # Core EE packages
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
            # Batch processing
            "javax.batch": "jakarta.batch",
            # Concurrency utilities  
            "javax.enterprise.concurrent": "jakarta.enterprise.concurrent",
            # Authentication
            "javax.security.jacc": "jakarta.security.jacc",
        }
        
        # Validate the mapping
        found_valid_mapping = False
        for javax_pkg, jakarta_pkg in javax_to_jakarta_mappings.items():
            if from_import.startswith(javax_pkg):
                expected_to = from_import.replace(javax_pkg, jakarta_pkg, 1)
                if to_import != expected_to:
                    print(f"      🚨 INCORRECT MAPPING: '{from_import}' → '{to_import}', expected '{expected_to}'")
                    return content, False
                found_valid_mapping = True
                break
        
        if not found_valid_mapping:
            print(f"      ⚠️  UNMAPPED javax package: '{from_import}' - please verify this is correct")
        
        # **ENHANCED: More precise import replacement**
        import re
        
        # Pattern 1: Standard import statement
        import_pattern = rf'^(\s*import\s+){re.escape(from_import)}(\s*;.*?)$'
        if re.search(import_pattern, content, re.MULTILINE):
            new_content = re.sub(import_pattern, rf'\g<1>{to_import}\g<2>', content, flags=re.MULTILINE)
            if new_content != content:
                print(f"      ✅ Updated import: {from_import} → {to_import}")
                return new_content, True
        
        # Pattern 2: Static import
        static_import_pattern = rf'^(\s*import\s+static\s+){re.escape(from_import)}(\.[^;]+\s*;.*?)$'  
        if re.search(static_import_pattern, content, re.MULTILINE):
            new_content = re.sub(static_import_pattern, rf'\g<1>{to_import}\g<2>', content, flags=re.MULTILINE)
            if new_content != content:
                print(f"      ✅ Updated static import: {from_import} → {to_import}")
                return new_content, True
                
        # Pattern 3: Wildcard import  
        wildcard_pattern = rf'^(\s*import\s+){re.escape(from_import)}(\.\*\s*;.*?)$'
        if re.search(wildcard_pattern, content, re.MULTILINE):
            new_content = re.sub(wildcard_pattern, rf'\g<1>{to_import}\g<2>', content, flags=re.MULTILINE)
            if new_content != content:
                print(f"      ✅ Updated wildcard import: {from_import}.* → {to_import}.*")
                return new_content, True

        print(f"      ⚠️  Import not found in content: {from_import}")
        return content, False
    
    def _apply_dependency_change(self, content, change):
        """Apply dependency version updates in build files."""
        import re
        
        from_version = change.get("from", "")
        to_version = change.get("to", "")
        description = change.get("description", "").lower()
        
        # Enhanced Spring Boot version update for Maven
        if "spring" in description and "boot" in description:
            # Handle Spring Boot parent version update
            spring_boot_pattern = r'(<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-parent</artifactId>\s*<version>)[^<]+(</version>)'
            if re.search(spring_boot_pattern, content):
                # Update to Spring Boot 3.x
                content = re.sub(spring_boot_pattern, r'\g<1>3.2.0\g<2>', content)
                print(f"      📦 Updated Spring Boot parent to 3.2.0")
                return content
        
        # Handle specific version replacements
        if from_version and to_version:
            # Direct version replacement
            content = content.replace(from_version, to_version)
            
            # Handle Maven version properties
            if "<version>" in from_version:
                content = content.replace(from_version, to_version)
            else:
                # Handle version numbers without tags
                version_pattern = rf'<version>{re.escape(from_version)}</version>'
                replacement = f'<version>{to_version}</version>'
                content = re.sub(version_pattern, replacement, content)
        
        # Generic Spring dependency updates
        if "spring" in description:
            # Update common Spring dependencies to compatible versions
            spring_updates = {
                r'<spring\.version>[^<]+</spring\.version>': '<spring.version>6.0.0</spring.version>',
                r'<spring-boot\.version>[^<]+</spring-boot\.version>': '<spring-boot.version>3.2.0</spring-boot.version>',
                r'<spring-security\.version>[^<]+</spring-security\.version>': '<spring-security.version>6.2.0</spring-security.version>',
            }
            
            for pattern, replacement in spring_updates.items():
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    print(f"      📦 Updated dependency version pattern")
        
        return content
    
    def _apply_configuration_change(self, content, change):
        """Apply configuration property changes."""
        from_prop = change.get("from", "")
        to_prop = change.get("to", "")
        
        if from_prop and to_prop:
            # For properties files
            if from_prop.endswith("="):
                content = content.replace(from_prop, to_prop)
            else:
                # For YAML/properties without =
                content = content.replace(from_prop, to_prop)
        
        return content
    
    def _apply_generic_change(self, content, change):
        """Apply generic string replacements."""
        from_text = change.get("from", "")
        to_text = change.get("to", "")
        
        if from_text and to_text:
            content = content.replace(from_text, to_text)
        
        return content
    
    def _apply_spring_boot_version_update(self, content, file_path):
        """Specifically handle Spring Boot version updates in pom.xml and build.gradle files."""
        import re
        
        updated = False
        
        if file_path.endswith('pom.xml'):
            original_content = content
            
            # Maven Spring Boot parent update
            spring_boot_parent_pattern = r'(<parent>\s*<groupId>org\.springframework\.boot</groupId>\s*<artifactId>spring-boot-starter-parent</artifactId>\s*<version>)[^<]+(</version>)'
            if re.search(spring_boot_parent_pattern, content, re.DOTALL):
                content = re.sub(spring_boot_parent_pattern, r'\g<1>3.2.0\g<2>', content, flags=re.DOTALL)
                print(f"      🔄 Updated Spring Boot parent version to 3.2.0 in {file_path}")
                updated = True
            
            # **NEW: Update Java version for Spring 6 compatibility**
            java_version_pattern = r'(<java\.version>)[^<]+(</java\.version>)'
            if re.search(java_version_pattern, content):
                # Check if current version is less than 17
                java_version_match = re.search(r'<java\.version>([^<]+)</java\.version>', content)
                if java_version_match:
                    current_version = java_version_match.group(1).strip()
                    try:
                        if current_version.startswith("1."):
                            current_major = int(current_version.split(".")[1])
                        else:
                            current_major = int(current_version.split(".")[0])
                        
                        if current_major < 17:
                            content = re.sub(java_version_pattern, r'\g<1>17\g<2>', content)
                            print(f"      🔄 Updated Java version from {current_version} to 17 in {file_path}")
                            updated = True
                    except (ValueError, IndexError):
                        # If we can't parse the version, update it anyway for safety
                        content = re.sub(java_version_pattern, r'\g<1>17\g<2>', content)
                        print(f"      🔄 Updated Java version (unparseable: {current_version}) to 17 in {file_path}")
                        updated = True
            
            # **NEW: Update Spring Cloud version for Spring Boot 3.x compatibility**
            spring_cloud_pattern = r'(<spring-cloud\.version>)[^<]+(</spring-cloud\.version>)'
            if re.search(spring_cloud_pattern, content):
                spring_cloud_match = re.search(r'<spring-cloud\.version>([^<]+)</spring-cloud\.version>', content)
                if spring_cloud_match:
                    current_cloud_version = spring_cloud_match.group(1).strip()
                    # Old versions like Finchley.RELEASE, Greenwich.RELEASE need updating
                    old_versions = ['finchley', 'greenwich', 'hoxton', 'edgware', '2020.', '2021.', '2022.']
                    if any(old_version in current_cloud_version.lower() for old_version in old_versions):
                        content = re.sub(spring_cloud_pattern, r'\g<1>2023.0.0\g<2>', content)
                        print(f"      🔄 Updated Spring Cloud version from {current_cloud_version} to 2023.0.0 in {file_path}")
                        updated = True
            
            # **NEW: Update JUnit version for Spring 6 compatibility**
            junit_version_pattern = r'(<junit\.version>)[^<]+(</junit\.version>)'
            if re.search(junit_version_pattern, content):
                junit_match = re.search(r'<junit\.version>([^<]+)</junit\.version>', content)
                if junit_match:
                    current_junit_version = junit_match.group(1).strip()
                    # JUnit 4.x needs updating to 5.x
                    if current_junit_version.startswith('4.'):
                        content = re.sub(junit_version_pattern, r'\g<1>5.10.0\g<2>', content)
                        print(f"      🔄 Updated JUnit version from {current_junit_version} to 5.10.0 in {file_path}")
                        updated = True
            
            # **NEW: Update Mockito version for Spring 6 compatibility**
            mockito_version_pattern = r'(<mockito\.version>)[^<]+(</mockito\.version>)'
            if re.search(mockito_version_pattern, content):
                mockito_match = re.search(r'<mockito\.version>([^<]+)</mockito\.version>', content)
                if mockito_match:
                    current_mockito_version = mockito_match.group(1).strip()
                    # Older Mockito versions may have compatibility issues
                    version_parts = current_mockito_version.split('.')
                    if len(version_parts) >= 1 and int(version_parts[0]) < 4:
                        content = re.sub(mockito_version_pattern, r'\g<1>5.5.0\g<2>', content)
                        print(f"      🔄 Updated Mockito version from {current_mockito_version} to 5.5.0 in {file_path}")
                        updated = True
            
            # **NEW: Add missing dependency versions if Spring Boot 3.x parent is detected**
            if '<version>3.' in content and '<parent>' in content:
                # Add JUnit 5 version if missing
                if '<junit.version>' not in content and '<junit-jupiter.version>' not in content:
                    properties_pattern = r'(<properties>.*?)(</properties>)'
                    if re.search(properties_pattern, content, re.DOTALL):
                        properties_replacement = r'\g<1>\t\t<junit-jupiter.version>5.10.0</junit-jupiter.version>\n\t\g<2>'
                        content = re.sub(properties_pattern, properties_replacement, content, flags=re.DOTALL)
                        print(f"      ➕ Added JUnit Jupiter version 5.10.0 to {file_path}")
                        updated = True
        
        elif file_path.endswith(('.gradle', '.gradle.kts')):
            # Gradle Spring Boot plugin update
            gradle_plugin_pattern = r"(id\s+['\"]org\.springframework\.boot['\"]?\s+version\s+['\"])[^'\"]+(['\"])"
            if re.search(gradle_plugin_pattern, content):
                content = re.sub(gradle_plugin_pattern, r'\g<1>3.2.0\g<2>', content)
                print(f"      🔄 Updated Spring Boot plugin to 3.2.0 in {file_path}")
                updated = True
            
            # **NEW: Kotlin DSL style plugin update**
            kotlin_plugin_pattern = r'(id\s*\(\s*["\']org\.springframework\.boot["\']\s*\)\s+version\s+["\'])[^"\']+(["\'])'
            if re.search(kotlin_plugin_pattern, content):
                content = re.sub(kotlin_plugin_pattern, r'\g<1>3.2.0\g<2>', content)
                print(f"      🔄 Updated Spring Boot plugin (Kotlin DSL) to 3.2.0 in {file_path}")
                updated = True
            
            # **NEW: Update Java version in Gradle**
            gradle_java_pattern = r"(sourceCompatibility\s*=\s*['\"]?)(\d+)['\"]?"
            if re.search(gradle_java_pattern, content):
                java_match = re.search(r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?", content)
                if java_match:
                    current_java = int(java_match.group(1))
                    if current_java < 17:
                        content = re.sub(gradle_java_pattern, r'\g<1>17\g<2>', content)
                        print(f"      🔄 Updated Gradle Java sourceCompatibility to 17 in {file_path}")
                        updated = True
            
            # **NEW: Kotlin DSL Java version**
            kotlin_java_pattern = r'(java\s*\{\s*sourceCompatibility\s*=\s*JavaVersion\.VERSION_)(\d+)(\s*\})'
            if re.search(kotlin_java_pattern, content):
                java_match = re.search(r'java\s*\{\s*sourceCompatibility\s*=\s*JavaVersion\.VERSION_(\d+)', content)
                if java_match:
                    current_java = int(java_match.group(1))
                    if current_java < 17:
                        content = re.sub(kotlin_java_pattern, r'\g<1>17\g<3>', content)
                        print(f"      🔄 Updated Kotlin DSL Java sourceCompatibility to 17 in {file_path}")
                        updated = True
            
            # **NEW: Update JUnit version in Gradle**
            gradle_junit_pattern = r'(testImplementation\s+["\']org\.junit\.jupiter:junit-jupiter:)[^"\']+(["\'])'
            if re.search(gradle_junit_pattern, content):
                content = re.sub(gradle_junit_pattern, r'\g<1>5.10.0\g<2>', content)
                print(f"      🔄 Updated JUnit Jupiter to 5.10.0 in {file_path}")
                updated = True
            
            # **NEW: Update Mockito version in Gradle**
            gradle_mockito_pattern = r'(testImplementation\s+["\']org\.mockito:mockito-core:)[^"\']+(["\'])'
            if re.search(gradle_mockito_pattern, content):
                content = re.sub(gradle_mockito_pattern, r'\g<1>5.5.0\g<2>', content)
                print(f"      🔄 Updated Mockito to 5.5.0 in {file_path}")
                updated = True
            
            # **NEW: Spring Cloud BOM update in Gradle**
            gradle_spring_cloud_pattern = r'(implementation\s+platform\s*\(["\']org\.springframework\.cloud:spring-cloud-dependencies:)[^"\']+(["\'])'
            if re.search(gradle_spring_cloud_pattern, content):
                content = re.sub(gradle_spring_cloud_pattern, r'\g<1>2023.0.0\g<2>', content)
                print(f"      🔄 Updated Spring Cloud BOM to 2023.0.0 in {file_path}")
                updated = True
            
            # Gradle dependency version
            gradle_dep_pattern = r"(implementation\s+['\"]org\.springframework\.boot:spring-boot-.*?:)[^'\"]+(['\"])"
            if re.search(gradle_dep_pattern, content):
                content = re.sub(gradle_dep_pattern, r'\g<1>3.2.0\g<2>', content)
                print(f"      🔄 Updated Spring Boot dependencies to 3.2.0 in {file_path}")
                updated = True
        
        return content, updated
    
    def post(self, shared, prep_res, exec_res):
        """Store the application results and update shared state."""
        vlogger = get_verbose_logger()
        
        if exec_res.get("skipped", False):
            # Operation was skipped
            shared["applied_changes"] = {"skipped": True, "reason": exec_res.get("reason", "Unknown")}
            if shared.get("verbose_mode"):
                vlogger.debug(f"File application skipped: {exec_res.get('reason')}")
            return "default"
        
        if exec_res.get("success", False):
            shared["applied_changes"] = exec_res
            
            total_applied = exec_res.get("total_changes_applied", 0)
            files_modified = len(exec_res.get("files_modified", set()))
            
            if shared.get("verbose_mode"):
                vlogger.success(f"Migration changes applied: {total_applied} changes to {files_modified} files")
            
            print(f"✅ Successfully applied {total_applied} migration changes to {files_modified} files")
            
            # Show which files were modified
            if exec_res.get("files_modified"):
                print(f"\n📄 Files Modified:")
                for file_path in sorted(exec_res["files_modified"]):
                    print(f"   📝 {file_path}")
        else:
            if shared.get("verbose_mode"):
                vlogger.error("Failed to apply migration changes")
            print(f"❌ Failed to apply migration changes: {exec_res.get('error', 'Unknown error')}")
        
        return "default"


class MigrationReportGenerator(Node):
    """
    Generates and saves comprehensive migration reports to files in the migration workspace.
    Creates both JSON files for machine processing and markdown files for human readability.
    """
    
    def prep(self, shared):
        vlogger = get_verbose_logger()
        
        if shared.get("verbose_mode"):
            vlogger.step("Preparing migration report generation")
        
        # Collect all migration data from shared state
        migration_analysis = shared.get("migration_analysis", {})
        generated_changes = shared.get("generated_changes", {})
        migration_plan = shared.get("migration_plan", {})
        applied_changes = shared.get("applied_changes", {})
        backup_info = shared.get("backup_info", {})
        project_name = shared.get("project_name", "unknown_project")
        line_change_report = shared.get("line_change_report", {})
        migration_changes_summary = shared.get("migration_changes_summary", {})
        
        # Get migration workspace path
        migration_workspace = backup_info.get("migration_workspace")
        if not migration_workspace or not os.path.exists(migration_workspace):
            if shared.get("verbose_mode"):
                vlogger.warning("Migration workspace not found - will save reports to current directory")
            migration_workspace = f"./migration_reports_{project_name}"
            os.makedirs(migration_workspace, exist_ok=True)
        
        return {
            "migration_analysis": migration_analysis,
            "generated_changes": generated_changes,
            "migration_plan": migration_plan,
            "applied_changes": applied_changes,
            "backup_info": backup_info,
            "project_name": project_name,
            "migration_workspace": migration_workspace,
            "line_change_report": line_change_report,
            "migration_changes_summary": migration_changes_summary,
            "verbose_mode": shared.get("verbose_mode", False)
        }

    def exec(self, prep_res):
        import json
        from datetime import datetime
        
        vlogger = get_verbose_logger()
        
        print(f"📄 Generating comprehensive migration reports...")
        
        workspace = prep_res["migration_workspace"]
        project_name = prep_res["project_name"]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if prep_res["verbose_mode"]:
            vlogger.debug(f"Saving reports to: {workspace}")
        
        report_files = []
        
        try:
            # 1. Save migration analysis report
            analysis_file = os.path.join(workspace, "spring_migration_analysis.json")
            with open(analysis_file, 'w', encoding='utf-8') as f:
                json.dump(prep_res["migration_analysis"], f, indent=2, ensure_ascii=False)
            report_files.append(("Migration Analysis", analysis_file))
            print(f"   ✅ Saved migration analysis: spring_migration_analysis.json")
            
            # 2. Save detailed changes report
            changes_file = os.path.join(workspace, "migration_changes_detailed.json")
            with open(changes_file, 'w', encoding='utf-8') as f:
                json.dump(prep_res["generated_changes"], f, indent=2, ensure_ascii=False)
            report_files.append(("Detailed Changes", changes_file))
            print(f"   ✅ Saved detailed changes: migration_changes_detailed.json")
            
            # 3. Save migration plan
            plan_file = os.path.join(workspace, "migration_plan.json")
            with open(plan_file, 'w', encoding='utf-8') as f:
                json.dump(prep_res["migration_plan"], f, indent=2, ensure_ascii=False)
            report_files.append(("Migration Plan", plan_file))
            print(f"   ✅ Saved migration plan: migration_plan.json")
            
            # 4. Save line-by-line change report
            if prep_res["line_change_report"]:
                line_report_file = os.path.join(workspace, "line_change_report.json")
                with open(line_report_file, 'w', encoding='utf-8') as f:
                    json.dump(prep_res["line_change_report"], f, indent=2, ensure_ascii=False)
                report_files.append(("Line Change Report", line_report_file))
                print(f"   ✅ Saved line change report: line_change_report.json")
            
            # 5. Save application results
            if prep_res["applied_changes"]:
                applied_file = os.path.join(workspace, "migration_application_results.json")
                with open(applied_file, 'w', encoding='utf-8') as f:
                    json.dump(prep_res["applied_changes"], f, indent=2, ensure_ascii=False)
                report_files.append(("Application Results", applied_file))
                print(f"   ✅ Saved application results: migration_application_results.json")
            
            # 6. Generate comprehensive metrics
            metrics = self._generate_migration_metrics(prep_res)
            metrics_file = os.path.join(workspace, "migration_metrics.json")
            with open(metrics_file, 'w', encoding='utf-8') as f:
                json.dump(metrics, f, indent=2, ensure_ascii=False)
            report_files.append(("Migration Metrics", metrics_file))
            print(f"   ✅ Saved migration metrics: migration_metrics.json")
            
            # 7. Generate human-readable summary report
            summary_md = self._generate_summary_markdown(prep_res, metrics, timestamp)
            summary_file = os.path.join(workspace, "MIGRATION_SUMMARY.md")
            with open(summary_file, 'w', encoding='utf-8') as f:
                f.write(summary_md)
            report_files.append(("Summary Report", summary_file))
            print(f"   ✅ Saved summary report: MIGRATION_SUMMARY.md")
            
            # 8. Generate executive summary for stakeholders
            exec_summary = self._generate_executive_summary(prep_res, metrics)
            exec_file = os.path.join(workspace, "EXECUTIVE_SUMMARY.md")
            with open(exec_file, 'w', encoding='utf-8') as f:
                f.write(exec_summary)
            report_files.append(("Executive Summary", exec_file))
            print(f"   ✅ Saved executive summary: EXECUTIVE_SUMMARY.md")
            
            # 9. Create index file for easy navigation
            index_content = self._generate_report_index(report_files, project_name, timestamp)
            index_file = os.path.join(workspace, "README_REPORTS.md")
            with open(index_file, 'w', encoding='utf-8') as f:
                f.write(index_content)
            report_files.append(("Report Index", index_file))
            print(f"   ✅ Saved report index: README_REPORTS.md")
            
            return {
                "success": True,
                "reports_generated": len(report_files),
                "report_files": report_files,
                "workspace": workspace,
                "metrics": metrics
            }
            
        except Exception as e:
            if prep_res["verbose_mode"]:
                vlogger.error(f"Error generating reports: {e}")
            return {
                "success": False,
                "error": str(e),
                "reports_generated": len(report_files),
                "partial_files": report_files
            }
    
    def _generate_migration_metrics(self, prep_res):
        """Generate comprehensive migration metrics."""
        from datetime import datetime
        
        metrics = {
            "project_info": {
                "name": prep_res["project_name"],
                "analysis_timestamp": datetime.now().isoformat(),
                "migration_workspace": prep_res["migration_workspace"]
            },
            "analysis_metrics": {},
            "change_metrics": {},
            "application_metrics": {},
            "overall_metrics": {}
        }
        
        # Analysis metrics
        analysis = prep_res["migration_analysis"]
        if isinstance(analysis, dict):
            exec_summary = analysis.get("executive_summary", {})
            metrics["analysis_metrics"] = {
                "migration_impact": exec_summary.get("migration_impact", "Unknown"),
                "key_blockers_count": len(exec_summary.get("key_blockers", [])),
                "recommended_approach": exec_summary.get("recommended_approach", "Unknown"),
                "analysis_completed": True
            }
            
            # Extract effort estimation if available
            effort_estimation = analysis.get("effort_estimation", {})
            if effort_estimation:
                metrics["analysis_metrics"]["estimated_effort"] = effort_estimation.get("total_effort", "Unknown")
        
        # Change generation metrics
        changes = prep_res["generated_changes"]
        change_summary = prep_res["migration_changes_summary"]
        
        if isinstance(changes, dict):
            total_changes = sum(len(changes_list) for changes_list in changes.values() if isinstance(changes_list, list))
            metrics["change_metrics"] = {
                "total_changes_identified": total_changes,
                "changes_by_category": {},
                "files_requiring_changes": change_summary.get("files_with_changes", 0)
            }
            
            for category, changes_list in changes.items():
                if isinstance(changes_list, list):
                    metrics["change_metrics"]["changes_by_category"][category] = len(changes_list)
        
        # Application metrics
        applied = prep_res["applied_changes"]
        if isinstance(applied, dict) and not applied.get("skipped", False):
            metrics["application_metrics"] = {
                "changes_applied": applied.get("total_changes_applied", 0),
                "files_modified": len(applied.get("files_modified", set())),
                "successful_changes": len(applied.get("successful", [])),
                "skipped_changes": len(applied.get("skipped", [])),
                "failed_changes": len(applied.get("failed", [])),
                "application_success_rate": 0
            }
            
            total_attempted = (metrics["application_metrics"]["successful_changes"] + 
                             metrics["application_metrics"]["failed_changes"])
            if total_attempted > 0:
                success_rate = metrics["application_metrics"]["successful_changes"] / total_attempted * 100
                metrics["application_metrics"]["application_success_rate"] = round(success_rate, 2)
        
        # Overall metrics
        metrics["overall_metrics"] = {
            "migration_readiness": "Unknown",
            "automation_coverage": 0,
            "critical_issues": [],
            "next_steps": []
        }
        
        # Determine migration readiness
        if metrics["change_metrics"].get("total_changes_identified", 0) == 0:
            metrics["overall_metrics"]["migration_readiness"] = "Ready - No changes needed"
        elif metrics["application_metrics"].get("changes_applied", 0) > 0:
            metrics["overall_metrics"]["migration_readiness"] = "In Progress - Changes applied"
        elif metrics["change_metrics"].get("total_changes_identified", 0) > 0:
            metrics["overall_metrics"]["migration_readiness"] = "Analysis Complete - Ready for changes"
        
        # Calculate automation coverage
        total_identified = metrics["change_metrics"].get("total_changes_identified", 0)
        total_applied = metrics["application_metrics"].get("changes_applied", 0)
        if total_identified > 0:
            automation_coverage = (total_applied / total_identified) * 100
            metrics["overall_metrics"]["automation_coverage"] = round(automation_coverage, 2)
        
        return metrics
    
    def _generate_summary_markdown(self, prep_res, metrics, timestamp):
        """Generate a comprehensive human-readable summary report."""
        project_name = prep_res["project_name"]
        
        md = f"""# Spring Migration Summary Report

**Project:** {project_name}  
**Generated:** {timestamp}  
**Migration Tool:** Spring 5 → Spring 6 Migration Analyzer

---

## 🎯 Executive Summary

### Migration Status: {metrics["overall_metrics"]["migration_readiness"]}

"""
        
        # Add analysis summary
        analysis = prep_res["migration_analysis"]
        if isinstance(analysis, dict):
            exec_summary = analysis.get("executive_summary", {})
            if exec_summary:
                md += f"""### Analysis Overview
- **Impact Assessment:** {exec_summary.get("migration_impact", "Not available")}
- **Recommended Approach:** {exec_summary.get("recommended_approach", "Not specified")}

"""
                
                key_blockers = exec_summary.get("key_blockers", [])
                if key_blockers:
                    md += f"""### Key Migration Blockers
"""
                    for i, blocker in enumerate(key_blockers[:5], 1):
                        md += f"{i}. {blocker}\n"
                    md += "\n"
        
        # Add metrics
        change_metrics = metrics.get("change_metrics", {})
        app_metrics = metrics.get("application_metrics", {})
        
        md += f"""## 📊 Migration Metrics

| Metric | Value |
|--------|--------|
| **Changes Identified** | {change_metrics.get("total_changes_identified", 0)} |
| **Files Requiring Changes** | {change_metrics.get("files_requiring_changes", 0)} |
| **Changes Applied** | {app_metrics.get("changes_applied", 0)} |
| **Files Modified** | {app_metrics.get("files_modified", 0)} |
| **Automation Coverage** | {metrics["overall_metrics"]["automation_coverage"]}% |
| **Success Rate** | {app_metrics.get("application_success_rate", 0)}% |

"""
        
        # Add change breakdown
        changes_by_category = change_metrics.get("changes_by_category", {})
        if changes_by_category:
            md += f"""## 🔧 Changes by Category

| Category | Changes Identified |
|----------|-------------------|
"""
            for category, count in changes_by_category.items():
                category_name = category.replace('_', ' ').title()
                md += f"| {category_name} | {count} |\n"
            md += "\n"
        
        # Add application results
        applied = prep_res["applied_changes"]
        if isinstance(applied, dict) and not applied.get("skipped", False):
            md += f"""## ✅ Application Results

### Summary
- **✅ Successful:** {len(applied.get("successful", []))} changes
- **⏭️ Skipped:** {len(applied.get("skipped", []))} changes  
- **❌ Failed:** {len(applied.get("failed", []))} changes

"""
            
            # Show modified files
            files_modified = applied.get("files_modified", set())
            if files_modified:
                md += f"""### Files Modified ({len(files_modified)})
"""
                for file_path in sorted(files_modified):
                    md += f"- `{file_path}`\n"
                md += "\n"
        
        # Add recommendations
        md += f"""## 🎯 Next Steps

"""
        
        migration_plan = prep_res["migration_plan"]
        if isinstance(migration_plan, dict):
            roadmap = migration_plan.get("migration_roadmap", [])
            if roadmap:
                md += f"""### Migration Roadmap
"""
                for step in roadmap[:3]:  # Show first 3 steps
                    step_num = step.get("step", "?")
                    title = step.get("title", "Unknown step")
                    description = step.get("description", "No description")
                    effort = step.get("estimated_effort", "Unknown effort")
                    
                    md += f"""**Step {step_num}: {title}**
- Description: {description}
- Estimated Effort: {effort}

"""
        
        # Add manual review items
        if applied and len(applied.get("skipped", [])) > 0:
            md += f"""### Manual Review Required

The following changes were identified but require manual review:

"""
            for skipped in applied.get("skipped", [])[:10]:  # Show first 10
                file_name = skipped.get("file", "Unknown file")
                reason = skipped.get("reason", "Manual review required")
                md += f"- **{file_name}**: {reason}\n"
            
            if len(applied.get("skipped", [])) > 10:
                md += f"- ... and {len(applied.get('skipped', [])) - 10} more items\n"
            md += "\n"
        
        # Add file locations
        md += f"""## 📁 Generated Reports

The following detailed reports have been generated:

- **`spring_migration_analysis.json`** - Complete LLM analysis results
- **`migration_changes_detailed.json`** - All identified changes
- **`migration_plan.json`** - Detailed migration plan
- **`migration_metrics.json`** - Key metrics and statistics
- **`line_change_report.json`** - Line-by-line change analysis
- **`EXECUTIVE_SUMMARY.md`** - Stakeholder-friendly summary

## 🛠️ How to Use These Reports

1. **Review the Executive Summary** for a high-level overview
2. **Check migration_metrics.json** for detailed statistics
3. **Use migration_plan.json** for step-by-step implementation guidance
4. **Reference migration_changes_detailed.json** for specific code changes
5. **Test thoroughly** before applying changes to production

---

*Generated by Spring Migration Tool - {timestamp}*
"""
        
        return md
    
    def _generate_executive_summary(self, prep_res, metrics):
        """Generate an executive summary for stakeholders."""
        project_name = prep_res["project_name"]
        
        md = f"""# Executive Summary: {project_name} Spring Migration

## Overview

This report summarizes the analysis and migration of **{project_name}** from Spring Framework 5 to Spring Framework 6.

## Key Findings

### Migration Readiness
**Status:** {metrics["overall_metrics"]["migration_readiness"]}

### Impact Assessment
"""
        
        analysis = prep_res["migration_analysis"]
        if isinstance(analysis, dict):
            exec_summary = analysis.get("executive_summary", {})
            impact = exec_summary.get("migration_impact", "Impact assessment not available")
            md += f"- {impact}\n\n"
        
        # Add metrics in business terms
        change_metrics = metrics.get("change_metrics", {})
        app_metrics = metrics.get("application_metrics", {})
        
        md += f"""### Scope
- **{change_metrics.get("total_changes_identified", 0)}** code changes identified
- **{change_metrics.get("files_requiring_changes", 0)}** files require modification
- **{metrics["overall_metrics"]["automation_coverage"]}%** of changes can be automated

### Effort Estimation
"""
        
        if isinstance(analysis, dict):
            effort_estimation = analysis.get("effort_estimation", {})
            total_effort = effort_estimation.get("total_effort", "Effort estimation not available")
            md += f"- **Estimated Effort:** {total_effort}\n"
            
            team_size = effort_estimation.get("by_category", {}).get("team_size_recommendation", "2-3 developers")
            if isinstance(team_size, str):
                md += f"- **Recommended Team Size:** {team_size}\n"
        
        md += f"""
### Risk Assessment
"""
        
        if isinstance(analysis, dict):
            key_blockers = exec_summary.get("key_blockers", [])
            if key_blockers:
                md += f"**Critical Issues ({len(key_blockers)}):**\n"
                for blocker in key_blockers[:3]:
                    md += f"- {blocker}\n"
                if len(key_blockers) > 3:
                    md += f"- ... and {len(key_blockers) - 3} more issues\n"
            else:
                md += "- No critical blocking issues identified\n"
        
        md += f"""
## Recommendations

### Immediate Actions Required
1. **Review Critical Issues**: Address any blocking issues before proceeding
2. **Plan Migration Timeline**: Schedule migration activities with development team
3. **Prepare Test Environment**: Ensure comprehensive testing capabilities

### Implementation Strategy
"""
        
        migration_plan = prep_res["migration_plan"]
        if isinstance(migration_plan, dict):
            strategy = migration_plan.get("migration_strategy", {})
            approach = strategy.get("approach", "Phased approach recommended")
            timeline = strategy.get("estimated_timeline", "Timeline to be determined")
            
            md += f"""- **Approach:** {approach}
- **Estimated Timeline:** {timeline}
"""
        
        md += f"""
## Success Metrics

- **Automated Changes:** {app_metrics.get("changes_applied", 0)}/{change_metrics.get("total_changes_identified", 0)} applied
- **Success Rate:** {app_metrics.get("application_success_rate", 0)}%
- **Files Updated:** {app_metrics.get("files_modified", 0)} files modified

## Next Steps

1. **Executive Approval**: Secure approval for migration project
2. **Resource Allocation**: Assign development team and timeline
3. **Detailed Planning**: Review technical implementation plan
4. **Testing Strategy**: Plan comprehensive testing approach
5. **Risk Mitigation**: Address identified blocking issues

---

*For detailed technical information, see the complete migration analysis reports.*
"""
        
        return md
    
    def _generate_report_index(self, report_files, project_name, timestamp):
        """Generate an index file for easy navigation of all reports."""
        md = f"""# Migration Reports Index - {project_name}

**Generated:** {timestamp}

This directory contains comprehensive migration analysis and reports for the Spring 5 → Spring 6 migration.

## 📋 Report Files

### 🎯 Executive Reports (Start Here)
- **[EXECUTIVE_SUMMARY.md](./EXECUTIVE_SUMMARY.md)** - High-level summary for stakeholders
- **[MIGRATION_SUMMARY.md](./MIGRATION_SUMMARY.md)** - Comprehensive technical summary

### 📊 Detailed Analysis Reports
- **[spring_migration_analysis.json](./spring_migration_analysis.json)** - Complete LLM analysis results
- **[migration_plan.json](./migration_plan.json)** - Detailed step-by-step migration plan
- **[migration_metrics.json](./migration_metrics.json)** - Key metrics and statistics

### 🔧 Change Reports
- **[migration_changes_detailed.json](./migration_changes_detailed.json)** - All identified code changes
- **[line_change_report.json](./line_change_report.json)** - Line-by-line change analysis
- **[migration_application_results.json](./migration_application_results.json)** - Results of applying changes

## 🚀 Quick Start Guide

1. **Executives/Managers**: Start with `EXECUTIVE_SUMMARY.md`
2. **Development Team**: Review `MIGRATION_SUMMARY.md` and `migration_plan.json`
3. **Implementation**: Use `migration_changes_detailed.json` for specific changes
4. **Metrics/Tracking**: Reference `migration_metrics.json` for progress tracking

## 📂 File Descriptions

| File | Purpose | Audience |
|------|---------|----------|
| `EXECUTIVE_SUMMARY.md` | Business overview and recommendations | Executives, Project Managers |
| `MIGRATION_SUMMARY.md` | Technical summary with next steps | Development Team, Tech Leads |
| `spring_migration_analysis.json` | Raw LLM analysis output | Developers, Tool Integration |
| `migration_plan.json` | Structured implementation plan | Project Managers, Developers |
| `migration_changes_detailed.json` | Specific code changes needed | Developers |
| `line_change_report.json` | Line-by-line change breakdown | Developers, QA |
| `migration_metrics.json` | Statistics and metrics | All stakeholders |
| `migration_application_results.json` | Results of automated changes | Developers, QA |

## 🛠️ How to Use

### For Project Planning
1. Review effort estimates in `migration_metrics.json`
2. Use `migration_plan.json` for timeline planning
3. Identify risks from `EXECUTIVE_SUMMARY.md`

### For Implementation
1. Start with automated changes from `migration_application_results.json`
2. Review manual changes needed from `migration_changes_detailed.json`
3. Use `line_change_report.json` for detailed change tracking

### For Testing
1. Reference changed files from `migration_application_results.json`
2. Create test cases based on `migration_changes_detailed.json`
3. Validate against requirements in `migration_plan.json`

---

*Generated by Spring Migration Tool*
"""
        
        return md

    def post(self, shared, prep_res, exec_res):
        """Store the report generation results."""
        vlogger = get_verbose_logger()
        
        shared["migration_reports"] = exec_res
        
        if exec_res.get("success", False):
            reports_count = exec_res.get("reports_generated", 0)
            workspace = exec_res.get("workspace", "unknown location")
            
            print(f"\n📄 Migration Reports Summary:")
            print(f"   ✅ Generated {reports_count} comprehensive reports")
            print(f"   📁 Location: {workspace}")
            print(f"   📋 Key reports:")
            print(f"      • EXECUTIVE_SUMMARY.md - For stakeholders")
            print(f"      • MIGRATION_SUMMARY.md - Technical overview")
            print(f"      • spring_migration_analysis.json - Detailed analysis")
            print(f"      • migration_metrics.json - Key metrics")
            print(f"      • README_REPORTS.md - Navigation guide")
            
            if shared.get("verbose_mode"):
                vlogger.success(f"Generated {reports_count} migration reports in {workspace}")
        else:
            error = exec_res.get("error", "Unknown error")
            print(f"❌ Report generation failed: {error}")
            
            # Show partial results if any
            partial_count = exec_res.get("reports_generated", 0)
            if partial_count > 0:
                print(f"   📄 Generated {partial_count} partial reports")
            
            if shared.get("verbose_mode"):
                vlogger.error(f"Report generation failed: {error}")
        
        return "default"
