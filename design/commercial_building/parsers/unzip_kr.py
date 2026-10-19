# -*- coding: utf-8 -*-
"""한글 파일명이 CP949 로 들어간 zip 을 안전하게 푼다.

zipfile 은 UTF-8 플래그(0x800)가 없으면 이름을 cp437 로 읽는다. 한국에서 만든 zip 은
실제로는 cp949 라서 그 바이트를 되돌려 다시 디코딩해야 한다.
경로 탈출(zip slip)은 대상 디렉터리 밖으로 나가는 항목을 버려서 막는다.
"""
import os, sys, zipfile

def real_name(info):
    if info.flag_bits & 0x800:          # 이미 UTF-8
        return info.filename
    raw = info.filename.encode("cp437", errors="replace")
    for enc in ("cp949", "utf-8"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return info.filename

def main(dest, zips):
    dest = os.path.realpath(dest)
    os.makedirs(dest, exist_ok=True)
    n_ok = n_skip = 0
    for zp in zips:
        with zipfile.ZipFile(zp) as z:
            for info in z.infolist():
                name = real_name(info)
                out = os.path.realpath(os.path.join(dest, name))
                if not out.startswith(dest + os.sep):
                    print("건너뜀(경로 탈출):", name); n_skip += 1; continue
                if info.is_dir():
                    os.makedirs(out, exist_ok=True); continue
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with z.open(info) as src, open(out, "wb") as dst:
                    while True:
                        buf = src.read(1 << 20)
                        if not buf:
                            break
                        dst.write(buf)
                n_ok += 1
    print(f"풀린 파일 {n_ok}개 / 건너뜀 {n_skip}개")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
