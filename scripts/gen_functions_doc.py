#!/usr/bin/env python3
"""
Sinh tài liệu danh sách function: docs/app_service-functions.md

Mục đích:
    - Quét toàn bộ function/component trong `app_service/backend/app` (Python) và
      `app_service/src` (JS/TS/JSX/TSX), tạo một bản đồ index "hàm X nằm ở file/dòng nào"
      để tra cứu nhanh thay vì grep cả repo.

Cách chạy (từ thư mục app_service):
    python scripts/gen_functions_doc.py

Ghi chú:
    - Bộ nhận diện dùng regex theo dòng (không phải full AST) nên cố ý đơn giản, đủ dùng cho
      index tra cứu. Khi đổi quy ước viết hàm, chỉnh các pattern trong PATTERNS bên dưới.
    - Output ghi đè trực tiếp `docs/app_service-functions.md`.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

# Thư mục gốc app_service = cha của thư mục scripts/
APP_SERVICE = Path(__file__).resolve().parent.parent
REPO_ROOT = APP_SERVICE.parent
OUTPUT = REPO_ROOT / "docs" / "app_service-functions.md"

# Các gốc quét và phần mở rộng tương ứng.
SCAN_ROOTS = [
    (APP_SERVICE / "backend" / "app", {".py"}),
    (APP_SERVICE / "src", {".js", ".jsx", ".ts", ".tsx"}),
]

# Bỏ qua các thư mục sinh tự động / phụ thuộc.
IGNORE_DIRS = {"node_modules", "__pycache__", ".venv", "venv", "dist", "build"}

# (regex, nhãn loại). Group 1 = tên hàm. Thứ tự ưu tiên từ trên xuống.
PATTERNS = [
    (re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\("), "python-def"),
    (re.compile(r"^\s*async\s+def\s+([A-Za-z_]\w*)\s*\("), "python-async-def"),
    # export function Foo() / function Foo()
    (re.compile(r"^\s*(?:export\s+)?(?:default\s+)?function\s+([A-Za-z_]\w*)\s*\("), "function-declaration"),
    # const Foo = (...) => / const Foo = async (...) =>  (component/hook/handler)
    (re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>"), "arrow-function"),
    # const Foo = React.memo(function ... ) / const Foo = forwardRef(...)
    (re.compile(r"^\s*(?:export\s+)?const\s+([A-Za-z_]\w*)\s*=\s*(?:React\.)?(?:memo|forwardRef)\s*\("), "wrapped-component"),
]


def iter_source_files():
    for root, exts in SCAN_ROOTS:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.is_dir():
                continue
            if any(part in IGNORE_DIRS for part in path.parts):
                continue
            if path.suffix in exts:
                yield path


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Trả về [(ten_ham, so_dong, loai)] theo thứ tự xuất hiện, không trùng tên trên cùng dòng."""
    found: list[tuple[str, int, str]] = []
    seen_lines: set[int] = set()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (UnicodeDecodeError, OSError):
        return found
    for idx, line in enumerate(lines, start=1):
        if idx in seen_lines:
            continue
        for pattern, label in PATTERNS:
            m = pattern.match(line)
            if m:
                found.append((m.group(1), idx, label))
                seen_lines.add(idx)
                break
    return found


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def main() -> None:
    file_count = 0
    func_count = 0
    sections: list[str] = []

    for path in iter_source_files():
        funcs = scan_file(path)
        if not funcs:
            continue
        file_count += 1
        func_count += len(funcs)
        lines = [f"## {rel(path)}", ""]
        for name, lineno, label in funcs:
            lines.append(f"- {name} (dòng {lineno}, {label})")
        lines.append("")
        sections.append("\n".join(lines))

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = [
        "# App Service — Danh sách function",
        "",
        "> Tài liệu **tự sinh** bởi `app_service/scripts/gen_functions_doc.py`.",
        "> Là bản đồ index tra cứu nhanh: hàm/component nằm ở file nào, dòng nào.",
        "> KHÔNG sửa tay — chạy lại script để cập nhật.",
        "",
        f"- Phạm vi quét: `app_service/backend/app` + `app_service/src`",
        f"- Thời điểm tạo: {now}",
        f"- Số file có function: {file_count}",
        f"- Tổng số function tìm thấy: {func_count}",
        "",
    ]

    OUTPUT.write_text("\n".join(header) + "\n".join(sections), encoding="utf-8")
    # Tránh lỗi encode trên console Windows (cp1252): chỉ in ASCII.
    print(f"Wrote {OUTPUT} - {file_count} files, {func_count} functions.")


if __name__ == "__main__":
    main()
