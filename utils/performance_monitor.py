import time
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from collections import defaultdict
import json
import os


@dataclass
class PerformanceMetrics:
    """Performance metrics for a specific operation."""
    operation_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    memory_start: Optional[float] = None
    memory_end: Optional[float] = None
    memory_peak: Optional[float] = None
    files_processed: int = 0
    llm_calls: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    warnings: int = 0


class PerformanceMonitor:
    """
    Performance monitoring and optimization for large repository analysis.
    """
    
    def __init__(self, enable_detailed_tracking: bool = True):
        self.enable_detailed_tracking = enable_detailed_tracking
        self.metrics: Dict[str, PerformanceMetrics] = {}
        self.overall_start_time = time.time()
        self.memory_samples: List[tuple] = []  # (timestamp, memory_mb)
        self.optimization_recommendations: List[str] = []
        self._monitoring_thread = None
        self._stop_monitoring = False
        
        # Start background memory monitoring
        if enable_detailed_tracking:
            self._start_memory_monitoring()
    
    def start_operation(self, operation_name: str) -> str:
        """Start tracking a new operation."""
        if not self.enable_detailed_tracking:
            return operation_name
        
        current_memory = self._get_memory_usage()
        
        metric = PerformanceMetrics(
            operation_name=operation_name,
            start_time=time.time(),
            memory_start=current_memory
        )
        
        self.metrics[operation_name] = metric
        print(f"🚀 Started: {operation_name} (Memory: {current_memory:.1f} MB)")
        return operation_name
    
    def end_operation(self, operation_name: str, 
                     files_processed: int = 0, 
                     llm_calls: int = 0,
                     cache_hits: int = 0,
                     cache_misses: int = 0,
                     errors: int = 0,
                     warnings: int = 0):
        """End tracking an operation and calculate metrics."""
        if not self.enable_detailed_tracking or operation_name not in self.metrics:
            return
        
        metric = self.metrics[operation_name]
        metric.end_time = time.time()
        metric.duration = metric.end_time - metric.start_time
        metric.memory_end = self._get_memory_usage()
        metric.files_processed = files_processed
        metric.llm_calls = llm_calls
        metric.cache_hits = cache_hits
        metric.cache_misses = cache_misses
        metric.errors = errors
        metric.warnings = warnings
        
        # Calculate peak memory for this operation
        if self.memory_samples:
            operation_samples = [
                mem for timestamp, mem in self.memory_samples
                if metric.start_time <= timestamp <= metric.end_time
            ]
            metric.memory_peak = max(operation_samples) if operation_samples else metric.memory_end
        
        # Print summary
        print(f"✅ Completed: {operation_name}")
        print(f"   Duration: {metric.duration:.1f}s")
        print(f"   Memory: {metric.memory_start:.1f} → {metric.memory_end:.1f} MB (Peak: {metric.memory_peak:.1f} MB)")
        if files_processed > 0:
            print(f"   Files: {files_processed} ({files_processed/metric.duration:.1f} files/sec)")
        if llm_calls > 0:
            print(f"   LLM Calls: {llm_calls} ({llm_calls/metric.duration:.1f} calls/sec)")
        if cache_hits + cache_misses > 0:
            cache_rate = cache_hits / (cache_hits + cache_misses) * 100
            print(f"   Cache: {cache_hits} hits, {cache_misses} misses ({cache_rate:.1f}% hit rate)")
        if errors > 0:
            print(f"   ⚠️ Errors: {errors}")
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except Exception:
            return 0.0
    
    def _start_memory_monitoring(self):
        """Start background memory monitoring."""
        def monitor_memory():
            while not self._stop_monitoring:
                timestamp = time.time()
                memory = self._get_memory_usage()
                self.memory_samples.append((timestamp, memory))
                
                # Keep only last 1000 samples to avoid memory bloat
                if len(self.memory_samples) > 1000:
                    self.memory_samples = self.memory_samples[-1000:]
                
                time.sleep(5)  # Sample every 5 seconds
        
        self._monitoring_thread = threading.Thread(target=monitor_memory, daemon=True)
        self._monitoring_thread.start()
    
    def generate_optimization_recommendations(self, total_files: int, total_size_mb: float) -> List[str]:
        """Generate optimization recommendations based on analysis metrics."""
        recommendations = []
        
        # Memory optimization recommendations
        peak_memory = max((mem for _, mem in self.memory_samples), default=0)
        if peak_memory > 2048:  # > 2GB
            recommendations.append(
                f"🔧 High memory usage detected ({peak_memory:.1f} MB). "
                "Consider enabling content truncation for large files."
            )
        
        # File processing recommendations
        if total_files > 1000:
            recommendations.append(
                f"📊 Large repository detected ({total_files} files). "
                "Consider using parallel processing or file filtering."
            )
        
        # LLM call optimization
        total_llm_calls = sum(metric.llm_calls for metric in self.metrics.values())
        if total_llm_calls > 100:
            recommendations.append(
                f"🤖 High LLM usage ({total_llm_calls} calls). "
                "Consider enabling response caching or batch processing."
            )
        
        # Cache performance
        total_cache_hits = sum(metric.cache_hits for metric in self.metrics.values())
        total_cache_misses = sum(metric.cache_misses for metric in self.metrics.values())
        if total_cache_misses > 0:
            cache_rate = total_cache_hits / (total_cache_hits + total_cache_misses) * 100
            if cache_rate < 50:
                recommendations.append(
                    f"💾 Low cache hit rate ({cache_rate:.1f}%). "
                    "Consider increasing cache size or enabling persistent caching."
                )
        
        # Processing speed recommendations
        for metric in self.metrics.values():
            if metric.files_processed > 0 and metric.duration:
                files_per_sec = metric.files_processed / metric.duration
                if files_per_sec < 1 and metric.files_processed > 10:
                    recommendations.append(
                        f"⏱️ Slow file processing in {metric.operation_name} "
                        f"({files_per_sec:.2f} files/sec). Consider parallel processing."
                    )
        
        return recommendations
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary."""
        total_duration = time.time() - self.overall_start_time
        total_files = sum(metric.files_processed for metric in self.metrics.values())
        total_llm_calls = sum(metric.llm_calls for metric in self.metrics.values())
        total_errors = sum(metric.errors for metric in self.metrics.values())
        
        peak_memory = max((mem for _, mem in self.memory_samples), default=0) if self.memory_samples else 0
        current_memory = self._get_memory_usage()
        
        return {
            "overall_duration": total_duration,
            "total_files_processed": total_files,
            "total_llm_calls": total_llm_calls,
            "total_errors": total_errors,
            "peak_memory_mb": peak_memory,
            "current_memory_mb": current_memory,
            "files_per_second": total_files / total_duration if total_duration > 0 else 0,
            "operations": {
                name: {
                    "duration": metric.duration,
                    "files_processed": metric.files_processed,
                    "llm_calls": metric.llm_calls,
                    "memory_peak": metric.memory_peak,
                    "cache_hits": metric.cache_hits,
                    "cache_misses": metric.cache_misses,
                    "errors": metric.errors
                }
                for name, metric in self.metrics.items()
                if metric.duration is not None
            },
            "optimization_recommendations": self.optimization_recommendations
        }
    
    def save_performance_report(self, output_path: str):
        """Save detailed performance report."""
        report = self.get_performance_summary()
        
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📊 Performance report saved: {output_path}")
    
    def stop_monitoring(self):
        """Stop background monitoring."""
        self._stop_monitoring = True
        if self._monitoring_thread:
            self._monitoring_thread.join(timeout=1)


class ResourceOptimizer:
    """
    Resource optimization utilities for large repository analysis.
    """
    
    @staticmethod
    def estimate_analysis_requirements(files_data: List[tuple], 
                                     enable_llm_analysis: bool = True) -> Dict[str, Any]:
        """Estimate resource requirements for analysis."""
        total_files = len(files_data)
        total_size = sum(len(content) for _, content in files_data)
        
        # File type analysis
        java_files = sum(1 for path, _ in files_data if path.endswith('.java'))
        config_files = sum(1 for path, _ in files_data if any(path.endswith(ext) for ext in ['.xml', '.properties', '.yml', '.yaml']))
        build_files = sum(1 for path, _ in files_data if any(name in path for name in ['pom.xml', 'build.gradle']))
        
        # Memory estimation (rough)
        estimated_memory_mb = (total_size / 1024 / 1024) * 2  # 2x content size for processing overhead
        
        # Time estimation
        estimated_minutes = 0
        if enable_llm_analysis:
            # Estimate based on file types and LLM calls
            estimated_llm_calls = java_files + config_files + build_files
            estimated_minutes = estimated_llm_calls * 0.5  # ~30 seconds per LLM call
        else:
            # Static analysis only
            estimated_minutes = total_files * 0.02  # ~1 second per file
        
        return {
            "total_files": total_files,
            "total_size_mb": total_size / 1024 / 1024,
            "file_breakdown": {
                "java_files": java_files,
                "config_files": config_files,
                "build_files": build_files,
                "other_files": total_files - java_files - config_files - build_files
            },
            "estimated_memory_mb": estimated_memory_mb,
            "estimated_duration_minutes": estimated_minutes,
            "recommended_settings": ResourceOptimizer.get_recommended_settings(total_files, total_size)
        }
    
    @staticmethod
    def get_recommended_settings(total_files: int, total_size: int) -> Dict[str, Any]:
        """Get recommended settings based on repository size."""
        settings = {
            "enable_caching": True,
            "enable_parallel_processing": False,
            "max_content_length": 10000,
            "batch_size": 10,
            "enable_content_truncation": False,
            "skip_large_files": False,
            "max_file_size_mb": 1
        }
        
        # Adjust based on repository size
        if total_files > 500:
            settings["enable_parallel_processing"] = True
            settings["batch_size"] = 20
        
        if total_files > 1000:
            settings["max_content_length"] = 5000
            settings["enable_content_truncation"] = True
        
        if total_size > 100 * 1024 * 1024:  # > 100MB
            settings["skip_large_files"] = True
            settings["max_file_size_mb"] = 0.5
        
        if total_files > 2000:
            settings["max_content_length"] = 3000
            settings["batch_size"] = 50
        
        return settings
    
    @staticmethod
    def filter_files_for_analysis(files_data: List[tuple], 
                                 max_files: int = None,
                                 prioritize_spring_files: bool = True) -> List[tuple]:
        """Filter and prioritize files for analysis to optimize performance."""
        
        if not max_files or len(files_data) <= max_files:
            return files_data
        
        # Prioritize Spring-relevant files
        spring_priority_patterns = [
            'pom.xml', 'build.gradle', 'application.', 'config', 
            'controller', 'service', 'repository', 'entity', 'component',
            'security', 'boot', 'spring'
        ]
        
        prioritized_files = []
        regular_files = []
        
        for file_path, content in files_data:
            is_priority = any(pattern.lower() in file_path.lower() for pattern in spring_priority_patterns)
            
            if is_priority:
                prioritized_files.append((file_path, content))
            else:
                regular_files.append((file_path, content))
        
        # Take all priority files plus fill remaining quota with regular files
        result = prioritized_files
        remaining_quota = max_files - len(prioritized_files)
        
        if remaining_quota > 0:
            result.extend(regular_files[:remaining_quota])
        
        if len(result) < len(files_data):
            print(f"🎯 Optimized file selection: {len(result)}/{len(files_data)} files (prioritized Spring-relevant files)")
        
        return result


class ConcurrentAnalysisManager:
    """
    Manages concurrent analysis operations for improved performance.
    """
    
    def __init__(self, max_workers: int = None, enable_batching: bool = True):
        import concurrent.futures
        
        self.max_workers = max_workers or min(32, (os.cpu_count() or 1) + 4)
        self.enable_batching = enable_batching
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
    
    def process_files_concurrently(self, files_data: List[tuple], 
                                 process_function, 
                                 batch_size: int = 10,
                                 **kwargs) -> List[Any]:
        """Process files concurrently with batching support."""
        import concurrent.futures
        
        if not self.enable_batching or len(files_data) <= batch_size:
            # Process all files in parallel
            futures = []
            for file_path, content in files_data:
                future = self.executor.submit(process_function, file_path, content, **kwargs)
                futures.append(future)
            
            results = []
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    print(f"Error processing file: {e}")
            
            return results
        else:
            # Process in batches to manage memory
            all_results = []
            for i in range(0, len(files_data), batch_size):
                batch = files_data[i:i + batch_size]
                print(f"Processing batch {i//batch_size + 1}/{(len(files_data) + batch_size - 1)//batch_size}...")
                
                futures = []
                for file_path, content in batch:
                    future = self.executor.submit(process_function, file_path, content, **kwargs)
                    futures.append(future)
                
                batch_results = []
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            batch_results.append(result)
                    except Exception as e:
                        print(f"Error processing file: {e}")
                
                all_results.extend(batch_results)
            
            return all_results
    
    def shutdown(self):
        """Shutdown the executor."""
        self.executor.shutdown(wait=True)


# Global performance monitor instance
_global_monitor = None

def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor

def enable_performance_monitoring(enable_detailed_tracking: bool = True):
    """Enable global performance monitoring."""
    global _global_monitor
    _global_monitor = PerformanceMonitor(enable_detailed_tracking=enable_detailed_tracking) 