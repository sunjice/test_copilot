-- ============================================================
-- test-copilot AITC + AI 业务表初始化脚本 (PostgreSQL 16+)
-- 
-- 基于真实数据库 (PostgreSQL 16.14, 2026-08-12) 导出，100% 一致。
-- 依赖：先执行 youlai-admin.sql 建好 sys_* 基础表
-- 
-- 使用方法：
--   psql -h <host> -U youlai -d youlai_admin -f youlai-aitc.sql
-- ============================================================

-- 按依赖顺序 DROP 所有 AITC 表
DROP TABLE IF EXISTS chat_drafts CASCADE;
DROP TABLE IF EXISTS ai_tc_review_records CASCADE;
DROP TABLE IF EXISTS ai_tc_task_items CASCADE;
DROP TABLE IF EXISTS ai_tc_tasks CASCADE;
DROP TABLE IF EXISTS ai_tc_scripts CASCADE;
DROP TABLE IF EXISTS ai_tc_cases CASCADE;
DROP TABLE IF EXISTS ai_tc_suites CASCADE;
DROP TABLE IF EXISTS ai_tc_samples CASCADE;
DROP TABLE IF EXISTS ai_tc_specs CASCADE;
DROP TABLE IF EXISTS ai_tc_projects CASCADE;
DROP TABLE IF EXISTS ai_llm_logs CASCADE;
DROP TABLE IF EXISTS ai_usage_logs CASCADE;
DROP TABLE IF EXISTS ai_run_events CASCADE;
DROP TABLE IF EXISTS ai_usage_daily CASCADE;
DROP TABLE IF EXISTS chat_messages CASCADE;
DROP TABLE IF EXISTS chat_sessions CASCADE;
DROP TABLE IF EXISTS ai_tc_ai_configs CASCADE;
DROP TABLE IF EXISTS retrieval_synonyms CASCADE;

-- ----------------------------
-- 建表语句 (DDL)
-- ----------------------------

-- ==================== ai_run_events ====================
CREATE TABLE ai_run_events (
    id                        bigint PRIMARY KEY,
    session_id                bigint,
    message_id                bigint,
    seq                       integer NOT NULL DEFAULT 0,
    event_type                varchar(40) NOT NULL DEFAULT 'llm_call',
    module                    varchar(50) NOT NULL DEFAULT 'chat',
    action                    varchar(80) NOT NULL DEFAULT '',
    tool_call_id              varchar(128),
    provider                  varchar(50) NOT NULL DEFAULT '',
    api_base                  varchar(255) NOT NULL DEFAULT '',
    model                     varchar(100) NOT NULL DEFAULT '',
    status                    varchar(20) NOT NULL DEFAULT 'success',
    error_msg                 text,
    request_messages          jsonb,
    response_raw              text,
    response_json             jsonb,
    prompt_tokens             integer NOT NULL DEFAULT 0,
    prompt_cache_hit_tokens   integer NOT NULL DEFAULT 0,
    prompt_cache_miss_tokens  integer NOT NULL DEFAULT 0,
    prompt_cache_write_tokens integer NOT NULL DEFAULT 0,
    completion_tokens         integer NOT NULL DEFAULT 0,
    reasoning_tokens          integer NOT NULL DEFAULT 0,
    duration_ms               integer NOT NULL DEFAULT 0,
    create_time               timestamp NOT NULL DEFAULT now()
);
CREATE INDEX idx_run_events_message ON ai_run_events (message_id, seq);
CREATE INDEX idx_run_events_session ON ai_run_events (session_id, create_time);
CREATE INDEX idx_run_events_time ON ai_run_events (create_time);
CREATE INDEX idx_run_events_model ON ai_run_events (provider, model);
COMMENT ON TABLE ai_run_events IS 'AI 运行事件（平铺轨迹 + 用量）';
COMMENT ON COLUMN ai_run_events.id IS '主键ID';
COMMENT ON COLUMN ai_run_events.session_id IS '关联会话ID（一个对话界面）';
COMMENT ON COLUMN ai_run_events.message_id IS '关联消息ID（一轮问答）';
COMMENT ON COLUMN ai_run_events.seq IS '轮内单调递增序号';
COMMENT ON COLUMN ai_run_events.event_type IS '事件类型 turn_start/user_message/llm_call/tool_call/tool_result/assistant_message/turn_end';
COMMENT ON COLUMN ai_run_events.module IS '来源模块 chat/task_engine/agent';
COMMENT ON COLUMN ai_run_events.action IS '动作名称';
COMMENT ON COLUMN ai_run_events.tool_call_id IS '工具调用 ID（关联 tool_call 与 tool_result）';
COMMENT ON COLUMN ai_run_events.provider IS '供应商 deepseek/openai/local';
COMMENT ON COLUMN ai_run_events.api_base IS '接口地址 base_url';
COMMENT ON COLUMN ai_run_events.model IS '模型名称';
COMMENT ON COLUMN ai_run_events.status IS '调用状态 success/error/timeout';
COMMENT ON COLUMN ai_run_events.error_msg IS '错误信息';
COMMENT ON COLUMN ai_run_events.request_messages IS '请求 messages 完整 JSON';
COMMENT ON COLUMN ai_run_events.response_raw IS 'LLM 原始返回文本';
COMMENT ON COLUMN ai_run_events.response_json IS 'LLM 结构化返回（JSON parse 后）';
COMMENT ON COLUMN ai_run_events.prompt_tokens IS '输入 token 总数';
COMMENT ON COLUMN ai_run_events.prompt_cache_hit_tokens IS '缓存命中 token';
COMMENT ON COLUMN ai_run_events.prompt_cache_miss_tokens IS '缓存未命中 token';
COMMENT ON COLUMN ai_run_events.prompt_cache_write_tokens IS '缓存写入 token';
COMMENT ON COLUMN ai_run_events.completion_tokens IS '输出 token 总数';
COMMENT ON COLUMN ai_run_events.reasoning_tokens IS '思考过程 token（reasoner 模型）';
COMMENT ON COLUMN ai_run_events.duration_ms IS '耗时(毫秒)';
COMMENT ON COLUMN ai_run_events.create_time IS '创建时间';

-- ==================== ai_usage_daily ====================
CREATE TABLE ai_usage_daily (
    id                        bigint PRIMARY KEY,
    stat_date                 date NOT NULL,
    provider                  varchar(50) NOT NULL DEFAULT '',
    model                     varchar(100) NOT NULL DEFAULT '',
    api_base                  varchar(255) NOT NULL DEFAULT '',
    request_count             integer NOT NULL DEFAULT 0,
    prompt_tokens             integer NOT NULL DEFAULT 0,
    prompt_cache_hit_tokens   integer NOT NULL DEFAULT 0,
    prompt_cache_miss_tokens  integer NOT NULL DEFAULT 0,
    prompt_cache_write_tokens integer NOT NULL DEFAULT 0,
    completion_tokens         integer NOT NULL DEFAULT 0,
    reasoning_tokens          integer NOT NULL DEFAULT 0,
    cost_cny                  numeric(14,6) NOT NULL DEFAULT 0,
    create_time               timestamp NOT NULL DEFAULT now(),
    CONSTRAINT uq_usage_daily_key UNIQUE (stat_date, provider, model, api_base)
);
CREATE INDEX idx_usage_daily_date ON ai_usage_daily (stat_date);
COMMENT ON TABLE ai_usage_daily IS 'AI 按日用量汇总表';
COMMENT ON COLUMN ai_usage_daily.id IS '主键ID';
COMMENT ON COLUMN ai_usage_daily.stat_date IS '统计日期';
COMMENT ON COLUMN ai_usage_daily.provider IS '供应商';
COMMENT ON COLUMN ai_usage_daily.model IS '模型名称';
COMMENT ON COLUMN ai_usage_daily.api_base IS '接口地址 base_url';
COMMENT ON COLUMN ai_usage_daily.request_count IS '调用次数';
COMMENT ON COLUMN ai_usage_daily.cost_cny IS '费用（人民币）';

-- ==================== ai_tc_ai_configs ====================
CREATE TABLE ai_tc_ai_configs (
    name                 varchar(128) NOT NULL,
    provider             varchar(32) NOT NULL DEFAULT 'openai_compat',
    api_base             varchar(256) NOT NULL,
    api_key              varchar(512) NOT NULL,
    model                varchar(64) NOT NULL,
    temperature          double precision NOT NULL DEFAULT 0.3,
    max_tokens           integer NOT NULL DEFAULT 4096,
    scenes               jsonb,
    is_default           smallint NOT NULL DEFAULT 0,
    status               smallint NOT NULL DEFAULT 1,
    remark               varchar(512),
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0
);
COMMENT ON TABLE ai_tc_ai_configs IS 'AI 配置表（无 ORM 模型，代码仅通过 ai_config_id 字段引用）';
COMMENT ON COLUMN ai_tc_ai_configs.id IS '主键ID';
COMMENT ON COLUMN ai_tc_ai_configs.name IS '配置名称';
COMMENT ON COLUMN ai_tc_ai_configs.provider IS '提供商 openai_compat/deepseek';
COMMENT ON COLUMN ai_tc_ai_configs.api_base IS 'API 端点';
COMMENT ON COLUMN ai_tc_ai_configs.api_key IS 'API 密钥';
COMMENT ON COLUMN ai_tc_ai_configs.model IS '模型名称';
COMMENT ON COLUMN ai_tc_ai_configs.temperature IS '温度参数';
COMMENT ON COLUMN ai_tc_ai_configs.max_tokens IS '最大 token';
COMMENT ON COLUMN ai_tc_ai_configs.scenes IS '适用场景列表';
COMMENT ON COLUMN ai_tc_ai_configs.is_default IS '是否默认配置 0-否 1-是';
COMMENT ON COLUMN ai_tc_ai_configs.status IS '状态 0-停用 1-启用';
COMMENT ON COLUMN ai_tc_ai_configs.remark IS '备注';
COMMENT ON COLUMN ai_tc_ai_configs.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_ai_configs.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_ai_configs.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_projects ====================
CREATE TABLE ai_tc_projects (
    name                 varchar(128) NOT NULL,
    prefix               varchar(64) NOT NULL,
    description          text,
    last_sync_time       varchar(32),
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0,
    testlink_project_id  bigint,
    CONSTRAINT uq_ai_tc_projects_prefix UNIQUE (prefix)
);
COMMENT ON TABLE ai_tc_projects IS '测试项目表';
COMMENT ON COLUMN ai_tc_projects.id IS '主键ID';
COMMENT ON COLUMN ai_tc_projects.name IS '项目名称';
COMMENT ON COLUMN ai_tc_projects.prefix IS '项目标识';
COMMENT ON COLUMN ai_tc_projects.description IS '项目描述';
COMMENT ON COLUMN ai_tc_projects.testlink_project_id IS 'TestLink testproject id';
COMMENT ON COLUMN ai_tc_projects.last_sync_time IS '最后导入时间';
COMMENT ON COLUMN ai_tc_projects.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_projects.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_projects.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_suites ====================
CREATE TABLE ai_tc_suites (
    project_id           bigint NOT NULL,
    parent_id            bigint NOT NULL DEFAULT 0,
    tree_path            varchar(512) NOT NULL DEFAULT '',
    name                 varchar(128) NOT NULL,
    sort_order           integer NOT NULL DEFAULT 0,
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0,
    testlink_suite_id    bigint,
    description          text
);
ALTER TABLE ai_tc_suites ADD CONSTRAINT fk_ai_tc_suites_project_id FOREIGN KEY (project_id) REFERENCES ai_tc_projects(id);
CREATE INDEX idx_aitc_suite_project ON ai_tc_suites (project_id, is_deleted);
CREATE INDEX idx_aitc_suite_parent ON ai_tc_suites (parent_id);
CREATE INDEX idx_aitc_suite_tree ON ai_tc_suites (tree_path);
COMMENT ON TABLE ai_tc_suites IS '测试套件表';
COMMENT ON COLUMN ai_tc_suites.id IS '主键ID';
COMMENT ON COLUMN ai_tc_suites.project_id IS '项目ID';
COMMENT ON COLUMN ai_tc_suites.parent_id IS '父套件ID，0 为根';
COMMENT ON COLUMN ai_tc_suites.tree_path IS '祖先路径如 0,1,5';
COMMENT ON COLUMN ai_tc_suites.name IS '套件名称';
COMMENT ON COLUMN ai_tc_suites.description IS '套件描述';
COMMENT ON COLUMN ai_tc_suites.sort_order IS '排序';
COMMENT ON COLUMN ai_tc_suites.testlink_suite_id IS 'TestLink testsuite id';
COMMENT ON COLUMN ai_tc_suites.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_suites.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_suites.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_cases ====================
CREATE TABLE ai_tc_cases (
    project_id           bigint NOT NULL,
    suite_id             bigint NOT NULL,
    external_id          varchar(64),
    name                 varchar(256) NOT NULL,
    summary              text,
    preconditions        text,
    topo                 varchar(512),
    test_data            text,
    steps                jsonb,
    importance           smallint NOT NULL DEFAULT 2,
    is_core              smallint NOT NULL DEFAULT 0,
    core_reason          varchar(512),
    core_source          smallint,
    review_status        smallint NOT NULL DEFAULT 0,
    script_count         integer NOT NULL DEFAULT 0,
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0,
    is_sample            smallint NOT NULL DEFAULT 0,
    purpose              varchar(256),
    testlink_tc_id       bigint,
    testlink_version_id  bigint,
    sync_status          smallint NOT NULL DEFAULT 0,
    synced_version       integer,
    synced_hash          varchar(64),
    synced_snapshot      jsonb,
    last_sync_at         timestamp,
    last_push_at         timestamp,
    testlink_modified_at timestamp,
    testlink_modifier    varchar(128),
    auto_sync            smallint NOT NULL DEFAULT 1,
    sync_error           text,
    index_hash           varchar(64),
    indexed_at           timestamp,
    CONSTRAINT uq_ai_tc_cases_project_id_external_id UNIQUE (project_id, external_id)
);
ALTER TABLE ai_tc_cases ADD CONSTRAINT fk_ai_tc_cases_project_id FOREIGN KEY (project_id) REFERENCES ai_tc_projects(id);
ALTER TABLE ai_tc_cases ADD CONSTRAINT fk_ai_tc_cases_suite_id FOREIGN KEY (suite_id) REFERENCES ai_tc_suites(id);
CREATE INDEX idx_aitc_case_suite ON ai_tc_cases (suite_id, is_deleted);
CREATE INDEX idx_aitc_case_project_core ON ai_tc_cases (project_id, is_core);
CREATE INDEX idx_aitc_case_review ON ai_tc_cases (project_id, review_status);
CREATE INDEX idx_aitc_case_tl_tc ON ai_tc_cases (testlink_tc_id);
CREATE INDEX idx_aitc_case_sync_status ON ai_tc_cases (project_id, sync_status);
COMMENT ON TABLE ai_tc_cases IS '测试用例表';
COMMENT ON COLUMN ai_tc_cases.id IS '主键ID';
COMMENT ON COLUMN ai_tc_cases.project_id IS '项目ID';
COMMENT ON COLUMN ai_tc_cases.suite_id IS '所属套件ID';
COMMENT ON COLUMN ai_tc_cases.external_id IS 'TestLink用例编号';
COMMENT ON COLUMN ai_tc_cases.name IS '英文标识名';
COMMENT ON COLUMN ai_tc_cases.purpose IS '测试目的/中文用例名称';
COMMENT ON COLUMN ai_tc_cases.summary IS '测试思想';
COMMENT ON COLUMN ai_tc_cases.preconditions IS '前置条件';
COMMENT ON COLUMN ai_tc_cases.topo IS '测试Topo';
COMMENT ON COLUMN ai_tc_cases.test_data IS '测试数据';
COMMENT ON COLUMN ai_tc_cases.steps IS '测试步骤 [{action, expected, step_no}]';
COMMENT ON COLUMN ai_tc_cases.importance IS '级别 1-低 2-中 3-高';
COMMENT ON COLUMN ai_tc_cases.is_core IS '是否核心用例 0-否 1-是';
COMMENT ON COLUMN ai_tc_cases.core_reason IS '标记为核心的原因';
COMMENT ON COLUMN ai_tc_cases.core_source IS '核心来源 1-AI挑选 2-人工标记';
COMMENT ON COLUMN ai_tc_cases.is_sample IS '是否样本用例 0-否 1-是';
COMMENT ON COLUMN ai_tc_cases.review_status IS '审核状态 0-未审核 1-已审核';
COMMENT ON COLUMN ai_tc_cases.script_count IS '关联脚本数量（冗余计数）';
COMMENT ON COLUMN ai_tc_cases.testlink_tc_id IS 'TestLink 内部 testcase_id';
COMMENT ON COLUMN ai_tc_cases.testlink_version_id IS 'TestLink tcversion_id';
COMMENT ON COLUMN ai_tc_cases.sync_status IS '同步状态';
COMMENT ON COLUMN ai_tc_cases.synced_version IS '上次同步时的 TestLink version';
COMMENT ON COLUMN ai_tc_cases.synced_hash IS '上次同步内容的 SHA256';
COMMENT ON COLUMN ai_tc_cases.synced_snapshot IS '上次同步时的字段快照';
COMMENT ON COLUMN ai_tc_cases.last_sync_at IS '上次同步时间';
COMMENT ON COLUMN ai_tc_cases.last_push_at IS '上次反写时间';
COMMENT ON COLUMN ai_tc_cases.testlink_modified_at IS 'TestLink 端 modification_ts';
COMMENT ON COLUMN ai_tc_cases.testlink_modifier IS 'TestLink 端最后修改人';
COMMENT ON COLUMN ai_tc_cases.auto_sync IS '修改后是否自动反写 0-否 1-是';
COMMENT ON COLUMN ai_tc_cases.sync_error IS '最近一次反写失败原因';
COMMENT ON COLUMN ai_tc_cases.index_hash IS '索引内容 SHA256';
COMMENT ON COLUMN ai_tc_cases.indexed_at IS '最近一次索引时间';
COMMENT ON COLUMN ai_tc_cases.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_cases.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_cases.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_samples ====================
CREATE TABLE ai_tc_samples (
    project_id           bigint,
    sample_type          varchar(16) NOT NULL,
    name                 varchar(128) NOT NULL,
    language             varchar(32),
    framework            varchar(32) DEFAULT 'pytest',
    content              text NOT NULL,
    description          varchar(512),
    status               smallint NOT NULL DEFAULT 1,
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0
);
ALTER TABLE ai_tc_samples ADD CONSTRAINT fk_ai_tc_samples_project_id FOREIGN KEY (project_id) REFERENCES ai_tc_projects(id);
CREATE INDEX idx_aitc_sample_type ON ai_tc_samples (sample_type, project_id);
COMMENT ON TABLE ai_tc_samples IS '样本库表';
COMMENT ON COLUMN ai_tc_samples.id IS '主键ID';
COMMENT ON COLUMN ai_tc_samples.project_id IS '项目ID，NULL 为通用';
COMMENT ON COLUMN ai_tc_samples.sample_type IS '类型 case-用例样本 script-脚本样本';
COMMENT ON COLUMN ai_tc_samples.name IS '样本名称';
COMMENT ON COLUMN ai_tc_samples.language IS '语言（脚本样本用）';
COMMENT ON COLUMN ai_tc_samples.framework IS '框架';
COMMENT ON COLUMN ai_tc_samples.content IS '样本内容';
COMMENT ON COLUMN ai_tc_samples.description IS '样本描述';
COMMENT ON COLUMN ai_tc_samples.status IS '状态 0-停用 1-启用';
COMMENT ON COLUMN ai_tc_samples.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_samples.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_samples.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_scripts ====================
CREATE TABLE ai_tc_scripts (
    case_id              bigint NOT NULL,
    language             varchar(32) NOT NULL DEFAULT 'python',
    framework            varchar(32) NOT NULL DEFAULT 'pytest',
    content              text NOT NULL,
    source               smallint NOT NULL DEFAULT 1,
    task_item_id         bigint,
    version              integer NOT NULL DEFAULT 1,
    status               smallint NOT NULL DEFAULT 1,
    reviewed_by          varchar(64),
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0
);
ALTER TABLE ai_tc_scripts ADD CONSTRAINT fk_ai_tc_scripts_case_id FOREIGN KEY (case_id) REFERENCES ai_tc_cases(id);
ALTER TABLE ai_tc_scripts ADD CONSTRAINT fk_ai_tc_scripts_task_item_id FOREIGN KEY (task_item_id) REFERENCES ai_tc_task_items(id);
CREATE INDEX idx_aitc_script_case ON ai_tc_scripts (case_id, is_deleted);
COMMENT ON TABLE ai_tc_scripts IS '测试脚本表';
COMMENT ON COLUMN ai_tc_scripts.id IS '主键ID';
COMMENT ON COLUMN ai_tc_scripts.case_id IS '用例ID';
COMMENT ON COLUMN ai_tc_scripts.language IS '脚本语言';
COMMENT ON COLUMN ai_tc_scripts.framework IS '测试框架';
COMMENT ON COLUMN ai_tc_scripts.content IS '脚本内容';
COMMENT ON COLUMN ai_tc_scripts.source IS '来源 1-AI生成 2-人工录入';
COMMENT ON COLUMN ai_tc_scripts.task_item_id IS '来源任务明细ID';
COMMENT ON COLUMN ai_tc_scripts.version IS '版本号';
COMMENT ON COLUMN ai_tc_scripts.status IS '状态 1-草稿 2-已入库';
COMMENT ON COLUMN ai_tc_scripts.reviewed_by IS '审核人';
COMMENT ON COLUMN ai_tc_scripts.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_scripts.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_scripts.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_specs ====================
CREATE TABLE ai_tc_specs (
    id                   bigint PRIMARY KEY,
    project_id           bigint,
    suite_id             bigint,
    task_type            varchar(32) NOT NULL,
    spec_type            varchar(32) NOT NULL,
    content              text NOT NULL,
    sort_order           integer DEFAULT 0,
    status               smallint DEFAULT 1,
    is_deleted           smallint DEFAULT 0,
    create_time          timestamp DEFAULT CURRENT_TIMESTAMP,
    update_time          timestamp DEFAULT CURRENT_TIMESTAMP
);
ALTER TABLE ai_tc_specs ADD CONSTRAINT fk_ai_tc_specs_project_id FOREIGN KEY (project_id) REFERENCES ai_tc_projects(id);
ALTER TABLE ai_tc_specs ADD CONSTRAINT fk_ai_tc_specs_suite_id FOREIGN KEY (suite_id) REFERENCES ai_tc_suites(id);
CREATE INDEX idx_aitc_spec_task ON ai_tc_specs (task_type, spec_type);
CREATE INDEX idx_aitc_spec_project ON ai_tc_specs (project_id, task_type);
CREATE INDEX idx_aitc_spec_suite ON ai_tc_specs (suite_id);
COMMENT ON TABLE ai_tc_specs IS 'AI 规范表';
COMMENT ON COLUMN ai_tc_specs.id IS '主键ID';
COMMENT ON COLUMN ai_tc_specs.project_id IS '项目ID，NULL 为全局通用';
COMMENT ON COLUMN ai_tc_specs.suite_id IS '模块ID';
COMMENT ON COLUMN ai_tc_specs.task_type IS '任务类型 core_select/case_review/script_gen';
COMMENT ON COLUMN ai_tc_specs.spec_type IS '规范类型 general/module_specific/common_issues';
COMMENT ON COLUMN ai_tc_specs.content IS '规范内容（Markdown）';
COMMENT ON COLUMN ai_tc_specs.sort_order IS '排序号';
COMMENT ON COLUMN ai_tc_specs.status IS '状态 0-停用 1-启用';
COMMENT ON COLUMN ai_tc_specs.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_specs.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_specs.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_tasks ====================
CREATE TABLE ai_tc_tasks (
    task_type            varchar(32) NOT NULL,
    project_id           bigint NOT NULL,
    suite_id             bigint NOT NULL,
    sample_ids           jsonb,
    ai_config_id         bigint,
    model                varchar(64),
    status               smallint NOT NULL DEFAULT 0,
    total_count          integer NOT NULL DEFAULT 0,
    done_count           integer NOT NULL DEFAULT 0,
    input_tokens         integer NOT NULL DEFAULT 0,
    output_tokens        integer NOT NULL DEFAULT 0,
    error_msg            text,
    create_by            varchar(64),
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0,
    spec_ids             jsonb,
    session_id           bigint
);
ALTER TABLE ai_tc_tasks ADD CONSTRAINT fk_ai_tc_tasks_ai_config_id FOREIGN KEY (ai_config_id) REFERENCES ai_tc_ai_configs(id);
ALTER TABLE ai_tc_tasks ADD CONSTRAINT fk_ai_tc_tasks_project_id FOREIGN KEY (project_id) REFERENCES ai_tc_projects(id);
ALTER TABLE ai_tc_tasks ADD CONSTRAINT fk_ai_tc_tasks_suite_id FOREIGN KEY (suite_id) REFERENCES ai_tc_suites(id);
CREATE INDEX idx_aitc_task_project ON ai_tc_tasks (project_id, task_type);
COMMENT ON TABLE ai_tc_tasks IS 'AI 任务表';
COMMENT ON COLUMN ai_tc_tasks.id IS '主键ID';
COMMENT ON COLUMN ai_tc_tasks.task_type IS '任务类型 core_select/case_review/script_gen';
COMMENT ON COLUMN ai_tc_tasks.project_id IS '项目ID';
COMMENT ON COLUMN ai_tc_tasks.suite_id IS '目标套件ID';
COMMENT ON COLUMN ai_tc_tasks.sample_ids IS '使用的样本ID列表';
COMMENT ON COLUMN ai_tc_tasks.spec_ids IS '使用的规范ID列表';
COMMENT ON COLUMN ai_tc_tasks.ai_config_id IS 'AI配置ID';
COMMENT ON COLUMN ai_tc_tasks.model IS '实际使用的模型名（快照）';
COMMENT ON COLUMN ai_tc_tasks.status IS '状态 0-排队 1-运行中 2-已完成 3-失败 4-已确认';
COMMENT ON COLUMN ai_tc_tasks.total_count IS '总用例数';
COMMENT ON COLUMN ai_tc_tasks.done_count IS '已完成数';
COMMENT ON COLUMN ai_tc_tasks.input_tokens IS '输入token数';
COMMENT ON COLUMN ai_tc_tasks.output_tokens IS '输出token数';
COMMENT ON COLUMN ai_tc_tasks.session_id IS '创建任务的会话ID';
COMMENT ON COLUMN ai_tc_tasks.error_msg IS '错误信息';
COMMENT ON COLUMN ai_tc_tasks.create_by IS '创建人';
COMMENT ON COLUMN ai_tc_tasks.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_tasks.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_tasks.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_task_items ====================
CREATE TABLE ai_tc_task_items (
    task_id              bigint NOT NULL,
    case_id              bigint NOT NULL,
    case_name            varchar(256) NOT NULL,
    output               jsonb,
    item_status          smallint NOT NULL DEFAULT 0,
    confirm_status       smallint NOT NULL DEFAULT 0,
    final_content        text,
    reviewed_by          varchar(64),
    review_time          varchar(32),
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0
);
ALTER TABLE ai_tc_task_items ADD CONSTRAINT fk_ai_tc_task_items_task_id FOREIGN KEY (task_id) REFERENCES ai_tc_tasks(id);
ALTER TABLE ai_tc_task_items ADD CONSTRAINT fk_ai_tc_task_items_case_id FOREIGN KEY (case_id) REFERENCES ai_tc_cases(id);
COMMENT ON TABLE ai_tc_task_items IS 'AI 任务明细表';
COMMENT ON COLUMN ai_tc_task_items.id IS '主键ID';
COMMENT ON COLUMN ai_tc_task_items.task_id IS '任务ID';
COMMENT ON COLUMN ai_tc_task_items.case_id IS '用例ID';
COMMENT ON COLUMN ai_tc_task_items.case_name IS '用例名称（快照）';
COMMENT ON COLUMN ai_tc_task_items.output IS 'AI输出结果';
COMMENT ON COLUMN ai_tc_task_items.item_status IS '明细状态 0-待处理 1-成功 2-失败';
COMMENT ON COLUMN ai_tc_task_items.confirm_status IS '确认状态 0-待确认 1-采纳 2-忽略 3-编辑采纳';
COMMENT ON COLUMN ai_tc_task_items.final_content IS '人工修改后的最终内容';
COMMENT ON COLUMN ai_tc_task_items.reviewed_by IS '审核人';
COMMENT ON COLUMN ai_tc_task_items.review_time IS '审核时间';
COMMENT ON COLUMN ai_tc_task_items.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_task_items.update_time IS '更新时间';
COMMENT ON COLUMN ai_tc_task_items.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== ai_tc_review_records ====================
CREATE TABLE ai_tc_review_records (
    id                   integer PRIMARY KEY,
    task_id              integer NOT NULL,
    task_item_id         integer NOT NULL,
    case_id              integer,
    review_action        varchar(32) NOT NULL,
    field_name           varchar(128),
    before_value         text,
    after_value          text,
    reviewer             varchar(64),
    reviewer_ip          varchar(64),
    review_time          timestamp,
    memo                 text,
    create_time          timestamp NOT NULL DEFAULT now(),
    update_time          timestamp NOT NULL DEFAULT now()
);
ALTER TABLE ai_tc_review_records ADD CONSTRAINT fk_ai_tc_review_records_task_id FOREIGN KEY (task_id) REFERENCES ai_tc_tasks(id);
ALTER TABLE ai_tc_review_records ADD CONSTRAINT fk_ai_tc_review_records_task_item_id FOREIGN KEY (task_item_id) REFERENCES ai_tc_task_items(id);
ALTER TABLE ai_tc_review_records ADD CONSTRAINT fk_ai_tc_review_records_case_id FOREIGN KEY (case_id) REFERENCES ai_tc_cases(id);
CREATE INDEX idx_aitc_review_task ON ai_tc_review_records (task_id);
CREATE INDEX idx_aitc_review_item ON ai_tc_review_records (task_item_id);
CREATE INDEX idx_aitc_review_case ON ai_tc_review_records (case_id);
COMMENT ON TABLE ai_tc_review_records IS '审核记录表';
COMMENT ON COLUMN ai_tc_review_records.id IS '主键ID';
COMMENT ON COLUMN ai_tc_review_records.task_id IS '任务ID';
COMMENT ON COLUMN ai_tc_review_records.task_item_id IS '任务明细ID';
COMMENT ON COLUMN ai_tc_review_records.case_id IS '用例ID';
COMMENT ON COLUMN ai_tc_review_records.review_action IS '操作 accept/ignore/edit_accept/field_accept';
COMMENT ON COLUMN ai_tc_review_records.field_name IS '审核字段名';
COMMENT ON COLUMN ai_tc_review_records.before_value IS '修改前的值';
COMMENT ON COLUMN ai_tc_review_records.after_value IS '修改后的值';
COMMENT ON COLUMN ai_tc_review_records.reviewer IS '审核人';
COMMENT ON COLUMN ai_tc_review_records.reviewer_ip IS '审核人IP';
COMMENT ON COLUMN ai_tc_review_records.review_time IS '审核时间';
COMMENT ON COLUMN ai_tc_review_records.memo IS '备注';
COMMENT ON COLUMN ai_tc_review_records.create_time IS '创建时间';
COMMENT ON COLUMN ai_tc_review_records.update_time IS '更新时间';

-- ==================== chat_sessions ====================
CREATE TABLE chat_sessions (
    title                varchar(200) NOT NULL DEFAULT '新对话',
    domain               varchar(50) NOT NULL DEFAULT 'case',
    context_json         jsonb,
    message_count        integer NOT NULL DEFAULT 0,
    is_pinned            smallint NOT NULL DEFAULT 0,
    user_id              bigint,
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now(),
    is_deleted           smallint NOT NULL DEFAULT 0
);
CREATE INDEX idx_chat_session_user ON chat_sessions (user_id, is_deleted);
CREATE INDEX idx_chat_session_domain ON chat_sessions (domain);
COMMENT ON TABLE chat_sessions IS '对话会话表';
COMMENT ON COLUMN chat_sessions.id IS '主键ID';
COMMENT ON COLUMN chat_sessions.title IS '会话标题';
COMMENT ON COLUMN chat_sessions.domain IS '会话域 case/bug/analytics';
COMMENT ON COLUMN chat_sessions.context_json IS '页面上下文快照';
COMMENT ON COLUMN chat_sessions.message_count IS '消息数量';
COMMENT ON COLUMN chat_sessions.is_pinned IS '是否置顶 0-否 1-是';
COMMENT ON COLUMN chat_sessions.user_id IS '所属用户ID';
COMMENT ON COLUMN chat_sessions.create_time IS '创建时间';
COMMENT ON COLUMN chat_sessions.update_time IS '更新时间';
COMMENT ON COLUMN chat_sessions.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== chat_messages ====================
CREATE TABLE chat_messages (
    session_id           bigint NOT NULL,
    role                 varchar(20) NOT NULL,
    msg_type             varchar(30) NOT NULL DEFAULT 'text',
    content              text NOT NULL,
    metadata_json        jsonb,
    draft_id             bigint,
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now()
);
ALTER TABLE chat_messages ADD CONSTRAINT fk_chat_messages_session_id FOREIGN KEY (session_id) REFERENCES chat_sessions(id);
CREATE INDEX idx_chat_msg_session ON chat_messages (session_id, id);
COMMENT ON TABLE chat_messages IS '对话消息表';
COMMENT ON COLUMN chat_messages.id IS '主键ID';
COMMENT ON COLUMN chat_messages.session_id IS '所属会话ID';
COMMENT ON COLUMN chat_messages.role IS '角色 user/assistant/system';
COMMENT ON COLUMN chat_messages.msg_type IS '消息类型 text/action_card/task_card/confirm_card/clarify_card/help_card';
COMMENT ON COLUMN chat_messages.content IS '消息正文（Markdown）';
COMMENT ON COLUMN chat_messages.metadata_json IS '附加数据';
COMMENT ON COLUMN chat_messages.draft_id IS '关联草稿ID';
COMMENT ON COLUMN chat_messages.create_time IS '创建时间';
COMMENT ON COLUMN chat_messages.update_time IS '更新时间';

-- ==================== chat_drafts ====================
CREATE TABLE chat_drafts (
    session_id           bigint NOT NULL,
    message_id           bigint NOT NULL,
    draft_type           varchar(30) NOT NULL,
    title                varchar(200) NOT NULL DEFAULT '',
    content_json         jsonb NOT NULL,
    status               varchar(20) NOT NULL DEFAULT 'pending',
    confirmed_by         varchar(64),
    confirmed_at         varchar(32),
    id                   bigint PRIMARY KEY,
    create_time          timestamp DEFAULT now(),
    update_time          timestamp DEFAULT now()
);
ALTER TABLE chat_drafts ADD CONSTRAINT fk_chat_drafts_session_id FOREIGN KEY (session_id) REFERENCES chat_sessions(id);
ALTER TABLE chat_drafts ADD CONSTRAINT fk_chat_drafts_message_id FOREIGN KEY (message_id) REFERENCES chat_messages(id);
CREATE INDEX idx_chat_draft_msg ON chat_drafts (message_id);
CREATE INDEX idx_chat_draft_session ON chat_drafts (session_id);
COMMENT ON TABLE chat_drafts IS '对话草稿/确认卡片表';
COMMENT ON COLUMN chat_drafts.id IS '主键ID';
COMMENT ON COLUMN chat_drafts.session_id IS '会话ID';
COMMENT ON COLUMN chat_drafts.message_id IS '关联消息ID';
COMMENT ON COLUMN chat_drafts.draft_type IS '草稿类型';
COMMENT ON COLUMN chat_drafts.title IS '标题';
COMMENT ON COLUMN chat_drafts.content_json IS '草稿内容 JSON';
COMMENT ON COLUMN chat_drafts.status IS '状态 pending/confirmed';
COMMENT ON COLUMN chat_drafts.confirmed_by IS '确认人';
COMMENT ON COLUMN chat_drafts.confirmed_at IS '确认时间';
COMMENT ON COLUMN chat_drafts.create_time IS '创建时间';
COMMENT ON COLUMN chat_drafts.update_time IS '更新时间';

-- ==================== retrieval_synonyms ====================
-- 代码通过 SynonymsManager 原生 SQL 操作此表
CREATE TABLE retrieval_synonyms (
    id                   bigint PRIMARY KEY,
    synonym_group        varchar(128) NOT NULL,
    term                 varchar(256) NOT NULL,
    is_preferred         boolean DEFAULT false,
    domain               varchar(64) DEFAULT '',
    created_at           timestamp DEFAULT now(),
    updated_at           timestamp DEFAULT now(),
    CONSTRAINT uq_retrieval_synonyms_synonym_group_term UNIQUE (synonym_group, term)
);
COMMENT ON TABLE retrieval_synonyms IS '同义词表（无 ORM 模型，代码通过原生 SQL 操作）';
COMMENT ON COLUMN retrieval_synonyms.id IS '主键ID';
COMMENT ON COLUMN retrieval_synonyms.synonym_group IS '同义词分组';
COMMENT ON COLUMN retrieval_synonyms.term IS '词条';
COMMENT ON COLUMN retrieval_synonyms.is_preferred IS '是否首选词';
COMMENT ON COLUMN retrieval_synonyms.domain IS '领域';
COMMENT ON COLUMN retrieval_synonyms.created_at IS '创建时间';
COMMENT ON COLUMN retrieval_synonyms.updated_at IS '更新时间';

-- ----------------------------
-- 种子数据
-- ----------------------------

-- Router 测试数据：项目 + 套件 + 30 条真实用例

INSERT INTO ai_tc_projects (id, name, prefix, description)
VALUES (1, 'Router', 'router', '路由器测试用例库，覆盖WAN口、LAN口、无线三大模块的功能测试');

-- WAN / LAN / Wireless 三个一级套件
INSERT INTO ai_tc_suites (id, project_id, parent_id, tree_path, name, sort_order) VALUES
(1, 1, 0, '0', 'WAN', 1),
(2, 1, 0, '0', 'LAN', 2),
(3, 1, 0, '0', 'Wireless', 3);

-- WAN 10条用例 (suite_id=1)
INSERT INTO ai_tc_cases (id, project_id, suite_id, external_id, name, importance, summary, preconditions, topo, test_data, steps, is_sample) VALUES
(1, 1, 1, 'WAN-001', 'PPPoE拨号连接建立', 3,
'验证路由器通过PPPoE拨号方式正常建立WAN口连接',
'1. WAN口已连接光猫/上级设备\n2. 已获取宽带账号和密码\n3. 路由器恢复出厂设置',
'PC -> Router(WAN) -> 光猫 -> 运营商网络',
'宽带账号: test@pppoe, 密码: 123456, MTU: 1492',
'[{"step_no":1,"action":"登录路由器管理页面，进入WAN口设置","expected":"显示WAN口配置界面"},{"step_no":2,"action":"连接类型选择PPPoE，输入宽带账号和密码","expected":"表单提交成功"},{"step_no":3,"action":"保存并等待连接建立","expected":"页面显示WAN口已连接，获取到公网IP"},{"step_no":4,"action":"使用PC访问外部网站","expected":"浏览器正常打开网页"},{"step_no":5,"action":"查看WAN口连接状态","expected":"显示连接时长、收发字节数正常增长"}]', 1),

(2, 1, 1, 'WAN-002', 'DHCP方式获取WAN口IP地址', 3,
'验证路由器通过DHCP客户端自动获取上级设备分配的WAN口IP地址',
'1. WAN口连接到启用DHCP服务的上级路由器/光猫\n2. 上级设备DHCP地址池充足',
'PC -> Router(WAN) -> 上级路由器(DHCP Server)',
'上级路由器LAN: 192.168.0.1, DHCP池: 192.168.0.100-200, 租约: 24h',
'[{"step_no":1,"action":"WAN口连接类型选择动态IP(DHCP)","expected":"配置界面正常"},{"step_no":2,"action":"保存设置，等待WAN口获取IP","expected":"WAN口成功获取IP地址、网关、DNS"},{"step_no":3,"action":"检查获取的IP是否在上级设备DHCP地址池范围内","expected":"IP在192.168.0.100-200范围内"},{"step_no":4,"action":"使用PC访问互联网","expected":"能正常上网"},{"step_no":5,"action":"重启路由器，验证IP是否重新获取","expected":"重启后WAN口IP自动获取成功"}]', 0),

(3, 1, 1, 'WAN-003', '静态IP上网配置', 3,
'验证路由器设置固定静态IP地址后能正常连接网络',
'1. 已从运营商/网管获取固定IP、掩码、网关、DNS\n2. WAN口已物理连接',
'PC -> Router(WAN) -> 上级路由器/交换机',
'IP: 10.0.0.50, 掩码: 255.255.255.0, 网关: 10.0.0.1, DNS: 8.8.8.8, 114.114.114.114',
'[{"step_no":1,"action":"WAN口连接类型选择静态IP","expected":"显示IP/掩码/网关/DNS输入框"},{"step_no":2,"action":"输入分配的IP地址、子网掩码、默认网关、DNS服务器","expected":"表单校验通过"},{"step_no":3,"action":"保存配置，等待生效","expected":"WAN口状态显示已连接"},{"step_no":4,"action":"在PC上ping WAN口网关地址","expected":"ping通网关"},{"step_no":5,"action":"访问外网网站","expected":"正常上网"}]', 0),

(4, 1, 1, 'WAN-004', 'WAN口MAC地址克隆', 2,
'验证MAC地址克隆功能，使路由器WAN口使用指定MAC地址',
'1. 路由器正常开机\n2. WAN口已连接\n3. 获知需要克隆的目标MAC地址',
'PC -> Router(WAN) -> 运营商设备',
'克隆目标MAC: AA:BB:CC:DD:EE:01, 默认MAC: 路由器原生WAN口MAC',
'[{"step_no":1,"action":"进入WAN口高级设置，找到MAC地址克隆","expected":"显示当前WAN口MAC和克隆输入框"},{"step_no":2,"action":"选择克隆本机MAC或手动输入目标MAC地址","expected":"MAC地址已填入"},{"step_no":3,"action":"保存并应用","expected":"提示保存成功"},{"step_no":4,"action":"在状态页查看WAN口当前MAC地址","expected":"显示为克隆后的MAC地址"},{"step_no":5,"action":"验证上网正常","expected":"能正常访问互联网"}]', 0),

(5, 1, 1, 'WAN-005', 'MTU值修改配置', 2,
'验证修改WAN口MTU值后网络通信是否正常',
'1. WAN口已正常连接上网\n2. 了解运营商支持的最大MTU值',
'PC -> Router(WAN) -> 互联网',
'测试MTU值: 1492(PPPoE默认), 1500(以太网默认), 1480, 1400',
'[{"step_no":1,"action":"进入WAN口高级设置，找到MTU配置项","expected":"显示当前MTU值"},{"step_no":2,"action":"将MTU值修改为1480","expected":"配置保存成功"},{"step_no":3,"action":"在PC上执行 ping -f -l 1472 外网IP 测试","expected":"ping正常，不分片"},{"step_no":4,"action":"再改为1492，重复测试","expected":"1492测试正常"},{"step_no":5,"action":"访问网页、视频等常规应用","expected":"各应用正常"}]', 0),

(6, 1, 1, 'WAN-006', '手动DNS服务器配置', 2,
'验证WAN口手动指定DNS服务器后域名解析正常',
'1. WAN口已联网\n2. 知道可用的DNS服务器地址',
'PC -> Router(WAN) -> 互联网',
'主DNS: 223.5.5.5, 备DNS: 119.29.29.29, 测试域名: www.baidu.com',
'[{"step_no":1,"action":"WAN口DNS设置选择手动","expected":"显示DNS输入框"},{"step_no":2,"action":"输入主备DNS服务器地址","expected":"输入成功"},{"step_no":3,"action":"保存配置","expected":"提示保存成功"},{"step_no":4,"action":"PC上用nslookup查询域名","expected":"使用配置的DNS服务器解析成功"},{"step_no":5,"action":"禁用主DNS后测试备DNS是否生效","expected":"备DNS接管解析"}]', 0),

(7, 1, 1, 'WAN-007', 'WAN口速率与双工模式协商', 2,
'验证WAN口速率和双工模式的自动协商及手动设置',
'1. WAN口已连接上级设备\n2. 知道上级设备支持的速率模式',
'PC -> Router(WAN) -> 上级交换机/光猫',
'可选模式: Auto, 1000M全双工, 100M全双工, 100M半双工, 10M全双工',
'[{"step_no":1,"action":"进入WAN口高级设置-端口速率","expected":"显示当前协商速率"},{"step_no":2,"action":"模式设置为自动协商","expected":"自动协商为1000M全双工(上级支持千兆)"},{"step_no":3,"action":"手动设置为100M全双工，保存","expected":"WAN口按100M全双工工作"},{"step_no":4,"action":"查看端口状态统计","expected":"速率显示100Mbps，无错误包"},{"step_no":5,"action":"恢复为自动协商","expected":"恢复正常千兆协商"}]', 0),

(8, 1, 1, 'WAN-008', '多WAN口负载均衡', 3,
'验证多WAN口同时接入时流量负载均衡功能',
'1. 路由器支持双WAN或多WAN\n2. 至少两条宽带线路已接入\n3. 两条线路均已配置上网',
'PC -> Router -> WAN1(电信线路) + WAN2(联通线路)',
'WAN1: IP 192.168.1.100, 带宽100M | WAN2: IP 192.168.2.100, 带宽50M | 负载比例: 2:1',
'[{"step_no":1,"action":"分别配置WAN1和WAN2上网参数","expected":"两个WAN口均显示已连接"},{"step_no":2,"action":"进入多WAN策略-负载均衡","expected":"显示负载均衡配置界面"},{"step_no":3,"action":"启用负载均衡，设置权重2:1","expected":"配置保存成功"},{"step_no":4,"action":"从PC发起大量并发下载请求","expected":"流量按权重比例分配至两个WAN口"},{"step_no":5,"action":"断开WAN1验证流量切换到WAN2","expected":"所有流量自动切换，业务不中断"}]', 0),

(9, 1, 1, 'WAN-009', 'WAN口断线自动重连', 3,
'验证WAN口断线后能否自动检测并重新连接',
'1. WAN口已正常连接上网\n2. 连接类型为PPPoE',
'PC -> Router(WAN) -> 光猫 -> 运营商',
'检测间隔: 30秒, 重试次数: 3次, 重试间隔: 10秒',
'[{"step_no":1,"action":"确认WAN口当前在线","expected":"状态显示已连接"},{"step_no":2,"action":"拔掉WAN口网线模拟物理断线","expected":"WAN口状态变为未连接或正在检测"},{"step_no":3,"action":"等待30秒（检测间隔）","expected":"路由器检测到断线"},{"step_no":4,"action":"重新插上网线","expected":"路由器自动发起PPPoE拨号"},{"step_no":5,"action":"验证WAN口状态恢复","expected":"WAN口重新连接成功，IP已获取"}]', 0),

(10, 1, 1, 'WAN-010', 'NAT类型与端口映射配置', 2,
'验证NAT类型配置及端口映射规则生效',
'1. WAN口已联网\n2. LAN口下有服务器需要外网访问',
'外网PC -> 互联网 -> Router(WAN) -> LAN Server(192.168.1.100:8080)',
'NAT类型: Full Cone/Symmetric | 映射: WAN口80 -> LAN 192.168.1.100:8080',
'[{"step_no":1,"action":"进入NAT/端口映射设置","expected":"显示NAT类型和端口映射列表"},{"step_no":2,"action":"添加端口映射规则: 外部80端口映射到内部192.168.1.100:8080","expected":"规则添加成功"},{"step_no":3,"action":"在外网PC浏览器访问路由器WAN口IP:80","expected":"成功访问内部服务器的8080服务"},{"step_no":4,"action":"修改NAT类型为Symmetric","expected":"配置保存"},{"step_no":5,"action":"验证P2P应用连通性","expected":"根据NAT类型表现不同穿透能力"}]', 0);

-- LAN 10条用例 (suite_id=2)
INSERT INTO ai_tc_cases (id, project_id, suite_id, external_id, name, importance, summary, preconditions, topo, test_data, steps, is_sample) VALUES
(11, 1, 2, 'LAN-001', 'DHCP服务器地址池配置', 3,
'验证LAN口DHCP服务器能为下联设备正确分配IP地址',
'1. 路由器LAN口IP已配置为192.168.1.1\n2. DHCP服务已启用',
'Router(LAN:192.168.1.1) -> PC1/PC2/手机',
'地址池: 192.168.1.100~192.168.1.200, 租约: 24h, 网关: 192.168.1.1',
'[{"step_no":1,"action":"进入DHCP服务器设置页面","expected":"显示DHCP配置，默认已启用"},{"step_no":2,"action":"设置地址池起始和结束IP","expected":"参数保存成功"},{"step_no":3,"action":"用PC连接路由器LAN口，设为自动获取IP","expected":"PC获取到192.168.1.100-200范围内的IP"},{"step_no":4,"action":"查看PC获取的网关和DNS","expected":"网关=192.168.1.1, DNS=192.168.1.1"},{"step_no":5,"action":"再连接第2台设备，验证分配不同IP","expected":"第2台设备获取到不同的IP地址"}]', 1),

(12, 1, 2, 'LAN-002', 'DHCP静态地址绑定(MAC绑定)', 3,
'验证根据MAC地址为特定设备分配固定IP地址',
'1. DHCP服务已启用\n2. 已知目标设备的MAC地址',
'Router(LAN) -> 特定PC(MAC: AA:BB:CC:DD:EE:FF)',
'绑定的MAC: AA:BB:CC:DD:EE:FF, 绑定的IP: 192.168.1.50',
'[{"step_no":1,"action":"进入DHCP静态地址绑定页面","expected":"显示已有绑定列表"},{"step_no":2,"action":"添加绑定: MAC=AA:BB:CC:DD:EE:FF, IP=192.168.1.50","expected":"绑定规则添加成功"},{"step_no":3,"action":"将该MAC设备接入网络自动获取IP","expected":"设备获取到192.168.1.50"},{"step_no":4,"action":"重启设备再次获取IP","expected":"仍然获取到192.168.1.50"},{"step_no":5,"action":"查看DHCP客户端列表","expected":"该MAC地址显示为绑定状态"}]', 0),

(13, 1, 2, 'LAN-003', 'LAN口IP网段修改', 3,
'验证修改LAN口IP地址后DHCP服务自动调整，下联设备重新入网',
'1. 原LAN口IP: 192.168.1.1\n2. PC通过DHCP获取IP在线',
'Router(LAN) -> PC',
'新LAN IP: 10.0.0.1, 新子网: 255.255.255.0, 新DHCP池: 10.0.0.100-200',
'[{"step_no":1,"action":"进入LAN口设置将IP改为10.0.0.1保存","expected":"提示修改成功，管理地址变更为10.0.0.1"},{"step_no":2,"action":"DHCP地址池自动变更为10.0.0.100-200","expected":"地址池范围跟随新网段"},{"step_no":3,"action":"PC释放旧IP并重新获取","expected":"PC获取到10.0.0.x网段IP"},{"step_no":4,"action":"PC ping新网关10.0.0.1","expected":"ping通"},{"step_no":5,"action":"浏览器访问10.0.0.1管理页面","expected":"能正常打开管理页面"}]', 0),

(14, 1, 2, 'LAN-004', '子网掩码配置验证', 2,
'验证不同子网掩码下网络容量和子网广播域',
'1. LAN口IP可修改\n2. 了解子网掩码含义',
'Router(LAN:172.16.0.1) -> PC1/PC2',
'测试掩码: 255.255.255.0(/24), 255.255.0.0(/16), 255.255.255.252(/30)',
'[{"step_no":1,"action":"设置LAN IP为172.16.0.1/24","expected":"PC获取172.16.0.x IP正常上网"},{"step_no":2,"action":"改为172.16.0.1/16","expected":"PC获取172.16.x.x IP正常"},{"step_no":3,"action":"在线PC ping 172.16.255.200地址","expected":"/16时通，/24时不通"},{"step_no":4,"action":"改为172.16.0.1/30","expected":"仅172.16.0.0-3为可用"},{"step_no":5,"action":"恢复为/24标准配置","expected":"功能恢复正常"}]', 0),

(15, 1, 2, 'LAN-005', '第二IP/从IP绑定', 2,
'验证单个LAN口绑定多个IP地址，实现多网段共存',
'1. LAN口主IP已配置\n2. 规划需要绑定的从IP网段',
'Router(LAN:192.168.1.1 + 192.168.10.1) -> 双网段PC',
'主IP: 192.168.1.1/24, 从IP1: 192.168.10.1/24',
'[{"step_no":1,"action":"进入LAN口高级设置-第二IP","expected":"显示从IP配置界面"},{"step_no":2,"action":"添加从IP: 192.168.10.1/24","expected":"从IP添加成功"},{"step_no":3,"action":"PC手动配置IP 192.168.10.100/24, 网关192.168.10.1","expected":"能ping通路由器192.168.10.1"},{"step_no":4,"action":"PC访问互联网","expected":"通过从IP网关正常上网"},{"step_no":5,"action":"主网段PC访问从网段PC","expected":"默认可以互通"}]', 0),

(16, 1, 2, 'LAN-006', 'DNS代理/转发功能', 2,
'验证路由器DNS代理功能，向LAN口设备提供DNS解析服务',
'1. WAN口已联网\n2. DHCP服务已启用',
'PC -> Router(DNS代理) -> 互联网DNS',
'路由器IP: 192.168.1.1, 上游DNS: 223.5.5.5, 测试域名: www.qq.com',
'[{"step_no":1,"action":"确认WAN口DNS设置为223.5.5.5","expected":"DNS配置确认"},{"step_no":2,"action":"PC通过DHCP获取DNS为192.168.1.1","expected":"PC的DNS服务器=192.168.1.1"},{"step_no":3,"action":"PC执行nslookup www.qq.com","expected":"路由器DNS代理成功解析域名"},{"step_no":4,"action":"添加静态域名解析: test.local->192.168.1.200","expected":"PC ping test.local解析为192.168.1.200"},{"step_no":5,"action":"断开WAN口测试内网域名解析","expected":"静态域名仍可解析，外网域名解析超时"}]', 0),

(17, 1, 2, 'LAN-007', 'ARP绑定表管理', 2,
'验证IP-MAC绑定功能，防止ARP欺骗',
'1. 有已知MAC地址的设备在线\n2. LAN口正常工作',
'Router(LAN) -> PC1/PC2 -> 交换机',
'绑定条目: 192.168.1.100<->AA:BB:CC:DD:EE:01, 192.168.1.101<->AA:BB:CC:DD:EE:02',
'[{"step_no":1,"action":"进入安全设置-ARP绑定","expected":"显示当前ARP表"},{"step_no":2,"action":"手动添加IP-MAC绑定条目并启用","expected":"绑定规则生效"},{"step_no":3,"action":"对应设备正常通信","expected":"已绑定的设备通信正常"},{"step_no":4,"action":"用未绑定的MAC地址尝试使用已绑定IP","expected":"拒绝通信或有告警"},{"step_no":5,"action":"查看系统日志","expected":"记录ARP异常告警"}]', 0),

(18, 1, 2, 'LAN-008', '链路聚合(LACP)配置', 2,
'验证多个LAN口聚合为逻辑链路，增加带宽和冗余',
'1. 路由器至少有2个可聚合的LAN口\n2. 对端交换机支持LACP',
'Router(LAN1+LAN2) -> LACP -> 交换机(LACP) -> PC',
'聚合口: LAN1+LAN2, 模式: LACP动态, 负载均衡: src-dst-ip',
'[{"step_no":1,"action":"进入端口管理-链路聚合","expected":"显示链路聚合配置"},{"step_no":2,"action":"创建聚合组选择LAN1和LAN2模式LACP","expected":"聚合组创建成功"},{"step_no":3,"action":"交换机侧同样配置LACP","expected":"两端LACP协商成功链路聚合UP"},{"step_no":4,"action":"查看聚合口状态","expected":"显示2Gbps总带宽"},{"step_no":5,"action":"拔掉LAN1网线验证无缝切换","expected":"流量不中断自动切到LAN2"}]', 0),

(19, 1, 2, 'LAN-009', 'VLAN子接口创建', 2,
'验证在LAN口上创建VLAN子接口，实现二层隔离',
'1. 路由器支持802.1Q VLAN\n2. LAN口IP已配置',
'Router(LAN,VLAN10/20) -> Trunk -> 交换机 -> VLAN10-PC/VLAN20-PC',
'VLAN10: 172.16.10.1/24, VLAN20: 172.16.20.1/24',
'[{"step_no":1,"action":"进入VLAN管理新建VLAN10","expected":"VLAN10创建成功VLAN ID=10"},{"step_no":2,"action":"为VLAN10配置接口IP: 172.16.10.1/24","expected":"VLAN10接口UP"},{"step_no":3,"action":"同样创建VLAN20配置IP: 172.16.20.1/24","expected":"VLAN20接口UP"},{"step_no":4,"action":"LAN口配置为Trunk允许VLAN10,20通过","expected":"Trunk口配置生效"},{"step_no":5,"action":"PC1(VLAN10) ping PC2(VLAN20)","expected":"跨VLAN默认不通（需路由），同VLAN互通"}]', 0),

(20, 1, 2, 'LAN-010', 'LAN口STP生成树协议配置', 2,
'验证STP/RSTP防止网络环路功能',
'1. 路由器多个LAN口连接到交换机\n2. 网络存在物理环路',
'Router(LAN1)->交换机A->交换机B->Router(LAN2), 环路',
'STP模式: RSTP, 优先级: 32768, Hello Time: 2s, Forward Delay: 15s',
'[{"step_no":1,"action":"进入STP设置启用RSTP","expected":"STP功能开启"},{"step_no":2,"action":"查看STP端口状态","expected":"环路中一个端口被阻塞"},{"step_no":3,"action":"查看STP拓扑确认根桥选举","expected":"显示桥ID最小的为根桥"},{"step_no":4,"action":"断开当前活跃链路","expected":"阻塞端口自动切换为转发状态收敛<2s"},{"step_no":5,"action":"从PC持续ping测试观察丢包","expected":"切换过程丢包数<5个"}]', 0);

-- Wireless 10条用例 (suite_id=3)
INSERT INTO ai_tc_cases (id, project_id, suite_id, external_id, name, importance, summary, preconditions, topo, test_data, steps, is_sample) VALUES
(21, 1, 3, 'WLS-001', '2.4G无线网络开启与关闭', 3,
'验证2.4G频段WiFi网络的开启、关闭及SSID广播开关',
'1. 路由器支持2.4G无线\n2. 天线已安装\n3. 有无线终端可搜索WiFi',
'Router(2.4G WiFi) <--> 手机/笔记本',
'SSID: Router-2.4G-Test, 默认开启状态, 信道: Auto',
'[{"step_no":1,"action":"进入无线设置-2.4G基本设置确认WiFi已开启","expected":"显示2.4G已启用SSID可见"},{"step_no":2,"action":"用手机搜索WiFi信号","expected":"搜索到Router-2.4G-Test信号"},{"step_no":3,"action":"关闭2.4G无线网络开关保存","expected":"提示保存成功"},{"step_no":4,"action":"手机重新扫描WiFi","expected":"Router-2.4G-Test信号消失"},{"step_no":5,"action":"重新开启2.4G无线验证恢复","expected":"手机再次搜索到该WiFi信号"}]', 1),

(22, 1, 3, 'WLS-002', 'SSID广播与隐藏设置', 2,
'验证SSID广播关闭后隐藏WiFi，及手动添加能否连接',
'1. 2.4G或5G无线已开启\n2. 知道SSID和密码',
'Router(WiFi隐藏SSID) <--> 手机',
'SSID: Hidden-WiFi, 密码: test123456, 广播: 关闭',
'[{"step_no":1,"action":"进入无线设置找到SSID广播选项","expected":"显示SSID广播开关"},{"step_no":2,"action":"关闭SSID广播保存","expected":"隐藏WiFi配置生效"},{"step_no":3,"action":"手机WiFi列表刷新","expected":"该SSID不在列表中显示"},{"step_no":4,"action":"手机上选择添加网络手动输入SSID和密码","expected":"手动添加后成功连接"},{"step_no":5,"action":"查看路由器无线客户端列表","expected":"显示已连接的手机"}]', 0),

(23, 1, 3, 'WLS-003', '无线加密方式配置 WPA2/WPA3', 3,
'验证不同加密方式(WPA2-PSK、WPA3-SAE、混合模式)的安全性配置',
'1. 无线已开启\n2. 终端设备支持WPA3（测试WPA3时）',
'Router(WiFi加密) <--> 支持WPA2的设备/支持WPA3的设备',
'WPA2密码: wp2test123, WPA3密码: wp3test456, 加密: AES',
'[{"step_no":1,"action":"设置加密方式为WPA2-PSK+AES","expected":"配置保存成功"},{"step_no":2,"action":"手机连接该WiFi输入密码","expected":"WPA2连接成功加密显示AES"},{"step_no":3,"action":"改为WPA3-SAE+AES保存","expected":"部分老设备无法连接（不支持WPA3）"},{"step_no":4,"action":"用支持WPA3的手机连接","expected":"WPA3连接成功"},{"step_no":5,"action":"改为WPA2/WPA3混合模式","expected":"WPA2和WPA3设备均能连接"}]', 0),

(24, 1, 3, 'WLS-004', '无线信道自动/手动选择', 2,
'验证无线信道自动选择和手动指定后信道生效',
'1. 无线已开启\n2. 了解当前环境信道占用情况',
'Router(2.4G WiFi) <--> WiFi分析工具',
'2.4G可选信道: 1,6,11(互不干扰), Auto-自动选择',
'[{"step_no":1,"action":"信道设置为Auto保存","expected":"路由器自动选择最佳信道"},{"step_no":2,"action":"查看当前使用的信道号","expected":"显示当前工作信道(如6)"},{"step_no":3,"action":"手动选择信道13保存","expected":"AP切换到信道13"},{"step_no":4,"action":"用WiFi分析App检测路由器信号所在信道","expected":"确认在信道13"},{"step_no":5,"action":"恢复为Auto重启WiFi","expected":"重新自动选择最佳信道"}]', 0),

(25, 1, 3, 'WLS-005', '无线发射功率调节', 2,
'验证WiFi发射功率高中低三档对信号覆盖的影响',
'1. 无线已开启\n2. 有移动终端可测试信号强度',
'Router(WiFi可变功率) <--> 手机(固定距离5m/10m)',
'功率档位: 高(100%), 中(50%), 低(25%), 测试距离: 5米/10米',
'[{"step_no":1,"action":"功率设置为高在5米外测试信号强度","expected":"手机显示信号满格或-30~-50dBm"},{"step_no":2,"action":"功率改为中同样5米测试","expected":"信号-50~-65dBm略有下降"},{"step_no":3,"action":"功率改为低5米测试","expected":"信号-65~-75dBm明显减弱"},{"step_no":4,"action":"低功率下走到10米外测试","expected":"信号更弱或断连"},{"step_no":5,"action":"恢复为高功率","expected":"信号恢复"}]', 0),

(26, 1, 3, 'WLS-006', 'WPS一键连接功能', 2,
'验证WPS按钮/PIN码方式无线快速连接功能',
'1. 无线已开启\n2. 终端设备支持WPS\n3. WPS功能已启用',
'Router(支持WPS) <--> 支持WPS的手机/打印机',
'WPS方式: PBC(按键), PIN码, 连接超时: 120秒',
'[{"step_no":1,"action":"进入无线WPS设置确认WPS已启用","expected":"WPS状态为已启用"},{"step_no":2,"action":"手机上选择WPS按钮连接方式","expected":"手机开始搜索WPS信号"},{"step_no":3,"action":"在2分钟内按下路由器的WPS按钮","expected":"WPS配对进行中"},{"step_no":4,"action":"等待连接完成","expected":"手机自动连接WiFi成功无需输入密码"},{"step_no":5,"action":"测试PIN码方式在WPS页面输入手机PIN","expected":"PIN验证通过手机连接成功"}]', 0),

(27, 1, 3, 'WLS-007', '无线MAC地址过滤/访问控制', 3,
'验证基于MAC地址的无线接入控制（白名单/黑名单）',
'1. 无线已开启\n2. 知道允许/禁止连接设备的MAC地址\n3. 至少2台设备用于测试',
'Router(MAC过滤) <--> 手机A(白名单)/手机B(黑名单)',
'白名单: 手机A的MAC, 黑名单: 手机B的MAC, 策略: 白名单模式',
'[{"step_no":1,"action":"进入无线MAC过滤设置","expected":"显示MAC过滤配置页面"},{"step_no":2,"action":"过滤模式选白名单添加手机A的MAC","expected":"白名单保存成功"},{"step_no":3,"action":"手机A尝试连接WiFi","expected":"连接成功（在白名单中）"},{"step_no":4,"action":"手机B尝试连接WiFi","expected":"无法连接（不在白名单中）"},{"step_no":5,"action":"切换为黑名单模式添加手机B MAC","expected":"手机B被拒绝连接手机A可连接"}]', 0),

(28, 1, 3, 'WLS-008', '访客网络隔离', 2,
'验证访客WiFi与主网络之间的访问隔离',
'1. 主WiFi网络已开启\n2. 访客网络功能已开启\n3. 有主网络设备和访客设备',
'Router -> 主WiFi(192.168.1.x) <--> 主设备 + 访客WiFi(192.168.10.x) <--> 访客设备',
'主网络: 192.168.1.0/24 | 访客网络: 192.168.10.0/24 | 隔离: 访客->主网络禁止',
'[{"step_no":1,"action":"进入访客网络设置开启访客WiFi","expected":"访客网络SSID开始广播"},{"step_no":2,"action":"启用访客网络隔离和禁止访客访问内网","expected":"隔离规则生效"},{"step_no":3,"action":"访客设备连接Guest WiFi主设备连接Home WiFi","expected":"两台设备均连接成功"},{"step_no":4,"action":"访客设备ping主设备IP","expected":"ping不通隔离生效"},{"step_no":5,"action":"访客设备访问外网","expected":"可以正常上网"}]', 0),

(29, 1, 3, 'WLS-009', '无线定时开关(时间计划)', 2,
'验证WiFi定时开启/关闭计划任务功能',
'1. 无线网络已开启\n2. 路由器系统时间已同步(NTP)',
'Router(WiFi定时关闭) <--> 手机',
'计划: 每日23:00关闭WiFi, 每日07:00开启WiFi',
'[{"step_no":1,"action":"进入无线计划/定时设置页面","expected":"显示定时规则配置界面"},{"step_no":2,"action":"添加规则每天23:00关闭07:00开启","expected":"定时规则保存成功"},{"step_no":3,"action":"修改系统时间到22:59等待1分钟","expected":"23:00 WiFi自动关闭信号消失"},{"step_no":4,"action":"已连接设备检查","expected":"设备自动断开WiFi"},{"step_no":5,"action":"修改系统时间到06:59等待1分钟","expected":"07:00 WiFi自动开启信号恢复"}]', 0),

(30, 1, 3, 'WLS-010', '5GHz频段独立配置', 3,
'验证5G频段WiFi的独立SSID、信道、带宽配置',
'1. 路由器支持双频(2.4G+5G)\n2. 5G天线已安装\n3. 终端设备支持5G WiFi',
'Router -> 2.4G WiFi(SSID-2G) <--> 旧手机 + 5G WiFi(SSID-5G) <--> 新手机/笔记本',
'5G SSID: Router-5G, 信道: 36, 带宽: 80MHz, 加密: WPA3-SAE',
'[{"step_no":1,"action":"进入5G无线设置页面","expected":"显示5G频段独立配置项"},{"step_no":2,"action":"设置5G SSID为Router-5G信道36带宽80MHz","expected":"配置保存成功"},{"step_no":3,"action":"用支持5G的手机搜索WiFi","expected":"搜索到Router-5G信号"},{"step_no":4,"action":"连接5G WiFi并测速","expected":"连接成功速度明显高于2.4G"},{"step_no":5,"action":"禁用2.4G仅保留5G","expected":"2.4G信号消失5G正常旧设备可能无法连接"}]', 0);

-- AI 规范表 + 种子数据
INSERT INTO ai_tc_specs (id, task_type, spec_type, content, sort_order) VALUES
(1, 'case_review', 'general', E'# 用例审核通用规范\n\n## 1. 用例名称\n- 应简洁明确，准确概括测试对象和核心场景\n- 不超过30字\n- 不应包含模糊词汇如「测试」「验证一下」等冗余前缀（系统自动补充）\n\n## 2. 测试思想（summary）\n- 应清晰说明测试策略、风险点和验证目标\n- 体现测试设计思路，而非简单重复用例名称\n- 一句话描述不清时，可分点说明测试关注点\n\n## 3. 前置条件\n- 应完整列出执行测试前必须满足的环境、数据、权限等条件\n- 采用编号列表，每项一条\n- 避免「设备正常运行」等过于笼统的表述\n\n## 4. 测试数据\n- 应明确列出测试所需的具体数据内容、格式和来源\n- 包含 IP 地址、账号密码、参数值等具体信息\n- 避免「IP地址相关参数」等空泛表述\n\n## 5. 测试Topo\n- 应描述测试的网络拓扑、服务依赖关系\n- 使用箭头或文本图表示设备连接关系\n- 标注关键设备角色和接口\n\n## 6. 测试步骤\n- 每步应包含明确的操作(action)和可验证的预期结果(expected)\n- 步骤逻辑连贯，无歧义，无断层\n- 预期结果应具体可验证，避免「OK」「成功了」等模糊表述\n- 每个步骤应有清晰的 step_no 编号', 1),
(2, 'case_review', 'module_specific', '', 2),
(3, 'case_review', 'common_issues', '', 3),
(4, 'core_select', 'general', E'# 核心用例挑选通用规范\n\n## 挑选原则\n- 覆盖核心业务流程的主路径用例优先\n- 高风险、高频率使用的功能模块用例优先\n- 边界值和异常场景的关键用例\n- 涉及安全、数据一致性、事务完整性的用例\n\n## 排除原则\n- 纯 UI 展示类用例不选\n- 与核心用例高度重复的变体酌情保留\n- 依赖外部不可控环境的用例降权\n\n## 覆盖面要求\n- 每个一级模块至少选 1 条核心用例\n- 关键模块的核心用例比例不低于 20%', 4),
(5, 'core_select', 'module_specific', '', 5),
(6, 'core_select', 'common_issues', '', 6),
(7, 'script_gen', 'general', E'# 脚本生成通用规范\n\n## 代码风格\n- 使用 pytest 框架，unittest 风格兼容\n- 函数命名：test_<被测功能>_<场景>\n- docstring 包含用例名称、步骤、预期结果\n\n## 断言要求\n- 每个步骤应有至少一个 assert\n- 断言失败信息应包含预期值和实际值\n- 关键节点使用 log 输出可观测信息\n\n## 健壮性要求\n- setup/teardown 正确处理资源释放\n- 网络超时设置合理默认值\n- 异常场景应有 try/except 处理', 7),
(8, 'script_gen', 'module_specific', '', 8),
(9, 'script_gen', 'common_issues', '', 9);

-- AITC 菜单 + 按钮权限 (从数据库直接导出)
DELETE FROM sys_role_menu WHERE menu_id >= 2826 AND menu_id <= 3100;
DELETE FROM sys_menu WHERE id >= 2826 AND id <= 3100;

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, external_url, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params)
VALUES
(3000, 0, '0', 'WorkSpace', 'C', NULL, '/aitc', 'Layout', NULL, NULL, 0, 0, 1, 2, 'el-icon-AddLocation', '', '2026-07-31T21:39:12.237250', '2026-08-05T00:57:11.552420', '[]'),
(3010, 3000, '0,3000', '用例管理', 'M', 'AITCCases', 'cases', 'aitc/case', NULL, NULL, 0, 1, 1, 1, 'el-icon-List', NULL, '2026-07-31T21:39:12.237250', '2026-08-01T23:18:29.693088', '[]'),
(3011, 3010, '0,3000,3010', '用例查询', 'B', NULL, '', NULL, 'aitc:case:list', NULL, 0, 0, 1, 1, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3012, 3010, '0,3000,3010', '用例导入', 'B', NULL, '', NULL, 'aitc:case:import', NULL, 0, 0, 1, 2, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3013, 3010, '0,3000,3010', '用例编辑', 'B', NULL, '', NULL, 'aitc:case:update', NULL, 0, 0, 1, 3, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3014, 3010, '0,3000,3010', '用例删除', 'B', NULL, '', NULL, 'aitc:case:delete', NULL, 0, 0, 1, 4, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3015, 3010, '0,3000,3010', '标记核心', 'B', NULL, '', NULL, 'aitc:case:core', NULL, 0, 0, 1, 5, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3016, 3010, '0,3000,3010', '项目查询', 'B', NULL, '', NULL, 'aitc:project:list', NULL, 0, 0, 1, 6, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3017, 3010, '0,3000,3010', '项目创建', 'B', NULL, '', NULL, 'aitc:project:create', NULL, 0, 0, 1, 7, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3018, 3010, '0,3000,3010', '项目编辑', 'B', NULL, '', NULL, 'aitc:project:update', NULL, 0, 0, 1, 8, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3019, 3010, '0,3000,3010', '项目删除', 'B', NULL, '', NULL, 'aitc:project:delete', NULL, 0, 0, 1, 9, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3020, 3000, '0,3000', '任务管理', 'M', 'AITCTask', 'tasks', 'aitc/task', NULL, NULL, 0, 1, 1, 2, 'el-icon-Collection', NULL, '2026-07-31T21:39:12.237250', '2026-08-01T23:19:03.112315', '[]'),
(3021, 3020, '0,3000,3020', '任务查询', 'B', NULL, '', NULL, 'aitc:task:list', NULL, 0, 0, 1, 1, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3022, 3020, '0,3000,3020', '创建任务', 'B', NULL, '', NULL, 'aitc:task:create', NULL, 0, 0, 1, 2, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3023, 3020, '0,3000,3020', '确认任务', 'B', NULL, '', NULL, 'aitc:task:confirm', NULL, 0, 0, 1, 3, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3024, 3010, '0,3000,3010', '标记样本', 'B', NULL, '', NULL, 'aitc:case:sample', NULL, 0, 0, 1, 10, '', NULL, '2026-08-02T14:42:51.282890', '2026-08-02T14:42:51.282890', NULL),
(3040, 3000, '0,3000', '样本库', 'M', 'AITCSample', 'samples', 'aitc/sample', NULL, NULL, 0, 1, 1, 4, 'el-icon-CreditCard', NULL, '2026-07-31T21:39:12.237250', '2026-08-01T23:19:47.274460', '[]'),
(3041, 3040, '0,3000,3040', '样本查询', 'B', NULL, '', NULL, 'aitc:sample:list', NULL, 0, 0, 1, 1, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3042, 3040, '0,3000,3040', '样本创建', 'B', NULL, '', NULL, 'aitc:sample:create', NULL, 0, 0, 1, 2, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3043, 3040, '0,3000,3040', '样本编辑', 'B', NULL, '', NULL, 'aitc:sample:update', NULL, 0, 0, 1, 3, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3044, 3040, '0,3000,3040', '样本删除', 'B', NULL, '', NULL, 'aitc:sample:delete', NULL, 0, 0, 1, 4, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3060, 3000, '0,3000', '用例审核', 'M', 'CaseReviewIndex', 'review', 'aitc/task/case-review-index', NULL, NULL, 0, 1, 0, 6, 'gitcode', NULL, '2026-07-31T21:39:12.237250', '2026-08-05T00:40:25.548695', '[]'),
(3070, 3000, '0,3000', '脚本库', 'M', 'AITCScript', 'scripts', 'aitc/script', 'aitc:script:list', NULL, 0, 1, 1, 7, 'code', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3071, 3070, '0,3000,3070', '脚本查询', 'B', NULL, '', NULL, 'aitc:script:list', NULL, 0, 0, 1, 1, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3072, 3070, '0,3000,3070', '脚本编辑', 'B', NULL, '', NULL, 'aitc:script:update', NULL, 0, 0, 1, 2, '', NULL, '2026-07-31T21:39:12.237250', '2026-07-31T21:39:12.237250', NULL),
(3080, 3000, '0,3000', '规范管理', 'M', 'AITCSpec', 'specs', 'aitc/spec', 'aitc:spec:list', NULL, 0, 1, 1, 8, 'document', '', '2026-08-01T10:52:52.561991', '2026-08-01T10:52:52.561991', NULL),
(3081, 3080, '0,3000,3080', '规范查询', 'B', NULL, '', NULL, 'aitc:spec:list', NULL, 0, 0, 1, 1, '', '', '2026-08-01T10:52:52.561991', '2026-08-01T10:52:52.561991', NULL),
(3082, 3080, '0,3000,3080', '规范创建', 'B', NULL, '', NULL, 'aitc:spec:create', NULL, 0, 0, 1, 2, '', '', '2026-08-01T10:52:52.561991', '2026-08-01T10:52:52.561991', NULL),
(3083, 3080, '0,3000,3080', '规范编辑', 'B', NULL, '', NULL, 'aitc:spec:update', NULL, 0, 0, 1, 3, '', '', '2026-08-01T10:52:52.561991', '2026-08-01T10:52:52.561991', NULL),
(3084, 3080, '0,3000,3080', '规范删除', 'B', NULL, '', NULL, 'aitc:spec:delete', NULL, 0, 0, 1, 4, '', '', '2026-08-01T10:52:52.561991', '2026-08-01T10:52:52.561991', NULL),
(3090, 3000, '0,3000', 'AI轨迹', 'M', 'AITCTrace', 'ai-trace', 'aitc/ai-trace', NULL, NULL, 0, 1, 1, 9, 'el-icon-DataLine', '', now(), now(), '[]');

-- 授权：ROOT (role_id=1) + ADMIN (role_id=2) 获取所有 AITC 菜单
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu WHERE id BETWEEN 3000 AND 3090
ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 2, id FROM sys_menu WHERE id BETWEEN 3000 AND 3090
ON CONFLICT DO NOTHING;

-- 重置序列
SELECT setval(pg_get_serial_sequence('ai_tc_projects', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_projects), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_suites', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_suites), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_cases', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_cases), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_samples', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_samples), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_ai_configs', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_ai_configs), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_tasks', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_tasks), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_task_items', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_task_items), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_scripts', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_scripts), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_review_records', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_review_records), 1));
SELECT setval(pg_get_serial_sequence('ai_tc_specs', 'id'), COALESCE((SELECT MAX(id) FROM ai_tc_specs), 1));
SELECT setval(pg_get_serial_sequence('sys_menu', 'id'), COALESCE((SELECT MAX(id) FROM sys_menu), 1));

-- ============================================================
-- youlai-aitc.sql 初始化完成
-- ============================================================
