"""AI 자가테스트: 예상 질문 100개를 run_agent로 돌려 활동로그에 누적하고,
휴리스틱으로 1차 평가한 뒤 리포트(JSON)를 만든다. AI 답변 품질 점검·회귀 추적용.

실행:  cd /opt/koczip && .venv/bin/python scripts/ai_selftest.py [--only 1,5,70] [--tag run1]
산출:  data/ai_selftest_report.json  (+ 콘솔 요약)
로그:  event_log(kind='ai_ask', provider='selftest', detail.selftest=True)
"""
import os
import sys
import re
import json
import time
import argparse
from collections import Counter

sys.path.insert(0, os.getcwd())               # scripts.local_api
sys.path.insert(0, os.path.join(os.getcwd(), "scripts"))  # ai_agent
from dotenv import load_dotenv
load_dotenv(".env")
import ai_agent
import scripts.local_api as api

# 카테고리별 예상 질문 100 — 실제 로그 질문을 변형 + 전 도구/엣지 커버
QUESTIONS = [
    # A. 가장 비싼/싼 (find_apartments sort) — 통합시 포함
    "청주 가장 비싼 아파트", "수원 제일 비싼 아파트 알려줘", "성남 비싼 아파트 top",
    "고양시 가장 비싼 아파트", "용인 제일 비싼 아파트", "강남구에서 제일 비싼 아파트",
    "제주 가장 싼 아파트", "대전 서구 싼 아파트 알려줘", "부산 해운대구 비싼 아파트 순서대로",
    "전주 가장 비싼 아파트",
    # B. 평형/가격대 매물 (find_apartments)
    "대전 30평대 매매 5억 이하 매물", "서울 강남구 20평대 매물", "수원 영통구 30평대 매물 보여줘",
    "인천 40평대 아파트 매매", "대구 수성구 10억 이하 30평대", "세종 30평대 매물 보여줘",
    "분당 국민평형 매매 매물", "천안 25평 전세 매물",
    # C. 급매 (find_quick_deals)
    "서울 급매 찾아줘", "청주 급매 찾아줘", "수원 30평대 급매", "을지로 급매 찾아줘",
    "대전 둔산동 급매 10% 이상 할인", "부산 전세 급매", "인천 연수구 급매 최근 6개월", "강남 급매 매매",
    # D. 단지 정보 (get_complex_info)
    "둔산 대우아파트 설명해줘", "헬리오시티 정보 알려줘", "은마아파트 세대수랑 시세",
    "잠실엘스 어때", "마포래미안푸르지오 시세", "반포자이 실거래가",
    # E. 시세/분위기
    "대전 시세가 어떻게돼?", "서울 요즘 거래 활발해?", "강남구 분위기 어때",
    "세종 부동산 분위기", "수원 시장 어때", "제주 집값 어때",
    # F. 거래량/통계
    "서울 5월이랑 6월 거래량 비교", "대전 최근 거래량 많은 단지", "강남구 거래량 순위",
    "2026년 거래 활발한 단지 전국", "경기도 거래량 많은 단지", "서울 거래량 26년 1월부터 지금까지",
    # G. 신고가
    "서울 최근 신고가 단지", "강남구 신고가 경신 단지", "대전 신고가 단지 알려줘",
    "전국 최고가 거래 아파트", "수원 신고가 단지",
    # H. 취소거래
    "서울 취소거래 알려줘", "강남구 직거래 취소거래", "대전 해제된 거래 있어?", "전국 취소거래 많은 곳",
    # I. 매물수
    "실거래 말고 매물수가 궁금해", "대전시랑 서울시 매물수 차이", "강남구 매물 몇 개야", "서울 전세 매물수",
    # J. 지역 비교(멀티 도구)
    "수원 실거래하고 서울 실거래 비교해줘", "대전이랑 세종 집값 비교", "강남구랑 서초구 시세 비교",
    "부산이랑 대구 거래량 비교", "제주랑 서울 아파트값 차이",
    # K. 실거래 추이/최신
    "서울 실거래 신고 추이", "서울 2026년 6월 실거래", "오늘 서울 실거래 신고가 어때",
    "대전 최근 실거래가 알려줘", "서울 실거래가 오늘 신고된거 알려줘",
    # L. 중개사 (rank_realtors / find_realtor)
    "중개사무소 직원수 순위", "전국 중개사 업력 순위", "청주 업력 순위 보여줘",
    "서울 직원수 많은 중개사무소", "강남구 중개사무소 순위", "직원수 top20 알려줘",
    "봇당이부동산 정보", "제이에스부동산중개 어디야", "매물 많이 가진 중개사무소 순위",
    "대전 중개사무소 업력 순위",
    # M. 멀티 구
    "영통구 기흥구 수지구 동탄구 30평대 거래량과 신고가", "수원 영통구 용인 기흥구 화성 동탄구 실거래 활발한 단지",
    "강남 서초 송파 거래량 비교",
    # N. 맥락 없는 후속/대명사
    "반대로 비싼거부터 보여줘", "거기서 30평대만", "그 단지 전세는?", "수지구나 동탄구는 없는거야?",
    # O. 엣지/범위밖/모호
    "안녕", "넌 뭘 할 수 있어?", "내일 집값 오를까?", "주식 추천해줘",
    "서울 아파트 살까 말까", "ㅁㄴㅇㄹ", "청약 정보 알려줘", "대출 얼마나 받을 수 있어",
    # P. 오타/붙임
    "직원수 top20알려주ㅏ", "대전아파트시세", "서울집값얼마야", "제주도아파트비싼곳",
    # Q. 광역/전국
    "전국에서 제일 비싼 아파트", "전국 평당가 높은 단지", "전국 저평가 단지 알려줘", "갭투자 유리한 단지 추천",
    # R. 복합질문(다중 의도·다중 제약) — 통합 점검
    "강남구 30평대 매매 급매 할인율 높은 순으로 보여주고 그 단지 급매 가진 중개사 연락처도",
    "은마아파트 시세랑 근처 급매 있으면 같이 알려줘",
    "대전 둔산동 전세 급매랑 매매 급매 둘 다 보여줘",
    "마포구 국평 10억 이하 매물 중에서 전세가율도 같이",
    "서울에서 거래량 많은 단지 top3랑 각각 신고가도 알려줘",
    "수원 영통구 30평대 급매 찾아주고 거래량도 활발한지",
    "반포자이랑 잠실엘스 시세 비교해줘",
    "강남구 20평대 전세 5억 이하 매물 중 역세권 위주로",
    "세종 30평대 매매 급매 중 10% 이상 할인된거만",
    "헬리오시티 전세 실거래랑 지금 나온 전세 매물 같이",
    "부산 해운대 비싼 아파트 top5랑 평당가도",
    "대구 수성구 거래량이랑 신고가 단지 같이 알려줘",
    "인천 연수구 급매 매매랑 전세 중 할인 큰 순으로",
    "강남 서초 송파 중 어디가 전세가율 제일 높아",
    "서울 25평 매매 8억 이하 중 거래 활발한 동네",
    "용인 수지구 30평대 급매 있으면 중개사도 연결해줘",
    "성남 분당 국평 매매 시세랑 최근 거래량 추이",
    "노원구 20평대 전세 매물이랑 그 동네 전세가율",
    "광교 신도시 대장 아파트 시세랑 급매",
    "동탄 30평대 매매 급매 할인율순 그리고 신고가 단지도",
    "청량리 재개발 투자 매물이랑 분양권 같이 알려줘",
    "송파구 헬리오시티 매물수랑 급매 가진 중개사 top",
    "대전 유성구 30평대 거래량 많은 단지랑 평당가 순위",
    "잠실 30평대 매매 25억 이하 중 저평가된거",
    "서초구 반포동 전세 급매랑 매매 신고가 같이",
]

TEST_USER = {"id": "selftest-bot", "email": "selftest@koczip", "provider": "selftest"}


def heuristics(ans, tools, ms):
    f = []
    a = ans or ""
    if not a.strip():
        f.append("EMPTY")
        return f
    low = a.lower()
    if any(s in a for s in ("찾지 못", "찾을 수 없", "오류가", "처리 중 오류")) or "error" in low:
        f.append("ERROR_MSG")
    # 환각: 도구 호출 0인데 구체 수치 단언
    if not tools and re.search(r"\d[\d,\.]*\s*(억|만원|세대|건|위|평\b)", a):
        f.append("HALLUC?")
    # 중복: 동일 줄 3회 이상(8자 초과)
    lines = [ln.strip() for ln in a.split("\n") if len(ln.strip()) > 8]
    if lines:
        ln, cnt = Counter(lines).most_common(1)[0]
        if cnt >= 3:
            f.append(f"DUP{cnt}")
    if ms > 30000:
        f.append("SLOW")
    if len(a) < 15:
        f.append("SHORT")
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")     # "1,5,70" → 해당 번호만
    ap.add_argument("--tag", default="run")
    args = ap.parse_args()
    only = {int(x) for x in args.only.split(",") if x.strip()} if args.only else None

    results = []
    for i, q in enumerate(QUESTIONS, 1):
        if only and i not in only:
            continue
        t0 = time.perf_counter()
        err = None
        try:
            r = ai_agent.run_agent(q)
            ans = r.get("answer") or ""
            tools = r.get("tools_used") or []
        except Exception as e:
            ans, tools, err = "", [], f"{type(e).__name__}: {e}"
        ms = int((time.perf_counter() - t0) * 1000)
        flags = heuristics(ans, tools, ms)
        if err:
            flags.append("EXC")
        tnames = [t.get("tool") for t in tools]
        targs = [t.get("args") for t in tools]
        try:
            api._log_event("ai_ask", user_id=TEST_USER["id"], email=TEST_USER["email"],
                           provider="selftest", path="/ai/ask", method="POST", status=200,
                           duration_ms=ms,
                           detail={"question": q, "answer": ans[:8000], "tools": tools,
                                   "selftest": True, "tag": args.tag})
        except Exception:
            pass
        results.append({"i": i, "q": q, "tools": tnames, "args": targs,
                        "ms": ms, "flags": flags, "answer": ans, "err": err})
        print(f"[{i:3}/{len(QUESTIONS)}] {ms:6}ms {(','.join(flags) or 'ok'):14} "
              f"{'+'.join(tnames) or '(no-tool)':28.28} {q[:34]}", flush=True)

    out = "data/ai_selftest_report.json"
    # --only 재실행 시 기존 리포트와 병합(번호 기준 덮어쓰기)
    if only and os.path.exists(out):
        prev = {r["i"]: r for r in json.load(open(out, encoding="utf-8"))}
        for r in results:
            prev[r["i"]] = r
        results = [prev[k] for k in sorted(prev)]
    json.dump(results, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    fc = Counter(fl for r in results for fl in r["flags"])
    print("\n=== FLAG 요약 ===")
    for k, v in fc.most_common():
        print(f"  {k}: {v}")
    bad = [r for r in results if r["flags"]]
    print(f"\n문제 의심 문항: {len(bad)}/{len(results)}")
    for r in bad:
        print(f"  #{r['i']:3} [{','.join(r['flags'])}] {r['q']}")
    print(f"\n리포트: {out}")


if __name__ == "__main__":
    main()
