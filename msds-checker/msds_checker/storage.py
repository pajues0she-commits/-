"""업로드된 MSDS의 누적 관리 저장소.

- 파싱 결과 + 도입일자·작성부서·작성자를 JSON(history.json)에 저장한다.
- 원본 파일은 저장소 폴더(files/)로 복사해 원본이 이동·삭제돼도 이력이 유지된다.
- 저장 위치: 환경변수 MSDS_DATA_DIR, 없으면 ~/.msds_checker
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime

from .parser import Ingredient, MsdsRecord

_INTRO_YEAR_RE = re.compile(r"^\s*((?:19|20)\d{2})")


def intro_year(intro_date: str) -> int | None:
    """도입일자(YYYY-MM-DD)에서 기준연도를 얻는다. 형식이 아니면 None."""
    m = _INTRO_YEAR_RE.match(intro_date or "")
    return int(m.group(1)) if m else None


def apply_base_year(record: MsdsRecord, intro_date: str) -> None:
    """도입일자의 연도를 기준연도로 설정한다.

    도입일자가 없거나 연도를 읽을 수 없으면 MSDS 문서의 개정/작성 연도
    (doc_year)를 그대로 기준연도로 사용한다.
    """
    y = intro_year(intro_date)
    if y is not None:
        record.year = y
        # 도입일자로 기준연도가 정해졌으므로 연도 관련 경고는 해소됨
        record.warnings = [w for w in record.warnings if "연도" not in w]
    else:
        record.year = record.doc_year


def data_dir() -> str:
    d = os.environ.get("MSDS_DATA_DIR") or os.path.join(
        os.path.expanduser("~"), ".msds_checker"
    )
    os.makedirs(os.path.join(d, "files"), exist_ok=True)
    return d


def history_path() -> str:
    return os.path.join(data_dir(), "history.json")


@dataclass
class HistoryEntry:
    """누적 이력의 한 건: 파싱된 MSDS + 등록 정보."""

    id: str
    record: MsdsRecord
    source_path: str = ""   # 사용자가 첨부한 원본 경로
    intro_date: str = ""    # 사업장 도입일자 (YYYY-MM-DD)
    department: str = ""    # 작성부서
    author: str = ""        # 작성자
    added_at: str = ""      # 등록 일시 (ISO)

    def to_dict(self) -> dict:
        r = self.record
        return {
            "id": self.id,
            "source_path": self.source_path,
            "intro_date": self.intro_date,
            "department": self.department,
            "author": self.author,
            "added_at": self.added_at,
            "record": {
                "path": r.path,
                "year": r.year,
                "doc_year": r.doc_year,
                "product": r.product,
                "manufacturer": r.manufacturer,
                "ingredients": [
                    {"name": i.name, "cas": i.cas, "content": i.content}
                    for i in r.ingredients
                ],
                "warnings": list(r.warnings),
            },
        }

    @staticmethod
    def from_dict(d: dict) -> "HistoryEntry":
        rd = d.get("record", {})
        record = MsdsRecord(
            path=rd.get("path", ""),
            year=rd.get("year"),
            # 구버전 데이터에는 doc_year가 없으므로 기존 year를 문서 연도로 간주
            doc_year=rd.get("doc_year", rd.get("year")),
            product=rd.get("product", ""),
            manufacturer=rd.get("manufacturer", ""),
            ingredients=[
                Ingredient(i.get("name", ""), i.get("cas", ""), i.get("content", ""))
                for i in rd.get("ingredients", [])
            ],
            warnings=list(rd.get("warnings", [])),
        )
        return HistoryEntry(
            id=d.get("id", uuid.uuid4().hex),
            record=record,
            source_path=d.get("source_path", ""),
            intro_date=d.get("intro_date", ""),
            department=d.get("department", ""),
            author=d.get("author", ""),
            added_at=d.get("added_at", ""),
        )


@dataclass
class History:
    """누적 이력 전체 + 마지막으로 사용한 작성부서/작성자."""

    department: str = ""
    author: str = ""
    entries: list[HistoryEntry] = field(default_factory=list)

    def records(self) -> list[MsdsRecord]:
        return [e.record for e in self.entries]


def load() -> History:
    path = history_path()
    if not os.path.exists(path):
        return History()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return History()
    return History(
        department=data.get("department", ""),
        author=data.get("author", ""),
        entries=[HistoryEntry.from_dict(d) for d in data.get("entries", [])],
    )


def save(history: History) -> None:
    data = {
        "department": history.department,
        "author": history.author,
        "entries": [e.to_dict() for e in history.entries],
    }
    path = history_path()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _store_copy(source_path: str, entry_id: str) -> str:
    """원본 파일을 저장소 폴더로 복사하고 사본 경로를 반환. 실패하면 원본 경로 유지."""
    try:
        name = f"{entry_id[:8]}_{os.path.basename(source_path)}"
        dest = os.path.join(data_dir(), "files", name)
        shutil.copy2(source_path, dest)
        return dest
    except OSError:
        return source_path


def add_record(
    history: History,
    record: MsdsRecord,
    intro_date: str = "",
    department: str = "",
    author: str = "",
    copy_file: bool = True,
) -> HistoryEntry:
    """레코드를 누적 이력에 추가하고 저장한다. 원본 파일은 저장소로 복사.

    기준연도는 도입일자(intro_date)의 연도로 설정된다.
    """
    apply_base_year(record, intro_date)
    entry_id = uuid.uuid4().hex
    source = record.path
    if copy_file and os.path.exists(source):
        record.path = _store_copy(source, entry_id)
    entry = HistoryEntry(
        id=entry_id,
        record=record,
        source_path=source,
        intro_date=intro_date,
        department=department,
        author=author,
        added_at=datetime.now().isoformat(timespec="seconds"),
    )
    history.entries.append(entry)
    history.department = department or history.department
    history.author = author or history.author
    save(history)
    return entry


def remove_entries(history: History, entry_ids: set[str]) -> None:
    """이력에서 해당 항목들을 제거하고 저장. 저장소의 파일 사본도 삭제한다."""
    files_dir = os.path.join(data_dir(), "files")
    for e in history.entries:
        if e.id in entry_ids and e.record.path.startswith(files_dir):
            try:
                os.remove(e.record.path)
            except OSError:
                pass
    history.entries = [e for e in history.entries if e.id not in entry_ids]
    save(history)
