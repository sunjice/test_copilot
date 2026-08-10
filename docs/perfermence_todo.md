# AI Chat 性能优化实施清单

> 目标：解决"发 Hi 等 1 分钟"问题。三条通道各司其职：
>
> ```
> 用户输入
>   ├── command 通道（菜单按钮 / slash 命令）→ 上下文取参 → 直接执行 skill（秒级、确定性）
>   ├── fast path（规则判定为闲聊）→ freeform chat（1-3s）
>   └── 其余 → Agent 全工具（现状不变）
> ```

## 一期：Command 通道 + 闲聊 Fast Path（零风险）

### 1. 后端：command 通道

- [ ] `BaseSkill` 增加 `command` 字段（如 `case_review`、`core_case_select`、`script_gen`、`case_complete`、`complete_steps`、`case_design`）
- [ ] `skill_registry` 支持按 command 查找，并提供命令清单序列化接口（供前端拉取，避免双份维护）
- [ ] `orchestrator.process_message` 入口增加 command 短路：
  - 请求体带 `command` 字段 → 直接从上下文（`project_id` / `suite_id` / `selected_case_ids` / `current_case_id`）组装参数 → 调用对应 skill 执行
  - 不经过 `fast_router`、`intent_router`，不进 Agent
  - 执行结果写入同一 session 消息历史，后续对话可引用
- [ ] 后端兜底解析：消息文本命中 `^/([a-z][\w-]*)\s*(.*)$` 且命令已注册 → 转为 command 处理
- [ ] 未注册命令（如打错的 `/casereview`）→ 直接返回"未识别的命令，输入 / 查看可用命令"，**不静默降级**走普通路由
- [ ] `/case-design` 特殊处理：尾随文本作为 `requirement`；无尾随文本 → 降级进 Agent 用 `ask_question` 澄清（唯一需要澄清轮次的命令）
- [ ] scope 语义：用户有勾选 → `selected`；无勾选 → `all`；尾随文本显式表达的范围优先于当前选择

### 2. 前端：菜单按钮 + slash 命令

- [ ] AI Chat 菜单栏列出 skill 入口（数据来自后端命令清单接口），按当前页面上下文（`required_page`）过滤/置灰
- [ ] 点击按钮 → 组装 `{ command, params, message }` 结构化请求发送
- [ ] 输入框检测 `/` 开头 → 弹出命令列表自动补全
- [ ] 发送前校验：需要选用例的命令（如 `/case-review`）在无勾选且无模块上下文时 → toast 提示"请先选择要审核的用例或切换到模块视图"，不发请求
- [ ] `/case-design` 无尾随文本时弹输入框收集需求描述（或放行让后端走 Agent 澄清）

### 3. 闲聊 fast path

- [ ] 新建 `app/ai/chat/fast_router.py`（~120 行），纯规则分类器：
  - 签名：`classify(message: str, history: list[dict] | None) -> str`
  - 规则优先级：
    1. **会话延续保护**：history 最后一条 assistant 消息是卡片类（`confirm_card` / `clarify_card` / `draft_card`）→ `agent`（防止"好的/确认"被误判打断任务流）
    2. 消息 ≤ 15 字、无数字/ID、命中闲聊模式（`你好/hi/hello/谢谢/再见/你是谁/你能做什么/帮助`，正则 + 关键词表）→ `chitchat`
    3. 其余 → `agent`（保守兜底，宁可慢不可错）
  - 一期只分两类：`chitchat` vs `agent`，不做 query/task 细分
- [ ] `orchestrator.process_message` 插入路由：`chitchat` → 复用现有 `_freeform_chat()`（精简 SYSTEM_PROMPT、无工具、流式）
- [ ] `app/ai/config.py` 新增 `AI_FAST_ROUTE_ENABLED`（默认 true），可一键回退全 Agent 模式

### 4. 可观测

- [ ] SSE `message` 事件 `metadata` 增加 `"route": "command|chitchat|agent"`
- [ ] `ai_llm_logs` 的 `action` 字段记录路由结果，便于统计误判率

### 5. 验收标准

| 场景 | 现状 | 一期目标 |
|------|------|----------|
| "Hi / 你好 / 谢谢" | 30-60s | 1-3s |
| 菜单点击"审核用例"（已选用例） | 30-60s（Agent 循环） | 秒级，直接执行 |
| `/core-select`（模块页） | 30-60s | 秒级，直接执行 |
| 任务流程中回复"好的" | 正常确认 | 不变（会话延续保护） |
| 普通开放对话 | 30-60s | 不变 |

## 二期：查询类工具瘦身（需一期日志数据支撑）

> 风险：工具过滤后 LLM 可能幻觉（编造结果）或强行凑合。必须先用一期日志验证查询关键词召回率后再做。

- [ ] 从 `ai_llm_logs` 统计真实用户消息，验证查询类关键词（`有哪些/列出/查询/搜索/详情/看看/显示`）召回率
- [ ] `build_case_tools(ctx, groups: set[str] | None)` 增加分组过滤参数（`None` = 全部，向后兼容）
- [ ] `fast_router` 增加 `query` 分类 → `_agent_chat(tools=查询组)`（5 个查询工具 + `ask_question`）
- [ ] query 模式两道保险：
  - 保留 `ask_question`，模型拿不准可反问
  - system prompt 明示："如需执行操作类任务请告知用户描述需求"，用户下一句会重新分类回全工具链路（风险窗口仅一轮）
- [ ] 可选：`agent_case.txt` 拆 base/page/tools 三层，query 场景不注入任务相关章节

## 明确不做

- 不上 LLM 意图分类器（多一次调用多 2-5s 延迟，规则对闲聊/任务二分类足够；误判率高时再升级 `deepseek-chat` + structured output）
- 前端不把按钮点击伪造成用户文本扔进 Agent（把最可靠的入口降级成概率猜测）
- 未注册命令不静默降级走普通路由
