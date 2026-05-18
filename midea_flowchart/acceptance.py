from __future__ import annotations

from pathlib import Path
import json
from typing import Any

from .flow_parser import ParsedFlow, parse_programs_dir, write_intermediate
from .naming_rules import NamingRuleIndex, compile_naming_rules


def build_acceptance_report(
    programs_root: str | Path,
    excel_path: str | Path,
    data_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    programs_root = Path(programs_root)
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    intermediate_dir = output_dir / "intermediate"
    output_dir.mkdir(parents=True, exist_ok=True)

    naming_meta = compile_naming_rules(
        excel_path=excel_path,
        sqlite_path=data_dir / "naming_rules.sqlite",
        json_path=data_dir / "naming_rules.json",
    )
    index = NamingRuleIndex(data_dir / "naming_rules.json")
    parsed_flows = parse_programs_dir(programs_root)
    projects = [_project_report(flow, index) for flow in parsed_flows]
    intermediate_paths = [str(write_intermediate(flow, intermediate_dir)) for flow in parsed_flows]

    report = {
        "naming_rules": {
            "source_path": naming_meta["source_path"],
            "sqlite_path": naming_meta["sqlite_path"],
            "json_path": naming_meta["json_path"],
            "rule_count": naming_meta["rule_count"],
            "alias_count": naming_meta["alias_count"],
            "alias_conflict_count": naming_meta["alias_conflict_count"],
        },
        "program_count": len(projects),
        "projects": projects,
        "intermediate_paths": intermediate_paths,
        "acceptance": _acceptance_summary(projects, naming_meta),
    }
    (output_dir / "acceptance_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "acceptance_report.md").write_text(
        _markdown_report(report),
        encoding="utf-8",
    )
    return report


def _project_report(flow: ParsedFlow, index: NamingRuleIndex) -> dict[str, Any]:
    quote_total = len(flow.quotes)
    quote_resolved = sum(1 for quote in flow.quotes if quote.resolved)
    point_matches = [_match_point(point, index) for point in flow.points]
    matched = [item for item in point_matches if item["matched"]]
    unmatched = [item for item in point_matches if not item["matched"]]
    return {
        "source_path": flow.source_path,
        "family": flow.family,
        "project": flow.project,
        "object_count": flow.object_count,
        "tab_count": len(flow.tabs),
        "subflow_count": len(flow.subflows),
        "subflow_instance_count": len(flow.subflow_instances),
        "edge_count": len(flow.edges),
        "quote_total": quote_total,
        "quote_resolved": quote_resolved,
        "quote_resolution_rate": round(quote_resolved / quote_total, 4) if quote_total else 1.0,
        "point_total": len(flow.points),
        "point_matched": len(matched),
        "point_unmatched": len(unmatched),
        "point_match_rate": round(len(matched) / len(flow.points), 4) if flow.points else 1.0,
        "tabs": [tab.__dict__ for tab in flow.tabs],
        "subflows": [subflow.__dict__ for subflow in flow.subflows],
        "node_type_counts": flow.node_type_counts,
        "unmatched_points_sample": unmatched[:80],
    }


def _match_point(point: Any, index: NamingRuleIndex) -> dict[str, Any]:
    match = index.match_candidates(point.candidates)
    return {
        "id": point.id,
        "type": point.type,
        "display_name": point.display_name,
        "candidates": point.candidates,
        "matched": match is not None,
        "rule_id": match.rule_id if match else None,
        "strategy": match.strategy if match else None,
        "candidate": match.candidate if match else None,
    }


def _acceptance_summary(projects: list[dict[str, Any]], naming_meta: dict[str, Any]) -> dict[str, Any]:
    failures: list[str] = []
    if naming_meta["rule_count"] < 100:
        failures.append("命名规则数量异常偏低")
    if naming_meta["alias_count"] <= naming_meta["rule_count"]:
        failures.append("命名规则别名索引数量未超过规则数量")
    for project in projects:
        label = f"{project['family']}/{project['project']}"
        if project["tab_count"] == 0:
            failures.append(f"{label} 未解析到 tab")
        if project["edge_count"] == 0:
            failures.append(f"{label} 未解析到 edge")
        if project["quote_total"] and project["quote_resolution_rate"] < 0.99:
            failures.append(f"{label} quote 回溯率低于 99%")
        if project["point_total"] == 0:
            failures.append(f"{label} 未提取到点位")
    return {
        "passed": not failures,
        "failure_count": len(failures),
        "failures": failures,
    }


def _markdown_report(report: dict[str, Any]) -> str:
    lines = [
        "# 验收报告",
        "",
        "## 命名规则索引",
        "",
        f"- 规则数量：{report['naming_rules']['rule_count']}",
        f"- 别名数量：{report['naming_rules']['alias_count']}",
        f"- 别名冲突数量：{report['naming_rules']['alias_conflict_count']}",
        f"- SQLite：`{report['naming_rules']['sqlite_path']}`",
        f"- JSON：`{report['naming_rules']['json_path']}`",
        "",
        "## 项目解析",
        "",
        "| 项目 | 对象 | 页签 | 子流程 | 实例 | 边 | quote回溯 | 点位匹配 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for project in report["projects"]:
        lines.append(
            "| "
            f"{project['family']}/{project['project']} | "
            f"{project['object_count']} | "
            f"{project['tab_count']} | "
            f"{project['subflow_count']} | "
            f"{project['subflow_instance_count']} | "
            f"{project['edge_count']} | "
            f"{project['quote_resolution_rate']:.2%} | "
            f"{project['point_match_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## 验收结论",
            "",
            f"- 通过：{report['acceptance']['passed']}",
            f"- 失败项数量：{report['acceptance']['failure_count']}",
        ]
    )
    for failure in report["acceptance"]["failures"]:
        lines.append(f"- {failure}")
    return "\n".join(lines) + "\n"
