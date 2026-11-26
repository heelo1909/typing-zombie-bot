# progress.md

## 2026-11-26: session 4c (34-minute instant run)
- Instant version, real game, Hard: **5279 kills, level 16**, 2030 s (34 min). 3 automatic reconnects, CPU 6.4 % avg, 113 MB peak. `lane_reversals` 1609 over 5292 targets: many are expected in instant mode (next zombie in the opposite direction), not yet split into real flip-flops.
- That run's CSV log was overwritten when the user started the next run with the same `--log` path. The bot now never overwrites: an existing log gets a new `-YYYYMMDD-HHMMSS` file, and the path is printed at start.

## 2026-11-26: session 4b (first instant run on the real game)
- Normal version, real game (summary of the run before): 323 s, 225 targets, game over at **253 kills, level 6**. `lane_reversals` 33, `stale_player_reads` 205 (the lane fix caught 205 stale reads). CPU 4.9 %, 120 MB.
- Instant version, real game: started typing ("designing", "annual"), then the typing.com tab disappeared from the bot's Chrome. Its DevTools connection closed and reconnecting looped silently. Cause of the tab loss is unknown; asked the user.
- Fixes:
  - Reconnect now waits indefinitely for the game tab, with a message after 3 s and on success.
  - Startup with no game tab waits with instructions instead of crashing.
  - Tested on the mock by closing and reopening the tab mid-run: 1 reconnect, play resumed.

## 2026-11-26: session 4 (two versions)
- User asked for two versions: one that kills everything instantly, one that plays normally at ~140 WPM.
- `PRESETS` in `zombie_bot.py` + two runnable scripts:
  - `tommyq_normal.py`: 140 WPM, ±30 % jitter, speeds up to 220 WPM only when needed, one letter per tick, 20 Hz polling.
  - `tommyq_instant.py`: no delays or jitter, whole word per tick (`word_burst`), 30 Hz polling.
  - Both use real key presses only; game data is read, never written.
  - `--preset normal|instant` on `zombie_bot.py`; explicit flags override the preset.
- Mock, hard, 60 s, seed 21:

| version | kills / spawned | stopped before logs | avg zombie life | bot CPU avg | RSS |
|---|---|---|---|---|---|
| normal | 48 / 50 | 100 % | 0.95 s | 2.7 % | 99 MB |
| instant | 42 / 43 | 100 % | **0.03 s** | 3.4 % | 99 MB |

- Instant survival on the mock with 10 HP: ran the full 300 s cap, **0 HP lost**, level 8, 3.5 % CPU. Normal with the 220 WPM limit had died at 173 s.
- Mock now records zombie lifetime (`avg_zombie_life_s`). Tests **87 / 87**.

## 2026-11-26: session 3d (second real run, after the lane fix)
- Real game, Hard: **315 kills, level 6** (previous run: 106 kills, level 4). First 4 min of the log: no zombie reached the logs, steady 140 WPM, collected book + ice.
- The CSV log is now line-buffered so it can be read while the bot runs.

## 2026-11-26: session 3c (lanes flipping back and forth)
- User report: the bot sometimes alternated between lanes very fast and stalled.
- Cause: since keys run on a clock (140 WPM change), the bot reads the game right after pressing an arrow. When Chrome applies the key late, the read still shows the old lane, so the bot pressed again, overshot and bounced back. Reproduced with a key-lag option in the mock (`lag=ms`).
- Fix: for `MOVE_TRUST_S` = 0.35 s after a move, a read that disagrees with the bot's own position is treated as stale (`stale_player_reads`). Also gave real-game objects stable ids (`__zbId`); list positions shift whenever anything dies.
- Mock, 45 s, key lag 40 ms: old 411 arrows / **198 reversals** / 7 kills → new 74 arrows / **3 reversals** / 34 kills. At 80 ms: 152 → 1 reversals, 5 → 34 kills.
- A planner-only simulation (3000 random games incl. power-up words and knock-back) showed the targeting itself almost never reverses (23 single reversals), so the timing bug was the cause.
- Summary now reports `lane_reversals` and `stale_player_reads`. Tests **81 / 81**.

## 2026-11-26: session 3b (speed-up limit 220 WPM)
- Default `--max-wpm` raised from 160 to **220** at the user's request (normal speed stays 140 WPM).
- Mock survival, 10 HP, seed 21, hard: 160 WPM limit → 141 s, 130 kills, level 9. 220 WPM limit → **173 s, 183 kills, level 13** (+41 % kills). CPU 3.4 % in both.

## 2026-11-26: session 3 (first live run on the real game)
- Real game, Hard: **106 kills, reached level 4**, ~4 min 13 s. Game data read every tick (3591/3591), CPU 4.9 % avg, 101 MB peak. Bot typed at a steady 140 WPM; almost no zombie reached the logs until the last ~15 s.
- Lost in the level-4 horde wave. Spawn delay 2650 ms × 0.75³ × 0.65 ≈ 0.73 s per zombie. 7.6-letter words at 140 WPM + moves ≈ 1.3 kills/s, so the bot was at capacity and the right side got swamped.
- Power-ups: 16 books used, 0 ice/bomb. Fixes:
  - No power-up pickup while one is held (the game destroys the held one).
  - Ice/bomb/book are also used when **overloaded** (required speed > `--max-wpm` for the next 3 zombies), not only when a zombie is already doomed.
  - Pickups are logged as `pickup:<kind>`.
- Mock check after the change: 48/49 kills, 100 % stopped before the logs, 3.3 % CPU. Tests **76 / 76**.
- OCR agreement on the real game was 41.5 %. The real label font/positions need tuning, but OCR is only a fallback.

## 2026-11-26: session 2 (recon on the real game, done from the work Mac)
- The user ran `recon.py` on the live game. Found Phaser 3.10.1 on a 916×400 WebGL canvas in the page. Read the game's objects and code read-only over CDP; full findings in `docs/game_notes.md`.
- Wrote `probes/tommyq.js` (zombies + power-up words, rows, sides, distance to the chop line, speed from fps, letters typed, held power-up, log health, game over) and filled `profiles/tommyq.json` (`needs_recon: false`). Verified the probe on the live page.
- Planner: power-ups are words to collect (`pickup_if_safe`: only when the most dangerous zombie keeps ≥ 1.5 s spare). The book now matches the real rule (Tommy's row, facing side only).
- Real-game behaviour:
  - Waits quietly while the game is on a menu (no OCR typing of menu text).
  - After game over it waits for the next round instead of exiting.
  - No focus click, which could hit a menu button.
- OCR CPU: a dry run on the real page showed 42.9 % CPU. The Retina PNG screenshot cost ~0.45 s CPU per read. Now JPEG q100 at CSS resolution (~0.10 s/read), and the OCR rate adapts: every 3 s as a cross-check while game data works, 1.5/s only when it fails. Real page dry run: 3.8 % CPU.
- Benchmark fix: the mock tab is brought to the front (background tabs pause the game loop), and OCR-only runs auto-start the mock.
- Tests: **72 / 72 pass**.

| mock, hard, 60 s, seed 21 | kills / spawned | stopped before logs | HP lost | bot CPU avg | RSS |
|---|---|---|---|---|---|
| mixed (default) | 47 / 48 | **100 %** | 0 | **3.1 %** | 100 MB |
| mixed, 90 % game-data reads failing | 46 / 48 | **100 %** | 0 | 6.1 % | 99 MB |
| ocr only | 46 / 50 | **97.9 %** ✅ | 0 | 8.6 % | 103 MB |

Not done yet: a live run on the real game (needs the user to click PLAY).
- Raw recon dumps (incl. copies of typing.com's game code) were pushed by mistake. History was rewritten and force-pushed (user approved), so `main` no longer contains them. GitHub still serves the orphaned commit 0091b5e by direct link until GitHub Support purges it.

## 2026-11-26: session 1f (speed set to 140 WPM)
- Default `--wpm` changed from 80 to **140** at the user's request; burst cap `--max-wpm` stays 160.
- Measured speed was only ~118–124 WPM: each key waited its full delay *plus* the time to read state and send the key, and Chrome sometimes takes 100+ ms to accept a key. Keys now run on a clock (`next_key_at`): processing time comes out of the delay, and keys after a slow one catch up. Measured within words: memory 138 WPM, mixed 140 WPM.
- 60 s hard-pace mixed run at 140 WPM: 47 kills, **100 % stopped before the logs**, 0 HP lost, 0 wrong keys, CPU 4.1 % avg, 99 MB.

## 2026-11-26: session 1e (first run by the user)
- The user's first run hit "game over" immediately: the mock auto-started on page load and lost its HP before the bot connected. The mock now waits on a "Press Enter to start" screen (`autostart=1` for the old behaviour), and the bot presses Enter when the probe reports `started: false`. The real-game probe should report `started` too.
- If the bot finds a finished game before it has pressed a key, it reloads the tab once (`reload_if_over` in the profile; on for the mock). The user's open tab still had the old, finished game.
- `cpu_percent_avg` counted startup work (Vision warm-up) against a ~0 s run, so it showed 60,275 %. It's now measured from the start of play, and is null for runs under 1 s. Verified: 12 s run, 4.4 %.

## 2026-11-26: session 1d
User confirmed: zombies at the logs stay there chopping until killed. The bot and mock already assumed this; docs updated.

## 2026-11-26: session 1c (targeting + game-data priority)

### User input
Letters go to the word you **start** typing; a zombie behind another can have its label covered on screen; prioritize zombies **closest to the logs / most dangerous**; **game data must outrank OCR**.

### Changes
- Planner priority (`danger_key`): zombies chopping the logs first, then closest to the logs (time-to-logs), then fewest moves, then shortest word. Choppers are always killable and get a 0.75 s deadline, so the bot speeds up for them.
- `game_lock`: a word already started in Tommy's lane is where letters go, so the bot finishes it unless switching saves more zombies.
- Fallback order when game data isn't available: fresh game data → last game data moved forward (≤ 1 s, `--mem-hold`) → OCR with words snapped to game-data spellings and hidden zombies kept (≤ 2 s, `--mem-carry`) → raw OCR (needs 2 identical reads).
- Zombies whose last letter was sent are treated as dead unless fresh game data shows them alive. This fixed the bot chasing killed zombies in old game data: with 90 % of game-data reads failing, stopped-before-logs went from 61 % to 100 %.
- Mock: first-letter lock, zombies chop the logs (1 HP / 1.5 s) until killed (`chop=1`, assumed), nearer labels drawn over the ones behind, `flaky=p` to make game-data reads fail.
- Tests: **65 / 65 pass** (+16: danger order, game lock, fusion, source priority, presumed-dead).

### E2E on the mock: hard pace, chopping on, 60 s, seed 21
"Stopped" = killed before reaching the logs.

| mode | game-data reads failing | kills | stopped before logs | HP lost | wrong keys | bot CPU avg | RSS |
|---|---|---|---|---|---|---|---|
| memory | 0 % | 43 | 86.4 % (seeds 5 / 33: 97.7 / 100 %; avg 94.7 %) | 0 | 0 | 1.7 % | 23 MB |
| mixed (default) | 0 % | 43 | **91.3 %** | 2 | 0 | 6.0 % | 105 MB |
| mixed | 30 % | 45 | **93.3 %** | 2 | 0 | 6.3 % | 106 MB |
| mixed | 90 % | 46 | **100 %** | 0 | 7 | 6.1 % | 102 MB |
| ocr only | n/a | 32 | 81.2 % ❌ | 4 | 0 | 13.0 % | 101 MB |

### Notes
- Runs started as background jobs from the agent sometimes ran 2–3× slower than requested (macOS throttling those jobs); foreground runs are on time. Benchmark in the foreground.
- OCR-only is still below 90 %; retune on the real game's font after recon.


## 2026-11-26: session 1b (game rules confirmed by the user)

### Confirmed rules
5 rows; zombies spawn in any row from either side; Tommy faces left or right; **a typo does nothing**; **leaving the row or turning resets the partly typed word**.

### Changes
- Mock: typos ignored by default; moving or turning resets the partly typed word (`stats.resets`).
- Planner: `switch_pays_off` treats the reset as the cost of switching. It only leaves a half-typed word if that saves more zombies than finishing it first, and it locks onto a zombie the game already shows progress on.
- Bot: counts its own letters sent per target (`_next_index`). In mixed mode the game's `typed` count lagged behind keys sent during OCR screenshots, so the bot retyped letters. Wrong keystrokes dropped from 68 to 0, and kills in 60 s rose from 38 to 43.
- Tests: **49 / 49 pass** (+9 for switch cost and letter counting).

### E2E on the mock, real rules, hard pace, 60 s, seed 21
| mode | kills / fence hits | kill ratio | wrong keys | bot CPU avg | bot RSS max |
|---|---|---|---|---|---|
| memory | 43 / 2 | **95.6 %** ✅ | 1 | 1.5 % | 23 MB |
| mixed (default) | 43 / 3 | **93.5 %** ✅ | 0 | 5.9 % | ~100 MB |
| ocr only | 39 / 6 | 86.7 % ❌ | 36 | 13.9 % | 98 MB |

OCR-only is still the known gap (fallback mode; retune on the real font after recon).


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
