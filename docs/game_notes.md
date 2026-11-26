# Game notes: Tommy Q: Zombie Defender

Status: **web research only; the live game has not been inspected yet.** It will be filled in from `recon.py` output at the user's home desktop (Claude in Chrome connected).

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
- [ ] Row count and y-coordinates; word label offset from row
- [ ] Fence x for each side; Tommy's center x
- [ ] Zombie speed (px/s) and spawn interval on hard pace; does it rise per level?
- [ ] Typo effect (ignored / resets word / penalty)
- [ ] Does typing lock onto one zombie? Does a partial word survive switching rows?
- [ ] Power-up pickup and display (how to read which one is held)
- [ ] Fence HP and game-over detection
- [ ] Start/restart flow (menus to click, settings to pick)
