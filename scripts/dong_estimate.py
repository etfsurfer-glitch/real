"""등기 전 거래 동(棟) 추정 — 일일 배치·재학습·시드.

  --daily [--days 150]     최근 N일 거래를 대상으로 ① 등기 올라온 매매 대조(정답 기록·라벨)
                           ② 새 거래 예비 추정 ③ 계약 +45일 거래 최종 추정(고정) ④ 일별 로그
                           ⑤ 일요일이면 재학습(개선 시에만 승격). 메인 DB 는 읽기만.
  --retrain [--force]      학습 로그(dong_est_feat)로 재학습.
  --seed-npz FILE          백테스트 특징 캐시(oof_cache.npz: Xs, ys, Gs, oof)로 학습 로그 시드 + v1 학습.
  --stats                  모델·누적 정확도 요약 출력.

옵션: --db 메인 DB 경로(기본 settings.local_db_path) · --store 결과 DB(기본 data/dong_estimates.sqlite)
      --archive 아카이브 매물 DB(있으면 90일 넘은 매물까지 단서로 사용) · --from YYYY-MM-DD 추정 시작일 강제
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from collector.dong_estimate import (  # noqa: E402
    FEAT, FINAL_AFTER_DAYS, KST, THRESH, WINDOW_BEFORE, Context, Deal, Est, Store, build_features, displayable,
    eval_at, fit, ndong, oof_scores, pdate, rgst_date, score, today_kst,
)


def _tg(text: str) -> None:
    try:
        from scripts.tg_notify import tg_send
        tg_send(text)
    except Exception:
        pass


def _ro(path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    return c


def _now() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


# ── 시드(백테스트 특징 → 학습 로그 + v1) ───────────────────────────────────
def seed_npz(store: Store, npz: Path) -> None:
    z = np.load(npz)
    Xs, ys, Gs, oof = z["Xs"], z["ys"], z["Gs"], z["oof"]
    assert Xs.shape[1] == len(FEAT), f"특징 수 불일치 {Xs.shape[1]} vs {len(FEAT)}"
    print(f"seed rows={len(Xs):,} deals={len(set(Gs.tolist())):,}")
    # 학습 로그 — 후보 이름은 없으니 그룹 내 순번. 라벨은 y.
    rows, pos = [], Counter()
    for i in range(len(Xs)):
        g = int(Gs[i])
        rows.append((f"boot:{g}", str(pos[g]), Xs[i].tolist(), int(ys[i]), "boot"))
        pos[g] += 1
    store.put_feats(rows)
    # OOF 지표(규칙 포함) — 거래는 전부 매매(A1)
    n_deals = int(Gs.max()) + 1
    deals = [Deal(f"boot:{g}", "A1", "", date(2026, 1, 1), 0, 0, 0, 0) for g in range(n_deals)]
    cand_of = {g: [str(k) for k in range(pos[g])] for g in pos}
    ncand = {g: pos[g] for g in pos}
    ests = score(None, Xs, Gs, cand_of, ncand, y=ys, scores=oof)
    m = eval_at(ests, deals, THRESH)
    m["n_rows"] = len(Xs)
    print(f"OOF: 전체 {m['acc_all']*100:.1f}% · 문턱 {THRESH} 커버 {m['cov']*100:.1f}% · 그 정확도 {m['acc_shown']*100:.1f}%")
    model = fit(Xs, ys)
    ver = store.save_model(model, m, f"seed from {npz.name} (백테스트 6/10~10/15 등기 중개매매)", promote=True)
    store.commit()
    print(f"model v{ver} saved+active")


# ── 재학습 ───────────────────────────────────────────────────────────────
def retrain(store: Store, force: bool = False) -> str:
    X, y, G = store.training_matrix()
    n_deals = len(set(G.tolist()))
    cur = store.c.execute("SELECT ver, n_deals, oof_acc_th, oof_cov_th FROM dong_model WHERE active=1 "
                          "ORDER BY ver DESC LIMIT 1").fetchone()
    if cur and not force and n_deals < (cur[1] or 0) + 1000:
        return f"재학습 생략: 라벨 거래 {n_deals:,} (활성 v{cur[0]} 학습 {cur[1]:,} + 1,000 미만)"
    if n_deals < 5000:
        return f"재학습 생략: 라벨 거래 {n_deals:,} < 5,000"
    t0 = time.time()
    oof = oof_scores(X, y, G)
    # 그룹키→연속 인덱스
    keys = {k: i for i, k in enumerate(dict.fromkeys(G.tolist()))}
    Gi = np.array([keys[k] for k in G])
    pos: Counter = Counter()
    cand_of: dict[int, list[str]] = defaultdict(list)
    for g in Gi:
        cand_of[int(g)].append(str(pos[int(g)]))
        pos[int(g)] += 1
    deals = [Deal(k, "A1", "", date(2026, 1, 1), 0, 0, 0, 0) for k in keys]
    ests = score(None, X, Gi, cand_of, dict(pos), y=y, scores=oof)
    m = eval_at(ests, deals, THRESH)
    m["n_rows"] = len(X)
    promote = True
    why = "첫 모델"
    if cur:
        acc0, cov0 = cur[2] or 0, cur[3] or 0
        promote = m["acc_shown"] >= acc0 - 0.005 and m["cov"] >= cov0 - 0.02
        why = (f"v{cur[0]} 대비 정확도 {acc0*100:.1f}→{m['acc_shown']*100:.1f}% 커버 {cov0*100:.1f}→{m['cov']*100:.1f}%"
               + (" 승격" if promote else " 보류(개선 없음)"))
    model = fit(X, y)
    ver = store.save_model(model, m, why, promote)
    store.commit()
    msg = (f"동 추정 재학습 v{ver}: 라벨 거래 {n_deals:,}·행 {len(X):,} · OOF 전체 {m['acc_all']*100:.1f}% · "
           f"문턱{THRESH} 커버 {m['cov']*100:.1f}% 정확도 {m['acc_shown']*100:.1f}% · {why} ({time.time()-t0:.0f}s)")
    return msg


# ── 일일 ─────────────────────────────────────────────────────────────────
def load_deals(main: sqlite3.Connection, since: date) -> list[Deal]:
    out: list[Deal] = []
    q = ("SELECT deal_id, matched_complex_no, deal_ymd, deal_amount, floor, excl_use_ar, dealing_gbn, "
         "json_extract(raw,'$.aptDong'), json_extract(raw,'$.rgstDate') FROM transactions "
         "WHERE deal_ymd >= ? AND is_cancelled=0 AND matched_complex_no IS NOT NULL "
         "AND floor IS NOT NULL AND excl_use_ar IS NOT NULL")
    for did, c, ymd, amt, fl, ex, gbn, dong, rg in main.execute(q, (since.isoformat(),)):
        dd = pdate(ymd)
        if not dd:
            continue
        truth = ndong(dong) if (dong and rgst_date(rg)) else None
        out.append(Deal(f"A1:{did}", "A1", c, dd, int(amt or 0), 0, int(fl), round(float(ex)), None, truth, gbn))
    q = ("SELECT rental_id, matched_complex_no, deal_ymd, deposit, monthly_rent, floor, excl_use_ar, contract_type "
         "FROM rentals WHERE deal_ymd >= ? AND matched_complex_no IS NOT NULL AND floor IS NOT NULL "
         "AND excl_use_ar IS NOT NULL")
    for rid, c, ymd, dep, mr, fl, ex, ct in main.execute(q, (since.isoformat(),)):
        dd = pdate(ymd)
        if not dd:
            continue
        tt = "B2" if (mr or 0) > 0 else "B1"
        out.append(Deal(f"{tt}:{rid}", tt, c, dd, int(dep or 0), int(mr or 0), int(fl), round(float(ex)), (ct or "").strip()))
    return out


def daily(store: Store, main: sqlite3.Connection, archive: sqlite3.Connection | None, days: int,
          force_from: date | None, dry: bool) -> None:
    t0 = time.time()
    today = today_kst()
    now = _now()
    since = today - timedelta(days=days)
    # 단서(내려간 매물)가 남아 있는 구간만 추정 가능 — 핫 DB 는 90일 보관.
    if force_from:
        est_from = force_from
    elif archive is not None:
        est_from = since
    else:
        mn = main.execute("SELECT MIN(last_seen_date) FROM articles WHERE is_active=0").fetchone()[0]
        est_from = max(since, (pdate(mn) or since) + timedelta(days=WINDOW_BEFORE))
    final_cut = today - timedelta(days=FINAL_AFTER_DAYS)
    train_cut = today - timedelta(days=10)      # 등기분 학습행: 매물 창(+10일)이 닫힌 뒤
    ver, model = store.active_model()
    if model is None:
        print("활성 모델 없음 — --seed-npz 또는 --retrain 먼저")
        return
    deals = load_deals(main, since)
    print(f"deals since {since}: {len(deals):,} · est_from {est_from} · final_cut {final_cut} · model v{ver}")
    ex = store.existing(d.key for d in deals)

    confirm: list[tuple[Deal, str]] = []           # 등기 올라온 추정 거래
    todo: list[tuple[Deal, str]] = []               # (거래, 패스) 특징 계산 대상: est | final | train
    for d in deals:
        st = ex.get(d.key)
        if d.trade == "A1" and d.truth:
            if st and st[0] in ("est", "final", "none"):
                confirm.append((d, d.truth))
            elif not st and est_from <= d.when <= train_cut and d.dealing_gbn != "직거래":
                todo.append((d, "train"))
            continue
        if d.when < est_from:
            continue
        if not st:
            todo.append((d, "final" if d.when <= final_cut else "est"))
        elif st[0] in ("est", "none") and d.when <= final_cut:
            todo.append((d, "final"))

    cnt: dict[str, Counter] = defaultdict(Counter)
    # ① 등기 대조
    for d, actual in confirm:
        correct, pre_reg, shown = store.confirm(d.key, actual, now)
        store.label_feats(d.key, actual)
        k = cnt["A1"]
        k["n_confirmed"] += 1
        k["n_correct"] += correct or 0
        if pre_reg and shown:
            k["n_conf_shown"] += 1
            k["n_conf_shown_correct"] += correct or 0
    print(f"confirm {len(confirm):,} · todo {Counter(p for _, p in todo)}")

    # ②③ 특징·추정 — 단지 묶음으로 메모리 제한
    by_c: dict[str, list[tuple[Deal, str]]] = defaultdict(list)
    for d, p in todo:
        by_c[d.complex_no].append((d, p))
    complexes = sorted(by_c)
    CH = 400
    done = 0
    for i in range(0, len(complexes), CH):
        chunk = complexes[i:i + CH]
        ctx = Context()
        ctx.load_hist(main, chunk)
        ctx.load_articles(main, chunk, archive)
        items = [it for c in chunk for it in by_c[c]]
        dl = [d for d, _ in items]
        X, y, G, cand_of, ncand = build_features(dl, ctx)
        ests = score(model, X, G, cand_of, ncand, y=y) if len(X) else {}
        rows_by_deal: dict[int, list[int]] = defaultdict(list)
        for ri, g in enumerate(G):
            rows_by_deal[int(g)].append(ri)
        for j, (d, p) in enumerate(items):
            e = ests.get(j)
            k = cnt[d.trade]
            if p == "train":
                # 등기 완료분: 학습 로그 + confirmed 기록(표시 안 함)
                store.upsert_est(d, e, "confirmed", ver, False, now, final=True)
                store.c.execute("UPDATE dong_est SET actual_dong=?, actual_at=?, correct=? WHERE deal_key=?",
                                (d.truth, now, int(e.top1 == d.truth) if e else 0, d.key))
                if e:
                    store.put_feats((d.key, cand_of[j][q], X[ri], int(cand_of[j][q] == d.truth), "final")
                                    for q, ri in enumerate(rows_by_deal[j]))
                k["n_train"] += 1
                continue
            if e is None:
                store.upsert_est(d, None, "none" if p == "est" else "final", ver, False, now, final=(p == "final"))
                k["n_" + p] += 1
                continue
            shown = displayable(d, e)
            store.upsert_est(d, e, p, ver, shown, now, final=(p == "final"))
            if p == "final" and d.trade == "A1":
                store.put_feats((d.key, cand_of[j][q], X[ri], None, "final") for q, ri in enumerate(rows_by_deal[j]))
            k["n_" + p] += 1
            k["n_shown"] += int(shown)
        done += len(items)
        if not dry:
            store.commit()
        print(f"  {min(i+CH, len(complexes)):,}/{len(complexes):,} complexes · {done:,} deals · {time.time()-t0:.0f}s")

    # ④ 일별 로그
    for tt, k in cnt.items():
        store.log_day(today.isoformat(), tt, **{x: k[x] for x in k if x in (
            "n_new", "n_final", "n_shown", "n_confirmed", "n_correct", "n_conf_shown", "n_conf_shown_correct")},
            n_new=k["n_est"])
    if dry:
        store.c.rollback()
        print("dry-run: rollback")
    else:
        store.commit()
    for tt in ("A1", "B1", "B2"):
        k = cnt[tt]
        print(f"[{tt}] 예비 {k['n_est']:,} · 최종 {k['n_final']:,} · 표시 {k['n_shown']:,} · 학습행 {k['n_train']:,} · "
              f"등기대조 {k['n_confirmed']:,}(정답 {k['n_correct']:,}; 표시중이던 {k['n_conf_shown']:,} 중 정답 {k['n_conf_shown_correct']:,})")

    # ⑤ 주간 재학습(일요일)
    if not dry and today.weekday() == 6:
        msg = retrain(store)
        print(msg)
        if msg.startswith("동 추정 재학습"):
            _tg(msg)
    print(f"done {time.time()-t0:.0f}s")


def stats(store: Store) -> None:
    for r in store.c.execute("SELECT ver, trained_at, n_deals, n_rows, oof_acc, oof_acc_th, oof_cov_th, active, note FROM dong_model ORDER BY ver"):
        print(f"v{r[0]} {r[1]} deals={r[2]:,} rows={r[3]:,} oof={r[4]*100:.1f}% th_acc={r[5]*100:.1f}% th_cov={r[6]*100:.1f}% "
              f"{'ACTIVE' if r[7] else ''} {r[8]}")
    print("\n상태별:")
    for r in store.c.execute("SELECT trade_type, status, count(*), sum(shown) FROM dong_est GROUP BY 1,2 ORDER BY 1,2"):
        print(f"  {r[0]} {r[1]:<9} {r[2]:>8,}  표시 {r[3] or 0:,}")
    print("\n등기 대조(추정이 먼저 있었던 매매):")
    r = store.c.execute("SELECT count(*), sum(correct), sum(shown_before_reg), sum(CASE WHEN shown_before_reg=1 THEN correct END) "
                        "FROM dong_est WHERE status='confirmed' AND pre_reg=1").fetchone()
    if r and r[0]:
        print(f"  전체 {r[0]:,} 정답 {(r[1] or 0)/r[0]*100:.1f}% · 표시분 {r[2] or 0:,} 정답 {((r[3] or 0)/(r[2] or 1))*100:.1f}%")
    print("\n최근 일별 로그:")
    for r in store.c.execute("SELECT * FROM dong_daily_log ORDER BY day DESC, trade_type LIMIT 21"):
        print("  ", r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--daily", action="store_true")
    ap.add_argument("--days", type=int, default=150)
    ap.add_argument("--retrain", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--seed-npz", type=Path)
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--db", type=Path)
    ap.add_argument("--store", type=Path)
    ap.add_argument("--archive", type=Path)
    ap.add_argument("--from", dest="from_", type=str)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    if a.db:
        db = a.db
    else:
        from collector.config import settings
        db = settings.local_db_path
    store = Store(a.store or (Path(db).parent / "dong_estimates.sqlite"))

    if a.seed_npz:
        seed_npz(store, a.seed_npz)
    if a.retrain:
        print(retrain(store, a.force))
    if a.daily:
        main_c = _ro(Path(db))
        arc = _ro(a.archive) if a.archive else None
        daily(store, main_c, arc, a.days, pdate(a.from_) if a.from_ else None, a.dry_run)
    if a.stats:
        stats(store)


if __name__ == "__main__":
    main()
