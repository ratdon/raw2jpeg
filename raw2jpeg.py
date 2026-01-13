#!/usr/bin/env python3
"""Entry point for raw2jpeg batch converter."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from common.cli import main

if __name__ == '__main__':
    sys.exit(main())
