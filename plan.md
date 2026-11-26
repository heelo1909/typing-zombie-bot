# plan.md: next steps (read this first after a context clear)

Full approved plan: `docs/spec.md` (what/why), `docs/design.md` (how). Progress log: `progress.md`.

## Where we paused
Everything that doesn't depend on the real game is built and tested against `mock/tommyq_mock.html`. **The next session must happen on the user's home desktop with the Claude in Chrome extension connected**, because the real game's internals are still unknown.

## Next steps (in order)
1. **Look at the live game** with Claude in Chrome: open `https://www.typing.com/student/game/tommyq`, take screenshots of the menu, settings (pick **Hard words + hard pace**) and gameplay. Confirm controls (Up/Down rows, Left/Right facing, Enter power-up) and note the start flow.
2. **Recon:** `./launch_chrome.sh` → user logs in → open the game and start a hard round → `.venv/bin/python recon.py --match typing.com --seconds 8`. Also try `--match` with the game iframe's host if `recon/summary.txt` shows an iframe.
3. Read `recon/summary.txt` + `recon/report.json`:
   - If `drawn strings` show moving words → it's a 2D canvas: the fillText hook gives word + x/y. Write `probes/tommyq.js` from the hook data, or better, from the object-scan hits (JS path to the zombie list).
   - If engines show Phaser/PIXI/Construct/etc. → walk that engine's scene graph in the probe.
   - If it's an iframe: set `frame_match` (same-origin) or `frame_oopif_match` (cross-origin target) in `profiles/tommyq.json`.
4. Fill `profiles/tommyq.json` geometry (`rows_y`, `word_offset_y`, `center_x`, `fence_x`, `game_w/h`, `default_speed`, `start_row/facing`), set `needs_recon` to false, and update `tests/test_planner.py::test_real_profile_flagged_until_recon` (flip the assertion).
5. Save one probe snapshot as `tests/fixtures/tommyq_state.json` and a screenshot for an OCR accuracy check (target ≥ 90 %).
6. Write `docs/game_notes.md` (tick every checklist item).
7. `--dry-run` on the live game, then live runs on easy, then **hardest**. Log with `--log bench/run_log.csv`. Pass = ≥ 90 % kills before the fence, bot avg CPU ≤ 20 %, RSS < 2 GB. If kills < 90 %: check typo handling, `key_time`, power-up rules, `--max-wpm`; loop.
8. Update `progress.md`, this file, commit + push.

## Known open questions
- Real typo behaviour (the mock supports `typo=ignore|reset`).
- Whether a partly typed word survives moving rows in the real game.
- Power-up indicator location (for the probe or OCR).
