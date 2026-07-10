"""MSDS 연도별 변경 판정 PC 앱 (Tkinter GUI)."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from .comparator import (
    MatrixRow, build_matrix, build_matrix_csv, build_report, compare_all,
)
from .parser import MsdsRecord, parse_file


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.records: list[MsdsRecord] = []
        self.comparisons = []
        self.warnings: list[str] = []
        self.matrix_years: list[int] = []
        self.matrix_rows: list[MatrixRow] = []

        root.title(f"MSDS 연도별 변경 판정 v{__version__}")
        root.geometry("980x680")
        root.minsize(760, 520)

        self._build_widgets()

    # ------------------------------------------------------------ UI 구성

    def _build_widgets(self) -> None:
        toolbar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="MSDS 파일 추가…", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="선택 제거", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="전체 지우기", command=self.clear_all).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="판정 실행", command=self.run_compare).pack(side="left", padx=(18, 0))
        ttk.Button(toolbar, text="보고서 저장…", command=self.save_report).pack(side="right")

        paned = ttk.PanedWindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        # 상단: 첨부 파일 목록
        top = ttk.LabelFrame(paned, text="첨부된 MSDS (연도가 틀리면 행을 더블클릭해 수정)")
        cols = ("year", "product", "manufacturer", "n_ing", "note")
        self.file_tree = ttk.Treeview(top, columns=cols, show="tree headings", height=7)
        self.file_tree.heading("#0", text="파일명")
        self.file_tree.heading("year", text="연도")
        self.file_tree.heading("product", text="제품명")
        self.file_tree.heading("manufacturer", text="제조사")
        self.file_tree.heading("n_ing", text="성분 수")
        self.file_tree.heading("note", text="비고")
        self.file_tree.column("#0", width=240, anchor="w")
        self.file_tree.column("year", width=60, anchor="center", stretch=False)
        self.file_tree.column("product", width=150, anchor="w")
        self.file_tree.column("manufacturer", width=180, anchor="w")
        self.file_tree.column("n_ing", width=60, anchor="center", stretch=False)
        self.file_tree.column("note", width=220, anchor="w")
        self.file_tree.tag_configure("warn", foreground="#b45309")
        self.file_tree.bind("<Double-1>", self._edit_year)
        fsb = ttk.Scrollbar(top, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=fsb.set)
        self.file_tree.pack(side="left", fill="both", expand=True)
        fsb.pack(side="right", fill="y")
        paned.add(top, weight=1)

        # 중단: 연도×항목 변경 매트릭스
        mid = ttk.LabelFrame(paned, text="연도별 판정 결과  (▲ = 직전 연도 대비 변경,  — = 해당 연도에 없음)")
        self.result_tree = ttk.Treeview(mid, columns=(), show="tree headings", height=6)
        self.result_tree.heading("#0", text="항목")
        self.result_tree.column("#0", width=230, anchor="w")
        self.result_tree.tag_configure("changed", foreground="#b91c1c")
        self.result_tree.tag_configure("mfr", font=("맑은 고딕", 10, "bold"))
        rsb = ttk.Scrollbar(mid, orient="vertical", command=self.result_tree.yview)
        self.result_tree.configure(yscrollcommand=rsb.set)
        self.result_tree.pack(side="left", fill="both", expand=True)
        rsb.pack(side="right", fill="y")
        paned.add(mid, weight=1)

        # 하단: 상세 보고서
        bottom = ttk.LabelFrame(paned, text="상세 보고서")
        self.report_text = tk.Text(bottom, wrap="word", font=("맑은 고딕", 10), state="disabled")
        tsb = ttk.Scrollbar(bottom, orient="vertical", command=self.report_text.yview)
        self.report_text.configure(yscrollcommand=tsb.set)
        self.report_text.pack(side="left", fill="both", expand=True)
        tsb.pack(side="right", fill="y")
        paned.add(bottom, weight=2)

        self.status = ttk.Label(self.root, anchor="w", padding=(8, 2))
        self.status.pack(fill="x")
        self._set_status("MSDS 파일(PDF/TXT)을 추가한 뒤 '판정 실행'을 누르세요.")

    # ------------------------------------------------------------ 동작

    def _set_status(self, msg: str) -> None:
        self.status.configure(text=msg)

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="MSDS 파일 선택",
            filetypes=[("MSDS 문서", "*.pdf *.txt"), ("PDF", "*.pdf"),
                       ("텍스트", "*.txt"), ("모든 파일", "*.*")],
        )
        if not paths:
            return
        existing = {r.path for r in self.records}
        added = 0
        for p in paths:
            p = os.path.abspath(p)
            if p in existing:
                continue
            rec = parse_file(p)
            self.records.append(rec)
            added += 1
        self._refresh_file_list()
        self._set_status(f"{added}개 파일을 추가했습니다. 총 {len(self.records)}개.")

    def remove_selected(self) -> None:
        selected = self.file_tree.selection()
        if not selected:
            return
        paths = set(selected)  # iid == 파일 경로
        self.records = [r for r in self.records if r.path not in paths]
        self._refresh_file_list()

    def clear_all(self) -> None:
        if self.records and not messagebox.askyesno("확인", "첨부 목록을 모두 지울까요?"):
            return
        self.records = []
        self.comparisons = []
        self.matrix_years = []
        self.matrix_rows = []
        self._refresh_file_list()
        self._show_results()

    def _refresh_file_list(self) -> None:
        self.file_tree.delete(*self.file_tree.get_children())
        for rec in sorted(self.records, key=lambda r: (r.year or 9999, r.filename)):
            note = "; ".join(rec.warnings)
            tags = ("warn",) if rec.warnings else ()
            self.file_tree.insert(
                "", "end", iid=rec.path, text=rec.filename, tags=tags,
                values=(rec.year if rec.year is not None else "?",
                        rec.product, rec.manufacturer,
                        len(rec.ingredients), note),
            )

    def _edit_year(self, event: tk.Event) -> None:
        iid = self.file_tree.identify_row(event.y)
        if not iid:
            return
        rec = next((r for r in self.records if r.path == iid), None)
        if rec is None:
            return
        year = simpledialog.askinteger(
            "연도 수정", f"{rec.filename}\n이 MSDS의 기준 연도:",
            parent=self.root, initialvalue=rec.year or 2024,
            minvalue=1900, maxvalue=2100,
        )
        if year is not None:
            rec.year = year
            rec.warnings = [w for w in rec.warnings if "연도" not in w]
            self._refresh_file_list()

    def run_compare(self) -> None:
        if len(self.records) < 2:
            messagebox.showinfo("안내", "서로 다른 연도의 MSDS 파일을 2개 이상 추가하세요.")
            return
        self.comparisons, self.warnings = compare_all(self.records)
        self.matrix_years, self.matrix_rows, _ = build_matrix(self.records)
        self._show_results()
        n_changed = sum(sum(r.changed) for r in self.matrix_rows)
        self._set_status(
            f"판정 완료: {len(self.matrix_years)}개 연도 비교, 변경 {n_changed}건 감지 (▲ 표시)."
        )

    def _show_results(self) -> None:
        self.result_tree.delete(*self.result_tree.get_children())
        years = getattr(self, "matrix_years", [])
        cols = [str(y) for y in years]
        self.result_tree.configure(columns=cols)
        self.result_tree.heading("#0", text="항목")
        self.result_tree.column("#0", width=230, anchor="w")
        for c in cols:
            self.result_tree.heading(c, text=f"{c}년")
            self.result_tree.column(c, width=140, anchor="center")
        for row in getattr(self, "matrix_rows", []):
            values = [
                f"▲ {v}" if ch else v
                for v, ch in zip(row.values, row.changed)
            ]
            tags = []
            if row.any_changed:
                tags.append("changed")
            if row.kind == "manufacturer":
                tags.append("mfr")
            self.result_tree.insert(
                "", "end", text=row.label, values=values, tags=tuple(tags),
            )
        report = build_report(self.records, self.comparisons, self.warnings) \
            if self.records else ""
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", report)
        self.report_text.configure(state="disabled")

    def save_report(self) -> None:
        if not self.comparisons:
            messagebox.showinfo("안내", "먼저 '판정 실행'을 눌러 결과를 만드세요.")
            return
        path = filedialog.asksaveasfilename(
            title="보고서 저장",
            defaultextension=".txt",
            filetypes=[("텍스트 보고서", "*.txt"), ("CSV 요약", "*.csv")],
            initialfile="MSDS_변경판정보고서.txt",
        )
        if not path:
            return
        if path.lower().endswith(".csv"):
            data = build_matrix_csv(self.matrix_years, self.matrix_rows)
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(data)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_report(self.records, self.comparisons, self.warnings))
        self._set_status(f"보고서를 저장했습니다: {path}")


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
