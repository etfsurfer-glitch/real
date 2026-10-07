#!/usr/bin/env python3
"""주인대출(매도인 자금 제공) 광고 일별 추출 v3 — 2026-09-28 갱신.

v2 대비 수정: deal_or_warrant_price 는 **원 단위**다(만원 아님).
v2 는 만원으로 가정해 밴드가 전량 20억+ 로 뭉개져 있었다 — 원 기준으로 바로잡고
보고서와 같은 5구간(5/10/20/30억)으로 낸다.
출력: sf3_summary.csv(일별 분모·밴드) + sf3_candidates.csv(후보 원문 전수)
"""
import csv, glob, re, sys
import pyarrow.parquet as pq
import pandas as pd

FILES = sorted(glob.glob("/opt/koczip-archive/archive/listings/*/*/listings_*.parquet"))
COLS = ["article_no", "complex_no", "trade_type", "deal_or_warrant_price",
        "area_name", "article_feature_desc", "article_confirm_ymd", "snapshot_date", "same_addr_cnt"]

SUBJ = r"(?:매도인|매도자|집\s*주인|주인|소유자|소유주)"
FIN = r"(?:대출|융자|근저당|담보|대여)"
CAND = re.compile(SUBJ + r"[^가-힣]{0,2}[가-힣]{0,8}?" + FIN)
NEG = re.compile(r"(?:근저당|융자|대출)\s*(?:없음|없는|무|엑스|X|x)|무근저당|무융자|무대출|근저당X|근저당x")
EOK = 1e8  # 1억 = 1e8 원

sums, cands = [], []
for fp in FILES:
    day = fp.rsplit("_", 1)[1][:10]
    try:
        df = pq.read_table(fp, columns=COLS).to_pandas()
    except Exception as e:
        print(day, "READ FAIL", e, file=sys.stderr); continue
    sale = df[df["trade_type"].isin(["A1", "매매"])]
    n_sale = len(sale)
    desc = sale["article_feature_desc"].fillna("")
    has_desc = desc.str.len() > 0
    n_desc = int(has_desc.sum())
    e = pd.to_numeric(sale["deal_or_warrant_price"], errors="coerce").fillna(0) / EOK  # 억
    bands = [int(((e > 0) & (e < 5)).sum()), int(((e >= 5) & (e < 10)).sum()),
             int(((e >= 10) & (e < 20)).sum()), int(((e >= 20) & (e < 30)).sum()),
             int((e >= 30).sum())]
    d = desc[has_desc]
    n_neg = int(d.str.contains(NEG, regex=True).sum())
    pre = d[d.str.contains(r"매도|주인|소유", regex=True)]
    hits = pre[pre.str.contains(CAND, regex=True)]
    for idx in hits.index:
        r = sale.loc[idx]
        cands.append([day, r["article_no"], r["complex_no"], r["deal_or_warrant_price"],
                      r["area_name"], str(r["article_feature_desc"])[:300],
                      r["article_confirm_ymd"], r["same_addr_cnt"]])
    sums.append([day, n_sale, n_desc, *bands, n_neg, len(hits)])
    print(day, n_sale, n_desc, n_neg, len(hits), flush=True)

with open("/opt/koczip-archive/sf3_summary.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["day", "sale", "desc", "b_u5", "b_5_10", "b_10_20", "b_20_30", "b_30p", "neg", "cand"])
    w.writerows(sums)
with open("/opt/koczip-archive/sf3_candidates.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["day", "article_no", "complex_no", "price_won", "area", "desc", "confirm", "same_addr_cnt"])
    w.writerows(cands)
print("DONE", len(sums), "days,", len(cands), "candidates")
