# -*- coding: utf-8 -*-
"""MSDS PDF에서 '화학물질 작업공정별 관리 요령' 양식에 필요한 항목을 추출한다.

지원하는 항목 헤더 형식:
  "4. 응급조치 요령" / "제4항" / "항 4: 응급조치요령"(Merck 등) / "SECTION 4"
소항목 표기는 가나다(가. 나.)와 영문자(a. b.) 모두 인식하며,
"쪽 4 / 14" 같은 페이지 푸터와 반복되는 상용구는 자동 제거한다.
"""
import re
from collections import Counter
from dataclasses import dataclass, field
from io import BytesIO

import pdfplumber

from ghs_data import (H_STATEMENTS, pictograms_for_codes, signal_word_for_codes)
from ko_spacing import fix_spacing_all

# ── 난독화된 Arial Unicode MS(CID) 폰트 복원 ────────────────────────────
# 일부 MSDS 생성 프로그램(DR-Software 구버전 등)은 ToUnicode 없이
# "WinCharSetFFFF" CMap + cmap 테이블이 제거된 Arial Unicode MS 서브셋을
# 내장한다. 이 경우 pdfminer는 한글을 전부 버린다. 다행히 원본 폰트의
# 글리프 배치가 한글 음절(U+AC00~D7A3) 구간에서 선형(GID 38325부터)이라
# CIDToGIDMap만 있으면 유니코드를 복원할 수 있다.
_AUMS_HANGUL_GID0 = 38325            # GID of U+AC00 '가' in Arial Unicode MS
_AUMS_EXTRA = {3564: "∙"}       # '∙' 등 개별 확인된 글리프


def _aums_gid_to_char(gid: int):
    if _AUMS_HANGUL_GID0 <= gid < _AUMS_HANGUL_GID0 + 11172:
        return chr(0xAC00 + gid - _AUMS_HANGUL_GID0)
    return _AUMS_EXTRA.get(gid)


_CIDRANGE_RX = re.compile(
    rb"<([0-9a-fA-F]{2,8})>\s*<([0-9a-fA-F]{2,8})>\s*(\d+)")
_CIDCHAR_RX = re.compile(rb"<([0-9a-fA-F]{2,8})>\s*(\d+)")


def _parse_embedded_cmap(data: bytes):
    """내장 CMap 스트림에서 code→CID 매핑을 읽는다 (2바이트 코드 가정)."""
    from pdfminer.cmapdb import FileCMap
    cm = FileCMap()
    d = cm.code2cid

    def put(code, cid):
        d.setdefault(code >> 8, {})[code & 0xFF] = cid

    pos = 0
    while True:
        s = data.find(b"begincidrange", pos)
        if s < 0:
            break
        e = data.find(b"endcidrange", s)
        if e < 0:
            break
        for m in _CIDRANGE_RX.finditer(data[s:e]):
            lo, hi, cid = (int(m.group(1), 16), int(m.group(2), 16),
                           int(m.group(3)))
            for i in range(hi - lo + 1):
                put(lo + i, cid + i)
        pos = e + 1
    pos = 0
    while True:
        s = data.find(b"begincidchar", pos)
        if s < 0:
            break
        e = data.find(b"endcidchar", s)
        if e < 0:
            break
        for m in _CIDCHAR_RX.finditer(data[s:e]):
            put(int(m.group(1), 16), int(m.group(2)))
        pos = e + 1
    return cm if d else None


def _install_font_fallback():
    from pdfminer import pdffont as _pf
    from pdfminer.pdftypes import resolve1, stream_value
    from pdfminer.cmapdb import FileUnicodeMap

    if getattr(_pf.PDFCIDFont, "_msds_patched", False):
        return
    orig_init = _pf.PDFCIDFont.__init__

    def patched(self, rsrcmgr, spec, strict=False):
        orig_init(self, rsrcmgr, spec, strict)
        if "ArialUnicodeMS" not in str(getattr(self, "basefont", "")):
            return
        try:
            # 1) pdfminer는 이름 있는 CMap만 찾는다. Encoding이 내장 CMap
            #    스트림이면 (code→CID 매핑이 비어 한글이 전부 사라짐) 직접 파싱.
            enc = resolve1(spec.get("Encoding"))
            if hasattr(enc, "get_data") and not getattr(self.cmap, "code2cid", None):
                cm = _parse_embedded_cmap(stream_value(enc).get_data())
                if cm is not None:
                    self.cmap = cm
            # 2) ToUnicode가 없으면 CIDToGIDMap + 글리프 배치 규칙으로 복원.
            has_map = getattr(self, "unicode_map", None) and \
                getattr(self.unicode_map, "cid2unichr", None)
            if has_map:
                return
            c2g_obj = resolve1(spec.get("CIDToGIDMap"))
            if not hasattr(c2g_obj, "get_data"):
                return
            c2g = stream_value(c2g_obj).get_data()
            um = FileUnicodeMap()
            for cid in range(len(c2g) // 2):
                gid = (c2g[2 * cid] << 8) | c2g[2 * cid + 1]
                ch = _aums_gid_to_char(gid)
                if ch:
                    um.cid2unichr[cid] = ch
            if um.cid2unichr:
                self.unicode_map = um
        except Exception:
            pass

    _pf.PDFCIDFont.__init__ = patched
    _pf.PDFCIDFont._msds_patched = True


_install_font_fallback()


@dataclass
class MsdsData:
    source_name: str = ""
    product_name: str = ""
    signal_word: str = ""
    pictograms: list = field(default_factory=list)      # ["GHS05", ...]
    hazards: list = field(default_factory=list)          # 유해·위험문구
    precautions: list = field(default_factory=list)      # 안전·보건상 취급주의
    ppe: list = field(default_factory=list)              # 적절한 보호구
    inhalation: list = field(default_factory=list)       # 흡입 시
    skin_eye: list = field(default_factory=list)         # 피부·눈 접촉 시
    ingestion: list = field(default_factory=list)        # 먹었을 때
    emergency: list = field(default_factory=list)        # 응급대응(화재·누출)
    un_number: str = ""                                  # 국제연합번호(14항)
    manufacturer: str = ""                               # 제조사·공급자(1항)
    components: list = field(default_factory=list)       # 구성성분(3항)
    #   components: [{"name": 성분명, "cas": CAS번호, "content": 함유량}]
    revision_date: str = ""                              # 최종 개정일자(16항 등)
    hcodes: str = ""                                     # 2항 H-code 목록(구분 포함)
    risk: dict = field(default_factory=dict)             # 위험성평가용 수치(8·9·11·12항)
    warnings: list = field(default_factory=list)         # 파싱 경고 메시지


def _drop_overprint(page, tol=1.5):
    """가짜 볼드(같은 글자를 미세하게 어긋나게 겹쳐 찍기) 중복 글자를 제거한다.

    pdfplumber의 dedupe_chars는 좌표를 tolerance 단위로 반올림해 비교하기
    때문에 경계에 걸친 중복(0.24pt 어긋난 4중 인쇄 등)을 놓친다.
    여기서는 실제 거리로 비교한다.
    """
    buckets = {}
    for c in page.chars:
        t = c.get("text")
        bx, by = int(c["x0"] // tol), int(c["top"] // tol)
        dup = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for (x, y) in buckets.get((t, bx + dx, by + dy), ()):
                    if abs(x - c["x0"]) <= tol and abs(y - c["top"]) <= tol:
                        dup = True
                        break
                if dup:
                    break
            if dup:
                break
        if dup:
            c["_overprint_dup"] = True
        else:
            buckets.setdefault((t, bx, by), []).append((c["x0"], c["top"]))
    return page.filter(
        lambda o: o.get("object_type") != "char" or not o.get("_overprint_dup"))


def extract_text(pdf_source) -> str:
    """PDF 전체 텍스트를 추출한다. pdf_source는 경로 또는 파일 객체.

    페이지 경계는 \\f(폼피드)로 표시한다 — clean_text가 페이지 수 기반으로
    반복 머리글/바닥글을 걸러내는 데 쓴다.
    """
    pages = []
    with pdfplumber.open(pdf_source) as pdf:
        for page in pdf.pages:
            try:
                page = _drop_overprint(page)
            except Exception:
                pass
            pages.append(page.extract_text() or "")
    return "\n\f\n".join(pages)


_FOOTER_RX = re.compile(
    r"쪽\s*[:：]?\s*\d+\s*/\s*\d+"          # "쪽 4 / 14", "쪽: 3/9"
    r"|^\s*page\s*\d+"
    r"|^\s*-?\s*\d+\s*/\s*\d+\s*-?\s*$"
    r"|\(\s*\d+\s*쪽\s*(?:에서?|부터)\s*계속\s*\)"   # "(3 쪽에계속)", "(2 쪽부터계속)"
    r"|^MSDS\b.*\d+\s*/\s*\d+\s*$"          # "MSDS 물질명 ... 개정번호 28 6/9"
    r"|continued\s+(?:on|from)\s+page", re.I)


def clean_text(text: str) -> str:
    """페이지 푸터·"(N쪽에 계속)" 문구·반복되는 머리글(회사 상용구 등)을 제거한다."""
    pages = text.split("\f") or [text]
    n_pages = len(pages)
    # 줄이 나타나는 "페이지 수"를 센다 — 같은 줄이 한 페이지 안에서 여러 번
    # 나오는 것(예: 제조자/공급자 회사명 반복)은 본문이므로 세지 않는다.
    page_count = Counter()
    for pg in pages:
        page_count.update({l.strip() for l in pg.splitlines()
                           if len(l.strip()) > 1})
    # 여러 페이지에서 반복되는 짧은 머리글("물질안전보건자료", "KR" 등)은
    # 페이지 수 기준으로, 긴 상용구는 3개 페이지 반복이면 제거한다.
    boiler = {l for l, c in page_count.items()
              if (len(l) > 10 and c >= 3) or c >= max(3, n_pages - 1)}
    kept = [l for l in text.replace("\f", "\n").splitlines()
            if l.strip() not in boiler and not _FOOTER_RX.search(l)]
    return "\n".join(kept)


# ── 섹션 분리 ────────────────────────────────────────────────────────────
_SECTION_KEYS = {
    1: r"(?:화학제품과\s*(?:제조\s*)?회사|제품\s*및\s*회사|화학제품에\s*관한)",
    2: r"유해성?\s*[·ㆍ.,]?\s*위험성|위험\s*[·ㆍ.,]?\s*유해성",
    3: r"구성\s*성분|구성성분의\s*명칭",
    4: r"응급\s*조치\s*요령",
    5: r"폭발\s*[·ㆍ.]?\s*화재\s*시|화재\s*시\s*대처",
    6: r"누출\s*사고\s*시",
    7: r"취급\s*및\s*저장",
    8: r"노출\s*방지\s*및\s*개인\s*보호구|노출방지",
    9: r"물리\s*[·ㆍ.,]?\s*화학적\s*특성",
    10: r"안정성\s*및\s*반응성",
    11: r"독성에\s*관한\s*정보",
    12: r"환경에\s*미치는\s*영향|환경\s*영향",
    13: r"폐기\s*시\s*주의사항|폐기시",
    14: r"운송에\s*필요한\s*정보",
    15: r"법적\s*규제\s*현황|법규에\s*관한",
    16: r"그\s*밖의\s*참고사항|기타\s*참고사항",
}


def split_sections(text: str) -> dict:
    """텍스트를 MSDS 항목 번호별로 나눈다.

    "4. 제목", "제4항 제목", "항 4: 제목", "SECTION 4 제목"을 모두 인식한다.
    """
    hits = []
    for num, pat in _SECTION_KEYS.items():
        # "01. 화학제품과..."처럼 0을 붙여 쓰는 형식(한국가스공사 등)도 인식
        rx = re.compile(
            r"^[^\S\n]*(?:제\s*|항\s*|SECTION\s*|섹션\s*)?0?%d\s*[.):：항]?\s*[:：]?\s*(?:%s)"
            % (num, pat), re.M | re.I)
        m = rx.search(text)
        if m:
            hits.append((m.start(), num))
    hits.sort()
    sections = {}
    for i, (pos, num) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(text)
        sections[num] = text[pos:end]
    return sections


# ── 라벨 블록 추출 ───────────────────────────────────────────────────────
# 가나다 또는 a. b. c. 형식의 소항목 헤더
_SUB_HEAD = r"^\s*(?:[가나다라마바사]|[a-hA-H])\s*[.)]\s"


def grab_block(text: str, start_pat: str, stop_pats: list) -> str:
    """start_pat 라벨 다음부터 stop_pats 중 하나가 나오기 전까지의 텍스트."""
    m = re.search(start_pat, text, re.M)
    if not m:
        return ""
    rest = text[m.end():]
    end = len(rest)
    for sp in stop_pats:
        sm = re.search(sp, rest, re.M)
        if sm and sm.start() < end:
            end = sm.start()
    return rest[:end]


_BULLET_RX = re.compile(r"^[\s○●◦•·ㆍ\-–—▶▷►*∙:：,]+")
_NOISE_RX = re.compile(
    r"^(자료\s*없음|해당\s*(?:사항\s*)?없음|자료없음|해당없음|내용\s*없음|없음|"
    r"누락(?:되어(?:\s*있음)?|됨|되다)?|N/?A|-|페이지|page|\d+\s*/\s*\d+)\s*\.?$",
    re.I)

# 내용이 없다는 뜻의 문구("없음", "해당없음", "내용없음", "누락" 등)만 적힌 경우
_NONE_LINE_RX = re.compile(
    r"^(자료\s*없음|해당\s*(?:사항\s*)?없음|내용\s*없음|없음|"
    r"누락(?:되어(?:\s*있음)?|됨|되다)?|N/?A)\s*\.?$", re.I)
NONE_TEXT = "해당없음"


def _none_stated(block: str) -> bool:
    """블록에 '없음/누락' 류 문구가 명시되어 있는지 확인한다."""
    for raw in block.splitlines():
        line = _BULLET_RX.sub("", raw.strip()).strip()
        if line and _NONE_LINE_RX.match(line):
            return True
    return False


# H290, P260, P301+P312 같은 유해·위험/예방조치 코드 — 양식에는 코드 뒤의
# 문구만 적는다 (문장 어디에 있어도 제거)
_CODE_RX = re.compile(
    r"(?<![A-Za-z0-9])(?:EU)?[HP]\d{3}(?:\s*\+\s*(?:EU)?[HP]\d{3})*\s*[:.]?\s*")
_MARKERS = ("○", "●", "◦", "•", "·", "ㆍ", "∙", "-", "–", "▶", "▷", "►", "*")
_SENT_END = ("음", "함", "됨", "킴", "임", "짐", "오", "요", "것", ".", ")", "%")


def bulletize(block: str, drop_codes: bool = True) -> list:
    """블록을 문장 단위 목록으로 정리한다. 줄바꿈으로 잘린 문장은 앞 줄에 잇는다."""
    items = []
    for raw in block.splitlines():
        stripped = raw.strip()
        has_marker = stripped.startswith(_MARKERS)
        line = _BULLET_RX.sub("", stripped).strip()
        if not line or _NOISE_RX.match(line):
            continue
        if drop_codes:
            # "H315 피부에 자극을 일으킴", "P301 + P312 삼켰다면..." -> 코드 제거
            # H/P 코드로 시작하는 줄은 표식이 없어도 새 항목으로 취급한다
            if _CODE_RX.match(line):
                has_marker = True
            line = _CODE_RX.sub("", line)
            line = re.sub(r"\(\s*\)", "", line).strip()   # "(H315)" 제거 후 빈 괄호 정리
            if not line or _NOISE_RX.match(line):
                continue
        # 표식 없는 줄이 이어지고 앞 문장이 끝나지 않았으면 줄바꿈으로 잘린 문장으로 본다
        if items and not has_marker and not items[-1].endswith(_SENT_END):
            items[-1] = items[-1] + " " + line
        else:
            items.append(line)
    return items


# 응급조치 내용이 라벨을 다시 반복하는 형식("눈에 들어갔을 때: 다량의 물로...") 정리
_RESTATED_RX = re.compile(
    r"^(?:눈에\s*들어갔을\s*때|눈에\s*묻으면|피부에\s*접촉(?:했을|된|한)?\s*(?:때|경우)?|"
    r"피부(?:\s*\(또는\s*머리카락\))?에\s*묻으면|흡입(?:했을\s*때|한\s*경우|하면)|"
    r"먹었을\s*때|삼켰을\s*때|삼켰다면)\s*[:：]\s*")


# ── 항목 수 제한·중복 병합 ───────────────────────────────────────────────
# 양식 가독성을 위해 취급주의는 최대 8개, 응급조치·응급대응은 각 5개로
# 한정한다. 같은 내용을 반복하는 항목은 병합(더 자세한 쪽 유지)하거나
# 삭제한다.
MAX_PRECAUTIONS = 8
MAX_AID = 5

_NORM_RX = re.compile(r"[\s.,·ㆍ:：;/()\[\]▶\-–—!?'\"%]+")


def _norm_item(s: str) -> str:
    return _NORM_RX.sub("", s).lower()


def _bigram_sim(a: str, b: str) -> float:
    """2-gram 포함 유사도 (짧은 쪽 기준)."""
    A = {a[i:i + 2] for i in range(len(a) - 1)}
    B = {b[i:i + 2] for i in range(len(b) - 1)}
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def dedupe_merge(items: list) -> list:
    """중복·유사 항목을 병합한다. 포함 관계면 더 자세한 문장을 남긴다."""
    kept = []
    for it in items:
        n = _norm_item(it)
        if not n:
            continue
        merged = False
        for i, k in enumerate(kept):
            kn = _norm_item(k)
            if n == kn or n in kn:
                merged = True                    # 이미 포함된 내용
                break
            if kn in n or (_bigram_sim(n, kn) >= 0.75 and len(it) > len(k)):
                kept[i] = it                     # 더 자세한 문장으로 대체
                merged = True
                break
            if _bigram_sim(n, kn) >= 0.75:
                merged = True
                break
        if not merged:
            kept.append(it)
    return kept


# 취급주의에서 우선순위가 낮은 "대응(사고 후)" 성격의 문구 — 응급조치 칸과
# 중복되므로 8개를 넘길 때 먼저 제외한다.
_RESPONSE_RX = re.compile(
    r"삼켰|묻으면|흡입하면|접촉\s*시|들어갔|연락|의사|의료|병원|센터|진찰|"
    r"처치|증상이|토하|헹구|불편함|입을\s*씻|(?:라벨|취급\s*설명서)\s*참조")


def curate_precautions(items: list) -> list:
    items = dedupe_merge(items)
    if len(items) <= MAX_PRECAUTIONS:
        return items
    scored = sorted(enumerate(items),
                    key=lambda p: (bool(_RESPONSE_RX.search(p[1])), p[0]))
    keep_idx = sorted(i for i, _ in scored[:MAX_PRECAUTIONS])
    return [items[i] for i in keep_idx]


# ── 개인보호구(8항) 요약 ────────────────────────────────────────────────
# 성분별 노출농도 구간마다 보호구를 나열하는 상세형 MSDS(예: 수산화나트륨
# 20/50/100/2000mg/m3 …)는 전문을 그대로 옮기면 양식 칸을 넘친다.
# 보호구 종류별로 핵심 문장 두 개 내외만 남긴다.
MAX_PPE_PER_TYPE = 2

_PPE_LADDER_RX = re.compile(r"노출\s*농도가\s*[\d,.]+\s*(?:mg|㎎|ppm)", re.I)
_PPE_HEADER_RX = re.compile(r"(?:다음과\s*같은.*)?권고됨\s*[.:：]?$")
_PPE_EQUIP_RX = re.compile(r"보호|착용|마스크|장갑|보안경|보호구|설치")


def condense_ppe(items: list, limit: int = MAX_PPE_PER_TYPE) -> list:
    """보호구 항목을 종류별 핵심 문장 limit개 내외로 요약한다."""
    if not items:
        return items
    # 1) 성분명이 문장 머리에 반복되는 형식("수산화나트륨 …을 착용하시오",
    #    "물(WATER) …") — 두 번 이상 반복되는 머리 단어는 성분명으로 보고 뗀다
    heads = Counter()
    for it in items:
        m = re.match(r"^(\S{2,20})(?:\s|$)", it)
        if m and not _PPE_EQUIP_RX.search(m.group(1)):
            heads[m.group(1)] += 1
    strip = {h for h, c in heads.items() if c >= 2}
    out = []
    for it in items:
        for h in strip:
            if it == h:                      # 성분명만 있는 줄은 버린다
                it = ""
                break
            if it.startswith(h + " "):
                it = it[len(h):].strip()
                break
        if it:
            out.append(it)
    # 2) 노출농도 구간별 나열("노출농도가 20mg/m3보다 낮을 경우 …")과
    #    목록 머리글("…이 권고됨")은 제외한다
    core = [it for it in out
            if not _PPE_LADDER_RX.search(it) and not _PPE_HEADER_RX.search(it)]
    if not core:
        core = out
    # 3) "A 또는 B 또는 C 또는 …"처럼 긴 대안 나열은 앞의 두 개 + "등"으로 줄인다
    shortened = []
    for it in core:
        parts = it.split(" 또는 ")
        if len(parts) >= 3:
            it = " 또는 ".join(parts[:2]).rstrip(",.") + " 등"
        shortened.append(it)
    return dedupe_merge(shortened)[:limit]


# ── 제조사(1항)·구성성분(3항) — 화학물질 도입검토용 ─────────────────────
_CAS_RX = re.compile(r"(?<![\d-])(\d{2,7}-\d{2}-\d)(?![\d-])")


def _valid_cas(cas: str) -> bool:
    """CAS 등록번호 검증(마지막 자리는 검사숫자) — EC번호·색인번호 오인 방지."""
    digits = cas.replace("-", "")
    body, check = digits[:-1], int(digits[-1])
    s = sum(int(d) * w for w, d in enumerate(reversed(body), start=1))
    return s % 10 == check


# 분류 용어(영문)가 성분명 자리에 들어온 경우(Merck 등 표 형식 붕괴) 걸러낸다
_CLASS_TERM_RX = re.compile(
    r"Flam|Tox|Skin|Corr|Irrit|STOT|Aquatic|Repr|Muta|Carc|Liq|Sol|"
    r"Eye|Dam|Acute|Chronic|구분\s*\d|분류|함유량|식별번호|번호", re.I)
_CONTENT_RX = re.compile(
    r"([<>≥≤=]{0,2}\s*\d+(?:[.,]\d+)?\s*(?:%|(?:\s*[–\-~]\s*"
    r"[<>≥≤=]{0,2}\s*\d+(?:[.,]\d+)?\s*%?))?%?)\s*$")


def _clean_component_name(s: str) -> str:
    s = re.sub(r"^[·ㆍ○●\-–—*\s:：]+|[;,·\s]+$", "", s.strip())
    s = re.sub(r"\s{2,}", " ", s)
    return "" if _CLASS_TERM_RX.search(s) else s


def extract_manufacturer(sec1: str) -> str:
    """1항에서 회사명(제조자·공급자)을 찾는다.

    라벨은 줄 머리(번호·글머리표 뒤 포함)에 있을 때만 인정한다 —
    "사용상의 제한 : ... 제조사 측과 합의되지 않은 용도" 같은 본문 속
    단어에 걸리지 않도록 한다.
    """
    # 글머리표에는 라틴 O·그리스 ο(한국가스공사)·전각 별표 ＊(동양하이테크)도 쓰인다
    _pre = r"(?m)^\s*(?:[0-9가-힣a-zA-Z]{1,2}\s*[.)])?[\s·ㆍ•○◦oOο\-–—*＊]*"
    for pat in (r"회\s*사\s*명", r"제조\s*(?:회\s*)?사", r"제조\s*업체",
                r"공급\s*(?:자|업체)", r"수입\s*자", r"판매\s*자", r"업체\s*명"):
        for m in re.finditer(_pre + r"(?:" + pat + r")\s*[:：]?[ \t]*([^\n]*)",
                             sec1):
            val = re.sub(r"^[:：·ㆍ\-\s]+", "", m.group(1)).strip()
            # "제조자/수입자/유통업자 정보:"처럼 라벨이 이어지는 경우는 건너뛴다
            if not val or val.startswith(("/", "·")):
                continue
            # "(주)한솔케미칼"은 회사명이지만 "(수입품의 경우 ...)"는 지침 문구
            if val.startswith("(") and \
                    not re.match(r"^\(\s*(?:주|유|합|사)\s*\)", val):
                continue
            # 회사명 뒤에 다른 항목이 이어지면("OCI㈜ 사업장명 : ...") 잘라낸다
            val = re.split(r"\s+(?:사업장명?|주\s*소|담당\s*부서|연락처|전화|"
                           r"TEL|FAX)\b", val)[0].strip()
            # 표 머리글·지침 문구("주소 정보제공 서비스 ...")는 건너뛴다
            if len(val) < 2 or re.search(
                    r"정보\s*[:：]?$|주소|전화|담당|서비스|기재|홈페이지", val):
                continue
            return val[:60].strip()
    # 표 형식: "제조자 | 주소 | ..." 머리글 다음 줄에 회사명이 오는 경우
    # ("㈜유니드 울산공장 울산광역시 남구 ..." — 주소가 시작되기 전까지)
    m = re.search(r"(?m)^\s*제조자\s+주소\b[^\n]*\n\s*(\S[^\n]*)", sec1)
    if m:
        out = []
        for t in m.group(1).split()[:4]:
            if re.search(r"광역시|특별시|특별자치|^[가-힣]{2,8}(?:시|도|군|구|"
                         r"읍|면)$|^\(?전화|^\d|TEL|FAX", t):
                break
            out.append(t)
        if out:
            return " ".join(out)[:60]
    return ""


# "영업비밀"로 CAS 번호를 밝히지 않는 성분(산업안전보건법 비공개 승인 물질 등)
_SECRET_RX = re.compile(r"영\s*업\s*비\s*밀|기업\s*비밀|trade\s*secret", re.I)
_CONTENT_TOK = (r"[<>≥≤=]{0,2}\s*\d+(?:[.,]\d+)?"
                r"(?:\s*[–\-~]\s*[<>≥≤=]{0,2}\s*\d+(?:[.,]\d+)?)?\s*%?")


def _row_name(before: str) -> str:
    """행 형식에서 CAS 앞 텍스트로부터 성분명을 뽑는다.

    "에틸렌 글리콜"처럼 띄어쓰기가 있는 이름은 같은 문자계열(한글/영문)
    토큰을 이어 붙이고, "수산화나트륨 수산화 나트륨"처럼 이름의 띄어쓰기
    변형(관용명)이 반복되면 앞부분만 남긴다.
    """
    # "제조성분 무수암모니아 ..."처럼 행 머리에 붙는 구분 라벨은 뗀다
    before = re.sub(r"^\s*(?:제\s*조\s*성\s*분|주\s*성\s*분|부\s*성\s*분)\s+",
                    "", before)
    toks = before.split()
    if not toks:
        return ""
    name = toks[0]
    i = 1
    # 여는 괄호가 닫히지 않았으면 닫힐 때까지 잇는다 ("염산 (HYDROCHLORIC ACID)")
    while name.count("(") > name.count(")") and i < len(toks):
        name += " " + toks[i]
        i += 1
    if "(" not in name:
        first_kor = bool(re.search(r"[가-힣]", toks[0]))
        added = 0
        while i < len(toks) and added < 2:
            t = toks[i]
            if ("(" in t or ")" in t or _SECRET_RX.search(t)
                    or not re.search(r"[가-힣A-Za-z]", t)
                    or bool(re.search(r"[가-힣]", t)) != first_kor):
                break
            name += " " + t
            i += 1
            added += 1
    # 뒤가 이름의 띄어쓰기 변형이면 정리 ("수산화나트륨 수산화 나트륨")
    parts = name.split()

    def nrm(s):
        return re.sub(r"\s+", "", s).lower()
    for k in range(1, len(parts)):
        if nrm("".join(parts[:k])) == nrm("".join(parts[k:])):
            return " ".join(parts[:k])
    return name


_KDATE_RX = re.compile(
    r"(\d{4})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]?\s*(\d{1,2})\s*일?")


def extract_revision_date(text: str) -> str:
    """MSDS 개정일자(최종 개정일자)를 찾는다 — 여러 날짜가 있으면 최신값.

    "최종 개정일자 : 2024. 01. 26", "개정일자 2025년 01월 10일",
    "27차 개정 : 2024/10/07" 형식을 모두 지원한다. 결과는 YYYY-MM-DD.
    """
    best = ""
    for m in re.finditer(r"개정[^\n]{0,60}", text):
        for dm in _KDATE_RX.finditer(m.group(0)):
            y, mo, d = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
            if 1990 <= y <= 2100 and 1 <= mo <= 12 and 1 <= d <= 31:
                iso = f"{y:04d}-{mo:02d}-{d:02d}"
                if iso > best:
                    best = iso
    return best


# ── 위험성평가용 데이터 추출 (2·8·9·11·12항) ────────────────────────────
_HCAT_CLASSES = [                       # 구분(Cat) 표기가 필요한 H-code
    ("H314", r"피부\s*부식성"),
    ("H340", r"(?:생식\s*세포\s*)?변이원성"),
    ("H350", r"발암성"),
    ("H360", r"생식\s*독성"),
]
_NO_DATA_RX = re.compile(
    r"자료\s*없음|해당\s*없음|없\s*음|측정\s*불가|않음|안\s*됨|비인화성|무기물")
_NUM_RX = re.compile(r"-?\d+(?:[.,]\d+)?")


def extract_hcodes(sec2: str) -> str:
    """2항의 H-code 목록 — H314/H340/H350/H360은 구분(Cat)까지 붙인다.

    위험성평가 양식(①기초Data C17)에 그대로 넣을 수 있는 형식.
    구분 표기("발암성 : 구분1A" 등)를 찾으면 "H350 Cat1A"처럼 보강한다.
    H314는 MSDS에 구분 1만 있으면(1A/1B 명기 없음) 원문대로 "H314"만
    표기한다(등급 산정은 구분1로 처리). H340/H350/H360은 구분 1만 있으면
    보수적으로 1A로 본다(수정 가능)."""
    codes = sorted(set(re.findall(r"H\d{3}", sec2 or "")))
    out = []
    for c in codes:
        cls = next((rx for code, rx in _HCAT_CLASSES if code == c), None)
        if cls:
            m = re.search(cls + r"[^\n]{0,60}?구분\s*[:：]?\s*1\s*([ABC])?",
                          sec2)
            if m:
                sub = m.group(1)
                if c == "H314":
                    out.append(f"{c} Cat1{sub}" if sub in ("A", "B") else c)
                else:
                    out.append(f"{c} Cat1{sub if sub in ('A', 'B') else 'A'}")
                continue
        out.append(c)
    return ", ".join(out)


def _risk_num(line: str, after: int = 0) -> str:
    """라벨 뒤 텍스트에서 첫 숫자(부호 포함)를 찾는다.

    '자료없음·해당없음' 등으로 명기된 항목은 "없음"으로 처리한다."""
    tail = line[after:]
    if _NO_DATA_RX.search(tail):
        return "없음"
    m = _NUM_RX.search(tail)
    return m.group(0).replace(",", "") if m else ""


def _line_field(sec: str, label_rx: str) -> str:
    """9항처럼 '라벨 : 값' 한 줄 형식에서 값(첫 숫자)을 찾는다."""
    for m in re.finditer(label_rx, sec):
        line = sec[m.end():].split("\n", 1)[0]
        v = _risk_num(line)
        if v:
            return v
        if _NO_DATA_RX.search(line):
            return "없음"
    return ""


_VP_UNITS = [                            # 증기압 단위 → mmHg 환산 계수
    (r"㎜\s*Hg|mm\s*Hg|torr", 1.0),
    (r"㎪|kPa", 7.50062),
    (r"hPa|㍱", 0.750062),
    (r"㎩|(?<![khKH])Pa(?![a-z])", 1 / 133.322),
    (r"atm", 760.0),
    (r"bar", 750.062),
]


def _vapor_mmhg(sec9: str) -> str:
    for m in re.finditer(r"증\s*기\s*압", sec9):
        line = sec9[m.end():].split("\n", 1)[0]
        nm = _NUM_RX.search(line)
        if not nm:
            if _NO_DATA_RX.search(line):
                return "없음"
            continue
        v = float(nm.group(0).replace(",", ""))
        unit_part = line[nm.end():nm.end() + 12]
        factor = 1.0
        for rx, f in _VP_UNITS:
            if re.search(rx, unit_part):
                factor = f
                break
        v = round(v * factor, 3)
        return f"{v:g}"
    return ""


def _tox_line(sec: str, subject_rx: str, marker_rx: str, unit_rx: str,
              exclude_rx: str = "") -> str:
    """11·12항 — 주제어와 LD50/LC50 등이 같은 줄에 있는 값을 찾는다.

    "10 ~ 20 ㎎/ℓ"처럼 범위로 표기된 값은 가장 낮은 값을 취하고,
    '자료없음' 등으로 명기된 항목은 "없음"으로 처리한다."""
    no_data = False
    for line in (sec or "").split("\n"):
        if not re.search(subject_rx, line):
            continue
        if exclude_rx and re.search(exclude_rx, line):
            continue
        m = re.search(marker_rx + r"\D{0,25}?(-?\d[\d,]*(?:\.\d+)?)"
                      r"(?:\s*[~∼–—-]\s*(\d[\d,]*(?:\.\d+)?))?\s*" +
                      unit_rx, line)
        if m:
            lo = float(m.group(1).replace(",", ""))
            if m.group(2):
                lo = min(lo, float(m.group(2).replace(",", "")))
            return f"{lo:g}"
        if _NO_DATA_RX.search(line):
            no_data = True
    return "없음" if no_data else ""


def _taboo_count(sec10: str) -> str:
    """10항 '피해야 할 물질'의 항목 개수 → 금기물질 유형 수(종).

    예) "산, 금속, 아민, 가연성물질, 환원제" → "5". 같은 줄 값이 없으면
    다음 줄부터 다음 라벨 전까지의 목록을 센다. '자료없음'이면 "없음"."""
    lines = (sec10 or "").split("\n")
    for i, ln in enumerate(lines):
        m = re.search(r"피해야\s*할?\s*물\s*질(?!과)", ln)
        if not m:
            continue
        content = re.sub(r"^[\s:：)(]+", "", ln[m.end():]).strip()
        # "피해야 할 물질 및 조건에 유의하시오" 같은 지침 문장은 제외
        if re.match(r"^(및|과의|등에)", content) or \
                re.search(r"유의|주의|하시오", content):
            continue
        items = [content] if content else []
        if not items:
            for nxt in lines[i + 1:]:
                t = nxt.strip()
                if not t:
                    if items:
                        break
                    continue
                if re.match(r"^(?:[가-하]\.|\d+\.|[①-⑳○◦])", t) or \
                        re.search(r"분해\s*시|유해\s*반응|피해야\s*할\s*조건",
                                  t):
                    break
                items.append(re.sub(r"^[-·•.\s]+", "", t))
        if not items:
            return ""
        blob = ", ".join(items)
        if _NO_DATA_RX.search(blob):
            return "없음"
        toks = [t.strip(" .") for t in
                re.split(r"[,·、;/]|\s및\s", blob)]
        toks = [t for t in toks if t and t != "등"]
        return str(len(toks)) if toks else ""
    return ""


def extract_risk_data(sections: dict) -> dict:
    """위험성평가(①기초Data)용 수치 데이터를 MSDS 8~12항에서 추출한다.

    찾지 못한 항목은 빈 문자열 — 작성자가 직접 입력한다.
    '자료없음·해당없음' 등으로 명기된 항목은 "없음"으로 채운다."""
    out = {}
    sec8 = sections.get(8, "")
    sec9 = sections.get(9, "")
    sec10 = sections.get(10, "")
    sec11 = sections.get(11, "")
    sec12 = sections.get(12, "")

    # 8항 — 노출기준 TWA (STEL 앞부분만, 첫 TWA 줄)
    for line in sec8.split("\n"):
        if not re.search(r"TWA", line, re.I):
            continue
        part = re.split(r"STEL|C\s*[:：]", line, flags=re.I)[0]
        ppm = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*ppm", part, re.I)
        mg = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(?:㎎|mg)\s*/\s*(?:㎥|m³|m3)",
                       part, re.I)
        if ppm or mg:
            out["twa_ppm"] = ppm.group(1).replace(",", "") if ppm else ""
            out["twa_mg"] = mg.group(1).replace(",", "") if mg else ""
            break
        if _NO_DATA_RX.search(part):
            out["twa_ppm"] = out["twa_mg"] = "없음"
            break

    # 9항 — 물리화학적 특성 (라벨 : 값)
    out["flash"] = _line_field(sec9, r"인\s*화\s*점")
    out["boiling"] = _line_field(sec9, r"끓는\s*점")
    out["ait"] = _line_field(sec9, r"자연\s*발화\s*온도|자연발화점")
    out["vapor"] = _vapor_mmhg(sec9)
    out["logkow"] = _line_field(
        sec9, r"옥탄올[^\n]{0,10}물\s*분배\s*계수|분배\s*계수|log\s*Kow")
    out["decomp_temp"] = _line_field(sec9, r"분해\s*온도")

    # 11항 — 독성 데이터
    out["ld50_oral"] = _tox_line(sec11, r"경구", r"LD\s*50",
                                 r"(?:㎎|mg)\s*/\s*(?:㎏|kg)")
    out["ld50_dermal"] = _tox_line(sec11, r"경피", r"LD\s*50",
                                   r"(?:㎎|mg)\s*/\s*(?:㎏|kg)")
    out["lc50_vapor"] = _tox_line(sec11, r"흡입|증기", r"LC\s*50",
                                  r"(?:㎎|mg)\s*/\s*(?:ℓ|L)",
                                  exclude_rx=r"분진|미스트")
    out["lc50_dust"] = _tox_line(sec11, r"분진|미스트", r"LC\s*50",
                                 r"(?:㎎|mg)\s*/\s*(?:ℓ|L)")
    m = re.search(r"IARC[^\n]{0,40}?(?:Group|그룹)\s*(1|2A|2B|3)\b",
                  sec11, re.I) or \
        re.search(r"IARC[^\n]{0,40}?(1|2A|2B|3)\s*군", sec11)
    out["iarc"] = f"IARC Group{m.group(1).upper()}" if m else ""

    # 12항 — 환경 데이터
    out["fish_lc50"] = _tox_line(sec12, r"어류", r"[LE]C\s*50", r"(?:㎎|mg)")
    out["daphnia_ec50"] = _tox_line(sec12, r"물벼룩|갑각류", r"[LE]C\s*50",
                                    r"(?:㎎|mg)")
    out["bcf"] = _tox_line(sec12, r"BCF|생물\s*농축\s*계수", r"(?:BCF|계수)",
                           r"") or _line_field(sec12, r"농축성\s*[:：]")
    if re.search(r"생분해[^\n]*\d[\d,.]*\s*%", sec12):
        m = re.search(r"생분해[^\n]*?(\d[\d,]*(?:\.\d+)?)\s*%", sec12)
        out["biodeg"] = m.group(1).replace(",", "") if m else ""
    else:
        out["biodeg"] = "없음" if any(
            re.search(r"생분해", ln) and _NO_DATA_RX.search(ln)
            for ln in sec12.split("\n")) else ""
    out["koc"] = _tox_line(sec12, r"Koc", r"Koc", r"") or \
        _line_field(sec12, r"토양\s*이동성")
    out["dt50"] = _tox_line(sec12, r"DT\s*50|반감기", r"(?:DT\s*50|반감기)",
                            r"")
    out["pbt"] = ""
    if re.search(r"vPvB[^\n]{0,20}(해당(?!\s*없)|물질임)", sec12):
        out["pbt"] = "vPvB 해당"

    # 10항 — 피해야 할 물질 개수 → 금기물질 유형 수(종).
    # 10항 헤더가 인식되지 않는 문서는 내용이 9항 블록에 붙으므로 9·11항도
    # 함께 살핀다(지침 문장은 _taboo_count 안에서 걸러짐).
    out["taboo"] = _taboo_count(
        "\n".join(s for s in (sec10, sec9, sec11) if s))
    return {k: v for k, v in out.items()}


def _content_mid(content):
    """함유량 문자열의 대푯값(단일값 또는 범위 중간값). 없으면 None."""
    nums = [float(x.replace(",", "."))
            for x in re.findall(r"\d+(?:[.,]\d+)?", content or "")]
    if not nums:
        return None
    return sum(nums[:2]) / min(len(nums), 2)


def drop_product_row(components, product_name: str):
    """혼합물 MSDS가 제품 자체를 성분 행으로 함께 적는 경우 제품 행을 뺀다.

    예: 암모니아수 MSDS가 "암모니아수 100%"와 제조 성분(무수암모니아 25%,
    물 75%)을 모두 적는 형식 — 성분의 함량 합은 100%가 되어야 하므로,
    나머지 성분 합이 100%(±5)이면 제품 행(이름이 제품명과 같거나 함량이
    100%인 행)을 제외한다.
    """
    if len(components) < 3:
        return components
    pn = re.sub(r"\s+", "", product_name or "").lower()
    for idx, c in enumerate(components):
        nm = re.sub(r"\s+", "", c.get("name") or "").lower()
        name_match = bool(nm and pn and (nm in pn or pn in nm))
        if not (name_match or _content_mid(c.get("content")) == 100):
            continue
        rest = components[:idx] + components[idx + 1:]
        mids = [_content_mid(r.get("content")) for r in rest]
        if len(rest) >= 2 and all(m is not None for m in mids) \
                and 95 <= sum(mids) <= 105:
            return rest
    return components


def extract_components(sec3: str) -> list:
    """3항에서 성분명·CAS번호·함유량 목록을 뽑는다.

    지원 형식:
      1) 전치 형식(블록 반복) "물질명 메틸 알코올 / 이명 … / CAS 번호 67-56-1
         / 함유량(%) 48.0 ~ 52.0 / 물질명 물 / …"
      2) 행 형식              "에틸렌 글리콜 (이명) 107-21-1 30"
      3) CAS 라벨 형식        "CAS: 7775-27-1 성분명 85–90%"
      4) 영업비밀 성분        CAS 자리에 "영업비밀"로 적는 형식
    """
    comps = []          # [{"name", "cas", "content"}]

    def add(name, cas, content):
        name = _clean_component_name(name or "")
        content = (content or "").strip().rstrip(".")
        if content and "%" not in content:
            content += "%"
        real_cas = bool(re.fullmatch(r"\d{2,7}-\d{2}-\d", cas or ""))
        for c in comps:
            # 같은 CAS(실제 번호)는 정보를 보강만 한다 — 영업비밀·빈 값은
            # 서로 다른 성분일 수 있으므로 이름까지 같을 때만 병합한다
            if (real_cas and c["cas"] == cas) or \
                    (not real_cas and c["cas"] == cas and c["name"] == name):
                if name and not c["name"]:
                    c["name"] = name
                if content and not c["content"]:
                    c["content"] = content
                return
        comps.append({"name": name, "cas": cas, "content": content})

    # 1) 전치 형식 — "물질명 …" 블록이 하나 이상 반복될 수 있다 (메탄올50% 등)
    heads = list(re.finditer(
        r"(?m)^[·ㆍ\s]*(?:화학)?물질명[ \t]*[:：]?[ \t]*([^\n]*)$", sec3))
    for bi, hm in enumerate(heads):
        header = hm.group(1).strip()
        # "물질명 이명(관용명) CAS 번호 함유량(%)" 같은 표 머리글은 제외
        if not header or re.search(r"CAS|이명|관용명|함유량", header, re.I):
            continue
        end = heads[bi + 1].start() if bi + 1 < len(heads) else len(sec3)
        seg = sec3[hm.end():end]
        cm = re.search(r"^[·ㆍ\s]*CAS\s*[\-]?\s*(?:번호|No)?\.?\s*[:：]?\s+(.+)$",
                       seg, re.M | re.I)
        if not cm:
            continue
        cases = [c for c in _CAS_RX.findall(cm.group(1)) if _valid_cas(c)]
        secret = bool(_SECRET_RX.search(cm.group(1)))
        if not cases and not secret:
            continue
        fm = re.search(r"^[·ㆍ\s]*함\s*유\s*량\s*(?:\(%\))?\s*[:：]?\s+(.+)$",
                       seg, re.M)
        contents = re.findall(_CONTENT_TOK, fm.group(1)) if fm else []
        if len(cases) <= 1:
            # 블록 하나 = 성분 하나: 물질명 줄 전체가 이름 ("메틸 알코올")
            add(header, cases[0] if cases else "영업비밀",
                contents[0] if contents else "")
        else:
            # 한 블록에 여러 성분(Biotector 등): 토큰을 이름으로 나눠 짝짓는다
            names = []
            for tok in header.split():
                if (names and re.fullmatch(r"[A-Za-z0-9().\-]+", tok)
                        and re.fullmatch(r"[A-Za-z0-9().\-]+",
                                         names[-1].split()[-1])):
                    names[-1] += " " + tok
                else:
                    names.append(tok)
            for k, cas in enumerate(cases):
                add(names[k] if k < len(names) else "", cas,
                    contents[k] if k < len(contents) else "")
    if comps:
        return comps

    # 2)+3) 행 형식·CAS 라벨 형식
    lines = sec3.splitlines()
    for i, line in enumerate(lines):
        for cmm in _CAS_RX.finditer(line):
            cas = cmm.group(1)
            if not _valid_cas(cas):
                continue
            before = line[:cmm.start()]
            after = line[cmm.end():]
            # "CAS: 7775-27-1 성분명 85–90%" — CAS 라벨 뒤 또는 줄 머리에
            # CAS가 오는 형식은 성분명·함유량을 CAS 뒤에서 찾는다
            if not before.strip() or \
                    re.search(r"CAS[\s.:：번호No또는식별\-]*$", before, re.I):
                m = _CONTENT_RX.search(after)
                content = m.group(1) if m else ""
                name = after[:m.start()] if m else after
                # 성분명이 없으면 바로 윗줄(표 헤더 제외)을 성분명으로 본다
                if not _clean_component_name(name):
                    name = ""
                    for j in range(i - 1, max(i - 3, -1), -1):
                        prev = lines[j].strip()
                        if prev and not re.search(
                                r"성\s*분|분\s*류|함유량|CAS|번호|^\d|[:：]",
                                prev):
                            name = prev
                            break
                add(name, cas, content)
            else:
                # "성분명 (이명) CAS 함유량" — 행 형식
                m = re.match(r"\s*(" + _CONTENT_TOK + r")\s*(?:%|이상|이하)?\s*$",
                             after) or re.match(r"\s*(" + _CONTENT_TOK + r")",
                                                after)
                content = m.group(1) if m else ""
                if not content:
                    # "CAS 식별번호 함유량" — 식별번호(KE-03964 등) 뒤에
                    # 함유량이 오는 형식은 줄 끝에서 찾는다. 단 EC번호 꼬리
                    # ("231-595-7"의 "595-7")를 함유량으로 오인하지 않도록
                    # 숫자·붙임표 바로 뒤에서 시작하는 매치는 버린다.
                    m = _CONTENT_RX.search(after)
                    if m:
                        pos = m.start(1) + \
                            len(m.group(1)) - len(m.group(1).lstrip())
                        if pos == 0 or after[pos - 1] not in "-0123456789":
                            content = m.group(1).strip()
                if not content and after.strip() in ("~", "-", "–", "—"):
                    # 함유량 범위가 위·아래 줄에 세로로 걸친 형식(한국가스공사):
                    #   "... 99.9994" / "성분명 CAS ~" / "... 99.9997"
                    def _tail_num(j):
                        if 0 <= j < len(lines):
                            tm = re.search(r"(\d+(?:\.\d+)?)\s*%?\s*$",
                                           lines[j].strip())
                            return tm.group(1) if tm else ""
                        return ""
                    lo = _tail_num(i - 1) or _tail_num(i - 2)
                    hi = _tail_num(i + 1) or _tail_num(i + 2)
                    if lo and hi:
                        content = f"{lo} ~ {hi}"
                add(_row_name(before), cas, content)

    # 4) 영업비밀 성분 — CAS 자리에 "영업비밀"로 적는 행
    for line in lines:
        if not _SECRET_RX.search(line) or _CAS_RX.search(line):
            continue                      # CAS가 있는 행은 위에서 처리됨
        m = re.match(r"^\s*(\S.*?)\s+(?:영\s*업\s*비\s*밀|기업\s*비밀|"
                     r"trade\s*secret)\s*(.*)$", line, re.I)
        if not m:
            continue
        name = _row_name(m.group(1))
        # 문장·각주("...제19조(비밀유지 항목)에 의거한 영업비밀임" 등)는
        # 성분 행이 아니다
        if not name or name.startswith(("(", "※")) or re.search(
                r"법|따라|해당|비공개|승인|정보|자료|의거|고시|기준|항목|"
                r"비밀유지|명칭", name):
            continue
        cm2 = re.search(_CONTENT_TOK, m.group(2))
        add(name, "영업비밀", cm2.group(0) if cm2 else "")
    return comps


def _sentences(items: list) -> list:
    """한 줄에 여러 문장이 몰린 항목을 문장 단위로 나눈다 (응급조치용)."""
    out = []
    for it in items:
        it = _RESTATED_RX.sub("", it).strip()
        if not it:
            continue
        parts = re.split(r"(?<=[.!?])\s+(?=[가-힣A-Z(])", it)
        out.extend(p.strip() for p in parts if p.strip())
    return out


def parse_msds(pdf_source, source_name: str = "") -> MsdsData:
    data = MsdsData(source_name=source_name)
    text = extract_text(pdf_source)
    if len(text.strip()) < 50:
        data.warnings.append(
            "PDF에서 텍스트를 추출하지 못했습니다. 스캔본(이미지) MSDS인 경우 "
            "OCR 처리된 PDF를 사용하거나 항목을 직접 입력해 주세요.")
        return data
    text = clean_text(text)

    sections = split_sections(text)
    if not sections:
        data.warnings.append("MSDS 표준 항목 헤더를 찾지 못해 전체 텍스트에서 키워드로 추출합니다.")
        sections = {0: text}
    whole = text

    # 1) 제품명 ──────────────────────────────────────────────
    # "제품명"/"품명" 라벨, 라벨만 있고 값이 다음 줄인 형식("가. 품명" 줄바꿈),
    # "물질명:"으로 적는 형식(OCI 등 — 1항 안에서만), 지침 문구가 섞인 형식
    # ("제품명 (경고표지 상에 사용되는 것과 동일한 명칭...을 기재한다)")을 지원한다.
    sec1 = sections.get(1, whole)

    def _pick_name(text, pat, require_colon=False):
        tail = r"\s*[:：]\s*([^\n]*)" if require_colon else \
               r"\s*[:：]?[ \t]*([^\n]*)"
        for pm in re.finditer(pat + tail, text):
            val = re.sub(r"^[:：·ㆍ\-\s]+", "", pm.group(1).strip())
            if not val:
                # 라벨만 있는 줄 → 다음 줄이 값 ("가. 품명 ⏎ 초저유황경유 ...")
                rest = text[pm.end():].lstrip("\n").split("\n", 1)[0]
                val = re.sub(r"^[\s·ㆍ•○\-–—]+", "", rest).strip()
            # 양식 지침 문구는 건너뛴다
            if not val or val.startswith("(") or \
                    re.search(r"기재한다|분류\s*코드", val):
                continue
            return val
        return ""

    data.product_name = (
        _pick_name(sec1, r"제\s*품\s*명")
        or _pick_name(sec1, r"(?<![상제])품\s*명")   # "상품명(동의어)"은 제외
        or (_pick_name(sec1, r"물\s*질\s*명", require_colon=True)
            if 1 in sections else "")
        or _pick_name(whole, r"제\s*품\s*명"))
    if not data.product_name:
        data.warnings.append("제품명을 찾지 못했습니다.")

    # 1항 제조사·3항 구성성분·개정일자 — 화학물질 도입검토 메뉴에서 사용
    data.manufacturer = extract_manufacturer(sec1)
    data.components = drop_product_row(
        extract_components(sections.get(3, "")), data.product_name)
    data.revision_date = extract_revision_date(whole)

    # 2) 유해성·위험성 ───────────────────────────────────────
    sec2 = sections.get(2, whole)
    # 위험성평가 메뉴용 — H-code(구분 포함)·8/9/11/12항 수치 데이터
    data.hcodes = extract_hcodes(sec2)
    data.risk = extract_risk_data(sections)
    h_codes = sorted(set(re.findall(r"H\d{3}", sec2)))

    hz_block = grab_block(
        sec2, r"유해\s*[·ㆍ]?\s*위험\s*문구\s*[:：]?",
        [r"예방\s*조치\s*문구", r"신호어", r"그림\s*문자", _SUB_HEAD,
         r"기타\s*유해성", r"NFPA"])
    data.hazards = bulletize(hz_block)
    if not h_codes:
        # 2항 유해성·위험성에 H-code가 하나도 없으면 유해성이 없는 물질로
        # 보아 '해당없음'으로 기재한다
        if data.hazards and data.hazards != [NONE_TEXT]:
            data.warnings.append(
                "2항에 H-code가 없어 유해·위험문구를 '해당없음'으로 표기했습니다.")
        data.hazards = [NONE_TEXT]
    elif not data.hazards and _none_stated(hz_block):
        # 원문이 "없음/해당없음/내용없음/누락" 등으로 명시한 경우
        data.hazards = [NONE_TEXT]
    elif not data.hazards:
        data.hazards = [H_STATEMENTS[c] for c in h_codes if c in H_STATEMENTS]
        if data.hazards:
            data.warnings.append("유해·위험문구를 H-code로부터 표준 문구로 복원했습니다.")
    if not data.hazards:
        data.hazards = [NONE_TEXT]
        data.warnings.append("유해·위험문구를 찾지 못해 '해당없음'으로 표기했습니다.")

    # 신호어 ("신호어 : 위험" / "신호어 위험" / 다음 줄에 "- 위험" 모두 인식)
    m = re.search(r"신호어\s*[:：]?\s*(위험|경고)", sec2) or \
        re.search(r"신호어[^\n]*\n\s*[-–—·ㆍ○]*\s*(위험|경고)", sec2) or \
        re.search(r"신호어\s*[:：]?\s*(위험|경고)", whole)
    if m:
        data.signal_word = m.group(1)
    elif h_codes:
        data.signal_word = signal_word_for_codes(h_codes)
        data.warnings.append("신호어를 H-code로부터 추론했습니다.")

    # 그림문자: 명시된 GHS 코드 > 그림문자 설명 키워드 > H-code 추론
    pics = sorted(set(re.findall(r"GHS0[1-9]", sec2)))
    if not pics:
        kw_map = [("폭발", "GHS01"), ("인화", "GHS02"), ("산화", "GHS03"),
                  ("고압가스", "GHS04"), ("부식", "GHS05"), ("해골", "GHS06"),
                  ("독성", "GHS06"), ("느낌표", "GHS07"), ("감탄", "GHS07"),
                  ("건강유해", "GHS08"), ("환경", "GHS09")]
        pic_block = grab_block(sec2, r"그림\s*문자\s*[:：]?",
                               [r"신호어", r"유해\s*[·ㆍ]?\s*위험\s*문구", r"○"])
        for kw, code in kw_map:
            if kw in pic_block:
                pics.append(code)
        pics = sorted(set(pics))
    if not pics and h_codes:
        pics = pictograms_for_codes(h_codes)
        if pics:
            data.warnings.append("그림문자를 H-code로부터 추론했습니다. 확인 후 수정하세요.")
    data.pictograms = pics

    # 예방조치문구(예방/저장 위주 = 취급주의 사항)
    # 라벨은 "예방 :" 또는 줄 단독 "예방"(Merck) 형식 모두 지원
    _prec_stops = [r"^\s*대응\s*[:：]?[ \t]*$", r"대응\s*[:：]",
                   r"^\s*저장\s*[:：]?[ \t]*$", r"저장\s*[:：]",
                   r"^\s*폐기\s*[:：]?[ \t]*$", r"폐기\s*[:：]",
                   r"기타\s*유해성", _SUB_HEAD, r"NFPA"]
    prev_block = grab_block(sec2, r"(?:예방\s*[:：]|^\s*예방[ \t]*$)", _prec_stops)
    store_block = grab_block(sec2, r"(?:저장\s*[:：]|^\s*저장[ \t]*$)",
                             [p for p in _prec_stops if "저장" not in p])
    if not prev_block:
        prev_block = grab_block(
            sec2, r"예방\s*조치\s*문구\s*[:：]?",
            [r"기타\s*유해성", _SUB_HEAD, r"NFPA"])
    data.precautions = bulletize(prev_block) + bulletize(store_block)
    if not data.precautions:
        data.precautions = [NONE_TEXT]
        if not (_none_stated(prev_block) or _none_stated(store_block)):
            data.warnings.append(
                "예방조치문구(취급주의 사항)를 찾지 못해 '해당없음'으로 표기했습니다.")

    # 4) 응급조치 요령 ───────────────────────────────────────
    sec4 = sections.get(4, whole)
    _aid_stops = {
        "eye": r"눈에\s*들어갔을\s*때",
        "skin": r"피부에\s*접촉",
        "inhale": r"흡입\s*(?:했을|한|시)",
        "ingest": r"(?:먹었을|삼켰을)\s*때",
    }
    # 주의: 정지 패턴은 소제목에만 걸려야 한다. "의료진의"처럼 짧은 패턴은
    # "의료진의 도움을 구한다" 같은 본문 문장을 잘라 버린다.
    _aid_common = [_SUB_HEAD, r"가장\s*중요한", r"일반적인\s*조치",
                   r"기타\s*의사의|의사의\s*주의사항|의료진의\s*주의",
                   r"즉각적인\s*의료\s*처?치", r"급성\s*증상"]

    def aid(key, start_pat):
        # 자기 자신의 라벨은 정지 조건에서 빼서, 본문이 라벨을 반복하는 형식도 지원
        stops = [p for k, p in _aid_stops.items() if k != key] + _aid_common
        return _sentences(bulletize(grab_block(sec4, start_pat, stops)))

    eye = aid("eye", r"눈에\s*들어갔을\s*때\s*[:：]?")
    skin = aid("skin", r"피부에\s*접촉(?:했을|한)?\s*(?:때)?\s*[:：]?")
    data.inhalation = aid("inhale", r"흡입\s*(?:했을\s*때|한\s*경우|시)\s*[:：]?")
    data.skin_eye = skin + eye
    data.ingestion = aid("ingest", r"(?:먹었을|삼켰을)\s*때\s*[:：]?")
    if not (eye or skin or data.inhalation or data.ingestion):
        data.warnings.append("응급조치 요령(4항)을 찾지 못했습니다.")

    # 5)+6) 응급대응: 소화제·화재 유해성·누출 대처 ──────────
    sec5 = sections.get(5, "")
    sec6 = sections.get(6, "")
    emergency = []
    ext = bulletize(grab_block(
        sec5, r"(?:적절한\s*(?:\(및\s*부적절한\)?\s*)?)?소화제\s*[:：]?",
        [r"부적절한", r"안전상의\s*이유로", r"사용해서는\s*안되는",
         r"화학물질로부터", r"^\s*[·ㆍ○\-]*\s*본\s*화학물질",
         r"특[정별]\s*유해성", _SUB_HEAD,
         r"소방대원|소방관|화재\s*진압", r"그\s*밖의"]))
    # "· 소화제" 밑에 "· 적절한 소화제: ..."가 다시 오는 형식(라벨 중복) 정리
    ext = [x for x in (re.sub(r"^(?:적절한\s*)?소화제\s*[:：]\s*", "", x).strip()
                       for x in ext) if x]
    if ext:
        emergency.append("적절한 소화제 : " + ", ".join(x.rstrip(",.") for x in ext[:3]))
    fire_hz = _sentences(bulletize(grab_block(
        sec5, r"(?:화학물질로부터\s*생기는\s*|(?:화학물질이나\s*혼합물에서\s*)?발생하는\s*)?"
              r"특[정별]\s*유해성\s*[:：]?",
        [_SUB_HEAD, r"소방대원", r"소방관", r"화재\s*진압\s*시", r"그\s*밖의"])))
    emergency += fire_hz[:3]
    spill = _sentences(bulletize(grab_block(
        sec6, r"정화\s*(?:또는\s*제거)?\s*방법(?:과\s*소재)?\s*[:：]?",
        [_SUB_HEAD, r"타\s*섹션\s*참조", r"다른\s*항목?\s*참조",
         r"^\s*(?:제\s*|항\s*)?7\s*[.):：]"])))
    emergency += spill[:4]
    data.emergency = emergency
    if not emergency:
        data.warnings.append("응급대응(화재·누출 대처) 정보를 찾지 못했습니다.")

    # 8) 개인 보호구 ─────────────────────────────────────────
    sec8 = sections.get(8, whole)
    # 정지 조건은 라벨이 "줄 단독"이거나 "줄 머리(공백 뒤 본문 허용)"로 나올 때만
    # 걸리게 해서 본문 속 "눈 보호용 도구" 같은 표현에 잘리지 않도록 한다
    _ppe_labels = {
        "resp": r"호흡기\s*보호", "eye": r"눈\s*보호",
        "hand": r"손\s*보호", "body": r"신체\s*보호",
        "full": r"전체\s*보호", "splash": r"튐\s*보호",
    }
    _ppe_common = [r"위생상", r"주\s*변\s*환경에\s*대한", r"환경\s*노출\s*방지",
                   _SUB_HEAD, r"^\s*(?:제\s*|항\s*)?9\s*[.):：]"]
    _BUL = r"[·ㆍ○●◦•∙\-–—*\s]*"
    # "1) 호흡기 보호"처럼 번호가 붙는 형식(OCI 등)의 줄 머리 번호
    _NUM = r"(?:\d{1,2}\s*[).]\s*)?"
    ppe = []

    def grab8(key):
        # 정지: 다른 라벨이 줄 단독("눈 보호", "2) 눈 보호"), 줄 머리+콜론
        # ("눈 보호 : "), 줄 머리+공백+본문("눈 보호 눈에 자극을...") 형식일 때.
        stops = []
        for k, p in _ppe_labels.items():
            if k == key:
                continue
            stops.append(r"^\s*" + _NUM + p + r"\s*[:：]?[ \t]*$")
            stops.append(r"^" + _BUL + p + r"\s*[:：]")
            stops.append(r"^\s*" + _NUM + p + r"(?=[ \t])")
        stops += _ppe_common
        # 시작: "라벨 :", 줄 단독 "라벨"/"1) 라벨", 줄 머리 "라벨 본문..." 지원
        pat = (r"(?:" + _ppe_labels[key] + r"\s*[:：]|^\s*" + _NUM
               + _ppe_labels[key] + r"[ \t]*$|^\s*" + _NUM
               + _ppe_labels[key] + r"(?=[ \t]))")
        block = grab_block(sec8, pat, stops)
        # 블록 안에서 같은 라벨이 반복되면("호흡기 보호 입자상 물질의...") 제거
        block = re.sub(r"(?m)^\s*" + _ppe_labels[key] + r"\s*[:：]?\s*", "",
                       block)
        return condense_ppe(bulletize(block))

    resp = grab8("resp")
    eye_p = grab8("eye")
    hand = grab8("hand")
    body = grab8("body")
    if resp:
        ppe.append("호흡기 보호 : " + " ".join(resp))
    if eye_p:
        ppe.append("눈 보호 : " + " ".join(eye_p))
    if hand:
        ppe.append("손 보호 : " + " ".join(hand))
    if body:
        ppe.append("신체 보호 : " + " ".join(body))
    data.ppe = ppe
    if not ppe:
        data.warnings.append("개인 보호구(8항)를 찾지 못했습니다.")

    # 14) 국제연합번호(UN No.) — 유해화학물질 규격 표지의 표에 기재 ────
    sec14 = sections.get(14, "")
    m = re.search(r"(?:유엔|UN|국제\s*연합)\s*번호[^\d\n]{0,40}(\d{4})", sec14) or \
        re.search(r"\bUN\s*(\d{4})\b", sec14)
    if m:
        data.un_number = m.group(1)

    # 띄어쓰기 자동 교정 (글자 사이 공백·붙은 문장 이상이 있는 줄만, 글자 불변)
    for f in ("hazards", "precautions", "ppe", "inhalation",
              "skin_eye", "ingestion", "emergency"):
        setattr(data, f, fix_spacing_all(getattr(data, f)))

    # 항목 수 제한: 취급주의 8개, 응급조치·응급대응 각 5개 (중복은 병합·삭제)
    data.hazards = dedupe_merge(data.hazards)
    data.precautions = curate_precautions(data.precautions)
    for f in ("inhalation", "skin_eye", "ingestion", "emergency"):
        setattr(data, f, dedupe_merge(getattr(data, f))[:MAX_AID])

    return data
