# Spec: Tommy Q: Zombie Defender auto-typer

## What
A Python bot that plays typing.com's **Tommy Q: Zombie Defender** (`typing.com/student/game/tommyq`) on **hardest settings** (Hard words, hard zombie pace).

## Why
The user wants a hands-off player that is accurate and cheap to run on an M4 Mac.

## Requirements
| # | Requirement | How it's verified |
|---|---|---|
| R1 | Reads game state from Chrome "memory" (live JS objects via the DevTools Protocol): each zombie's row, side, word, distance | memory-mode e2e run |
| R2 | Also reads the screen with OCR (Apple Vision) and mixes the two, **game data always outranking OCR**: fresh game data > last game data moved forward (≤ 1 s) > OCR with words snapped to game-data spellings and hidden zombies kept > raw OCR | `TestSourcePriority`, `TestFusion`, flaky-memory e2e run |
| R3a | Targets **closest to the logs / most dangerous** first: zombies chopping the logs, then smallest time-to-logs; always finishes the word the game has locked in Tommy's lane unless switching saves more zombies | `TestDangerPriority`, `TestGameLock`, `TestSwitchCost` |
| R3 | Moves Tommy (Up/Down rows, Left/Right facing) and types whole words; uses power-ups with Enter | unit tests + e2e |
| R4 | Human-like typing at ~140 WPM (user set, was 80) with jitter, bursting up to `--max-wpm` (220, user set; was 160) only when a zombie would otherwise reach the fence | unit tests (`choose_cps`, `key_delay`) |
| R5 | Bot process < 2 GB RAM | e2e `bot_rss_max_mb` |
| R6 | Bot process ≤ 20 % CPU on average | e2e `bot_cpu_avg` |
| R7 | ≥ 90 % of zombies killed before the fence on hardest mode | e2e `kill_ratio` (mock now, real game after recon) |
| R8 | Tests pass ≥ 90 % | `python -m unittest` |
| R9 | No macOS Accessibility / Screen Recording permission needed | keys + screenshots go through CDP |
| R10 | Safe stop: Ctrl+C, game over, or 10 s without game state | code path in `Bot._tick` |

## Game model (rules marked ✔ confirmed by the user)
- ✔ **5 rows**; zombies spawn in any row, from **either left or right**. Tommy is inside a wooden fence in the middle.
- ✔ Up/Down = change row, Left/Right = face that side. Typing only hits a zombie in Tommy's row on the side he faces.
- ✔ A typo does nothing (no penalty, no reset).
- ✔ Leaving the row or turning resets the partly typed word.
- ✔ Letters go to the word you start typing (either of two zombies in one lane can be chosen).
- ✔ A zombie behind another can have its label covered on screen.
- Type the whole word over a zombie to shoot it. Enter uses a power-up (Book = clear row, Ice = freeze 10 s, Bomb = kill all).
- ✔ A zombie that reaches the logs (fence) stays there chopping until killed.
- Game over when zombies break the fence.
