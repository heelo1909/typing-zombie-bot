# Tommy Q zombie bot

A small Python bot for typing.com's **Tommy Q: Zombie Defender**. It reads the game's live state out of Chrome through the DevTools Protocol (the main source), uses on-screen OCR (Apple Vision) only to check and fill gaps, goes after zombies closest to the logs first, moves Tommy to the right row and side, and types the words at a human-like ~80 WPM. It speeds up to 160 WPM only when a zombie would otherwise reach the fence.

> **Status:** fully working against the included local mock (`mock/tommyq_mock.html`). The real game's state reader (`probes/tommyq.js` + `profiles/tommyq.json`) is filled in after one recon session on the live game. See `plan.md`.

## Setup (macOS, Apple Silicon)
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Run against the real game (after recon)
```bash
./launch_chrome.sh                 # separate Chrome profile with DevTools on :9222
# log into typing.com in that window, open Tommy Q, pick Hard words + hard pace, start
.venv/bin/python zombie_bot.py --profile profiles/tommyq.json
```
Flags: `--mode mixed|memory|ocr` (default mixed), `--wpm 80`, `--max-wpm 160`, `--dry-run`, `--seconds N`, `--log bench/run_log.csv`, `--ocr-fast`, `-v`. Stop with Ctrl+C.

## Recon (first time on the live game)
```bash
.venv/bin/python recon.py --match typing.com --seconds 8   # while playing
```
Writes `recon/report.json`, `recon/summary.txt`, and a screenshot.

## Try it on the mock
```bash
HEADLESS=1 PORT=9333 PROFILE_DIR=/tmp/zb-chrome ./launch_chrome.sh "file://$PWD/mock/tommyq_mock.html"
.venv/bin/python bench/e2e_mock.py --port 9333 --seconds 60 --mode mixed
```

## Tests
```bash
.venv/bin/python -m unittest discover -s tests -v
```

## Measured on the mock (M4, hard pace, real rules, 60 s)
See `progress.md` for the latest numbers.

## Note
Using a bot may break typing.com's terms or a teacher's rules if this is a school account.
