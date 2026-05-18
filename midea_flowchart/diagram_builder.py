from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json
import re
from typing import Any

from .flow_parser import ParsedFlow, _safe_filename, parse_programs_dir
from .naming_rules import NamingRuleIndex


POINT_TYPES = {"swInput", "hwInput", "hwOutput", "modbusOutput"}
IGNORED_TYPES = {"tab", "subflow"}
CONFIG_TYPES = {"constInput"}
REFERENCE_TYPES = {"quote"}
INTERFACE_TYPES = {"hwInput", "hwOutput", "modbusOutput"}
PID_TYPES = {"pid"}
LOGIC_TYPES = {"logic", "switch", "compare", "limit", "absolute"}
TIME_TYPES = {"delayOn", "delayOff", "delayOut", "edgeTrigger", "rsFlipflop", "srFlipflop"}
BIT_TYPES = {"bitFetch", "bitGroup", "bitOperation"}
MATH_TYPES = {"add", "subtract", "multiply", "divide", "linear", "round"}
STAT_TYPES = {"runtime", "sort", "statistics", "counter"}
PSY_TYPES = {"wetBulbT", "dewpointT", "moisture", "enthalpy"}


@dataclass(frozen=True)
class DomainProfile:
    name: str
    tab_roles: list[dict[str, Any]]
    point_groups: list[dict[str, Any]]


def build_diagrams_for_programs(
    programs_root: str | Path,
    naming_index_path: str | Path,
    profiles_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    programs_root = Path(programs_root)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    index = NamingRuleIndex(naming_index_path)
    profiles = _load_profiles(profiles_dir)
    diagrams = []
    for flow in parse_programs_dir(programs_root):
        diagram = build_diagram(flow, programs_root, index, profiles)
        diagram_path = output_dir / f"{_safe_filename(flow.family + '_' + flow.project + '_' + Path(flow.source_path).stem)}.json"
        diagram_path.write_text(json.dumps(diagram, ensure_ascii=False, indent=2), encoding="utf-8")
        diagrams.append({"path": str(diagram_path), "diagram": diagram})
    report = _build_diagram_report(diagrams)
    (output_dir.parent / "diagram_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir.parent / "diagram_report.md").write_text(
        _diagram_report_markdown(report),
        encoding="utf-8",
    )
    return report


def build_diagram(
    flow: ParsedFlow,
    programs_root: str | Path,
    naming_index: NamingRuleIndex,
    profiles: list[dict[str, Any]],
) -> dict[str, Any]:
    raw_nodes = json.loads(Path(flow.source_path).read_text(encoding="utf-8"))
    by_id = {node["id"]: node for node in raw_nodes if "id" in node}
    profile = _select_profile(flow, profiles)
    tab_by_id = {tab.id: tab for tab in flow.tabs}
    point_match_by_id = _match_points(flow, naming_index)

    overview = _build_overview(flow, raw_nodes, tab_by_id, profile)
    pages: dict[str, Any] = {}
    for tab in flow.tabs:
        pages[tab.id] = _build_page_diagram(
            flow=flow,
            tab_id=tab.id,
            raw_nodes=raw_nodes,
            by_id=by_id,
            profile=profile,
            point_match_by_id=point_match_by_id,
        )

    return {
        "schema_version": "0.1",
        "source_path": flow.source_path,
        "family": flow.family,
        "project": flow.project,
        "profile": profile.name,
        "overview": overview,
        "pages": pages,
        "trace": {
            "object_count": flow.object_count,
            "tab_count": len(flow.tabs),
            "subflow_count": len(flow.subflows),
            "edge_count": len(flow.edges),
        },
    }


def _build_overview(
    flow: ParsedFlow,
    raw_nodes: list[dict[str, Any]],
    tab_by_id: dict[str, Any],
    profile: DomainProfile,
) -> dict[str, Any]:
    node_tab = {node["id"]: node.get("z") for node in raw_nodes if node.get("z") in tab_by_id and "id" in node}
    nodes = []
    for index, tab in enumerate(flow.tabs):
        role = _tab_role(tab.label, profile)
        nodes.append(
            {
                "id": f"tab:{tab.id}",
                "label": role["label"] if role else tab.label,
                "raw_label": tab.label,
                "kind": "tab",
                "role": role["role"] if role else "page",
                "node_count": tab.node_count,
                "type_counts": tab.type_counts,
                "source_node_ids": [tab.id],
                "position": {"x": (index % 3) * 360, "y": (index // 3) * 220},
            }
        )
    edges = _aggregate_edges(flow.edges, lambda node_id: f"tab:{node_tab[node_id]}" if node_id in node_tab else None)
    edges = _merge_edges(edges, _quote_overview_edges(flow, node_tab))
    return {
        "nodes": nodes,
        "edges": edges,
        "metrics": {
            "module_count": len(nodes),
            "edge_count": len(edges),
            "compression_ratio": round(flow.object_count / len(nodes), 2) if nodes else 0,
        },
    }


def _build_page_diagram(
    flow: ParsedFlow,
    tab_id: str,
    raw_nodes: list[dict[str, Any]],
    by_id: dict[str, dict[str, Any]],
    profile: DomainProfile,
    point_match_by_id: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    tab = next(item for item in flow.tabs if item.id == tab_id)
    instance_by_id = {instance.id: instance for instance in flow.subflow_instances}
    modules: dict[str, dict[str, Any]] = {}
    node_to_module: dict[str, str] = {}
    for node in raw_nodes:
        if node.get("z") != tab_id or node.get("type") in IGNORED_TYPES:
            continue
        if node.get("type") in REFERENCE_TYPES:
            continue
        module_id, module_seed = _classify_node(node, profile, instance_by_id)
        module = modules.setdefault(module_id, _new_module(module_id, module_seed))
        _add_node_to_module(module, node, point_match_by_id.get(node["id"]))
        node_to_module[node["id"]] = module_id

    edges = _aggregate_edges(flow.edges, lambda node_id: node_to_module.get(node_id))
    ordered_modules = _ordered_modules(list(modules.values()))
    for index, module in enumerate(ordered_modules):
        module["position"] = {"x": (index % 4) * 340, "y": (index // 4) * 220}
    return {
        "id": tab.id,
        "label": tab.label,
        "nodes": ordered_modules,
        "edges": edges,
        "metrics": {
            "source_node_count": tab.node_count,
            "module_count": len(ordered_modules),
            "edge_count": len(edges),
            "compression_ratio": round(tab.node_count / len(ordered_modules), 2) if ordered_modules else 0,
            "unmatched_point_count": sum(module["unmatched_point_count"] for module in ordered_modules),
            "reference_node_count": sum(1 for node in raw_nodes if node.get("z") == tab_id and node.get("type") in REFERENCE_TYPES),
        },
    }


def _classify_node(
    node: dict[str, Any],
    profile: DomainProfile,
    instance_by_id: dict[str, Any],
) -> tuple[str, dict[str, str]]:
    node_type = node.get("type", "")
    if node_type.startswith("subflow:"):
        instance = instance_by_id.get(node["id"])
        label = instance.subflow_name if instance else node.get("name") or "子流程实例"
        return f"subflow:{node_type}", {"label": label, "kind": "subflow", "role": "control_module"}
    if node_type in INTERFACE_TYPES:
        label = {"hwInput": "物理输入", "hwOutput": "物理输出", "modbusOutput": "通讯点"}.get(node_type, "接口点")
        return f"interface:{node_type}", {"label": label, "kind": "interface", "role": node_type}
    if node_type == "swInput":
        group = _point_group(node, profile)
        return f"point:{group['key']}", {"label": group["label"], "kind": "points", "role": "software_points"}
    if node_type in CONFIG_TYPES:
        return "config:constants", {"label": "配置/常量", "kind": "config", "role": "constants"}
    algo = _algorithm_group(node_type)
    return f"algorithm:{algo['key']}", {"label": algo["label"], "kind": "algorithm", "role": algo["key"]}


def _algorithm_group(node_type: str) -> dict[str, str]:
    groups = [
        (LOGIC_TYPES | TIME_TYPES | BIT_TYPES, "logic_timing", "联锁/时序/状态位"),
        (PID_TYPES | MATH_TYPES | STAT_TYPES | PSY_TYPES, "calculation", "计算/PID/统计"),
    ]
    for types, key, label in groups:
        if node_type in types:
            return {"key": key, "label": label}
    return {"key": "other", "label": "其他逻辑"}


def _point_group(node: dict[str, Any], profile: DomainProfile) -> dict[str, str]:
    candidate = _point_name(node)
    compact = _prefix_token(candidate)
    for group in profile.point_groups:
        for prefix in group.get("prefixes", []):
            if compact == prefix.upper() or compact.startswith(prefix.upper() + "_") or compact.startswith(prefix.upper()):
                return {"key": _safe_key(group["label"]), "label": group["label"]}
        for keyword in group.get("keywords", []):
            if keyword and keyword.upper() in candidate.upper():
                return {"key": _safe_key(group["label"]), "label": group["label"]}
    if compact:
        return {"key": "other_points", "label": "其他软件点/设定点"}
    return {"key": "other_points", "label": "其他软件点/设定点"}


def _new_module(module_id: str, seed: dict[str, str]) -> dict[str, Any]:
    return {
        "id": module_id,
        "label": seed["label"],
        "kind": seed["kind"],
        "role": seed["role"],
        "source_node_ids": [],
        "source_node_count": 0,
        "type_counts": {},
        "point_count": 0,
        "matched_point_count": 0,
        "unmatched_point_count": 0,
        "sample_points": [],
    }


def _add_node_to_module(module: dict[str, Any], node: dict[str, Any], match: dict[str, Any] | None) -> None:
    node_type = node.get("type", "")
    module["source_node_ids"].append(node["id"])
    module["source_node_count"] += 1
    module["type_counts"][node_type] = module["type_counts"].get(node_type, 0) + 1
    if node_type in POINT_TYPES:
        module["point_count"] += 1
        if match and match["matched"]:
            module["matched_point_count"] += 1
        else:
            module["unmatched_point_count"] += 1
        if len(module["sample_points"]) < 8:
            module["sample_points"].append(_point_name(node))


def _aggregate_edges(edges: list[Any], module_for_node: Any) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for edge in edges:
        source = module_for_node(edge.source_id)
        target = module_for_node(edge.target_id)
        if not source or not target or source == target:
            continue
        item = grouped.setdefault(
            (source, target),
            {"id": f"{source}->{target}", "source": source, "target": target, "weight": 0, "source_edges": []},
        )
        item["weight"] += 1
        if len(item["source_edges"]) < 20:
            item["source_edges"].append(
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "source_port": edge.source_port,
                    "target_port": edge.target_port,
                }
            )
    return sorted(grouped.values(), key=lambda item: (-item["weight"], item["source"], item["target"]))


def _quote_overview_edges(flow: ParsedFlow, node_tab: dict[str, str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for quote in flow.quotes:
        if not quote.source_id or quote.source_id not in node_tab or quote.tab_id not in node_tab.values():
            continue
        source = f"tab:{node_tab[quote.source_id]}"
        target = f"tab:{quote.tab_id}"
        if source == target:
            continue
        item = grouped.setdefault(
            (source, target),
            {"id": f"{source}->{target}", "source": source, "target": target, "weight": 0, "source_edges": []},
        )
        item["weight"] += 1
        if len(item["source_edges"]) < 20:
            item["source_edges"].append({"source_id": quote.source_id, "target_id": quote.id, "source_port": quote.source_port, "target_port": 0})
    return sorted(grouped.values(), key=lambda item: (-item["weight"], item["source"], item["target"]))


def _merge_edges(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = {(edge["source"], edge["target"]): dict(edge) for edge in left}
    for edge in right:
        key = (edge["source"], edge["target"])
        if key not in grouped:
            grouped[key] = dict(edge)
            continue
        grouped[key]["weight"] += edge["weight"]
        remaining = 20 - len(grouped[key]["source_edges"])
        if remaining > 0:
            grouped[key]["source_edges"].extend(edge["source_edges"][:remaining])
    return sorted(grouped.values(), key=lambda item: (-item["weight"], item["source"], item["target"]))


def _match_points(flow: ParsedFlow, index: NamingRuleIndex) -> dict[str, dict[str, Any]]:
    result = {}
    for point in flow.points:
        match = index.match_candidates(point.candidates)
        result[point.id] = {
            "matched": match is not None,
            "rule_id": match.rule_id if match else None,
            "strategy": match.strategy if match else None,
        }
    return result


def _ordered_modules(modules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {"interface": 0, "points": 1, "config": 2, "reference": 3, "subflow": 4, "algorithm": 5}
    return sorted(modules, key=lambda item: (priority.get(item["kind"], 9), item["label"], item["id"]))


def _load_profiles(profiles_dir: str | Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(Path(profiles_dir).glob("*.json"))]


def _select_profile(flow: ParsedFlow, profiles: list[dict[str, Any]]) -> DomainProfile:
    for profile in profiles:
        family_match = any(keyword in flow.family for keyword in profile.get("family_keywords", []))
        file_keywords = profile.get("file_keywords", [])
        file_match = not file_keywords or any(keyword in flow.project or keyword in Path(flow.source_path).name for keyword in file_keywords)
        if family_match and file_match:
            return DomainProfile(
                name=profile["name"],
                tab_roles=profile.get("tab_roles", []),
                point_groups=profile.get("point_groups", []),
            )
    return DomainProfile(name="generic", tab_roles=[], point_groups=[])


def _tab_role(label: str, profile: DomainProfile) -> dict[str, str] | None:
    for item in profile.tab_roles:
        if all(part in label for part in item.get("contains", [])):
            return {"role": item["role"], "label": item["label"]}
    return None


def _point_name(node: dict[str, Any]) -> str:
    return str(node.get("bacnetObjectPrefix") or node.get("name") or node["id"]).strip()


def _prefix_token(value: str) -> str:
    value = re.sub(r"^\d+号", "", value.strip().upper())
    value = re.sub(r"^([A-Z]+)\d+_", r"\1_", value)
    value = re.sub(r"^M_", "", value)
    match = re.match(r"[A-Z]+(?:_[A-Z]+)?", value)
    if match:
        return match.group(0)
    cn_match = re.match(r"[\u4e00-\u9fff]+", value)
    return cn_match.group(0) if cn_match else ""


def _safe_key(value: str) -> str:
    return re.sub(r"[^A-Z0-9a-z\u4e00-\u9fff]+", "_", value).strip("_")


def _build_diagram_report(diagrams: list[dict[str, Any]]) -> dict[str, Any]:
    projects = []
    failures: list[str] = []
    for item in diagrams:
        diagram = item["diagram"]
        page_metrics = []
        for page in diagram["pages"].values():
            module_count = page["metrics"]["module_count"]
            if page["metrics"]["source_node_count"] and not (1 <= module_count <= 20):
                failures.append(f"{diagram['family']}/{diagram['project']} 页面 {page['label']} 模块数 {module_count} 超出 1-20")
            page_metrics.append(
                {
                    "label": page["label"],
                    "source_node_count": page["metrics"]["source_node_count"],
                    "module_count": module_count,
                    "edge_count": page["metrics"]["edge_count"],
                    "compression_ratio": page["metrics"]["compression_ratio"],
                    "unmatched_point_count": page["metrics"]["unmatched_point_count"],
                }
            )
        if diagram["overview"]["metrics"]["module_count"] == 0:
            failures.append(f"{diagram['family']}/{diagram['project']} 未生成总览图")
        projects.append(
            {
                "family": diagram["family"],
                "project": diagram["project"],
                "profile": diagram["profile"],
                "diagram_path": item["path"],
                "overview_modules": diagram["overview"]["metrics"]["module_count"],
                "overview_edges": diagram["overview"]["metrics"]["edge_count"],
                "pages": page_metrics,
            }
        )
    return {
        "project_count": len(projects),
        "projects": projects,
        "acceptance": {"passed": not failures, "failure_count": len(failures), "failures": failures},
    }


def _diagram_report_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# 抽象图验收报告",
        "",
        "| 项目 | Profile | 总览模块 | 总览边 | 页面数 | 最大页面模块 | 最大压缩率 | 未匹配点位 |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for project in report["projects"]:
        pages = project["pages"]
        max_modules = max((page["module_count"] for page in pages), default=0)
        max_ratio = max((page["compression_ratio"] for page in pages), default=0)
        unmatched = sum(page["unmatched_point_count"] for page in pages)
        lines.append(
            f"| {project['family']}/{project['project']} | {project['profile']} | "
            f"{project['overview_modules']} | {project['overview_edges']} | {len(pages)} | "
            f"{max_modules} | {max_ratio:.2f} | {unmatched} |"
        )
    lines.extend(["", "## 页面明细", ""])
    for project in report["projects"]:
        lines.append(f"### {project['family']}/{project['project']}")
        lines.append("")
        lines.append("| 页面 | 原始节点 | 模块 | 边 | 压缩率 | 未匹配点位 |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
        for page in project["pages"]:
            lines.append(
                f"| {page['label']} | {page['source_node_count']} | {page['module_count']} | "
                f"{page['edge_count']} | {page['compression_ratio']:.2f} | {page['unmatched_point_count']} |"
            )
        lines.append("")
    lines.extend(["## 验收结论", "", f"- 通过：{report['acceptance']['passed']}", f"- 失败项数量：{report['acceptance']['failure_count']}"])
    for failure in report["acceptance"]["failures"]:
        lines.append(f"- {failure}")
    return "\n".join(lines) + "\n"
