"""실거래 매칭 — 동 불일치 차단·aptSeq 지도·이름 조각+면적 (2026-11-12).

python3 tests/test_realprice_matching.py  또는  pytest tests/test_realprice_matching.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collector.realprice import matching as m  # noqa: E402


def cx(no, name, dong, addr, areas=(), road="", offi=False):
    return {"complex_no": no, "complex_name": name, "cortar_no": "4113510200", "detail_address": addr,
            "road_address_norm": m.normalize_road(road), "dong_name": dong, "variants": m.name_variants(name),
            "is_offi": offi, "tokens": m.name_tokens(name), "areas": list(areas)}


PURUN = cx("2063", "푸른벽산,신성,쌍용", "수내동", "71", (59.78, 84.72, 101.82, 131.4, 139.68, 163.83, 176.77))
KKACHI = cx("9230", "까치마을우방,우성", "구미동", "75", (191.94, 192.28))
YANGJI = cx("2100", "양지마을금호1단지", "수내동", "80", (84.9, 101.9))


def tx(name, umd, jibun, excl, seq=""):
    return {"aptNm": name, "umdNm": umd, "sggCd": "41135", "jibun": jibun, "excluUseAr": str(excl), "aptSeq": seq}


def run(t, complexes, seq_map=None):
    return m.match_one(t, m.ComplexIndex(complexes, seq_map=seq_map))


def test_crossdong_jibun_rejected_and_token_area_matches():
    # 수내동 75 쌍용 거래가 구미동 75 까치마을로 가던 버그
    assert run(tx("푸른마을(쌍용)", "수내동", "75", 59.78), [PURUN, KKACHI, YANGJI])[:2] == ("2063", "token+dong+area")


def test_multi_jibun_sinseong():
    assert run(tx("푸른마을(신성)", "수내동", "73", 84.72), [PURUN, KKACHI])[0] == "2063"


def test_same_dong_jibun_still_matches():
    assert run(tx("까치마을(우방)", "구미동", "75", 191.94), [PURUN, KKACHI])[:2] == ("9230", "jibun+dong")


def test_rural_ri_naming_kept():
    c = cx("5", "아주", "북평면", "455-1")
    assert run(tx("아주빌라", "북평면 남창리", "455-1", 59.0), [c])[:2] == ("5", "jibun")


def test_empty_umd_keeps_jibun():
    assert run(tx("아무개", "", "75", 59.0), [KKACHI])[0] == "9230"


def test_token_area_mismatch_not_matched():
    # 이름 조각은 맞지만 면적이 평형표에 없으면 붙이지 않는다
    assert run(tx("푸른마을(쌍용)", "수내동", "75", 45.0), [PURUN, KKACHI])[0] is None


def test_token_ambiguous_not_matched():
    other = cx("3000", "쌍용,한양", "수내동", "90", (59.78,))
    assert run(tx("푸른마을(쌍용)", "수내동", "75", 59.78), [PURUN, other])[0] is None


def test_seq_rule_overrides_everything():
    # 규칙은 지번 일치보다 먼저 — 사람이 확정한 것
    r = run(tx("까치마을(우방)", "구미동", "75", 191.94, seq="41135-1"), [PURUN, KKACHI], {"41135-1": ("2063", "rule")})
    assert r[:2] == ("2063", "seq_rule")


def test_seq_consensus_after_jibun():
    smap = {"41135-79": ("2063", "consensus")}
    # 지번이 마스터에 없는 다지번 단지: 합의로 붙는다
    assert run(tx("다른표기", "수내동", "73", 84.72, seq="41135-79"), [PURUN, KKACHI], smap)[:2] == ("2063", "seq")
    # 지번+동이 맞으면 지번이 먼저(합의는 보조)
    assert run(tx("까치마을(우방)", "구미동", "75", 191.94, seq="41135-79"), [PURUN, KKACHI], smap)[:2] == ("9230", "jibun+dong")


def test_exact_name_other_dong_rejected():
    c = cx("7", "신동아", "쌍문동", "1")
    assert run(tx("신동아", "방학동", "999", 84.0), [c])[0] is None


def test_digits_block_wrong_number():
    # 상계주공7(고층)이 도로명+이름으로 상계주공2단지에 붙던 것
    c2 = cx("203", "상계주공2단지", "상계동", "746-5", road="동일로 1")
    c7 = cx("921", "상계주공7단지", "상계동", "692", road="동일로 1")
    t = tx("상계주공7(고층)", "상계동", "691", 49.0)
    t["roadNm"] = "동일로"
    assert run(t, [c2, c7])[0] == "921"
    assert run(t, [c2])[0] is None


def test_token_requires_same_number():
    base = cx("114809", "e편한세상서울대입구", "봉천동", "1", (84.98,))
    two = cx("108126", "e편한세상서울대입구2차", "봉천동", "2", (59.0,))
    r = run(tx("e편한세상서울대입구2단지", "봉천동", "999", 84.98), [base, two])
    assert r[0] != "114809"


def test_token_ambiguous_before_area():
    a = cx("25272", "에이원(392-58)", "화곡동", "392-58", (40.0,))
    b = cx("142254", "에이원(46-120)", "화곡동", "46-120", (59.06,))
    assert run(tx("에이원B둥", "화곡동", "999", 59.06), [a, b])[1] != "token+dong+area"


def test_myeon_to_eup_promotion():
    c = cx("109248", "대구국가산단반도유보라아이비파크", "구지면", "100")
    assert run(tx("대구국가산단반도유보라아이비파크", "구지읍 응암리", "100", 84.0), [c])[0] == "109248"


def test_road_unique_needs_related_name():
    c = cx("18623", "노빌리안골드", "상계동", "734-3", road="동일로 2")
    t = tx("상계주공6(고층)", "상계동", "720", 58.0)
    t["roadNm"] = "동일로"
    assert run(t, [c])[0] is None


def test_name_digits():
    assert m.name_digits("상계주공7(고층)") == {"7"}
    assert m.name_digits("대아(740)") == set()
    assert m.name_digits("광해리드빌(102동)") == set()
    assert m.name_digits("래미안2차") == {"2"}


def test_comma_numbers_and_boundary():
    assert m.name_digits("이화1,2차") == {"1", "2"}
    assert m.digits_compatible("이화2차", "이화1,2차")
    assert m.digits_compatible("수원아이파크시티6단지", "수원아이파크시티5,6단지")
    assert m.names_related("용상4주공", "주공4단지")
    # 지번·이름이 같고 동 표기만 다르면(경계 단지) 붙인다
    c = cx("143069", "평택지제역자이", "세교동", "100")
    assert run(tx("평택지제역자이", "동삭동", "100", 84.0), [c])[:2] == ("143069", "jibun+name")
    # 이름이 다르면 여전히 거부(푸른마을 쌍용 ↔ 까치마을)
    assert run(tx("푸른마을(쌍용)", "수내동", "75", 191.94), [KKACHI])[0] is None


def test_weak_steps_need_number():
    c = cx("128264", "힐스테이트호매실", "호매실동", "1")
    assert run(tx("수원호매실휴먼시아7단지아파트", "호매실동", "999", 46.66), [c])[0] is None


def test_whole_name_exception():
    c = cx("110001", "래미안포레스티지", "반포동", "1", (59.9, 84.9))
    assert run(tx("래미안포레스티지2단지", "반포동", "999", 84.9), [c])[0] == "110001"
    # 형제 단지(번호만 다름)가 있으면 예외 없음
    sib = cx("110002", "래미안포레스티지2단지", "반포동", "2", (59.0,))
    assert run(tx("래미안포레스티지3단지", "반포동", "999", 84.9), [c, sib])[0] is None
    # 면적이 안 맞으면 예외 없음
    assert run(tx("래미안포레스티지2단지", "반포동", "999", 30.0), [c])[0] is None


def test_name_tokens():
    assert m.name_tokens("푸른벽산,신성,쌍용") == {"푸른벽산", "신성", "쌍용"}
    assert m.name_tokens("푸른마을(신성)") == {"푸른마을", "신성"}
    assert m.name_tokens("광해리드빌(102동,주상복합)") == {"광해리드빌"}


if __name__ == "__main__":
    fails = 0
    for k, f in list(globals().items()):
        if k.startswith("test_") and callable(f):
            try:
                f(); print("PASS", k)
            except AssertionError as e:  # noqa: PERF203
                fails += 1; print("FAIL", k, e)
    sys.exit(1 if fails else 0)


def test_incheon_old_gu_loads_new_codes():
    """인천 옛 서구(28260) 거래 재매칭 — 단지는 신코드(서해 석남동·검단 불로동)에 있다."""
    import sqlite3
    conn = sqlite3.connect(":memory:")
    conn.executescript(
        "CREATE TABLE complexes(complex_no, complex_name, cortar_no, detail_address, road_address, real_estate_type_name);"
        "CREATE TABLE regions(cortar_no, cortar_name);"
        "CREATE TABLE complex_areas(complex_no, exclusive_area);"
        "INSERT INTO regions VALUES('2827510800','석남동'),('2829011000','불로동');"
        "INSERT INTO complexes VALUES('122809','트윈팰리스','2827510800','498-1','','오피스텔'),"
        "('170298','검단중흥S-클래스에듀파크','2829011000','498','','아파트분양권');")
    cs = m.load_complexes(conn, cortar_prefix="28260")
    assert {c["complex_no"] for c in cs} == {"122809", "170298"}
    def itx(*a):
        return {**tx(*a), "sggCd": "28260"}
    assert run(itx("트윈팰리스", "석남동", "498", 68.92), cs)[0] != "170298"
    # 지번 색인이 옛 코드(28260)로 걸려 있어야 지번 단계가 동작한다
    r = run(itx("검단중흥에듀파크", "불로동", "498", 84.9), cs)
    assert r[0] == "170298" and r[1].startswith("jibun"), r
