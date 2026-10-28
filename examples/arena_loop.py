"""Skeleton of the main loop on Classic Arena: screenshot -> which screen -> handler -> again.
Needs templates (cut from YOUR screen, 1280x720) in examples/templates/:
  tap_continue.png  return_arena.png  refresh_list.png  battle_btn.png
  start_btn.png     auto_btn.png      close_x.png
Run with the game open on the Classic Arena list:  python arena_loop.py --battles 2
"""
import argparse
import os
import re
import time

import cv2
import numpy as np

from device import Device
from vision import OCR, Templates, find, parse_power

LOG_DIR = "logs"
P_RESULT_TAP = (640, 662)          # "TAP TO CONTINUE" / "RETURN TO ARENA"
SWIPE_UP = ((640, 640), (640, 300))
UNKNOWN_BACK = 20                  # unknown screen this long -> screenshot + Back
UNKNOWN_STOP = 180                 # stuck this long -> stop


def detect(img, words, tpl):
    """Templates first (fast, reliable), OCR only when they find nothing."""
    if tpl.match(img, "tap_continue"):
        return "result1"
    if tpl.match(img, "return_arena"):
        return "result2"
    if tpl.match(img, "refresh_list") or tpl.match(img, "battle_btn"):
        return "list"
    if tpl.match(img, "start_btn"):
        return "prep"
    if tpl.match(img, "auto_btn"):
        return "battle"
    if tpl.match(img, "close_x"):
        return "popup_x"
    if words is None:
        return "need_ocr"
    if find(words, r"classic\s*arena") and find(words, r"live\s*arena"):
        return "arena_map"
    return "unknown"


class Bot:
    def __init__(self, a):
        self.a = a
        self.dev, self.tpl, self.ocr = Device(a.serial), Templates(), OCR()
        self.fights = self.wins = 0
        self.unknown_since = None
        self.swipes = 0
        os.makedirs(LOG_DIR, exist_ok=True)

    def log(self, msg):
        print(time.strftime("%H:%M:%S"), msg, flush=True)

    def save(self, img, tag):
        cv2.imwrite(os.path.join(LOG_DIR, f"{time.strftime('%Y%m%d-%H%M%S')}-{tag}.png"), img)

    def run(self):
        while not (self.a.battles and self.fights >= self.a.battles):
            img = self.dev.screenshot()
            words = None
            state = detect(img, None, self.tpl)
            if state == "need_ocr":
                words = self.ocr.read(img)
                state = detect(img, words, self.tpl)
            if state != "unknown":
                self.unknown_since = None
            if getattr(self, "on_" + state)(img, words):
                break
        self.log(f"done: {self.fights} battles, {self.wins} wins")

    # ---- handlers: one per screen; return True to stop -------------------------
    def on_result1(self, img, words):
        self.dev.tap(*P_RESULT_TAP)

    def on_result2(self, img, words):
        self.dev.tap(*P_RESULT_TAP)

    def on_battle(self, img, words):
        time.sleep(5)                      # just wait; never Back here (pauses the battle)

    def on_prep(self, img, words):
        self.dev.tap(*self.tpl.match(img, "start_btn"))
        self.fights += 1
        self.log(f"battle {self.fights} started")
        time.sleep(3)

    def on_popup_x(self, img, words):
        self.dev.tap(*self.tpl.match(img, "close_x"), jitter=2)

    def on_arena_map(self, img, words):
        w = find(words, r"classic\s*arena")[0]
        self.dev.tap(w.cx, w.cy)

    def on_list(self, img, words):
        tokens = re.search(r"(\d{1,3})\s*/\s*10", self.ocr.crop(img, (935, 6, 1005, 44)))
        if tokens and int(tokens.group(1)) == 0:
            self.log("0 tokens -> stop (add the free-refill popup logic here)")
            return True
        for x, y, power in self.opponents(img):
            if power and power <= self.a.max_power:
                self.log(f"attack power {power:,}")
                self.dev.tap(x, y)
                self.swipes = 0
                return
        if self.swipes < 4:
            self.dev.swipe(*SWIPE_UP)      # waits 2.5 s for the inertia
            self.swipes += 1
            return
        self.log("no eligible opponents -> press Refresh List or wait for its timer")
        return True

    def opponents(self, img):
        """[(x, y, power)] for every Battle button; power is read by OCR under the button."""
        t = self.tpl.t.get("battle_btn")
        if t is None:
            return []
        th, tw = t.shape[:2]
        r = cv2.matchTemplate(img, t, cv2.TM_CCOEFF_NORMED)
        out, last_y = [], -999
        for y, x in sorted(zip(*np.where(r >= 0.8))):
            if y - last_y < th:            # one hit per row
                continue
            last_y = y
            cx, cy = x + tw // 2, y + th // 2
            if cy < 230:                   # under the header only
                continue
            p = parse_power(self.ocr.crop(img, (700, cy + 25, 1010, cy + 62)))
            out.append((cx, cy, p if p and 10_000 <= p <= 20_000_000 else None))
        return out

    def on_unknown(self, img, words):
        if not self.dev.raid_in_front():
            self.log("Raid is not in front -> launch it")
            self.dev.launch_raid()
            time.sleep(10)
            return
        self.unknown_since = self.unknown_since or time.time()
        waited = time.time() - self.unknown_since
        if waited > UNKNOWN_STOP:
            self.save(img, "stuck")
            self.log("stuck for 3 minutes -> stop")
            return True
        if waited > UNKNOWN_BACK:
            self.save(img, "unknown")
            self.log(f"unknown screen, text: {[w.text for w in words][:15]}")
            self.dev.back()                # Esc closes almost any window in Raid
        time.sleep(2)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--serial", default="127.0.0.1:5555")
    ap.add_argument("--battles", type=int, default=0, help="0 = until tokens are gone")
    ap.add_argument("--max-power", type=int, default=700_000, help="skip stronger opponents")
    Bot(ap.parse_args()).run()
