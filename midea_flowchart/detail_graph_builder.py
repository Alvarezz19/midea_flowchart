from __future__ import annotations

from collections import defaultdict
import re
from typing import Any

from .ahu_rules import (
    AHU_IO_MODULE_ORDER,
    MODULE_KIND_META,
    classify_control_point,
    classify_module_instance,
    control_profile_edges,
    detail_position,
    module_order_for_control_tab,
)
from .models import ProjectModel, TabModel
from .serializers import point_search_text


def tab_detail_graph(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    if project.profile_name == "ahu":
        if tab.role == "io_comm":
            return _io_comm_detail_graph(project, tab, point_ids)
        if tab.role == "control":
            return _control_detail_graph(project, tab, point_ids)
        if tab.role == "schedule":
            return _schedule_detail_graph(project, tab, point_ids)
        if tab.role == "dx_status":
            return _dx_status_detail_graph(project, tab, point_ids)
        if tab.role in {"dx_fault", "exhaust_fan"}:
            return _control_detail_graph(project, tab, point_ids)
    return _generic_tab_detail_graph(project, tab, point_ids)


def _io_comm_detail_graph(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    assignments: dict[str, str] = {}
    for point_id in point_ids:
        point = project.points[point_id]
        node = project.nodes[point.node_id]
        if node.type == "hwInput":
            assignments[node.id] = "field_input"
        elif node.type == "modbusOutput":
            assignments[node.id] = "comm_input" if _has_downstream(project, node.id) else "comm_output"
        elif node.type == "quote":
            assignments[node.id] = "reference"
        elif node.type == "hwOutput":
            assignments[node.id] = "physical_output"
        else:
            assignments[node.id] = "internal"
    pairs = [
        ("field_input", "internal"),
        ("comm_input", "internal"),
        ("reference", "internal"),
        ("internal", "physical_output"),
        ("internal", "comm_output"),
    ]
    nodes = [_module_graph_node(project, tab, module_id, assignments, index) for index, module_id in enumerate(AHU_IO_MODULE_ORDER)]
    edges = _supported_profile_edges(project, assignments, pairs)
    return {"level": "L2", "layout": "signal_flow", "nodes": nodes, "edges": edges, "supportEdges": _module_edges_from_assignments(project, assignments)}


def _control_detail_graph(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    assignments: dict[str, str] = {}
    for point_id in point_ids:
        point = project.points[point_id]
        module_id = classify_control_point(point)
        assignments[point.node_id] = module_id
    for module in project.module_instances.values():
        if module.tab_id == tab.id:
            assignments[module.node_id] = classify_module_instance(module.name, module.subflow_name, tab.role)
    _assign_connected_operator_nodes(project, tab, assignments)
    module_order = module_order_for_control_tab(tab.role)
    nodes = [
        _module_graph_node(project, tab, module_id, assignments, index)
        for index, module_id in enumerate(module_order)
        if module_id != "unclassified" or any(value == "unclassified" for value in assignments.values())
    ]
    edges = _supported_profile_edges(project, assignments, control_profile_edges(tab.role))
    return {"level": "L2", "layout": "module_flow", "nodes": nodes, "edges": edges, "supportEdges": _module_edges_from_assignments(project, assignments)}


def _schedule_detail_graph(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    assignments: dict[str, str] = {}
    for point_id in point_ids:
        point = project.points[point_id]
        name = point_search_text(point)
        assignments[point.node_id] = "timer_output" if "TIME_CST" in name else "timer_input"
    for node_id in tab.node_ids:
        if node_id not in assignments:
            assignments[node_id] = "timer_logic"
    nodes = [
        _module_graph_node(project, tab, "timer_input", assignments, 0),
        _module_graph_node(project, tab, "timer_logic", assignments, 1),
        _module_graph_node(project, tab, "timer_output", assignments, 2),
    ]
    edges = _supported_profile_edges(project, assignments, [("timer_input", "timer_logic"), ("timer_logic", "timer_output")])
    return {
        "level": "L2",
        "layout": "compact_logic",
        "nodes": nodes,
        "edges": edges,
        "supportEdges": _module_edges_from_assignments(project, assignments),
        "note": "TIME_CST 表示定时允许输出，由 TIME_EN 和 SP0 共同决定。",
    }


def _dx_status_detail_graph(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    assignments: dict[str, str] = {}
    for point_id in point_ids:
        node = project.nodes[project.points[point_id].node_id]
        assignments[node.id] = "dx_register" if node.type == "modbusOutput" else "dx_standard"
    for node_id in tab.node_ids:
        if node_id not in assignments:
            assignments[node_id] = "dx_convert"
    nodes = [
        _module_graph_node(project, tab, "dx_register", assignments, 0),
        _module_graph_node(project, tab, "dx_convert", assignments, 1),
        _module_graph_node(project, tab, "dx_standard", assignments, 2),
    ]
    edges = _supported_profile_edges(project, assignments, [("dx_register", "dx_convert"), ("dx_convert", "dx_standard")])
    return {"level": "L2", "layout": "mapping_matrix", "nodes": nodes, "edges": edges, "supportEdges": _module_edges_from_assignments(project, assignments)}


def _generic_tab_detail_graph(project: ProjectModel, tab: TabModel, point_ids: list[str]) -> dict[str, Any]:
    assignments: dict[str, str] = {}
    for point_id in point_ids:
        point = project.points[point_id]
        module_id = _safe_module_id(point.group)
        assignments[point.node_id] = module_id
    for module in project.module_instances.values():
        if module.tab_id == tab.id:
            assignments[module.node_id] = _safe_module_id(module.subflow_name)
    _assign_connected_operator_nodes(project, tab, assignments)
    module_ids = list(dict.fromkeys(assignments.values()))
    nodes = [_module_graph_node(project, tab, module_id, assignments, index, fallback_label=module_id) for index, module_id in enumerate(module_ids)]
    support_edges = _module_edges_from_assignments(project, assignments)
    return {"level": "L2", "layout": "generic_groups", "nodes": nodes, "edges": support_edges, "supportEdges": support_edges}


def _module_graph_node(
    project: ProjectModel,
    tab: TabModel,
    module_id: str,
    assignments: dict[str, str],
    index: int,
    fallback_label: str | None = None,
) -> dict[str, Any]:
    node_ids = [node_id for node_id, assigned in assignments.items() if assigned == module_id and node_id in project.nodes]
    point_ids = [project.nodes[node_id].point_id for node_id in node_ids if project.nodes[node_id].point_id]
    input_points = [
        point_id
        for point_id in point_ids
        if project.nodes[project.points[point_id].node_id].type in {"hwInput", "quote", "swInput"}
    ]
    output_points = [
        point_id
        for point_id in point_ids
        if project.nodes[project.points[point_id].node_id].type in {"hwOutput", "modbusOutput", "swInput"}
    ]
    meta = MODULE_KIND_META.get(module_id, {"label": fallback_label or module_id, "kind": "unknown"})
    x, y = detail_position(tab.role, index)
    issues = _recognition_issues(project, node_ids, point_ids)
    return {
        "id": module_id,
        "label": meta["label"],
        "kind": meta["kind"],
        "position": {"x": x, "y": y},
        "nodeIds": node_ids[:200],
        "inputPointIds": [item for item in input_points if item][:80],
        "outputPointIds": [item for item in output_points if item][:80],
        "stats": {
            "nodeCount": len(node_ids),
            "pointCount": len([item for item in point_ids if item]),
            "inputPointCount": len([item for item in input_points if item]),
            "outputPointCount": len([item for item in output_points if item]),
            "namingIssueCount": sum(
                1
                for point_id in point_ids
                if point_id and project.points[point_id].naming_status in {"unmatched", "conflict"}
            ),
        },
        "recognitionIssues": issues,
        "status": "incomplete" if issues else "ok",
    }


def _module_edges_from_assignments(project: ProjectModel, assignments: dict[str, str]) -> list[dict[str, Any]]:
    support_map: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in project.edges:
        source_module = assignments.get(edge.source_node_id)
        target_module = assignments.get(edge.target_node_id)
        if not source_module or not target_module or source_module == target_module:
            continue
        source = project.nodes[edge.source_node_id]
        target = project.nodes[edge.target_node_id]
        support_map[(source_module, target_module)].append(
            {
                "edgeId": edge.id,
                "sourceNodeId": source.id,
                "sourceName": source.name,
                "targetNodeId": target.id,
                "targetName": target.name,
            }
        )
    return [
        {
            "id": f"me{index}",
            "source": source,
            "target": target,
            "label": "原始连接支撑",
            "relationType": "raw_internal",
            "supportCount": len(support),
            "support": support[:20],
        }
        for index, ((source, target), support) in enumerate(sorted(support_map.items()), start=1)
    ]


def _supported_profile_edges(
    project: ProjectModel,
    assignments: dict[str, str],
    pairs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    raw_edges = _module_edges_from_assignments(project, assignments)
    support_by_pair = {(edge["source"], edge["target"]): edge for edge in raw_edges}
    supported_edges: list[dict[str, Any]] = []
    for index, (source, target) in enumerate(pairs, start=1):
        direct = support_by_pair.get((source, target))
        reverse = support_by_pair.get((target, source))
        direct_count = direct["supportCount"] if direct else 0
        reverse_count = reverse["supportCount"] if reverse else 0
        support_count = direct_count + reverse_count
        support_direction = "mixed" if direct_count and reverse_count else "direct" if direct_count else "reverse" if reverse_count else "none"
        support = []
        if direct:
            support.extend(direct["support"])
        if reverse:
            support.extend(reverse["support"])
        supported_edges.append(
            {
                "id": f"se{index}",
                "source": source,
                "target": target,
                "label": "业务规则链路",
                "relationType": "profile_rule",
                "directSupportCount": direct_count,
                "reverseSupportCount": reverse_count,
                "supportCount": support_count,
                "supportDirection": support_direction,
                "support": support[:20],
            }
        )
    return supported_edges


def _assign_connected_operator_nodes(project: ProjectModel, tab: TabModel, assignments: dict[str, str]) -> None:
    changed = True
    while changed:
        changed = False
        for edge in project.edges:
            source = project.nodes.get(edge.source_node_id)
            target = project.nodes.get(edge.target_node_id)
            if source is None or target is None or source.z != tab.id or target.z != tab.id:
                continue
            if edge.source_node_id in assignments and edge.target_node_id not in assignments:
                assignments[edge.target_node_id] = assignments[edge.source_node_id]
                changed = True
            elif edge.target_node_id in assignments and edge.source_node_id not in assignments:
                assignments[edge.source_node_id] = assignments[edge.target_node_id]
                changed = True
    for node_id in tab.node_ids:
        if node_id not in assignments and project.nodes[node_id].type != "comment":
            assignments[node_id] = "unclassified"


def _recognition_issues(project: ProjectModel, node_ids: list[str], point_ids: list[str | None]) -> list[str]:
    issues: list[str] = []
    actual_point_ids = [point_id for point_id in point_ids if point_id]
    if node_ids and not actual_point_ids:
        issues.append("无明确点位")
    if actual_point_ids and not any(
        project.nodes[project.points[point_id].node_id].type in {"hwOutput", "modbusOutput", "swInput"} for point_id in actual_point_ids
    ):
        issues.append("无明确输出点")
    if any(project.points[point_id].naming_status == "unmatched" for point_id in actual_point_ids):
        issues.append("存在未匹配命名")
    return issues


def _has_downstream(project: ProjectModel, node_id: str) -> bool:
    return any(edge.source_node_id == node_id for edge in project.edges)


def _safe_module_id(value: str) -> str:
    text = re.sub(r"\W+", "_", value.strip(), flags=re.UNICODE).strip("_")
    return text or "unclassified"
