import requests
import base64
import os
import tempfile
import git
import time
import fnmatch
import subprocess
from typing import Union, Set, List, Dict, Tuple, Any
from urllib.parse import urlparse
import re
import shutil
from pathlib import Path
from git import Repo
from utils.crawl_local_files import crawl_local_files

def clear_git_credentials(repo_url: str):
    """Clear any cached git credentials for the repository URL to prevent auth issues."""
    try:
        # Extract the hostname from the repository URL
        parsed_url = urlparse(repo_url)
        hostname = parsed_url.hostname
        
        if hostname:
            # Try to clear cached credentials for this hostname
            try:
                subprocess.run(['git', 'credential', 'reject'], 
                             input=f'protocol=https\nhost={hostname}\n\n', 
                             text=True, capture_output=True, timeout=10)
                print(f"Cleared git credentials for {hostname}")
            except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
                # git credential command may not be available or may fail
                # This is not critical, so we continue
                pass
    except Exception:
        # If anything fails, continue without clearing credentials
        pass

def crawl_github_files(
    repo_url: str,
    token: str = None,
    branch: str = None,
    include_patterns: list = None,
    exclude_patterns: list = None,
    max_file_size: int = 100000,
    use_relative_paths: bool = True,
    shallow_clone: bool = False,  # Changed default to False to ensure all subdirectories are cloned
    clone_timeout: int = 300,
    max_depth: int = 10  # Increased depth to ensure subdirectories are included
) -> dict:
    """
    Clone a GitHub repository to a temporary directory and crawl its files.
    
    Args:
        repo_url: GitHub repository URL
        token: GitHub API token (optional)
        branch: Specific branch to clone and analyze (optional, defaults to repository's default branch)
        include_patterns: List of glob patterns to include
        exclude_patterns: List of glob patterns to exclude
        max_file_size: Maximum file size in bytes
        use_relative_paths: Whether to use relative paths in output
        shallow_clone: Whether to perform a shallow clone (default: False)
        clone_timeout: Maximum time in seconds to wait for clone (default: 300)
        max_depth: Depth for shallow clone (default: 10)
        
    Returns:
        Dict containing file contents and metadata
    """
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="github_crawl_")
    try:
        print(f"Cloning repository to temporary directory: {temp_dir}")
        print(f"Repository URL: {repo_url}")
        if branch:
            print(f"Target branch: {branch}")
        print(f"Include patterns: {include_patterns}")
        print(f"Exclude patterns: {exclude_patterns}")
        
        # Clear any cached git credentials to prevent auth issues
        clear_git_credentials(repo_url)
        
        # Extract specific path within repo if specified
        target_path = None
        if "/tree/" in repo_url:
            # If the URL points to a specific path within the repo, extract it
            path_match = re.search(r'/tree/[^/]+/(.+)$', repo_url)
            if path_match:
                target_path = path_match.group(1)
                # Clean up the repo URL to point to the root
                repo_url = repo_url.split("/tree/")[0]
                print(f"Detected specific path in repo: {target_path}")
                print(f"Cleaned repo URL: {repo_url}")
        
        # Clone the repository with timeout and proper token handling
        start_time = time.time()
        
        # Setup git environment to handle credentials properly
        git_env = os.environ.copy()
        if token:
            # Use git credential helper approach for better token handling
            git_env['GIT_ASKPASS'] = 'echo'  # Prevent password prompts
            git_env['GIT_USERNAME'] = token  # Set username as token
            git_env['GIT_PASSWORD'] = ''     # Empty password for token auth
            
            # Alternative: Use token in URL but handle it more securely
            auth_url = repo_url.replace("https://", f"https://{token}@")
            
            try:
                if shallow_clone:
                    repo = Repo.clone_from(auth_url, temp_dir, depth=max_depth, env=git_env)
                else:
                    repo = Repo.clone_from(auth_url, temp_dir, env=git_env)
            except git.exc.GitCommandError as git_error:
                # Handle specific git authentication errors
                if git_error.status == 128:
                    print(f"Git authentication failed (error 128). Trying alternative method...")
                    print(f"Original error: {git_error}")
                    
                    # Clean up partial clone if it exists
                    if os.path.exists(temp_dir) and os.listdir(temp_dir):
                        shutil.rmtree(temp_dir)
                        temp_dir = tempfile.mkdtemp(prefix="github_crawl_retry_")
                        print(f"Created new temp directory for retry: {temp_dir}")
                    
                    # Clear any cached credentials and try again
                    clear_git_credentials(repo_url)
                    
                    try:
                        # Try without embedding token in URL, using environment variables
                        git_env['GIT_USERNAME'] = token
                        git_env['GIT_PASSWORD'] = 'x-oauth-basic'
                        
                        print(f"Retrying clone with alternative authentication method...")
                        if shallow_clone:
                            repo = Repo.clone_from(repo_url, temp_dir, depth=max_depth, env=git_env)
                        else:
                            repo = Repo.clone_from(repo_url, temp_dir, env=git_env)
                        print("Retry successful!")
                    except git.exc.GitCommandError as retry_error:
                        print(f"Second method failed: {retry_error}")
                        
                        # Try a third method with different token format
                        try:
                            # Clean up and create new temp dir
                            if os.path.exists(temp_dir) and os.listdir(temp_dir):
                                shutil.rmtree(temp_dir)
                                temp_dir = tempfile.mkdtemp(prefix="github_crawl_final_")
                                print(f"Created final temp directory: {temp_dir}")
                            
                            # Try with token as username and empty password (GitHub CLI style)
                            final_auth_url = repo_url.replace("https://", f"https://{token}:@")
                            
                            print(f"Trying final authentication method...")
                            if shallow_clone:
                                repo = Repo.clone_from(final_auth_url, temp_dir, depth=max_depth)
                            else:
                                repo = Repo.clone_from(final_auth_url, temp_dir)
                            print("Final method successful!")
                        except git.exc.GitCommandError as final_error:
                            print(f"All authentication methods failed.")
                            print(f"Error 1: {git_error}")
                            print(f"Error 2: {retry_error}")
                            print(f"Error 3: {final_error}")
                            raise Exception(f"Failed to clone repository with token after all retry attempts. Please check your GitHub token permissions.")
                else:
                    print(f"Git error {git_error.status}: {git_error}")
                    raise git_error
        else:
            # No token provided, try public access
            try:
                if shallow_clone:
                    repo = Repo.clone_from(repo_url, temp_dir, depth=max_depth)
                else:
                    repo = Repo.clone_from(repo_url, temp_dir)
            except git.exc.GitCommandError as git_error:
                if git_error.status == 128:
                    raise Exception(f"Repository clone failed (error 128). This might be a private repository requiring authentication. Please provide a GitHub token.")
                else:
                    raise git_error
                
        # Check if clone took too long
        if time.time() - start_time > clone_timeout:
            raise TimeoutError(f"Repository clone took longer than {clone_timeout} seconds")
            
        print("Repository cloned successfully")
        
        # Checkout specific branch if requested
        if branch:
            try:
                print(f"Checking out branch: {branch}")
                repo.git.checkout(branch)
                print(f"Successfully switched to branch: {branch}")
            except git.exc.GitCommandError as branch_error:
                # Try to checkout as a remote branch if local checkout fails
                try:
                    print(f"Local branch '{branch}' not found, trying remote branch...")
                    repo.git.checkout(f"origin/{branch}")
                    print(f"Successfully switched to remote branch: origin/{branch}")
                except git.exc.GitCommandError as remote_error:
                    print(f"❌ Failed to checkout branch '{branch}':")
                    print(f"   Local checkout error: {branch_error}")
                    print(f"   Remote checkout error: {remote_error}")
                    
                    # List available branches for user reference
                    try:
                        branches = repo.git.branch('-a').split('\n')
                        available_branches = [b.strip().replace('* ', '').replace('remotes/origin/', '') 
                                            for b in branches if b.strip() and not b.strip().startswith('HEAD')]
                        available_branches = list(set(available_branches))  # Remove duplicates
                        print(f"   Available branches: {', '.join(available_branches[:10])}")
                        if len(available_branches) > 10:
                            print(f"   ... and {len(available_branches) - 10} more")
                    except:
                        print("   Could not list available branches")
                    
                    raise Exception(f"Branch '{branch}' not found in repository. Please check the branch name and try again.")
        
        # If a specific path within the repo was specified, adjust the directory to scan
        scan_dir = temp_dir
        if target_path:
            target_dir = os.path.join(temp_dir, target_path)
            if os.path.exists(target_dir):
                scan_dir = target_dir
                print(f"Scanning specific path: {target_path}")
            else:
                print(f"Warning: Specified path '{target_path}' not found in repository. Scanning entire repo.")
        
        # Use the local file crawler to process the cloned repository
        result = crawl_local_files(
            directory=scan_dir,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_file_size=max_file_size,
            use_relative_paths=use_relative_paths
        )
        
        # Add repository information to the result
        result["repo_name"] = os.path.basename(repo_url.rstrip('/'))
        if branch:
            result["branch"] = branch
        if target_path:
            result["target_path"] = target_path
            
        return result
        
    finally:
        # Clean up the temporary directory
        print("Cleaning up temporary directory...")
        shutil.rmtree(temp_dir)

# Example usage
if __name__ == "__main__":
    # Get token from environment variable (recommended for private repos)
    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Warning: No GitHub token found in environment variable 'GITHUB_TOKEN'.\n"
              "Private repositories will not be accessible without a token.\n"
              "To access private repos, set the environment variable or pass the token explicitly.")
    
    repo_url = "https://github.com/pydantic/pydantic"
    target_branch = "main"  # Specify branch to analyze
    
    # Example: Get Python and Markdown files from specific branch, but exclude test files
    result = crawl_github_files(
        repo_url, 
        token=github_token,
        branch=target_branch,  # Analyze specific branch
        max_file_size=1 * 1024 * 1024,  # 1 MB in bytes
        use_relative_paths=True,  # Enable relative paths
        include_patterns={"*.py", "*.md"},  # Include Python and Markdown files
    )
    
    files = result["files"]
    
    print(f"\nDownloaded {len(files)} files.")
    
    # Display all file paths in the dictionary
    print("\nFiles in dictionary:")
    for file_path in sorted(files.keys()):
        print(f"  {file_path}")
    
    # Example: accessing content of a specific file
    if files:
        sample_file = next(iter(files))
        print(f"\nSample file: {sample_file}")
        print(f"Content preview: {files[sample_file][:200]}...")
