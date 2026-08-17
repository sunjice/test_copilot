# TestLink Mock 使用说明

本目录用于模拟 TestLink 的接口，方便在无真实 TestLink 环境下进行接入适配和联调。

## 文件说明

| 文件 | 作用 |
|------|------|
| `mock_testlink_server.py` | Mock 服务器（仅用 Python 标准库，无第三方依赖），同时模拟 XML-RPC 与 Web API 两个端点 |
| `mock_data.py` | Mock 数据，与 `testlink.txt` 中记录的接口返回示例保持一致 |
| `test_mock_client.py` | 客户端验证脚本，用真实接入方式调用 Mock 接口进行校验 |
| `testlink.txt` | 真实 TestLink 接口调用方式与返回示例（参考来源） |

## 模拟的接口

TestLink 采用两种接入方式：

### 1. get_case_detail（XML-RPC）

- 端点：`POST /xmlrpc`（兼容 `/RPC2`、`/api/xmlrpc`）
- 参数：用例 ID 列表，如 `["C-2185677"]`
- 返回：`{用例ID: 详情}` 字典，详情含 `item_a`、`idea_a`、`summary`、`condition_a`、`steps`（HTML 表格）、`expected_results` 等字段
- 用例 ID 兼容带横杠 `C-2185677` 与不带横杠 `C2185677` 两种写法

### 2. get_tree_nodes（Web API）

- 端点：`GET /get_tree_nodes`
- 参数：`node_id`、`tcase_prefix`、`root_node`
- 返回：该节点下一层子节点列表，每个节点含 `node_id`、`type`、`name`、`case_id`、`case_count` 字段

## 快速开始

### 1. 启动 Mock 服务器

```bash
python mock_testlink_server.py --host 127.0.0.1 --port 8088
```

默认监听 `127.0.0.1:8088`，启动后可访问：

- XML-RPC：`http://127.0.0.1:8088/xmlrpc`
- Web API：`http://127.0.0.1:8088/get_tree_nodes`
- 健康检查：`http://127.0.0.1:8088/health`

### 2. 验证 Mock 接口

```bash
python test_mock_client.py --base-url http://127.0.0.1:8088
```

## 客户端接入示例

```python
import xmlrpc.client
import urllib.request
import json

base_url = "http://127.0.0.1:8088"

# XML-RPC 调用 get_case_detail
proxy = xmlrpc.client.ServerProxy(f"{base_url}/xmlrpc")
case_detail = proxy.get_case_detail(["C-2185677"])

# HTTP GET 调用 get_tree_nodes
url = f"{base_url}/get_tree_nodes?node_id=12345&tcase_prefix=TP-&root_node=root"
with urllib.request.urlopen(url) as resp:
    tree_nodes = json.loads(resp.read().decode("utf-8"))
```

## 自定义 Mock 数据

修改 `mock_data.py` 即可调整返回内容：

- `CASE_DETAILS`：`get_case_detail` 的返回数据（key 为不带横杠的用例 ID）
- `TREE_NODES`：`get_tree_nodes` 的返回数据

## 扩展其他接口

如需补充 TestLink 的其他接口（如 `createTestCase`、`getTestSuitesForTestPlan` 等），
在 `mock_testlink_server.py` 中按以下方式添加即可：

- XML-RPC 接口：新增函数并用 `@dispatcher.register_function` 注册
- Web API 接口：在 `MockTestLinkHandler` 中新增对应的 `do_GET`/`do_POST` 处理逻辑
