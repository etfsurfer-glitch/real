"""등기 전 실거래의 동(棟) 추정.

국토부 실거래는 등기가 끝난 매매에만 동(aptDong)이 붙고(계약 후 보통 1~3개월), 전월세는
아예 없다. 같은 단지·같은 면적(±1㎡)·같은 층의 매물이 계약일 전후(−21~+10일)에 내려갔으면
그 매물의 동이 거래의 동일 가능성이 높다 — 이 단서들(층 일치·호가/보증금 비율·내려간 시점·
과거 등기 분포)을 특징으로 만들고, 등기 완료 매매를 정답으로 학습한 랭커가 후보 동마다 점수를
매긴다. 거래별 softmax 확신도가 THRESH 이상이면 "101동(추정)"으로 보여 주고, 등기가 올라와
실제 동이 생기면 그걸로 바뀐다(= (추정) 사라짐).

검증(2026-11-07, 6/10~10/15 등기 중개매매 81,812건, 5겹 그룹 OOF): 전체 78%, 확신도≥0.78
구간 커버 63%·정확도 95%, ≥0.75 커버 66%·94%.

규칙(백테스트로 확인):
  · 매물 단서가 하나도 없고 후보가 2동 이상 → 표시 안 함(사전확률만으로는 30%).
  · 전월세 갱신(및 계약유형 미상)은 광고를 안 하므로 단일동 단지만 표시.
  · 직거래도 단서가 없어 대부분 공란(규칙이 자연히 막음). 학습에서는 제외.

학습 로그: 매매는 최종 패스(계약 +45일)의 특징 벡터를 dong_est_feat 에 남기고, 등기가 올라오면
정답 라벨을 채운다 → 주간 재학습이 이 로그로 모델을 갱신(개선될 때만 승격). 일별 정확도는
dong_daily_log 에 쌓인다.

저장: 메인 DB는 읽기만. 결과는 별도 파일 data/dong_estimates.sqlite (API 가 deal_id 로 조인).
"""
from __future__ import annotations

import json
import math
import pickle
import re
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

# ── 설정 ────────────────────────────────────────────────────────────────
THRESH = 0.75                 # 표시 문턱(확신도). 사용자 결정 2026-11-07.
FINAL_AFTER_DAYS = 45         # 계약 +45일에 최종 추정(매물 내려감/잔존이 확정된 뒤) 후 고정
WINDOW_BEFORE, WINDOW_AFTER = 21, 10   # 매물 last_seen 이 계약일 기준 이 창 안이면 단서
TRADES = ("A1", "B1", "B2")   # 매매·전세·월세
KST = timezone(timedelta(hours=9))

FEAT = ["log_prior", "prior_n", "prior_share", "ncand", "best_w", "exact_w", "band_w", "price_w", "n_match",
        "n_exact", "min_abs_off", "consensus", "neg_alive", "neg_after", "height_ok", "dong_tx_n", "best_pr",
        "listing_dong_share"]
MODEL_PARAMS = dict(max_iter=300, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=40,
                    l2_regularization=1.0, random_state=0)

HAN = {"에이": "A", "비": "B", "씨": "C", "디": "D", "이": "E", "에프": "F", "지": "G", "에이치": "H",
       "가": "A", "나": "B", "다": "C", "라": "D", "마": "E", "바": "F", "사": "G", "아": "H"}


def today_kst() -> date:
    return datetime.now(KST).date()


def pdate(s: str | None) -> date | None:
    try:
        return date(int(s[:4]), int(s[5:7]), int(s[8:10]))  # type: ignore[index]
    except Exception:
        return None


def rgst_date(s: str | None) -> date | None:
    """등기일 'YY.MM.DD' → date."""
    m = re.match(r"(\d{2})\.(\d{2})\.(\d{2})", s or "")
    return date(2000 + int(m[1]), int(m[2]), int(m[3])) if m else None


def ndong(s: str | None) -> str | None:
    """동 이름 정규화 — 등기(aptDong)와 매물(building_name)이 체계가 달라 맞춰야 비교 가능.
    '101동'→'101', '제101동'→'101', '래미안 101'→'101', '에이'→'A', '3호'→'3', 단지명만/'아파트'→'1'."""
    s = (s or "").strip()
    if not s:
        return None
    s = re.sub(r"동$", "", s).strip()
    s = re.sub(r"^주건축물제", "", s)
    s = re.sub(r"^제", "", s)
    m = re.search(r"(\d+)$", s)
    if m and not re.fullmatch(r"\d+", s):
        s = m[1]
    if re.fullmatch(r"\d+", s):
        return str(int(s))
    if re.fullmatch(r"\d+-\d+", s):
        return s
    s = s.upper()
    if s in HAN:
        return HAN[s]
    if re.fullmatch(r"[A-Z]", s):
        return s
    if re.fullmatch(r"\d+호", s):
        return s[:-1]
    if s == "아파트":
        return "1"
    return "1" if len(s) >= 4 and not re.search(r"\d", s) else s


def band(floor: int, tot: int) -> str:
    r = floor / tot
    return "저" if r <= 1 / 3 else "중" if r <= 2 / 3 else "고"


# ── 입력 ────────────────────────────────────────────────────────────────
@dataclass
class Deal:
    key: str            # 'A1:'+deal_id / 'B1:'+rental_id / 'B2:'+rental_id
    trade: str          # A1 | B1 | B2
    complex_no: str
    when: date          # 계약일
    amt: int            # 매매가 또는 보증금(원)
    mrent: int          # 월세(원), 매매·전세 0
    floor: int
    area: int           # 전용면적 반올림(㎡)
    contract_type: str | None = None   # 전월세: 신규/갱신/''(미상)
    truth: str | None = None           # 등기 동(정규화) — 매매 등기 완료분만
    dealing_gbn: str | None = None


class Context:
    """한 번의 실행에서 쓰는 단지별 자료: 등기 이력 · 매물 · 면적별 동 집합 · 동별 높이."""

    def __init__(self) -> None:
        self.hist: dict[str, list[tuple]] = defaultdict(list)       # c → [(rg, area, dong, floor, when, amt)]
        self.arts: dict[str, dict[str, list[tuple]]] = {t: defaultdict(list) for t in TRADES}
        self.adong: dict[tuple[str, int], set[str]] = defaultdict(set)
        self.height: dict[tuple[str, str], int] = defaultdict(int)

    # 등기 완료 매매(사전확률·후보). 단지 단위 인덱스(transactions_complex_idx) 조회.
    def load_hist(self, main: sqlite3.Connection, complexes: Iterable[str]) -> None:
        q = ("SELECT deal_ymd, deal_amount, floor, excl_use_ar, json_extract(raw,'$.aptDong'), "
             "json_extract(raw,'$.rgstDate') FROM transactions WHERE matched_complex_no=? AND is_cancelled=0 "
             "AND TRIM(COALESCE(json_extract(raw,'$.rgstDate'),''))<>''")
        for c in complexes:
            for ymd, amt, fl, ex, dong, rg in main.execute(q, (c,)):
                dd, rgd, dg = pdate(ymd), rgst_date(rg), ndong(dong)
                if dd and rgd and dg and fl is not None and ex is not None:
                    self.hist[c].append((rgd, round(float(ex)), dg, int(fl), dd, int(amt or 0)))

    def add_hist_rows(self, rows: Iterable[tuple]) -> None:
        """(complex_no, rgst_date, area, dong, floor, when, amt) 를 직접 넣는다(테스트·시드용)."""
        for c, rgd, a, dg, fl, dd, amt in rows:
            self.hist[c].append((rgd, a, dg, fl, dd, amt))

    # 매물. 활성 매물은 후보 동·높이에만 쓰고(아직 팔리지 않았으니 단서 아님), 내려간 매물만 단서.
    ART_Q = ("SELECT article_no, trade_type, area2_m2, floor_info, building_name, deal_or_warrant_price, "
             "rent_price, article_confirm_ymd, first_seen_date, last_seen_date, is_active "
             "FROM {t} WHERE complex_no=? AND trade_type IN ('A1','B1','B2')")

    def load_articles(self, main: sqlite3.Connection, complexes: Iterable[str],
                      archive: sqlite3.Connection | None = None) -> None:
        seen: set[str] = set()
        for c in complexes:
            rows = list(main.execute(self.ART_Q.format(t="articles"), (c,)))
            if archive is not None:
                rows += list(archive.execute(self.ART_Q.format(t="articles"), (c,)))
            self.add_article_rows(c, rows, seen)

    def add_article_rows(self, c: str, rows: Iterable[tuple], seen: set[str] | None = None) -> None:
        seen = set() if seen is None else seen
        for no, tt, a2, fi, bn, price, rent, conf, fs, ls, act in rows:
            dong = ndong(bn)
            if not dong or a2 is None or tt not in self.arts:
                continue
            a = round(float(a2))
            m = re.match(r"(\S+)/(\d+)", fi or "")
            fl, tot = (m[1], int(m[2])) if m else (None, None)
            if tot:
                self.height[(c, dong)] = max(self.height[(c, dong)], tot)
            self.adong[(c, a)].add(dong)
            if int(act or 0) == 1 or no in seen:
                continue
            seen.add(no)
            lsd, fsd = pdate(ls), pdate(fs)
            if not lsd:
                continue
            cf = (date(int(conf[:4]), int(conf[4:6]), int(conf[6:8]))
                  if conf and len(str(conf)) == 8 and str(conf).isdigit() else None)
            slack = ((cf + timedelta(days=30)) - lsd).days if cf else 0
            self.arts[tt][c].append((a, dong, fl, tot, lsd, fsd, int(price or 0), int(rent or 0), slack, False))


# ── 특징 ────────────────────────────────────────────────────────────────
def build_features(deals: list[Deal], ctx: Context):
    """→ X(n_rows×len(FEAT)), y(정답 1/0; truth 없으면 0), G(행→거래 인덱스), cands(거래→후보 목록 순서), ncand."""
    X: list[list[float]] = []
    y: list[int] = []
    G: list[int] = []
    cand_of: dict[int, list[str]] = {}
    ncand: dict[int, int] = {}
    W_FLOOR = {"exact": 1.0, "band": 0.45, "unk": 0.3, "wrongband": 0.05}
    for idx, dl in enumerate(deals):
        c, when, amt, mrent, floor, area = dl.complex_no, dl.when, dl.amt, dl.mrent, dl.floor, dl.area
        H = [h for h in ctx.hist.get(c, ()) if h[0] < when]
        cnt = Counter(h[2] for h in H if abs(h[1] - area) <= 1)
        cands = (set(cnt) | ctx.adong.get((c, area), set()) | ctx.adong.get((c, area - 1), set())
                 | ctx.adong.get((c, area + 1), set()))
        cands = {dg for dg in cands if not (ctx.height.get((c, dg)) and floor > ctx.height[(c, dg)])}
        ncand[idx] = len(cands)
        if not cands:
            continue
        tot = sum(cnt.values())
        dong_tx = Counter(h[2] for h in H)
        f = {dg: dict(best_w=0.0, exact_w=0.0, band_w=0.0, price_w=0.0, n_match=0, n_exact=0, min_abs_off=99,
                      cons=set(), neg_alive=0, neg_after=0, best_pr=0.0, listed=0) for dg in cands}
        for a, dg, fl, tot_f, lsd, fsd, price, rent, slack, alive in ctx.arts[dl.trade].get(c, ()):
            if dg not in cands or abs(a - area) > 1:
                continue
            g = f[dg]
            if fl is None:
                fm = "unk"
            elif fl.isdigit():
                fm = "exact" if int(fl) == floor else "wrong"
            elif tot_f:
                fm = "band" if fl == band(floor, tot_f) else "wrongband"
            else:
                fm = "unk"
            if fsd and fsd <= when:
                g["listed"] += 1
            if fm == "exact" and (fsd is None or fsd <= when + timedelta(days=3)) and lsd >= when + timedelta(days=30):
                g["neg_alive" if alive else "neg_after"] += 1
            if alive:
                continue
            off = (lsd - when).days
            if not (-WINDOW_BEFORE <= off <= WINDOW_AFTER):
                continue
            w = W_FLOOR.get(fm, 0.0)
            pr = price / amt if price and amt else None
            pw = 0.0
            if pr is not None:
                pw = (1.0 + (0.8 if abs(pr - 1) < 0.005 else 0.4 if pr <= 1.08 else 0.0)) if 0.97 <= pr <= 1.18 else 0.15
                if dl.trade == "B2" and mrent and rent:
                    rr = rent / mrent
                    pw *= 1.0 if 0.9 <= rr <= 1.15 else 0.3
                w *= pw
            w *= 1.0 if slack >= 4 else 0.25
            g["n_match"] += 1
            g["min_abs_off"] = min(g["min_abs_off"], abs(off))
            if fm == "exact":
                g["n_exact"] += 1
                g["exact_w"] = max(g["exact_w"], w)
                g["cons"].add((fl, price))
            if fm == "band":
                g["band_w"] = max(g["band_w"], w)
            if w > g["best_w"]:
                g["best_w"], g["best_pr"], g["price_w"] = w, pr or 0, pw
        tot_listed = sum(g["listed"] for g in f.values()) or 1
        order = sorted(cands)
        cand_of[idx] = order
        for dg in order:
            g = f[dg]
            lp = math.log((cnt[dg] + 0.3) / (tot + 0.3 * len(cands)))
            X.append([lp, cnt[dg], cnt[dg] / tot if tot else 0, len(cands), g["best_w"], g["exact_w"], g["band_w"],
                      g["price_w"], g["n_match"], g["n_exact"], g["min_abs_off"], len(g["cons"]), g["neg_alive"],
                      g["neg_after"], 1 if ctx.height.get((c, dg)) else 0, dong_tx[dg], g["best_pr"],
                      g["listed"] / tot_listed])
            y.append(1 if dg == dl.truth else 0)
            G.append(idx)
    return (np.array(X, float).reshape(-1, len(FEAT)), np.array(y, int), np.array(G, int), cand_of, ncand)


# ── 모델 ────────────────────────────────────────────────────────────────
def new_model():
    from sklearn.ensemble import HistGradientBoostingClassifier
    return HistGradientBoostingClassifier(**MODEL_PARAMS)


def fit(X, y):
    return new_model().fit(X, y)


def oof_scores(X, y, G, folds: int = 5) -> np.ndarray:
    from sklearn.model_selection import GroupKFold
    oof = np.zeros(len(X))
    for trn, tst in GroupKFold(folds).split(X, y, G):
        oof[tst] = new_model().fit(X[trn], y[trn]).decision_function(X[tst])
    return oof


@dataclass
class Est:
    top1: str
    conf1: float
    top2: str | None
    conf2: float
    n_signal: int       # 후보 전체의 매물 단서 수(0 = 단서 없음)
    ncand: int
    correct: int | None = None   # truth 있을 때


def score(model, X, G, cand_of: dict[int, list[str]], ncand: dict[int, int], y=None,
          scores: np.ndarray | None = None) -> dict[int, Est]:
    """후보 점수 → 거래별 softmax 확신도. scores 를 주면(OOF) 모델을 쓰지 않는다."""
    if len(X) == 0:
        return {}
    s = model.decision_function(X) if scores is None else scores
    nm_i = FEAT.index("n_match")
    rows: dict[int, list[int]] = defaultdict(list)
    for i, g in enumerate(G):
        rows[int(g)].append(i)
    out: dict[int, Est] = {}
    for g, idxs in rows.items():
        sc = s[idxs]
        z = np.exp(sc - sc.max())
        p = z / z.sum()
        order = np.argsort(-p)
        k = idxs[order[0]]
        top1 = cand_of[g][order[0]]
        top2 = cand_of[g][order[1]] if len(order) > 1 else None
        n_signal = int(X[idxs, nm_i].sum())
        correct = None if y is None else int(y[k])
        out[g] = Est(top1, float(p[order[0]]), top2, float(p[order[1]]) if len(order) > 1 else 0.0,
                     n_signal, ncand[g], correct)
    return out


def displayable(dl: Deal, e: Est, thresh: float = THRESH) -> bool:
    """표시 규칙. 단서 없음+후보 2동↑ 금지, 전월세 갱신·미상은 단일동만, 그 외 확신도 문턱."""
    if e.ncand >= 2 and e.n_signal == 0:
        return False
    if dl.trade in ("B1", "B2") and (dl.contract_type or "").strip() != "신규" and e.ncand != 1:
        return False
    return e.conf1 >= thresh


def eval_at(est_by_deal: dict[int, Est], deals: list[Deal], thresh: float) -> dict:
    """정답 있는 거래로 커버·정확도 (규칙 적용)."""
    n = len(deals)
    shown = [(e.correct or 0) for i, e in est_by_deal.items() if displayable(deals[i], e, thresh)]
    overall = sum((e.correct or 0) for e in est_by_deal.values())
    return {"n": n, "acc_all": overall / n if n else 0.0,
            "cov": len(shown) / n if n else 0.0, "acc_shown": (sum(shown) / len(shown)) if shown else 0.0}


# ── 저장소 ──────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS dong_est (
    deal_key      TEXT PRIMARY KEY,       -- 'A1:'||deal_id, 'B1:'||rental_id, 'B2:'||rental_id
    trade_type    TEXT NOT NULL,
    complex_no    TEXT NOT NULL,
    deal_ymd      TEXT NOT NULL,
    floor         INTEGER, area INTEGER, amount INTEGER, mrent INTEGER, contract_type TEXT,
    n_cand        INTEGER, n_signal INTEGER,
    pred_dong     TEXT, conf REAL, pred2_dong TEXT, conf2 REAL,
    shown         INTEGER NOT NULL DEFAULT 0,   -- 규칙+문턱 통과(API 는 이것만 본다)
    status        TEXT NOT NULL,                -- est(예비) | final(+45일 고정) | confirmed(등기 대조 완료) | none(후보 없음)
    model_ver     INTEGER, est_at TEXT, final_at TEXT,
    actual_dong   TEXT, actual_at TEXT, correct INTEGER,
    pre_reg       INTEGER NOT NULL DEFAULT 0,   -- 1 = 등기 전에 추정이 있었다(표시 정확도 집계 대상)
    shown_before_reg INTEGER                    -- 등기 직전 표시 여부
);
CREATE INDEX IF NOT EXISTS dong_est_status_idx  ON dong_est(status, deal_ymd);
CREATE INDEX IF NOT EXISTS dong_est_complex_idx ON dong_est(complex_no, deal_ymd);
CREATE TABLE IF NOT EXISTS dong_est_feat (        -- 학습 로그(매매 최종 패스·시드)
    deal_key TEXT NOT NULL, cand TEXT NOT NULL, feats TEXT NOT NULL,
    label INTEGER, pass TEXT NOT NULL, PRIMARY KEY(deal_key, cand)
);
CREATE INDEX IF NOT EXISTS dong_est_feat_label_idx ON dong_est_feat(label);
CREATE TABLE IF NOT EXISTS dong_model (
    ver INTEGER PRIMARY KEY, trained_at TEXT, n_deals INTEGER, n_rows INTEGER,
    oof_acc REAL, oof_acc_th REAL, oof_cov_th REAL, thresh REAL, active INTEGER NOT NULL DEFAULT 0,
    note TEXT, path TEXT
);
CREATE TABLE IF NOT EXISTS dong_daily_log (
    day TEXT NOT NULL, trade_type TEXT NOT NULL,
    n_new INTEGER DEFAULT 0, n_final INTEGER DEFAULT 0, n_shown INTEGER DEFAULT 0,
    n_confirmed INTEGER DEFAULT 0, n_correct INTEGER DEFAULT 0,
    n_conf_shown INTEGER DEFAULT 0, n_conf_shown_correct INTEGER DEFAULT 0,
    PRIMARY KEY(day, trade_type)
);
"""


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.c = sqlite3.connect(self.path, timeout=30)
        self.c.execute("PRAGMA journal_mode=WAL")
        self.c.execute("PRAGMA synchronous=NORMAL")
        self.c.executescript(SCHEMA)

    # 모델 ------------------------------------------------------------------
    def active_model(self):
        r = self.c.execute("SELECT ver, path, oof_acc_th, oof_cov_th FROM dong_model WHERE active=1 "
                           "ORDER BY ver DESC LIMIT 1").fetchone()
        if not r:
            return None, None
        p = Path(r[1])
        if not p.is_absolute():
            p = self.path.parent / p
        with open(p, "rb") as fh:
            return r[0], pickle.load(fh)

    def save_model(self, model, metrics: dict, note: str, promote: bool) -> int:
        ver = (self.c.execute("SELECT COALESCE(MAX(ver),0) FROM dong_model").fetchone()[0] or 0) + 1
        d = self.path.parent / "dong_models"
        d.mkdir(exist_ok=True)
        p = d / f"v{ver}.pkl"
        with open(p, "wb") as fh:
            pickle.dump(model, fh)
        if promote:
            self.c.execute("UPDATE dong_model SET active=0")
        self.c.execute(
            "INSERT INTO dong_model(ver, trained_at, n_deals, n_rows, oof_acc, oof_acc_th, oof_cov_th, thresh, active, note, path) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ver, datetime.now(KST).isoformat(timespec="seconds"), metrics.get("n"), metrics.get("n_rows"),
             metrics.get("acc_all"), metrics.get("acc_shown"), metrics.get("cov"), THRESH, 1 if promote else 0,
             note, str(p.relative_to(self.path.parent))))
        self.c.commit()
        return ver

    # 학습 로그 ---------------------------------------------------------------
    def put_feats(self, rows: Iterable[tuple[str, str, list[float], int | None, str]]) -> None:
        self.c.executemany(
            "INSERT OR REPLACE INTO dong_est_feat(deal_key, cand, feats, label, pass) VALUES (?,?,?,?,?)",
            [(k, cd, json.dumps([float(v) for v in fv]), lb, ps) for k, cd, fv, lb, ps in rows])

    def label_feats(self, deal_key: str, actual: str) -> None:
        self.c.execute("UPDATE dong_est_feat SET label=(cand=?) WHERE deal_key=?", (actual, deal_key))

    def training_matrix(self):
        X, y, G = [], [], []
        for k, fv, lb in self.c.execute("SELECT deal_key, feats, label FROM dong_est_feat WHERE label IS NOT NULL"):
            X.append(json.loads(fv))
            y.append(int(lb))
            G.append(k)
        return np.array(X, float).reshape(-1, len(FEAT)), np.array(y, int), np.array(G)

    # 추정 -------------------------------------------------------------------
    def existing(self, keys: Iterable[str]) -> dict[str, tuple]:
        out: dict[str, tuple] = {}
        keys = list(keys)
        for i in range(0, len(keys), 900):
            chunk = keys[i:i + 900]
            q = ("SELECT deal_key, status, pred_dong, conf, shown, actual_dong FROM dong_est WHERE deal_key IN (%s)"
                 % ",".join("?" * len(chunk)))
            for r in self.c.execute(q, chunk):
                out[r[0]] = r[1:]
        return out

    def upsert_est(self, dl: Deal, e: Est | None, status: str, model_ver: int | None, shown: bool,
                   now: str, final: bool) -> None:
        self.c.execute(
            "INSERT INTO dong_est(deal_key, trade_type, complex_no, deal_ymd, floor, area, amount, mrent, contract_type, "
            " n_cand, n_signal, pred_dong, conf, pred2_dong, conf2, shown, status, model_ver, est_at, final_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(deal_key) DO UPDATE SET n_cand=excluded.n_cand, n_signal=excluded.n_signal, "
            " pred_dong=excluded.pred_dong, conf=excluded.conf, pred2_dong=excluded.pred2_dong, conf2=excluded.conf2, "
            " shown=excluded.shown, status=excluded.status, model_ver=excluded.model_ver, "
            " final_at=COALESCE(excluded.final_at, dong_est.final_at)",
            (dl.key, dl.trade, dl.complex_no, dl.when.isoformat(), dl.floor, dl.area, dl.amt, dl.mrent, dl.contract_type,
             e.ncand if e else 0, e.n_signal if e else 0, e.top1 if e else None, e.conf1 if e else None,
             e.top2 if e else None, e.conf2 if e else None, 1 if shown else 0, status, model_ver, now,
             now if final else None))

    def confirm(self, deal_key: str, actual: str, now: str) -> tuple[int | None, int | None, int | None]:
        """등기 동 대조. → (correct, pre_reg, shown_before_reg)"""
        r = self.c.execute("SELECT pred_dong, shown, status FROM dong_est WHERE deal_key=?", (deal_key,)).fetchone()
        if not r:
            return None, None, None
        pred, shown, status = r
        correct = int(pred == actual) if pred else 0
        pre_reg = 1 if status in ("est", "final") else 0
        self.c.execute(
            "UPDATE dong_est SET actual_dong=?, actual_at=?, correct=?, status='confirmed', shown=0, "
            " pre_reg=CASE WHEN status IN ('est','final') THEN 1 ELSE pre_reg END, "
            " shown_before_reg=CASE WHEN status IN ('est','final') THEN shown ELSE shown_before_reg END "
            "WHERE deal_key=?", (actual, now, correct, deal_key))
        return correct, pre_reg, shown

    def log_day(self, day: str, trade: str, **counts: int) -> None:
        cols = ["n_new", "n_final", "n_shown", "n_confirmed", "n_correct", "n_conf_shown", "n_conf_shown_correct"]
        vals = [int(counts.get(k, 0)) for k in cols]
        self.c.execute(
            f"INSERT INTO dong_daily_log(day, trade_type, {','.join(cols)}) VALUES (?,?,{','.join('?' * len(cols))}) "
            f"ON CONFLICT(day, trade_type) DO UPDATE SET " + ",".join(f"{k}={k}+excluded.{k}" for k in cols),
            [day, trade, *vals])

    def commit(self) -> None:
        self.c.commit()
