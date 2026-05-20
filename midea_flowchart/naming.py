from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import PointModel, ProjectModel

GENERIC_NAMES = {"变量", "常量", "备用", "预留", "输入", "输出"}


@dataclass
class NamingMatch:
    status: str
    rule_ids: list[int]
    candidates: list[dict[str, Any]]
    matched_by: str | None = None


class NamingMatcher:
    def __init__(self, rules_path: str | Path = "data/naming_rules.json") -> None:
        self.rules_path = Path(rules_path)
        data = json.loads(self.rules_path.read_text(encoding="utf-8"))
        self.rules: dict[int, dict[str, Any]] = {int(rule["id"]): rule for rule in data.get("rules", [])}
        self.alias_norm: dict[str, set[int]] = {}
        self.alias_compact: dict[str, set[int]] = {}
        for alias in data.get("aliases", []):
            rule_id = int(alias["rule_id"])
            norm = str(alias.get("alias_norm") or normalize_name(alias.get("alias", "")))
            compact = str(alias.get("alias_compact") or compact_name(norm))
            self.alias_norm.setdefault(norm, set()).add(rule_id)
            self.alias_compact.setdefault(compact, set()).add(rule_id)

        # 规则本体也进入索引，避免别名文件缺项时漏匹配。
        for rule_id, rule in self.rules.items():
            for value in (rule.get("object_name"), rule.get("object_name_norm"), rule.get("chinese_desc")):
                if value not in (None, ""):
                    norm = normalize_name(str(value))
                    compact = compact_name(norm)
                    self.alias_norm.setdefault(norm, set()).add(rule_id)
                    self.alias_compact.setdefault(compact, set()).add(rule_id)

    def match_point(self, point: PointModel) -> NamingMatch:
        meaningful = [item for item in point.candidate_names if not is_generic_name(item)]
        if not meaningful:
            return NamingMatch(status="ignored", rule_ids=[], candidates=[])

        for candidate in meaningful:
            norm = normalize_name(candidate)
            rule_ids = sorted(self.alias_norm.get(norm, set()))
            if rule_ids:
                return self._to_match(rule_ids, "exact", candidate)

        for candidate in meaningful:
            compact = compact_name(candidate)
            rule_ids = sorted(self.alias_compact.get(compact, set()))
            if rule_ids:
                return self._to_match(rule_ids, "compact", candidate)

        prefix_match = self._prefix_match(meaningful)
        if prefix_match.rule_ids:
            return prefix_match

        return NamingMatch(status="unmatched", rule_ids=[], candidates=[])

    def _to_match(self, rule_ids: list[int], matched_by: str, source: str) -> NamingMatch:
        status = "matched" if len(rule_ids) == 1 else "conflict"
        return NamingMatch(
            status=status,
            rule_ids=rule_ids,
            candidates=[self._candidate(rule_id, source, matched_by) for rule_id in rule_ids],
            matched_by=matched_by,
        )

    def _prefix_match(self, candidates: list[str]) -> NamingMatch:
        for candidate in candidates:
            variants = _prefix_variants(candidate)
            for variant in variants:
                compact = compact_name(variant)
                rule_ids = sorted(self.alias_compact.get(compact, set()))
                if rule_ids:
                    return self._to_match(rule_ids, "prefix", candidate)
        return NamingMatch(status="unmatched", rule_ids=[], candidates=[])

    def _candidate(self, rule_id: int, source: str, matched_by: str) -> dict[str, Any]:
        rule = self.rules[rule_id]
        return {
            "rule_id": rule_id,
            "object_name": rule.get("object_name"),
            "chinese_desc": rule.get("chinese_desc"),
            "sheet_name": rule.get("sheet_name"),
            "matched_source": source,
            "matched_by": matched_by,
        }


def match_project_naming(project: ProjectModel, matcher: NamingMatcher) -> ProjectModel:
    stats = {"matched": 0, "conflict": 0, "unmatched": 0, "ignored": 0, "not_applicable": 0}
    for point in project.points.values():
        result = matcher.match_point(point)
        point.naming_status = result.status
        point.matched_rule_ids = result.rule_ids
        point.naming_candidates = result.candidates
        if result.status == "matched":
            rule = matcher.rules[result.rule_ids[0]]
            point.display_name = str(rule.get("chinese_desc") or rule.get("object_name") or point.raw_name)
        elif result.status == "conflict":
            point.display_name = point.raw_name
        project.nodes[point.node_id].naming_status = result.status
        stats[result.status] = stats.get(result.status, 0) + 1

    stats["not_applicable"] = len(project.nodes) - len(project.points)
    project.naming_stats = stats
    return project


def normalize_name(value: Any) -> str:
    text = str(value).strip()
    return text.upper()


def compact_name(value: Any) -> str:
    text = normalize_name(value)
    return re.sub(r"[\s_\-\/\\\(\)（）\[\]【】,，、:#]+", "", text)


def is_generic_name(value: str) -> bool:
    return value.strip() in GENERIC_NAMES


def _prefix_variants(value: str) -> list[str]:
    text = normalize_name(value)
    variants: list[str] = []
    # 设备编号常见于点位中，例如 SF1_RUN、HP_2_F。
    variants.append(re.sub(r"([A-Z]+)_?(\d+)_", r"\1_", text))
    variants.append(re.sub(r"([A-Z]+)(\d+)_", r"\1_", text))
    variants.append(re.sub(r"_(\d+)(?=_|$)", "", text))
    return [item for item in dict.fromkeys(variants) if item != text]
