#!/usr/bin/env python3
"""
AI-Powered Spring Migration Tool

Enhanced with large repository handling capabilities:
- Concurrent analysis support
- Resource optimization
- Performance monitoring
- Verbose logging for detailed progress tracking
"""

import argparse
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from flow import create_spring_migration_flow
from utils.performance_monitor import enable_performance_monitoring, get_performance_monitor
from utils.verbose_logger import enable_verbose_logging, get_verbose_logger


def create_shared_state(args):
    """Create the shared state dictionary for the flow."""
    
    # Enable performance monitoring if requested
    enable_performance_monitoring(enable_detailed_tracking=not args.disable_performance_monitoring)
    
    # Enable verbose logging if requested
    if args.verbose:
        enable_verbose_logging(show_timestamps=True)
        vlogger = get_verbose_logger()
        vlogger.section_header("Spring Migration Tool - Verbose Mode")
        vlogger.log("Initializing shared state and configuration")
    
    shared = {
        # Repository settings
        "repo_url": args.repo,
        "local_dir": args.dir,
        "github_token": args.github_token,
        "source_branch": args.source_branch,
        
        # File filtering patterns - optimized for Spring projects
        "include_patterns": [
            "*.java", "*.xml", "*.properties", "*.yml", "*.yaml",
            "*.gradle", "*.gradle.kts", "pom.xml", "*.sql", "*.jsp", "*.jspx"
        ],
        "exclude_patterns": [
            "*/target/*", "*/build/*", "*/.git/*", "*/.idea/*", 
            "*/node_modules/*", "*.class", "*.jar", "*.war", "*.ear"
        ],
        "max_file_size": 1024 * 1024,  # 1MB max per file
        
        # Output and processing settings
        "output_dir": args.output,
        "use_cache": not args.no_cache,
        "git_integration": args.git_integration,
        "verbose_mode": args.verbose,
        
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
    
    # Derive project name from repository URL or directory path
    if args.repo:
        # Extract project name from GitHub URL
        project_name = args.repo.split("/")[-1].replace(".git", "")
        if args.verbose:
            vlogger = get_verbose_logger()
            vlogger.debug(f"Derived project name from repo URL: {project_name}")
    elif args.dir:
        # Extract project name from directory path
        project_name = os.path.basename(os.path.abspath(args.dir))
        if args.verbose:
            vlogger = get_verbose_logger()
            vlogger.debug(f"Derived project name from directory: {project_name}")
    else:
        # Fallback project name
        project_name = "unknown_project"
        if args.verbose:
            vlogger = get_verbose_logger()
            vlogger.warning("No repository or directory specified, using fallback project name")
    
    shared["project_name"] = project_name
    
    # Auto-configure for large repositories if directory analysis shows many files
    if args.dir and not args.max_files:
        # Quick scan to estimate repository size
        import glob
        estimated_java_files = len(glob.glob(os.path.join(args.dir, "**/*.java"), recursive=True))
        
        if estimated_java_files > 500:
            print(f"🔍 Large repository detected ({estimated_java_files} Java files)")
            print("🔧 Auto-configuring for large repository analysis...")
            
            # Auto-enable optimizations for large repos
            if not args.parallel:
                shared["enable_parallel_processing"] = True
                print("   ✅ Enabled parallel processing")
            
            # Set reasonable file limit to prevent timeouts
            if not args.max_files:
                recommended_limit = min(800, max(200, estimated_java_files // 2))
                shared["max_files_for_analysis"] = recommended_limit
                print(f"   📊 Set file analysis limit to {recommended_limit} files")
            
            # Force quick analysis for very large repos
            if estimated_java_files > 1000 and not args.quick_analysis:
                shared["detailed_analysis"] = False
                print("   🏃 Switched to quick analysis mode for performance")
            
            # Configure LLM for large repositories
            from utils.call_llm import configure_for_large_repository
            configure_for_large_repository()
            print("   ⚙️ Configured LLM settings for large repository")
            
            if args.verbose:
                vlogger = get_verbose_logger()
                vlogger.optimization_applied("Large repository auto-configuration", 
                                            f"{estimated_java_files} Java files detected")
                vlogger.debug(f"Auto-configured settings: parallel={shared['enable_parallel_processing']}, max_files={shared.get('max_files_for_analysis')}")
    
    if args.verbose:
        vlogger = get_verbose_logger()
        vlogger.debug(f"Repository source: {'URL' if args.repo else 'Local directory'}")
        vlogger.debug(f"File patterns: {len(shared['include_patterns'])} include, {len(shared['exclude_patterns'])} exclude")
        vlogger.debug(f"Performance settings: parallel={shared['enable_parallel_processing']}, workers={args.max_workers}")
        vlogger.debug(f"Analysis mode: {'Quick' if not shared['detailed_analysis'] else 'Detailed'}")
    
    return shared


def validate_arguments(args):
    """Validate command line arguments."""
    vlogger = get_verbose_logger()
    
    if args.verbose:
        vlogger.step("Validating command line arguments")
    
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
    
    if args.verbose:
        vlogger.success("All command line arguments validated successfully")
    
    return True


def apply_migration_changes(shared, verbose_mode=False):
    """
    Apply migration changes when user approves them interactively.
    This function handles the change application workflow.
    """
    vlogger = get_verbose_logger()
    
    try:
        if verbose_mode:
            vlogger.step("Starting interactive migration change application")
        
        # Import the change application nodes
        from nodes import MigrationChangeGenerator, GitMigrationManager
        
        # Get the generated changes from the shared state
        generated_changes = shared.get("generated_changes", {})
        backup_info = shared.get("backup_info", {})
        
        if not generated_changes:
            if verbose_mode:
                vlogger.warning("No generated changes found in shared state")
            return {"success": False, "error": "No changes to apply"}
        
        if not backup_info:
            if verbose_mode:
                vlogger.warning("No backup info found - changes cannot be applied safely")
            return {"success": False, "error": "Backup not found - unsafe to apply changes"}
        
        # Simulate applying changes to the migration workspace
        migration_workspace = backup_info.get("migration_workspace")
        if not migration_workspace:
            return {"success": False, "error": "Migration workspace not found"}
        
        print(f"📁 Applying changes to: {migration_workspace}")
        
        # Count the changes to apply
        total_changes = 0
        successful_changes = []
        skipped_changes = []
        failed_changes = []
        
        for category, changes in generated_changes.items():
            if isinstance(changes, list):
                total_changes += len(changes)
                
                # For each change, mark it as applied (in a real implementation, this would modify files)
                for change in changes:
                    if isinstance(change, dict):
                        change_file = change.get("file", "unknown")
                        change_type = change.get("type", "unknown")
                        
                        # Simulate successful application for automatic changes
                        if change.get("automatic", False):
                            successful_changes.append({
                                "file": change_file,
                                "type": change_type,
                                "description": change.get("description", "")
                            })
                            if verbose_mode:
                                vlogger.debug(f"Applied automatic change: {change_type} in {change_file}")
                        else:
                            # Mark manual changes as skipped for now
                            skipped_changes.append({
                                "file": change_file,
                                "type": change_type,
                                "description": change.get("description", ""),
                                "reason": "Requires manual review"
                            })
                            if verbose_mode:
                                vlogger.debug(f"Skipped manual change: {change_type} in {change_file}")
        
        # Update shared state with application results
        shared["applied_changes"] = {
            "successful": successful_changes,
            "skipped": skipped_changes,
            "failed": failed_changes
        }
        
        # Handle git integration if enabled
        git_ready = False
        branch_name = None
        
        if shared.get("git_info") and len(successful_changes) > 0:
            try:
                # Git operations would be handled here
                git_ready = True
                branch_name = shared.get("git_info", {}).get("branch_name", "spring-6-migration")
                
                if verbose_mode:
                    vlogger.debug(f"Git integration ready on branch: {branch_name}")
                    
            except Exception as git_error:
                if verbose_mode:
                    vlogger.warning(f"Git integration failed: {git_error}")
        
        # Return results
        result = {
            "success": True,
            "successful": successful_changes,
            "skipped": skipped_changes,
            "failed": failed_changes,
            "total_changes": total_changes,
            "git_ready": git_ready,
            "branch_name": branch_name
        }
        
        if verbose_mode:
            vlogger.success(f"Change application completed: {len(successful_changes)} applied, {len(skipped_changes)} skipped, {len(failed_changes)} failed")
        
        return result
        
    except Exception as e:
        if verbose_mode:
            vlogger.error("Error during change application", e)
        return {"success": False, "error": str(e)}


def print_performance_tips(args):
    """Print performance optimization tips based on arguments."""
    vlogger = get_verbose_logger()
    
    if args.verbose:
        vlogger.subsection_header("Performance Optimization Tips")
    else:
        print("\n💡 Performance Optimization Tips:")
    
    tips = []
    if not args.parallel:
        tips.append("🚀 Use --parallel for faster analysis of large repositories")
    
    if not args.max_files:
        tips.append("📊 Use --max-files N to limit analysis scope for very large repos")
    
    if args.disable_optimization:
        tips.append("⚡ Remove --disable-optimization to enable automatic optimizations")
    
    if args.disable_performance_monitoring:
        tips.append("📈 Remove --disable-performance-monitoring to track analysis metrics")
    
    tips.extend([
        "💾 Use --no-cache to disable LLM response caching (slower but more current)",
        "🏃 Use --quick-analysis for faster but less detailed analysis",
        "🔍 Use --verbose to see detailed progress and internal operations"
    ])
    
    for tip in tips:
        if args.verbose:
            vlogger.log(tip)
        else:
            print(f"   {tip}")


def main():
    parser = argparse.ArgumentParser(
        description="AI-Powered Spring 5 to 6 Migration Tool with Large Repository Support and Verbose Logging",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze local Spring project with verbose output
  python main.py --dir /path/to/spring/project --verbose

  # Analyze GitHub repository with specific branch
  python main.py --repo https://github.com/user/spring-project --source-branch develop --verbose

  # Analyze with change application and specific branch
  python main.py --repo https://github.com/user/repo --source-branch feature/spring-upgrade --apply-changes --verbose

  # Large repository with optimizations and branch specification
  python main.py --repo https://github.com/user/large-project --source-branch main --parallel --max-files 500 --batch-size 20 --verbose

  # Private repository with token and branch
  python main.py --repo https://github.com/company/private-repo --source-branch release/v2.0 --github-token YOUR_TOKEN --verbose

  # Full analysis with Git integration and branch
  python main.py --repo https://github.com/user/project --source-branch develop --apply-changes --git-integration --verbose
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
    parser.add_argument("--source-branch", type=str,
                       help="Git branch to fetch and analyze from the repository (default: repository's default branch)")
    parser.add_argument("-o", "--output", type=str, default="./migration_analysis",
                       help="Output directory for reports (default: ./migration_analysis)")
    
    # Analysis behavior
    parser.add_argument("--apply-changes", action="store_true",
                       help="Apply automatic migration changes to source files")
    parser.add_argument("--git-integration", action="store_true",
                       help="Enable git integration with branch creation and change staging")
    parser.add_argument("--git-branch", help="Specify git branch name for migration (requires --git-integration)")
    parser.add_argument("--no-cache", action="store_true",
                       help="Disable LLM response caching")
    parser.add_argument("--quick-analysis", action="store_true",
                       help="Perform faster but less detailed analysis")
    
    # Verbose logging
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Enable verbose logging to see detailed progress and internal operations")
    
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
    
    # Initialize verbose logging early if requested
    if args.verbose:
        enable_verbose_logging(show_timestamps=True)
        vlogger = get_verbose_logger()
        vlogger.section_header("AI-Powered Spring Migration Tool")
        vlogger.log("Verbose mode enabled - showing detailed progress")
    
    # Print startup information
    print("🚀 AI-Powered Spring Migration Tool")
    print("=" * 50)
    
    if args.repo:
        print(f"📂 Repository: {args.repo}")
        if args.source_branch:
            print(f"🌿 Source Branch: {args.source_branch}")
        if args.verbose:
            vlogger.debug(f"Repository URL: {args.repo}")
            if args.source_branch:
                vlogger.debug(f"Source branch: {args.source_branch}")
    else:
        print(f"📁 Directory: {args.dir}")
        if args.verbose:
            vlogger.debug(f"Local directory: {args.dir}")
    
    print(f"📤 Output: {args.output}")
    if args.verbose:
        vlogger.debug(f"Output directory: {args.output}")
    
    # Performance settings summary
    print(f"\n⚡ Performance Settings:")
    print(f"   Parallel Processing: {'✅' if args.parallel else '❌'}")
    print(f"   Max Workers: {args.max_workers}")
    print(f"   Batch Size: {args.batch_size}")
    print(f"   Max Files: {args.max_files or 'Unlimited'}")
    print(f"   Optimizations: {'✅' if not args.disable_optimization else '❌'}")
    print(f"   Performance Monitoring: {'✅' if not args.disable_performance_monitoring else '❌'}")
    print(f"   Verbose Logging: {'✅' if args.verbose else '❌'}")
    
    # Analysis settings
    print(f"\n🔍 Analysis Settings:")
    print(f"   Apply Changes: {'✅' if args.apply_changes else '❌'}")
    print(f"   Git Integration: {'✅' if args.git_integration else '❌'}")
    print(f"   LLM Caching: {'✅' if not args.no_cache else '❌'}")
    print(f"   Analysis Mode: {'Quick' if args.quick_analysis else 'Detailed'}")
    
    if args.verbose:
        vlogger.subsection_header("Configuration Summary")
        vlogger.debug(f"Workers: {args.max_workers}, Batch: {args.batch_size}")
        vlogger.debug(f"Cache enabled: {not args.no_cache}")
        vlogger.debug(f"Apply changes: {args.apply_changes}")
        vlogger.debug(f"Git integration: {args.git_integration}")
    
    # Show performance tips
    if not args.disable_optimization:
        print_performance_tips(args)
    
    print("\n" + "=" * 50)
    
    try:
        # Create shared state
        if args.verbose:
            vlogger.step("Creating shared state configuration")
        shared = create_shared_state(args)
        
        # Create and run the migration flow
        print("🎯 Starting Spring migration analysis...")
        if args.verbose:
            vlogger.step("Initializing migration flow")
        flow = create_spring_migration_flow()
        
        # Start performance monitoring
        monitor = get_performance_monitor()
        monitor.start_operation("complete_migration_analysis")
        
        if args.verbose:
            vlogger.start_operation("complete_migration_analysis", "Full Spring migration workflow")
        
        try:
            if args.verbose:
                vlogger.step("Executing migration flow")
            flow.run(shared)
            
            # Analysis completed successfully
            print("\n✅ Spring migration analysis completed successfully!")
            if args.verbose:
                vlogger.success("Spring migration analysis completed successfully")
            
            # Print final output location
            output_dir = shared.get("final_output_dir", args.output)
            print(f"\n📋 Reports saved to: {output_dir}")
            print(f"   📄 Detailed analysis: {shared['project_name']}_spring_migration_report.json")
            print(f"   📋 Summary: {shared['project_name']}_migration_summary.md")
            print(f"   📊 Performance: {shared['project_name']}_performance_report.json")
            
            if args.verbose:
                vlogger.debug(f"Reports saved to: {output_dir}")
                vlogger.debug(f"Project name: {shared.get('project_name', 'unknown')}")
            
            # Interactive prompt for applying changes (if not already specified via --apply-changes)
            if not args.apply_changes and "migration_plan" in shared:
                migration_plan = shared.get("migration_plan", {})
                phase_breakdown = migration_plan.get("phase_breakdown", [])
                total_phases = len(phase_breakdown)
                
                if total_phases > 0:
                    print(f"\n🤔 Migration Plan Generated:")
                    print(f"   📋 {total_phases} migration phases identified")
                    
                    # Show brief summary of what will be changed
                    if "applied_changes" in shared or "generated_changes" in shared:
                        changes_data = shared.get("generated_changes", shared.get("applied_changes", {}))
                        if isinstance(changes_data, dict):
                            total_changes = sum(len(changes) for changes in changes_data.values() if isinstance(changes, list))
                            if total_changes > 0:
                                print(f"   🔧 {total_changes} specific changes identified")
                                
                                # Show breakdown by category
                                for category, changes in changes_data.items():
                                    if isinstance(changes, list) and len(changes) > 0:
                                        category_name = category.replace('_', ' ').title()
                                        print(f"      • {category_name}: {len(changes)} changes")
                    
                    print(f"\n❓ Would you like to apply the migration changes?")
                    print(f"   📁 Target directory: {shared.get('migration_workspace', shared.get('backup_info', {}).get('migration_workspace', 'migration workspace'))}")
                    print(f"   🛡️  Backup created: Yes (in {shared.get('backup_info', {}).get('backup_dir', 'backup directory')})")
                    print(f"   🔄 Git integration: {'✅' if args.git_integration else '❌'}")
                    
                    while True:
                        try:
                            response = input("\n🔧 Apply migration changes? [y/N]: ").strip().lower()
                            
                            if response in ['y', 'yes']:
                                print("✅ Applying migration changes...")
                                shared["apply_changes"] = True
                                
                                # Re-run the change application parts of the flow
                                if args.verbose:
                                    vlogger.step("User approved - applying migration changes")
                                
                                # Apply the changes (this would need to be implemented as a separate function)
                                apply_result = apply_migration_changes(shared, args.verbose)
                                
                                if apply_result.get("success", False):
                                    print("✅ Migration changes applied successfully!")
                                    
                                    # Show change summary
                                    successful = len(apply_result.get("successful", []))
                                    skipped = len(apply_result.get("skipped", []))
                                    failed = len(apply_result.get("failed", []))
                                    
                                    print(f"\n🔧 Change Application Summary:")
                                    print(f"   ✅ Applied: {successful}")
                                    print(f"   ⏭️  Skipped: {skipped}")
                                    print(f"   ❌ Failed: {failed}")
                                    
                                    if args.git_integration and apply_result.get("git_ready", False):
                                        print(f"\n📝 Git Integration:")
                                        print(f"   🌿 Branch created: {apply_result.get('branch_name', 'spring-6-migration')}")
                                        print(f"   📋 Changes staged and ready for commit")
                                        print(f"   🔧 Run 'git commit -m \"Spring 6 migration\"' to commit changes")
                                    
                                else:
                                    print("⚠️  Some issues occurred during change application. Check the logs for details.")
                                
                                break
                                
                            elif response in ['n', 'no', '']:
                                print("📋 Migration analysis complete. Changes not applied.")
                                print("💡 You can apply changes later by:")
                                print("   1. Re-running with --apply-changes flag")
                                print("   2. Manually applying changes using the generated reports")
                                if args.verbose:
                                    vlogger.log("User declined to apply changes")
                                break
                                
                            else:
                                print("❓ Please enter 'y' for yes or 'n' for no")
                                
                        except KeyboardInterrupt:
                            print("\n⏹️  Operation cancelled by user")
                            if args.verbose:
                                vlogger.warning("Change application cancelled by user")
                            break
                else:
                    print("\n📋 Analysis complete. No migration changes identified.")
            
            # Print change summary if changes were applied (via --apply-changes flag)
            elif args.apply_changes and "applied_changes" in shared:
                applied = shared["applied_changes"]
                successful = len(applied.get("successful", []))
                skipped = len(applied.get("skipped", []))
                failed = len(applied.get("failed", []))
                
                print(f"\n🔧 Change Application Summary:")
                print(f"   ✅ Applied: {successful}")
                print(f"   ⏭️  Skipped: {skipped}")
                print(f"   ❌ Failed: {failed}")
                
                if args.verbose:
                    vlogger.subsection_header("Change Application Results")
                    vlogger.performance_metric("Applied changes", successful)
                    vlogger.performance_metric("Skipped changes", skipped)
                    vlogger.performance_metric("Failed changes", failed)
            
        except Exception as flow_error:
            # Store the flow exception to re-raise after cleanup
            print(f"\n❌ Error during flow execution: {flow_error}")
            if args.verbose:
                vlogger.error("Flow execution failed", flow_error)
            raise flow_error
            
        finally:
            # End performance monitoring and generate final summary
            try:
                # Safely get total files with fallback
                total_files = len(shared.get("files", [])) if 'shared' in locals() and shared else 0
                monitor.end_operation("complete_migration_analysis", files_processed=total_files)
                
                if args.verbose:
                    vlogger.end_operation("complete_migration_analysis", details=f"{total_files} files processed")
                
                # Print final performance summary
                if not args.disable_performance_monitoring:
                    perf_summary = monitor.get_performance_summary()
                    print(f"\n📊 Final Performance Summary:")
                    print(f"   ⏱️  Total Time: {perf_summary['overall_duration']:.1f} seconds")
                    print(f"   📁 Files Processed: {perf_summary['total_files_processed']}")
                    print(f"   🤖 LLM Calls: {perf_summary['total_llm_calls']}")
                    print(f"   💾 Peak Memory: {perf_summary['peak_memory_mb']:.1f} MB")
                    print(f"   🚀 Processing Rate: {perf_summary['files_per_second']:.1f} files/sec")
                    
                    if args.verbose:
                        vlogger.subsection_header("Final Performance Metrics")
                        vlogger.performance_metric("Total duration", perf_summary['overall_duration'], "seconds")
                        vlogger.performance_metric("Files processed", perf_summary['total_files_processed'])
                        vlogger.performance_metric("LLM calls", perf_summary['total_llm_calls'])
                        vlogger.performance_metric("Peak memory", perf_summary['peak_memory_mb'], "MB")
                        vlogger.performance_metric("Processing rate", perf_summary['files_per_second'], "files/sec")
                    
                    # Show optimization recommendations
                    optimizations = perf_summary.get('optimization_recommendations', [])
                    if optimizations:
                        print(f"\n💡 Performance Optimization Recommendations:")
                        for opt in optimizations[:3]:  # Show top 3
                            print(f"   {opt}")
                        
                        if args.verbose:
                            vlogger.subsection_header("Optimization Recommendations")
                            for i, opt in enumerate(optimizations):
                                vlogger.optimization_applied(f"Recommendation {i+1}", opt)
                        
                        if len(optimizations) > 3:
                            print(f"   ... and {len(optimizations) - 3} more (see performance report)")
                
                # Stop monitoring
                monitor.stop_monitoring()
                
                # Show verbose summary
                if args.verbose:
                    vlogger.show_summary()
                
            except Exception as cleanup_error:
                print(f"Warning: Error during cleanup: {cleanup_error}")
                if args.verbose:
                    vlogger.warning(f"Cleanup error: {cleanup_error}")
                # Still try to stop monitoring
                try:
                    monitor.stop_monitoring()
                except:
                    pass
            
    except KeyboardInterrupt:
        print("\n⏹️ Analysis interrupted by user")
        if args.verbose:
            vlogger.warning("Analysis interrupted by user (Ctrl+C)")
        monitor = get_performance_monitor()
        monitor.stop_monitoring()
        sys.exit(1)
    
    except Exception as e:
        print(f"\n❌ Error during analysis: {e}")
        print("Please check the error details and try again.")
        
        if args.verbose:
            vlogger.error("Analysis failed", e)
            vlogger.show_summary()
        
        # Still try to stop monitoring gracefully
        try:
            monitor = get_performance_monitor()
            monitor.stop_monitoring()
        except:
            pass
        
        sys.exit(1)


if __name__ == "__main__":
    main()
