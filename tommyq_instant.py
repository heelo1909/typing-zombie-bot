#!/usr/bin/env python3
"""Tommy Q bot, instant version: types every word as fast as Chrome accepts keys. Same flags as zombie_bot.py (e.g. --log, --dry-run)."""
import sys

from zombie_bot import main

if __name__ == "__main__":
    sys.exit(main(["--preset", "instant"] + sys.argv[1:]))
