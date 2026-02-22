# executor.py
"""Sandboxed parallel execution with thread affinity and GPU management."""

import os
import re
import signal
import subprocess
import sys
import threading
import time
import shutil
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set

from tqdm import tqdm

from .config import get_config
from .utils import to_forward_slashes


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


def get_affinity_mask(start_thread: int, end_thread: int) -> str:
    """Calculates the hex mask for a range of threads (0-indexed)."""
    mask = 0
    for i in range(start_thread, end_thread + 1):
        mask |= (1 << i)
    return hex(mask).replace("0x", "").upper()


def generate_worker_profiles(max_workers: int, max_gpu: int) -> List[dict]:
    """Generate worker profiles with CPU affinity."""
    total_threads = os.cpu_count() or 4
    profiles = []
    
    current_end = total_threads - 1
    
    gpu_count = min(max_workers, max_gpu)
    cpu_count = max(0, max_workers - gpu_count)
    
    worker_id = 1
    
    # Assign GPU instances from reverse, 2 threads each
    for _ in range(gpu_count):
        gpu_threads = 2
        start = max(0, current_end - gpu_threads + 1)
        if start > current_end:
            start, current_end = 0, 0
        profiles.append({
            'worker_id': worker_id,
            'type': 'gpu',
            'start_thread': start,
            'end_thread': current_end,
            'hex_mask': get_affinity_mask(start, current_end),
            'use_gpu': True
        })
        current_end = start - 1
        worker_id += 1
        
    # Assign CPU instances from reverse, 4 threads each
    for _ in range(cpu_count):
        cpu_threads = 4
        start = max(0, current_end - cpu_threads + 1)
        if start > current_end:
            start, current_end = 0, 0
        profiles.append({
            'worker_id': worker_id,
            'type': 'cpu',
            'start_thread': start,
            'end_thread': current_end,
            'hex_mask': get_affinity_mask(start, current_end),
            'use_gpu': False
        })
        current_end = start - 1
        worker_id += 1
        
    return profiles


class SandboxExecutor:
    """
    Executor with sandboxed instances using explicit thread affinity.
    """
    
    def __init__(self, quiet: bool = False):
        config = get_config()
        self.quiet = quiet
        self.max_workers = config.max_workers
        self.gpu_instances = config.gpu_instances
        self.max_retry = config.max_retry
        
        # Darktable settings
        self.darktable_cli = config.darktable_cli
        self.width = config.default_width
        self.height = config.default_height
        self.jpeg_quality = config.jpeg_quality
        
        self._lock = threading.Lock()
        
        self.profiles = generate_worker_profiles(self.max_workers, self.gpu_instances)
        self.profile_queue = queue.Queue()
        for p in self.profiles:
            self.profile_queue.put(p)
            
    def _run_conversion(self, job: dict, profile: dict) -> dict:
        """
        Run darktable-cli for a single folder using a worker profile.
        """
        result = {
            'success': False,
            'folder': str(job['input_folder']),
            'failed_files': [],
            'error': None,
        }
        
        worker_id = profile['worker_id']
        hex_mask = profile['hex_mask']
        use_gpu = profile['use_gpu']
        
        config_dir = f"C:/temp/dt_worker_{worker_id}_config"
        cache_dir = f"C:/temp/dt_worker_{worker_id}_cache"
        os.makedirs(config_dir, exist_ok=True)
        os.makedirs(cache_dir, exist_ok=True)
        
        input_folder = to_forward_slashes(job['input_folder'])
        output_template = job['output_template']
        if output_template.startswith("'") and output_template.endswith("'"):
            output_template = output_template[1:-1]
            
        exe_path = str(self.darktable_cli)
        
        cmd_str = (
            f'start "" /affinity {hex_mask} /b /wait "{exe_path}" '
            f'"{input_folder}" "{output_template}" '
            f'--width {self.width} --height {self.height} '
            f'--apply-custom-presets false --core '
            f'--library :memory: --configdir "{config_dir}" --cachedir "{cache_dir}" '
            f'--conf plugins/imageio/format/jpeg/quality={self.jpeg_quality} '
            f'--conf opencl_memory_headroom=1500 '
            f'--conf opencl_async_pixelpipe=TRUE '
            f'--conf opencl_scheduling_profile=very_fast_gpu '
            f'--conf opencl={"TRUE" if use_gpu else "FALSE"}'
        )
        
        if self.quiet:
            cmd_str += ' > NUL 2>&1'
        
        try:
            proc = subprocess.run(
                cmd_str,
                capture_output=True,
                text=True,
                check=False,
                shell=True
            )
            
            if proc.returncode == 0:
                result['success'] = True
            else:
                result['error'] = proc.stderr or f"Exit code: {proc.returncode}"
                result['failed_files'] = self._extract_failed_files(proc.stderr)
                
        except Exception as e:
            result['error'] = str(e)
            
        finally:
            shutil.rmtree(config_dir, ignore_errors=True)
            shutil.rmtree(cache_dir, ignore_errors=True)
        
        return result

    def _extract_failed_files(self, stderr: str) -> List[str]:
        if not stderr:
            return []
        files = []
        for line in stderr.split('\n'):
            match = re.search(r'([A-Za-z]:[^\s]+\.(arw|cr2|cr3|nef|dng))', line, re.IGNORECASE)
            if match:
                files.append(match.group(1))
        return files

    def execute_jobs(
        self,
        jobs: List[dict],
        progress_callback: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        global _shutdown_requested
        _shutdown_requested = False
        
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
        
        original_sigint = signal.signal(signal.SIGINT, _signal_handler)
        
        try:
            pbar = tqdm(total=total_files, desc="Converting", unit="file")
            
            max_workers = len(self.profiles)
            if max_workers == 0:
                print("No worker profiles available.")
                return results

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                
                def task_wrapper(job):
                    profile = self.profile_queue.get()
                    try:
                        if _shutdown_requested:
                            return {
                                'success': False,
                                'folder': str(job['input_folder']),
                                'failed_files': [],
                                'error': "Shutdown requested",
                            }
                        return self._run_conversion(job, profile)
                    finally:
                        self.profile_queue.put(profile)

                future_to_job = {executor.submit(task_wrapper, job): job for job in jobs}
                
                for future in as_completed(future_to_job):
                    job = future_to_job[future]
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
                        
                    if _shutdown_requested:
                        for f in future_to_job:
                            f.cancel()
                        break
                        
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
            
            remaining = retry_results['failed_jobs']
        
        all_results['failed'] = len(remaining)
        all_results['failed_jobs'] = remaining
        
        return all_results
