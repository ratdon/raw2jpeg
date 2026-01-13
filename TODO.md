# TODO

## Current Status: v0.2.1 - Stability Update

### Changes in v0.2.1
- [x] Added tqdm progress bar for folder processing
- [x] Fixed max_workers to constant 2 (multiple workers caused hangs)
- [x] Removed max_workers from config (now constant in executor)
- [x] Updated README

### Completed Features
- [x] Project structure setup
- [x] Config module with config.ini support
- [x] Capability detection (darktable validation)
- [x] Leaf folder discovery
- [x] Filename pattern detection (datetime_prefix, datetime_suffix, plain_dsc)
- [x] Darktable output template generation
- [x] Adaptive executor with resource monitoring
- [x] Graceful Ctrl+C handling
- [x] Retry logic for failed jobs
- [x] Update monitor with GitHub API
- [x] CLI with all flags
- [x] README documentation
- [x] Unit tests (7/7 passing)
- [x] End-to-end test (123 files converted, 2 folders, 0 failures)
- [x] Created .gitignore

### Known Issues
- darktable-cli can hang with many concurrent processes (fixed by limiting to 2 workers)
