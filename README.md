# RAW to JPEG Batch Converter

A Python wrapper around darktable-cli for batch conversion of RAW camera files to JPEG with progress tracking and retry capability.
** tested in windows 11, can be easily ported to linux by changing the path to datrktable-cli and handling other paths where-ever used.**

## Features

- **Batch Folder Processing**: Uses darktable's native batch conversion (folder input)
- **Progress Bar**: Visual progress with tqdm showing files processed
- **Smart Filename Handling**: Detects filename patterns and generates appropriate output templates
- **Retry Support**: Auto-retry failed jobs with `--resume`
- **Update Notifications**: Checks for new darktable releases
- **Graceful Shutdown**: Ctrl+C waits for current jobs to complete

## Requirements

- Python 3.10+
- [darktable](https://www.darktable.org/) with darktable-cli
- Windows PowerShell

## Installation

```bash
pip install -r requirements.txt
python raw2jpeg.py --configure
```

## Usage

### Basic Conversion

```powershell
# Convert all RAW files in a directory
python raw2jpeg.py --inpath G:\Photos\RAW

# Specify output directory
python raw2jpeg.py --inpath G:\Photos\RAW --outpath D:\Photos\JPEG

# Quiet mode (suppress darktable output)
python raw2jpeg.py --inpath G:\Photos\RAW --quiet

# Auto-retry failed jobs
python raw2jpeg.py --inpath G:\Photos\RAW --resume
```

### Utility Commands

```powershell
# Create config.ini with default settings
python raw2jpeg.py --configure

# Validate installation
python raw2jpeg.py --validate

# Check for darktable updates
python raw2jpeg.py --check-update
```

## Configuration

Edit `config.ini` to customize settings:

```ini
[paths]
darktable_cli = C:\Program Files\darktable\bin\darktable-cli.exe

[output]
default_width = 2048
default_height = 2048
jpeg_quality = 90

[performance]
target_cpu_percent = 70
target_memory_percent = 85
max_retry = 5

[updates]
check_updates = true
cache_days = 7
```

**Note**: The number of parallel workers is fixed at 2 for stability, as darktable-cli can become unresponsive with more concurrent processes.

## Filename Pattern Handling

The tool detects filename patterns and generates appropriate output:

| Input Pattern | Example | Output Subfolder |
|--------------|---------|------------------|
| Datetime prefix | `2025-12-25_16-34-32_DSC07514.ARW` | `2025-12-25/` |
| Datetime suffix | `DSC07514_2025-12-25_16-34-32.ARW` | `2025-12-25/` |
| Plain DSC | `DSC07514.ARW` | `2025-12-25/` (from EXIF) |

For plain DSC files, the output filename includes the EXIF datetime:
`DSC07514.ARW` → `2025-12-25_16-34-32_DSC07514.jpg`

## How It Works

1. **Discovery**: Recursively finds leaf folders containing RAW files
2. **Pattern Detection**: Checks sample file to determine filename format
3. **Job Creation**: Creates darktable-cli commands with appropriate output templates
4. **Parallel Execution**: Runs up to 2 concurrent conversions with resource monitoring
5. **Retry**: Failed folders are automatically retried up to `max_retry` times

## License

MIT License

<!-- Build ID: 524154444F4E -->
