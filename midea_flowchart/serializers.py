from __future__ import annotations

from collections import defaultdict
from typing import Any

from .models import ProjectModel, TabModel


def raw_graph(project: ProjectModel) -> dict[str, Any]:
    return {
        "nodes": [raw_node(project, node_id) for node_id in project.nodes],
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


def raw_node(project: ProjectModel, node_id: str) -> dict[str, Any]:
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


def point_to_dict(project: ProjectModel, point_id: str) -> dict[str, Any]:
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


def module_to_dict(module: Any) -> dict[str, Any]:
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


def naming_issues(project: ProjectModel) -> list[dict[str, Any]]:
    issues = []
    for point_id in sorted(project.points):
        point = project.points[point_id]
        if point.naming_status not in {"unmatched", "conflict", "ignored"}:
            continue
        issues.append(point_to_dict(project, point_id))
    return issues


def tab_point_ids(project: ProjectModel, tab_id: str) -> list[str]:
    return [
        point.id
        for point in project.points.values()
        if project.nodes[point.node_id].z == tab_id
    ]


def point_search_text(point: Any) -> str:
    return " ".join([point.raw_name, point.display_name, point.group, *point.candidate_names]).upper()


def tab_raw_trace(project: ProjectModel, tab: TabModel) -> dict[str, Any]:
    upstream: dict[str, list[dict[str, str]]] = defaultdict(list)
    downstream: dict[str, list[dict[str, str]]] = defaultdict(list)
    for edge in project.edges:
        source = project.nodes.get(edge.source_node_id)
        target = project.nodes.get(edge.target_node_id)
        if source is None or target is None:
            continue
        if target.z == tab.id:
            upstream[target.id].append({"nodeId": source.id, "name": source.name, "type": source.type})
        if source.z == tab.id:
            downstream[source.id].append({"nodeId": target.id, "name": target.name, "type": target.type})
    return {
        "nodes": [
            {
                "nodeId": node_id,
                "upstream": upstream.get(node_id, [])[:30],
                "downstream": downstream.get(node_id, [])[:30],
            }
            for node_id in tab.node_ids
            if upstream.get(node_id) or downstream.get(node_id)
        ]
    }


def diagnostic_to_dict(item: Any) -> dict[str, Any]:
    return {
        "severity": item.severity,
        "code": item.code,
        "message": item.message,
        "objectId": item.object_id,
        "context": item.context,
    }
