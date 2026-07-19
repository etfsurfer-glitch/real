"""부동산 전문 AI 에이전트 (콕집).

사용자 자연어 질문 → Gemini 가 '도구(=우리 엔드포인트)'를 골라 호출 →
결과(JSON)만 받아 한국어로 답변. DB 전체를 LLM 에 넘기지 않는다.

- LLM 호출은 _llm 한 군데로 추상화 (나중에 Claude 등으로 교체 가능).
- 도구는 기존 local_api 함수를 내부에서 직접 호출(HTTP 아님 → 빠르고 무료).
- 지역 자연어("대전 서구 둔산동")는 regions 테이블로 코드 변환(resolve 내부 처리).

주의: Gemini SDK 가 도구 함수의 타입힌트를 introspection 하므로
`from __future__ import annotations` 를 쓰면 안 된다(힌트가 문자열이 되어 깨짐).
"""
import os
import re
import time
from functools import lru_cache
from pathlib import Path
import sqlite3

DB_PATH = Path(os.getenv("LOCAL_DB_PATH", "./data/naverreal.sqlite")).resolve()
# 자료 취합(도구호출+한국어 요약)엔 Flash-Lite로 충분 — Flash 대비 ~70% 저렴.
# GEMINI_MODEL 환경변수로 덮어쓸 수 있음(품질 이슈 시 gemini-2.5-flash로 즉시 롤백).
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

SYSTEM_PROMPT = (
    "너는 '콕집' 부동산 데이터 분석가야. 한국 아파트 매물·실거래·중개사 데이터를 다룬다.\n"
    "규칙:\n"
    "1) 수치가 필요한 질문은 반드시 제공된 도구로 조회해서 답한다. 도구 결과에 없는 가격·건수를 지어내지 마라.\n"
    "1.2) [도구 결과가 있으면 반드시 그걸로 답하라] 도구가 결과(목록·요약)를 반환했다면, 비어 보여도 그 데이터로 답하라. "
    "절대 '질문을 이해하지 못했어요'·'어느 지역이요?' 같은 폴백/되묻기를 쓰지 마라. 결과가 0건이면 '해당 조건 거래가 없어요'라고 정직히 답한다.\n"
    "1.5) [환각 절대 금지 — 최우선] 이번 턴에 도구를 호출하지 않았다면 거래량·가격·시세·직원수·건수 등 "
    "어떤 구체적 숫자도, 그리고 단지명·중개사무소명 같은 고유명사도 말하지 마라(예: '래미안대치팰리스가 거래 많다'를 "
    "도구 없이 쓰면 안 된다). 기억·추정으로 숫자나 단지명을 만들어내는 것은 절대 금지다(가짜 데이터는 서비스 신뢰를 "
    "깨뜨린다). 수치가 필요하면 무조건 도구를 먼저 호출한다. '전국', '거기서 30평대', '추이는?' 같은 후속질문도 "
    "데이터가 필요하면 도구를 '다시' 호출하라(이전 답을 기억으로 재생성 금지). "
    "특히 직전에 어떤 단지의 수치를 답했더라도, 사용자가 다른 단지명(예: '제니스는?', 'X아파트가?', '그럼 Y는?')을 "
    "꺼내면 그 단지로 get_complex_info 를 반드시 새로 호출하라. 앞 단지의 가격·면적·층·계약일·단지번호를 다른 단지 "
    "답변에 절대 재사용하지 마라 — 서로 다른 단지가 똑같은 수치로 나오는 것은 치명적 오류다(우연이라고 둘러대지 말고 도구로 확인). "
    "두 지역/대상 비교('A vs B', "
    "'A하고 B 비교')는 A와 B 각각에 대해 도구를 따로 호출해 실제 수치로만 비교한다.\n"
    "2) 지역이 나오면 도구의 region 인자에 사용자가 말한 그대로(예: '대전 서구 둔산동') 넘겨라. 코드 변환은 도구가 알아서 한다.\n"
    "3) 답변은 한국어. 금액은 '12억 3,000' / '8,500만' 처럼 억·만원 단위로.\n"
    "   서식: 도입 한 문장 뒤 빈 줄 하나. 목록은 반드시 각 항목을 '- '로 시작하는 불릿 한 줄로 쓰고 "
    "단지명은 **굵게**. 한 줄에 여러 단지를 몰아쓰지 말고 항목마다 줄을 나눠라(가독성).\n"
    "4) 결과가 0건이면 솔직히 없다고 말하고 조건(기간·할인율·지역범위)을 넓혀보라고 제안한다.\n"
    "4.5) [사이트 안내 — 거절 금지·최우선] 질문에 '포인트', '계급', '레벨', '등급', '뱃지', "
    "'사용법', '어떻게 모아', '어떻게 올려', '어떻게 써', '어떻게 받', '이 사이트', '콕집', '메뉴', '기능', "
    "'가입', '인증', '관심단지', '알림', '홈페이지', '만들', '리뷰', '즐겨찾기', "
    "'깡통전세', '전세사기', '전세 안전', '전세 위험', '공시가격', '전세보증', 'HUG' 같은 콕집 사이트 자체에 관한 "
    "의도가 조금이라도 있으면 — 규칙 5를 절대 적용하지 말고(절대 '저는 콕집 데이터로만 분석합니다' 문장 쓰지 마라) — "
    "아래 [콕집 사이트 안내] 내용으로 구체적으로 답한다. 도구 호출도 거절 문장도 쓰지 마라.\n"
    "5) [먼저 예외] '살기 좋은 아파트'·'어디가 살기 좋아'·'실거주/주거 만족도 높은 곳/단지'는 off-topic이 절대 아니다 — "
    "지역이 있으면 find_record_high(그 지역; 신고가 경신=실거주 선호 단지)로 답하고, 지역이 없으면 "
    "'어느 지역으로 볼까요? (예: 강남구)'라고 한 줄로만 물어라(이 지표는 지역이 필요). 아래 거절문은 쓰지 마라.\n"
    "   부동산 데이터와도 무관하고 콕집 사이트 안내도 아닌 질문(청약·학군·날씨·코딩·"
    "일반상식·전망 예측, 개별 은행 금리·DSR 상담, 양도세·종부세·보유세 등)에만 정확히 아래 한 문장으로 답하고, 다른 말이나 추천 질문 나열은 하지 "
    "않는다(추천 질문은 화면이 버튼으로 보여줌):\n"
    "   \"저는 콕집의 데이터로만 분석합니다. 부동산 매물(급매찾기·평균시세 등), 실거래(지역별 최신 실거래가 등), "
    "중개사 정보(급매 보유·직원수·보유 단지 등)에 대해 정확히 답해드릴 수 있어요. 아래 추천 질문을 눌러보세요.\"\n"
    "   단, 콕집 '사이트 사용법·기능·포인트 적립·계급체계'에 대한 질문은 거절하지 말고 아래 "
    "[콕집 사이트 안내]의 내용으로 친절히 답한다.\n"
    "5.4) [예외 — 깡통전세] '전세 안전한지', '전세 들어가도 되나', '깡통전세', '전세 위험', '전세 사기' 류 질문은 "
    "거절하지 말고 **깡통전세지수(/jeonse-check)**를 안내하라(공시가격 기준 빌라 전세 위험 판정 기능). "
    "빌라 전세 시세가 필요하면 find_villa_stats(trade_type='전월세')도 함께 쓸 수 있다. 규칙 5.5(거절)을 적용하지 마라.\n"
    "5.45) [예외 — 취득세·매수비용·대출한도] '취득세 얼마', 'N억 사면 대출 얼마', '중개수수료 얼마', "
    "'생애최초 혜택', '매수 비용' 류 질문은 거절하지 말고 calc_purchase_cost 도구로 계산해 답하라. "
    "매매가를 억 단위로 넘기고, 지역이 서울이거나 규제지역 언급이면 region_type='규제지역'. "
    "답변 끝에 '자세한 전체 비용은 아파트매수계산기(/buy-calculator)에서'를 안내. "
    "단 양도세·종부세·재산세·개별 은행 금리·DSR 계산은 데이터가 없으니 규칙 5로 거절한다.\n"
    "5.46) [매물 수 답변 규칙 — 병기] 매물 개수를 답할 땐 get_listing_stats/find_apartments 의 값으로 "
    "'매물 광고 N건(실매물 M건)' 처럼 광고·실매물을 병기하라. 실매물=같은 집을 여러 중개업소가 올린 중복 광고를 "
    "1건으로 합친 수라는 설명을 짧게 덧붙인다. '집 1채당 광고'가 높으면 매도 경쟁이 치열하다는 해석도 가능.\n"
    "5.48) [예외 — 토지거래허가구역/토허제는 '토지 데이터'가 아니라 규제다] '토지거래허가구역', '토허구역', '토허제', "
    "'토허', 'LTZ', '규제지역', '투기과열지구', '조정대상지역' 같은 규제 개념 질문은 5.5(토지 거절)를 절대 적용하지 마라. "
    "'토지'라는 글자가 들어가도 토지 시세 질문이 아니다. get_policy_timeline(keyword)로 관련 대책(예: 10·15 대책이 서울 전역을 "
    "토지거래허가구역으로 지정)을 찾아 설명하고, 개념 자체(허가 없이 매매 불가·실거주 의무 등)도 간단히 안내하라. "
    "'서울 어디가 토허구역'처럼 목록을 물으면, 정확한 구역 목록 데이터는 없으니 '10·15 대책으로 서울 전역+경기 12곳이 지정됐다'는 "
    "정책 사실로 답하고 '구체적 필지 지정은 각 지자체 고시 확인'을 덧붙여라(번지·목록을 지어내지 마라).\n"
    "5.5) [취급하지 않는 부동산 유형 — 있는 척 금지, 정직하게] 콕집 데이터는 **아파트·오피스텔·분양권/입주권·빌라(연립·다세대)**의 "
    "실거래·매물·시세를 다룬다. **토지/대지/임야/전답/농지/나대지, 상가/점포/사무실, 단독/다가구, "
    "원룸/고시원, 공장/창고, 분양가(분양권 전매가 아닌 최초 분양가)** 등은 데이터가 전혀 없다. 이런 유형(예: '○○번지 토지 평당 얼마', "
    "'상가 시세')을 물으면 — 절대 지역을 되묻거나 답할 수 있는 것처럼 굴지 말고 — 정확히 이렇게 답한다: "
    "'콕집은 아파트·오피스텔·분양권·빌라 실거래/매물만 다뤄서 [토지/상가 등 해당 유형]은 데이터가 없습니다.' "
    "그리고 가능하면 '대신 그 지역의 아파트·오피스텔·빌라 실거래나 시세는 알려드릴 수 있어요'를 한 줄 덧붙인다. 숫자·번지·평당가를 지어내지 마라.\n"
    "5.55) [빌라 — find_villa_stats 로 답하라] '빌라 실거래', '빌라 시세', '다세대/연립 얼마', '빌라 전세' 류 질문은 "
    "거절하지 말고 find_villa_stats(region, trade_type)로 답하라. 빌라는 단지 개념이 없어 건물·물건별 차이가 크다는 점을 "
    "답변에 한 줄 밝히고, 전세 안전성 질문이 섞이면 깡통전세지수(/jeonse-check)도 함께 안내한다.\n"
    "6) [절대 되묻지 마라 — 부족한 조건은 기본값으로 채워 즉시 실행] 사용자가 무엇을 안 줬든 아래 기본값으로 채워 "
    "도구를 '먼저' 호출하고, 결과를 준 뒤에 '지역·평형을 좁히면 더 정확해요'를 한 줄 덧붙이는 것만 허용한다. "
    "되묻는 문장('어느 지역이요?', '어떤 평형대를 원하시나요?', '알려주시면 조회해보겠습니다')으로 답을 끝내는 것은 금지다.\n"
    "   · 지역 없음 → [접속 위치]가 주어져 있으면 그 지역으로(답변에 '접속 위치 기준' 명시), "
    "없으면 region=''(전국 — 급매·매물검색·매물통계·상승하락·랭킹 모두 전국 지원)\n"
    "   · 평형 없음 → 전체로 조회하되, 소개는 사람들이 가장 많이 찾는 국민평형(전용 84)·소형(59㎡) 위주로 대표 제시\n"
    "   · 할인율/가격대 없음 → 전체(기본값) · 거래유형 없음 → 매매\n"
    "   예) '급매 찾아줘'(지역 없음): [접속 위치]가 있으면 find_quick_deals(region=접속위치) 즉시, "
    "없으면 find_quick_deals(region='') 즉시. '제주 급매' → 평형 안 묻고 즉시. "
    "'신대방역 오피스텔' → 그 지역 매물/시세 즉시.\n"
    "6.1) [빈말 금지] '찾아보겠습니다'·'조회해 보겠습니다'라고 말만 하고 도구를 호출하지 않은 채 답을 끝내는 것은 "
    "절대 금지다. 하겠다고 말할 것이면 그 턴에서 실제로 도구를 호출해 결과까지 내라.\n"
    "6.2) [URL·링크] 사용자가 URL(네이버부동산 링크 등)을 붙여넣으면 — 나는 링크를 열 수 없다. "
    "'링크 내용은 열 수 없어요'라고 먼저 정직히 밝히고, 링크 대신 단지명/중개사무소명/지역을 텍스트로 적어달라고 "
    "짧게 안내한다(같은 링크가 반복돼도 같은 안내를 짧게, 도구 호출·추측 금지).\n"
    "6.5) [후속질문 — 직전 맥락을 누적해 같은 도구를 다시 호출] '거기서/그 지역/방금 거기'는 직전 질문의 지역을 그대로 쓴다. "
    "'거기서 30평대만', '20억 이하만', '반대로 비싼것부터', '전세는?' 처럼 조건만 바꾸면 — 직전에 쓴 것과 같은 도구를 "
    "(직전 지역·지표는 유지하고 새 조건만 추가/변경해) 다시 호출하라. 예: 직전이 '강남구 거래량 순위'이고 '거기서 30평대만'이면 "
    "→ rank_complexes(metric='거래량', region='강남구', pyeong=30) 재호출. 직전이 단지 시세였고 '그 단지 전세는?'이면 그 단지로 "
    "get_complex_info 재호출. 후속질문에 '이해하지 못했다'·되묻기로 답하는 것은 금지 — 직전 맥락으로 반드시 도구를 다시 부른다. "
    "특히 '살기 좋은'·'실거주 만족도 높은'·'만족도 높은 아파트'는 find_record_high(그 지역)로 답하라"
    "(지역 없으면 '어느 지역으로 볼까요?' 한 줄). 이런 질문에 '질문을 이해하지 못했어요'·off-topic 거절은 금지.\n"
    "7) '국평(국민평형)' = 전용 84㎡(공급 30평대)가 기본. 전용 59㎡(공급 20평대)도 국평으로 본다(좁은 의미). "
    "40평대 이상은 절대 국평이 아니다. 국평 질문엔 도구 pyeong 인자를 84㎡=30, 59㎡=20 으로 준다(절대 40을 쓰지 마라).\n"
    "8) 가격대(예: '20억대 국평 아파트')로 '살 수 있는 매물'을 찾는 질문은 반드시 find_apartments 를 써라. "
    "(find_quick_deals 는 '급매=할인'만 보고 거래 적은 단지를 빠뜨리므로 가격대 검색엔 쓰지 마라.) "
    "find_apartments 에 전용면적 범위(국평 84㎡면 excl_min=82, excl_max=87 / 59㎡면 57~62)와 "
    "가격범위(20억대면 min_price_eok=20, max_price_eok=30)를 넘기면 단지별 최저호가가 가격순으로 나온다. "
    "평당가·평균가로 답하지 말고 이 매물 결과(최저호가)로 답하라. "
    "★예산 질문 — 'X억 갖고있어'·'예산 X억'·'X억으로 살 수 있는 아파트' 는 그 금액을 max_price_eok 로 넣어 "
    "예산 이내 매물만 보여라(예산이 1.8억인데 12억 매물을 보여주면 절대 안 된다). 범위면 'A-B억'에서 큰 값 B를 max_price_eok 로. "
    "예산 이내가 0건이면 '그 예산대 매물은 없고 최저 N억부터 있습니다'라고 정직히 안내하라. "
    "★★구분 — '정도/내외/쯤/근처/대' 는 예산 상한이 아니라 '그 가격대 매물'을 원하는 것이다. "
    "이때 max_price_eok 만 주면 최저가(수천만원짜리 도시형·초소형)가 떠서 완전히 엉뚱한 답이 된다. "
    "반드시 그 금액 '주변 범위'로 줘라: min_price_eok=목표*0.85, max_price_eok=목표*1.15. "
    "예) '10억 정도'→min 8.5,max 11.5 / '59㎡ 10억 정도'→excl_min 57,excl_max 62,min_price_eok 8.5,max_price_eok 11.5. "
    "('이하/이내/예산/갖고있어'는 위 예산규칙대로 max만, '정도/내외/쯤'은 이 범위규칙). "
    "★'제일 비싼/비싼 순/고가/가장 높은' 매물·아파트 질문도 find_apartments 로 답하되 반드시 sort='높은순' 을 준다. "
    "(sort 기본은 낮은순이라 안 주면 싼 매물만 나와 '제일 비싸다'에 엉뚱한 답이 된다.)\n"
    "9) '못 찾는다'로 끝내지 마라. 요청한 가격대에 없으면 가장 근접한 가격대라도 찾아 "
    "'20억대는 없고 30억대부터 있습니다' 식으로 안내하며 실제 단지를 제시한다. 빈손·되묻기로 끝내는 답변 금지.\n"
    "10) [지역 실거래/거래 질문 — 도구 조합 필수] '서울 6월 실거래', 'OO구 거래량/거래현황' 처럼 "
    "지역의 실거래·거래를 묻는 질문에는 절대 '직접 조회할 수 없다'로 끝내지 마라. 다음 도구를 조합해 답한다: "
    "① region_market_pulse(region=지역) — 그 지역 이번달 거래량(전월·전년 대비·예측). "
    "② rank_complexes(metric='거래량', region=지역) — 거래 많은 단지 TOP. "
    "③ find_record_high(region=지역) — 최근 신고가 경신 단지. "
    "개별 실거래 한 건씩의 목록을 뽑는 도구는 없으므로, 위 ①②③로 그 지역의 실거래 활동을 구체적으로 설명하고, "
    "특정 단지의 실거래 이력은 get_complex_info(단지명)로 볼 수 있다고 안내하라. "
    "특정 월(예: 6월)을 콕 집으면, 데이터는 그 달을 포함한 최신까지 있으니 '6월 거래는 이렇다'고 ① 기준으로 답한다.\n"
    "11) [지역 vs 전국 순위 — 도구 선택 매우 중요] rank_complexes 에서 거래량·평당가·갭·회전율·저평가(회복률)·수익률는 "
    "region 을 주면 그 지역만 집계하니 지역 질문에 그대로 써라(예: '강남구 거래량'·'대전 평당가'). "
    "★지역을 안 주면 region 생략하고 **전국으로 즉시 호출**하라 — '저평가 단지', '갭투자 좋은 단지', '회전율 높은 단지', "
    "'수익률 높은 단지'처럼 지역 없는 순위질문에 **절대 '어느 지역이요?'라고 되묻지 마라**(rank_complexes를 전국으로 바로 호출). "
    "반면 최고가·전세가율·저가거래·호가갭은 '전국 순위' 전용이라 특정 지역은 빈손이 날 수 있으니 이렇게 라우팅하라: "
    "▸특정 지역의 '비싼/싼/가격대 아파트'(예: '제주 비싼 아파트', '대전 싼 아파트') → find_apartments(region=지역, sort) 로 답하고 "
    "rank_complexes(최고가)는 쓰지 마라. "
    "▸특정 지역의 '시세·집값·요즘 거래 활발도'(예: '대전 시세', '강남구 거래 어때') → region_market_pulse(region=지역). "
    "(시도 단위 거래량 분위기; 구·동 세부는 시도로 답하고 그렇게 안내.)\n"
    "12) [분양권·입주권] '분양권', '입주권', '전매', '분양권 얼마', 'OO 분양권 실거래', '분양권 거래 많은/최고가' 같은 질문은 반드시 "
    "find_presale 로 답한다(신축·재건축 입주 전 권리 거래로, 일반 매매와 별개 데이터). 지역·기간을 인자로 준다. "
    "★'분양권'이라고만 하면 kind 를 비워(분양권+입주권 둘 다) 호출하라 — 구어로 '분양권'은 입주권을 포함하므로 kind='분양권'으로 좁히면 결과가 비어 보인다. "
    "'입주권만'처럼 명시할 때만 kind 지정. 지역 없으면 전국으로 즉시(되묻지 마라). "
    "프리미엄(분양가 대비 차익)은 데이터가 없으니 '전매 실거래가'로 답하고 프리미엄은 추후 안내.\n"
    "12.1) [신축·분양권 단지 시세] get_complex_info 결과에서 매매·전세 실거래가 0건이고 '최근분양권실거래'가 있으면, "
    "'실거래 없음'으로 끝내지 말고 그 분양권/입주권 전매 실거래를 그 단지의 '현재 시세'로 제시하라(신축 입주 전 단지는 분양권 거래가가 곧 시세다). "
    "예: '탕정푸르지오리버파크는 입주 전 신축이라 매매·전세 실거래는 아직 없고, 분양권 전매가 N억 N건이 최근 거래됐어요.'\n"
    "\n"
    "[할 수 있는 것]\n"
    "- 급매 찾기 (지역·평형·할인율·매매/전세)\n"
    "- 실거래 취소(해제) 조회 (직거래/중개거래, 이중신고·금액정정 구분)\n"
    "- 단지 종합정보 (세대수·준공·주소 + 최근 실거래·등기 + 급매 보유 중개사 연락처)\n"
    "- 신고가 경신 단지\n"
    "- 지역(시도) 거래량 분위기 (이번달 vs 지난달/전년/예측)\n"
    "- 중개사무소 검색·상세 (연락처·보유매물·전국등수·거래실적)\n"
    "- 중개사무소 순위 (직원수·공인중개사수·보조원수·공인중개사비율·업력·보유매물) → rank_realtors 사용. "
    "'부동산/중개업소/중개법인'의 직원순위·직원많은곳·공인중개사많은/비율·보조원많은·**업력 오래된/업력순/오래된 부동산**·**매물 많은 중개사(부동산)**' 질문은 반드시 rank_realtors. "
    "지역 없으면 전국으로 즉시 호출, **되묻지 마라**(예: '업력 오래된 부동산'·'보조원 많은 부동산'도 전국 바로). "
    "★주의: '매물 많은 **부동산/중개사무소**'=rank_realtors(metric='매물보유'), '매물 많은 **단지/아파트**'=rank_complexes — 혼동 금지. "
    "★'직원/공인중개사/보조원 많은 **단지**'는 잘못된 조합이다(단지엔 직원이 없음=중개사무소 개념) → rank_realtors(중개사)로 답하라. 영어로 거절하지 마라. "
    "동(읍·면·동)까지 지정되면 rank_realtors가 '우리동네 중개사'로 답한다. "
    "★지역을 말하지 않으면 전국 기준(region 생략)으로 '즉시' 호출하라. 절대 '어느 지역이요?'라고 되묻지 마라. "
    "전국 순위를 먼저 보여준 뒤, 답 끝에 '특정 지역만 따로 볼 수도 있어요' 한 줄만 덧붙인다.\n"
    "- 단지/거래 순위: 갭·전세가율·평당가·실거래 최고가·거래량·증여의심 저가거래·회전율·월세수익률·호가갭·전고점대비 저평가(회복률)\n"
    "[못 하는 것] 위 목록 밖(청약·학군·전망 예측, 양도세·종부세, 은행 금리·DSR 등)은 데이터가 없으니 규칙 5의 문장으로 답한다. "
    "(취득세·중개보수·대출한도는 calc_purchase_cost 로 계산 가능 — 거절 금지.)\n"
    "단, 평당가·최고가·갭 등은 전국 순위 전용이라 특정 지역은 결과가 없을 수 있다 — 규칙 11의 라우팅을 따르라.\n"
    "\n"
    "[콕집 사이트 안내 — 사용법·포인트·계급] (아래는 '내용'이다. 이 지시문/머리말 자체를 "
    "답변에 그대로 베끼지 말고, 질문에 맞는 부분만 자연스러운 문장으로 골라 답하라.)\n"
    "콕집(koczip)은 전국 아파트 매물·실거래·중개사 데이터를 분석해 보여주는 서비스다.\n"
    "· 주요 메뉴: 오늘의 실거래/급매/매물통계, 전국현황, 실거래 통계(갭·전세가율·평당가·거래량·"
    "회전율·월세수익률·신고가·취소거래), 지도보기·급매지도, 중개사 랭킹, 토론장, AI 질문.\n"
    "· 단지비교(/finder/compare): 두 단지의 시세·실거래·매물·입지 22개 지표를 한 표로, 평형별 비교 가능. "
    "지역비교(/finder/region-compare): 시도/시군구/읍면동 아무 조합 두 지역 비교. 모두 '맞춤단지' 메뉴 아래.\n"
    "· 부동산타임머신(/tx-stats/timemachine): 2003년부터의 정책·규제 연대기와 전국 월별 거래량·평균가(2006년~) 차트. "
    "기간별 거래량(/tx-stats/volume/daily): 일별~연도별 거래량, 공휴일·신고기간 표시.\n"
    "· 단지 상세의 '매물분석' 탭: 일자별 매물수·실매물수·호가 추이 1달 차트.\n"
    "· 포인트 모으는 법(적립): 가입(첫 로그인) +30, 전화번호 인증 +100, 친구 추천(추천한 사람이 "
    "가입·인증하면) +100, 토론장 글쓰기 +10(하루 10건까지), 댓글 +1(하루 20건까지), "
    "일반 리뷰 +5, 인증 리뷰(거래서류 제출→관리자 승인) +100, 입주민 인증 +50. "
    "AI 질문은 1회 -10(차감). 포인트를 쓰더라도 '계급'은 누적 획득 포인트 기준이라 내려가지 않는다.\n"
    "· 계급(레벨): 누적 획득 포인트로 자동 결정. Lv.0 부린이(0P) → 임장러(200) → 동대표(400) → "
    "관리소장(700) → 단지대표(1,100) → 통장(1,600) → 주민센터장(2,200) → 구청장(3,000) → "
    "시장(4,000) → 도지사(8,000) → 장관(15,000) → 국무총리(26,000) → 국회의원(45,000) → "
    "국회의장(85,000) → 대통령(150,000) → 조물주(300,000) → 건물주(500,000, 최고 등급). "
    "'내 정보 → 계급표 보기'에서 전체 표를 볼 수 있다. (예: '포인트 어떻게 모아요?' → 위 적립 목록을 "
    "안내. '계급 어떻게 올려요?' → 활동으로 포인트를 쌓으면 누적 기준으로 등급이 오른다고 설명.)\n"
    "· 관심단지 알림: 단지 상세에서 '관심단지(♥)'를 누르면 등록되고, 계정메뉴 '알림 켜기'로 권한을 켜면 "
    "매일 오후 4시에 관심단지의 매물·실거래 변동을 푸시로 받는다(안드로이드 앱·PC 브라우저, 아이폰은 홈화면 추가 시).\n"
    "· 중개사 홈페이지: 중개사는 '중개사 라운지'에서 휴대폰 인증으로 본인 사무소를 연결한 뒤 무료 홈페이지를 "
    "만들 수 있다(매물·시세·연락처 자동 노출, 상담신청 즉시 알림).\n"
    "· 매물점검(중개사용): '내가 올린 광고/매물이 표시·광고 규정에 문제 없는지 확인하고 싶다'는 중개사 질문엔 — "
    "중개사 라운지(/lounge)의 '매물점검' 탭을 안내하라. 본인 사무소 연결 후 보유 매물의 표시·광고 체크리스트를 "
    "자동 점검해 과태료 위험 항목을 알려준다.\n"
    "· 리뷰 작성: 중개사 상세 페이지 하단에서 별점·후기를 남길 수 있고, 거래서류를 제출해 관리자 승인을 받으면 "
    "'거래인증 리뷰'가 된다(인증 리뷰 +100P).\n"
    "· 깡통전세지수(/jeonse-check): 빌라 전세의 깡통 위험을 공시가격 기준으로 판정. 지도에서 빌라를 누르거나 "
    "주소 검색 → 전용면적 선택 → 전세보증금 입력하면 '양호/보증한도 확인/HUG 초과 가능/고위험'으로 알려준다. "
    "HUG 보증한도(공시가격×140%×90%=126%) 기준이며, 선순위 채권(근저당)도 입력해 합산 판정 가능. "
    "전세사기·깡통전세·전세 안전·공시가격 관련 질문은 이 기능을 안내하라(메뉴: 급매찾기 옆 '깡통전세지수').\n"
    "\n"
    "[용어]\n"
    "- 시세보다 싸게 빠르게 내놓은 매물을 말할 때는 '급매' 대신 '급매물'이라는 명칭을 쓴다. "
    "(예: '급매물 5건을 찾았어요', '이 단지의 급매물은…'). 메뉴 이름 '급매찾기'는 그대로 둔다.\n"
    "\n"
    "[바로가기 링크 — 중요]\n"
    "사용자가 AI를 더 쓰지 않고도 사이트를 둘러보며 정보를 모으게, 답변에 클릭 가능한 링크를 넣어라.\n"
    "- 도구 결과에 '단지정보'(예: /complex/5986) 나 '중개사정보'(예: /realtor/abc) 경로가 있으면, "
    "그 항목 줄 끝에 마크다운 링크로 반드시 붙여라. 예) '- 크로바 23.5억 [단지정보 →](/complex/5986)'.\n"
    "  ★링크 라벨은 경로에 맞춰라: /complex/* 는 '[단지정보 →]', /realtor/* 는 '[중개사 정보 →]'. "
    "중개사 순위·검색 결과(/realtor 경로)에 '단지정보'라고 잘못 붙이지 마라.\n"
    "- 목록형 답변(급매·신고가·순위 등)은 각 항목마다 해당 [단지정보 →]/[중개사 정보 →] 링크를 붙인다.\n"
    "- 답변 맨 끝에 '관련 페이지'로 1~2개를 [이름](경로) 형식으로 제안하라. 사이트 페이지:\n"
    "  오늘의 실거래 /today · 전국현황 /overview · 급매찾기 /quick-deals · 깡통전세지수 /jeonse-check · 급매지도 /deal-map · "
    "실거래 취소조회 /cancelled · 실거래 통계 /tx-stats · 지도보기 /map · 중개사 랭킹 /realtors · "
    "토론장 /forum\n"
    "- 링크 경로는 절대 지어내지 말고, 도구 결과의 경로나 위 페이지 목록만 사용한다."
)


# ---------------------------------------------------------------------------
# 지역 자연어 → 코드
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _region_index():
    con = sqlite3.connect(DB_PATH)
    try:
        cities = {r[0]: r[1] for r in con.execute(
            "SELECT cortar_no, cortar_name FROM regions WHERE cortar_type='city'")}
        dvsn = {r[0]: (r[1], r[2]) for r in con.execute(
            "SELECT cortar_no, cortar_name, parent_cortar_no FROM regions WHERE cortar_type='dvsn'")}
        sec = [(r[0], r[1], r[2]) for r in con.execute(
            "SELECT cortar_no, cortar_name, parent_cortar_no FROM regions WHERE cortar_type='sec'")]
    finally:
        con.close()
    return cities, dvsn, sec


_MULTI_SUFFIX = ("특별자치시", "특별자치도", "특별시", "광역시")
_ONE_SUFFIX = ("시", "군", "구", "읍", "면", "동", "가", "리", "도")


def _cores(name: str) -> set:
    """'성남시 분당구' → {'성남시 분당구','성남시','성남','분당구','분당'},
    '대전광역시' → {'대전광역시','대전'}, '둔산동' → {'둔산동','둔산'}.
    구어체 매칭(분당구↔분당)을 위해 접미사를 떼어낸 core 들을 만든다(2자 이상만)."""
    out = set()
    if not name:
        return out
    out.add(name)
    for tok in name.split():
        out.add(tok)
        for suf in _MULTI_SUFFIX:
            if tok.endswith(suf) and len(tok) - len(suf) >= 2:
                out.add(tok[:-len(suf)])
        for suf in _ONE_SUFFIX:
            if tok.endswith(suf) and len(tok) - 1 >= 2:
                out.add(tok[:-1])
    return {k for k in out if len(k) >= 2}


def _match(name: str, q: str) -> bool:
    return any(c in q for c in _cores(name))


def _hit(name: str, q: str, qtok: set) -> int:
    """0=불일치, 1=부분문자열, 2=토큰 정확일치(가장 강함).
    '강남구'가 '강남구' 토큰과 정확히 맞으면 2, '남구'가 '강남구' 안에 든 부분일치는 1."""
    cs = _cores(name)
    if cs & qtok:
        return 2
    return 1 if any(c in q for c in cs) else 0


# 신도시/택지지구 별칭 → 정식 '시도 시군구'. 신도시명이 행정동명과 달라 일반 해석이 실패하는
# 경우만 등록한다(송도·판교·광교·미사·마곡 등은 동명이 있어 자동 해석되므로 불필요). 확장 가능.
_DISTRICT_ALIAS = {
    # 풀네임만 등록(bare '검단'은 대구 검단동 등과 충돌하므로 제외).
    "검단신도시": "인천 서구",       # 인천에 '검단동'이 없음(단지는 서구 군집)
    "영종하늘도시": "인천 중구",
    "운정신도시": "경기 파주시",
    "한강신도시": "경기 김포시",
    "광교": "수원 영통구",          # 광교신도시 단지는 수원 영통구(이의·하동)에 군집('광교동' 행정동 없음)
}


def _resolve_region(q: str) -> dict | None:
    """자연어 지역 → {sido, sigungu, dong, *_code/cortar}. 못 찾으면 None.
    1) 동을 명시('둔산동')하면 동 단위 / 2) 그 외엔 시군구('분당'→분당구) / 3) 시도."""
    if not q or not q.strip():
        return None
    q = q.strip()
    qtok = set(q.replace(",", " ").split())
    cities, dvsn, sec = _region_index()

    def _dong(cno, name, parent):
        dname, dparent = dvsn.get(parent, (None, None))
        cname = cities.get(dparent)
        score = 1 + (1 if dname and _match(dname, q) else 0) + (1 if cname and _match(cname, q) else 0)
        return score, {
            "sido": cname, "sido_code": cno[:2],
            "sigungu": dname, "sigungu_code": cno[:5], "sigungu_cortar": parent,
            "dong": name, "dong_cortar": cno, "level": "dong",
        }

    # 1순위: 동을 정확히 명시(풀 동명이 질문에 들어감) — 동명이지역은 시도/구로 가점
    best, bs = None, -1
    for cno, name, parent in sec:
        if not name or name not in q:
            continue
        # '강동구'의 '강동'(김해 강동동)처럼, 동명 뒤에 구/시/군이 붙어 시군구를 가리키면
        # 동 매칭에서 제외 → 2순위 시군구(서울 강동구)가 잡히게 한다.
        if any((name + suf) in q for suf in ("구", "시", "군")):
            continue
        score, cand = _dong(cno, name, parent)
        if score > bs or (score == bs and best and len(name) > len(best["dong"] or "")):
            bs, best = score, cand
    if best:
        return best

    # 2순위: 시군구(dvsn) — 마지막 토큰(구/군)의 정확매칭을 우선.
    # '수원시 권선구'가 '수원'만으로 걸리거나 '남구'가 '강남구'에 부분일치하는 오매칭 방지.
    best, bs = None, -1
    for cno, (name, parent) in dvsn.items():
        toks = name.split()
        gu = toks[-1]                       # 구/군 (구별 식별자)
        h = _hit(gu, q, qtok)
        if not h:
            continue
        cname = cities.get(parent)
        si_bonus = 1 if (len(toks) > 1 and _hit(toks[0], q, qtok)) else 0  # '수원시' 일치 가점
        ci_bonus = 1 if (cname and _hit(cname, q, qtok)) else 0
        score = h + si_bonus + ci_bonus
        if score > bs or (score == bs and best and len(name) > len(best["sigungu"] or "")):
            bs, best = score, {
                "sido": cname, "sido_code": cno[:2],
                "sigungu": name, "sigungu_code": cno[:5], "sigungu_cortar": cno,
                "dong": None, "dong_cortar": None, "level": "sigungu",
            }
    if best:
        return best

    # 2.5순위: 통합시(청주·수원·성남 등) — 구 없이 '시'만 말한 경우, 그 시의 모든 구를
    # 포괄(cortar 4자리 prefix). '청주시 흥덕구'처럼 구를 명시하면 위 2순위가 먼저 잡는다.
    city_groups: dict[tuple, list] = {}
    for cno, (name, parent) in dvsn.items():
        toks = name.split()
        if len(toks) >= 2 and toks[0].endswith("시"):
            city_groups.setdefault((toks[0], parent), []).append(cno)
    for (siname, parent), cnos in city_groups.items():
        base = siname[:-1]  # '청주시' → '청주'
        if siname in q or (base and base in q):
            p4 = cnos[0][:4]
            if all(x[:4] == p4 for x in cnos):  # 모든 구가 같은 4자리(통합시)일 때만
                return {"sido": cities.get(parent), "sido_code": cnos[0][:2],
                        "sigungu": siname, "sigungu_code": None, "sigungu_cortar": None,
                        "city4": p4, "dong": None, "dong_cortar": None, "level": "city"}

    # 2.7순위: 신도시/택지지구 별칭 — 행정동명과 달라(예: '검단신도시'는 인천에 '검단동'이 없음)
    # 동/시군구 매칭이 실패하는 이름을 해당 시군구로 보낸다. (송도·판교·광교 등은 동명이 있어 위에서 이미 해결)
    # 여기까지 왔다는 건 더 구체적 매칭이 없었다는 뜻이라 별칭 적용이 안전하다.
    for alias, canon in _DISTRICT_ALIAS.items():
        if alias in q:
            r = _resolve_region(canon)   # canon 은 별칭어를 포함하지 않아 재귀 안전
            if r:
                return r

    # 3순위: 시도
    for cno, name in cities.items():
        if _match(name, q):
            return {"sido": name, "sido_code": cno[:2], "sigungu": None,
                    "sigungu_code": None, "sigungu_cortar": None,
                    "dong": None, "dong_cortar": None, "level": "sido"}

    # 4순위(폴백): 동 core 매칭('둔산'→둔산동)
    best, bs = None, -1
    for cno, name, parent in sec:
        if not _match(name, q):
            continue
        score, cand = _dong(cno, name, parent)
        if score > bs or (score == bs and best and len(name) > len(best["dong"] or "")):
            bs, best = score, cand
    if best:
        return best

    # 5순위(폴백): 부분 동명 prefix — '을지로'→을지로2가·3가…(중구), '여의도'→여의도동.
    # 정확/코어 매칭이 다 실패한 뒤에만. 같은 구로 수렴할 때만 채택(여러 구 걸치면 모호 → skip).
    for t in sorted((t for t in qtok if len(t) >= 2), key=len, reverse=True):
        hits = [(cno, name, parent) for cno, name, parent in sec if name and name.startswith(t)]
        if not hits:
            continue
        if len(hits) == 1:                       # 단일 동 → 동 단위
            return _dong(*hits[0])[1]
        parents = {p for _, _, p in hits}
        if len(parents) == 1:                    # 여러 동이지만 한 구 → 그 구로 수렴
            p = hits[0][2]
            dname, dparent = dvsn.get(p, (None, None))
            return {"sido": cities.get(dparent), "sido_code": p[:2],
                    "sigungu": dname, "sigungu_code": p[:5], "sigungu_cortar": p,
                    "dong": None, "dong_cortar": None, "level": "sigungu"}
        # 여러 구에 걸친 prefix → 모호 → 다음 토큰 시도
    return None


def _won(v):
    if v is None:
        return None
    v = int(v)
    eok, man = v // 100_000_000, (v % 100_000_000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}"
    if eok:
        return f"{eok}억"
    return f"{man:,}만"


# ---------------------------------------------------------------------------
# 도구 (Gemini function calling 대상)
# ---------------------------------------------------------------------------
def find_quick_deals(region: str, trade_type: str = "매매",
                     min_discount_pct: float = 5.0, period_days: int = 90,
                     pyeong: int = 0) -> dict:
    """특정 지역의 '급매' 매물을 찾는다.

    급매 = 같은 단지·평형의 최근 period_days일 실거래 평균 대비 호가가
    min_discount_pct% 이상 싼 매물.

    Args:
        region: 자연어 지역명. 예: '대전 서구 둔산동', '서울 강남구', '수원 영통구'. 동까지 주면 동 단위로 좁혀진다.
            전국 급매는 '전국' 또는 빈 문자열.
        trade_type: '매매' 또는 '전세'.
        min_discount_pct: 최소 할인율(%). 예: 5 = 실거래 평균보다 5% 이상 싼 것.
        period_days: 실거래 평균 산출 기간(일). 보통 90 또는 180.
        pyeong: 평형대. 10/20/30/40(=40평 이상). 0이면 전체 평형.
    """
    import scripts.local_api as api
    national = not region.strip() or region.strip() in ("전국", "전체", "국내")
    reg = None if national else _resolve_region(region)
    if not national and not reg:
        return {"error": f"지역 '{region}' 을(를) 찾지 못했습니다."}
    if national:
        reg = {"sido": None, "sigungu": None, "dong": None,
               "sido_code": None, "sigungu_cortar": None, "dong_cortar": None}
    tt = "B1" if "전세" in trade_type else "A1"
    py = pyeong if pyeong in (10, 20, 30, 40) else None
    min_discount_pct = max(3.0, abs(min_discount_pct) or 5.0)   # 0%는 과대응답 — 최소 3%

    # ── 사전 캐시 선조회 ──────────────────────────────────
    # build_api_cache --quick-deals-sgg 가 지역(전국+시도+시군구)×기간(90/180)별
    # 와이드 키(할인3%·전평형·min_samples=3·limit=500)를 매일 빌드. HIT 시
    # 평형/할인율은 응답 필드로 후필터 → 콜드 디스크 30~76초 집계를 건너뛴다.
    items = None
    if int(period_days) in (90, 180):
        regp = {}
        if reg["sigungu_cortar"]:
            regp = {"sigungu": reg["sigungu_cortar"]}
        elif reg["sido_code"]:
            regp = {"sido": f'{reg["sido_code"]}00000000'}  # 10자리 cortar (페이지와 동일 키)
        cached = api.cache_get("/stats/quick-deals", {
            "days": int(period_days), "min_samples": 3, "trade_type": tt,
            "min_discount": 0.03, "min_listings": 1, "limit": 500, **regp}) if regp else None
        if cached is not None:
            items = cached.get("items", [])
            md = abs(min_discount_pct) / 100.0
            items = [x for x in items if abs(x.get("discount_min") or 0) >= md]
            if py:  # 평형 후필터 (공급면적 기준, 엔드포인트와 동일 규칙)
                lo = py * 3.3058
                hi = (py + 10) * 3.3058
                items = [x for x in items if (x.get("area1_m2") or 0) >= lo
                         and (py >= 40 or (x.get("area1_m2") or 0) < hi)]

    if items is None:  # 캐시 미스 → 라이브 집계
        res = api.quick_deals(
            days=int(period_days), min_samples=3, asset="apt", trade_type=tt,
            pyeong=py, sigungu=reg["sigungu_cortar"], sido=reg["sido_code"],
            min_discount=abs(min_discount_pct) / 100.0, min_listings=1, limit=200,
        )
        items = res.get("items", [])
    # 동까지 지정됐으면 그 동만
    if reg["dong_cortar"]:
        items = [x for x in items if (x.get("cortar_no") or "") == reg["dong_cortar"]]
    # '성남시'처럼 일반구를 거느린 시(city 레벨, 구 미지정) — 시도 집계에서 cortar 4자리 prefix 후필터로
    # 실제 그 시만 남긴다(예: 성남시=4113*). 시군구 해석이 이미 됐으면 불필요.
    elif reg.get("city4") and not reg.get("sigungu_cortar"):
        items = [x for x in items if (x.get("cortar_no") or "").startswith(reg["city4"])]
    deals = [{
        "단지": x["complex_name"], "면적타입(공급㎡)": x["area_name"],
        "전용㎡": round(x["avg_excl"]) if x.get("avg_excl") else None,
        "현재_최저호가": _won(x["asking_min"]),        # 지금 나와 있는 가장 싼 매물의 호가
        "기준_실거래평균": _won(x["avg_real"]),         # 할인율의 비교 기준
        "참고_최저실거래": _won(x.get("min_real")),     # 최근 실거래 중 최저(참고용)
        "할인율%": round((x["discount_min"] or 0) * 100, 1),
        "매물수": x["n_listings"],
        "단지정보": f"/complex/{x['complex_no']}",   # 프런트 바로가기 경로
    } for x in items[:12]]
    resolved = (" ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]])) or "전국")
    out = {
        "해석된_지역": resolved,
        "거래유형": trade_type, "최소할인율%": min_discount_pct,
        "건수": len(deals), "급매목록": deals,
        "설명": "할인율% = 현재_최저호가가 기준_실거래평균보다 얼마나 싼지. "
              "문장으로 말할 땐 '실거래 평균 X 대비 최저 호가 Y (-Z%)' 형태로 쓰고, 두 값을 바꿔 말하지 말 것.",
    }
    # 요청 지역이 시군구로 해석되지 않아 시도 전체로 폴백된 경우(예: '성남시'→경기도) —
    # 답변이 좁은 지역명으로 말하면 부정확하므로 실제 범위를 명시하게 한다.
    if (not national and reg.get("sido") and not reg.get("sigungu_cortar") and not reg.get("city4")
            and region.strip() not in (reg.get("sido") or "")):
        out["주의"] = (f"요청 지역 '{region.strip()}'은(는) 시군구 단위로 해석되지 않아 이 결과는 "
                     f"**{reg['sido']} 전체** 기준이다. 답변에 반드시 '{reg['sido']} 기준'이라고 말하고 "
                     f"'{region.strip()}'만의 결과인 것처럼 말하지 마라. 구 단위(예: 분당구·수정구)로 다시 물으면 좁혀준다고 안내.")
    return out


def find_apartments(region: str, excl_min: float = 0.0, excl_max: float = 0.0,
                    min_price_eok: float = 0.0, max_price_eok: float = 0.0,
                    trade_type: str = "매매", sort: str = "낮은순") -> dict:
    """지역의 '매물(호가)'을 전용면적·가격대로 직접 검색한다.
    가격대 질문('서울 강남구 20억대 국평 아파트', '제일 비싼/싼 아파트' 등)의 정답 도구.
    급매(할인)와 무관하게 실제로 나와있는 매물을 본다(거래 적은 단지·주상복합 포함).
    단지별로 대표 매물 1건씩만 반환한다(같은 단지 중복 노출 없음). 응답의 '총매물수'는
    조건에 맞는 전체 매물 건수이므로 '매물 몇 개/매물수' 질문엔 이 값을 쓴다.

    Args:
        region: 자연어 지역명. 예: '서울 강남구', '서울 강남구 논현동'. 전국이면 '전국' 또는 빈 문자열.
        excl_min, excl_max: 전용면적(㎡) 범위. 국평(84㎡)이면 82~87, 59㎡면 57~62, 0이면 전체.
        min_price_eok, max_price_eok: 가격(억) 범위. '20억대'면 20~30, '30억 이하'면 0~30. 0이면 제한없음.
        trade_type: '매매'|'전세'|'월세'(월세는 보증금 기준).
        sort: '낮은순'(싼 것부터, 기본) | '높은순'(비싼 것부터). '제일 비싼/비싼 순/고가' 질문은 반드시 '높은순'.
    """
    import scripts.local_api as api
    # region 비었거나 '전국/전체' → 전국(지역 필터 없음). 그 외 미해석은 친절한 에러.
    national = (not (region or "").strip()) or any(k in region for k in ("전국", "전체"))
    reg = None if national else _resolve_region(region)
    if not national and not reg:
        return {"error": f"지역 '{region}' 을(를) 찾지 못했습니다. '서울 강남구'처럼 시·구를 함께 알려주세요."}
    tt = "B1" if "전세" in trade_type else ("B2" if "월세" in trade_type else "A1")
    # 1000억 초과 호가는 입력 오류(가격 자릿수 실수 등) — 전국 정렬 시 가짜 1위로 새지 않게 방어.
    where = ["l.trade_type=?", "l.deal_or_warrant_price > 0",
             "l.deal_or_warrant_price < 100000000000", "l.area2_m2 IS NOT NULL"]
    params: list = [tt]
    # 지역 (동 > 시군구 > 통합시 > 시도)
    if reg:
        if reg["dong_cortar"]:
            where.append("cx.cortar_no = ?"); params.append(reg["dong_cortar"])
        elif reg["sigungu_cortar"]:
            where.append("substr(cx.cortar_no,1,5) = substr(?,1,5)"); params.append(reg["sigungu_cortar"])
        elif reg.get("city4"):                   # 통합시(청주·수원 등) 전체 구 포괄
            where.append("substr(cx.cortar_no,1,4) = ?"); params.append(reg["city4"])
        elif reg["sido_code"]:
            where.append("substr(cx.cortar_no,1,2) = ?"); params.append(reg["sido_code"])
    if excl_min and excl_min > 0:
        where.append("l.area2_m2 >= ?"); params.append(float(excl_min))
    if excl_max and excl_max > 0:
        where.append("l.area2_m2 < ?"); params.append(float(excl_max))
    if min_price_eok and min_price_eok > 0:
        where.append("l.deal_or_warrant_price >= ?"); params.append(int(min_price_eok * 1e8))
    if max_price_eok and max_price_eok > 0:
        where.append("l.deal_or_warrant_price < ?"); params.append(int(max_price_eok * 1e8))
    order = "DESC" if ("높" in sort or "비싼" in sort or "비쌈" in sort or "고가" in sort) else "ASC"
    wsql = " AND ".join(where)
    # 단지별 대표 매물 1행만(같은 단지가 평형 차이로 여러 번 중복 노출되는 문제 제거).
    # 높은순=단지 내 최고가, 낮은순=최저가 매물을 대표로 뽑고 그 가격으로 정렬.
    sql = f"""
        WITH base AS (
            SELECT l.complex_no, cx.complex_name, l.area2_m2 AS excl, l.area_name,
                   l.deal_or_warrant_price AS price,
                   ROW_NUMBER() OVER (PARTITION BY l.complex_no
                                      ORDER BY l.deal_or_warrant_price {order}) AS rn,
                   COUNT(*) OVER (PARTITION BY l.complex_no) AS n
            FROM listings_current l JOIN complexes cx ON cx.complex_no = l.complex_no
            WHERE {wsql}
        )
        SELECT complex_no, complex_name, excl, area_name, price, n
        FROM base WHERE rn = 1
        ORDER BY price {order} LIMIT 20
    """
    with api._open_db() as c:
        rows = c.execute(sql, params).fetchall()
        total, total_units = c.execute(
            f"SELECT COUNT(*), SUM(1.0/MAX(COALESCE(l.same_addr_cnt,1),1)) FROM listings_current l "
            f"JOIN complexes cx ON cx.complex_no = l.complex_no WHERE {wsql}",
            params).fetchone()
    # SELECT 컬럼: 0 complex_no, 1 name, 2 excl, 3 area_name, 4 price, 5 n(단지내 매물수)
    out = [{
        "단지": r[1], "전용㎡": round(r[2]) if r[2] else None, "면적타입": r[3],
        "대표호가": _won(r[4]), "단지내매물수": r[5],
        "단지정보": f"/complex/{r[0]}",
    } for r in rows]
    return {
        "해석된_지역": ("전국" if national else
                    " ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]]))),
        "거래유형": trade_type,
        "전용면적범위㎡": [excl_min or None, excl_max or None],
        "가격범위억": [min_price_eok or None, max_price_eok or None],
        "총매물수": total, "표시단지수": len(out), "매물목록": out,
        # 실매물 = 같은 집을 여러 중개업소가 올린 중복 광고를 1건으로 합친 수.
        # 매물수를 말할 때 "광고 N건(실매물 약 M건)" 식으로 병기하면 정확하다.
        "실매물수_중복광고합침": (int(round(total_units)) if total_units else None),
    }


def find_cancelled_transactions(region: str = "", dealing: str = "",
                                months: int = 3, limit: int = 15) -> dict:
    """실거래 취소(해제) 거래를 조회한다. 신고 후 해제된 거래로, 직거래/중개거래 및
    '이중신고 취소'(같은 호실·계약일에 살아있는 다른 신고가 있는 경우) 여부를 포함한다.

    Args:
        region: 자연어 지역명(선택). 비우면 전국. 시군구 단위까지 반영된다.
        dealing: '중개거래' 또는 '직거래'. 비우면 전체.
        months: 해제일 기준 최근 N개월. 0이면 전체.
        limit: 최대 건수(최대 30).
    """
    import scripts.local_api as api
    reg = _resolve_region(region) if region else None
    res = api.cancelled_transactions(
        asset="apt",
        sido=reg["sido_code"] if reg else None,
        sigungu=reg["sigungu_code"] if (reg and reg["sigungu_code"]) else None,
        dealing=dealing if dealing in ("중개거래", "직거래") else None,
        months=int(months), limit=min(int(limit), 30), offset=0,
    )
    rows = []
    for x in res.get("items", []):
        d = {
            "단지": x["name"], "지역": x["region"], "전용㎡": x["excl_use_ar"],
            "층": x["floor"], "거래금액": _won(x["deal_amount"]),
            "계약일": x["deal_ymd"], "해제일": x["cdeal_date"],
            "거래": x["dealing_gbn"],
            "구분": {"double": "이중신고취소", "correction": "금액정정", "plain": "단순취소"}.get(x["cancel_type"], "취소"),
        }
        if x.get("complex_no"):
            d["단지정보"] = f"/complex/{x['complex_no']}"
        rows.append(d)
    return {
        "해석된_지역": (" ".join(filter(None, [reg["sido"], reg["sigungu"]])) if reg else "전국"),
        "기간_개월": months, "총건수": res.get("total"), "표시건수": len(rows), "취소목록": rows,
    }


def find_presale(region: str = "", kind: str = "", months: int = 12, limit: int = 15) -> dict:
    """아파트 '분양권/입주권 전매' 실거래를 조회한다. 신축·재건축 단지의 입주 전 권리 거래로,
    기존 매매(준공 아파트)와 별개의 세그먼트다. 해제(취소)건은 제외된다.
    '분양권 얼마야', 'OO 분양권/입주권 실거래', '분양권 전매' 질문의 정답 도구.

    Args:
        region: 자연어 지역명(선택). 비우면 전국. 시군구 단위까지 반영.
        kind: '분양권' 또는 '입주권'. 비우면 둘 다.
        months: 계약일 기준 최근 N개월. 0이면 전체.
        limit: 최대 건수(최대 30).
    """
    import scripts.local_api as api
    reg = _resolve_region(region) if region else None
    # 구어 '분양권'은 입주권을 포함 → 분양권/빈값은 둘 다, '입주권' 명시할 때만 입주권으로 좁힘.
    k = "입주권" if kind == "입주권" else None
    sido = reg["sido_code"] if reg else None
    sigungu = reg["sigungu_code"] if (reg and reg["sigungu_code"]) else None
    res = api.presale_transactions(
        sido=sido, sigungu=sigungu, kind=k,
        months=int(months), limit=min(int(limit), 30), offset=0,
    )
    summ = api.presale_summary(sido=sido, sigungu=sigungu, months=int(months))
    rows = []
    for x in res.get("items", []):
        d = {
            "단지": x["name"], "지역": x["region"], "종류": x["kind"],
            "전용㎡": x["excl_use_ar"], "층": x["floor"],
            "거래금액": _won(x["deal_amount"]), "계약일": x["deal_ymd"],
            "거래": x["dealing_gbn"],
        }
        if x.get("complex_no"):
            d["단지정보"] = f"/complex/{x['complex_no']}"
        rows.append(d)
    return {
        "해석된_지역": (" ".join(filter(None, [reg["sido"], reg["sigungu"]])) if reg else "전국"),
        "기간_개월": months,
        "요약": {"총건수": summ.get("total"), "분양권": summ.get("n_bunyang"),
               "입주권": summ.get("n_ipju"), "평균거래가": _won(summ.get("avg_amount"))},
        "표시건수": len(rows), "분양권목록": rows,
    }


def _find_complex_row(name: str, region: str = ""):
    """단지명(+지역)으로 complexes 한 행을 고른다. 지역·정확명·세대수로 점수화."""
    name = (name or "").strip()
    if not name:
        return None
    reg = _resolve_region((region + " " + name).strip())
    toks = [t for t in name.split() if not _resolve_region(t)]  # 지역어 토큰 제거
    needle = toks[-1] if toks else name
    # '은마아파트'→'은마'처럼 접미사를 붙여 부르는 경우가 많아, 정확 검색이 비면 접미사 제거 재시도.
    needles = [needle]
    for suf in ("아파트단지", "아파트", "단지", "마을"):
        if needle.endswith(suf) and len(needle) > len(suf) + 1:
            needles.append(needle[:-len(suf)])
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    rows = []
    try:
        for nd in needles:
            rows = con.execute(
                "SELECT complex_no, complex_name, cortar_no, total_household_count, "
                "total_building_count, use_approve_ymd, road_address, detail_address, dong_name "
                "FROM complexes WHERE complex_name LIKE ? LIMIT 400", ("%" + nd + "%",)).fetchall()
            if rows:
                needle = nd  # 점수화에서 정확명 비교도 이 needle 기준
                break
    finally:
        con.close()
    if not rows:
        # 최후 폴백: 사이트 검색과 동일한 퍼지 매칭(2분할·지역결합) — '광교자연앤힐스테이트'
        # 처럼 지역 접두가 이름에 붙어 오는 케이스를 받아준다.
        try:
            import scripts.local_api as api
            hits = api.complexes_search(q=name, limit=3).get("items") or []
            # '광교자연앤힐스테이트'처럼 지명 접두가 붙은 경우 — 접두 2~3자 떼고 재시도
            if not hits and len(name) >= 6:
                for cut in (2, 3):
                    hits = api.complexes_search(q=name[cut:], limit=3).get("items") or []
                    if hits:
                        break
            if hits:
                con2 = sqlite3.connect(DB_PATH)
                con2.row_factory = sqlite3.Row
                try:
                    row = con2.execute(
                        "SELECT complex_no, complex_name, cortar_no, total_household_count, "
                        "total_building_count, use_approve_ymd, road_address, detail_address, dong_name "
                        "FROM complexes WHERE complex_no=?", (hits[0]["complex_no"],)).fetchone()
                    return dict(row) if row else None
                finally:
                    con2.close()
        except Exception:
            pass
        return None

    # 지역이 지정됐으면 그 지역 단지를 우선(있을 때만). 타지역 동명 단지가 정확명 보너스로
    # 이기는 것을 막는다(예: '해운대 마린시티 제니스' → 성남 '제니스'가 선택되던 버그).
    if reg:
        def _inreg(r):
            c = r["cortar_no"] or ""
            if reg.get("dong_cortar"):
                return c == reg["dong_cortar"]
            if reg.get("sigungu_code"):
                return c.startswith(reg["sigungu_code"])
            if reg.get("city4"):
                return c[:4] == reg["city4"]
            if reg.get("sido_code"):
                return c.startswith(reg["sido_code"])
            return True
        inreg = [r for r in rows if _inreg(r)]
        if inreg:
            rows = inreg

    def sc(r):
        s = 0.0
        if r["complex_name"] == needle:
            s += 4
        elif r["complex_name"].startswith(needle):
            s += 1.5
        c = r["cortar_no"] or ""
        if reg and reg.get("dong_cortar") and c == reg["dong_cortar"]:
            s += 5
        elif reg and reg.get("sigungu_code") and c.startswith(reg["sigungu_code"]):
            s += 2.5
        elif reg and reg.get("sido_code") and c.startswith(reg["sido_code"]):
            s += 1
        s += min((r["total_household_count"] or 0) / 2000.0, 2)
        return s

    return dict(max(rows, key=sc))


def get_complex_info(complex_name: str, region: str = "") -> dict:
    """특정 아파트 단지의 종합 정보. 세대수·준공·주소 + 최근 실거래 요약(등기·동 포함) +
    급매 보유 중개사(연락처)를 한 번에 준다. '이 단지 어때?', '실거래가', '급매 중개사' 질문용.

    Args:
        complex_name: 단지명. 예: '둔산동 크로바', '잠실엘스', '은하수'.
        region: 지역(선택). 동명이 단지가 많으면 지역을 주면 정확해진다.
    """
    import scripts.local_api as api
    cx = _find_complex_row(complex_name, region)
    if not cx:
        return {"error": f"'{complex_name}' 단지를 찾지 못했습니다. 지역을 함께 알려주세요."}
    cno = cx["complex_no"]
    tx = api.complex_transactions(cno, months=12, limit=120)
    sales = tx.get("sale", [])
    recent = [{
        "계약일": s["deal_ymd"], "전용㎡": s["excl_use_ar"], "층": s["floor"],
        "금액": _won(s["deal_amount"]), "거래": s["dealing_gbn"],
        "동": s.get("dong"), "등기": ("완료" if s.get("registered") else "미등기"),
    } for s in sales[:6]]
    # 전세·월세 실거래도 포함 — 'OO 전세/월세' 질문에 답할 수 있게(매매만 보던 버그 보완).
    rents = (tx.get("jeonse") or []) + (tx.get("wolse") or [])
    rents.sort(key=lambda r: r.get("deal_ymd", ""), reverse=True)
    recent_rent = [{
        "계약일": r.get("deal_ymd"), "전용㎡": r.get("excl_use_ar"), "층": r.get("floor"),
        "보증금": _won(r.get("deposit")),
        "월세": (_won(r["monthly_rent"]) if r.get("monthly_rent") else None),
        "구분": ("월세" if r.get("monthly_rent") else "전세"),
    } for r in rents[:6]]
    # 분양권/입주권 실거래(silv) — 신축 단지는 매매·전세가 없고 분양권만 있어 '실거래 없음'으로
    # 보이던 문제 수정. 분양권 전매가가 사실상 그 단지의 현재 시세다.
    silv = tx.get("silv", [])
    recent_silv = [{
        "계약일": s.get("deal_ymd"), "전용㎡": s.get("excl_use_ar"), "층": s.get("floor"),
        "금액": _won(s.get("deal_amount")), "종류": s.get("kind"),
    } for s in silv[:6]]
    try:
        dres = api.complex_quick_deals(cno, min_discount=0.05, limit=8)
        deals = [{
            "면적타입": d["area_name"], "층": d["floor_info"], "호가": _won(d["price"]),
            "할인율%": round((d["discount"] or 0) * 100, 1),
            "중개사": d["realtor_name"], "전화": d["tel"],
        } for d in dres.get("items", [])]
    except Exception:
        deals = []
    return {
        "단지": cx["complex_name"], "지역": cx.get("dong_name") or "",
        "세대수": cx["total_household_count"], "동수": cx["total_building_count"],
        "준공년도": (cx["use_approve_ymd"] or "")[:4] or None,
        "주소": cx.get("road_address") or cx.get("detail_address"),
        "단지정보": f"/complex/{cno}",   # 프런트 바로가기
        "최근12개월_매매건수": len(sales), "최근실거래": recent,
        "최근12개월_전월세건수": len(rents), "최근전월세": recent_rent,
        "최근12개월_분양권건수": len(silv), "최근분양권실거래": recent_silv,
        "급매_보유중개사": deals,
    }


def find_record_high(region: str, trade_type: str = "매매",
                     months: int = 6, limit: int = 15) -> dict:
    """특정 지역에서 '신고가 경신'(그 단지·평형의 역대 최고가를 최근 갈아치운) 거래 목록.

    Args:
        region: 자연어 지역. 예: '강남구', '대전 서구', '분당'.
        trade_type: '매매' 또는 '전세'.
        months: 최근 몇 개월 내 경신을 볼지. 보통 3~6.
    """
    import scripts.local_api as api
    reg = _resolve_region(region)
    if not reg:
        return {"error": f"지역 '{region}' 을(를) 찾지 못했습니다."}
    tt = "B1" if "전세" in trade_type else "A1"
    # 캐시 선조회 — 빌더 AI 캐논 키(days 30/90/180/360)와 일치 시 즉시. 미스 → 라이브.
    items = _rank_items("/stats/tx-record-high", api.tx_record_high,
                        days=int(months * 30), trade=tt, asset="apt",
                        order="recent", limit=1000)
    if reg.get("dong_cortar"):
        items = [x for x in items if (x.get("cortar_no") or "") == reg["dong_cortar"]]
    elif reg.get("sigungu_code"):
        items = [x for x in items if (x.get("cortar_no") or "").startswith(reg["sigungu_code"])]
    elif reg.get("sido_code"):
        items = [x for x in items if (x.get("cortar_no") or "").startswith(reg["sido_code"])]

    def up(x):
        rp, ph = x.get("record_price"), x.get("prev_high")
        return round((rp - ph) / ph * 100, 1) if rp and ph else None

    out = [{
        "단지": x["complex_name"], "면적타입(공급㎡)": x["area_key"],
        "신고가": _won(x["record_price"]), "경신일": x["record_date"],
        "직전최고": _won(x["prev_high"]), "상승률%": up(x), "층": x["floor"],
        "단지정보": f"/complex/{x['complex_no']}",
    } for x in items[:limit]]
    return {
        "해석된_지역": " ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]])),
        "거래유형": trade_type, "건수": len(out), "신고가목록": out,
    }


def region_market_pulse(region: str = "") -> dict:
    """지역(시도) 실거래 거래량 분위기: 이번달 vs 지난달 vs 전년동월 vs 3년평균/예측.
    '요즘 거래 활발해?' 같은 질문용. region 을 비우면 전국 시도 전체를 준다.
    (참고: 시도 단위까지만 지원. 구/동 단위 거래량은 미지원.)
    """
    import scripts.local_api as api
    # 기본 캐시(D리스트)에 같은 키가 있어 선조회 — 콜드 5.5s → 0초대
    res = api.cache_get("/stats/tx-region-pulse", {"asset": "apt"}) or api.tx_region_pulse(asset="apt")
    items = res.get("regions", [])
    reg = _resolve_region(region) if region else None

    def row(it):
        return {
            "지역": it["region_name"], "이번달": it["current_month_count"],
            "지난달": it["prev_month_count"], "전년동월": it.get("yoy_cur_actual"),
            "최근3년평균": it.get("avg3y_cur_actual"), "이번달_예측": it.get("current_month_pred"),
        }

    note = None
    if reg:
        m = [it for it in items if it["region_code"] == reg["sido_code"]]
        data = [row(it) for it in m] or [{"note": f"{reg['sido']} 데이터 없음"}]
        # 구·동을 물었어도 이 수치는 시도 전체다 → 모델이 '강남구 N건'으로 오기재하지 않도록 명시.
        if reg.get("sigungu") or reg.get("dong"):
            note = (f"이 거래량은 '{reg.get('sigungu') or reg.get('dong')}'가 아니라 "
                    f"**{reg['sido']} 전체(시도)** 기준입니다. 구·동 단위 거래량은 미지원이니 "
                    f"답변에 반드시 '{reg['sido']} 기준'이라고 밝히세요.")
    else:
        data = [row(it) for it in items]
    out = {"기준월": res.get("current_month"), "신고기준일": res.get("filed_date"), "분위기": data}
    if note:
        out["주의"] = note
    return out


def find_realtor(name: str = "", region: str = "") -> dict:
    """중개사무소 검색 + 상세. 주소·전화·보유매물수·전국등수·거래실적·개설등록일·상태·주요 보유단지.
    '강남 ㅇㅇ공인 어때?', '둔산동 크로바시티공인 연락처' 같은 질문용.
    이름 없이 '○○동 부동산 추천/근처 중개사무소' 처럼 물으면 name을 비워라 —
    그 지역 매물 많은 중개사무소 목록으로 답한다.

    Args:
        name: 중개사무소 이름(부분 가능). 예: '크로바시티공인', '래미안공인'. 이름 모르면 빈 문자열.
        region: 지역(선택). 같은 이름이 많으니 지역을 주면 정확.
    """
    import scripts.local_api as api
    if not (name or "").strip():
        # 이름 없는 '지역 부동산 추천' → 지역 매물보유 상위 중개사 랭킹으로 폴백
        return rank_realtors(metric="매물보유", region=region, limit=8)
    # 사무소 유형어 제거 — '제이에스부동산중개'의 '부동산'이 동(대구 '부동')으로 오매칭돼
    # 엉뚱한 지역으로 스코핑되던 버그 방지. 지역해석·검색 모두 핵심명 기준.
    _office = r"(공인중개사사무소|공인중개사|부동산중개법인|부동산중개|중개사무소|부동산|공인|중개사|중개|사무소|법인|주식회사)"
    name_clean = re.sub(_office, " ", name).strip()
    reg = _resolve_region((region + " " + name_clean).strip())
    toks = [t for t in name_clean.split() if not _resolve_region(t)]
    q = (" ".join(toks)).strip() or name_clean or name.strip()
    sido = (reg["sido_code"] if reg else "")
    cands = api.realtors_search(q=q, sido=sido, limit=10).get("items", [])
    if not cands:
        # 접미사 차이 보정: '제이에스부동산중개'→'제이에스'(실제명 '제이에스공인중개사')처럼
        # 사무소 유형어를 떼고 핵심명으로 재검색.
        core = re.sub(r"(공인중개사사무소|공인중개사|부동산중개법인|부동산중개|중개사무소|부동산|공인|중개사|중개|사무소|법인|주식회사)", "", q).strip()
        if core and core != q:
            cands = api.realtors_search(q=core, sido=sido, limit=10).get("items", [])
    if not cands:
        return {"error": f"'{name}' 중개사를 찾지 못했습니다. 지역을 함께 알려주세요."}
    det = api.realtor_detail(cands[0]["realtor_id"])
    nv = det.get("naver") or {}
    vw = det.get("vworld") or {}
    top = sorted(det.get("by_complex", []), key=lambda x: -(x.get("total") or 0))[:3]
    return {
        "중개사": det.get("realtor_name"),
        "중개사정보": f"/realtor/{cands[0]['realtor_id']}",   # 프런트 바로가기
        "주소": nv.get("address"),
        "전화": nv.get("tel") or nv.get("cell"),
        "보유매물수": det.get("total_count"),
        "전국등수": (f"{det.get('national_rank')}/{det.get('national_total')}"
                  if det.get("national_rank") else None),
        "거래실적": {"매매": nv.get("deal_count"), "전세": nv.get("lease_count"), "월세": nv.get("rent_count")},
        "개설등록일": vw.get("registered_ymd"), "상태": vw.get("status"),
        "주요_보유단지": [{"단지": t.get("complex_name"), "매물": t.get("total")} for t in top],
        "검색후보수": len(cands),
    }


def _in_region(rn: str, reg: dict | None) -> bool:
    """region_name 문자열이 해석된 지역에 속하는지(best-effort). regions.cortar_name 기반이라 양쪽이 일치."""
    if not reg:
        return True
    rn = rn or ""
    if reg.get("dong"):
        return reg["dong"] in rn
    if reg.get("sigungu"):
        return (reg["sigungu"] or "") in rn
    if reg.get("sido"):
        return (reg["sido"] or "") in rn
    return True


def _rank_items(path: str, fn, **params) -> list:
    """전국 랭킹 캐시 선조회 → 미스 시 라이브 폴백.

    build_api_cache 의 AI 캐논 키와 파라미터가 정확히 일치해야 HIT 하므로,
    호출부는 항상 limit=500 등 캐논 값을 쓰고 건수 축소는 호출 후 슬라이스.
    (콜드 디스크에서 매물적체 31s·저가거래 22s 등이 캐시로 0초대가 된다)
    """
    import scripts.local_api as api
    cached = api.cache_get(path, params)
    if cached is not None:
        return cached.get("items", [])
    return fn(**params).get("items", [])


def rank_complexes(metric: str, order: str = "", pyeong: int = 0,
                   region: str = "", limit: int = 15) -> dict:
    """단지/거래 순위 통계. 기본 전국 기준이며 region 을 주면 그 지역만 추린다(best-effort).

    Args:
        metric: 다음 중 하나 —
            '갭'(매매-전세 갭, 작을수록 갭투자 유리) | '전세가율'(전세/매매) | '평당가' |
            '최고가'(실거래 최고가 거래) | '거래량'(거래 많은 단지) |
            '저가거래'(평균 대비 크게 싼 거래=증여 의심) | '회전율'(거래량/세대수) |
            '수익률'(월세수익률) | '호가갭'(호가가 실거래보다 비싼 정도) |
            '저평가'/'회복률'(전고점 대비 현재가 — 낮을수록 저평가, '반등'·'전고점'도 동일).
        order: '낮은순' 또는 '높은순'. 비우면 metric별 기본 정렬.
        pyeong: 평형대 10/20/30/40. 0=전체.
        region: 자연어 지역(선택). 예: '강남구', '대전'. 일부 지표는 지역 결과가 적을 수 있음.
        limit: 최대 건수(최대 30).
    """
    import scripts.local_api as api
    ac = {0: "all", 10: "10s", 20: "20s", 30: "30s", 40: "40s"}.get(pyeong, "all")
    lim = min(max(int(limit), 1), 30)
    reg = _resolve_region(region) if region else None
    # 풀은 항상 500 — 캐시 키(빌더의 AI 캐논)와 일치시켜 HIT 시키고, 건수는
    # 마지막 items[:lim] 슬라이스로 줄인다. 지역 필터 시 큰 풀이 필요하기도 함.
    pool = 500
    param_region = False                  # 엔드포인트가 자체 지역 파라미터로 이미 좁혔는지
    m = metric.replace(" ", "")
    high = ("높" in order or "큰" in order or "비싼" in order) if order else None

    # 서버측 지역 스코핑 인자(거래량·평당가·갭·회전율·저평가·수익률 엔드포인트가 지원).
    # 전국 top-500 후필터로는 강남구 거래량처럼 '전국 상위 밖' 지역이 빈손이 되므로,
    # 가능한 지표는 엔드포인트 SQL 안에서 그 지역만 집계하게 한다.
    reg_kw: dict = {}
    if reg:
        if reg.get("sigungu_cortar"):
            reg_kw = {"sigungu": reg["sigungu_cortar"]}
        elif reg.get("dong_cortar"):
            reg_kw = {"sigungu": reg["dong_cortar"]}      # 동→그 동의 시군구(5자리)까지
        elif reg.get("sido_code"):
            reg_kw = {"sido": reg["sido_code"]}           # 통합시 포함 시도 단위

    def pct(v):
        return round((v or 0) * 100, 1)

    if "갭" in m and "호가" not in m:
        o = "desc" if high else "asc"
        items = _rank_items("/stats/tx-gap-rank", api.tx_gap_rank,
                            asset="apt", area_class=ac, order=o, limit=pool, **reg_kw)
        param_region = bool(reg_kw)
        title = f"갭 {'큰' if high else '작은'}순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "면적타입": x["area_key"],
                         "매매평균": _won(x["avg_sale"]), "전세평균": _won(x["avg_jeonse"]),
                         "갭": _won(x["gap"]), "전세가율%": pct(x["jeonse_rate"])}
    elif "전세" in m:
        o = "asc" if high is False else "desc"
        items = _rank_items("/stats/tx-jeonse-rate", api.tx_jeonse_rate,
                            asset="apt", area_class=ac, order=o, limit=pool)
        title = ("전세가율 높은순 — 주의: 100% 초과는 전세가 매매보다 비싼 역전 상태로 "
                 "깡통전세 위험 신호. 답변에 이 경고와 깡통전세지수(/jeonse-check) 안내를 포함하라")
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "면적타입": x["area_key"],
                         "전세가율%": pct(x["jeonse_rate"]), "매매평균": _won(x["avg_sale"]), "전세평균": _won(x["avg_jeonse"])}
    elif "평당" in m or "평단" in m:
        o = "asc" if high is False else "desc"
        items = _rank_items("/stats/tx-pyeong-price", api.tx_pyeong_price,
                            asset="apt", area_class=ac, order=o, limit=pool, **reg_kw)
        # 평형별 행이라 같은 단지가 반복 노출 → 단지당 대표 1행(최상위 평당가)만
        _seen: set = set()
        items = [x for x in items
                 if not (x.get("complex_no") in _seen or _seen.add(x.get("complex_no")))]
        param_region = bool(reg_kw)
        title = f"평당가 {'낮은' if high is False else '높은'}순 (단지별 대표 평형 1건)"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "면적타입": x["area_key"],
                         "평당가": _won(x["pyeong_price"]), "거래평균": _won(x["avg_price"])}
    elif "최고가" in m or "비싼" in m:
        items = _rank_items("/stats/tx-top-price", api.tx_top_price,
                            trade="A1", asset="apt", area_class=ac, limit=pool)
        title = "실거래 최고가순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "거래가": _won(x["price"]),
                         "전용㎡": x["excl_use_ar"], "층": x["floor"], "계약일": x["deal_ymd"]}
    elif "거래량" in m or "거래 많" in m:
        items = _rank_items("/stats/tx-top-volume", api.tx_top_volume,
                            trade="A1", asset="apt", area_class=ac, limit=pool, **reg_kw)
        param_region = bool(reg_kw)
        title = "거래량 많은순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "거래건수": x.get("count"), "세대수": x.get("households")}
    elif "저가" in m or "증여" in m:
        items = _rank_items("/stats/tx-low-price", api.tx_low_price,
                            asset="apt", area_class=ac, limit=pool)
        title = "평균 대비 크게 싼 거래(증여 의심)"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "거래가": _won(x["deal_amount"]),
                         "평균가": _won(x["avg_price"]), "할인율%": pct(x["discount_rate"]),
                         "전용㎡": x["excl_use_ar"], "층": x["floor"], "거래": x.get("dealing_gbn")}
    elif "회전" in m:
        items = _rank_items("/stats/tx-turnover", api.tx_turnover,
                            trade="A1", asset="apt", area_class=ac, limit=pool, **reg_kw)
        param_region = bool(reg_kw)
        title = "거래회전율 높은순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "거래건수": x["tx_count"],
                         "세대수": x["households"], "회전율%": pct(x["turnover_rate"])}
    elif "수익" in m:
        _yield_kw = dict(asset="apt", area_class=ac, limit=pool)
        if reg:
            _yield_kw["sido"] = reg["sido_code"]   # sido 키는 캐시 미스 → 라이브(0.7s라 무방)
        items = _rank_items("/stats/tx-yield", api.tx_yield, **_yield_kw)
        param_region = True              # yield 는 sido 파라미터로 이미 좁혔고 region_name 에 시도가 없어 후처리 제외
        title = "월세수익률 높은순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "수익률%": round((x["yield_rate"] or 0) * 100, 1),
                         "매매평균": _won(x["avg_sale"]), "월세평균": _won(x.get("avg_monthly"))}
    elif "호가" in m:
        items = _rank_items("/stats/tx-asking-vs-real", api.tx_asking_vs_real,
                            area_class=ac, order="desc", limit=pool)
        title = "호가-실거래 갭 큰순(호가 비쌈)"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "호가평균": _won(x["avg_asking"]),
                         "실거래평균": _won(x["avg_real"]), "갭율%": pct(x["gap_rate"])}
    elif "저평가" in m or "회복" in m or "전고점" in m or "반등" in m:
        o = "desc" if high else "asc"   # 기본 asc=저평가순(회복률 낮은)
        kw = dict(order=o, limit=pool)
        if reg and (reg.get("sigungu_cortar") or reg.get("sido_code")):
            if reg.get("sigungu_cortar"):
                kw["sigungu"] = reg["sigungu_cortar"]
            else:
                kw["sido"] = reg["sido_code"]
            param_region = True   # 엔드포인트가 지역 스코핑함
        items = _rank_items("/stats/tx-recovery", api.tx_recovery, **kw)
        title = f"전고점 대비 {'회복' if high else '저평가'}순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "면적타입": f"{x['pyeong']}㎡",
                         "전고점": _won(x["peak_amt"]), "최근평균": _won(x["cur_avg"]),
                         "회복률%": x["recovery_rate"], "거래수": x["n"]}
    else:
        # 단지엔 '직원'이 없다(중개사무소 개념) → 중개사 순위로 안내. 반드시 한국어로 답하라.
        if "직원" in m or "보조" in m or "공인중개사" in m:
            return {"안내_한국어로답할것": "아파트 '단지'는 직원수로 순위를 낼 수 없어요(직원은 중개사무소 개념입니다). "
                    "'직원 많은 부동산/중개사무소'를 찾으시면 중개사 순위로 알려드릴게요.", "권장도구": "rank_realtors"}
        return {"안내_한국어로답할것": "단지 순위 기준(metric)은 거래량·평당가·갭·전세가율·최고가·회전율·수익률·저평가 중 하나예요."}

    if reg and not param_region:
        items = [x for x in items if _in_region(x.get("region_name"), reg)]
    rows = []
    for x in items[:lim]:
        d = row(x)
        if x.get("complex_no"):
            d["단지정보"] = f"/complex/{x['complex_no']}"   # 프런트 바로가기
        rows.append(d)
    return {
        "통계": title,
        "범위": (" ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]])) if reg else "전국"),
        "평형대": (f"{pyeong}평대" if pyeong else "전체"),
        "건수": len(rows), "순위": rows,
    }


def rank_realtors(metric: str = "직원수", region: str = "", limit: int = 20) -> dict:
    """중개사무소(부동산 중개업소·중개법인) 순위.

    Args:
        metric: '직원수'(소속 인원) | '공인중개사수'(자격 보유 인원) | '보조원수'(중개보조원) |
                '공인중개사비율'(인원 대비 자격자 비율) | '업력'(개업 오래된순) |
                '매물보유'(중개사무소가 보유한 매물 많은순). 기본 '직원수'.
                ※ '매물 많은 부동산/중개사무소'는 여기(매물보유)로. '매물 많은 단지/아파트'는 rank_complexes 로.
        region: 자연어 지역(선택). 동(읍·면·동)까지 주면 '우리동네 중개사'(사무소 소재지) 랭킹.
        limit: 최대 건수(최대 50).
    """
    import scripts.local_api as api
    lim = min(max(int(limit), 1), 50)
    m = (metric or "").replace(" ", "").lower()

    # 지역 → sgg_cd 접두(2=시도 / 4=통합시 / 5=시군구). 엔드포인트 SQL 안에서 그 지역만
    # 랭킹하므로 '청주 업력순위'가 전국 상위로 새지 않는다. (동 단위는 시군구로 올림)
    reg = _resolve_region(region) if region else None
    pref = ""
    scope = "전국"
    if reg:
        if reg.get("dong_cortar"):
            pref = reg["dong_cortar"][:5]
        elif reg.get("sigungu_cortar"):
            pref = reg["sigungu_cortar"][:5]
        elif reg.get("city4"):
            pref = reg["city4"]
        elif reg.get("sido_code"):
            pref = reg["sido_code"]
        scope = " ".join(filter(None, [reg.get("sido"), reg.get("sigungu"), reg.get("dong")])) or "전국"

    # 동(읍·면·동)까지 지정되면 '우리동네 중개사'(사무소 소재지 기준) 랭킹 사용.
    dong_cortar = reg.get("dong_cortar") if reg else None
    if dong_cortar:
        sort = ("staff" if ("직원" in m or "보조" in m or "공인중개사" in m or "자격" in m or "비율" in m)
                else "tenure" if ("업력" in m or "오래" in m) else "listings")
        d = api.realtors_by_dong(cortar=dong_cortar, sort=sort, limit=lim)
        rows = []
        for x in d.get("items", [])[:lim]:
            r = {"중개사무소": x.get("realtor_name"), "매물수": x.get("listings"),
                 "직원수": x.get("staff_count"), "업력": x.get("tenure_years")}
            if x.get("realtor_id"):
                r["중개사정보"] = f"/realtor/{x['realtor_id']}"
            rows.append(r)
        return {"통계": f"{d.get('dong_name') or scope} 우리동네 중개사", "범위": scope,
                "건수": len(rows), "순위": rows}

    if "업력" in m or "오래" in m or "tenure" in m:
        items = api.realtors_by_tenure(limit=50, region=pref).get("items", [])
        title = "업력(개업 오래된) 순위"
    elif "매물" in m or "보유" in m or "listing" in m or "national" in m:
        # 매물보유 순위 — 전체매물(단지형+비단지) 기준. 시도 지정 시 그 시도 랭킹을 직접 쓴다.
        # (예전엔 전국 top100을 시도로 후필터해 '서울 2곳'처럼 거의 비어버리던 버그 수정.)
        if reg and reg.get("sido"):
            groups = api.realtors_by_sido(limit=lim, scope="all").get("groups", {})
            items = groups.get(reg["sido"], [])
            if reg.get("sigungu") or reg.get("dong"):
                scope = reg["sido"]  # 구·동 단위 매물보유 랭킹은 미지원 → 시도 기준으로 정직 표기
            title = f"{reg['sido']} 보유 매물 많은 순위(전체 매물)"
        else:
            items = api.realtors_national(limit=lim, scope="all").get("items", [])
            title = "전국 보유 매물 많은 순위(전체 매물)"
    elif "비율" in m or "ratio" in m:
        items = api.realtors_by_staff(limit=50, region=pref, by="ratio").get("items", [])
        title = "공인중개사 비율 높은 순위(인원 3명+)"
    elif "보조원" in m or "assistant" in m:
        items = api.realtors_by_staff(limit=50, region=pref, by="assistant").get("items", [])
        title = "중개보조원 많은 순위"
    elif "공인중개사" in m or "자격사" in m or "licensed" in m:
        items = api.realtors_by_staff(limit=50, region=pref, by="licensed").get("items", [])
        title = "공인중개사(자격) 많은 순위"
    else:
        items = api.realtors_by_staff(limit=50, region=pref).get("items", [])
        title = "직원수(소속 인원) 순위"

    rows = []
    for x in items[:lim]:
        d = {"중개사무소": x.get("realtor_name"), "지역": x.get("sido"),
             "직원수": x.get("staff_count"), "공인중개사수": x.get("licensed_count"),
             "보조원수": x.get("assistant_count"), "공인중개사비율": x.get("licensed_ratio"),
             "매물수(단지형·순위기준)": x.get("count"),
             "참고_전체매물(빌라·상가 포함)": x.get("total_count") or x.get("count"),
             "개업연도": x.get("established_year")}
        if x.get("realtor_id"):
            d["중개사정보"] = f"/realtor/{x['realtor_id']}"
        rows.append({k: v for k, v in d.items() if v is not None})
    return {"통계": title, "범위": scope, "건수": len(rows), "순위": rows,
            "정렬기준": "단지형 매물수 내림차순(콕집 표준). '보유매물(전체)'는 빌라·상가 등 "
                    "비단지를 포함한 참고값이라 나열 순서와 어긋날 수 있음 — 순서를 재배열하지 말고 "
                    "단지형 기준 순위라고 밝혀라."}


# ── 매물 시장 통계 · 상승/하락 · 매수비용 (2026-07-09 접목) ──────────────────

def get_listing_stats(region: str = "") -> dict:
    """지역 아파트 '매물(호가)' 시장 통계 — 매물 광고 수, 실매물 수(같은 집 중복 광고를 1건으로
    합친 수), 집 1채당 광고 수(높을수록 매도 경쟁 치열), 매매/전세/월세 평균 호가와 전일 변동.
    '서울 매물 몇 개야?', '요즘 매물 쌓이고 있어?', '평균 호가 어때?', '매도 경쟁 심해?' 질문용.
    region 비우면 전국. (실거래가 아니라 현재 나와 있는 매물 기준)
    """
    import scripts.local_api as api
    reg = _resolve_region(region) if region else None
    kw = {}
    note = None
    if reg:
        if reg.get("sigungu_code"):
            kw["sigungu"] = reg["sigungu_code"]
            if reg.get("dong"):
                note = (f"동 단위 매물통계는 미지원 — 이 수치는 '{reg['dong']}'이 아니라 "
                        f"**{reg.get('sigungu')}(시군구 전체)** 기준입니다. 답변에 명시하세요.")
        elif reg.get("sido_code"):
            kw["sido"] = reg["sido_code"]
    res = api.changes_summary(asset="apt", **kw)
    trades = res.get("trades", {})

    def row(t, price_key="avg_price", chg_key="avg_change"):
        tr = trades.get(t) or {}
        cnt, u = tr.get("count") or 0, tr.get("units")
        d = {"평균호가": _won(tr.get(price_key)),
             "전일변동%": (round(tr[chg_key] * 100, 2) if tr.get(chg_key) is not None else None),
             "매물광고수": cnt, "실매물수": u,
             "집1채당광고": (round(cnt / u, 2) if u else None)}
        return {k: v for k, v in d.items() if v is not None}

    scope_note = None
    if (reg and reg.get("sido") and not reg.get("sigungu_code") and region.strip()
            and region.strip() not in (reg.get("sido") or "")):
        scope_note = (f"요청 지역 '{region.strip()}'은(는) 시군구로 해석되지 않아 **{reg['sido']} 전체** 기준 — "
                      f"답변에 '{reg['sido']} 기준'이라고 정확히 말할 것.")
    out = {
        "지역": (" ".join(filter(None, [reg.get("sido"), reg.get("sigungu")])) if reg else "전국"),
        **({"범위주의": scope_note} if scope_note else {}),
        "기준일": res.get("latest_date"),
        "매매": row("A1"), "전세": row("B1"),
        "월세": (lambda b2: ({**{k: v for k, v in b2.items() if k != "평균호가"},
                              "보증금평균": b2.get("평균호가"),
                              "월세액평균_매달내는돈": _won((trades.get("B2") or {}).get("rent_avg"))}))(row("B2")),
        "총매물광고": res.get("total"), "총실매물": res.get("total_units"),
        "용어": "실매물=같은 집을 여러 중개업소가 올린 중복 광고를 1건으로 합친 수. "
              "매물수를 말할 때 '광고 N건(실매물 M건)'처럼 병기하면 정확하다. "
              "월세의 '평균호가/보증금평균'은 보증금(목돈), '월세액평균'은 매달 내는 돈 — 절대 바꿔 말하지 말 것. "
              "집1채당광고는 전국 평균이 약 2.3~2.4 — 그와 비슷하면 '보통 수준', 2.6 이상처럼 뚜렷이 높을 때만 "
              "'매도 경쟁이 치열'이라고 해석하라.",
    }
    if note:
        out["주의"] = note
    return out


def find_price_movers(region: str = "", days: int = 7, trade_type: str = "매매") -> dict:
    """최근 매물 평균 호가가 많이 오르거나 내린 단지 Top — 상승/하락 각 5개.
    '요즘 호가 많이 오른 단지', '가격 내린 아파트 어디야?' 질문용.
    days: 비교 기간(7/14/30일만). 실거래가 아니라 매물 호가 기준이며,
    매물 구성이 바뀌어도 평균이 움직일 수 있어 참고용임을 답변에 밝힐 것.
    """
    import scripts.local_api as api
    tt = {"매매": "A1", "전세": "B1", "월세": "B2"}.get(trade_type, "A1")
    days = days if days in (7, 14, 30) else 7
    reg = _resolve_region(region) if region else None
    kw = {}
    if reg:
        if reg.get("sigungu_code"):
            kw["sigungu"] = reg["sigungu_code"]
        elif reg.get("sido_code"):
            kw["sido"] = reg["sido_code"]
    res = api.changes_movers(trade=tt, asset="apt", days=days, min_listings=5, limit=5, **kw)

    def rows(lst):
        return [{"단지": x.get("complex_name"), "지역": x.get("region_name"),
                 "평형": x.get("area_name"),
                 "변동%": round((x.get("rate") or 0) * 100, 1),
                 "이전평균호가": _won(x.get("old_avg")), "현재평균호가": _won(x.get("new_avg")),
                 "단지정보": f"/complex/{x['complex_no']}" if x.get("complex_no") else None}
                for x in (lst or [])]

    return {"거래유형": trade_type, "비교기간": f"{res.get('from_date')} → {res.get('to_date')}",
            "상승Top": rows(res.get("up")), "하락Top": rows(res.get("down")),
            "주의": "매물 호가 평균 기준(실거래 아님). 매물이 들어오고 나가며 평균이 움직일 수 있어 참고용."}


def calc_purchase_cost(sale_price_eok: float, house_count: int = 0, is_first_time: bool = False,
                       is_over_85m2: bool = False, region_type: str = "규제지역",
                       is_adjusted_area: bool = True, is_temp_two_house: bool = False) -> dict:
    """아파트 매수 시 취득세·지방교육세·농어촌특별세·중개보수 상한·주택담보대출 한도 계산.
    '10억 아파트 취득세 얼마?', '15억 사면 대출 얼마 나와?', '중개수수료 얼마?' 질문용.
    콕집 아파트매수계산기(/buy-calculator)와 동일 산식(2025.10.15 대출규제+2026.6.30 추가지정 반영).

    Args:
        sale_price_eok: 매매가(억 단위, 예: 10.5)
        house_count: 구입 전 보유 주택 수(0=무주택)
        is_first_time: 생애최초 여부 — 사용자가 '생애최초'라고 명시했을 때만 True.
            '무주택'은 생애최초가 아니다(과거 주택 보유 이력이 있을 수 있음). 명시 없으면 False.
        is_over_85m2: 전용 85㎡ 초과 여부(농특세 과세·생초 감면 배제)
        region_type: "규제지역"(서울 전역+경기 과천·광명·하남·의왕·수원3구·성남3구·안양동안·용인수지·
                     화성동탄·용인기흥·구리) | "수도권 비규제" | "지방"
        is_adjusted_area: 조정대상지역 여부(다주택 중과 판단, 규제지역이면 True)
        is_temp_two_house: 일시적 2주택(처분조건부) 여부
    """
    p = int(round(sale_price_eok * 1e8))
    if p <= 0 or p > 500_000_000_000:
        return {"오류": "매매가가 범위를 벗어났습니다"}

    # ── 취득세 (frontend/src/lib/buycalc.ts acquisitionTax 와 동일 산식) ──
    ft_note = None
    if is_first_time and house_count <= 1 and not is_over_85m2 and p <= 6e8:
        acq = int(p * 0.005) if p <= 6e7 else int(3e5 + (p - 6e7) * 0.008)
        # 감면 전 일반세액(1주택 이하 기준) — '감면액'과 '납부액'을 모델이 혼동하지 않게 병기
        std = (int(p * 0.01) if p <= 6e7 else int(6e5 + (p - 6e7) * 0.013))
        ft_note = (f"생애최초 감면 적용 — 이 취득세는 **감면 후 납부액**. "
                   f"일반세액 {_won(std)}에서 {_won(std - acq)} 감면된 결과다(감면액과 납부액을 바꿔 말하지 말 것).")
    elif is_temp_two_house and house_count == 2:
        acq = int(p * 0.01)
    elif house_count <= 1:
        if p <= 6e7:
            acq = int(p * 0.01)
        elif p <= 6e8:
            acq = int(6e5 + (p - 6e7) * 0.013)
        elif p <= 9e8:
            acq = int(7_620_000 + (p - 6e8) * 0.028)
        else:
            acq = int(16_020_000 + (p - 9e8) * 0.04)
    elif house_count == 2:
        acq = int(p * (0.08 if is_adjusted_area else 0.01))
    else:
        acq = int(p * (0.12 if is_adjusted_area else 0.03))
    edu = acq // 10                                   # 지방교육세 = 취득세×10%
    rural = int(p * 0.002) if is_over_85m2 else 0     # 농특세: 85㎡ 초과만 취득가×0.2%

    # ── 중개보수 상한 (2021.10 개정 현행 요율, 정수 퍼밀 연산 — 법정상한 초과 불가) ──
    for mx, permille, limit in ((5e7, 6, 250_000), (2e8, 5, 800_000), (9e8, 4, None),
                                (12e8, 5, None), (15e8, 6, None), (float("inf"), 7, None)):
        if p < mx:
            broker = (p * permille) // 1000
            if limit:
                broker = min(broker, limit)
            break

    # ── 대출 규제 (2025.10.15 대책 + 2026.6.30 추가지정) ──
    capital_or_reg = region_type in ("규제지역", "수도권 비규제")
    buyer = ("무주택" if house_count == 0 else
             "처분조건부(일시적 2주택)" if is_temp_two_house else
             "1주택 유지" if house_count == 1 else "다주택")
    if capital_or_reg and buyer in ("다주택", "1주택 유지"):
        loan_line = f"대출 불가 — 수도권·규제지역 {buyer} 추가 구입은 주택담보대출 금지(6.27 대책)"
    else:
        if region_type == "규제지역":
            ltv = 0.7 if is_first_time else 0.4
            cap = 6e8 if p <= 15e8 else (4e8 if p <= 25e8 else 2e8)
        elif region_type == "수도권 비규제":
            ltv, cap = 0.7, 6e8
        else:
            ltv = (0.6 if buyer in ("1주택 유지", "다주택") else (0.8 if is_first_time else 0.7))
            cap = None
        ltv_amt = int(p * ltv)
        max_loan = min(ltv_amt, int(cap)) if cap else ltv_amt
        loan_line = (f"최대 {_won(max_loan)} (LTV {int(ltv * 100)}%={_won(ltv_amt)}, "
                     f"총액캡 {(_won(int(cap)) if cap else '없음')}) — 실제 한도는 DSR·소득·은행 심사로 더 줄 수 있음")

    # 평평한 구조(중첩·불리언 없음) — 함수응답 페이로드 견고화
    return {
        "매매가": _won(p), "매수자유형": buyer, "지역구분": region_type,
        "취득세": _won(acq), **({"취득세_비고": ft_note} if ft_note else {}),
        "지방교육세": _won(edu),
        "농어촌특별세": (_won(rural) if rural else "비과세(전용 85㎡ 이하)"),
        "세금합계": _won(acq + edu + rural),
        "중개보수_법정상한": _won(broker),
        "최대대출": loan_line,
        "안내": "등기비용(법무사·국민주택채권)·이사·인테리어까지 포함한 전체 필요현금은 "
              "아파트매수계산기(/buy-calculator)에서 확인 가능. 취득세는 개인 상황에 따라 달라질 수 있어 참고용.",
    }


def find_villa_stats(region: str = "", trade_type: str = "매매", limit: int = 10) -> dict:
    """빌라(연립·다세대) 실거래와 매물 통계. '○○동 빌라 실거래', '빌라 시세 어때?',
    '빌라 전세 얼마야?' 질문용. 아파트가 아닌 빌라 전용 도구.
    trade_type: 매매|전월세. region 비우면 전국.
    주의: 빌라는 단지 개념이 없어 지번·건물별 개별성이 강함 — 답변에 '개별 물건별 차이가 크다'를 밝힐 것.
    """
    import scripts.local_api as api
    reg = _resolve_region(region) if region else None
    cortar = ""
    if reg:
        cortar = reg.get("dong_cortar") or reg.get("sigungu_code") or reg.get("sido_code") or ""
    tr = "rent" if trade_type in ("전월세", "전세", "월세", "임대") else "sale"

    # 매물(호가) 요약 + 실거래 요약(최근) — 검증된 비단지 엔드포인트 재사용
    st = api.nonresi_stats(cat="villa", cortar=cortar)
    deals = api.nonresi_deals(cat="villa", cortar=cortar, trade=tr, sort="recent",
                              limit=max(1, min(int(limit), 20)))

    def _deal_row(d):
        if tr == "sale":
            return {"계약일": d.get("date"), "동": d.get("umd"), "건물": d.get("building"),
                    "전용㎡": d.get("area_m2"), "층": d.get("floor"),
                    "매매가": _won(d.get("amount")), "건축년도": d.get("build_year")}
        return {"계약일": d.get("date"), "동": d.get("umd"), "건물": d.get("building"),
                "전용㎡": d.get("area_m2"),
                "보증금": _won(d.get("deposit")), "월세": _won(d.get("monthly_rent")),
                "건축년도": d.get("build_year")}

    listings = []
    for b in (st.get("by_trade") or []):
        row = {"거래": b.get("trade"), "매물수": b.get("n"), "평균호가": _won(b.get("avg_price")),
               "평균전용㎡": b.get("avg_area_m2")}
        if b.get("avg_rent"):
            row["평균월세"] = _won(b.get("avg_rent"))
        listings.append(row)

    return {
        "지역": (st.get("region_name")
                 or (" ".join(filter(None, [reg.get("sido"), reg.get("sigungu"), reg.get("dong")])) if reg else "전국")),
        "실거래_최근": [_deal_row(d) for d in (deals.get("deals") or [])],
        "실거래_유형": ("매매(해제거래 제외)" if tr == "sale" else "전월세"),
        "매물_호가요약": listings,
        "주의": "빌라(연립·다세대)는 단지 개념이 없어 같은 동네라도 건물·물건별 가격 차이가 큼. "
              "평균·사례는 참고용이며 개별 물건 확인 필수. 실거래=국토부 신고 기준, 호가=현재 매물 기준.",
    }


def compare_complexes(complex_a: str, complex_b: str, area_a: str = "", area_b: str = "",
                      region_a: str = "", region_b: str = "") -> dict:
    """두 아파트 단지를 나란히 비교 — 개요(준공·세대수), 매매/전세 호가, 전세가율, 갭,
    최근 실거래·6개월 평균·평당가·역대 신고가, 12개월 거래량·회전율, 급매 수, 지하철·학교.
    'A랑 B 비교', 'A vs B 어디가 나아?', '헬리오시티랑 파크리오 중에' 질문용.
    area_a/area_b: 평형명(예 '84A') 지정 시 그 평형 기준(각 단지 독립). 사용자가 '국평끼리',
    '84 기준으로' 같이 평형을 말하면, 먼저 이 도구를 평형 없이 불러 areas 목록을 본 뒤
    전용면적이 조건에 맞는 평형명을 골라 재호출하라.
    """
    import scripts.local_api as api
    ra = _find_complex_row(complex_a, region_a)
    rb = _find_complex_row(complex_b, region_b)
    if not ra or not rb:
        missing = complex_a if not ra else complex_b
        return {"error": f"'{missing}' 단지를 찾지 못했습니다. 지역을 함께 알려주세요."}
    res = api.complex_compare(ra["complex_no"], rb["complex_no"], area_a or "", area_b or "")

    def flat(c):
        l = c.get("listings", {})
        a1, b1, b2 = l.get("A1") or {}, l.get("B1") or {}, l.get("B2") or {}
        tx = c.get("tx", {})
        rec, latest = tx.get("record"), tx.get("latest")
        return {
            "단지": c["name"], "지역": c["region"], "평형기준": c.get("area") or "전체",
            "준공": c.get("built"), "세대수": c.get("households"),
            "매매호가_최저": _won(a1.get("min")), "매매호가_평균": _won(a1.get("avg")),
            "매매매물_광고": a1.get("n"), "매매매물_실": a1.get("units"),
            "전세호가_최저": _won(b1.get("min")), "전세호가_평균": _won(b1.get("avg")),
            "월세평균": _won(b2.get("rent_avg")),
            "전세가율%": c.get("jeonse_rate"), "갭": _won(c.get("gap")),
            "최근실거래": (f"{_won(latest['price'])} ({latest['date']})" if latest else None),
            "실거래6개월평균": _won(tx.get("avg6m")), "평당가": _won(tx.get("pyeong6m")),
            "역대신고가": (f"{_won(rec['price'])} ({rec['date']})" if rec else None),
            "거래량12개월": tx.get("n12"), "연회전율%": tx.get("turnover"),
            "급매수": c.get("quick_deals"),
            "지하철": (f"{c['subway']['station']} 도보 {c['subway']['walk']}분" if c.get("subway") else None),
            "배정초등학교": (f"{c['school']['name']} 도보 {c['school']['walk']}분" if c.get("school") else None),
            "평형목록": [f"{a['name']}(전용{a['excl']}㎡·{a['hh'] or '?'}세대)" for a in c.get("areas", [])[:15]],
        }

    return {
        "A": flat(res["a"]), "B": flat(res["b"]),
        "안내": "사이트의 '맞춤단지 > 단지비교'(/finder/compare)에서 표와 차트로 볼 수 있다고 덧붙여라. "
              "호가와 실거래를 구분해 말하고, 어느 쪽이 '낫다'는 단정 대신 지표별 차이를 짚어라.",
    }


def compare_regions(region_a: str, region_b: str) -> dict:
    """두 지역의 아파트 매매 시장 비교 — 시도/시군구/읍면동 아무 조합(예: '강남구 vs 송파구',
    '대치동이랑 잠실동', '서울 vs 부산'). 90일 거래량·평균가·평당가, 12개월 거래량, 회전율,
    매물(광고/실), 평균 매매·전세 호가, 전세가율을 나란히 준다.
    """
    import scripts.local_api as api
    out = {}
    for key, rq in (("A", region_a), ("B", region_b)):
        reg = _resolve_region(rq)
        if not reg:
            return {"error": f"'{rq}' 지역을 찾지 못했습니다."}
        code = reg.get("dong_cortar") or reg.get("sigungu_code") or reg.get("sido_code")
        out[key] = {"code": code, "reg": reg}
    res = api.region_compare2(out["A"]["code"], out["B"]["code"])

    def flat(r):
        l = r.get("listings", {})
        a1, b1 = l.get("A1") or {}, l.get("B1") or {}
        return {
            "지역": r["name"], "단지수": r.get("complexes"), "세대수": r.get("households"),
            "거래량90일": r["tx90"].get("n"), "평균거래가90일": _won(r["tx90"].get("avg")),
            "평당가": _won(r["tx90"].get("pyeong")), "거래량12개월": r.get("n12"),
            "연회전율%": r.get("turnover"),
            "매물_광고": a1.get("n"), "매물_실": a1.get("units"),
            "세대대비매물%": r.get("listing_per_hh"),
            "평균매매호가": _won(a1.get("avg")), "평균전세호가": _won(b1.get("avg")),
            "전세가율%": r.get("jeonse_rate"),
        }

    return {"A": flat(res["a"]), "B": flat(res["b"]),
            "안내": "사이트 '맞춤단지 > 지역비교'(/finder/region-compare)에서 12개월 차트로 볼 수 있다고 덧붙여라. "
                  "호가 기준 지표와 실거래 기준 지표를 구분해 말하라."}


def get_complex_listing_trend(complex_name: str, region: str = "", days: int = 31) -> dict:
    """단지의 현재 매물 개수와 추세(일자별, 최근 1달) — 광고매물수·실매물수(중복 광고 합침)·
    평균 매매호가의 현재값과 변화. '이 단지 매물 몇 개야?', '실매물/진짜 매물 몇 개?',
    '매물 늘고 있어?', '호가 오르는 중이야?', '매물 잠기고 있어?' 질문용.
    (특정 단지의 매물수는 get_listing_stats(지역 전체)가 아니라 반드시 이 도구로.)
    """
    import scripts.local_api as api
    cx = _find_complex_row(complex_name, region)
    if not cx:
        return {"error": f"'{complex_name}' 단지를 찾지 못했습니다. 지역을 함께 알려주세요."}
    res = api.complex_listing_daily(cx["complex_no"], days=min(max(days, 7), 92))
    byday = {}
    for r in res.get("rows", []):
        if r["t"] != "A1":
            continue
        e = byday.setdefault(r["d"], {"n": 0, "u": 0, "ps": 0, "pw": 0})
        e["n"] += r["n"]
        if r["u"] is not None:
            e["u"] += r["u"]
        if r["avg"] is not None and r["n"] > 0:
            e["ps"] += r["avg"] * r["n"]
            e["pw"] += r["n"]
    if not byday:
        return {"단지": cx["complex_name"], "결과": "최근 매매 매물 데이터가 없습니다."}
    ds = sorted(byday)
    f, l = byday[ds[0]], byday[ds[-1]]
    favg = f["ps"] / f["pw"] if f["pw"] else None
    lavg = l["ps"] / l["pw"] if l["pw"] else None
    return {
        "단지": cx["complex_name"],
        "현재_광고매물": l["n"], "현재_실매물": l["u"],
        "기간": f"{ds[0]} ~ {ds[-1]}",
        "광고매물": f"{f['n']}건 → {l['n']}건 ({l['n']-f['n']:+d})",
        "실매물": f"{f['u']}건 → {l['u']}건 ({l['u']-f['u']:+d})",
        "평균매매호가": (f"{_won(favg)} → {_won(lavg)}"
                    + (f" ({(lavg-favg)/favg*100:+.1f}%)" if favg and lavg else "")),
        "해석힌트": "매물이 뚜렷이 줄며 호가가 오르면 '매물 잠김(매도 보류)' 신호. 반대는 매물 적체. "
                "단지 상세의 '매물분석' 탭에서 일자별 차트를 볼 수 있다고 안내하라.",
    }


def get_policy_timeline(keyword: str = "", year: int = 0) -> dict:
    """부동산 정책·규제·거시사건 연대기(2003~현재)와 당시 전국 시장 반응(2006년~ 월별
    거래량·평균가). '8·2 대책이 뭐야', '임대차법 언제 시행됐어', '2008년 시장 어땠어',
    '금융위기 때 거래량', '역대 규제 정리' 질문용.
    keyword: 대책·사건 이름 일부(예 '임대차', '8·2', '금리'). year: 특정 연도의 월별 시장.
    둘 다 비우면 최근 이벤트 8개.
    """
    import scripts.local_api as api
    tm = api.timemachine()
    events, series = tm["events"], tm["series"]
    by_m = {p["m"]: p for p in series}

    def with_market(e):
        m = e["d"][:7]
        pt = by_m.get(m)
        out = {"발표일": e["d"], "구분": e["cat"], "이름": e["title"], "내용": e["desc"], "출처": e["src"]}
        if pt:
            out["당월_전국거래량"] = pt["n"]
            out["당월_평균가"] = _won(pt["avg"])
        return out

    kw = (keyword or "").strip()
    if kw:
        # '8·2'/'8.2'/'82' 같은 대책명은 구분자 제거 후 통짜 매칭(토큰 분리하면 8·31에 오매칭)
        def _norm(x):
            return re.sub(r"[\s·.\-]", "", x)
        # 규제 개념 동의어 정규화 — 축약·별칭을 이벤트 원문 표현으로
        _alias = {"토허제": "토지거래허가", "토허구역": "토지거래허가", "토허": "토지거래허가",
                  "ltz": "토지거래허가", "임대차법": "임대차", "임대차2법": "임대차",
                  "종부세": "종부", "취득세중과": "취득세", "대출규제": "대출"}
        kw2 = kw
        for a, b in _alias.items():
            if a in kw2.lower():
                kw2 = b
                break
        nk = _norm(kw2)
        # '8.2 대책'처럼 일반어가 붙으면 떼고 한 번 더 (대책/정책/규제/부동산은 제목마다 있는 말)
        nk2 = re.sub(r"(대책|정책|규제|부동산|발표)", "", nk)
        hit = ([e for e in events if nk and nk in _norm(e["title"])]
               or [e for e in events if nk and nk in _norm(e["title"] + e["desc"] + e["d"])]
               or [e for e in events if nk2 and nk2 in _norm(e["title"] + e["desc"])])
        if not hit:
            return {"결과": f"'{keyword}'에 해당하는 이벤트를 찾지 못했습니다.",
                    "전체이벤트수": len(events)}
        return {"이벤트": [with_market(e) for e in hit[:6]],
                "안내": "발표일 기준·공식 발표만 수록. '실거래 > 부동산타임머신'(/tx-stats/timemachine)에서 "
                      "차트와 전체 연대기를 볼 수 있다고 안내하라."}
    if year:
        ys = [p for p in series if p["m"].startswith(str(year))]
        yev = [e for e in events if e["d"].startswith(str(year))]
        if not ys and not yev:
            return {"결과": f"{year}년 데이터가 없습니다(시장 데이터는 2006년부터)."}
        return {"연도": year,
                "월별": [{"월": p["m"], "거래량": p["n"], "평균가": _won(p["avg"])} for p in ys],
                "그해이벤트": [with_market(e) for e in yev],
                "안내": "거래량은 국토부 실거래 신고(해제 제외) 기준."}
    return {"최근이벤트": [with_market(e) for e in events[-8:]],
            "안내": "'실거래 > 부동산타임머신'에서 20년 연대기 전체를 볼 수 있다."}


_TOOLS = [find_quick_deals, find_apartments, find_cancelled_transactions,
          get_complex_info, find_record_high, region_market_pulse,
          find_realtor, rank_complexes, rank_realtors, find_presale,
          get_listing_stats, find_price_movers, calc_purchase_cost, find_villa_stats,
          compare_complexes, compare_regions, get_complex_listing_trend, get_policy_timeline]


# ---------------------------------------------------------------------------
# LLM 호출 (교체 가능 지점)
# ---------------------------------------------------------------------------
_client = None


def _genai():
    global _client
    if _client is None:
        from dotenv import load_dotenv
        load_dotenv()
        from google import genai
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY 미설정 (.env 확인)")
        _client = genai.Client(api_key=key)
    return _client


def _latest_tx_ymd() -> str | None:
    """실거래 롤업의 가장 최근 신고일(YYYY-MM-DD)."""
    try:
        with sqlite3.connect(DB_PATH) as c:
            row = c.execute("SELECT MAX(deal_ymd) FROM tx_avg_rollup").fetchone()
        return row[0] if row and row[0] else None
    except Exception:  # noqa: BLE001
        return None


@lru_cache(maxsize=2)
def _freshness_note(day: str) -> str:
    """오늘 날짜 + 최신 실거래일 주입. 학습시점 기반 '과거까지만' 추정 차단.
    day 인자(KST 날짜)로 캐시 → 하루 1회만 DB 조회."""
    latest = _latest_tx_ymd()
    latest_txt = f" 현재 데이터에 있는 가장 최근 실거래 신고일은 {latest}이다." if latest else ""
    return (
        f"\n\n[데이터 신선도 — 매우 중요] 오늘은 {day}(한국시간)이며, 콕집의 매물·실거래 데이터는 "
        f"매일 자동 갱신되어 오늘 기준 최신이다.{latest_txt} 너의 학습 시점과 무관하게, 실거래가·시세·"
        "매물은 반드시 도구가 돌려주는 최신 데이터로만 답하라. '2024년까지만 있다'처럼 특정 과거 연·월을 "
        "데이터의 한계로 단정하는 추정 답변을 절대 하지 마라. 실거래 데이터가 언제까지 있냐고 물으면 "
        "위 최근 신고일을 근거로 '최근까지 최신'이라고 답한다."
    )


def _system_for(nickname: str | None, user_region: str | None = None) -> str:
    """닉네임·접속지역이 있으면 규칙을 덧붙인 시스템 프롬프트. + 데이터 신선도 주입."""
    import datetime as _dt
    day = (_dt.datetime.utcnow() + _dt.timedelta(hours=9)).strftime("%Y-%m-%d")
    from scripts.ai_ontology import ONTOLOGY_PROMPT
    base = SYSTEM_PROMPT + ONTOLOGY_PROMPT + _freshness_note(day)
    if user_region:
        base += (f"\n\n[접속 위치] 이 사용자의 접속 위치 추정은 '{user_region}'다. "
                 f"질문에 지역이 없으면 되묻지 말고 region='{user_region}' 인자로 **반드시 도구를 호출한 뒤 "
                 "그 도구 결과로만** 답하라. 접속 위치를 안다고 해서 도구 없이 시세·매물수 등 숫자를 말하는 것은 "
                 "여전히 절대 금지다(규칙 1.5 그대로 적용). 답변에는 반드시 "
                 f"\"접속 위치({user_region}) 기준\"이라고 밝히고, 끝에 '다른 지역을 원하시면 "
                 "지역명을 말씀해 주세요'를 한 줄 덧붙여라(IP 추정이라 틀릴 수 있음). "
                 "사용자가 지역을 말했으면 이 추정은 무시하고 말한 지역을 쓴다.")
    if not nickname:
        return base
    return (base +
            f"\n\n[호칭] 사용자의 닉네임은 '{nickname}'이다. 답변 첫 문장에서 '{nickname}님,' 으로 "
            "한 번 친근하게 부르고 시작해라. 매 문장마다 반복하지는 마라.")


def _fix_links(text: str) -> str:
    """모델이 가끔 '이름 [/path]' 같은 비표준 형식으로 링크를 내보냄 → 표준 마크다운 [이름](/path)로
    정규화해 프런트에서 클릭되게 한다. 이미 올바른 [텍스트](url)는 건드리지 않는다."""
    if not text:
        return text
    out = []
    for ln in text.split("\n"):
        # '라벨 [/path]' (한 줄에 라벨+경로브래킷, 이미 마크다운 링크가 아닌 경우)
        if "](" not in ln:
            m = re.match(r'^(\s*(?:[-•*]\s*)?)(.+?)\s*\[(/[^\]\s]+)\]\s*$', ln)
            if m:
                ln = f"{m.group(1)}[{m.group(2).strip()}]({m.group(3)})"
        out.append(ln)
    text = "\n".join(out)
    # 라벨 없이 떠도는 인라인 '[/path]' → 클릭 가능하게
    text = re.sub(r'(?<!\])\[(/[^\]\s]+)\](?!\()', r'[\1](\1)', text)
    return text


_ASKBACK_RE = re.compile(
    r"(어느 지역|어떤 지역|지역을 말씀|지역을 알려|지역이 필요|알려주시면|"
    r"어떤 평형|평형대를 원|원하시나요\?|필요하신가요\?)")


def _askback_nudge(user_region):
    reg = user_region or "전국(region='')"
    return ("(시스템 지시: 방금 답은 되묻기라 규칙 위반이다. 되묻지 말고 지역이 없으면 "
            f"'{reg}' 기준, 평형·가격대는 전체 기본값으로 지금 즉시 도구를 호출해 "
            "그 결과로 답하라. 결과를 준 뒤 '지역을 좁히면 더 정확해요' 한 줄만 덧붙여라.)")


def _is_blank_response(resp) -> bool:
    """모델이 텍스트도 도구호출도 없이 빈 응답을 준 경우(일시 glitch). 안전차단은 제외(재시도 무의미)."""
    if resp is None:
        return True
    try:
        if (resp.text or "").strip():
            return False
    except Exception:  # noqa: BLE001
        pass  # text 추출 실패(멀티파트/함수콜) → 아래에서 도구이력 확인
    if getattr(resp, "automatic_function_calling_history", None):
        return False
    try:
        fr = str(getattr(resp.candidates[0], "finish_reason", "") or "").upper()
        if any(x in fr for x in ("SAFETY", "BLOCK", "RECITATION")):
            return False  # 안전차단은 재시도해도 동일
    except Exception:  # noqa: BLE001
        pass
    return True


def _safe_text(resp) -> str:
    """모델 응답 텍스트를 안전하게 추출. 빈 응답(안전필터·빈 생성)이면 안내 문구로 폴백
    → 프런트에 빈 답('무응답')이 나가지 않게 한다."""
    try:
        t = (resp.text or "").strip()
    except Exception:  # noqa: BLE001
        t = ""
    if t:
        return t
    fr = ""
    try:
        if resp.candidates:
            fr = str(getattr(resp.candidates[0], "finish_reason", "") or "")
    except Exception:  # noqa: BLE001
        fr = ""
    if "SAFETY" in fr.upper() or "BLOCK" in fr.upper() or "RECITATION" in fr.upper():
        return "이 질문에는 답변하기 어려워요. 부동산 매물·실거래·중개사 관련으로 다시 물어봐 주세요."
    return ("질문을 이해하지 못했어요. 지역·평형·가격대 등을 넣어 조금 더 구체적으로 물어봐 주세요. "
            "(예: '강남구 30평대 매매 급매', '서울 6월 거래량')")


def run_agent(question: str, history: list | None = None, nickname: str | None = None,
              thinking_budget: int = 0, user_region: str | None = None) -> dict:
    """질문 → 답변. 도구 호출 추적·토큰 사용량 포함.

    history: 이전 대화 [{role:'user'|'model', text:str}, ...] (멀티턴 맥락).
    '거기서 30평대만', '그 단지 전세는?' 같은 후속 질문을 위해 직전 턴들을 함께 보낸다.
    nickname: 있으면 '***님' 으로 호칭.
    thinking_budget: 0=사고끔(기본,빠름) / -1=동적 / N=고정. A/B 검증용 노출.
    """
    from google.genai import types
    client = _genai()
    cfg = types.GenerateContentConfig(
        system_instruction=_system_for(nickname, user_region),
        tools=_TOOLS,
        temperature=0.2,
        # thinking 기본 OFF(budget=0) — 데이터 조회/요약엔 불필요, 응답 6.6s→1.4s.
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6),
    )
    contents = []
    for h in (history or [])[-6:]:                # 최근 6턴만(토큰 절약)
        txt = (h.get("text") or "").strip()
        if not txt:
            continue
        role = "model" if h.get("role") == "model" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=txt)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))
    # 일시 과부하(503)·쿼터(429)는 짧게 재시도 — 답변 누락 방지.
    resp = None
    for _attempt in range(3):
        try:
            resp = client.models.generate_content(model=MODEL, contents=contents, config=cfg)
        except Exception as e:  # noqa: BLE001
            code = getattr(e, "code", None) or 0
            msg = str(e)
            transient = code in (429, 503) or "UNAVAILABLE" in msg or "overloaded" in msg or "RESOURCE_EXHAUSTED" in msg
            if transient and _attempt < 2:
                time.sleep(1.2 * (_attempt + 1))
                continue
            raise
        # 빈 응답(텍스트·도구호출 둘 다 없음, 안전차단 아님)도 일시 glitch → 재시도.
        # '질문을 이해하지 못했어요' 폴백이 정상 질문에 뜨던 원인(모델 빈 생성) 보완.
        if _attempt < 2 and _is_blank_response(resp):
            time.sleep(1.0 * (_attempt + 1))
            continue
        break

    # 도구는 실행됐는데 최종 텍스트가 빈 경우(finish=STOP·parts=[] 글리치, thinking=0에서 간헐 발생)
    # → thinking 을 동적으로 켜고 1회 재생성. 도구 결과 기반이라 정확성 동일, 폴백 문구 방지.
    def _txt(r):
        try:
            return (r.text or "").strip()
        except Exception:  # noqa: BLE001
            return ""
    if resp is not None and not _txt(resp) and (resp.automatic_function_calling_history or []):
        try:
            cfg2 = types.GenerateContentConfig(
                system_instruction=_system_for(nickname, user_region), tools=_TOOLS, temperature=0.2,
                thinking_config=types.ThinkingConfig(thinking_budget=-1),
                automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6),
            )
            resp2 = client.models.generate_content(model=MODEL, contents=contents, config=cfg2)
            if _txt(resp2):
                resp = resp2
        except Exception:  # noqa: BLE001
            pass

    # 어떤 도구를 어떤 인자로 호출했는지 추적
    trace = []
    for content in (resp.automatic_function_calling_history or []):
        for part in (content.parts or []):
            fc = getattr(part, "function_call", None)
            if fc:
                trace.append({"tool": fc.name, "args": dict(fc.args or {})})
    um = resp.usage_metadata
    usage = {
        "input_tokens": getattr(um, "prompt_token_count", None),
        "output_tokens": getattr(um, "candidates_token_count", None),
        "thinking_tokens": getattr(um, "thoughts_token_count", None),
        "total_tokens": getattr(um, "total_token_count", None),
    } if um else {}

    # 되묻기 백스톱 — 도구를 안 부르고 되묻기만 한 경우 1회 강제 재시도(기본값 실행 지시)
    try:
        _t0 = (resp.text or "").strip()
    except Exception:  # noqa: BLE001
        _t0 = ""
    if _t0 and not (resp.automatic_function_calling_history or []) and _ASKBACK_RE.search(_t0):
        try:
            retry_contents = contents + [
                types.Content(role="model", parts=[types.Part.from_text(text=_t0)]),
                types.Content(role="user", parts=[types.Part.from_text(text=_askback_nudge(user_region))]),
            ]
            resp3 = client.models.generate_content(model=MODEL, contents=retry_contents, config=cfg)
            _t3 = ""
            try:
                _t3 = (resp3.text or "").strip()
            except Exception:  # noqa: BLE001
                pass
            if _t3 and not _ASKBACK_RE.search(_t3):
                resp = resp3
                trace = []
                for content in (resp.automatic_function_calling_history or []):
                    for part in (content.parts or []):
                        fc = getattr(part, "function_call", None)
                        if fc:
                            trace.append({"tool": fc.name, "args": dict(fc.args or {})})
        except Exception:  # noqa: BLE001
            pass

    answer = _fix_links(_safe_text(resp))
    # 안전망: 모델이 가끔 영어 거절문을 내뱉음 → 한국어로 치환(고객 노출 방지).
    if answer and ("I'm sorry" in answer or "I cannot" in answer or "I am sorry" in answer
                   or "cannot fulfill" in answer or "unable to" in answer):
        answer = ("죄송해요, 그 조건으로는 바로 답하기 어려워요. 질문을 조금 바꿔서 다시 물어봐 주세요. "
                  "(예: '강남구 거래량 많은 단지', '직원 많은 부동산', '은마아파트 시세')")
    return {"answer": answer, "tools_used": trace, "usage": usage, "model": MODEL}


_TOOL_LABEL = {
    "find_quick_deals": "급매 검색",
    "find_apartments": "매물 검색(가격대·평형)",
    "find_cancelled_transactions": "취소거래 조회",
    "get_complex_info": "단지 정보 조회",
    "find_record_high": "신고가 조회",
    "region_market_pulse": "거래 분위기 조회",
    "find_realtor": "중개사무소 조회",
    "rank_complexes": "전국 순위 조회",
    "rank_realtors": "중개사무소 순위 조회",
    "find_presale": "분양권 전매 조회",
    "get_listing_stats": "매물 시장 통계 조회",
    "find_price_movers": "호가 상승·하락 단지 조회",
    "calc_purchase_cost": "매수 비용 계산",
    "find_villa_stats": "빌라 실거래·시세 조회",
}


def run_agent_stream(question: str, history: list | None = None, nickname: str | None = None,
                     user_region: str | None = None):
    """run_agent 의 스트리밍 버전. 진행 단계를 이벤트로 yield 한다.
    이벤트: {type:'status', stage, label} ... 마지막에 {type:'done', answer, tools_used, usage}.
    자동 함수호출 대신 수동 루프로 돌려 단계마다 진행상황을 흘려보낸다."""
    from google.genai import types
    client = _genai()
    cfg = types.GenerateContentConfig(
        system_instruction=_system_for(nickname, user_region), tools=_TOOLS, temperature=0.2,
        # thinking OFF — 스트리밍 수동 루프도 단계마다 추론지연 없애 응답 가속.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    tmap = {f.__name__: f for f in _TOOLS}
    contents = []
    for h in (history or [])[-6:]:
        txt = (h.get("text") or "").strip()
        if txt:
            role = "model" if h.get("role") == "model" else "user"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=txt)]))
    contents.append(types.Content(role="user", parts=[types.Part.from_text(text=question)]))

    trace, in_tok, out_tok = [], 0, 0
    _nudged = False
    yield {"type": "status", "stage": "analyze", "label": "질문 분석 중…"}
    for _step in range(6):
        resp = client.models.generate_content(model=MODEL, contents=contents, config=cfg)
        um = resp.usage_metadata
        if um:
            in_tok += (um.prompt_token_count or 0)
            out_tok += (um.candidates_token_count or 0)
        fcs = resp.function_calls
        if not fcs:
            # 도구 실행 후 빈 최종 턴(STOP·parts=[] 글리치) → thinking 켜고 1회 재생성
            try:
                _t = (resp.text or "").strip()
            except Exception:  # noqa: BLE001
                _t = ""
            # 되묻기 백스톱 — 도구 0회 + 되묻기면 지시문 넣고 루프 계속(1회만)
            if _t and not trace and not _nudged and _ASKBACK_RE.search(_t):
                _nudged = True
                contents.append(resp.candidates[0].content)
                contents.append(types.Content(role="user",
                                parts=[types.Part.from_text(text=_askback_nudge(user_region))]))
                continue
            if not _t and trace:
                cfg2 = types.GenerateContentConfig(
                    system_instruction=_system_for(nickname, user_region), tools=_TOOLS, temperature=0.2,
                    thinking_config=types.ThinkingConfig(thinking_budget=-1),
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                )
                try:
                    resp2 = client.models.generate_content(model=MODEL, contents=contents, config=cfg2)
                    if (resp2.text or "").strip() and not resp2.function_calls:
                        resp = resp2
                        um2 = resp2.usage_metadata
                        if um2:
                            in_tok += (um2.prompt_token_count or 0)
                            out_tok += (um2.candidates_token_count or 0)
                except Exception:  # noqa: BLE001
                    pass
            yield {"type": "done", "answer": _fix_links(_safe_text(resp)), "tools_used": trace,
                   "usage": {"input_tokens": in_tok, "output_tokens": out_tok,
                             "total_tokens": in_tok + out_tok}, "model": MODEL}
            return
        contents.append(resp.candidates[0].content)   # function_call 한 모델 턴
        parts = []
        for fc in fcs:
            args = dict(fc.args or {})
            trace.append({"tool": fc.name, "args": args})
            yield {"type": "status", "stage": "fetch",
                   "label": f"{_TOOL_LABEL.get(fc.name, '데이터 조회')} 중…"}
            try:
                result = tmap[fc.name](**args)
            except Exception as e:
                result = {"error": str(e)}
            yield {"type": "status", "stage": "organize", "label": "데이터 정리 중…"}
            parts.append(types.Part.from_function_response(name=fc.name, response={"result": result}))
        contents.append(types.Content(role="user", parts=parts))
        yield {"type": "status", "stage": "compose", "label": "답변 작성 중…"}

    yield {"type": "done", "answer": "(처리 단계를 초과했습니다. 질문을 더 구체적으로 해주세요.)",
           "tools_used": trace, "usage": {"total_tokens": in_tok + out_tok}, "model": MODEL}
