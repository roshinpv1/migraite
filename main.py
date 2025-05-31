import dotenv
import os
import argparse
# Import the function that creates the Spring migration flow
from flow import create_spring_migration_flow

dotenv.load_dotenv()

# Spring-specific file patterns for migration analysis
SPRING_INCLUDE_PATTERNS = {
    "*.java", "*.xml", "*.properties", "*.yml", "*.yaml", 
    "*.gradle", "*.gradle.kts", "pom.xml", "*.sql", "*.jpa",
    "*.jsp", "*.jspx", "*.tag", "*.tagx"
}

SPRING_EXCLUDE_PATTERNS = {
    "target/*", "build/*", "*.class", "*.jar", "*.war", "*.ear",
    "*test*", "*tests/*", "src/test/*", "test/*",
    ".git/*", ".idea/*", ".vscode/*", "node_modules/*",
    "**/generated/*", "**/generated-sources/*"
}

# --- Main Function ---
def main():
    parser = argparse.ArgumentParser(description="Analyze Spring codebase for migration from Spring 5 to Spring 6.")

    # Create mutually exclusive group for source
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--repo", help="URL of the GitHub repository.")
    source_group.add_argument("--dir", help="Path to local directory.")

    parser.add_argument("-n", "--name", help="Project name (optional, derived from repo/directory if omitted).")
    parser.add_argument("-t", "--token", help="GitHub personal access token (optional, reads from GITHUB_TOKEN env var if not provided).")
    parser.add_argument("-o", "--output", default="output", help="Base directory for output (default: ./output).")
    parser.add_argument("-i", "--include", nargs="+", help="Include file patterns (e.g. '*.py' '*.js'). Defaults to Spring-related files if not specified.")
    parser.add_argument("-e", "--exclude", nargs="+", help="Exclude file patterns (e.g. 'tests/*' 'docs/*'). Defaults to test/build directories if not specified.")
    parser.add_argument("-s", "--max-size", type=int, default=100000, help="Maximum file size in bytes (default: 100000, about 100KB).")
    # Add use_cache parameter to control LLM caching
    parser.add_argument("--no-cache", action="store_true", help="Disable LLM response caching (default: caching enabled)")
    # Add option to apply migration changes automatically
    parser.add_argument("--apply-changes", action="store_true", help="Automatically apply safe migration changes to files (only for local directories)")

    # Spring migration specific arguments
    migration_group = parser.add_argument_group('Spring Migration Options')
    migration_group.add_argument('--git-integration', action='store_true',
                                help='Enable Git integration for committing and pushing changes')

    args = parser.parse_args()

    # Get GitHub token from argument or environment variable if using repo
    github_token = None
    if args.repo:
        github_token = args.token or os.environ.get('GITHUB_TOKEN')
        if not github_token:
            print("Warning: No GitHub token provided. You might hit rate limits for public repositories.")

    # Initialize the shared dictionary with inputs
    shared = {
        "repo_url": args.repo,
        "local_dir": args.dir,
        "project_name": args.name, # Can be None, FetchRepo will derive it
        "github_token": args.token or os.getenv("GITHUB_TOKEN"),
        "output_dir": args.output, # Base directory for report output

        # Add include/exclude patterns and max file size
        "include_patterns": set(args.include) if args.include else SPRING_INCLUDE_PATTERNS,
        "exclude_patterns": set(args.exclude) if args.exclude else SPRING_EXCLUDE_PATTERNS,
        "max_file_size": args.max_size * 1024,
        
        # Add use_cache flag (inverse of no-cache flag)
        "use_cache": not args.no_cache,

        # Add option to apply migration changes automatically
        "apply_changes": args.apply_changes,

        # Add Git integration flag
        "git_integration": args.git_integration,

        # Outputs will be populated by the nodes
        "files": [],
        "final_output_dir": None,
        
        # Spring migration specific outputs
        "migration_analysis": {},
        "migration_plan": {}
    }

    # Display starting message
    print(f"Starting Spring 5 to 6 migration analysis for: {args.repo or args.dir}")
    print(f"LLM caching: {'Disabled' if args.no_cache else 'Enabled'}")

    # Create the Spring migration flow instance
    flow = create_spring_migration_flow()

    # Run the flow
    flow.run(shared)

if __name__ == "__main__":
    main()
