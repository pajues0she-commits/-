# -*- coding: utf-8 -*-
"""공공데이터포털 한국환경공단 NCIS 화학물질(유독물 GHS) 조회 API 연동.

엔드포인트: https://apis.data.go.kr/B552584/kecoapi/ncissbstn
(공공데이터포털에서 활용 신청 후 발급받은 serviceKey 필요)

이 모듈은 API의 정확한 요청 파라미터·응답 필드명이 배포 환경에 따라 다를 수
있다는 점을 감안해 방어적으로 동작한다:
  1. 물질명 검색 파라미터 후보를 순차 시도한다.
  2. 검색이 지원되지 않으면 전체 목록을 페이지 단위로 받아 클라이언트에서
     물질명을 부분일치로 걸러 낸다.
  3. 응답(JSON/XML 모두 지원)에서 물질명·국제연합번호(UN)·그림문자·신호어·
     CAS번호를 키 이름 패턴 매칭으로 추출한다.
"""
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from ghs_data import pictograms_for_codes

BASE_URL = "https://apis.data.go.kr/B552584/kecoapi/ncissbstn"

# 물질명 검색 파라미터 이름 후보 (순차 시도)
_NAME_PARAMS = ["sbstnNmKor", "mttrNmKor", "sbstnNm", "korNm", "chemNm",
                "srchWrd", "searchWord"]

_PIC_KW = [(r"폭발", "GHS01"), (r"인화", "GHS02"), (r"산화", "GHS03"),
           (r"고압\s*가스", "GHS04"), (r"부식", "GHS05"),
           (r"급성\s*독성|해골", "GHS06"), (r"느낌표|감탄", "GHS07"),
           (r"건강\s*유해|호흡기\s*과민", "GHS08"),
           (r"환경\s*유해|수생", "GHS09")]


def _build_url(service_key: str, params: dict) -> str:
    # 포털 발급 키는 이미 URL 인코딩된 형태('%2B' 등 포함)인 경우가 많다 —
    # '%'가 들어 있으면 그대로 쓰고, 아니면 인코딩한다.
    key = service_key.strip()
    if "%" not in key:
        key = urllib.parse.quote(key, safe="")
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    return f"{BASE_URL}?serviceKey={key}&{qs}"


def _http_get(url: str, timeout: int = 15) -> str:
    req = urllib.request.Request(
        url, headers={"Accept": "application/json, application/xml;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", "replace")


def _items_from_json(obj):
    """응답 JSON 어디에 있든 '레코드 목록(dict의 list)'을 찾아 낸다."""
    if isinstance(obj, list):
        if obj and all(isinstance(x, dict) for x in obj):
            return obj
        for x in obj:
            found = _items_from_json(x)
            if found:
                return found
    elif isinstance(obj, dict):
        for key in ("items", "item", "list", "data", "body", "response"):
            if key in obj:
                found = _items_from_json(obj[key])
                if found:
                    return found
        for v in obj.values():
            found = _items_from_json(v)
            if found:
                return found
    return []


def _items_from_xml(text):
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return [], ""
    # 오류 메시지(returnAuthMsg / resultMsg / errMsg) 수집
    err = ""
    for tag in ("returnAuthMsg", "resultMsg", "errMsg", "returnReasonCode"):
        el = root.find(f".//{tag}")
        if el is not None and el.text and "OK" not in el.text.upper() \
                and "NORMAL" not in el.text.upper():
            err = el.text.strip()
            break          # 앞쪽 태그(구체적 메시지)를 우선한다
    items = []
    for item in root.iter("item"):
        d = {}
        for child in item.iter():
            if child is not item and child.text and child.text.strip():
                d[child.tag] = child.text.strip()
        if d:
            items.append(d)
    return items, err


def parse_items(text):
    """응답 본문(JSON 또는 XML) → (레코드 목록, 오류메시지)."""
    t = text.lstrip()
    if t.startswith("{") or t.startswith("["):
        try:
            obj = json.loads(t)
        except ValueError:
            return [], "응답을 해석하지 못했습니다."
        err = ""
        m = re.search(r'"(?:resultMsg|returnAuthMsg|errMsg)"\s*:\s*"([^"]+)"', t)
        if m and "OK" not in m.group(1).upper() and "NORMAL" not in m.group(1).upper():
            err = m.group(1)
        return _items_from_json(obj), err
    return _items_from_xml(t)


def _first_match(item: dict, patterns, korean_only=False):
    for pat in patterns:
        rx = re.compile(pat, re.I)
        for k, v in item.items():
            if not isinstance(v, (str, int)):
                continue
            v = str(v).strip()
            if v and rx.search(k):
                if korean_only and not re.search(r"[가-힣]", v):
                    continue
                return v
    return ""


def extract_entry(item: dict) -> dict:
    """API 레코드/데이터 파일 행 → 표지판 항목 {name, un, pictograms, cas, signal}.

    영문 필드명(API)과 국문 열 이름(메타데이터 CSV/XLSX) 모두 지원한다.
    """
    name = _first_match(item, [r"물질\s*명|국문\s*명|화학물질명",
                               r"nm.*kor|kor.*nm", r"sbstn.*nm|mttr.*nm|chem.*nm",
                               r"(?<!e)nm$|name"], korean_only=True) or \
        _first_match(item, [r"물질\s*명|국문\s*명|화학물질명",
                            r"sbstn.*nm|mttr.*nm|chem.*nm", r"nm$|name"])
    un = ""
    m = re.search(r"\b(\d{4})\b",
                  _first_match(item, [r"유엔|국제\s*연합|un.?(no|num)", r"^un$"]))
    if m:
        un = m.group(1)
    cas = _first_match(item, [r"cas"])
    signal = _first_match(item, [r"신호어|sgnl|signal|snal"])
    if signal and "위험" not in signal and "경고" not in signal:
        signal = ""

    blob = " ".join(str(v) for v in item.values())
    pics = set(re.findall(r"GHS0[1-9]", blob))
    if not pics:
        pic_field = _first_match(item, [r"그림\s*문자|pctg|pictogram|grim|picto"])
        for kw, code in _PIC_KW:
            if re.search(kw, pic_field):
                pics.add(code)
    if not pics:
        h_codes = sorted(set(re.findall(r"H\d{3}", blob)))
        if h_codes:
            pics = set(pictograms_for_codes(h_codes))
    return {"name": name, "un": un, "pictograms": sorted(pics),
            "cas": cas, "signal": signal}


def _contains(item: dict, query: str) -> bool:
    q = re.sub(r"\s+", "", query).lower()
    for v in item.values():
        if q in re.sub(r"\s+", "", str(v)).lower():
            return True
    return False


def load_dataset(filename: str, data: bytes):
    """공공데이터포털에서 내려받은 메타데이터 파일(CSV/XLSX) → 행 dict 목록.

    첫 번째 비어 있지 않은 행을 열 이름으로 사용한다. CSV는 UTF-8(BOM)과
    CP949(EUC-KR) 인코딩을 모두 지원한다.
    """
    rows = []
    if re.search(r"\.xlsx?$|\.xlsm$", filename, re.I):
        import io as _io

        import openpyxl
        wb = openpyxl.load_workbook(_io.BytesIO(data), read_only=True,
                                    data_only=True)
        ws = wb.worksheets[0]
        headers = None
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v).strip() for v in row]
            if not any(vals):
                continue
            if headers is None:
                if sum(1 for v in vals if v) >= 2:
                    headers = vals
                continue
            d = {h: v for h, v in zip(headers, vals) if h and v}
            if d:
                rows.append(d)
        wb.close()
        return rows
    # CSV / TXT
    try:
        text = data.decode("utf-8-sig")
        if text.count("�") > 2:
            raise UnicodeDecodeError("utf-8", b"", 0, 1, "replacement")
    except UnicodeDecodeError:
        text = data.decode("cp949", "replace")
    import csv as _csv
    import io as _io
    headers = None
    for row in _csv.reader(_io.StringIO(text)):
        vals = [v.strip() for v in row]
        if not any(vals):
            continue
        if headers is None:
            if sum(1 for v in vals if v) >= 2:
                headers = vals
            continue
        d = {h: v for h, v in zip(headers, vals) if h and v}
        if d:
            rows.append(d)
    return rows


def search_dataset(rows, name: str):
    """불러온 메타데이터에서 물질명 부분일치 검색 → 표지판 항목 목록."""
    hits = [r for r in rows if _contains(r, name)]
    return [extract_entry(r) for r in hits[:20]]


def search_substance(service_key: str, name: str, max_pages: int = 4):
    """물질명으로 NCIS를 조회해 표지판 항목 후보 목록을 돌려준다.

    반환: (entries, 사용한 URL 설명, 오류메시지). entries가 비어 있으면
    오류메시지를 확인한다.
    """
    name = name.strip()
    last_err = ""
    # 1) 검색 파라미터 후보 순차 시도
    for p in _NAME_PARAMS:
        url = _build_url(service_key,
                         {"pageNo": 1, "numOfRows": 50, "dataType": "JSON", p: name})
        try:
            body = _http_get(url)
        except Exception as e:
            return [], url, f"API 접속 실패: {e}"
        items, err = parse_items(body)
        if err:
            last_err = err
            continue
        if items:
            hits = [it for it in items if _contains(it, name)]
            # 검색이 실제로 반영된 경우(전체 목록이 아니라 걸러진 결과)만 채택
            if hits and (len(items) < 50 or len(hits) < len(items)):
                return [extract_entry(it) for it in hits[:20]], url, ""
    # 2) 전체 목록을 받아 클라이언트에서 필터
    hits = []
    for page in range(1, max_pages + 1):
        url = _build_url(service_key,
                         {"pageNo": page, "numOfRows": 500, "dataType": "JSON"})
        try:
            body = _http_get(url)
        except Exception as e:
            return [], url, f"API 접속 실패: {e}"
        items, err = parse_items(body)
        if err and not items:
            return [], url, f"API 오류: {err}"
        if not items:
            break
        hits += [it for it in items if _contains(it, name)]
        if len(items) < 500:
            break
    if hits:
        return [extract_entry(it) for it in hits[:20]], BASE_URL, ""
    return [], BASE_URL, last_err or "검색 결과가 없습니다."
