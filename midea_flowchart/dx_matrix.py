from __future__ import annotations

import re
from typing import Any

from .models import ProjectModel, TabModel


def dx_status_matrix(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    unit_columns: dict[str, str] = {}
    rows: dict[str, dict[str, Any]] = {}
    system_rows: list[dict[str, Any]] = []
    for point_id in point_ids:
        point = project.points[point_id]
        prefix = point.bacnet_object_prefix or ""
        match = re.fullmatch(r"([A-Z])(\d+)", prefix.upper())
        if not match:
            if project.nodes[point.node_id].type == "swInput":
                system_rows.append(_matrix_cell(point, project.nodes[point.node_id].raw.get("modbusRegAddr")))
            continue
        unit_letter, metric_index = match.groups()
        if unit_letter < "E":
            system_rows.append(_matrix_cell(point, project.nodes[point.node_id].raw.get("modbusRegAddr")))
            continue
        unit_columns[unit_letter] = f"{ord(unit_letter) - ord('E') + 1}号外机"
        row_label = _dx_metric_label(metric_index, point.raw_name)
        row = rows.setdefault(row_label, {"metric": row_label, "cells": {}})
        row["cells"][unit_letter] = _matrix_cell(point, project.nodes[point.node_id].raw.get("modbusRegAddr"))
    columns = [
        {"id": unit_letter, "label": unit_columns[unit_letter]}
        for unit_letter in sorted(unit_columns)
    ]
    ordered_rows = [rows[key] for key in sorted(rows, key=_dx_metric_sort_key)]
    return {
        "columns": columns,
        "rows": ordered_rows,
        "systemRows": system_rows,
        "rowCount": len(ordered_rows),
        "columnCount": len(columns),
    }


def _matrix_cell(point: Any, reg_addr: Any) -> dict[str, Any]:
    return {
        "pointId": point.id,
        "displayName": point.display_name,
        "rawName": point.raw_name,
        "standardName": point.bacnet_object_prefix,
        "namingStatus": point.naming_status,
        "modbusRegAddr": reg_addr,
    }


def _dx_metric_label(metric_index: str, fallback: str) -> str:
    labels = {
        "1": "软件版本",
        "2": "外机地址",
        "3": "外机匹数",
        "4": "压缩机1频率",
        "5": "压缩机1交流电流",
        "6": "压缩机1直流母线电流",
        "7": "压缩机2频率",
        "8": "压缩机2交流电流",
        "9": "压缩机2直流母线电流",
        "10": "冷凝温度",
        "11": "蒸发温度",
        "12": "冷凝压力",
        "13": "蒸发压力",
    }
    return labels.get(metric_index, fallback)


def _dx_metric_sort_key(label: str) -> int:
    order = {
        "软件版本": 1,
        "外机地址": 2,
        "外机匹数": 3,
        "压缩机1频率": 4,
        "压缩机1交流电流": 5,
        "压缩机1直流母线电流": 6,
        "压缩机2频率": 7,
        "压缩机2交流电流": 8,
        "压缩机2直流母线电流": 9,
        "冷凝温度": 10,
        "蒸发温度": 11,
        "冷凝压力": 12,
        "蒸发压力": 13,
    }
    return order.get(label, 99)
