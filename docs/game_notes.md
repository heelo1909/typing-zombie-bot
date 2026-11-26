# Game notes: Tommy Q: Zombie Defender

Status: **web research + rules confirmed by the user (2026-11-26); the game's code has not been inspected yet.** It will be filled in from `recon.py` output at the user's home desktop (Claude in Chrome connected).

## Confirmed by the user (2026-11-26)
- **5 rows.** Zombies spawn in any of the 5 rows, from either the left or the right.
- Tommy can point left or right (and move between rows).
- **A typo does nothing:** no penalty and no reset; keep typing the rest of the word.
- **Leaving the row or turning to the other side resets the partly typed word**, and those letters are lost.

## Known from research (2026-11-26)
- URL: `https://www.typing.com/student/game/tommyq`
- Zombies approach along grass rows from both left and right; Tommy is inside a wooden fence.
- Up/Down arrows move between rows; Left/Right arrows turn to face a side.
- Type the whole word floating above a zombie to shoot it; must be in its row and facing it.
- Enter uses a power-up: Book (clears current row), Ice (freezes all 10 s), Bomb (kills all).
- Word sets: Easy words, Hard words, Top row, Home row, Bottom row. Zombie pace: easy / medium / hard. Target = Hard words + hard pace.
- Game ends when zombies chop through the fence. Levels go at least to 4.

Sources: EPCC typing guide, Homeschool Superfreak review, typinggams fan page (search snippet), YouTube titles ("typing.com/Tommy Q Part 1/2", "Level 1 through 4", "Let's Play").

## To fill in from recon
- [ ] Render tech (2D canvas / WebGL / engine name + version), iframe or not, cross-origin?
- [ ] Where zombie objects live (JS path), fields for word / typed / x / row / side
- [x] Row count: 5 (confirmed). Still need y-coordinates and word label offset
- [ ] Fence x for each side; Tommy's center x
- [ ] Zombie speed (px/s) and spawn interval on hard pace; does it rise per level?
- [x] Typo effect: ignored, no penalty (confirmed)
- [x] A partial word does NOT survive leaving the row/side: it resets (confirmed)
- [ ] Does typing lock onto one zombie when two share a row and side?
- [ ] Power-up pickup and display (how to read which one is held)
- [ ] Fence HP and game-over detection
- [ ] Start/restart flow (menus to click, settings to pick)
