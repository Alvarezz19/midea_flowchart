from __future__ import annotations

from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET
import re
import zipfile


NS_MAIN = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
NS_REL = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
NS_DOC_REL = {"r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}


def read_xlsx(path: str | Path) -> dict[str, list[list[Any]]]:
    """读取 xlsx 的单元格值，保持对本项目命名表足够的结构信息。"""
    xlsx_path = Path(path)
    with zipfile.ZipFile(xlsx_path) as archive:
        shared_strings = _read_shared_strings(archive)
        sheet_targets = _read_sheet_targets(archive)
        result: dict[str, list[list[Any]]] = {}
        for sheet_name, target in sheet_targets:
            rows = _read_sheet(archive, _normalise_target(target), shared_strings)
            result[sheet_name] = rows
        return result


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    values: list[str] = []
    for item in root.findall("m:si", NS_MAIN):
        parts = [text.text or "" for text in item.findall(".//m:t", NS_MAIN)]
        values.append("".join(parts))
    return values


def _read_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    rels = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rel_by_id = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("r:Relationship", NS_REL)
    }
    sheets: list[tuple[str, str]] = []
    for sheet in workbook.findall("m:sheets/m:sheet", NS_MAIN):
        rel_id = sheet.attrib[f"{{{NS_DOC_REL['r']}}}id"]
        sheets.append((sheet.attrib["name"], rel_by_id[rel_id]))
    return sheets


def _read_sheet(archive: zipfile.ZipFile, target: str, shared_strings: list[str]) -> list[list[Any]]:
    root = ET.fromstring(archive.read(target))
    rows: list[list[Any]] = []
    for row in root.findall("m:sheetData/m:row", NS_MAIN):
        values_by_col: dict[int, Any] = {}
        for cell in row.findall("m:c", NS_MAIN):
            col_index = _column_index(cell.attrib["r"])
            values_by_col[col_index] = _cell_value(cell, shared_strings)
        width = max(values_by_col, default=-1) + 1
        rows.append([values_by_col.get(index) for index in range(width)])
    return rows


def _cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(text.text or "" for text in cell.findall(".//m:t", NS_MAIN))
    value = cell.find("m:v", NS_MAIN)
    if value is None or value.text is None:
        return None
    text = value.text
    if cell_type == "s":
        return shared_strings[int(text)]
    if cell_type == "b":
        return bool(int(text))
    return _number_or_text(text)


def _number_or_text(value: str) -> int | float | str:
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def _column_index(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference).group(0)
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter) - ord("A") + 1
    return index - 1


def _normalise_target(target: str) -> str:
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return f"xl/{target}"
