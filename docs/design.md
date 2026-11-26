# Design

```
 Chrome (--remote-debugging-port)                 zombie_bot.py
 ┌───────────────────────────┐   Runtime.evaluate   ┌──────────────┐
 │ game tab / frame          │◄──────(20 Hz)────────┤ MemoryReader │──┐
 │   JS objects (zombies…)   │                      └──────────────┘  │ state
 │   canvas                  │◄─Page.captureScreenshot┌───────────┐   ├──► Planner ──► Typist
 │                           │   (thread, 1–3 Hz)    │ OcrWorker │───┘    (pure)      │
 └───────────────────────────┘                       │ + Vision  │                    │
            ▲                                        └───────────┘                    │
            └──────────── Input.dispatchKeyEvent ─────────────────────────────────────┘
```

## Modules (all in `zombie_bot.py`)
| Piece | Role |
|---|---|
| `CDP` | Minimal synchronous DevTools client (websocket-client). |
| `MemoryReader` | Runs the profile's JS probe (`probes/*.js`) in the game frame; returns normalized state. |
| `OcrReader` / `OcrWorker` | Screenshot of the canvas → `VNRecognizeTextRequest` → `parse_ocr_items` maps each word to row (nearest `rows_y + word_offset_y`), side (left/right of `center_x`), distance to fence. Runs on its own thread + CDP connection so typing never waits. |
| `SpeedTracker` | Estimates zombie speed (px/s) from successive distances when the source doesn't give it. |
| Planner functions | `edf_order`, `choose_target`, `choose_cps`, `movement_keys`, `choose_powerup`, `killable`. |
| `Typist` | Sends keys through CDP (`keyDown` with text for letters, `rawKeyDown` for arrows). |
| `Bot` | Tracks its own letters-sent count per target (`_next_index`) because the game's `typed` can lag behind a key sent during a screenshot; falls back to the game's count after 0.3 s. Loop: read → plan → act, dead-reckons the player in OCR-only mode, reconnects if the tab drops, writes CSV log and a JSON summary (CPU %, peak RSS). |

## Normalized state (probe contract)
```json
{"ok": true, "over": false, "rows": 5,
 "player": {"row": 2, "facing": "R"}, "powerup": null,
 "zombies": [{"id": 7, "word": "dangerous", "typed": 3, "row": 0, "side": "L",
              "dist": 212.5, "speed": 68.0}]}
```
`dist` = pixels left before the zombie reaches the fence; `speed` in px/s (0 when frozen).

## Math
- time-to-fence `ttf = dist / speed`
- moves = |row − player.row| + (1 if side ≠ facing)
- **Danger order** (`danger_key`): (1) zombies already chopping the logs, (2) smallest time-to-logs, (3) fewest moves, (4) shortest word. A chopping zombie gets a 0.75 s grace deadline (`CHOP_GRACE`) for speed math and is always killable.
- **Game lock** (`game_lock`): a word already started in Tommy's row and side is where letters go, so it is the current target regardless of what the bot planned.
- **Target**: most dangerous first, tie-break fewest moves then fewest chars. Skip zombies that can't be killed even at max speed (`moves·key_time + chars/max_cps ≥ ttf`) unless none can. Keep the current target unless switching saves more zombies (`switch_pays_off`). Switching away from the row or side resets the current word (confirmed rule), so the cost compares *finish current, then other* with *other now, then current from scratch*. With no current target, lock onto a zombie in Tommy's lane that the game already shows progress on.
- **Speed**: required cps over the first 3 EDF targets = max_k (Σchars_k / (ttf_k − Σmoves_k·key_time − 0.25 s)); typing cps = clamp(1.15 × required, base 140 WPM, max 220 WPM). 1 WPM = 5 chars/min.
- **Jitter**: each key delay = (1/cps) × U(0.7, 1.3).
- **Power-ups**: Bomb if ≥ 3 zombies have ttf < 3 s or any is doomed; Book if ≥ 2 in Tommy's row (or a doomed one is); Ice if any is doomed.

## Mixing memory and OCR
| Mode | Source of truth | OCR use |
|---|---|---|
| `mixed` (default) | memory | 1 Hz cross-check (`ocr_agreement`). If a read fails: last game data moved forward for ≤ `--mem-hold` 1 s (`memory-held`), then OCR with each word snapped to the most similar game-data word in the same row/side (difflib ≥ 0.7) and game-data zombies OCR can't see kept, for ≤ `--mem-carry` 2 s (`ocr+memory`), then raw OCR |
| `memory` | memory | off |
| `ocr` | OCR at 3 Hz | positions are advanced by `speed × age`; player row/facing dead-reckoned from the keys sent; just-typed words are ignored for 0.3 s after their OCR frame |

## Game profile (`profiles/*.json`)
Tab URL match, optional frame match, probe file, canvas selector, game size, `rows_y`, `word_offset_y`, `row_tol`, `center_x`, `fence_x`, default speed, start row/facing. `profiles/tommyq.json` has placeholders and `needs_recon: true` until recon fills it.
