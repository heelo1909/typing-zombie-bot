#!/usr/bin/env python3
"""Recon for the live Tommy Q game: find out how it renders and where its state lives.

Run with the game open (and ideally being played) in Chrome started by
launch_chrome.sh. Writes recon/report.json and recon/shot.png.

  ./recon.py [--match typing.com] [--seconds 6]
"""
import argparse
import base64
import json
import os
import time

from zombie_bot import CDP, CDPError, list_targets, HERE

DISCOVER_JS = r"""
(function(){
  var out = {url: location.href, title: document.title, engines: {}, canvases: [], iframes: [], globals: []};
  var probes = {Phaser:'Phaser', PIXI:'PIXI', createjs:'createjs', C3:'C3', cr:'cr',
                Unity:'unityInstance', UnityLoader:'UnityLoader', Laya:'Laya', cc:'cc',
                BABYLON:'BABYLON', THREE:'THREE', Konva:'Konva', fabric:'fabric', game:'game'};
  for (var k in probes) { try { if (window[probes[k]]) out.engines[k] = typeof window[probes[k]]; } catch(e){} }
  try { if (window.Phaser) out.engines.PhaserVersion = Phaser.VERSION; } catch(e){}
  try { if (window.PIXI) out.engines.PIXIVersion = PIXI.VERSION; } catch(e){}
  document.querySelectorAll('canvas').forEach(function(c){
    var b = c.getBoundingClientRect(), ctx = null;
    try { ctx = c.getContext('2d') ? '2d' : null; } catch(e){}
    out.canvases.push({id:c.id, cls:c.className, w:c.width, h:c.height,
                       rect:[b.left,b.top,b.width,b.height], ctx: ctx});
  });
  document.querySelectorAll('iframe').forEach(function(f){
    var b = f.getBoundingClientRect();
    out.iframes.push({src:f.src, id:f.id, rect:[b.left,b.top,b.width,b.height]});
  });
  var std = new Set(Object.getOwnPropertyNames(document.createElement('iframe').contentWindow || {}));
  Object.getOwnPropertyNames(window).forEach(function(n){
    if (!std.has(n) && !/^(on|webkit)/.test(n)) out.globals.push(n);
  });
  out.globals = out.globals.slice(0, 300);
  return out;
})()
"""

# Hook 2D-canvas text drawing: every word the game paints, with its position.
HOOK_JS = r"""
(function(){
  if (window.__zb_hook) return 'already';
  var P = CanvasRenderingContext2D.prototype, orig = P.fillText, origS = P.strokeText;
  window.__zb_text = [];
  function rec(kind){ return function(t, x, y){
    try {
      var m = this.getTransform();
      if (window.__zb_text.length < 5000)
        window.__zb_text.push({k:kind, t:String(t), x:m.a*x+m.c*y+m.e, y:m.b*x+m.d*y+m.f,
          cw:this.canvas.width, ch:this.canvas.height, onscreen: document.contains(this.canvas),
          ts: performance.now()});
    } catch(e){}
    return (kind === 'f' ? orig : origS).apply(this, arguments);
  };}
  P.fillText = rec('f'); P.strokeText = rec('s'); window.__zb_hook = true; return 'hooked';
})()
"""

# Bounded scan of JS objects for things that look like zombies: a short
# alphabetic string property next to numeric x / y properties.
SCAN_JS = r"""
(function(){
  var seen = new WeakSet(), hits = [], nodes = 0, MAX = 60000;
  function scan(o, path, depth){
    if (!o || typeof o !== 'object' || seen.has(o) || depth > 7 || nodes > MAX) return;
    seen.add(o); nodes++;
    var keys; try { keys = Object.keys(o); } catch(e){ return; }
    if (keys.length > 400) keys = keys.slice(0, 400);
    var str = null, num = {};
    for (var i = 0; i < keys.length; i++){
      var k = keys[i], v; try { v = o[k]; } catch(e){ continue; }
      if (typeof v === 'string' && /^[A-Za-z'-]{2,20}$/.test(v) && /text|word|label|name|str/i.test(k)) str = [k, v];
      if (typeof v === 'number' && /^(x|y|row|lane|speed|vx|typed|index|_x|_y)$/i.test(k)) num[k] = v;
    }
    if (str && ('x' in num || 'y' in num || 'row' in num || 'lane' in num)) hits.push({path:path, key:str[0], value:str[1], nums:num});
    for (var j = 0; j < keys.length; j++){
      var kk = keys[j], vv; try { vv = o[kk]; } catch(e){ continue; }
      if (vv && typeof vv === 'object' && !(vv instanceof Node) && !(vv instanceof Window)) scan(vv, path + '.' + kk, depth + 1);
    }
  }
  var roots = %ROOTS%;
  roots.forEach(function(r){ try { scan(window[r], r, 0); } catch(e){} });
  return {nodes: nodes, hits: hits.slice(0, 300)};
})()
"""


def evaluate(cdp, expr):
    r = cdp.call("Runtime.evaluate", expression=expr, returnByValue=True)
    if "exceptionDetails" in r:
        return {"error": r["exceptionDetails"].get("text")}
    return r["result"].get("value")


def recon_target(t, seconds, outdir, idx):
    cdp = CDP(t["webSocketDebuggerUrl"])
    rep = {"target": {k: t.get(k) for k in ("type", "url", "title")}}
    rep["discover"] = evaluate(cdp, DISCOVER_JS)
    rep["hook"] = evaluate(cdp, HOOK_JS)
    roots = [g for g in (rep["discover"] or {}).get("globals", [])][:80] or ["game"]
    samples = []
    t_end = time.time() + seconds
    while time.time() < t_end:
        time.sleep(1.0)
        scan = evaluate(cdp, SCAN_JS.replace("%ROOTS%", json.dumps(roots)))
        texts = evaluate(cdp, "(function(){var a=window.__zb_text||[];window.__zb_text=[];return a.slice(-400)})()")
        samples.append({"t": time.time(), "scan": scan, "drawn_text": texts})
    rep["samples"] = samples
    if t.get("type") == "page":
        try:
            shot = cdp.call("Page.captureScreenshot", format="png")
            with open(os.path.join(outdir, "shot%d.png" % idx), "wb") as f:
                f.write(base64.b64decode(shot["data"]))
            rep["screenshot"] = "shot%d.png" % idx
        except CDPError as e:
            rep["screenshot_error"] = str(e)
    cdp.close()
    return rep


def summarize(reports):
    """Short human summary: which strings moved (likely zombie words)."""
    lines = []
    for r in reports:
        d = r.get("discover") or {}
        lines.append("== %s %s" % (r["target"]["type"], r["target"]["url"]))
        lines.append("   engines=%s canvases=%s iframes=%d" % (
            d.get("engines"), [(c["w"], c["h"], c["ctx"]) for c in d.get("canvases", [])],
            len(d.get("iframes", []))))
        words = {}
        for s in r.get("samples", []):
            for tx in (s.get("drawn_text") or []):
                if isinstance(tx, dict):
                    words.setdefault(tx["t"], []).append((round(tx["x"]), round(tx["y"])))
        moving = {w: p for w, p in words.items() if len(set(p)) > 2}
        ys = sorted({round(p[-1][1]) for p in moving.values()})
        lines.append("   drawn strings=%d moving=%d  example moving=%s" % (
            len(words), len(moving), list(moving)[:8]))
        lines.append("   moving text y values (row candidates)=%s" % ys[:20])
        hits = sum(len((s.get("scan") or {}).get("hits", [])) for s in r.get("samples", []))
        lines.append("   object-scan hits=%d" % hits)
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--match", default="typing.com")
    ap.add_argument("--seconds", type=float, default=6)
    ap.add_argument("--out", default=os.path.join(HERE, "recon"))
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    targets = [t for t in list_targets(a.port)
               if t.get("type") in ("page", "iframe") and a.match in t.get("url", "")]
    if not targets:
        raise SystemExit("no tab/iframe whose URL contains %r" % a.match)
    reports = [recon_target(t, a.seconds, a.out, i) for i, t in enumerate(targets)]
    with open(os.path.join(a.out, "report.json"), "w") as f:
        json.dump(reports, f, indent=1)
    s = summarize(reports)
    with open(os.path.join(a.out, "summary.txt"), "w") as f:
        f.write(s + "\n")
    print(s)
    print("\nfull report: %s" % os.path.join(a.out, "report.json"))


if __name__ == "__main__":
    main()
