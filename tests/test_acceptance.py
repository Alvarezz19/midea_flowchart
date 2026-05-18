from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile
import unittest

from midea_flowchart.acceptance import build_acceptance_report
from midea_flowchart.diagram_builder import build_diagrams_for_programs
from midea_flowchart.flow_parser import parse_programs_dir
from midea_flowchart.naming_rules import NamingRuleIndex, compile_naming_rules


ROOT = Path(__file__).resolve().parents[1]
PROGRAMS = ROOT / "programs"
RULES = ROOT / "文档" / "1.命名规则v20191011B.XLSX"


class FlowParserTests(unittest.TestCase):
    def test_all_programs_parse_to_common_model(self) -> None:
        flows = parse_programs_dir(PROGRAMS)
        self.assertEqual(len(flows), 5)
        for flow in flows:
            self.assertGreater(flow.object_count, 0)
            self.assertGreater(len(flow.tabs), 0)
            self.assertGreater(len(flow.edges), 0)
            self.assertGreater(len(flow.points), 0)
            unresolved_quotes = [quote for quote in flow.quotes if not quote.resolved]
            self.assertEqual(unresolved_quotes, [])


class NamingRuleTests(unittest.TestCase):
    def test_compile_rules_creates_sqlite_and_json_index(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            sqlite_path = temp / "naming_rules.sqlite"
            json_path = temp / "naming_rules.json"
            result = compile_naming_rules(RULES, sqlite_path, json_path)
            self.assertGreater(result["rule_count"], 100)
            self.assertGreater(result["alias_count"], result["rule_count"])
            self.assertTrue(sqlite_path.exists())
            self.assertTrue(json_path.exists())

            index = NamingRuleIndex(json_path)
            self.assertIsNotNone(index.match("SF_RUN"))
            self.assertIsNotNone(index.match("SF_Frq_MC"))
            self.assertIsNotNone(index.match("送风机运行状态"))

            connection = sqlite3.connect(sqlite_path)
            try:
                indexes = {
                    row[1]
                    for row in connection.execute(
                        "SELECT type, name FROM sqlite_master WHERE type='index'"
                    )
                }
            finally:
                connection.close()
            self.assertIn("idx_alias_compact", indexes)
            self.assertIn("idx_rules_object_compact", indexes)


class AcceptanceReportTests(unittest.TestCase):
    def test_acceptance_report_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            report = build_acceptance_report(
                programs_root=PROGRAMS,
                excel_path=RULES,
                data_dir=temp / "data",
                output_dir=temp / "build",
            )
            self.assertTrue(report["acceptance"]["passed"], report["acceptance"]["failures"])
            self.assertEqual(report["program_count"], 5)


class DiagramBuilderTests(unittest.TestCase):
    def test_diagram_builder_generates_bounded_traceable_modules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp = Path(temp_dir)
            compile_naming_rules(
                RULES,
                temp / "data" / "naming_rules.sqlite",
                temp / "data" / "naming_rules.json",
            )
            report = build_diagrams_for_programs(
                programs_root=PROGRAMS,
                naming_index_path=temp / "data" / "naming_rules.json",
                profiles_dir=ROOT / "configs" / "domain_profiles",
                output_dir=temp / "build" / "diagrams",
            )
            self.assertTrue(report["acceptance"]["passed"], report["acceptance"]["failures"])
            self.assertEqual(report["project_count"], 5)
            diagram_paths = list((temp / "build" / "diagrams").glob("*.json"))
            self.assertEqual(len(diagram_paths), 5)

            for project in report["projects"]:
                self.assertGreater(project["overview_modules"], 0)
                for page in project["pages"]:
                    if page["source_node_count"]:
                        self.assertGreaterEqual(page["module_count"], 1)
                        self.assertLessEqual(page["module_count"], 20)


if __name__ == "__main__":
    unittest.main()
