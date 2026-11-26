# Spec: Tommy Q: Zombie Defender auto-typer

## What
A Python bot that plays typing.com's **Tommy Q: Zombie Defender** (`typing.com/student/game/tommyq`) on **hardest settings** (Hard words, hard zombie pace).

## Why
The user wants a hands-off player that is accurate and cheap to run on an M4 Mac.

## Requirements
| # | Requirement | How it's verified |
|---|---|---|
| R1 | Reads game state from Chrome "memory" (live JS objects via the DevTools Protocol): each zombie's row, side, word, distance | memory-mode e2e run |
| R2 | Also reads the screen with OCR (Apple Vision) and mixes the two: OCR cross-checks memory, and takes over if memory fails | mixed / OCR-only e2e runs, OCR accuracy ≥ 90 % |
| R3 | Moves Tommy (Up/Down rows, Left/Right facing) and types whole words; uses power-ups with Enter | unit tests + e2e |
| R4 | Human-like typing at ~80 WPM with jitter, bursting up to `--max-wpm` (160) only when a zombie would otherwise reach the fence | unit tests (`choose_cps`, `key_delay`) |
| R5 | Bot process < 2 GB RAM | e2e `bot_rss_max_mb` |
| R6 | Bot process ≤ 20 % CPU on average | e2e `bot_cpu_avg` |
| R7 | ≥ 90 % of zombies killed before the fence on hardest mode | e2e `kill_ratio` (mock now, real game after recon) |
| R8 | Tests pass ≥ 90 % | `python -m unittest` |
| R9 | No macOS Accessibility / Screen Recording permission needed | keys + screenshots go through CDP |
| R10 | Safe stop: Ctrl+C, game over, or 10 s without game state | code path in `Bot._tick` |

## Game model (from research; to be confirmed by recon)
- Tommy stands inside a wooden fence in the middle; zombies walk along grass rows from **both left and right**.
- Up/Down = change row, Left/Right = face that side. Typing only hits a zombie in Tommy's row on the side he faces.
- Type the whole word over a zombie to shoot it. Enter uses a power-up (Book = clear row, Ice = freeze 10 s, Bomb = kill all).
- Game over when zombies break the fence.
