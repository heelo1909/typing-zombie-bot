# Tommy Q zombie bot

A small Python bot for typing.com's **Tommy Q: Zombie Defender**. It reads the game's live state out of Chrome through the DevTools Protocol (the main source), uses on-screen OCR (Apple Vision) only to check and fill gaps, goes after zombies closest to the logs first, moves Tommy to the right row and side, and types the words.

> **Status:** plays the real game. Best real run so far: 315 kills, level 6 (normal version, Hard). See `progress.md`.

## Two versions
| Version | Run | Typing |
|---|---|---|
| **Normal** | `./tommyq_normal.py` | Human-like 140 WPM with random variation; speeds up to 220 WPM only when a zombie is about to reach the logs |
| **Instant** | `./tommyq_instant.py` | Every word as fast as Chrome accepts keys (~8 ms per letter, whole word at once): zombies die right after they appear |

Both versions press keys through the game's normal input and only read game data; they never change it. `zombie_bot.py --preset normal|instant` does the same thing, and any flag (e.g. `--wpm 120`) overrides the preset.

Measured on the mock (hard pace, 60 s): normal kills a zombie ~0.95 s after it spawns, instant ~0.03 s. Both stop 100 % before the logs at ~3 % CPU and < 100 MB.

## Setup (macOS, Apple Silicon)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run against the real game
```bash
./launch_chrome.sh                 # separate Chrome profile with DevTools on :9222
# log into typing.com in that window, open Tommy Q, pick Hard, click PLAY, keep the tab in front
.venv/bin/python tommyq_normal.py       # or: .venv/bin/python tommyq_instant.py
```
Both wait on menus, and after game over they wait for the next round. Stop with Ctrl+C.
Flags: `--mode mixed|memory|ocr` (default mixed), `--wpm N`, `--max-wpm N`, `--jitter F`, `--dry-run`, `--seconds N`, `--log bench/run_log.csv`, `--ocr-fast`, `-v`.

## Recon (first time on the live game)
```bash
.venv/bin/python recon.py --match typing.com --seconds 8   # while playing
```
Writes `recon/report.json`, `recon/summary.txt`, and a screenshot.

## Try it on the mock
```bash
HEADLESS=1 PORT=9333 PROFILE_DIR=/tmp/zb-chrome ./launch_chrome.sh "file://$PWD/mock/tommyq_mock.html"
.venv/bin/python bench/e2e_mock.py --port 9333 --seconds 60 --mode mixed --extra "--preset instant"
```

## Tests
```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Note
Using a bot may break typing.com's terms or a teacher's rules if this is a school account.
