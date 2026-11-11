import time
t0=time.perf_counter()
import cv2, numpy as np, os
img = cv2.imread(os.path.join(os.path.dirname(__file__), "fixture_f240.png"))
h,w = img.shape[:2]
DEF = os.path.expanduser("~/resolve-vision-models/face_detection_yunet_2023mar.onnx")
det = cv2.FaceDetectorYN.create(DEF, "", (64,64), 0.5, 0.3, 5000)
n=0
for r_ in range(3):
    for c_ in range(4):
        x0=round(c_*w/4)-(32 if c_ else 0); x1=round((c_+1)*w/4)
        y0=round(r_*h/3)-(32 if r_ else 0); y1=round((r_+1)*h/3)
        t=np.ascontiguousarray(img[y0:y1,x0:x1])
        det.setInputSize((x1-x0,y1-y0))
        _,rows=det.detect(t)
        n += 0 if rows is None else len(rows)
print(f"raw={n} total_s={time.perf_counter()-t0:.3f}")
