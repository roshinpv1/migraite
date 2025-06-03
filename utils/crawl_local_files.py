import os
import fnmatch
import pathspec
from .file_encoding_detector import RobustFileReader


def crawl_local_files(
    directory,
    include_patterns=None,
    exclude_patterns=None,
    max_file_size=None,
    use_relative_paths=True,
):
    """
    Crawl files in a local directory with similar interface as crawl_github_files.
    Enhanced with robust file reading to handle encoding issues gracefully.
    
    Args:
        directory (str): Path to local directory
        include_patterns (set): File patterns to include (e.g. {"*.py", "*.js"})
        exclude_patterns (set): File patterns to exclude (e.g. {"tests/*"})
        max_file_size (int): Maximum file size in bytes
        use_relative_paths (bool): Whether to use paths relative to directory

    Returns:
        dict: {"files": {filepath: content}, "stats": {processing_statistics}}
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Directory does not exist: {directory}")

    files_dict = {}
    
    # Statistics tracking
    stats = {
        "total_files_found": 0,
        "files_included": 0,
        "files_excluded_gitignore": 0,
        "files_excluded_patterns": 0,
        "files_excluded_size": 0,
        "files_binary_skipped": 0,
        "files_encoding_error": 0,
        "files_read_successfully": 0,
        "encoding_fallbacks_used": 0
    }

    # --- Load .gitignore ---
    gitignore_path = os.path.join(directory, ".gitignore")
    gitignore_spec = None
    if os.path.exists(gitignore_path):
        try:
            # Use robust file reader for .gitignore
            content, encoding, status = RobustFileReader.read_file_with_fallback(gitignore_path)
            if content is not None:
                gitignore_patterns = content.splitlines()
                gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", gitignore_patterns)
                print(f"Loaded .gitignore patterns from {gitignore_path} (encoding: {encoding})")
            else:
                print(f"Warning: Could not read .gitignore file {gitignore_path}: {status}")
        except Exception as e:
            print(f"Warning: Could not parse .gitignore file {gitignore_path}: {e}")

    print(f"Scanning directory: {directory}")
    print(f"Include patterns: {include_patterns}")
    print(f"Exclude patterns: {exclude_patterns}")
    
    # Find all files
    all_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            all_files.append(os.path.join(root, file))

    total_files = len(all_files)
    stats["total_files_found"] = total_files
    
    print(f"Found {total_files} files in total")
    
    processed_files = 0

    for filepath in all_files:
        relpath = os.path.relpath(filepath, directory) if use_relative_paths else filepath
        processed_files += 1

        # --- Exclusion check ---
        excluded = False
        exclusion_reason = None
        
        if gitignore_spec and gitignore_spec.match_file(relpath):
            excluded = True
            exclusion_reason = "gitignore"
            stats["files_excluded_gitignore"] += 1

        if not excluded and exclude_patterns:
            for pattern in exclude_patterns:
                # Check if the pattern matches any part of the path
                if fnmatch.fnmatch(relpath, pattern) or any(fnmatch.fnmatch(part, pattern) for part in relpath.split(os.sep)):
                    excluded = True
                    exclusion_reason = "exclude_pattern"
                    stats["files_excluded_patterns"] += 1
                    break

        # --- Inclusion check ---
        included = False
        if include_patterns:
            for pattern in include_patterns:
                # Match by filename or full path
                if fnmatch.fnmatch(relpath, pattern) or fnmatch.fnmatch(os.path.basename(relpath), pattern):
                    included = True
                    break
        else:
            included = True  # Include all files if no include patterns specified

        # Determine final status
        if not included or excluded:
            status = f"skipped ({exclusion_reason or 'not_included'})"
            # Print progress for skipped files
            if total_files > 0:
                percentage = (processed_files / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files}/{total_files} ({rounded_percentage}%) {relpath} [{status}]\033[0m")
            continue  # Skip to next file

        # --- File reading with robust encoding handling ---
        try:
            # Use robust file reader
            content, encoding_used, read_status = RobustFileReader.read_file_with_fallback(
                filepath, 
                max_file_size=max_file_size
            )
            
            if content is not None:
                files_dict[relpath] = content
                stats["files_included"] += 1
                stats["files_read_successfully"] += 1
                
                # Track encoding fallbacks
                if 'replacement' in read_status:
                    stats["encoding_fallbacks_used"] += 1
                    status = f"read with encoding fallback ({encoding_used})"
                else:
                    status = f"read successfully ({encoding_used})"
                    
            else:
                # Handle different read failure reasons
                if read_status == "size_skipped":
                    stats["files_excluded_size"] += 1
                    status = "skipped (size limit)"
                elif read_status == "binary_skipped":
                    stats["files_binary_skipped"] += 1
                    status = "skipped (binary file)"
                elif read_status == "encoding_error":
                    stats["files_encoding_error"] += 1
                    status = "skipped (encoding error)"
                else:
                    stats["files_encoding_error"] += 1
                    status = f"skipped ({read_status})"
                    
        except Exception as e:
            stats["files_encoding_error"] += 1
            status = f"skipped (unexpected error: {str(e)[:50]})"
            print(f"Warning: Unexpected error reading file {filepath}: {e}")

        # --- Print progress ---
        if total_files > 0:
            percentage = (processed_files / total_files) * 100
            rounded_percentage = int(percentage)
            print(f"\033[92mProgress: {processed_files}/{total_files} ({rounded_percentage}%) {relpath} [{status}]\033[0m")

    # Print summary statistics
    print(f"\n📊 File Processing Summary:")
    print(f"   Total files found: {stats['total_files_found']}")
    print(f"   Files successfully read: {stats['files_read_successfully']}")
    print(f"   Files with encoding fallbacks: {stats['encoding_fallbacks_used']}")
    print(f"   Files excluded (gitignore): {stats['files_excluded_gitignore']}")
    print(f"   Files excluded (patterns): {stats['files_excluded_patterns']}")
    print(f"   Files excluded (size): {stats['files_excluded_size']}")
    print(f"   Binary files skipped: {stats['files_binary_skipped']}")
    print(f"   Encoding errors: {stats['files_encoding_error']}")
    
    if stats['encoding_fallbacks_used'] > 0:
        print(f"   ⚠️  {stats['encoding_fallbacks_used']} files read with encoding fallbacks")
    
    if stats['files_encoding_error'] > 0:
        print(f"   ⚠️  {stats['files_encoding_error']} files could not be read due to encoding issues")
    
    print(f"✅ Included {stats['files_included']} out of {stats['total_files_found']} files in the analysis")
    
    return {"files": files_dict, "stats": stats}


if __name__ == "__main__":
    print("--- Crawling parent directory ('..') ---")
    files_data = crawl_local_files(
        "..",
        exclude_patterns={
            "*.pyc",
            "__pycache__/*",
            ".venv/*",
            ".git/*",
            "docs/*",
            "output/*",
        },
    )
    print(f"Found {len(files_data['files'])} files:")
    for path in files_data['files']:
        print(f"  {path}")