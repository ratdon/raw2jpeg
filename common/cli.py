# CLI module
"""Command-line interface for raw2jpeg."""

import argparse
import sys
from pathlib import Path

from .config import CONFIG_FILE, create_config_file, get_config


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog='raw2jpeg',
        description='Batch convert RAW files to JPEG using darktable-cli',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --inpath G:\\Photos\\RAW
  %(prog)s --inpath G:\\Photos\\RAW --outpath D:\\Photos\\JPEG
  %(prog)s --inpath G:\\Photos\\RAW --quiet
  %(prog)s --configure
  %(prog)s --check-update
        """,
    )
    
    # Main arguments
    parser.add_argument(
        '--inpath',
        type=Path,
        help='Input directory containing RAW files (recursive)',
    )
    parser.add_argument(
        '--outpath',
        type=Path,
        default=None,
        help='Output directory (default: <inpath-name>-jpeg/)',
    )
    
    # Progress/output control
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Suppress darktable-cli output',
    )
    parser.add_argument(
        '--resume',
        action='store_true',
        help='Track failed items and retry at the end',
    )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Skip confirmation prompts',
    )
    
    # Utility commands
    parser.add_argument(
        '--configure',
        action='store_true',
        help='Create initial config.ini with default values',
    )
    parser.add_argument(
        '--check-update',
        action='store_true',
        help='Check for darktable updates',
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate installation (check darktable-cli path)',
    )
    
    return parser


def handle_configure() -> int:
    """Create config.ini with default values."""
    if CONFIG_FILE.exists():
        print(f"⚠️  Config file already exists: {CONFIG_FILE.absolute()}")
        response = input("Overwrite? [y/N]: ").strip().lower()
        if response != 'y':
            print("Aborted.")
            return 1
    
    create_config_file()
    print(f"✓ Created config file: {CONFIG_FILE.absolute()}")
    print("  Edit this file to customize settings.")
    return 0


def handle_check_update() -> int:
    """Check for darktable updates."""
    from .updater import UpdateMonitor, format_update_message
    
    print("Checking for darktable updates...")
    monitor = UpdateMonitor()
    result = monitor.check_for_updates()
    print(format_update_message(result))
    return 0


def handle_validate() -> int:
    """Validate installation."""
    from .capability import validate_installation
    
    print("Validating installation...")
    result = validate_installation()
    
    print()
    if result['darktable_ok']:
        print(f"✓ darktable-cli: {result['darktable_version']}")
        print(f"  Path: {result['darktable_path']}")
    else:
        print(f"✗ darktable-cli: NOT FOUND")
        print(f"  Expected: {result['darktable_path']}")
    
    if result['errors']:
        print()
        print("Errors:")
        for err in result['errors']:
            print(f"  - {err}")
        return 1
    
    print()
    print("✓ All tools validated successfully!")
    return 0


def run_conversion(args: argparse.Namespace) -> int:
    """Run the main conversion workflow."""
    from .capability import validate_installation
    from .executor import SandboxExecutor
    from .planner import create_conversion_jobs, discover_leaf_folders, get_default_outpath
    from .updater import UpdateMonitor, format_update_message
    
    config = get_config()
    
    # Validate installation first
    validation = validate_installation()
    if not validation['darktable_ok']:
        print("❌ Installation validation failed!")
        for err in validation['errors']:
            print(f"   {err}")
        print("\nRun with --validate for more details.")
        return 1
    
    # Check for updates if enabled
    if config.check_updates:
        try:
            monitor = UpdateMonitor()
            update_check = monitor.check_for_updates()
            if update_check and update_check['update_available']:
                print(format_update_message(update_check))
        except Exception:
            pass  # Don't fail on update check errors
    
    # Determine paths
    inpath = args.inpath.resolve()
    outpath = args.outpath.resolve() if args.outpath else get_default_outpath(inpath)
    
    if args.outpath and not outpath.exists():
        if not args.yes:
            print(f"⚠️  Output directory does not exist: {outpath}")
            response = input("Create it and proceed? [y/N]: ").strip().lower()
            if response != 'y':
                print("Aborted.")
                return 1
        outpath.mkdir(parents=True, exist_ok=True)
    elif not outpath.exists():
        outpath.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📁 Input:  {inpath}")
    print(f"📁 Output: {outpath}")
    print()
    
    # Discover leaf folders
    print("🔍 Discovering folders with RAW files...")
    leaf_folders = discover_leaf_folders(inpath, outpath)
    print(f"   Found {len(leaf_folders)} folders to process")
    
    if not leaf_folders:
        print("   No RAW files found. Exiting.")
        return 0
    
    # Create jobs
    print("📋 Planning conversion jobs...")
    jobs, file_counts, total_files = create_conversion_jobs(leaf_folders, inpath, outpath)
    print(f"   Total: {total_files} files across {len(jobs)} folders")
    
    # Execute
    print()
    print("🚀 Starting conversion...")
    print()
    
    executor = SandboxExecutor(quiet=args.quiet)
    results = executor.execute_jobs(jobs)
    
    # Retry failed jobs if --resume is set
    if args.resume and results['failed_jobs']:
        print(f"\n🔄 Retrying {len(results['failed_jobs'])} failed jobs...")
        retry_results = executor.retry_failed_jobs(results['failed_jobs'])
        
        results['completed'] += retry_results['completed']
        results['failed'] = retry_results['failed']
        results['failed_jobs'] = retry_results['failed_jobs']
        results['results'].extend(retry_results['results'])
    
    # Summary
    print()
    print("=" * 50)
    print(f"✓ Completed: {results['completed']} folders")
    print(f"✗ Failed:    {results['failed']} folders")
    print("=" * 50)
    
    if results['failed'] == 0:
        print("\n✓ All folders converted successfully!")
    else:
        print(f"\n⚠️  Some folders failed.")
        for job in results['failed_jobs']:
            print(f"   ✗ {job['input_folder']}")
        return 1
    
    return 0


def main() -> int:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Handle utility commands first
    if args.configure:
        return handle_configure()
    
    if args.check_update:
        return handle_check_update()
    
    if args.validate:
        return handle_validate()
    
    # Require inpath for conversion
    if not args.inpath:
        parser.print_help()
        print("\n❌ Error: --inpath is required for conversion.")
        return 1
    
    if not args.inpath.exists():
        print(f"❌ Error: Input path does not exist: {args.inpath}")
        return 1
    
    return run_conversion(args)


if __name__ == '__main__':
    sys.exit(main())
