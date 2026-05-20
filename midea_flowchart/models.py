from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Diagnostic:
    severity: str
    code: str
    message: str
    object_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class TabModel:
    id: str
    label: str
    role: str = "unknown_tab"
    node_ids: list[str] = field(default_factory=list)
    stats: dict[str, int] = field(default_factory=dict)


@dataclass
class SubflowModel:
    id: str
    name: str
    inputs: int
    outputs: int
    internal_node_ids: list[str] = field(default_factory=list)


@dataclass
class NodeModel:
    id: str
    type: str
    z: str | None
    name: str
    inputs: int
    outputs: int
    x: float | None
    y: float | None
    raw: dict[str, Any]
    role: str = "unknown_node"
    point_id: str | None = None
    naming_status: str = "not_applicable"


@dataclass
class EdgeModel:
    id: str
    source_node_id: str
    source_port: int
    target_node_id: str
    target_port: int
    relation_type: str = "wire"
    confidence: float = 1.0


@dataclass
class PointModel:
    id: str
    node_id: str
    raw_name: str
    display_name: str
    point_kind: str
    candidate_names: list[str] = field(default_factory=list)
    bacnet_object_prefix: str | None = None
    group: str = "未归类"
    naming_status: str = "unmatched"
    matched_rule_ids: list[int] = field(default_factory=list)
    naming_candidates: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ModuleInstanceModel:
    id: str
    node_id: str
    subflow_id: str
    subflow_name: str
    tab_id: str | None
    name: str
    inputs: int
    outputs: int


@dataclass
class ProjectModel:
    source_path: Path
    raw_count: int
    tabs: dict[str, TabModel] = field(default_factory=dict)
    subflows: dict[str, SubflowModel] = field(default_factory=dict)
    nodes: dict[str, NodeModel] = field(default_factory=dict)
    edges: list[EdgeModel] = field(default_factory=list)
    points: dict[str, PointModel] = field(default_factory=dict)
    module_instances: dict[str, ModuleInstanceModel] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    profile_name: str = "generic"
    profile_config: dict[str, Any] = field(default_factory=dict)
    naming_stats: dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.diagnostics if item.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.diagnostics if item.severity == "warning")
