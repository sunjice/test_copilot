-- 手动修复 task 77：两条明细都是 ACCEPTED，task 理应 CONFIRMED
UPDATE ai_tc_tasks SET status = 4, update_time = NOW() WHERE id = 77;

-- 验证
SELECT id, task_type, status, update_time FROM ai_tc_tasks WHERE id = 77;
