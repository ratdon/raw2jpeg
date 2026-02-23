Goal: Modify my Python darktable-cli wrapper to maximize throughput for 52MP Sony RAW files by implementing "Sandboxed Parallelism" while avoiding GPU VRAM overflow and database locks.

Hardware Context:

    CPU: 8 Cores / 16 Threads (Intel i7-11800H).

    GPU: NVIDIA RTX 3070 Laptop (8GB VRAM).

    RAM: 64GB (Use this to offload disk I/O).

Core Logic Requirements:

    Thread Distribution: Implement a worker pool that runs 3 simultaneous instances.

        Two (2) instances should be pinned to specific CPU cores (e.g., threads 9-12 and 13-16) and use OpenCL=TRUE.

        One (1) instance should be CPU-only (OpenCL=FALSE) to fill the "gaps" in GPU usage without fighting for VRAM.

    Sandbox Isolation: Each instance must have its own unique, temporary --configdir and --cachedir in C:/temp/dt_worker_{n} to prevent "Database is Locked" errors.

    In-Memory Processing: Use --library :memory: to eliminate disk database latency.

    GPU Management: Set opencl_memory_headroom=1500 to prevent OOM (Out of Memory) crashes when both GPU instances process 52MP buffers simultaneously.

🛠️ The Final "Turbo" Command Template

For each worker in your script, the command generated should look like this:
Bash

# Windows Affinity Launch (Example for Threads 9-12, Hex Mask: F00)
:: Windows Affinity Launch (Example for Threads 9-12, Hex Mask: F00)
start /affinity F00 /b /wait darktable-cli.exe
  "{input_folder_or_file}"
  "{output_template}"
  --width 2048
  --height 2048
  --apply-custom-presets false
  --library :memory:
  --configdir "C:/temp/dt_config_{worker_id}"
  --cachedir "C:/temp/dt_cache_{worker_id}"
  --core
  --conf plugins/imageio/format/jpeg/quality=90
  --conf opencl_memory_headroom=1500
  --conf opencl_async_pixelpipe=TRUE
  --conf opencl_scheduling_profile=very_fast_gpu
  --conf opencl={TRUE_OR_FALSE}

Why these flags matter for you:

    --library :memory:: Stops the "1-second GPU idle" gap caused by writing to the slow local database.

    opencl_memory_headroom=1500: On an 8GB card, this ensures that even if Instance 1 spikes to 4GB, Instance 2 has room to breathe before the driver crashes.

    --configdir / --cachedir: This is the "ChatGPT recommendation" made real—it's the only way to truly run parallel darktable-cli processes on Windows without they themselves tripping over each other.

    very_fast_gpu: Tells darktable to send data to the RTX 3070 as fast as possible, reducing the "starvation" you noticed in Task Manager.
    
    

Pro-Tip: Cleanup

Since you are creating temporary directories for each thread, make sure your script deletes the tmp_config and tmp_cache folders after the process exits, or your C: drive will slowly fill up with tiny redundant databases!




def get_affinity_mask(start_thread, end_thread):
    """
    Calculates the hex mask for a range of threads (0-indexed).
    Example: (8, 11) -> bits for 8,9,10,11 set -> 'F00'
    """
    mask = 0
    for i in range(start_thread, end_thread + 1):
        mask |= (1 << i)
    return hex(mask).replace("0x", "").upper()

# Example Usage for your threads 9-16:
# print(get_affinity_mask(8, 11))  # Returns 'F00'
# print(get_affinity_mask(12, 15)) # Returns 'F000'





import subprocess
import os
import shutil

def run_darktable_worker(worker_id, thread_range, input_path, output_path, use_gpu=True):
    # 1. Setup Environment
    start, end = thread_range
    hex_mask = get_affinity_mask(start, end)
    
    config_dir = f"C:/temp/dt_config_{worker_id}"
    cache_dir = f"C:/temp/dt_cache_{worker_id}"
    os.makedirs(config_dir, exist_ok=True)
    os.makedirs(cache_dir, exist_ok=True)

    # 2. Build the Command
    # We use 'cmd /c start /affinity' to invoke the Windows affinity launcher
    cmd = [
        "cmd", "/c", "start", "/affinity", hex_mask, "/b", "/wait",
        "darktable-cli.exe",
        input_path,
        output_path,
        "--width", "2048",
        "--height", "2048",
        "--library", ":memory:",
        "--configdir", config_dir,
        "--cachedir", cache_dir,
        "--core",
        "--conf", "plugins/imageio/format/jpeg/quality=90",
        "--conf", "opencl_memory_headroom=1500",
        "--conf", "opencl_async_pixelpipe=TRUE",
        "--conf", "opencl_scheduling_profile=very_fast_gpu",
        "--conf", f"opencl={'TRUE' if use_gpu else 'FALSE'}"
    ]

    # 3. Execute
    try:
        print(f"Worker {worker_id} starting on threads {start}-{end} (GPU: {use_gpu})...")
        subprocess.run(cmd, check=True)
    finally:
        # Cleanup sandbox to save disk space
        shutil.rmtree(config_dir, ignore_errors=True)
        shutil.rmtree(cache_dir, ignore_errors=True)

# Example: Run worker 1 on threads 9-12 with GPU enabled
# run_darktable_worker(1, (8, 11), "in.ARW", "out.jpg", use_gpu=True)