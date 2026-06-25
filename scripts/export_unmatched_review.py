"""매칭 안 된 Naver realtor + vworld 후보를 카테고리별로 정리한 리뷰 파일 생성.

카테고리:
  A. Naver 정보 없음 (naver_realtors fetch 모두 실패)
  B. Naver regno 없음
  C. Naver regno 옛/이상 포맷 (vworld 매핑 안 됨)
  D. Naver regno 표준이지만 vworld 미등록
  E. 기타
"""
from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.config import settings  # noqa: E402
from collector.realtor_matching import addr_sgg_key, extract_dong, normalize_regno  # noqa: E402


def open_db():
    c = sqlite3.connect(settings.local_db_path, timeout=30.0)
    c.row_factory = sqlite3.Row
    return c


def digits(s):
    return re.sub(r"\D+", "", s) if s else ""


def categorize(nr_row):
    """returns (code, label)"""
    if nr_row is None:
        return "A", "Naver 정보 없음 (article 만료 또는 fetch 실패)"
    regno = (nr_row["establish_registration_no"] or "").strip()
    if not regno:
        return "B", "Naver 등록번호 없음"
    # 옛/이상 포맷: standardize 결과가 표준 패턴이 아니면
    nr_norm = normalize_regno(regno)
    std_re = re.compile(r"^\d{4,5}-\d{4}-\d{4,6}(?:-\d{3})?$")
    if not nr_norm or not std_re.match(nr_norm):
        return "C", f"옛/이상 포맷 등록번호 ({regno})"
    return "D", "표준 포맷이지만 vworld 미등록 (폐업/이전 추정)"


def find_candidates(conn, nr_row):
    """vworld 후보 추정 — rep, phone, addr_sgg+name 매칭"""
    if nr_row is None:
        return {"by_rep": [], "by_phone": [], "by_addr": []}
    cands = {"by_rep": [], "by_phone": [], "by_addr": []}
    rep = nr_row["representative_name"]
    if rep:
        rows = conn.execute(
            "SELECT sys_regno, sgg_cd, ra_regno, business_name, representative, address, phone "
            "FROM vworld_brokers WHERE representative=? LIMIT 5",
            (rep,),
        ).fetchall()
        cands["by_rep"] = rows
    # phone substring
    for fld in ("representative_tel_no", "cell_phone_no"):
        ph = digits(nr_row[fld]) if nr_row[fld] else ""
        if len(ph) < 9:
            continue
        rows = conn.execute(
            """
            SELECT sys_regno, sgg_cd, ra_regno, business_name, representative, address, phone
            FROM vworld_brokers
            WHERE phone IS NOT NULL
              AND REPLACE(REPLACE(REPLACE(REPLACE(phone, '-', ''), '.', ''), ' ', ''), '*', '') LIKE ?
            LIMIT 5
            """,
            (f"%{ph}%",),
        ).fetchall()
        cands["by_phone"].extend(rows)
    # addr+name fuzzy
    addr = nr_row["address"]
    if addr:
        sgg_key = addr_sgg_key(addr)
        dong = extract_dong(addr)
        if sgg_key and dong:
            # 동일 시·도+시군구+동에 있는 사무소 중 이름이 비슷한 거
            name = (nr_row["realtor_name"] or "").replace(" ", "")
            core = name[:6] if name else ""
            if core:
                # business_name LIKE %core%
                rows = conn.execute(
                    """
                    SELECT sys_regno, sgg_cd, ra_regno, business_name, representative, address, phone
                    FROM vworld_brokers
                    WHERE dong_name=? AND business_name LIKE ?
                    LIMIT 5
                    """,
                    (dong, f"%{core}%"),
                ).fetchall()
                cands["by_addr"] = rows
    return cands


def fmt_cand(c):
    return f"{c['business_name']} ({c['representative']}) / sgg={c['sgg_cd']} / ra={c['ra_regno']} / phone={c['phone']} / addr={(c['address'] or '')[:60]}"


def main():
    out_path = Path("D:/auto/naverreal/unmatched_review.md")
    conn = open_db()
    # match_type='none' realtors with total_listings (정렬 가능한 것)
    rows = conn.execute(
        """
        SELECT m.realtor_id, m.naver_name, m.primary_sgg_cd, m.total_listings
        FROM realtor_match m
        WHERE m.match_type='none'
        ORDER BY COALESCE(m.total_listings, 0) DESC
        """
    ).fetchall()

    # 분류 누적
    cat_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    cat_examples: dict[str, list] = {"A": [], "B": [], "C": [], "D": []}
    for r in rows:
        nr = conn.execute(
            "SELECT * FROM naver_realtors WHERE realtor_id=?", (r["realtor_id"],)
        ).fetchone()
        code, _ = categorize(nr)
        cat_counts[code] += 1
        # 카테고리별 상위 30건 (매물순)
        if len(cat_examples[code]) < 50:
            cat_examples[code].append((r, nr))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Naver 중개사 매칭 실패 리뷰\n\n")
        f.write(f"총 unmatched: {len(rows):,}\n\n")
        f.write("## 카테고리 분포\n\n")
        cat_labels = {
            "A": "Naver 정보 없음 (article 만료, fetch 실패)",
            "B": "Naver 등록번호 없음",
            "C": "옛/이상 포맷 등록번호 (vworld 매핑 불가)",
            "D": "표준 포맷이지만 vworld 미등록 (폐업/이전 추정)",
        }
        f.write("| 코드 | 분류 | 건수 |\n|------|------|------|\n")
        for k in "ABCD":
            f.write(f"| {k} | {cat_labels[k]} | {cat_counts[k]:,} |\n")
        f.write("\n")

        # 각 카테고리별 상위 50건 + vworld 후보
        for k in "ABCD":
            f.write(f"\n---\n\n## [{k}] {cat_labels[k]} — 상위 50건 (매물 많은 순)\n\n")
            for r, nr in cat_examples[k]:
                naver_name = r["naver_name"] or "(이름 없음)"
                f.write(f"### `{r['realtor_id']}` · {naver_name}  [매물 {r['total_listings'] or 0}건]\n\n")
                if nr:
                    f.write(f"- **Naver 측 정보**:\n")
                    f.write(f"    - 대표자: `{nr['representative_name']}`\n")
                    f.write(f"    - 등록번호: `{nr['establish_registration_no']}`\n")
                    f.write(f"    - 사무소 전화: `{nr['representative_tel_no']}`  핸드폰: `{nr['cell_phone_no']}`\n")
                    f.write(f"    - 주소: {nr['address']}\n")
                else:
                    f.write(f"- Naver 정보 없음 (article 만료)\n")
                    f.write(f"- primary_sgg: {r['primary_sgg_cd']}\n")
                cands = find_candidates(conn, nr)
                if any(cands.values()):
                    f.write(f"\n- **vworld 후보**:\n")
                    if cands["by_rep"]:
                        f.write(f"    - 같은 대표자 ({len(cands['by_rep'])}건):\n")
                        for c in cands["by_rep"][:5]:
                            f.write(f"        - {fmt_cand(c)}\n")
                    if cands["by_phone"]:
                        f.write(f"    - 같은 전화번호 ({len(cands['by_phone'])}건):\n")
                        for c in cands["by_phone"][:5]:
                            f.write(f"        - {fmt_cand(c)}\n")
                    if cands["by_addr"]:
                        f.write(f"    - 같은 동+이름 부분일치 ({len(cands['by_addr'])}건):\n")
                        for c in cands["by_addr"][:5]:
                            f.write(f"        - {fmt_cand(c)}\n")
                f.write("\n")

    print(f"wrote {out_path}")
    print(f"size: {out_path.stat().st_size:,} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
