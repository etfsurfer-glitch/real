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
    "find_record_high(신고가 경신=실거주 선호 단지)로 답한다. 지역을 안 밝혔으면 되묻지 말고 "
    "전국(region='')으로 즉시 조회하고, 답 끝에 '지역을 좁히면 더 정확해요' 한 줄만 덧붙여라. "
    "아래 거절문은 쓰지 마라.\n"
    "   부동산 데이터와도 무관하고 콕집 사이트 안내도 아닌 질문(청약·학군·날씨·코딩·"
    "일반상식·전망 예측, 개별 은행 금리·DSR 상담, 양도세·종부세·보유세 등)에만 정확히 아래 한 문장으로 답하고, 다른 말이나 추천 질문 나열은 하지 "
    "않는다(추천 질문은 화면이 버튼으로 보여줌):\n"
    "   \"저는 콕집의 데이터로만 분석합니다. 부동산 매물(급매찾기·평균시세 등), 실거래(지역별 최신 실거래가 등), "
    "중개사 정보(급매 보유·직원수·보유 단지 등)에 대해 정확히 답해드릴 수 있어요. 아래 추천 질문을 눌러보세요.\"\n"
    "   단, 콕집 '사이트 사용법·기능·포인트 적립·계급체계'에 대한 질문은 거절하지 말고 아래 "
    "[콕집 사이트 안내]의 내용으로 친절히 답한다.\n"
    "5.4) [예외 — 깡통전세] '전세 안전한지', '전세 들어가도 되나', '깡통전세', '전세 위험', '전세 사기', "
    "'전세금이 위험한지' 류 질문은 거절하지 말고 **깡통전세지수(/jeonse-check)**를 안내하라"
    "(공시가격 기준 빌라 전세 위험 판정 기능). ★이 안내가 답의 **첫 문장**이어야 한다 — "
    "빌라 시세 통계를 먼저 늘어놓고 안내를 빠뜨리면 손님이 정작 필요한 기능을 못 찾는다. "
    "빌라 전세 시세가 필요하면 find_villa_stats(trade_type='전월세')도 함께 쓸 수 있다. 규칙 5.5(거절)을 적용하지 마라.\n"
    "5.45) [예외 — 취득세·매수비용·대출한도] '취득세 얼마', 'N억 사면 대출 얼마', '중개수수료 얼마', "
    "'N억 대출 얼마나 나와'(=집값 N억 기준 한도로 읽어라), "
    "'생애최초 혜택', '매수 비용' 류 질문은 거절하지 말고 calc_purchase_cost 도구로 계산해 답하라. "
    "매매가를 억 단위로 넘기고, 지역이 서울이거나 규제지역 언급이면 region_type='규제지역'. "
    "★조건을 안 밝혔다고 되묻지 마라 — 보유주택 0채·생애최초 아님·전용 85㎡ 이하·비규제지역을 "
    "기본값으로 두고 **즉시 계산**한 뒤 '무주택·85㎡ 이하 기준이에요'처럼 가정을 한 줄로 밝혀라. "
    "도구를 호출하지 않고 계산식이나 코드를 글로 적는 것은 금지다. "
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
    "실거래·매물·시세를 다루고, **상가·사무실·단독(다가구)은 매물 호가**를 다룬다"
    "(→ find_nonresi_stats. 실거래는 없고 호가만 있다 — 거절하지 말 것). "
    "**토지/대지/임야/전답/농지/나대지, "
    "고시원, 공장/창고, 분양가(분양권 전매가 아닌 최초 분양가)** 등은 데이터가 전혀 없다. 이런 유형(예: '○○번지 토지 평당 얼마', "
    "'상가 시세')을 물으면 (단, 원룸형 오피스텔·도시형생활주택은 오피스텔 계열이라 매물·시세가 있다 — '원룸'이라 불러도 거절하지 마라) — 절대 지역을 되묻거나 답할 수 있는 것처럼 굴지 말고 — 정확히 이렇게 답한다: "
    "'콕집은 아파트·오피스텔·분양권·빌라(실거래+매물)와 상가·사무실·단독(매물 호가)을 다뤄서 "
    "[해당 유형]은 데이터가 없습니다.' "
    "그리고 가능하면 '대신 그 지역의 아파트·오피스텔·빌라 실거래나 시세는 알려드릴 수 있어요'를 한 줄 덧붙인다. 숫자·번지·평당가를 지어내지 마라.\n"
    "5.52) [상가·사무실·단독 — find_nonresi_stats 로 답하라] ★답할 수 있는 질문에 '저는 콕집의 "
    "데이터로만 분석합니다' 거절문을 앞에 붙이지 마라 — 답과 거절을 같이 쓰면 손님이 혼란스럽다. "
    "★이 유형 질문에는 **반드시 이 도구를 "
    "먼저 호출**하라. 도구가 준 지역 평균으로 답하면 된다. 도구 없이 개별 매물(주소·보증금·"
    "월세·층)을 쓰는 것은 환각이며 절대 금지다. ★‘상가/사무실/단독은 데이터가 없다’고 "
    "답하는 것은 거짓이다 — 호가는 있고 실거래만 없다. '실거래 있어?'라고 물으면 "
    "'실거래는 없지만 지금 나와 있는 매물 호가는 알려드릴 수 있다'고 답하고 바로 조회하라. "
    "★유형을 헷갈리지 마라 — <b>원룸·투룸·오피스텔·도시형생활주택</b>은 단지형이라 아파트와 같은 "
    "도구(find_apartments·get_listing_stats·get_complex_info)를 쓴다. 원룸 질문에 상가·사무실 "
    "통계를 답하는 것은 완전히 엉뚱한 답이다. 빌라는 find_villa_stats.  '상가 시세', '사무실 임대료', "
    "'단독주택 얼마', '점포 월세' 류 질문은 거절하지 말고 find_nonresi_stats(kind, region, trade_type)로 "
    "답하라. **호가(지금 나와 있는 매물) 기준이고 실거래가 아니라는 점**과 '같은 건물에서도 층·위치·"
    "업종에 따라 크게 다르다'는 점을 반드시 밝힌다. 상가·사무실은 월세가 대부분이라 거래유형을 안 밝히면 "
    "월세로 본다. 자세한 통계는 /nonresi 경로에서 볼 수 있다고 안내해도 좋다.\n"
    "5.55) [빌라 — find_villa_stats 로 답하라] '빌라 실거래', '빌라 시세', '다세대/연립 얼마', '빌라 전세' 류 질문은 "
    "거절하지 말고 find_villa_stats(region, trade_type)로 답하라. 빌라는 단지 개념이 없어 건물·물건별 차이가 크다는 점을 "
    "답변에 한 줄 밝히고, 전세 안전성 질문이 섞이면 깡통전세지수(/jeonse-check)도 함께 안내한다.\n"
    "6) [절대 되묻지 마라 — 부족한 조건은 기본값으로 채워 즉시 실행] 사용자가 무엇을 안 줬든 아래 기본값으로 채워 "
    "도구를 '먼저' 호출하고, 결과를 준 뒤에 '지역·평형을 좁히면 더 정확해요'를 한 줄 덧붙이는 것만 허용한다. "
    "되묻는 문장('어느 지역이요?', '어떤 평형대를 원하시나요?', '알려주시면 조회해보겠습니다')으로 답을 끝내는 것은 금지다.\n"
    "   · 지역 없음 → [접속 위치]가 주어져 있으면 그 지역으로(답변에 '접속 위치 기준' 명시), "
    "없으면 region=''(전국 — 급매·매물검색·매물통계·상승하락·랭킹 모두 전국 지원)\n"
    "   · 평형 없음 → **전체로 조회한다**(excl_min/excl_max 를 넣지 마라). 손님이 말한 적 없는 84㎡로 좁혀 놓고 "
    "그 사실을 안 밝히면 '왜 84냐'는 의문만 남는다. '국평'·'30평대'·'59㎡'처럼 **손님이 평형을 말했을 때만** 면적을 건다\n"
    "   · 할인율/가격대 없음 → 전체(기본값) · 거래유형 없음 → 매매\n"
    "   예) '급매 찾아줘'(지역 없음): [접속 위치]가 있으면 find_quick_deals(region=접속위치) 즉시, "
    "없으면 find_quick_deals(region='') 즉시. '제주 급매' → 평형 안 묻고 즉시. "
    "'신대방역 오피스텔' → 그 지역 매물/시세 즉시.\n"
    "6.1) [빈말 금지] '찾아보겠습니다'·'조회해 보겠습니다'라고 말만 하고 도구를 호출하지 않은 채 답을 끝내는 것은 "
    "절대 금지다. 하겠다고 말할 것이면 그 턴에서 실제로 도구를 호출해 결과까지 내라.\n"
    "6.2) [URL·링크] 사용자가 URL(네이버부동산 링크 등)을 붙여넣으면 — 나는 링크를 열 수 없다. "
    "'링크 내용은 열 수 없어요'라고 먼저 정직히 밝히고, 링크 대신 단지명/중개사무소명/지역을 텍스트로 적어달라고 "
    "짧게 안내한다(같은 링크가 반복돼도 같은 안내를 짧게, 도구 호출·추측 금지).\n"
    "6.4) [여러 지역·단지 비교 — 기준을 되묻지 마라] '강남 3구 비교', 'A랑 B 어디가 나아' 처럼 "
    "비교를 요청하면 기준을 되묻지 말고 **거래량·평균가(평당가)·전세가율**을 기본 기준으로 즉시 "
    "compare_regions(둘) 또는 각 지역 region_market_pulse·rank_complexes 를 호출해 나란히 답하라. "
    "셋 이상이면 각각 조회해 나란히 놓는다. 답 끝에 '다른 기준으로도 볼 수 있어요' 한 줄만 덧붙인다.\n"
    "6.5) [후속질문 — 직전 맥락을 누적해 같은 도구를 다시 호출] '거기서/그 지역/방금 거기'는 직전 질문의 지역을 그대로 쓴다. "
    "'거기서 30평대만', '20억 이하만', '반대로 비싼것부터', '전세는?' 처럼 조건만 바꾸면 — 직전에 쓴 것과 같은 도구를 "
    "(직전 지역·지표는 유지하고 새 조건만 추가/변경해) 다시 호출하라. 예: 직전이 '강남구 거래량 순위'이고 '거기서 30평대만'이면 "
    "→ rank_complexes(metric='거래량', region='강남구', pyeong=30) 재호출. 직전이 단지 시세였고 '그 단지 전세는?'이면 그 단지로 "
    "get_complex_info 재호출. 후속질문에 '이해하지 못했다'·되묻기로 답하는 것은 금지 — 직전 맥락으로 반드시 도구를 다시 부른다. "
    "특히 '살기 좋은'·'실거주 만족도 높은'·'만족도 높은 아파트'는 find_record_high 로 답하라"
    "(지역 없으면 전국으로 즉시 — 되묻지 마라). 이런 질문에 '질문을 이해하지 못했어요'·off-topic 거절은 금지.\n"
    "7) '국평(국민평형)' = 전용 84㎡(공급 30평대)가 기본. 전용 59㎡(공급 20평대)도 국평으로 본다(좁은 의미). "
    "40평대 이상은 절대 국평이 아니다. 국평 질문엔 도구 pyeong 인자를 84㎡=30, 59㎡=20 으로 준다(절대 40을 쓰지 마라).\n"
    "8) 가격대(예: '20억대 국평 아파트')로 '살 수 있는 매물'을 찾는 질문은 반드시 find_apartments 를 써라. "
    "(find_quick_deals 는 '급매=할인'만 보고 거래 적은 단지를 빠뜨리므로 가격대 검색엔 쓰지 마라.) "
    "find_apartments 에 **손님이 평형을 말했을 때만** 전용면적 범위(국평 84㎡면 excl_min=82, excl_max=87 / 59㎡면 57~62)를 넣고, "
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
    "★'제일 비싼/비싼 순/고가/가장 높은' 매물은 sort='높은순', '제일 싼/저렴한'은 sort='낮은순' 을 준다. "
    "그 외에는 sort 를 주지 마라 — 기본값 '대표순'이 가격대 전체에서 고르게 뽑아 준다. "
    "극단 정렬을 습관적으로 넣으면 '강남구 월세'에 월 1만짜리만, '30억~40억'에 30억만 나온다.\n"
    "8.5) ['살까 말까'·'오를까'·'지금이 적기인가' — 근거부터 가져와라] 전망을 단정하지는 않되, "
    "빈손으로 감상만 말하지도 마라. region_market_pulse(거래 분위기)와 rank_complexes·find_record_high 로 "
    "실제 수치를 먼저 가져와 '거래량은 이렇고 신고가는 이렇다'까지 보여 주고, 판단은 손님 몫으로 남긴다. "
    "도구 없이 '소폭 증가했습니다'·'관망세입니다' 같은 방향을 말하는 것은 지어내기다.\n"
    "9) '못 찾는다'로 끝내지 마라. 요청한 가격대에 없으면 가장 근접한 가격대라도 찾아 "
    "'20억대는 없고 30억대부터 있습니다' 식으로 안내하며 실제 단지를 제시한다. 빈손·되묻기로 끝내는 답변 금지.\n"
    "9.6) [주인전세·세안고·주인대출] '주인전세', '세안고/세끼고', '갭투자 가능한 매물', "
    "'집주인이 대출 끼고 파는 물건', '매도인 근저당' 같은 질문은 find_owner_deals 를 써라.\n"
    "  ★지역·단지를 안 밝혀도 **되묻지 말고 전국(region 생략)으로 바로 호출**하라. "
    "결과를 먼저 보여준 뒤 '지역을 좁혀 드릴까요?'라고 물어야 한다(규칙 1.2 그대로).\n"
    "  세 조건은 서로 다르다 — 주인전세=매도인이 전세로 눌러앉음, 세안고=기존 임차인 승계, "
    "주인대출=매도인이 직접 자금 제공. 질문 표현에 맞는 kind 로 호출하고, 도구가 준 '설명'을 "
    "한 줄로 곁들여라 — 용어만으로는 구분이 안 돼 매수자가 실익을 오해한다.\n"
    "  ★목록은 아래 9.45 규칙대로 도구가 준 본문을 그대로 옮겨 적어라.\n"
    "  반드시 '광고 문구 기준이라 실제 조건은 중개사무소 확인 필요'를 밝히고, 끝에 [주인 매물 보기](/special-deals)를 붙여라.\n"
    "9.3) [단지 질문 — 도구가 돌려준 정식 단지명과 링크를 반드시 밝혀라] get_complex_info 로 답할 때는 "
    "도구 결과의 '단지' 값(정식 명칭)을 그대로 쓰고, 첫 문장에 **[단지정보 →](/complex/…)** 링크를 붙여라.\n"
    "  ★사용자가 부른 이름과 도구가 찾은 '단지'가 다르면 반드시 알려라: "
    "'말씀하신 OO는 △△(정식 명칭)으로 찾았어요' 라고 한 줄 덧붙인다. "
    "이걸 빼면 엉뚱한 단지가 잡혀도 사용자가 알아채지 못한다(실제로 수원 단지 질문에 서울 단지 "
    "실거래가 나갔는데, 정식 명칭을 밝힌 덕에 발견됐다).\n"
    "  ★단, 도구가 찾은 단지가 질문과 무관해 보이면(지역·이름이 전혀 다름) 그 데이터를 쓰지 말고 "
    "'해당 단지를 찾지 못했어요. 지역을 함께 알려주세요'라고 답하라. 억지로 끼워 맞추지 마라.\n"
    "9.4) [매물 검색 답변 형식 — 고정] find_apartments·find_quick_deals 처럼 매물을 찾는 도구를 쓴 답변은 "
    "항목마다 **단지명 · 전용면적 · 가격 · 그 단지 매물 건수 · 단지상세 링크**를 모두 넣어라. 하나라도 빼지 마라.\n"
    "  형식: `- **단지명** 구·동 · 전용 32㎡ · 월세 120만 · 3건 [단지정보 →](/complex/12345)`\n"
    "  ★지역(구·동)을 빼지 마라. '면목동'만 적으면 어느 구인지 몰라 동명이동과 구분이 안 된다. "
    "도구가 준 줄에 이미 들어 있으니 그대로 옮기면 된다.\n"
    "  '단지내매물수'와 '단지정보' 값은 도구 결과에 이미 들어 있다 — 그대로 쓰면 된다. 없다고 생략하지 마라. "
    "건수를 빼면 사용자는 그 단지에 몇 개가 있는지 몰라 다시 물어야 하고, 링크를 빼면 확인하러 갈 곳이 없다.\n"
    "  끝에 '총 N건 중 상위 M개 단지'처럼 전체 규모를 한 줄로 밝혀라.\n"
    "9.45) [도구가 '답변에_그대로_쓸_본문'을 주면 그 줄들을 **그대로** 옮겨 적어라] 줄을 다시 쓰거나 "
    "요약·생략하지 마라. 직접 쓰면 지역(구·동)·거래유형·링크를 빠뜨린다. 앞뒤로 한두 문장 덧붙이는 것은 "
    "좋지만 목록 줄 자체는 손대지 않는다. 이 본문은 이미 10줄 이하로 맞춰져 있다.\n"
    "9.45-2) [건수만 말하고 끝내지 마라] '급매물 1,100건이 확인됐습니다'처럼 총계만 쓰고 목록을 "
    "빠뜨리면 손님은 어느 단지인지 알 수 없다. **반드시 5~10곳을 실제로 나열**하고, 그 뒤에 "
    "'전체 N곳 중 M곳'을 밝혀라. 조건이 넓어 건수가 많으면 '조건을 좁히거나 콕집요청으로 "
    "동네 중개사무소에 조건을 보내보라'고 한 줄 덧붙인다.\n"
    "9.5) [목록은 최대 10개 — 같은 줄을 반복하지 마라] 도구가 수십·수백 건을 돌려줘도 답변에 나열하는 항목은 **최대 10개**다. 그 이상은 '외 N건'으로 줄여라. "
    "이미 쓴 줄과 같은 내용을 다시 쓰지 마라 — 단지·면적·가격이 같으면 한 줄로 합치고 옆에 'N건'을 적는다. "
    "사용자 조건에 **맞지 않는 항목은 아예 싣지 마라**. '(조건 초과)'를 붙여 나열하는 것은 금지다 — 조건에 맞는 게 없으면 '조건에 맞는 매물이 없어요'라고 한 줄로 답하고, 가장 근접한 것 3건만 따로 제시하라.\n"
    "10) [지역 실거래/거래 질문 — 도구 조합 필수] '서울 6월 실거래', 'OO구 거래량/거래현황' 처럼 "
    "지역의 실거래·거래를 묻는 질문에는 절대 '직접 조회할 수 없다'로 끝내지 마라. 다음 도구를 조합해 답한다: "
    "① region_market_pulse(region=지역) — 그 지역 이번달 거래량(전월·전년 대비·예측). "
    "② rank_complexes(metric='거래량', region=지역) — 거래 많은 단지 TOP. "
    "③ find_record_high(region=지역) — 최근 신고가 경신 단지. "
    "개별 실거래 한 건씩의 목록을 뽑는 도구는 없으므로, 위 ①②③로 그 지역의 실거래 활동을 구체적으로 설명하고, "
    "특정 단지의 실거래 이력은 get_complex_info(단지명)로 볼 수 있다고 안내하라. "
    "특정 월(예: 6월)을 콕 집으면, 데이터는 그 달을 포함한 최신까지 있으니 '6월 거래는 이렇다'고 ① 기준으로 답한다.\n"
    "10.2) [지역 '최근 이슈/뉴스/소식/개발' — 정책·개발 이벤트 우선] 'OO(지역) 최근 이슈', 'OO 무슨 일', "
    "'OO 재건축/재개발/선도지구/개발 소식', 'OO 최근 뉴스/화제' 처럼 지역의 '이슈·소식'을 물으면, "
    "거래량(region_market_pulse)으로 답하기 전에 **먼저 get_policy_timeline(keyword=지역명)**으로 그 지역의 "
    "정책·개발 이벤트(예: 대전→2026-07-15 대전 선도지구 선정, 부산→부산 선도지구)를 확인하라. 이벤트가 있으면 "
    "그것을 '가장 최근 이슈'로 우선 답하고(발표일·내용), 필요하면 region_market_pulse(거래 분위기)를 보조로 덧붙인다. "
    "'이슈=거래량'으로 단정해 거래건수만 답하지 마라 — 사용자가 원한 건 대개 재건축·규제 같은 사건이다.\n"    "11) [지역 vs 전국 순위 — 도구 선택 매우 중요] rank_complexes 에서 거래량·평당가·갭·회전율·저평가(회복률)·수익률는 "
    "region 을 주면 그 지역만 집계하니 지역 질문에 그대로 써라(예: '강남구 거래량'·'대전 평당가'). "
    "★지역을 안 주면 region 생략하고 **전국으로 즉시 호출**하라 — '저평가 단지', '갭투자 좋은 단지', '회전율 높은 단지', "
    "'수익률 높은 단지'처럼 지역 없는 순위질문에 **절대 '어느 지역이요?'라고 되묻지 마라**(rank_complexes를 전국으로 바로 호출). "
    "최고가·전세가율·저가거래·호가갭도 region 을 받는다 — 지역 순위를 물으면 그대로 쓰면 된다. "
    "▸특정 지역의 '비싼/싼/가격대 **매물**'(예: '제주 비싼 아파트', '대전 싼 아파트')은 지금 나와 있는 호가를 묻는 것이므로 "
    "find_apartments(region=지역, sort) 로 답하고, '실거래 최고가 순위'를 물으면 rank_complexes(metric='최고가', region=지역). "
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
    "단지 순위는 모든 지표가 region 을 받는다 — 지역 질문에 그대로 쓰면 된다(규칙 11).\n"
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
    "AI 질문은 무료다 — 로그인도 포인트도 필요 없고, 한 사람당 하루 50번까지 물어볼 수 있다. "
"(포인트는 토론장·리뷰 등 다른 활동에 쓰인다. 포인트를 쓰더라도 '계급'은 누적 획득 기준이라 내려가지 않는다.)\n"
    "· 계급(레벨): 누적 획득 포인트로 자동 결정. Lv.0 부린이(0P) → 임장러(200) → 동대표(400) → "
    "관리소장(700) → 단지대표(1,100) → 통장(1,600) → 주민센터장(2,200) → 구청장(3,000) → "
    "시장(4,000) → 도지사(8,000) → 장관(15,000) → 국무총리(26,000) → 국회의원(45,000) → "
    "국회의장(85,000) → 대통령(150,000) → 조물주(300,000) → 건물주(500,000, 최고 등급). "
    "'내 정보 → 계급표 보기'에서 전체 표를 볼 수 있다. (예: '포인트 어떻게 모아요?' → 위 적립 목록을 "
    "안내. '계급 어떻게 올려요?' → 활동으로 포인트를 쌓으면 누적 기준으로 등급이 오른다고 설명.)\n"
    "· 콕집요청(/request): 조건만 남기면 그 조건의 매물을 가진 동네 중개사무소가 매물을 제안한다(무료). "
    "전화번호는 중개사무소로 넘어가지 않는다. **보낸 요청과 도착한 제안은 '내 요청 보기(/me/requests)'** 에서 본다.\n"
    "· 비단지 통계(/nonresi): 상가·사무실·빌라·단독의 지역별 매물 호가 통계. 유형별 경로는 "
    "/nonresi/sangga · /nonresi/office · /nonresi/villa · /nonresi/house. "
    "★지도·급매지도는 아파트·오피스텔 전용이다 — 상가·사무실을 지도에서 볼 수 있다고 "
    "안내하면 안 된다(그런 기능이 없다).\n"
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
    # ★단순 부분일치는 위험하다. '수동'(대구 중구)이 '성수동' 안에 들어 있어
    #   "성수동 아파트"가 대구로 튀었다(실측). 동명이 낱말 첫머리에 와야 인정한다.
    def _at_head(name: str) -> bool:
        return any(tok.startswith(name) for tok in qtok)

    best, bs = None, -1
    for cno, name, parent in sec:
        if not name or not _at_head(name):
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

    # 4순위 앞에 '동명 prefix'를 먼저 본다. 손님이 '성수동'처럼 동 이름을 통째로 말했으면
    # 그 이름으로 시작하는 동(성수동1가·2가)이 정답이고, 코어만 겹치는 다른 지역
    # (임실군 성수면)이 먼저 잡히면 안 된다.
    for t in sorted((t for t in qtok if len(t) >= 3 and t.endswith(("동", "가", "읍", "면", "리"))),
                    key=len, reverse=True):
        hits = [(cno, name, parent) for cno, name, parent in sec if name and name.startswith(t)]
        if len(hits) == 1:
            return _dong(*hits[0])[1]
        if hits and len({p for _, _, p in hits}) == 1:
            p_ = hits[0][2]
            dname, dparent = dvsn.get(p_, (None, None))
            return {"sido": cities.get(dparent), "sido_code": p_[:2],
                    "sigungu": dname, "sigungu_code": p_[:5], "sigungu_cortar": p_,
                    "dong": None, "dong_cortar": None, "level": "sigungu"}

    # 4순위(폴백): 동 core 매칭('둔산'→둔산동)
    # core 는 '개사동'→'개사' 처럼 두 글자라, 아무 데나 걸리면 '중개사무소'의 '개사'가
    # 군산 개사동으로 잡힌다(실측). 낱말 한가운데가 아니라 토큰 첫머리에서만 인정한다.
    def _core_at_head(name: str) -> bool:
        return any(tok.startswith(c) for c in _cores(name) for tok in qtok)

    best, bs = None, -1
    for cno, name, parent in sec:
        if not _core_at_head(name):
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
@lru_cache(maxsize=1)
def _dong_lookup() -> dict:
    """cortar_no(동) → '구 동'. 급매·매물 목록에 지역을 붙이는 데 쓴다."""
    cities, dvsn, sec = _region_index()
    out = {}
    for cno, name, parent in sec:
        gu = (dvsn.get(parent) or (None, None))[0]
        out[cno] = " ".join(x for x in (gu, name) if x)
    return out


def _gu_dong(cortar_no) -> str:
    return _dong_lookup().get(str(cortar_no or ""), "")


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
        "단지": x["complex_name"], "지역": _gu_dong(x.get("cortar_no")),
        "면적타입(공급㎡)": x["area_name"],
        "전용㎡": round(x["avg_excl"]) if x.get("avg_excl") else None,
        # 거래유형을 값에 붙인다 — 따로 두면 모델이 빠뜨려 매매인지 전세인지 알 수 없다
        "현재_최저호가": f"{trade_type} {_won(x['asking_min'])}",
        "기준_실거래평균": _won(x["avg_real"]),         # 할인율의 비교 기준
        "참고_최저실거래": _won(x.get("min_real")),     # 최근 실거래 중 최저(참고용)
        "할인율%": round((x["discount_min"] or 0) * 100, 1),
        "매물수": x["n_listings"],
        "단지정보": f"/complex/{x['complex_no']}",   # 프런트 바로가기 경로
    } for x in items[:_LIST_N]]
    resolved = (" ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]])) or "전국")
    # find_apartments 와 같은 이유로 본문을 완성해 준다 — 모델이 직접 쓰면 지역·거래유형이 샌다
    body = ""
    if deals:
        body = (f"**{resolved} · {trade_type} · 실거래 평균 대비 {min_discount_pct:g}% 이상 싼 매물**"
                f"\n\n" + "\n".join(
                    f"- **{d['단지']}** {d['지역']} · 전용 {d['전용㎡']}㎡ · {d['현재_최저호가']}"
                    f" (실거래 평균 {d['기준_실거래평균']} 대비 {float(d['할인율%']):+.1f}%)"
                    f" · 매물 {d['매물수']}건 [단지정보 →]({d['단지정보']})" for d in deals)
                + f"\n\n조건에 맞는 급매물은 모두 {len(items):,}곳이고, 그중 {len(deals)}곳을 "
                  "보여드렸어요.")
    out = {
        "해석된_지역": resolved,
        "거래유형": trade_type, "최소할인율%": min_discount_pct,
        "답변에_그대로_쓸_본문": body,
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


_LIST_N = 10          # 답변에 싣는 단지 수(프롬프트 규칙 9.5와 같은 값)


def find_apartments(region: str, excl_min: float = 0.0, excl_max: float = 0.0,
                    min_price_eok: float = 0.0, max_price_eok: float = 0.0,
                    trade_type: str = "매매", sort: str = "대표순") -> dict:
    """지역의 '매물(호가)'을 전용면적·가격대로 직접 검색한다.
    가격대 질문('서울 강남구 20억대 국평 아파트', '제일 비싼/싼 아파트' 등)의 정답 도구.
    급매(할인)와 무관하게 실제로 나와있는 매물을 본다(거래 적은 단지·주상복합 포함).
    단지별로 대표 매물 1건씩만 반환한다(같은 단지 중복 노출 없음). 응답의 '총매물수'는
    조건에 맞는 전체 매물 건수이므로 '매물 몇 개/매물수' 질문엔 이 값을 쓴다.

    ★'답변에_그대로_쓸_본문'을 **그대로** 답변에 넣는다. 줄을 다시 쓰거나 요약하지 말 것.
      직접 쓰면 지역(구·동)과 거래유형을 계속 빠뜨려서, 손님이 '서울 어디인지, 매매인지
      전세인지, 왜 84㎡인지' 알 수 없는 목록이 나간다.
      앞뒤로 한두 문장 덧붙이는 것은 좋지만 목록 자체는 손대지 않는다.

    Args:
        region: 자연어 지역명. 예: '서울 강남구', '서울 강남구 논현동'. 전국이면 '전국' 또는 빈 문자열.
        excl_min, excl_max: 전용면적(㎡) 범위. 국평(84㎡)이면 82~87, 59㎡면 57~62, 0이면 전체.
        min_price_eok, max_price_eok: 가격(억) 범위. 0이면 제한 없음.
            ★'N억대'는 반드시 **구간**으로 넣는다(한쪽만 주면 엉뚱한 값이 나온다).
              · '5억대'  → min 5,  max 6    (한 자리 억은 N ~ N+1)
              · '25억대' → min 25, max 26
              · '30억대' → min 30, max 40   (10의 배수는 십억 자리 기준 N ~ N+10)
              '5억 이하'처럼 명시적 상한만 말했을 때만 max 만 넣는다.
        trade_type: '매매'|'전세'|'월세'(월세는 보증금 기준).
        sort: '대표순'(기본 — 가격대 전체에서 고르게 뽑아 보여준다) | '낮은순'(싼 것부터) |
              '높은순'(비싼 것부터). **'제일 비싼/싼', '최고가', '가장 저렴' 처럼 극단을 묻는
              질문에만** 낮은순·높은순을 쓴다. 그냥 '매물 보여줘'엔 기본값(대표순)을 써야
              한쪽 끝(월 1만짜리 반전세, 하한선 가격)만 나오지 않는다.
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
    # 아래쪽 자릿수 오타도 막는다 — '디에이치방배 전세 15만'처럼 원문이 "15"로 들어온
    # 매물이 낮은순 정렬의 1위를 차지해 손님에게 헛것을 보여줬다(실측 2026-08-04).
    # 월세는 보증금이 정상적으로 작을 수 있으니 매매·전세에만 건다.
    if tt in ("A1", "B1"):
        where.append("l.deal_or_warrant_price >= 30000000")   # 3천만 미만은 오타로 본다
        # 단가가 말이 안 되는 매물도 뺀다. '전용 20㎡ 매매 265억'(㎡당 13억)처럼 건물
        # 통매매를 호실로 올린 건이 최고가 목록 상위를 차지했다(실측 2026-08-04).
        # 실제 최고가 단지(PH129 273㎡ 330억)는 ㎡당 1.2억이라 1.5억 상한이면 안 걸린다.
        where.append("l.deal_or_warrant_price / MAX(l.area2_m2, 1) < 150000000")
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
    # 가격대(하한·상한 모두)를 물었으면 구간 전체에서 고르게 뽑는다.
    # 낮은순 20개를 그대로 주면 '30억~40억'에 30억짜리만 20개가 나와서 손님이 물은
    # 구간의 아래 끝만 보게 된다(실측 2026-08-04: 6,898건 중 20개가 전부 30억).
    # '제일 비싼/싼'을 물은 게 아니면 정렬 극단 20개가 아니라 구간 전체의 대표를 보여준다.
    # 극단만 주면 '강남구 월세'에 월 1만짜리 반전세만, '30억~40억'에 30억만 나온다(실측).
    spread = ("대표" in sort) or bool(min_price_eok and max_price_eok)
    cap = 500 if spread else _LIST_N
    # 월세는 보증금이 아니라 '달마다 내는 돈'이 기준이다. 보증금순으로 뽑으면
    # 보증금 180만짜리 원룸만 줄줄이 나온다(실측 2026-08-04 강남구 월세).
    sort_col = "COALESCE(rent, 0)" if tt == "B2" else "price"
    row_col = "COALESCE(l.rent_price, 0)" if tt == "B2" else "l.deal_or_warrant_price"
    # 단지별 대표 매물 1행만(같은 단지가 평형 차이로 여러 번 중복 노출되는 문제 제거).
    # 높은순=단지 내 최고가, 낮은순=최저가 매물을 대표로 뽑고 그 가격으로 정렬.
    sql = f"""
        WITH base AS (
            SELECT l.complex_no, cx.complex_name, l.area2_m2 AS excl, l.area_name,
                   l.deal_or_warrant_price AS price, l.rent_price AS rent,
                   -- '서울 어디'인지 없으면 목록이 무의미하다. 구·동을 행마다 붙인다.
                   (SELECT gu.cortar_name FROM regions dong
                      JOIN regions gu ON gu.cortar_no = dong.parent_cortar_no
                     WHERE dong.cortar_no = cx.cortar_no) AS gu,
                   (SELECT cortar_name FROM regions WHERE cortar_no = cx.cortar_no) AS dong,
                   ROW_NUMBER() OVER (PARTITION BY l.complex_no
                                      ORDER BY {row_col} {order}) AS rn,
                   COUNT(*) OVER (PARTITION BY l.complex_no) AS n
            FROM listings_current l JOIN complexes cx ON cx.complex_no = l.complex_no
            WHERE {wsql}
        )
        SELECT complex_no, complex_name, excl, area_name, price, n, rent, gu, dong
        FROM base WHERE rn = 1
        ORDER BY {sort_col} {order} LIMIT {cap}
    """
    with api._open_db() as c:
        rows = c.execute(sql, params).fetchall()
        if spread and len(rows) > _LIST_N:
            # 가격순으로 정렬된 상태에서 일정 간격으로 집어 구간 전체를 대표하게 한다.
            # 무작위 표본이 아니라 고정 간격이라 같은 질문엔 같은 답이 나온다.
            step = len(rows) / float(_LIST_N)
            rows = [rows[min(len(rows) - 1, int(i * step))] for i in range(_LIST_N)]
        # 면적을 안 물었으면 결과에 59㎡와 235㎡가 섞여 나온다. 값이 틀린 건 아니지만
        # 뒤죽박죽 순서면 비교가 안 되니 작은 집→큰 집 순으로 정렬해 사다리처럼 읽히게 한다.
        if not (excl_min or excl_max):
            rows = sorted(rows, key=lambda r: (r[2] or 0))
        total, total_units = c.execute(
            f"SELECT COUNT(*), SUM(1.0/MAX(COALESCE(l.same_addr_cnt,1),1)) FROM listings_current l "
            f"JOIN complexes cx ON cx.complex_no = l.complex_no WHERE {wsql}",
            params).fetchone()
    # SELECT 컬럼: 0 complex_no, 1 name, 2 excl, 3 area_name, 4 price, 5 n(단지내 매물수), 6 rent
    # 값에 거래유형을 붙여 둔다. 전에는 응답 맨 위에만 있어서 모델이 빠뜨렸고,
    # 손님은 '반포자이 25억'이 매매인지 전세인지 알 수 없었다(실측 2026-08-04).
    def _price(p, rent):
        if trade_type == "월세":
            return f"월세 보증금 {_won(p)}" + (f" / 월 {_won(rent)}" if rent else "")
        return f"{trade_type} {_won(p)}"

    out = [{
        "단지": r[1], "지역": " ".join(x for x in (r[7], r[8]) if x),
        "전용㎡": round(r[2]) if r[2] else None, "면적타입": r[3],
        "거래유형": trade_type, "대표호가": _price(r[4], r[6]), "단지내매물수": r[5],
        "단지정보": f"/complex/{r[0]}",
    } for r in rows]
    where_txt = ("전국" if national else
                 " ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]])))
    # 무슨 조건으로 찾았는지 한 줄로 만들어 준다. 손님이 면적을 말한 적 없는데
    # 84㎡로 좁혀 놓고 그 사실을 안 밝히면 '왜 84냐'는 의문만 남는다(실측 2026-08-04).
    cond = [where_txt, trade_type]
    if excl_min or excl_max:
        lo, hi = excl_min or 0, excl_max or 0
        cond.append(f"전용 {lo:g}~{hi:g}㎡" if lo and hi else f"전용 {(lo or hi):g}㎡ 기준")
    else:
        cond.append("전용면적 전체")
    if min_price_eok or max_price_eok:
        lo, hi = min_price_eok or 0, max_price_eok or 0
        cond.append(f"{lo:g}억~{hi:g}억" if lo and hi else
                    (f"{hi:g}억 이하" if hi else f"{lo:g}억 이상"))
    # 모델에게 '이렇게 써라'라고 시켜 봤자 지역·거래유형을 계속 빠뜨린다(실측).
    # 그래서 본문을 여기서 완성해 주고 모델은 붙이기만 하게 한다.
    head = f"**{' · '.join(cond)}** 기준으로 찾았어요."
    if excl_min or excl_max:
        head += " 말씀하신 평형으로 좁혔어요 — 면적을 넓혀서 다시 볼 수도 있어요."
    elif out:
        # 면적을 안 물었으면 결과가 소형~대형까지 걸친다. 그 폭을 먼저 알려 줘야
        # 'why 59㎡와 203㎡가 같이 나오지?' 하는 혼란이 없다.
        sizes = [x["전용㎡"] for x in out if x["전용㎡"]]
        if sizes and max(sizes) - min(sizes) >= 20:
            head += (f" 같은 값이라도 전용 {min(sizes)}㎡부터 {max(sizes)}㎡까지 차이가 커요"
                     " — 작은 집부터 순서대로 보여드릴게요.")
    lines = [f"- **{x['단지']}** {x['지역']} · 전용 {x['전용㎡']}㎡ · {x['대표호가']}"
             f" · 단지 내 {x['단지내매물수']}건 [단지정보 →]({x['단지정보']})" for x in out]
    tail = (f"\n조건에 맞는 매물은 모두 {total:,}건이고, 그중 단지 {len(out)}곳을 보여드렸어요."
            if total else "")
    body = head + "\n\n" + "\n".join(lines) + "\n" + tail

    return {
        "해석된_지역": where_txt,
        "거래유형": trade_type,
        # 행 데이터(매물목록)는 일부러 돌려주지 않는다. 같이 주면 모델이 그걸로 목록을
        # 다시 써서 [단지정보] 링크를 통째로 날려 먹는다(실측 2026-08-04 강남구 30억대).
        # 재작성할 재료를 주지 않는 것이 '그대로 쓰라'는 지시보다 확실하다.
        "답변에_그대로_쓸_본문": body,
        "적용조건": " · ".join(cond),
        "전용면적범위㎡": [excl_min or None, excl_max or None],
        "가격범위억": [min_price_eok or None, max_price_eok or None],
        "총매물수": total, "표시단지수": len(out),
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
    # 공백 제거 전체명('ph 129'→'ph129')을 최우선 — 'PH129'를 직접 매칭(마지막 토큰 '129'만 잡아
    # '신라(1292)' 같은 이름 속 숫자에 오매칭되던 버그 방지). 2글자 이상일 때만.
    nospace = "".join(toks).replace(" ", "")
    needles = ([nospace] if nospace and len(nospace) >= 2 and nospace != needle else []) + [needle]
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
            # 어순이 다른 경우('신나무실주공5단지' vs 실제 '신나무실5단지주공') — 숫자/접미어를
            # 떼고 앞부분(고유명)만으로 다시 찾는다. 접두를 자르는 것보다 훨씬 안전하다.
            if not hits and len(name) >= 5:
                import re as _r
                stem = _r.sub(r"(주공|단지|아파트|마을|차)?\s*\d+\s*(주공|단지|아파트|차)?$", "", name).strip()
                stem = _r.sub(r"(주공|단지|아파트|마을)$", "", stem).strip()
                if len(stem) >= 2 and stem != name:
                    hits = api.complexes_search(q=stem, limit=3).get("items") or []
            # 지명 접두가 이름에 붙어 오는 경우('광교자연앤힐스테이트') — 접두 2~3자 제거.
            # ★남는 글자가 5자 이상일 때만: '신나무실주공5단지'→'실주공5단지'가 '잠실주공5단지'에
            #   오매칭되던 사고(2026-07-22, 수원 단지 질문에 서울 40억 실거래를 답함) 방지.
            if not hits and len(name) >= 8:
                for cut in (2, 3):
                    rest = name[cut:]
                    if len(rest) < 5:
                        continue
                    hits = api.complexes_search(q=rest, limit=3).get("items") or []
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


# 단지명 자리에 들어오면 안 되는 일반 용어(평형·유형). 지역명은 넣지 않는다 —
# '둔산동 크로바'처럼 지역+단지를 함께 주는 정상 호출을 막아버린다.
_NOT_COMPLEX = {"국평", "국민평형", "소형 국평", "아파트", "오피스텔", "빌라", "매물",
                "전용84", "전용59", "84㎡", "59㎡"}


def get_complex_info(complex_name: str, region: str = "") -> dict:
    """특정 아파트 단지의 종합 정보. 세대수·준공·주소 + 최근 실거래 요약(등기·동 포함) +
    급매 보유 중개사(연락처)를 한 번에 준다. '이 단지 어때?', '실거래가', '급매 중개사' 질문용.

    Args:
        complex_name: 단지명. 예: '둔산동 크로바', '잠실엘스', '은하수'.
        region: 지역(선택). 동명이 단지가 많으면 지역을 주면 정확해진다.
    """
    import scripts.local_api as api
    # '국평'·'30평대'는 평형이지 단지명이 아니다 — 모델이 단지명 자리에 넣고 와서
    # "'국평' 단지를 찾을 수 없습니다"라는 엉뚱한 문장을 손님에게 내보냈다(실측).
    nm = (complex_name or "").strip()
    if nm in _NOT_COMPLEX or re.fullmatch(r"\d{1,3}\s*(평대?|㎡)", nm):
        return {"안내_한국어로답할것": f"'{nm}'은(는) 단지명이 아니라 평형 표현입니다. "
                "지역의 평형별 시세를 묻는 것이면 region_market_pulse 나 find_apartments 를 "
                "쓰고, 단지 질문이면 실제 단지명을 넣으세요."}
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
    # 전국을 지원한다. 예전엔 region 이 비면 에러를 냈고, 모델이 그걸 '0건'으로 읽어
    # "전국에 신고가 경신 단지가 없다"는 거짓을 말했다(실측 2026-08-04).
    national = (not (region or "").strip()) or any(k in region for k in ("전국", "전체"))
    reg = None if national else _resolve_region(region)
    if not national and not reg:
        return {"error": f"지역 '{region}' 을(를) 찾지 못했습니다. '서울 강남구'처럼 알려주세요."}
    tt = "B1" if "전세" in trade_type else "A1"
    # 캐시 선조회 — 빌더 AI 캐논 키(days 30/90/180/360)와 일치 시 즉시. 미스 → 라이브.
    items = _rank_items("/stats/tx-record-high", api.tx_record_high,
                        days=int(months * 30), trade=tt, asset="apt",
                        order="recent", limit=1000)
    if reg and reg.get("dong_cortar"):
        items = [x for x in items if (x.get("cortar_no") or "") == reg["dong_cortar"]]
    elif reg and reg.get("sigungu_code"):
        items = [x for x in items if (x.get("cortar_no") or "").startswith(reg["sigungu_code"])]
    elif reg and reg.get("sido_code"):
        items = [x for x in items if (x.get("cortar_no") or "").startswith(reg["sido_code"])]

    def up(x):
        rp, ph = x.get("record_price"), x.get("prev_high")
        return round((rp - ph) / ph * 100, 1) if rp and ph else None

    out = [{
        "단지": x["complex_name"], "지역": _gu_dong(x.get("cortar_no")),
        "면적타입(공급㎡)": x["area_key"],
        "신고가": f"{trade_type}(실거래) " + _won(x["record_price"]), "경신일": x["record_date"],
        "직전최고": _won(x["prev_high"]), "상승률%": up(x), "층": x["floor"],
        "단지정보": f"/complex/{x['complex_no']}",
    } for x in items[:limit]]
    return {
        "해석된_지역": ("전국" if not reg else " ".join(filter(None, [reg["sido"], reg["sigungu"], reg["dong"]]))),
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
    # sido 로만 좁힌 경우엔 엔드포인트가 시도 전체를 준다 — '청주'에 충주·제천이 섞이므로
    # 이름 후필터를 한 번 더 걸어야 한다. sigungu(5자리)면 이미 정확해 후필터가 필요 없다.
    region_exact = "sigungu" in reg_kw

    def pct(v):
        return round((v or 0) * 100, 1)

    if "갭" in m and "호가" not in m:
        o = "desc" if high else "asc"
        items = _rank_items("/stats/tx-gap-rank", api.tx_gap_rank,
                            asset="apt", area_class=ac, order=o, limit=pool, **reg_kw)
        param_region = region_exact
        title = f"갭 {'큰' if high else '작은'}순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "면적타입": x["area_key"],
                         "매매평균": _won(x["avg_sale"]), "전세평균": _won(x["avg_jeonse"]),
                         "갭": _won(x["gap"]), "전세가율%": pct(x["jeonse_rate"])}
    elif "전세" in m:
        o = "asc" if high is False else "desc"
        items = _rank_items("/stats/tx-jeonse-rate", api.tx_jeonse_rate,
                            asset="apt", area_class=ac, order=o, limit=pool, **reg_kw)
        param_region = region_exact
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
        param_region = region_exact
        title = f"평당가 {'낮은' if high is False else '높은'}순 (단지별 대표 평형 1건)"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "면적타입": x["area_key"],
                         "평당가": _won(x["pyeong_price"]), "거래평균": _won(x["avg_price"])}
    elif "최고가" in m or "비싼" in m:
        # 지역은 반드시 엔드포인트로 넘긴다 — 전국 최고가 500건은 거의 수도권이라
        # 후필터로 거르면 대전·충북·전북·제주·강원·경북이 전부 0건이 된다(실측).
        items = _rank_items("/stats/tx-top-price", api.tx_top_price,
                            trade="A1", asset="apt", area_class=ac, limit=pool, **reg_kw)
        param_region = region_exact
        title = "실거래 최고가순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"],
                         "거래가": "매매(실거래) " + _won(x["price"]),
                         "전용㎡": x["excl_use_ar"], "층": x["floor"], "계약일": x["deal_ymd"]}
    elif "거래량" in m or "거래 많" in m:
        items = _rank_items("/stats/tx-top-volume", api.tx_top_volume,
                            trade="A1", asset="apt", area_class=ac, limit=pool, **reg_kw)
        param_region = region_exact
        title = "거래량 많은순"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "거래건수": x.get("count"), "세대수": x.get("households")}
    elif "저가" in m or "증여" in m:
        items = _rank_items("/stats/tx-low-price", api.tx_low_price,
                            asset="apt", area_class=ac, limit=pool, **reg_kw)
        param_region = region_exact
        title = "평균 대비 크게 싼 거래(증여 의심)"
        row = lambda x: {"단지": x["complex_name"], "지역": x["region_name"], "거래가": _won(x["deal_amount"]),
                         "평균가": _won(x["avg_price"]), "할인율%": pct(x["discount_rate"]),
                         "전용㎡": x["excl_use_ar"], "층": x["floor"], "거래": x.get("dealing_gbn")}
    elif "회전" in m:
        items = _rank_items("/stats/tx-turnover", api.tx_turnover,
                            trade="A1", asset="apt", area_class=ac, limit=pool, **reg_kw)
        param_region = region_exact
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
                            area_class=ac, order="desc", limit=pool, **reg_kw)
        param_region = region_exact
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


def _josa(word: str, with_batchim: str, without: str) -> str:
    """받침 유무에 따라 조사를 고른다('사무실는' 같은 어색한 말이 손님에게 나갔다)."""
    if not word:
        return without
    ch = word[-1]
    return with_batchim if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else without


def find_nonresi_stats(kind: str, region: str = "", trade_type: str = "매매") -> dict:
    """상가·사무실·단독주택의 매물(호가) 통계. 아파트가 아닌 '비단지' 물건 전용.

    콕집은 이 세 유형의 **매물 호가**를 지역별로 수집한다(실거래는 없다).
    '강남구 상가 시세', '사무실 임대료', '단독주택 얼마' 같은 질문의 정답 도구다.
    ★거절하지 마라 — 데이터가 있다. 다만 실거래가 아니라 '지금 나와 있는 매물의 호가'이고,
      상가·사무실은 같은 건물 안에서도 층·전면·업종에 따라 값이 크게 갈린다는 점을 밝힌다.

    ★가격 조건은 지원하지 않는다. '보증금 5천 이하', '월세 200만원 이하' 처럼 조건을 걸어도
      이 도구는 그 지역 **평균**만 준다. 그럴 땐 평균을 먼저 답하고
      "조건별 개별 검색은 /nonresi 에서 볼 수 있다"를 한 줄 덧붙여라.
      절대 '질문을 이해하지 못했다'로 끝내지 마라 — 지역 평균은 답할 수 있다.

    Args:
        kind: '상가' | '사무실' | '단독'(다가구 포함)
        region: 자연어 지역. 비우면 전국.
        trade_type: '매매' | '전세' | '월세'. 상가·사무실은 월세(임대)가 대부분이다.
    """
    import scripts.local_api as api
    cat = {"상가": "sangga", "점포": "sangga", "사무실": "office", "오피스": "office",
           "단독": "house", "다가구": "house", "주택": "house"}.get(kind.strip())
    if not cat:
        # 오피스텔·원룸·빌라를 여기로 보내는 일이 잦다. 예전엔 '알려줄 수 없다'고 거절하거나
        # ('원룸'→'사무실'처럼) 엉뚱하게 매핑돼 391㎡ 사무실 평균을 답했다(실측).
        # 라우팅을 프롬프트에 맡기지 않고 여기서 곧장 알맞은 조회로 넘긴다.
        k = kind.strip()
        if any(x in k for x in ("빌라", "연립", "다세대")):
            return find_villa_stats(region=region, trade_type=trade_type)
        if any(x in k for x in ("오피스텔", "원룸", "아파트", "주상복합", "도시형")):
            r = get_listing_stats(region=region)
            r["안내_한국어로답할것"] = (
                f"'{k}'은(는) 단지형이라 아파트·오피스텔 매물 통계로 답한다. "
                "상가·사무실·단독과는 다른 데이터다.")
            return r
        return {"error": "kind 는 '상가'·'사무실'·'단독' 중 하나여야 합니다. "
                        "오피스텔·원룸은 단지형(get_listing_stats), 빌라는 find_villa_stats."}
        # 위임 결과가 왔는데 '이해하지 못했다'로 끝내는 일이 있어 못을 박는다
    reg = _resolve_region(region) if region else None
    cortar = ""
    if reg:
        cortar = reg.get("dong_cortar") or reg.get("sigungu_code") or reg.get("sido_code") or ""
    tr = {"전세": "B1", "월세": "B2"}.get(trade_type.strip(), "A1")

    st = api.nonresi_stats(cat=cat, cortar=cortar, trade=tr)
    if not st.get("available", True):
        return {"안내_한국어로답할것": f"{kind} 매물 데이터를 아직 준비하지 못했습니다."}
    where = st.get("region_name") or (
        " ".join(filter(None, [reg.get("sido"), reg.get("sigungu"), reg.get("dong")])) if reg else "전국")

    rows = []
    for b in (st.get("by_trade") or []):
        r = {"거래": b.get("trade") or trade_type, "매물수": b.get("n"),
             "평균호가": _won(b.get("avg_price")), "평균전용㎡": b.get("avg_area_m2")}
        if b.get("avg_rent"):
            r["평균월세"] = _won(b.get("avg_rent"))
        if b.get("avg_pyeong_price"):
            r["평당가"] = _won(b.get("avg_pyeong_price"))
        rows.append(r)

    body = ""
    if rows:
        lines = []
        for r in rows:
            bits = [f"매물 {r['매물수']:,}건"]
            if r.get("평균호가"):
                bits.append(f"평균 {'보증금 ' if r['거래'] in ('월세', 'B2') else ''}{r['평균호가']}")
            if r.get("평균월세"):
                bits.append(f"평균 월세 {r['평균월세']}")
            if r.get("평균전용㎡"):
                bits.append(f"평균 전용 {round(r['평균전용㎡'])}㎡")
            lines.append(f"- **{r['거래']}** · " + " · ".join(bits))
        body = (f"**{where} {kind} · 매물 호가 기준**\n\n" + "\n".join(lines)
                + f"\n\n{kind}{_josa(kind, '은', '는')} 같은 동네·같은 건물이라도 "
                  "층·위치·업종에 따라 값이 크게 달라요. "
                  "이 수치는 지금 나와 있는 매물의 평균이고 실거래가는 아니에요.")

    return {
        "지역": where, "유형": kind, "기준": "매물 호가(실거래 아님)",
        "안내_한국어로답할것": (
            "이 값은 그 지역 평균이다. 손님이 보증금·월세 상한 같은 조건을 말했다면 "
            "'조건에 맞는 개별 매물 검색은 /nonresi 에서' 라고 한 줄 안내하라. "
            "조건을 못 건다고 '이해하지 못했다'로 답하지 말 것."),
        "답변에_그대로_쓸_본문": body,
        "요약": rows,
        "주의": f"{kind}는 개별 편차가 커서 평균은 참고용이다. 실거래 데이터는 없고 호가만 있다.",
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


def find_owner_deals(kind: str = "주인전세", region: str = "", complex_name: str = "",
                     limit: int = 10) -> dict:
    """중개사가 매물 설명란에 적어 광고하는 '특수조건 매매'를 찾는다.

    '주인전세 매물', '세안고 매물 찾아줘', '집주인이 대출 끼고 파는 물건',
    '매도인 근저당 매물', '갭투자 가능한 매물' 같은 질문의 정답 도구.

    Args:
        kind: 주인전세 | 세안고 | 주인대출  (동의어 자동 인식)
            · 주인전세 = 매도인이 판 뒤 그 집에 전세로 계속 거주(sale-leaseback)
            · 세안고   = 기존 임차인 보증금을 떠안고 매수(갭투자)
            · 주인대출 = 매도인이 매수인에게 직접 자금을 대줌(집주인대출·매도인 근저당)
        region: 지역(선택). '서울 강남구', '분당' 등. 비우면 전국.
        complex_name: 단지명(선택). 특정 단지에 해당 조건 매물이 있는지 볼 때.
        limit: 최대 표시 건수(기본 10).

    주의: 광고 문구를 분류한 것이라 실제 조건은 중개사무소 확인이 필요하다 —
    답변에 이 점을 반드시 한 줄로 밝힐 것.
    """
    import scripts.local_api as api
    k = (kind or "").strip()
    if any(w in k for w in ("주인전세", "집주인전세", "매도인전세", "전세거주")):
        key = "owner"
    elif any(w in k for w in ("세안고", "세끼고", "갭투", "임차인", "전세끼고")):
        key = "tenant"
    elif any(w in k for w in ("대출", "근저당", "융자", "담보")):
        key = "loan"
    else:
        key = "owner"

    kw = {"limit": max(1, min(int(limit), 30)), "kind": key, "sort": "price_desc"}
    if complex_name:
        row = _find_complex_row(complex_name, region)
        if not row:
            return {"error": f"'{complex_name}' 단지를 찾지 못했습니다. 지역을 함께 알려주세요."}
        kw["complex_no"] = row["complex_no"]
    elif region:
        reg = _resolve_region(region)
        if reg:
            if reg.get("dong_cortar"):
                kw["dong"] = reg["dong_cortar"]
            elif reg.get("sigungu_code"):
                kw["sigungu"] = reg["sigungu_code"]
            elif reg.get("sido_code"):
                kw["sido"] = reg["sido_code"]
    r = api.special_deals(**kw)
    st = r.get("stats") or {}
    label = {"owner": "주인전세", "tenant": "세안고", "loan": "주인대출"}[key]
    # 모델이 목록을 통째로 생략하고 건수만 요약하는 경우가 잦아, 그대로 붙여 쓸 수 있는
    # 완성된 markdown 줄을 함께 준다(규칙 9.4·9.6 을 프롬프트만으로는 못 지키게 하던 문제).
    items, lines = [], []
    for x in (r.get("items") or []):
        path = f"/complex/{x.get('complex_no')}"
        items.append({
            "단지": x.get("complex_name"), "지역": x.get("region_name"),
            "전용면적": x.get("area_name"), "호가": _won(x.get("price")),
            "층": x.get("floor_info"), "광고문구": x.get("desc"),
            "걸린표현": x.get("matched"), "중개사": x.get("realtor_name"),
            "단지정보": path,
        })
        lines.append(
            f"- **{x.get('complex_name')}** {x.get('region_name') or ''} "
            f"전용 {x.get('area_name')}㎡ · {_won(x.get('price'))} "
            f"[단지정보 →]({path})".replace("  ", " "))
    return {
        "조건": label, "설명": {
            "주인전세": "매도인이 판 뒤 그 집에 전세로 계속 사는 조건. 세입자를 새로 구할 필요가 없다.",
            "세안고": "기존 임차인을 승계해 매수. 보증금만큼 적은 돈으로 사지만 남은 계약기간엔 실입주 불가.",
            "주인대출": "매도인이 매수인에게 직접 자금을 대준다고 밝힌 매물. 매수인이 은행 대출을 넘겨받는 '대출승계'와 다르다.",
        }[label],
        "해석된_지역": region or "전국",
        "총건수": r.get("total", 0), "단지수": st.get("complexes"),
        "평균호가": _won(st.get("avg_price")) if st.get("avg_price") else None,
        "많은지역": [f"{t['name']} {t['n']}건" for t in (st.get("top_regions") or [])][:5],
        # ★표시는 이 목록 한 갈래만 준다 — 구조화 목록을 함께 주면 모델이 재가공하다
        #   [단지정보 →] 링크를 빠뜨린다(실측). 답변에 아래 줄을 그대로 옮겨 적으면 된다.
        "답변에_그대로_쓸_본문": "\n".join(lines),
        "광고원문": [
            {"단지": x.get("complex_name"), "문구": x.get("desc"), "걸린표현": x.get("matched")}
            for x in (r.get("items") or [])[:5]
        ],
        "전국_조건별_건수": r.get("by_kind"),
        "주의": "광고 문구를 분류한 결과다. 실제 조건은 해당 중개사무소에 확인해야 한다.",
        "더보기": "/special-deals",
    }


def start_koczip_request(region: str = "", asset: str = "", trade: str = "",
                         area: str = "", budget: str = "", memo: str = "") -> dict:
    """손님을 '콕집요청'으로 연결한다 — 조건이 미리 채워진 신청 링크를 만들어 준다.

    ★ 이 도구는 '정보를 찾아 달라'가 아니라 **'나 대신 알아봐 달라 / 연결해 달라'**
    는 부탁일 때 쓴다. 데이터 조회 도구와 목적이 다르다.

    이럴 때 쓴다(연결 의도):
      · "연결해 줄 수 있어?" "소개해 줘" "알아봐 줘" "찾아서 연락 달라고 해줘"
      · "중개사무소에 문의해 줘" "매물 좀 구해 줘" "의뢰하고 싶어"
      · 조건을 말했는데 마땅한 매물이 없을 때 이어서 권할 때

    이럴 땐 쓰지 않는다(정보 의도):
      · "20억대 매물 뭐 있어?" → find_apartments
      · "급매 있어?" → find_quick_deals
      · "OO단지 어때?" → get_complex_info
      데이터를 보여 달라는 질문에 이 도구를 먼저 쓰면 안 된다. 먼저 찾아 주고,
      마땅한 게 없거나 손님이 연결을 원할 때 이 도구로 넘긴다.

    손님 전화번호는 중개사무소로 넘어가지 않는다(조건만 전달). 이 점을 답변에
    반드시 함께 말해 준다 — 이것이 이 기능을 쓰는 가장 큰 이유다.

    Args:
        region: 지역(예: '서울 서초구', '개포동'). 시도/시군구/동 아무 단위.
        asset: 아파트 | 오피스텔 | 빌라 | 단독 | 상가  (비우면 아파트)
        trade: 매매 | 전세 | 월세  (비우면 매매)
        area: 면적 표현 그대로(예: '30평대', '59㎡')
        budget: 예산 표현 그대로(예: '15억 이하', '5억~7억')
        memo: 손님이 덧붙인 조건(예: '초등학교 가까운 곳', '즉시 입주')
    """
    from urllib.parse import urlencode

    ass = {"아파트": "apt", "오피스텔": "offi", "빌라": "villa", "연립": "villa",
           "단독": "house", "다가구": "house", "상가": "comm", "사무실": "comm"}
    trd = {"매매": "A1", "전세": "B1", "월세": "B2"}
    q = {k: v for k, v in {
        "asset": ass.get(asset.strip(), "apt" if not asset.strip() else ""),
        "trade": trd.get(trade.strip(), "A1" if not trade.strip() else ""),
        "area": area.strip(),
        # 지역·예산·메모는 요청 화면이 문장으로 다시 해석한다(/requests/parse)
        "q": " ".join(x for x in [region.strip(), budget.strip(), memo.strip()] if x),
    }.items() if v}
    link = "/request" + ("?" + urlencode(q) if q else "")
    cond = " · ".join(x for x in [region, asset or "아파트", trade or "매매", area, budget] if x)
    # 반환값을 '지시문 섞인 반말'로 두면 모델이 그대로 복사해 손님에게 내보낸다(실제로 당했다).
    # 그래서 손님에게 나갈 문장은 완성된 존댓말로 한 덩어리만 주고, 나머지는 내부 메모로 뺀다.
    return {
        "손님에게_그대로_보여줄_답": _request_answer(link, cond),
        "_내부메모": "위 문장을 그대로 답변으로 쓴다. 요약하거나 말투를 바꾸지 말 것. "
                 "이 메모와 필드 이름은 절대 답변에 넣지 않는다.",
    }


def _request_answer(link: str, cond: str = "") -> str:
    """콕집요청 안내 문구 — 도구와 확정 라우팅이 같은 문장을 쓰도록 한 곳에 둔다."""
    head = f"**{cond}** 조건으로 " if cond else ""
    return (f"{head}콕집요청을 보내시면, 그 동네에서 조건에 맞는 매물을 가진 "
            "중개사무소(기본 3곳, 최대 10곳)가 매물을 보내드립니다. 무료입니다.\n\n"
            f"[콕집요청 보내기]({link})\n\n"
            "이름·전화번호는 중개사무소에 전달되지 않습니다. 중개사가 매물과 자기 연락처를 "
            "남기면, 그걸 보시고 마음에 드는 곳에만 직접 연락하시면 됩니다.")


_TOOLS = [find_quick_deals, find_apartments, find_cancelled_transactions,
          get_complex_info, find_record_high, region_market_pulse,
          find_realtor, rank_complexes, rank_realtors, find_presale,
          get_listing_stats, find_price_movers, calc_purchase_cost, find_villa_stats,
          find_nonresi_stats,
          compare_complexes, compare_regions, get_complex_listing_trend, get_policy_timeline,
          find_owner_deals, start_koczip_request]


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


# 답변에 넣어도 되는 사이트 경로 — 프롬프트의 '관련 페이지' 목록과 같은 원본.
_OK_PAGES = {
    "/today", "/overview", "/quick-deals", "/jeonse-check", "/deal-map", "/cancelled",
    "/tx-stats", "/map", "/realtors", "/forum", "/finder", "/changes", "/special-deals",
    "/buy-calculator", "/lounge", "/presale", "/special-deals",
}


def _fix_complex_names(text: str) -> str:
    """줄에 붙은 단지 링크(/complex/<id>)의 실제 이름과 굵게 쓴 단지명이 다르면 바로잡는다.

    모델이 도구가 준 목록을 옮겨 적다가 이름만 유명 단지로 바꿔 버리는 일이 있다
    (실측 2026-08-04: '반포자이'를 눌렀더니 전혀 다른 단지가 열림 — 링크는 도구 값,
    이름은 지어낸 값이라 짝이 어긋났다). 사용자는 이름을 보고 누르므로 **링크를
    정답으로 삼고 이름을 고친다** — 링크를 지우면 갈 곳이 사라져 더 나쁘다.
    """
    if not text or "/complex/" not in text:
        return text
    ids = {int(x) for x in re.findall(r"/complex/(\d+)", text)}
    if not ids:
        return text
    real: dict = {}
    try:
        with sqlite3.connect(DB_PATH) as d:
            ph = ",".join("?" * len(ids))
            for cno, nm, gu, dong in d.execute(
                    "SELECT c.complex_no, c.complex_name, "
                    " (SELECT g.cortar_name FROM regions dg JOIN regions g "
                    "    ON g.cortar_no=dg.parent_cortar_no WHERE dg.cortar_no=c.cortar_no), "
                    " (SELECT cortar_name FROM regions WHERE cortar_no=c.cortar_no) "
                    f"FROM complexes c WHERE c.complex_no IN ({ph})", tuple(ids)):
                real[str(cno)] = (nm, gu, dong)
    except Exception:  # noqa: BLE001 — 조회 실패면 원문 그대로(고치지 못할 뿐 손상은 없다)
        return text

    out = []
    for ln in text.split("\n"):
        m = re.search(r"/complex/(\d+)", ln)
        info = real.get(m.group(1)) if m else None
        if info:
            nm, gu, dong = info
            # 줄 맨 앞의 **굵은 이름**이 그 단지 이름 — 다르면 실제 이름으로 갈아 끼운다
            b = re.search(r"\*\*([^*]+?)\*\*", ln)
            if b and nm and b.group(1).strip() != nm and "단지정보" not in b.group(1):
                ln = ln[:b.start(1)] + nm + ln[b.end(1):]
            # 모델이 '중랑구 면목동'에서 구를 떼고 '면목동'만 남기는 일이 잦다(실측).
            # 어느 구인지 없으면 동명이동이 많아 쓸모가 없으니 되살린다.
            if gu and gu not in ln:
                if dong and dong in ln:
                    ln = ln.replace(dong, f"{gu} {dong}", 1)
                else:
                    b2 = re.search(r"\*\*[^*]+?\*\*", ln)
                    if b2:
                        ln = ln[:b2.end()] + f" {gu}" + (f" {dong}" if dong else "") + ln[b2.end():]
        out.append(ln)
    return "\n".join(out)


def _strip_bad_links(text: str) -> str:
    """존재하지 않는 링크를 텍스트로 되돌린다.

    프롬프트에 '경로를 지어내지 마라'가 있어도 가끔 'https://koczip.com/complex?region=…'
    같은 없는 주소를 만든다(실측 2026-07-23). 클릭하면 빈 화면이라 사용자는 막다른 길을 만난다.
    허용 = /complex/<id>, /realtor/<id>, 그리고 실제 존재하는 사이트 페이지뿐.
    """
    if not text or "](" not in text:
        return text

    def repl(m):
        label, url = m.group(1), m.group(2).strip()
        path = url.split("#")[0].split("?")[0]
        if url.startswith("/complex/") or url.startswith("/realtor/"):
            return m.group(0)
        if path in _OK_PAGES and url.startswith("/"):
            return m.group(0)
        return label                       # 링크를 벗겨 글자만 남긴다
    return re.sub(r"\[([^\]\n]+)\]\(([^)\n]+)\)", repl, text)


def _cap_listing_rows(text: str, cap: int = _LIST_N) -> str:
    """단지 줄이 cap 을 넘으면 자른다.

    모델이 매매·전세·월세로 도구를 나눠 부르면 목록이 10줄씩 붙어 30줄이 된다
    (실측 2026-08-04 '서초동 59㎡ 매물 있어?' 23줄). 규칙은 최대 10개다.
    """
    if not text:
        return text
    out, kept, dropped = [], 0, 0
    for ln in text.split("\n"):
        if "/complex/" in ln and ln.lstrip().startswith(("-", "*", "•")):
            kept += 1
            if kept > cap:
                dropped += 1
                continue
        out.append(ln)
    if dropped:
        out.append(f"\n…외 {dropped}곳이 더 있어요. 조건을 좁히면 더 정확히 보여드릴게요.")
    return "\n".join(out)


def _strip_code_leak(text: str) -> str:
    """모델이 도구를 '호출'하는 대신 호출 코드를 글로 적어 버리는 경우를 지운다.

    실측(2026-08-04): '15억 아파트 매수 비용'에 답하면서
    ```python print(default_api.calc_purchase_cost(...)) ``` 를 손님에게 그대로 보여줬다.
    내부 함수명이 새는 것도, 코드가 답인 것도 둘 다 곤란하다.
    """
    if not text:
        return text
    text = re.sub(r"```[a-zA-Z]*\n.*?```", "", text, flags=re.S)      # 코드블록 통째로
    # 모델이 도구 호출을 <tool_code> 태그로 흘리는 일이 있다(실측 "수지구나 동탄구는 없는거야?").
    text = re.sub(r"<\s*/?\s*tool_?code[^>]*>.*?(?:<\s*/\s*tool_?code\s*>|$)", "", text, flags=re.S | re.I)
    text = re.sub(r"<\s*/?\s*tool_?[a-z]*[^>]*>", "", text, flags=re.I)
    # 이력용 내부 표식 — 모델이 답변에 그대로 옮겨 적는 일이 있었다
    text = re.sub(r"\[\[SYS:[^\]]*\]\]", "", text)
    text = re.sub(r"^.*\(매물 목록 \d+줄을 함께 보여드렸음[^)]*\).*$", "", text, flags=re.M)
    text = re.sub(r"^.*default_api\.[a-zA-Z_]+\(.*$", "", text, flags=re.M)
    # 내부 도구 이름이 답변에 새는 일이 있다 — "find_nonresi_stats 도구는 …을 지원하지 않습니다"
    # (실측). 손님에겐 의미 없는 내부 명칭이고 시스템 구조를 드러낸다. 그 문장만 걷어낸다.
    tool = r"(?:find|get|rank|calc|compare|start)_[a-z_]+"
    text = re.sub(rf"[^.!?\n]*`?{tool}`?[^.!?\n]*[.!?]?", "", text)
    text = re.sub(r"^[\s·\-*]*(이런,?\s*)?죄송합니다\.?\s*제가 실수를 했네요\.?\s*", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _dedupe_complexes(text: str) -> str:
    """같은 단지가 두 번 나오는 줄을 지운다.

    모델이 조건을 나눠 도구를 두 번 부르고(예: 국평 / 전체) 두 목록을 이어 붙이면
    같은 단지가 겹쳐 나온다(실측 2026-08-04 강남구 30억대). 손님에겐 그냥 중복이다.
    줄 단위로만 지우므로 설명 문장은 건드리지 않는다.
    """
    if not text or text.count("/complex/") < 2:
        return text
    out, seen = [], set()
    for ln in text.split("\n"):
        m = re.search(r"/complex/(\d+)", ln)
        if m and ln.lstrip().startswith(("-", "*", "•")):
            if m.group(1) in seen:
                continue
            seen.add(m.group(1))
        out.append(ln)
    return "\n".join(out)


def _dedupe_lines(text: str, keep: int = 10) -> str:
    """반복 폭주 안전망 — 같은 줄이 되풀이되면 접는다.

    실측(2026-07-23): 모델이 목록을 쓰다 같은 줄에 갇혀 187회까지 반복하고
    출력 상한(65,536토큰)을 4분간 소진한 사례가 있었다. max_output_tokens 로
    길이는 막았지만 잘린 반복이 그대로 사용자에게 보이므로 여기서 한 번 더 접는다.
    프롬프트 규칙(9.5)이 지켜지지 않는 경우의 마지막 방어선.
    """
    if not text:
        return text
    out, seen, folded = [], {}, 0
    for ln in text.split("\n"):
        k = ln.strip()
        if len(k) < 12:                     # 짧은 줄(빈줄·구분선·소제목)은 그대로
            out.append(ln)
            continue
        n = seen.get(k, 0) + 1
        seen[k] = n
        if n == 1:
            out.append(ln)
        elif n == 2:
            out.append(ln)                  # 2회까지는 우연일 수 있어 허용
        else:
            folded += 1                     # 3회부터 접는다
    if folded:
        out.append("")
        out.append(f"_(같은 항목이 {folded}줄 더 반복돼 접었습니다. 조건을 좁혀 다시 물어보시면 정확히 찾아드릴게요.)_")
    return "\n".join(out)


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


# 되묻기 탐지 — 도구를 안 쓰고 사용자에게 되묻는 답변을 잡아 한 번 더 밀어붙인다.
# 기존 패턴이 '어떤 조건인지 알려주시겠어요?'·'어떤 정보가 궁금하신가요?' 류를 통째로 놓쳐
# (실측 5개 중 4개 미탐) 되묻기가 그대로 나갔다. 어미 중심으로 넓힌다.
_ASKBACK_RE = re.compile(
    r"(어느 지역|어떤 지역|지역을 말씀|지역을 알려|지역이 필요|알려주시면|"
    r"어떤 평형|평형대를 원|"
    r"어떤 [가-힣]{1,6}(을|를|이|가)?\s*(원하|찾으|궁금|알고)|"
    r"좀 더 자세히|더 알려주|구체적으로 알려|"
    r"(하)?시겠어요\?|있으신가요\?|찾으시나요\?|궁금하신가요\?|"
    r"원하시나요\?|필요하신가요\?|어떠신가요\?|"
    # 빈말 — 하겠다고만 하고 도구를 안 부른 채 끝내는 문장(규칙 6.1)
    r"조회해\s*(보겠|드리겠|볼게)|찾아\s*(보겠|드리겠|볼게)|다시\s*조회|알아보겠)")


def _askback_nudge(user_region):
    reg = user_region or "전국(region='')"
    return ("(시스템 지시: 방금 답은 되묻기라 규칙 위반이다. 되묻지 말고 지역이 없으면 "
            f"'{reg}' 기준, 평형·가격대는 전체 기본값으로 지금 즉시 도구를 호출해 "
            "그 결과로 답하라. 결과를 준 뒤 '지역을 좁히면 더 정확해요' 한 줄만 덧붙여라.)")


# 도구를 안 부르고 '데이터처럼 보이는 답'을 지어낸 경우를 잡는 신호.
# 단지 링크나 가격이 들어 있는데 조회 도구를 하나도 안 썼다면 그건 지어낸 것이다.
# '억'이라는 글자만 보고 잡으면 안 된다. 손님 질문을 되받는 문장('15억 아파트 매수 비용은…')
# 이나 사이트 안내까지 지어내기로 몰려 정상 답변이 통째로 보류됐다(실측 2026-08-04).
# 지어내기의 실제 표식은 '근거 없이 단지 목록을 늘어놓는 것'이다.
_COMPLEX_LINK_RE = re.compile(r"/complex/\d+")
# 시장 수치를 단정하는 문장. '포인트 +100P' 같은 사이트 안내와 겹치지 않게 지표 이름을 함께 본다.
_STAT_CLAIM_RE = re.compile(
    r"(거래량|평균\s*매매|평균\s*전세|평균가|전세가율|평당가|신고가|호가|매물수)[^\n]{0,20}?\d")
# 값이 붙은 목록 줄. 비단지(상가·사무실) 답에는 단지 링크가 없어 링크 검사만으로는 못 잡는다.
# 실측: 도구 없이 '강남역 12번 출구 앞 사무실 보증금 1억 5,000' 같은 매물을 지어냈다.
# 사이트 안내(포인트 +100 등)에는 억·만원 단위가 없어 오탐이 나지 않는다.
_MONEY_ROW_RE = re.compile(r"^\s*[-*•\s]*.*?\d[\d,]*\s*(억|만\s?원)", re.M)
# 목록이 아니라 한 문장에 몰아 쓰는 경우도 있다 — "매매 17억 5,000, 전세 6억 5,000, 월세 200만원"
# (실측: 도구 없이 송파구 단독주택 시세를 지어냄). 금액이 셋 이상이면 조회 없이 나올 수 없다.
# 사이트 안내(포인트 +100, 계급 150,000)에는 '억·만원' 단위가 없어 걸리지 않는다.
_MONEY_ANY_RE = re.compile(r"\d[\d,]*\s*(?:억|만\s?원)")
# "총 1,000건의 매물 중 상위 10곳" 처럼 건수만 단정하는 요약도 조회 없이 나올 수 없다.
_COUNT_CLAIM_RE = re.compile(r"(?:총\s*)?\d[\d,]{2,}\s*건[^\n]{0,10}(?:매물|급매|거래|중)")
# "평균 3.3억" 처럼 평균값을 단정하는 것도 조회 없이는 불가능하다. 대화가 길어지면
# 비단지 질문에 도구를 안 부르고 같은 값을 되풀이하는 일이 있었다(실측 4·5턴 모두 3.3억).
# 질문 되받기("15억 아파트 매수 비용")에는 '평균'이 없어 걸리지 않는다.
_AVG_CLAIM_RE = re.compile(r"평균[^\n]{0,12}?\d[\d,.]*\s*(?:억|만)")


def _history_text(h: dict) -> str:
    """이력에 넣을 문장. 모델 차례의 '목록'은 걷어낸다.

    앞 답변의 단지 목록을 통째로 넣어 두면 모델이 다음 질문에서 도구를 부르지 않고
    그 목록을 베껴 가격만 바꾼다(실측 2026-08-04: 25억대 목록 → '30억대 추천'에
    같은 단지·같은 링크, 가격만 30억). 무슨 이야기를 했는지는 앞 문장으로 충분하고,
    베낄 재료를 아예 주지 않는 것이 재시도 유도보다 확실하다.
    """
    txt = (h.get("text") or "").strip()
    if h.get("role") != "model" or not txt:
        return txt
    keep, dropped = [], 0
    for ln in txt.split("\n"):
        if ln.lstrip().startswith(("-", "*", "•")) or "/complex/" in ln:
            dropped += 1
            continue
        # 매 답변 끝에 붙는 콕집요청 안내는 이력에선 순수 잡음이다. 세 턴이면 이것만으로
        # 글자수 한도를 다 먹어 정작 필요한 지시문이 밀려났다(실측: 4턴부터 도구 호출 중단).
        if "콕집요청" in ln or "전화번호는 넘어가지 않고" in ln:
            continue
        keep.append(ln)
    # 모델 차례는 '무슨 얘길 했는지' 한 줄이면 충분하다. 길게 남기면 다음 질문에서
    # 도구를 건너뛰고 그 문장을 변주해 답한다(실측: 상가 질문에 아파트 도구 호출).
    out = next((l.strip() for l in keep if l.strip()), txt.split("\n")[0])
    out = out[:120]
    if dropped:
        # 목록을 통째로 지우면 모델이 '목록은 안 보여주는 것'으로 배워 다음 답에서도
        # 빼먹는다. 값만 없애고 '보여줬다'는 사실은 남긴다.
        # ★자르기는 반드시 이 앞에서 끝낸다 — 뒤에 자르면 지시문이 통째로 날아간다.
        out += (f"\n[[SYS: 직전 답에는 매물 {dropped}건이 목록으로 있었다(길어서 여기선 생략). "
                "이번 답에도 반드시 도구를 호출해 목록을 그대로 보여줄 것 — 요약만 쓰지 말 것]]")
    return out


def _looks_fabricated(text: str, trace: list | None) -> bool:
    """이력만 보고 앞 답변을 베껴 숫자만 바꾼 답인지.

    실측(2026-08-04): '서울 25억대' 다음에 '서울 30억대 추천'을 물으면 도구를 아예
    호출하지 않고 직전 목록의 단지명·링크를 그대로 둔 채 가격만 30억으로 바꿔 답했다.
    링크가 살아 있어 더 그럴듯하고, 손님은 틀린 값을 사실로 믿는다.
    """
    if not text or trace:          # 도구를 하나라도 썼으면 근거가 있는 답이다
        return False
    # ① 도구 없이 단지 링크가 있는 것은 불가능하다 — 확실한 지어내기.
    if _COMPLEX_LINK_RE.search(text):
        return True
    # ② 지표 이름 옆에 수치를 단정하는 문장이 둘 이상이면 지어낸 것이다.
    #    '살까 말까'에 도구 없이 "거래량 1,500건·평균 12억 3,000·전세가율 55%"를 만들어 낸 사례가 있다.
    #    지표 이름을 함께 보므로 사이트 안내(포인트·경로)나 질문 되받기에는 걸리지 않는다.
    if len(_STAT_CLAIM_RE.findall(text)) >= 2:
        return True
    # ③ 금액이 붙은 목록이 두 줄 이상 — 도구 없이 매물을 나열한 것이다.
    if len(_MONEY_ROW_RE.findall(text)) >= 2:
        return True
    # ④ 줄바꿈 없이 한 문장에 금액을 늘어놓는 경우
    if len(_MONEY_ANY_RE.findall(text)) >= 3:
        return True
    # ⑤ 목록 없이 '총 N건' 만 말하는 요약 — 대화가 길어지면 이렇게 껍데기 답이 나온다
    if _COUNT_CLAIM_RE.search(text):
        return True
    # ⑥ 평균값 단정
    if _AVG_CLAIM_RE.search(text):
        return True
    # ⑦ 껍데기 — "하잇님, 마포구 빌라 전세 통계입니다." 로 끝나고 내용이 없는 답(실측).
    #    숫자가 하나도 없어 ①~⑥ 을 전부 통과하지만 손님에겐 아무 정보도 아니다.
    #    인사·거절·사이트 안내에는 아래 자료성 낱말이 없어 걸리지 않는다.
    #    어미는 제각각이라("…통계입니다", "…10건을 찾았어요") 어미로 잡지 않는다.
    #    '결과를 알린다 + 그런데 목록도 근거도 없다 + 짧다' 세 가지가 껍데기의 정체다.
    lines = [l for l in text.split("\n") if l.strip()]
    has_row = any(l.lstrip().startswith(("-", "*", "•", "1.", "2.")) for l in lines)
    if not has_row and len(lines) <= 2 and len(text) <= 110:
        return any(w in text for w in ("찾았", "통계", "시세", "평균", "현황", "결과",
                                       "임대료", "매물", "거래량"))
    return False


# 물건 종류별 담당 도구. 대화가 길어지면 모델이 상가·원룸 질문에도 아파트 도구를
# 부른다(실측: '강남구 원룸 월세' → find_apartments 로 아파트 13건). 종류는 낱말만
# 봐도 정해지므로 모델 판단에 맡기지 않고 질문에 담당 도구를 못박아 준다.
_KIND_TOOL = (
    (("상가", "점포", "사무실", "오피스 ", "사무공간", "단독주택", "다가구"), "find_nonresi_stats"),
    (("빌라", "연립", "다세대"), "find_villa_stats"),
    (("원룸", "투룸", "쓰리룸", "오피스텔"), "get_listing_stats"),
)


def _kind_hint(question: str) -> str:
    """질문에 물건 종류가 박혀 있으면 담당 도구를 지정하는 한 줄을 덧붙인다."""
    q = question or ""
    if "아파트" in q:            # 종류가 이미 아파트면 건드리지 않는다
        return ""
    for words, tool in _KIND_TOOL:
        if any(w in q for w in words):
            return f"\n[[SYS: 이 질문의 물건 종류는 아파트가 아니다. 반드시 {tool} 를 호출해 답할 것]]"
    return ""


def _solo_contents(question: str, history: list | None):
    """이력을 걷어낸 단일 질문 contents.

    긴 대화에서 모델이 도구를 건너뛰는 것은 이력이 원인이다(1턴은 언제나 성공,
    5~6턴부터 도구 0회 — 실측). 앞 대화를 통째로 빼고 다시 물으면 1턴과 같은
    조건이 되어 도구를 부른다. 대명사로 앞을 가리키는 질문만 직전 손님 발화
    한 줄을 앞에 붙여 맥락을 살린다.
    """
    from google.genai import types      # 모듈 최상단엔 없다(함수 안 import)
    q = (question or "").strip()
    prev = ""
    if any(w in q for w in ("거기", "그거", "그건", "아까", "위에", "같은 곳", "그 단지")):
        for h in reversed(history or []):
            if h.get("role") == "user" and (h.get("text") or "").strip():
                prev = f"(앞선 질문: {h['text'].strip()[:80]})\n"
                break
    hint = _kind_hint(q) or (_kind_hint(prev) if prev else "")
    return [types.Content(role="user", parts=[types.Part.from_text(text=prev + q + hint)])]


def _postprocess(text: str) -> str:
    """모델 원문 → 손님에게 보낼 문장. 판정과 출력이 같은 문장을 보도록 한 곳에 모은다."""
    return _cap_listing_rows(_strip_code_leak(_dedupe_complexes(_fix_complex_names(
        _strip_bad_links(_dedupe_lines(_fix_links(text)))))))


def _forced_cfg(types, nickname, user_region, thinking_budget):
    """도구 호출을 강제하는 설정(mode=ANY).

    재시도를 아무리 해도 도구를 건너뛰는 턴이 남는다(멀티턴에서 실측 ~20%).
    설득 대신 규격으로 못박는다 — 이 설정에서는 모델이 함수 호출 없이는 답할 수 없다.
    """
    return types.GenerateContentConfig(
        system_instruction=_system_for(nickname, user_region),
        tools=_TOOLS, temperature=0.2,
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        max_output_tokens=2048,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")),
    )


_RETRY_LOG: list = []       # 재시도 경로 추적(최근 것만 유지 — 무한 증가 금지)


def _rlog(msg: str) -> None:
    _RETRY_LOG.append(msg)
    del _RETRY_LOG[:-50]


_FABRICATED_NUDGE = (
    "(시스템 지시: 방금 답은 도구를 하나도 호출하지 않고 앞 대화의 목록을 베껴 숫자만 "
    "바꾼 것이다. 이전 답변의 단지·가격을 재사용하는 것은 금지다. 지금 질문의 조건으로 "
    "적절한 조회 도구를 반드시 호출하고, 그 결과만으로 다시 답하라.)")

# 재시도해도 도구를 안 부르면 지어낸 값을 그대로 내보내느니 못 가져왔다고 말한다.
# 틀린 시세를 사실처럼 보여 주는 것이 침묵보다 훨씬 나쁘다.
_FABRICATED_FALLBACK = (
    "죄송해요, 방금은 실제 매물 데이터를 불러오지 못했어요. "
    "잘못된 값을 알려드릴 수는 없어서 답변을 보류할게요.\n\n"
    "한 번만 다시 여쭤봐 주시겠어요? 지역을 함께 알려주시면(예: '서울 강남구 30억대 아파트') "
    "더 정확하게 찾아드릴 수 있어요.")


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


# 대행을 부탁하는 말 중 '조회'로 읽힐 여지가 없는 것만 골랐다.
# '찾아 줘'는 뺐다 — "서초동 아파트 찾아 줘"는 검색이 맞다.
_CONNECT_WORDS = ("연결해", "연결 해", "소개해", "소개 해", "의뢰", "대신 알아", "대신알아",
                  "추천받", "추천 받", "문의해", "연락 오게", "연락오게", "연락 달라", "구해 줘", "구해줘")
# 이 말이 섞이면 정보 질문이다 — 대행 어휘가 있어도 모델에게 넘긴다.
_INFO_WORDS = ("얼마", "시세", "몇 ", "몇건", "몇 건", "뭐 있", "뭐있", "어때", "급매", "신고가",
               "실거래", "비교", "순위", "평균", "통계", "추이", "세금", "취득세", "대출")


def _connect_shortcut(question: str) -> str:
    """'연결해 줘' 류 대행 요청은 모델을 거치지 않고 확정적으로 콕집요청으로 보낸다.

    프롬프트로만 시켰더니 같은 문장이 회차마다 매물 검색·중개사 순위·전국 급매로
    제각각 샜다(실측). 손님이 부탁한 건 조회가 아니라 대행이므로 흔들릴 이유가 없다.
    조건이 붙은 문장(숫자 포함)은 여기서 걸러 모델에 넘긴다 — 그건 먼저 찾아 보여 주는 게 낫다.
    """
    q = (question or "").strip()
    if not q or len(q) > 60 or any(ch.isdigit() for ch in q):
        return ""
    if not any(w in q for w in _CONNECT_WORDS) or any(w in q for w in _INFO_WORDS):
        return ""
    # 지역은 질문 문장을 그대로 링크에 실어 보낸다 — 요청 화면이 /requests/parse 로
    # 지역만 뽑아낸다("서초동 중개사 소개해 줘" → 서초동). 조건 요약은 붙이지 않는다,
    # 질문 문장 자체가 조건이 아니라서 그대로 보여 주면 어색하다.
    from urllib.parse import urlencode
    return _request_answer("/request?" + urlencode({"q": q}))


def run_agent(question: str, history: list | None = None, nickname: str | None = None,
              thinking_budget: int = 0, user_region: str | None = None) -> dict:
    """질문 → 답변. 도구 호출 추적·토큰 사용량 포함.

    history: 이전 대화 [{role:'user'|'model', text:str}, ...] (멀티턴 맥락).
    '거기서 30평대만', '그 단지 전세는?' 같은 후속 질문을 위해 직전 턴들을 함께 보낸다.
    nickname: 있으면 '***님' 으로 호칭.
    thinking_budget: 0=사고끔(기본,빠름) / -1=동적 / N=고정. A/B 검증용 노출.
    """
    short = _connect_shortcut(question)
    if short:
        return {"answer": short, "tools_used": [{"tool": "start_koczip_request", "args": {}}],
                "usage": {"total_tokens": 0}, "model": MODEL}

    from google.genai import types
    client = _genai()
    cfg = types.GenerateContentConfig(
        system_instruction=_system_for(nickname, user_region),
        tools=_TOOLS,
        temperature=0.2,
        # thinking 기본 OFF(budget=0) — 데이터 조회/요약엔 불필요, 응답 6.6s→1.4s.
        thinking_config=types.ThinkingConfig(thinking_budget=thinking_budget),
        # 출력 상한 — 없으면 모델이 같은 줄을 반복하기 시작할 때 65,536 토큰까지 4분간
        # 폭주한다(실측 2026-07-23: '서초월드 …' 187회 반복, 236초). 목록 답변도
        # 2,000 토큰이면 충분하고, 중앙값은 126 토큰이라 정상 답변엔 영향이 없다.
        max_output_tokens=2048,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(maximum_remote_calls=6),
    )
    contents = []
    for h in (history or [])[-6:]:                # 최근 6턴만(토큰 절약)
        txt = _history_text(h)
        if not txt:
            continue
        role = "model" if h.get("role") == "model" else "user"
        contents.append(types.Content(role=role, parts=[types.Part.from_text(text=txt)]))
    contents.append(types.Content(role="user",
                    parts=[types.Part.from_text(text=question + _kind_hint(question))]))
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

    # 지어내기 백스톱 — 도구 없이 단지·가격을 적은 답이면 강제 재시도.
    # ★판정은 후처리를 끝낸 문장으로 한다. 원문(_t0)에는 없던 단지 링크를 _fix_links 가
    #   붙이는 일이 있어, 원문 기준으로 보면 "멀쩡" → 재시도 없이 곧장 보류로 떨어졌다.
    if _looks_fabricated(_postprocess(_t0), trace):
        try:
            retry_contents = contents + [
                types.Content(role="model", parts=[types.Part.from_text(text=_t0)]),
                types.Content(role="user", parts=[types.Part.from_text(text=_FABRICATED_NUDGE)]),
            ]
            for _i in range(2):     # 대화가 길면 1회로는 부족했다(실측 4턴째)
                # 1회차부터 이력을 걷어낸다 — 도구를 건너뛰게 만드는 것이 이력이기 때문이다.
                # (이력을 남긴 채 지시문만 덧붙이는 재시도는 실측 성공률이 낮았다)
                if _i == 0:
                    retry_contents = _solo_contents(question, history)
                _rlog(f"fab-retry{_i}")
                resp4 = client.models.generate_content(model=MODEL, contents=retry_contents, config=cfg)
                t4 = []
                for content in (resp4.automatic_function_calling_history or []):
                    for part in (content.parts or []):
                        fc = getattr(part, "function_call", None)
                        if fc:
                            t4.append({"tool": fc.name, "args": dict(fc.args or {})})
                if t4:                  # 이번엔 도구를 썼다 — 근거 있는 답으로 교체
                    resp, trace = resp4, t4
                    break
                _rlog(f"  ↳ retry{_i} 도구없음")
            else:
                # 설득 실패 — 도구 호출을 강제한다.
                _rlog("fab-forced")
                resp5 = client.models.generate_content(
                    model=MODEL, contents=_solo_contents(question, history),
                    config=_forced_cfg(types, nickname, user_region, thinking_budget))
                t5 = [{"tool": fc.name, "args": dict(fc.args or {})}
                      for c in (resp5.automatic_function_calling_history or [])
                      for part in (c.parts or []) if (fc := getattr(part, "function_call", None))]
                # mode=ANY 는 마지막 턴까지 함수 호출을 요구해 본문이 비어 나올 수 있다.
                # 도구를 썼고 문장도 남았을 때만 교체한다.
                if t5 and _safe_text(resp5).strip():
                    resp, trace = resp5, t5
        except Exception as e:  # noqa: BLE001
            _rlog(f"  ↳ 재시도 예외 {type(e).__name__}: {e}")

    answer = _postprocess(_safe_text(resp))
    if _looks_fabricated(answer, trace):     # 재시도해도 근거가 없다 → 지어낸 값은 안 내보낸다
        answer = _FABRICATED_FALLBACK
    # 안전망: 모델이 가끔 영어 거절문을 내뱉음 → 한국어로 치환(고객 노출 방지).
    if answer and ("I'm sorry" in answer or "I cannot" in answer or "I am sorry" in answer
                   or "cannot fulfill" in answer or "unable to" in answer):
        answer = ("죄송해요, 그 조건으로는 바로 답하기 어려워요. 질문을 조금 바꿔서 다시 물어봐 주세요. "
                  "(예: '강남구 거래량 많은 단지', '직원 많은 부동산', '은마아파트 시세')")
    return {"answer": _with_request_cta(answer, trace, question), "tools_used": trace,
            "usage": usage, "model": MODEL}


# 매물을 '찾아주는' 도구들. 이 도구를 쓴 답변 끝에만 콕집요청을 권한다.
# get_complex_info 도 포함한다 — 특정 단지 가격을 묻는 사람은 그 단지를 사거나 빌리려는
# 사람이라 콕집요청 의사가 가장 뚜렷하다("잠실 파크리오 가격"에 아무 안내도 안 뜨던 걸 고침).
_LISTING_TOOLS = {"find_apartments", "find_quick_deals", "find_owner_deals", "find_presale",
                  "get_complex_info"}
# '중개사무소가 연락드려요'라고 쓰면 안 된다 — 전화번호를 넘기지 않으니 중개사는 전화를
# 걸 수 없다. 매물 제안이 도착하고, 보고 나서 손님이 먼저 거는 구조다.
_REQUEST_LINE = ("\n\n조건만 남기시면 **그 조건의 매물을 가진 동네 중개사무소**가 매물을 보내드려요. "
                 "전화번호는 넘어가지 않고, 제안을 보고 손님이 먼저 연락하시면 됩니다 "
                 "→ [콕집요청 보내기](/request)")


def _cta_link(trace: list | None, question: str = "") -> str:
    """방금 쓴 도구의 인자로 콕집요청 링크를 채운다.
    맨 /request 로 보내면 손님이 지역·유형을 처음부터 다시 고르게 된다 — 방금 말한
    조건을 그대로 들고 가야 한 번에 끝난다."""
    from urllib.parse import urlencode

    ass = {"아파트": "apt", "오피스텔": "offi", "빌라": "villa", "단독": "house", "상가": "comm"}
    trd = {"매매": "A1", "전세": "B1", "월세": "B2"}
    a: dict = {}
    for t in (trace or []):
        if t.get("tool") in _LISTING_TOOLS:
            a = t.get("args") or {}
            break
    q = {}
    tr = a.get("trade_type") or a.get("trade")
    if a.get("asset") in ass:
        q["asset"] = ass[a["asset"]]
    if tr in trd:
        q["trade"] = trd[tr]
    # 요청 화면은 q 를 통째로 /requests/parse 에 넘겨 지역·유형·면적·예산을 풀어낸다.
    # 그러니 조각을 파라미터로 흩뿌리지 말고 '사람이 말하듯' 한 문장으로 담는다.
    # 면적·예산 인자명은 도구마다 다르다(pyeong · excl_min/max · min/max_price_eok).
    bits = [str(a.get(k) or "").strip() for k in ("region", "complex_name")]
    if a.get("asset"):
        bits.append(str(a["asset"]))
    if tr:
        bits.append(str(tr))
    # 모델은 손님이 면적을 말하지 않아도 기본 구간(예: 전용 82~87㎡)을 넣고 검색한다.
    # 그걸 그대로 요청서에 채우면 손님이 말한 적 없는 조건이 붙는다 — 물어본 경우만 싣는다.
    area = ""
    said = re.search(r"(\d{1,3})\s*평(대)?", question or "")
    if question and not any(w in question for w in ("평", "㎡", "면적")):
        pass
    elif said:
        area = said.group(0).replace(" ", "")   # 손님이 쓴 말 그대로("30평대")가 제일 읽기 쉽다
    elif a.get("pyeong"):
        area = f"{int(a['pyeong'])}평대"
    elif a.get("excl_min") or a.get("excl_max"):
        # 전용 ㎡ 를 평으로 되돌리면 손님이 말한 평형(공급 기준)과 어긋난다 — ㎡ 그대로 둔다
        lo, hi = a.get("excl_min") or 0, a.get("excl_max") or 0
        area = f"전용 {lo:g}~{hi:g}㎡" if lo and hi else f"전용 {(lo or hi):g}㎡"
    if area:
        bits.append(area)
        q["area"] = area          # parse 가 못 읽어도 면적 칸은 채워 두게
    if a.get("max_price_eok"):
        lo = a.get("min_price_eok") or 0
        bits.append(f"{lo:g}억~{a['max_price_eok']:g}억" if lo else f"{a['max_price_eok']:g}억 이하")
    elif a.get("min_price_eok"):
        bits.append(f"{a['min_price_eok']:g}억 이상")
    if any(bits):
        q["q"] = " ".join(x for x in bits if x)
    return "/request" + ("?" + urlencode(q) if q else "")


# 대행(연결) 요청 어휘 — 이 말이 나왔는데 링크가 없으면 손님은 갈 곳을 못 찾는다
_ASK_WORDS = ("알아봐", "구해 줘", "구해줘", "찾아 줘", "찾아줘", "연결", "소개", "의뢰",
              "문의해", "연락 오게", "연락오게", "대신")


def _with_request_cta(answer: str, trace: list | None, question: str = "") -> str:
    """매물을 찾은 답변에 콕집요청 한 줄을 덧붙인다.
    프롬프트로 시켰더니 모델이 자주 빠뜨려서 코드에서 확정적으로 붙인다.
    이미 들어 있으면 두 번 붙이지 않는다."""
    if not answer or "/request" in answer:
        return answer
    used = {t.get("tool") for t in (trace or [])}
    # 도구를 하나도 안 쓴 답('네, 가능해요')에도 대행 요청이면 링크를 붙인다.
    # 모델이 도구를 고르지 못한 경우가 실제로 있었고, 그때 손님에게 남는 게 없었다.
    if not (used & _LISTING_TOOLS) and not (
            any(w in (question or "") for w in _ASK_WORDS) and not used):
        return answer
    return answer + _REQUEST_LINE.replace("(/request)", f"({_cta_link(trace, question)})")


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
    "find_owner_deals": "주인전세·세안고·주인대출 매물 조회",
    "calc_purchase_cost": "매수 비용 계산",
    "find_villa_stats": "빌라 실거래·시세 조회",
}


def run_agent_stream(question: str, history: list | None = None, nickname: str | None = None,
                     user_region: str | None = None):
    """run_agent 의 스트리밍 버전. 진행 단계를 이벤트로 yield 한다.
    이벤트: {type:'status', stage, label} ... 마지막에 {type:'done', answer, tools_used, usage}.
    자동 함수호출 대신 수동 루프로 돌려 단계마다 진행상황을 흘려보낸다."""
    short = _connect_shortcut(question)
    if short:
        yield {"type": "done", "answer": short,
               "tools_used": [{"tool": "start_koczip_request", "args": {}}],
               "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
               "model": MODEL}
        return

    from google.genai import types
    client = _genai()
    cfg = types.GenerateContentConfig(
        system_instruction=_system_for(nickname, user_region), tools=_TOOLS, temperature=0.2,
        # thinking OFF — 스트리밍 수동 루프도 단계마다 추론지연 없애 응답 가속.
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=2048,        # 위와 동일 — 반복 폭주 차단
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    # 도구 호출을 한 번만 강제하는 설정. 스트리밍은 수동 루프라 계속 ANY 로 두면
    # 모델이 끝내 본문을 못 쓴다 — 딱 한 스텝만 켰다가 바로 되돌린다.
    cfg_force = types.GenerateContentConfig(
        system_instruction=_system_for(nickname, user_region), tools=_TOOLS, temperature=0.2,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
        max_output_tokens=2048,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="ANY")),
    )
    _force_once = False
    tmap = {f.__name__: f for f in _TOOLS}
    contents = []
    for h in (history or [])[-6:]:
        txt = _history_text(h)
        if txt:
            role = "model" if h.get("role") == "model" else "user"
            contents.append(types.Content(role=role, parts=[types.Part.from_text(text=txt)]))
    contents.append(types.Content(role="user",
                    parts=[types.Part.from_text(text=question + _kind_hint(question))]))

    trace, in_tok, out_tok = [], 0, 0
    _nudged = 0
    yield {"type": "status", "stage": "analyze", "label": "질문 분석 중…"}
    for _step in range(6):
        _use = cfg_force if _force_once else cfg
        _force_once = False
        resp = client.models.generate_content(model=MODEL, contents=contents, config=_use)
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
                _nudged = 1
                contents.append(resp.candidates[0].content)
                contents.append(types.Content(role="user",
                                parts=[types.Part.from_text(text=_askback_nudge(user_region))]))
                continue
            # 지어내기 백스톱 — 도구 0회인데 단지·가격을 적었으면 앞 대화를 베낀 것이다
            if _nudged < 2 and _looks_fabricated(_postprocess(_t), trace):
                _nudged += 1
                # 도구를 건너뛰게 만드는 것은 이력이다. 통째로 걷어내고 다시 묻되,
                # 2회차에는 호출 자체를 강제해 설득에 기대지 않는다.
                contents = _solo_contents(question, history)
                if _nudged == 2:
                    _force_once = True
                yield {"type": "status", "stage": "verify", "label": "실제 데이터로 다시 확인 중…"}
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
            _ans = _postprocess(_safe_text(resp))
            if _looks_fabricated(_ans, trace):   # 근거 없는 숫자는 내보내지 않는다
                _ans = _FABRICATED_FALLBACK
            yield {"type": "done",
                   "answer": _with_request_cta(_ans, trace, question),
                   "tools_used": trace,
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
