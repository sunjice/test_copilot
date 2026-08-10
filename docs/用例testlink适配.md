# 用例 TestLink 适配

> 创建日期：2026-08-04
> 状态：✅ 第一部分完成（用例域字段改造 + 前端展示），第二部分待后续执行
> 依赖：`开发指导手册.md`

---

## 一、背景与目标

后续要从 TestLink 获取用例信息，并在本地修改用例后反写回 TestLink。为避免两套数据源不一致，需要：
1. 在用例表中增加与 TestLink 对应的身份映射字段
2. 增加同步状态控制字段（乐观锁、版本追踪、内容哈希等）

TestLink 字段映射（已确认）：

| 数据 | 示例 | 本地字段 | TestLink 字段 |
|---|---|---|---|
| 用例编号 | `001`（完整 ID `TC001` = 前缀+编号） | `external_id` | `external_id` |
| 英文标识名 | `ssid_name_length_check` | `name` | `name` |
| 中文用例名称 | `SSID长度验证` | `purpose`（新增） | 测试目的字段 |
| 测试思想 | — | `summary` | `summary` |
| 前置条件 | — | `preconditions` | `preconditions` |
| 步骤 | — | `steps` | `steps` |
| 级别 | — | `importance` | `importance` |

---

## 二、执行计划

### 第一部分（本次执行）：用例域字段改造 + 前端展示

#### 阶段 1：后端模型改造

| # | 文件 | 操作 | 内容 |
|---|---|---|---|
| 1 | `app/aitc/case/models.py` | 改 | ① `AiTcCase` 新增 `purpose` 字段；② `name` / `external_id` 注释语义更新；③ 新增 12 个同步控制/身份映射字段；④ 新增 2 个索引；⑤ `AiTcSuite` 新增 `testlink_suite_id`；⑥ `AiTcProject` 新增 `testlink_project_id` |
| 2 | `app/aitc/case/schemas.py` | 改 | `CaseVO`、`CaseUpdate` 各加 `purpose` 字段 |
| 3 | `app/aitc/case/service.py` | 改 | `_case_to_vo()`、`update_case()`、`import_cases()`、`apply_case_review_result()` 透传 `purpose`；`editForm` 兼容 |

#### 阶段 2：前端展示改造

| # | 文件 | 操作 | 内容 |
|---|---|---|---|
| 4 | `src/api/aitc/case/types.ts` | 改 | `CaseVO`、`CaseForm` 加 `purpose` |
| 5 | `case/components/CaseTable.vue` | 改 | 新增「测试目的」主列，`name` 调整为辅助列 |
| 6 | `case/components/CaseEditForm.vue` | 改 | 表单加「测试目的」输入项 |
| 7 | `case/components/CaseDetail.vue` | 改 | 详情展示「测试目的」 |
| 8 | `case/composables/useCasePage.ts` | 改 | `editForm` 加 `purpose`，`populateEditForm`/`submitEdit` 透传 |

#### 阶段 3：文档更新

| # | 文件 | 操作 | 内容 |
|---|---|---|---|
| 9 | `TODO.md` | 改 | 登记 TestLink 集成待办项 |
| 10 | `用例testlink适配.md` | 改 | 更新执行状态 / 变更记录 |

---

### 第二部分（TODO，后续专项）：TestLink 集成

- [ ] 阶段 0：TestLink 连通验证（需提供 URL + devKey + 样例用例编号）
  - `config.py`/`.env` 加 `TESTLINK_URL`、`TESTLINK_DEVKEY`
  - `scripts/verify_testlink.py`：拉真实用例，确认「测试目的」字段位置、`updater_login`/`modification_ts` 可用性 → 定稿 FIELD_MAP
- [ ] 新建 `app/aitc/testlink/` 包
  - `client.py`（XML-RPC 封装）
  - `field_map.py`（字段映射表 + full_external_id 组装）
  - `hashing.py`（canonical 序列化 + SHA256，字段范围: purpose/name/summary/preconditions/steps/importance）
  - `models.py`（`ai_tc_sync_logs` 审计表）
  - `sync_service.py`：拉取（external_id 幂等匹配）/ 反写（version 乐观锁 → 时间戳降级 → hash 兜底；`aitc_bot` 回声抑制）/ 三方合并 / 冲突解决
  - `router.py`：`POST /pull`、`POST /push`、`GET /conflicts`、`POST /conflicts/{id}/resolve`、`GET /logs`
  - 注册进 `aitc/router.py`
- [ ] `service.py`：内容字段变更自动置 `sync_status=2`（`topo`/`test_data`/AI 字段除外）
- [ ] 巡检定时任务：比对 `version`/`modification_ts`，标记 `sync_status=3`（只标记不自动拉）
- [ ] 前端：同步状态列、拉取/反写按钮、待反写筛选、冲突三栏处理页
- [ ] Excel 导入功能下线（`import_cases` 去掉 Excel 格式解析，`CaseImportDialog.vue` + 入口按钮移除）
- [ ] `开发指导手册.md` 补 testlink 域、字段映射表、同步状态机、降级链章节

---

## 三、改后 AiTcCase 字段清单

### 框架字段（不动）
| 字段 | 类型 | 状态 | 作用 |
|---|---|---|---|
| `id` | BigInteger | 已有 | 主键 |
| `created_at` / `updated_at` | DateTime | 已有 | TimestampMixin |
| `is_deleted` | SmallInteger | 已有 | SoftDeleteMixin |

### 组织归属（不动）
| 字段 | 类型 | 状态 | 作用 |
|---|---|---|---|
| `project_id` | BigInteger FK | 已有 | 所属项目 |
| `suite_id` | BigInteger FK | 已有 | 所属套件 |

### 用例内容字段
| 字段 | 类型 | 状态 | 作用 |
|---|---|---|---|
| `external_id` | String(64) | ⚠️ 语义微调 | TestLink 用例编号（如 `001`），完整展示 ID = `project.prefix + external_id` |
| `name` | String(256) | ⚠️ 语义变更 | 英文标识名（如 `ssid_name_length_check`），与 TestLink `name` 同语义 |
| `purpose` | String(256) | 🆕 新增 | 测试目的 / 中文用例名称（如 `SSID长度验证`） |
| `summary` | Text | 已有 | 测试思想 |
| `preconditions` | Text | 已有 | 前置条件 |
| `topo` | String(512) | 已有 | TestTopo（不同步） |
| `test_data` | Text | 已有 | 测试数据（不同步） |
| `steps` | JSONB | 已有 | 测试步骤 |
| `importance` | SmallInteger | 已有 | 级别 1-低 2-中 3-高 |

### AI 业务字段（不动，不参与同步）
保持现有字段：`is_core`/`core_reason`/`core_source`/`is_sample`/`review_status`/`script_count`

### TestLink 身份映射（全部新增，本次建列）
| 字段 | 类型 | 作用 |
|---|---|---|
| `testlink_tc_id` | BigInteger | TestLink 内部 testcase_id |
| `testlink_version_id` | BigInteger | TestLink tcversion_id |

### 同步状态与控制（全部新增，本次建列）
| 字段 | 类型 | 作用 |
|---|---|---|
| `sync_status` | SmallInteger | 0-未关联 1-已同步 2-待反写 3-远端有更新 4-冲突 5-反写失败 6-远端已删除 |
| `synced_version` | Integer | 上次同步时 TestLink version |
| `synced_hash` | String(64) | 上次同步内容 SHA256 |
| `synced_snapshot` | JSONB | 上次同步时字段快照（三方合并基准） |
| `last_sync_at` | DateTime | 上次同步时间 |
| `last_push_at` | DateTime | 上次反写时间 |
| `testlink_modified_at` | DateTime | TestLink 端最后修改时间 |
| `testlink_modifier` | String(128) | TestLink 端最后修改人 |
| `auto_sync` | SmallInteger | 修改后是否自动反写 0-否 1-是 |
| `sync_error` | Text | 最近反写失败原因 |

### 新增索引
| 名称 | 作用 |
|---|---|
| `idx_aitc_case_tl_tc` | TestLink ID 反查本地用例 |
| `idx_aitc_case_sync_status` | 待反写/冲突列表查询 |

---

## 四、变更记录

| 日期 | 内容 |
|---|---|
| 2026-08-04 | 创建文档；第一部分执行中 |
| 2026-08-04 | 第一部分完成：models.py（+14 字段 +2 索引）、schemas.py（CaseVO/CaseUpdate 加 purpose）、service.py（_case_to_vo/update_case/import/review 透传 purpose + 树节点适配）、types.ts（CaseVO/CaseForm 加 purpose）、CaseTable.vue（加 purpose 主列，name 调为辅助列）、CaseEditForm.vue（加 purpose 输入项）、CaseDetail.vue（加 purpose 展示）、useCasePage.ts（editForm/populateEditForm/submitEdit 透传 purpose）；TODO.md 登记 TestLink 待办项 |
| 2026-08-04 | Alembic 迁移：`e2f3a4b5c6d7` — ai_tc_cases 加 13 列 + 2 索引；ai_tc_projects 加 testlink_project_id；ai_tc_suites 加 testlink_suite_id；DML 回填 `purpose = name`（现有数据）；验证：13 列全部入库、数据回填正确、索引创建成功 |
| 2026-08-04 | 编号显示格式改为 `{prefix}{external_id}__{name}`（如 `TC001__user_login_test`）：后端 CaseVO 加 `project_prefix`、service 批量查前缀透传；前端 CaseTable 合并"编号"+"英文标识"为一列；CaseDetail 头部/编号字段用新格式；CaseEditForm 头部用新格式、编号改为只读 `{prefix}{external_id}`、英文标识 editable |
| 2026-08-04 | Alembic 迁移 `4e01c2c52b72`：规范化 4 个项目 prefix（router→RT、NIC→NC、switch→SW、testx→TX）；35 条用例 external_id 改为项目内自增编号（001~035）；35 条用例 name 改为英文标识（如 pppoe_dial_connect_stability、user_login_test） |
| 2026-08-05 | Alembic 迁移 `99bbb7b233f9`：隐藏非核心菜单（按 tree_path 反选），仅保留 系统管理(id=1) 和 WorkSpace(id=3000) 及其子树，共计隐藏 55 条菜单（代码生成、平台文档、接口文档、组件封装、功能演示、多级菜单、路由参数等） |
