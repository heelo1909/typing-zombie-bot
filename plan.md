# plan.md: next steps (read this first after a context clear)

Full approved plan: `docs/spec.md` (what/why), `docs/design.md` (how). Progress log: `progress.md`.

## Where we are
Recon is done and the real-game probe/profile are in place (see `docs/game_notes.md`). **Next: first live run on the real game.**

## Next steps
1. User: in the bot's Chrome window (`./launch_chrome.sh`), pick Hard and click PLAY; keep the tab in front.
2. Run `.venv/bin/python zombie_bot.py --log bench/real_run.csv`. It waits on menus and after game over.
3. Check the summary + log: kills, logs' health, CPU ≤ 20 %, RSS < 2 GB. Pass = ≥ 90 % of zombies killed before the logs on Hard.
4. If short: tune `--wpm/--max-wpm`, `PICKUP_MARGIN`, power-up rules; check `ocr_agreement` on the real font.
5. Find the spawn-delay table per difficulty (still unknown) and whether power-up words expire.
6. Update `progress.md`, this file, commit + push.

## Confirmed (user, 2026-11-26)
5 rows, both sides, typo = no effect, leaving row/side resets the partly typed word. The mock and planner already follow these rules.

Also confirmed: letters go to the word you start typing; a label behind another zombie can be covered on screen. User priority: closest to the logs / most dangerous first; game data outranks OCR (already implemented).

Also confirmed: a zombie at the logs stays there chopping until killed (mock default `chop=1`).

## Known open questions
- In recon, find how the game marks a chopping zombie so `probes/tommyq.js` can set `chopping: true` (otherwise `dist <= 0` is used).
- Power-up indicator location (for the probe or OCR).
