# -*- coding: utf-8 -*-
"""MSDS PDF에서 '화학물질 작업공정별 관리 요령' 양식에 필요한 항목을 추출한다.

한국 고용노동부 고시(16개 항목) 형식의 MSDS를 대상으로 하며,
항목 구성이 다르더라도 키워드 기반으로 최대한 추출한다.
"""
import re
from dataclasses import dataclass, field

import pdfplumber

from ghs_data import (H_STATEMENTS, pictograms_for_codes, signal_word_for_codes)


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


def extract_text(pdf_source) -> str:
    """PDF 전체 텍스트를 추출한다. pdf_source는 경로 또는 파일 객체."""
    pages = []
    with pdfplumber.open(pdf_source) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages)


# ── 섹션 분리 ────────────────────────────────────────────────────────────
# "2. 유해성·위험성", "제2항 유해성", "SECTION 2" 등의 헤더를 인식
_SECTION_KEYS = {
    1: r"(?:화학제품과\s*회사|제품\s*및\s*회사|화학제품에\s*관한)",
    2: r"유해성\s*[·ㆍ.,]?\s*위험성",
    3: r"구성\s*성분|구성성분의\s*명칭",
    4: r"응급조치\s*요령",
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
    """텍스트를 MSDS 항목 번호별로 나눈다."""
    hits = []
    for num, pat in _SECTION_KEYS.items():
        rx = re.compile(
            r"^[^\S\n]*(?:제\s*)?%d\s*[.)항]?\s*(?:%s)" % (num, pat), re.M)
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

def grab_block(text: str, start_pat: str, stop_pats: list) -> str:
    """start_pat 라벨 다음부터 stop_pats 중 하나가 나오기 전까지의 텍스트."""
    m = re.search(start_pat, text)
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
    r"^(자료\s*없음|해당\s*없음|자료없음|해당없음|없음|N/?A|-|페이지|page|\d+\s*/\s*\d+)$",
    re.I)


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
            # "H315 피부에 자극을 일으킴" -> 코드 제거, 코드만 있는 줄은 버림
            line = re.sub(r"^[HP]\d{3}(?:\s*\+\s*[HP]\d{3})*\s*[:.]?\s*", "", line).strip()
            if not line:
                continue
        # 표식 없는 줄이 이어지고 앞 문장이 끝나지 않았으면 줄바꿈으로 잘린 문장으로 본다
        if items and not has_marker and not items[-1].endswith(_SENT_END):
            items[-1] = items[-1] + " " + line
        else:
            items.append(line)
    return items


def parse_msds(pdf_source, source_name: str = "") -> MsdsData:
    data = MsdsData(source_name=source_name)
    text = extract_text(pdf_source)
    if len(text.strip()) < 50:
        data.warnings.append(
            "PDF에서 텍스트를 추출하지 못했습니다. 스캔본(이미지) MSDS인 경우 "
            "OCR 처리된 PDF를 사용하거나 항목을 직접 입력해 주세요.")
        return data

    sections = split_sections(text)
    if not sections:
        data.warnings.append("MSDS 표준 항목 헤더를 찾지 못해 전체 텍스트에서 키워드로 추출합니다.")
        sections = {0: text}
    whole = text

    # 1) 제품명 ──────────────────────────────────────────────
    sec1 = sections.get(1, whole)
    m = re.search(r"제품명\s*[::]?\s*([^\n]+)", sec1)
    if not m:
        m = re.search(r"(?:가\s*[.)]\s*)?제품명\s*[::]?\s*([^\n]+)", whole)
    if m:
        name = m.group(1).strip()
        name = re.sub(r"^[::·ㆍ\-\s]+", "", name)
        data.product_name = name
    else:
        data.warnings.append("제품명을 찾지 못했습니다.")

    # 2) 유해성·위험성 ───────────────────────────────────────
    sec2 = sections.get(2, whole)
    h_codes = sorted(set(re.findall(r"H\d{3}", sec2)))

    hz_block = grab_block(
        sec2, r"유해\s*[·ㆍ]?\s*위험\s*문구\s*[::]?",
        [r"예방\s*조치\s*문구", r"신호어", r"그림\s*문자", r"^\s*[다라마]\s*[.)]",
         r"기타\s*유해성", r"NFPA"])
    data.hazards = bulletize(hz_block)
    if not data.hazards and h_codes:
        data.hazards = [H_STATEMENTS[c] for c in h_codes if c in H_STATEMENTS]
        if data.hazards:
            data.warnings.append("유해·위험문구를 H-code로부터 표준 문구로 복원했습니다.")
    if not data.hazards:
        data.warnings.append("유해·위험문구를 찾지 못했습니다.")

    # 신호어
    m = re.search(r"신호어\s*[::]?\s*(위험|경고)", sec2) or \
        re.search(r"신호어\s*[::]?\s*(위험|경고)", whole)
    if m:
        data.signal_word = m.group(1)
    elif h_codes:
        data.signal_word = signal_word_for_codes(h_codes)
        data.warnings.append("신호어를 H-code로부터 추론했습니다.")

    # 그림문자: 명시된 GHS 코드 우선, 없으면 H-code로 추론
    pics = sorted(set(re.findall(r"GHS0[1-9]", sec2)))
    if not pics:
        kw_map = [("폭발", "GHS01"), ("인화", "GHS02"), ("산화", "GHS03"),
                  ("고압가스", "GHS04"), ("부식", "GHS05"), ("해골", "GHS06"),
                  ("독성", "GHS06"), ("느낌표", "GHS07"), ("감탄", "GHS07"),
                  ("건강유해", "GHS08"), ("환경", "GHS09")]
        pic_block = grab_block(sec2, r"그림\s*문자\s*[::]?",
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
    _prec_stops = [r"대응\s*[::]", r"저장\s*[::]", r"폐기\s*[::]",
                   r"기타\s*유해성", r"^\s*[다라마]\s*[.)]", r"NFPA"]
    prev_block = grab_block(sec2, r"예방\s*[::]", _prec_stops)
    store_block = grab_block(sec2, r"저장\s*[::]",
                             [p for p in _prec_stops if "저장" not in p])
    if not prev_block:
        prev_block = grab_block(
            sec2, r"예방\s*조치\s*문구\s*[::]?",
            [r"기타\s*유해성", r"^\s*[다라마]\s*[.)]", r"NFPA"])
    data.precautions = bulletize(prev_block) + bulletize(store_block)
    if not data.precautions:
        data.warnings.append("예방조치문구(취급주의 사항)를 찾지 못했습니다.")

    # 4) 응급조치 요령 ───────────────────────────────────────
    sec4 = sections.get(4, whole)
    stops4 = [r"^\s*[가나다라마]\s*[.)]", r"눈에\s*들어갔을\s*때", r"피부에\s*접촉",
              r"흡입\s*(?:했을|한|시)", r"먹었을\s*때", r"삼켰을\s*때",
              r"기타\s*의사의|의사의\s*주의사항|의료진의"]
    eye = bulletize(grab_block(sec4, r"눈에\s*들어갔을\s*때\s*[::]?", stops4))
    skin = bulletize(grab_block(sec4, r"피부에\s*접촉(?:했을|한)?\s*(?:때)?\s*[::]?", stops4))
    inhale = bulletize(grab_block(sec4, r"흡입\s*(?:했을\s*때|한\s*경우|시)\s*[::]?", stops4))
    ingest = bulletize(grab_block(sec4, r"(?:먹었을|삼켰을)\s*때\s*[::]?", stops4))
    data.inhalation = inhale
    data.skin_eye = skin + eye
    data.ingestion = ingest
    if not (eye or skin or inhale or ingest):
        data.warnings.append("응급조치 요령(4항)을 찾지 못했습니다.")

    # 5)+6) 응급대응: 소화제·화재 유해성·누출 대처 ──────────
    sec5 = sections.get(5, "")
    sec6 = sections.get(6, "")
    emergency = []
    ext = bulletize(grab_block(
        sec5, r"(?:적절한\s*(?:\(및\s*부적절한\)?\s*)?)?소화제\s*[::]?",
        [r"부적절한", r"화학물질로부터", r"특정\s*유해성", r"^\s*[나다라]\s*[.)]",
         r"소방대원|화재\s*진압"]))
    if ext:
        emergency.append("적절한 소화제 : " + ", ".join(x.rstrip(",.") for x in ext[:3]))
    fire_hz = bulletize(grab_block(
        sec5, r"(?:화학물질로부터\s*생기는\s*)?특정\s*유해성\s*[::]?",
        [r"^\s*[다라]\s*[.)]", r"소방대원", r"화재\s*진압\s*시"]))
    emergency += fire_hz[:3]
    spill = bulletize(grab_block(
        sec6, r"정화\s*(?:또는\s*제거)?\s*방법\s*[::]?",
        [r"^\s*[가나다라]\s*[.)]", r"^\s*7\s*[.)]"]))
    emergency += spill[:4]
    data.emergency = emergency
    if not emergency:
        data.warnings.append("응급대응(화재·누출 대처) 정보를 찾지 못했습니다.")

    # 8) 개인 보호구 ─────────────────────────────────────────
    sec8 = sections.get(8, whole)
    stops8 = [r"호흡기\s*보호", r"눈\s*보호", r"손\s*보호", r"신체\s*보호",
              r"^\s*[가나다라마]\s*[.)]", r"^\s*9\s*[.)]", r"위생상"]
    ppe = []
    resp = bulletize(grab_block(sec8, r"호흡기\s*보호\s*[::]?", stops8))
    eye_p = bulletize(grab_block(sec8, r"눈\s*보호\s*[::]?", stops8))
    hand = bulletize(grab_block(sec8, r"손\s*보호\s*[::]?", stops8))
    body = bulletize(grab_block(sec8, r"신체\s*보호\s*[::]?", stops8))
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

    return data
