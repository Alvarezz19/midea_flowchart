from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from midea_flowchart.naming import NamingMatcher, compact_name, match_project_naming, normalize_name
from midea_flowchart.parser import load_project
from midea_flowchart.validation import validate_programs


ROOT = Path(__file__).resolve().parents[1]


class ParserTests(unittest.TestCase):
    def test_loads_all_sample_programs(self) -> None:
        results = validate_programs(ROOT / "programs")
        self.assertEqual(len(results), 5)
        failed = [result for result in results if not result.ok]
        self.assertEqual(failed, [])

    def test_ahu_sample_counts_and_profile(self) -> None:
        project = load_project(ROOT / "programs/AHU程序/三山经开区/flows_20251210190941.json")
        self.assertEqual(project.raw_count, 913)
        self.assertEqual(len(project.tabs), 4)
        self.assertEqual(len(project.subflows), 5)
        self.assertEqual(len(project.nodes), 904)
        self.assertGreater(len(project.edges), 0)
        self.assertEqual(project.profile_name, "ahu")
        roles = {tab.role for tab in project.tabs.values()}
        self.assertIn("io_comm", roles)
        self.assertIn("control", roles)
        self.assertIn("schedule", roles)
        self.assertIn("dx_status", roles)

    def test_wire_direction_uses_current_node_as_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "tab1", "type": "tab", "label": "控制"},
                        {"id": "a", "type": "swInput", "z": "tab1", "name": "CH_RUN", "outputs": 1, "wires": []},
                        {
                            "id": "b",
                            "type": "logic",
                            "z": "tab1",
                            "name": "与",
                            "inputs": 1,
                            "outputs": 1,
                            "wires": [[{"id": "a", "port": 0}]],
                        },
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            project = load_project(path)
        self.assertEqual(len(project.edges), 1)
        self.assertEqual(project.edges[0].source_node_id, "a")
        self.assertEqual(project.edges[0].target_node_id, "b")
        self.assertEqual(project.edges[0].target_port, 0)


class NamingTests(unittest.TestCase):
    def test_name_normalization(self) -> None:
        self.assertEqual(normalize_name(" ch_run "), "CH_RUN")
        self.assertEqual(compact_name("[AV-1] CH_RUN"), "AV1CHRUN")

    def test_matches_known_rule(self) -> None:
        matcher = NamingMatcher(ROOT / "data/naming_rules.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "tab1", "type": "tab", "label": "控制"},
                        {"id": "a", "type": "swInput", "z": "tab1", "name": "CH_CSP", "outputs": 1, "wires": []},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            project = match_project_naming(load_project(path), matcher)
        point = project.points["a"]
        self.assertEqual(point.naming_status, "matched")
        self.assertEqual(point.matched_rule_ids, [5])

    def test_ignores_generic_variable_without_other_name(self) -> None:
        matcher = NamingMatcher(ROOT / "data/naming_rules.json")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "mini.json"
            path.write_text(
                json.dumps(
                    [
                        {"id": "tab1", "type": "tab", "label": "控制"},
                        {"id": "a", "type": "swInput", "z": "tab1", "name": "变量", "outputs": 1, "wires": []},
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            project = match_project_naming(load_project(path), matcher)
        self.assertEqual(project.points["a"].naming_status, "ignored")


if __name__ == "__main__":
    unittest.main()
