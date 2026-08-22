# AI Chat 多域化架构改造 — 落地方案 + 逐文件改动清单

> 目标：将现有「AI 对话」体系改造为以 **domain（领域）** 为驱动的可扩展架构。
> 覆盖范围：LayoutChat（悬浮专业对话）+ ai-chat（独立普通对话页）。
> 设计基线：**后端零改动**、**前端先行可运行**、**只做架构扩展（新领域仅留扩展点，不落地业务逻辑）**。
> 文档状态：**已实施（前端多域化改造完成，后端零改动）**。
> 标记说明：`[x]` 已实现并验证；`[ ]` 待实施。

---

## 一、总体设计

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  前端展示层（按域过滤）                                        │
│  - 欢迎页 / 快捷卡片 / /命令 / 上下文栏                         │
│  - 全部由 Domain Profile 动态驱动，切域即切换整套 UI           │
└──────────────────────────────┬──────────────────────────────┘
                               │ domain 标签（字符串）
┌──────────────────────────────▼──────────────────────────────┐
│  状态层（前端按域分区软隔离）                                  │
│  - aiContextStore：contextByDomain 分桶                       │
│  - useChat：currentDomain 参数化 + 每域独立会话/消息状态        │
│  - 会话打 domain 标签，切域自动切换状态桶                       │
└──────────────────────────────┬──────────────────────────────┘
                               │ 复用现有接口（domain 为自由字符串）
┌──────────────────────────────▼──────────────────────────────┐
│  后端（保持不变）                                              │
│  - domain 已是自由字符串，非枚举、无白名单校验                  │
│  - SkillRegistry 按域精确过滤，查不到返回空列表、不报错          │
│  - 非 case 域自动回落 FreeformStrategy 自由对话，流式正常        │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 领域清单（当前 + 预留）

| domain | 用途 | Agent | 本期状态 |
|---|---|---|---|
| `case` | 测试用例专业对话 | 现有 Agent | 已存在，保持不变 |
| `bug` | 测试 Bug 专业对话 | 预留 | **仅前端留扩展点，不落地** |
| `exec` | 测试执行数据对话 | 预留 | **仅前端留扩展点，不落地** |
| `kb` | 普通知识库问答（独立页面） | 无专属 Agent，走 Freeform | **本期落地（纯前端）** |

> 说明：**不设 `common` 域**。`common` 依赖后端 `domains` 多值机制（跨域共享 skill），
> 与「后端零改动」目标冲突，本期删除；如未来确有跨域共享需求，再单独评估后端改动。

### 1.3 关键设计决策（已确认）

1. **后端零改动**：后端 `domain` 字段本就是自由字符串（`str`，默认 `"case"`），无枚举限制、无白名单校验。前端传 `bug`/`kb`/`exec` 任意字符串均可正常入库、查询、对话。
2. **新领域只留扩展点，不落地业务**：本期不新建 bug/exec 域的 skill、Agent、ContextBuilder、提示词。前端仅在 `domainProfiles` 中预留 `bug`/`exec` 的 profile 配置位，保证「架构上能扩展」。
3. **上下文软隔离（纯前端，软隔离状态桶）**：`aiContextStore` 从「单例全局」改为「按域分区」，每域独立维护 `project_id/suite_id/selected_case_ids` 等；LayoutChat 每域独立维护聊天 UI 状态（当前会话 id、消息列表、输入框文字），切域自动保存/恢复各自的状态桶，彼此互不干扰。
4. **流式写入绑定发起时 domain 快照**：防止「case 域发起流式（后端持续返回 token）→ 中途切到 kb 域 → 流式回写错桶」的竞态。即发送消息那一刻固化 `startDomain`，流式过程中始终写 `startDomain` 对应的状态桶，而不是读实时变化的 `currentDomain`。
   - **切域不取消进行中的流式任务**：任务后台继续，结果异步归位到发起域（对齐 Copilot Chat 并行 Agent 任务的做法）。
   - **进行中状态提示**：发起域若存在后台进行中的回复，其聊天入口需显示「进行中」加载态/角标，否则用户切回时会看到一条看似静止的半截消息。
5. **`SkillInfo.domain` 保持单值 `string`**：后端 `SkillInfoVO.domain` 仍返回单值字符串，前端**不得**升级为 `domains: string[]`，否则技能列表全部拿到 `undefined`。
6. **会话列表按域过滤**：历史会话按 domain 过滤，每个域只展示本域的会话。后端 `list_sessions(domain)` 已在 SQL 层过滤（权威可靠），前端 `loadSessions(domain)` 传当前域即可，后端零改动。

---

## 二、前端改动清单

### 2.1 `src/stores/aiContext.ts` — 上下文按域分区（核心改造） `[x]`

**现状**：单例全局 `context`，所有页面共享一份，无法隔离。

**改动**：
- `context` 改为 `contextByDomain: Record<string, AiPageContext>`。
- 新增 `activeDomain: string`，`register(page, domain?)` 时切换/初始化对应分桶。
- `contextJson` computed 改为读取 `activeDomain` 对应的桶。
- `update(data)` 只写当前激活域的桶。
- `unregister()` / `clear()` 只清理当前域或指定域。

```ts
// 伪代码示意
const contextByDomain = ref<Record<string, AiPageContext>>({})
const activeDomain = ref("case")

function register(page: string, domain: string = "case") {
  activeDomain.value = domain
  const bucket = contextByDomain.value[domain] ?? { currentPage: "", projectId: null }
  bucket.currentPage = page
  contextByDomain.value[domain] = bucket
}
function update(data: Record<string, any>) {
  const d = activeDomain.value
  if (!d) return
  contextByDomain.value[d] = { ...contextByDomain.value[d], ...data }
}
```

> 兼容性：`register(page)` 不传 domain 时默认 `"case"`，保证现有 case 页面调用无需改动。

---

### 2.2 `src/layouts/components/chat/useChat.ts` — domain 参数化 + 状态分桶 `[x]`

**现状**：`createSession` 写死 `domain: "case"`（第 87 行）；`pageContext` 全局单份；无 domain 概念。

**改动点**：
1. 新增 `currentDomain = ref("case")` 与 `setDomain(domain)`。
2. `createSession` 使用 `domain: currentDomain.value` 而非写死 `"case"`。
3. `loadSessions()` 改为 `loadSessions(domain?)`，调用 `ChatSessionAPI.list(domain ?? currentDomain.value)`（会话列表按域过滤，后端 SQL 层过滤）。
4. `loadSkills()` 改为 `loadSkills(domain?)`，调用 `ChatSkillAPI.list(domain)`（技能列表需按域过滤，kb 域无 skill）。
5. `sendMessage` 中 `ChatContextAPI.set` 携带 domain。
6. 流式写入（`addLocalMessage` / `segments` 结算）绑定「发起时的 domain 快照」：
   ```ts
   const startDomain = currentDomain.value
   // ... 流式过程中始终写 startDomain 对应的状态桶
   ```

> 说明：若 LayoutChat 与 ai-chat 页面**各自持有独立的 useChat 实例**，则「状态分桶」可简化为「每个实例自带 domain」；真正需要分桶的是 **LayoutChat 常驻实例**（见 2.4）。

---

### 2.3 `src/layouts/components/chat/useChatPanel.ts` — 欢迎页/命令/卡片按域动态化 `[x]`

**现状**：`welcomeTitle` 固定「有什么我能帮你的吗？」；`SKILL_LABELS` 硬编码 case；`quickActions` 硬编码 case 快捷卡片；`contextBarItems` 逻辑写死 case 字段。

**改动**：
1. 新增 `domainProfile` 依赖注入（或从 deps 传入 `currentDomain`）。
2. `welcomeTitle` 改为从 profile 读取：`domainProfile.welcomeTitle`。
3. `quickActions` 改为按 domain 从 profile 取（`profile.quickActions`）。
4. `skillLabel` 的 `SKILL_LABELS` 改为从 profile 的 label 映射读取。
5. `contextBarItems` 改为按 domain 的「上下文渲染器」生成，case/bug/exec 各自定义字段渲染（本期 bug/exec 可先复用 case 渲染器或留空）。
6. `welcomeSubtitle` 改为从 profile 读取，并在两个 Chat 面板（LayoutChat / ChatPanel）以 `v-if="welcomeSubtitle"` 展示。

> 新建 `src/layouts/components/chat/domainProfiles.ts` 集中定义各域 profile：
> ```ts
> export interface DomainProfile {
>   welcomeTitle: string
>   welcomeSubtitle: string
>   quickActions: QuickAction[]
>   skillLabels: Record<string, string>
>   contextRenderers: ...
> }
> export const domainProfiles: Record<string, DomainProfile> = {
>   case: { ... },      // 现有用例助手
>   kb:   { ... },      // 知识库助手（无卡片/命令/上下文）
>   bug:  { ... },      // 预留占位
>   exec: { ... },      // 预留占位
> }
> ```

---

### 2.4 `src/layouts/components/LayoutChat.vue` — 切域状态桶 + 按域加载 `[x]`

**现状**：常驻悬浮组件；`useChat()` 单实例；watch route/contextJson 注入 pageContext；`toggle()` 时 `ensureInit()` 一次性初始化。

**改动**（采用「软隔离状态桶」方案）：
1. 监听路由变化推导 `currentDomain`（从 `route.meta.domain` 或 path 前缀），调用 `setDomain(domain)`。
2. 切域时（**不 abort 当前流式任务**，仅切换状态桶展示）：
   - 保存当前域聊天 UI 状态（`activeSessionId / messages / text`）到 `domainState[currentDomain]`。
   - 切换至目标域状态桶（无则新建空态），恢复该域之前的会话/输入状态。
   - `loadSkills(currentDomain)`、`loadSessions(currentDomain)` 重新拉取（两者均按域过滤）。
   - 若离开的域有进行中的流式回复，保留其「进行中」标记，入口显示进度角标。
3. 保持 `pageContext` 同步逻辑，但 `pageContext` 来源改为 `aiContextStore` 当前域桶。
4. 头部标题**保持「AI 助手」不变，不按域显示**。
5. **AI Chat 独立页隐藏 LayoutChat**：`hideCollapsed = computed(() => currentDomain.value === "kb")`，浮标与展开面板的 `v-if`/`v-else-if` 都叠加 `!hideCollapsed`，避免与页内 ChatPanel 重复。

---

### 2.5 `src/views/ai-chat/index.vue` — 独立普通对话页（kb 域） `[x]`

**现状**：含 WorkspacePanel + ChatPanel，`onContextChange` 里写死 `register("case")`（第 90 行）。

**改动**（已确定采用「无工作区树，纯对话」方案）：
- 移除 WorkspacePanel 与 resizer，仅保留 `ChatPanel`。
- `onMounted` 时 `register("kb", "kb")`。
- `ChatPanel` 使用 `kb` 域 profile（无快捷卡片、无 `/` 命令、无上下文栏）。

---

### 2.6 `src/views/ai-chat/chat/ChatPanel.vue` — kb 域禁用 skill/命令/上下文 `[x]`

**现状**：完整复用 useChatPanel，展示欢迎页/快捷卡片/命令补全/上下文栏。

**改动**：
1. 传入 `currentDomain = "kb"`。
2. `useChatPanel` 根据 profile 判断：`kb` 域 `quickActions=[]`、`showSlashPanel` 恒 false、`showContextBar` 恒 false。
3. `init()` 里 `loadSkills` 可跳过（kb 无 skill）。

---

### 2.7 `src/api/chat/types.ts` — 类型扩展（`SkillInfo` 保持不变） `[x]`

**改动**：
1. **`SkillInfo.domain` 保持单值 `string`，不做任何改动**。后端 `SkillInfoVO.domain` 仍是单值，升级为数组会导致技能列表全部 `undefined`。
2. 新增 `DomainProfile` 相关类型（若独立到 domainProfiles.ts 则放那里）。

```ts
// 保持不变 —— 不要改成 domains: string[]
export interface SkillInfo {
  name: string
  domain: string
  description: string
  mode: 'SYNC' | 'ASYNC'
  keywords: string[]
}
```

---

### 2.8 `src/api/chat/index.ts` — API 参数透传（已支持，无需改动） `[x]`

**现状**：`ChatSessionAPI.list(domain?)`、`ChatSkillAPI.list(domain?)` 已支持 domain 参数。

**改动**：
- 会话列表 `ChatSessionAPI.list(domain)` 按域过滤（见 2.2）。
- 技能列表 `ChatSkillAPI.list(domain)` 按域过滤（见 2.2）。

---

## 三、后端改动清单

**结论：后端零改动，无需任何代码修改。**

后端现有的 domain 机制天然支持多域扩展，依据如下：

1. **`domain` 是自由字符串**：`SessionCreate.domain: str = "case"`（schemas.py），无枚举、无白名单，前端传 `bug`/`kb`/`exec` 任意值都能正常入库。
2. **查询已支持 domain 过滤**：`list_sessions(domain)` / `list_skills(domain)` 已提供 `?domain=` 查询参数（SQL 层过滤，权威可靠）。前端会话列表、技能列表均按域过滤使用（见 1.3 第 6 点）。
3. **技能注册表按域精确过滤**：`SkillRegistry.list_by_domain` 用 `s.domain == domain` 精确匹配，查不存在的域返回空列表，**不会报错**。
4. **非 case 域自动回落自由对话**：`TriggerRouter` 对非 `case` 域落到 `IntentRoutingStrategy` → 匹配不到 skill → 退回 `FreeformStrategy`，流式正常返回。这正是 kb 域「纯对话」想要的形态。

**未来接新域的扩展路径（本期不做，仅记录）**：要接 `bug` 域时，只需在后端新增 `BugSkill`（声明 `domain = "bug"`）并注册，无需改任何框架代码。前端在 `domainProfiles` 加一项 profile 即可。

---

## 四、实施顺序（建议）

| 阶段 | 内容 | 关键文件 | 状态 |
|---|---|---|---|
| P0 | 前端上下文分桶（aiContextStore） | 2.1 | `[x]` 已实现 |
| P1 | 前端 domain 参数化 + 分桶（useChat / LayoutChat） | 2.2、2.4 | `[x]` 已实现 |
| P2 | 前端 Domain Profile 动态化（useChatPanel + domainProfiles.ts） | 2.3 | `[x]` 已实现 |
| P3 | 独立 kb 页面（ai-chat/index.vue + ChatPanel.vue） | 2.5、2.6 | `[x]` 已实现 |
| P4 | 前端类型扩展（types.ts 新增 DomainProfile 类型） | 2.7 | `[x]` 已实现 |

> 全部为纯前端改动，后端零改动。每个阶段可独立编译/运行验证。
> bug/exec 域仅在前端 `domainProfiles` 预留配置位，不建 skill、不建 Agent、不改后端。

---

## 五、风险与兼容性

1. **`SkillInfo.domain` 误改数组风险**：后端 `SkillInfoVO.domain` 仍是单值字符串，前端若升级为 `domains: string[]`，`ChatSkillAPI.list()` 返回的对象将缺失 `domains` 字段，技能列表全部 `undefined`。**必须保持单值 `string`**。
2. **`createSession` 写死 `"case"` 未放开**：若不参数化，kb 页新建会话仍打 `case` 标签，会话 domain 标签错误。**必须放开为 `currentDomain`**。
3. **流式回写竞态**：跨域切换发生在流式返回期间时，若用实时 `currentDomain` 回写会写错桶。必须绑定「发起时 domain 快照」（见 2.2 第 6 点）。
4. **非 case 域为自由对话**：kb/bug/exec 域在后端无对应 skill，会回落 Freeform 自由对话（无工具、无卡片）。这是本期预期行为，属架构扩展的「空实现」状态。

---

## 六、已决事项

1. kb 页最终形态：**无工作区树，纯对话**（仅保留 ChatPanel）。
2. LayoutChat 切域：**软隔离状态桶**（每域独立保存/恢复会话与输入状态，不做强制新会话）。
3. 会话列表：**按域过滤 domain**，每个域只展示本域历史会话（后端 SQL 层过滤）。
4. 头部标题：**保持「AI 助手」不变**，不按域显示。
5. bug/exec 域：**本期不落地**，仅前端预留 profile 扩展点，后端零改动。
6. 欢迎副标题：**welcomeSubtitle 按域展示**（LayoutChat 与 ChatPanel 两个面板均展示）。
7. AI Chat 独立页：**隐藏 LayoutChat 浮标与面板**，避免与页内 ChatPanel 重复。
