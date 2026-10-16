"""Read copied tables and ordinary Excel exports; never evaluate formulas."""
from __future__ import annotations

import csv
from datetime import date, datetime
import importlib
import io
from pathlib import Path
import re
import sys
import zipfile


def excel_module():
    try:
        return importlib.import_module("openpyxl")
    except ModuleNotFoundError:
        # Development installs stay inside the project. Published apps bundle it.
        deps = Path(__file__).resolve().parent / ".build/deps"
        if deps.is_dir() and str(deps) not in sys.path:
            sys.path.insert(0, str(deps))
        try:
            return importlib.import_module("openpyxl")
        except ModuleNotFoundError:
            raise ValueError("Excel 读取组件缺失，请使用完整发布版，或先复制表格内容粘贴。") from None


def norm(value):
    return re.sub(r"[\s_（）()\[\]%％:：\-]", "", str(value)).casefold()


def table_rows(matrix, aliases):
    """Find the actual header after report titles, empty lines or merged cells."""
    matrix = list(matrix)
    known = {norm(a) for names in aliases.values() for a in names}
    identities = {norm(a) for key in ("source_id", "title", "keyword") for a in aliases[key]}
    header_index = None
    best = 0
    for i, row in enumerate(matrix[:20]):
        cells = {norm(v) for v in row if v is not None and str(v).strip()}
        score = len(cells & known)
        if cells & identities and score > best:
            header_index, best = i, score
    if header_index is None:
        raise ValueError("没有识别出表头。复制 Excel 时请连同 ASIN、标题或关键词等列名一起复制。")
    headers = [str(v or "").strip().lstrip("\ufeff") for v in matrix[header_index]]
    if len(headers) > 200:
        raise ValueError("表格超过 200 列，请先选择需要的列。")
    result = []
    for row in matrix[header_index + 1:]:
        if not any(v is not None and str(v).strip() for v in row):
            continue
        item = {}
        for i, header in enumerate(headers):
            if not header:
                continue
            value = row[i] if i < len(row) else None
            if isinstance(value, (datetime, date)):
                value = value.date().isoformat() if isinstance(value, datetime) else value.isoformat()
            item[header] = "" if value is None else str(value).strip()
        if any(item.values()):
            result.append(item)
        if len(result) > 10000:
            raise ValueError("单次最多整理 10000 行，请分批导入。")
    return result


def pasted_rows(text, aliases):
    if len(text.encode("utf-8")) > 3_000_000:
        raise ValueError("粘贴内容较大，请分批粘贴或直接选择文件。")
    delimiter = "\t" if "\t" in text else ","
    return table_rows(list(csv.reader(io.StringIO(text), delimiter=delimiter)), aliases)


def read_file(path, aliases):
    path = Path(path)
    if path.stat().st_size > 15_000_000:
        raise ValueError("导入文件请控制在 15 MB 内。")
    if path.suffix.lower() == ".xls":
        raise ValueError("这是旧版 .xls 文件，可直接复制表格粘贴，或另存为 .xlsx 后选择文件。")
    if path.suffix.lower() == ".xlsx":
        try:
            with zipfile.ZipFile(path) as package:
                if sum(i.file_size for i in package.infolist()) > 80_000_000 or len(package.infolist()) > 10000:
                    raise ValueError("工作簿较大，请仅保留需要导入的工作表。")
            workbook = excel_module().load_workbook(path, read_only=True, data_only=True, keep_links=False)
            try:
                last_error = None
                for sheet in workbook.worksheets:
                    # Some export tools declare an inaccurate used range.
                    sheet.reset_dimensions()
                    matrix = []
                    for i, cells in enumerate(sheet.iter_rows(max_col=200)):
                        if i >= 10020:
                            raise ValueError("单次最多整理 10000 行，请分批导入。")
                        row = []
                        for cell in cells:
                            value = cell.value
                            fmt = re.sub(r'"[^\"]*"|\\.', "", getattr(cell, "number_format", "") or "")
                            if isinstance(value, (int, float)) and not isinstance(value, bool) and "%" in fmt:
                                value = f"{value * 100:.12g}%"
                            row.append(value)
                        matrix.append(row)
                    if not matrix:
                        continue
                    try:
                        rows = table_rows(matrix, aliases)
                    except ValueError as error:
                        last_error = error
                        continue
                    if rows:
                        return rows, sheet.title
                raise last_error or ValueError("工作簿没有可识别的数据表，请连同表头复制粘贴。")
            finally:
                workbook.close()
        except (zipfile.BadZipFile, KeyError, OSError) as error:
            raise ValueError("无法读取这个 Excel 文件。请确认它没有加密，并且是有效的 .xlsx。") from error
    if path.suffix.lower() not in (".csv", ".tsv"):
        raise ValueError("请选择 Excel (.xlsx)、CSV 或 TSV 文件，也可直接粘贴表格。")
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "gb18030", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeError:
            continue
    delimiter = "\t" if path.suffix.lower() == ".tsv" or text.count("\t") > text.count(",") else ","
    return table_rows(list(csv.reader(io.StringIO(text), delimiter=delimiter)), aliases), ""
