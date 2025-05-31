import os
import fnmatch
import pathspec


def crawl_local_files(
    directory,
    include_patterns=None,
    exclude_patterns=None,
    max_file_size=None,
    use_relative_paths=True,
):
    """
    Crawl files in a local directory with similar interface as crawl_github_files.
    Args:
        directory (str): Path to local directory
        include_patterns (set): File patterns to include (e.g. {"*.py", "*.js"})
        exclude_patterns (set): File patterns to exclude (e.g. {"tests/*"})
        max_file_size (int): Maximum file size in bytes
        use_relative_paths (bool): Whether to use paths relative to directory

    Returns:
        dict: {"files": {filepath: content}}
    """
    if not os.path.isdir(directory):
        raise ValueError(f"Directory does not exist: {directory}")

    files_dict = {}

    # --- Load .gitignore ---
    gitignore_path = os.path.join(directory, ".gitignore")
    gitignore_spec = None
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, "r", encoding="utf-8-sig") as f:
                gitignore_patterns = f.readlines()
            gitignore_spec = pathspec.PathSpec.from_lines("gitwildmatch", gitignore_patterns)
            print(f"Loaded .gitignore patterns from {gitignore_path}")
        except Exception as e:
            print(f"Warning: Could not read or parse .gitignore file {gitignore_path}: {e}")

    print(f"Scanning directory: {directory}")
    print(f"Include patterns: {include_patterns}")
    print(f"Exclude patterns: {exclude_patterns}")
    
    # Special handling for Excel files
    excel_extensions = {'.xlsx', '.xls', '.xlsm', '.xlsb', '.csv'}
    excel_folders = []
    
    # First pass: Find all files (including those in Excel folders)
    all_files = []
    for root, dirs, files in os.walk(directory):
        # Check if this directory might be an Excel folder
        dir_name = os.path.basename(root)
        if any(dir_name.lower().endswith(ext.lower()) for ext in excel_extensions):
            excel_folders.append(root)
            print(f"Found potential Excel folder: {root}")
            
        # Filter directories using .gitignore and exclude_patterns early
        excluded_dirs = set()
        for d in dirs:
            dirpath = os.path.join(root, d)
            dirpath_rel = os.path.relpath(dirpath, directory)

            # Skip exclusion check for Excel folders to make sure we process all files
            if any(dirpath.startswith(excel_folder) for excel_folder in excel_folders):
                continue

            if gitignore_spec and gitignore_spec.match_file(dirpath_rel):
                excluded_dirs.add(d)
                continue

            if exclude_patterns:
                for pattern in exclude_patterns:
                    # Check both the full relative path and just the directory name
                    if fnmatch.fnmatch(dirpath_rel, pattern) or fnmatch.fnmatch(d, pattern):
                        excluded_dirs.add(d)
                        break

        # Remove excluded directories to prevent walking into them
        # But don't exclude Excel folders
        for d in excluded_dirs:
            if d in dirs:
                dirpath = os.path.join(root, d)
                if not any(dirpath.startswith(excel_folder) for excel_folder in excel_folders):
                    dirs.remove(d)

        for filename in files:
            filepath = os.path.join(root, filename)
            all_files.append(filepath)

    total_files = len(all_files)
    print(f"Found {total_files} files to process")
    processed_files = 0
    included_files = 0

    for filepath in all_files:
        relpath = os.path.relpath(filepath, directory) if use_relative_paths else filepath

        # Special handling for files in Excel folders - always include them
        in_excel_folder = any(filepath.startswith(excel_folder) for excel_folder in excel_folders)
        
        # --- Exclusion check --- (skip for Excel folder files)
        excluded = False
        if not in_excel_folder:
            if gitignore_spec and gitignore_spec.match_file(relpath):
                excluded = True

            if not excluded and exclude_patterns:
                for pattern in exclude_patterns:
                    # Check if the pattern matches any part of the path
                    if fnmatch.fnmatch(relpath, pattern) or any(fnmatch.fnmatch(part, pattern) for part in relpath.split(os.sep)):
                        excluded = True
                        break

        # --- Inclusion check --- (Excel folder files are always included)
        included = in_excel_folder  # Automatically include Excel folder files
        if not included and include_patterns:
            for pattern in include_patterns:
                # Match by filename or full path
                if fnmatch.fnmatch(relpath, pattern) or fnmatch.fnmatch(os.path.basename(relpath), pattern):
                    included = True
                    break
        elif not included and not include_patterns:
            included = True

        processed_files += 1  # Increment processed count regardless of inclusion/exclusion

        status = "processed"
        if not included or excluded:
            status = "skipped (excluded)"
            # Print progress for skipped files due to exclusion
            if total_files > 0:
                percentage = (processed_files / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files}/{total_files} ({rounded_percentage}%) {relpath} [{status}]\033[0m")
            continue  # Skip to next file if not included or excluded

        if max_file_size and os.path.getsize(filepath) > max_file_size:
            status = "skipped (size limit)"
            # Print progress for skipped files due to size limit
            if total_files > 0:
                percentage = (processed_files / total_files) * 100
                rounded_percentage = int(percentage)
                print(f"\033[92mProgress: {processed_files}/{total_files} ({rounded_percentage}%) {relpath} [{status}]\033[0m")
            continue  # Skip large files

        # --- File is being processed ---        
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                content = f.read()
            files_dict[relpath] = content
            included_files += 1
            if in_excel_folder:
                print(f"Including Excel folder file: {relpath}")
        except Exception as e:
            print(f"Warning: Could not read file {filepath}: {e}")
            status = "skipped (read error)"
            
            # Try reading as binary for Excel files
            if in_excel_folder:
                try:
                    with open(filepath, "rb") as f:
                        content = f.read().decode('utf-8', errors='replace')
                    files_dict[relpath] = content
                    included_files += 1
                    status = "processed (binary)"
                    print(f"Successfully read Excel folder file as binary: {relpath}")
                except Exception as e2:
                    print(f"Warning: Could not read Excel folder file even as binary {filepath}: {e2}")

        # --- Print progress for processed or error files ---
        if total_files > 0:
            percentage = (processed_files / total_files) * 100
            rounded_percentage = int(percentage)
            print(f"\033[92mProgress: {processed_files}/{total_files} ({rounded_percentage}%) {relpath} [{status}]\033[0m")

    print(f"Included {included_files} out of {total_files} files in the analysis")
    print(f"Found {len(excel_folders)} Excel folders containing additional files")
    
    # Special check to confirm Excel folder files are included
    excel_folder_files_count = sum(1 for path in files_dict.keys() if any(path.startswith(os.path.relpath(folder, directory)) for folder in excel_folders))
    print(f"Included {excel_folder_files_count} files from Excel folders")
    
    return {"files": files_dict}


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