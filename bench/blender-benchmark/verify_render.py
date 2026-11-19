#!/usr/bin/env python3
"""verify_render.py — grade a rendered frame against the brief:
"a pretty woman in a red dress sitting at a table with a computer and a lamp".

Independent read-backs, house doctrine: we do not trust that the scene
*script* created features — we look for them in the finished pixels.

Checks (hard):
  rendered      non-black coverage > 5 %
  red_dress     saturated-red pixel share >= 0.5 %
  figure        warm skin-tone cluster present (>= 0.15 %) near the red cluster
  lamp          a compact hot-light cluster exists (bright connected blob)
  screen        blue-dominant illuminated cluster exists (the computer display)
Check (soft):
  face          mediapipe face detection (WARN only — stylized figures may miss)

Run with the vision venv:
  ~/resolve-vision-venv312/bin/python verify_render.py FRAME.png [--json OUT]
"""
import argparse
import json

import cv2
import numpy as np

ap = argparse.ArgumentParser()
ap.add_argument("frame")
ap.add_argument("--json", dest="json_out", default=None)
args = ap.parse_args()

img = cv2.imread(args.frame)
if img is None:
    print(json.dumps({"error": f"cannot read {args.frame}"}))
    raise SystemExit(2)
h, w = img.shape[:2]
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
H, S, V = cv2.split(hsv)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
B, G, R = cv2.split(img.astype(np.int16))


def largest_blob_area(mask):
    if mask.sum() == 0:
        return 0
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    return int(stats[1:, cv2.CC_STAT_AREA].max()) if n > 1 else 0


def centroid(mask):
    if mask.sum() == 0:
        return None
    ys, xs = np.nonzero(mask)
    return float(xs.mean() / w), float(ys.mean() / h)


checks = []

# 1. actually rendered
cov = float((gray > 16).mean())
checks.append(("rendered", round(cov, 4), cov > 0.05))

# 2. red dress: saturated red hue (wraps at 0/180 in OpenCV HSV)
red = (((H <= 12) | (H >= 168)) & (S > 110) & (V > 30))
red_frac = float(red.mean())
red_c = centroid(red)
checks.append(("red_dress", round(red_frac, 4),
               red_frac >= 0.005 and largest_blob_area(red) > 0.002 * w * h))

# 3. figure: warm skin tones clustered near the red cluster
skin = ((H >= 5) & (H <= 25) & (S > 40) & (S < 170) & (V > 90))
skin_frac = float(skin.mean())
skin_c = centroid(skin)
near = False
if skin_c and red_c:
    near = ((skin_c[0] - red_c[0]) ** 2 + (skin_c[1] - red_c[1]) ** 2) ** 0.5 < 0.25
checks.append(("figure", round(skin_frac, 4), skin_frac >= 0.0015 and near))

# 4. lamp: compact hot blob (the shade/bulb), not scattered noise
hot = (gray > 200)
hot_frac = float(hot.mean())
hot_blob = largest_blob_area(hot)
checks.append(("lamp", f"frac={hot_frac:.4f} blob={hot_blob}",
               hot_blob > 0.0005 * w * h))

# 5. screen: blue-dominant illuminated region
blue = ((B > R + 25) & (B > G + 10) & (B > 120))
blue_blob = largest_blob_area(blue)
checks.append(("screen", round(float(blue.mean()), 4),
               blue_blob > 0.0005 * w * h))

# soft: frontal-face detection (Haar ships inside cv2; stylized figures may miss,
# and mediapipe 1.2 removed the legacy solutions API, so this stays WARN-only)
soft = {}
try:
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = cascade.detectMultiScale(gray, 1.15, 5, minSize=(int(0.03 * w),) * 2)
    soft["face"] = bool(len(faces))
    soft["face_boxes"] = int(len(faces))
except Exception as e:
    soft["face"] = "unavailable"
    soft["face_note"] = str(e)[:80]

hard_pass = all(p for _, _, p in checks)
out = {
    "frame": args.frame.split("/")[-1],
    "resolution": [w, h],
    "checks": [{"name": n, "value": v, "pass": p} for n, v, p in checks],
    "soft": soft,
    "PASS": hard_pass,
    "score": f"{sum(p for *_, p in checks)}/{len(checks)}",
    "brief": "a pretty woman in a red dress sitting at a table with a computer and a lamp",
}
print(json.dumps(out, indent=2))
if args.json_out:
    with open(args.json_out, "w") as f:
        json.dump(out, f, indent=2)
raise SystemExit(0 if hard_pass else 1)
