# -*- coding: utf-8 -*-
"""한글 띄어쓰기 자동 교정 (MSDS 도메인 특화).

일부 MSDS 생성 프로그램은 글자 사이에 공백을 무작위로 넣거나
("신 선 한 공 기") 문장 전체를 붙여 쓴다("즉시물로씻는다").
이 모듈은 그런 이상이 감지된 구간만 도메인 사전 기반으로 다시 띄어 쓴다.

원칙:
  * 글자 자체는 절대 바꾸지 않는다 — 공백만 넣거나 뺀다.
  * 이상 징후(연속된 한 글자 조각 3개 이상, 어절 없이 길게 붙은 문장)가
    있는 구간에만 적용한다. 이미 정상인 문장은 건드리지 않는다.
  * 사전으로 충분히 해석되지 않는 구간(낯선 화학물질명 등)은 원문 유지.
"""
import re

# ── 도메인 사전 ──────────────────────────────────────────────────────────
# NOUNS: 명사·명사구(조사가 붙을 수 있음).  FUNCS: 용언 활용형·부사·관형형 등
# (문장을 이루는 기능어 — 이것이 하나 이상 포함될 때만 붙은 문장을 띄운다).
NOUNS = """
공기 산소 물 눈 입 피부 의사 안과의사 의료진 병원 센터 독성물질 환자 피재자
호흡 인공호흡 호흡기 신체 손 발 머리 머리카락 의복 의류 의상 옷 신발
보호구 보호대 보안경 보안면 안전안경 고글 방독면 방진마스크 마스크 장갑
보호장갑 안전작업복 작업복 보호복 앞치마 장화 보호제 세척제 화장품
증기 먼지 분진 흄 가스 미스트 스프레이 에어로졸 연기 산화물
소화제 소화기 소화 분말 포말 폼 모래 이산화탄소 물분무 분말소화제
화재 폭발 폭발성 인화성 가연성 산화성 부식성 자극성 과민성 독성 유해성
환기 통풍 누출 유출 확산 접촉 흡입 섭취 노출 오염 세척 세안
용기 밀폐용기 포장 라벨 저장 보관 취급 폐기 처리 처분 규정 규제 지침
장비 도구 설비 세안설비 샤워설비 세면장 작업장 작업 공정 현장
증상 자극 화상 손상 알레르기 반응 구토 두통 현기증 마비 경련
조치 응급조치 치료 처치 진찰 검진 조언 주의 도움 상담 진료
방법 요령 수단 대책 예방 대응 안전 보건 위생 건강
시간 분 동안 이상 이하 이내 직후 즉시 경우 때 후 전 중 시 곳 것 등
지역 지방 국가 국제 당국 관청 기관 제조자 제조사 공급자 공급업체
물질 화학물질 혼합물 제품 성분 원료 시약 용액 폐기물 쓰레기 잔여물
가열 발생 방출 유독성 유독 수 다음 진화 진화방법 작용 좌우 사용 피부용
하수구 하수도 배수구 수로 하천 지하수 환경 대기 토양
방화수 진화 진압 소방 소방관 소방대원 장비 보호장비
콘택트렌즈 렌즈 흐르는물 비눗물 세정제
니트릴고무 고무 재질 재료 두께 투과 침투 관통 시간
경고 위험 신호어 그림문자 문구 항목 참조 정보 자료 목록 기준
보호용 흡수성 액체 고체 기체 가루 가연물 발화원 점화원 열 불꽃 스파크 화기
방지 금지 금연 주변 부위 부분 전신 전체 다량 소량 충분히
""".split()

FUNCS = """
씻는다 씻어낸다 씻어내시오 씻으시오 씻으십시오 씻고 씻은 씻어
마신다 마시게 마시지 마시오 마십시오 먹거나 먹지 먹은
받는다 받게 받고 받으시오 받으십시오 받을 받아야
구한다 구하시오 구하십시오 부른다 부르시오 부르십시오
제공한다 제공하고 공급받고 공급한다 공급하고
옮긴다 옮기고 옮기시오 옮기십시오 벗긴다 벗기고 벗을 벗고 벗은
헹군 헹구고 헹구시오 헹구어 토하게 토하지
사용한다 사용하고 사용하지 사용할 사용하는 사용하시오 사용하십시오 사용된 사용후
착용한다 착용하고 착용할 착용하시오 착용하십시오 착용은
보호한다 보호하고 보호하는 보호할 방문한다 방문하고
제거한다 제거하고 제거하시오 제거하십시오 제거할
방지한다 방지하고 방지하시오 피한다 피하고 피하시오 피하십시오 피할
유지한다 유지하고 보관한다 보관하고 보관하시오 저장한다 저장하고 저장하시오
처리한다 처분한다 폐기한다 폐기하고 폐기하시오
발생한다 발생할 발생될 발생하는 발생되는 방출될 방출한다 방출하는
취한다 취하고 취하시오 눕힌다 눕히고 안정시킨다
계속해서 계속 즉시 즉각 신속히 천천히 조심해서 철저히 완전히 충분히 반드시
가능하면 가능한 필요하면 필요시 필요한 몇 다시 미리 먼저 바로 절대로
자극될 자극되는 오염된 오염되는 노출된 노출되는 손상된 감염된
흐르는 붙은 남은 젖은 마른 깨끗한 신선한 따뜻한 차가운 맞는 알맞은 적절한
꽉 조이는 밀착된 밀착형 밀폐된 밀봉된 건조한 정확한
있다 있는 있을 있음 없다 없는 없음 된다 되는 될 되고 되어야 한다 하는 할 하고 하지
좋다 좋은 나쁜 크다 작은 높은 낮은 심한 가벼운
인지되고 준수되어야 확인한다 확인하고 참고하시오 참고한다 상담한다 상담하시오
문지르지 비비지 만지지 긁지 삼키지 삼켰을 삼킨 들어갔을 들이마신
접촉했을 접촉한 접촉된 묻으면 묻은 닿으면 닿은 걸린 나타나면 지속되면 느끼면
의하여 의해 대하여 대한 위하여 위한 따라 따라서 관한 인한
작용할 작용하는 작용하면 같이 혹은 또는 및 사용하여 착용하여 나서
되지 않는 않은 않고 않도록 않게 흘러들게 말아야 모아야 두지 두시오 놓지
""".split()

# 앞의 명사에 붙여 써야 하는 보조용언·접미 활용형 ("가열되거나", "발생할")
AUX_ATTACH = set("""
한다 하고 하는 할 하지 하면 하여 하시오 하십시오 함 된다 되고 되는 될
되거나 되어 되어야 되도록 됨 됩니다 하니 시킨다 시키고 시키지
""".split())

PARTICLES = ("을 를 이 가 은 는 에 의 와 과 도 만 로 나 랑 께 에서 에게 으로 "
             "이나 부터 까지 마다 처럼 보다 조차 마저 밖에 에는 에도 로는 와는 "
             "과는 에서는 에게서 으로는 으로부터 로부터").split()

_ALL_WORDS = set(NOUNS) | set(FUNCS) | set(PARTICLES) | AUX_ATTACH
_NOUN_SET = set(NOUNS)
_FUNC_SET = set(FUNCS) | AUX_ATTACH
_PARTICLE_SET = set(PARTICLES)
_MAX_WORD = max(len(w) for w in _ALL_WORDS)

_UNKNOWN_COST = 2.5     # 사전에 없는 글자 1자당 비용
_WORD_COST = 1.0        # 사전 단어 1개당 비용 (짧게 쪼개기 억제)

# 문장이 붙어 있음을 시사하는 서술형 어미(문장 끝)
_VERB_END_RX = re.compile(r"(?:한다|된다|는다|니다|시오|십시오|하라|할것|말것)\.?$")

# 한글(+공백) 구간
_HANGUL_RUN_RX = re.compile(r"[가-힣][가-힣 ]*[가-힣]|[가-힣]")


def _segment(chunk):
    """공백 없는 한글 문자열을 사전 기반 최소비용 분절. (토큰列, 커버리지) 반환."""
    n = len(chunk)
    INF = float("inf")
    cost = [INF] * (n + 1)
    back = [None] * (n + 1)   # (시작위치, 사전단어여부)
    cost[0] = 0.0
    for i in range(1, n + 1):
        lo = max(0, i - _MAX_WORD)
        for j in range(lo, i):
            w = chunk[j:i]
            if w in _ALL_WORDS:
                c = cost[j] + _WORD_COST
                if c < cost[i]:
                    cost[i], back[i] = c, (j, True)
        c = cost[i - 1] + _UNKNOWN_COST
        if c < cost[i]:
            cost[i], back[i] = c, (i - 1, False)
    tokens = []           # [(문자열, 사전단어여부)]
    i = n
    while i > 0:
        j, known = back[i]
        tokens.append((chunk[j:i], known))
        i = j
    tokens.reverse()
    # 연속된 미등록 글자는 한 덩어리로 합친다
    merged = []
    for tok, known in tokens:
        if not known and merged and not merged[-1][1]:
            merged[-1] = (merged[-1][0] + tok, False)
        else:
            merged.append((tok, known))
    known_chars = sum(len(t) for t, k in merged if k)
    return merged, (known_chars / n if n else 0.0)


def _respace(tokens):
    """분절 토큰을 맞춤법에 맞게 결합: 조사·보조용언은 앞 말에 붙인다."""
    out = []          # 토큰 문자열
    bare_noun = []    # out[i]가 조사 없는 명사인지
    for tok, known in tokens:
        if known and tok in _PARTICLE_SET and out:
            out[-1] += tok
            bare_noun[-1] = False
        elif (known and tok in AUX_ATTACH and out and bare_noun[-1]):
            out[-1] += tok            # "가열" + "되거나", "발생" + "할"
            bare_noun[-1] = False
        else:
            out.append(tok)
            bare_noun.append(known and tok in _NOUN_SET)
    return " ".join(out)


def _has_func_word(tokens):
    return any(k and t in _FUNC_SET for t, k in tokens)


def _anomalous(run):
    """공백이 망가진 구간인지 판정."""
    parts = run.split(" ")
    consec = best = 0
    for p in parts:
        consec = consec + 1 if len(p) == 1 else 0
        best = max(best, consec)
    if best >= 3:                      # "신 선 한 공 기" 형태
        return "spread"
    if len(parts) > 1 and parts[-1] == "다":
        return "spread"                # "상담한 다" — 끝의 '다'가 떨어진 형태
    for p in parts:
        if len(p) >= 7 and _VERB_END_RX.search(p):
            return "glued"             # "즉시물로씻는다" 형태
    if " " not in run and len(run) >= 6:
        return "maybe_glued"           # "꽉조이는보안경" 형태(신중 적용)
    return None


def fix_spacing(text: str) -> str:
    """이상이 감지된 한글 구간의 띄어쓰기를 교정한다. 글자는 바꾸지 않는다."""
    if not text or not any("가" <= c <= "힣" for c in text):
        return text

    def repl(m):
        run = m.group(0)
        kind = _anomalous(run)
        if not kind:
            return run
        chunk = run.replace(" ", "")
        tokens, coverage = _segment(chunk)
        if kind == "spread":
            # 원래 띄어쓰기가 이미 망가져 있으므로 사전 해석이 충분하면 교정
            if coverage >= 0.65:
                return _respace(tokens)
            # 사전으로 못 풀면 조각난 공백만 제거(원문에 없던 공백이므로 안전)
            return chunk if len(tokens) == 1 else run
        # 붙은 문장: 확실할 때만(용언 포함 + 높은 커버리지) 띄운다
        need = 0.85 if kind == "glued" else 1.0
        if coverage >= need and _has_func_word(tokens) and len(tokens) > 1:
            return _respace(tokens)
        return run

    return _HANGUL_RUN_RX.sub(repl, text)


def fix_spacing_all(items):
    """문자열 리스트에 fix_spacing을 적용한다."""
    return [fix_spacing(x) for x in items]
