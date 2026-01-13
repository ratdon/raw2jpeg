# Utility functions
"""Helpers for filename pattern detection and output path generation."""

import re
from pathlib import Path
from typing import Optional, Tuple


# Filename patterns
# Pattern 1: yyyy-mm-dd_hh-mm-ss_DSC#####.ext (datetime prefix)
DATETIME_PREFIX_PATTERN = re.compile(
    r'^(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})_([A-Za-z]+\d+)\.(\w+)$'
)

# Pattern 2: DSC#####.ext (plain DSC)
PLAIN_DSC_PATTERN = re.compile(
    r'^([A-Za-z]+\d+)\.(\w+)$'
)

# Pattern 3: DSC#####_yyyy-mm-dd_hh-mm-ss.ext (datetime suffix)
DATETIME_SUFFIX_PATTERN = re.compile(
    r'^([A-Za-z]+\d+)_(\d{4})-(\d{2})-(\d{2})_(\d{2})-(\d{2})-(\d{2})\.(\w+)$'
)


def detect_filename_pattern(filename: str) -> str:
    """
    Detect the filename pattern type.
    
    Returns:
        'datetime_prefix' - 2025-12-25_16-34-32_DSC07514.ARW
        'datetime_suffix' - DSC07514_2025-12-25_16-34-32.ARW
        'plain_dsc' - DSC07514.ARW
        'unknown' - unrecognized pattern
    """
    if DATETIME_PREFIX_PATTERN.match(filename):
        return 'datetime_prefix'
    elif DATETIME_SUFFIX_PATTERN.match(filename):
        return 'datetime_suffix'
    elif PLAIN_DSC_PATTERN.match(filename):
        return 'plain_dsc'
    return 'unknown'


def get_output_template(pattern: str, base_outpath: str) -> str:
    """
    Generate the darktable output path template based on filename pattern.
    
    Args:
        pattern: One of 'datetime_prefix', 'datetime_suffix', 'plain_dsc', 'unknown'
        base_outpath: Base output directory (with forward slashes)
    
    Returns:
        Output path template with darktable variables
    """
    # Ensure forward slashes and no trailing slash
    base = base_outpath.rstrip('/')
    
    if pattern == 'datetime_prefix':
        # Already has datetime in name, just use date subfolder
        return f"'{base}/$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)/$(FILE.NAME).jpg'"
    
    elif pattern == 'datetime_suffix':
        # Already has datetime in name, just use date subfolder
        return f"'{base}/$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)/$(FILE.NAME).jpg'"
    
    elif pattern == 'plain_dsc':
        # Need to add datetime prefix to filename
        return f"'{base}/$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)/$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)_$(EXIF.HOUR)-$(EXIF.MINUTE)-$(EXIF.SECOND)_$(FILE.NAME).jpg'"
    
    else:  # unknown - treat like plain_dsc
        return f"'{base}/$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)/$(EXIF.YEAR)-$(EXIF.MONTH)-$(EXIF.DAY)_$(EXIF.HOUR)-$(EXIF.MINUTE)-$(EXIF.SECOND)_$(FILE.NAME).jpg'"


def to_forward_slashes(path: Path) -> str:
    """Convert Windows path to forward slashes for darktable-cli."""
    return str(path).replace('\\', '/')


def get_sample_file(folder: Path) -> Optional[Path]:
    """
    Get a sample RAW file from a folder to detect filename pattern.
    
    Returns:
        Path to first RAW file found, or None
    """
    raw_extensions = {'.arw', '.cr2', '.cr3', '.nef', '.dng', '.orf', '.rw2', '.raf', '.pef'}
    
    for f in folder.iterdir():
        if f.is_file() and f.suffix.lower() in raw_extensions:
            return f
    return None


def detect_folder_pattern(folder: Path) -> str:
    """
    Detect the filename pattern used in a folder.
    
    Returns:
        Pattern name or 'unknown'
    """
    sample = get_sample_file(folder)
    if sample:
        return detect_filename_pattern(sample.name)
    return 'unknown'
