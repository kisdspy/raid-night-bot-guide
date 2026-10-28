"""Screen recognition: image templates (buttons) + OCR (text, numbers).
OCR: Apple Vision (ocrmac) on a Mac, EasyOCR elsewhere."""
import os
import re
import sys

import cv2

TPL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")


class Templates:
    """templates/<name>.png = tight crops of buttons cut from 1280x720 screenshots."""

    def __init__(self, folder=TPL_DIR):
        self.t = {f[:-4]: cv2.imread(os.path.join(folder, f))
                  for f in os.listdir(folder) if f.endswith(".png")} if os.path.isdir(folder) else {}

    def match(self, img, name, thr=0.8):
        """Centre (x, y) of the best match, or None."""
        if name not in self.t:
            return None
        r = cv2.matchTemplate(img, self.t[name], cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx < thr:
            return None
        h, w = self.t[name].shape[:2]
        return loc[0] + w // 2, loc[1] + h // 2


class Word:
    def __init__(self, text, x, y, w, h):
        self.text, self.x, self.y, self.w, self.h = text, x, y, w, h
        self.cx, self.cy = x + w / 2, y + h / 2

    def __repr__(self):
        return f"{self.text!r}@({self.cx:.0f},{self.cy:.0f})"


class OCR:
    def __init__(self):
        try:
            from ocrmac import ocrmac  # noqa: F401
            self.backend = "vision"
        except ImportError:
            import easyocr
            self.reader = easyocr.Reader(["en"])
            self.backend = "easyocr"

    def read(self, img):
        """All text lines on the image with boxes in image pixels."""
        if self.backend == "vision":
            from ocrmac import ocrmac
            from PIL import Image
            H, W = img.shape[:2]
            pil = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
            res = ocrmac.OCR(pil, recognition_level="accurate", language_preference=["en-US"]).recognize()
            # Vision boxes are normalised, origin bottom-left
            return [Word(t.strip(), bx * W, (1 - by - bh) * H, bw * W, bh * H) for t, _c, (bx, by, bw, bh) in res]
        out = []
        for box, text, conf in self.reader.readtext(img):
            if conf < 0.3:
                continue
            xs, ys = [p[0] for p in box], [p[1] for p in box]
            out.append(Word(text, min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)))
        return out

    def crop(self, img, box, scale=2):
        """Text of a small region (counter, power), upscaled first - OCR reads small digits badly."""
        x0, y0, x1, y1 = box
        c = img[max(0, y0):y1, max(0, x0):x1]
        if not c.size:
            return ""
        c = cv2.resize(c, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        return " ".join(w.text for w in self.read(c))


def find(words, pattern, region=None):
    """Words matching a regex (case-insensitive), optionally with the centre inside region=(x0,y0,x1,y1)."""
    rx = re.compile(pattern, re.I)
    return [w for w in words if rx.search(w.text) and
            (not region or (region[0] <= w.cx <= region[2] and region[1] <= w.cy <= region[3]))]


def parse_power(text):
    """'Team Power: 508.78K' -> 508780 ; '88,288' -> 88288 ; '1.2M' -> 1200000"""
    t = re.sub(r"[^0-9.,KMkm]", "", text.split("ower")[-1]).upper()
    m = re.search(r"(\d+(?:[.,]\d+)?)([KM])", t)
    if m:
        return int(float(m.group(1).replace(",", ".")) * (1000 if m.group(2) == "K" else 1_000_000))
    m = re.search(r"\d{1,3}(?:,\d{3})+", t)
    return int(m.group(0).replace(",", "")) if m else None


if __name__ == "__main__":
    # python vision.py screen.png -> prints every text line found (to write detect() rules)
    img = cv2.resize(cv2.imread(sys.argv[1]), (1280, 720))
    for w in OCR().read(img):
        print(w)
