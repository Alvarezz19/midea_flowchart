from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from .abstraction import build_project_view
from .naming import NamingMatcher, match_project_naming
from .parser import load_project, load_project_from_text

ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = ROOT / "web"
PROGRAMS_DIR = ROOT / "programs"


class FlowchartRequestHandler(BaseHTTPRequestHandler):
    matcher = NamingMatcher(ROOT / "data/naming_rules.json")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/samples":
            self._send_json(_sample_index())
            return
        if parsed.path == "/api/analyze":
            query = parse_qs(parsed.query)
            sample = query.get("sample", [""])[0]
            try:
                path = _sample_path(sample)
                self._send_json(_analyze_path(path, self.matcher))
            except ValueError as exc:
                self._send_error(str(exc), HTTPStatus.BAD_REQUEST)
            return
        self._send_static(parsed.path)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path != "/api/analyze":
            self._send_error("未知接口", HTTPStatus.NOT_FOUND)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
            content = str(payload["content"])
            filename = str(payload.get("filename") or "<uploaded>")
            project = match_project_naming(load_project_from_text(content, filename), self.matcher)
            self._send_json(build_project_view(project))
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self._send_error(str(exc), HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args) -> None:
        return

    def _send_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(self, message: str, status: HTTPStatus) -> None:
        self._send_json({"error": message}, status)

    def _send_static(self, request_path: str) -> None:
        path_text = unquote(request_path).lstrip("/") or "index.html"
        path = (WEB_DIR / path_text).resolve()
        if WEB_DIR.resolve() not in path.parents and path != WEB_DIR.resolve():
            self._send_error("非法路径", HTTPStatus.BAD_REQUEST)
            return
        if not path.is_file():
            self._send_error("文件不存在", HTTPStatus.NOT_FOUND)
            return
        data = path.read_bytes()
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type in {"application/javascript"}:
            content_type += "; charset=utf-8"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _sample_index() -> list[dict[str, str]]:
    samples = []
    for path in sorted(PROGRAMS_DIR.rglob("*.json")):
        sample_id = path.relative_to(PROGRAMS_DIR).as_posix()
        samples.append({"id": sample_id, "label": sample_id})
    return samples


def _sample_path(sample: str) -> Path:
    if not sample:
        raise ValueError("缺少 sample 参数")
    path = (PROGRAMS_DIR / sample).resolve()
    if PROGRAMS_DIR.resolve() not in path.parents:
        raise ValueError("示例路径超出 programs 目录")
    if not path.is_file():
        raise ValueError("示例文件不存在")
    return path


def _analyze_path(path: Path, matcher: NamingMatcher) -> dict[str, object]:
    project = match_project_naming(load_project(path), matcher)
    return build_project_view(project)


def main() -> None:
    parser = argparse.ArgumentParser(description="启动流程图交互前端")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), FlowchartRequestHandler)
    print(f"流程图前端已启动：http://{args.host}:{args.port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
