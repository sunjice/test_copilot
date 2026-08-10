# Frontend AI Chat Refactor Plan

## 1. 目标

为 `vue3-element-admin` 中的 AI 聊天模块建立更清晰、可维护、可扩展的前端架构。

目标包括：
- 解除 `LayoutChat.vue` 与核心业务逻辑的过度耦合
- 将消息流、任务状态、草稿/确认卡片、页面上下文分别提取为独立模块
- 统一流式消息与 SSE 事件处理，避免因后端事件粒度变化导致前端逻辑混乱
- 规范 `ChatMessage` / `metadata_json` / SSE event 的数据契约
- 通过分阶段实施降低风险，确保可回归、可测

## 2. 当前痛点

### 2.1 逻辑集中，维护成本高

- `useChat.ts` 当前包含会话、消息、发送、流解析、任务轮询、草稿确认、上下文同步等多重职责。
- `LayoutChat.vue` 直接管理大量 UI 交互和状态，组件职责不清。
- 任务、草稿、确认卡片与主消息流混用，导致消息类型边界不明确。

### 2.2 流式消息与 SSE 混淆

- `ChatMessageAPI.send()` 直接使用 `fetch` 读取 SSE-like 流，流解析逻辑写在 `useChat.ts`。
- 项目已有通用 `useSse` 全局服务，但当前聊天模块并未充分复用它。
- 后端事件分发和前端解析耦合，缺少统一事件模型和稳定的容错策略。

### 2.3 任务处理不一致

- `task_card` 依赖本地轮询 `TaskAPI.getDetail`，没有统一的任务进度事件分发。
- 轮询和消息列表更新混在一起，历史消息加载后需要额外调用 `monitorIncompleteTasks()`。
- 任务状态变化与 `TaskListPanel` 的渲染逻辑依赖隐式 `metadata_json` 字段。

### 2.4 数据契约不明确

- `metadata_json` 目前包含多个动态字段：`skill_name`、`tool_names`、`tool_calls`、`task_status`、`done_count`、`total_count`、`clarify_status`、`confirm_status` 等。
- 前端直接根据这些字段判断 UI 类型，缺少一套类型安全、文档化的消息元数据结构。
- `MessageSendReq` 结构过于简化，未把上下文、skill、模式与后端请求明确区分。

## 3. 模块拆分建议

建议按功能拆成 5 个核心子模块：

### 3.1 Chat UI 层

- `src/layouts/components/chat/ChatMessage.vue`
- `src/layouts/components/chat/TaskListPanel.vue`
- `src/layouts/components/chat/StreamingBubble.vue`
- `src/layouts/components/chat/ChatHistoryPanel.vue`（建议新增）
- `src/layouts/components/chat/ChatInputBar.vue`（建议新增）

职责：仅负责显示和用户交互，事件通过 props/emits 传递。

### 3.2 Chat 状态/逻辑层

建议拆分为：
- `src/composables/chat/useChatSessions.ts`
- `src/composables/chat/useChatMessages.ts`
- `src/composables/chat/useChatStream.ts`
- `src/composables/chat/useChatTasks.ts`
- `src/composables/chat/useChatDrafts.ts`
- `src/composables/chat/useChatContext.ts`

职责：
- `useChatSessions`：会话列表/切换/CRUD
- `useChatMessages`：消息加载、历史恢复、列表变更
- `useChatStream`：发送消息、解析流、组装 assistant 消息
- `useChatTasks`：任务创建、进度更新、task_card 状态管理
- `useChatDrafts`：草稿获取、确认、状态回写
- `useChatContext`：页内上下文同步与会话 context_json 管理

### 3.3 Chat API 层

优化现有 `src/api/chat/index.ts`：
- 保留 `ChatSessionAPI`、`ChatMessageAPI`、`ChatDraftAPI`、`ChatContextAPI`、`ChatSkillAPI`、`ChatTaskAPI`
- 新增 `ChatStreamAPI` 或 `ChatEventAPI`，用于统一流式请求与 SSE 事件契约
- 将流式消息发送和标准请求分离：
  - `sendMessage(sessionId, payload, signal)` 负责 `fetch` / stream
  - `createMessage(sessionId, payload)` 负责普通 POST
- 推荐将 `MessageSendReq` 扩展为 `ChatSendPayload`

### 3.4 SSE/后台事件层

当前已有通用 `src/composables/sse/useSse.ts`，建议如下重构：
- 保持 `useSse` 作为全局长连接事件总线
- 引入 `ChatSseService`：负责订阅聊天相关事件，如 `task_progress`、`new_message`、`session_update`
- 聊天消息流仍可保留单次 `fetch` 流式通道；SSE 用于后台状态和任务进度推送
- 将 `TaskAPI` 的轮询作为 fallback，实现「优先 SSE 推送，失败时退回轮询」

### 3.5 任务/草稿/确认卡片层

拆分 `task_card` 等高级消息卡片的行为：
- `TaskCard`：只负责展示任务进度、跳转、状态 badge
- `ConfirmCard`：只负责收集确认选择并触发 `confirmCreateTask`
- `ClarifyCard`：只负责展示澄清问题并提交答案
- `DraftCard`：只负责草稿查看/确认/丢弃

这些卡片应脱离主消息流的发送逻辑，作为 `ChatMessage` 渲染层的独立子组件。

## 4. SSE 与任务处理重构方案

### 4.1 现状回顾

- `ChatMessageAPI.send()` 直接返回 `Response`，在 `useChat.ts` 手动读取 `ReadableStream`。
- 解析流程混合了 `event: thinking/chunk/skill_start/tool_start/tool_end/message/error`。
- 任务进度与状态更新由 `TaskAPI.getDetail` 轮询，并在 `messages` 中 patch `metadata_json`。
- `useSse` 全局连接主要用于在线数、字典同步等，不用于 chat task 进度。

### 4.2 目标流程

- 保留 `fetch` 流式发送用于用户 query 的实时生成。
- 引入统一 `ChatStreamParser`：
  - 解析事件类型
  - 维护 `partialMessage`、`assistantMessage`、`toolSteps`
  - 统一处理 `AbortError`、`error` 事件
- 创建 `ChatBackgroundEventService`：
  - 订阅 SSE 全局事件
  - 处理 `task_progress`、`task_status_change`、`session_update`、`capability_update`
  - 向 `useChatTasks` 和 `useChatMessages` 分发
- 任务处理逻辑改为：
  - `confirm create task` 触发后产生本地 `task_card`
  - 优先等待 `task_progress` SSE 更新
  - SSE 不可用时回退 `TaskAPI.getDetail` 轮询
  - `task_card` 状态更新仅写入 `metadata_json`，不替换整条消息

### 4.3 核心重构点

- `useChatStream.sendMessage()` 负责：
  - 创建 user message
  - 调用 `ChatStreamAPI.send()`
  - 通过 `ChatStreamParser` 处理 `thinking/chunk/message/tool_start/tool_end/error`
  - 生成最终 assistant 消息并调用 `addLocalMessage`
- `useChatTasks` 负责：
  - `confirmCreateTask(metadata)`
  - `handleTaskEvent(taskEvent)`
  - `createLocalTaskCard()`
  - `syncTaskStatusToMessages(taskId)`
- `useChatDrafts` 负责：
  - `openDraft(draftId)`
  - `confirmDraft(action)`
  - `updateDraftCardState()`
- `useChatContext` 负责：
  - `syncPageContext(pageContext)`
  - `patchSessionContext(sessionId)`

### 4.4 推荐消息处理边界

- `partial stream content` 只在 `StreamingBubble` 内显示
- `assistant` 最终消息应只创建一次
- 出错时生成 `system/error` 消息，支持重试按钮
- `tool_start/tool_end` 事件仅影响观察状态，不输出到聊天正文
- `message` 事件中的 `msg_type` 由后端决定，前端只负责展示对应卡片

## 5. 数据契约建议

### 5.1 ChatMessage 统一模型

```ts
interface ChatMessage {
  id: number | null
  session_id: number | null
  role: 'user' | 'assistant' | 'system'
  msg_type: 
    | 'text'
    | 'action_card'
    | 'task_card'
    | 'draft_card'
    | 'clarify_card'
    | 'confirm_card'
    | 'help_card'
    | 'error'
  content: string
  metadata_json: ChatMessageMetadata | null
  draft_id: number | null
  create_time: string | null
}
```

### 5.2 消息元数据结构

```ts
type ChatMessageMetadata =
  | SkillMetadata
  | ToolMetadata
  | TaskMetadata
  | DraftMetadata
  | ClarifyMetadata
  | ConfirmMetadata
  | ErrorMetadata

interface SkillMetadata {
  skill_name: string
  domain?: string
  mode?: 'SYNC' | 'ASYNC'
}

interface ToolMetadata {
  tool_names: string[]
  tool_calls: number
}

interface TaskMetadata {
  skill_name: string
  task_id: number
  task_status: number
  done_count: number
  total_count: number
  project_id?: number
  suite_id?: number
  case_ids?: number[]
  _selected_option?: string
}

interface DraftMetadata {
  draft_status?: 'pending' | 'confirmed' | 'discarded'
  skill_name?: string
}

interface ClarifyMetadata {
  questions: ClarifyQuestion[]
  clarify_status?: 'submitted'
  clarify_answers?: Record<string, string>
}

interface ConfirmMetadata {
  confirm_options?: ConfirmOption[]
  confirm_status?: 'confirmed' | 'cancelled'
}

interface ErrorMetadata {
  error: true
  last_user_message?: string
}
```

### 5.3 后端流事件契约

建议后端 SSE / stream 事件保持以下统一结构：

```ts
interface ChatStreamEvent {
  event: 'thinking' | 'chunk' | 'message' | 'skill_start' | 'tool_start' | 'tool_end' | 'error' | 'task_update'
  data: Record<string, any>
}
```

其中：
- `thinking`：仅触发 loading / thinking indicator
- `chunk`：逐步追加助手生成文本
- `message`：最终消息体，含 `content`、`msg_type`、`metadata` 等
- `skill_start`：记录当前 skill
- `tool_start` / `tool_end`：更新执行状态
- `error`：统一错误展示
- `task_update`：可选，用于 SSE 推送任务进度

### 5.4 发送请求契约

建议扩展 `MessageSendReq`：

```ts
interface ChatSendPayload {
  content: string
  skill_name?: string
  context_json?: Record<string, any>
  mode?: 'normal' | 'agent' | 'tool'
  stream?: boolean
}
```

这有助于后端增强能力路由、上下文传递、可选技能控制。

## 6. 分阶段实施任务

### Phase 0 — 评估与契约确认

- [ ] 读取并确认当前 `useChat.ts`、`LayoutChat.vue`、`ChatMessage.vue`、`ChatTaskPanel.vue`、`useSse.ts` 的当前实现。
- [ ] 与后端确认当前 `/api/v1/aitc/chat/sessions/{id}/messages` 返回的 SSE 事件格式。
- [ ] 定义统一 `ChatMessageMetadata`、`ChatStreamEvent`、`ChatSendPayload` 契约文档。
- [ ] 制定可回滚方案：先不改后端接口，再逐步调整前端读写。

### Phase 1 — 提取聊天状态模块

- [ ] 从 `useChat.ts` 中拆出 `useChatSessions.ts`、`useChatMessages.ts`、`useChatContext.ts`。
- [ ] 让 `LayoutChat.vue` 只负责 UI 事件和渲染 props。
- [ ] 保留 `ChatMessageAPI` / `ChatSessionAPI` 不变，作为稳定边界。

### Phase 2 — 流式消息与卡片显示重构

- [ ] 创建 `useChatStream.ts`，将 `fetch` + `ReadableStream` 解析逻辑提取到独立服务。
- [ ] 将 `streamingText`、`thinkingStep`、`toolSteps` 等状态与消息列表分离。
- [ ] 让 `StreamingBubble` 只显示“流式渲染内容”，最终消息由 `messages` 数组渲染。
- [ ] 重构 `ChatMessage.vue`，将 `action_card` / `draft_card` / `task_card` / `clarify_card` / `confirm_card` 等提取为子组件。

### Phase 3 — 任务与 SSE 事件统一化

- [ ] 增加 `useChatTasks.ts`，负责 `confirmCreateTask`、`cancelTask`、`updateTaskStatus`。
- [ ] 在 `useSse` 全局连接上订阅 chat 事件，如 `task_progress` / `task_status`。
- [ ] 优先使用 SSE 更新 `task_card`，轮询作为 fallback
- [ ] 将 `TaskListPanel.vue` 的任务列表数据源转为 `useChatTasks` 的标准任务集合。

### Phase 4 — 草稿、确认、澄清卡片交互

- [ ] 提取 `useChatDrafts.ts`，只负责草稿加载和确认状态变更。
- [ ] 规范 `ChatMessageAPI.updateCardStatus()` 的请求入参与后端契约。
- [ ] 优化 `confirm_card` / `clarify_card` 的本地状态更新，保证历史消息恢复后仍能显示已提交结果。

### Phase 5 — 验证与收尾

- [ ] 逐个页面验证 AI 聊天功能：新对话、历史切换、停止生成、重试、确认任务、查看草稿、任务列表跳转。
- [ ] 添加单元测试/可视化回归验证：`useChatStream` 流式解析、`useChatTasks` 状态更新、`ChatMessage` 卡片渲染。
- [ ] 清理遗留逻辑：移除 `useChat.ts` 中已拆分出的冗余部分，避免副作用。
- [ ] 将 `LayoutChat.vue` 变为纯展示层，剩余业务仅依赖 composables。

## 7. 关键改造风险

- 后端 SSE 事件格式调整与前端解析逻辑不一致。
- `metadata_json` 字段不稳定，会导致卡片渲染回退错误。
- 任务状态推送失败时，轮询和 SSE 混用会出现重复更新。
- 旧历史消息中缺少 `task_status` / `done_count` 信息时，任务面板渲染可能错误。

## 8. 建议落地方案

- 采用“先拆后改”策略：先提取模块，不改接口；再逐步规范数据契约；最后统一 SSE 和任务进度。
- 聊天流暂时保持 `fetch` 解析逻辑，但将其从 `useChat.ts` 迁移到 `useChatStream.ts`。
- 任务进度优先通过 SSE 事件推送；后端当前未支持时继续使用当前轮询方式。
- 明确 `ChatMessage` 元数据类型后，可进一步将 `metadata_json` 从 `Record<string, any>` 收窄为类型安全结构。

---

文件: `vue3-element-admin/AI-Chat-Refactor-Plan.md`
