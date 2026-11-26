// Memory probe for mock/tommyq_mock.html. Runs inside the game frame via CDP
// Runtime.evaluate and returns the normalized state the bot expects.
var g = window.game;
if (!g) return {ok: false};
return {
  ok: true, over: !!g.over, started: !!g.started, rows: g.rows.length,
  player: {row: g.player.row, facing: g.player.facing},
  powerup: g.powerup || null,
  hp: g.hp, stats: g.stats,
  zombies: g.zombies.filter(function (z) { return z.alive; }).map(function (z) {
    return {id: z.id, word: z.word, typed: z.typed, row: z.row, side: z.side,
            dist: Math.max(0, z.side === 'L' ? g.fenceL - z.x : z.x - g.fenceR),
            speed: g.frozen > 0 ? 0 : z.speed, chopping: !!z.atFence};
  })
};
