#!/usr/bin/env python3
"""본체 줄이기 1단계 — 안 잰 다섯 값을 잰다. 전부 읽기 전용."""
import os, sqlite3, random, re, sys, time
D = '/opt/koczip/data'
def ro(p): 
    c = sqlite3.connect(f'file:{p}?mode=ro', uri=True); c.row_factory = sqlite3.Row; return c
def drop(p):
    try:
        f = os.open(p, os.O_RDONLY); os.posix_fadvise(f, 0, 0, os.POSIX_FADV_DONTNEED); os.close(f)
    except OSError: pass
def mb(b): return b / 1048576
def sec(t): print(f'\n{"="*72}\n{t}\n{"="*72}')

# ── ① VACUUM 으로 회수 가능한 조각 공간 ──────────────────────────────────
sec('① VACUUM 회수량 — 빈 페이지가 파일에 남아 있는 몫')
tot_free = 0
for f in sorted(os.listdir(D)):
    if not f.endswith('.sqlite'): continue
    p = f'{D}/{f}'
    try:
        c = ro(p)
        ps = c.execute('PRAGMA page_size').fetchone()[0]
        pc = c.execute('PRAGMA page_count').fetchone()[0]
        fl = c.execute('PRAGMA freelist_count').fetchone()[0]
        c.close()
    except Exception as e:
        print(f'  {f:<28} 못 읽음 ({type(e).__name__})'); continue
    free = fl * ps; tot_free += free
    if pc:
        print(f'  {f:<28} {mb(pc*ps):>8,.0f} MB 중 빈 페이지 {mb(free):>7,.0f} MB ({fl/pc*100:>4.1f}%)')
print(f'\n  → VACUUM 으로 회수 가능 합계 {mb(tot_free):,.0f} MB')

# ── ② articles 죽은 매물 비율 ────────────────────────────────────────────
sec('② articles — 지금 살아 있지 않은 매물의 몫')
try:
    c = ro(f'{D}/naverreal.sqlite')
    t0 = time.time()
    rows = c.execute('SELECT last_seen_date, COUNT(*) n FROM articles GROUP BY 1 ORDER BY 1').fetchall()
    tot = sum(r['n'] for r in rows)
    print(f'  전체 {tot:,}행 · last_seen 분포 조회 {time.time()-t0:.1f}초')
    print(f'  {"기준":<14}{"그 이전":>14}{"비율":>8}{"추정 회수":>12}')
    tbl_mb = 4481  # 데이터 구조도 실측값
    import datetime as dt
    today = dt.date.today()
    for days in (7, 14, 30, 60, 90):
        cut = (today - dt.timedelta(days=days)).isoformat()
        old = sum(r['n'] for r in rows if (r['last_seen_date'] or '') < cut)
        print(f'  {days:>3}일 이전     {old:>14,}{old/tot*100:>7.1f}%{tbl_mb*old/tot:>10,.0f} MB')
    print(f'  가장 오래된 last_seen: {rows[0]["last_seen_date"]} · 가장 최근: {rows[-1]["last_seen_date"]}')
    c.close()
except Exception as e:
    print(f'  실패: {type(e).__name__} {e}')

# ── ③ raw 원본이 차지하는 몫 ─────────────────────────────────────────────
sec('③ raw JSON 이 차지하는 몫 — 표본 2,000행')
def raw_share(path, table, tbl_mb, label):
    try:
        c = ro(path)
        cols = [r[1] for r in c.execute(f'PRAGMA table_info({table})')]
        if 'raw' not in cols: 
            print(f'  {label:<22} raw 칸 없음'); c.close(); return
        mx = c.execute(f'SELECT MAX(rowid) FROM {table}').fetchone()[0] or 0
        if not mx: c.close(); return
        random.seed(3); ids = [random.randrange(1, mx+1) for _ in range(2000)]
        q = ','.join('?'*len(ids))
        other = '+'.join(f'COALESCE(LENGTH(CAST({x} AS BLOB)),0)' for x in cols if x != 'raw')
        r = c.execute(f'SELECT AVG(COALESCE(LENGTH(raw),0)), AVG({other}), COUNT(*) '
                      f'FROM {table} WHERE rowid IN ({q})', ids).fetchone()
        c.close()
        if not r[2]: print(f'  {label:<22} 표본 없음'); return
        rawb, othb = r[0] or 0, r[1] or 0
        share = rawb / (rawb + othb) if (rawb + othb) else 0
        print(f'  {label:<22} raw {rawb:>7,.0f} B/행 · 나머지 {othb:>6,.0f} B/행 · '
              f'raw 비중 {share*100:>4.0f}% → 약 {tbl_mb*share:>6,.0f} MB')
    except Exception as e:
        print(f'  {label:<22} 실패 {type(e).__name__}')
raw_share(f'{D}/naverreal.sqlite', 'articles', 4481, 'articles')
raw_share(f'{D}/naverreal.sqlite', 'listings_current', 721, 'listings_current')
for cat, m in (('sangga',1700),('house',558),('office',550),('villa',538),('land',489),
               ('building',356),('oneroom',346),('factory',320),('knowledge',164),('redev',27)):
    raw_share(f'{D}/listings_{cat}.sqlite', 'listings', m, f'listings_{cat}')

# ── ④ 실거래를 실제로 몇 개월치 조회하나 ─────────────────────────────────
sec('④ 실거래 조회 기간 분포 — 24개월 초과분을 내려도 되나')
try:
    c = ro(f'{D}/logs.sqlite')
    rows = c.execute("SELECT path, query FROM event_log "
                     "WHERE path LIKE '%transaction%' OR path LIKE '%/stats%' "
                     "   OR query LIKE '%months%' OR query LIKE '%years%'").fetchall()
    c.close()
    print(f'  기간 파라미터가 있는 조회 {len(rows):,}건')
    from collections import Counter
    cnt = Counter()
    for r in rows:
        m = re.search(r'months=(\d+)', r['query'] or '')
        cnt[int(m.group(1)) if m else '없음(기본값)'] += 1
    for k, v in sorted(cnt.items(), key=lambda x: -x[1])[:10]:
        lab = f'{k}개월' if isinstance(k, int) else k
        over = ' ← 24개월 초과' if isinstance(k, int) and k > 24 else ''
        print(f'    {lab:<14}{v:>8,}건 ({v/max(1,len(rows))*100:>5.1f}%){over}')
    over = sum(v for k, v in cnt.items() if isinstance(k, int) and k > 24)
    print(f'\n  → 24개월 초과 조회 {over:,}건 ({over/max(1,len(rows))*100:.2f}%)')
except Exception as e:
    print(f'  실패: {type(e).__name__} {e}')

# ── ⑤ article_events 인덱스 4종이 실제로 쓰이나 ──────────────────────────
sec('⑤ article_events 인덱스 실사용 — API 가 실제로 던지는 쿼리로')
try:
    c = ro(f'{D}/naverreal.sqlite')
    qs = [
      ("최근 변동일", "SELECT MAX(ae.event_date) FROM article_events ae WHERE ae.event_type='PRICE_CHANGE'"),
      ("상승·하락 집계", "SELECT CASE WHEN ae.new_price>ae.old_price THEN 'up' ELSE 'down' END, COUNT(*) "
                    "FROM article_events ae WHERE ae.event_type='PRICE_CHANGE' AND ae.event_date='2026-08-07' GROUP BY 1"),
      ("변동 피드", "SELECT e.event_date,e.complex_no,e.trade_type FROM article_events e "
                "WHERE e.event_type='PRICE_CHANGE' ORDER BY e.event_date DESC, "
                "abs(e.new_price-e.old_price) DESC LIMIT 30"),
      ("단지별 변동", "SELECT * FROM article_events WHERE complex_no='111515' AND event_date>='2026-07-01'"),
      ("매물별 이력", "SELECT * FROM article_events WHERE article_no='2636633244'"),
    ]
    used = set()
    for lab, q in qs:
        plan = [r[3] for r in c.execute('EXPLAIN QUERY PLAN ' + q)]
        for p in plan:
            for ix in re.findall(r'USING (?:COVERING )?INDEX (\S+)', p): used.add(ix)
        print(f'  {lab:<14} {plan[0][:88]}')
    print()
    allix = [r[0] for r in c.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='article_events'")]
    for ix in allix:
        sz = c.execute('SELECT ROUND(SUM(pgsize)/1048576.0) FROM dbstat WHERE name=?', (ix,)).fetchone()[0]
        print(f'  {ix:<34} {sz or 0:>6,.0f} MB   {"쓰임" if ix in used else "★ 위 쿼리에선 안 쓰임"}')
    c.close()
except Exception as e:
    print(f'  실패: {type(e).__name__} {e}')
print('\n측정 끝.')
