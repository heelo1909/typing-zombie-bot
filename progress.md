# progress.md

## 2026-11-26: session 1 (work computer, no access to the live game)

### Done
- Researched the game (no live access; Chrome extension not connected). Model in `docs/game_notes.md`.
- `zombie_bot.py`: CDP client, memory probe reader, Apple Vision OCR on a background thread, EDF planner, burst-WPM typing, power-ups, dead reckoning in OCR-only mode, auto-reconnect, CSV log, CPU/RSS summary.
- `mock/tommyq_mock.html`: local stand-in that follows the game model (5 rows, both sides, facing, whole words, fence HP, power-ups, `pace`/`typo`/`seed` params).
- `recon.py`: engine detection, canvas `fillText` hook (word + x/y as drawn), bounded JS object scan, screenshot. Checked on the mock: found all moving words and the 5 row y-values.
- `launch_chrome.sh`: separate profile + DevTools port; opens the tab via CDP if managed Chrome shows a profile picker (it does on this work Mac).
- `bench/e2e_mock.py`: end-to-end run with psutil CPU/RSS sampling.
- Docs: `docs/spec.md`, `docs/design.md`, `docs/game_notes.md`, `README.md`.

### Test results
- Unit tests: **40 / 40 pass** (`.venv/bin/python -m unittest discover -s tests`).
- OCR accuracy vs. memory ground truth (fully visible zombies, 15 frames): **92.9 %** of words read right, with the right row and side.
- E2E on the mock, **hard pace, typos reset the word**, 60 s, seed 21:

| mode | kills / fence hits | kill ratio | bot CPU avg (max) | bot RSS max |
|---|---|---|---|---|
| memory | 43 / 3 | **93.5 %** ✅ | 1.4 % (8.5) | 23 MB |
| mixed (default) | 43 / 2 | **95.6 %** ✅ | 6.2 % (32.6) | 99 MB |
| ocr only | 38 / 7 | 84.4 % ❌ | 15.8 % | 98 MB |

  With typos ignored, the 40 s runs got: memory 96.4 %, mixed 100 %, OCR-only 96.4 %. A 90 s mixed run with typo reset got 100 % (40 / 40).
- The CPU and RAM budgets (≤ 20 % avg, < 2 GB) are met in every mode.

### Problems found and fixed
- First mixed run got 23 % kills: the first Apple Vision call loads its model (several seconds) and blocked typing. Fixed by running OCR on its own thread and warming it up before play starts.
- One run crashed on a dropped DevTools connection. Added auto-reconnect (a tab reload mid-run is handled).
- OCR-only typed misread words. Words now need 2 identical OCR reads first (`--ocr-confirm`), which cut misses from 63 to 27.

### Known gaps
- **OCR-only is below 90 %** on hard pace with typo reset. Fence-hit analysis: 3 of 10 were words OCR read missing their last letter (bot typed 8/9 letters). 7 were never read cleanly enough to target (overlapping labels, left edge). Retune on the real game's font after recon. The mock's font isn't the real one.
- `probes/tommyq.js` and `profiles/tommyq.json` are placeholders (`needs_recon: true`) until the live game is inspected.

### Next
See `plan.md`: recon at the home desktop with Claude in Chrome.
