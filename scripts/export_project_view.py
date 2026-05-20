from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from midea_flowchart.abstraction import build_project_view
from midea_flowchart.naming import NamingMatcher, match_project_naming
from midea_flowchart.parser import load_project


def main() -> None:
    parser = argparse.ArgumentParser(description="导出流程图中间视图 JSON")
    parser.add_argument("input", type=Path, help="美的编程平台导出的 JSON 文件")
    parser.add_argument("-o", "--output", type=Path, help="输出文件；不提供时输出到标准输出")
    args = parser.parse_args()

    matcher = NamingMatcher()
    project = match_project_naming(load_project(args.input), matcher)
    payload = build_project_view(project)
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)


if __name__ == "__main__":
    main()
