from __future__ import annotations

import json
import tempfile
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


class Phase5DetailGraphTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.matcher = NamingMatcher(ROOT / "data/naming_rules.json")
        project = match_project_naming(load_project(ROOT / "programs/AHU程序/三山经开区/flows_20251210190941.json"), cls.matcher)
        cls.view = build_project_view(project)

    def _tab(self, role: str) -> dict:
        return next(tab for tab in self.view["tabs"] if tab["role"] == role)

    def test_control_tab_uses_aggregated_module_graph(self) -> None:
        tab = self._tab("control")
        graph = tab["detailGraph"]
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertEqual(graph["level"], "L2")
        self.assertEqual(graph["layout"], "module_flow")
        self.assertIn("system", node_ids)
        self.assertIn("fan_start", node_ids)
        self.assertIn("temperature", node_ids)
        self.assertIn("valve", node_ids)
        self.assertLess(len(graph["nodes"]), 20)
        self.assertGreater(len(graph["edges"]), 0)

    def test_io_comm_tab_uses_signal_boundary_graph(self) -> None:
        tab = self._tab("io_comm")
        graph = tab["detailGraph"]
        node_ids = {node["id"] for node in graph["nodes"]}
        self.assertEqual(graph["layout"], "signal_flow")
        self.assertIn("field_input", node_ids)
        self.assertIn("comm_input", node_ids)
        self.assertIn("internal", node_ids)
        self.assertIn("physical_output", node_ids)
        self.assertIn("comm_output", node_ids)

    def test_schedule_tab_uses_compact_logic_graph(self) -> None:
        tab = self._tab("schedule")
        graph = tab["detailGraph"]
        self.assertEqual(graph["layout"], "compact_logic")
        self.assertEqual([node["id"] for node in graph["nodes"]], ["timer_input", "timer_logic", "timer_output"])
        self.assertIn("TIME_CST", graph["note"])

    def test_dx_status_tab_has_matrix(self) -> None:
        tab = self._tab("dx_status")
        self.assertEqual(tab["detailGraph"]["layout"], "mapping_matrix")
        matrix = tab["statusMatrix"]
        self.assertIsNotNone(matrix)
        self.assertGreaterEqual(matrix["columnCount"], 4)
        self.assertGreaterEqual(matrix["rowCount"], 10)
        row_names = {row["metric"] for row in matrix["rows"]}
        self.assertIn("软件版本", row_names)
        self.assertIn("冷凝压力", row_names)

    def test_ahu_detail_edges_use_curated_business_links(self) -> None:
        control = self._tab("control")
        self.assertLessEqual(len(control["detailGraph"]["edges"]), 12)
        self.assertTrue(all(edge["relationType"] == "profile_rule" for edge in control["detailGraph"]["edges"]))
        for edge in control["detailGraph"]["edges"]:
            self.assertIn("directSupportCount", edge)
            self.assertIn("reverseSupportCount", edge)
            self.assertIn(edge["supportDirection"], {"direct", "reverse", "mixed", "none"})
            self.assertEqual(edge["supportCount"], edge["directSupportCount"] + edge["reverseSupportCount"])
        self.assertIn("supportEdges", control["detailGraph"])
        self.assertGreater(len(control["detailGraph"]["supportEdges"]), len(control["detailGraph"]["edges"]))

        dx_status = self._tab("dx_status")
        self.assertEqual(
            [(edge["source"], edge["target"]) for edge in dx_status["detailGraph"]["edges"]],
            [("dx_register", "dx_convert"), ("dx_convert", "dx_standard")],
        )

    def test_all_samples_have_detail_graph_and_raw_trace(self) -> None:
        matcher = NamingMatcher(ROOT / "data/naming_rules.json")
        for path in sorted((ROOT / "programs").rglob("*.json")):
            with self.subTest(path=path):
                view = build_project_view(match_project_naming(load_project(path), matcher))
                for tab in view["tabs"]:
                    self.assertIn("detailGraph", tab)
                    self.assertIn("rawTrace", tab)
                    self.assertIn("nodes", tab["detailGraph"])
                    self.assertIn("edges", tab["detailGraph"])
                    self.assertIn("supportEdges", tab["detailGraph"])

    def test_ahu_declarative_graph_rules_come_from_profile(self) -> None:
        profile = json.loads((ROOT / "configs/domain_profiles/ahu.json").read_text(encoding="utf-8"))
        profile["overview"]["role_meta"] = {"io_comm": {"label": "现场输入配置"}}
        profile["overview"]["edges"][0]["label"] = "自定义总览链路"
        profile["detail"]["module_meta"] = {"field_input": {"label": "现场采集"}}
        profile["detail"]["profile_edges"]["io_comm"] = [["field_input", "internal"]]

        with tempfile.TemporaryDirectory() as tmp:
            profile_path = Path(tmp) / "ahu.json"
            profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
            project = match_project_naming(
                load_project(ROOT / "programs/AHU程序/三山经开区/flows_20251210190941.json", profiles_dir=tmp),
                self.matcher,
            )
            view = build_project_view(project)

        io_node = next(node for node in view["overview"]["nodes"] if node["role"] == "io_comm")
        io_tab = next(tab for tab in view["tabs"] if tab["role"] == "io_comm")
        self.assertEqual(io_node["label"], "现场输入配置")
        self.assertIn("自定义总览链路", {edge["label"] for edge in view["overview"]["edges"]})
        self.assertEqual(next(node for node in io_tab["detailGraph"]["nodes"] if node["id"] == "field_input")["label"], "现场采集")
        self.assertEqual([(edge["source"], edge["target"]) for edge in io_tab["detailGraph"]["edges"]], [("field_input", "internal")])


if __name__ == "__main__":
    unittest.main()
