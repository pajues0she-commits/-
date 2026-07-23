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
    r"|continued\s+(?:on|from)\s+page", re.I)


def clean_text(text: str) -> str:
    """페이지 푸터·"(N쪽에 계속)" 문구·반복되는 머리글(회사 상용구 등)을 제거한다."""
    n_pages = text.count("\f") + 1
    lines = text.replace("\f", "\n").splitlines()
    counts = Counter(l.strip() for l in lines if len(l.strip()) > 1)
    # 페이지마다 반복되는 짧은 머리글("물질안전보건자료", "KR" 등)은 페이지 수
    # 기준으로, 긴 상용구는 3회 반복이면 제거한다.
    boiler = {l for l, c in counts.items()
              if (len(l) > 10 and c >= 3) or c >= max(3, n_pages - 1)}
    kept = [l for l in lines
            if l.strip() not in boiler and not _FOOTER_RX.search(l)]
    return "\n".join(kept)


# ── 섹션 분리 ────────────────────────────────────────────────────────────
_SECTION_KEYS = {
    1: r"(?:화학제품과\s*회사|제품\s*및\s*회사|화학제품에\s*관한)",
    2: r"유해성\s*[·ㆍ.,]?\s*위험성|위험\s*[·ㆍ.,]?\s*유해성",
    3: r"구성\s*성분|구성성분의\s*명칭",
    4: r"응급\s*조치\s*요령",
    5: r"폭발\s*[·ㆍ.]?\s*화재\s*시|화재\s*시\s*대처",
    6: r"누출\s*사고\s*시",
    7: r"취급\s*및\s*저장",
    8: r"노출\s*방지\s*및\s*개인\s*보호구|노출방지",
    9: r"물리\s*화학적\s*특성",
    10: r"안정성\s*및\s*반응성",
    11: r"독성에\s*관한\s*정보",
    12: r"환경에\s*미치는\s*영향",
    13: r"폐기\s*시\s*주의사항|폐기시",
    14: r"운송에\s*필요한\s*정보",
    15: r"법적\s*규제\s*현황",
    16: r"그\s*밖의\s*참고사항|기타\s*참고사항",
}


def split_sections(text: str) -> dict:
    """텍스트를 MSDS 항목 번호별로 나눈다.

    "4. 제목", "제4항 제목", "항 4: 제목", "SECTION 4 제목"을 모두 인식한다.
    """
    hits = []
    for num, pat in _SECTION_KEYS.items():
        rx = re.compile(
            r"^[^\S\n]*(?:제\s*|항\s*|SECTION\s*|섹션\s*)?%d\s*[.):：항]?\s*[:：]?\s*(?:%s)"
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
    sec1 = sections.get(1, whole)
    m = re.search(r"제품명\s*[:：]?\s*([^\n]+)", sec1) or \
        re.search(r"제품명\s*[:：]?\s*([^\n]+)", whole)
    if m:
        data.product_name = re.sub(r"^[:：·ㆍ\-\s]+", "", m.group(1).strip())
    else:
        data.warnings.append("제품명을 찾지 못했습니다.")

    # 2) 유해성·위험성 ───────────────────────────────────────
    sec2 = sections.get(2, whole)
    h_codes = sorted(set(re.findall(r"H\d{3}", sec2)))

    hz_block = grab_block(
        sec2, r"유해\s*[·ㆍ]?\s*위험\s*문구\s*[:：]?",
        [r"예방\s*조치\s*문구", r"신호어", r"그림\s*문자", _SUB_HEAD,
         r"기타\s*유해성", r"NFPA"])
    data.hazards = bulletize(hz_block)
    if not data.hazards and _none_stated(hz_block):
        # 원문이 "없음/해당없음/내용없음/누락" 등으로 명시한 경우
        data.hazards = [NONE_TEXT]
    elif not data.hazards and h_codes:
        data.hazards = [H_STATEMENTS[c] for c in h_codes if c in H_STATEMENTS]
        if data.hazards:
            data.warnings.append("유해·위험문구를 H-code로부터 표준 문구로 복원했습니다.")
    if not data.hazards:
        data.hazards = [NONE_TEXT]
        data.warnings.append("유해·위험문구를 찾지 못해 '해당없음'으로 표기했습니다.")

    # 신호어 ("신호어 : 위험" / "신호어 위험" 모두 인식)
    m = re.search(r"신호어\s*[:：]?\s*(위험|경고)", sec2) or \
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
    # 정지 조건은 "라벨만 있는 줄"(예: "눈 보호")에만 걸리게 해서
    # 본문 속 "눈 보호용 도구" 같은 표현에 잘리지 않도록 한다
    _ppe_labels = {
        "resp": r"호흡기\s*보호", "eye": r"눈\s*보호",
        "hand": r"손\s*보호", "body": r"신체\s*보호",
        "full": r"전체\s*보호", "splash": r"튐\s*보호",
    }
    _ppe_common = [r"위생상", r"주\s*변\s*환경에\s*대한", r"환경\s*노출\s*방지",
                   _SUB_HEAD, r"^\s*(?:제\s*|항\s*)?9\s*[.):：]"]
    _BUL = r"[·ㆍ○●◦•∙\-–—*\s]*"
    ppe = []

    def grab8(key):
        # 정지: 다른 라벨이 "줄 단독"이거나 "줄 머리 + 콜론"으로 나올 때만.
        # (본문 속 "눈 보호용 도구" 같은 표현에는 걸리지 않는다)
        stops = []
        for k, p in _ppe_labels.items():
            if k == key:
                continue
            stops.append(r"^\s*" + p + r"\s*[:：]?[ \t]*$")
            stops.append(r"^" + _BUL + p + r"\s*[:：]")
        stops += _ppe_common
        pat = r"(?:" + _ppe_labels[key] + r"\s*[:：]|^\s*" + _ppe_labels[key] + r"[ \t]*$)"
        return bulletize(grab_block(sec8, pat, stops))

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
