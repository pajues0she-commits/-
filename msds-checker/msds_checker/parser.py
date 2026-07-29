"""MSDS 파일(PDF/TXT)에서 연도, 제조사, 구성성분을 추출한다.

한국 고용노동부 고시 양식(16개 항목)과 일반적인 영문 SDS 양식을 함께 지원한다.
  - 1항: 화학제품과 회사에 관한 정보 → 제조사/공급자
  - 3항: 구성성분의 명칭 및 함유량 → 성분명, CAS 번호, 함유량
  - 개정일/작성일(주로 16항) 또는 파일명에서 연도를 추출
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field


@dataclass
class Ingredient:
    name: str
    cas: str  # CAS 번호. 없으면 빈 문자열
    content: str  # 함유량(%) 표기 원문. 없으면 빈 문자열

    def key(self) -> str:
        """비교용 키: CAS 번호가 있으면 CAS, 없으면 정규화한 성분명."""
        return self.cas if self.cas else normalize_name(self.name)


@dataclass
class MsdsRecord:
    path: str
    year: int | None = None       # 기준연도 (등록 시 도입일자의 연도로 설정됨)
    doc_year: int | None = None   # MSDS 문서 자체의 개정/작성 연도 (참고용)
    product: str = ""
    manufacturer: str = ""
    ingredients: list[Ingredient] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def filename(self) -> str:
        return os.path.basename(self.path)


# ---------------------------------------------------------------- 텍스트 추출

def extract_text(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError(
                "PDF를 읽으려면 pypdf가 필요합니다. 'pip install pypdf'로 설치하세요."
            ) from e
        reader = PdfReader(path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    # txt 등 텍스트 파일: 한국 문서에서 흔한 인코딩을 순서대로 시도
    for enc in ("utf-8", "cp949", "euc-kr", "utf-16"):
        try:
            with open(path, encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


# ---------------------------------------------------------------- CAS 번호

_CAS_RE = re.compile(r"\b(\d{2,7})-(\d{2})-(\d)\b")


def is_valid_cas(cas: str) -> bool:
    """CAS 번호 체크섬 검증(마지막 자리 = 가중합 mod 10)."""
    m = re.fullmatch(r"(\d{2,7})-(\d{2})-(\d)", cas)
    if not m:
        return False
    digits = m.group(1) + m.group(2)
    check = int(m.group(3))
    total = sum(int(d) * w for w, d in enumerate(reversed(digits), start=1))
    return total % 10 == check


# ---------------------------------------------------------------- 섹션 분리

_SECTION_RE = re.compile(
    r"^\s*(?:제\s*)?(\d{1,2})\s*(?:항|[.)：:])?\s*"
    r"(?:화학제품과\s*(?:제조\s*)?회사|유해성|구성성분|응급조치|폭발|누출|취급|노출|물리화학|안정성"
    r"|독성|환경|폐기|운송|법적|그\s*밖의|기타|SECTION|Identification|Composition)",
    re.IGNORECASE | re.MULTILINE,
)


def _split_sections(text: str) -> dict[int, str]:
    """섹션 번호 → 해당 섹션 본문. 헤더를 찾지 못하면 빈 dict."""
    matches = list(_SECTION_RE.finditer(text))
    sections: dict[int, str] = {}
    for i, m in enumerate(matches):
        num = int(m.group(1))
        if not 1 <= num <= 16:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        # 같은 번호가 여러 번 나오면(목차 등) 더 긴 본문을 채택
        body = text[m.start():end]
        if num not in sections or len(body) > len(sections[num]):
            sections[num] = body
    return sections


# ---------------------------------------------------------------- 연도 추출

_DATE_LABEL_RE = re.compile(
    r"(?:최종\s*)?(?:개정|작성|발행|제정|revision|revised|issue)"
    r"[^\n0-9]{0,20}[:：]?[^\n]{0,15}?"
    r"((?:19|20)\d{2})\s*[.\-/년]",
    re.IGNORECASE,
)
_FILENAME_YEAR_RE = re.compile(r"(?<!\d)((?:19|20)\d{2})(?!\d)")


def extract_year(text: str, path: str) -> tuple[int | None, str]:
    """(연도, 출처 설명)을 반환. 개정일 > 작성일 순으로 문서에서 찾고, 없으면 파일명."""
    years = [int(m.group(1)) for m in _DATE_LABEL_RE.finditer(text)]
    if years:
        # 개정을 거듭한 문서는 여러 날짜가 있으므로 가장 최근 연도를 문서 연도로 본다
        return max(years), "문서의 개정/작성일"
    m = _FILENAME_YEAR_RE.search(os.path.basename(path))
    if m:
        return int(m.group(1)), "파일명"
    return None, ""


# ---------------------------------------------------------------- 제조사 추출

# 불릿에 라틴문자 O/o를 쓰는 문서(예: "O 회 사 명 : …")가 있고,
# 라벨 글자 사이에 공백을 넣는 경우("회 사 명")도 흔하다.
_MFR_LABEL_RE = re.compile(
    r"^[\s○◦•·\-①-⑳Oo]*(?:[가나다]\s*[.)])?\s*"
    r"(?:제\s*조\s*(?:회\s*사|업\s*체|자|사)?|공\s*급\s*(?:업\s*체|자|원)?"
    r"|수\s*입\s*(?:업\s*체|자)?|회\s*사|업\s*체)\s*"
    r"(?:명\s*칭|명|정\s*보)?\s*[:：]\s*(.+)$",
    re.MULTILINE,
)
_MFR_LABEL_EN_RE = re.compile(
    r"^[\s\-•]*(?:company(?:\s*name)?|manufacturer|supplier)\s*[:：]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)
_PRODUCT_RE = re.compile(
    r"^[\s○◦•·\-①-⑳Oo]*(?:[가나다]\s*[.)])?\s*"
    r"(?:제\s*품\s*(?:명\s*칭|명)|물\s*질\s*명|product\s*name)\s*[:：]\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)

# 회사명 뒤에 같은 줄로 이어지는 다른 라벨(사업장명, 담당부서, 전화 등)을 잘라낸다
_MFR_TAIL_RE = re.compile(
    r"\s{2,}.*$|\s*(?:사\s*업\s*장\s*명|담\s*당\s*부\s*서|주\s*소|전\s*화|TEL|FAX)\s*[:：].*$",
    re.IGNORECASE,
)


def _clean_company(raw: str) -> str:
    return _MFR_TAIL_RE.sub("", raw.strip()).strip(" ,·-")


def extract_manufacturer(text: str, sections: dict[int, str]) -> str:
    scope = sections.get(1, text)
    for regex in (_MFR_LABEL_RE, _MFR_LABEL_EN_RE):
        m = regex.search(scope)
        if m:
            return _clean_company(m.group(1))
    # 1항에서 못 찾았으면 문서 전체에서 한 번 더
    if scope is not text:
        for regex in (_MFR_LABEL_RE, _MFR_LABEL_EN_RE):
            m = regex.search(text)
            if m:
                return _clean_company(m.group(1))
    return ""


def extract_product(text: str, sections: dict[int, str]) -> str:
    m = _PRODUCT_RE.search(sections.get(1, text)) or _PRODUCT_RE.search(text)
    return m.group(1).strip() if m else ""


def normalize_company(name: str) -> str:
    """법인 접미사·공백·괄호 표기를 제거해 실질 상호만 남긴다."""
    s = name.strip().lower()
    s = re.sub(
        r"주식회사|유한회사|\(주\)|㈜|\bco\.?,?\s*ltd\.?|\binc\.?"
        r"|\bcorp(?:oration)?\.?|\bllc\b|\bgmbh\b|[()\[\]]",
        "", s,
    )
    s = re.sub(r"[\s.,·\-_/]+", "", s)
    return s


def normalize_name(name: str) -> str:
    return re.sub(r"[\s.,·\-_/()]+", "", name.strip().lower())


# ---------------------------------------------------------------- 성분 추출

# CAS 뒤에 오는 함유량 표기: "10-20", "≤ 5", "60~70 %", "잔량" 등
_CONTENT_RE = re.compile(
    r"((?:[<>≤≥약]?\s*\d+(?:\.\d+)?\s*(?:[-~–]\s*\d+(?:\.\d+)?)?\s*%?)|잔량|balance)",
    re.IGNORECASE,
)
_NOISE_NAME_RE = re.compile(
    r"^(?:화학물질명|관용명|이명|성분명|분자식|cas(?:\s*no\.?|\s*번호)?"
    r"|번호|함유량(?:\(%\))?|no\.?|명칭"
    r"|msds\b.*|material\s*safety\s*data\s*sheet.*|물질안전보건자료.*)$",
    re.IGNORECASE,
)


def _scan_lines(lines: list[str]) -> list[Ingredient]:
    """줄 단위 스캔: 'CAS 번호가 있는 줄'에서 성분명·함유량을 뽑는다."""
    ingredients: list[Ingredient] = []
    seen: set[str] = set()
    for idx, line in enumerate(lines):
        for m in _CAS_RE.finditer(line):
            cas = m.group(0)
            if not is_valid_cas(cas):
                continue
            name = line[: m.start()].strip(" \t|,;:·-")
            # 표가 줄바꿈으로 깨져 이름이 앞줄에 있는 경우
            if (not name or _NOISE_NAME_RE.match(name)) and idx > 0:
                prev = lines[idx - 1].strip(" \t|,;:·-")
                if prev and not _CAS_RE.search(prev) and not _NOISE_NAME_RE.match(prev):
                    name = prev
            if _NOISE_NAME_RE.match(name):
                name = ""
            rest = line[m.end():]
            cm = _CONTENT_RE.search(rest)
            content = cm.group(1).strip() if cm else ""
            if cas in seen:
                continue
            seen.add(cas)
            ingredients.append(Ingredient(name=name, cas=cas, content=content))
    return ingredients


# 뒤섞인 표 재조합용: 한 줄 전체가 함유량 값인 경우 ("12.6", "40 - 50 %", "잔량" 등)
_LONE_CONTENT_RE = re.compile(
    r"^(?:[<>≤≥약]?\s*\d+(?:\.\d+)?\s*(?:[-~–]\s*\d+(?:\.\d+)?)?\s*%?|잔량|balance)$",
    re.IGNORECASE,
)
_TABLE_KEYWORD_RE = re.compile(r"함유량|함량|CAS\s*번호|화학물질명", re.IGNORECASE)


def _content_value_ok(s: str) -> bool:
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    return all(0 < n <= 100 for n in nums) if nums else True


def _pair_scrambled_table(lines: list[str]) -> dict[str, str]:
    """PDF 표가 열 단위로 흩어져 나온 경우, 홀로 떨어진 CAS 줄과 함유량 줄을
    줄 간 거리 기준으로 짝지어 {CAS: 함유량}을 복원한다.

    오인식을 줄이기 위해 '함유량/CAS번호' 등 표 머리글 근처(±20줄)의 값만 쓴다.
    """
    keyword_idx = [i for i, l in enumerate(lines) if _TABLE_KEYWORD_RE.search(l)]
    if not keyword_idx:
        return {}

    def near_table(i: int) -> bool:
        return any(abs(i - k) <= 20 for k in keyword_idx)

    cas_lines = [
        (i, l) for i, l in enumerate(lines)
        if _CAS_RE.fullmatch(l) and is_valid_cas(l) and near_table(i)
    ]
    content_lines = [
        (i, l) for i, l in enumerate(lines)
        if not _CAS_RE.fullmatch(l) and _LONE_CONTENT_RE.match(l)
        and _content_value_ok(l) and near_table(i)
    ]
    # (거리, CAS줄, 값줄) 조합을 거리 오름차순으로 탐욕 매칭 (거리 12줄 이내)
    pairs = sorted(
        (abs(ci - vi), ci, vi)
        for ci, _ in cas_lines for vi, _ in content_lines if abs(ci - vi) <= 12
    )
    cas_by_idx = dict(cas_lines)
    val_by_idx = dict(content_lines)
    result: dict[str, str] = {}
    used_cas: set[int] = set()
    used_val: set[int] = set()
    for _, ci, vi in pairs:
        if ci in used_cas or vi in used_val:
            continue
        cas = cas_by_idx[ci]
        if cas not in result:
            result[cas] = val_by_idx[vi]
        used_cas.add(ci)
        used_val.add(vi)
    return result


_KNOWN_CAS_NAMES = {"7732-18-5": "물"}
_HEADER_CAS_RE = re.compile(r"CAS\s*(?:No\.?|번호)\s*[:：]?\s*(\d{2,7}-\d{2}-\d)", re.IGNORECASE)
_PCT_SUFFIX_RE = re.compile(r"\s*\d+(?:\.\d+)?\s*%|\(\s*\)")


def _doc_main_cas(text: str) -> str:
    """문서 머리글에 반복 표기되는 대표 CAS 번호(가장 자주 나온 것)."""
    counts: dict[str, int] = {}
    for m in _HEADER_CAS_RE.finditer(text):
        if is_valid_cas(m.group(1)):
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return max(counts, key=counts.get) if counts else ""


def extract_ingredients(text: str, sections: dict[int, str],
                        product: str = "") -> list[Ingredient]:
    scope = sections.get(3, "")
    ingredients = _scan_lines(scope.splitlines()) if scope else []
    if not ingredients:
        # 3항이 없거나 표 내용이 3항 밖으로 밀려난 경우 문서 전체에서 재시도
        ingredients = _scan_lines(text.splitlines())

    # 함유량을 하나도 못 얻었으면 뒤섞인 표 복원을 시도해 보완한다
    if not any(i.content for i in ingredients):
        lines = [l.strip() for l in text.splitlines()]
        recovered = _pair_scrambled_table(lines)
        by_cas = {i.cas: i for i in ingredients}
        for cas, content in recovered.items():
            if cas in by_cas:
                by_cas[cas].content = by_cas[cas].content or content
            else:
                ingredients.append(Ingredient(name="", cas=cas, content=content))

    # 이름이 빈 성분에 알려진 이름(물 등)·대표성분(제품명 기반)을 채운다
    main_cas = _doc_main_cas(text)
    main_name = _PCT_SUFFIX_RE.sub("", product).strip(" ,·-") if product else ""
    for ing in ingredients:
        if ing.name:
            continue
        if ing.cas in _KNOWN_CAS_NAMES:
            ing.name = _KNOWN_CAS_NAMES[ing.cas]
        elif ing.cas == main_cas and main_name:
            ing.name = main_name
    return ingredients


# ---------------------------------------------------------------- 통합 파서

def parse_file(path: str) -> MsdsRecord:
    rec = MsdsRecord(path=path)
    try:
        text = extract_text(path)
    except Exception as e:
        rec.warnings.append(f"파일을 읽지 못했습니다: {e}")
        return rec

    if not text.strip():
        rec.warnings.append("텍스트를 추출하지 못했습니다(스캔 이미지 PDF일 수 있음).")
        return rec

    sections = _split_sections(text)
    # 문서의 개정/작성 연도를 추출한다. 기준연도(year)는 등록 시 도입일자의
    # 연도로 덮어써지며, 도입일자가 없을 때만 이 값이 기준연도로 쓰인다.
    rec.doc_year, year_src = extract_year(text, path)
    rec.year = rec.doc_year
    if rec.doc_year is None:
        rec.warnings.append(
            "문서에서 연도를 찾지 못했습니다. 도입일자를 입력하면 그 연도가 기준연도가 됩니다."
        )
    rec.product = extract_product(text, sections)
    rec.manufacturer = extract_manufacturer(text, sections)
    if not rec.manufacturer:
        rec.warnings.append("제조사/공급자 정보를 찾지 못했습니다.")
    rec.ingredients = extract_ingredients(text, sections, product=rec.product)
    if not rec.ingredients:
        rec.warnings.append("구성성분(CAS 번호)을 찾지 못했습니다.")
    return rec
