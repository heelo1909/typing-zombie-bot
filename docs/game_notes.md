# Game notes: Tommy Q: Zombie Defender

Status: **recon done on the live game (2026-11-26)**, using `recon.py` plus read-only inspection of the game's own objects and code over CDP. Raw dumps: `recon/explore*.json`, `recon/source*.json`, `recon/samples_live.json`.

## Tech
- URL `https://www.typing.com/student/game/tommyq`. **Phaser 3.10.1**, runs in the page itself (no game iframe; the iframes are ads).
- WebGL canvas 916×400 CSS px (the first `<canvas>` on the page). Retina: devicePixelRatio 2.
- No global game variable. Found via `Phaser.Display.Canvas.Pool.pool[i].parent.scene.sys.game`; the probe caches it as `window.__zbGame`.
- Scenes: `bootScene`, `preloaderScene`, `menuScene` (menus), `gameScene` (play).

## gameScene fields used by `probes/tommyq.js`
| field | meaning |
|---|---|
| `playing` | true during a round |
| `typableObjects[]` | every word on screen: zombies (`name: "zombie"`) **and power-ups** (`icePowerUp`, `bombPowerUp`, `bookPowerUp`) |
| `currentlyTypedObjects[]` | words receiving letters right now |
| `player.currentLane` (1–5), `player.direction` (−1 left / 1 right), `player.laneNumber` = lane × direction | Tommy |
| `leftLog.health`, `rightLog.health` (start 100), `.attackers` | the logs |
| `powerUpObject` / `powerUpInUse` | held power-up and whether one is active |
| `level`, `killCount`, `score`, `zombieSpawnDelay` | progress |

Typable object: `word`, `highlightIndex` (letters typed), `laneNumber` (row 1–5 × side, **negative = left**), `direction` (+1 walks right = comes from the left), `state` (walk / attack / dying), `frozen`, `objectContainer.x/y`.

## Rules (from the game's code + the user)
- **Typing** (`handleInput`): letters only reach objects whose `laneNumber` equals Tommy's.
  - The first letter selects **every** word in the lane starting with it.
  - Later letters keep the words whose next letter matches. The others reset.
  - A wrong letter does nothing.
- **Moving:** Up/Down (rows 1–5, no-op at the edges) or turning resets every word in progress.
- **Zombies:** spawn at x −30 (left) or 946 (right), walk **0.5 px per frame** (30 px/s at 60 fps, the same on every difficulty), and stop to **chop at x = 370 (left) / 545 (right)** until killed (confirmed by the user). Each correct letter knocks the zombie back 3 px.
- **Rows:** zombie y = 95 + 60 × lane (155, 215, 275, 335, 395); word label 120 px above. Tommy x = 458; log images at x 440 / 476.
- **Game over** when either log's health ≤ 0.
- **Power-ups:**
  - A power-up spawns as a word in a random lane/side (chance per zombie spawn). Typing the word collects it; **Enter** uses it.
  - Ice: freezes all zombies for 5 s and pauses spawning; typing a letter on a frozen zombie unfreezes it.
  - Bomb: kills the oldest ⌊n/2⌋+1 live zombies.
  - Book ("coffin"): kills every live zombie in Tommy's lane **on the side he faces**.
- **Waves:**
  - Normal waves last 45 s, then a 10 s horde wave with 0.65× spawn delay, then level up (spawn delay × 0.75).
  - The between-wave screens continue by themselves: the horde banner, then a 4 s level-complete countdown.
- **Menus:**
  - The difficulty menu (Easy / Medium / Hard + PLAY) needs a click, as does the game-over menu.
  - Without premium, "Play again" reloads the page.
  - The bot does not click menus. It waits until a round starts.
- A background tab pauses the game (Phaser runs on requestAnimationFrame). Keep the game tab in front.
- Starting spawn delay seen: 2650 ms (difficulty from `registry.difficulty`).

## Still unknown
- Spawn delay per difficulty (table `p[...]` in the code); only 2650 ms has been observed.
- Whether power-up words expire.
