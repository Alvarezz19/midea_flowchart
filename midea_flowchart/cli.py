from __future__ import annotations

import argparse
import json
from pathlib import Path

from .acceptance import build_acceptance_report
from .diagram_builder import build_diagrams_for_programs
from .flow_parser import parse_programs_dir, write_intermediate
from .naming_rules import compile_naming_rules


def main() -> None:
    parser = argparse.ArgumentParser(prog="midea-flowchart")
    subparsers = parser.add_subparsers(dest="command", required=True)

    compile_parser = subparsers.add_parser("compile-rules")
    compile_parser.add_argument("--excel", default="文档/1.命名规则v20191011B.XLSX")
    compile_parser.add_argument("--sqlite", default="data/naming_rules.sqlite")
    compile_parser.add_argument("--json", default="data/naming_rules.json")

    parse_parser = subparsers.add_parser("parse-programs")
    parse_parser.add_argument("--programs", default="programs")
    parse_parser.add_argument("--out", default="build/intermediate")

    acceptance_parser = subparsers.add_parser("accept")
    acceptance_parser.add_argument("--programs", default="programs")
    acceptance_parser.add_argument("--excel", default="文档/1.命名规则v20191011B.XLSX")
    acceptance_parser.add_argument("--data-dir", default="data")
    acceptance_parser.add_argument("--out", default="build")

    diagram_parser = subparsers.add_parser("build-diagrams")
    diagram_parser.add_argument("--programs", default="programs")
    diagram_parser.add_argument("--rules-json", default="data/naming_rules.json")
    diagram_parser.add_argument("--profiles", default="configs/domain_profiles")
    diagram_parser.add_argument("--out", default="build/diagrams")

    args = parser.parse_args()
    if args.command == "compile-rules":
        result = compile_naming_rules(args.excel, args.sqlite, args.json)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "parse-programs":
        parsed = parse_programs_dir(args.programs)
        output_dir = Path(args.out)
        paths = [str(write_intermediate(flow, output_dir)) for flow in parsed]
        print(json.dumps({"program_count": len(paths), "paths": paths}, ensure_ascii=False, indent=2))
    elif args.command == "accept":
        report = build_acceptance_report(args.programs, args.excel, args.data_dir, args.out)
        print(json.dumps(report["acceptance"], ensure_ascii=False, indent=2))
    elif args.command == "build-diagrams":
        report = build_diagrams_for_programs(args.programs, args.rules_json, args.profiles, args.out)
        print(json.dumps(report["acceptance"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
