from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .naming import NamingMatcher, match_project_naming
from .parser import load_project


@dataclass
class ValidationResult:
    path: Path
    ok: bool
    profile: str
    raw_count: int
    tab_count: int
    subflow_count: int
    node_count: int
    edge_count: int
    point_count: int
    module_instance_count: int
    naming_stats: dict[str, int]
    errors: list[str]
    warnings: int


def validate_programs(programs_dir: str | Path = "programs") -> list[ValidationResult]:
    matcher = NamingMatcher()
    results: list[ValidationResult] = []
    for path in sorted(Path(programs_dir).rglob("*.json")):
        project = match_project_naming(load_project(path), matcher)
        errors = _project_errors(project)
        results.append(
            ValidationResult(
                path=path,
                ok=not errors,
                profile=project.profile_name,
                raw_count=project.raw_count,
                tab_count=len(project.tabs),
                subflow_count=len(project.subflows),
                node_count=len(project.nodes),
                edge_count=len(project.edges),
                point_count=len(project.points),
                module_instance_count=len(project.module_instances),
                naming_stats=project.naming_stats,
                errors=errors,
                warnings=project.warning_count,
            )
        )
    return results


def _project_errors(project) -> list[str]:
    errors: list[str] = []
    if project.error_count:
        errors.append(f"存在 {project.error_count} 个解析错误")
    if project.raw_count <= 0:
        errors.append("原始对象数量为 0")
    if not project.tabs:
        errors.append("未识别到页签")
    if not project.nodes:
        errors.append("未识别到普通节点")
    if not project.edges:
        errors.append("未生成连线")
    if not project.points:
        errors.append("未识别到点位")
    naming_total = sum(project.naming_stats.get(key, 0) for key in ("matched", "conflict", "unmatched", "ignored"))
    if naming_total != len(project.points):
        errors.append(f"命名统计不等于点位数量：{naming_total} != {len(project.points)}")
    return errors
