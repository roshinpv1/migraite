import time
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO" 
    WARNING = "WARNING"
    ERROR = "ERROR"
    SUCCESS = "SUCCESS"


class VerboseLogger:
    """
    Comprehensive verbose logging system for Spring migration tool.
    Shows detailed progress, internal operations, and status updates.
    """
    
    def __init__(self, enabled: bool = False, show_timestamps: bool = True):
        self.enabled = enabled
        self.show_timestamps = show_timestamps
        self.operation_stack = []
        self.step_counters = {}
        self.start_time = time.time()
        self.last_update_time = time.time()
        
    def enable(self):
        """Enable verbose logging."""
        self.enabled = True
        self.log("🔍 Verbose mode enabled - showing detailed progress", LogLevel.INFO)
        
    def disable(self):
        """Disable verbose logging."""
        self.enabled = False
        
    def log(self, message: str, level: LogLevel = LogLevel.INFO, indent: int = 0):
        """Log a message with optional formatting."""
        if not self.enabled:
            return
            
        # Get timestamp
        timestamp = ""
        if self.show_timestamps:
            current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
            elapsed = time.time() - self.start_time
            timestamp = f"[{current_time}] [{elapsed:6.1f}s] "
        
        # Get level emoji and color
        level_info = self._get_level_info(level)
        
        # Format indentation
        indent_str = "  " * (indent + len(self.operation_stack))
        
        # Print formatted message
        print(f"{timestamp}{level_info['emoji']} {indent_str}{message}")
        sys.stdout.flush()
        
        self.last_update_time = time.time()
    
    def start_operation(self, operation_name: str, details: str = ""):
        """Start a new operation with progress tracking."""
        self.operation_stack.append(operation_name)
        details_str = f" - {details}" if details else ""
        self.log(f"🚀 Started: {operation_name}{details_str}", LogLevel.INFO)
        return time.time()
    
    def end_operation(self, operation_name: str, duration: Optional[float] = None, 
                     success: bool = True, details: str = ""):
        """End an operation and show completion status."""
        if self.operation_stack and self.operation_stack[-1] == operation_name:
            self.operation_stack.pop()
        
        if duration is None:
            duration = time.time() - self.last_update_time
            
        status = "✅ Completed" if success else "❌ Failed"
        details_str = f" - {details}" if details else ""
        self.log(f"{status}: {operation_name} ({duration:.1f}s){details_str}", 
                LogLevel.SUCCESS if success else LogLevel.ERROR)
    
    def progress(self, current: int, total: int, item_name: str = "items", 
                operation: str = "Processing"):
        """Show progress with percentage and rate."""
        if not self.enabled:
            return
            
        percentage = (current / total) * 100 if total > 0 else 0
        elapsed = time.time() - self.start_time
        rate = current / elapsed if elapsed > 0 else 0
        
        self.log(f"📊 {operation}: {current}/{total} {item_name} "
                f"({percentage:.1f}%) - {rate:.1f} {item_name}/sec")
    
    def step(self, step_name: str, step_number: Optional[int] = None):
        """Log a processing step with automatic numbering."""
        if step_number is None:
            if step_name not in self.step_counters:
                self.step_counters[step_name] = 0
            self.step_counters[step_name] += 1
            step_number = self.step_counters[step_name]
            
        self.log(f"🔸 Step {step_number}: {step_name}", LogLevel.INFO)
    
    def file_processing(self, file_path: str, action: str, details: str = ""):
        """Log file processing operations."""
        details_str = f" ({details})" if details else ""
        self.log(f"📁 {action}: {file_path}{details_str}", LogLevel.DEBUG, indent=1)
    
    def llm_call(self, prompt_type: str, file_path: str = "", tokens: int = 0, cached: bool = False):
        """Log LLM API calls with details."""
        cache_str = " [CACHED]" if cached else ""
        tokens_str = f" ({tokens} tokens)" if tokens > 0 else ""
        file_str = f" for {file_path}" if file_path else ""
        self.log(f"🤖 LLM Call: {prompt_type}{file_str}{tokens_str}{cache_str}", 
                LogLevel.DEBUG, indent=1)
    
    def performance_metric(self, metric_name: str, value: float, unit: str = ""):
        """Log performance metrics."""
        unit_str = f" {unit}" if unit else ""
        self.log(f"📈 {metric_name}: {value:.2f}{unit_str}", LogLevel.DEBUG, indent=1)
    
    def warning(self, message: str):
        """Log a warning message."""
        self.log(f"⚠️  {message}", LogLevel.WARNING)
    
    def error(self, message: str, exception: Exception = None):
        """Log an error message."""
        error_msg = message
        if exception:
            error_msg += f" - {str(exception)}"
        self.log(f"❌ {error_msg}", LogLevel.ERROR)
    
    def debug(self, message: str):
        """Log a debug message."""
        self.log(f"🐛 {message}", LogLevel.DEBUG, indent=1)
    
    def success(self, message: str):
        """Log a success message."""
        self.log(f"✅ {message}", LogLevel.SUCCESS)
    
    def section_header(self, title: str):
        """Log a section header."""
        separator = "=" * min(60, len(title) + 10)
        self.log(separator, LogLevel.INFO)
        self.log(f"📋 {title}", LogLevel.INFO)
        self.log(separator, LogLevel.INFO)
    
    def subsection_header(self, title: str):
        """Log a subsection header."""
        self.log(f"📂 {title}", LogLevel.INFO)
        self.log("-" * min(40, len(title) + 5), LogLevel.INFO)
    
    def git_operation(self, operation: str, details: str = ""):
        """Log Git operations."""
        details_str = f": {details}" if details else ""
        self.log(f"🔀 Git {operation}{details_str}", LogLevel.INFO, indent=1)
    
    def dependency_analysis(self, file_path: str, dependency_count: int, analysis_type: str = ""):
        """Log dependency analysis operations."""
        type_str = f" ({analysis_type})" if analysis_type else ""
        self.log(f"🔍 Analyzing {dependency_count} dependencies in {file_path}{type_str}", 
                LogLevel.DEBUG, indent=1)
    
    def cache_hit(self, cache_type: str, key: str):
        """Log cache hits."""
        self.log(f"💾 Cache hit ({cache_type}): {key}", LogLevel.DEBUG, indent=2)
    
    def cache_miss(self, cache_type: str, key: str):
        """Log cache misses."""
        self.log(f"💿 Cache miss ({cache_type}): {key}", LogLevel.DEBUG, indent=2)
    
    def memory_usage(self, current_mb: float, peak_mb: float = None):
        """Log memory usage."""
        if peak_mb:
            self.log(f"💾 Memory: {current_mb:.1f} MB (Peak: {peak_mb:.1f} MB)", 
                    LogLevel.DEBUG, indent=1)
        else:
            self.log(f"💾 Memory: {current_mb:.1f} MB", LogLevel.DEBUG, indent=1)
    
    def network_request(self, url: str, method: str = "GET", status_code: int = None):
        """Log network requests."""
        status_str = f" -> {status_code}" if status_code else ""
        self.log(f"🌐 {method} {url}{status_str}", LogLevel.DEBUG, indent=1)
    
    def json_parsing(self, source: str, success: bool, error: str = ""):
        """Log JSON parsing operations."""
        status = "✅ Parsed" if success else "❌ Failed to parse"
        error_str = f" - {error}" if error else ""
        self.log(f"📋 {status} JSON from {source}{error_str}", LogLevel.DEBUG, indent=1)
    
    def optimization_applied(self, optimization: str, improvement: str = ""):
        """Log applied optimizations."""
        improvement_str = f" ({improvement})" if improvement else ""
        self.log(f"⚡ Applied optimization: {optimization}{improvement_str}", 
                LogLevel.INFO, indent=1)
    
    def _get_level_info(self, level: LogLevel) -> Dict[str, str]:
        """Get emoji and color info for log levels."""
        level_map = {
            LogLevel.DEBUG: {"emoji": "🐛", "color": "\033[90m"},     # Gray
            LogLevel.INFO: {"emoji": "ℹ️", "color": "\033[94m"},      # Blue  
            LogLevel.WARNING: {"emoji": "⚠️", "color": "\033[93m"},   # Yellow
            LogLevel.ERROR: {"emoji": "❌", "color": "\033[91m"},     # Red
            LogLevel.SUCCESS: {"emoji": "✅", "color": "\033[92m"},   # Green
        }
        return level_map.get(level, {"emoji": "📝", "color": "\033[0m"})
    
    def show_summary(self):
        """Show verbose logging summary."""
        if not self.enabled:
            return
            
        total_time = time.time() - self.start_time
        self.section_header("Verbose Logging Summary")
        self.log(f"Total analysis time: {total_time:.1f} seconds")
        self.log(f"Operations completed: {len(self.step_counters)}")
        self.log(f"Steps executed: {sum(self.step_counters.values())}")
        

# Global verbose logger instance
_verbose_logger = VerboseLogger()


def get_verbose_logger() -> VerboseLogger:
    """Get the global verbose logger instance."""
    return _verbose_logger


def enable_verbose_logging(show_timestamps: bool = True):
    """Enable verbose logging globally."""
    _verbose_logger.show_timestamps = show_timestamps
    _verbose_logger.enable()


def disable_verbose_logging():
    """Disable verbose logging globally."""
    _verbose_logger.disable()


# Convenience functions
def vlog(message: str, level: LogLevel = LogLevel.INFO):
    """Quick verbose log function."""
    _verbose_logger.log(message, level)


def vdebug(message: str):
    """Quick verbose debug function."""
    _verbose_logger.debug(message)


def verror(message: str, exception: Exception = None):
    """Quick verbose error function."""
    _verbose_logger.error(message, exception)


def vsuccess(message: str):
    """Quick verbose success function."""
    _verbose_logger.success(message) 