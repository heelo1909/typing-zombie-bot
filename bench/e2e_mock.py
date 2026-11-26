#!/usr/bin/env python3
"""End-to-end benchmark: run zombie_bot.py against the local mock in Chrome and
measure kill ratio, bot CPU % and RSS (sampled with psutil every second).

Needs Chrome on --port (e.g. HEADLESS=1 PORT=9333 ./launch_chrome.sh about:blank).
  .venv/bin/python bench/e2e_mock.py --port 9333 --seconds 60 --mode mixed
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request

import psutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from zombie_bot import CDP, list_targets  # noqa: E402


def mock_page(port, url):
    t = next((t for t in list_targets(port) if t.get("type") == "page"
              and "tommyq_mock.html" in t.get("url", "")), None)
    if t is None:
        req = urllib.request.Request("http://127.0.0.1:%d/json/new?%s" % (port, url), method="PUT")
        t = json.loads(urllib.request.urlopen(req, timeout=5).read().decode())
        time.sleep(1)
    cdp = CDP(t["webSocketDebuggerUrl"])
    cdp.call("Page.bringToFront")  # background tabs pause the game loop
    cdp.call("Page.navigate", url=url)
    time.sleep(1.0)
    return cdp


def stats(cdp):
    r = cdp.call("Runtime.evaluate", returnByValue=True,
                 expression="(function(){var g; for (var i = 0; i < 50 && !g; i++) g = window.game;"
                 "return {s: g.stats, hp: g.hp, over: g.over, level: g.level,"
                 "at_fence: g.zombies.filter(function(z){return z.alive && z.atFence}).length}})()")
    return r["result"]["value"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=9333)
    ap.add_argument("--seconds", type=float, default=60)
    ap.add_argument("--mode", default="mixed")
    ap.add_argument("--pace", default="hard")
    ap.add_argument("--typo", default="ignore", help="real game: ignore")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--hp", type=int, default=1000, help="high HP so the run lasts --seconds")
    ap.add_argument("--flaky", type=float, default=0.0, help="chance a game-data read fails")
    ap.add_argument("--lag", type=int, default=0, help="ms the mock waits before handling each key")
    ap.add_argument("--extra", default="", help="extra args for zombie_bot.py")
    ap.add_argument("--out", default=os.path.join(ROOT, "bench", "e2e_result.json"))
    a = ap.parse_args()

    url = "file://%s/mock/tommyq_mock.html?seed=%d&pace=%s&typo=%s&hp=%d&flaky=%s" % (
        ROOT, a.seed, a.pace, a.typo, a.hp, a.flaky)
    url += "&lag=%d" % a.lag
    if a.mode == "ocr":  # no game data to see the start screen, so auto-start
        url += "&autostart=1"
    cdp = mock_page(a.port, url)
    cmd = [sys.executable, os.path.join(ROOT, "zombie_bot.py"), "--profile",
           os.path.join(ROOT, "profiles", "mock.json"), "--port", str(a.port),
           "--mode", a.mode, "--seconds", str(a.seconds), "--seed", "1",
           "--log", os.path.join(ROOT, "bench", "run_log.csv")] + a.extra.split()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    ps = psutil.Process(proc.pid)
    ps.cpu_percent(None)
    cpu, rss = [], []
    while proc.poll() is None:
        time.sleep(1.0)
        try:
            cpu.append(ps.cpu_percent(None))
            rss.append(ps.memory_info().rss / 2**20)
        except psutil.NoSuchProcess:
            break
    out = proc.communicate()[0]
    cdp.close()  # the idle connection may have been dropped; use a fresh one
    t = next(t for t in list_targets(a.port) if "tommyq_mock.html" in t.get("url", ""))
    st = stats(CDP(t["webSocketDebuggerUrl"]))
    s = st["s"]
    resolved = s["kills"] + s["fence_hits"]
    res = {
        "mode": a.mode, "pace": a.pace, "typo": a.typo, "seconds": a.seconds,
        "spawned": s["spawned"], "kills": s["kills"], "fence_hits": s["fence_hits"],
        "kill_ratio": round(s["kills"] / resolved, 3) if resolved else None,
        # zombies stopped before reaching the logs, out of all that were killed or reached them
        "stopped_before_logs": round((s["kills"] - s.get("kills_at_fence", 0)) /
                                     max(1, s["kills"] + st.get("at_fence", 0)), 3),
        "hp_lost_to_chopping": s.get("chops", 0), "flaky": a.flaky,
        "avg_zombie_life_s": round(s.get("life_sum", 0) / max(1, s["kills"]), 2),
        "misses": s["misses"], "resets": s.get("resets"), "keys": s["keys"], "powerups": s["powerups"], "level": st["level"],
        "bot_cpu_avg": round(sum(cpu[1:]) / max(1, len(cpu) - 1), 1) if cpu else None,
        "bot_cpu_max": round(max(cpu), 1) if cpu else None,
        "bot_rss_max_mb": round(max(rss), 1) if rss else None,
    }
    print(out[-800:])
    print(json.dumps(res, indent=2))
    with open(a.out, "w") as f:
        json.dump(res, f, indent=2)


if __name__ == "__main__":
    main()
