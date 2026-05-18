from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import hashlib
import json
import re
import sqlite3
from typing import Any

from .xlsx_reader import read_xlsx


RULE_START_ROW = 3
DIRECTORY_SHEET = "目录"


@dataclass(frozen=True)
class NamingRule:
    id: int
    sheet_name: str
    source_row: int
    struct_type: str
    data_type: str
    object_name: str
    object_name_norm: str
    object_name_compact: str
    rw: str
    english_desc: str
    chinese_desc: str
    unit_state0_en: str
    unit_state1_en: str
    unit_state0_cn: str
    unit_state1_cn: str
    decimal_point: str
    default_value: str


@dataclass(frozen=True)
class RuleMatch:
    rule_id: int
    strategy: str
    candidate: str


def compile_naming_rules(
    excel_path: str | Path,
    sqlite_path: str | Path,
    json_path: str | Path,
) -> dict[str, Any]:
    excel_path = Path(excel_path)
    sqlite_path = Path(sqlite_path)
    json_path = Path(json_path)
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    rules = _extract_rules(excel_path)
    aliases = _build_aliases(rules)
    conflicts = _find_alias_conflicts(aliases)
    meta = {
        "source_path": str(excel_path),
        "source_sha256": _sha256(excel_path),
        "rule_count": len(rules),
        "alias_count": len(aliases),
        "alias_conflict_count": len(conflicts),
    }

    _write_sqlite(sqlite_path, rules, aliases, conflicts, meta)
    _write_json(json_path, rules, aliases, conflicts, meta)
    return {
        **meta,
        "sqlite_path": str(sqlite_path),
        "json_path": str(json_path),
        "conflicts": conflicts,
    }


class NamingRuleIndex:
    def __init__(self, json_path: str | Path):
        payload = json.loads(Path(json_path).read_text(encoding="utf-8"))
        self.rules_by_id = {int(rule["id"]): rule for rule in payload["rules"]}
        self.alias_norm: dict[str, list[int]] = {}
        self.alias_compact: dict[str, list[int]] = {}
        self.chinese_rules: list[dict[str, Any]] = []
        for alias in payload["aliases"]:
            self.alias_norm.setdefault(alias["alias_norm"], []).append(int(alias["rule_id"]))
            self.alias_compact.setdefault(alias["alias_compact"], []).append(int(alias["rule_id"]))
        for rule in payload["rules"]:
            chinese_desc = rule.get("chinese_desc") or ""
            if len(chinese_desc) >= 3:
                self.chinese_rules.append(rule)

    def match_candidates(self, candidates: list[str]) -> RuleMatch | None:
        for candidate in candidates:
            match = self.match(candidate)
            if match:
                return match
        return None

    def match(self, candidate: str) -> RuleMatch | None:
        for variant in candidate_variants(candidate):
            norm = normalize_name(variant)
            compact = compact_name(variant)
            for strategy, table, key in (
                ("alias_norm", self.alias_norm, norm),
                ("alias_compact", self.alias_compact, compact),
            ):
                ids = table.get(key)
                if ids:
                    return RuleMatch(rule_id=ids[0], strategy=strategy, candidate=variant)
            chinese_match = self._match_chinese(variant)
            if chinese_match:
                return RuleMatch(rule_id=int(chinese_match["id"]), strategy="chinese_contains", candidate=variant)
        return None

    def _match_chinese(self, candidate: str) -> dict[str, Any] | None:
        if not re.search(r"[\u4e00-\u9fff]", candidate):
            return None
        for rule in self.chinese_rules:
            chinese_desc = rule["chinese_desc"]
            if chinese_desc and (chinese_desc in candidate or candidate in chinese_desc):
                return rule
        return None


def normalize_name(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "").strip().upper())


def compact_name(value: Any) -> str:
    return re.sub(r"[^A-Z0-9\u4e00-\u9fff]", "", normalize_name(value))


def candidate_variants(value: str) -> list[str]:
    variants = [str(value or "").strip()]
    # 工程点位常带“1号/2号”前缀，命名规则通常描述设备类型而不是实例。
    variants.append(re.sub(r"^\d+号", "", variants[0]))
    # 英文点位常把实例号插在设备缩写后，例如 HP4_Run -> HP_Run。
    variants.append(re.sub(r"^([A-Z]+)(\d+)([_A-Z])", r"\1\3", normalize_name(variants[0])))
    variants.append(re.sub(r"^([A-Z]+)(\d+)_", r"\1_", normalize_name(variants[0])))

    result: list[str] = []
    seen: set[str] = set()
    for variant in variants:
        if variant and variant not in seen:
            seen.add(variant)
            result.append(variant)
    return result


def _extract_rules(excel_path: Path) -> list[NamingRule]:
    workbook = read_xlsx(excel_path)
    rules: list[NamingRule] = []
    rule_id = 1
    for sheet_name, rows in workbook.items():
        if sheet_name == DIRECTORY_SHEET:
            continue
        for row_number, row in enumerate(rows[RULE_START_ROW - 1 :], start=RULE_START_ROW):
            object_name = _cell(row, 2)
            if not object_name:
                continue
            rule = NamingRule(
                id=rule_id,
                sheet_name=sheet_name,
                source_row=row_number,
                struct_type=_cell(row, 0),
                data_type=_cell(row, 1),
                object_name=object_name,
                object_name_norm=normalize_name(object_name),
                object_name_compact=compact_name(object_name),
                rw=_cell(row, 3),
                english_desc=_cell(row, 4),
                chinese_desc=_cell(row, 5),
                unit_state0_en=_cell(row, 6),
                unit_state1_en=_cell(row, 7),
                unit_state0_cn=_cell(row, 8),
                unit_state1_cn=_cell(row, 9),
                decimal_point=_cell(row, 10),
                default_value=_cell(row, 11),
            )
            rules.append(rule)
            rule_id += 1
    return rules


def _build_aliases(rules: list[NamingRule]) -> list[dict[str, Any]]:
    aliases: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()
    for rule in rules:
        for alias_type, alias in _rule_alias_values(rule):
            alias = str(alias or "").strip()
            if not alias:
                continue
            norm = normalize_name(alias)
            compact = compact_name(alias)
            if not compact:
                continue
            key = (rule.id, alias_type, compact)
            if key in seen:
                continue
            seen.add(key)
            aliases.append(
                {
                    "rule_id": rule.id,
                    "alias": alias,
                    "alias_type": alias_type,
                    "alias_norm": norm,
                    "alias_compact": compact,
                }
            )
    return aliases


def _rule_alias_values(rule: NamingRule) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = [
        ("object_name", rule.object_name),
        ("object_name_upper", normalize_name(rule.object_name)),
        ("chinese_desc", rule.chinese_desc),
    ]
    for struct in _split_structs(rule.struct_type):
        values.append(("struct_object", f"{struct}_{rule.object_name}"))
    values.extend(_state_phrase_aliases(rule))
    return values


def _state_phrase_aliases(rule: NamingRule) -> list[tuple[str, str]]:
    state0 = rule.unit_state0_cn
    state1 = rule.unit_state1_cn
    desc = rule.chinese_desc
    if not desc or not state0 or not state1 or "/" in {state0, state1}:
        return []
    base = desc
    if desc.endswith(state1):
        base = desc[: -len(state1)]
    elif desc.endswith(state0):
        base = desc[: -len(state0)]
    if not base:
        return []
    return [
        ("chinese_state_pair", f"{base}{state0}{state1}"),
        ("chinese_state_pair_slash", f"{base}{state0}/{state1}"),
        ("chinese_state_desc", f"{desc}状态"),
    ]


def _split_structs(struct_type: str) -> list[str]:
    if not struct_type or "[" in struct_type or struct_type in {"IO", "System", "Alarm", "Display", "Datetime"}:
        return []
    parts: list[str] = []
    for raw in re.split(r"[/、,，]", struct_type):
        part = raw.strip()
        if part and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", part):
            parts.append(part)
    return parts


def _find_alias_conflicts(aliases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_compact: dict[str, set[int]] = {}
    for alias in aliases:
        by_compact.setdefault(alias["alias_compact"], set()).add(int(alias["rule_id"]))
    conflicts = []
    for alias_compact, rule_ids in sorted(by_compact.items()):
        if len(rule_ids) > 1:
            conflicts.append({"alias_compact": alias_compact, "rule_ids": sorted(rule_ids)})
    return conflicts


def _write_sqlite(
    sqlite_path: Path,
    rules: list[NamingRule],
    aliases: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    meta: dict[str, Any],
) -> None:
    if sqlite_path.exists():
        sqlite_path.unlink()
    connection = sqlite3.connect(sqlite_path)
    try:
        connection.execute(
            """
            CREATE TABLE rules (
                id INTEGER PRIMARY KEY,
                sheet_name TEXT NOT NULL,
                source_row INTEGER NOT NULL,
                struct_type TEXT NOT NULL,
                data_type TEXT NOT NULL,
                object_name TEXT NOT NULL,
                object_name_norm TEXT NOT NULL,
                object_name_compact TEXT NOT NULL,
                rw TEXT NOT NULL,
                english_desc TEXT NOT NULL,
                chinese_desc TEXT NOT NULL,
                unit_state0_en TEXT NOT NULL,
                unit_state1_en TEXT NOT NULL,
                unit_state0_cn TEXT NOT NULL,
                unit_state1_cn TEXT NOT NULL,
                decimal_point TEXT NOT NULL,
                default_value TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id INTEGER NOT NULL,
                alias TEXT NOT NULL,
                alias_type TEXT NOT NULL,
                alias_norm TEXT NOT NULL,
                alias_compact TEXT NOT NULL,
                FOREIGN KEY(rule_id) REFERENCES rules(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE alias_conflicts (
                alias_compact TEXT NOT NULL,
                rule_ids_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE build_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        connection.executemany(
            """
            INSERT INTO rules VALUES (
                :id, :sheet_name, :source_row, :struct_type, :data_type,
                :object_name, :object_name_norm, :object_name_compact, :rw,
                :english_desc, :chinese_desc, :unit_state0_en, :unit_state1_en,
                :unit_state0_cn, :unit_state1_cn, :decimal_point, :default_value
            )
            """,
            [asdict(rule) for rule in rules],
        )
        connection.executemany(
            """
            INSERT INTO aliases (rule_id, alias, alias_type, alias_norm, alias_compact)
            VALUES (:rule_id, :alias, :alias_type, :alias_norm, :alias_compact)
            """,
            aliases,
        )
        connection.executemany(
            "INSERT INTO alias_conflicts VALUES (:alias_compact, :rule_ids_json)",
            [
                {
                    "alias_compact": conflict["alias_compact"],
                    "rule_ids_json": json.dumps(conflict["rule_ids"], ensure_ascii=False),
                }
                for conflict in conflicts
            ],
        )
        connection.executemany(
            "INSERT INTO build_meta VALUES (:key, :value)",
            [{"key": key, "value": json.dumps(value, ensure_ascii=False)} for key, value in meta.items()],
        )
        connection.execute("CREATE INDEX idx_rules_object_norm ON rules(object_name_norm)")
        connection.execute("CREATE INDEX idx_rules_object_compact ON rules(object_name_compact)")
        connection.execute("CREATE INDEX idx_alias_norm ON aliases(alias_norm)")
        connection.execute("CREATE INDEX idx_alias_compact ON aliases(alias_compact)")
        connection.commit()
    finally:
        connection.close()


def _write_json(
    json_path: Path,
    rules: list[NamingRule],
    aliases: list[dict[str, Any]],
    conflicts: list[dict[str, Any]],
    meta: dict[str, Any],
) -> None:
    payload = {
        "meta": meta,
        "rules": [asdict(rule) for rule in rules],
        "aliases": aliases,
        "alias_conflicts": conflicts,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _cell(row: list[Any], index: int) -> str:
    if index >= len(row) or row[index] is None:
        return ""
    return str(row[index]).strip()


def _sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()
