# Agent Tools 清单

> 共 12 个工具，分为查询类、澄清类、任务类、即时处理类四大类。

---

## 一、查询类（5 个）

### 1. `list_projects`

| 项目 | 内容 |
|---|---|
| **描述** | 获取所有可用项目列表。 |
| **参数** | 无 |
| **返回** | `{ projects: [{id, name}] }` |
| **使用场景** | 用户问「有哪些项目」「我在哪个项目」；用户刚进来还没选项目；跨项目对比时先看有哪些项目 |
| **触发词** | 有哪些项目、列出项目、项目列表 |

### 2. `get_suite_tree`

| 项目 | 内容 |
|---|---|
| **描述** | 获取指定项目下的模块树结构。 |
| **参数** | `project_id` (int, 必填) — 项目 ID |
| **返回** | `{ suites: [{id, name, parent_id, tree_path, description}], total }` |
| **使用场景** | 用户问「这个项目有哪些模块」；用户想看模块层级关系；用户想了解模块组织结构 |
| **触发词** | 有哪些模块、模块树、查看模块结构 |

### 3. `search_cases`

| 项目 | 内容 |
|---|---|
| **描述** | 搜索/列出测试用例，支持按模块、关键字、是否核心用例、是否有步骤等条件过滤。`has_steps=false` 可找出缺少测试步骤的用例。 |
| **参数** | `suite_id` (int, 可选) — 模块 ID，不传用当前页面；`keywords` (str, 可选)；`is_core` (bool, 可选)；`has_steps` (bool, 可选)；`page` (int, 默认 1)；`page_size` (int, 默认 20，最多 50) |
| **返回** | `{ cases: [{id, name, summary, importance, is_core, has_steps, steps_count, suite_id, project_id}], total, page, page_size }` |
| **使用场景** | 用户问「这个模块有哪些用例」「找一下登录相关的用例」；用户问「哪些用例是核心的」「哪些用例缺步骤」；用户模糊提到某个功能名，需要搜索定位；用户问「帮我看看这个模块的用例情况」 |
| **触发词** | 有哪些用例、搜索用例、找一下XX、看看模块、核心用例、缺步骤的 |

### 4. `get_case_detail`

| 项目 | 内容 |
|---|---|
| **描述** | 获取单条用例的完整详情（步骤、前置条件、测试数据等）。 |
| **参数** | `case_id` (int, 必填) — 用例 ID |
| **返回** | `{ case: {id, name, summary, preconditions, topo, test_data, importance, is_core, purpose, steps, suite_id, project_id} }` |
| **使用场景** | 用户问「这条用例的具体步骤是什么」；用户说「帮我看看用例 123」；需要了解用例详情后做判断（补写/审核前先看一下） |
| **触发词** | 看看这条用例、用例详情、具体步骤、这条用例的 |

### 5. `get_suite_samples`

| 项目 | 内容 |
|---|---|
| **描述** | 获取模块下标记为样本的用例列表（最多 5 条）。样本用例代表了该模块的用例编写规范。 |
| **参数** | `suite_id` (int, 可选) — 模块 ID，不传用当前页面模块 |
| **返回** | `{ samples: [{id, name, summary, steps_count, ...}], total }` |
| **使用场景** | 用户问「这个模块的样本用例是什么」；用户问「用例应该怎么写」；设计新用例/补全字段前参考样本格式 |
| **触发词** | 样本用例、参考用例、用例范例、怎么写 |

---

## 二、澄清类（1 个）

### 6. `ask_question`

| 项目 | 内容 |
|---|---|
| **描述** | 向用户弹出交互式问卷，收集确认信息后再继续。前端渲染为问答表单（clarify_card）。 |
| **参数** | `title` (str, 必填) — 问题标题，如"审核用例前需要确认以下信息"；`questions` (list, 必填) — 问题列表，每项含：`id` (str)、`label` (str)、`type` (str, 默认 text，可选 select)、`placeholder` (str, 可选)、`options` ([{id, label}], 可选)、`required` (bool, 默认 true) |
| **返回** | `{ msg_type: "clarify_card", content, metadata: {questions} }` |
| **使用场景** | ① 意图模糊，需确认项目/模块（如「帮我审核用例」→ 哪项目？哪模块？）；② 任务前需确认范围（如「审核全部用例还是只审核选中的？」）；③ 需要用户在多个选项中做选择才能继续；④ 用户说的不够明确，需要补充参数 |
| **规则** | 一次性列出所有问题在一张表单中；有明确选项时优先用 select；调用后必须等待用户回答，不能同时调用任务工具 |

---

## 三、任务类（4 个）— 返回确认卡片

> 任务类工具共用 `CreateTaskArgs` 参数基类：`suite_id`、`project_id`、`scope`（`'all'` 整个模块 / 不传为选中用例）、`case_ids`（仅 `create_case_complete_task` 使用）。

### 7. `create_core_select_task`

| 项目 | 内容 |
|---|---|
| **描述** | AI 从指定模块用例中挑选核心/重要用例，返回确认卡片等用户确认后创建后台任务。 |
| **参数** | `suite_id` (int, 可选) — 模块 ID；`project_id` (int, 可选) — 项目 ID，不传均用当前页面 |
| **返回** | `{ msg_type: "confirm_card", content, metadata: {task_type, project_id, suite_id, total, ...} }` |
| **使用场景** | 用户说「帮我挑一下核心用例」；用户说「这个模块哪些用例最重要」；用例太多，需要筛选出关键的做重点维护 |
| **触发词** | 挑选核心用例、挑重要用例、哪些核心、核心用例、优先级高的 |

### 8. `create_case_review_task`

| 项目 | 内容 |
|---|---|
| **描述** | 批量审核用例质量（字段完整性、步骤规范性等），返回确认卡片等用户确认。 |
| **参数** | `suite_id` (int, 可选)；`project_id` (int, 可选)；`scope` (str, 可选) — `'all'` 审核整个模块，`'selected'` 或留空审核选中用例 |
| **返回** | `{ msg_type: "confirm_card", content, metadata: {task_type, project_id, suite_id, total, ...} }` |
| **使用场景** | 用户说「帮我审核一下用例」「检查一下用例质量」；用户问「这些用例写得怎么样」；用例评审前做一轮自动检查；新导入一批用例后检查质量 |
| **触发词** | 审核用例、检查质量、评审用例、用例怎么样、合不合格 |

### 9. `create_script_gen_task`

| 项目 | 内容 |
|---|---|
| **描述** | 批量生成 pytest 自动化测试脚本，返回确认卡片等用户确认。 |
| **参数** | `suite_id` (int, 可选)；`project_id` (int, 可选) |
| **返回** | `{ msg_type: "confirm_card", content, metadata: {task_type, project_id, suite_id, total, ...} }` |
| **使用场景** | 用户说「帮我生成自动化脚本」；用户说「给这些用例写 pytest」；用例审核通过后想一键生成脚本 |
| **触发词** | 生成脚本、写自动化、生成自动化测试、pytest、自动化脚本 |

### 10. `create_case_complete_task`

| 项目 | 内容 |
|---|---|
| **描述** | 对指定模块下字段不完整的用例进行 AI 补全（含测试步骤），参考同模块样本用例的写法。用例必须有编号、名称、测试目的，缺任一项的用例将在执行阶段被跳过。返回确认卡片等用户确认后创建后台任务。 |
| **参数** | `suite_id` (int, 可选) — 模块 ID；`project_id` (int, 可选) — 项目 ID；`scope` (str, 可选) — `'all'` 补全整个模块，不传则处理选中用例；`case_ids` (list[int], 可选) — 精确指定要补全的用例 ID 列表。可通过 `search_cases(has_steps=false)` 提前筛出缺步骤的用例再传入 |
| **返回** | `{ msg_type: "confirm_card", content, metadata: {task_type, project_id, suite_id, total, ...} }` |
| **使用场景** | 用户说「这些用例字段不全，帮我补一下」；用例导入后大量字段为空需要批量补全；用户说「帮我完善一下这个模块的用例」；先用 `search_cases` 筛出缺字段的用例，再传入 `case_ids` 精确补全 |
| **触发词** | 完善用例、补全字段、补充信息、用例字段不全、帮忙补写、信息不完整 |

---

## 四、即时处理类（2 个）— 返回草稿卡片

### 11. `complete_case_steps`

| 项目 | 内容 |
|---|---|
| **描述** | AI 补写测试步骤和预期结果，返回草稿卡片可直接回填到用例编辑表单。 |
| **参数** | `case_id` (int, 可选) — 用例 ID，有 ID 时基于用例的 summary/purpose 补写；`case_title` (str, 可选) — 用例标题，无 ID 时基于标题推断编写 |
| **返回** | `{ msg_type: "draft_card", content, draft_type: "case_steps", draft_data }` |
| **使用场景** | 用户说「这个用例没有步骤，帮我补一下」；`search_cases` 发现大量缺步骤的用例，建议用户补写；用户给了一个标题「帮我写一下这个场景的测试步骤」 |
| **触发词** | 补写步骤、补充测试步骤、写步骤、没步骤帮我补一下 |

### 12. `design_test_case`

| 项目 | 内容 |
|---|---|
| **描述** | 根据需求描述从零设计一条新用例（包含标题、前置条件、测试步骤、预期结果），返回草稿卡片。 |
| **参数** | `requirement` (str, 必填) — 需求描述或功能点说明 |
| **返回** | `{ msg_type: "draft_card", content, draft_type, draft_data }` |
| **使用场景** | 用户说「帮我设计一条登陆功能的测试用例」；用户说「根据这个需求文档写条用例」；用户给了一段功能描述，想要生成用例草稿；新功能上线前需要补充用例 |
| **触发词** | 设计用例、写一条用例、根据需求设计、创建新用例、帮我写用例 |

---

## Agent 工作流优先级

```
用户意图明确 + 上下文充足       → 直接调任务工具
用户意图模糊                   → ask_question → 等回答 → 再调任务工具
用户提到模块名/功能名            → 先 search_cases / get_case_detail 查数据 → 再建议操作
发现大量缺步骤的用例            → 主动建议 complete_case_steps
发现字段不完整                 → 先 search_cases(has_steps=false) 筛出缺步骤用例 → 建议 create_case_complete_task
上下文有 selected_case_ids      → 优先以选中用例为操作对象，而非整个模块
```

## 工具调用规则

1. **批量操作先确认** — 所有任务类工具会先返回确认卡片，用户确认后才真正执行
2. **ask_question 后等待** — 不紧接着调用任务工具，等用户提交回答
3. **上下文充足直接创建** — 页面已有 project_id / suite_id 且意图清晰时，可跳过 ask_question
4. **主动查，不猜测** — 提到模块/用例先调查询工具获取实际数据
5. **完善用例先筛选** — `create_case_complete_task` 支持 `case_ids` 参数，可先用 `search_cases` 精确筛出缺字段的用例再传入，避免处理不必要的用例
