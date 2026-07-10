"""MSDS 연도별 변경 판정 PC 앱 (Tkinter GUI).

사업장에 도입한 화학물질의 MSDS를 누적 관리하며, 연도별로 제조사·성분 함량
변경 여부를 판정한다. tkinterdnd2가 설치되어 있으면 드래그 앤 드롭을 지원한다.
"""

from __future__ import annotations

import os
import re
import tkinter as tk
from datetime import date
from tkinter import filedialog, messagebox, simpledialog, ttk

from . import __version__
from .comparator import (
    MatrixRow, build_matrix, build_matrix_csv, build_report, compare_all,
)
from .parser import parse_file
from . import storage

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    _HAS_DND = True
except ImportError:
    _HAS_DND = False

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.history = storage.load()
        self.comparisons = []
        self.warnings: list[str] = []
        self.matrix_years: list[int] = []
        self.matrix_rows: list[MatrixRow] = []

        root.title(f"MSDS 변경 판정·누적 관리 v{__version__}")
        root.geometry("1020x720")
        root.minsize(780, 560)

        self._build_widgets()
        self._refresh_file_list()
        if self.history.entries:
            self._set_status(
                f"누적 이력 {len(self.history.entries)}건을 불러왔습니다. "
                "'판정 실행'으로 변경 여부를 확인하세요."
            )

    # ------------------------------------------------------------ UI 구성

    def _build_widgets(self) -> None:
        # 등록 정보: 작성부서 / 작성자 / 도입일자
        info = ttk.LabelFrame(self.root, text="등록 정보", padding=(8, 4))
        info.pack(fill="x", padx=8, pady=(8, 0))
        ttk.Label(info, text="작성부서:").pack(side="left")
        self.department_var = tk.StringVar(value=self.history.department)
        ttk.Entry(info, textvariable=self.department_var, width=16).pack(side="left", padx=(4, 14))
        ttk.Label(info, text="작성자:").pack(side="left")
        self.author_var = tk.StringVar(value=self.history.author)
        ttk.Entry(info, textvariable=self.author_var, width=12).pack(side="left", padx=(4, 14))
        ttk.Label(info, text="도입일자:").pack(side="left")
        self.intro_var = tk.StringVar(value=date.today().isoformat())
        ttk.Entry(info, textvariable=self.intro_var, width=12).pack(side="left", padx=(4, 4))
        ttk.Label(info, text="(YYYY-MM-DD, 새로 추가되는 파일에 적용)").pack(side="left")

        toolbar = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="MSDS 파일 추가…", command=self.add_files).pack(side="left")
        ttk.Button(toolbar, text="선택 제거", command=self.remove_selected).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="전체 지우기", command=self.clear_all).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="판정 실행", command=self.run_compare).pack(side="left", padx=(18, 0))
        ttk.Button(toolbar, text="엑셀 내보내기…", command=self.export_excel).pack(side="right")
        ttk.Button(toolbar, text="보고서 저장…", command=self.save_report).pack(side="right", padx=(0, 6))

        paned = ttk.PanedWindow(self.root, orient="vertical")
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 4))

        # 상단: 누적 관리 목록
        dnd_hint = " — 파일을 여기로 드래그해 추가" if _HAS_DND else ""
        top = ttk.LabelFrame(
            paned,
            text=f"누적 관리 MSDS (연도·도입일자는 해당 칸 더블클릭으로 수정){dnd_hint}",
        )
        cols = ("intro", "year", "product", "manufacturer", "n_ing", "note")
        self.file_tree = ttk.Treeview(top, columns=cols, show="tree headings", height=7)
        self.file_tree.heading("#0", text="파일명")
        self.file_tree.heading("intro", text="도입일자")
        self.file_tree.heading("year", text="연도")
        self.file_tree.heading("product", text="제품명")
        self.file_tree.heading("manufacturer", text="제조사")
        self.file_tree.heading("n_ing", text="성분 수")
        self.file_tree.heading("note", text="비고")
        self.file_tree.column("#0", width=210, anchor="w")
        self.file_tree.column("intro", width=90, anchor="center", stretch=False)
        self.file_tree.column("year", width=55, anchor="center", stretch=False)
        self.file_tree.column("product", width=140, anchor="w")
        self.file_tree.column("manufacturer", width=170, anchor="w")
        self.file_tree.column("n_ing", width=55, anchor="center", stretch=False)
        self.file_tree.column("note", width=210, anchor="w")
        self.file_tree.tag_configure("warn", foreground="#b45309")
        self.file_tree.bind("<Double-1>", self._edit_cell)
        fsb = ttk.Scrollbar(top, orient="vertical", command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=fsb.set)
        self.file_tree.pack(side="left", fill="both", expand=True)
        fsb.pack(side="right", fill="y")
        paned.add(top, weight=1)

        # 드래그 앤 드롭 등록 (tkinterdnd2가 있을 때)
        if _HAS_DND:
            self.file_tree.drop_target_register(DND_FILES)
            self.file_tree.dnd_bind("<<Drop>>", self._on_drop)
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>", self._on_drop)

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
        hint = "MSDS 파일을 드래그하거나 '파일 추가'로 첨부하세요." if _HAS_DND \
            else "MSDS 파일(PDF/TXT)을 추가하세요. (드래그 앤 드롭: pip install tkinterdnd2)"
        self._set_status(hint)

    # ------------------------------------------------------------ 동작

    def _set_status(self, msg: str) -> None:
        self.status.configure(text=msg)

    def _current_intro_date(self) -> str:
        s = self.intro_var.get().strip()
        if s and not _DATE_RE.match(s):
            messagebox.showwarning(
                "도입일자 형식",
                f"도입일자 '{s}'가 YYYY-MM-DD 형식이 아닙니다. 그대로 저장은 되지만 "
                "정렬이 올바르지 않을 수 있습니다.",
            )
        return s

    def add_files(self) -> None:
        paths = filedialog.askopenfilenames(
            title="MSDS 파일 선택",
            filetypes=[("MSDS 문서", "*.pdf *.txt"), ("PDF", "*.pdf"),
                       ("텍스트", "*.txt"), ("모든 파일", "*.*")],
        )
        if paths:
            self._add_paths(paths)

    def _on_drop(self, event) -> None:
        try:
            paths = self.root.tk.splitlist(event.data)
        except tk.TclError:
            paths = event.data.split()
        files = [p for p in paths if os.path.isfile(p)]
        if files:
            self._add_paths(files)

    def _add_paths(self, paths) -> None:
        intro = self._current_intro_date()
        department = self.department_var.get().strip()
        author = self.author_var.get().strip()
        existing = {e.source_path for e in self.history.entries} | {
            e.record.path for e in self.history.entries
        }
        added = skipped = 0
        for p in paths:
            p = os.path.abspath(p)
            if p in existing:
                skipped += 1
                continue
            rec = parse_file(p)
            storage.add_record(
                self.history, rec,
                intro_date=intro, department=department, author=author,
            )
            added += 1
        self._refresh_file_list()
        msg = f"{added}개 파일을 누적 이력에 등록했습니다. 총 {len(self.history.entries)}건."
        if skipped:
            msg += f" (이미 등록된 {skipped}개는 건너뜀)"
        self._set_status(msg)

    def remove_selected(self) -> None:
        selected = self.file_tree.selection()
        if not selected:
            return
        if not messagebox.askyesno(
            "확인", f"선택한 {len(selected)}건을 누적 이력에서 삭제할까요?"
        ):
            return
        storage.remove_entries(self.history, set(selected))  # iid == entry.id
        self._refresh_file_list()
        self._set_status(f"삭제 완료. 남은 이력 {len(self.history.entries)}건.")

    def clear_all(self) -> None:
        if not self.history.entries:
            return
        if not messagebox.askyesno(
            "확인",
            f"누적 이력 {len(self.history.entries)}건을 모두 삭제할까요?\n"
            "저장된 파일 사본도 함께 삭제됩니다.",
        ):
            return
        storage.remove_entries(self.history, {e.id for e in self.history.entries})
        self.comparisons = []
        self.matrix_years = []
        self.matrix_rows = []
        self._refresh_file_list()
        self._show_results()
        self._set_status("누적 이력을 모두 삭제했습니다.")

    def _refresh_file_list(self) -> None:
        self.file_tree.delete(*self.file_tree.get_children())
        for e in sorted(
            self.history.entries,
            key=lambda x: (x.record.year or 9999, x.intro_date, x.record.filename),
        ):
            rec = e.record
            note = "; ".join(rec.warnings)
            tags = ("warn",) if rec.warnings else ()
            self.file_tree.insert(
                "", "end", iid=e.id, text=rec.filename, tags=tags,
                values=(e.intro_date or "-",
                        rec.year if rec.year is not None else "?",
                        rec.product, rec.manufacturer,
                        len(rec.ingredients), note),
            )

    def _edit_cell(self, event: tk.Event) -> None:
        iid = self.file_tree.identify_row(event.y)
        if not iid:
            return
        entry = next((e for e in self.history.entries if e.id == iid), None)
        if entry is None:
            return
        column = self.file_tree.identify_column(event.x)
        if column == "#1":  # 도입일자
            value = simpledialog.askstring(
                "도입일자 수정",
                f"{entry.record.filename}\n사업장 도입일자 (YYYY-MM-DD):",
                parent=self.root, initialvalue=entry.intro_date or date.today().isoformat(),
            )
            if value is None:
                return
            value = value.strip()
            if value and not _DATE_RE.match(value):
                messagebox.showwarning("형식 오류", "YYYY-MM-DD 형식으로 입력하세요.")
                return
            entry.intro_date = value
        else:  # 그 외 칸: 기준 연도 수정
            year = simpledialog.askinteger(
                "연도 수정", f"{entry.record.filename}\n이 MSDS의 기준 연도:",
                parent=self.root, initialvalue=entry.record.year or date.today().year,
                minvalue=1900, maxvalue=2100,
            )
            if year is None:
                return
            entry.record.year = year
            entry.record.warnings = [w for w in entry.record.warnings if "연도" not in w]
        storage.save(self.history)
        self._refresh_file_list()

    def _save_meta(self) -> None:
        """작성부서/작성자 최신 값을 이력 파일에 반영."""
        self.history.department = self.department_var.get().strip()
        self.history.author = self.author_var.get().strip()
        storage.save(self.history)

    def run_compare(self) -> None:
        records = self.history.records()
        if len(records) < 2:
            messagebox.showinfo("안내", "서로 다른 연도의 MSDS 파일을 2개 이상 등록하세요.")
            return
        self._save_meta()
        self.comparisons, self.warnings = compare_all(records)
        self.matrix_years, self.matrix_rows, _ = build_matrix(records)
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
        records = self.history.records()
        report = build_report(records, self.comparisons, self.warnings) \
            if records else ""
        self.report_text.configure(state="normal")
        self.report_text.delete("1.0", "end")
        self.report_text.insert("1.0", report)
        self.report_text.configure(state="disabled")

    def export_excel(self) -> None:
        if not self.history.entries:
            messagebox.showinfo("안내", "내보낼 누적 이력이 없습니다. 먼저 MSDS를 등록하세요.")
            return
        self._save_meta()
        # 판정을 아직 안 했으면 매트릭스를 조용히 생성해서 함께 내보낸다
        records = self.history.records()
        if not self.matrix_rows and len(records) >= 2:
            self.matrix_years, self.matrix_rows, _ = build_matrix(records)
        path = filedialog.asksaveasfilename(
            title="엑셀 내보내기",
            defaultextension=".xlsx",
            filetypes=[("엑셀 통합 문서", "*.xlsx")],
            initialfile="MSDS_누적관리대장.xlsx",
        )
        if not path:
            return
        try:
            from .exporter import export_excel
            export_excel(
                path, self.history, self.matrix_years, self.matrix_rows,
                department=self.department_var.get().strip(),
                author=self.author_var.get().strip(),
            )
        except RuntimeError as e:
            messagebox.showerror("엑셀 내보내기 실패", str(e))
            return
        self._set_status(f"엑셀로 내보냈습니다: {path}")

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
        records = self.history.records()
        if path.lower().endswith(".csv"):
            data = build_matrix_csv(self.matrix_years, self.matrix_rows)
            with open(path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(data)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(build_report(records, self.comparisons, self.warnings))
        self._set_status(f"보고서를 저장했습니다: {path}")


def main() -> None:
    root = TkinterDnD.Tk() if _HAS_DND else tk.Tk()
    try:
        ttk.Style().theme_use("clam")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
