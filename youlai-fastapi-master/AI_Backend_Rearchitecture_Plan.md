# AI 后端整体架构改造方案

## 一、改造目标

- 将后端 AI 结构重构为清晰的分层架构：
  - API 层
  - 用例/应用层
  - 领域服务层
  - AI 编排层
  - AI 提供层
- 去除草稿持久化和草稿 API 流，减少后端复杂度
- 明确 chat 对话和 task 后台任务两条线的边界
- 让 Skill / Tool / Provider / Task 体系可插拔、易扩展
- 保持现有对话、技能、Agent、后台执行能力，但消除耦合点

## 二、为什么要这样改造

### 1. 现状问题

- `app/ai/chat/router.py` 与业务实现耦合过紧，承担请求、会话、消息、AI 编排与草稿逻辑
- `ChatOrchestrator` 混合 Skill 路由、Agent 执行、自由对话，职责不清
- `ChatService` 既负责会话、消息，又负责草稿和元数据，模块粒度太大
- `SessionContext` 与页面上下文、工作状态、AI 参数混在一起，难以扩展
- `SkillRegistry` 与工具调用没有明确边界，新增能力时需要改核心类
- 草稿机制与后台任务、卡片渲染混杂，增加代码复杂度和维护成本
- 后台任务执行逻辑分散，`TaskEngine`、`TaskScheduler`、`execute_task_bg`之间职责不够清楚

### 2. 重构理由

- 分层架构让每一层只做一件事，便于测试、维护与扩展
- 清晰的责任边界降低后续迭代风险，特别是接入新模型、新 provider、新 domain
- 去掉草稿存储后，后端只需保留核心对话与卡片结果，避免状态管理混乱
- 独立的 Skill/Tool/Provider 体系可支持未来插件化、动态加载与权限控制
- 后台任务与请求处理分离后，可更容易做队列调度、限流、重试、任务取消

## 三、建议架构

### 3.1 架构层次

- API 层
  - `app/ai/chat/router.py`：FastAPI 路由与 SSE 返回
- 用例/应用层
  - `ChatUseCase`、`TaskUseCase`：编排调用、参数转换、业务流程
- 领域服务层
  - `SessionService`、`MessageService`、`UsageLogService`：CRUD、领域行为
- AI 编排层
  - `AiChatOrchestrator`：策略选择器
  - `IntentRoutingStrategy` / `AgentStrategy` / `FreeformStrategy`
  - `PromptManager` / `ContextBuilderRegistry`
- AI 提供层
  - `AiConfigProvider`：配置管理
  - `AiProviderAdapter`：OpenAI/DeepSeek/Azure 等适配
  - `AiClient`：底层调用与日志
- 后台任务层
  - `TaskEngine`：任务创建与状态管理
  - `TaskScheduler`：队列调度
  - `TaskWorker`：实际执行 AI 任务

### 3.2 数据与功能边界

- Chat 对话：会话、消息、上下文、技能路由、Agent 调用、自由对话
- Task 执行：任务创建、排队、执行、结果写回、确认
- 草稿：后端不再持久化与确认草稿，改用即时响应或确认卡片模式
- 日志：LLM 调用日志与用量日志继续保留

### 3.3 触发器与多领域扩展支持

- `/` 触发 Skill：前缀命令解析器负责识别 `/skill_name`、`/domain skill_name` 等语法，并把请求路由到 Skill 调度。
- `@` 触发 Agent：前缀命令或上下文标记决定进入 Agent 模式，Agent 选择对应领域的 Tool 集合并执行。
- 多域支持：每个业务域（如 `case`、`bug`、`exec`、`project`）都应有独立的 domain 注册、SkillRegistry、ToolRegistry 和 Prompt/Context 构建规则。
- 统一入口：由 `AiChatOrchestrator` 维护一个 `TriggerRouter`，根据输入前缀、当前域、用户上下文，选择 `SkillStrategy`、`AgentStrategy` 或 `FreeformStrategy`。
- 可扩展性保障：新增领域时只需新增 domain 级别配置、domain-specific skill/tool 注册、domain-specific prompt 模板，无需改动核心路由和执行框架。

### 3.4 数据库与迁移关注点

- 当前数据库表结构仍保留草稿体系：`chat_drafts` 和 `chat_messages.draft_id`，这与方案“取消后端草稿体系”直接冲突。
- 需要新增或修改 Alembic 迁移，删除 `chat_drafts` 表，并移除 `chat_messages.draft_id` 字段。
- `chat_messages.draft_id` 目前没有外键约束，建议如果保留该字段必须补上 FK，否则应删除该字段以避免不一致。
- `chat_drafts.confirmed_at` 使用了 `String(32)`，建议改为标准时间类型或删除该表时一并清理。
- `ai_usage_logs.created_at` 目前是字符串字段，建议改为 `DateTime`，便于统计、排序和时序查询。
- `chat_sessions.domain` 字段是多领域扩展的关键基础，必须保留并确认业务层对它的使用逻辑一致。
- 迁移策略应包括：
  1. 先清理代码中对草稿表和 `draft_id` 的引用
  2. 再创建对应 Alembic 迁移脚本删除表/字段
  3. 确认历史消息元数据已迁移到 `metadata_json` 或新的卡片结构
  4. 检查 `ai_llm_logs` 与 `ai_usage_logs` 的时间字段规范性

## 四、详细改造方案

### 阶段 1：拆分当前模块并清晰职责

1. 保留 `app/ai/chat/router.py`，但只保留 API 层职责：
   - 参数校验
   - 用户鉴权
   - 调用 UseCase
   - 返回结果或 SSE
2. 在 `app/ai/chat/` 下新增或拆分：
   - `usecases.py`
   - `services/session_service.py`
   - `services/message_service.py`
   - `services/usage_log_service.py`
3. 将 `ChatService` 中的业务拆分为更小服务，去掉草稿服务
4. 让 `SessionContext` 更结构化，区分：
   - 页面上下文
   - 运行时工作状态
   - AI 配置上下文

### 阶段 2：重构 AI 编排层

1. 将 `app/ai/chat/orchestrator.py` 拆成：
   - `AiChatOrchestrator`：顶层调度器
   - `IntentRoutingStrategy`：Skill 路由处理
   - `AgentStrategy`：LangGraph Agent 执行
   - `FreeformStrategy`：普通 LLM 对话
2. 让策略返回结构化结果而不是直接发 SSE
3. 将 SSE 负责权交给 `router.py` 或专门的 Transport 层
4. 让 `intent_router.py` 只做意图匹配，后续可替换为 LLM-based routing
5. 将 `context_builder_registry` 作为 prompt 注入组件，统一 domain 上下文构建

### 阶段 3：重构 Skill / Tool / Provider 体系

1. 让 `SkillRegistry` 只管理意图技能与参数定义
2. 新建 `ToolRegistry`，管理 Agent 工具、schema、描述、调用接口
3. `app/ai/agent/tools/case/action.py` 修改为：
   - 不再依赖 `draft_card` artifact
   - 结果采用纯文本或确认卡片结构
4. `app/ai/agent/graph/builder.py` 保留 LLm 缓存与 graph 构建逻辑
5. `app/ai/agent/graph/runner.py` 只做 Agent 执行与事件转结果，不直接写入业务状态
6. 让 `AiClient` 只做底层 provider 调用与日志写入，不携带业务逻辑

### 阶段 4：取消后端草稿体系

1. 删除数据库 `ChatDraft` 模型
2. 删除 `ChatMessage.draft_id` 字段与索引
3. 删除 `app/ai/chat/schemas.py` 中 `DraftVO`、`DraftConfirmReq`
4. 删除 `router.py` 中草稿接口 `GET /drafts/{draft_id}` 与 `POST /drafts/{draft_id}/confirm`
5. 删除 `ChatService` 中所有 draft 方法
6. 将 `SkillResult` 的 `draft_card` 输出统一改成直接结构化响应或适用卡片类型
7. 清理 `app/ai/agent/graph/runner.py` 中 `draft_type`/`draft_data` 的后端处理
8. 修改 `case_design_skill.py`、`steps_complete_skill.py`、以及所有返回 `draft_card` 的 skill

### 阶段 5：优化后台任务执行

1. 保留 `TaskEngine` 的任务创建、验证、状态写入职责
2. 强化 `app/ai/agent/tasks/scheduler.py` 为独立调度器
3. 让 `execute_task_bg` 仅负责后台任务执行与 AI 客户端调用
4. 让任务 handler 只做任务领域处理，不再与请求链路耦合
5. 如需可接入消息队列/Redis 作为后续扩展

## 五、逐阶段执行任务清单

### 任务清单 1：拆分与清理

- [x] `app/ai/chat/router.py` 仅保留路由与 UseCase 调用
- [x] 新增 `app/ai/chat/usecases.py`，实现对话发送、上下文更新、技能调用入口
- [x] 拆分 `app/ai/chat/service.py` 为：
  - `SessionService`
  - `MessageService`
  - `UsageLogService`
- [x] 保留 `ChatService` 业务逻辑，逐步迁移到更小服务
- [ ] 调整 `SessionContext` 类为更明确的状态对象
- [x] 清理 `app/ai/chat/models.py` 中 `ChatDraft` 相关定义
- [x] 清理 `app/ai/chat/schemas.py` 草稿 DTO

### 任务清单 2：重构 AI 编排层

- [x] 新建 `app/ai/chat/orchestrator.py` 的策略划分
- [x] 实现 `AiChatOrchestrator.process()`，按 trigger / domain / config 选择策略
- [x] 增加 `TriggerRouter`，支持 `/` 触发 Skill、`@` 触发 Agent、普通对话
- [x] 抽象 `IntentRoutingStrategy`、`AgentStrategy`、`FreeformStrategy`
- [x] 让 `AgentStrategy` 调用 `AgentExecutor` 返回结构化结果
- [x] 让 `FreeformStrategy` 继续使用 `LangChain` 流式调用，但与 SSE 分离
- [x] 将 prompt / context 生成移入 `PromptManager`
- [x] 设计多领域注册机制，支持 `case`、`bug`、`exec`、`project` 等 domain

### 任务清单 3：Skill/Tool/Provider 重构

- [x] 提取 `SkillRegistry` 和 `ToolRegistry` 的单独职责
- [x] 让 `Skill` 只定义意图、参数、执行逻辑
- [x] 让 `Tool` 只定义可调用接口与返回格式
- [x] 修改 `app/ai/agent/tools/case/action.py` 取消 `draft_card` artifact
- [x] `app/ai/agent/graph/builder.py` 保留 graph 构建逻辑
- [x] `app/ai/agent/graph/runner.py` 只负责事件解析与结果生成
- [x] 修改 `app/ai/client.py` 保持 provider 适配器职责单一

### 任务清单 4：草稿体系删除

- [x] 从 ORM 模型删除 `ChatDraft` 与 `draft_id`
- [x] 实现数据库迁移脚本删除草稿表与字段
- [x] 删除草稿 API 路由与后台逻辑
- [x] 删除 `ChatService` 中草稿相关方法与 metadata 回写
- [x] 全面修正 `SkillResult` 的 `msg_type` 输出，避免后台依赖 `draft_card`
- [x] 修改所有 `draft_card` skill 为直接响应或新卡片类型
- [x] 清理 `draft` 相关搜索结果

### 任务清单 5：后台任务与调度优化

- [x] 清晰定义 `TaskEngine` 与 `TaskScheduler` 的边界
- [x] 保持 `execute_task_bg` 仅做独立后台执行
- [x] 让任务 handler 只负责业务逻辑，不依赖 HTTP 请求上下文
- [x] 新增 `Worker` / `TaskQueue` 封装
- [ ] 测试任务创建、执行、停止、重跑全流程

## 六、验证与回归

- [x] 搜索并确认无残留 `draft`、`DraftVO`、`ChatDraft`、`draft_card`、`draft_id`
- [x] 确认后端路由不再暴露 `/drafts/*`
- [x] 确认 `send_message` 不再创建草稿数据
- [x] 确认数据库迁移移除 `chat_drafts` 表和 `chat_messages.draft_id`
- [ ] 运行后端 chat/task 相关测试用例
- [ ] 手动验证 `chat` 三种路径：Intent Skill / Agent / Freeform
- [ ] 手动验证 task 注册、排队、执行、取消、重跑

## 七、重要理由总结

- 通过分层架构，使后端逻辑更易读、可维护、可测试
- 通过移除草稿持久化，减少对话状态管理复杂度
- 通过清晰拆分策略，AI 逻辑更易替换与升级
- 通过独立任务层，后台执行更稳定且便于扩展队列机制
- 通过 provider 抽象，未来可支持更多 AI 平台而不改业务层

## 八、注意事项

- 本方案聚焦后端结构改造，前端草稿/卡片交互需同步调整
- 草稿删除后，聊天结果应以即时文本或确认卡片为主
- 该方案适合逐步实施，先拆分层次再做功能迁移
- 建议先在小范围内完成第 1、2 阶段，再推进草稿删除与任务优化
