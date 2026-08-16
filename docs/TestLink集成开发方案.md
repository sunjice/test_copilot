# TestLink 集成开发方案

> 创建日期：2026-08-16
> 状态：方案评审稿（待确认后进入实施）
> 前置文档：`docs/用例testlink适配.md`（已完成第一部分：用例域字段改造）
> 依赖：`docs/开发指导手册.md`

---

## 一、背景与目标

本系统（测试部 AI 助手）需要接入公司内部 TestLink 系统，将 TestLink 中的测试用例拉取到本地 `ai_tc_cases` 表，作为 AI 审核、补全、脚本生成等能力的数据基础；同时把 AI 审核/完善后的结果反写回 TestLink，保持两端数据一致。

**核心难点**：内部 TestLink 返回的用例数据（测试思想、前置条件、测试步骤、预期结果等）是 **HTML 富文本格式**，无法直接存入现有结构化字段，也无法直接喂给向量化/ES/AI。

**目标**：建立「原文存库 + 清洗入字段 + 向量化用精简字段 + ES 用去 HTML 文本 + 前端渲染富文本 + 反写按字段增量」的分层数据策略，并实现全量/增量同步、独立 worker 异步索引、按字段反写的完整闭环。

---

## 二、整体架构

```
                          ┌─────────────────────────────┐
                          │       内部 TestLink           │
                          │  (XML-RPC / REST 双协议)      │
                          └──────────────┬──────────────┘
                                         │ 拉取(全量/增量) / 反写
                                         ▼
                    ┌────────────────────────────────────────┐
                    │  TestLink Client 抽象层 (app/aitc/testlink) │
                    │   client.py / xmlrpc_client / rest_client   │
                    │   field_map.py / hashing.py                 │
                    └──────────────┬─────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────────┐
              │ 同步服务 (sync_service)                       │ 反写服务 (push_service)
              ▼                                              ▼
   ┌──────────────────────┐                    ┌──────────────────────────┐
   │  1. 原文 HTML 存 *_raw  │                    │  按字段增量反写 TestLink    │
   │  2. 清洗入结构化字段      │                    │  纯文本→HTML(可逆格式)      │
   │  3. 步骤结构化解析(降级)  │                    │  反写后立即回拉校验         │
   └──────────┬───────────┘                    └──────────────────────────┘
              │ 写入 PG (ai_tc_cases)
              ▼
   ┌──────────────────────────────────────────────────────────────┐
   │                    PostgreSQL (ai_tc_cases)                    │
   │  *_raw(原文HTML) + 清洗字段 + testlink身份映射 + sync状态机      │
   └──────────────┬───────────────────────────────┬───────────────┘
                  │ 投递待索引任务                    │
                  ▼                                ▼
   ┌──────────────────────────┐      ┌──────────────────────────────┐
   │  独立常驻 Worker (独立进程) │      │  前端 (vue3-element-admin)      │
   │  批量向量化 + ES + Milvus  │      │  详情页渲染 *_raw 富文本        │
   └──────────┬───────────────┘      │  审核/补全用清洗后纯文本         │
              │                      └──────────────────────────────┘
              ▼
   ┌──────────────────────────────────────────────┐
   │  Milvus(向量) + Elasticsearch(BM25) 混合检索    │
   └──────────────────────────────────────────────┘
```

---

## 三、数据模型变更

### 3.1 现有字段盘点（`app/aitc/case/models.py::AiTcCase`）

已有字段按用途分四类：

| 类别 | 字段 | 说明 |
|---|---|---|
| 内容字段 | `external_id`/`name`/`purpose`/`summary`/`preconditions`/`topo`/`test_data`/`steps`/`importance` | 现有结构化字段 |
| TestLink 身份映射 | `testlink_tc_id`/`testlink_version_id` | 已建（第一部分） |
| 同步状态与控制 | `sync_status`(0-6)/`synced_version`/`synced_hash`/`synced_snapshot`/`last_sync_at`/`last_push_at`/`testlink_modified_at`/`testlink_modifier`/`auto_sync`/`sync_error` | 已建（第一部分） |
| 检索引擎追踪 | `index_hash`/`indexed_at` | 已建 |
| AI 业务字段 | `is_core`/`core_reason`/`core_source`/`is_sample`/`review_status`/`script_count` | 不参与同步 |

### 3.2 新增字段（本次建列）

新增 HTML 原文字段（`Text` 类型），存 TestLink 原始富文本：

| 字段 | 类型 | 说明 |
|---|---|---|
| `summary_raw` | Text | 测试思想的原始 HTML |
| `preconditions_raw` | Text | 前置条件的原始 HTML |
| `steps_raw` | Text | 测试步骤的原始 HTML（整段） |
| `test_data_raw` | Text | 测试数据的原始 HTML |
| `steps_parse_status` | SmallInt | 步骤结构化解析状态：0-未解析 1-解析成功 2-解析降级为纯文本（默认 0） |

> 说明：`name`/`purpose` 通常为纯文本，TestLink 中一般不包含 HTML，是否额外存 `name_raw`/`purpose_raw` 在阶段 0 连通验证后视实际数据决定。若确认含 HTML，则同样补 `name_raw`/`purpose_raw`。

### 3.3 字段「双轨」关系（核心设计）

```
TestLink HTML 原文 ──▶ *_raw 字段（原文，前端渲染/回溯/反写对齐用）
                          │
                          │ 同步时清洗（strip_html / 步骤结构化解析）
                          ▼
                  清洗字段（summary/preconditions/steps 等，AI/向量化/ES 用）
```

**决策（已确认）**：采用「同步时就清洗好写入」方案。

- `summary` / `preconditions` / `test_data` → 去 HTML 后的**纯文本**，同步时直接写入。
- `steps` → 从 HTML **结构化解析**为 `[{step_no, action, expected}]`（JSONB），每个 cell 内部去 HTML。
- `*_raw` 始终保留原始 HTML。

**好处**：AI tools 无需大改（继续读清洗字段）；向量化/ES 直接用清洗字段；前端详情页用 `*_raw` 富文本，可读性不受损。

### 3.4 Alembic 迁移

新增迁移脚本（对齐现有 `alembic/versions/` 双轨：Alembic + SQL 脚本 `sql/postgresql/youlai-aitc.sql` 同步更新）：

- `ai_tc_cases` 加 `summary_raw`/`preconditions_raw`/`steps_raw`/`test_data_raw`/`steps_parse_status` 5 列。

---

## 四、TestLink Client 抽象层

新建 `app/aitc/testlink/` 包（对齐 `docs/用例testlink适配.md` 第二部分的规划），采用 provider 注册表模式（与现有 embedding provider 一致）。

### 4.1 目录结构

```
app/aitc/testlink/
├── __init__.py
├── base.py           # TestLinkClient 抽象基类 + 工厂 get_testlink_client()
├── xmlrpc_client.py  # 标准 XML-RPC 实现（testlink.getTestCasesForTestSuite 等，devKey 认证）
├── rest_client.py    # 内部 REST/HTTP 实现
├── field_map.py      # 字段映射：TestLink 字段 ↔ *_raw 字段 ↔ 清洗字段
├── hashing.py        # canonical 序列化 + SHA256（复用 synced_hash 语义）
├── parser.py         # HTML 清洗 + 步骤结构化解析器（核心，见 §六）
├── models.py         # ai_tc_sync_logs 审计表 + 同步相关 Pydantic 模型
├── sync_service.py   # 全量/增量拉取、清洗、写 PG
├── push_service.py   # 按字段反写、回拉校验
├── monitor.py        # 增量监控定时任务（每日）
└── router.py         # 同步/反写/冲突处理的 HTTP 接口
```

### 4.2 抽象基类接口

```python
class TestLinkClient(ABC):
    # ── 拉取 ──
    @abstractmethod
    async def get_projects(self) -> list[dict]: ...
    @abstractmethod
    async def get_test_suites(self, project_id: int) -> list[dict]: ...      # 套件树
    @abstractmethod
    async def get_cases_by_suite(self, suite_id: int) -> list[dict]: ...     # 套件下用例
    @abstractmethod
    async def get_case(self, testcase_id: int, version_id: int) -> dict: ... # 单条用例（含 HTML 字段）
    @abstractmethod
    async def get_changed_cases(self, since: datetime) -> list[dict]: ...    # 增量：按修改时间

    # ── 反写 ──
    @abstractmethod
    async def update_case_field(self, testcase_id: int, version_id: int,
                                field: str, value_html: str) -> dict: ...   # 单字段反写（返回新 version）

    # ── 元信息 ──
    @abstractmethod
    async def verify_connection(self) -> bool: ...
```

### 4.3 协议切换

配置项（`app/config.py` + `.env`）：

```python
TESTLINK_PROTOCOL: str = "xmlrpc"   # xmlrpc | rest
TESTLINK_URL: str = ""
TESTLINK_DEVKEY: str = ""           # xmlrpc 认证
TESTLINK_REST_BASE_URL: str = ""    # rest 用
TESTLINK_REST_TOKEN: str = ""
```

`get_testlink_client()` 工厂按 `TESTLINK_PROTOCOL` 返回对应实现（懒加载单例，参考 `retrieval/common/client.py`）。

---

## 五、可逆 text↔HTML 固定格式规范

**背景**：AI 审核/补全产生的是纯文本，反写 TestLink 时需转成 HTML；而 TestLink 回传的又是 HTML。为保证「AI 反写后的字段能被无损解回纯文本供后续 AI 再次消费」，需要一套**成对、可逆**的转换函数。

新增 `app/aitc/case/html_format.py`：

```python
def text_to_html(text: str) -> str:
    """纯文本 → 固定格式 HTML（可逆）。
    规则：
    1. 转义 & < > "（防止注入/破坏结构）
    2. 空行 → 段落分隔 <p>；单换行 → <br>
    3. 输出统一包在 <div class="tc-plain"> 内，便于识别本系统生成的内容
    """
    ...

def html_to_text(html: str) -> str:
    """HTML → 纯文本（text_to_html 的逆）。
    优先识别本系统生成的固定格式；对 TestLink 任意 HTML 退化为通用去标签 + <br>/<p> → 换行。
    """
    ...
```

**关键点**：
- `text_to_html` 生成的内容带固定标记（如 `class="tc-plain"`），反写后回拉时能被 `html_to_text` 精准识别并无损还原。
- 对 TestLink 原生任意 HTML，`html_to_text` 退化为通用 `strip_html` + 换行还原（见 §六），保证任意来源都能解出可读纯文本。
- 该函数与 `cleaner.py::strip_html`/`steps_to_text` 配合使用，形成「清洗→消费→反写→再清洗」的闭环。

---

## 六、HTML 清洗与步骤结构化解析器

新建 `app/aitc/testlink/parser.py`（核心模块），负责把 TestLink 原始 HTML 转成结构化字段。

### 6.1 正文字段清洗

对 `summary`/`preconditions`/`test_data` 等正文，复用 `cleaner.py::strip_html` 去标签，并补 `<br>`/`<p>`/`<li>` → 换行的处理：

```python
def html_to_plain(html: str) -> str:
    """TestLink 任意 HTML → 可读纯文本（非可逆，用于展示/向量化/AI）。"""
    # 1. <br>/<p>/</p>/<li> → 换行
    # 2. 去剩余标签（strip_html）
    # 3. 解 HTML 实体（&nbsp; &amp; 等）
    # 4. 压缩多余空行/空格
```

### 6.2 步骤结构化解析（重点 + 降级）

`steps` 的 HTML 结构**不规整、千奇百怪**（已确认），需要健壮的多模式解析 + 降级：

```python
def parse_steps(html: str) -> tuple[list[dict], int]:
    """解析步骤 HTML → ([{step_no, action, expected}], parse_status)
    parse_status: 1-解析成功 2-降级为纯文本 0-无步骤
    """
```

解析策略（按优先级尝试）：

| 优先级 | 识别模式 | 解析方式 |
|---|---|---|
| 1 | `<table>`（2 列：步骤/预期 或 3 列：序号/步骤/预期） | 按 `<tr>` 拆行，`<td>` 拆 cell |
| 2 | `<ol>/<ul>` + `<li>`（每条一步） | 每个 `<li>` 一步，内部再识别预期（如「预期：」分隔） |
| 3 | 连续的 `<div>`/`<p>` 分段 | 每段一步 |
| 4 | 纯文本多行 | 按行拆分，尝试「序号. 操作 -> 预期」模式 |

**降级策略**：以上模式都无法可靠解析时：
1. 将整个 HTML 用 `html_to_plain` 转纯文本；
2. 存入 `steps_raw` 对应的纯文本（或存为单步 `[{step_no:1, action:纯文本, expected:""}]`）；
3. 置 `steps_parse_status = 2`，前端/AI 按纯文本处理，不强行结构化。

> 该解析器是本次接入的**核心工作量与风险点**，建议阶段 0 抓取真实用例样本驱动开发与测试。

---

## 七、同步流程

### 7.1 全量同步（首批）

1. 调 `get_projects()` + `get_test_suites()` 拉项目/套件树，建立 `testlink_suite_id → 本地 suite_id` 映射（复用现有 `AiTcSuite.testlink_suite_id`）。
2. 遍历套件，`get_cases_by_suite()` 拉全部用例。
3. 对每条用例：
   - 原文 HTML 写入 `*_raw` 字段；
   - 清洗写入 `summary`/`preconditions`/`test_data`；
   - `parse_steps` 解析 `steps` 并写 `steps_parse_status`；
   - 写 `testlink_tc_id`/`testlink_version_id`/`synced_hash`/`synced_snapshot`/`last_sync_at`，置 `sync_status=1`（已同步）。
4. 批量写 PG（复用现有 `import_cases` 的批量思路，但走 TestLink 而非 Excel）。
5. 全量同步完成后，投递全量索引任务给 worker（见 §八）。

> 幂等：按 `project_id + external_id`（或 `testlink_tc_id`）匹配，存在则更新，不存在则插入。

### 7.2 增量监控（每日定时任务）

新建 `monitor.py`，复用自研「计算下次运行时间 + asyncio.sleep + Redis 分布式锁」模式（参考 `app/ai/llm_log/aggregator.py`）：

1. 每天固定时间（如凌晨 1:00）运行。
2. 调 `get_changed_cases(since=上次巡检时间)`，或按 `version`/`modification_ts` 比对。
3. 对变化的用例，比较本地 `synced_version`：
   - 本地无未反写变更 → 拉取更新，写 PG，置 `sync_status=1`，投递索引任务；
   - 本地有未反写变更（`sync_status=2`）→ 置 `sync_status=4`（冲突），不覆盖，进入冲突处理。

### 7.3 增量拉取

只处理变化的用例（同全量同步的清洗+写入流程，但按单条/小批量执行），写 PG 后投递索引更新任务给 worker。

---

## 八、独立 Worker（向量化 + ES + Milvus）

**决策（已确认）**：采用**独立进程/常驻 worker**，不复用现有 `app/ai/agent/tasks/` 进程内协程。

### 8.1 形态

- 独立入口文件：`worker_main.py`（项目根）或 `app/aitc/testlink/worker.py` + `python -m` 启动。
- 独立 Docker 服务（`docker-compose.yml` 增加 `tc-sync-worker` 服务），与 API 服务共享 DB/Redis/ES/Milvus，但独立进程。
- 消费模型：DB 轮询「待索引队列」（可用现有 `index_hash` 为空的用例，或独立待处理表/Redis 队列 `aitc:index:queue`）。

### 8.2 职责

1. 消费待索引的 case_id 列表。
2. **批量向量化**：复用 `embed_texts()` + `build_vector_text(name, purpose, summary[:200], steps_text, topo)`。
   - 文本来源：清洗字段（已去 HTML），summary 截 200 字符（对齐用户要求）。
3. **批量写 ES**：复用 `indexer.py` 的 `_index_one_to_es`（或 `scripts/sync_cases_fast.py` 的 bulk 逻辑），文档字段 `summary`/`steps_text` 等均为去 HTML 文本。
4. **批量写 Milvus**：复用 `indexer.py` 的 `_index_one_to_milvus`。
5. 更新 `index_hash`/`indexed_at` 追踪字段。

### 8.3 关键约束

- 与 API 服务**共享 DB**，但使用**独立 Session + 独立事务边界**，批量提交，不阻塞用例更新（对齐用户第 5 点）。
- 向量化是 CPU 密集（本地 bge 模型），在独立进程内用 `run_in_executor` 或直接同步执行，避免占用 API 进程。
- 失败重试：失败的 case_id 保留在待处理队列，带重试次数上限，超限写 `sync_error` 审计。

---

## 九、向量化与 ES 索引策略

### 9.1 向量化（对齐用户第 2 点）

```python
vector_text = build_vector_text(
    name=case.name,
    purpose=case.purpose,
    summary=(case.summary or "")[:200],   # 截断 200 字符
    steps_text=steps_text,                # 清洗后纯文本
    topo=case.topo,
)
```

- 仅用 `name` + `purpose` + `summary`(截 200) 为主，`steps_text`/`topo` 作为补充（沿用现有 `build_vector_text` 逻辑）。
- **不含 HTML 原文**，避免 HTML 标签噪音。

### 9.2 ES 索引（对齐用户第 3 点）

- 文档字段 `summary`/`steps_text`/`purpose` 等均写**去 HTML 后的纯文本**（同步时清洗字段已就绪，直接取自清洗字段）。
- `steps_text` 由结构化 `steps` 经 `steps_to_text` 生成（`cleaner.py` 已有）。
- ES mapping 无需变更（现有 `ES_CASE_MAPPING` 已覆盖）。

---

## 十、按字段反写流程（对齐用户第 7 点）

### 10.1 触发点

在以下写操作**提交成功后**挂反写钩子：

- `service.py::review_case()`（审核提交）
- `service.py::apply_case_review_result()` / `update_case_field()`（AI 结果写入）
- `service.py::update_case()`（人工编辑，若该用例已关联 TestLink）

### 10.2 变更识别

对比当前字段值与 `synced_snapshot`（上次同步快照），识别**变更字段**，只反写这些字段（对齐用户第 2 点：按字段增量反写）。

主要反写字段：`name`、`purpose`、`steps`、`summary`、`preconditions`、`test_data`、`importance`。

### 10.3 反写与回拉校验

1. 对每个变更字段，纯文本/结构化值经 `text_to_html`（或步骤的 `steps_to_html`）转 HTML。
2. 调 `update_case_field()` 逐个反写（或一次性提交），拿回新 `version_id`。
3. **反写完成后立即拉取该用例**，校验内容一致（对齐用户第 7 点）。
4. 更新 `synced_version`/`synced_hash`/`synced_snapshot`/`last_push_at`，置 `sync_status=1`。
5. 反写失败 → 置 `sync_status=5`（反写失败）+ 写 `sync_error`。

### 10.4 回声抑制

反写时记录本次反写产生的 `testlink_modifier`/`modification_ts`；增量监控发现远端变更时，若变更来源是本次反写（`modifier` 为本系统账号、`modification_ts` 与 `last_push_at` 接近），则忽略，避免「自己写回的被当成远端变更」触发误同步。

### 10.5 步骤反写（新用例/全字段场景）

新生成用例（`design_test_case`）可能涉及全字段（对齐用户第 2 点：少量新生成用例涉及所有字段），此时走「在 TestLink 新建用例 + 全字段反写」分支（需 TestLink 支持 `createTestCase`，阶段 0 验证）。

---

## 十一、前端改造（对齐用户第 6 点）

### 11.1 用例详情页（渲染富文本）

`src/views/aitc/case/components/CaseDetail.vue`：

- 正文字段（`summary`/`preconditions`/`test_data`）：改用 `v-html` 渲染 `*_raw` 原文（若 `*_raw` 为空则回退清洗字段纯文本）。
- 测试步骤：优先用结构化 `steps` 表格展示（现有 `el-table`），同时可提供「原文」切换查看 `steps_raw` 富文本。
- **XSS 防护**：`v-html` 前用 DOMPurify 白名单清洗（新增依赖 `dompurify`），过滤 script/事件属性等危险标签。

### 11.2 审核/补全页（用 AI 格式化文本）

`src/views/aitc/task/case_review/ReviewPage.vue`、`case_complete/ReviewPage.vue`：

- 继续使用清洗后的结构化/纯文本字段（`summary`/`steps` 等），不做富文本渲染。
- AI 建议展示为纯文本，人工可编辑。

### 11.3 同步状态与操作界面

- 用例列表/详情增加 `sync_status` 状态展示（未关联/已同步/待反写/远端有更新/冲突/反写失败/远端已删除）。
- 提供「拉取」/「反写」手动触发入口。
- 冲突处理页：本地/远端/快照三方对比（复用 `synced_snapshot`），人工选择采纳。

---

## 十二、AI case tools 改造说明

**结论**：采用「同步时就清洗好写入」方案后，AI tools **几乎无需改动**——`summary`/`steps`/`preconditions` 等清洗字段在同步时已就绪，现有 3 处 dict 构建函数（`query.py::_case_to_dict`、`make_get_case_detail_tool` 内联 dict、`case_task.py::_build_case_detail`）继续读清洗字段即可。

**仅需少量兼容处理**：

| 位置 | 改动 |
|---|---|
| `steps_parse_status == 2`（解析降级）的用例 | `case_task._build_case_detail` 的 `steps` 字段需兼容「纯文本单步」形态，避免 AI 拿到空结构 |
| `case_detail_for_bug()`（`skills/case/tools.py`） | `summary` 若为空可回退 `html_to_text(summary_raw)`，但正常情况同步已清洗，无需改 |
| `recall.py` | 走 ES/Milvus（已清洗），无需改 |
| `contexts.py` | 只取 name，无需改 |

> 兜底规则：清洗字段为空且 `*_raw` 非空时（理论上不应发生，仅作防御），统一经 `html_to_text` 兜底取值。建议抽一个 `get_case_text(case, field)` 工具函数统一封装，避免口径漂移。

---

## 十三、实施阶段划分与里程碑

| 阶段 | 内容 | 交付物 |
|---|---|---|
| 0 | TestLink 连通性验证 + 字段映射/步骤 HTML 结构定稿 | `verify_testlink.py`、真实用例样本、FIELD_MAP 定稿 |
| 1 | 数据模型（Alembic 加 `*_raw` 等字段）+ TestLink client 抽象 + `parser.py` + 全量同步 | 迁移脚本、`app/aitc/testlink/` 包、全量同步跑通 |
| 2 | 增量监控定时任务 + 独立 worker（向量化 + ES + Milvus） | `monitor.py`、`worker_main.py`、docker 服务 |
| 3 | 按字段反写 + 可逆 text↔HTML + 回拉校验 + 冲突处理 | `push_service.py`、`html_format.py` |
| 4 | 前端富文本渲染 + 同步状态/操作界面 | CaseDetail 改造、同步状态列、冲突页 |
| 5 | 审计日志（`ai_tc_sync_logs`）+ 失败重试 + Excel 导入去留决策 + 文档收尾 | 审计表、`开发指导手册.md` 补 testlink 章节 |

---

## 十四、注意事项与风险清单

| # | 风险/注意点 | 应对 |
|---|---|---|
| 1 | **XSS 安全**：前端 `v-html` 渲染 TestLink 原文 | DOMPurify 白名单过滤；后端也可做一层清洗标记 |
| 2 | **步骤 HTML 不规整**（已确认千奇百怪） | 多模式解析 + 降级（`steps_parse_status=2`），阶段 0 抓真实样本驱动 |
| 3 | **向量截断** | summary 只取 200 字符，避免超长 |
| 4 | **增量幂等** | `synced_hash`（同步脏检测）+ `index_hash`（索引变更检测）双 hash |
| 5 | **冲突处理** | `sync_status` 状态机（0-6）+ `synced_snapshot` 三方合并 |
| 6 | **回声抑制** | 反写记录 modifier/modification_ts，避免自触发增量 |
| 7 | **全量同步性能** | 批量向量化、bulk 写 ES、Milvus 批量 insert（参考 `sync_cases_fast.py`） |
| 8 | **worker 与 API 隔离** | 独立进程 + 独立 Session/事务边界，不阻塞用例更新 |
| 9 | **失败重试与审计** | 待索引队列带重试上限；`ai_tc_sync_logs` 审计表记录同步/反写历史 |
| 10 | **纯文本↔HTML 可逆性** | `html_format.py` 成对函数 + 固定标记，保证 AI 反写字段可无损解回 |
| 11 | **Excel 导入去留** | 已有文档提出下线 Excel 导入；本方案接入 TestLink 后评估是否保留（建议保留为离线兜底，待定） |
| 12 | **清洗字段留空兜底** | 防御性 `get_case_text` 统一封装，`*_raw` 兜底 |
| 13 | **vector 维度不可变** | Milvus collection 建好后 EMBEDDING_DIM 不可改，切换 embedding provider 需谨慎 |
| 14 | **同步大事务** | 全量同步分批提交，避免单事务过大 / 长事务锁表 |

---

## 十五、待阶段 0 确认项

1. TestLink 具体 URL / devKey / 样例用例编号。
2. 「测试目的」「测试思想」等字段在 TestLink 中的准确字段位置（`updater_login`/`modification_ts` 可用性）。
3. 步骤 HTML 的真实结构样本（决定 `parser.py` 的模式优先级与降级阈值）。
4. TestLink 是否支持 `createTestCase`（决定新用例全字段反写路径）。
5. `name`/`purpose` 是否含 HTML（决定是否补 `name_raw`/`purpose_raw`）。
