#!/usr/bin/env python3
"""
AI-Powered Spring Migration Tool

Enhanced with large repository handling capabilities:
- Concurrent analysis support
- Resource optimization
- Performance monitoring
"""

import argparse
import sys
import os
from flow import create_spring_migration_flow
from utils.performance_monitor import enable_performance_monitoring, get_performance_monitor


def create_shared_state(args):
    """Create the shared state dictionary for the flow."""
    
    # Enable performance monitoring if requested
    enable_performance_monitoring(enable_detailed_tracking=not args.disable_performance_monitoring)
    
    shared = {
        # Repository settings
        "repo_url": args.repo,
        "local_dir": args.dir,
        "github_token": args.github_token,
        
        # File filtering patterns - optimized for Spring projects
        "include_patterns": [
            "*.java", "*.xml", "*.properties", "*.yml", "*.yaml",
            "*.gradle", "*.gradle.kts", "pom.xml", "*.sql", "*.jsp", "*.jspx"
        ],
        "exclude_patterns": [
            "*/target/*", "*/build/*", "*/.git/*", "*/.idea/*", 
            "*/node_modules/*", "*.class", "*.jar", "*.war", "*.ear",
            "*/test/*", "*/tests/*", "*Test.java", "*Tests.java"
        ],
        "max_file_size": 1024 * 1024,  # 1MB max per file
        
        # Output and processing settings
        "output_dir": args.output,
        "use_cache": not args.no_cache,
        "git_integration": args.git_integration,
        
        # Performance optimization settings
        "enable_optimization": not args.disable_optimization,
        "max_files_for_analysis": args.max_files,
        "enable_parallel_processing": args.parallel,
        "max_workers": args.max_workers,
        "batch_size": args.batch_size,
        
        # Analysis settings
        "apply_changes": args.apply_changes,
        "detailed_analysis": not args.quick_analysis,
    }
    
    return shared


def validate_arguments(args):
    """Validate command line arguments."""
    
    if not args.repo and not args.dir:
        print("❌ Error: Either --repo or --dir must be specified")
        return False
    
    if args.repo and args.dir:
        print("❌ Error: Cannot specify both --repo and --dir")
        return False
    
    if args.dir and not os.path.exists(args.dir):
        print(f"❌ Error: Directory does not exist: {args.dir}")
        return False
    
    # Validate performance settings
    if args.max_workers and args.max_workers < 1:
        print("❌ Error: --max-workers must be at least 1")
        return False
    
    if args.batch_size and args.batch_size < 1:
        print("❌ Error: --batch-size must be at least 1")
        return False
    
    if args.max_files and args.max_files < 10:
        print("❌ Error: --max-files must be at least 10")
        return False
    
    return True


def print_performance_tips(args):
    """Print performance optimization tips based on arguments."""
    
    print("\n💡 Performance Optimization Tips:")
    
    if not args.parallel:
        print("   🚀 Use --parallel for faster analysis of large repositories")
    
    if not args.max_files:
        print("   📊 Use --max-files N to limit analysis scope for very large repos")
    
    if args.disable_optimization:
        print("   ⚡ Remove --disable-optimization to enable automatic optimizations")
    
    if args.disable_performance_monitoring:
        print("   📈 Remove --disable-performance-monitoring to track analysis metrics")
    
    print("   💾 Use --no-cache to disable LLM response caching (slower but more current)")
    print("   🏃 Use --quick-analysis for faster but less detailed analysis")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered Spring 5 to 6 Migration Tool with Large Repository Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze local Spring project
  python main.py --dir /path/to/spring/project

  # Analyze with change application
  python main.py --dir /path/to/spring/project --apply-changes

  # Large repository with optimizations
  python main.py --dir /path/to/large/project --parallel --max-files 500 --batch-size 20

  # Quick analysis with performance monitoring
  python main.py --dir /path/to/project --quick-analysis --max-workers 8

  # Full analysis with Git integration
  python main.py --dir /path/to/project --apply-changes --git-integration
        """
    )
    
    # Repository source (mutually exclusive)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--repo", type=str, 
                             help="GitHub repository URL (e.g., https://github.com/user/repo)")
    source_group.add_argument("--dir", type=str,
                             help="Local directory path to analyze")
    
    # Basic settings
    parser.add_argument("--github-token", type=str,
                       help="GitHub personal access token (for private repos)")
    parser.add_argument("-o", "--output", type=str, default="./migration_analysis",
                       help="Output directory for reports (default: ./migration_analysis)")
    
    # Analysis behavior
    parser.add_argument("--apply-changes", action="store_true",
                       help="Apply automatic migration changes to source files")
    parser.add_argument("--git-integration", action="store_true",
                       help="Enable Git operations (commit, push, PR preparation)")
    parser.add_argument("--no-cache", action="store_true",
                       help="Disable LLM response caching")
    parser.add_argument("--quick-analysis", action="store_true",
                       help="Perform faster but less detailed analysis")
    
    # Performance optimization options
    perf_group = parser.add_argument_group("Performance Options")
    perf_group.add_argument("--parallel", action="store_true",
                           help="Enable parallel processing for faster analysis")
    perf_group.add_argument("--max-workers", type=int, default=4,
                           help="Maximum number of concurrent workers (default: 4)")
    perf_group.add_argument("--batch-size", type=int, default=10,
                           help="Batch size for concurrent processing (default: 10)")
    perf_group.add_argument("--max-files", type=int,
                           help="Maximum number of files to analyze (for very large repos)")
    perf_group.add_argument("--disable-optimization", action="store_true",
                           help="Disable automatic performance optimizations")
    perf_group.add_argument("--disable-performance-monitoring", action="store_true",
                           help="Disable performance metrics collection")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not validate_arguments(args):
        sys.exit(1)
    
    # Print startup information
    print("🚀 AI-Powered Spring Migration Tool")
    print("=" * 50)
    
    if args.repo:
        print(f"📂 Repository: {args.repo}")
    else:
        print(f"📁 Directory: {args.dir}")
    
    print(f"📤 Output: {args.output}")
    
    # Performance settings summary
    print(f"\n⚡ Performance Settings:")
    print(f"   Parallel Processing: {'✅' if args.parallel else '❌'}")
    print(f"   Max Workers: {args.max_workers}")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Max Files: {args.max_files or 'Unlimited'}")
    print(f"   Optimizations: {'✅' if not args.disable_optimization else '❌'}")
    print(f"   Performance Monitoring: {'✅' if not args.disable_performance_monitoring else '❌'}")
    
    # Analysis settings
    print(f"\n🔍 Analysis Settings:")
    print(f"   Apply Changes: {'✅' if args.apply_changes else '❌'}")
    print(f"   Git Integration: {'✅' if args.git_integration else '❌'}")
    print(f"   LLM Caching: {'✅' if not args.no_cache else '❌'}")
    print(f"   Analysis Mode: {'Quick' if args.quick_analysis else 'Detailed'}")
    
    # Show performance tips
    if not args.disable_optimization:
        print_performance_tips(args)
    
    print("\n" + "=" * 50)
    
    try:
        # Create shared state
        shared = create_shared_state(args)
        
        # Create and run the migration flow
        print("🎯 Starting Spring migration analysis...")
        flow = create_spring_migration_flow()
        
        # Start performance monitoring
        monitor = get_performance_monitor()
        monitor.start_operation("complete_migration_analysis")
        
        try:
            flow.run(shared)
            
            # Analysis completed successfully
            print("\n✅ Spring migration analysis completed successfully!")
            
            # Print final output location
            output_dir = shared.get("final_output_dir", args.output)
            print(f"\n📋 Reports saved to: {output_dir}")
            print(f"   📄 Detailed analysis: {shared['project_name']}_spring_migration_report.json")
            print(f"   📋 Summary: {shared['project_name']}_migration_summary.md")
            print(f"   📊 Performance: {shared['project_name']}_performance_report.json")
            
            # Print change summary if changes were applied
            if args.apply_changes and "applied_changes" in shared:
                applied = shared["applied_changes"]
                successful = len(applied.get("successful", []))
                skipped = len(applied.get("skipped", []))
                failed = len(applied.get("failed", []))
                
                print(f"\n🔧 Change Application Summary:")
                print(f"   ✅ Applied: {successful}")
                print(f"   ⏭️  Skipped: {skipped}")
                print(f"   ❌ Failed: {failed}")
            
        except Exception as flow_error:
            # Store the flow exception to re-raise after cleanup
            print(f"\n❌ Error during flow execution: {flow_error}")
            raise flow_error
            
        finally:
            # End performance monitoring and generate final summary
            try:
                # Safely get total files with fallback
                total_files = len(shared.get("files", [])) if 'shared' in locals() and shared else 0
                monitor.end_operation("complete_migration_analysis", files_processed=total_files)
                
                # Print final performance summary
                if not args.disable_performance_monitoring:
                    perf_summary = monitor.get_performance_summary()
                    print(f"\n📊 Final Performance Summary:")
                    print(f"   ⏱️  Total Time: {perf_summary['overall_duration']:.1f} seconds")
                    print(f"   📁 Files Processed: {perf_summary['total_files_processed']}")
                    print(f"   🤖 LLM Calls: {perf_summary['total_llm_calls']}")
                    print(f"   💾 Peak Memory: {perf_summary['peak_memory_mb']:.1f} MB")
                    print(f"   🚀 Processing Rate: {perf_summary['files_per_second']:.1f} files/sec")
                    
                    # Show optimization recommendations
                    optimizations = perf_summary.get('optimization_recommendations', [])
                    if optimizations:
                        print(f"\n💡 Performance Optimization Recommendations:")
                        for opt in optimizations[:3]:  # Show top 3
                            print(f"   {opt}")
                        
                        if len(optimizations) > 3:
                            print(f"   ... and {len(optimizations) - 3} more (see performance report)")
                
                # Stop monitoring
                monitor.stop_monitoring()
                
            except Exception as cleanup_error:
                print(f"Warning: Error during cleanup: {cleanup_error}")
                # Still try to stop monitoring
                try:
                    monitor.stop_monitoring()
                except:
                    pass
            
    except KeyboardInterrupt:
        print("\n⏹️ Analysis interrupted by user")
        monitor = get_performance_monitor()
        monitor.stop_monitoring()
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("Please check the error details and try again.")
        
        # Still try to stop monitoring gracefully
        try:
            monitor = get_performance_monitor()
            monitor.stop_monitoring()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
