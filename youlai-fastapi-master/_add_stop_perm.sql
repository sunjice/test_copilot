-- 插入 停止任务 按钮权限记录
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, external_url, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params)
VALUES
(3025, 3020, '0,3000,3020', '停止任务', 'B', NULL, '', NULL, 'aitc:task:stop', NULL, 0, 0, 1, 4, '', NULL, NOW(), NOW(), NULL)
ON CONFLICT (id) DO NOTHING;

-- 授权 ROOT (role_id=1)
INSERT INTO sys_role_menu (role_id, menu_id) VALUES (1, 3025) ON CONFLICT DO NOTHING;

-- 授权 ADMIN (role_id=2)
INSERT INTO sys_role_menu (role_id, menu_id) VALUES (2, 3025) ON CONFLICT DO NOTHING;
