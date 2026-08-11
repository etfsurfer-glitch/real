#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SNS 소재 레이더 — 조회 API (루프백 전용).

본서버 FastAPI 가 SSH 터널로 붙어 관리자 화면에 중계한다. 이 서버는 공인 IP 에
열지 않는다(carosell 과 같은 구조).

Run: python3 server.py   →  127.0.0.1:4310
"""
import json
import re
import sqlite3
import subprocess
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE = Path("/opt/koczip-radar")
DB = BASE / "radar.sqlite"
PORT = 4310

FIELDS = ("id, post_key, author, text, url, like_count, reply_count, repost_count,"
          " quote_count, age_min, keyword, keywords_all, engagement, velocity,"
          " analyzed_at, humor, satire, gossip, controversy, surprise, empathy, hook,"
          " realestate, ai_score, categories, ai_reason, content_idea, final_score,"
          " saved, excluded, first_seen_at, collected_at")


def db():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def rows_to_list(rows):
    return [dict(r) for r in rows]


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def log_message(self, *a):                      # 접근로그는 journald 를 더럽히기만 한다
        pass

    # ── 조회 ──────────────────────────────────────────────────────────────
    def do_GET(self):                               # noqa: N802
        u = urlparse(self.path)
        q = parse_qs(u.query)
        one = lambda k, d="": (q.get(k) or [d])[0]  # noqa: E731
        try:
            if u.path == "/api/posts":
                hours = int(one("hours", "24") or 24)
                cat = one("category")
                mode = one("mode", "top")           # top / saved / fresh
                limit = min(max(int(one("limit", "50") or 50), 1), 200)
                w = ["excluded=0"]
                p = []
                if mode == "saved":
                    w.append("saved=1")
                else:
                    w.append("first_seen_at >= datetime('now','+9 hours', ?)")
                    p.append(f"-{hours} hours")
                if cat:
                    w.append("(','||COALESCE(categories,'')||',') LIKE ?")
                    p.append(f"%,{cat},%")
                order = "first_seen_at DESC" if mode == "fresh" else "final_score DESC"
                with db() as c:
                    rows = c.execute(
                        f"SELECT {FIELDS} FROM posts WHERE {' AND '.join(w)}"
                        f" ORDER BY {order} LIMIT ?", (*p, limit)).fetchall()
                return self._send(200, {"posts": rows_to_list(rows)})

            if u.path == "/api/stats":
                with db() as c:
                    s = c.execute(
                        "SELECT COUNT(*) total,"
                        " SUM(first_seen_at >= datetime('now','+9 hours','-24 hours')) day,"
                        " SUM(analyzed_at IS NOT NULL) analyzed,"
                        " SUM(saved=1) saved FROM posts WHERE excluded=0").fetchone()
                    last = c.execute(
                        "SELECT started_at, ended_at, keywords, found, fresh, error"
                        " FROM runs ORDER BY id DESC LIMIT 1").fetchone()
                    cats = c.execute(
                        "SELECT categories FROM posts WHERE categories IS NOT NULL"
                        " AND categories<>'' AND excluded=0"
                        "   AND first_seen_at >= datetime('now','+9 hours','-24 hours')"
                    ).fetchall()
                cnt = {}
                for r in cats:
                    for t in (r["categories"] or "").split(","):
                        if t:
                            cnt[t] = cnt.get(t, 0) + 1
                return self._send(200, {
                    "stats": dict(s) if s else {},
                    "last_run": dict(last) if last else None,
                    "categories": sorted(cnt.items(), key=lambda x: -x[1]),
                })

            if u.path == "/api/keywords":
                with db() as c:
                    rows = c.execute(
                        "SELECT id, keyword, category, enabled, priority, every_min,"
                        " last_run_at FROM keywords ORDER BY enabled DESC, priority DESC,"
                        " keyword").fetchall()
                return self._send(200, {"keywords": rows_to_list(rows)})

            return self._send(404, {"error": "not found"})
        except Exception as e:                      # noqa: BLE001
            return self._send(500, {"error": str(e)[:300]})

    # ── 조작 ──────────────────────────────────────────────────────────────
    def do_POST(self):                              # noqa: N802
        u = urlparse(self.path)
        n = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(n) or b"{}")
        except Exception:                           # noqa: BLE001
            body = {}
        try:
            m = re.match(r"^/api/posts/(\d+)/(save|exclude)$", u.path)
            if m:
                pid, act = int(m.group(1)), m.group(2)
                col = "saved" if act == "save" else "excluded"
                val = 1 if body.get("on", True) else 0
                with db() as c:
                    c.execute(f"UPDATE posts SET {col}=? WHERE id=?", (val, pid))
                    c.commit()
                return self._send(200, {"ok": True})

            if u.path == "/api/keywords":
                kw = str(body.get("keyword") or "").strip()
                if not kw:
                    return self._send(400, {"error": "keyword 가 비었다"})
                with db() as c:
                    c.execute(
                        "INSERT INTO keywords(keyword, category, enabled, priority, every_min)"
                        " VALUES(?,?,1,?,?) ON CONFLICT(keyword) DO UPDATE SET"
                        " category=excluded.category, priority=excluded.priority,"
                        " every_min=excluded.every_min",
                        (kw, str(body.get("category") or "etc"),
                         int(body.get("priority") or 5), int(body.get("every_min") or 30)))
                    c.commit()
                return self._send(200, {"ok": True})

            m = re.match(r"^/api/keywords/(\d+)/toggle$", u.path)
            if m:
                with db() as c:
                    c.execute("UPDATE keywords SET enabled = 1-enabled WHERE id=?",
                              (int(m.group(1)),))
                    c.commit()
                return self._send(200, {"ok": True})

            if u.path == "/api/run":
                # 수집·분석을 지금 한 번 돌린다(관리자 화면의 '지금 수집' 버튼).
                # 오래 걸리므로 띄우고 바로 응답한다 — 진행은 /api/stats 의 last_run 으로 본다.
                subprocess.Popen(["/usr/bin/systemctl", "start", "koczip-radar-collect"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return self._send(202, {"ok": True})

            return self._send(404, {"error": "not found"})
        except Exception as e:                      # noqa: BLE001
            return self._send(500, {"error": str(e)[:300]})


if __name__ == "__main__":
    print(f"SNS 레이더 API → http://127.0.0.1:{PORT}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
