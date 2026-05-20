from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import ProjectModel, TabModel


ROLE_META: dict[str, dict[str, str]] = {
    "io_comm": {"label": "IO/通讯", "kind": "boundary"},
    "control": {"label": "控制", "kind": "control"},
    "schedule": {"label": "定时", "kind": "schedule"},
    "dx_status": {"label": "直膨机状态", "kind": "communication"},
    "dx_fault": {"label": "直膨机故障", "kind": "alarm"},
    "exhaust_fan": {"label": "排风机", "kind": "output"},
    "unknown_tab": {"label": "未识别页签", "kind": "unknown"},
}

AHU_ROLE_ORDER = ["io_comm", "schedule", "dx_status", "control", "exhaust_fan", "dx_fault", "unknown_tab"]
AHU_RELATIONS = [
    ("io_comm", "control", "现场/通讯点位进入控制逻辑"),
    ("schedule", "control", "定时使能参与控制判断"),
    ("dx_status", "control", "直膨机状态反馈参与控制"),
    ("control", "io_comm", "控制结果写回输出和通讯点"),
    ("io_comm", "dx_status", "通讯寄存器支撑直膨状态解析"),
    ("dx_fault", "control", "直膨故障参与联锁保护"),
    ("control", "exhaust_fan", "控制逻辑生成排风机命令"),
]


def build_project_view(project: ProjectModel) -> dict[str, Any]:
    overview = build_overview_graph(project)
    return {
        "project": {
            "sourcePath": str(project.source_path),
            "profile": project.profile_name,
            "rawCount": project.raw_count,
            "tabCount": len(project.tabs),
            "subflowCount": len(project.subflows),
            "nodeCount": len(project.nodes),
            "edgeCount": len(project.edges),
            "pointCount": len(project.points),
            "moduleInstanceCount": len(project.module_instances),
            "diagnostics": [_diagnostic_to_dict(item) for item in project.diagnostics],
            "namingStats": dict(project.naming_stats),
        },
        "overview": overview,
        "tabs": [_tab_detail(project, tab) for tab in _ordered_tabs(project)],
        "namingIssues": _naming_issues(project),
        "rawGraph": _raw_graph(project),
    }


def build_overview_graph(project: ProjectModel) -> dict[str, Any]:
    tabs = _ordered_tabs(project)
    nodes = [_overview_node(project, tab, index) for index, tab in enumerate(tabs)]
    node_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        node_by_role[node["role"]].append(node)

    if project.profile_name == "ahu":
        edges = _ahu_edges(project, node_by_role)
    else:
        edges = _generic_edges(project)

    return {
        "level": "L1",
        "profile": project.profile_name,
        "nodes": nodes,
        "edges": edges,
        "legend": ROLE_META,
    }


def _overview_node(project: ProjectModel, tab: TabModel, index: int) -> dict[str, Any]:
    point_ids = _tab_point_ids(project, tab.id)
    issue_count = sum(1 for point_id in point_ids if project.points[point_id].naming_status in {"unmatched", "conflict"})
    module_count = sum(1 for item in project.module_instances.values() if item.tab_id == tab.id)
    unknown_count = sum(
        1
        for node_id in tab.node_ids
        if project.nodes[node_id].role in {"unknown_node", "operator"} and project.nodes[node_id].type not in {"comment"}
    )
    naming_counts = Counter(project.points[point_id].naming_status for point_id in point_ids)
    x, y = _overview_position(project, tab.role, index)
    meta = ROLE_META.get(tab.role, ROLE_META["unknown_tab"])
    label = meta["label"] if tab.role != "unknown_tab" else tab.label
    return {
        "id": f"tab:{tab.id}",
        "tabId": tab.id,
        "label": label,
        "sourceLabel": tab.label,
        "role": tab.role,
        "kind": meta["kind"],
        "position": {"x": x, "y": y},
        "stats": {
            "nodeCount": len(tab.node_ids),
            "pointCount": len(point_ids),
            "moduleInstanceCount": module_count,
            "namingIssueCount": issue_count,
            "unknownNodeCount": unknown_count,
            "matched": naming_counts.get("matched", 0),
            "conflict": naming_counts.get("conflict", 0),
            "unmatched": naming_counts.get("unmatched", 0),
            "ignored": naming_counts.get("ignored", 0),
        },
    }


def _ahu_edges(project: ProjectModel, node_by_role: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    raw_support = _cross_tab_support(project)
    edges: list[dict[str, Any]] = []
    edge_index = 0
    for source_role, target_role, label in AHU_RELATIONS:
        for source_node in node_by_role.get(source_role, []):
            for target_node in node_by_role.get(target_role, []):
                support = raw_support.get((source_node["tabId"], target_node["tabId"]), [])
                edge_index += 1
                edges.append(
                    {
                        "id": f"ae{edge_index}",
                        "source": source_node["id"],
                        "target": target_node["id"],
                        "label": label,
                        "relationType": "profile_rule",
                        "supportCount": len(support),
                        "support": support[:20],
                    }
                )
    return edges


def _generic_edges(project: ProjectModel) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for index, ((source_tab, target_tab), support) in enumerate(sorted(_cross_tab_support(project).items()), start=1):
        edges.append(
            {
                "id": f"ge{index}",
                "source": f"tab:{source_tab}",
                "target": f"tab:{target_tab}",
                "label": "跨页引用",
                "relationType": "raw_cross_tab",
                "supportCount": len(support),
                "support": support[:20],
            }
        )
    return edges


def _cross_tab_support(project: ProjectModel) -> dict[tuple[str, str], list[dict[str, Any]]]:
    support: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for edge in project.edges:
        source = project.nodes.get(edge.source_node_id)
        target = project.nodes.get(edge.target_node_id)
        if source is None or target is None or source.z == target.z:
            continue
        if source.z not in project.tabs or target.z not in project.tabs:
            continue
        support[(source.z, target.z)].append(
            {
                "edgeId": edge.id,
                "sourceNodeId": source.id,
                "sourceName": source.name,
                "targetNodeId": target.id,
                "targetName": target.name,
            }
        )
    return support


def _tab_detail(project: ProjectModel, tab: TabModel) -> dict[str, Any]:
    point_ids = _tab_point_ids(project, tab.id)
    points = [project.points[point_id] for point_id in point_ids]
    node_type_counts = Counter(project.nodes[node_id].type for node_id in tab.node_ids if node_id in project.nodes)
    return {
        "id": tab.id,
        "label": tab.label,
        "role": tab.role,
        "summary": {
            "nodeCount": len(tab.node_ids),
            "pointCount": len(point_ids),
            "moduleInstanceCount": sum(1 for item in project.module_instances.values() if item.tab_id == tab.id),
            "nodeTypeCounts": dict(sorted(node_type_counts.items())),
            "namingStats": dict(Counter(point.naming_status for point in points)),
        },
        "points": [_point_to_dict(project, point_id) for point_id in point_ids],
        "inputPoints": [_point_to_dict(project, point.id) for point in points if project.nodes[point.node_id].type in {"hwInput", "quote"}],
        "outputPoints": [_point_to_dict(project, point.id) for point in points if project.nodes[point.node_id].type in {"hwOutput", "modbusOutput"}],
        "moduleInstances": [_module_to_dict(item) for item in project.module_instances.values() if item.tab_id == tab.id],
        "rawNodes": [_raw_node(project, node_id) for node_id in tab.node_ids if node_id in project.nodes],
    }


def _raw_graph(project: ProjectModel) -> dict[str, Any]:
    return {
        "nodes": [_raw_node(project, node_id) for node_id in project.nodes],
        "edges": [
            {
                "id": edge.id,
                "source": edge.source_node_id,
                "target": edge.target_node_id,
                "sourcePort": edge.source_port,
                "targetPort": edge.target_port,
            }
            for edge in project.edges
        ],
    }


def _raw_node(project: ProjectModel, node_id: str) -> dict[str, Any]:
    node = project.nodes[node_id]
    return {
        "id": node.id,
        "type": node.type,
        "name": node.name,
        "tabId": node.z,
        "role": node.role,
        "pointId": node.point_id,
        "namingStatus": node.naming_status,
        "x": node.x,
        "y": node.y,
    }


def _point_to_dict(project: ProjectModel, point_id: str) -> dict[str, Any]:
    point = project.points[point_id]
    node = project.nodes[point.node_id]
    return {
        "id": point.id,
        "nodeId": point.node_id,
        "tabId": node.z,
        "rawName": point.raw_name,
        "displayName": point.display_name,
        "pointKind": point.point_kind,
        "group": point.group,
        "namingStatus": point.naming_status,
        "candidateNames": list(point.candidate_names),
        "matchedRuleIds": list(point.matched_rule_ids),
        "namingCandidates": list(point.naming_candidates),
        "nodeType": node.type,
    }


def _module_to_dict(module: Any) -> dict[str, Any]:
    return {
        "id": module.id,
        "nodeId": module.node_id,
        "subflowId": module.subflow_id,
        "subflowName": module.subflow_name,
        "tabId": module.tab_id,
        "name": module.name,
        "inputs": module.inputs,
        "outputs": module.outputs,
    }


def _naming_issues(project: ProjectModel) -> list[dict[str, Any]]:
    issues = []
    for point_id in sorted(project.points):
        point = project.points[point_id]
        if point.naming_status not in {"unmatched", "conflict", "ignored"}:
            continue
        issues.append(_point_to_dict(project, point_id))
    return issues


def _tab_point_ids(project: ProjectModel, tab_id: str) -> list[str]:
    return [
        point.id
        for point in project.points.values()
        if project.nodes[point.node_id].z == tab_id
    ]


def _ordered_tabs(project: ProjectModel) -> list[TabModel]:
    if project.profile_name == "ahu":
        role_rank = {role: index for index, role in enumerate(AHU_ROLE_ORDER)}
        return sorted(project.tabs.values(), key=lambda tab: (role_rank.get(tab.role, 99), tab.label))
    return list(project.tabs.values())


def _overview_position(project: ProjectModel, role: str, index: int) -> tuple[int, int]:
    if project.profile_name == "ahu":
        positions = {
            "io_comm": (90, 260),
            "schedule": (360, 110),
            "dx_status": (360, 410),
            "control": (640, 260),
            "exhaust_fan": (920, 160),
            "dx_fault": (920, 390),
        }
        if role in positions:
            return positions[role]
        return 920, 520 + index * 130
    return 110 + (index % 4) * 280, 120 + (index // 4) * 190


def _diagnostic_to_dict(item: Any) -> dict[str, Any]:
    return {
        "severity": item.severity,
        "code": item.code,
        "message": item.message,
        "objectId": item.object_id,
        "context": item.context,
    }
