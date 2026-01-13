# Capability detection module
"""Detect darktable capabilities and validate installation."""

import re
import subprocess
from pathlib import Path
from typing import Optional

from .config import get_config


def validate_installation() -> dict:
    """
    Validate that darktable-cli is installed and accessible.
    
    Returns:
        dict with keys:
            - 'darktable_ok': bool
            - 'darktable_path': str
            - 'darktable_version': str or None
            - 'errors': list of error messages
    """
    config = get_config()
    
    result = {
        'darktable_ok': False,
        'darktable_path': str(config.darktable_cli),
        'darktable_version': None,
        'errors': [],
    }
    
    # Check darktable-cli
    if not config.darktable_cli.exists():
        result['errors'].append(f"darktable-cli not found at: {config.darktable_cli}")
    else:
        version = get_darktable_version()
        if version:
            result['darktable_ok'] = True
            result['darktable_version'] = version
        else:
            result['errors'].append("darktable-cli exists but version check failed")
    
    return result


def get_darktable_version() -> Optional[str]:
    """
    Get the installed darktable-cli version.
    
    Returns:
        Version string (e.g., "5.4.0") or None
    """
    config = get_config()
    
    try:
        result = subprocess.run(
            [str(config.darktable_cli), '--version'],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        
        # Parse version from output
        output = result.stdout + result.stderr
        match = re.search(r'darktable[- ]cli\s+(\d+\.\d+\.\d+)', output, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Try simpler pattern
        match = re.search(r'(\d+\.\d+\.\d+)', output)
        if match:
            return match.group(1)
            
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    
    return None
