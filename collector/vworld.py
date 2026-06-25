"""V-WORLD 부동산중개업 조회 — 사무소 정보 수집.

엔드포인트:
  POST https://www.vworld.kr/dtld/broker/dtld_list_s001.do
    필수: sidoCd, sigunguCd
    선택: pageIndex, recordCountPerPage (10/20/50만 동작 확인됨)
  POST https://www.vworld.kr/dtld/broker/dtld_view_d001.do
    필수: sggCd, raRegno, sysRegno

list는 등록번호/상호/소재지/대표자/상태 + sysRegno (detail key),
detail은 전화번호 추가 제공.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Iterator

import httpx
from bs4 import BeautifulSoup

LIST_URL = "https://www.vworld.kr/dtld/broker/dtld_list_s001.do"
DETAIL_URL = "https://www.vworld.kr/dtld/broker/dtld_view_d001.do"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


@dataclass
class BrokerListItem:
    sys_regno: str
    ra_regno: str
    sgg_cd: str
    business_name: str
    address: str | None
    representative: str | None
    registered_ymd: str | None
    status: str | None


@dataclass
class EmployeeRow:
    """직원/공인중개사 행. 개인 식별 PK는 (sys_regno, name, role, position)."""
    sys_regno: str
    ra_regno: str
    sgg_cd: str
    business_name: str
    employee_name: str
    role: str | None       # 공인중개사 / 중개보조원 / 법인
    position: str | None   # 대표 / 일반 / 이사 / 감사
    status: str | None


@dataclass
class BrokerDetail:
    sys_regno: str
    ra_regno: str
    business_name: str | None
    address: str | None
    representative: str | None
    registered_ymd: str | None
    status: str | None
    phone: str | None
    classification: str | None


def new_session() -> httpx.Client:
    c = httpx.Client(
        headers={"User-Agent": UA, "Referer": LIST_URL},
        timeout=30.0,
        follow_redirects=True,
    )
    # warm cookies
    c.get(LIST_URL)
    return c


# href="javascript:fn_goView('11680', '11680-2022-00032', '116802022000037');"
# 직원 모드는 4번째 인자(빈 문자열) 추가됨.
_GOVIEW_RE = re.compile(r"fn_goView\('([^']+)',\s*'([^']+)',\s*'([^']+)'(?:,\s*'[^']*')?\s*\)")


def parse_list(html: str, sgg_cd: str) -> tuple[int, list[BrokerListItem]]:
    """Returns (total_count, items_on_page)."""
    soup = BeautifulSoup(html, "lxml")

    # 총<b>N,NNN</b>건  — total result count
    m = re.search(r"총<b>\s*([\d,]+)\s*</b>", html)
    total = int(m.group(1).replace(",", "")) if m else 0

    items: list[BrokerListItem] = []
    tbody = soup.select_one("table tbody")
    if not tbody:
        return total, items
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 9:
            continue
        link = tr.find("a", href=_GOVIEW_RE)
        if not link:
            continue
        gv = _GOVIEW_RE.search(link.get("href", ""))
        if not gv:
            continue
        row_sgg, ra_regno, sys_regno = gv.group(1), gv.group(2), gv.group(3)
        name = link.get_text(strip=True)
        addr_btn = tds[3].find("button")
        address = addr_btn.get_text(strip=True) if addr_btn else tds[3].get_text(strip=True)
        rep = tds[4].get_text(strip=True)
        reg_ymd = tds[5].get_text(strip=True)
        status_span = tds[6].find("span")
        status = status_span.get_text(strip=True) if status_span else tds[6].get_text(strip=True)
        items.append(BrokerListItem(
            sys_regno=sys_regno,
            ra_regno=ra_regno,
            sgg_cd=row_sgg or sgg_cd,
            business_name=name,
            address=address or None,
            representative=rep or None,
            registered_ymd=reg_ymd or None,
            status=status or None,
        ))
    return total, items


def fetch_list_page(
    client: httpx.Client,
    sido_cd: str,
    sigungu_cd: str,
    page: int,
    page_size: int = 50,
) -> tuple[int, list[BrokerListItem]]:
    data = {
        "sidoCd": sido_cd,
        "sigunguCd": sigungu_cd,
        "pageIndex": str(page),
        "recordCountPerPage": str(page_size),
    }
    r = client.post(LIST_URL, data=data)
    r.raise_for_status()
    return parse_list(r.text, sigungu_cd)


def iter_sigungu(
    client: httpx.Client,
    sido_cd: str,
    sigungu_cd: str,
    page_size: int = 50,
    sleep_s: float = 0.4,
    max_pages: int = 200,
) -> Iterator[BrokerListItem]:
    """Page through brokers. Stops when seen >= total or page is empty.
    벼슬: 일부 row가 파싱에서 빠질 수 있어 page_size 미만 ≠ 마지막 페이지로 가정."""
    page = 1
    seen = 0
    known_total: int | None = None
    while page <= max_pages:
        total, items = fetch_list_page(client, sido_cd, sigungu_cd, page, page_size)
        if known_total is None:
            known_total = total
        if not items:
            break
        for it in items:
            yield it
        seen += len(items)
        # 명확한 종료: known total 도달 또는 페이지가 비었을 때만
        if known_total and seen >= known_total:
            break
        page += 1
        time.sleep(sleep_s)


def parse_employee_list(html: str, sgg_cd: str) -> tuple[int, list[EmployeeRow]]:
    """직원 list 페이지 파싱. 컬럼: 성명/상호/구분/직위/상태/시작/종료."""
    soup = BeautifulSoup(html, "lxml")
    m = re.search(r"총<b>\s*([\d,]+)\s*</b>", html)
    total = int(m.group(1).replace(",", "")) if m else 0
    items: list[EmployeeRow] = []
    tbody = soup.select_one("table tbody")
    if not tbody:
        return total, items
    for tr in tbody.find_all("tr"):
        tds = tr.find_all("td", recursive=False)
        if len(tds) < 6:
            continue
        link = tr.find("a", href=_GOVIEW_RE)
        if not link:
            continue
        gv = _GOVIEW_RE.search(link.get("href", ""))
        if not gv:
            continue
        row_sgg, ra_regno, sys_regno = gv.group(1), gv.group(2), gv.group(3)
        emp_name = tds[1].get_text(strip=True)
        biz_name = tds[2].get_text(strip=True)
        role = tds[3].get_text(strip=True)
        position = tds[4].get_text(strip=True)
        status_span = tds[5].find("span")
        status = status_span.get_text(strip=True) if status_span else tds[5].get_text(strip=True)
        items.append(EmployeeRow(
            sys_regno=sys_regno,
            ra_regno=ra_regno,
            sgg_cd=row_sgg or sgg_cd,
            business_name=biz_name,
            employee_name=emp_name,
            role=role or None,
            position=position or None,
            status=status or None,
        ))
    return total, items


def fetch_employees_page(
    client: httpx.Client,
    sido_cd: str,
    sigungu_cd: str,
    page: int,
    page_size: int = 50,
) -> tuple[int, list[EmployeeRow]]:
    data = {
        "sidoCd": sido_cd,
        "sigunguCd": sigungu_cd,
        "pageIndex": str(page),
        "recordCountPerPage": str(page_size),
        "svcCode": "118",  # 직원/공인중개사 모드
    }
    r = client.post(LIST_URL, data=data)
    r.raise_for_status()
    return parse_employee_list(r.text, sigungu_cd)


def iter_employees_sigungu(
    client: httpx.Client,
    sido_cd: str,
    sigungu_cd: str,
    page_size: int = 50,
    sleep_s: float = 0.0,
    max_pages: int = 500,
) -> Iterator[EmployeeRow]:
    page = 1
    seen = 0
    known_total: int | None = None
    while page <= max_pages:
        total, items = fetch_employees_page(client, sido_cd, sigungu_cd, page, page_size)
        if known_total is None:
            known_total = total
        if not items:
            break
        for it in items:
            yield it
        seen += len(items)
        if known_total and seen >= known_total:
            break
        page += 1
        if sleep_s > 0:
            time.sleep(sleep_s)


def parse_detail(html: str) -> dict:
    """Extracts fields from <dl><dt>label</dt><dd>value</dd>...</dl> block."""
    soup = BeautifulSoup(html, "lxml")
    out: dict[str, str | None] = {}
    for dl in soup.find_all("dl"):
        dts = dl.find_all("dt")
        dds = dl.find_all("dd")
        for dt, dd in zip(dts, dds):
            k = dt.get_text(strip=True)
            v = " ".join(dd.get_text(separator=" ", strip=True).split())
            out[k] = v
    return out


def fetch_detail(
    client: httpx.Client,
    sgg_cd: str,
    ra_regno: str,
    sys_regno: str,
) -> BrokerDetail:
    data = {"sggCd": sgg_cd, "raRegno": ra_regno, "sysRegno": sys_regno}
    r = client.post(DETAIL_URL, data=data)
    r.raise_for_status()
    d = parse_detail(r.text)
    # 등록번호 / 대표자 / 구분 / 소재지 / 전화번호 / 등록상태 / 등록일자
    return BrokerDetail(
        sys_regno=sys_regno,
        ra_regno=d.get("등록번호") or ra_regno,
        business_name=d.get("상호") or None,
        address=d.get("소재지") or None,
        representative=d.get("대표자") or None,
        registered_ymd=(d.get("등록일자") or "").replace(".", "-") or None,
        status=d.get("등록상태") or None,
        phone=d.get("전화번호") or None,
        classification=d.get("구분") or None,
    )
