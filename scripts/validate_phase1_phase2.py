from __future__ import annotations

import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from midea_flowchart.validation import validate_programs


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    results = validate_programs(ROOT / "programs")
    payload = [asdict(result) for result in results]
    for item in payload:
        item["path"] = str(item["path"])
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    failed = [result for result in results if not result.ok]
    if failed:
        print("\n阶段一/二验收失败：", file=sys.stderr)
        for result in failed:
            print(f"- {result.path}: {'; '.join(result.errors)}", file=sys.stderr)
        return 1

    print("\n阶段一/二验收通过：所有样例均可解析并完成命名匹配。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
