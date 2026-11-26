(function(){
  function prims(o, max){ var out = {}; if (!o) return out; var n = 0;
    for (var k in o){ if (n > (max||80)) break; var v; try { v = o[k]; } catch(e){ continue; }
      var t = typeof v;
      if (t === 'number' || t === 'string' || t === 'boolean'){ out[k] = (t === 'string' && v.length > 40) ? v.slice(0,40) : v; n++; }
      else if (v && t === 'object'){ out[k] = Array.isArray(v) ? '[array ' + v.length + ']' : '{' + (v.constructor && v.constructor.name || 'obj') + (v.type ? ':' + v.type : '') + '}'; n++; }
    } return out; }
  var pool = Phaser.Display.Canvas.Pool.pool, game = null, sample = null;
  for (var i = 0; i < pool.length; i++){ var p = pool[i].parent; if (p && p.scene){ game = p.scene.sys.game; } if (p && p.parentContainer && !sample) sample = p; }
  if (!game) return {err: 'no game'};
  var out = {scenes: game.scene.scenes.map(function(s){ return {key: s.sys.settings.key, active: s.sys.settings.active, visible: s.sys.settings.visible,
                 children: s.sys.displayList ? s.sys.displayList.list.length : null, own: Object.keys(s).filter(function(k){ return !/^(sys|game|anims|cache|registry|sound|textures|events|cameras|add|make|scene|children|data|input|load|time|tweens|lights|physics|matter|impact|plugins)$/.test(k); }).slice(0,60)}; })};
  if (sample){
    var c = sample.parentContainer;
    out.sampleText = prims(sample, 40);
    out.container = prims(c, 120);
    out.containerChildren = c.list.map(function(ch){ return {type: ch.type, name: ch.name, x: ch.x, y: ch.y, text: ch.text, texture: ch.texture && ch.texture.key, frame: ch.frame && ch.frame.name}; });
    var s = sample.scene;
    out.gameScene = s.sys.settings.key;
    out.sceneProps = prims(s, 150);
  }
  return out;
})()
