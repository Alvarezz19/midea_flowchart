from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .ahu_rules import AHU_RELATIONS, AHU_ROLE_ORDER, ROLE_META, overview_position
from .models import ProjectModel, TabModel
from .serializers import tab_point_ids


def build_overview_graph(project: ProjectModel) -> dict[str, Any]:
    tabs = ordered_tabs(project)
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


def ordered_tabs(project: ProjectModel) -> list[TabModel]:
    if project.profile_name == "ahu":
        role_rank = {role: index for index, role in enumerate(AHU_ROLE_ORDER)}
        return sorted(project.tabs.values(), key=lambda tab: (role_rank.get(tab.role, 99), tab.label))
    return list(project.tabs.values())


def _overview_node(project: ProjectModel, tab: TabModel, index: int) -> dict[str, Any]:
    point_ids = tab_point_ids(project, tab.id)
    issue_count = sum(1 for point_id in point_ids if project.points[point_id].naming_status in {"unmatched", "conflict"})
    module_count = sum(1 for item in project.module_instances.values() if item.tab_id == tab.id)
    unknown_count = sum(
        1
        for node_id in tab.node_ids
        if project.nodes[node_id].role in {"unknown_node", "operator"} and project.nodes[node_id].type not in {"comment"}
    )
    naming_counts = Counter(project.points[point_id].naming_status for point_id in point_ids)
    x, y = overview_position(project.profile_name, tab.role, index)
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
