import os
import fnmatch

def read_gitignore(root_dir):
    """Reads and parses the .gitignore file from the project's root directory."""
    ignore_patterns = []
    # Add default patterns that are almost always ignored
    default_ignores = ['.git', '.venv', '__pycache__', '.vscode', 'generate_tree.py']
    
    for pattern in default_ignores:
        ignore_patterns.append(pattern)
        ignore_patterns.append(f"{pattern}/*") # Also ignore contents of these folders

    try:
        gitignore_path = os.path.join(root_dir, '.gitignore')
        with open(gitignore_path, 'r') as f:
            for line in f:
                # Ignore comments and empty lines
                if line.strip() and not line.strip().startswith('#'):
                    pattern = line.strip().rstrip('/')
                    ignore_patterns.append(pattern)
                    # Add pattern to ignore contents of a directory
                    if not pattern.endswith('*'):
                        ignore_patterns.append(f"{pattern}/*")

    except FileNotFoundError:
        print("No .gitignore file found. Using default ignores.")

    return ignore_patterns

def is_ignored(path, ignore_patterns, root_dir):
    """Checks if a file or directory should be ignored."""
    relative_path = os.path.relpath(path, root_dir).replace('\\', '/')
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(relative_path, pattern):
            return True
    return False

def generate_tree(start_path='.'):
    """Generates the clean file tree structure."""
    root_dir = os.path.abspath(start_path)
    ignore_patterns = read_gitignore(root_dir)
    
    for root, dirs, files in os.walk(root_dir, topdown=True):
        # Filter directories to not walk into ignored ones
        dirs[:] = [d for d in dirs if not is_ignored(os.path.join(root, d), ignore_patterns, root_dir)]
        
        level = root.replace(root_dir, '').count(os.sep)
        indent = '│   ' * (level)
        
        # Only print the directory if it's not the root folder itself
        if root != root_dir:
            print(f'{indent}├── {os.path.basename(root)}/')
        
        sub_indent = '│   ' * (level + 1)
        for f in files:
            file_path = os.path.join(root, f)
            if not is_ignored(file_path, ignore_patterns, root_dir):
                print(f'{sub_indent}├── {f}')

if __name__ == "__main__":
    generate_tree()