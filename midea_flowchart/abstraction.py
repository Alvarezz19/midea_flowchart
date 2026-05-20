from __future__ import annotations

from collections import Counter
from typing import Any

from .detail_graph_builder import tab_detail_graph
from .dx_matrix import dx_status_matrix
from .models import ProjectModel, TabModel
from .overview_builder import build_overview_graph, ordered_tabs
from .serializers import (
    diagnostic_to_dict,
    module_to_dict,
    naming_issues,
    point_to_dict,
    raw_graph,
    raw_node,
    tab_point_ids,
    tab_raw_trace,
)


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
            "diagnostics": [diagnostic_to_dict(item) for item in project.diagnostics],
            "namingStats": dict(project.naming_stats),
        },
        "overview": overview,
        "tabs": [_tab_detail(project, tab) for tab in ordered_tabs(project)],
        "namingIssues": naming_issues(project),
        "rawGraph": raw_graph(project),
    }


def _tab_detail(project: ProjectModel, tab: TabModel) -> dict[str, Any]:
    point_ids = tab_point_ids(project, tab.id)
    points = [project.points[point_id] for point_id in point_ids]
    node_type_counts = Counter(project.nodes[node_id].type for node_id in tab.node_ids if node_id in project.nodes)
    detail_graph = tab_detail_graph(project, tab, point_ids)
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
        "points": [point_to_dict(project, point_id) for point_id in point_ids],
        "inputPoints": [point_to_dict(project, point.id) for point in points if project.nodes[point.node_id].type in {"hwInput", "quote"}],
        "outputPoints": [point_to_dict(project, point.id) for point in points if project.nodes[point.node_id].type in {"hwOutput", "modbusOutput"}],
        "moduleInstances": [module_to_dict(item) for item in project.module_instances.values() if item.tab_id == tab.id],
        "detailGraph": detail_graph,
        "statusMatrix": dx_status_matrix(project, tab, point_ids) if tab.role == "dx_status" else None,
        "rawTrace": tab_raw_trace(project, tab),
        "rawNodes": [raw_node(project, node_id) for node_id in tab.node_ids if node_id in project.nodes],
    }
