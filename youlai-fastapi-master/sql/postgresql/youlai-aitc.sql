SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_table_access_method = heap;

-- Name: ai_llm_logs; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_llm_logs (
    trace_id character varying(128) DEFAULT ''''''::character varying NOT NULL,
    span_seq integer DEFAULT 0 NOT NULL,
    attempt integer DEFAULT 0 NOT NULL,
    module character varying(50) DEFAULT '''chat'''::character varying NOT NULL,
    action character varying(80) DEFAULT ''''''::character varying NOT NULL,
    session_id bigint,
    task_id bigint,
    message_id bigint,
    model character varying(100) DEFAULT ''''''::character varying NOT NULL,
    status character varying(20) DEFAULT '''success'''::character varying NOT NULL,
    error_msg text,
    messages jsonb,
    response_raw text,
    response_json jsonb,
    prompt_tokens integer DEFAULT 0 NOT NULL,
    completion_tokens integer DEFAULT 0 NOT NULL,
    duration_ms integer DEFAULT 0 NOT NULL,
    create_time timestamp without time zone DEFAULT now() NOT NULL,
    id bigint NOT NULL
);

-- Name: COLUMN ai_llm_logs.trace_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.trace_id IS '调用链 ID，同一用户动作的多次 LLM 调用共享';

-- Name: COLUMN ai_llm_logs.span_seq; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.span_seq IS '调用链内序号，从 0 开始';

-- Name: COLUMN ai_llm_logs.attempt; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.attempt IS '重试次数';

-- Name: COLUMN ai_llm_logs.module; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.module IS '来源模块 chat/task_engine';

-- Name: COLUMN ai_llm_logs.action; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.action IS '动作名称 intent_recognize/case_review/script_gen 等';

-- Name: COLUMN ai_llm_logs.session_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.session_id IS '关联会话ID（chat 模块）';

-- Name: COLUMN ai_llm_logs.task_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.task_id IS '关联任务ID（task_engine 模块）';

-- Name: COLUMN ai_llm_logs.message_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.message_id IS '关联消息ID（chat 模块）';

-- Name: COLUMN ai_llm_logs.model; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.model IS '模型名称';

-- Name: COLUMN ai_llm_logs.status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.status IS '调用状态 success/error/timeout';

-- Name: COLUMN ai_llm_logs.error_msg; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.error_msg IS '错误信息';

-- Name: COLUMN ai_llm_logs.messages; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.messages IS '请求 messages 完整 JSON（系统提示词 + 历史消息 + 用户输入）';

-- Name: COLUMN ai_llm_logs.response_raw; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.response_raw IS 'LLM 原始返回文本';

-- Name: COLUMN ai_llm_logs.response_json; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.response_json IS 'LLM 结构化返回（JSON parse 后）';

-- Name: COLUMN ai_llm_logs.prompt_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.prompt_tokens IS '输入 token';

-- Name: COLUMN ai_llm_logs.completion_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.completion_tokens IS '输出 token';

-- Name: COLUMN ai_llm_logs.duration_ms; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.duration_ms IS '耗时(毫秒)';

-- Name: COLUMN ai_llm_logs.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.create_time IS '创建时间';

-- Name: COLUMN ai_llm_logs.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_llm_logs.id IS '主键ID';

-- Name: ai_llm_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_llm_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_llm_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_llm_logs_id_seq OWNED BY public.ai_llm_logs.id;

-- Name: ai_tc_ai_configs; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_ai_configs (
    name character varying(128) NOT NULL,
    provider character varying(32) DEFAULT '''openai_compat'''::character varying NOT NULL,
    api_base character varying(256) NOT NULL,
    api_key character varying(512) NOT NULL,
    model character varying(64) NOT NULL,
    temperature double precision DEFAULT '0.3'::double precision NOT NULL,
    max_tokens integer DEFAULT 4096 NOT NULL,
    scenes jsonb,
    is_default smallint DEFAULT '0'::smallint NOT NULL,
    status smallint DEFAULT '1'::smallint NOT NULL,
    remark character varying(512),
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL
);

-- Name: COLUMN ai_tc_ai_configs.name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.name IS '配置名称';

-- Name: COLUMN ai_tc_ai_configs.provider; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.provider IS '提供方';

-- Name: COLUMN ai_tc_ai_configs.api_base; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.api_base IS 'API地址';

-- Name: COLUMN ai_tc_ai_configs.api_key; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.api_key IS 'API密钥';

-- Name: COLUMN ai_tc_ai_configs.model; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.model IS '模型名';

-- Name: COLUMN ai_tc_ai_configs.temperature; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.temperature IS '采样温度';

-- Name: COLUMN ai_tc_ai_configs.max_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.max_tokens IS '最大输出token';

-- Name: COLUMN ai_tc_ai_configs.scenes; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.scenes IS '适用场景列表';

-- Name: COLUMN ai_tc_ai_configs.is_default; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.is_default IS '全局兜底默认';

-- Name: COLUMN ai_tc_ai_configs.status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.status IS '状态 0-停用 1-启用';

-- Name: COLUMN ai_tc_ai_configs.remark; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.remark IS '备注';

-- Name: COLUMN ai_tc_ai_configs.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.id IS '主键ID';

-- Name: COLUMN ai_tc_ai_configs.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.create_time IS '创建时间';

-- Name: COLUMN ai_tc_ai_configs.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.update_time IS '更新时间';

-- Name: COLUMN ai_tc_ai_configs.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_ai_configs.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: ai_tc_ai_configs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_ai_configs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_ai_configs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_ai_configs_id_seq OWNED BY public.ai_tc_ai_configs.id;

-- Name: ai_tc_cases; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_cases (
    project_id bigint NOT NULL,
    suite_id bigint NOT NULL,
    external_id character varying(64),
    name character varying(256) NOT NULL,
    summary text,
    preconditions text,
    topo character varying(512),
    test_data text,
    steps jsonb,
    importance smallint DEFAULT '2'::smallint NOT NULL,
    is_core smallint DEFAULT '0'::smallint NOT NULL,
    core_reason character varying(512),
    core_source smallint,
    review_status smallint DEFAULT '0'::smallint NOT NULL,
    script_count integer DEFAULT 0 NOT NULL,
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL,
    is_sample smallint DEFAULT '0'::smallint NOT NULL,
    purpose character varying(256),
    testlink_tc_id bigint,
    testlink_version_id bigint,
    sync_status smallint DEFAULT '0'::smallint NOT NULL,
    synced_version integer,
    synced_hash character varying(64),
    synced_snapshot jsonb,
    last_sync_at timestamp without time zone,
    last_push_at timestamp without time zone,
    testlink_modified_at timestamp without time zone,
    testlink_modifier character varying(128),
    auto_sync smallint DEFAULT '1'::smallint NOT NULL,
    sync_error text
);

-- Name: COLUMN ai_tc_cases.project_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.project_id IS '项目ID';

-- Name: COLUMN ai_tc_cases.suite_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.suite_id IS '所属套件ID';

-- Name: COLUMN ai_tc_cases.external_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.external_id IS 'Excel用例ID，项目内唯一';

-- Name: COLUMN ai_tc_cases.name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.name IS '用例名称';

-- Name: COLUMN ai_tc_cases.summary; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.summary IS '测试思想';

-- Name: COLUMN ai_tc_cases.preconditions; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.preconditions IS '前置条件';

-- Name: COLUMN ai_tc_cases.topo; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.topo IS '测试Topo';

-- Name: COLUMN ai_tc_cases.test_data; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.test_data IS '测试数据';

-- Name: COLUMN ai_tc_cases.steps; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.steps IS '测试步骤 [{action, expected, step_no}]';

-- Name: COLUMN ai_tc_cases.importance; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.importance IS '级别 1-低 2-中 3-高';

-- Name: COLUMN ai_tc_cases.is_core; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.is_core IS '是否核心用例 0-否 1-是';

-- Name: COLUMN ai_tc_cases.core_reason; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.core_reason IS '标记为核心的原因';

-- Name: COLUMN ai_tc_cases.core_source; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.core_source IS '核心来源 1-AI挑选 2-人工标记';

-- Name: COLUMN ai_tc_cases.review_status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.review_status IS '审核状态 0-未审核 1-已审核';

-- Name: COLUMN ai_tc_cases.script_count; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.script_count IS '关联脚本数量';

-- Name: COLUMN ai_tc_cases.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.id IS '主键ID';

-- Name: COLUMN ai_tc_cases.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.create_time IS '创建时间';

-- Name: COLUMN ai_tc_cases.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.update_time IS '更新时间';

-- Name: COLUMN ai_tc_cases.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: COLUMN ai_tc_cases.is_sample; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.is_sample IS '是否样本用例 0-否 1-是';

-- Name: COLUMN ai_tc_cases.purpose; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.purpose IS '测试目的 / 中文用例名称（如 SSID长度验证）';

-- Name: COLUMN ai_tc_cases.testlink_tc_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.testlink_tc_id IS 'TestLink 内部 testcase_id';

-- Name: COLUMN ai_tc_cases.testlink_version_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.testlink_version_id IS 'TestLink tcversion_id（每次远端编辑会变）';

-- Name: COLUMN ai_tc_cases.sync_status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.sync_status IS '同步状态 0-未关联 1-已同步 2-待反写 3-远端有更新 4-冲突 5-反写失败 6-远端已删除';

-- Name: COLUMN ai_tc_cases.synced_version; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.synced_version IS '上次同步时的 TestLink version';

-- Name: COLUMN ai_tc_cases.synced_hash; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.synced_hash IS '上次同步内容的 SHA256（本地脏检测基准）';

-- Name: COLUMN ai_tc_cases.synced_snapshot; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.synced_snapshot IS '上次同步时的字段快照（三方合并用）';

-- Name: COLUMN ai_tc_cases.last_sync_at; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.last_sync_at IS '上次同步时间';

-- Name: COLUMN ai_tc_cases.last_push_at; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.last_push_at IS '上次反写时间';

-- Name: COLUMN ai_tc_cases.testlink_modified_at; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.testlink_modified_at IS 'TestLink 端 modification_ts';

-- Name: COLUMN ai_tc_cases.testlink_modifier; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.testlink_modifier IS 'TestLink 端最后修改人';

-- Name: COLUMN ai_tc_cases.auto_sync; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.auto_sync IS '修改后是否自动反写 0-否 1-是';

-- Name: COLUMN ai_tc_cases.sync_error; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_cases.sync_error IS '最近一次反写失败原因';

-- Name: ai_tc_cases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_cases_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_cases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_cases_id_seq OWNED BY public.ai_tc_cases.id;

-- Name: ai_tc_projects; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_projects (
    name character varying(128) NOT NULL,
    prefix character varying(64) NOT NULL,
    description text,
    last_sync_time character varying(32),
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL,
    testlink_project_id bigint
);

-- Name: COLUMN ai_tc_projects.name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.name IS '项目名称';

-- Name: COLUMN ai_tc_projects.prefix; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.prefix IS '项目标识';

-- Name: COLUMN ai_tc_projects.description; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.description IS '项目描述';

-- Name: COLUMN ai_tc_projects.last_sync_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.last_sync_time IS '最后导入时间';

-- Name: COLUMN ai_tc_projects.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.id IS '主键ID';

-- Name: COLUMN ai_tc_projects.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.create_time IS '创建时间';

-- Name: COLUMN ai_tc_projects.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.update_time IS '更新时间';

-- Name: COLUMN ai_tc_projects.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: COLUMN ai_tc_projects.testlink_project_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_projects.testlink_project_id IS 'TestLink testproject id';

-- Name: ai_tc_projects_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_projects_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_projects_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_projects_id_seq OWNED BY public.ai_tc_projects.id;

-- Name: ai_tc_review_records; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_review_records (
    id integer NOT NULL,
    task_id integer NOT NULL,
    task_item_id integer NOT NULL,
    case_id integer,
    review_action character varying(32) NOT NULL,
    field_name character varying(128),
    before_value text,
    after_value text,
    reviewer character varying(64),
    reviewer_ip character varying(64),
    review_time timestamp without time zone,
    memo text,
    create_time timestamp without time zone DEFAULT now() NOT NULL,
    update_time timestamp without time zone DEFAULT now() NOT NULL
);

-- Name: TABLE ai_tc_review_records; Type: COMMENT; Schema: public; Owner: -
COMMENT ON TABLE public.ai_tc_review_records IS '审核记录（审计日志）';

-- Name: COLUMN ai_tc_review_records.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.id IS '主键ID';

-- Name: COLUMN ai_tc_review_records.task_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.task_id IS '任务ID';

-- Name: COLUMN ai_tc_review_records.task_item_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.task_item_id IS '任务明细ID';

-- Name: COLUMN ai_tc_review_records.case_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.case_id IS '用例ID';

-- Name: COLUMN ai_tc_review_records.review_action; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.review_action IS '操作 accept/ignore/edit_accept/field_accept';

-- Name: COLUMN ai_tc_review_records.field_name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.field_name IS '审核字段名';

-- Name: COLUMN ai_tc_review_records.before_value; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.before_value IS '修改前的值';

-- Name: COLUMN ai_tc_review_records.after_value; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.after_value IS '修改后的值';

-- Name: COLUMN ai_tc_review_records.reviewer; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.reviewer IS '审核人';

-- Name: COLUMN ai_tc_review_records.reviewer_ip; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.reviewer_ip IS '审核人IP';

-- Name: COLUMN ai_tc_review_records.review_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.review_time IS '审核时间';

-- Name: COLUMN ai_tc_review_records.memo; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.memo IS '备注';

-- Name: COLUMN ai_tc_review_records.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.create_time IS '创建时间';

-- Name: COLUMN ai_tc_review_records.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_review_records.update_time IS '更新时间';

-- Name: ai_tc_review_records_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_review_records_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_review_records_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_review_records_id_seq OWNED BY public.ai_tc_review_records.id;

-- Name: ai_tc_samples; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_samples (
    project_id bigint,
    sample_type character varying(16) NOT NULL,
    name character varying(128) NOT NULL,
    language character varying(32),
    framework character varying(32) DEFAULT 'pytest'::character varying,
    content text NOT NULL,
    description character varying(512),
    status smallint DEFAULT '1'::smallint NOT NULL,
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL
);

-- Name: COLUMN ai_tc_samples.project_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.project_id IS '项目ID，NULL为通用';

-- Name: COLUMN ai_tc_samples.sample_type; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.sample_type IS '类型 case-用例样本 script-脚本样本';

-- Name: COLUMN ai_tc_samples.name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.name IS '样本名称';

-- Name: COLUMN ai_tc_samples.language; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.language IS '语言';

-- Name: COLUMN ai_tc_samples.framework; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.framework IS '框架';

-- Name: COLUMN ai_tc_samples.content; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.content IS '样本内容';

-- Name: COLUMN ai_tc_samples.description; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.description IS '样本描述';

-- Name: COLUMN ai_tc_samples.status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.status IS '状态 0-停用 1-启用';

-- Name: COLUMN ai_tc_samples.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.id IS '主键ID';

-- Name: COLUMN ai_tc_samples.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.create_time IS '创建时间';

-- Name: COLUMN ai_tc_samples.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.update_time IS '更新时间';

-- Name: COLUMN ai_tc_samples.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_samples.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: ai_tc_samples_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_samples_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_samples_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_samples_id_seq OWNED BY public.ai_tc_samples.id;

-- Name: ai_tc_scripts; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_scripts (
    case_id bigint NOT NULL,
    language character varying(32) DEFAULT '''python'''::character varying NOT NULL,
    framework character varying(32) DEFAULT '''pytest'''::character varying NOT NULL,
    content text NOT NULL,
    source smallint DEFAULT '1'::smallint NOT NULL,
    task_item_id bigint,
    version integer DEFAULT 1 NOT NULL,
    status smallint DEFAULT '1'::smallint NOT NULL,
    reviewed_by character varying(64),
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL
);

-- Name: COLUMN ai_tc_scripts.case_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.case_id IS '用例ID';

-- Name: COLUMN ai_tc_scripts.language; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.language IS '脚本语言';

-- Name: COLUMN ai_tc_scripts.framework; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.framework IS '测试框架';

-- Name: COLUMN ai_tc_scripts.content; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.content IS '脚本内容';

-- Name: COLUMN ai_tc_scripts.source; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.source IS '来源 1-AI生成 2-人工录入';

-- Name: COLUMN ai_tc_scripts.task_item_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.task_item_id IS '来源任务明细ID';

-- Name: COLUMN ai_tc_scripts.version; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.version IS '版本号';

-- Name: COLUMN ai_tc_scripts.status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.status IS '状态 1-草稿 2-已入库';

-- Name: COLUMN ai_tc_scripts.reviewed_by; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.reviewed_by IS '审核人';

-- Name: COLUMN ai_tc_scripts.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.id IS '主键ID';

-- Name: COLUMN ai_tc_scripts.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.create_time IS '创建时间';

-- Name: COLUMN ai_tc_scripts.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.update_time IS '更新时间';

-- Name: COLUMN ai_tc_scripts.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_scripts.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: ai_tc_scripts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_scripts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_scripts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_scripts_id_seq OWNED BY public.ai_tc_scripts.id;

-- Name: ai_tc_specs; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_specs (
    id bigint NOT NULL,
    project_id bigint,
    suite_id bigint,
    task_type character varying(32) NOT NULL,
    spec_type character varying(32) NOT NULL,
    content text NOT NULL,
    sort_order integer DEFAULT 0,
    status smallint DEFAULT 1,
    is_deleted smallint DEFAULT 0,
    create_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    update_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);

-- Name: ai_tc_specs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_specs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_specs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_specs_id_seq OWNED BY public.ai_tc_specs.id;

-- Name: ai_tc_suites; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_suites (
    project_id bigint NOT NULL,
    parent_id bigint DEFAULT '0'::bigint NOT NULL,
    tree_path character varying(512) DEFAULT ''::character varying NOT NULL,
    name character varying(128) NOT NULL,
    sort_order integer DEFAULT 0 NOT NULL,
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL,
    testlink_suite_id bigint,
    description text
);

-- Name: COLUMN ai_tc_suites.project_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.project_id IS '项目ID';

-- Name: COLUMN ai_tc_suites.parent_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.parent_id IS '父套件ID，0为根';

-- Name: COLUMN ai_tc_suites.tree_path; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.tree_path IS '祖先路径';

-- Name: COLUMN ai_tc_suites.name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.name IS '套件名称';

-- Name: COLUMN ai_tc_suites.sort_order; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.sort_order IS '排序';

-- Name: COLUMN ai_tc_suites.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.id IS '主键ID';

-- Name: COLUMN ai_tc_suites.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.create_time IS '创建时间';

-- Name: COLUMN ai_tc_suites.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.update_time IS '更新时间';

-- Name: COLUMN ai_tc_suites.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: COLUMN ai_tc_suites.testlink_suite_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.testlink_suite_id IS 'TestLink testsuite id';

-- Name: COLUMN ai_tc_suites.description; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_suites.description IS '套件描述';

-- Name: ai_tc_suites_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_suites_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_suites_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_suites_id_seq OWNED BY public.ai_tc_suites.id;

-- Name: ai_tc_task_items; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_task_items (
    task_id bigint NOT NULL,
    case_id bigint NOT NULL,
    case_name character varying(256) NOT NULL,
    output jsonb,
    item_status smallint DEFAULT '0'::smallint NOT NULL,
    confirm_status smallint DEFAULT '0'::smallint NOT NULL,
    final_content text,
    reviewed_by character varying(64),
    review_time character varying(32),
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL
);

-- Name: COLUMN ai_tc_task_items.task_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.task_id IS '任务ID';

-- Name: COLUMN ai_tc_task_items.case_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.case_id IS '用例ID';

-- Name: COLUMN ai_tc_task_items.case_name; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.case_name IS '用例名称（快照）';

-- Name: COLUMN ai_tc_task_items.output; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.output IS 'AI输出结果';

-- Name: COLUMN ai_tc_task_items.item_status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.item_status IS '0-待处理 1-成功 2-失败';

-- Name: COLUMN ai_tc_task_items.confirm_status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.confirm_status IS '0-待确认 1-采纳 2-忽略 3-编辑采纳';

-- Name: COLUMN ai_tc_task_items.final_content; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.final_content IS '人工修改后最终内容';

-- Name: COLUMN ai_tc_task_items.reviewed_by; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.reviewed_by IS '审核人';

-- Name: COLUMN ai_tc_task_items.review_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.review_time IS '审核时间';

-- Name: COLUMN ai_tc_task_items.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.id IS '主键ID';

-- Name: COLUMN ai_tc_task_items.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.create_time IS '创建时间';

-- Name: COLUMN ai_tc_task_items.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.update_time IS '更新时间';

-- Name: COLUMN ai_tc_task_items.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_task_items.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: ai_tc_task_items_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_task_items_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_task_items_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_task_items_id_seq OWNED BY public.ai_tc_task_items.id;

-- Name: ai_tc_tasks; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_tc_tasks (
    task_type character varying(32) NOT NULL,
    project_id bigint NOT NULL,
    suite_id bigint NOT NULL,
    sample_ids jsonb,
    ai_config_id bigint,
    model character varying(64),
    status smallint DEFAULT '0'::smallint NOT NULL,
    total_count integer DEFAULT 0 NOT NULL,
    done_count integer DEFAULT 0 NOT NULL,
    input_tokens integer DEFAULT 0 NOT NULL,
    output_tokens integer DEFAULT 0 NOT NULL,
    error_msg text,
    create_by character varying(64),
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL,
    spec_ids jsonb,
    session_id bigint
);

-- Name: COLUMN ai_tc_tasks.task_type; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.task_type IS '任务类型';

-- Name: COLUMN ai_tc_tasks.project_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.project_id IS '项目ID';

-- Name: COLUMN ai_tc_tasks.suite_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.suite_id IS '目标套件ID';

-- Name: COLUMN ai_tc_tasks.sample_ids; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.sample_ids IS '样本ID列表';

-- Name: COLUMN ai_tc_tasks.ai_config_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.ai_config_id IS 'AI配置ID';

-- Name: COLUMN ai_tc_tasks.model; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.model IS '实际使用的模型名';

-- Name: COLUMN ai_tc_tasks.status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.status IS '0-排队 1-运行中 2-完成 3-失败 4-已确认';

-- Name: COLUMN ai_tc_tasks.total_count; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.total_count IS '总用例数';

-- Name: COLUMN ai_tc_tasks.done_count; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.done_count IS '已完成数';

-- Name: COLUMN ai_tc_tasks.input_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.input_tokens IS '输入token数';

-- Name: COLUMN ai_tc_tasks.output_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.output_tokens IS '输出token数';

-- Name: COLUMN ai_tc_tasks.error_msg; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.error_msg IS '错误信息';

-- Name: COLUMN ai_tc_tasks.create_by; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.create_by IS '创建人';

-- Name: COLUMN ai_tc_tasks.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.id IS '主键ID';

-- Name: COLUMN ai_tc_tasks.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.create_time IS '创建时间';

-- Name: COLUMN ai_tc_tasks.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.update_time IS '更新时间';

-- Name: COLUMN ai_tc_tasks.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: COLUMN ai_tc_tasks.session_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_tc_tasks.session_id IS '创建任务的会话ID（从对话中发起任务时记录）';

-- Name: ai_tc_tasks_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_tc_tasks_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_tc_tasks_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_tc_tasks_id_seq OWNED BY public.ai_tc_tasks.id;

-- Name: ai_usage_logs; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.ai_usage_logs (
    module character varying(50) DEFAULT 'chat'::character varying NOT NULL,
    session_id bigint,
    task_id bigint,
    model character varying(100) NOT NULL,
    prompt_tokens integer DEFAULT 0 NOT NULL,
    completion_tokens integer DEFAULT 0 NOT NULL,
    total_tokens integer DEFAULT 0 NOT NULL,
    duration_ms integer DEFAULT 0 NOT NULL,
    created_at character varying(32) NOT NULL,
    id bigint NOT NULL
);

-- Name: COLUMN ai_usage_logs.module; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.module IS '来源模块 chat/task_engine';

-- Name: COLUMN ai_usage_logs.session_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.session_id IS '会话ID（chat 模块）';

-- Name: COLUMN ai_usage_logs.task_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.task_id IS '任务ID（task_engine 模块）';

-- Name: COLUMN ai_usage_logs.model; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.model IS '模型名称';

-- Name: COLUMN ai_usage_logs.prompt_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.prompt_tokens IS '输入 token';

-- Name: COLUMN ai_usage_logs.completion_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.completion_tokens IS '输出 token';

-- Name: COLUMN ai_usage_logs.total_tokens; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.total_tokens IS '总 token';

-- Name: COLUMN ai_usage_logs.duration_ms; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.duration_ms IS '耗时(毫秒)';

-- Name: COLUMN ai_usage_logs.created_at; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.created_at IS '创建时间';

-- Name: COLUMN ai_usage_logs.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.ai_usage_logs.id IS '主键ID';

-- Name: ai_usage_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.ai_usage_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: ai_usage_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.ai_usage_logs_id_seq OWNED BY public.ai_usage_logs.id;

-- Name: chat_drafts; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.chat_drafts (
    session_id bigint NOT NULL,
    message_id bigint NOT NULL,
    draft_type character varying(30) NOT NULL,
    title character varying(200) DEFAULT ''::character varying NOT NULL,
    content_json jsonb NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    confirmed_by character varying(64),
    confirmed_at character varying(32),
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now()
);

-- Name: COLUMN chat_drafts.session_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.session_id IS '所属会话ID';

-- Name: COLUMN chat_drafts.message_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.message_id IS '关联消息ID';

-- Name: COLUMN chat_drafts.draft_type; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.draft_type IS '草稿类型 core_select/case_review/script_gen/field_complete/steps_complete/case_design';

-- Name: COLUMN chat_drafts.title; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.title IS '草稿标题';

-- Name: COLUMN chat_drafts.content_json; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.content_json IS '草稿内容';

-- Name: COLUMN chat_drafts.status; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.status IS '状态 pending/confirmed/applied/discarded';

-- Name: COLUMN chat_drafts.confirmed_by; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.confirmed_by IS '确认人';

-- Name: COLUMN chat_drafts.confirmed_at; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.confirmed_at IS '确认时间';

-- Name: COLUMN chat_drafts.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.id IS '主键ID';

-- Name: COLUMN chat_drafts.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.create_time IS '创建时间';

-- Name: COLUMN chat_drafts.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_drafts.update_time IS '更新时间';

-- Name: chat_drafts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.chat_drafts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: chat_drafts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.chat_drafts_id_seq OWNED BY public.chat_drafts.id;

-- Name: chat_messages; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.chat_messages (
    session_id bigint NOT NULL,
    role character varying(20) NOT NULL,
    msg_type character varying(30) DEFAULT 'text'::character varying NOT NULL,
    content text NOT NULL,
    metadata_json jsonb,
    draft_id bigint,
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now()
);

-- Name: COLUMN chat_messages.session_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.session_id IS '所属会话ID';

-- Name: COLUMN chat_messages.role; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.role IS '角色 user/assistant/system';

-- Name: COLUMN chat_messages.msg_type; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.msg_type IS '消息类型 text/action_card/task_card/draft_card/clarify_card/help_card';

-- Name: COLUMN chat_messages.content; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.content IS '消息正文（Markdown）';

-- Name: COLUMN chat_messages.metadata_json; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.metadata_json IS '附加数据 {skill_name, tool_calls, tokens, execution_time_ms, ...}';

-- Name: COLUMN chat_messages.draft_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.draft_id IS '关联的 Draft ID（如有产出）';

-- Name: COLUMN chat_messages.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.id IS '主键ID';

-- Name: COLUMN chat_messages.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.create_time IS '创建时间';

-- Name: COLUMN chat_messages.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_messages.update_time IS '更新时间';

-- Name: chat_messages_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.chat_messages_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: chat_messages_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.chat_messages_id_seq OWNED BY public.chat_messages.id;

-- Name: chat_sessions; Type: TABLE; Schema: public; Owner: -
CREATE TABLE public.chat_sessions (
    title character varying(200) DEFAULT '新对话'::character varying NOT NULL,
    domain character varying(50) DEFAULT 'case'::character varying NOT NULL,
    context_json jsonb,
    message_count integer DEFAULT 0 NOT NULL,
    is_pinned smallint DEFAULT '0'::smallint NOT NULL,
    user_id bigint,
    id bigint NOT NULL,
    create_time timestamp without time zone DEFAULT now(),
    update_time timestamp without time zone DEFAULT now(),
    is_deleted smallint DEFAULT '0'::smallint NOT NULL
);

-- Name: COLUMN chat_sessions.title; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.title IS '会话标题';

-- Name: COLUMN chat_sessions.domain; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.domain IS '会话域 case/bug/analytics';

-- Name: COLUMN chat_sessions.context_json; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.context_json IS '页面上下文快照 {project_id, suite_id, ...}';

-- Name: COLUMN chat_sessions.message_count; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.message_count IS '消息数量';

-- Name: COLUMN chat_sessions.is_pinned; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.is_pinned IS '是否置顶 0-否 1-是';

-- Name: COLUMN chat_sessions.user_id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.user_id IS '所属用户ID（单用户模式可为空）';

-- Name: COLUMN chat_sessions.id; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.id IS '主键ID';

-- Name: COLUMN chat_sessions.create_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.create_time IS '创建时间';

-- Name: COLUMN chat_sessions.update_time; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.update_time IS '更新时间';

-- Name: COLUMN chat_sessions.is_deleted; Type: COMMENT; Schema: public; Owner: -
COMMENT ON COLUMN public.chat_sessions.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- Name: chat_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
CREATE SEQUENCE public.chat_sessions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;

-- Name: chat_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
ALTER SEQUENCE public.chat_sessions_id_seq OWNED BY public.chat_sessions.id;

-- Name: ai_llm_logs id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_llm_logs ALTER COLUMN id SET DEFAULT nextval('public.ai_llm_logs_id_seq'::regclass);

-- Name: ai_tc_ai_configs id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_ai_configs ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_ai_configs_id_seq'::regclass);

-- Name: ai_tc_cases id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_cases ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_cases_id_seq'::regclass);

-- Name: ai_tc_projects id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_projects ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_projects_id_seq'::regclass);

-- Name: ai_tc_review_records id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_review_records ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_review_records_id_seq'::regclass);

-- Name: ai_tc_samples id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_samples ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_samples_id_seq'::regclass);

-- Name: ai_tc_scripts id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_scripts ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_scripts_id_seq'::regclass);

-- Name: ai_tc_specs id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_specs ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_specs_id_seq'::regclass);

-- Name: ai_tc_suites id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_suites ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_suites_id_seq'::regclass);

-- Name: ai_tc_task_items id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_task_items ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_task_items_id_seq'::regclass);

-- Name: ai_tc_tasks id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_tasks ALTER COLUMN id SET DEFAULT nextval('public.ai_tc_tasks_id_seq'::regclass);

-- Name: ai_usage_logs id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_usage_logs ALTER COLUMN id SET DEFAULT nextval('public.ai_usage_logs_id_seq'::regclass);

-- Name: chat_drafts id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_drafts ALTER COLUMN id SET DEFAULT nextval('public.chat_drafts_id_seq'::regclass);

-- Name: chat_messages id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_messages ALTER COLUMN id SET DEFAULT nextval('public.chat_messages_id_seq'::regclass);

-- Name: chat_sessions id; Type: DEFAULT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_sessions ALTER COLUMN id SET DEFAULT nextval('public.chat_sessions_id_seq'::regclass);

-- Name: ai_llm_logs ai_llm_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_llm_logs
    ADD CONSTRAINT ai_llm_logs_pkey PRIMARY KEY (id);

-- Name: ai_tc_ai_configs ai_tc_ai_configs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_ai_configs
    ADD CONSTRAINT ai_tc_ai_configs_pkey PRIMARY KEY (id);

-- Name: ai_tc_cases ai_tc_cases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_cases
    ADD CONSTRAINT ai_tc_cases_pkey PRIMARY KEY (id);

-- Name: ai_tc_projects ai_tc_projects_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_projects
    ADD CONSTRAINT ai_tc_projects_pkey PRIMARY KEY (id);

-- Name: ai_tc_review_records ai_tc_review_records_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_review_records
    ADD CONSTRAINT ai_tc_review_records_pkey PRIMARY KEY (id);

-- Name: ai_tc_samples ai_tc_samples_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_samples
    ADD CONSTRAINT ai_tc_samples_pkey PRIMARY KEY (id);

-- Name: ai_tc_scripts ai_tc_scripts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_scripts
    ADD CONSTRAINT ai_tc_scripts_pkey PRIMARY KEY (id);

-- Name: ai_tc_specs ai_tc_specs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_specs
    ADD CONSTRAINT ai_tc_specs_pkey PRIMARY KEY (id);

-- Name: ai_tc_suites ai_tc_suites_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_suites
    ADD CONSTRAINT ai_tc_suites_pkey PRIMARY KEY (id);

-- Name: ai_tc_task_items ai_tc_task_items_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_task_items
    ADD CONSTRAINT ai_tc_task_items_pkey PRIMARY KEY (id);

-- Name: ai_tc_tasks ai_tc_tasks_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_tasks
    ADD CONSTRAINT ai_tc_tasks_pkey PRIMARY KEY (id);

-- Name: ai_usage_logs ai_usage_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_usage_logs
    ADD CONSTRAINT ai_usage_logs_pkey PRIMARY KEY (id);

-- Name: chat_drafts chat_drafts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_drafts
    ADD CONSTRAINT chat_drafts_pkey PRIMARY KEY (id);

-- Name: chat_messages chat_messages_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_pkey PRIMARY KEY (id);

-- Name: chat_sessions chat_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_sessions
    ADD CONSTRAINT chat_sessions_pkey PRIMARY KEY (id);

-- Name: ai_tc_cases uq_aitc_case_extid; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_cases
    ADD CONSTRAINT uq_aitc_case_extid UNIQUE (project_id, external_id);

-- Name: ai_tc_projects uq_aitc_project_prefix; Type: CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_projects
    ADD CONSTRAINT uq_aitc_project_prefix UNIQUE (prefix);

-- Name: idx_aitc_case_project_core; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_case_project_core ON public.ai_tc_cases USING btree (project_id, is_core);

-- Name: idx_aitc_case_review; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_case_review ON public.ai_tc_cases USING btree (project_id, review_status);

-- Name: idx_aitc_case_suite; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_case_suite ON public.ai_tc_cases USING btree (suite_id, is_deleted);

-- Name: idx_aitc_case_sync_status; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_case_sync_status ON public.ai_tc_cases USING btree (project_id, sync_status);

-- Name: idx_aitc_case_tl_tc; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_case_tl_tc ON public.ai_tc_cases USING btree (testlink_tc_id);

-- Name: idx_aitc_review_case; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_review_case ON public.ai_tc_review_records USING btree (case_id);

-- Name: idx_aitc_review_item; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_review_item ON public.ai_tc_review_records USING btree (task_item_id);

-- Name: idx_aitc_review_task; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_review_task ON public.ai_tc_review_records USING btree (task_id);

-- Name: idx_aitc_sample_type; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_sample_type ON public.ai_tc_samples USING btree (sample_type, project_id);

-- Name: idx_aitc_script_case; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_script_case ON public.ai_tc_scripts USING btree (case_id, is_deleted);

-- Name: idx_aitc_spec_project; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_spec_project ON public.ai_tc_specs USING btree (project_id, task_type);

-- Name: idx_aitc_spec_suite; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_spec_suite ON public.ai_tc_specs USING btree (suite_id);

-- Name: idx_aitc_spec_task; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_spec_task ON public.ai_tc_specs USING btree (task_type, spec_type);

-- Name: idx_aitc_suite_parent; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_suite_parent ON public.ai_tc_suites USING btree (parent_id);

-- Name: idx_aitc_suite_project; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_suite_project ON public.ai_tc_suites USING btree (project_id, is_deleted);

-- Name: idx_aitc_suite_tree; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_suite_tree ON public.ai_tc_suites USING btree (tree_path);

-- Name: idx_aitc_task_project; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_aitc_task_project ON public.ai_tc_tasks USING btree (project_id, task_type);

-- Name: idx_chat_draft_msg; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_chat_draft_msg ON public.chat_drafts USING btree (message_id);

-- Name: idx_chat_draft_session; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_chat_draft_session ON public.chat_drafts USING btree (session_id);

-- Name: idx_chat_msg_session; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_chat_msg_session ON public.chat_messages USING btree (session_id, id);

-- Name: idx_chat_session_domain; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_chat_session_domain ON public.chat_sessions USING btree (domain);

-- Name: idx_chat_session_user; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_chat_session_user ON public.chat_sessions USING btree (user_id, is_deleted);

-- Name: idx_llm_log_action; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_llm_log_action ON public.ai_llm_logs USING btree (action);

-- Name: idx_llm_log_session; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_llm_log_session ON public.ai_llm_logs USING btree (session_id, create_time);

-- Name: idx_llm_log_status; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_llm_log_status ON public.ai_llm_logs USING btree (status, create_time);

-- Name: idx_llm_log_trace; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_llm_log_trace ON public.ai_llm_logs USING btree (trace_id);

-- Name: idx_usage_module; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_usage_module ON public.ai_usage_logs USING btree (module, created_at);

-- Name: idx_usage_session; Type: INDEX; Schema: public; Owner: -
CREATE INDEX idx_usage_session ON public.ai_usage_logs USING btree (session_id);

-- Name: ai_tc_cases ai_tc_cases_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_cases
    ADD CONSTRAINT ai_tc_cases_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_tc_projects(id);

-- Name: ai_tc_cases ai_tc_cases_suite_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_cases
    ADD CONSTRAINT ai_tc_cases_suite_id_fkey FOREIGN KEY (suite_id) REFERENCES public.ai_tc_suites(id);

-- Name: ai_tc_samples ai_tc_samples_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_samples
    ADD CONSTRAINT ai_tc_samples_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_tc_projects(id);

-- Name: ai_tc_scripts ai_tc_scripts_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_scripts
    ADD CONSTRAINT ai_tc_scripts_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.ai_tc_cases(id);

-- Name: ai_tc_scripts ai_tc_scripts_task_item_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_scripts
    ADD CONSTRAINT ai_tc_scripts_task_item_id_fkey FOREIGN KEY (task_item_id) REFERENCES public.ai_tc_task_items(id);

-- Name: ai_tc_suites ai_tc_suites_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_suites
    ADD CONSTRAINT ai_tc_suites_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_tc_projects(id);

-- Name: ai_tc_task_items ai_tc_task_items_case_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_task_items
    ADD CONSTRAINT ai_tc_task_items_case_id_fkey FOREIGN KEY (case_id) REFERENCES public.ai_tc_cases(id);

-- Name: ai_tc_task_items ai_tc_task_items_task_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_task_items
    ADD CONSTRAINT ai_tc_task_items_task_id_fkey FOREIGN KEY (task_id) REFERENCES public.ai_tc_tasks(id);

-- Name: ai_tc_tasks ai_tc_tasks_ai_config_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_tasks
    ADD CONSTRAINT ai_tc_tasks_ai_config_id_fkey FOREIGN KEY (ai_config_id) REFERENCES public.ai_tc_ai_configs(id);

-- Name: ai_tc_tasks ai_tc_tasks_project_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_tasks
    ADD CONSTRAINT ai_tc_tasks_project_id_fkey FOREIGN KEY (project_id) REFERENCES public.ai_tc_projects(id);

-- Name: ai_tc_tasks ai_tc_tasks_suite_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.ai_tc_tasks
    ADD CONSTRAINT ai_tc_tasks_suite_id_fkey FOREIGN KEY (suite_id) REFERENCES public.ai_tc_suites(id);

-- Name: chat_drafts chat_drafts_message_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_drafts
    ADD CONSTRAINT chat_drafts_message_id_fkey FOREIGN KEY (message_id) REFERENCES public.chat_messages(id);

-- Name: chat_drafts chat_drafts_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_drafts
    ADD CONSTRAINT chat_drafts_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);

-- Name: chat_messages chat_messages_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
ALTER TABLE ONLY public.chat_messages
    ADD CONSTRAINT chat_messages_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.chat_sessions(id);
