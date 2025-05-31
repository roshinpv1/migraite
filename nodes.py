import os
import re
import yaml
import json
from pocketflow import Node, BatchNode
from utils.crawl_github_files import crawl_github_files
from utils.call_llm import call_llm
from utils.crawl_local_files import crawl_local_files
from utils.performance_monitor import (
    get_performance_monitor,
    ResourceOptimizer,
    ConcurrentAnalysisManager
)


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

        # Get file patterns directly from shared
        include_patterns = shared["include_patterns"]
        exclude_patterns = shared["exclude_patterns"]
        max_file_size = shared["max_file_size"]
        
        # Performance optimization settings
        enable_optimization = shared.get("enable_optimization", True)
        max_files_for_analysis = shared.get("max_files_for_analysis", None)

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
        }

    def exec(self, prep_res):
        monitor = get_performance_monitor()
        monitor.start_operation("fetch_repository")
        
        if prep_res["repo_url"]:
            print(f"Crawling repository: {prep_res['repo_url']}...")
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

            result = crawl_local_files(
                directory=prep_res["local_dir"],
                include_patterns=prep_res["include_patterns"],
                exclude_patterns=prep_res["exclude_patterns"],
                max_file_size=prep_res["max_file_size"],
                use_relative_paths=prep_res["use_relative_paths"]
            )

        # Convert dict to list of tuples: [(path, content), ...]
        files_list = list(result.get("files", {}).items())
        if len(files_list) == 0:
            raise (ValueError("Failed to fetch files"))
        
        # Performance optimization: filter files if enabled
        if prep_res["enable_optimization"] and prep_res["max_files_for_analysis"]:
            files_list = ResourceOptimizer.filter_files_for_analysis(
                files_list, 
                max_files=prep_res["max_files_for_analysis"],
                prioritize_spring_files=True
            )
        
        print(f"Fetched {len(files_list)} files.")
        
        # Generate analysis estimates
        if prep_res["enable_optimization"]:
            estimates = ResourceOptimizer.estimate_analysis_requirements(files_list)
            print(f"📊 Analysis Estimates:")
            print(f"   Files: {estimates['total_files']} ({estimates['total_size_mb']:.1f} MB)")
            print(f"   Estimated Duration: {estimates['estimated_duration_minutes']:.1f} minutes")
            print(f"   Estimated Memory: {estimates['estimated_memory_mb']:.1f} MB")
        
        monitor.end_operation("fetch_repository", files_processed=len(files_list))
        return files_list

    def post(self, shared, prep_res, exec_res):
        shared["files"] = exec_res  # List of (path, content) tuples
        
        # Store optimization settings for downstream nodes
        shared["optimization_settings"] = ResourceOptimizer.get_recommended_settings(
            total_files=len(exec_res),
            total_size=sum(len(content) for _, content in exec_res)
        )


# ==========================================
# SPRING MIGRATION NODES
# ==========================================

class SpringMigrationAnalyzer(Node):
    """
    Analyzes a Spring codebase for migration from Spring 5 to Spring 6.
    Enhanced with concurrent analysis and performance optimization.
    """
    
    def prep(self, shared):
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

You are an expert in Java, Spring Framework (5 and 6), Jakarta EE 9+, and enterprise application modernization. Analyze the Java codebase for project `{project_name}` targeted for migration from Spring Framework 5.x (and optionally Spring Boot 2.x) to Spring Framework 6.x and Spring Boot 3.x, with Java 17+ and Jakarta namespace compatibility.

## Codebase Context:
{context}

## Available Files:
{file_listing}

## IMPORTANT: Provide REALISTIC effort estimates based on the actual codebase size and complexity:

**Project Size Assessment:**
- Small project (< 50 Java files): 5-15 person-days, 1-2 developers, 2-4 weeks timeline
- Medium project (50-200 Java files): 15-30 person-days, 2-3 developers, 1-2 months timeline  
- Large project (200+ Java files): 30-60 person-days, 3-5 developers, 2-4 months timeline

**Complexity Factors** (add extra effort):
- Heavy use of deprecated APIs: +20-40% effort
- Complex security configuration: +10-20% effort
- Extensive custom configurations: +10-30% effort
- Large test suite: +10-20% effort
- Multiple modules/microservices: +20-50% effort

## Analysis Requirements:

## 1. Framework and Dependency Audit
- Identify current Spring and Spring Boot versions.
- Detect deprecated or removed Spring modules and APIs.
- Audit third-party libraries for compatibility with Spring 6 and Jakarta EE.
- Flag any usage of `javax.*` APIs that are no longer supported.

## 2. Jakarta Namespace Impact
- Search and list all usages of `javax.*` packages (e.g., `javax.servlet`, `javax.persistence`, `javax.validation`).
- Map these to their `jakarta.*` counterparts.
- Assess classes, annotations, XML, and other affected configuration files.
- Identify incompatible external libraries that still use `javax.*`.

## 3. Configuration and Component Analysis
- Analyze Java-based and XML-based Spring configurations.
- Evaluate `@Configuration`, `@ComponentScan`, `@Profile`, `@Conditional`, and lifecycle methods.
- Identify deprecated constructs or non-functional patterns under Spring 6.

## 4. Spring Security Migration
- Detect usage of `WebSecurityConfigurerAdapter` (removed in Spring Security 6).
- Identify how authentication, authorization, CORS, CSRF, JWT, and OAuth are implemented.
- Recommend changes using `SecurityFilterChain` and new configuration DSL.
- Highlight deprecated or removed security annotations.

## 5. Spring Data and JPA
- Audit all use of `javax.persistence.*` and related annotations.
- Review repository interfaces and custom queries.
- Validate Hibernate version and compatibility with Hibernate 6.
- Check for deprecated or removed entity features and mapping strategies.

## 6. Web Layer (Spring MVC / WebFlux)
- Identify all controllers, `@RequestMapping` methods, interceptors, filters, listeners, and exception handlers.
- Detect servlet-based components that are impacted by Jakarta migration.
- Highlight APIs or components deprecated or removed in Spring 6.

## 7. Testing Analysis
- Review tests using Spring Test, JUnit 4/5, MockMvc, WebTestClient.
- Detect `javax.*` usage in tests.
- Flag fragile or deprecated testing patterns.
- Identify any reliance on removed internals or XML-based test bootstrapping.

## 8. Build Tooling and CI/CD
- Audit Maven or Gradle setup for compatibility with Spring Boot 3.x and Java 17+.
- Validate use of compiler, Surefire, Failsafe, and plugin versions.
- Check Dockerfiles, build scripts, and CI/CD configurations for migration readiness.

## 9. Migration Tooling Suggestions
- Recommend tools and automation:
  - OpenRewrite migration recipes (Spring Boot 3, Jakarta EE)
  - Static analysis tools (e.g., jdeps, japi-compliance-checker)
  - IDE refactor support (IntelliJ, Eclipse)
  - Custom code mod scripts where needed

## 10. Output Requirements

Your output must be in valid JSON format with the following structure. IMPORTANT: 
- Return ONLY valid JSON, no additional text or explanations
- Ensure all strings are properly escaped with double quotes
- Avoid special characters that break JSON parsing
- Keep string values concise to prevent truncation

```json
{{
  "executive_summary": {{
    "migration_impact": "High-level overview of migration impact",
    "key_blockers": ["Critical issue 1", "Critical issue 2", "Critical issue 3"],
    "recommended_approach": "Recommendation for overall migration approach"
  }},
  "detailed_analysis": {{
    "framework_audit": {{
      "current_versions": {{}},
      "deprecated_apis": [],
      "third_party_compatibility": []
    }},
    "jakarta_migration": {{
      "javax_usages": [],
      "mapping_required": {{}},
      "incompatible_libraries": []
    }},
    "configuration_analysis": {{
      "java_config_issues": [],
      "xml_config_issues": [],
      "deprecated_patterns": []
    }},
    "security_migration": {{
      "websecurity_adapter_usage": [],
      "auth_config_changes": [],
      "deprecated_security_features": []
    }},
    "data_layer": {{
      "jpa_issues": [],
      "repository_issues": [],
      "hibernate_compatibility": []
    }},
    "web_layer": {{
      "controller_issues": [],
      "servlet_issues": [],
      "deprecated_web_features": []
    }},
    "testing": {{
      "test_framework_issues": [],
      "deprecated_test_patterns": []
    }},
    "build_tooling": {{
      "build_file_issues": [],
      "plugin_compatibility": [],
      "cicd_considerations": []
    }}
  }},
  "module_breakdown": [
    {{
      "module_name": "main_module",
      "complexity": "Medium",
      "refactor_type": "Semi-manual",
      "issues": ["Issue 1", "Issue 2"],
      "effort_estimate": "X person-days"
    }}
  ],
  "effort_estimation": {{
    "total_effort": "X person-days",
    "by_category": {{
      "jakarta_migration": "X person-days",
      "security_updates": "X person-days", 
      "dependency_updates": "X person-days",
      "testing": "X person-days",
      "build_config": "X person-days"
    }},
    "priority_levels": {{
      "high": ["Critical item 1", "Critical item 2"],
      "medium": ["Important item 1", "Important item 2"],
      "low": ["Nice to have 1", "Nice to have 2"]
    }}
  }},
  "code_samples": {{
    "jakarta_namespace": {{
      "before": "import javax.persistence.Entity;",
      "after": "import jakarta.persistence.Entity;"
    }},
    "security_config": {{
      "before": "extends WebSecurityConfigurerAdapter", 
      "after": "SecurityFilterChain filterChain(HttpSecurity http)"
    }},
    "spring_config": {{
      "before": "Spring Boot 2.x config",
      "after": "Spring Boot 3.x config"
    }}
  }},
  "migration_roadmap": [
    {{
      "step": 1,
      "title": "Dependency Updates",
      "description": "Update Spring Boot to 3.x and related dependencies",
      "estimated_effort": "X person-days",
      "dependencies": []
    }},
    {{
      "step": 2,
      "title": "Jakarta Migration",
      "description": "Replace javax imports with jakarta equivalents",
      "estimated_effort": "X person-days",
      "dependencies": ["step-1"]
    }}
  ]
}}
```

Analyze the codebase thoroughly and provide the complete JSON response."""

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
    
    def _get_fallback_analysis(self, prep_res, file_listing):
        """Generate a fallback analysis when LLM parsing fails."""
        # Extract files data from prep_res
        context, file_listing, project_name, use_cache = prep_res
        
        # Count files from file listing
        file_count = len(file_listing.split('\n')) if file_listing else 0
        
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
        else:
            project_size = "Large"
            base_effort = "30-45 person-days"
            team_size = "3-4 developers" 
            timeline = "2-3 months"
        
        # Create a fallback response with realistic estimates
        fallback_analysis = {
            "executive_summary": {
                "migration_impact": f"Analysis of {file_count} files indicates a {project_size.lower()} project requiring Spring 5 to 6 migration. Based on project size, estimated effort is {base_effort}. LLM analysis encountered parsing issues, manual review recommended.",
                "key_blockers": ["LLM response parsing failed - manual code review required", "Potential javax.* to jakarta.* namespace changes", "Spring Security configuration updates may be needed"],
                "recommended_approach": f"Phased migration approach recommended for {project_size.lower()} projects. Start with dependency updates, then tackle deprecated APIs systematically. Consider manual code review due to analysis parsing issues."
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
            "module_breakdown": [
                {
                    "module_name": "main_application",
                    "complexity": "Medium",
                    "refactor_type": "Semi-manual",
                    "issues": ["Manual review required due to analysis parsing issues"],
                    "effort_estimate": base_effort
                }
            ],
            "effort_estimation": {
                "total_effort": base_effort,
                "by_category": {
                    "jakarta_migration": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "security_updates": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "dependency_updates": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "testing": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "build_config": f"{int(base_effort.split('-')[0]) // 6} person-days"
                },
                "priority_levels": {
                    "high": [f"Manual code review of {file_count} files due to analysis parsing issues", "Dependency version updates", "Testing migration"],
                    "medium": ["Configuration optimization", "Performance validation"],
                    "low": ["Documentation updates", "Code style improvements"]
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
                    "title": "Manual Code Review",
                    "description": "Perform manual analysis due to automated parsing issues",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "dependencies": []
                },
                {
                    "step": 2,
                    "title": "Dependency Updates",
                    "description": "Update Spring Boot to 3.x and related dependencies",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 4} person-days",
                    "dependencies": ["step-1"]
                },
                {
                    "step": 3,
                    "title": "Jakarta Migration",
                    "description": "Replace javax.* imports with jakarta.* equivalents",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "dependencies": ["step-2"]
                },
                {
                    "step": 4,
                    "title": "Testing and Validation",
                    "description": "Comprehensive testing of migrated application",
                    "estimated_effort": f"{int(base_effort.split('-')[0]) // 3} person-days",
                    "dependencies": ["step-3"]
                }
            ]
        }
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
        
        prompt = f"""Based on the Spring migration analysis for project `{project_name}`, create a detailed, actionable migration plan.

## Analysis Results:
{json.dumps(analysis, indent=2)}

Generate a comprehensive migration plan in JSON format with REALISTIC estimates based on the analysis:

**Guidelines for Realistic Estimates:**
- Small projects (5-15 person-days): 1-2 developers, 2-6 weeks timeline
- Medium projects (15-30 person-days): 2-3 developers, 6-12 weeks timeline  
- Large projects (30-60 person-days): 3-5 developers, 3-6 months timeline

**Team Size Guidelines:**
- 1-2 developers: Small projects, simple migrations
- 2-3 developers: Medium projects, moderate complexity
- 3-5 developers: Large projects, high complexity
- NEVER recommend more than 5 developers for a migration project

**Timeline Guidelines:**
- Include time for testing, validation, and deployment
- Account for parallel development work
- Consider team availability and other project commitments

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

Focus on practical, actionable steps that a development team can follow."""

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
            
            # Basic validation
            required_keys = ["migration_strategy", "phase_breakdown", "automation_recommendations", "testing_strategy"]
            for key in required_keys:
                if key not in plan:
                    print(f"Warning: Missing required key in plan: {key}")
                    plan[key] = self._get_default_plan_value(key)
            
            return plan
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error in migration plan: {e}")
            print(f"Response content (first 500 chars): {response[:500]}")
            return self._get_fallback_plan(analysis, project_name)
        except Exception as e:
            print(f"Error processing migration plan LLM response: {e}")
            return self._get_fallback_plan(analysis, project_name)
    
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
                "rationale": "Manual plan generation required due to parsing issues",
                "estimated_timeline": "To be determined manually",
                "team_size_recommendation": "2-3 developers"
            },
            "phase_breakdown": [
                {
                    "phase": 1,
                    "name": "Manual Planning Required",
                    "description": "LLM plan generation failed - manual planning recommended",
                    "duration": "TBD",
                    "deliverables": ["Manual migration plan"],
                    "tasks": [],
                    "risks": ["Plan generation failed"],
                    "success_criteria": ["Manual plan created"]
                }
            ],
            "automation_recommendations": [
                {
                    "tool": "Manual Review",
                    "purpose": "Plan generation failed - manual review required",
                    "setup_instructions": "Review migration analysis and create plan manually",
                    "coverage": "100% manual"
                }
            ],
            "manual_changes": [
                {
                    "category": "Plan Generation",
                    "changes": ["Manual planning required"],
                    "rationale": "LLM plan parsing failed"
                }
            ],
            "testing_strategy": {
                "unit_tests": "To be determined manually",
                "integration_tests": "To be determined manually",
                "regression_testing": "To be determined manually"
            },
            "rollback_plan": {
                "triggers": ["Migration failure"],
                "steps": ["Restore from backup"],
                "data_considerations": "Manual assessment required"
            },
            "success_metrics": [
                {
                    "metric": "Manual Assessment",
                    "target": "TBD",
                    "measurement_method": "Manual review"
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


class FileBackupManager(Node):
    """
    Creates backups of files before applying migration changes.
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
        os.makedirs(backup_dir, exist_ok=True)
        
        print(f"📦 Creating backup of {len(files_data)} files...")
        
        backup_info = {
            "backup_dir": backup_dir,
            "timestamp": timestamp,
            "files_backed_up": []
        }
        
        for i, (file_path, content) in enumerate(files_data):
            # Create backup file path
            backup_file_path = os.path.join(backup_dir, file_path.replace("/", "_").replace("\\", "_"))
            
            # Write backup file
            with open(backup_file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            backup_info["files_backed_up"].append({
                "original_path": file_path,
                "backup_path": backup_file_path
            })
            
            if (i + 1) % 10 == 0:
                print(f"   Backed up {i + 1}/{len(files_data)} files...")
        
        # Create backup manifest
        manifest_path = os.path.join(backup_dir, "backup_manifest.json")
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(backup_info, f, indent=2)
        
        print(f"✅ Backup completed: {backup_dir}")
        return backup_info
    
    def post(self, shared, prep_res, exec_res):
        shared["backup_info"] = exec_res
        return "default"


class MigrationChangeGenerator(Node):
    """
    Enhanced change generator with concurrent file processing capabilities.
    """
    
    def prep(self, shared):
        files_data = shared["files"]
        analysis = shared["migration_analysis"]
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        optimization_settings = shared.get("optimization_settings", {})
        
        return files_data, analysis, project_name, use_cache, optimization_settings
    
    def exec(self, prep_res):
        monitor = get_performance_monitor()
        monitor.start_operation("migration_change_generation")
        
        files_data, analysis, project_name, use_cache, optimization_settings = prep_res
        
        print(f"🔧 Generating specific migration changes using LLM analysis...")
        
        # Check if we should use concurrent processing
        enable_parallel = optimization_settings.get("enable_parallel_processing", False)
        batch_size = optimization_settings.get("batch_size", 10)
        
        changes = {
            "javax_to_jakarta": [],
            "spring_security_updates": [],
            "dependency_updates": [],
            "configuration_updates": [],
            "other_changes": []
        }
        
        if enable_parallel and len(files_data) > batch_size:
            print("⚡ Using concurrent change generation...")
            concurrent_manager = ConcurrentAnalysisManager(max_workers=4)
            
            def analyze_file_wrapper(file_path, content):
                return self._analyze_file_with_llm(file_path, content, analysis, project_name, use_cache)
            
            try:
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
                
                file_changes = self._analyze_file_with_llm(file_path, content, analysis, project_name, use_cache)
                
                for change_type, file_change_list in file_changes.items():
                    changes[change_type].extend(file_change_list)
        
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
        
        prompt = f"""# Spring Migration Change Analysis

You are analyzing a file from project `{project_name}` for Spring 5 to 6 migration. Based on the overall migration analysis and the specific file content, generate precise, actionable changes.

## Overall Migration Analysis Context:
{analysis_context}

## File to Analyze:
**File Path:** {file_path}
**File Type:** {self._get_file_type(file_path)}
**File Content:**
```
{clean_content}
```

## Your Task:
Analyze this specific file and identify ALL changes needed for Spring 5 to 6 migration. For each change, determine:

1. **Change Type** (javax_to_jakarta, spring_security_updates, dependency_updates, configuration_updates, other_changes)
2. **Safety Level** (automatic vs manual_review_required)
3. **Specific transformation details**

## IMPORTANT JSON Output Rules:
- Return ONLY valid JSON, no additional text
- Escape all special characters in strings (quotes, backslashes, etc.)
- Keep descriptions short and simple
- Avoid including raw file content in JSON strings
- Use simple English descriptions

## Output Format:
Return ONLY a JSON object with this exact structure:

```json
{{
  "javax_to_jakarta": [
    {{
      "file": "{file_path}",
      "type": "import_replacement",
      "from": "javax.specific.package",
      "to": "jakarta.specific.package", 
      "description": "Replace javax import with jakarta import",
      "line_numbers": [5],
      "automatic": true,
      "explanation": "Standard javax to jakarta namespace migration"
    }}
  ],
  "spring_security_updates": [],
  "dependency_updates": [],
  "configuration_updates": [],
  "other_changes": []
}}
```

## Guidelines:
- **Be specific**: Include exact line numbers, package names
- **Be conservative**: Mark complex changes as `requires_manual_review: true`
- **Be accurate**: Only suggest changes that are actually needed for this file
- **Empty arrays**: If no changes needed in a category, return empty array `[]`
- **Line numbers**: Count from 1, include affected lines
- **Simple strings**: Keep all string values simple and short
- **No raw content**: Never include raw file content in JSON responses

Now analyze the file and return ONLY the JSON (no additional text):"""

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            
            # Clean and extract JSON from response
            json_str = self._extract_and_clean_json(response, file_path)
            if not json_str:
                print(f"     No valid JSON found in LLM response for {file_path}")
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
            
            return file_changes
            
        except json.JSONDecodeError as e:
            print(f"     JSON parsing error for {file_path}: {e}")
            return self._get_empty_changes()
        except Exception as e:
            print(f"     Error analyzing {file_path}: {e}")
            return self._get_empty_changes()
    
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
        """Extract and clean JSON from LLM response."""
        try:
            # Clean the response
            response = response.strip()
            
            # Try to find JSON block in response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif response.startswith("{") and response.endswith("}"):
                # Assume entire response is JSON
                json_str = response
            else:
                # Try to find JSON-like content
                import re
                json_match = re.search(r'\{.*\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return None
            
            # Clean up JSON string
            json_str = json_str.strip()
            
            # Remove any trailing incomplete content
            json_str = json_str.rstrip(',\n\r\t ')
            
            # Basic bracket/brace balancing
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            if open_braces > close_braces:
                json_str += '}' * (open_braces - close_braces)
            
            open_brackets = json_str.count('[')
            close_brackets = json_str.count(']')
            if open_brackets > close_brackets:
                json_str += ']' * (open_brackets - close_brackets)
            
            # Test parse to validate
            json.loads(json_str)
            return json_str
            
        except Exception as e:
            print(f"     JSON extraction/cleaning failed for {file_path}: {e}")
            return None
    
    def _create_analysis_context(self, analysis):
        """Create a concise context from the migration analysis for the LLM."""
        context = "Key Migration Issues Identified:\n"
        
        # Extract key findings from analysis
        if "executive_summary" in analysis:
            summary = analysis["executive_summary"]
            context += f"- Migration Impact: {summary.get('migration_impact', 'Unknown')}\n"
            if "key_blockers" in summary:
                context += "- Key Blockers:\n"
                for blocker in summary["key_blockers"][:3]:  # Top 3 blockers
                    context += f"  * {blocker}\n"
        
        # Add specific areas of concern
        if "detailed_analysis" in analysis:
            detailed = analysis["detailed_analysis"]
            
            if "jakarta_migration" in detailed and detailed["jakarta_migration"].get("javax_usages"):
                context += "- javax.* packages detected - need jakarta.* migration\n"
            
            if "security_migration" in detailed and detailed["security_migration"].get("websecurity_adapter_usage"):
                context += "- WebSecurityConfigurerAdapter usage detected - needs SecurityFilterChain migration\n"
            
            if "build_tooling" in detailed and detailed["build_tooling"].get("build_file_issues"):
                context += "- Build configuration issues detected\n"
        
        return context
    
    def _is_text_file(self, file_path, content):
        """Check if file is a text file suitable for analysis."""
        # Check by extension
        text_extensions = {'.java', '.xml', '.properties', '.yml', '.yaml', '.gradle', '.sql', '.jsp', '.jspx', '.tag', '.tagx'}
        if any(file_path.endswith(ext) for ext in text_extensions):
            return True
        
        # Check for binary content
        try:
            # Try to encode as UTF-8
            content.encode('utf-8')
            # Check for null bytes (common in binary files)
            if '\x00' in content:
                return False
            return True
        except UnicodeEncodeError:
            return False
    
    def _validate_change(self, change, file_path):
        """Validate that a change has the required fields."""
        required_fields = ["file", "type", "description"]
        
        for field in required_fields:
            if field not in change:
                print(f"     Warning: Missing field '{field}' in change for {file_path}")
                return False
        
        # Ensure file path matches
        if change["file"] != file_path:
            change["file"] = file_path  # Correct it
        
        return True
    
    def _get_empty_changes(self):
        """Return empty changes structure."""
        return {
            "javax_to_jakarta": [],
            "spring_security_updates": [],
            "dependency_updates": [],
            "configuration_updates": [],
            "other_changes": []
        }
    
    def _analyze_file_for_changes(self, file_path, content, analysis, use_cache):
        """Legacy method - now redirects to LLM analysis."""
        return self._analyze_file_with_llm(file_path, content, analysis, "project", use_cache)
    
    def post(self, shared, prep_res, exec_res):
        shared["migration_changes"] = exec_res
        
        # Count total changes
        total_changes = sum(len(changes) for changes in exec_res.values())
        print(f"✅ Generated {total_changes} specific migration changes using LLM analysis")
        
        return "default"


class ChangeConfirmationNode(Node):
    """
    Shows users what changes will be made and asks for confirmation.
    """
    
    def prep(self, shared):
        changes = shared["migration_changes"]
        return changes
    
    def exec(self, prep_res):
        changes = prep_res
        
        print("\n" + "="*80)
        print("🔍 SPRING MIGRATION CHANGES PREVIEW")
        print("="*80)
        
        total_changes = sum(len(change_list) for change_list in changes.values())
        
        if total_changes == 0:
            print("No automatic changes identified. Manual review may still be needed.")
            return {"approved": False, "reason": "no_changes"}
        
        print(f"\nFound {total_changes} changes across {len([k for k, v in changes.items() if v])} categories:\n")
        
        # Display changes by category
        for category, change_list in changes.items():
            if change_list:
                category_display = category.replace("_", " ").title()
                print(f"📂 {category_display} ({len(change_list)} changes):")
                
                for i, change in enumerate(change_list[:5]):  # Show first 5 changes
                    print(f"   {i+1}. {change['file']}: {change['description']}")
                
                if len(change_list) > 5:
                    print(f"   ... and {len(change_list) - 5} more changes")
                print()
        
        # Ask for user confirmation
        print("⚠️  IMPORTANT: This will modify your source files!")
        print("   - A backup has been created automatically")
        print("   - Changes can be reviewed and undone if needed")
        print("   - Some changes may require manual review")
        
        while True:
            user_input = input("\n🤔 Apply these migration changes? [y/N/preview]: ").strip().lower()
            
            if user_input in ['y', 'yes']:
                return {"approved": True, "changes": changes}
            elif user_input in ['n', 'no', '']:
                return {"approved": False, "reason": "user_declined"}
            elif user_input in ['p', 'preview']:
                self._show_detailed_preview(changes)
                continue
            else:
                print("Please enter 'y' for yes, 'n' for no, or 'preview' to see details")
    
    def _show_detailed_preview(self, changes):
        """Show detailed preview of changes"""
        print("\n" + "-"*60)
        print("DETAILED CHANGE PREVIEW")
        print("-"*60)
        
        for category, change_list in changes.items():
            if change_list:
                category_display = category.replace("_", " ").title()
                print(f"\n📂 {category_display}:")
                
                for change in change_list:
                    print(f"   File: {change['file']}")
                    print(f"   Type: {change['type']}")
                    print(f"   Description: {change['description']}")
                    
                    if 'from' in change and 'to' in change:
                        print(f"   Change: {change['from']} → {change['to']}")
                    
                    if change.get('requires_manual_review'):
                        print("   ⚠️  Manual review required")
                    
                    print()
        
        print("-"*60)
    
    def post(self, shared, prep_res, exec_res):
        shared["change_approval"] = exec_res
        
        if exec_res["approved"]:
            print("✅ Changes approved by user")
            return "apply_changes"
        else:
            print("❌ Changes not approved - skipping application")
            return "skip_changes"


class MigrationChangeApplicator(Node):
    """
    Applies the approved migration changes to files.
    """
    
    def prep(self, shared):
        changes = shared["migration_changes"]
        approval = shared["change_approval"]
        
        if not approval["approved"]:
            return None
        
        # Only proceed if we have a local directory (not GitHub repo)
        local_dir = shared.get("local_dir")
        if not local_dir:
            print("⚠️  Cannot apply changes to GitHub repository. Changes can only be applied to local directories.")
            return None
        
        return changes, local_dir
    
    def exec(self, prep_res):
        if prep_res is None:
            return {"applied": False, "reason": "not_approved_or_not_local"}
        
        changes, local_dir = prep_res
        
        print(f"🔧 Applying migration changes to {local_dir}...")
        
        applied_changes = {
            "successful": [],
            "failed": [],
            "skipped": []
        }
        
        # Apply javax to jakarta changes (automatic)
        for change in changes.get("javax_to_jakarta", []):
            if change.get("automatic", True):  # Default to automatic for javax→jakarta
                try:
                    result = self._apply_import_replacement(change, local_dir)
                    if result:
                        applied_changes["successful"].append(change)
                    else:
                        applied_changes["skipped"].append(change)
                except Exception as e:
                    change["error"] = str(e)
                    applied_changes["failed"].append(change)
            else:
                applied_changes["skipped"].append({**change, "reason": "requires_manual_review"})
        
        # Apply configuration updates (if marked as automatic)
        for change in changes.get("configuration_updates", []):
            if change.get("automatic", False) and not change.get("requires_manual_review", True):
                try:
                    result = self._apply_configuration_update(change, local_dir)
                    if result:
                        applied_changes["successful"].append(change)
                    else:
                        applied_changes["skipped"].append(change)
                except Exception as e:
                    change["error"] = str(e)
                    applied_changes["failed"].append(change)
            else:
                applied_changes["skipped"].append({**change, "reason": "requires_manual_review"})
        
        # Skip complex changes that require manual review
        manual_review_categories = ["spring_security_updates", "dependency_updates", "other_changes"]
        for category in manual_review_categories:
            for change in changes.get(category, []):
                applied_changes["skipped"].append({**change, "reason": "requires_manual_review"})
        
        return applied_changes
    
    def _apply_import_replacement(self, change, local_dir):
        """Apply javax to jakarta import replacements using enhanced change info."""
        import os
        
        file_path = os.path.join(local_dir, change["file"])
        
        if not os.path.exists(file_path):
            print(f"   ⚠️  File not found: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Get change details
            from_package = change.get("from", "")
            to_package = change.get("to", "")
            
            if not from_package or not to_package:
                print(f"   ⚠️  Missing from/to packages in change: {change}")
                return False
            
            changes_made = 0
            
            # Replace import statements
            import_pattern = f"import {from_package}"
            if import_pattern in content:
                content = content.replace(import_pattern, f"import {to_package}")
                changes_made += 1
            
            # Replace static imports
            static_import_pattern = f"import static {from_package}"
            if static_import_pattern in content:
                content = content.replace(static_import_pattern, f"import static {to_package}")
                changes_made += 1
            
            # Replace fully qualified class names (more conservative)
            # Only replace if it's clearly a package reference (followed by a dot and capital letter)
            import re
            qualified_pattern = re.compile(rf'\b{re.escape(from_package)}\.([A-Z][a-zA-Z0-9_]*)', re.MULTILINE)
            matches = qualified_pattern.findall(content)
            if matches:
                content = qualified_pattern.sub(rf'{to_package}.\1', content)
                changes_made += len(matches)
            
            if content != original_content and changes_made > 0:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"   ✅ Applied: {change['file']} - {from_package} → {to_package} ({changes_made} changes)")
                return True
            else:
                print(f"   ℹ️  No changes needed: {change['file']} - {from_package}")
                return False
                
        except Exception as e:
            print(f"   ❌ Failed to apply change to {change['file']}: {e}")
            raise e
    
    def _apply_configuration_update(self, change, local_dir):
        """Apply configuration property updates."""
        import os
        
        file_path = os.path.join(local_dir, change["file"])
        
        if not os.path.exists(file_path):
            print(f"   ⚠️  File not found: {file_path}")
            return False
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Get property change details
            from_property = change.get("from_property", "")
            to_property = change.get("to_property", "")
            
            if not from_property or not to_property:
                print(f"   ⚠️  Missing from_property/to_property in change: {change}")
                return False
            
            # Handle different file types
            if file_path.endswith(('.properties', '.yml', '.yaml')):
                if file_path.endswith('.properties'):
                    # Properties file format: key=value
                    if f"{from_property}=" in content:
                        content = content.replace(f"{from_property}=", f"{to_property}=")
                else:
                    # YAML format: key: value
                    if f"{from_property}:" in content:
                        content = content.replace(f"{from_property}:", f"{to_property}:")
                
                if content != original_content:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"   ✅ Applied: {change['file']} - {from_property} → {to_property}")
                    return True
                else:
                    print(f"   ℹ️  Property not found: {change['file']} - {from_property}")
                    return False
            else:
                print(f"   ⚠️  Unsupported file type for configuration update: {file_path}")
                return False
                
        except Exception as e:
            print(f"   ❌ Failed to apply configuration change to {change['file']}: {e}")
            raise e
    
    def _apply_dependency_update(self, change, local_dir):
        """Apply dependency updates to build files."""
        # This is intentionally conservative - dependency updates should be manual
        print(f"   ⚠️  Dependency update marked for manual review: {change['file']}")
        return False
    
    def post(self, shared, prep_res, exec_res):
        if prep_res is None:
            print("⏭️  Change application skipped")
            return "default"
        
        shared["applied_changes"] = exec_res
        
        successful = len(exec_res["successful"])
        failed = len(exec_res["failed"])  
        skipped = len(exec_res["skipped"])
        
        print(f"\n📊 Change Application Summary:")
        print(f"   ✅ Successfully applied: {successful}")
        print(f"   ⏭️  Skipped (manual review): {skipped}")
        print(f"   ❌ Failed: {failed}")
        
        if successful > 0:
            print(f"\n✅ Successfully applied changes:")
            for change in exec_res["successful"]:
                print(f"   - {change['file']}: {change['description']}")
        
        if failed > 0:
            print(f"\n❌ Failed changes:")
            for change in exec_res["failed"]:
                print(f"   - {change['file']}: {change.get('error', 'Unknown error')}")
        
        return "default"


class MigrationReportGenerator(Node):
    """
    Enhanced report generator with performance metrics.
    """
    
    def prep(self, shared):
        analysis = shared["migration_analysis"]
        plan = shared["migration_plan"]
        dependency_compatibility = shared.get("dependency_compatibility", {})
        project_name = shared["project_name"]
        output_dir = shared["output_dir"]
        backup_info = shared.get("backup_info")
        applied_changes = shared.get("applied_changes")
        files_data = shared.get("files", [])  # Add files data for performance metrics
        
        return analysis, plan, dependency_compatibility, project_name, output_dir, backup_info, applied_changes, files_data
    
    def exec(self, prep_res):
        monitor = get_performance_monitor()
        monitor.start_operation("report_generation")
        
        analysis, plan, dependency_compatibility, project_name, output_dir, backup_info, applied_changes, files_data = prep_res
        
        # Create comprehensive report with performance metrics
        report = {
            "project_name": project_name,
            "analysis_date": None,  # Will be set in post()
            "migration_analysis": analysis,
            "migration_plan": plan,
            "dependency_compatibility": dependency_compatibility,
            "backup_info": backup_info,
            "applied_changes": applied_changes,
            "performance_metrics": monitor.get_performance_summary(),
            "recommendations": {
                "immediate_actions": [],
                "long_term_considerations": [],
                "risk_mitigation": [],
                "performance_optimizations": monitor.generate_optimization_recommendations(
                    total_files=len(files_data),
                    total_size_mb=sum(len(content) for _, content in files_data) / 1024 / 1024
                )
            }
        }
        
        # Extract immediate actions from high-priority items
        if "effort_estimation" in analysis and "priority_levels" in analysis["effort_estimation"]:
            report["recommendations"]["immediate_actions"] = analysis["effort_estimation"]["priority_levels"].get("high", [])
        
        # Add change application summary
        if applied_changes:
            report["change_summary"] = {
                "automatic_changes_applied": len(applied_changes.get("successful", [])),
                "changes_requiring_manual_review": len(applied_changes.get("skipped", [])),
                "failed_changes": len(applied_changes.get("failed", []))
            }
        
        monitor.end_operation("report_generation", files_processed=1)
        return report
    
    def post(self, shared, prep_res, exec_res):
        import json
        import os
        from datetime import datetime
        
        monitor = get_performance_monitor()
        
        analysis, plan, dependency_compatibility, project_name, output_dir, backup_info, applied_changes, files_data = prep_res
        report = exec_res
        
        # Add timestamp
        report["analysis_date"] = datetime.now().isoformat()
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save detailed JSON report
        json_file = os.path.join(output_dir, f"{project_name}_spring_migration_report.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Save performance report
        performance_file = os.path.join(output_dir, f"{project_name}_performance_report.json")
        monitor.save_performance_report(performance_file)
        
        # Save human-readable summary with performance info
        summary_file = os.path.join(output_dir, f"{project_name}_migration_summary.md")
        self._generate_enhanced_summary(summary_file, report, monitor)
        
        shared["final_output_dir"] = output_dir
        
        print(f"✅ Enhanced migration report saved to:")
        print(f"   📄 Detailed report: {json_file}")
        print(f"   📋 Summary: {summary_file}")
        print(f"   📊 Performance: {performance_file}")
        
        if backup_info:
            print(f"   📦 Backup: {backup_info['backup_dir']}")
        
        # Print performance summary
        perf_summary = monitor.get_performance_summary()
        print(f"\n⚡ Performance Summary:")
        print(f"   Total Duration: {perf_summary['overall_duration']:.1f}s")
        print(f"   Files Processed: {perf_summary['total_files_processed']}")
        print(f"   LLM Calls: {perf_summary['total_llm_calls']}")
        print(f"   Peak Memory: {perf_summary['peak_memory_mb']:.1f} MB")
        
        if perf_summary['optimization_recommendations']:
            print(f"   💡 Optimizations available - see performance report")
        
        return "default"
    
    def _generate_enhanced_summary(self, summary_file, report, monitor):
        """Generate enhanced summary with performance metrics."""
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# Spring 5 to 6 Migration Analysis & Implementation Report\n\n")
            f.write(f"**Project:** {report['project_name']}\n")
            f.write(f"**Analysis Date:** {report['analysis_date']}\n\n")
            
            # Performance Summary
            perf_summary = report.get('performance_metrics', {})
            if perf_summary:
                f.write("## Performance Summary\n\n")
                f.write(f"**Total Analysis Time:** {perf_summary.get('overall_duration', 0):.1f} seconds\n")
                f.write(f"**Files Processed:** {perf_summary.get('total_files_processed', 0)}\n")
                f.write(f"**LLM Calls Made:** {perf_summary.get('total_llm_calls', 0)}\n")
                f.write(f"**Peak Memory Usage:** {perf_summary.get('peak_memory_mb', 0):.1f} MB\n")
                f.write(f"**Processing Rate:** {perf_summary.get('files_per_second', 0):.1f} files/second\n\n")
                
                # Performance optimizations
                optimizations = report['recommendations'].get('performance_optimizations', [])
                if optimizations:
                    f.write("### Performance Optimization Recommendations\n")
                    for opt in optimizations:
                        f.write(f"- {opt}\n")
                    f.write("\n")
            
            # ... rest of existing summary generation ...


class GitOperationsManager(Node):
    """
    Manages Git operations for migration changes - comparison, branching, and pushing.
    """
    
    def prep(self, shared):
        local_dir = shared.get("local_dir")
        applied_changes = shared.get("applied_changes")
        project_name = shared["project_name"]
        git_integration = shared.get("git_integration", False)
        
        if not local_dir:
            return None  # Skip Git operations for GitHub repos
        
        if not git_integration:
            return None  # Skip Git operations if not enabled
        
        return local_dir, applied_changes, project_name
    
    def exec(self, prep_res):
        if prep_res is None:
            return {"skipped": True, "reason": "Not a local repository"}
        
        import os
        import subprocess
        from datetime import datetime
        
        local_dir, applied_changes, project_name = prep_res
        
        print(f"🔀 Managing Git operations for Spring migration...")
        
        # Check if directory is a Git repository
        if not os.path.exists(os.path.join(local_dir, '.git')):
            print(f"   ⚠️  Directory is not a Git repository: {local_dir}")
            return {"skipped": True, "reason": "Not a Git repository"}
        
        # Change to the repository directory
        original_cwd = os.getcwd()
        os.chdir(local_dir)
        
        try:
            git_operations = {
                "repository_status": self._get_repository_status(),
                "changes_summary": self._analyze_git_changes(),
                "branch_info": self._get_branch_info(),
                "commit_prepared": False,
                "push_ready": False
            }
            
            # Check if there are any changes to commit
            if git_operations["changes_summary"]["has_changes"]:
                # Create a migration branch
                branch_name = self._create_migration_branch(project_name)
                git_operations["migration_branch"] = branch_name
                
                # Stage the changes
                self._stage_migration_changes()
                git_operations["changes_staged"] = True
                
                # Show diff summary
                git_operations["diff_summary"] = self._get_diff_summary()
                
                # Ask user if they want to commit and push
                commit_decision = self._ask_commit_decision(git_operations)
                
                if commit_decision["commit"]:
                    # Create commit
                    commit_hash = self._create_migration_commit(applied_changes, project_name)
                    git_operations["commit_hash"] = commit_hash
                    git_operations["commit_prepared"] = True
                    
                    if commit_decision["push"]:
                        # Push to remote
                        push_result = self._push_migration_branch(branch_name)
                        git_operations["push_result"] = push_result
                        git_operations["push_ready"] = True
                        
                        # Generate pull request info
                        git_operations["pull_request_info"] = self._generate_pr_info(project_name, applied_changes)
            
            return git_operations
            
        except Exception as e:
            print(f"   ❌ Git operations failed: {e}")
            return {"error": str(e), "skipped": True}
        finally:
            os.chdir(original_cwd)
    
    def _get_repository_status(self):
        """Get current Git repository status."""
        try:
            import subprocess
            
            # Get current branch
            current_branch = subprocess.check_output(
                ["git", "branch", "--show-current"], 
                text=True
            ).strip()
            
            # Get repository remote info
            try:
                remote_url = subprocess.check_output(
                    ["git", "config", "--get", "remote.origin.url"],
                    text=True
                ).strip()
            except:
                remote_url = "No remote configured"
            
            # Check if working directory is clean
            status_output = subprocess.check_output(
                ["git", "status", "--porcelain"],
                text=True
            ).strip()
            
            return {
                "current_branch": current_branch,
                "remote_url": remote_url,
                "is_clean": len(status_output) == 0,
                "modified_files": len(status_output.split('\n')) if status_output else 0
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _analyze_git_changes(self):
        """Analyze what changes are present in the working directory."""
        try:
            import subprocess
            
            # Get status of all files
            status_output = subprocess.check_output(
                ["git", "status", "--porcelain"],
                text=True
            ).strip()
            
            if not status_output:
                return {"has_changes": False, "summary": "No changes detected"}
            
            changes = {"modified": [], "added": [], "deleted": [], "untracked": []}
            
            for line in status_output.split('\n'):
                if len(line) >= 3:
                    status = line[:2]
                    filename = line[3:]
                    
                    if status.startswith('M'):
                        changes["modified"].append(filename)
                    elif status.startswith('A'):
                        changes["added"].append(filename)
                    elif status.startswith('D'):
                        changes["deleted"].append(filename)
                    elif status.startswith('??'):
                        changes["untracked"].append(filename)
            
            total_changes = sum(len(files) for files in changes.values())
            
            return {
                "has_changes": True,
                "total_changes": total_changes,
                "changes": changes,
                "summary": f"{total_changes} files changed"
            }
            
        except Exception as e:
            return {"error": str(e), "has_changes": False}
    
    def _get_branch_info(self):
        """Get information about Git branches."""
        try:
            import subprocess
            
            # List all branches
            branches = subprocess.check_output(
                ["git", "branch", "-a"],
                text=True
            ).strip().split('\n')
            
            return {
                "all_branches": [b.strip().replace('*', '').strip() for b in branches],
                "current_branch": subprocess.check_output(
                    ["git", "branch", "--show-current"],
                    text=True
                ).strip()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def _create_migration_branch(self, project_name):
        """Create a new branch for migration changes."""
        import subprocess
        from datetime import datetime
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"spring-migration-{timestamp}"
        
        try:
            # Create and checkout new branch
            subprocess.run(
                ["git", "checkout", "-b", branch_name],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"   ✅ Created migration branch: {branch_name}")
            return branch_name
        except subprocess.CalledProcessError as e:
            print(f"   ⚠️  Failed to create branch: {e}")
            return None
    
    def _stage_migration_changes(self):
        """Stage all migration-related changes."""
        import subprocess
        
        try:
            # Add all changes (be careful - this adds everything)
            subprocess.run(
                ["git", "add", "."],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"   ✅ Staged all migration changes")
            return True
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to stage changes: {e}")
            return False
    
    def _get_diff_summary(self):
        """Get a summary of the staged changes."""
        import subprocess
        
        try:
            # Get diff stats
            diff_stats = subprocess.check_output(
                ["git", "diff", "--cached", "--stat"],
                text=True
            ).strip()
            
            # Get number of changed files
            diff_numstat = subprocess.check_output(
                ["git", "diff", "--cached", "--numstat"],
                text=True
            ).strip()
            
            if not diff_numstat:
                return {"summary": "No staged changes", "files_changed": 0}
            
            lines = diff_numstat.split('\n')
            files_changed = len(lines)
            
            total_additions = 0
            total_deletions = 0
            
            for line in lines:
                parts = line.split('\t')
                if len(parts) >= 2:
                    try:
                        additions = int(parts[0]) if parts[0] != '-' else 0
                        deletions = int(parts[1]) if parts[1] != '-' else 0
                        total_additions += additions
                        total_deletions += deletions
                    except ValueError:
                        continue
            
            return {
                "summary": diff_stats,
                "files_changed": files_changed,
                "additions": total_additions,
                "deletions": total_deletions
            }
            
        except Exception as e:
            return {"error": str(e)}
    
    def _ask_commit_decision(self, git_operations):
        """Ask user whether to commit and push changes."""
        print("\n" + "="*60)
        print("🔀 GIT OPERATIONS SUMMARY")
        print("="*60)
        
        print(f"📊 Changes Summary:")
        if git_operations["changes_summary"]["has_changes"]:
            changes = git_operations["changes_summary"]["changes"]
            print(f"   📝 Modified files: {len(changes.get('modified', []))}")
            print(f"   ➕ Added files: {len(changes.get('added', []))}")
            print(f"   ➖ Deleted files: {len(changes.get('deleted', []))}")
            print(f"   ❓ Untracked files: {len(changes.get('untracked', []))}")
        
        if "diff_summary" in git_operations:
            diff = git_operations["diff_summary"]
            print(f"\n📈 Diff Summary:")
            print(f"   Files changed: {diff.get('files_changed', 0)}")
            print(f"   Lines added: +{diff.get('additions', 0)}")
            print(f"   Lines deleted: -{diff.get('deletions', 0)}")
        
        print(f"\n🌿 Branch: {git_operations.get('migration_branch', 'unknown')}")
        print(f"🏠 Repository: {git_operations['repository_status'].get('remote_url', 'unknown')}")
        
        # Ask for commit decision
        print("\n" + "="*60)
        while True:
            commit_choice = input("💾 Commit these migration changes? [y/N]: ").strip().lower()
            if commit_choice in ['y', 'yes']:
                commit_decision = True
                break
            elif commit_choice in ['n', 'no', '']:
                commit_decision = False
                break
            else:
                print("Please enter 'y' for yes or 'n' for no")
        
        push_decision = False
        if commit_decision:
            while True:
                push_choice = input("🚀 Push to remote repository? [y/N]: ").strip().lower()
                if push_choice in ['y', 'yes']:
                    push_decision = True
                    break
                elif push_choice in ['n', 'no', '']:
                    push_decision = False
                    break
                else:
                    print("Please enter 'y' for yes or 'n' for no")
        
        return {"commit": commit_decision, "push": push_decision}
    
    def _create_migration_commit(self, applied_changes, project_name):
        """Create a commit with migration changes."""
        import subprocess
        from datetime import datetime
        
        # Generate commit message
        successful_changes = len(applied_changes.get("successful", []))
        skipped_changes = len(applied_changes.get("skipped", []))
        
        commit_message = f"""Spring 5 to 6 Migration - Automated Changes

- Applied {successful_changes} automatic migration changes
- {skipped_changes} changes marked for manual review
- Jakarta namespace migration (javax.* → jakarta.*)
- Updated import statements and references

Generated by AI Codebase Migration Tool
Project: {project_name}
Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        try:
            result = subprocess.run(
                ["git", "commit", "-m", commit_message],
                check=True,
                capture_output=True,
                text=True
            )
            
            # Get commit hash
            commit_hash = subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                text=True
            ).strip()
            
            print(f"   ✅ Created commit: {commit_hash[:8]}")
            return commit_hash
            
        except subprocess.CalledProcessError as e:
            print(f"   ❌ Failed to create commit: {e}")
            return None
    
    def _push_migration_branch(self, branch_name):
        """Push the migration branch to remote repository."""
        import subprocess
        
        try:
            # Push branch to origin
            result = subprocess.run(
                ["git", "push", "-u", "origin", branch_name],
                check=True,
                capture_output=True,
                text=True
            )
            
            print(f"   ✅ Pushed branch '{branch_name}' to remote")
            return {"success": True, "branch": branch_name}
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr if e.stderr else str(e)
            print(f"   ❌ Failed to push branch: {error_msg}")
            return {"success": False, "error": error_msg}
    
    def _generate_pr_info(self, project_name, applied_changes):
        """Generate pull request information."""
        successful_changes = len(applied_changes.get("successful", []))
        skipped_changes = len(applied_changes.get("skipped", []))
        
        pr_title = f"Spring 5 to 6 Migration - Automated Changes for {project_name}"
        
        pr_description = f"""## Spring Framework Migration

This pull request contains automated migration changes from Spring 5 to Spring 6.

### Changes Applied
- ✅ **{successful_changes} automatic changes** applied successfully
- ⚠️ **{skipped_changes} changes** require manual review

### Migration Details
- **Jakarta Namespace**: Updated `javax.*` imports to `jakarta.*`
- **Import Updates**: Cleaned up package references
- **Configuration**: Basic property updates where applicable

### Manual Review Required
The following changes were identified but require manual review:
"""
        
        # Add details about skipped changes
        for change in applied_changes.get("skipped", [])[:5]:  # Show first 5
            reason = change.get("reason", "manual review required")
            pr_description += f"- `{change['file']}`: {change['description']} ({reason})\n"
        
        if len(applied_changes.get("skipped", [])) > 5:
            remaining = len(applied_changes.get("skipped", [])) - 5
            pr_description += f"- ... and {remaining} more changes\n"
        
        pr_description += f"""
### Testing
- [ ] Application builds successfully
- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Manual testing completed

### Generated by
🤖 AI Codebase Migration Tool
"""
        
        return {
            "title": pr_title,
            "description": pr_description,
            "labels": ["migration", "spring-6", "jakarta-ee", "automated"]
        }
    
    def post(self, shared, prep_res, exec_res):
        shared["git_operations"] = exec_res
        
        if exec_res.get("skipped"):
            print("⏭️  Git operations skipped")
            return "default"
        
        if exec_res.get("error"):
            print(f"❌ Git operations failed: {exec_res['error']}")
            return "default"
        
        # Print summary
        print(f"\n📋 Git Operations Summary:")
        if exec_res.get("migration_branch"):
            print(f"   🌿 Created branch: {exec_res['migration_branch']}")
        
        if exec_res.get("commit_prepared"):
            commit_hash = exec_res.get("commit_hash", "unknown")
            print(f"   💾 Created commit: {commit_hash[:8] if commit_hash else 'unknown'}")
        
        if exec_res.get("push_ready"):
            print(f"   🚀 Pushed to remote repository")
            
            # Show PR information
            if "pull_request_info" in exec_res:
                pr_info = exec_res["pull_request_info"]
                print(f"\n📝 Ready for Pull Request:")
                print(f"   Title: {pr_info['title']}")
                print(f"   Branch: {exec_res.get('migration_branch')}")
                print(f"   \n💡 Create a pull request on your Git platform with the generated title and description.")
        
        return "default"


class DependencyCompatibilityAnalyzer(Node):
    """
    Enhanced dependency analyzer with concurrent processing capabilities.
    """
    
    def prep(self, shared):
        files_data = shared["files"]
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        optimization_settings = shared.get("optimization_settings", {})
        
        # Extract build files for dependency analysis
        build_files = self._extract_build_files(files_data)
        dependency_info = self._parse_dependencies(build_files)
        
        return dependency_info, project_name, use_cache, optimization_settings
    
    def exec(self, prep_res):
        monitor = get_performance_monitor()
        monitor.start_operation("dependency_compatibility_analysis")
        
        dependency_info, project_name, use_cache, optimization_settings = prep_res
        
        print(f"🔍 Analyzing dependency compatibility with Spring 6...")
        
        # Check if we should use concurrent processing
        enable_parallel = optimization_settings.get("enable_parallel_processing", False)
        
        if enable_parallel and len(dependency_info) > 2:
            print("⚡ Using concurrent dependency analysis...")
            compatibility_analysis = self._analyze_dependencies_concurrently(
                dependency_info, project_name, use_cache
            )
        else:
            compatibility_analysis = self._analyze_dependencies_sequentially(
                dependency_info, project_name, use_cache
            )
        
        # Perform cross-dependency analysis
        compatibility_analysis["dependency_graph"] = self._analyze_dependency_relationships(dependency_info)
        compatibility_analysis["version_conflicts"] = self._detect_version_conflicts(compatibility_analysis)
        compatibility_analysis["migration_roadmap"] = self._generate_dependency_migration_roadmap(compatibility_analysis)
        
        monitor.end_operation("dependency_compatibility_analysis",
                            files_processed=len(dependency_info),
                            llm_calls=len(dependency_info))
        
        return compatibility_analysis
    
    def _analyze_dependencies_concurrently(self, dependency_info, project_name, use_cache):
        """Analyze dependencies using concurrent processing."""
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import threading
        
        compatibility_analysis = {
            "maven_dependencies": [],
            "gradle_dependencies": [],
            "internal_modules": [],
            "spring_dependencies": [],
            "jakarta_dependencies": [],
            "incompatible_dependencies": [],
            "recommended_versions": {},
            "migration_blockers": [],
            "transitive_conflicts": []
        }
        
        # Thread-safe result collection
        results_lock = threading.Lock()
        
        def analyze_single_file(build_file, content):
            try:
                print(f"   Analyzing {build_file} (concurrent)...")
                return self._analyze_build_file_with_llm(build_file, content, project_name, use_cache)
            except Exception as e:
                print(f"   Error analyzing {build_file}: {e}")
                return self._get_empty_dependency_analysis()
        
        # Process files concurrently
        with ThreadPoolExecutor(max_workers=min(4, len(dependency_info))) as executor:
            future_to_file = {
                executor.submit(analyze_single_file, build_file, content): build_file
                for build_file, content in dependency_info.items()
            }
            
            for future in as_completed(future_to_file):
                build_file = future_to_file[future]
                try:
                    file_analysis = future.result()
                    
                    # Merge results thread-safely
                    with results_lock:
                        for category in compatibility_analysis:
                            if category in file_analysis:
                                if isinstance(compatibility_analysis[category], list):
                                    compatibility_analysis[category].extend(file_analysis[category])
                                else:
                                    compatibility_analysis[category].update(file_analysis[category])
                
                except Exception as e:
                    print(f"   Failed to process {build_file}: {e}")
        
        return compatibility_analysis
    
    def _analyze_dependencies_sequentially(self, dependency_info, project_name, use_cache):
        """Analyze dependencies sequentially (existing method)."""
        compatibility_analysis = {
            "maven_dependencies": [],
            "gradle_dependencies": [],
            "internal_modules": [],
            "spring_dependencies": [],
            "jakarta_dependencies": [],
            "incompatible_dependencies": [],
            "recommended_versions": {},
            "migration_blockers": [],
            "transitive_conflicts": []
        }
        
        # Analyze each build file
        for build_file, content in dependency_info.items():
            print(f"   Analyzing {build_file}...")
            file_analysis = self._analyze_build_file_with_llm(build_file, content, project_name, use_cache)
            
            # Merge results
            for category in compatibility_analysis:
                if category in file_analysis:
                    if isinstance(compatibility_analysis[category], list):
                        compatibility_analysis[category].extend(file_analysis[category])
                    else:
                        compatibility_analysis[category].update(file_analysis[category])
        
        return compatibility_analysis
    
    def _extract_build_files(self, files_data):
        """Extract build files (pom.xml, build.gradle, etc.) for dependency analysis."""
        build_files = {}
        
        for file_path, content in files_data:
            if any(file_path.endswith(pattern) for pattern in ['pom.xml', 'build.gradle', 'build.gradle.kts', 'gradle.properties']):
                build_files[file_path] = content
            elif 'dependencies' in file_path.lower() or 'libs' in file_path.lower():
                # Include other dependency-related files
                build_files[file_path] = content
        
        return build_files
    
    def _parse_dependencies(self, build_files):
        """Parse dependencies from build files to extract basic information."""
        parsed_dependencies = {}
        
        for file_path, content in build_files.items():
            if file_path.endswith('pom.xml'):
                parsed_dependencies[file_path] = self._parse_maven_dependencies(content)
            elif file_path.endswith(('.gradle', '.gradle.kts')):
                parsed_dependencies[file_path] = self._parse_gradle_dependencies(content)
            else:
                parsed_dependencies[file_path] = content
        
        return parsed_dependencies
    
    def _parse_maven_dependencies(self, content):
        """Extract Maven dependency information."""
        import re
        
        dependencies = []
        
        # Find dependency blocks
        dependency_pattern = r'<dependency>(.*?)</dependency>'
        dependencies_matches = re.findall(dependency_pattern, content, re.DOTALL)
        
        for dep_block in dependencies_matches:
            group_match = re.search(r'<groupId>(.*?)</groupId>', dep_block)
            artifact_match = re.search(r'<artifactId>(.*?)</artifactId>', dep_block)
            version_match = re.search(r'<version>(.*?)</version>', dep_block)
            
            if group_match and artifact_match:
                dependencies.append({
                    'groupId': group_match.group(1).strip(),
                    'artifactId': artifact_match.group(1).strip(),
                    'version': version_match.group(1).strip() if version_match else 'unknown',
                    'type': 'maven'
                })
        
        return {
            'raw_content': content,
            'parsed_dependencies': dependencies,
            'spring_boot_version': self._extract_spring_boot_version_maven(content),
            'java_version': self._extract_java_version_maven(content)
        }
    
    def _parse_gradle_dependencies(self, content):
        """Extract Gradle dependency information."""
        import re
        
        dependencies = []
        
        # Find dependency declarations
        dependency_patterns = [
            r"implementation\s+['\"]([^'\"]+)['\"]",
            r"compile\s+['\"]([^'\"]+)['\"]",
            r"api\s+['\"]([^'\"]+)['\"]",
            r"testImplementation\s+['\"]([^'\"]+)['\"]"
        ]
        
        for pattern in dependency_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                parts = match.split(':')
                if len(parts) >= 2:
                    dependencies.append({
                        'groupId': parts[0],
                        'artifactId': parts[1],
                        'version': parts[2] if len(parts) > 2 else 'unknown',
                        'type': 'gradle'
                    })
        
        return {
            'raw_content': content,
            'parsed_dependencies': dependencies,
            'spring_boot_version': self._extract_spring_boot_version_gradle(content),
            'java_version': self._extract_java_version_gradle(content)
        }
    
    def _extract_spring_boot_version_maven(self, content):
        """Extract Spring Boot version from Maven pom.xml."""
        import re
        
        # Look for Spring Boot parent
        parent_pattern = r'<parent>.*?<groupId>org\.springframework\.boot</groupId>.*?<version>(.*?)</version>.*?</parent>'
        parent_match = re.search(parent_pattern, content, re.DOTALL)
        if parent_match:
            return parent_match.group(1).strip()
        
        # Look for Spring Boot version property
        version_pattern = r'<spring\.boot\.version>(.*?)</spring\.boot\.version>'
        version_match = re.search(version_pattern, content)
        if version_match:
            return version_match.group(1).strip()
        
        return None
    
    def _extract_spring_boot_version_gradle(self, content):
        """Extract Spring Boot version from Gradle build file."""
        import re
        
        # Look for Spring Boot plugin
        plugin_pattern = r"id\s+['\"]org\.springframework\.boot['\"].*?version\s+['\"]([^'\"]+)['\"]"
        plugin_match = re.search(plugin_pattern, content)
        if plugin_match:
            return plugin_match.group(1).strip()
        
        # Look for version variable
        version_pattern = r"springBootVersion\s*=\s*['\"]([^'\"]+)['\"]"
        version_match = re.search(version_pattern, content)
        if version_match:
            return version_match.group(1).strip()
        
        return None
    
    def _extract_java_version_maven(self, content):
        """Extract Java version from Maven pom.xml."""
        import re
        
        patterns = [
            r'<maven\.compiler\.source>(.*?)</maven\.compiler\.source>',
            r'<maven\.compiler\.target>(.*?)</maven\.compiler\.target>',
            r'<java\.version>(.*?)</java\.version>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_java_version_gradle(self, content):
        """Extract Java version from Gradle build file."""
        import re
        
        patterns = [
            r"sourceCompatibility\s*=\s*['\"]?([^'\"\\s]+)['\"]?",
            r"targetCompatibility\s*=\s*['\"]?([^'\"\\s]+)['\"]?",
            r"javaVersion\s*=\s*['\"]([^'\"]+)['\"]"
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _analyze_build_file_with_llm(self, file_path, content_info, project_name, use_cache):
        """Use LLM to analyze dependency compatibility."""
        
        if isinstance(content_info, dict):
            content = content_info.get('raw_content', str(content_info))
            parsed_deps = content_info.get('parsed_dependencies', [])
            spring_boot_version = content_info.get('spring_boot_version')
            java_version = content_info.get('java_version')
        else:
            content = content_info
            parsed_deps = []
            spring_boot_version = None
            java_version = None
        
        # Truncate content for LLM analysis
        if len(content) > 8000:
            content = content[:8000] + "\\n... [Content truncated for analysis]"
        
        prompt = f"""# Spring 6 Dependency Compatibility Analysis

You are a Spring Framework migration expert analyzing dependency compatibility for Spring 6 migration.

## Project Context:
- **Project**: {project_name}
- **Build File**: {file_path}
- **Current Spring Boot Version**: {spring_boot_version or 'Unknown'}
- **Current Java Version**: {java_version or 'Unknown'}

## Build File Content:
```
{content}
```

## Analysis Requirements:

Analyze ALL dependencies for Spring 6 compatibility and provide a comprehensive assessment.

### 1. Spring Framework Dependencies
- Identify current Spring/Spring Boot versions
- Check compatibility with Spring 6.x and Spring Boot 3.x
- Recommend specific version upgrades

### 2. Jakarta EE Dependencies  
- Find dependencies still using javax.* namespaces
- Identify Jakarta EE compatible versions
- Flag libraries that haven't migrated to Jakarta

### 3. Third-Party Library Compatibility
- Check popular libraries (Hibernate, Jackson, etc.)
- Identify minimum versions required for Spring 6
- Flag incompatible or deprecated libraries

### 4. Java Version Requirements
- Verify Java 17+ compatibility
- Check for deprecated Java features

### 5. Internal Module Dependencies
- Identify internal/custom modules
- Check for Spring version dependencies
- Assess internal API compatibility

### 6. Transitive Dependency Conflicts
- Identify potential version conflicts
- Check for mixing javax.* and jakarta.* dependencies

## CRITICAL: Output ONLY valid JSON with this exact structure:

```json
{{
  "maven_dependencies": [
    {{
      "groupId": "string",
      "artifactId": "string", 
      "currentVersion": "string",
      "compatible": true/false,
      "recommendedVersion": "string",
      "compatibilityIssues": ["string"],
      "migrationRequired": true/false
    }}
  ],
  "gradle_dependencies": [
    {{
      "groupId": "string",
      "artifactId": "string",
      "currentVersion": "string", 
      "compatible": true/false,
      "recommendedVersion": "string",
      "compatibilityIssues": ["string"],
      "migrationRequired": true/false
    }}
  ],
  "spring_dependencies": [
    {{
      "component": "string",
      "currentVersion": "string",
      "targetVersion": "string",
      "migrationPath": "string",
      "breakingChanges": ["string"]
    }}
  ],
  "jakarta_dependencies": [
    {{
      "dependency": "string",
      "currentNamespace": "javax.*",
      "targetNamespace": "jakarta.*",
      "compatibleVersion": "string",
      "available": true/false
    }}
  ],
  "incompatible_dependencies": [
    {{
      "dependency": "string",
      "reason": "string",
      "alternatives": ["string"],
      "migrationComplexity": "Low|Medium|High"
    }}
  ],
  "recommended_versions": {{
    "springBoot": "3.x.x",
    "springFramework": "6.x.x",
    "java": "17+",
    "hibernate": "6.x.x"
  }},
  "migration_blockers": [
    {{
      "blocker": "string",
      "impact": "Low|Medium|High|Critical",
      "resolution": "string"
    }}
  ]
}}
```

Focus on providing actionable, specific version recommendations and clear migration paths."""

        try:
            response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
            
            # Extract and parse JSON
            json_str = self._extract_and_clean_json(response, file_path)
            if not json_str:
                print(f"     No valid JSON found in dependency analysis for {file_path}")
                return self._get_empty_dependency_analysis()
            
            analysis = json.loads(json_str)
            
            # Validate structure
            expected_keys = ["maven_dependencies", "gradle_dependencies", "spring_dependencies", 
                           "jakarta_dependencies", "incompatible_dependencies", "recommended_versions", "migration_blockers"]
            for key in expected_keys:
                if key not in analysis:
                    analysis[key] = [] if key != "recommended_versions" else {}
            
            return analysis
            
        except Exception as e:
            print(f"     Error analyzing dependencies in {file_path}: {e}")
            return self._get_empty_dependency_analysis()
    
    def _analyze_dependency_relationships(self, dependency_info):
        """Analyze relationships between dependencies."""
        relationships = {
            "spring_ecosystem": [],
            "jakarta_migration_required": [],
            "version_mismatches": [],
            "circular_dependencies": []
        }
        
        # Basic relationship analysis
        all_dependencies = []
        for file_path, content_info in dependency_info.items():
            if isinstance(content_info, dict) and 'parsed_dependencies' in content_info:
                all_dependencies.extend(content_info['parsed_dependencies'])
        
        # Group Spring-related dependencies
        spring_deps = [dep for dep in all_dependencies if 'spring' in dep.get('groupId', '').lower()]
        relationships["spring_ecosystem"] = spring_deps
        
        # Find javax dependencies that need Jakarta migration
        javax_deps = [dep for dep in all_dependencies if 'javax' in dep.get('groupId', '').lower()]
        relationships["jakarta_migration_required"] = javax_deps
        
        return relationships
    
    def _detect_version_conflicts(self, compatibility_analysis):
        """Detect potential version conflicts between dependencies."""
        conflicts = []
        
        # Check for Spring version conflicts
        spring_versions = set()
        for spring_dep in compatibility_analysis.get("spring_dependencies", []):
            current_version = spring_dep.get("currentVersion")
            if current_version:
                spring_versions.add(current_version)
        
        if len(spring_versions) > 1:
            conflicts.append({
                "type": "spring_version_mismatch",
                "conflicting_versions": list(spring_versions),
                "impact": "High",
                "resolution": "Standardize on Spring Boot 3.x"
            })
        
        # Check for javax/jakarta mixing
        javax_deps = compatibility_analysis.get("jakarta_dependencies", [])
        if javax_deps:
            conflicts.append({
                "type": "javax_jakarta_mixing",
                "affected_dependencies": [dep["dependency"] for dep in javax_deps],
                "impact": "Critical", 
                "resolution": "Migrate all javax.* dependencies to jakarta.*"
            })
        
        return conflicts
    
    def _generate_dependency_migration_roadmap(self, compatibility_analysis):
        """Generate a step-by-step dependency migration roadmap."""
        roadmap = []
        
        # Step 1: Java version upgrade
        roadmap.append({
            "step": 1,
            "title": "Java Version Upgrade",
            "description": "Upgrade to Java 17 or later",
            "priority": "Critical",
            "dependencies": [],
            "estimated_effort": "1-2 days"
        })
        
        # Step 2: Spring Boot version upgrade
        roadmap.append({
            "step": 2,
            "title": "Spring Boot Version Upgrade", 
            "description": "Upgrade Spring Boot to 3.x",
            "priority": "Critical",
            "dependencies": ["step-1"],
            "estimated_effort": "2-3 days"
        })
        
        # Step 3: Jakarta dependencies
        jakarta_deps = compatibility_analysis.get("jakarta_dependencies", [])
        if jakarta_deps:
            roadmap.append({
                "step": 3,
                "title": "Jakarta EE Migration",
                "description": f"Migrate {len(jakarta_deps)} javax.* dependencies to jakarta.*",
                "priority": "High",
                "dependencies": ["step-2"],
                "estimated_effort": "3-5 days"
            })
        
        # Step 4: Incompatible dependencies
        incompatible_deps = compatibility_analysis.get("incompatible_dependencies", [])
        if incompatible_deps:
            roadmap.append({
                "step": 4,
                "title": "Replace Incompatible Dependencies",
                "description": f"Replace or upgrade {len(incompatible_deps)} incompatible dependencies",
                "priority": "High", 
                "dependencies": ["step-3"],
                "estimated_effort": "2-4 days"
            })
        
        return roadmap
    
    def _get_empty_dependency_analysis(self):
        """Return empty dependency analysis structure."""
        return {
            "maven_dependencies": [],
            "gradle_dependencies": [],
            "spring_dependencies": [],
            "jakarta_dependencies": [],
            "incompatible_dependencies": [],
            "recommended_versions": {},
            "migration_blockers": []
        }
    
    def _extract_and_clean_json(self, response, file_path):
        """Extract and clean JSON from LLM response."""
        try:
            response = response.strip()
            
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif response.startswith("{") and response.endswith("}"):
                json_str = response
            else:
                import re
                json_match = re.search(r'\\{.*\\}', response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    return None
            
            # Basic JSON cleaning
            json_str = json_str.strip()
            
            # Test parse
            json.loads(json_str)
            return json_str
            
        except Exception:
            return None
    
    def post(self, shared, prep_res, exec_res):
        shared["dependency_compatibility"] = exec_res
        
        # Count issues
        total_incompatible = len(exec_res.get("incompatible_dependencies", []))
        total_blockers = len(exec_res.get("migration_blockers", []))
        jakarta_migrations = len(exec_res.get("jakarta_dependencies", []))
        
        print(f"✅ Dependency compatibility analysis completed")
        print(f"   🚨 {total_incompatible} incompatible dependencies found")
        print(f"   🔄 {jakarta_migrations} javax → jakarta migrations needed")
        print(f"   ⚠️  {total_blockers} migration blockers identified")
        
        return "default"
