#!/usr/bin/env python3
"""Auto-typer for typing.com's "Tommy Q: Zombie Defender".

Reads game state two ways and mixes them:
  * memory  - a small JS probe evaluated inside the game frame over the Chrome
              DevTools Protocol (CDP) returns zombies, rows, words, player.
  * ocr     - CDP screenshot of the game canvas -> Apple Vision text recognition
              -> words mapped to rows by y-coordinate (fallback / cross-check).
Keys are sent with CDP Input.dispatchKeyEvent, so no macOS Accessibility or
Screen Recording permission is required.

Chrome must be started with --remote-debugging-port (see launch_chrome.sh).
Usage:  ./tommyq_normal.py     (human-like, 140 WPM)
        ./tommyq_instant.py    (as fast as Chrome accepts keys)
        ./zombie_bot.py --preset normal|instant [--wpm N] [--max-wpm N] [--dry-run]
"""
import argparse
import base64
import csv
import json
import os
import random
import resource
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- #
# CDP client (minimal, synchronous)
# --------------------------------------------------------------------------- #


class CDPError(RuntimeError):
    pass


class CDP:
    def __init__(self, ws_url, timeout=5.0):
        import websocket  # websocket-client
        self.ws = websocket.create_connection(ws_url, timeout=timeout,
                                              suppress_origin=True)
        self._id = 0
        self.events = []

    def call(self, method, **params):
        self._id += 1
        mid = self._id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise CDPError("%s: %s" % (method, msg["error"]))
                return msg.get("result", {})
            if "method" in msg and len(self.events) < 500:
                self.events.append(msg)

    def drain_events(self):
        ev, self.events = self.events, []
        return ev

    def close(self):
        try:
            self.ws.close()
        except Exception:
            pass


def list_targets(port):
    with urllib.request.urlopen("http://127.0.0.1:%d/json/list" % port, timeout=3) as r:
        return json.loads(r.read().decode())


def find_targets(port, page_match, frame_match=None):
    """Return (page_target, frame_target_or_None). frame target is an OOPIF."""
    targets = list_targets(port)
    page = next((t for t in targets if t.get("type") == "page"
                 and page_match in t.get("url", "")), None)
    if page is None:
        raise CDPError("no Chrome tab whose URL contains %r (open the game first)" % page_match)
    frame = None
    if frame_match:
        frame = next((t for t in targets if t.get("type") == "iframe"
                      and frame_match in t.get("url", "")), None)
    return page, frame


# --------------------------------------------------------------------------- #
# Game model + planner (pure functions; unit-tested)
# --------------------------------------------------------------------------- #

INF = float("inf")


def remaining(z):
    return max(0, len(z["word"]) - int(z.get("typed", 0)))


MOVE_TRUST_S = 0.35  # s to trust our own arrow presses over a lagging game read
CHOP_GRACE = 0.75  # s: deadline used for a zombie already chopping the logs


def at_logs(z):
    """Zombie has reached the fence (logs) and is chopping: the most dangerous."""
    return bool(z.get("chopping")) or z["dist"] <= 0


def time_to_fence(z):
    if at_logs(z):
        return 0.0
    sp = z.get("speed") or 0.0
    return z["dist"] / sp if sp > 0 else INF


def deadline(z):
    """Seconds we have to kill z. A chopping zombie damages the logs every
    moment, so it gets a short grace deadline instead of 0."""
    return CHOP_GRACE if at_logs(z) else time_to_fence(z)


def moves(z, player):
    m = abs(z["row"] - player["row"])
    if z["side"] != player["facing"]:
        m += 1
    return m


def danger_key(z, player):
    """Priority: chopping the logs first, then closest to the logs (in time),
    then fewest moves, then shortest word."""
    return (not at_logs(z), time_to_fence(z), moves(z, player), remaining(z))


def is_powerup(z):
    return z.get("kind") == "powerup"


def edf_order(zombies, player):
    """Most dangerous first (see danger_key); finished words and power-up
    pickups dropped (pickups are chosen separately in choose_target)."""
    live = [z for z in zombies if remaining(z) > 0 and not is_powerup(z)]
    return sorted(live, key=lambda z: danger_key(z, player))


def required_cps(queue, player, key_time, margin=0.25, depth=3):
    """Chars/sec needed so the first `depth` zombies in priority order die in time."""
    need, chars, keys, cur = 0.0, 0, 0, dict(player)
    for z in queue[:depth]:
        keys += moves(z, cur)
        cur = {"row": z["row"], "facing": z["side"]}
        chars += remaining(z)
        avail = deadline(z) - keys * key_time - margin
        if avail == INF:
            continue
        need = max(need, chars / max(avail, 0.05))
    return need


def choose_cps(queue, player, base_cps, max_cps, key_time):
    need = required_cps(queue, player, key_time) * 1.15
    return min(max_cps, max(base_cps, need))


def killable(z, player, cps, key_time):
    if at_logs(z):  # it stays at the logs, so it can always still be killed
        return True
    return moves(z, player) * key_time + remaining(z) / cps < time_to_fence(z)


def switch_pays_off(cur, other, player, cps, key_time):
    """Leaving cur's row/side resets its typed letters (confirmed game rule).
    Compare 'finish cur, then other' with 'other now, then cur from scratch'
    and switch only if it saves more zombies."""
    t_cur = moves(cur, player) * key_time + remaining(cur) / cps
    after_cur = {"row": cur["row"], "facing": cur["side"]}
    a_other = t_cur + moves(other, after_cur) * key_time + remaining(other) / cps < deadline(other)
    a_saved = 1 + a_other  # cur itself is assumed saved when finished first
    t_other = moves(other, player) * key_time + remaining(other) / cps
    after_other = {"row": other["row"], "facing": other["side"]}
    resets = moves(other, player) > 0
    cur_left = len(cur["word"]) if resets else remaining(cur)
    b_other = t_other < deadline(other)
    b_cur = t_other + moves(cur, after_other) * key_time + cur_left / cps < deadline(cur)
    return b_other + b_cur > a_saved


def game_lock(zombies, player):
    """The zombie the game is sending letters to: letters go to the word you
    started typing, in Tommy's current row and facing side."""
    return next((z for z in zombies if z.get("typed", 0) > 0 and remaining(z) > 0
                 and z["row"] == player["row"] and z["side"] == player["facing"]), None)


def choose_target(zombies, player, current_id, max_cps, key_time, holding=False):
    """The game's lock (a word already started in Tommy's lane) wins: letters
    go there. It's only abandoned when switching saves more zombies, since
    leaving the lane resets it. Otherwise: most dangerous first (chopping the
    logs, then closest to the logs), skipping walkers that can't be reached in
    time even at max speed (unless none can).
    holding: a power-up is already held. Collecting another would destroy it
    (real game rule), so power-up words are ignored then."""
    queue = edf_order(zombies, player)
    pickup = [] if holding else [z for z in zombies if is_powerup(z) and remaining(z) > 0]
    lock = game_lock(zombies, player)
    if lock is not None and is_powerup(lock) and not holding:
        return lock  # already typing a power-up word: finish it
    if not queue:
        return pickup_if_safe(pickup, queue, player, max_cps, key_time) if pickup else None
    cur = game_lock(queue, player)
    if cur is None:
        cur = next((z for z in queue if z["id"] == current_id), None)
    if cur is not None:
        for o in queue:
            if o["id"] == cur["id"] or danger_key(o, player)[:2] >= danger_key(cur, player)[:2]:
                continue
            if killable(o, player, max_cps, key_time) and switch_pays_off(cur, o, player, max_cps, key_time):
                return o
        return cur
    p = pickup_if_safe(pickup, queue, player, max_cps, key_time)
    if p is not None:
        return p
    for z in queue:
        if killable(z, player, max_cps, key_time):
            return z
    return queue[0]


PICKUP_MARGIN = 1.5  # s of spare time the most urgent zombie must still have


def pickup_if_safe(pickups, queue, player, cps, key_time, held=None):
    """Collect a power-up (type its word) only when the most dangerous zombie
    can still be killed with PICKUP_MARGIN s to spare afterwards."""
    if not pickups:
        return None
    p = min(pickups, key=lambda z: (moves(z, player), remaining(z)))
    t_p = moves(p, player) * key_time + remaining(p) / cps
    after = {"row": p["row"], "facing": p["side"]}
    for z in queue[:2]:
        t = t_p + moves(z, after) * key_time + remaining(z) / cps
        if at_logs(z) or t + PICKUP_MARGIN >= deadline(z):
            return None
        t_p, after = t, {"row": z["row"], "facing": z["side"]}
    return p


def movement_keys(z, player):
    keys = []
    d = z["row"] - player["row"]
    keys += ["ArrowDown"] * d if d > 0 else ["ArrowUp"] * (-d)
    if z["side"] != player["facing"]:
        keys.append("ArrowLeft" if z["side"] == "L" else "ArrowRight")
    return keys


def choose_powerup(state, player, cps, key_time):
    """Return True if Enter (use power-up) should be pressed now."""
    p = state.get("powerup")
    if not p:
        return False
    zs = [z for z in state["zombies"] if remaining(z) > 0 and not is_powerup(z)]
    if not zs:
        return False
    doomed = [z for z in zs if not killable(z, player, cps, key_time)]
    # overloaded: even at max speed the next few zombies can't all be killed in time
    overloaded = required_cps(edf_order(zs, player), player, key_time) > cps
    if p == "bomb":
        near = [z for z in zs if deadline(z) < 3.0]
        return len(near) >= 3 or bool(doomed) or (overloaded and len(zs) >= 3)
    if p == "book":  # kills every zombie in Tommy's row on the side he faces
        lane = [z for z in zs if z["row"] == player["row"] and z["side"] == player["facing"]]
        return len(lane) >= 2 or any(at_logs(z) for z in lane) or any(z in doomed for z in lane) \
            or (overloaded and len(lane) >= 1)
    if p == "ice":
        return bool(doomed) or sum(1 for z in zs if at_logs(z)) >= 2 or overloaded
    return bool(doomed) or overloaded


def key_delay(cps, rng, jitter=0.3):
    base = 1.0 / cps
    return base * (1.0 + rng.uniform(-jitter, jitter))


def wpm_to_cps(wpm):
    return wpm * 5.0 / 60.0


# --------------------------------------------------------------------------- #
# Speed tracker (fills z["speed"] when the source doesn't provide it)
# --------------------------------------------------------------------------- #


class SpeedTracker:
    def __init__(self, default_speed):
        self.default = default_speed
        self.last = {}  # id -> (t, dist, speed)

    def update(self, zombies, t):
        seen = {}
        for z in zombies:
            prev = self.last.get(z["id"])
            sp = z.get("speed")
            if not sp:
                if prev and t > prev[0] + 0.05 and prev[1] > z["dist"]:
                    inst = (prev[1] - z["dist"]) / (t - prev[0])
                    sp = 0.6 * prev[2] + 0.4 * inst if prev[2] else inst
                else:
                    sp = prev[2] if prev else self.default
                z["speed"] = sp
            seen[z["id"]] = (t, z["dist"], z["speed"]) if (not prev or t > prev[0] + 0.05) else (prev[0], prev[1], z["speed"])
        self.last = seen
        return zombies


# --------------------------------------------------------------------------- #
# State readers
# --------------------------------------------------------------------------- #


class MemoryReader:
    """Evaluates the profile's JS probe inside the game frame."""

    def __init__(self, cdp, probe_js, frame_match=None):
        self.cdp = cdp
        self.expr = "(function(){%s})()" % probe_js
        self.ctx = None
        if frame_match:
            self.ctx = self._find_context(frame_match)

    def _find_context(self, frame_match):
        """Default JS context of the (same-process) frame whose URL matches."""
        tree = self.cdp.call("Page.getFrameTree")["frameTree"]
        frame_id, stack = None, [tree]
        while stack and frame_id is None:
            n = stack.pop()
            if frame_match in n["frame"].get("url", ""):
                frame_id = n["frame"]["id"]
            stack += n.get("childFrames", [])
        if frame_id is None:
            raise CDPError("no frame whose URL contains %r" % frame_match)
        self.cdp.call("Runtime.enable")
        time.sleep(0.3)
        ctx = None
        for ev in self.cdp.drain_events():
            if ev["method"] == "Runtime.executionContextCreated":
                aux = ev["params"]["context"].get("auxData", {})
                if aux.get("frameId") == frame_id and aux.get("isDefault"):
                    ctx = ev["params"]["context"]["id"]
        self.cdp.call("Runtime.disable")
        if ctx is None:
            raise CDPError("no JS context for frame %s" % frame_id)
        return ctx

    def read(self):
        kw = {"expression": self.expr, "returnByValue": True}
        if self.ctx:
            kw["contextId"] = self.ctx
        r = self.cdp.call("Runtime.evaluate", **kw)
        if "exceptionDetails" in r:
            raise CDPError("probe error: %s" % r["exceptionDetails"].get("text"))
        v = r["result"].get("value")
        if v and not v.get("ok") and v.get("reason"):
            # the probe ran fine but the game isn't in play (menu, page loading):
            # that's "waiting", not a failed read, so OCR must not take over
            return {"ok": True, "waiting": v["reason"], "zombies": []}
        if not v or not v.get("ok"):
            raise CDPError("probe returned no state")
        return v


def parse_ocr_items(items, rows_y, row_tol, center_x, fence_x, img_w, img_h,
                    min_len=2):
    """items: [(text, (x, y, w, h) normalized, bottom-left origin)] ->
    zombie dicts. Words not near a row band are dropped (HUD text etc.)."""
    zs = []
    for text, (bx, by, bw, bh) in items:
        word = "".join(ch for ch in text.strip() if ch.isalpha() or ch in "'-")
        if len(word) < min_len:
            continue
        cx = (bx + bw / 2.0) * img_w
        cy = (1.0 - (by + bh / 2.0)) * img_h
        row = min(range(len(rows_y)), key=lambda i: abs(rows_y[i] - cy))
        if abs(rows_y[row] - cy) > row_tol:
            continue
        side = "L" if cx < center_x else "R"
        dist = abs(cx - fence_x[side])
        zs.append({"id": "%s:%d:%s" % (word, row, side), "word": word,
                   "typed": 0, "row": row, "side": side, "dist": dist})
    return zs


class OcrReader:
    """CDP screenshot of the game area -> Apple Vision OCR."""

    def __init__(self, cdp, profile, fast=False):
        import Vision  # noqa: F401  (pyobjc)
        self.cdp, self.p, self.fast = cdp, profile, fast

    def _clip(self):
        sel = self.p.get("canvas_selector", "canvas")
        r = self.cdp.call("Runtime.evaluate", returnByValue=True, expression=(
            "(function(){var c=document.querySelector(%s);if(!c)return null;"
            "var b=c.getBoundingClientRect();return {x:b.left+scrollX,y:b.top+scrollY,"
            "w:b.width,h:b.height};})()" % json.dumps(sel)))
        return r["result"].get("value")

    def recognize(self, png_bytes):
        import Vision
        from Foundation import NSData
        data = NSData.dataWithBytes_length_(png_bytes, len(png_bytes))
        req = Vision.VNRecognizeTextRequest.alloc().init()
        req.setRecognitionLevel_(1 if self.fast else 0)
        req.setUsesLanguageCorrection_(False)
        req.setMinimumTextHeight_(0.01)
        h = Vision.VNImageRequestHandler.alloc().initWithData_options_(data, None)
        ok, err = h.performRequests_error_([req], None)
        out = []
        for ob in (req.results() or []):
            cand = ob.topCandidates_(1)
            if not cand:
                continue
            bb = ob.boundingBox()
            for tok in self._split(cand[0].string(), bb):
                out.append(tok)
        return out

    @staticmethod
    def _split(text, bb):
        """Vision may merge neighbouring words into one line; split evenly."""
        parts = text.split()
        if len(parts) <= 1:
            return [(text, (bb.origin.x, bb.origin.y, bb.size.width, bb.size.height))]
        total = sum(len(p) for p in parts) + len(parts) - 1
        x, out = bb.origin.x, []
        for p in parts:
            w = bb.size.width * len(p) / total
            out.append((p, (x, bb.origin.y, w, bb.size.height)))
            x += bb.size.width * (len(p) + 1) / total
        return out

    def read(self):
        clip = self._clip()
        if not clip:
            raise CDPError("game canvas not found for OCR")
        if not getattr(self, "scale", None):  # capture at CSS pixels, not Retina
            dpr = self.cdp.call("Runtime.evaluate", expression="devicePixelRatio",
                                returnByValue=True)["result"].get("value") or 1
            self.scale = 1.0 / max(1.0, float(dpr))
        # JPEG q100 at CSS resolution. Measured on the real page: ~0.10 s CPU per
        # read (Retina PNG ~0.45 s); on the mock q100 kept 89 % word accuracy
        # vs 92 % for PNG, while q85 dropped to 79 %.
        shot = self.cdp.call("Page.captureScreenshot", format="jpeg", quality=100, clip=dict(
            x=clip["x"], y=clip["y"], width=clip["w"], height=clip["h"], scale=self.scale))
        items = self.recognize(base64.b64decode(shot["data"]))
        p = self.p
        sx = clip["w"] / p["game_w"]
        sy = clip["h"] / p["game_h"]
        off = p.get("word_offset_y", 0)
        zs = parse_ocr_items(items, [(y + off) * sy for y in p["rows_y"]], p["row_tol"] * sy,
                             p["center_x"] * sx,
                             {"L": p["fence_x"]["L"] * sx, "R": p["fence_x"]["R"] * sx},
                             clip["w"], clip["h"])
        for z in zs:  # back to game units
            z["dist"] /= sx
        return {"ok": True, "src": "ocr", "zombies": zs, "rows": len(p["rows_y"])}


def advance(zombies, dt):
    """Copy of zombies moved forward dt seconds along their speed."""
    out = []
    for z in zombies:
        z = dict(z)
        if not at_logs(z):
            z["dist"] = max(0.0, z["dist"] - (z.get("speed") or 0.0) * dt)
        out.append(z)
    return out


def fuse_ocr_with_memory(ocr_zs, mem_zs, min_ratio=0.7):
    """Game data outranks OCR. Each OCR word is snapped to the most similar
    game-data word in the same row and side (fixes misreads like
    'quartgrback'); game-data zombies OCR can't see (label hidden behind the
    zombie in front) are kept. Returns (zombies, corrections)."""
    import difflib
    out, used, fixes = [], set(), 0
    for o in ocr_zs:
        best, br = None, min_ratio
        for m in mem_zs:
            if m["id"] in used or m["row"] != o["row"] or m["side"] != o["side"]:
                continue
            r = difflib.SequenceMatcher(None, o["word"].lower(), m["word"].lower()).ratio()
            if r >= br:
                best, br = m, r
        if best is None:
            out.append(o)
            continue
        used.add(best["id"])
        if best["word"] != o["word"]:
            fixes += 1
        # word/id/typed from game data, position from the fresher OCR frame
        out.append(dict(best, dist=o["dist"]))
    out += [m for m in mem_zs if m["id"] not in used]
    return out, fixes


class OcrWorker(threading.Thread):
    """Runs OCR on its own CDP connection so the typing loop never waits."""

    def __init__(self, ws_url, profile, hz, fast=False, fallback_hz=None):
        super().__init__(daemon=True)
        self.reader = OcrReader(CDP(ws_url, timeout=10), profile, fast=fast)
        self.hz, self.fallback_hz = hz, fallback_hz or hz
        self.needed = False  # set by the bot when game data isn't available
        self.period = 1.0 / hz
        self.latest = None  # (capture_time, state)
        self.reads = 0
        self.error = None
        self._stop = threading.Event()
        self.ready = threading.Event()

    def run(self):
        while not self._stop.is_set():
            t = time.time()
            try:
                st = self.reader.read()
                self.latest = (t, st)
                self.reads += 1
            except Exception as e:  # keep going; main loop falls back
                self.error = str(e)
            self.ready.set()
            # slow cross-checks while game data works; faster when OCR is needed
            self.period = 1.0 / (self.fallback_hz if self.needed else self.hz)
            self._stop.wait(max(0.0, self.period - (time.time() - t)))

    def stop(self):
        self._stop.set()


# --------------------------------------------------------------------------- #
# Typist
# --------------------------------------------------------------------------- #

SPECIAL = {"ArrowUp": 38, "ArrowDown": 40, "ArrowLeft": 37, "ArrowRight": 39, "Enter": 13}


class Typist:
    def __init__(self, cdp, dry_run=False):
        self.cdp, self.dry = cdp, dry_run
        self.sent = 0

    def press(self, key):
        self.sent += 1
        if self.dry:
            return
        if key in SPECIAL:
            vk = SPECIAL[key]
            base = {"key": key, "code": key, "windowsVirtualKeyCode": vk,
                    "nativeVirtualKeyCode": vk}
            if key == "Enter":
                base["text"] = "\r"
            self.cdp.call("Input.dispatchKeyEvent", type="rawKeyDown" if key != "Enter" else "keyDown", **base)
            base.pop("text", None)
            self.cdp.call("Input.dispatchKeyEvent", type="keyUp", **base)
            return
        up = key.upper()
        ev = {"key": key, "text": key, "unmodifiedText": key}
        if up.isalpha() and len(up) == 1:
            ev.update(code="Key" + up, windowsVirtualKeyCode=ord(up), nativeVirtualKeyCode=ord(up))
        self.cdp.call("Input.dispatchKeyEvent", type="keyDown", **ev)
        ev.pop("text"), ev.pop("unmodifiedText")
        self.cdp.call("Input.dispatchKeyEvent", type="keyUp", **ev)

    def focus(self, clip):
        """Click the game canvas once so it has keyboard focus."""
        if self.dry or not clip:
            return
        x, y = clip["x"] + clip["w"] / 2, clip["y"] + clip["h"] - 5
        for t in ("mousePressed", "mouseReleased"):
            self.cdp.call("Input.dispatchMouseEvent", type=t, x=x, y=y,
                          button="left", clickCount=1)


# --------------------------------------------------------------------------- #
# Bot loop
# --------------------------------------------------------------------------- #


class Bot:
    def __init__(self, args, profile):
        self.a, self.p = args, profile
        self.rng = random.Random(args.seed)
        page = self._connect()
        self.page_ws = page["webSocketDebuggerUrl"]
        self.ocr = None
        if args.mode in ("mixed", "ocr"):
            try:
                hz = args.ocr_hz if args.mode == "mixed" else args.ocr_fallback_hz
                self.ocr = OcrWorker(page["webSocketDebuggerUrl"], profile, hz, fast=args.ocr_fast,
                                     fallback_hz=args.ocr_fallback_hz)
            except ImportError:
                print("[warn] pyobjc Vision not installed; OCR disabled", file=sys.stderr)
        self.speed = SpeedTracker(profile.get("default_speed", 60.0))
        # dead-reckoned player, used when the source has no player info (OCR)
        self.player = {"row": profile.get("start_row", 0), "facing": profile.get("start_facing", "R")}
        self.base_cps = wpm_to_cps(args.wpm)
        self.max_cps = wpm_to_cps(max(args.max_wpm, args.wpm))
        self.key_time = 1.0 / self.max_cps
        self.target_id = None
        self.recent_typed = {}  # word -> time it was finished (OCR-only staleness guard)
        self.last_ocr_t = 0.0
        self.ocr_seen = {}  # OCR word id -> consecutive frames seen
        self.own = (None, 0, 0.0)  # (target id, letters sent, time of last send)
        self.last_mem = None  # (time, last good game-data state)
        self.presumed_dead = {}  # id -> time we sent its last letter
        self.last_start_press = 0.0
        self.last_move, self.last_move_t = None, 0.0
        self.reloaded = False
        self.waiting_msg = None
        self.over_reported = False
        self.games = 0
        self.stats = {"ticks": 0, "mem_ok": 0, "ocr_ok": 0, "ocr_agree": [], "keys": 0,
                      "powerups": 0, "words_started": 0, "reconnects": 0,
                      "mem_held": 0, "ocr_fixed": 0, "reversals": 0, "stale_player_reads": 0}
        self.log = None
        if args.log:
            os.makedirs(os.path.dirname(os.path.abspath(args.log)), exist_ok=True)
            if os.path.exists(args.log) and os.path.getsize(args.log) > 0:
                # never overwrite an earlier run's log: add the start time
                root, ext = os.path.splitext(args.log)
                args.log = "%s-%s%s" % (root, time.strftime("%Y%m%d-%H%M%S"), ext or ".csv")
            print("logging to %s" % args.log)
            self.log = csv.writer(open(args.log, "w", newline="", buffering=1))  # line-buffered: readable mid-run
            self.log.writerow(["t", "event", "word", "row", "side", "ttf", "cps", "src"])

    def _connect(self):
        """(Re)open CDP connections to the game tab (and OOPIF game frame)."""
        a, p = self.a, self.p
        page, frame = find_targets(a.port, p["page_match"], p.get("frame_oopif_match"))
        self.page = CDP(page["webSocketDebuggerUrl"])
        self.game = CDP(frame["webSocketDebuggerUrl"]) if frame else self.page
        self.typist = Typist(self.page, a.dry_run)
        self.mem = None
        if a.mode in ("mixed", "memory") and p.get("probe"):
            with open(os.path.join(HERE, p["probe"])) as f:
                self.mem = MemoryReader(self.game, f.read(), p.get("frame_match"))
        return page

    def _reconnect(self, err):
        print("[cdp] connection lost (%s); reconnecting" % err, file=sys.stderr)
        for c in {id(self.page): self.page, id(self.game): self.game}.values():
            c.close()
        t0, last_err, hinted = time.time(), None, False
        while True:  # wait until the game tab is back (closed, reloaded, Chrome restarted)
            time.sleep(0.5)
            if not hinted and time.time() - t0 > 3:
                hinted = True
                print("[cdp] no Tommy Q tab on port %d (%s). Open %s in the bot's Chrome window;"
                      " waiting, Ctrl+C to quit" % (self.a.port, last_err, self.p["page_match"]),
                      file=sys.stderr)
            try:
                self.page_ws = self._connect()["webSocketDebuggerUrl"]
                if self.ocr:  # OCR thread keeps its own connection; restart it
                    self.ocr.stop()
                    self.ocr = OcrWorker(self.page_ws, self.p, self.ocr.hz, fast=self.a.ocr_fast,
                                         fallback_hz=self.ocr.fallback_hz)
                    self.ocr.start()
                self.stats["reconnects"] += 1
                if hinted:
                    print("[cdp] reconnected to the game tab", file=sys.stderr)
                return True
            except Exception as e:
                last_err = e
                continue

    def read_state(self, now):
        """Game data (memory) is the source of truth; OCR only fills gaps.
        1. fresh memory read            -> use it (OCR = cross-check stat only)
        2. memory failed < mem_hold ago -> last memory state moved forward
        3. otherwise OCR, snapped to recent game-data words (fuse_ocr_with_memory)"""
        st = None
        if self.mem:
            try:
                st = self.mem.read()
                st["src"] = "memory"
                self.stats["mem_ok"] += 1
                self.last_mem = (now, st)
            except (CDPError, KeyError) as e:
                if self.a.verbose:
                    print("[mem] %s" % e, file=sys.stderr)
        if st is not None:  # fresh game data is the truth: forget guesses it contradicts
            alive = {z["id"] for z in st["zombies"]}
            self.presumed_dead = {i: t for i, t in self.presumed_dead.items()
                                  if i not in alive and now - t < 3}
        mem_age = now - self.last_mem[0] if self.last_mem else INF
        if self.ocr:
            self.ocr.needed = st is None
        if st is None and mem_age < self.a.mem_hold:
            held = self.last_mem[1]
            st = dict(held, src="memory-held", zombies=[
                z for z in advance(held["zombies"], mem_age) if z["id"] not in self.presumed_dead])
            self.stats["mem_held"] += 1
        latest = self.ocr.latest if self.ocr else None
        if latest and now - latest[0] < 1.5:
            ocr_t, o = latest
            fresh = ocr_t > self.last_ocr_t
            self.last_ocr_t = ocr_t
            if st is None:
                if fresh:  # count consecutive OCR frames each word was read identically
                    self.ocr_seen = {z["id"]: self.ocr_seen.get(z["id"], 0) + 1 for z in o["zombies"]}
                zs = [dict(z) for z in o["zombies"]
                      if self.ocr_seen.get(z["id"], 0) >= self.a.ocr_confirm
                      and not (z["word"] in self.recent_typed and ocr_t < self.recent_typed[z["word"]] + 0.3)]
                src = "ocr"
                if self.last_mem and mem_age < self.a.mem_carry:
                    # game data still outranks: fix OCR spellings, keep hidden zombies
                    mem_zs = advance(self.last_mem[1]["zombies"], ocr_t - self.last_mem[0])
                    zs = [dict(z) for z in o["zombies"]]  # no confirm wait needed
                    zs, fixes = fuse_ocr_with_memory(zs, mem_zs)
                    zs = [z for z in zs if z["id"] not in self.presumed_dead]
                    for z in zs:  # old game-data progress is stale; trust our own count
                        z["typed"] = self.own[1] if z["id"] == self.own[0] else 0
                    self.stats["ocr_fixed"] += fixes
                    src = "ocr+memory"
                self.speed.update(zs, ocr_t)
                zs = advance(zs, now - ocr_t)
                self.recent_typed = {w: t for w, t in self.recent_typed.items() if now - t < 3}
                return dict(o, zombies=zs, src=src)
            if fresh and st["src"] == "memory":  # cross-check only
                mw = {z["word"].lower() for z in st["zombies"]}
                ow = {z["word"].lower() for z in o["zombies"]}
                if mw:
                    self.stats["ocr_agree"].append(len(mw & ow) / len(mw))
        if st is None:
            return None
        if st.get("player") and st["src"] == "memory":  # held state's player is stale
            game_p = {"row": st["player"]["row"], "facing": st["player"]["facing"]}
            # Chrome can apply arrow keys late. Right after we moved, a read that
            # still shows the old lane is stale: trust our own position, or the
            # bot sends the arrows again, overshoots and bounces between lanes.
            if game_p == self.player or now - self.last_move_t > MOVE_TRUST_S:
                self.player = game_p
            else:
                self.stats["stale_player_reads"] += 1
        self.speed.update(st["zombies"], now)
        return st

    def send(self, key, delay):
        """Press key, then hold until `delay` after the press. Keys run on a
        clock (next_key_at), so time spent reading state between keys comes
        out of the delay instead of slowing the WPM."""
        due = getattr(self, "next_key_at", 0.0)
        wait = due - time.time()
        if 0 < wait < 1.0:
            time.sleep(wait)
        pressed = time.time()
        # stay on schedule: after a slow key (Chrome sometimes takes 100+ ms),
        # the next few keys catch up so the average speed stays at the target
        base = due if 0 <= pressed - due < 0.15 else pressed
        self.typist.press(key)
        self.stats["keys"] += 1
        if key.startswith("Arrow"):
            # a reversal = undoing the previous move within 1 s (wasted time)
            undo = {"ArrowUp": "ArrowDown", "ArrowDown": "ArrowUp",
                    "ArrowLeft": "ArrowRight", "ArrowRight": "ArrowLeft"}[key]
            if self.last_move == undo and pressed - self.last_move_t < 1.0:
                self.stats["reversals"] += 1
            self.last_move, self.last_move_t = key, pressed
        if key == "ArrowUp":
            self.player["row"] = max(0, self.player["row"] - 1)
        elif key == "ArrowDown":
            self.player["row"] = min(self.p.get("rows", 5) - 1, self.player["row"] + 1)
        elif key in ("ArrowLeft", "ArrowRight"):
            self.player["facing"] = key[5]
        self.next_key_at = base + delay

    def run(self):
        a = self.a
        if self.ocr:
            self.ocr.start()  # first read also warms up the Vision model
            self.ocr.ready.wait(15)
            if self.ocr.error and self.a.verbose:
                print("[ocr] %s" % self.ocr.error, file=sys.stderr)
        if self.p.get("focus_click", True):  # off for the real game: could hit a menu button
            try:
                self.typist.focus(self.ocr.reader._clip() if self.ocr else None)
            except Exception:
                pass
        t0 = time.time()
        ru0 = resource.getrusage(resource.RUSAGE_SELF)
        self.cpu0 = ru0.ru_utime + ru0.ru_stime
        tick = 1.0 / a.hz
        self.idle_reads = 0
        try:
            while a.seconds <= 0 or time.time() - t0 < a.seconds:
                try:
                    if self._tick(t0, tick) == "stop":
                        break
                except (OSError, CDPError, json.JSONDecodeError) as e:
                    if isinstance(e, CDPError) and "probe" in str(e):
                        raise
                    if not self._reconnect(e):
                        print("could not reconnect; stopping")
                        break
                except Exception as e:  # websocket-client errors
                    if type(e).__module__.startswith("websocket") and self._reconnect(e):
                        continue
                    raise
        except KeyboardInterrupt:
            print("\nstopped (Ctrl+C)")
        finally:
            if self.ocr:
                self.ocr.stop()
            self.report(time.time() - t0)

    def _next_index(self, tgt, now):
        """Which letter to send next. The game's `typed` can lag behind keys
        just sent (e.g. while a screenshot is taken), so trust our own count
        for the same target unless the game disagrees for > 0.3 s (key lost)."""
        game_typed = int(tgt["typed"])
        tid, n, t = self.own
        if tid == tgt["id"] and n > game_typed and now - t < 0.3:
            return n
        return game_typed

    def _tick(self, t0, tick):
        """One plan/act step. Returns "stop" to end the run."""
        a = self.a
        now = time.time()
        st = self.read_state(now)
        self.stats["ticks"] += 1
        if st is None:
            self.idle_reads += 1
            if self.idle_reads > a.hz * 10:
                print("no game state for 10 s; stopping")
                return "stop"
            time.sleep(tick)
            return
        self.idle_reads = 0
        if st.get("waiting"):
            if self.waiting_msg != st["waiting"]:
                self.waiting_msg = st["waiting"]
                print("waiting: %s (start a round in Chrome)" % st["waiting"])
            self.target_id = None
            time.sleep(0.25)
            return
        self.waiting_msg = None
        if st.get("over") and self.p.get("wait_after_over"):
            if not self.over_reported:
                self.over_reported = True
                self.games += 1
                print("game over (kills %s, level %s); waiting for the next round, Ctrl+C to quit"
                      % (st.get("kills"), st.get("level")))
            self.target_id = None
            time.sleep(0.5)
            return
        self.over_reported = False
        if st.get("over"):
            if self.p.get("reload_if_over") and self.stats["keys"] == 0 and not self.reloaded:
                # found a finished game before playing: reload the tab once
                self.reloaded = True
                print("game already over; reloading the game tab")
                self.page.call("Page.reload", ignoreCache=True)
                time.sleep(2.0)
                return
            print("game over detected (reload the game tab to play again)")
            return "stop"
        if st.get("started") is False:  # waiting on a start screen: press Enter
            if now - self.last_start_press > 1.0:
                self.last_start_press = now
                print("starting the game (Enter)")
                self.send("Enter", tick)
            else:
                time.sleep(tick)
            return
        zs = st["zombies"]
        queue = edf_order(zs, self.player)
        cps = choose_cps(queue, self.player, self.base_cps, self.max_cps, self.key_time)
        if choose_powerup(st, self.player, self.max_cps, self.key_time):
            self.stats["powerups"] += 1
            self._log(now, "powerup", st.get("powerup"), None, cps, st["src"])
            self.send("Enter", tick)
            return
        tgt = choose_target(zs, self.player, self.target_id, self.max_cps, self.key_time,
                            holding=bool(st.get("powerup")))
        if tgt is None:
            self.target_id = None
            time.sleep(tick)
            return
        if tgt["id"] != self.target_id:
            self.target_id = tgt["id"]
            self.stats["words_started"] += 1
            self._log(now, "pickup:" + str(tgt.get("powerup")) if is_powerup(tgt) else "target",
                      tgt["word"], tgt, cps, st["src"])
        mv = movement_keys(tgt, self.player)
        if mv:  # movement first, then re-read state
            for k in mv:
                self.send(k, self.key_time * (1 + self.rng.uniform(0, self.a.jitter)))
            return
        # type the next char; when source has no `typed`, type whole word
        if "typed" in tgt and st["src"].startswith("memory"):
            idx = self._next_index(tgt, now)
            if idx >= len(tgt["word"]):
                time.sleep(tick)  # all sent; wait for the game to register the kill
                return
            end = len(tgt["word"]) if self.a.word_burst else idx + 1
            for i in range(idx, end):  # instant: the whole rest of the word at once
                self.send(tgt["word"][i], key_delay(cps, self.rng, self.a.jitter))
                self.own = (tgt["id"], i + 1, time.time())
            if end >= len(tgt["word"]):
                self.presumed_dead[tgt["id"]] = time.time()
        else:
            for ch in tgt["word"][int(tgt.get("typed", 0)):]:
                self.send(ch, key_delay(cps, self.rng, self.a.jitter))
            self.recent_typed[tgt["word"]] = time.time()
            self.presumed_dead[tgt["id"]] = time.time()
            self.target_id = None

    def _log(self, now, event, word, z, cps, src):
        if self.log:
            self.log.writerow(["%.3f" % now, event, word or "",
                               z["row"] if z else "", z["side"] if z else "",
                               "%.2f" % time_to_fence(z) if z else "", "%.1f" % cps, src])

    def report(self, wall):
        ru = resource.getrusage(resource.RUSAGE_SELF)
        cpu = ru.ru_utime + ru.ru_stime - getattr(self, "cpu0", 0.0)
        rss_mb = ru.ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024)
        agree = self.stats["ocr_agree"]
        summary = {
            "seconds": round(wall, 1), "ticks": self.stats["ticks"],
            "memory_reads": self.stats["mem_ok"], "ocr_reads": self.ocr.reads if self.ocr else 0,
            "ocr_agreement": round(sum(agree) / len(agree), 3) if agree else None,
            "keys_sent": self.stats["keys"], "targets": self.stats["words_started"],
            "powerups_used": self.stats["powerups"], "reconnects": self.stats["reconnects"],
            "memory_held_ticks": self.stats["mem_held"], "ocr_words_fixed_by_memory": self.stats["ocr_fixed"],
            "lane_reversals": self.stats["reversals"], "stale_player_reads": self.stats["stale_player_reads"],
            "cpu_percent_avg": round(100.0 * cpu / wall, 1) if wall >= 1.0 else None,
            "peak_rss_mb": round(rss_mb, 1),
        }
        print(json.dumps(summary, indent=2))
        if self.a.summary_json:
            with open(self.a.summary_json, "w") as f:
                json.dump(summary, f, indent=2)
        return summary


def load_profile(path):
    with open(path) as f:
        p = json.load(f)
    p.setdefault("rows", len(p.get("rows_y", [])) or 5)
    return p


# Two versions of the bot (see tommyq_normal.py / tommyq_instant.py):
#   normal  - human-like: 140 WPM with +-30 % jitter, speeds up to 220 WPM only
#             when a zombie is about to reach the logs; one letter per tick.
#   instant - kills each word as fast as Chrome accepts keys (~8 ms/letter):
#             no delays or jitter, whole word sent in one burst, faster polling.
# Both play only through normal key presses; game data is only ever read.
PRESETS = {
    "normal": {"wpm": 140, "max_wpm": 220, "jitter": 0.3, "word_burst": False, "hz": 20},
    "instant": {"wpm": 6000, "max_wpm": 6000, "jitter": 0.0, "word_burst": True, "hz": 30},
}


def parse_args(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--profile", default=os.path.join(HERE, "profiles", "tommyq.json"))
    ap.add_argument("--port", type=int, default=9222)
    ap.add_argument("--mode", choices=["mixed", "memory", "ocr"], default="mixed")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="normal",
                    help="normal = human-like 140 WPM; instant = as fast as possible")
    ap.add_argument("--wpm", type=float, default=None, help="normal typing speed (preset default)")
    ap.add_argument("--max-wpm", type=float, default=None,
                    help="speed-up limit when a zombie is about to reach the logs (preset default)")
    ap.add_argument("--jitter", type=float, default=None, help="random +- fraction on each key delay")
    ap.add_argument("--hz", type=float, default=None, help="state polls per second (preset default)")
    ap.add_argument("--ocr-hz", type=float, default=0.33,
                    help="OCR cross-checks per second while game data works")
    ap.add_argument("--ocr-fallback-hz", type=float, default=1.5,
                    help="OCR reads per second when game data fails (and in --mode ocr)")
    ap.add_argument("--mem-hold", type=float, default=1.0,
                    help="s to keep using the last game-data state if a read fails, before OCR")
    ap.add_argument("--mem-carry", type=float, default=2.0,
                    help="s that old game data still corrects OCR words / keeps hidden zombies")
    ap.add_argument("--ocr-confirm", type=int, default=2,
                    help="OCR-only: frames a word must be read identically before typing it")
    ap.add_argument("--ocr-fast", action="store_true", help="Vision fast mode (less CPU, less accurate)")
    ap.add_argument("--seconds", type=float, default=0, help="stop after N seconds (0 = until game over)")
    ap.add_argument("--dry-run", action="store_true", help="plan but send no keys")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--log", default=None, help="CSV event log path")
    ap.add_argument("--summary-json", default=None)
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    for k, v in PRESETS[a.preset].items():  # preset fills anything not given explicitly
        if getattr(a, k, None) is None:
            setattr(a, k, v)
    return a


def main(argv=None):
    a = parse_args(argv)
    profile = load_profile(a.profile)
    if profile.get("needs_recon") and a.mode != "ocr":
        print("profile %s still needs recon (see plan.md); run recon.py first" % a.profile)
        return 2
    hinted = False
    while True:  # wait for Chrome / the game tab instead of crashing
        try:
            bot = Bot(a, profile)
            break
        except (CDPError, OSError) as e:
            if not hinted:
                hinted = True
                print("waiting for the game tab: %s\n  start Chrome with ./launch_chrome.sh and open %s"
                      " (Ctrl+C to quit)" % (e, profile["page_match"]))
            try:
                time.sleep(1.0)
            except KeyboardInterrupt:
                return 1
    bot.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
