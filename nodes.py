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
            vlogger.step("Preparing repository fetch configuration")
        
        repo_url = shared.get("repo_url")
        local_dir = shared.get("local_dir")
        project_name = shared.get("project_name")

        if not project_name:
            # Basic name derivation from URL or directory
            if repo_url:
                project_name = repo_url.split("/")[-1].replace(".git", "")
            else:
                project_name = os.path.basename(os.path.abspath(local_dir))
            shared["project_name"] = project_name
            
            if shared.get("verbose_mode"):
                vlogger.debug(f"Derived project name: {project_name}")

        # Get file patterns directly from shared
        include_patterns = shared["include_patterns"]
        exclude_patterns = shared["exclude_patterns"]
        max_file_size = shared["max_file_size"]
        
        # Performance optimization settings
        enable_optimization = shared.get("enable_optimization", True)
        max_files_for_analysis = shared.get("max_files_for_analysis", None)

        if shared.get("verbose_mode"):
            vlogger.debug(f"File patterns: {len(include_patterns)} include, {len(exclude_patterns)} exclude")
            vlogger.debug(f"Max file size: {max_file_size / 1024 / 1024:.1f} MB")
            vlogger.debug(f"Optimization enabled: {enable_optimization}")
            if max_files_for_analysis:
                vlogger.debug(f"File limit: {max_files_for_analysis} files")

        return {
            "repo_url": repo_url,
            "local_dir": local_dir,
            "token": shared.get("github_token"),
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "max_file_size": max_file_size,
            "use_relative_paths": True,
            "enable_optimization": enable_optimization,
            "max_files_for_analysis": max_files_for_analysis,
            "verbose_mode": shared.get("verbose_mode", False)
        }

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
                if prep_res["token"]:
                    vlogger.debug("Using authentication token")
                else:
                    vlogger.warning("No GitHub token provided - may hit rate limits")
            
            result = crawl_github_files(
                repo_url=prep_res["repo_url"],
                token=prep_res["token"],
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
        prompt = f"""# System Prompt: Spring 6 Migration – Full Codebase Analysis

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

## 4. Spring Security Migration
- Detect actual usage of `WebSecurityConfigurerAdapter` in the codebase
- Identify how authentication, authorization, CORS, CSRF are actually implemented
- Recommend changes based on the actual security configuration found

## 5. Spring Data and JPA
- Audit actual use of `javax.persistence.*` and related annotations in the code
- Review actual repository interfaces and custom queries present
- Check actual Hibernate usage and version from build files

## 6. Web Layer (Spring MVC / WebFlux)
- Identify actual controllers, `@RequestMapping` methods, interceptors found in code
- Detect actual servlet-based components in the codebase
- Highlight APIs that are actually used and need migration

## 7. Testing Analysis
- Review actual tests using Spring Test, JUnit that exist in the codebase
- Detect actual `javax.*` usage in test code
- Identify actual testing patterns that need updates

## 8. Build Tooling
- Audit actual Maven or Gradle setup from the build files provided
- Validate actual plugin versions and compiler settings
- Check actual build configuration compatibility

## 9. Output Requirements

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

Analyze the codebase thoroughly and provide the complete JSON response based on actual findings."""

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

Based on the following analysis results, create a comprehensive, actionable migration plan:

**Project:** {project_name}
**Analysis Results:**
{json.dumps(analysis, indent=2)}

**IMPORTANT:** You MUST include ALL required fields in your JSON response:
- migration_strategy (with approach, rationale, estimated_timeline, team_size_recommendation)
- phase_breakdown (array of phases with tasks, risks, success criteria)
- automation_recommendations (array of automation tools and guidance)
- testing_strategy (with unit_tests, integration_tests, regression_testing)

Generate a detailed migration plan based on the actual findings from the analysis.

**Migration Complexity Guidelines:**
- Simple projects (< 50 files): 1-2 phases, 2-4 weeks
- Medium projects (50-200 files): 3-4 phases, 1-2 months  
- Large projects (200+ files): 4-6 phases, 2-4 months

**Timeline Guidelines:**
- Include time for testing, validation, and deployment
- Account for parallel development work
- Consider team availability and other project commitments

**REQUIRED JSON OUTPUT FORMAT - Include ALL sections:**
```json
{{
  "migration_strategy": {{
    "approach": "Big Bang|Phased|Hybrid",
    "rationale": "Explanation of chosen approach based on project size and risk",
    "estimated_timeline": "X weeks|X months (be specific and realistic)",
    "team_size_recommendation": "X developers (1-5 max)"
  }},
  "phase_breakdown": [
    {{
      "phase": 1,
      "name": "string",
      "description": "string",
      "duration": "X days/weeks",
      "deliverables": [],
      "tasks": [
        {{
          "task_id": "string",
          "title": "string", 
          "description": "string",
          "complexity": "Low|Medium|High",
          "estimated_hours": "number (8-40 hours per task)",
          "dependencies": [],
          "automation_potential": "High|Medium|Low",
          "tools_required": []
        }}
      ],
      "risks": [],
      "success_criteria": []
    }}
  ],
  "automation_recommendations": [
    {{
      "tool": "string",
      "purpose": "string",
      "setup_instructions": "string",
      "coverage": "percentage of issues it can handle"
    }}
  ],
  "manual_changes": [
    {{
      "category": "string",
      "changes": [],
      "rationale": "why manual changes are needed"
    }}
  ],
  "testing_strategy": {{
    "unit_tests": "approach for unit test migration",
    "integration_tests": "approach for integration test migration", 
    "regression_testing": "strategy for ensuring no functionality is broken"
  }},
  "rollback_plan": {{
    "triggers": ["conditions that would require rollback"],
    "steps": ["detailed rollback procedures"],
    "data_considerations": "any data migration rollback needs"
  }},
  "success_metrics": [
    {{
      "metric": "string",
      "target": "string",
      "measurement_method": "string"
    }}
  ]
}}
```

**CRITICAL:** Return ONLY the JSON object. Do not include any explanatory text before or after the JSON. Ensure all required top-level fields are present: migration_strategy, phase_breakdown, automation_recommendations, testing_strategy."""

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
                "data_considerations": "Ensure database schema compatibility, backup configuration files"
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
        
        # Create context from the migration analysis
        analysis_context = self._create_analysis_context(analysis)
        
        # Prepare file content for LLM (limit size and clean it)
        clean_content = self._prepare_file_content_for_llm(content, file_path)
        
        # Enhanced prompt with better JSON guidance
        prompt = f"""# Spring Migration Change Analysis

You are analyzing a file from project `{project_name}` for Spring 6 migration. Based on the overall migration analysis and the specific file content, generate precise, actionable changes.

## Overall Migration Analysis Context:
{analysis_context}

## File to Analyze:
**File Path:** {file_path}
**File Type:** {self._get_file_type(file_path)}
**File Content:**
```
{clean_content}
```

## CRITICAL: You MUST respond with ONLY valid JSON - no additional text or explanations

Your response must be ONLY a JSON object with this exact structure. Do not include any text before or after the JSON:

{{
  "javax_to_jakarta": [],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}}

For each category, include objects like:
{{
  "file": "{file_path}",
  "type": "import_replacement",
  "from": "javax.package.name",
  "to": "jakarta.package.name",
  "description": "Short description",
  "line_numbers": [1, 2, 3],
  "automatic": true,
  "explanation": "Brief reason"
}}

## JSON Response Rules:
1. Return ONLY the JSON object - no markdown, no explanation text
2. Keep all string values short and simple
3. Use only basic ASCII characters in strings
4. If no changes needed in a category, use empty array: []
5. Base recommendations only on what you find in the file content
6. Include exact line numbers where possible
7. Use "automatic": true only for simple import replacements
8. Escape any quotes in string values

## Example Response Format:
{{
  "javax_to_jakarta": [
    {{
      "file": "{file_path}",
      "type": "import_replacement",
      "from": "javax.persistence.Entity",
      "to": "jakarta.persistence.Entity",
      "description": "Replace javax persistence import",
      "line_numbers": [3],
      "automatic": true,
      "explanation": "Standard javax to jakarta migration"
    }}
  ],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}}

Analyze the file and return ONLY the JSON object:"""

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            
            # Enhanced debugging
            if len(response) < 50:
                print(f"     Warning: Very short LLM response for {file_path}: {len(response)} chars")
                print(f"     Response: {response}")
                return self._get_empty_changes()
            
            # Clean and extract JSON from response
            json_str = self._extract_and_clean_json(response, file_path)
            if not json_str:
                print(f"     Failed to extract JSON from LLM response for {file_path}")
                # In debug mode, save the response for inspection
                self._save_debug_response(file_path, response)
                return self._get_empty_changes()
            
            # Parse JSON
            file_changes = json.loads(json_str)
            
            # Validate structure
            expected_keys = ["javax_to_jakarta", "spring_security_updates", "dependency_updates", "configuration_updates", "other_changes"]
            for key in expected_keys:
                if key not in file_changes:
                    file_changes[key] = []
            
            # Validate each change has required fields
            for category, changes_list in file_changes.items():
                validated_changes = []
                for change in changes_list:
                    if self._validate_change(change, file_path):
                        validated_changes.append(change)
                file_changes[category] = validated_changes
            
            # Report success with some statistics
            total_changes = sum(len(changes) for changes in file_changes.values())
            if total_changes > 0:
                print(f"     ✅ Found {total_changes} changes for {file_path}")
            
            return file_changes
            
        except json.JSONDecodeError as e:
            print(f"     JSON parsing error for {file_path}: {e}")
            self._save_debug_response(file_path, response if 'response' in locals() else "No response")
            return self._get_empty_changes()
        except Exception as e:
            print(f"     Error analyzing {file_path}: {e}")
            return self._get_empty_changes()
    
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
            'test', 'tests', 'spec', 'mock', 'readme', 'changelog', 'license', 
            'docker', 'target/', 'build/', 'node_modules/', '.git/', '.idea/'
        }
        
        # Check extension
        file_lower = file_path.lower()
        if any(file_lower.endswith(ext) for ext in skip_extensions):
            return True
        
        # Check patterns
        if any(pattern in file_lower for pattern in skip_patterns):
            return True
        
        # Skip large non-Java files (properties files with many entries)
        if file_path.endswith('.properties') and len(file_path.split('/')) > 4:
            # Skip deeply nested properties files which are likely translations/configs
            return True
        
        return False
    
    def _get_file_type(self, file_path):
        """Get a simple description of file type for LLM context."""
        if file_path.endswith('.java'):
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
