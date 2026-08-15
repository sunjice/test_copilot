# 测试用例 \& Bug 混合检索系统设计

> 状态：待审核
> 日期：2026‑08‑12
> 变更：补充完整 Bug 检索全链路设计，与原有用例检索架构、编码风格、目录、接口规范保持完全对齐
> 
> 

---

## 1\. 总体架构

```Plain Text
┌─────────────────────────────────────────────────────────┐
│                     LLM Agent (Tools)                    │
│  recall_similar_cases  / recall_similar_bugs / search_cases / get_case_detail / get_bug_detail │
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

|存储|角色|存什么|
|---|---|---|
|**PostgreSQL**|唯一事实源|用例 / Bug 全部业务字段；检索辅助字段`index_hash`、`indexed_at`；同义词表`retrieval_synonyms`；用例‑缺陷关联表|
|**Milvus**|语义向量检索|`case_id`/`bug_id` \+ `vector` \+ 过滤字段；**不存储任何文本**|
|**Elasticsearch**|BM25 关键词检索|Bug / 用例搜索字段 \+ 过滤字段；**不存储完整展示业务字段**|

> 召回逻辑统一：Milvus / ES 召回只返回主键 ID 列表 → 批量回查 PG 获取完整信息 → 返回 LLM Agent。
> 
> 

---

## 2\. 知识库范围

|类型|是否纳入|说明|
|---|---|---|
|测试用例 \(ai\_tc\_cases\)|✅|本项目核心|
|Bug \(ai\_tc\_bugs\)|✅|新增；来源 Bugzilla 同步，向量 \+ BM25 混合检索|
|用例‑缺陷关联表 \(ai\_tc\_case\_bug\_rel\)|✅|PG 内多对多关联，不进入向量 / ES 索引，仅业务查询|
|测试指南 / 培训材料|❌|交给 Dify 平台|
|执行记录 / 轮次总结 / 周报 / 报告|❌|走 SQL 聚合 \+ LLM 生成，**不参与语义检索**|

---

## 3\. Milvus Collection 设计

### 3\.1 用例 Collection：`tc_cases`

|字段名|类型|作用|
|---|---|---|
|`case_id`|INT64 \(主键\)|关联 PG `ai_tc_cases.id`|
|`vector`|FLOAT\_VECTOR\(1024\)|语义向量（BGE‑large‑zh‑v1\.5 /bge‑m3）|
|`project_id`|INT64|过滤字段|
|`suite_id`|INT64|过滤字段|
|`is_core`|BOOL|过滤字段|
|`is_sample`|BOOL|过滤字段|
|`is_deleted`|BOOL|过滤字段（软删除标记）|

索引：`IVF_FLAT` 或 `HNSW`（视规模决定）

### 3\.2 Bug Collection：`tc_bugs`（完整实现）

|字段名|类型|作用|
|---|---|---|
|`bug_id`|INT64 \(主键\)|关联 PG `ai_tc_bugs.id`，对应 Bugzilla bug\_id|
|`vector`|FLOAT\_VECTOR\(1024\)|语义向量，由 PG 字段`embedding_text`生成|
|`project_id`|INT64|过滤字段，项目 ID|
|`severity`|INT16|过滤字段；1 致命 2 严重 3 一般 4 轻微|
|`status`|INT16|过滤字段；状态编码，同 PG 业务枚举|
|`is_duplicate`|INT16|过滤字段；是否重复缺陷，重复缺陷不参与检索召回|
|`is_deleted`|BOOL|过滤字段（软删除标记）|

> 索引：同用例，`HNSW`/`IVF_FLAT`；标量索引建立在 `project_id`、`is_deleted`、`is_duplicate`，检索默认过滤 `is_deleted=false AND is_duplicate=0`。
> 
> 

---

## 4\. Elasticsearch 索引设计

### 4\.1 用例索引：`tc_cases`

|字段名|类型|分词器|作用|
|---|---|---|---|
|`case_id`|keyword|\-|关联 PG 主键|
|`project_id`|integer|\-|过滤|
|`suite_id`|integer|\-|过滤|
|`is_core`|boolean|\-|过滤|
|`importance`|keyword|\-|过滤（高 / 中 / 低）|
|`is_sample`|boolean|\-|过滤|
|`is_deleted`|boolean|\-|过滤（软删除）|
|`name_words`|text|`ik_max_word`\(索引\) / `ik_smart`\(查询\) \+ 同义词|name 预拆词后存储（去下划线 / 驼峰→空格分隔）|
|`purpose`|text|`ik_max_word` / `ik_smart` \+ 同义词|测试目的|
|`summary`|text|`ik_max_word` / `ik_smart` \+ 同义词|摘要 / 描述|
|`steps_text`|text|`ik_max_word` / `ik_smart` \+ 同义词|测试步骤（纯文本）|
|`topo`|text|`ik_max_word` / `ik_smart` \+ 同义词|拓扑 / 环境信息|
|`updated_at`|date|\-|排序 / 过滤|

**不入索引的字段**：`preconditions`、`test_data`、`review_status`（公司用例中这两个字段很少有值）

### 4\.2 Bug 索引：`tc_bugs`（完整实现）

> ES 只存储检索过滤、BM25 全文字段；完整业务详情回查 PG；
> BM25 数据源使用 PG 中`full_text`字段（保留全部报错码、堆栈关键词，不做重度语义删减）。
> 
> 

|字段名|类型|分词器|作用|
|---|---|---|---|
|`bug_id`|keyword|\-|关联 PG 主键`ai_tc_bugs.id`|
|`project_id`|integer|\-|过滤|
|`component`|keyword|\-|Bugzilla 模块，精确过滤|
|`severity`|integer|\-|严重等级编码，过滤|
|`status`|integer|\-|缺陷状态编码，过滤|
|`is_duplicate`|integer|\-|是否重复缺陷，过滤；重复缺陷过滤不召回|
|`is_deleted`|boolean|\-|软删除过滤|
|`title`|text|`ik_max_word`\(索引\)/`ik_smart`\(查询\)\+ 同义词|Bug 标题；boost 权重 = 3\.0，标题匹配优先级更高|
|`environment`|text|`ik_max_word`/`ik_smart`\+ 同义词|环境、版本信息|
|`full_content`|text|`ik_max_word`/`ik_smart`\+ 同义词|BM25 主检索字段，来自 PG`full_text`完整清洗文本|
|`update_time`|date|\-|更新时间，时间范围过滤、排序|

> 说明：
> 
> 1. `full_content`：PG 侧清洗输出，供给 ES BM25；**和向量输入****`embedding_text`****为两份不同文本，不可复用**；
> 
> 2. 重复缺陷`is_duplicate=1`在 ES 查询条件直接过滤排除；
> 
> 3. 原始评论 JSONB 不进 ES 索引。
> 
> 

---

## 5\. 分词策略

### 5\.1 ES 侧

|内容|策略|
|---|---|
|**中文文本**|IK 分词器：索引侧 `ik_max_word`（细粒度），查询侧 `ik_smart`（粗粒度）\+ 同义词过滤器|
|**name 英文标识（用例）**|Python indexer 预拆词（`_`/ 驼峰→空格分隔），存 `name_words`|
|**Bug 字段英文 / 报错码 / 接口名**|IK 会原样保留英文 token，配合同义词表统一术语；不需要额外预分词脚本；报错码、版本号交由 IK 原生处理|
|**数字 / 编号**|Bugzilla bug\_id、用例编号走 PG 精确匹配，不走 BM25 语义检索|

### 5\.2 Bug 向量化拼接规则（向量输入：`embedding_text`）

> 与用例保持相同风格：**带字段标签、换行分隔；不空行；空字段直接省略该行；不做外部 jieba 分词；不喂原始杂乱堆栈**
> 来源：PG 经过清洗脚本 \+ 可选 LLM 抽取后得到的`embedding_text`，格式示例：
> 
> 

```Plain Text
缺陷标题: 高并发登录接口偶发500空指针异常
问题现象: 100并发压测，调用登录接口偶现返回500错误
复现操作: 多线程并发调用登录接口
环境信息: CentOS7.9 JDK11 MySQL8.0
根因分析: 连接池耗尽未做空值判断
修复方案: 增加空值校验，调整连接池最大连接数
```

规则：

1. 字段顺序固定：`缺陷标题` → `问题现象` → `复现操作` → `环境信息` → `根因分析` → `修复方案`

2. 某字段为空，直接省略整行，不输出`xxx:`空标签噪声；

3. **不做外部手工分词**，交由 Embedding 模型内部 tokenizer；

4. 该文本**不用于 ES BM25**；ES 使用 PG 独立字段`full_text`。

### 5\.3 Query 侧

- 不手工做分词、术语替换、停用词移除；依赖 IK \+ IDF 自然降权常见词

- LLM 前置抽取核心 query 作为兜底；

- Bug 检索 query 处理逻辑与用例完全一致。

---

## 6\. 术语表 / 同义词

> Bug 检索与用例**共用同一套同义词表****`retrieval_synonyms`****，同一套 ES 同义词热更新机制，不需要新建表**。
> 
> 

### 6\.1 存储

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

> Bug 领域新增术语示例（仅数据，不改表结构）
> \| id \| synonym\_group \| term \| is\_preferred \| domain \|
> \|\-\-\-\-\|\-\-\-\-\-\-\-\-\-\-\-\-\-\-\|\-\-\-\-\-\-\|:\-\-\-:\|\-\-\-\-\-\-\-\-\|
> \| 11 \| null\_pointer \| 空指针异常 \| true \| bug \|
> \| 12 \| null\_pointer \| NPE \| false \| bug \|
> \| 13 \| oom \| 内存溢出 \| true \| bug \|
> \| 14 \| oom \| OOM \| false \| bug \|
> 
> 

### 6\.2 生效方式

- 定期（或手动触发）按组聚合生成 ES 同义词规则 → 调用 ES Synonyms API 热更新；

- **仅查询侧生效，索引构建阶段不展开同义词，避免引入歧义噪声**；

- 用例、Bug 两套 ES 索引共用同一套同义词配置。

---

## 7\. 召回算法

### 7\.1 用例召回整体流程（原始完整内容）

```Plain Text
用户 Query
    │
    ├─ Milvus tc_cases 向量检索 → top 20 (相似度分数)
    ├─ ES tc_cases BM25 检索   → top 20 (BM25 分数)
    │
    └─ RRF 融合 (k=60) → 综合排名 top 20
          │
          ├─ 可选：Reranker 精排（预留，默认关闭）
          │
          └─ 批量回查 PG ai_tc_cases 获取完整详情
                │
                └─ 返回结果（含各阶段分数）
```

### 7\.2 Bug 召回整体流程（和用例完全对齐）

```Plain Text
用户 Query
    │
    ├─ Milvus tc_bugs 向量检索 → top 20 (相似度分数)
    ├─ ES tc_bugs BM25 检索   → top 20 (BM25 分数)
    │
    └─ RRF 融合 (k=60) → 综合排名 top 20
          │
          ├─ 可选：Reranker 精排（预留，默认关闭）
          │
          └─ 批量回查 PG ai_tc_bugs 获取完整详情
                │
                └─ 返回结果（含各阶段分数）
```

### 7\.3 RRF 参数

- `k = 60`；融合后取 top20；

- 过滤条件：`project_id`、`is_deleted`、`is_duplicate`、`severity` 在 Milvus、ES 查询阶段**直接下推过滤**。

### 7\.4 Reranker

- 沿用原有预留接口，**默认关闭**；

- 启用条件：融合后 top20 质量不满足需求时开启；用例 / Bug 复用同一套 reranker 抽象。

> 编号精确查询（Bugzilla bug\_id）由 LLM 判断后调用`get_bug_detail`，不属于`recall_similar_bugs`工具职责。
> 
> 

---

## 8\. Tool 设计

### 8\.1 已有 Tool（完整原始内容，不改动）

|Tool 名|功能|数据源|
|---|---|---|
|`search_cases`|按条件过滤查询用例（project\_id/suite\_id/importance 等）|PG|
|`get_case_detail`|根据 case\_id 精确查询用例详情|PG|
|`recall_similar_cases`|向量\+BM25混合召回相似测试用例|Milvus\+ES\+PG|

**recall\_similar\_cases 完整参数定义**

|参数|类型|必填|说明|
|---|---|---|---|
|`query`|string|✅|自然语言查询描述|
|`project_id`|int|❌|项目过滤|
|`suite_id`|int|❌|用例套件过滤|
|`is_core`|bool|❌|是否核心用例过滤|
|`importance`|string|❌|优先级过滤：高/中/低|
|`top_k`|int|❌|返回数量，默认 5|
|`enable_rerank`|bool|❌|是否启用 reranker，默认 false|

**recall\_similar\_cases 返回参数完整定义**

|字段|类型|说明|
|---|---|---|
|`case_id`|int|用例主键ID|
|`name`|string|用例名称|
|`purpose`|string|测试目的|
|`summary`|string|用例摘要描述|
|`steps_text`|string||

> （注：部分内容可能由 AI 生成）
