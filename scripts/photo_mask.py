# -*- coding: utf-8 -*-
"""매물 사진 자동 모자이크 — 사람 얼굴 + 글자(간판·표지) 영역.

비공개매물 사진은 중개사가 현장에서 찍어 올린다. 지나가는 행인 얼굴, 간판·차량번호처럼
글자가 박힌 영역이 그대로 올라가면 초상권·개인정보 문제가 된다. 업로드 즉시 서버에서
검출→모자이크 하고 **원본은 저장하지 않는다**(마스킹본만 디스크에 남긴다).

검출기(둘 다 opencv_zoo, models/ 에 동봉):
  · 얼굴: YuNet(face_detection_yunet_2023mar, 228KB) — 작고 빠르고 정확.
  · 글자: PP-OCRv3 detection(cn, 2.4MB) — 한글·한자 간판 포함 장면 텍스트에 강함.
    인식(OCR)이 아니라 **영역 검출만** 한다. 글자 내용은 읽지도, 저장하지도 않는다.

정책: 프라이버시 보호가 목적이므로 **과검출 쪽으로 기운다**(놓치는 것보다 더 가리는 게 안전).
검출 실패·모델 부재 시에는 예외를 삼키지 않고 호출측에 알린다 — 조용히 원본이 올라가면 안 된다.
"""
from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np

MODELS = Path(__file__).resolve().parent.parent / "models"
YUNET = MODELS / "yunet.onnx"
PPOCR = MODELS / "text_ppocr.onnx"

FACE_PAD = 0.28      # 얼굴 박스 확장 비율 — 머리카락·턱선까지 덮어 식별 가능성을 줄인다
# 글자는 검출 박스가 실제 글자보다 짧게 잡히는 경향이 있어(실측: 전화번호 윗부분이 노출됨)
# 세로를 더 넉넉히 준다. 프라이버시 목적상 조금 더 가리는 쪽이 안전.
TEXT_PAD_X = 0.14
TEXT_PAD_Y = 0.42
BLOCKS = 12          # 모자이크 격자 수(작을수록 굵게 뭉갬)
MAX_SIDE = 2400      # 초대형 사진은 축소 후 처리(속도·메모리)


class MaskError(RuntimeError):
    pass


def _pixelate(img, x0, y0, x1, y1) -> None:
    """영역을 격자 평균색으로 뭉갠다(복원 불가). 제자리 수정."""
    h, w = img.shape[:2]
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(w, int(x1)), min(h, int(y1))
    if x1 - x0 < 2 or y1 - y0 < 2:
        return
    import cv2
    roi = img[y0:y1, x0:x1]
    bw = max(1, (x1 - x0) // BLOCKS)
    bh = max(1, (y1 - y0) // BLOCKS)
    small = cv2.resize(roi, (max(1, (x1 - x0) // bw), max(1, (y1 - y0) // bh)),
                       interpolation=cv2.INTER_LINEAR)
    img[y0:y1, x0:x1] = cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_NEAREST)


def _expand(x, y, w, h, padx, pady=None):
    dx, dy = w * padx, h * (padx if pady is None else pady)
    return x - dx, y - dy, x + w + dx, y + h + dy


def detect_faces(img) -> list:
    """[(x,y,w,h), ...]. 여러 배율로 훑어 작은 얼굴도 잡는다."""
    import cv2
    if not YUNET.exists():
        raise MaskError(f"얼굴 모델 없음: {YUNET}")
    h, w = img.shape[:2]
    out = []
    det = cv2.FaceDetectorYN.create(str(YUNET), "", (w, h), 0.55, 0.3, 5000)
    det.setInputSize((w, h))
    _, faces = det.detect(img)
    if faces is not None:
        out += [tuple(f[:4]) for f in faces]
    # 작은 얼굴 보강 — 2배 확대해 한 번 더(원좌표로 환산)
    if max(h, w) < 1600:
        big = cv2.resize(img, (w * 2, h * 2), interpolation=cv2.INTER_LINEAR)
        det2 = cv2.FaceDetectorYN.create(str(YUNET), "", (w * 2, h * 2), 0.6, 0.3, 5000)
        _, f2 = det2.detect(big)
        if f2 is not None:
            out += [(f[0] / 2, f[1] / 2, f[2] / 2, f[3] / 2) for f in f2]
    return out


def _text_pass(img, scale: float) -> list:
    """한 배율에서 글자 영역 검출 → 원본 좌표계 [(x0,y0,x1,y1)]."""
    import cv2
    h, w = img.shape[:2]
    if scale != 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LINEAR)
    ih, iw = img.shape[:2]
    tw, th = max(32, (iw // 32) * 32), max(32, (ih // 32) * 32)
    m = cv2.dnn.TextDetectionModel_DB(str(PPOCR))
    # 임계값을 낮춰 작고 흐린 글자까지 잡는다(작은 표지판 누락 실측 반영)
    m.setBinaryThreshold(0.18).setPolygonThreshold(0.4).setMaxCandidates(600).setUnclipRatio(2.4)
    m.setInputParams(1 / 255.0, (tw, th), (122.68, 116.78, 103.94), True)
    boxes, _ = m.detect(img)
    sx, sy = (iw / tw) / scale, (ih / th) / scale
    out = []
    for quad in boxes or []:
        q = np.array(quad, dtype=float)
        out.append((q[:, 0].min() * sx, q[:, 1].min() * sy,
                    q[:, 0].max() * sx, q[:, 1].max() * sy))
    return out


def detect_text(img) -> list:
    """[(x0,y0,x1,y1), ...] 글자 영역. 내용은 읽지 않는다.
    원본 + 2배 확대 2패스 — 멀리 있는 작은 간판이 1패스에서 누락되던 것을 보완."""
    if not PPOCR.exists():
        raise MaskError(f"글자 모델 없음: {PPOCR}")
    h, w = img.shape[:2]
    out = _text_pass(img, 1.0)
    if max(h, w) <= 1600:
        out += _text_pass(img, 2.0)
    return out


def mask_image(data: bytes, do_face=True, do_text=True) -> tuple[bytes, dict]:
    """이미지 바이트 → (모자이크된 JPEG 바이트, 통계). 원본은 반환하지 않는다."""
    import cv2
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise MaskError("이미지를 해석할 수 없습니다")
    h, w = img.shape[:2]
    if max(h, w) > MAX_SIDE:                      # 과대 이미지 축소(EXIF 회전은 아래에서 처리)
        s = MAX_SIDE / max(h, w)
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    nf = nt = 0
    if do_face:
        for (x, y, fw, fh) in detect_faces(img):
            _pixelate(img, *_expand(x, y, fw, fh, FACE_PAD))
            nf += 1
    if do_text:
        for (x0, y0, x1, y1) in detect_text(img):
            _pixelate(img, *_expand(x0, y0, x1 - x0, y1 - y0, TEXT_PAD_X, TEXT_PAD_Y))
            nt += 1
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise MaskError("인코딩 실패")
    return enc.tobytes(), {"faces": nf, "texts": nt,
                           "w": int(img.shape[1]), "h": int(img.shape[0])}


def mask_rects(data: bytes, rects: list) -> tuple[bytes, int]:
    """사용자가 직접 지정한 영역을 추가로 모자이크(수동 보정).

    rects 는 **상대좌표(0~1)** [{x,y,w,h}, ...] — 화면 표시 크기·기기 해상도와 무관하게
    같은 지점을 가리키게 한다. 자동 검출이 놓친 작은 글자·측면 얼굴을 사람이 덧칠하는 용도.
    이미 마스킹된 파일 위에 덧입히므로 결과는 되돌릴 수 없다(원본은 애초에 없다).
    """
    import cv2
    arr = np.frombuffer(data, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        raise MaskError("이미지를 해석할 수 없습니다")
    h, w = img.shape[:2]
    n = 0
    for r in rects or []:
        try:
            x, y = float(r.get("x", 0)), float(r.get("y", 0))
            rw, rh = float(r.get("w", 0)), float(r.get("h", 0))
        except (TypeError, ValueError, AttributeError):
            continue
        if rw <= 0 or rh <= 0:
            continue
        _pixelate(img, x * w, y * h, (x + rw) * w, (y + rh) * h)
        n += 1
    ok, enc = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        raise MaskError("인코딩 실패")
    return enc.tobytes(), n


if __name__ == "__main__":
    import sys
    src = sys.argv[1]
    out, st = mask_image(Path(src).read_bytes())
    dst = sys.argv[2] if len(sys.argv) > 2 else src.rsplit(".", 1)[0] + "_masked.jpg"
    Path(dst).write_bytes(out)
    print(f"{dst}  얼굴 {st['faces']} · 글자 {st['texts']} · {st['w']}x{st['h']}")
