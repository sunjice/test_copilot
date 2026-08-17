"""Mock TestLink 客户端验证脚本。

模拟真实 TestLink 接入方式（XML-RPC 调用 get_case_detail、
HTTP GET 调用 get_tree_nodes），用于验证 Mock 服务器返回格式正确。

运行前需先启动 Mock 服务器：
    python mock_testlink_server.py

然后运行：
    python test_mock_client.py [--base-url http://127.0.0.1:8088]
"""

import argparse
import json
import urllib.request
import xmlrpc.client


def test_get_case_detail(base_url):
    """XML-RPC 调用 get_case_detail。"""
    proxy = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc")
    result = proxy.get_case_detail(["C-2185677"])
    print("==== get_case_detail 返回 ====")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def test_get_tree_nodes(base_url):
    """HTTP GET 调用 get_tree_nodes。"""
    url = (
        f"{base_url}/get_tree_nodes"
        "?node_id=12345&tcase_prefix=TP-&root_node=root"
    )
    with urllib.request.urlopen(url) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    print("==== get_tree_nodes 返回 ====")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return data


def main():
    parser = argparse.ArgumentParser(description="Mock TestLink 客户端验证")
    parser.add_argument("--base-url", default="http://127.0.0.1:8088", help="Mock 服务器地址")
    args = parser.parse_args()

    test_get_case_detail(args.base_url)
    print()
    test_get_tree_nodes(args.base_url)


if __name__ == "__main__":
    main()
