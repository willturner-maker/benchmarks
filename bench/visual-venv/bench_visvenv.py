#!/usr/bin/env python3
"""Visual venv baseline bench — pre-OpenCV-5.1.0 snapshot (run: venv python -I bench_visvenv.py --out run1.json).
Measures on fixed fixtures: import cost, model init, YuNet tiled detect (counts x thresholds x grids),
SFace alignCrop embed ms/face, cosine pair stats, the 5.0.0.93 match()-in-place behaviour probe, and API
surface presence relevant to the 5.1.0 changelog (classic DNN/TensorFlow reader removal, logging move)."""
import argparse, json, os, sys, time, hashlib
t_import0 = time.perf_counter()
import cv2, numpy as np
t_import = time.perf_counter() - t_import0

ap = argparse.ArgumentParser()
ap.add_argument("--out", required=True)
ap.add_argument("--png", default=os.path.join(os.path.dirname(__file__), "fixture_f240.png"))
ap.add_argument("--mp4", default=os.path.join(os.path.dirname(__file__), "fixture_f240_h264.mp4"))
ap.add_argument("--models", default=os.path.expanduser("~/resolve-vision-models"))
args = ap.parse_args()

DEF = os.path.join(args.models, "face_detection_yunet_2023mar.onnx")
SFM = os.path.join(args.models, "face_recognition_sface_2021dec.onnx")

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""): h.update(b)
    return h.hexdigest()

def tiles(h, w, cols, rows):
    out = []
    for r in range(rows):
        for c in range(cols):
            x0 = round(c * w / cols); x1 = round((c + 1) * w / cols)
            y0 = round(r * h / rows); y1 = round((r + 1) * h / rows)
            if c: x0 -= 32  # 32-px overlap like face_probe tiles
            if r: y0 -= 32
            out.append((x0, y0, x1, y1))
    return out

def detect_pass(img, grid, thr, with_vec=False):
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN.create(DEF, "", (64, 64), float(thr), 0.3, 5000)
    sf = cv2.FaceRecognizerSF.create(SFM, "") if with_vec else None
    raw, faces, vecs = 0, [], []
    t0 = time.perf_counter()
    for (x0, y0, x1, y1) in tiles(h, w, *grid):
        tile = np.ascontiguousarray(img[y0:y1, x0:x1])
        det.setInputSize((x1 - x0, y1 - y0))
        _, rows_out = det.detect(tile)
        if rows_out is None: continue
        for r in rows_out:
            raw += 1
            if with_vec:
                vecs.append(sf.feature(sf.alignCrop(tile, r)).flatten())
            faces.append((r[0] + x0, r[1] + y0, r[2], r[3], r[4]))
    det_ms = time.perf_counter() - t0
    feat_ms = 0.0
    if with_vec:
        # separate timing pass for per-face embed cost on the same tile grid
        sf2 = cv2.FaceRecognizerSF.create(SFM, "")
        crops = []
        t1 = time.perf_counter()
        for (x0, y0, x1, y1) in tiles(h, w, *grid):
            tile = np.ascontiguousarray(img[y0:y1, x0:x1])
            det.setInputSize((x1 - x0, y1 - y0))
            _, rows_out = det.detect(tile)
            if rows_out is None: continue
            for r in rows_out:
                crops.append(sf2.alignCrop(tile, r))
        feats = [sf2.feature(c).flatten() for c in crops]
        feat_ms = time.perf_counter() - t1
        return raw, faces, det_ms, len(crops), feat_ms, feats
    return raw, faces, det_ms, 0, 0.0, None

png = cv2.imread(args.png)          # 8-bit BGR like face_probe
cap = cv2.VideoCapture(args.mp4)
ok, mp4 = cap.read(); cap.release()

out = {"label": "visvenv-baseline-2026-11-11",
       "env": {"python": sys.version.split()[0], "cv2": cv2.__version__, "numpy": np.__version__,
               "platform": " ".join(__import__("platform").uname()[:4])},
       "fixtures": {"png": {"path_sha256": sha(args.png), "shape": list(png.shape)},
                    "mp4_h264": {"path_sha256": sha(args.mp4), "decoded": bool(ok), "shape": list(mp4.shape) if ok else None}},
       "import_cv2_s": round(t_import, 4),
       "detect": [], "whole_frame_050": None, "embed": None, "match_probe": None, "cosine": None, "surface": None}

t0 = time.perf_counter()
_ = cv2.FaceDetectorYN.create(DEF, "", (64, 64), 0.5, 0.3, 5000)
out["det_model_init_s"] = round(time.perf_counter() - t0, 4)
t0 = time.perf_counter()
_ = cv2.FaceRecognizerSF.create(SFM, "")
out["sface_model_init_s"] = round(time.perf_counter() - t0, 4)

for fname, img in (("png", png), ("mp4_h264", mp4)):
    for grid in ((2, 2), (4, 3), (4, 4), (8, 4)):
        for thr in (0.9, 0.75, 0.6, 0.5, 0.45, 0.3):
            raw, faces, ms, *_ = detect_pass(img, grid, thr)
            # merged count: dedupe boxes closer than 50% min-side (same spirit as face_probe)
            merged = 0
            kept = []
            for (x, y, w, h, s) in sorted(faces, key=lambda f: -f[4]):
                if all(max(w, h) * 0.5 < np.hypot(x - kx, y - ky) for (kx, ky, kw, kh, _) in kept):
                    kept.append((x, y, w, h, s)); merged += 1
            out["detect"].append({"fixture": fname, "grid": f"{grid[0]}x{grid[1]}", "thr": thr,
                                  "raw": raw, "merged": merged, "det_s": round(ms, 3)})

# whole-frame (untiled) reference at 0.5 — known-poor at 8K, keep the number
raw, faces, ms, *_ = detect_pass(png, (1, 1), 0.5)
out["whole_frame_050"] = {"raw": raw, "det_s": round(ms, 3)}

# embed pass + cosine stats on the canonical 4x3 @ 0.5 (png)
raw, faces, det_ms, ncrops, feat_ms, feats = detect_pass(png, (4, 3), 0.5, with_vec=True)
V = np.stack(feats)
norms = np.linalg.norm(V, axis=1)
Vn = V / norms[:, None]
S = Vn @ Vn.T
iupper = np.triu_indices(len(V), 1)
pair = S[iupper]
if not feats:
    json.dump(out, open(args.out, "w"), indent=1); print("no crops in embed pass; partial", args.out); sys.exit(0)
out["embed"] = {"crops": ncrops, "feat_ms_total": round(feat_ms, 3),
                "ms_per_face": round(feat_ms / ncrops, 3) if ncrops else None,
                "det_ms_same_pass": round(det_ms, 3),
                "embedding_norm_median": round(float(np.median(norms)), 3)}
out["cosine"] = {"pairs": int(pair.size), "median": round(float(np.median(pair)), 4),
                 "p95": round(float(np.percentile(pair, 95)), 4),
                 "mean_self": round(float(np.mean(np.diag(S))), 4)}

# match()-in-place probe: 5.0.0.93 L2-normalises the PASSED vectors in place (fixed upstream in 5.1.0)
sf = cv2.FaceRecognizerSF.create(SFM, "")
a, b = feats[0].copy(), feats[1].copy()
na0, nb0 = float(np.linalg.norm(a)), float(np.linalg.norm(b))
d_cos = sf.match(a, b, cv2.FaceRecognizerSF_FR_COSINE)
na1, nb1 = float(np.linalg.norm(a)), float(np.linalg.norm(b))
out["match_probe"] = {"cosine_dist": round(float(d_cos), 4),
                      "norm_a_before": round(na0, 3), "norm_a_after": round(na1, 3),
                      "norm_b_before": round(nb0, 3), "norm_b_after": round(nb1, 3),
                      "in_place_mutation": bool(abs(na1 - na0) > 0.01 or abs(nb1 - nb0) > 0.01)}

# API surface presence relevant to the 5.1.0 changelog
out["surface"] = {
    "cv2.setLogLevel_present": hasattr(cv2, "setLogLevel"),
    "cv2.utils.logging_present": hasattr(cv2, "utils") and hasattr(cv2.utils, "logging"),
    "readNetFromTensorflow_present": hasattr(cv2.dnn, "readNetFromTensorflow"),
    "readNetFromCaffe_present": hasattr(cv2.dnn, "readNetFromCaffe"),
    "readNetFromONNX_present": hasattr(cv2.dnn, "readNetFromONNX"),
    "FaceDetectorYN_present": hasattr(cv2, "FaceDetectorYN"),
    "FaceRecognizerSF_present": hasattr(cv2, "FaceRecognizerSF"),
}

json.dump(out, open(args.out, "w"), indent=1)
print("wrote", args.out)
