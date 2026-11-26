(function(){
  function prims(o, max){ var out = {}; if (!o) return o; var n = 0;
    for (var k in o){ if (n > (max||90)) break; var v; try { v = o[k]; } catch(e){ continue; }
      if (/^(_events|scene|_sysEvents|_displayList|pipeline|defaultPipeline|localTransform|tempTransformMatrix|canvas|context|canvasTexture|frame|texture|anims|body|data|input|style|padding|splitRegExp)$/.test(k)) continue;
      var t = typeof v;
      if (t === 'number' || t === 'string' || t === 'boolean'){ if (/^_?alpha|^_?scale|^display|^_blend|^blend|^cameraFilter|^renderFlags|^tabIndex|^_?rotation|^angle|^z$|^w$|^origin|^_?depth|^scrollFactor|^_?visible|^ignoreDestroy|^_?tint|^isTinted|^flip|^_crop|^isCropped|^resolution|^autoRound|^dirty/.test(k)) continue;
        out[k] = (t === 'string' && v.length > 40) ? v.slice(0,40) : v; n++; }
      else if (v && t === 'object'){ out[k] = Array.isArray(v) ? '[array ' + v.length + ']' : '{' + (v.constructor && v.constructor.name || 'obj') + (v.type ? ':' + v.type : '') + (v.texture ? ':' + v.texture.key + '/' + (v.frame && v.frame.name) : '') + '}'; n++; }
    } return out; }
  var pool = Phaser.Display.Canvas.Pool.pool, game = null;
  for (var i = 0; i < pool.length && !game; i++){ var p = pool[i].parent; if (p && p.scene) game = p.scene.sys.game; }
  var gs = game.scene.getScene('gameScene'), ms = game.scene.getScene('menuScene');
  var out = {playing: gs.playing, level: gs.level, kills: gs.killCount, inactiveLane: gs.inactiveLane,
             typedNow: gs.currentlyTypedObjects.length, spawnDelay: gs.zombieSpawnDelay,
             canvas: [game.config.width, game.config.height]};
  out.typable = gs.typableObjects.slice(0, 4).map(function(o){ return prims(o, 90); });
  out.typableTypes = gs.typableObjects.map(function(o){ return (o.constructor && o.constructor.name) + ':' + (o.word || o.text || o.name || ''); });
  out.player = prims(gs.player, 90);
  out.leftLog = prims(gs.leftLog, 60); out.rightLog = prims(gs.rightLog, 60);
  out.powerUpObject = prims(gs.powerUpObject, 60);
  out.menus = {difficulty: prims(ms.difficultyMenu, 30), gameOver: prims(ms.gameOverMenu, 30), levelComplete: prims(ms.levelCompleteMenu, 30)};
  return out;
})()
