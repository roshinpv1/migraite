import os
import re
import yaml
import json
from pocketflow import Node, BatchNode
from utils.crawl_github_files import crawl_github_files
from utils.call_llm import call_llm
from utils.crawl_local_files import crawl_local_files


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

        return {
            "repo_url": repo_url,
            "local_dir": local_dir,
            "token": shared.get("github_token"),
            "include_patterns": include_patterns,
            "exclude_patterns": exclude_patterns,
            "max_file_size": max_file_size,
            "use_relative_paths": True,
        }

    def exec(self, prep_res):
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
        print(f"Fetched {len(files_list)} files.")
        return files_list

    def post(self, shared, prep_res, exec_res):
        shared["files"] = exec_res  # List of (path, content) tuples


# ==========================================
# SPRING MIGRATION NODES
# ==========================================

class SpringMigrationAnalyzer(Node):
    """
    Analyzes a Spring codebase for migration from Spring 5 to Spring 6.
    Uses the comprehensive system prompt provided by the user.
    """
    
    def prep(self, shared):
        files_data = shared["files"]
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        
        # Filter for Spring-relevant files and create context
        def create_spring_context(files_data):
            context = ""
            file_summary = []
            
            for i, (path, content) in enumerate(files_data):
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
                
                # Limit total context size
                if len(context) > 50000:
                    context += "... [Additional files truncated for context length] ...\n"
                    break
            
            return context, file_summary
        
        context, file_summary = create_spring_context(files_data)
        file_listing = "\n".join(file_summary)
        
        return context, file_listing, project_name, use_cache
    
    def exec(self, prep_res):
        context, file_listing, project_name, use_cache = prep_res
        print(f"Analyzing Spring codebase for migration...")
        
        # The comprehensive system prompt from the user
        prompt = f"""# System Prompt: Spring 6 Migration – Full Codebase Analysis

You are an expert in Java, Spring Framework (5 and 6), Jakarta EE 9+, and enterprise application modernization. Analyze the Java codebase for project `{project_name}` targeted for migration from Spring Framework 5.x (and optionally Spring Boot 2.x) to Spring Framework 6.x and Spring Boot 3.x, with Java 17+ and Jakarta namespace compatibility.

Perform a complete and structured analysis of the entire codebase. Your goal is to assess the **migration scope, required changes, complexity, and overall effort** involved. The output should include both **summary and detailed findings** that support prioritization and planning.

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

        response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
        
        # Extract JSON from response with improved error handling
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
                    raise ValueError("No JSON content found in response")
            
            # Clean up common JSON issues
            json_str = self._clean_json_string(json_str)
            
            # Try to parse JSON
            analysis = json.loads(json_str)
            
            # Basic validation
            required_keys = ["executive_summary", "detailed_analysis", "module_breakdown", "effort_estimation", "migration_roadmap"]
            for key in required_keys:
                if key not in analysis:
                    print(f"Warning: Missing required key: {key}")
                    analysis[key] = self._get_default_value(key)
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"JSON parsing error: {e}")
            print(f"Response content (first 500 chars): {response[:500]}")
            print(f"Attempting to fix JSON and retry...")
            
            # Try to fix common JSON issues and retry
            try:
                fixed_json = self._attempt_json_fix(response)
                if fixed_json:
                    analysis = json.loads(fixed_json)
                    # Add any missing required keys
                    required_keys = ["executive_summary", "detailed_analysis", "module_breakdown", "effort_estimation", "migration_roadmap"]
                    for key in required_keys:
                        if key not in analysis:
                            analysis[key] = self._get_default_value(key)
                    return analysis
                else:
                    raise ValueError("Could not fix JSON")
            except:
                print("Failed to fix JSON, using fallback analysis...")
                return self._get_fallback_analysis(shared, file_listing)
            
        except Exception as e:
            print(f"Error processing LLM response: {e}")
            print(f"Response content (first 500 chars): {response[:500]}")
            return self._get_fallback_analysis(shared, file_listing)
    
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
    
    def _get_fallback_analysis(self, shared, file_listing):
        """Generate a fallback analysis when LLM parsing fails."""
        # Calculate realistic estimates based on codebase size
        file_count = len(shared["files"])
        
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

        response = call_llm(prompt, use_cache=(use_cache and self.cur_retry == 0))
        
        try:
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            else:
                json_str = response.strip()
            
            plan = json.loads(json_str)
            
            # Basic validation
            required_keys = ["migration_strategy", "phase_breakdown", "automation_recommendations", "testing_strategy"]
            for key in required_keys:
                if key not in plan:
                    raise ValueError(f"Missing required key: {key}")
            
            return plan
            
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from LLM: {e}")
        except Exception as e:
            raise ValueError(f"Error processing LLM response: {e}")
    
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
    Generates specific file changes based on the migration analysis using LLM.
    """
    
    def prep(self, shared):
        files_data = shared["files"]
        analysis = shared["migration_analysis"]
        project_name = shared["project_name"]
        use_cache = shared.get("use_cache", True)
        
        return files_data, analysis, project_name, use_cache
    
    def exec(self, prep_res):
        files_data, analysis, project_name, use_cache = prep_res
        
        print(f"🔧 Generating specific migration changes using LLM analysis...")
        
        # Create file changes based on analysis
        changes = {
            "javax_to_jakarta": [],
            "spring_security_updates": [],
            "dependency_updates": [],
            "configuration_updates": [],
            "other_changes": []
        }
        
        # Process each file for migration changes using LLM
        for i, (file_path, content) in enumerate(files_data):
            print(f"   Analyzing {file_path} ({i+1}/{len(files_data)})...")
            file_changes = self._analyze_file_with_llm(file_path, content, analysis, project_name, use_cache)
            
            for change_type, file_change_list in file_changes.items():
                changes[change_type].extend(file_change_list)
        
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
    Generates the final migration report combining analysis and plan.
    """
    
    def prep(self, shared):
        analysis = shared["migration_analysis"]
        plan = shared["migration_plan"]
        project_name = shared["project_name"]
        output_dir = shared["output_dir"]
        backup_info = shared.get("backup_info")
        applied_changes = shared.get("applied_changes")
        
        return analysis, plan, project_name, output_dir, backup_info, applied_changes
    
    def exec(self, prep_res):
        analysis, plan, project_name, output_dir, backup_info, applied_changes = prep_res
        
        # Create comprehensive report
        report = {
            "project_name": project_name,
            "analysis_date": None,  # Will be set in post()
            "migration_analysis": analysis,
            "migration_plan": plan,
            "backup_info": backup_info,
            "applied_changes": applied_changes,
            "recommendations": {
                "immediate_actions": [],
                "long_term_considerations": [],
                "risk_mitigation": []
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
        
        return report
    
    def post(self, shared, prep_res, exec_res):
        import json
        import os
        from datetime import datetime
        
        analysis, plan, project_name, output_dir, backup_info, applied_changes = prep_res
        report = exec_res
        
        # Add timestamp
        report["analysis_date"] = datetime.now().isoformat()
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Save detailed JSON report
        json_file = os.path.join(output_dir, f"{project_name}_spring_migration_report.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Save human-readable summary
        summary_file = os.path.join(output_dir, f"{project_name}_migration_summary.md")
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(f"# Spring 5 to 6 Migration Analysis & Implementation Report\n\n")
            f.write(f"**Project:** {project_name}\n")
            f.write(f"**Analysis Date:** {report['analysis_date']}\n\n")
            
            # Executive Summary
            if "executive_summary" in analysis:
                f.write("## Executive Summary\n\n")
                exec_summary = analysis["executive_summary"]
                f.write(f"**Migration Impact:** {exec_summary.get('migration_impact', 'N/A')}\n\n")
                
                if "key_blockers" in exec_summary:
                    f.write("**Key Blockers:**\n")
                    for blocker in exec_summary["key_blockers"]:
                        f.write(f"- {blocker}\n")
                    f.write("\n")
                
                f.write(f"**Recommended Approach:** {exec_summary.get('recommended_approach', 'N/A')}\n\n")
            
            # Effort Estimation
            if "effort_estimation" in analysis:
                f.write("## Effort Estimation\n\n")
                effort = analysis["effort_estimation"]
                f.write(f"**Total Effort:** {effort.get('total_effort', 'N/A')}\n\n")
                
                if "priority_levels" in effort:
                    priorities = effort["priority_levels"]
                    f.write("**Priority Breakdown:**\n")
                    f.write(f"- High Priority: {len(priorities.get('high', []))} items\n")
                    f.write(f"- Medium Priority: {len(priorities.get('medium', []))} items\n")
                    f.write(f"- Low Priority: {len(priorities.get('low', []))} items\n\n")
            
            # Migration Strategy
            if "migration_strategy" in plan:
                f.write("## Migration Strategy\n\n")
                strategy = plan["migration_strategy"]
                f.write(f"**Approach:** {strategy.get('approach', 'N/A')}\n")
                f.write(f"**Timeline:** {strategy.get('estimated_timeline', 'N/A')}\n")
                f.write(f"**Team Size:** {strategy.get('team_size_recommendation', 'N/A')}\n\n")
                f.write(f"**Rationale:** {strategy.get('rationale', 'N/A')}\n\n")
            
            # Change Application Results
            if applied_changes:
                f.write("## Migration Changes Applied\n\n")
                change_summary = report.get("change_summary", {})
                f.write(f"**Automatic Changes Applied:** {change_summary.get('automatic_changes_applied', 0)}\n")
                f.write(f"**Manual Review Required:** {change_summary.get('changes_requiring_manual_review', 0)}\n")
                f.write(f"**Failed Changes:** {change_summary.get('failed_changes', 0)}\n\n")
                
                if applied_changes.get("successful"):
                    f.write("### Successfully Applied Changes\n")
                    for change in applied_changes["successful"][:10]:  # Show first 10
                        f.write(f"- {change['file']}: {change['description']}\n")
                    if len(applied_changes["successful"]) > 10:
                        f.write(f"- ... and {len(applied_changes['successful']) - 10} more\n")
                    f.write("\n")
                
                if applied_changes.get("skipped"):
                    f.write("### Changes Requiring Manual Review\n")
                    for change in applied_changes["skipped"][:10]:  # Show first 10
                        f.write(f"- {change['file']}: {change['description']}\n")
                    if len(applied_changes["skipped"]) > 10:
                        f.write(f"- ... and {len(applied_changes['skipped']) - 10} more\n")
                    f.write("\n")
            
            # Backup Information
            if backup_info:
                f.write("## Backup Information\n\n")
                f.write(f"**Backup Location:** `{backup_info['backup_dir']}`\n")
                f.write(f"**Backup Timestamp:** {backup_info['timestamp']}\n")
                f.write(f"**Files Backed Up:** {len(backup_info['files_backed_up'])}\n\n")
            
            f.write(f"\n---\n\n")
            f.write(f"For detailed analysis and step-by-step migration plan, see: `{os.path.basename(json_file)}`\n")
        
        shared["final_output_dir"] = output_dir
        
        print(f"✅ Migration report saved to:")
        print(f"   📄 Detailed report: {json_file}")
        print(f"   📋 Summary: {summary_file}")
        
        if backup_info:
            print(f"   📦 Backup: {backup_info['backup_dir']}")
        
        return "default"


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
