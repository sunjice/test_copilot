-- 给已运行的数据库添加「AI轨迹」菜单（挂在 WorkSpace 下，规范管理后面）
-- 执行环境：youlai_admin 库

-- 1. 插入菜单（id=3090，parent=3000，sort=9）
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, external_url, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params)
VALUES (3090, 3000, '0,3000', 'AI轨迹', 'M', 'AITCTrace', 'ai-trace', 'aitc/ai-trace', NULL, NULL, 0, 1, 1, 9, 'el-icon-DataLine', '', now(), now(), '[]')
ON CONFLICT (id) DO NOTHING;

-- 2. 授权给 ROOT(1) 和 ADMIN(2)
INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 1, id FROM sys_menu WHERE id = 3090
ON CONFLICT DO NOTHING;

INSERT INTO sys_role_menu (role_id, menu_id)
SELECT 2, id FROM sys_menu WHERE id = 3090
ON CONFLICT DO NOTHING;
