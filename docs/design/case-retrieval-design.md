# 测试用例 & Bug 混合检索系统设计

> 状态：待审核  
> 日期：2026-08-11

---

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                     LLM Agent (Tools)                    │
│  recall_similar_cases  /  search_cases  /  get_case_detail │
└──────────┬──────────┬──────────┬────────────────────────┘
           │          │          │
     ┌─────▼──┐  ┌───▼───┐  ┌──▼────┐
     │Milvus  │  │  ES   │  │  PG   │
     │(向量)  │  │(BM25) │  │(事实源)│
     └────────┘  └───────┘  └───────┘
           │          │          │
           └──────────┴──────────┘
                     │
              RRF 融合召回
                     │
              回查 PG 获取完整详情
```

### 存储分工

| 存储 | 角色 | 存什么 |
|------|------|--------|
| **PostgreSQL** | 唯一事实源 | 用例/Bug 全部字段 |
| **Milvus** | 语义向量检索 | `case_id` + `vector` + 过滤字段（无文本） |
| **Elasticsearch** | BM25 关键词检索 | 搜索字段 + 过滤字段（无展示字段） |

### 召回后回查 PG

ES / Milvus 召回只返回 `case_id` 列表 → 批量回查 PG 获取完整信息 → 返回 LLM。

---

## 2. 知识库范围

| 类型 | 是否纳入 | 说明 |
|------|---------|------|
| 测试用例 (ai_tc_cases) | ✅ | 本项目核心 |
| Bug (待确认表名) | ✅ | 后续扩展 |
| 测试指南 / 培训材料 | ❌ | 交给 Dify 平台 |
| 执行记录 / 轮次总结 / 周报 / 报告 | ❌ | 走 SQL 聚合 + LLM 生成，不参与语义检索 |

---

## 3. Milvus Collection 设计

### 3.1 用例 Collection：`tc_cases`

| 字段名 | 类型 | 作用 |
|--------|------|------|
| `case_id` | INT64 (主键) | 关联 PG `ai_tc_cases.id` |
| `vector` | FLOAT_VECTOR(1024) | 语义向量（BGE-large-zh-v1.5） |
| `project_id` | INT64 | 过滤字段 |
| `suite_id` | INT64 | 过滤字段 |
| `is_core` | BOOL | 过滤字段 |
| `is_sample` | BOOL | 过滤字段 |
| `is_deleted` | BOOL | 过滤字段（软删除标记） |

索引：`IVF_FLAT` 或 `HNSW`（视规模决定）

### 3.2 Bug Collection：`tc_bugs`（预留）

| 字段名 | 类型 | 作用 |
|--------|------|------|
| `bug_id` | INT64 (主键) | 关联 PG bug 表主键 |
| `vector` | FLOAT_VECTOR(1024) | 语义向量 |
| `project_id` | INT64 | 过滤字段 |
| `severity` | VARCHAR | 过滤字段（critical/major/minor/trivial） |
| `status` | VARCHAR | 过滤字段 |
| `is_deleted` | BOOL | 过滤字段 |

---

## 4. Elasticsearch 索引设计

### 4.1 用例索引：`tc_cases`

| 字段名 | 类型 | 分词器 | 作用 |
|--------|------|--------|------|
| `case_id` | keyword | - | 关联 PG 主键 |
| `project_id` | integer | - | 过滤 |
| `suite_id` | integer | - | 过滤 |
| `is_core` | boolean | - | 过滤 |
| `importance` | keyword | - | 过滤（高/中/低） |
| `is_sample` | boolean | - | 过滤 |
| `is_deleted` | boolean | - | 过滤（软删除） |
| `name_words` | text | `ik_max_word`(索引) / `ik_smart`(查询) + 同义词 | name 预拆词后存储（去下划线/驼峰→空格分隔） |
| `purpose` | text | `ik_max_word`(索引) / `ik_smart`(查询) + 同义词 | 测试目的 |
| `summary` | text | `ik_max_word` / `ik_smart` + 同义词 | 摘要/描述 |
| `steps_text` | text | `ik_max_word` / `ik_smart` + 同义词 | 测试步骤（纯文本） |
| `topo` | text | `ik_max_word` / `ik_smart` + 同义词 | 拓扑/环境信息 |
| `updated_at` | date | - | 排序/过滤 |

**不入索引的字段**：`preconditions`、`test_data`、`review_status`（公司用例中这两个字段很少有值）

### 4.2 Bug 索引：`tc_bugs`（预留）

| 字段名 | 类型 | 分词器 | 作用 |
|--------|------|--------|------|
| `bug_id` | keyword | - | 关联 PG 主键 |
| `project_id` | integer | - | 过滤 |
| `severity` | keyword | - | 过滤 |
| `status` | keyword | - | 过滤 |
| `title` | text | `ik_max_word` / `ik_smart` + 同义词 | 标题 |
| `description` | text | `ik_max_word` / `ik_smart` + 同义词 | 描述 |
| `steps_reproduce` | text | `ik_max_word` / `ik_smart` + 同义词 | 复现步骤 |
| `is_deleted` | boolean | - | 过滤 |

---

## 5. 分词策略

### 5.1 ES 侧

| 内容 | 策略 |
|------|------|
| **中文文本** (purpose/summary/steps_text/topo) | IK 分词器：索引侧 `ik_max_word`（细粒度），查询侧 `ik_smart`（粗粒度）+ 同义词过滤器 |
| **name 英文标识** | Python indexer 预拆词（`_`/驼峰→空格分隔），存 `name_words`，与其他文本字段一致用 IK + 同义词（IK 对英文单词原样保留，中英文混合 name 也能被中文分词覆盖，且可命中同义词扩展） |
| **数字/编号** | 不做分词，编号查询走 PG 精确匹配 |

### 5.2 向量化侧

**拼接格式：带字段标签 + 换行**

```
用例名称: test login api
测试目的: 验证用户登录接口的正确性
测试摘要: 使用合法/非法账号密码组合调用登录接口
测试步骤: 1. 构造请求参数 2. 调用登录接口 3. 校验返回码
拓扑环境: 单节点部署
```

**规则**：

- name 先预拆词（去 `_`/驼峰拆分 → 空格分隔），再放入 `用例名称` 行
- 字段顺序固定：`用例名称` → `测试目的` → `测试摘要` → `测试步骤` → `拓扑环境`
- 空字段直接省略该行，不产生 `"测试目的: "` 这种噪声
- **不做分词，不做术语替换**，语义模型本身具备一定的同义理解能力

**为什么用标签格式**：

- BGE 等模型训练时见过大量 `"标签: 内容"` 格式，标签能帮模型区分各段语义角色，向量质量比裸拼接更稳
- 字段边界清晰，避免短字段被长步骤文本淹没

### 5.3 Query 侧

- 不手工做分词、术语替换、停用词移除
- 依赖 IK + IDF 自然降权常见词
- LLM 前置抽取核心 query 作为兜底

---

## 6. 术语表 / 同义词

### 6.1 存储

PG 表 `retrieval_synonyms`：

```sql
CREATE TABLE retrieval_synonyms (
    id SERIAL PRIMARY KEY,
    synonym_group VARCHAR(200) NOT NULL,   -- 同义词组标识（短标识，如 login/stress_test）
    term VARCHAR(500) NOT NULL,            -- 术语（放宽到500，兼容带参数的长短语）
    is_preferred BOOLEAN DEFAULT FALSE,    -- 是否为推荐词
    domain VARCHAR(100),                   -- 领域（如 network/storage/security）
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE (synonym_group, term)           -- 同组内术语唯一
);
```

**说明**：

- `synonym_group` 是组标识（短英文标识即可），200 足够
- `term` 是单个术语，通常是一个词/短语，但兼容 `TC_登录接口_并发场景` 这类带参数的长术语，放宽到 500

### 6.2 数据示例

一组同义词 = 多行，靠 `synonym_group` 关联：

| id | synonym_group | term | is_preferred | domain |
|----|--------------|------|:---:|--------|
| 1 | login | 登录 | true | auth |
| 2 | login | 登陆 | false | auth |
| 3 | login | login | false | auth |
| 4 | login | sign in | false | auth |
| 5 | concurrent | 并发 | true | performance |
| 6 | concurrent | 并行 | false | performance |
| 7 | concurrent | concurrent | false | performance |
| 8 | stress_test | 压测 | true | performance |
| 9 | stress_test | 压力测试 | false | performance |
| 10 | stress_test | stress test | false | performance |

### 6.3 生效方式

- 定期（或手动触发）按组聚合生成 ES 同义词规则 → 调用 ES Synonyms API 热更新
- 仅查询侧生效（索引侧不做同义词展开，避免歧义引入噪声）

上表示例生成的 ES 规则（每组一行，查询时命中任一词则全组展开匹配）：

```
登录, 登陆, login, sign in
并发, 并行, concurrent
压测, 压力测试, stress test
```

如查询 `登陆失败`，ES 会同时匹配包含 `登录` / `login` / `sign in` 的文档。

---

## 7. 召回算法

### 7.1 整体流程

`recall_similar_cases` 只负责语义混合召回。编号精确查找（如 TC-2024-001）由 LLM 判断后调 `get_case_detail` 完成，不在本工具职责范围内。

```
用户 Query
    │
    ├─ Milvus 向量检索 → top 20 (相似度分数)
    ├─ ES BM25 检索   → top 20 (BM25 分数)
    │
    └─ RRF 融合 (k=60) → 综合排名 top 20
          │
          ├─ 可选：Reranker 精排
          │
          └─ 批量回查 PG 获取完整详情
                │
                └─ 返回结果（含各阶段分数）
```

### 7.2 RRF 参数

- `k = 60`
- 融合后取 top 20
- 过滤条件（project_id / suite_id / is_deleted 等）在 Milvus 和 ES 各自查询时带上

### 7.3 Reranker

- 预留 reranker 接口，**默认关闭**
- 可选方案：BGE-Reranker-large（本地部署）或 API 调用
- 启用条件：融合后 top 20 质量不满足需求时开启

---

## 8. Tool 设计

### 8.1 已有 Tool（不改动）

| Tool 名 | 功能 | 数据源 |
|---------|------|--------|
| `search_cases` | 按条件过滤查询用例（project_id/suite_id/importance 等） | PG |
| `get_case_detail` | 根据 case_id 精确查询用例详情 | PG |

### 8.2 新增 Tool

#### `recall_similar_cases`

**功能**：语义向量 + BM25 混合召回相似用例

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | string | ✅ | 自然语言查询描述 |
| `project_id` | int | ❌ | 项目过滤 |
| `suite_id` | int | ❌ | 套件过滤 |
| `importance` | string | ❌ | 重要程度过滤 |
| `top_k` | int | ❌ | 返回数量，默认 5 |
| `enable_rerank` | bool | ❌ | 是否启用 reranker，默认 false |

**返回**：用例列表，每条包含：

| 字段 | 类型 | 说明 |
|------|------|------|
| `case_id` | int | 用例 ID |
| `name` | string | 用例名称 |
| `purpose` | string | 测试目的 |
| `summary` | string | 摘要 |
| `steps` | string | 测试步骤 |
| `topo` | string | 拓扑信息 |
| `importance` | string | 重要程度 |
| `project_id` | int | 项目 ID |
| `suite_id` | int | 套件 ID |
| `score` | float | RRF 综合排序分数 |
| `vector_score` | float | Milvus 向量相似度分数（未命中为 null） |
| `bm25_score` | float | ES BM25 分数（未命中为 null） |
| `rank_vector` | int | 向量召回排名（未命中为 null） |
| `rank_bm25` | int | BM25 召回排名（未命中为 null） |

> LLM 可根据 `score` 判断相似度，`vector_score` / `bm25_score` 分别反映语义和关键词匹配程度。

---

## 9. 数据同步

### 9.1 同步方式

- **增量同步**：PG 数据变更后 → 异步任务写入 Milvus + ES
- **全量重建**：提供管理接口手动触发
- 复用 `app/aitc/task/` 现有任务引擎

### 9.2 追踪字段

`ai_tc_cases` 表新增：

| 字段 | 类型 | 说明 |
|------|------|------|
| `index_hash` | VARCHAR(64) | 索引内容的 hash，用于增量变更检测 |
| `indexed_at` | TIMESTAMP | 最近一次索引时间 |

**`index_hash` 工作机制**：

1. 索引时，将参与索引的内容（向量拼接文本 + BM25 字段 + 过滤字段）拼接后计算 hash（SHA256 截断），写入 `index_hash`
2. 增量同步时重新计算当前内容 hash 并比对：
   - 一致 → 内容未变，跳过（不调 Embedding、不写 ES/Milvus）
   - 不一致 → 重新向量化并更新索引，刷新 `index_hash` 和 `indexed_at`

**为什么不用 `updated_at` 判断变更**：

- `updated_at` 在任意字段变更时都会更新，改了 `review_status` 等不进索引的字段也会触发重新向量化
- 向量化需调 Embedding 模型（GPU 资源 / API 费用），误触发浪费明显
- `index_hash` 只覆盖真正影响索引的字段，无关改动零成本跳过

### 9.3 软删除处理

- `is_deleted=True` 的用例：从 Milvus 和 ES 中删除
- 查询时 Milvus/ES 均过滤 `is_deleted != true`

---

## 10. 数据清洗

### 10.1 name 字段

- 去除前后空白
- `_` → 空格（如 `test_login_api` → `test login api`）
- 驼峰拆分（如 `LoginTest` → `Login Test`）
- 存入 ES `name_words` 字段，用 IK 分词 + 同义词（与 purpose 等字段同一 analyzer）

### 10.2 HTML / Markdown

- `steps` 字段中如有 HTML 标签 → 去除，保留纯文本
- 存入 ES `steps_text` 字段

### 10.3 空字段

- `preconditions`、`test_data` 不进入索引
- 其他字段为空时写入空字符串（ES 不报错）

---

## 11. ES 镜像与版本

- **镜像**：`docker.elastic.co/elasticsearch/elasticsearch:8.12.0`
- **插件**：`analysis-ik`（预装或挂载）
- **内存**：建议 ≥ 2GB（开发环境 1GB 可跑）

---

## 12. 实施计划（共 8 步）

| 步骤 | 内容 | 预估工作量 |
|------|------|-----------|
| 1 | 环境搭建：ES + IK 插件 + Milvus + 索引/Collection 创建脚本 | 0.5d |
| 2 | PG 表新增 `index_hash` / `indexed_at` 字段 + migration + 改sql | 0.5h |
| 3 | 数据清洗模块 `retrieval/cleaner.py`（name拆词、HTML去标签） | 0.5d |
| 4 | 同义词管理 `retrieval/synonyms.py`（CRUD + ES 同步） | 0.5d |
| 5 | 索引同步 `retrieval/indexer.py`（增量 + 全量） | 1d |
| 6 | 混合召回 `retrieval/retriever.py`（Milvus + ES + RRF） | 1d |
| 7 | Tool 注册 `recall_similar_cases`（对接 Agent 框架） | 0.5d |
| 8 | 接口测试 + 召回质量评估 | 0.5d |

---

## 13. 目录结构

公共层抽取与 case / bug 各自独立的拆分方式：

```
app/aitc/retrieval/
├── __init__.py
├── common/                     # 公共层：case/bug 共享
│   ├── __init__.py
│   ├── client.py               # ES/Milvus 客户端封装
│   ├── config.py               # 连接配置
│   ├── cleaner.py              # 通用清洗（name拆词、HTML去标签）
│   ├── fusion.py               # RRF 融合算法
│   ├── reranker.py             # Reranker 接口（预留）
│   └── synonyms.py             # 术语/同义词管理
├── case/                       # 用例检索
│   ├── __init__.py
│   ├── indexer.py              # 用例索引同步（增量+全量）
│   ├── retriever.py            # 用例混合召回
│   ├── schemas.py              # 用例 Pydantic 模型
│   └── service.py              # Tool 入口（recall_similar_cases）
├── bug/                        # Bug 检索（预留，结构同 case）
│   ├── __init__.py
│   ├── indexer.py
│   ├── retriever.py
│   ├── schemas.py
│   └── service.py              # Tool 入口（recall_similar_bugs）
└── management/                 # 运维接口
    ├── __init__.py
    ├── reindex.py              # 全量重建入口
    └── debug.py                # 调试工具（见第 14 节）
```

**原则**：

- `common/` 存放与业务无关的通用逻辑，case 和 bug 直接复用
- `case/` 和 `bug/` 各自独立，互不依赖，新增类型时照抄结构即可
- `service.py` 作为 Tool 入口，调用 `retriever.py` 完成召回

---

## 14. 调试与追踪

### 14.1 调试接口

提供独立的调试接口，不走 LLM Agent，可直接 HTTP 调用：

```
POST /api/v1/retrieval/debug/case
```

**请求参数**（与 `recall_similar_cases` 一致）：

```json
{
  "query": "用户登录接口测试",
  "project_id": 1,
  "top_k": 5
}
```

**响应**（各阶段完整追踪）：

```json
{
  "query": "用户登录接口测试",
  "stages": {
    "vector": {
      "results": [
        {"case_id": 101, "score": 0.8234, "rank": 1},
        {"case_id": 205, "score": 0.7891, "rank": 2}
      ],
      "total": 20,
      "latency_ms": 12
    },
    "bm25": {
      "results": [
        {"case_id": 101, "score": 8.452, "rank": 1},
        {"case_id": 88,  "score": 7.213, "rank": 2}
      ],
      "total": 20,
      "latency_ms": 8
    },
    "fusion": {
      "results": [
        {"case_id": 101, "rrf_score": 0.0322, "vector_rank": 1, "bm25_rank": 1},
        {"case_id": 88,  "rrf_score": 0.0161, "vector_rank": null, "bm25_rank": 2}
      ],
      "total": 20,
      "latency_ms": 2
    },
    "rerank": {
      "enabled": false,
      "results": null
    }
  },
  "final": [
    {"case_id": 101, "name": "test_login_api", "score": 0.0322, ...}
  ],
  "total_latency_ms": 22
}
```

### 14.2 日志追踪

每个召回请求生成唯一 `trace_id`，各阶段输出结构化日志：

```json
{"trace_id": "abc123", "stage": "vector",  "latency_ms": 12, "hits": 20, "top1_case_id": 101}
{"trace_id": "abc123", "stage": "bm25",    "latency_ms": 8,  "hits": 20, "top1_case_id": 101}
{"trace_id": "abc123", "stage": "fusion",  "latency_ms": 2,  "hits": 20, "top1_case_id": 101}
{"trace_id": "abc123", "stage": "rerank",  "latency_ms": 0,  "enabled": false}
{"trace_id": "abc123", "stage": "pg_fetch","latency_ms": 5,  "fetched": 5}
```

### 14.3 调试面板

后续可在管理界面中提供召回质量分析页面：
- 输入 query → 展示三路结果对比（向量 / BM25 / 融合后）
- 展示各字段匹配高亮
- 支持手动调整 RRF `k` 值、top_k 并实时查看效果

---

## 附录：关键决策记录

| # | 决策 | 理由 |
|---|------|------|
| 1 | ES 不存展示字段，召回后回查 PG | PG 是唯一事实源，避免数据不一致 |
| 2 | 编号精确查询走 `get_case_detail`，不在 `recall_similar_cases` 中处理 | 职责分离，LLM 自主选择调用哪个 Tool |
| 3 | 向量化前不做分词/术语替换 | 语义模型自身具备理解能力，预处理可能损失语义 |
| 4 | Query 不做手工预处理 | IK + IDF 自然降权通用词，手工规则难维护 |
| 5 | `preconditions` / `test_data` 不进索引 | 公司用例中这两个字段极少有值 |
| 6 | `review_status` 不进过滤字段 | 不需要 |
| 7 | Reranker 默认关闭 | 先看 RRF 融合效果，不够再加 |
| 8 | 文档知识库交给 Dify | 自研效果不一定好，且非本项目核心 |
| 9 | 模块化单体，不拆新工程 | 用例/Bug 检索仅服务本项目，独立部署成本高于收益 |

---

## 15. 配置指导

> 新增日期：2026-08-11。检索模块所有配置均由 `app/config.py` 定义默认值，
> 可通过项目根 `.env` / `.env.local` 或系统环境变量覆盖（pydantic-settings 加载，
> 环境变量优先级最高）。

### 15.1 检索基础设施

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `ES_HOST` | `http://localhost:9200` | Elasticsearch 地址 |
| `ES_INDEX_CASE` | `tc_cases` | 用例 ES 索引名 |
| `ES_INDEX_BUG` | `tc_bugs` | Bug ES 索引名（预留） |
| `MILVUS_HOST` | `localhost` | Milvus 地址 |
| `MILVUS_PORT` | `19530` | Milvus 端口 |
| `MILVUS_COLLECTION_CASE` | `tc_cases` | 用例 Milvus Collection 名 |
| `MILVUS_COLLECTION_BUG` | `tc_bugs` | Bug Collection 名（预留） |

### 15.2 Embedding Provider

向量化通过 `EMBEDDING_PROVIDER` 切换，内置 `local / ollama / openai / azure` 四种，
注册表实现位于 `app/aitc/retrieval/common/embedding/`，新增供应商无需改动分发代码。

| Provider | 配置项 | 默认值 | 说明 |
|----------|--------|--------|------|
| **local**（默认，离线） | `EMBEDDING_MODEL` | `models/bge-large-zh-v1.5` | 本地模型目录（相对项目根），兼容 HF 模型名 |
| | `EMBEDDING_DEVICE` | `cpu` | `cpu` / `cuda` |
| **ollama** | `OLLAMA_BASE_URL` | `http://localhost:11434` | 本地 Ollama 服务地址 |
| | `OLLAMA_EMBEDDING_MODEL` | `bge-m3` | 常用 `bge-m3` / `nomic-embed-text` 等 |
| **openai**（OpenAI 兼容） | `OPENAI_EMBEDDING_BASE_URL` | `""` | 通义千问 / DeepSeek / OpenAI 官方均适用 |
| | `OPENAI_EMBEDDING_API_KEY` | `""` | 对应厂商 API Key |
| | `OPENAI_EMBEDDING_MODEL` | `text-embedding-v3` | 通义千问默认模型 |
| **azure** | `AZURE_OPENAI_API_KEY` | `""` | Azure OpenAI Key |
| | `AZURE_OPENAI_ENDPOINT` | `https://your-resource.openai.azure.com` | 资源端点 |
| | `AZURE_OPENAI_API_VERSION` | `2024-02-01` | API 版本 |
| | `AZURE_EMBEDDING_DEPLOYMENT` | `text-embedding-3-small` | 部署名 |

**全局必配**：`EMBEDDING_DIM`（默认 `1024`）必须与当前 provider 所用模型的实际输出维度一致，
Milvus Collection 创建后维度不可修改。

### 15.3 配置模板（写入 `.env`）

**A. 本地模型（现状，离线可用）**

```ini
EMBEDDING_PROVIDER=local
EMBEDDING_MODEL=models/bge-large-zh-v1.5
EMBEDDING_DIM=1024
EMBEDDING_DEVICE=cpu
```

**B. 本地 Ollama（需先 `ollama pull bge-m3`）**

```ini
EMBEDDING_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBEDDING_MODEL=bge-m3
EMBEDDING_DIM=1024
```

**C. 通义千问 API（中文效果最佳，需 DashScope Key）**

```ini
EMBEDDING_PROVIDER=openai
OPENAI_EMBEDDING_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_EMBEDDING_API_KEY=sk-xxxx
OPENAI_EMBEDDING_MODEL=text-embedding-v3
EMBEDDING_DIM=1024
```

**D. Azure OpenAI**

```ini
EMBEDDING_PROVIDER=azure
AZURE_OPENAI_API_KEY=xxxx
AZURE_OPENAI_ENDPOINT=https://xxx.openai.azure.com
AZURE_EMBEDDING_DEPLOYMENT=text-embedding-3-small
EMBEDDING_DIM=1536
```

### 15.4 切换 Provider 操作流程

1. 修改 `.env` 中 `EMBEDDING_PROVIDER` 及对应配置
2. **维度变化时**删除旧 Milvus Collection（维度不可变）：
   - `python -c "from pymilvus import utility, connections; connections.connect('default', host='localhost', port='19530'); utility.drop_collection('tc_cases')"`
3. 全量重建索引（按当前 provider 向量化写入 ES + Milvus）：
   - 全量：`python scripts/sync_cases_to_engines.py`
   - 增量（未变更自动跳过）：`python scripts/sync_cases_incremental.py`
   - 指定用例：`python scripts/sync_cases_incremental.py --case-ids 101,102,103`
4. 验证召回：
   - `GET /api/v1/aitc/retrieval/debug/case?query=用户登录接口测试`

> 注意：写入与查询必须使用同一 provider + 同一模型，跨模型检索无语义可比性。

### 15.5 约束与注意事项

- **Collection 维度不可变**：切 provider 前先核对 `EMBEDDING_DIM`，不符先删库重建
- **全链路模型一致**：索引写入与查询召回必须同 provider 同模型
- 中文场景推荐：本地 `bge-m3`（Ollama）或 API `text-embedding-v3`（通义千问）；
  Azure 系列中文为弱项
- RRF 参数 `k=60` 固定（`common/config.py` 的 `RRF_K`），双路各召回 20 条
- ES 使用自建 IK 镜像（`docker/elasticsearch`），首次启动按 `docker-compose.yml` 构建

---

## 16. 实现状态对照（2026-08-11）

### 16.1 逐章节对照

| 设计章节 | 内容 | 状态 | 说明 |
|----------|------|:----:|------|
| 1 总体架构 | Milvus + ES + PG 回查 + RRF | ✅ | 完全按设计实现 |
| 2 知识库范围 | 用例纳入、Bug 预留 | ✅ | `bug/` 预留空包 |
| 3.1 Collection `tc_cases` | 7 字段 + 索引 | ✅ | IVF_FLAT + IP，与设计一致 |
| 3.2 Collection `tc_bugs` | 预留 | ⏳ | 未创建（符合"预留"） |
| 4.1 ES 索引 `tc_cases` | 13 字段 + IK + 同义词 | ✅ | 与设计字段一致 |
| 4.2 ES 索引 `tc_bugs` | 预留 | ⏳ | 未创建 |
| 5 分词策略 | name 预拆词、向量标签拼接 | ✅ | `cleaner.py` 完整实现 |
| 6 同义词管理 | PG 表 + ES 热更新 | ✅ | 建表 SQL ✅；`app/aitc/retrieval/router.py` 提供 CRUD + ES 同步接口（前端页面可对接） |
| 7.1 RRF 融合 | k=60、top 20 | ✅ | `fusion.py` 实现 |
| 7.3 Reranker | 预留、默认关闭 | ⚠️ | 参数已透传，实现为 TODO 占位 |
| 8 Tool `recall_similar_cases` | 参数/返回 | ✅ | 已挂载 Agent 工具列表 |
| 9.1 数据同步 | 增量 + 全量 | ✅ | `index_single/index_batch/reindex_all` + 同步脚本 |
| 9.2 `index_hash` 追踪 | 字段 + 迁移 | ✅ | ORM ✅、独立 migration ✅；**已合并进 `youlai-aitc.sql` 主建表** |
| 9.3 软删除 | 删除 + 过滤 | ✅ | 已实现 |
| 10 数据清洗 | name / HTML / 空字段 | ✅ | 与设计一致 |
| 11 ES 镜像 | 8.12.0 | ⚠️ | 实际用 **8.17.1** 自建 IK 镜像（版本更高，无碍） |
| 12 实施计划 | 8 步 | ✅ | 核心步骤全部落地 |
| 13 目录结构 | 公共层 + case/bug 拆分 | ⚠️ | `management/reindex.py`、`common/reranker.py` 未建（功能并入现有文件）；新增 `embedding/` 包与 `common/schemas.py` |
| 14 调试接口 | POST `/api/v1/retrieval/debug/case` | ⚠️ | 已实现但为 **GET `/api/v1/aitc/retrieval/debug/case`**，仅保留开发调试；索引运维已迁至 `scripts/`（无 HTTP 入口） |

### 16.2 设计外新增（超预期）

| 新增项 | 说明 |
|--------|------|
| `common/embedding/` 包 | Provider 注册表（local/ollama/openai/azure），可扩展任意供应商 |
| `common/schemas.py` | 召回结果 / 调试追踪公共 Pydantic 模型 |
| `scripts/sync_cases_to_engines.py` | 运维入口：命令行全量同步脚本（无需启动 FastAPI） |
| `scripts/sync_cases_fast.py` | 批量向量化全量同步脚本 |
| `scripts/sync_cases_incremental.py` | 运维入口：增量同步（`index_hash` 跳过未变更），支持 `--case-ids` 指定用例 |
| `scripts/run_sync_background.ps1` | 运维入口：后台运行封装，`-Script` 参数切换全量/增量 |
| `management/debug.py` `/debug/case` | 仅开发调试：召回全过程追踪（运维接口已从 debug 迁出） |
| `retrieval/router.py` 同义词路由 | 同义词 CRUD + ES 同步的正式业务接口（前端页面可对接） |

### 16.3 遗留项（Gap 清单）

| # | 事项 | 优先级 | 说明 |
|---|------|:------:|------|
| 1 | `common/reranker.py` 占位实现 | 低 | 当前 `enable_rerank` 为 TODO |
| 2 | 增量同步事件驱动 | 中 | 当前靠手动接口/脚本；`scripts/` 已有后台轮询方案（`Dockerfile.sync`） |

> 已关闭（2026-08-11）：
> - `retrieval_synonyms` 建表 SQL 已并入 `youlai-aitc.sql`
> - `index_hash` / `indexed_at` 已并入 `ai_tc_cases` 主建表，新库无需再执行 `retrieval-migration.sql`（存量库仍可执行）
> - 同义词管理 HTTP 接口已落地于 `app/aitc/retrieval/router.py`（正式业务路由，非 debug 入口）
