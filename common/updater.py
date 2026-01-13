# Update Monitor module
"""Monitor darktable releases and notify user of updates."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import requests

from .capability import get_darktable_version
from .config import get_config


class UpdateMonitor:
    """Monitor darktable releases from GitHub."""
    
    GITHUB_REPO = "darktable-org/darktable"
    CACHE_FILE = Path.home() / ".raw2jpeg_update_cache.json"
    
    def __init__(self):
        self._config = get_config()
        self._cache: dict = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load cached update info."""
        if self.CACHE_FILE.exists():
            try:
                with open(self.CACHE_FILE, 'r') as f:
                    self._cache = json.load(f)
            except (json.JSONDecodeError, IOError):
                self._cache = {}
    
    def _save_cache(self) -> None:
        """Save update cache."""
        try:
            with open(self.CACHE_FILE, 'w') as f:
                json.dump(self._cache, f)
        except IOError:
            pass
    
    def _is_cache_valid(self) -> bool:
        """Check if cache is still valid."""
        last_check = self._cache.get('last_check')
        if not last_check:
            return False
        
        try:
            last_dt = datetime.fromisoformat(last_check)
            cache_days = self._config.cache_days
            return datetime.now() - last_dt < timedelta(days=cache_days)
        except ValueError:
            return False
    
    def get_latest_release(self, force_refresh: bool = False) -> Optional[dict]:
        """
        Get the latest darktable release info.
        
        Args:
            force_refresh: Ignore cache and fetch fresh data
        
        Returns:
            dict with 'version', 'url', 'published' or None
        """
        # Use cache if valid
        if not force_refresh and self._is_cache_valid():
            return {
                'version': self._cache.get('latest_version'),
                'url': self._cache.get('release_url'),
                'published': self._cache.get('published'),
            }
        
        try:
            api_url = f"https://api.github.com/repos/{self.GITHUB_REPO}/releases/latest"
            response = requests.get(
                api_url,
                headers={'Accept': 'application/vnd.github.v3+json'},
                timeout=10,
            )
            response.raise_for_status()
            
            data = response.json()
            
            # Extract version from tag (e.g., "release-5.4.0" -> "5.4.0")
            tag = data.get('tag_name', '')
            version = tag.replace('release-', '').lstrip('v')
            
            result = {
                'version': version,
                'url': data.get('html_url'),
                'published': data.get('published_at'),
            }
            
            # Update cache
            self._cache = {
                'last_check': datetime.now().isoformat(),
                'latest_version': version,
                'release_url': data.get('html_url'),
                'published': data.get('published_at'),
            }
            self._save_cache()
            
            return result
            
        except (requests.RequestException, json.JSONDecodeError, KeyError):
            return None
    
    def check_for_updates(self) -> Optional[dict]:
        """
        Check if an update is available.
        
        Returns:
            dict with 'update_available', 'current', 'latest', 'url' or None on error
        """
        current = get_darktable_version()
        if not current:
            return None
        
        latest_info = self.get_latest_release()
        if not latest_info or not latest_info.get('version'):
            return None
        
        latest = latest_info['version']
        
        return {
            'update_available': self._compare_versions(current, latest) < 0,
            'current': current,
            'latest': latest,
            'url': latest_info.get('url'),
        }
    
    @staticmethod
    def _compare_versions(v1: str, v2: str) -> int:
        """
        Compare two version strings.
        
        Returns:
            -1 if v1 < v2, 0 if equal, 1 if v1 > v2
        """
        def parse(v):
            return [int(x) for x in v.split('.') if x.isdigit()]
        
        p1, p2 = parse(v1), parse(v2)
        
        # Pad to same length
        while len(p1) < len(p2):
            p1.append(0)
        while len(p2) < len(p1):
            p2.append(0)
        
        for a, b in zip(p1, p2):
            if a < b:
                return -1
            if a > b:
                return 1
        return 0


def format_update_message(check_result: dict) -> str:
    """Format a user-friendly update message."""
    if check_result is None:
        return "Unable to check for updates."
    
    if check_result['update_available']:
        return (
            f"\n{'='*50}\n"
            f"📦 darktable update available!\n"
            f"   Current: {check_result['current']}\n"
            f"   Latest:  {check_result['latest']}\n"
            f"   Download: {check_result['url']}\n"
            f"{'='*50}\n"
        )
    else:
        return f"✓ darktable {check_result['current']} is up to date."
