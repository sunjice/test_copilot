-- 用例检索引擎追踪字段 migration
-- 在 ai_tc_cases 表上新增 index_hash 和 indexed_at 两列

ALTER TABLE ai_tc_cases
    ADD COLUMN IF NOT EXISTS index_hash VARCHAR(64),
    ADD COLUMN IF NOT EXISTS indexed_at TIMESTAMP;

COMMENT ON COLUMN ai_tc_cases.index_hash IS '索引内容 SHA256，用于增量变更检测';
COMMENT ON COLUMN ai_tc_cases.indexed_at IS '最近一次索引时间';
