"""ADB device: screenshot, tap, swipe, Back. Everything works in a 1280x720 reference frame,
taps are scaled back to the real screen (e.g. 1920x1080)."""
import random
import subprocess
import sys
import time

import cv2
import numpy as np

REF_W, REF_H = 1280, 720
RAID_PACKAGE = "com.plarium.raidlegends"


class Device:
    def __init__(self, serial="127.0.0.1:5555"):
        self.serial = serial
        self.W, self.H = REF_W, REF_H
        subprocess.run(["adb", "connect", serial], capture_output=True, timeout=15)

    def adb(self, *args, timeout=20):
        cmd = ["adb", "-s", self.serial, *args]
        for attempt in range(3):          # a hung adb command must not kill the whole night
            try:
                return subprocess.run(cmd, capture_output=True, timeout=timeout)
            except subprocess.TimeoutExpired:
                if attempt == 2:
                    raise
                self.reconnect()

    def reconnect(self):
        for c in ("disconnect", "connect"):
            subprocess.run(["adb", c, self.serial], capture_output=True, timeout=15)
        time.sleep(5)

    def screenshot(self):
        for _ in range(12):               # ~2 min of retries
            r = self.adb("exec-out", "screencap", "-p")
            img = cv2.imdecode(np.frombuffer(r.stdout, np.uint8), cv2.IMREAD_COLOR) if r.stdout else None
            if img is not None and img.size:
                self.H, self.W = img.shape[:2]
                return cv2.resize(img, (REF_W, REF_H), interpolation=cv2.INTER_AREA)
            self.reconnect()
        raise RuntimeError("screencap failed, ADB lost")

    def _scale(self, x, y):
        return int(x * self.W / REF_W), int(y * self.H / REF_H)

    def tap(self, x, y, jitter=4):
        x += random.randint(-jitter, jitter)
        y += random.randint(-jitter, jitter)
        self.adb("shell", "input", "tap", *map(str, self._scale(x, y)))
        time.sleep(random.uniform(0.6, 1.1))

    def swipe(self, a, b, ms=500):
        (x1, y1), (x2, y2) = self._scale(*a), self._scale(*b)
        self.adb("shell", "input", "swipe", *map(str, (x1, y1, x2, y2, ms)))
        time.sleep(2.5)                   # lists and maps keep scrolling by inertia

    def back(self):
        self.adb("shell", "input", "keyevent", "4")
        time.sleep(1)

    def raid_in_front(self):
        out = self.adb("shell", "dumpsys", "window").stdout.decode(errors="ignore")
        return any(RAID_PACKAGE in l for l in out.splitlines() if "mCurrentFocus" in l)

    def launch_raid(self):
        self.adb("shell", "monkey", "-p", RAID_PACKAGE, "-c", "android.intent.category.LAUNCHER", "1")


if __name__ == "__main__":
    # python device.py [serial] -> saves screen.png (1280x720) to cut templates from
    dev = Device(*sys.argv[1:2])
    cv2.imwrite("screen.png", dev.screenshot())
    print(f"saved screen.png, device screen {dev.W}x{dev.H}, Raid in front: {dev.raid_in_front()}")
