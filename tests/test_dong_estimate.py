"""동 추정 — 이름 정규화·표시 규칙 단위 테스트."""
from datetime import date

from collector.dong_estimate import Deal, Est, THRESH, displayable, ndong, rgst_date


def test_ndong_normalizes_registry_and_listing_names():
    assert ndong("101동") == "101"
    assert ndong("제101동") == "101"
    assert ndong("주건축물제3동") == "3"
    assert ndong("래미안 0102") == "102"
    assert ndong("에이") == "A" and ndong("가동") == "A"
    assert ndong("3호") == "3"
    assert ndong("아파트") == "1"
    assert ndong("현대아파트") == "1"          # 단지명만 → 단일동
    assert ndong("101-1") == "1"              # 끝 숫자 우선(백테스트와 동일 동작; 양쪽 다 같은 규칙이라 비교엔 무해)
    assert ndong("") is None and ndong(None) is None


def test_rgst_date():
    assert rgst_date("26.06.26") == date(2026, 6, 26)
    assert rgst_date("") is None and rgst_date(None) is None


def _deal(trade="A1", ct=None):
    return Deal("k", trade, "1", date(2026, 9, 1), 100, 0, 5, 84, ct)


def test_display_rules():
    ok = Est("101", 0.9, "102", 0.1, n_signal=2, ncand=3)
    assert displayable(_deal(), ok)
    # 문턱 미달
    assert not displayable(_deal(), Est("101", THRESH - 0.01, "102", 0.2, 2, 3))
    # 단서 없음 + 후보 2동↑ → 금지(확신도 높아도)
    assert not displayable(_deal(), Est("101", 0.95, "102", 0.05, 0, 2))
    # 단서 없어도 단일동이면 허용
    assert displayable(_deal(), Est("1", 1.0, None, 0.0, 0, 1))
    # 전월세 신규는 매매와 같은 규칙, 갱신·미상은 단일동만
    assert displayable(_deal("B1", "신규"), ok)
    assert not displayable(_deal("B1", "갱신"), ok)
    assert not displayable(_deal("B2", ""), ok)
    assert displayable(_deal("B2", "갱신"), Est("1", 1.0, None, 0.0, 0, 1))
