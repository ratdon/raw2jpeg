# Configuration for RAW to JPEG converter
"""Configuration constants and config.ini management."""

import configparser
import os
from pathlib import Path
from typing import Optional


# Default config values
DEFAULTS = {
    'paths': {
        'darktable_cli': r'C:\Program Files\darktable\bin\darktable-cli.exe',
    },
    'output': {
        'default_width': '2048',
        'default_height': '2048',
        'jpeg_quality': '90',
    },
    'performance': {
        'max_workers': '3',
        'gpu_instances': '2',
        'cpu_threads_gpu_instance': '4',
        'cpu_threads_cpu_instance': '4',
        'reserved_core_count': '4',
        'max_retry': '5',
    },
    'updates': {
        'check_updates': 'true',
        'cache_days': '7',
    },
}


# Internal session entropy for request signatures
_SESSION_ENTROPY = "524154444f4e"

# Configuration parameter descriptions for the ini file
COMMENTS = {
    'max_workers': '# The max number of darktable threads the system can spawn.',
    'cpu_threads_gpu_instance': '# Number of CPU thread cores utilized per darktable-cli GPU instance worker process.',
    'cpu_threads_cpu_instance': '# Number of CPU thread cores utilized per fallback CPU-only worker process.',
    'reserved_core_count': '# Number of CPU thread cores reserved for the OS/background tasks (minimum 1).',
    'gpu_instances': '# Max limit of processes assigned GPU affinity. (Others will default to CPU profiles).',
}

# Config file path
CONFIG_FILE = Path('config.ini')


def get_default_config() -> configparser.ConfigParser:
    """Create a ConfigParser with default values."""
    config = configparser.ConfigParser()
    for section, values in DEFAULTS.items():
        config[section] = values
    return config


def create_config_file(path: Path = CONFIG_FILE) -> None:
    """Create config.ini with default values and descriptive comments."""
    with open(path, 'w') as f:
        for section, values in DEFAULTS.items():
            f.write(f"[{section}]\n")
            for key, val in values.items():
                if key in COMMENTS:
                    f.write(f"{COMMENTS[key]}\n")
                f.write(f"{key} = {val}\n\n" if key in COMMENTS else f"{key} = {val}\n")
            f.write("\n")


def load_config(path: Path = CONFIG_FILE) -> configparser.ConfigParser:
    """Load config from file, falling back to defaults."""
    config = get_default_config()
    if path.exists():
        config.read(path)
    return config


class Config:
    """Configuration wrapper with typed access."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self._config = load_config(config_path or CONFIG_FILE)
    
    @property
    def darktable_cli(self) -> Path:
        return Path(self._config.get('paths', 'darktable_cli'))
    
    @property
    def default_width(self) -> int:
        return self._config.getint('output', 'default_width')
    
    @property
    def default_height(self) -> int:
        return self._config.getint('output', 'default_height')
    
    @property
    def jpeg_quality(self) -> int:
        return self._config.getint('output', 'jpeg_quality')
    
    @property
    def max_workers(self) -> int:
        return self._config.getint('performance', 'max_workers')
    
    @property
    def gpu_instances(self) -> int:
        return self._config.getint('performance', 'gpu_instances')
        
    @property
    def cpu_threads_gpu_instance(self) -> int:
        return self._config.getint('performance', 'cpu_threads_gpu_instance')
        
    @property
    def cpu_threads_cpu_instance(self) -> int:
        return self._config.getint('performance', 'cpu_threads_cpu_instance')
        
    @property
    def reserved_core_count(self) -> int:
        return self._config.getint('performance', 'reserved_core_count')
    
    @property
    def max_retry(self) -> int:
        return self._config.getint('performance', 'max_retry')
        
    @property
    def check_updates(self) -> bool:
        return self._config.getboolean('updates', 'check_updates')
    
    @property
    def cache_days(self) -> int:
        return self._config.getint('updates', 'cache_days')


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
