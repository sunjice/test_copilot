"""TestLink Mock 服务器。

用于模拟 TestLink 的 XML-RPC 接口和 Web API 接口，方便在无真实 TestLink
环境的情况下进行接入适配和联调。

模拟的接口：
  1. XML-RPC 方法 get_case_detail — 获取用例详情
     对应示例: gw.get_case_detail(["C-2185677"])
  2. Web API /get_tree_nodes — 获取指定节点下一层子节点
     对应示例: gw.get_tree_nodes(node_id=..., tcase_prefix=..., root_node=...)

使用方式：
    python mock_testlink_server.py [--host 127.0.0.1] [--port 8088]

说明：
  - XML-RPC 端点位于 /xmlrpc（通过 HTTP POST 的 XML 请求体调用）。
  - Web API 端点位于 /get_tree_nodes（GET 请求）。
  - 数据默认从同目录下的 mock_data.py 加载，可自行修改。
"""

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from xmlrpc.server import SimpleXMLRPCDispatcher
from urllib.parse import parse_qs, urlparse

try:
    from .mock_data import TREE_NODES, SUITE_NODES, CASE_DETAILS
except ImportError:  # 直接以脚本方式运行时回退
    from mock_data import TREE_NODES, SUITE_NODES, CASE_DETAILS


# ═══════════════ XML-RPC 部分 ═══════════════

dispatcher = SimpleXMLRPCDispatcher(allow_none=True, encoding=None)


@dispatcher.register_function
def get_case_detail(case_ids):
    """模拟 TestLink 的 get_case_detail。

    参数:
        case_ids: list[str]  例如 ["C-2185677"]

    返回:
        dict[str, dict]  形如 {"C2185677": {...}}
    """
    result = {}
    for cid in case_ids:
        # 兼容带横杠与不带横杠的写法
        key = str(cid).replace("-", "")
        detail = CASE_DETAILS.get(key) or CASE_DETAILS.get(str(cid))
        if detail is not None:
            result[key] = detail
    return result


# 常用别名：testlink 的 XML-RPC 方法名习惯用小写
dispatcher.register_function(get_case_detail, "getCaseDetail")


# ═══════════════ 数据工具 ═══════════════

def _build_tree_response(node_id, tcase_prefix, root_node):
    """构建 get_tree_nodes 的返回数据。

    根据 node_id / root_node 判断返回层级：
      - node_id 指向某个 test_suite（或在 SUITE_NODES 中）→ 返回该套件下的 test_case 列表
      - 否则（顶层目录）→ 返回 test_suite 列表
    """
    # 若 node_id 是某个套件，返回其下的用例
    suite_ids = {s["node_id"] for s in SUITE_NODES}
    if node_id in suite_ids:
        return [dict(n) for n in TREE_NODES]
    # 顶层目录：返回套件列表
    return [dict(s) for s in SUITE_NODES]


# ═══════════════ HTTP 处理器 ═══════════════

class MockTestLinkHandler(BaseHTTPRequestHandler):
    """统一处理 XML-RPC 与 Web API 请求。"""

    server_version = "MockTestLink/1.0"

    def _send_json(self, status, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_xmlrpc(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        response = dispatcher._marshaled_dispatch(body)
        self.send_response(200)
        self.send_header("Content-Type", "text/xml; charset=utf-8")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def _handle_get_tree_nodes(self):
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        node_id = qs.get("node_id", [None])[0]
        tcase_prefix = qs.get("tcase_prefix", [None])[0]
        root_node = qs.get("root_node", [None])[0]

        nodes = _build_tree_response(node_id, tcase_prefix, root_node)
        self._send_json(200, nodes)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/get_tree_nodes":
            self._handle_get_tree_nodes()
        elif path == "/" or path == "/health":
            self._send_json(200, {"status": "ok", "service": "mock-testlink"})
        else:
            self._send_json(404, {"error": f"unknown path: {path}"})

    def do_POST(self):
        path = urlparse(self.path).path
        if path in ("/xmlrpc", "/RPC2", "/api/xmlrpc"):
            self._handle_xmlrpc()
        else:
            self._send_json(404, {"error": f"unknown path: {path}"})

    def log_message(self, format, *args):
        # 精简日志
        print(f"[mock-testlink] {self.address_string()} - {format % args}")


def main():
    parser = argparse.ArgumentParser(description="TestLink Mock Server")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    parser.add_argument("--port", type=int, default=8088, help="监听端口")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), MockTestLinkHandler)
    print(f"Mock TestLink server running at http://{args.host}:{args.port}")
    print(f"  XML-RPC : http://{args.host}:{args.port}/xmlrpc")
    print(f"  Web API : http://{args.host}:{args.port}/get_tree_nodes")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBye")
        server.shutdown()


if __name__ == "__main__":
    main()
