from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from typing import Any


POINT_TYPES = {"swInput", "hwInput", "hwOutput", "modbusOutput"}
GENERIC_NODE_NAMES = {"变量", "引用", "物理输入", "物理输出", "常量", ""}
QUOTE_REF_RE = re.compile(r"^\[([^:\]]+):(\d+)\]\s*(.*)$")
BRACKET_PREFIX_RE = re.compile(r"^(?:\[[^\]]+\]\s*)+")


@dataclass(frozen=True)
class FlowEdge:
    source_id: str
    source_port: int
    target_id: str
    target_port: int
    target_tab_id: str | None
    source_type: str | None
    target_type: str


@dataclass(frozen=True)
class FlowTab:
    id: str
    label: str
    node_count: int
    type_counts: dict[str, int]


@dataclass(frozen=True)
class FlowSubflow:
    id: str
    name: str
    inputs: int
    outputs: int
    node_count: int
    instance_count: int


@dataclass(frozen=True)
class FlowSubflowInstance:
    id: str
    tab_id: str | None
    subflow_id: str
    subflow_name: str
    inputs: int
    outputs: int
    x: float | int | None
    y: float | int | None


@dataclass(frozen=True)
class FlowQuote:
    id: str
    tab_id: str | None
    label_name: str
    source_id: str | None
    source_port: int | None
    display_name: str
    resolved: bool
    x: float | int | None
    y: float | int | None


@dataclass(frozen=True)
class FlowPoint:
    id: str
    tab_id: str | None
    type: str
    name: str
    bacnet_object_prefix: str
    display_name: str
    candidates: list[str]
    x: float | int | None
    y: float | int | None


@dataclass(frozen=True)
class ParsedFlow:
    source_path: str
    family: str
    project: str
    object_count: int
    tabs: list[FlowTab]
    subflows: list[FlowSubflow]
    subflow_instances: list[FlowSubflowInstance]
    quotes: list[FlowQuote]
    points: list[FlowPoint]
    edges: list[FlowEdge]
    node_type_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_flow_file(path: str | Path, programs_root: str | Path = "programs") -> ParsedFlow:
    source_path = Path(path)
    programs_root = Path(programs_root)
    data = json.loads(source_path.read_text(encoding="utf-8"))
    by_id = {node["id"]: node for node in data if "id" in node}
    tabs_raw = [node for node in data if node.get("type") == "tab"]
    subflows_raw = [node for node in data if node.get("type") == "subflow"]
    tab_ids = {node["id"] for node in tabs_raw}
    subflow_by_id = {node["id"]: node for node in subflows_raw}

    tabs = [_build_tab(tab, data) for tab in tabs_raw]
    subflows = [_build_subflow(subflow, data) for subflow in subflows_raw]
    instances = [_build_subflow_instance(node, subflow_by_id) for node in data if _is_subflow_instance(node)]
    quotes = [_build_quote(node, by_id) for node in data if node.get("type") == "quote"]
    points = [_build_point(node) for node in data if node.get("type") in POINT_TYPES]
    edges = _build_edges(data, by_id)
    node_type_counts = _count_by_type(data)
    family, project = _infer_family_project(source_path, programs_root)

    return ParsedFlow(
        source_path=str(source_path),
        family=family,
        project=project,
        object_count=len(data),
        tabs=tabs,
        subflows=subflows,
        subflow_instances=instances,
        quotes=quotes,
        points=points,
        edges=edges,
        node_type_counts=node_type_counts,
    )


def parse_programs_dir(programs_root: str | Path) -> list[ParsedFlow]:
    root = Path(programs_root)
    return [parse_flow_file(path, root) for path in sorted(root.rglob("*.json"))]


def write_intermediate(parsed: ParsedFlow, output_dir: str | Path) -> Path:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    filename = _safe_filename(f"{parsed.family}_{parsed.project}_{Path(parsed.source_path).stem}.json")
    output_path = output_dir / filename
    output_path.write_text(
        json.dumps(parsed.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path


def _build_tab(tab: dict[str, Any], data: list[dict[str, Any]]) -> FlowTab:
    nodes = [node for node in data if node.get("z") == tab["id"]]
    return FlowTab(
        id=tab["id"],
        label=tab.get("label", ""),
        node_count=len(nodes),
        type_counts=_count_by_type(nodes),
    )


def _build_subflow(subflow: dict[str, Any], data: list[dict[str, Any]]) -> FlowSubflow:
    nodes = [node for node in data if node.get("z") == subflow["id"]]
    instances = [node for node in data if node.get("type") == f"subflow:{subflow['id']}"]
    return FlowSubflow(
        id=subflow["id"],
        name=subflow.get("name") or subflow.get("label") or "",
        inputs=len(subflow.get("in") or []),
        outputs=len(subflow.get("out") or []),
        node_count=len(nodes),
        instance_count=len(instances),
    )


def _build_subflow_instance(node: dict[str, Any], subflow_by_id: dict[str, dict[str, Any]]) -> FlowSubflowInstance:
    subflow_id = node["type"].split(":", 1)[1]
    subflow = subflow_by_id[subflow_id]
    return FlowSubflowInstance(
        id=node["id"],
        tab_id=node.get("z"),
        subflow_id=subflow_id,
        subflow_name=subflow.get("name") or subflow.get("label") or "",
        inputs=int(node.get("inputs") or 0),
        outputs=int(node.get("outputs") or 0),
        x=node.get("x"),
        y=node.get("y"),
    )


def _build_quote(node: dict[str, Any], by_id: dict[str, dict[str, Any]]) -> FlowQuote:
    source_id, source_port, remainder = parse_quote_label(node.get("labelName", ""))
    return FlowQuote(
        id=node["id"],
        tab_id=node.get("z"),
        label_name=node.get("labelName", ""),
        source_id=source_id,
        source_port=source_port,
        display_name=_clean_quote_display_name(remainder or node.get("labelName", "")),
        resolved=bool(source_id and source_id in by_id),
        x=node.get("x"),
        y=node.get("y"),
    )


def _build_point(node: dict[str, Any]) -> FlowPoint:
    name = str(node.get("name") or "")
    prefix = str(node.get("bacnetObjectPrefix") or "")
    display_name = _point_display_name(node)
    candidates = _point_candidates(node, display_name)
    return FlowPoint(
        id=node["id"],
        tab_id=node.get("z"),
        type=node["type"],
        name=name,
        bacnet_object_prefix=prefix,
        display_name=display_name,
        candidates=candidates,
        x=node.get("x"),
        y=node.get("y"),
    )


def parse_quote_label(label_name: str) -> tuple[str | None, int | None, str]:
    match = QUOTE_REF_RE.match(label_name or "")
    if not match:
        return None, None, label_name or ""
    return match.group(1), int(match.group(2)), match.group(3)


def _build_edges(data: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]) -> list[FlowEdge]:
    edges: list[FlowEdge] = []
    for target in data:
        wires = target.get("wires")
        if not isinstance(wires, list):
            continue
        for target_port, upstream_group in enumerate(wires):
            if not isinstance(upstream_group, list):
                continue
            for upstream in upstream_group:
                source_id = upstream.get("id")
                if not source_id:
                    continue
                source = by_id.get(source_id)
                edges.append(
                    FlowEdge(
                        source_id=source_id,
                        source_port=int(upstream.get("port") or 0),
                        target_id=target["id"],
                        target_port=target_port,
                        target_tab_id=target.get("z"),
                        source_type=source.get("type") if source else None,
                        target_type=target.get("type", ""),
                    )
                )
    return edges


def _point_display_name(node: dict[str, Any]) -> str:
    prefix = str(node.get("bacnetObjectPrefix") or "").strip()
    name = str(node.get("name") or "").strip()
    if prefix:
        return prefix
    if name and name not in GENERIC_NODE_NAMES:
        return name
    return name or node["id"]


def _point_candidates(node: dict[str, Any], display_name: str) -> list[str]:
    values = [
        str(node.get("bacnetObjectPrefix") or ""),
        str(node.get("name") or ""),
        display_name,
    ]
    seen: set[str] = set()
    candidates: list[str] = []
    for value in values:
        value = value.strip()
        if value and value not in GENERIC_NODE_NAMES and value not in seen:
            seen.add(value)
            candidates.append(value)
    return candidates


def _clean_quote_display_name(remainder: str) -> str:
    value = BRACKET_PREFIX_RE.sub("", remainder or "").strip()
    return value or remainder.strip()


def _is_subflow_instance(node: dict[str, Any]) -> bool:
    node_type = node.get("type")
    return isinstance(node_type, str) and node_type.startswith("subflow:")


def _count_by_type(nodes: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in nodes:
        node_type = node.get("type", "")
        counts[node_type] = counts.get(node_type, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _infer_family_project(source_path: Path, programs_root: Path) -> tuple[str, str]:
    try:
        parts = source_path.relative_to(programs_root).parts
    except ValueError:
        parts = source_path.parts
    family = parts[0] if len(parts) > 1 else ""
    project = parts[1] if len(parts) > 2 else source_path.stem
    return family, project


def _safe_filename(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]+', "_", value).strip("_")
