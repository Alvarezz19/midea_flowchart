from __future__ import annotations

import unittest
from pathlib import Path

from midea_flowchart.abstraction import build_project_view
from midea_flowchart.naming import NamingMatcher, match_project_naming
from midea_flowchart.parser import load_project, load_project_from_text


ROOT = Path(__file__).resolve().parents[1]


class Phase3OverviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matcher = NamingMatcher(ROOT / "data/naming_rules.json")

    def _view(self, path: Path) -> dict:
        project = match_project_naming(load_project(path), self.matcher)
        return build_project_view(project)

    def test_sanshan_ahu_overview_contains_required_modules(self) -> None:
        view = self._view(ROOT / "programs/AHU程序/三山经开区/flows_20251210190941.json")
        roles = {node["role"] for node in view["overview"]["nodes"]}
        self.assertEqual(view["project"]["profile"], "ahu")
        self.assertIn("io_comm", roles)
        self.assertIn("control", roles)
        self.assertIn("schedule", roles)
        self.assertIn("dx_status", roles)
        relations = {(edge["source"], edge["target"]) for edge in view["overview"]["edges"]}
        node_by_role = {node["role"]: node["id"] for node in view["overview"]["nodes"]}
        self.assertIn((node_by_role["io_comm"], node_by_role["control"]), relations)
        self.assertIn((node_by_role["schedule"], node_by_role["control"]), relations)
        self.assertIn((node_by_role["dx_status"], node_by_role["control"]), relations)

    def test_all_ahu_samples_build_overview(self) -> None:
        paths = sorted((ROOT / "programs/AHU程序").rglob("*.json"))
        self.assertEqual(len(paths), 3)
        for path in paths:
            with self.subTest(path=path):
                view = self._view(path)
                roles = {node["role"] for node in view["overview"]["nodes"]}
                self.assertEqual(view["project"]["profile"], "ahu")
                self.assertIn("io_comm", roles)
                self.assertIn("control", roles)
                self.assertIn("schedule", roles)
                self.assertIn("dx_status", roles)
                self.assertGreaterEqual(len(view["overview"]["nodes"]), 4)
                self.assertGreater(len(view["namingIssues"]), 0)

    def test_extra_ahu_tabs_are_visible(self) -> None:
        view = self._view(ROOT / "programs/AHU程序/泰安宁阳中医院/flows_20260206160555.json")
        roles = {node["role"] for node in view["overview"]["nodes"]}
        self.assertIn("exhaust_fan", roles)
        self.assertIn("dx_fault", roles)

    def test_non_ahu_samples_degrade_to_generic_overview(self) -> None:
        paths = sorted((ROOT / "programs/机房群控程序").rglob("*.json"))
        self.assertEqual(len(paths), 2)
        for path in paths:
            with self.subTest(path=path):
                view = self._view(path)
                self.assertGreater(len(view["overview"]["nodes"]), 0)
                self.assertEqual(len(view["tabs"]), view["project"]["tabCount"])
                self.assertIn(view["project"]["profile"], {"chiller_plant", "air_source_heat_pump"})


class Phase4InteractionDataTests(unittest.TestCase):
    def test_uploaded_text_uses_same_project_view_shape(self) -> None:
        path = ROOT / "programs/AHU程序/三山经开区/flows_20251210190941.json"
        content = path.read_text(encoding="utf-8")
        matcher = NamingMatcher(ROOT / "data/naming_rules.json")
        project = match_project_naming(load_project_from_text(content, "uploaded.json"), matcher)
        view = build_project_view(project)
        self.assertEqual(view["project"]["sourcePath"], "uploaded.json")
        self.assertIn("overview", view)
        self.assertIn("rawGraph", view)
        self.assertTrue(view["rawGraph"]["nodes"])
        self.assertTrue(view["tabs"][0]["rawNodes"])


if __name__ == "__main__":
    unittest.main()
