#!/usr/bin/env python3
"""Tommy Q bot, normal version: human-like 140 WPM, speeds up to 220 WPM only when a zombie nears the logs. Same flags as zombie_bot.py (e.g. --log, --dry-run)."""
import sys

from zombie_bot import main

if __name__ == "__main__":
    sys.exit(main(["--preset", "normal"] + sys.argv[1:]))
