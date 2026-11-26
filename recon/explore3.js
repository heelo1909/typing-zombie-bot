(function(){
  var pool = Phaser.Display.Canvas.Pool.pool, game = null;
  for (var i = 0; i < pool.length && !game; i++){ var p = pool[i].parent; if (p && p.scene) game = p.scene.sys.game; }
  var gs = game.scene.getScene('gameScene');
  function wpos(o){ if (!o) return null; var m = o.getWorldTransformMatrix ? o.getWorldTransformMatrix() : null; return {x: o.x, y: o.y, wx: m ? Math.round(m.tx) : null, wy: m ? Math.round(m.ty) : null}; }
  var out = {
    zombies: gs.typableObjects.map(function(o){ var c = o.objectContainer;
      return {word: o.word, name: o.name, hi: o.highlightIndex, lane: o.laneNumber, dir: o.direction, state: o.state, frozen: o.frozen,
              c: wpos(c), zombieSprite: o.zombie ? wpos(o.zombie) : null, wordText: o.wordText ? (o.wordText.text || '').slice(0, 80) : null,
              speed: o.speed, vel: o.body ? o.body.velocity : undefined, keys: Object.keys(o).filter(function(k){ return typeof o[k] !== 'object' && typeof o[k] !== 'function'; })}; }),
    player: {lane: gs.player.currentLane, dir: gs.player.direction, c: wpos(gs.player.playerContainer), keys: Object.keys(gs.player)},
    leftLog: {img: wpos(gs.leftLog.logImage), health: gs.leftLog.health, attackers: gs.leftLog.attackers, keys: Object.keys(gs.leftLog)},
    rightLog: {img: wpos(gs.rightLog.logImage), health: gs.rightLog.health, attackers: gs.rightLog.attackers},
    spawner: Object.keys(gs.zombieSpawner).filter(function(k){ return typeof gs.zombieSpawner[k] !== 'function'; }).map(function(k){ var v = gs.zombieSpawner[k]; return k + '=' + (typeof v === 'object' ? (v && v.constructor ? v.constructor.name : v) : v); }),
    protoZ: Object.getOwnPropertyNames(Object.getPrototypeOf(gs.typableObjects[0])),
    protoP: Object.getOwnPropertyNames(Object.getPrototypeOf(gs.player)),
    protoScene: Object.getOwnPropertyNames(Object.getPrototypeOf(gs)).slice(0, 80)
  };
  return out;
})()
