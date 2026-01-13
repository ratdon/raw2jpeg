# Executor module
"""Adaptive parallel execution with resource monitoring."""

import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

import psutil
from tqdm import tqdm

from .config import get_config
from .utils import to_forward_slashes


# Constant max workers - multiple workers can cause darktable to hang
MAX_WORKERS = 2


# Global shutdown flag
_shutdown_requested = False


def _signal_handler(signum, frame):
    """Handle Ctrl+C gracefully."""
    global _shutdown_requested
    if _shutdown_requested:
        # Second Ctrl+C - force exit
        print("\n\n❌ Force quit requested. Terminating...")
        sys.exit(1)
    
    _shutdown_requested = True
    print("\n\n⚠️  Shutdown requested. Waiting for current jobs to complete...")
    print("   (Press Ctrl+C again to force quit)")


class ResourceMonitor:
    """Monitor system resources for adaptive scaling."""
    
    def __init__(self, target_cpu: float, target_memory: float):
        self.target_cpu = target_cpu
        self.target_memory = target_memory
        self._lock = threading.Lock()
        self._current_usage: Dict[str, float] = {'cpu': 0, 'memory': 0}
    
    def update(self) -> None:
        """Update current resource usage."""
        with self._lock:
            self._current_usage['cpu'] = psutil.cpu_percent(interval=0.5)
            self._current_usage['memory'] = psutil.virtual_memory().percent
    
    def can_spawn_new(self) -> bool:
        """Check if we can spawn a new process without exceeding targets."""
        with self._lock:
            return (
                self._current_usage['cpu'] < self.target_cpu and
                self._current_usage['memory'] < self.target_memory
            )
    
    @property
    def cpu(self) -> float:
        with self._lock:
            return self._current_usage['cpu']
    
    @property
    def memory(self) -> float:
        with self._lock:
            return self._current_usage['memory']


class AdaptiveExecutor:
    """
    Executor with adaptive spawning based on resource usage.
    
    Spawns one process at a time, waits 5s, checks resources,
    then decides whether to spawn another or wait.
    """
    
    SPAWN_DELAY = 5  # Seconds to wait after spawning before checking resources
    
    def __init__(self, quiet: bool = False):
        config = get_config()
        self.quiet = quiet
        self.max_workers = MAX_WORKERS  # Use constant, not configurable
        self.max_retry = config.max_retry
        self.monitor = ResourceMonitor(
            config.target_cpu_percent,
            config.target_memory_percent,
        )
        
        # Darktable settings
        self.darktable_cli = config.darktable_cli
        self.width = config.default_width
        self.height = config.default_height
        self.jpeg_quality = config.jpeg_quality
        
        self._active_count = 0
        self._lock = threading.Lock()
    
    def _build_command(self, job: dict) -> str:
        """Build darktable-cli command for PowerShell."""
        input_folder = to_forward_slashes(job['input_folder'])
        output_template = job['output_template']
        
        # Quote the exe path for paths with spaces (like C:\Program Files)
        exe_path = f'& "{self.darktable_cli}"'
        
        # Build the full command string
        # Input folder needs double quotes, output template already has single quotes
        cmd = (
            f'{exe_path} '
            f'"{input_folder}" '
            f'{output_template} '
            f'--width {self.width} '
            f'--height {self.height} '
            f'--core '
            f'--conf plugins/imageio/format/jpeg/quality={self.jpeg_quality}'
        )
        
        return cmd
    
    def _run_conversion(self, job: dict) -> dict:
        """
        Run darktable-cli for a single folder.
        
        Returns:
            dict with 'success', 'folder', 'failed_files', 'error'
        """
        result = {
            'success': False,
            'folder': str(job['input_folder']),
            'failed_files': [],
            'error': None,
        }
        
        shell_cmd = self._build_command(job)
        
        if self.quiet:
            shell_cmd += ' | out-null'
        
        try:
            # Run with PowerShell to handle single quotes in output template
            proc = subprocess.run(
                ['powershell', '-Command', shell_cmd],
                capture_output=True,
                text=True,
                check=False,
            )
            
            if proc.returncode == 0:
                result['success'] = True
            else:
                result['error'] = proc.stderr or f"Exit code: {proc.returncode}"
                # Extract failed file paths from error output
                result['failed_files'] = self._extract_failed_files(proc.stderr)
                
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def _extract_failed_files(self, stderr: str) -> List[str]:
        """Extract file paths from error messages."""
        if not stderr:
            return []
        
        # Look for file paths in error messages
        # This is a heuristic - adjust based on actual error format
        files = []
        for line in stderr.split('\n'):
            # Look for paths ending in RAW extensions
            match = re.search(r'([A-Za-z]:[^\s]+\.(arw|cr2|cr3|nef|dng))', line, re.IGNORECASE)
            if match:
                files.append(match.group(1))
        
        return files
    
    def execute_jobs(
        self,
        jobs: List[dict],
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """
        Execute conversion jobs with adaptive parallelism.
        
        Args:
            jobs: List of job dicts (each with 'file_count' for progress tracking)
            progress_callback: Called after each job completes
        
        Returns:
            dict with 'completed', 'failed', 'failed_jobs', 'results', 'files_completed'
        """
        global _shutdown_requested
        _shutdown_requested = False
        
        # Calculate total files from jobs
        total_files = sum(job.get('file_count', 0) for job in jobs)
        files_completed = 0
        
        results = {
            'completed': 0,
            'failed': 0,
            'failed_jobs': [],
            'results': [],
            'files_completed': 0,
        }
        
        if not jobs:
            return results
        
        # Setup signal handler
        original_sigint = signal.signal(signal.SIGINT, _signal_handler)
        
        try:
            pending = list(jobs)
            active_futures = {}
            
            # Create progress bar based on file count
            pbar = tqdm(total=total_files, desc="Converting", unit="file")
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                while pending or active_futures:
                    if _shutdown_requested:
                        break
                    
                    # Update resource monitoring
                    self.monitor.update()
                    
                    # Try to submit new jobs if resources allow
                    while pending and len(active_futures) < self.max_workers:
                        if _shutdown_requested:
                            break
                        
                        # Check resources if we already have active jobs
                        if active_futures and not self.monitor.can_spawn_new():
                            break
                        
                        job = pending.pop(0)
                        future = executor.submit(self._run_conversion, job)
                        active_futures[future] = job
                        
                        pbar.set_postfix({
                            'folder': job['input_folder'].name[:20],
                            'cpu': f"{self.monitor.cpu:.0f}%",
                        })
                        
                        # Wait before spawning another
                        if pending and not _shutdown_requested:
                            time.sleep(self.SPAWN_DELAY)
                            self.monitor.update()
                    
                    # Check for completed jobs
                    completed_futures = []
                    for future in active_futures:
                        if future.done():
                            completed_futures.append(future)
                    
                    for future in completed_futures:
                        job = active_futures.pop(future)
                        job_file_count = job.get('file_count', 0)
                        
                        try:
                            result = future.result()
                        except Exception as e:
                            result = {
                                'success': False,
                                'folder': str(job['input_folder']),
                                'failed_files': [],
                                'error': str(e),
                            }
                        
                        results['results'].append(result)
                        
                        # Update progress bar by file count
                        pbar.update(job_file_count)
                        files_completed += job_file_count
                        
                        if result['success']:
                            results['completed'] += 1
                            pbar.set_description(f"✓ {job['input_folder'].name[:25]}")
                        else:
                            results['failed'] += 1
                            results['failed_jobs'].append(job)
                            pbar.set_description(f"✗ {job['input_folder'].name[:25]}")
                        
                        pbar.set_postfix({
                            'folders': f"{results['completed']}/{len(jobs)}",
                            'fail': results['failed'],
                        })
                        
                        if progress_callback:
                            progress_callback(result)
                    
                    # Small sleep to prevent busy-waiting
                    if active_futures:
                        time.sleep(0.5)
        
        finally:
            pbar.close()
            signal.signal(signal.SIGINT, original_sigint)
        
        results['files_completed'] = files_completed
        return results
    
    def retry_failed_jobs(
        self,
        failed_jobs: List[dict],
        max_retries: Optional[int] = None,
    ) -> dict:
        """
        Retry failed jobs up to max_retries times.
        
        Args:
            failed_jobs: List of failed job dicts
            max_retries: Maximum retry attempts (default from config)
        
        Returns:
            Same format as execute_jobs
        """
        max_retries = max_retries or self.max_retry
        
        remaining = list(failed_jobs)
        all_results = {
            'completed': 0,
            'failed': 0,
            'failed_jobs': [],
            'results': [],
        }
        
        for attempt in range(1, max_retries + 1):
            if not remaining:
                break
            
            print(f"\n🔄 Retry attempt {attempt}/{max_retries} for {len(remaining)} failed jobs...")
            
            retry_results = self.execute_jobs(remaining)
            
            all_results['completed'] += retry_results['completed']
            all_results['results'].extend(retry_results['results'])
            
            # Update remaining for next iteration
            remaining = retry_results['failed_jobs']
        
        # Any still remaining are final failures
        all_results['failed'] = len(remaining)
        all_results['failed_jobs'] = remaining
        
        return all_results
