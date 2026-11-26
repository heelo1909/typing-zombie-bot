"""Unit tests for the pure logic in zombie_bot.py (no Chrome needed).
Run: .venv/bin/python -m unittest discover -s tests -v
"""
import json
import os
import random
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import zombie_bot as zb  # noqa: E402


def Z(id, word, row, side, dist, speed=60.0, typed=0):
    return {"id": id, "word": word, "row": row, "side": side, "dist": dist,
            "speed": speed, "typed": typed}


P = {"row": 2, "facing": "R"}
KT = 0.075  # key time at 160 WPM


class TestBasics(unittest.TestCase):
    def test_wpm_to_cps(self):
        self.assertAlmostEqual(zb.wpm_to_cps(80), 80 * 5 / 60)

    def test_remaining(self):
        self.assertEqual(zb.remaining(Z(1, "zombie", 0, "L", 10, typed=2)), 4)
        self.assertEqual(zb.remaining(Z(1, "zombie", 0, "L", 10, typed=9)), 0)

    def test_time_to_fence(self):
        self.assertAlmostEqual(zb.time_to_fence(Z(1, "a", 0, "L", 120, 60)), 2.0)
        self.assertEqual(zb.time_to_fence(Z(1, "a", 0, "L", 120, 0)), zb.INF)

    def test_moves_same_lane(self):
        self.assertEqual(zb.moves(Z(1, "a", 2, "R", 1), P), 0)

    def test_moves_counts_turn(self):
        self.assertEqual(zb.moves(Z(1, "a", 0, "L", 1), P), 3)


class TestMovement(unittest.TestCase):
    def test_up_and_turn(self):
        self.assertEqual(zb.movement_keys(Z(1, "a", 0, "L", 1), P),
                         ["ArrowUp", "ArrowUp", "ArrowLeft"])

    def test_down(self):
        self.assertEqual(zb.movement_keys(Z(1, "a", 4, "R", 1), P), ["ArrowDown", "ArrowDown"])

    def test_none_needed(self):
        self.assertEqual(zb.movement_keys(Z(1, "a", 2, "R", 1), P), [])


class TestTargeting(unittest.TestCase):
    def test_edf_order_by_deadline(self):
        zs = [Z(1, "far", 2, "R", 300), Z(2, "near", 0, "L", 60), Z(3, "mid", 4, "R", 150)]
        self.assertEqual([z["id"] for z in zb.edf_order(zs, P)], [2, 3, 1])

    def test_edf_skips_finished(self):
        zs = [Z(1, "done", 2, "R", 10, typed=4), Z(2, "live", 2, "R", 100)]
        self.assertEqual([z["id"] for z in zb.edf_order(zs, P)], [2])

    def test_edf_tiebreak_moves(self):
        zs = [Z(1, "abc", 0, "L", 100), Z(2, "abc", 2, "R", 100)]
        self.assertEqual(zb.edf_order(zs, P)[0]["id"], 2)

    def test_choose_most_urgent(self):
        zs = [Z(1, "lane", 2, "R", 400), Z(2, "urgent", 0, "L", 120)]
        self.assertEqual(zb.choose_target(zs, P, None, 13.3, KT)["id"], 2)

    def test_keeps_current_when_safe(self):
        zs = [Z(1, "current", 2, "R", 200, typed=3), Z(2, "other", 0, "L", 180)]
        self.assertEqual(zb.choose_target(zs, P, 1, 13.3, KT)["id"], 1)

    def test_switches_when_threatened(self):
        zs = [Z(1, "verylongcurrentword", 2, "R", 500), Z(2, "go", 1, "R", 40)]
        self.assertEqual(zb.choose_target(zs, P, 1, 13.3, KT)["id"], 2)

    def test_skips_unkillable(self):
        zs = [Z(1, "impossiblylongword", 0, "L", 5), Z(2, "ok", 2, "R", 200)]
        self.assertEqual(zb.choose_target(zs, P, None, 13.3, KT)["id"], 2)

    def test_none_when_empty(self):
        self.assertIsNone(zb.choose_target([], P, None, 13.3, KT))

    def test_killable(self):
        self.assertTrue(zb.killable(Z(1, "abc", 2, "R", 120), P, 13.3, KT))
        self.assertFalse(zb.killable(Z(1, "abcdefghijklmnop", 0, "L", 30), P, 13.3, KT))


class TestSwitchCost(unittest.TestCase):
    """Real game: leaving the row / turning resets the partly typed word."""

    def test_finishes_nearly_done_word(self):
        cur = Z(1, "abcdefghij", 2, "R", 90, typed=9)       # 1 char left, ttf 1.5 s
        other = Z(2, "abc", 1, "R", 60)                       # ttf 1.0 s
        self.assertEqual(zb.choose_target([cur, other], P, 1, 13.3, KT)["id"], 1)

    def test_switch_pays_off_false_when_both_saved_anyway(self):
        cur = Z(1, "abcdefghij", 2, "R", 90, typed=9)
        other = Z(2, "abc", 1, "R", 60)
        self.assertFalse(zb.switch_pays_off(cur, other, P, 13.3, KT))

    def test_switches_when_finishing_first_loses_other(self):
        cur = Z(1, "averyveryverylongword", 2, "R", 900, typed=2)  # far away
        other = Z(2, "go", 0, "L", 40)                              # ttf 0.67 s
        self.assertTrue(zb.switch_pays_off(cur, other, P, 13.3, KT))
        self.assertEqual(zb.choose_target([cur, other], P, 1, 13.3, KT)["id"], 2)

    def test_reset_counted_in_switch_cost(self):
        # Switching saves `other` but the reset would doom cur -> same count, stay.
        cur = Z(1, "abcdefghijklmn", 2, "R", 90, typed=12)  # 2 left, ttf 1.5 s
        other = Z(2, "abcdefgh", 0, "L", 60)                 # ttf 1.0 s, can't wait
        self.assertFalse(zb.switch_pays_off(cur, other, P, 13.3, KT))

    def test_locks_onto_in_game_progress(self):
        partial = Z(1, "abcdef", 2, "R", 200, typed=3)
        other = Z(2, "abc", 2, "R", 190)
        self.assertEqual(zb.choose_target([partial, other], P, None, 13.3, KT)["id"], 1)

    def test_no_lock_when_progress_elsewhere(self):
        partial = Z(1, "abcdef", 0, "L", 200, typed=3)   # not in our lane
        other = Z(2, "abc", 2, "R", 100)
        self.assertEqual(zb.choose_target([partial, other], P, None, 13.3, KT)["id"], 2)


class TestDangerPriority(unittest.TestCase):
    """User: prioritize zombies closest to the logs / most dangerous."""

    def test_chopping_zombie_first(self):
        chop = Z(1, "longerword", 0, "L", 0, speed=0)
        chop["chopping"] = True
        walker = Z(2, "abc", 2, "R", 30)
        self.assertEqual(zb.edf_order([walker, chop], P)[0]["id"], 1)

    def test_chopping_always_killable(self):
        chop = Z(1, "averyveryverylongword", 0, "L", 0)
        self.assertTrue(zb.killable(chop, P, 13.3, KT))

    def test_closest_to_logs_beats_easier_lane(self):
        near = Z(1, "abcdef", 0, "L", 60)    # 1 s from the logs, 3 moves away
        lane = Z(2, "abc", 2, "R", 300)      # in our lane but 5 s away
        self.assertEqual(zb.choose_target([lane, near], P, None, 13.3, KT)["id"], 1)

    def test_chopping_pulls_bot_off_long_far_word(self):
        cur = Z(1, "averyveryverylongword", 2, "R", 900, typed=3)
        chop = Z(2, "go", 1, "R", 0)
        chop["chopping"] = True
        self.assertEqual(zb.choose_target([cur, chop], P, 1, 13.3, KT)["id"], 2)


class TestGameLock(unittest.TestCase):
    """User: letters go to the word you start typing."""

    def test_lock_beats_bot_choice_in_lane(self):
        started = Z(1, "abcdef", 2, "R", 300, typed=2)  # game locked onto this one
        nearer = Z(2, "xyz", 2, "R", 200)               # same lane, bot wanted it
        self.assertEqual(zb.choose_target([started, nearer], P, 2, 13.3, KT)["id"], 1)

    def test_game_lock_helper(self):
        zs = [Z(1, "abc", 2, "R", 100), Z(2, "abc", 2, "R", 200, typed=1), Z(3, "abc", 1, "R", 50, typed=2)]
        self.assertEqual(zb.game_lock(zs, P)["id"], 2)


class TestFusion(unittest.TestCase):
    """User: game data is more accurate, so it must outrank OCR."""

    def test_ocr_misread_snapped_to_game_word(self):
        mem = [Z(7, "quarterback", 1, "L", 200)]
        ocr = [{"id": "quartgrback:1:L", "word": "quartgrback", "typed": 0, "row": 1, "side": "L", "dist": 190.0}]
        zs, fixes = zb.fuse_ocr_with_memory(ocr, mem)
        self.assertEqual((zs[0]["word"], zs[0]["id"], zs[0]["dist"], fixes), ("quarterback", 7, 190.0, 1))

    def test_hidden_zombie_kept_from_game_data(self):
        mem = [Z(1, "front", 0, "L", 50), Z(2, "behind", 0, "L", 70)]   # label of 2 is covered
        ocr = [{"id": "front:0:L", "word": "front", "typed": 0, "row": 0, "side": "L", "dist": 48.0}]
        zs, _ = zb.fuse_ocr_with_memory(ocr, mem)
        self.assertEqual(sorted(z["word"] for z in zs), ["behind", "front"])

    def test_no_snap_across_rows(self):
        mem = [Z(7, "quarterback", 3, "L", 200)]
        ocr = [{"id": "quartgrback:1:L", "word": "quartgrback", "typed": 0, "row": 1, "side": "L", "dist": 190.0}]
        zs, fixes = zb.fuse_ocr_with_memory(ocr, mem)
        self.assertEqual(fixes, 0)
        self.assertIn("quartgrback", [z["word"] for z in zs])

    def test_advance_moves_walkers_not_choppers(self):
        w = Z(1, "a", 0, "L", 100, speed=50)
        c = Z(2, "b", 0, "L", 0, speed=50)
        c["chopping"] = True
        out = zb.advance([w, c], 1.0)
        self.assertEqual((out[0]["dist"], out[1]["dist"], w["dist"]), (50.0, 0, 100))


def PU(id, word, row, side):
    return {"id": id, "kind": "powerup", "powerup": "bomb", "word": word, "typed": 0,
            "row": row, "side": side, "dist": 1e6, "speed": 0}


class TestPowerupPickup(unittest.TestCase):
    """Real game: power-ups are words in a lane; typing one collects it."""

    def test_pickup_when_calm(self):
        zs = [Z(1, "abc", 0, "L", 380, speed=30), PU("p", "bonus", 2, "R")]
        self.assertEqual(zb.choose_target(zs, P, None, 13.3, KT)["id"], "p")

    def test_no_pickup_when_zombie_urgent(self):
        zs = [Z(1, "abcdefgh", 0, "L", 30, speed=30), PU("p", "bonus", 2, "R")]
        self.assertEqual(zb.choose_target(zs, P, None, 13.3, KT)["id"], 1)

    def test_no_pickup_when_chopping(self):
        chop = Z(1, "abc", 4, "L", 0)
        chop["chopping"] = True
        zs = [chop, PU("p", "bonus", 2, "R")]
        self.assertEqual(zb.choose_target(zs, P, None, 13.3, KT)["id"], 1)

    def test_finish_started_pickup(self):
        p = PU("p", "bonus", 2, "R")
        p["typed"] = 2
        zs = [Z(1, "abc", 0, "L", 60, speed=30), p]
        self.assertEqual(zb.choose_target(zs, P, None, 13.3, KT)["id"], "p")

    def test_pickup_only(self):
        self.assertEqual(zb.choose_target([PU("p", "bonus", 0, "L")], P, None, 13.3, KT)["id"], "p")

    def test_pickups_not_counted_for_powerup_use(self):
        st = {"powerup": "bomb", "zombies": [PU("a", "x", 0, "L"), PU("b", "y", 1, "L"), PU("c", "z", 2, "L")]}
        self.assertFalse(zb.choose_powerup(st, P, 13.3, KT))


class TestSpeedChoice(unittest.TestCase):
    def test_base_speed_when_relaxed(self):
        q = zb.edf_order([Z(1, "abc", 2, "R", 600)], P)
        self.assertAlmostEqual(zb.choose_cps(q, P, 6.67, 13.3, KT), 6.67)

    def test_bursts_when_tight(self):
        q = zb.edf_order([Z(1, "abcdefghij", 2, "R", 60)], P)  # 1 s for 10 chars
        cps = zb.choose_cps(q, P, 6.67, 13.3, KT)
        self.assertGreater(cps, 6.67)
        self.assertLessEqual(cps, 13.3)

    def test_capped_at_max(self):
        q = zb.edf_order([Z(1, "abcdefghijklmnopqrst", 2, "R", 10)], P)
        self.assertEqual(zb.choose_cps(q, P, 6.67, 13.3, KT), 13.3)

    def test_key_delay_jitter_bounds(self):
        rng = random.Random(0)
        for _ in range(200):
            d = zb.key_delay(6.67, rng)
            self.assertTrue(0.7 / 6.67 - 1e-9 <= d <= 1.3 / 6.67 + 1e-9)


class TestPowerups(unittest.TestCase):
    def test_no_powerup(self):
        st = {"powerup": None, "zombies": [Z(1, "a", 0, "L", 1)]}
        self.assertFalse(zb.choose_powerup(st, P, 13.3, KT))

    def test_bomb_on_crowd(self):
        st = {"powerup": "bomb", "zombies": [Z(i, "abc", i, "L", 100) for i in range(3)]}
        self.assertTrue(zb.choose_powerup(st, P, 13.3, KT))

    def test_bomb_saved_when_calm(self):
        st = {"powerup": "bomb", "zombies": [Z(1, "abc", 2, "R", 400)]}
        self.assertFalse(zb.choose_powerup(st, P, 13.3, KT))

    def test_book_two_in_row(self):
        st = {"powerup": "book", "zombies": [Z(1, "abc", 2, "R", 300), Z(2, "abc", 2, "R", 350)]}
        self.assertTrue(zb.choose_powerup(st, P, 13.3, KT))

    def test_book_ignores_other_side(self):
        # real game: the book only clears Tommy's row on the side he faces
        st = {"powerup": "book", "zombies": [Z(1, "abc", 2, "R", 300), Z(2, "abc", 2, "L", 300)]}
        self.assertFalse(zb.choose_powerup(st, P, 13.3, KT))

    def test_ice_when_doomed(self):
        st = {"powerup": "ice", "zombies": [Z(1, "abcdefghijklmnop", 0, "L", 20)]}
        self.assertTrue(zb.choose_powerup(st, P, 13.3, KT))


class TestSpeedTracker(unittest.TestCase):
    def test_estimates_speed(self):
        tr = zb.SpeedTracker(50.0)
        z = {"id": 1, "word": "a", "row": 0, "side": "L", "dist": 300.0}
        tr.update([dict(z)], 0.0)
        out = tr.update([dict(z, dist=240.0)], 1.0)
        self.assertAlmostEqual(out[0]["speed"], 0.6 * 50 + 0.4 * 60, places=3)

    def test_default_for_new(self):
        tr = zb.SpeedTracker(42.0)
        out = tr.update([{"id": 9, "word": "a", "row": 0, "side": "L", "dist": 100.0}], 0.0)
        self.assertEqual(out[0]["speed"], 42.0)

    def test_keeps_given_speed(self):
        tr = zb.SpeedTracker(42.0)
        out = tr.update([Z(1, "a", 0, "L", 100, speed=70)], 0.0)
        self.assertEqual(out[0]["speed"], 70)


class TestOcrParse(unittest.TestCase):
    ROWS = [103, 183, 263, 343, 423]

    def item(self, text, cx, cy, w=0.1, h=0.04, W=960, H=540):
        # build Vision-style normalized bbox (bottom-left origin) centered on cx, cy
        return (text, (cx / W - w / 2, 1 - cy / H - h / 2, w, h))

    def parse(self, items):
        return zb.parse_ocr_items(items, self.ROWS, 30, 480, {"L": 420, "R": 540}, 960, 540)

    def test_maps_row_side_dist(self):
        zs = self.parse([self.item("zombie", 200, 185)])
        self.assertEqual((zs[0]["word"], zs[0]["row"], zs[0]["side"]), ("zombie", 1, "L"))
        self.assertAlmostEqual(zs[0]["dist"], 220, delta=1)

    def test_right_side(self):
        zs = self.parse([self.item("brains", 800, 420)])
        self.assertEqual((zs[0]["row"], zs[0]["side"]), (4, "R"))

    def test_drops_hud_text(self):
        self.assertEqual(self.parse([self.item("Kills", 100, 20)]), [])

    def test_drops_short_and_punct(self):
        zs = self.parse([self.item("a", 200, 103), self.item("hello!", 300, 103)])
        self.assertEqual([z["word"] for z in zs], ["hello"])

    def test_split_merged_line(self):
        class BB:  # mimic NSRect
            class origin: x, y = 0.1, 0.5
            class size: width, height = 0.4, 0.05
        parts = zb.OcrReader._split("alpha beta", BB)
        self.assertEqual([p[0] for p in parts], ["alpha", "beta"])
        self.assertLess(parts[0][1][0], parts[1][1][0])


class TestProfiles(unittest.TestCase):
    def test_profiles_load(self):
        for name in ("mock.json", "tommyq.json"):
            p = zb.load_profile(os.path.join(ROOT, "profiles", name))
            for k in ("page_match", "rows_y", "fence_x", "center_x", "game_w", "game_h"):
                self.assertIn(k, p)
            self.assertEqual(p["rows"], len(p["rows_y"]))

    def test_real_profile_filled_from_recon(self):
        p = zb.load_profile(os.path.join(ROOT, "profiles", "tommyq.json"))
        self.assertFalse(p.get("needs_recon"))
        self.assertEqual(p["rows_y"], [155, 215, 275, 335, 395])

    def test_probe_fixture_shape(self):
        with open(os.path.join(ROOT, "tests", "fixtures", "mock_state.json")) as f:
            st = json.load(f)
        self.assertTrue(st["ok"])
        for z in st["zombies"]:
            for k in ("id", "word", "typed", "row", "side", "dist", "speed"):
                self.assertIn(k, z)
        self.assertIsNotNone(zb.choose_target(st["zombies"], st["player"], None, 13.3, KT))


class TestTypistDry(unittest.TestCase):
    def test_dry_run_sends_nothing(self):
        class Boom:
            def call(self, *a, **k):
                raise AssertionError("should not send in dry run")
        t = zb.Typist(Boom(), dry_run=True)
        for k in ["a", "ArrowUp", "Enter"]:
            t.press(k)
        self.assertEqual(t.sent, 3)

    def test_letter_event_shape(self):
        calls = []

        class Rec:
            def call(self, m, **k):
                calls.append((m, k))
        zb.Typist(Rec()).press("q")
        self.assertEqual(calls[0][1]["type"], "keyDown")
        self.assertEqual(calls[0][1]["text"], "q")
        self.assertEqual(calls[0][1]["windowsVirtualKeyCode"], ord("Q"))
        self.assertEqual(calls[1][1]["type"], "keyUp")

    def test_arrow_event_shape(self):
        calls = []

        class Rec:
            def call(self, m, **k):
                calls.append((m, k))
        zb.Typist(Rec()).press("ArrowLeft")
        self.assertEqual(calls[0][1]["windowsVirtualKeyCode"], 37)
        self.assertNotIn("text", calls[0][1])


class TestOwnTypedCount(unittest.TestCase):
    def bot(self, own):
        b = zb.Bot.__new__(zb.Bot)
        b.own = own
        return b

    def test_trusts_own_count_while_game_lags(self):
        b = self.bot((7, 4, 10.0))
        self.assertEqual(b._next_index(Z(7, "zombies", 0, "L", 9, typed=3), 10.1), 4)

    def test_falls_back_when_key_lost(self):
        b = self.bot((7, 4, 10.0))
        self.assertEqual(b._next_index(Z(7, "zombies", 0, "L", 9, typed=3), 10.5), 3)

    def test_other_target_uses_game_count(self):
        b = self.bot((7, 4, 10.0))
        self.assertEqual(b._next_index(Z(8, "zombies", 0, "L", 9, typed=1), 10.1), 1)


class TestSourcePriority(unittest.TestCase):
    """read_state: fresh game data > held game data > OCR snapped to game data > raw OCR."""

    def bot(self, mem_ok, last_mem_age, now=100.0):
        import types
        b = zb.Bot.__new__(zb.Bot)
        b.a = types.SimpleNamespace(mem_hold=1.0, mem_carry=2.0, ocr_confirm=2, verbose=False)
        mem_state = {"ok": True, "player": {"row": 2, "facing": "R"},
                     "zombies": [Z(7, "quarterback", 1, "L", 200)]}

        class Mem:
            def read(self_inner):
                if not mem_ok:
                    raise zb.CDPError("probe returned no state")
                return json.loads(json.dumps(mem_state))
        b.mem = Mem()
        ocr_z = {"id": "quartgrback:1:L", "word": "quartgrback", "typed": 0, "row": 1, "side": "L", "dist": 150.0}
        b.ocr = types.SimpleNamespace(latest=(now - 0.1, {"ok": True, "zombies": [ocr_z]}))
        b.stats = {"mem_ok": 0, "mem_held": 0, "ocr_fixed": 0, "ocr_agree": []}
        b.last_ocr_t, b.ocr_seen, b.recent_typed = 0.0, {}, {}
        b.presumed_dead, b.own = {}, (None, 0, 0.0)
        b.speed = zb.SpeedTracker(60.0)
        b.player = {"row": 0, "facing": "L"}
        b.last_mem = (now - last_mem_age, mem_state) if last_mem_age is not None else None
        return b

    def test_fresh_memory_wins(self):
        st = self.bot(True, None).read_state(100.0)
        self.assertEqual((st["src"], st["zombies"][0]["word"]), ("memory", "quarterback"))

    def test_recent_memory_held_before_ocr(self):
        b = self.bot(False, 0.5)
        st = b.read_state(100.0)
        self.assertEqual(st["src"], "memory-held")
        self.assertEqual(b.player, {"row": 0, "facing": "L"})  # stale player not applied

    def test_ocr_corrected_by_older_memory(self):
        st = self.bot(False, 1.5).read_state(100.0)
        self.assertEqual((st["src"], st["zombies"][0]["word"]), ("ocr+memory", "quarterback"))

    def test_held_state_drops_presumed_dead(self):
        b = self.bot(False, 0.5)
        b.presumed_dead = {7: 99.8}
        self.assertEqual(b.read_state(100.0)["zombies"], [])

    def test_fresh_memory_overrides_presumed_dead(self):
        b = self.bot(True, None)
        b.presumed_dead = {7: 99.8}
        st = b.read_state(100.0)
        self.assertEqual(len(st["zombies"]), 1)
        self.assertNotIn(7, b.presumed_dead)

    def test_raw_ocr_needs_confirmation(self):
        st = self.bot(False, None).read_state(100.0)
        self.assertEqual((st["src"], st["zombies"]), ("ocr", []))


if __name__ == "__main__":
    unittest.main()
