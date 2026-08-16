# -*- coding: utf-8 -*-
"""인바디(InBody) 기록 관리용 엑셀 파일 생성 스크립트.

생성물: inbody_tracker.xlsx
  - 사용안내 : 입력 방법 / 항목 설명
  - 인바디기록 : 측정값 입력 시트 (100회분)
  - 요약 : 항목별 최초/최근/변화량/최소/최대/평균 (수식)
  - 그래프 : 항목별 추이 그래프
"""

from datetime import date

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.chart.marker import Marker
from openpyxl.chart.axis import ChartLines
from openpyxl.drawing.line import LineProperties
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

FONT = "Arial"

# ---------------------------------------------------------------- 기본 설정
FIRST_DATA_ROW = 4          # 실제 입력이 시작되는 행 (4행은 예시)
LAST_DATA_ROW = 103         # 100회분
HEADER_ROW = 3

INK = "1F2933"              # 본문 글자색
MUTED = "6B7785"            # 보조 글자색
HEAD_BG = "1F3A5F"          # 헤더 배경
BAND_BG = "EDF2F7"          # 그룹 구분 배경
INPUT_BG = "FFFDE7"         # 입력 셀 배경
RULE = "C7D0DA"             # 테두리

# 그래프 색상 (항목 그룹별로 구분)
C_BODY = "2F6FB3"           # 체성분 계열
C_FAT = "D06B2C"            # 지방 계열
C_SCORE = "3E8E7E"          # 점수/대사 계열
C_GIRTH = "7A5EA8"          # 둘레 계열

# (헤더, 단위표시, 숫자서식, 열너비, 그래프색, 예시값, 설명)
COLUMNS = [
    ("측정일",          "",       "yyyy-mm-dd", 13, None,    date(2026, 1, 5), "인바디를 측정한 날짜"),
    ("체중",            "kg",     "0.0",        10, C_BODY,  68.4,  "인바디 결과지의 체중"),
    ("골격근량",        "kg",     "0.0",        11, C_BODY,  31.2,  "SMM(골격근량). 근육량과 다른 항목이므로 주의"),
    ("체지방량",        "kg",     "0.0",        11, C_FAT,   14.8,  "체지방의 무게"),
    ("체지방률",        "%",      "0.0",        11, C_FAT,   21.6,  "퍼센트 숫자만 입력 (예: 21.6)"),
    ("내장지방",        "레벨",   "0.0",        11, C_FAT,   7,     "내장지방 레벨 (보통 1~20). 장비에 따라 면적(cm2)이면 그대로 입력"),
    ("복부지방률",      "WHR",    "0.00",       12, C_FAT,   0.86,  "허리-엉덩이 둘레 비율(WHR). 예: 0.86"),
    ("신체발달점수",    "점",     "0",          13, C_SCORE, 78,    "인바디 점수 (보통 100점 만점)"),
    ("기초대사량",      "kcal",   "#,##0",      12, C_SCORE, 1580,  "BMR"),
    ("가슴",            "cm",     "0.0",        10, C_GIRTH, 98.5,  "겉둘레 - 가슴"),
    ("복부",            "cm",     "0.0",        10, C_GIRTH, 84.0,  "겉둘레 - 복부(배꼽 기준)"),
    ("오른팔",          "cm",     "0.0",        10, C_GIRTH, 32.5,  "겉둘레 - 오른팔"),
    ("왼팔",            "cm",     "0.0",        10, C_GIRTH, 32.1,  "겉둘레 - 왼팔"),
    ("오른허벅지",      "cm",     "0.0",        12, C_GIRTH, 54.2,  "겉둘레 - 오른쪽 허벅지"),
    ("왼허벅지",        "cm",     "0.0",        11, C_GIRTH, 53.8,  "겉둘레 - 왼쪽 허벅지"),
    ("목",              "cm",     "0.0",        10, C_GIRTH, 37.4,  "겉둘레 - 목"),
    ("엉덩이",          "cm",     "0.0",        10, C_GIRTH, 97.6,  "겉둘레 - 엉덩이"),
]

GIRTH_START = 10            # J열 = 가슴
GIRTH_END = 17              # Q열 = 엉덩이

DATA_SHEET = "인바디기록"


def head_font(size=11, bold=True, color="FFFFFF"):
    return Font(name=FONT, size=size, bold=bold, color=color)


def body_font(size=11, bold=False, color=INK, italic=False):
    return Font(name=FONT, size=size, bold=bold, color=color, italic=italic)


thin = Side(style="thin", color=RULE)
box = Border(left=thin, right=thin, top=thin, bottom=thin)


# ------------------------------------------------------------ 1. 사용안내
def build_guide(ws):
    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 12
    ws.column_dimensions["D"].width = 72

    ws["B2"] = "인바디 기록 관리표 - 사용 안내"
    ws["B2"].font = body_font(16, bold=True, color=HEAD_BG)

    lines = [
        "1. '인바디기록' 시트의 노란색 칸에만 값을 입력하세요. (4행은 입력 예시입니다 - 지우고 사용)",
        "2. 측정일은 위에서부터 순서대로 채우면 되고, 순서가 뒤바뀌어도 요약/그래프는 정상 동작합니다.",
        "3. '요약' 시트와 '그래프' 시트는 수식/자동 연결이라 따로 손댈 필요가 없습니다.",
        "4. 기본 100회분(4~103행)까지 준비되어 있습니다.",
        "5. 값이 비어 있는 항목은 그래프에서 그냥 건너뜁니다. 측정 안 한 항목은 비워두세요.",
    ]
    r = 4
    for line in lines:
        ws.cell(row=r, column=2, value=line).font = body_font(11)
        ws.merge_cells(start_row=r, start_column=2, end_row=r, end_column=4)
        ws.cell(row=r, column=2).alignment = Alignment(vertical="center")
        ws.row_dimensions[r].height = 20
        r += 1

    r += 1
    ws.cell(row=r, column=2, value="항목 설명").font = body_font(13, bold=True, color=HEAD_BG)
    r += 1
    for c, label in enumerate(["항목", "단위", "설명"], start=2):
        cell = ws.cell(row=r, column=c, value=label)
        cell.font = head_font()
        cell.fill = PatternFill("solid", fgColor=HEAD_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = box
    ws.row_dimensions[r].height = 22
    r += 1

    for header, unit, _fmt, _w, _color, _sample, desc in COLUMNS:
        ws.cell(row=r, column=2, value=header).font = body_font(11, bold=True)
        ws.cell(row=r, column=3, value=unit or "-").font = body_font(11, color=MUTED)
        ws.cell(row=r, column=4, value=desc).font = body_font(11)
        ws.cell(row=r, column=3).alignment = Alignment(horizontal="center")
        for c in (2, 3, 4):
            ws.cell(row=r, column=c).border = box
        r += 1

    r += 1
    ws.cell(row=r, column=2, value="※ 체지방률은 % 기호 없이 숫자만(21.6), 복부지방률은 WHR 값(0.86)으로 입력합니다.").font = body_font(10, color=MUTED)
    r += 1
    ws.cell(row=r, column=2, value="※ 예시 행의 값은 형식을 보여주기 위한 임의의 값이며 실제 측정치가 아닙니다.").font = body_font(10, color=MUTED)


# ---------------------------------------------------------- 2. 인바디기록
def build_data(ws):
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B4"

    ws["A1"] = "인바디 측정 기록"
    ws["A1"].font = body_font(15, bold=True, color=HEAD_BG)
    ws["A2"] = "노란색 칸에 측정값을 입력하세요. (4행은 예시 - 삭제 후 사용)"
    ws["A2"].font = body_font(10, color=MUTED)

    # 그룹 밴드
    ws.merge_cells(start_row=2, start_column=10, end_row=2, end_column=17)
    band = ws.cell(row=2, column=10, value="부위별 근육발달 (겉둘레, cm)")
    band.font = body_font(11, bold=True, color=HEAD_BG)
    band.alignment = Alignment(horizontal="center", vertical="center")
    band.fill = PatternFill("solid", fgColor=BAND_BG)

    input_fill = PatternFill("solid", fgColor=INPUT_BG)

    for idx, (header, unit, fmt, width, _color, sample, _desc) in enumerate(COLUMNS, start=1):
        letter = get_column_letter(idx)
        ws.column_dimensions[letter].width = width

        title = f"{header}({unit})" if unit else header
        hc = ws.cell(row=HEADER_ROW, column=idx, value=title)
        hc.font = head_font()
        hc.fill = PatternFill("solid", fgColor=HEAD_BG)
        hc.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        hc.border = box

        # 예시 행
        ex = ws.cell(row=FIRST_DATA_ROW, column=idx, value=sample)
        ex.font = body_font(11, color=MUTED, italic=True)
        ex.number_format = fmt
        ex.alignment = Alignment(horizontal="center")
        ex.fill = input_fill
        ex.border = box

        # 입력 영역
        for row in range(FIRST_DATA_ROW + 1, LAST_DATA_ROW + 1):
            cell = ws.cell(row=row, column=idx)
            cell.number_format = fmt
            cell.font = body_font(11)
            cell.alignment = Alignment(horizontal="center")
            cell.fill = input_fill
            cell.border = box

    ws.row_dimensions[HEADER_ROW].height = 34

    # 날짜 열 유효성 검사 (날짜만 입력)
    dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(1900,1,1)",
                        allow_blank=True, showErrorMessage=True)
    dv.error = "측정일은 날짜 형식으로 입력해 주세요. (예: 2026-01-05)"
    dv.errorTitle = "날짜 형식 오류"
    ws.add_data_validation(dv)
    dv.add(f"A{FIRST_DATA_ROW}:A{LAST_DATA_ROW}")

    ws.auto_filter.ref = f"A{HEADER_ROW}:{get_column_letter(len(COLUMNS))}{LAST_DATA_ROW}"


# -------------------------------------------------------------- 3. 요약
def build_summary(ws):
    ws.sheet_view.showGridLines = False

    ws["A1"] = "항목별 요약"
    ws["A1"].font = body_font(15, bold=True, color=HEAD_BG)
    ws["A2"] = "'인바디기록' 시트에 값을 넣으면 자동으로 계산됩니다. (변화량 = 최근값 - 최초값)"
    ws["A2"].font = body_font(10, color=MUTED)

    headers = ["항목", "단위", "최초 기록", "최근 기록", "변화량", "최소", "최대", "평균", "기록 횟수"]
    widths = [14, 8, 12, 12, 12, 11, 11, 11, 11]
    for c, (h, w) in enumerate(zip(headers, widths), start=1):
        ws.column_dimensions[get_column_letter(c)].width = w
        cell = ws.cell(row=HEADER_ROW, column=c, value=h)
        cell.font = head_font()
        cell.fill = PatternFill("solid", fgColor=HEAD_BG)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = box
    ws.row_dimensions[HEADER_ROW].height = 24

    d = f"'{DATA_SHEET}'"
    date_rng = f"{d}!$A${FIRST_DATA_ROW}:$A${LAST_DATA_ROW}"

    row = HEADER_ROW + 1
    for idx, (header, unit, fmt, _w, _color, _sample, _desc) in enumerate(COLUMNS, start=1):
        if idx == 1:
            continue  # 측정일은 요약 대상 아님
        letter = get_column_letter(idx)
        rng = f"{d}!${letter}${FIRST_DATA_ROW}:${letter}${LAST_DATA_ROW}"

        ws.cell(row=row, column=1, value=header).font = body_font(11, bold=True)
        ws.cell(row=row, column=2, value=unit).font = body_font(11, color=MUTED)
        ws.cell(row=row, column=2).alignment = Alignment(horizontal="center")

        first = f'=IFERROR(INDEX({rng},MATCH(MIN({date_rng}),{date_rng},0)),"")'
        last = f'=IFERROR(INDEX({rng},MATCH(MAX({date_rng}),{date_rng},0)),"")'
        formulas = [
            first,
            last,
            f'=IF(OR(C{row}="",D{row}=""),"",D{row}-C{row})',
            f'=IF(COUNT({rng})=0,"",MIN({rng}))',
            f'=IF(COUNT({rng})=0,"",MAX({rng}))',
            f'=IF(COUNT({rng})=0,"",AVERAGE({rng}))',
            f"=COUNT({rng})",
        ]
        for offset, formula in enumerate(formulas, start=3):
            cell = ws.cell(row=row, column=offset, value=formula)
            cell.number_format = "0" if offset == 9 else fmt
            cell.font = body_font(11)
            cell.alignment = Alignment(horizontal="center")
            cell.border = box
        for c in (1, 2):
            ws.cell(row=row, column=c).border = box

        if idx == GIRTH_START:
            ws.cell(row=row, column=1).value = f"{header} (겉둘레)"
        row += 1

    note = ws.cell(row=row + 1, column=1,
                   value="※ 최초/최근 기록은 '측정일'이 가장 이른 행과 가장 늦은 행의 값입니다. 측정일이 비어 있으면 계산되지 않습니다.")
    note.font = body_font(10, color=MUTED)


# ------------------------------------------------------------- 4. 그래프
def make_chart(wb, title, y_title, col_indexes, color, width=15.5, height=8.5):
    data_ws = wb[DATA_SHEET]
    chart = LineChart()
    chart.title = title
    chart.style = None
    chart.y_axis.title = y_title
    chart.x_axis.title = "측정일"
    chart.height = height
    chart.width = width
    chart.x_axis.number_format = "yyyy-mm-dd"
    chart.x_axis.majorTickMark = "out"
    chart.y_axis.majorTickMark = "out"
    chart.x_axis.delete = False      # 엑셀에서 축이 숨겨지는 문제 방지
    chart.y_axis.delete = False
    chart.y_axis.majorGridlines = ChartLines(spPr=None)

    for col in col_indexes:
        ref = Reference(data_ws, min_col=col, min_row=HEADER_ROW,
                        max_row=LAST_DATA_ROW, max_col=col)
        chart.add_data(ref, titles_from_data=True)

    cats = Reference(data_ws, min_col=1, min_row=FIRST_DATA_ROW, max_row=LAST_DATA_ROW)
    chart.set_categories(cats)

    palette = [color, "D06B2C", "3E8E7E", "7A5EA8", "B23A48", "2F6FB3", "8A8F98", "C9A227"]
    for i, series in enumerate(chart.series):
        c = palette[i % len(palette)] if len(chart.series) > 1 else color
        series.graphicalProperties.line = LineProperties(solidFill=c, w=22000)
        series.marker = Marker(symbol="circle", size=6)
        series.marker.graphicalProperties.solidFill = c
        series.marker.graphicalProperties.line.solidFill = c
        series.smooth = False

    if len(chart.series) == 1:
        chart.legend = None
    else:
        chart.legend.position = "b"
    return chart


def build_charts(wb, ws):
    ws.sheet_view.showGridLines = False
    ws["A1"] = "항목별 추이 그래프"
    ws["A1"].font = body_font(15, bold=True, color=HEAD_BG)
    ws["A2"] = "'인바디기록' 시트에 값을 입력하면 그래프가 자동으로 그려집니다."
    ws["A2"].font = body_font(10, color=MUTED)

    anchors_row = 4
    col_anchors = ["A", "L"]     # 2열 배치
    step = 18                    # 그래프 1개 높이(행)

    charts = []
    for idx, (header, unit, _fmt, _w, color, _s, _d) in enumerate(COLUMNS, start=1):
        if idx == 1:
            continue
        label = f"{header} 추이"
        if idx >= GIRTH_START:
            label = f"겉둘레 - {header} 추이"
        charts.append((label, unit, [idx], color))

    # 겉둘레 통합 비교 그래프
    charts.append(("겉둘레 종합 비교", "cm", list(range(GIRTH_START, GIRTH_END + 1)), C_GIRTH))
    # 체중 vs 골격근량 vs 체지방량 비교
    charts.append(("체중 / 골격근량 / 체지방량 비교", "kg", [2, 3, 4], C_BODY))

    for i, (title, unit, cols, color) in enumerate(charts):
        chart = make_chart(wb, title, unit or "값", cols, color)
        anchor = f"{col_anchors[i % 2]}{anchors_row + (i // 2) * step}"
        ws.add_chart(chart, anchor)


def main():
    wb = Workbook()
    guide = wb.active
    guide.title = "사용안내"
    data = wb.create_sheet(DATA_SHEET)
    summary = wb.create_sheet("요약")
    graphs = wb.create_sheet("그래프")

    build_guide(guide)
    build_data(data)
    build_summary(summary)
    build_charts(wb, graphs)

    wb.active = 1
    # openpyxl은 수식의 계산값을 저장하지 않으므로, 파일을 열 때 전체 재계산하도록 지정
    wb.calculation.fullCalcOnLoad = True
    out = "inbody_tracker.xlsx"
    wb.save(out)
    print(f"saved: {out}")


if __name__ == "__main__":
    main()
