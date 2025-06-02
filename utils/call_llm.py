import os
import logging
import json
from datetime import datetime
import requests
import time
from functools import lru_cache
import hashlib
from utils.verbose_logger import get_verbose_logger

# Configure logging
log_directory = os.getenv("LOG_DIR", "logs")
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(
    log_directory, f"llm_calls_{datetime.now().strftime('%Y%m%d')}.log"
)

# Set up logger
logger = logging.getLogger("llm_logger")
logger.setLevel(logging.INFO)
logger.propagate = False  # Prevent propagation to root logger
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
)
logger.addHandler(file_handler)

# Simple cache configuration
cache_file = "llm_cache.json"

# Configure LLM settings for large repositories
DEFAULT_TIMEOUT = 300  # 5 minutes for large prompts
MAX_RETRIES = 3
RATE_LIMIT_DELAY = 2  # seconds between requests
MAX_CONTEXT_LENGTH = 100000  # chars - adjust based on LLM model


def call_llm(prompt, use_cache=True, timeout=DEFAULT_TIMEOUT, max_retries=MAX_RETRIES):
    """
    Enhanced LLM calling with timeout handling, rate limiting, and large content optimization.
    """
    vlogger = get_verbose_logger()
    
    # Apply content length optimization for large prompts
    if len(prompt) > MAX_CONTEXT_LENGTH:
        vlogger.warning(f"Large prompt detected ({len(prompt)} chars), truncating to {MAX_CONTEXT_LENGTH}")
        prompt = _optimize_large_prompt(prompt)
    
    # Generate cache key
    cache_key = hashlib.md5(prompt.encode()).hexdigest()
    
    if use_cache:
        cached_result = _get_cached_response(cache_key)
        if cached_result:
            vlogger.cache_hit("LLM", cache_key[:8])
            return cached_result
        else:
            vlogger.cache_miss("LLM", cache_key[:8])
    
    # Track attempt number for verbose logging
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                # Rate limiting: wait before retry
                delay = RATE_LIMIT_DELAY * (2 ** attempt)  # Exponential backoff
                vlogger.warning(f"LLM retry {attempt + 1}/{max_retries}, waiting {delay}s")
                time.sleep(delay)
            
            vlogger.llm_call(f"Attempt {attempt + 1}", "", len(prompt), use_cache)
            
            # Use the appropriate LLM provider
            response = _make_llm_request(prompt, timeout)
            
            # Cache successful response
            if use_cache and response:
                _cache_response(cache_key, response)
            
            vlogger.success(f"LLM call successful (attempt {attempt + 1})")
            return response
            
        except TimeoutError as e:
            vlogger.error(f"LLM request timeout on attempt {attempt + 1}", e)
            if attempt == max_retries - 1:
                raise Exception(f"LLM request timed out after {max_retries} attempts")
        except Exception as e:
            vlogger.error(f"LLM request failed on attempt {attempt + 1}", e)
            if attempt == max_retries - 1:
                raise Exception(f"LLM request failed: {str(e)}")
    
    raise Exception("LLM request failed after all retry attempts")


def _optimize_large_prompt(prompt):
    """Optimize large prompts by intelligent truncation and summarization."""
    vlogger = get_verbose_logger()
    
    # Strategy 1: Extract key sections
    key_sections = []
    
    # Always keep the system prompt and instructions
    lines = prompt.split('\n')
    system_section = []
    files_section = []
    current_section = system_section
    
    for line in lines:
        if "# System Prompt" in line or "## Analysis Requirements" in line:
            current_section = system_section
        elif "## Codebase Context" in line or "--- File" in line:
            current_section = files_section
        
        current_section.append(line)
    
    # Keep all system instructions
    optimized_prompt = '\n'.join(system_section)
    
    # Intelligently sample files section
    remaining_budget = MAX_CONTEXT_LENGTH - len(optimized_prompt)
    
    # Prioritize certain file types
    priority_files = []
    regular_files = []
    
    for line in files_section:
        if any(pattern in line.lower() for pattern in ['pom.xml', 'build.gradle', 'application.', 'security', 'config']):
            priority_files.append(line)
        else:
            regular_files.append(line)
    
    # Add priority files first
    files_content = '\n'.join(priority_files)
    if len(files_content) < remaining_budget:
        # Add regular files until budget is reached
        for line in regular_files:
            if len(files_content) + len(line) < remaining_budget:
                files_content += '\n' + line
            else:
                break
        
        files_content += '\n... [Additional files truncated for performance optimization] ...'
    
    optimized_prompt += '\n\n## Codebase Context (Optimized):\n' + files_content
    
    vlogger.optimization_applied("Large prompt truncation", f"{len(prompt)} → {len(optimized_prompt)} chars")
    return optimized_prompt


def _make_llm_request(prompt, timeout):
    """Make the actual LLM request with timeout handling."""
    vlogger = get_verbose_logger()
    
    # Try different LLM providers in order of preference
    providers = ['openai', 'anthropic', 'google']
    
    for provider in providers:
        try:
            if provider == 'openai' and os.getenv('OPENAI_API_KEY'):
                return _call_openai(prompt, timeout)
            elif provider == 'anthropic' and os.getenv('ANTHROPIC_API_KEY'):
                return _call_anthropic(prompt, timeout)
            elif provider == 'google' and os.getenv('GOOGLE_API_KEY'):
                return _call_google(prompt, timeout)
        except Exception as e:
            vlogger.warning(f"Provider {provider} failed: {str(e)}")
            continue
    
    # Fallback: return a structured error response that can be parsed
    vlogger.error("All LLM providers failed, returning fallback response")
    return _get_fallback_llm_response(prompt)


def _call_openai(prompt, timeout):
    """Call OpenAI with timeout handling."""
    try:
        from openai import OpenAI
        import signal
        
        def timeout_handler(signum, frame):
            raise TimeoutError("OpenAI request timed out")
        
        # Set timeout alarm
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(timeout)
        
        try:
            client_kwargs = {
                "api_key": os.environ.get("OPENAI_API_KEY", "your-api-key"),
                "base_url": os.environ.get("OPENAI_URL", "http://localhost:1234/v1")
            }
            client = OpenAI(**client_kwargs)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                timeout=timeout
            )
            return response.choices[0].message.content
        finally:
            signal.alarm(0)  # Cancel the alarm
            
    except ImportError:
        raise Exception("OpenAI library not installed")
    except TimeoutError:
        raise TimeoutError("OpenAI request timed out")
    except Exception as e:
        raise Exception(f"OpenAI error: {str(e)}")


def _call_anthropic(prompt, timeout):
    """Call Anthropic with timeout handling."""
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        response = client.messages.create(
            model="claude-3-sonnet-20240229",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4000,
            timeout=timeout
        )
        return response.content[0].text
    except ImportError:
        raise Exception("Anthropic library not installed")
    except Exception as e:
        raise Exception(f"Anthropic error: {str(e)}")


def _call_google(prompt, timeout):
    """Call Google Generative AI with timeout handling."""
    try:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)
        return response.text
    except ImportError:
        raise Exception("Google Generative AI library not installed")
    except Exception as e:
        raise Exception(f"Google AI error: {str(e)}")


def _get_fallback_llm_response(prompt):
    """Generate a structured fallback response when all LLM providers fail."""
    vlogger = get_verbose_logger()
    vlogger.warning("Generating fallback LLM response due to provider failures")
    
    # Analyze the prompt to determine response type
    prompt_lower = prompt.lower()
    if "dependency compatibility" in prompt_lower:
        return _get_fallback_dependency_response()
    elif "spring migration" in prompt_lower or "migration change analysis" in prompt_lower:
        # Check if this is individual file analysis or overall migration analysis
        if "file to analyze" in prompt_lower or "file content:" in prompt_lower:
            return _get_fallback_file_analysis_response()
        else:
            return _get_fallback_migration_response()
    elif "migration plan" in prompt_lower:
        return _get_fallback_plan_response()
    else:
        return _get_fallback_generic_response()


def _get_fallback_dependency_response():
    """Fallback response for dependency analysis."""
    return json.dumps({
        "analysis_status": "fallback_analysis_incomplete",
        "maven_dependencies": [],
        "gradle_dependencies": [],
        "spring_dependencies": [],
        "jakarta_dependencies": [],
        "incompatible_dependencies": [],
        "recommended_versions": {},
        "migration_blockers": [
            {
                "blocker": "LLM analysis service unavailable",
                "impact": "Critical",
                "resolution": "Manual analysis required - cannot provide automated recommendations"
            }
        ],
        "dependencies": {
            "analyzed": 0,
            "compatible": [],
            "migration_required": [],
            "incompatible": []
        },
        "recommendations": [
            "LLM analysis service is unavailable",
            "Manual dependency analysis required",
            "Review actual project dependencies and Spring documentation",
            "Cannot provide specific version recommendations without analysis"
        ],
        "confidence": "none",
        "manual_review_required": True,
        "fallback_reason": "LLM service unavailable - no automated analysis performed"
    }, indent=2)


def _get_fallback_migration_response():
    """Fallback response for Spring migration analysis."""
    return json.dumps({
        "executive_summary": {
            "migration_impact": "Unknown - automated analysis failed",
            "key_blockers": ["LLM analysis service unavailable"],
            "recommended_approach": "Manual code review and analysis required"
        },
        "detailed_analysis": {
            "framework_audit": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "jakarta_migration": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "configuration_analysis": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "security_migration": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "data_layer": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "web_layer": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "testing": {"analysis_status": "failed", "reason": "LLM service unavailable"},
            "build_tooling": {"analysis_status": "failed", "reason": "LLM service unavailable"}
        },
        "effort_estimation": {
            "total_effort": "Cannot estimate - analysis not performed",
            "by_category": {},
            "priority_levels": {"high": [], "medium": [], "low": []}
        },
        "migration_roadmap": [
            {
                "step": 1,
                "title": "Manual Analysis Required",
                "description": "LLM analysis failed - manual code review needed to determine migration requirements",
                "estimated_effort": "Unknown"
            }
        ],
        "analysis_metadata": {
            "status": "failed",
            "reason": "LLM service unavailable",
            "automated_analysis_performed": False,
            "manual_review_required": True
        }
    }, indent=2)


def _get_fallback_plan_response():
    """Fallback response for migration plan generation."""
    return json.dumps({
        "migration_strategy": {
            "approach": "Manual planning required",
            "rationale": "LLM planning service unavailable - cannot generate automated migration plan",
            "estimated_timeline": "Unknown - requires manual analysis",
            "team_size_recommendation": "To be determined based on manual analysis"
        },
        "phase_breakdown": [
            {
                "phase": 1,
                "name": "Manual Planning Phase",
                "description": "LLM service unavailable - manual migration planning required",
                "duration": "Unknown",
                "deliverables": ["Manual migration assessment"],
                "tasks": [
                    {
                        "task_id": "manual-analysis",
                        "title": "Manual Code Analysis",
                        "description": "Perform manual analysis since automated LLM analysis failed",
                        "complexity": "Unknown",
                        "estimated_hours": "To be determined",
                        "dependencies": [],
                        "automation_potential": "Unknown",
                        "tools_required": ["Manual review"]
                    }
                ],
                "risks": ["No automated analysis available"],
                "success_criteria": ["Manual analysis completed"]
            }
        ],
        "automation_recommendations": [],
        "manual_changes": [
            {
                "category": "All Changes",
                "changes": ["Manual analysis required - LLM service unavailable"],
                "rationale": "Cannot provide automated recommendations without LLM analysis"
            }
        ],
        "testing_strategy": {
            "unit_tests": "Manual strategy required",
            "integration_tests": "Manual strategy required",
            "regression_testing": "Manual strategy required"
        },
        "rollback_plan": {
            "triggers": ["Manual assessment required"],
            "steps": ["Manual planning required"],
            "data_considerations": "Manual assessment required"
        },
        "success_metrics": [
            {
                "metric": "Manual Analysis Completion",
                "target": "TBD",
                "measurement_method": "Manual review"
            }
        ],
        "plan_metadata": {
            "status": "failed",
            "reason": "LLM service unavailable",
            "automated_planning_performed": False,
            "manual_planning_required": True
        }
    }, indent=2)


def _get_fallback_file_analysis_response():
    """Fallback response for individual file analysis."""
    return json.dumps({
        "javax_to_jakarta": [],
        "spring_security_updates": [],
        "dependency_updates": [],
        "configuration_updates": [],
        "other_changes": []
    }, indent=2)


def _get_fallback_generic_response():
    """Generic fallback response."""
    return json.dumps({
        "status": "error",
        "message": "LLM service timeout",
        "recommendation": "Manual analysis required",
        "fallback_analysis": True
    }, indent=2)


# Simple in-memory cache
_response_cache = {}


def _get_cached_response(cache_key):
    """Get cached response if available."""
    return _response_cache.get(cache_key)


def _cache_response(cache_key, response):
    """Cache successful response."""
    # Limit cache size to prevent memory issues
    if len(_response_cache) > 100:
        # Remove oldest entries
        keys_to_remove = list(_response_cache.keys())[:20]
        for key in keys_to_remove:
            del _response_cache[key]
    
    _response_cache[cache_key] = response


# Rate limiting for concurrent requests
_last_request_time = 0
_request_count = 0
_rate_limit_window = 60  # seconds
_max_requests_per_window = 20


def apply_rate_limiting():
    """Apply rate limiting to prevent overwhelming LLM services."""
    global _last_request_time, _request_count
    
    current_time = time.time()
    
    # Reset counter if window has passed
    if current_time - _last_request_time > _rate_limit_window:
        _request_count = 0
        _last_request_time = current_time
    
    # Check if we've hit the rate limit
    if _request_count >= _max_requests_per_window:
        wait_time = _rate_limit_window - (current_time - _last_request_time)
        if wait_time > 0:
            vlogger = get_verbose_logger()
            vlogger.warning(f"Rate limit reached, waiting {wait_time:.1f}s")
            time.sleep(wait_time)
            _request_count = 0
            _last_request_time = time.time()
    
    _request_count += 1


def configure_for_large_repository():
    """Configure LLM settings for large repository analysis."""
    global DEFAULT_TIMEOUT, MAX_CONTEXT_LENGTH, _max_requests_per_window
    
    DEFAULT_TIMEOUT = 600  # 10 minutes for very large prompts
    MAX_CONTEXT_LENGTH = 50000  # Reduce context for large repos
    _max_requests_per_window = 10  # More conservative rate limiting
    
    vlogger = get_verbose_logger()
    vlogger.optimization_applied("Large repository LLM configuration", 
                                f"timeout={DEFAULT_TIMEOUT}s, context={MAX_CONTEXT_LENGTH}, rate_limit={_max_requests_per_window}/min")

if __name__ == "__main__":
    test_prompt = "Hello, how are you?"

    # First call - should hit the API
    print("Making call...")
    response1 = call_llm(test_prompt, use_cache=False)
    print(f"Response: {response1}")
