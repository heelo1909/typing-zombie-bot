// Memory probe for typing.com "Tommy Q: Zombie Defender" (Phaser 3.10.1).
// Built from recon on 2026-11-26 (see docs/game_notes.md). Runs inside the
// page via CDP Runtime.evaluate and returns the bot's normalized state:
//   {ok, over, started, rows, player:{row, facing}, powerup, hp, zombies:[...]}
// Game facts used here (from the game's own code):
//   - typableObjects holds zombies AND power-ups (power-ups are typed to collect)
//   - laneNumber = row(1..5) * side, negative = left side; Tommy's
//     player.laneNumber = currentLane * direction, and letters only reach
//     objects whose laneNumber equals it
//   - zombies walk 0.5 px per frame; they stop and chop at x=370 (left) / x=545 (right)
//   - currentlyTypedObjects = words being typed (filtered to Tommy's lane, as
//     handleInput does); other objects' highlightIndex is not live progress
var g = window.__zbGame;
if (!g || !g.scene) {
  var pool = (window.Phaser && Phaser.Display.Canvas.Pool.pool) || [];
  for (var i = 0; i < pool.length && !g; i++) {
    var p = pool[i].parent;
    if (p && p.scene && p.scene.sys) g = p.scene.sys.game;
  }
  if (!g) return {ok: false, reason: 'phaser game not found'};
  window.__zbGame = g;
}
var gs = g.scene.getScene('gameScene');
if (!gs || !gs.player || !gs.leftLog) return {ok: false, reason: 'game not started'};
var STOP_L = 370, STOP_R = 545;
var fps = (g.loop && g.loop.actualFps) || 60;
var pl = gs.player;
var lane = pl.laneNumber;
var typing = (gs.currentlyTypedObjects || []).filter(function (o) { return o.active && o.laneNumber === lane; });
var hpL = gs.leftLog.health, hpR = gs.rightLog.health;
var held = null;
if (gs.powerUpObject && !gs.powerUpInUse) {
  held = {icePowerUp: 'ice', bombPowerUp: 'bomb', bookPowerUp: 'book'}[gs.powerUpObject.name] || null;
}
var zs = [];
gs.typableObjects.forEach(function (o) {
  if (!o.active || !o.word || o.highlightIndex >= o.word.length) return;
  // stable id per object (list positions shift whenever anything dies)
  if (!o.__zbId) o.__zbId = (window.__zbSeq = (window.__zbSeq || 0) + 1);
  var isZ = o.name === 'zombie';
  if (isZ && o.isAlive && !o.isAlive()) return;
  var side = o.laneNumber < 0 ? 'L' : 'R';
  var x = o.objectContainer.x;
  var chopping = isZ && o.state !== undefined && o.isAttacking ? (o.isAttacking() || (o.frozen && (side === 'L' ? x >= STOP_L : x <= STOP_R))) : false;
  zs.push({
    id: (isZ ? 'z' : 'p') + o.__zbId,
    kind: isZ ? 'zombie' : 'powerup',
    powerup: isZ ? null : ({icePowerUp: 'ice', bombPowerUp: 'bomb', bookPowerUp: 'book'}[o.name] || o.name),
    word: o.word,
    typed: typing.indexOf(o) >= 0 ? o.highlightIndex : 0,
    row: Math.abs(o.laneNumber) - 1,
    side: side,
    x: Math.round(x),
    dist: isZ ? Math.max(0, side === 'L' ? STOP_L - x : x - STOP_R) : 1e6,
    speed: isZ ? (o.frozen ? 0 : 0.5 * fps) : 0,
    frozen: !!o.frozen,
    chopping: chopping
  });
});
return {
  ok: true,
  started: gs.playing ? true : null,   // null: don't press Enter on the real menus
  over: !gs.playing && (hpL <= 0 || hpR <= 0),
  rows: 5,
  player: {row: pl.currentLane - 1, facing: pl.direction < 0 ? 'L' : 'R'},
  powerup: held,
  hp: Math.min(hpL, hpR), hpL: hpL, hpR: hpR,
  level: gs.level, kills: gs.killCount, fps: Math.round(fps),
  zombies: zs
};
