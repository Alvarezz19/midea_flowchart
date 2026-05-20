from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .models import (
    Diagnostic,
    EdgeModel,
    ModuleInstanceModel,
    NodeModel,
    PointModel,
    ProjectModel,
    SubflowModel,
    TabModel,
)
from .profiles import assign_tab_roles, classify_point_group, detect_profile, load_profiles

POINT_NODE_TYPES = {"swInput", "hwInput", "hwOutput", "modbusOutput", "quote"}


def load_project(path: str | Path, profiles_dir: str | Path = "configs/domain_profiles") -> ProjectModel:
    source_path = Path(path)
    raw_objects = _read_project_json(source_path)
    return load_project_from_objects(raw_objects, source_path, profiles_dir)


def load_project_from_text(
    content: str,
    source_path: str | Path = "<uploaded>",
    profiles_dir: str | Path = "configs/domain_profiles",
) -> ProjectModel:
    raw_objects = _read_project_json_text(content, Path(source_path))
    return load_project_from_objects(raw_objects, source_path, profiles_dir)


def load_project_from_objects(
    raw_objects: list[dict[str, Any]],
    source_path: str | Path = "<memory>",
    profiles_dir: str | Path = "configs/domain_profiles",
) -> ProjectModel:
    source_path = Path(source_path)
    project = ProjectModel(source_path=source_path, raw_count=len(raw_objects))

    _collect_tabs_and_subflows(project, raw_objects)
    profile = detect_profile(source_path, project.tabs, load_profiles(Path(profiles_dir)))
    project.profile_name = profile.name if profile else "generic"
    assign_tab_roles(project.tabs, profile)

    all_ids = _collect_nodes(project, raw_objects)
    _attach_nodes_to_owners(project)
    _collect_edges(project, all_ids)
    _collect_points(project, profile)
    _collect_stats(project)
    return project


def _read_project_json(path: Path) -> list[dict[str, Any]]:
    try:
        return _read_project_json_text(path.read_text(encoding="utf-8"), path)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误：{path}，第 {exc.lineno} 行第 {exc.colno} 列") from exc


def _read_project_json_text(content: str, source_path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON 格式错误：{source_path}，第 {exc.lineno} 行第 {exc.colno} 列") from exc
    if not isinstance(data, list):
        raise ValueError(f"JSON 顶层必须是数组：{source_path}")
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"JSON 顶层第 {index} 项必须是对象：{source_path}")
        if "id" not in item or "type" not in item:
            raise ValueError(f"JSON 顶层第 {index} 项缺少 id 或 type：{source_path}")
    return data


def _collect_tabs_and_subflows(project: ProjectModel, raw_objects: list[dict[str, Any]]) -> None:
    seen_ids: set[str] = set()
    for item in raw_objects:
        object_id = str(item["id"])
        if object_id in seen_ids:
            project.diagnostics.append(
                Diagnostic("error", "duplicate_id", "发现重复 id", object_id=object_id)
            )
        seen_ids.add(object_id)

        item_type = str(item["type"])
        if item_type == "tab":
            project.tabs[object_id] = TabModel(id=object_id, label=str(item.get("label") or item.get("name") or object_id))
        elif item_type == "subflow":
            project.subflows[object_id] = SubflowModel(
                id=object_id,
                name=str(item.get("name") or object_id),
                inputs=_read_port_count(item, "inputs", "in"),
                outputs=_read_port_count(item, "outputs", "out"),
            )


def _collect_nodes(project: ProjectModel, raw_objects: list[dict[str, Any]]) -> set[str]:
    all_ids = {str(item["id"]) for item in raw_objects}
    for item in raw_objects:
        item_type = str(item["type"])
        if item_type in {"tab", "subflow"}:
            continue

        node_id = str(item["id"])
        node = NodeModel(
            id=node_id,
            type=item_type,
            z=str(item["z"]) if item.get("z") is not None else None,
            name=str(item.get("name") or item.get("label") or item.get("labelName") or node_id),
            inputs=_read_port_count(item, "inputs", None),
            outputs=_read_port_count(item, "outputs", None),
            x=_read_number(item.get("x")),
            y=_read_number(item.get("y")),
            raw=item,
            role=_classify_node_role(item_type),
        )
        project.nodes[node_id] = node

        if item_type.startswith("subflow:"):
            subflow_id = item_type.split(":", 1)[1]
            subflow = project.subflows.get(subflow_id)
            project.module_instances[node_id] = ModuleInstanceModel(
                id=node_id,
                node_id=node_id,
                subflow_id=subflow_id,
                subflow_name=subflow.name if subflow else subflow_id,
                tab_id=node.z,
                name=node.name if node.name != node.id else (subflow.name if subflow else node.name),
                inputs=node.inputs,
                outputs=node.outputs,
            )
            if subflow is None:
                project.diagnostics.append(
                    Diagnostic("warning", "missing_subflow_definition", "子流程实例找不到定义", object_id=node_id)
                )
    return all_ids


def _attach_nodes_to_owners(project: ProjectModel) -> None:
    for node in project.nodes.values():
        if node.z in project.tabs:
            project.tabs[node.z].node_ids.append(node.id)
        elif node.z in project.subflows:
            project.subflows[node.z].internal_node_ids.append(node.id)
        elif node.z is not None:
            project.diagnostics.append(
                Diagnostic("warning", "unknown_owner", "节点 z 指向未知页签或子流程", object_id=node.id, context={"z": node.z})
            )


def _collect_edges(project: ProjectModel, all_ids: set[str]) -> None:
    edge_index = 0
    for target in project.nodes.values():
        wires = target.raw.get("wires", [])
        if wires is None:
            wires = []
        if not isinstance(wires, list):
            project.diagnostics.append(
                Diagnostic("warning", "invalid_wires", "节点 wires 不是数组，已忽略", object_id=target.id)
            )
            continue

        for target_port, upstream_items in enumerate(wires):
            if upstream_items is None:
                continue
            if not isinstance(upstream_items, list):
                project.diagnostics.append(
                    Diagnostic("warning", "invalid_wire_port", "wires 端口项不是数组，已忽略", object_id=target.id)
                )
                continue
            for upstream in upstream_items:
                if not isinstance(upstream, dict) or "id" not in upstream:
                    project.diagnostics.append(
                        Diagnostic("warning", "invalid_wire_ref", "连线引用不是有效对象，已忽略", object_id=target.id)
                    )
                    continue
                source_id = str(upstream["id"])
                source_port = int(upstream.get("port", 0) or 0)
                if source_id not in all_ids:
                    project.diagnostics.append(
                        Diagnostic("warning", "dangling_wire", "连线引用了不存在的上游节点", object_id=target.id, context={"source": source_id})
                    )
                    continue
                edge_index += 1
                project.edges.append(
                    EdgeModel(
                        id=f"e{edge_index}",
                        source_node_id=source_id,
                        source_port=source_port,
                        target_node_id=target.id,
                        target_port=target_port,
                    )
                )


def _collect_points(project: ProjectModel, profile: Any) -> None:
    for node in project.nodes.values():
        if node.type not in POINT_NODE_TYPES:
            continue
        raw_name = _best_raw_name(node.raw, node.id)
        candidates = _candidate_names(node.raw, raw_name)
        point = PointModel(
            id=node.id,
            node_id=node.id,
            raw_name=raw_name,
            display_name=raw_name,
            point_kind=_point_kind(node.type),
            candidate_names=candidates,
            bacnet_object_prefix=_optional_str(node.raw.get("bacnetObjectPrefix")),
            group=classify_point_group(candidates[0] if candidates else raw_name, profile),
        )
        project.points[point.id] = point
        node.point_id = point.id
        node.naming_status = point.naming_status


def _collect_stats(project: ProjectModel) -> None:
    for tab in project.tabs.values():
        type_counts = Counter(project.nodes[node_id].type for node_id in tab.node_ids if node_id in project.nodes)
        tab.stats = dict(type_counts)


def _best_raw_name(raw: dict[str, Any], fallback: str) -> str:
    for key in ("name", "labelName", "label", "bacnetObjectPrefix"):
        value = raw.get(key)
        if value not in (None, ""):
            return str(value)
    return fallback


def _candidate_names(raw: dict[str, Any], raw_name: str) -> list[str]:
    values: list[str] = []
    for value in (raw.get("bacnetObjectPrefix"), raw_name, raw.get("labelName"), raw.get("label")):
        if value not in (None, ""):
            values.append(str(value))

    expanded: list[str] = []
    for value in values:
        expanded.append(value)
        stripped = _strip_platform_prefix(value)
        if stripped != value:
            expanded.append(stripped)

    # 保持顺序去重，便于后续解释匹配来源。
    unique: list[str] = []
    seen: set[str] = set()
    for value in expanded:
        if value not in seen:
            unique.append(value)
            seen.add(value)
    return unique


def _strip_platform_prefix(value: str) -> str:
    text = value.strip()
    while text.startswith("[") and "]" in text:
        text = text[text.index("]") + 1 :].strip()
    return text


def _read_port_count(item: dict[str, Any], count_key: str, list_key: str | None) -> int:
    value = item.get(count_key)
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    if list_key is not None and isinstance(item.get(list_key), list):
        return len(item[list_key])
    return 0


def _read_number(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _optional_str(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


def _point_kind(node_type: str) -> str:
    return {
        "swInput": "software",
        "hwInput": "hardware_input",
        "hwOutput": "hardware_output",
        "modbusOutput": "communication",
        "quote": "reference",
    }.get(node_type, "unknown")


def _classify_node_role(node_type: str) -> str:
    if node_type in POINT_NODE_TYPES:
        return _point_kind(node_type)
    if node_type.startswith("subflow:"):
        return "module_instance"
    if node_type in {"logic", "switch", "compare", "limit", "delayOn", "delayOff", "edgeTrigger"}:
        return "control_logic"
    if node_type in {"pid", "add", "subtract", "multiply", "divide", "linear", "enthalpy", "moisture"}:
        return "algorithm"
    if node_type == "comment":
        return "comment"
    return "operator"
