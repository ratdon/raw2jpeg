# Job Planner module
"""Discover leaf folders for batch conversion."""

from pathlib import Path
from typing import List, Optional

from .utils import detect_folder_pattern, to_forward_slashes, get_output_template


# RAW file extensions
RAW_EXTENSIONS = {'.arw', '.cr2', '.cr3', '.nef', '.dng', '.orf', '.rw2', '.raf', '.pef'}


def is_leaf_folder(folder: Path) -> bool:
    """
    Check if folder is a leaf folder (contains RAW files, no subdirectories with RAW files).
    
    A leaf folder contains at least one RAW file directly.
    """
    has_raw_files = False
    
    for item in folder.iterdir():
        if item.is_file() and item.suffix.lower() in RAW_EXTENSIONS:
            has_raw_files = True
            break
    
    return has_raw_files


def discover_leaf_folders(inpath: Path, outpath: Optional[Path] = None) -> List[Path]:
    """
    Recursively discover all leaf folders containing RAW files.
    
    Excludes the output directory if it's inside the input directory.
    
    Args:
        inpath: Input directory to search
        outpath: Output directory to exclude (optional)
    
    Returns:
        List of leaf folder paths
    """
    if not inpath.exists() or not inpath.is_dir():
        raise ValueError(f"Input path does not exist or is not a directory: {inpath}")
    
    leaf_folders = []
    
    # Use a stack for iterative traversal
    stack = [inpath]
    
    while stack:
        current = stack.pop()
        
        # Skip output directory
        if outpath:
            try:
                current.relative_to(outpath)
                continue  # This folder is inside output dir, skip it
            except ValueError:
                pass  # Not inside output dir, continue processing
        
        # Check if current folder is a leaf folder
        if is_leaf_folder(current):
            leaf_folders.append(current)
        
        # Add subdirectories to stack
        for item in current.iterdir():
            if item.is_dir():
                stack.append(item)
    
    return sorted(leaf_folders)


def count_raw_files(folder: Path) -> int:
    """Count the number of RAW files in a folder."""
    count = 0
    for item in folder.iterdir():
        if item.is_file() and item.suffix.lower() in RAW_EXTENSIONS:
            count += 1
    return count


def create_conversion_jobs(
    leaf_folders: List[Path],
    inpath: Path,
    outpath: Path,
) -> tuple[List[dict], dict[Path, int], int]:
    """
    Create conversion job definitions for each leaf folder.
    
    Args:
        leaf_folders: List of leaf folder paths
        inpath: Base input directory
        outpath: Base output directory
    
    Returns:
        Tuple of:
            - List of job dicts with 'input_folder', 'output_template', 'pattern', 'file_count'
            - Dict mapping folder path to file count
            - Total file count across all folders
    """
    jobs = []
    file_counts = {}
    total_files = 0
    outpath_str = to_forward_slashes(outpath)
    
    for folder in leaf_folders:
        pattern = detect_folder_pattern(folder)
        output_template = get_output_template(pattern, outpath_str)
        file_count = count_raw_files(folder)
        
        file_counts[folder] = file_count
        total_files += file_count
        
        jobs.append({
            'input_folder': folder,
            'output_template': output_template,
            'pattern': pattern,
            'file_count': file_count,
        })
    
    return jobs, file_counts, total_files


def get_default_outpath(inpath: Path) -> Path:
    """
    Generate default output path based on input path.
    
    Default: <inpath>-jpeg/ (sibling of inpath, not inside)
    
    Args:
        inpath: Input directory path
    
    Returns:
        Output directory path
    """
    return inpath.parent / f"{inpath.name}-jpeg"
