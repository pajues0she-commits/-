# -*- coding: utf-8 -*-
"""명령행에서 MSDS PDF들을 관리요령 엑셀로 변환한다.

사용법:  python cli.py msds1.pdf msds2.pdf -o 관리요령.xlsx
"""
import argparse
import os
import sys

from msds_parser import parse_msds
from excel_writer import build_workbook


def main():
    ap = argparse.ArgumentParser(
        description="MSDS PDF → 화학물질 작업공정별 관리 요령 엑셀 자동 작성")
    ap.add_argument("pdfs", nargs="+", help="MSDS PDF 파일 경로 (여러 개 가능)")
    ap.add_argument("-o", "--output", default="화학물질_작업공정별_관리요령.xlsx",
                    help="출력 엑셀 파일 경로")
    args = ap.parse_args()

    records = []
    for path in args.pdfs:
        if not os.path.exists(path):
            print(f"[오류] 파일 없음: {path}", file=sys.stderr)
            sys.exit(1)
        print(f"분석 중: {path}")
        data = parse_msds(path, source_name=os.path.basename(path))
        for w in data.warnings:
            print(f"  [주의] {w}")
        print(f"  제품명: {data.product_name or '(미확인)'} / 신호어: {data.signal_word or '해당없음'}"
              f" / 그림문자: {', '.join(data.pictograms) or '(없음)'}")
        records.append(data)

    xlsx = build_workbook(records)
    with open(args.output, "wb") as f:
        f.write(xlsx)
    print(f"완료: {args.output} (시트 {len(records)}개)")


if __name__ == "__main__":
    main()
