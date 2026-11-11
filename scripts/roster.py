"""입주자·소유자 명단(사무소 보유) ↔ 광고 중 매물 대조 — 중개사라운지 '명단 대조'.

중개사는 단지·동·호·이름·연락처가 든 명단을 갖고 있고, 그중 지금 광고가 걸린 집을 찾아 연락한다.
콕집은 ① 명단을 사무소별로 암호화해 보관하고(이름·연락처는 Fernet, 서버 키 data/roster.key)
② 광고(listings_current)와 **동·층** 단위로 대조한다. 광고는 호수를 공개하지 않고 동과 층(정확 59%,
고·중·저 41%)만 공개하므로, 대조 결과는 '그 집'이 아니라 '그 집이 있는 동·층의 광고'다.

법적 전제(화면에 고지·동의): 명단의 적법 수집·보유 책임은 사무소에 있고, 콕집은 사무소의 위탁을 받아
보관·대조만 한다. 다른 사무소에 보이지 않는다. 연락처는 누를 때만 복호화하고 그 사실을 기록한다.
명단은 지우는 게 아니라 같은 명단에 새 파일을 올려 업데이트해 간다(동·호가 같으면 갱신, 새 세대는 추가).
보관·대조 동의는 180일짜리다. 동의 후 90일이 지나면 연장 동의를 받을 수 있고, 연장하면 그날부터 다시 180일.
180일 안에 연장하지 않으면 대조·연락처 열람을 멈춘다(자료는 두고, 연장 동의하면 다시 쓸 수 있다).

고객원장과의 분리(2026-11-11 원칙): 명단은 고객원장(reviews.sqlite 의 biz_customers·biz_needs)과 **완전히 다른
DB**다. 이 모듈은 roster.sqlite 와 읽기 전용 광고 DB 만 연다. 고객원장을 읽지도 쓰지도 않고, 명단 행을 고객원장으로
옮기거나 고객원장 행을 명단에 넣는 경로를 두지 않는다. 암호화 키도 별도(roster.key). 지운 행은 secure_delete 로 덮어쓴다.
"""
from __future__ import annotations
import base64, hashlib, io, json, os, re, sqlite3, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEEP_DAYS = 180     # 동의 한 번의 효력
RENEW_AFTER = 90    # 동의 후 이만큼 지나면 연장 동의를 받을 수 있다

SCHEMA = """
CREATE TABLE IF NOT EXISTS roster_lists(
  id INTEGER PRIMARY KEY AUTOINCREMENT, realtor_id TEXT NOT NULL, user_id TEXT, name TEXT, filename TEXT,
  n_rows INTEGER DEFAULT 0, n_linked INTEGER DEFAULT 0, ack_at TEXT, uploaded_at TEXT DEFAULT (datetime('now','+9 hours')),
  expires_at TEXT);
CREATE TABLE IF NOT EXISTS roster_units(
  id INTEGER PRIMARY KEY AUTOINCREMENT, list_id INTEGER NOT NULL, realtor_id TEXT NOT NULL,
  complex_no TEXT, complex_raw TEXT, dong TEXT, ho TEXT, floor INTEGER, role TEXT, area TEXT,
  name_enc TEXT, phone_enc TEXT, phone_hash TEXT, note TEXT,
  created_at TEXT DEFAULT (datetime('now','+9 hours')));
CREATE INDEX IF NOT EXISTS roster_units_rt ON roster_units(realtor_id, complex_no, dong, floor);
CREATE INDEX IF NOT EXISTS roster_units_list ON roster_units(list_id);
CREATE TABLE IF NOT EXISTS roster_reveals(
  id INTEGER PRIMARY KEY AUTOINCREMENT, realtor_id TEXT, user_id TEXT, unit_id INTEGER, at TEXT DEFAULT (datetime('now','+9 hours')));
"""


def db_path(data_dir: Path) -> Path:
    return data_dir / "roster.sqlite"


def connect(data_dir: Path) -> sqlite3.Connection:
    p = db_path(data_dir)
    assert p.name == "roster.sqlite"   # 고객원장(reviews.sqlite)과 섞이지 않게 — 다른 파일을 열지 않는다
    c = sqlite3.connect(p, timeout=30)
    c.execute("PRAGMA secure_delete=ON")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    c.executescript(SCHEMA)
    if "area" not in {r[1] for r in c.execute("PRAGMA table_info(roster_units)")}:
        c.execute("ALTER TABLE roster_units ADD COLUMN area TEXT")
    cols = {r[1] for r in c.execute("PRAGMA table_info(roster_lists)")}
    if "updated_at" not in cols:
        c.execute("ALTER TABLE roster_lists ADD COLUMN updated_at TEXT")
        c.execute("ALTER TABLE roster_lists ADD COLUMN n_updates INTEGER DEFAULT 0")
    if "updated_at" not in {r[1] for r in c.execute("PRAGMA table_info(roster_units)")}:
        c.execute("ALTER TABLE roster_units ADD COLUMN updated_at TEXT")
    return c


# ── 암호화 ────────────────────────────────────────────────────────────────
def _fernet(data_dir: Path):
    from cryptography.fernet import Fernet
    kp = data_dir / "roster.key"
    if not kp.exists():
        kp.write_bytes(Fernet.generate_key())
        os.chmod(kp, 0o600)
    return Fernet(kp.read_bytes().strip())


def enc(data_dir: Path, s: str | None) -> str | None:
    if not s:
        return None
    return _fernet(data_dir).encrypt(s.encode("utf-8")).decode("ascii")


def dec(data_dir: Path, s: str | None) -> str:
    if not s:
        return ""
    try:
        return _fernet(data_dir).decrypt(s.encode("ascii")).decode("utf-8")
    except Exception:  # noqa: BLE001
        return ""


def phone_digits(s: str | None) -> str:
    return re.sub(r"\D", "", str(s or ""))


def phone_hash(s: str | None) -> str | None:
    d = phone_digits(s)
    return hashlib.sha256(("koczip-roster|" + d).encode()).hexdigest()[:32] if len(d) >= 9 else None


def mask_name(n: str) -> str:
    n = (n or "").strip()
    if len(n) <= 1:
        return n
    if len(n) == 2:
        return n[0] + "*"
    return n[0] + "*" * (len(n) - 2) + n[-1]


def mask_phone(p: str) -> str:
    d = phone_digits(p)
    if len(d) < 8:
        return ""
    return f"{d[:3]}-****-{d[-4:]}"


# ── 엑셀 읽기 ─────────────────────────────────────────────────────────────
HEAD = {
    "complex": ["단지명", "아파트명", "건물명", "단지", "아파트", "오피스텔", "건물", "물건지", "소재지"],
    "dongho": ["동호수", "동호", "동/호", "동·호", "동-호", "호수동"],
    "dong": ["동수", "동번호", "동"],
    "ho": ["호수", "호실", "호"],
    "name": ["소유자명", "입주자명", "세대주명", "성명", "소유자", "입주자", "세대주", "이름", "고객명", "임대인"],
    "phone": ["연락처", "전화번호", "휴대폰", "핸드폰", "전화", "휴대전화", "번호"],
    "role": ["구분", "소유구분", "거주구분", "관계", "임대차"],
    "note": ["비고", "메모", "특이사항", "참고"],
    "area": ["타입", "평형", "면적", "전용면적", "전용", "주택형", "평수", "평", "공급면적", "공급", "계약면적", "타입명", "type", "평형대", "형별", "형", "평형타입", "py"],
}


def _norm(s) -> str:
    return re.sub(r"[\s()\[\]/·.\-_:]+", "", str(s or "")).lower()


def _match_head(cell) -> str | None:
    h = _norm(cell)
    if not h or len(h) > 20:
        return None
    for f, words in HEAD.items():
        for w in words:
            if h == _norm(w):
                return f
    best = None
    for f, words in HEAD.items():
        for w in words:
            wn = _norm(w)
            if len(wn) >= 2 and wn in h and (best is None or len(wn) > best[1]):
                best = (f, len(wn))
    return best[0] if best else None


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v).strip()


def read_rows(data: bytes, filename: str) -> list[list]:
    if filename.lower().endswith(".csv"):
        txt = None
        for encd in ("utf-8-sig", "cp949", "utf-8"):
            try:
                txt = data.decode(encd); break
            except UnicodeDecodeError:
                continue
        import csv
        return [row for row in csv.reader(io.StringIO(txt or ""))]
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    rows: list[list] = []
    for ws in wb.worksheets:
        if ws.sheet_state != "visible":
            continue
        blank = 0
        for r in ws.iter_rows(values_only=True, max_row=50000):
            row = list(r)
            if any(v not in (None, "") for v in row):
                blank = 0; rows.append(row)
            else:
                blank += 1
                if blank >= 200:
                    break
        rows.append(None)   # 시트 경계
    wb.close()
    return rows


_DONGHO = re.compile(r"(\d{1,4})\s*동?\s*[-/ ]\s*(\d{1,5})\s*호?")
_DONG = re.compile(r"(\d{1,4})\s*동")
_HO = re.compile(r"(\d{1,5})\s*호")


def split_dongho(t: str) -> tuple[str | None, str | None]:
    t = (t or "").strip()
    m = _DONGHO.search(t)
    if m:
        return m.group(1), m.group(2)
    d = _DONG.search(t); h = _HO.search(t)
    return (d.group(1) if d else None), (h.group(1) if h else None)


def floor_of(ho: str | None) -> int | None:
    """호수 → 층. 1203→12, 505→5, 101→1. 지하(B101)·5자리(10203→102층?)는 보수적으로."""
    if not ho:
        return None
    s = re.sub(r"\D", "", str(ho))
    if not s:
        return None
    if len(s) <= 2:
        return int(s) if int(s) > 0 else None
    f = int(s[:-2])
    return f if 0 < f <= 120 else None


_TYPE_VAL = re.compile(r"^\d{2,3}(\.\d{1,2})?\s*([A-Za-z]{1,2}\d?)?\s*(평형?|㎡|m2|m²|형|타입|py)?$", re.I)


def _looks_type_col(vals: list[str]) -> bool:
    """값만 보고 타입 칸인지 — 84A·34평·59.99·112 꼴이 대부분이고, 전화번호·동호수 꼴이 아니다."""
    vs = [v for v in vals if v][:200]
    if len(vs) < 5:
        return False
    hit = sum(1 for v in vs if _TYPE_VAL.match(v))
    letters_or_unit = sum(1 for v in vs if re.search(r"[A-Za-z평㎡형.]", v))
    return hit >= len(vs) * 0.7 and letters_or_unit >= len(vs) * 0.3


def parse(data: bytes, filename: str, col_map: dict | None = None) -> dict:
    """명단 파일 → {rows:[{complex_raw, dong, ho, floor, name, phone, role, note, area}], skipped, fields, columns}.
    col_map = {머리글 글자: 필드} 로 사무소가 고른 칸을 덮어쓴다(예: {'평수': 'area'}, 빼려면 ''). 
    타입 칸은 머리글로 못 찾으면 값(84A·34평·59.99)으로 찾는다."""
    raw = read_rows(data, filename)
    sheets: list[list] = [[]]
    for r in raw:
        if r is None:
            sheets.append([]); continue
        sheets[-1].append([_cell(v) for v in r])
    cmap = {_norm(k): v for k, v in (col_map or {}).items()}
    out, skipped = [], 0
    fields_seen: set = set()
    columns: list[dict] = []      # 화면용: 머리글마다 어떤 필드로 읽었는지(값은 담지 않는다)
    col_seen: set = set()
    for rows in sheets:
        hi, mapping = None, {}
        for k, cells in enumerate(rows):
            if not any(cells):
                continue
            m = {}
            for j, c in enumerate(cells):
                f = _match_head(c)
                if f and f not in m.values():
                    m[j] = f
            if len({v for v in m.values()} & {"name", "phone", "dongho", "dong", "ho", "complex"}) >= 2 and not any(re.fullmatch(r"[\d,.\-]+", c) for c in cells if c):
                hi, mapping = k, m
                break
            skipped += 1
        if hi is None:
            continue
        head = rows[hi]
        body = rows[hi + 1:]
        how: dict[int, str] = {j: "머리글" for j in mapping}
        if "area" not in mapping.values():
            # 머리글로 못 찾았으면 값으로 — 이름 없는 칸이나 구분·비고로 잡힌 칸에 84A·34평이 가득하면 그게 타입 칸
            for j, h in enumerate(head):
                if mapping.get(j) not in (None, "role", "note"):
                    continue
                if _looks_type_col([b[j] if j < len(b) else "" for b in body]):
                    mapping[j] = "area"; how[j] = "값으로 찾음"
                    break
        for j, h in enumerate(head):          # 사무소가 고른 칸이 우선
            if h and _norm(h) in cmap:
                f = cmap[_norm(h)]
                for jj, ff in list(mapping.items()):
                    if f and ff == f and jj != j:
                        del mapping[jj]
                if f:
                    mapping[j] = f; how[j] = "직접 고름"
                else:
                    mapping.pop(j, None)
        fields_seen |= set(mapping.values())
        # '평수'·'평형' 칸에 숫자만 적혀 있으면 평으로 읽는다(34 → 34평)
        pyeong_cols = {j for j, f in mapping.items() if f == "area" and _norm(head[j] if j < len(head) else "") in ("평수", "평", "평형", "평형대", "py", "평형평")}
        for j, h in enumerate(head):
            if h and h not in col_seen:
                col_seen.add(h)
                columns.append({"header": h, "field": mapping.get(j) or "", "how": how.get(j, "") if j in mapping else ""})
        for cells in body:
            if not any(cells):
                continue
            rec = {k: "" for k in ("complex_raw", "dong", "ho", "name", "phone", "role", "note", "area")}
            for j, f in mapping.items():
                v = cells[j] if j < len(cells) else ""
                if not v:
                    continue
                if f == "complex":
                    rec["complex_raw"] = v
                elif f == "dongho":
                    d, h = split_dongho(v); rec["dong"] = d or rec["dong"]; rec["ho"] = h or rec["ho"]
                elif f == "dong":
                    rec["dong"] = re.sub(r"\D", "", v) or v
                elif f == "ho":
                    rec["ho"] = re.sub(r"\D", "", v) or v
                elif f == "area" and j in pyeong_cols and re.fullmatch(r"\d{1,3}(\.\d+)?", v):
                    rec["area"] = v + "평"
                else:
                    rec[f] = v
            if not (rec["dong"] or rec["ho"]) or not (rec["name"] or rec["phone"]):
                skipped += 1
                continue
            rec["floor"] = floor_of(rec["ho"])
            out.append(rec)
    return {"rows": out, "skipped": skipped, "fields": sorted(fields_seen), "columns": columns,
            "n_area": sum(1 for r in out if r["area"])}


# ── 단지 연결 ─────────────────────────────────────────────────────────────
def norm_cx(s: str) -> str:
    s = re.sub(r"\(.*?\)", "", str(s or ""))
    s = re.sub(r"(아파트|APT|apt|주상복합|오피스텔|단지)", "", s)
    return re.sub(r"[\s\-·.]+", "", s).lower()


def complex_candidates(main_db: sqlite3.Connection, raw: str, limit: int = 8) -> list[dict]:
    """자동 연결이 안 된 단지 이름 → 전국 후보(이름 같은 것 먼저, 세대 많은 순). 사무소가 고른다."""
    key = norm_cx(raw)
    if len(key) < 2:
        return []
    rows = main_db.execute(
        "SELECT cx.complex_no, cx.complex_name, trim(COALESCE(g.cortar_name,'') || ' ' || COALESCE(d.cortar_name,'')) AS addr, cx.total_household_count AS hh FROM complexes cx "
        "LEFT JOIN regions d ON d.cortar_no=cx.cortar_no LEFT JOIN regions g ON g.cortar_no=d.parent_cortar_no "
        "WHERE cx.real_estate_type IN ('APT','OPST','ABYG','JGC') AND replace(cx.complex_name,' ','') LIKE ? LIMIT 200", ("%" + key[:10] + "%",)).fetchall()
    out = [{"complex_no": r[0], "name": r[1], "addr": r[2] or "", "households": r[3] or 0, "exact": norm_cx(r[1]) == key} for r in rows]
    out.sort(key=lambda x: (not x["exact"], -(x["households"] or 0)))
    return out[:limit]


def link_complexes(main_db: sqlite3.Connection, rows: list[dict], sgg_prefixes: list[str], default_complex_no: str | None = None, cx_map: dict | None = None) -> dict:
    """명단의 단지 이름 → complex_no. 사무소가 있는 시군구(앞 5자리) 단지부터 보고, 이름 정규화 일치 → 포함 순."""
    cache: dict[str, str | None] = {}
    linked = 0
    cands_by_sgg: dict[str, list] = {}
    for p in sgg_prefixes:
        cands_by_sgg[p] = [(r[0], r[1], norm_cx(r[1])) for r in main_db.execute(
            "SELECT complex_no, complex_name FROM complexes WHERE cortar_no LIKE ? AND real_estate_type IN ('APT','OPST','ABYG','JGC')", (p + "%",))]
    cx_map = cx_map or {}
    for rec in rows:
        if cx_map.get(rec.get("complex_raw") or ""):         # 사무소가 화면에서 고른 단지
            rec["complex_no"] = str(cx_map[rec.get("complex_raw") or ""]); linked += 1; continue
        key = norm_cx(rec.get("complex_raw") or "")
        if not key:
            rec["complex_no"] = default_complex_no
            linked += bool(default_complex_no)
            continue
        if key in cache:
            rec["complex_no"] = cache[key]; linked += bool(cache[key]); continue
        hit = None
        for p in sgg_prefixes:
            exact = [c for c in cands_by_sgg[p] if c[2] == key]
            if len(exact) == 1:
                hit = exact[0][0]; break
            part = [c for c in cands_by_sgg[p] if key and (key in c[2] or c[2] in key) and min(len(key), len(c[2])) >= 3]
            if len(part) == 1:
                hit = part[0][0]; break
        if not hit and len(key) >= 6:
            rows_any = main_db.execute("SELECT complex_no, complex_name FROM complexes WHERE replace(complex_name,' ','') LIKE ? AND real_estate_type IN ('APT','OPST') LIMIT 3",
                                       ("%" + (rec.get("complex_raw") or "").replace(" ", "")[:12] + "%",)).fetchall()
            if len(rows_any) == 1:
                hit = rows_any[0][0]
        cache[key] = hit
        rec["complex_no"] = hit
        linked += bool(hit)
    return {"linked": linked, "total": len(rows)}


# ── 저장 ─────────────────────────────────────────────────────────────────
def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 9 * 3600))


def _exp() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime(time.time() + 9 * 3600 + KEEP_DAYS * 86400))


def _ukey(complex_no, complex_raw, dong, ho) -> tuple:
    return (complex_no or norm_cx(complex_raw or ""), re.sub(r"\D", "", dong or ""), re.sub(r"\D", "", ho or ""))


def _unit_vals(data_dir: Path, r: dict) -> dict:
    return {"complex_no": r.get("complex_no"), "complex_raw": (r.get("complex_raw") or "")[:60], "dong": (r.get("dong") or "")[:10], "ho": (r.get("ho") or "")[:10],
            "floor": r.get("floor"), "role": (r.get("role") or "")[:10], "name_enc": enc(data_dir, r.get("name")), "phone_enc": enc(data_dir, r.get("phone")),
            "phone_hash": phone_hash(r.get("phone")), "note": (r.get("note") or "")[:200], "area": (r.get("area") or "")[:20] or None}


def save_list(c: sqlite3.Connection, data_dir: Path, realtor_id: str, user_id: str, name: str, filename: str, rows: list[dict], list_id: int | None = None) -> dict:
    """새 명단을 만들거나(list_id 없음) 기존 명단을 업데이트한다. 업데이트 = 동·호가 같은 세대는 새 값으로 갱신
    (빈 칸은 기존 값 유지), 새 세대는 추가, 파일에 없는 기존 세대는 그대로 둔다. 올릴 때 받은 동의로 기간을 새로 연다."""
    now, exp = _now(), _exp()
    added = updated = same = 0
    if list_id:
        cur_rows = {_ukey(u["complex_no"], u["complex_raw"], u["dong"], u["ho"]): u for u in c.execute("SELECT * FROM roster_units WHERE list_id=? AND realtor_id=?", (list_id, realtor_id))}
        c.execute("UPDATE roster_lists SET filename=?, ack_at=?, expires_at=?, updated_at=?, n_updates=COALESCE(n_updates,0)+1, user_id=? WHERE id=? AND realtor_id=?",
                  (filename[:120], now, exp, now, user_id, list_id, realtor_id))
        lid = list_id
    else:
        cur_rows = {}
        lid = c.execute("INSERT INTO roster_lists(realtor_id, user_id, name, filename, ack_at, uploaded_at, expires_at, updated_at) VALUES(?,?,?,?,?,?,?,?)",
                        (realtor_id, user_id, name[:60], filename[:120], now, now, exp, now)).lastrowid
    seen: set = set()
    for r in rows:
        v = _unit_vals(data_dir, r)
        k = _ukey(v["complex_no"], v["complex_raw"], v["dong"], v["ho"])
        if k in seen:
            continue
        seen.add(k)
        old = cur_rows.get(k)
        if old is None:
            c.execute("INSERT INTO roster_units(list_id, realtor_id, complex_no, complex_raw, dong, ho, floor, role, name_enc, phone_enc, phone_hash, note, area, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (lid, realtor_id, v["complex_no"], v["complex_raw"], v["dong"], v["ho"], v["floor"], v["role"], v["name_enc"], v["phone_enc"], v["phone_hash"], v["note"], v["area"], now))
            added += 1
            continue
        # 빈 칸으로 덮어쓰지 않는다. 이름·연락처는 복호화해 비교(암호문은 매번 달라서)
        ch = {}
        for f in ("complex_no", "floor", "role", "note", "area"):
            if v[f] not in (None, "") and v[f] != old[f]:
                ch[f] = v[f]
        for f, raw in (("name_enc", r.get("name")), ("phone_enc", r.get("phone"))):
            if raw and (dec(data_dir, old[f]) or "") != raw:
                ch[f] = v[f]
                if f == "phone_enc":
                    ch["phone_hash"] = v["phone_hash"]
        if ch:
            ch["updated_at"] = now
            c.execute("UPDATE roster_units SET %s WHERE id=?" % ",".join(f"{f}=?" for f in ch), (*ch.values(), old["id"]))
            updated += 1
        else:
            same += 1
    n, nl = c.execute("SELECT count(*), sum(complex_no IS NOT NULL) FROM roster_units WHERE list_id=?", (lid,)).fetchone()
    c.execute("UPDATE roster_lists SET n_rows=?, n_linked=? WHERE id=?", (n, nl or 0, lid))
    c.commit()
    return {"list_id": lid, "added": added, "updated": updated, "same": same, "n_rows": n}


def list_state(row) -> dict:
    """동의 상태 — active(사용 중) · renewable(90일 지나 연장 동의 가능) · expired(180일 지남, 대조·열람 멈춤)."""
    import datetime as _dt
    today = _dt.date.fromisoformat(_now()[:10])
    ack = _dt.date.fromisoformat((row["ack_at"] or row["uploaded_at"])[:10])
    exp = _dt.date.fromisoformat(row["expires_at"][:10])
    days_left, since = (exp - today).days, (today - ack).days
    state = "expired" if days_left < 0 else ("renewable" if since >= RENEW_AFTER else "active")
    return {"state": state, "days_left": days_left, "since_ack": since, "renew_from": str(ack + _dt.timedelta(days=RENEW_AFTER))}


def renew(c: sqlite3.Connection, realtor_id: str, user_id: str, list_id: int) -> dict:
    row = c.execute("SELECT * FROM roster_lists WHERE id=? AND realtor_id=?", (list_id, realtor_id)).fetchone()
    if not row:
        raise LookupError("명단을 찾을 수 없어요")
    st = list_state(row)
    if st["state"] == "active":
        raise ValueError(f"연장 동의는 {st['renew_from']}부터 할 수 있어요")
    now, exp = _now(), _exp()
    c.execute("UPDATE roster_lists SET ack_at=?, expires_at=?, user_id=? WHERE id=?", (now, exp, user_id, list_id))
    c.commit()
    return {"expires_at": exp}


def active_list_ids(c: sqlite3.Connection, realtor_id: str) -> list[int]:
    return [r["id"] for r in c.execute("SELECT * FROM roster_lists WHERE realtor_id=?", (realtor_id,)) if list_state(r)["state"] != "expired"]


def status_counts(c: sqlite3.Connection) -> dict:
    out = {"active": 0, "renewable": 0, "expired": 0}
    for r in c.execute("SELECT * FROM roster_lists"):
        out[list_state(r)["state"]] += 1
    return out


# ── 대조 ─────────────────────────────────────────────────────────────────
def _band(floor: int, total: int | None) -> str:
    """정확한 층을 광고의 고·중·저로 옮긴다. 광고 쪽 관행: 저=1~(총/3), 고=상위 1/3."""
    if not total or total <= 0:
        return "저" if floor <= 3 else "중"
    if floor <= max(3, total // 3):
        return "저"
    if floor >= total - max(2, total // 3) + 1:
        return "고"
    return "중"


PYEONG = 3.305785


def complex_types(main_db: sqlite3.Connection, complex_no: str, ads=None) -> list[tuple]:
    """단지의 실제 타입 목록 [(이름, 공급㎡, 전용㎡)]. 단지 면적표가 없으면 광고에서 모은다."""
    rows = [(r[0], r[1] or 0.0, r[2] or 0.0) for r in main_db.execute(
        "SELECT pyeong_name, supply_area, exclusive_area FROM complex_areas WHERE complex_no=?", (complex_no,))]
    if not rows and ads:
        seen = {}
        for a in ads:
            if a["area_name"] and a["area_name"] not in seen:
                seen[a["area_name"]] = (a["area_name"], float(a["area1_m2"] or 0), float(a["area2_m2"] or 0))
        rows = list(seen.values())
    return rows


def resolve_type(text: str | None, types: list[tuple]) -> tuple[set, str]:
    """명단의 타입 칸 → 그 단지의 실제 타입 이름 집합. ('', '') 이면 명단에 타입이 없음, 빈 집합+사유면 못 읽음.
    읽는 순서: ① 타입 이름 그대로(113A) ② 평(34평 → 공급 112㎡ 근처, 안 되면 전용평)
    ③ 숫자(+글자): 타입 이름 앞 숫자가 같은 것 → 없으면 전용·공급 면적이 같은 것. 소수(76.79)는 면적으로만.
    글자(84A 의 A)가 있으면 후보 중 같은 글자로 끝나는 타입으로 좁힌다."""
    t = re.sub(r"\s+", "", str(text or "")).upper().replace("M²", "㎡").replace("M2", "㎡")
    if not t:
        return set(), ""
    if not types:
        return set(), "단지 타입 정보 없음"
    names = {n.upper(): n for n, _, _ in types}
    if t in names:
        return {names[t]}, "타입 이름"
    m = re.match(r"(\d{1,3}(?:\.\d+)?)", t)
    if not m:
        return set(), "타입을 읽지 못함"
    v = float(m.group(1))
    rest = t[m.end():]
    if "평" in rest or "PY" in rest:
        s = v * PYEONG
        # 사무소마다 공급÷3.3 을 내림하거나 반올림해 부른다(115.54㎡ = 34평이자 35평) — 둘 다, 그리고 ±2.5㎡
        got = {n for n, sup, ex in types if sup and (int(sup / PYEONG) == int(v) or round(sup / PYEONG) == int(v) or abs(sup - s) <= 2.5)}
        if not got:
            got = {n for n, sup, ex in types if ex and abs(ex - s) <= 1.5}
        return (got, "평") if got else (set(), f"{v:g}평에 맞는 타입 없음")
    letter = re.sub(r"[^A-Z]", "", rest.replace("㎡", "").replace("형", "").replace("타입", "").replace("TYPE", ""))[:2]
    if "." in m.group(1):
        got = {n for n, sup, ex in types if (ex and abs(ex - v) <= 0.005) or (sup and abs(sup - v) <= 0.005)} \
            or {n for n, sup, ex in types if (ex and abs(ex - v) <= 0.5) or (sup and abs(sup - v) <= 0.5)}
    else:
        # 같은 숫자를 두 갈래로 읽는다 — 타입 이름 앞 숫자(단지가 공급 기준이면 84B=전용59)와 전용·공급 면적(84=전용84).
        # 글자(84A 의 A)가 한쪽에만 맞으면 그쪽, 글자가 없고 두 갈래가 다르면 둘 다(놓치지 않게).
        iv = int(v)
        by_name = {n for n, _, _ in types if re.match(r"(\d+)", n) and int(re.match(r"(\d+)", n).group(1)) == iv}
        by_area = {n for n, sup, ex in types if ex and abs(ex - v) <= 1.0} or {n for n, sup, ex in types if sup and abs(sup - v) <= 1.0}
        if letter:
            def _lt(ss):
                return {n for n in ss if re.sub(r"[\d.]", "", n.upper()).startswith(letter)}
            a1, b1 = _lt(by_name), _lt(by_area)
            got = (a1 | b1) or (by_name | by_area)
        else:
            got = by_name | by_area
        return (got, "면적") if got else (set(), f"{t}에 맞는 타입 없음")
    return (got, "면적") if got else (set(), f"{t}에 맞는 타입 없음")


def match(c: sqlite3.Connection, main_db: sqlite3.Connection, data_dir: Path, realtor_id: str, list_id: int | None = None, only_others: bool = False) -> dict:
    """사무소 명단 ↔ 광고 중 매물. 동이 같고 (층이 같거나, 광고가 고·중·저면 그 층대에 들면) 후보."""
    ok_ids = active_list_ids(c, realtor_id)          # 동의 기간이 지난 명단은 대조하지 않는다
    if list_id:
        ok_ids = [x for x in ok_ids if x == list_id]
    units = c.execute("SELECT * FROM roster_units WHERE realtor_id=? AND complex_no IS NOT NULL AND list_id IN (%s)" % (",".join("?" * len(ok_ids)) or "NULL"),
                      (realtor_id, *ok_ids)).fetchall()
    by_cx: dict[str, list] = {}
    for u in units:
        by_cx.setdefault(u["complex_no"], []).append(u)
    out_units, n_ads = [], 0
    for cx, us in by_cx.items():
        ads = main_db.execute(
            "SELECT l.article_no, l.building_name, l.floor_info, l.trade_type, l.area_name, l.area1_m2, l.area2_m2, l.deal_or_warrant_price, l.rent_price, l.realtor_id, l.realtor_name, "
            "l.article_confirm_ymd, l.direction, cx.complex_name, cx.high_floor FROM listings_current l JOIN complexes cx ON cx.complex_no=l.complex_no WHERE l.complex_no=?", (cx,)).fetchall()
        if not ads:
            continue
        idx: dict[str, list] = {}
        for a in ads:
            d = re.sub(r"\D", "", a["building_name"] or "")
            idx.setdefault(d, []).append(a)
        types = complex_types(main_db, cx, ads)
        for u in us:
            d = re.sub(r"\D", "", u["dong"] or "")
            if not d or d not in idx or not u["floor"]:
                continue
            # 명단에 타입이 있으면 그 단지의 실제 타입으로 바꿔 광고 타입과 맞춘다(같은 층 다른 타입 광고를 걸러 정확도↑)
            utypes, why = resolve_type(u["area"] if "area" in u.keys() else None, types)
            hits = []
            for a in idx[d]:
                fi = str(a["floor_info"] or "")
                top = fi.split("/")[0].strip()
                tot = None
                try:
                    tot = int(fi.split("/")[1]) if "/" in fi else None
                except ValueError:
                    tot = None
                if top.isdigit():
                    if int(top) != u["floor"]:
                        continue
                    strength = "층 일치"
                elif top in ("고", "중", "저"):
                    if _band(u["floor"], tot or a["high_floor"]) != top:
                        continue
                    strength = f"층대 일치({top}층)"
                else:
                    continue
                if utypes and a["area_name"] not in utypes:
                    continue
                mine = a["realtor_id"] == realtor_id
                if only_others and mine:
                    continue
                price = a["deal_or_warrant_price"] or 0
                hits.append({"article_no": a["article_no"], "trade": a["trade_type"], "price": price, "rent": a["rent_price"], "area_name": a["area_name"], "excl_m2": a["area2_m2"],
                             "floor_info": fi, "direction": a["direction"] or "", "realtor_name": a["realtor_name"] or "", "mine": mine, "hidden_realtor": not a["realtor_id"],
                             "confirm_ymd": a["article_confirm_ymd"] or "", "strength": strength})
            if hits:
                # 같은 집을 여러 사무소가 광고한다 — 면적타입·거래·가격·층 표기가 같으면 한 집으로 묶는다
                houses: dict[tuple, dict] = {}
                for h in hits:
                    k = (h["area_name"], h["trade"], h["price"], h["rent"], h["floor_info"])
                    g = houses.setdefault(k, {**h, "n_offices": 0, "offices": [], "article_nos": []})
                    g["n_offices"] += 1
                    g["article_nos"].append(h["article_no"])
                    if h["realtor_name"] and h["realtor_name"] not in g["offices"]:
                        g["offices"].append(h["realtor_name"])
                    g["mine"] = g["mine"] or h["mine"]
                hs = sorted(houses.values(), key=lambda h: (h["strength"] != "층 일치", -h["n_offices"]))
                exact = any(h["strength"] == "층 일치" for h in hs)
                n_ads += len(hits)
                out_units.append({"unit_id": u["id"], "complex_no": cx, "complex_name": ads[0]["complex_name"], "dong": u["dong"], "ho": u["ho"], "floor": u["floor"], "role": u["role"] or "",
                                  "grade": "층 일치" if exact else "층대만 일치",
                                  "type_raw": (u["area"] if "area" in u.keys() else "") or "", "type_ok": bool(utypes), "types": sorted(utypes), "type_note": "" if utypes else why,
                                  "name_masked": mask_name(dec(data_dir, u["name_enc"])), "phone_masked": mask_phone(dec(data_dir, u["phone_enc"])), "note": u["note"] or "",
                                  "houses": [h for h in hs if h["strength"] == "층 일치"] if exact else hs})
    out_units.sort(key=lambda x: (x["grade"] != "층 일치", x["complex_name"], int(re.sub(r"\D", "", x["dong"]) or 0), x["floor"]))
    return {"units": out_units, "n_units": len(out_units), "n_exact": sum(1 for x in out_units if x["grade"] == "층 일치"),
            "n_type_ok": sum(1 for x in out_units if x["type_ok"]), "n_exact_type": sum(1 for x in out_units if x["type_ok"] and x["grade"] == "층 일치"),
            "n_houses": sum(len(x["houses"]) for x in out_units), "n_ads": n_ads, "n_roster": len(units)}


if __name__ == "__main__":   # daily_run step 11h: 명단 동의 상태 집계(지우지 않는다)
    import sys
    _dd = Path(__file__).resolve().parent.parent / "data"
    if not db_path(_dd).exists():
        print("roster: 명단 없음"); sys.exit(0)
    with connect(_dd) as _c:
        print("roster:", status_counts(_c))
