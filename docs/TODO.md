# TODO

> 最后更新：2026-08-07
> 范围：`vue3-element-admin` + `youlai-fastapi-master`

---

## 一、前端（vue3-element-admin）

### 页面能力补齐

- [ ] 1. sample/script/spec 接入 `usePageTable`（或 `useAitcPageTable`），去掉手写分页兜底
- [ ] 2. aiContext 接入 task/script/sample 页面

### 收尾验证

- [ ] 3. `vue-tsc` 类型检查 + 页面冒烟（用例树、审核提交、SSE 聊天、任务轮询）

---

## 二、后端（youlai-fastapi-master）

### TestLink 集成（用例同步）

- [ ] 4. 阶段 0：TestLink 连通验证（需提供 URL + devKey + 样例用例编号）
  - `config.py`/`.env` 加 `TESTLINK_URL`、`TESTLINK_DEVKEY`
  - `scripts/verify_testlink.py`：拉真实用例，确认「测试目的」字段位置、`updater_login`/`modification_ts` 可用性 → 定稿 FIELD_MAP
- [ ] 5. 新建 `app/aitc/testlink/` 包
  - `client.py`（XML-RPC 封装）
  - `field_map.py`（字段映射表 + `full_external_id()` 组装）
  - `hashing.py`（canonical 序列化 + SHA256，字段范围: purpose/name/summary/preconditions/steps/importance）
  - `models.py`（`ai_tc_sync_logs` 审计表）
  - `sync_service.py`（拉取幂等 / 反写乐观锁+降级链 / 三方合并 / 回声抑制）
  - `router.py`（`POST /pull`、`POST /push`、`GET /conflicts`、`POST /conflicts/{id}/resolve`、`GET /logs`）
  - 注册进 `aitc/router.py`
- [ ] 6. `service.py`：内容字段变更自动置 `sync_status=2`（`topo`/`test_data`/AI 字段除外）
- [ ] 7. 巡检定时任务：比对 version/modification_ts，标记 `sync_status=3`（只标记不自动拉）
- [ ] 8. 前端：同步状态列、拉取/反写按钮、待反写筛选、冲突三栏处理页
- [ ] 9. Excel 导入功能下线（`import_cases` 去掉 Excel 格式解析，`CaseImportDialog.vue` + 入口按钮移除）
- [ ] 10. `开发指导手册.md` 补 testlink 域、字段映射表、同步状态机、降级链章节

### 消息存储优化

- [ ] 11. `get_message_history` 返回完整字段（`role` + `content` + `tool_calls` + `tool_call_id` + `name` + `msg_type`）
  - 当前只返回 `{role, content}`，导致 Agent 多轮对话时上一轮的工具调用上下文丢失
  - `runner.py` 中的 `tool_calls` 重建逻辑（`_build_history` L218-222）因缺少数据字段从未被触发
- [ ] 12. assistant 消息防丢失：在 SSE 流开始前创建占位记录（`status=pending`），流中更新 content，异常时标记 `status=error`
  - 当前 user 消息先入库、assistant 在 SSE 流结束后才入库，流中断时会造成 user 有记录但 assistant 丢失的不一致状态
- [ ] 13. 历史查询加 SQL 层 LIMIT/OFFSET，去掉 `get_messages(session_id)` 全量查 + 内存切片

### LangGraph 二期

- [ ] 14. 新建 `agent/graphs/`：base + core_select/case_review/script_gen 三张作业图，handler 改为薄适配层
- [ ] 15. 新建 `chat/graph.py`：LangGraph 重写 orchestrator 内部实现，保留关键词 fast path

**说明**：两层图各司其职 — 作业图编排单次任务内多节点 LLM 流程；会话图替换 orchestrator 的意图路由 + 自由对话，SSE 事件协议不变。

---

## 三、共享

- [ ] 16. 权限控制补齐（前端 `v-hasPerm` + 后端端点 `Depends(require_perm(...))`）
- [ ] 17. 测试覆盖补充（aitc/ai 域）

---

## 变更记录

| 日期 | 内容 |
|------|------|
| 2026-08-07 | 新增消息存储优化 3 项（历史字段完整性、assistant 防丢失、SQL 分页）；编号顺延 |
