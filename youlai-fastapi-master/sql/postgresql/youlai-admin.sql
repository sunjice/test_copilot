-- ============================================================
-- test-copilot 系统管理数据库初始化脚本 (PostgreSQL 16+)
-- 
-- 基于真实数据库 (PostgreSQL 16.14, 2026-08-12) 导出，100% 一致。
-- 使用方法：
--   psql -h <host> -U youlai -d youlai_admin -f youlai-admin.sql
-- ============================================================

-- 按依赖顺序 DROP 所有 sys_* 表
DROP TABLE IF EXISTS sys_user_social CASCADE;
DROP TABLE IF EXISTS sys_user_role CASCADE;
DROP TABLE IF EXISTS sys_user CASCADE;
DROP TABLE IF EXISTS sys_role_menu CASCADE;
DROP TABLE IF EXISTS sys_role_dept CASCADE;
DROP TABLE IF EXISTS sys_role CASCADE;
DROP TABLE IF EXISTS sys_user_notice CASCADE;
DROP TABLE IF EXISTS sys_notice CASCADE;
DROP TABLE IF EXISTS sys_menu CASCADE;
DROP TABLE IF EXISTS sys_log CASCADE;
DROP TABLE IF EXISTS sys_dict_item CASCADE;
DROP TABLE IF EXISTS sys_dict CASCADE;
DROP TABLE IF EXISTS sys_dept CASCADE;
DROP TABLE IF EXISTS sys_config CASCADE;

-- ----------------------------
-- 建表语句 (DDL)
-- ----------------------------

-- ==================== sys_config ====================
CREATE TABLE sys_config (
    id                   bigint PRIMARY KEY,
    config_name          varchar(50) NOT NULL,
    config_key           varchar(50) NOT NULL,
    config_value         varchar(100) NOT NULL,
    remark               varchar(255),
    create_time          timestamp,
    create_by            bigint,
    update_time          timestamp,
    update_by            bigint,
    is_deleted           smallint NOT NULL DEFAULT 0
);
COMMENT ON TABLE sys_config IS '系统配置表';
COMMENT ON COLUMN sys_config.id IS '主键ID';
COMMENT ON COLUMN sys_config.config_name IS '配置名称';
COMMENT ON COLUMN sys_config.config_key IS '配置键';
COMMENT ON COLUMN sys_config.config_value IS '配置值';
COMMENT ON COLUMN sys_config.remark IS '备注';
COMMENT ON COLUMN sys_config.create_time IS '创建时间';
COMMENT ON COLUMN sys_config.create_by IS '创建人ID';
COMMENT ON COLUMN sys_config.update_time IS '更新时间';
COMMENT ON COLUMN sys_config.update_by IS '修改人ID';
COMMENT ON COLUMN sys_config.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_dept ====================
CREATE TABLE sys_dept (
    id                   bigint PRIMARY KEY,
    name                 varchar(100) NOT NULL,
    code                 varchar(100) NOT NULL,
    parent_id            bigint DEFAULT 0,
    tree_path            varchar(255) NOT NULL,
    sort                 smallint DEFAULT 0,
    status               smallint DEFAULT 1,
    create_by            bigint,
    create_time          timestamp,
    update_by            bigint,
    update_time          timestamp,
    is_deleted           smallint DEFAULT 0
);
CREATE UNIQUE INDEX uk_code ON sys_dept (code);
COMMENT ON TABLE sys_dept IS '部门表';
COMMENT ON COLUMN sys_dept.id IS '主键ID';
COMMENT ON COLUMN sys_dept.name IS '部门名称';
COMMENT ON COLUMN sys_dept.code IS '部门编号';
COMMENT ON COLUMN sys_dept.parent_id IS '父节点id';
COMMENT ON COLUMN sys_dept.tree_path IS '父节点id路径';
COMMENT ON COLUMN sys_dept.sort IS '显示顺序';
COMMENT ON COLUMN sys_dept.status IS '状态 1-正常 0-禁用';
COMMENT ON COLUMN sys_dept.create_by IS '创建人ID';
COMMENT ON COLUMN sys_dept.create_time IS '创建时间';
COMMENT ON COLUMN sys_dept.update_by IS '修改人ID';
COMMENT ON COLUMN sys_dept.update_time IS '更新时间';
COMMENT ON COLUMN sys_dept.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_dict ====================
CREATE TABLE sys_dict (
    id                   bigint PRIMARY KEY,
    dict_code            varchar(50),
    name                 varchar(50),
    status               smallint DEFAULT 0,
    remark               varchar(255),
    create_time          timestamp,
    create_by            bigint,
    update_time          timestamp,
    update_by            bigint,
    is_deleted           smallint DEFAULT 0
);
CREATE INDEX idx_dict_code ON sys_dict (dict_code);
COMMENT ON TABLE sys_dict IS '字典类型表';
COMMENT ON COLUMN sys_dict.id IS '主键ID';
COMMENT ON COLUMN sys_dict.dict_code IS '类型编码';
COMMENT ON COLUMN sys_dict.name IS '类型名称';
COMMENT ON COLUMN sys_dict.status IS '状态 0:正常 1:禁用';
COMMENT ON COLUMN sys_dict.remark IS '备注';
COMMENT ON COLUMN sys_dict.create_time IS '创建时间';
COMMENT ON COLUMN sys_dict.create_by IS '创建人ID';
COMMENT ON COLUMN sys_dict.update_time IS '更新时间';
COMMENT ON COLUMN sys_dict.update_by IS '修改人ID';
COMMENT ON COLUMN sys_dict.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_dict_item ====================
CREATE TABLE sys_dict_item (
    id                   bigint PRIMARY KEY,
    dict_code            varchar(50),
    value                varchar(50),
    label                varchar(100),
    tag_type             varchar(50),
    status               smallint DEFAULT 0,
    sort                 integer DEFAULT 0,
    remark               varchar(255),
    create_time          timestamp,
    create_by            bigint,
    update_time          timestamp,
    update_by            bigint
);
COMMENT ON TABLE sys_dict_item IS '字典项表';
COMMENT ON COLUMN sys_dict_item.id IS '主键ID';
COMMENT ON COLUMN sys_dict_item.dict_code IS '关联字典编码';
COMMENT ON COLUMN sys_dict_item.value IS '字典项值';
COMMENT ON COLUMN sys_dict_item.label IS '字典项标签';
COMMENT ON COLUMN sys_dict_item.tag_type IS '标签类型';
COMMENT ON COLUMN sys_dict_item.status IS '状态 1-正常 0-禁用';
COMMENT ON COLUMN sys_dict_item.sort IS '排序';
COMMENT ON COLUMN sys_dict_item.remark IS '备注';
COMMENT ON COLUMN sys_dict_item.create_time IS '创建时间';
COMMENT ON COLUMN sys_dict_item.create_by IS '创建人ID';
COMMENT ON COLUMN sys_dict_item.update_time IS '更新时间';
COMMENT ON COLUMN sys_dict_item.update_by IS '修改人ID';

-- ==================== sys_log ====================
CREATE TABLE sys_log (
    id                   bigint PRIMARY KEY,
    module               smallint NOT NULL,
    action_type          smallint NOT NULL,
    title                varchar(100) NOT NULL,
    content              text,
    operator_id          bigint,
    operator_name        varchar(50),
    request_uri          varchar(255),
    request_method       varchar(10),
    ip                   varchar(45),
    province             varchar(100),
    city                 varchar(100),
    device               varchar(100),
    os                   varchar(100),
    browser              varchar(100),
    status               smallint DEFAULT 1,
    error_msg            varchar(255),
    execution_time       integer,
    create_time          timestamp
);
CREATE INDEX idx_module_action_time ON sys_log (module, action_type, create_time);
CREATE INDEX idx_operator_time ON sys_log (operator_id, create_time);
CREATE INDEX idx_time ON sys_log (create_time);
COMMENT ON TABLE sys_log IS '操作日志表';
COMMENT ON COLUMN sys_log.id IS '主键ID';
COMMENT ON COLUMN sys_log.module IS '模块 数字枚举';
COMMENT ON COLUMN sys_log.action_type IS '操作类型 数字枚举';
COMMENT ON COLUMN sys_log.title IS '显示标题';
COMMENT ON COLUMN sys_log.content IS '日志内容';
COMMENT ON COLUMN sys_log.operator_id IS '操作人ID';
COMMENT ON COLUMN sys_log.operator_name IS '操作人名称';
COMMENT ON COLUMN sys_log.request_uri IS '请求路径';
COMMENT ON COLUMN sys_log.request_method IS '请求方法';
COMMENT ON COLUMN sys_log.ip IS 'IP地址';
COMMENT ON COLUMN sys_log.province IS '省份';
COMMENT ON COLUMN sys_log.city IS '城市';
COMMENT ON COLUMN sys_log.device IS '设备';
COMMENT ON COLUMN sys_log.os IS '操作系统';
COMMENT ON COLUMN sys_log.browser IS '浏览器';
COMMENT ON COLUMN sys_log.status IS '0-失败 1-成功';
COMMENT ON COLUMN sys_log.error_msg IS '错误信息';
COMMENT ON COLUMN sys_log.execution_time IS '执行时间 ms';
COMMENT ON COLUMN sys_log.create_time IS '操作时间';

-- ==================== sys_menu ====================
CREATE TABLE sys_menu (
    id                   bigint PRIMARY KEY,
    parent_id            bigint NOT NULL,
    tree_path            varchar(255),
    name                 varchar(64) NOT NULL,
    type                 char(1) NOT NULL,
    route_name           varchar(255),
    route_path           varchar(128),
    component            varchar(128),
    perm                 varchar(128),
    external_url         varchar(512),
    always_show          smallint DEFAULT 0,
    keep_alive           smallint DEFAULT 0,
    visible              smallint DEFAULT 1,
    sort                 integer DEFAULT 0,
    icon                 varchar(64),
    redirect             varchar(128),
    create_time          timestamp,
    update_time          timestamp,
    params               jsonb
);
COMMENT ON TABLE sys_menu IS '菜单表';
COMMENT ON COLUMN sys_menu.id IS '主键ID';
COMMENT ON COLUMN sys_menu.parent_id IS '父菜单ID';
COMMENT ON COLUMN sys_menu.tree_path IS '父节点ID路径';
COMMENT ON COLUMN sys_menu.name IS '菜单名称';
COMMENT ON COLUMN sys_menu.type IS '菜单类型 C-目录 M-菜单 E-外链 B-按钮';
COMMENT ON COLUMN sys_menu.route_name IS '路由名称';
COMMENT ON COLUMN sys_menu.route_path IS '路由路径';
COMMENT ON COLUMN sys_menu.component IS '组件路径';
COMMENT ON COLUMN sys_menu.external_url IS '外链地址';
COMMENT ON COLUMN sys_menu.perm IS '权限标识';
COMMENT ON COLUMN sys_menu.always_show IS '目录-只有一个子路由是否始终显示';
COMMENT ON COLUMN sys_menu.keep_alive IS '菜单-是否开启页面缓存';
COMMENT ON COLUMN sys_menu.visible IS '显示状态 1-显示 0-隐藏';
COMMENT ON COLUMN sys_menu.sort IS '排序';
COMMENT ON COLUMN sys_menu.icon IS '菜单图标';
COMMENT ON COLUMN sys_menu.redirect IS '跳转路径';
COMMENT ON COLUMN sys_menu.create_time IS '创建时间';
COMMENT ON COLUMN sys_menu.update_time IS '更新时间';
COMMENT ON COLUMN sys_menu.params IS '路由参数';

-- ==================== sys_notice ====================
CREATE TABLE sys_notice (
    id                   bigint PRIMARY KEY,
    title                varchar(50),
    content              text,
    type                 smallint NOT NULL,
    level                varchar(5) NOT NULL,
    target_type          smallint NOT NULL,
    target_user_ids      varchar(255),
    publisher_id         bigint,
    publish_status       smallint DEFAULT 0,
    publish_time         timestamp,
    revoke_time          timestamp,
    create_by            bigint NOT NULL,
    create_time          timestamp NOT NULL,
    update_by            bigint,
    update_time          timestamp,
    is_deleted           smallint DEFAULT 0
);
COMMENT ON TABLE sys_notice IS '通知公告表';
COMMENT ON COLUMN sys_notice.id IS '主键ID';
COMMENT ON COLUMN sys_notice.title IS '通知标题';
COMMENT ON COLUMN sys_notice.content IS '通知内容';
COMMENT ON COLUMN sys_notice.type IS '通知类型 关联字典编码notice_type';
COMMENT ON COLUMN sys_notice.level IS '通知等级 L-低 M-中 H-高';
COMMENT ON COLUMN sys_notice.target_type IS '目标类型 1-全体 2-指定';
COMMENT ON COLUMN sys_notice.target_user_ids IS '目标用户ID 逗号分隔';
COMMENT ON COLUMN sys_notice.publisher_id IS '发布人ID';
COMMENT ON COLUMN sys_notice.publish_status IS '发布状态 0-未发布 1-已发布 -1-已撤回';
COMMENT ON COLUMN sys_notice.publish_time IS '发布时间';
COMMENT ON COLUMN sys_notice.revoke_time IS '撤回时间';
COMMENT ON COLUMN sys_notice.create_by IS '创建人ID';
COMMENT ON COLUMN sys_notice.create_time IS '创建时间';
COMMENT ON COLUMN sys_notice.update_by IS '修改人ID';
COMMENT ON COLUMN sys_notice.update_time IS '更新时间';
COMMENT ON COLUMN sys_notice.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_user_notice ====================
CREATE TABLE sys_user_notice (
    id                   bigint PRIMARY KEY,
    notice_id            bigint NOT NULL,
    user_id              bigint NOT NULL,
    is_read              smallint DEFAULT 0,
    read_time            timestamp,
    create_time          timestamp NOT NULL,
    update_time          timestamp,
    is_deleted           smallint DEFAULT 0
);
COMMENT ON TABLE sys_user_notice IS '用户通知关联表';
COMMENT ON COLUMN sys_user_notice.id IS '主键ID';
COMMENT ON COLUMN sys_user_notice.notice_id IS '通知ID';
COMMENT ON COLUMN sys_user_notice.user_id IS '用户ID';
COMMENT ON COLUMN sys_user_notice.is_read IS '读取状态 0-未读 1-已读';
COMMENT ON COLUMN sys_user_notice.read_time IS '阅读时间';
COMMENT ON COLUMN sys_user_notice.create_time IS '创建时间';
COMMENT ON COLUMN sys_user_notice.update_time IS '更新时间';
COMMENT ON COLUMN sys_user_notice.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_role ====================
CREATE TABLE sys_role (
    id                   bigint PRIMARY KEY,
    name                 varchar(64) NOT NULL,
    code                 varchar(32) NOT NULL,
    sort                 integer,
    status               smallint DEFAULT 1,
    data_scope           smallint,
    create_by            bigint,
    create_time          timestamp,
    update_by            bigint,
    update_time          timestamp,
    is_deleted           smallint DEFAULT 0
);
CREATE UNIQUE INDEX uk_name ON sys_role (name);
CREATE UNIQUE INDEX uk_role_code ON sys_role (code);
COMMENT ON TABLE sys_role IS '角色表';
COMMENT ON COLUMN sys_role.id IS '主键ID';
COMMENT ON COLUMN sys_role.name IS '角色名称';
COMMENT ON COLUMN sys_role.code IS '角色编码';
COMMENT ON COLUMN sys_role.sort IS '显示顺序';
COMMENT ON COLUMN sys_role.status IS '角色状态 1-正常 0-停用';
COMMENT ON COLUMN sys_role.data_scope IS '数据权限 1-所有 2-部门及子部门 3-本部门 4-本人 5-自定义部门';
COMMENT ON COLUMN sys_role.create_by IS '创建人ID';
COMMENT ON COLUMN sys_role.create_time IS '创建时间';
COMMENT ON COLUMN sys_role.update_by IS '更新人ID';
COMMENT ON COLUMN sys_role.update_time IS '更新时间';
COMMENT ON COLUMN sys_role.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_role_menu ====================
CREATE TABLE sys_role_menu (
    role_id              bigint NOT NULL,
    menu_id              bigint NOT NULL
);
CREATE UNIQUE INDEX uk_roleid_menuid ON sys_role_menu (role_id, menu_id);
COMMENT ON TABLE sys_role_menu IS '角色菜单关联表';
COMMENT ON COLUMN sys_role_menu.role_id IS '角色ID';
COMMENT ON COLUMN sys_role_menu.menu_id IS '菜单ID';

-- ==================== sys_role_dept ====================
CREATE TABLE sys_role_dept (
    role_id              bigint NOT NULL,
    dept_id              bigint NOT NULL
);
CREATE UNIQUE INDEX uk_roleid_deptid ON sys_role_dept (role_id, dept_id);
COMMENT ON TABLE sys_role_dept IS '角色部门关联表';
COMMENT ON COLUMN sys_role_dept.role_id IS '角色ID';
COMMENT ON COLUMN sys_role_dept.dept_id IS '部门ID';

-- ==================== sys_user ====================
CREATE TABLE sys_user (
    id                   bigint PRIMARY KEY,
    username             varchar(64),
    nickname             varchar(64),
    gender               smallint DEFAULT 1,
    password             varchar(100),
    dept_id              bigint,
    avatar               varchar(255),
    mobile               varchar(20),
    status               smallint DEFAULT 1,
    email                varchar(128),
    create_time          timestamp,
    create_by            bigint,
    update_time          timestamp,
    update_by            bigint,
    is_deleted           smallint DEFAULT 0
);
COMMENT ON TABLE sys_user IS '用户表';
COMMENT ON COLUMN sys_user.id IS '主键ID';
COMMENT ON COLUMN sys_user.username IS '用户名';
COMMENT ON COLUMN sys_user.nickname IS '昵称';
COMMENT ON COLUMN sys_user.gender IS '性别 1-男 2-女 0-保密';
COMMENT ON COLUMN sys_user.password IS '密码';
COMMENT ON COLUMN sys_user.dept_id IS '部门ID';
COMMENT ON COLUMN sys_user.avatar IS '头像URL';
COMMENT ON COLUMN sys_user.mobile IS '手机号';
COMMENT ON COLUMN sys_user.status IS '状态 1-启用 0-禁用';
COMMENT ON COLUMN sys_user.email IS '邮箱';
COMMENT ON COLUMN sys_user.create_time IS '创建时间';
COMMENT ON COLUMN sys_user.create_by IS '创建人ID';
COMMENT ON COLUMN sys_user.update_time IS '更新时间';
COMMENT ON COLUMN sys_user.update_by IS '修改人ID';
COMMENT ON COLUMN sys_user.is_deleted IS '逻辑删除 0-未删除 1-已删除';

-- ==================== sys_user_role ====================
CREATE TABLE sys_user_role (
    user_id              bigint NOT NULL,
    role_id              bigint NOT NULL,
    PRIMARY KEY (user_id, role_id)
);
COMMENT ON TABLE sys_user_role IS '用户角色关联表';
COMMENT ON COLUMN sys_user_role.user_id IS '用户ID';
COMMENT ON COLUMN sys_user_role.role_id IS '角色ID';

-- ==================== sys_user_social ====================
CREATE TABLE sys_user_social (
    id                   bigint PRIMARY KEY,
    user_id              bigint NOT NULL,
    platform             varchar(20) NOT NULL,
    openid               varchar(64) NOT NULL,
    unionid              varchar(64),
    nickname             varchar(64),
    avatar               varchar(255),
    session_key          varchar(128),
    verified             smallint DEFAULT 1,
    create_time          timestamp,
    update_time          timestamp
);
CREATE UNIQUE INDEX uk_platform_openid ON sys_user_social (platform, openid);
CREATE INDEX idx_user_id ON sys_user_social (user_id);
CREATE INDEX idx_unionid ON sys_user_social (unionid);
COMMENT ON TABLE sys_user_social IS '用户社交账号表';
COMMENT ON COLUMN sys_user_social.id IS '主键ID';
COMMENT ON COLUMN sys_user_social.user_id IS '用户ID';
COMMENT ON COLUMN sys_user_social.platform IS '平台类型 WECHAT_MINI/WECHAT_MP/ALIPAY/QQ/APPLE';
COMMENT ON COLUMN sys_user_social.openid IS '平台openid';
COMMENT ON COLUMN sys_user_social.unionid IS '微信unionid';
COMMENT ON COLUMN sys_user_social.nickname IS '第三方昵称';
COMMENT ON COLUMN sys_user_social.avatar IS '第三方头像URL';
COMMENT ON COLUMN sys_user_social.session_key IS '微信session_key';
COMMENT ON COLUMN sys_user_social.verified IS '是否已验证 1-已验证 0-未验证';
COMMENT ON COLUMN sys_user_social.create_time IS '绑定时间';
COMMENT ON COLUMN sys_user_social.update_time IS '更新时间';

-- ----------------------------
-- 种子数据
-- ----------------------------

-- sys_dept
INSERT INTO sys_dept VALUES (1, '有来技术', 'YOULAI', 0, '0', 1, 1, 1, NULL, 1, now(), 0);
INSERT INTO sys_dept VALUES (2, '研发部门', 'RD001', 1, '0,1', 1, 1, 2, NULL, 2, now(), 0);
INSERT INTO sys_dept VALUES (3, '测试部门', 'QA001', 1, '0,1', 1, 1, 2, NULL, 2, now(), 0);

-- sys_dict
INSERT INTO sys_dict VALUES (1, 'gender', '性别', 1, NULL, now(), 1, now(), 1, 0);
INSERT INTO sys_dict VALUES (2, 'notice_type', '通知类型', 1, NULL, now(), 1, now(), 1, 0);
INSERT INTO sys_dict VALUES (3, 'notice_level', '通知级别', 1, NULL, now(), 1, now(), 1, 0);

-- sys_dict_item
INSERT INTO sys_dict_item VALUES (1, 'gender', '1', '男', 'primary', 1, 1, NULL, now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (2, 'gender', '2', '女', 'danger', 1, 2, NULL, now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (3, 'gender', '0', '保密', 'info', 1, 3, NULL, now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (4, 'notice_type', '1', '系统升级', 'success', 1, 1, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (5, 'notice_type', '2', '系统维护', 'primary', 1, 2, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (6, 'notice_type', '3', '安全警告', 'danger', 1, 3, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (7, 'notice_type', '4', '假期通知', 'success', 1, 4, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (8, 'notice_type', '5', '公司新闻', 'primary', 1, 5, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (9, 'notice_type', '99', '其他', 'info', 1, 99, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (10, 'notice_level', 'L', '低', 'info', 1, 1, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (11, 'notice_level', 'M', '中', 'warning', 1, 2, '', now(), 1, now(), 1);
INSERT INTO sys_dict_item VALUES (12, 'notice_level', 'H', '高', 'danger', 1, 3, '', now(), 1, now(), 1);

-- sys_menu (标准 youlai-admin 菜单 + 代码生成)
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (1, 0, '0', '系统管理', 'C', '', '/system', 'Layout', NULL, NULL, NULL, 1, 1, 'system', '/system/user', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2, 0, '0', '代码生成', 'C', '', '/codegen', 'Layout', NULL, NULL, NULL, 1, 2, 'code', '/codegen/index', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (4, 0, '0', '平台文档', 'C', '', '/doc', 'Layout', NULL, NULL, NULL, 1, 4, 'document', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (5, 0, '0', '接口文档', 'C', '', '/api', 'Layout', NULL, NULL, NULL, 1, 5, 'api', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (6, 0, '0', '组件封装', 'C', '', '/component', 'Layout', NULL, NULL, NULL, 1, 6, 'menu', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (7, 0, '0', '功能演示', 'C', '', '/function', 'Layout', NULL, NULL, NULL, 1, 7, 'menu', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (8, 0, '0', '多级菜单', 'C', NULL, '/multi-level', 'Layout', NULL, 1, NULL, 1, 8, 'cascader', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (9, 0, '0', '路由参数', 'C', '', '/route-param', 'Layout', NULL, NULL, NULL, 1, 9, 'el-icon-ElementPlus', '', now(), now(), NULL);

-- 系统管理子菜单
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (210, 1, '0,1', '用户管理', 'M', 'User', 'user', 'system/user/index', NULL, NULL, 1, 1, 1, 'el-icon-User', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2101, 210, '0,1,210', '用户查询', 'B', NULL, '', NULL, 'sys:user:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2102, 210, '0,1,210', '用户新增', 'B', NULL, '', NULL, 'sys:user:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2103, 210, '0,1,210', '用户编辑', 'B', NULL, '', NULL, 'sys:user:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2104, 210, '0,1,210', '用户删除', 'B', NULL, '', NULL, 'sys:user:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2105, 210, '0,1,210', '重置密码', 'B', NULL, '', NULL, 'sys:user:reset-password', NULL, NULL, 1, 5, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2106, 210, '0,1,210', '用户导入', 'B', NULL, '', NULL, 'sys:user:import', NULL, NULL, 1, 6, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2107, 210, '0,1,210', '用户导出', 'B', NULL, '', NULL, 'sys:user:export', NULL, NULL, 1, 7, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (220, 1, '0,1', '角色管理', 'M', 'Role', 'role', 'system/role/index', NULL, NULL, 1, 1, 2, 'role', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2201, 220, '0,1,220', '角色查询', 'B', NULL, '', NULL, 'sys:role:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2202, 220, '0,1,220', '角色新增', 'B', NULL, '', NULL, 'sys:role:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2203, 220, '0,1,220', '角色编辑', 'B', NULL, '', NULL, 'sys:role:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2204, 220, '0,1,220', '角色删除', 'B', NULL, '', NULL, 'sys:role:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2205, 220, '0,1,220', '角色分配权限', 'B', NULL, '', NULL, 'sys:role:assign', NULL, NULL, 1, 5, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (230, 1, '0,1', '菜单管理', 'M', 'SysMenu', 'menu', 'system/menu/index', NULL, NULL, 1, 1, 3, 'menu', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2301, 230, '0,1,230', '菜单查询', 'B', NULL, '', NULL, 'sys:menu:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2302, 230, '0,1,230', '菜单新增', 'B', NULL, '', NULL, 'sys:menu:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2303, 230, '0,1,230', '菜单编辑', 'B', NULL, '', NULL, 'sys:menu:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2304, 230, '0,1,230', '菜单删除', 'B', NULL, '', NULL, 'sys:menu:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (240, 1, '0,1', '部门管理', 'M', 'Dept', 'dept', 'system/dept/index', NULL, NULL, 1, 1, 4, 'tree', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2401, 240, '0,1,240', '部门查询', 'B', NULL, '', NULL, 'sys:dept:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2402, 240, '0,1,240', '部门新增', 'B', NULL, '', NULL, 'sys:dept:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2403, 240, '0,1,240', '部门编辑', 'B', NULL, '', NULL, 'sys:dept:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2404, 240, '0,1,240', '部门删除', 'B', NULL, '', NULL, 'sys:dept:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (250, 1, '0,1', '字典管理', 'M', 'Dict', 'dict', 'system/dict/index', NULL, NULL, 1, 1, 5, 'dict', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2501, 250, '0,1,250', '字典查询', 'B', NULL, '', NULL, 'sys:dict:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2502, 250, '0,1,250', '字典新增', 'B', NULL, '', NULL, 'sys:dict:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2503, 250, '0,1,250', '字典编辑', 'B', NULL, '', NULL, 'sys:dict:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2504, 250, '0,1,250', '字典删除', 'B', NULL, '', NULL, 'sys:dict:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (251, 1, '0,1', '字典项', 'M', 'DictItem', 'dict-item', 'system/dict/dict-item', NULL, 0, 1, 0, 6, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2511, 251, '0,1,251', '字典项查询', 'B', NULL, '', NULL, 'sys:dict-item:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2512, 251, '0,1,251', '字典项新增', 'B', NULL, '', NULL, 'sys:dict-item:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2513, 251, '0,1,251', '字典项编辑', 'B', NULL, '', NULL, 'sys:dict-item:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2514, 251, '0,1,251', '字典项删除', 'B', NULL, '', NULL, 'sys:dict-item:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (260, 1, '0,1', '系统日志', 'M', 'Log', 'log', 'system/log/index', NULL, 0, 1, 1, 7, 'document', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2601, 260, '0,1,260', '日志查询', 'B', NULL, '', NULL, 'sys:log:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (270, 1, '0,1', '系统配置', 'M', 'Config', 'config', 'system/config/index', NULL, 0, 1, 1, 8, 'setting', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2701, 270, '0,1,270', '系统配置查询', 'B', NULL, '', NULL, 'sys:config:list', 0, 1, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2702, 270, '0,1,270', '系统配置新增', 'B', NULL, '', NULL, 'sys:config:create', 0, 1, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2703, 270, '0,1,270', '系统配置修改', 'B', NULL, '', NULL, 'sys:config:update', 0, 1, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2704, 270, '0,1,270', '系统配置删除', 'B', NULL, '', NULL, 'sys:config:delete', 0, 1, 1, 4, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2705, 270, '0,1,270', '系统配置刷新', 'B', NULL, '', NULL, 'sys:config:refresh', 0, 1, 1, 5, '', NULL, now(), now(), NULL);

INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (280, 1, '0,1', '通知公告', 'M', 'Notice', 'notice', 'system/notice/index', NULL, NULL, NULL, 1, 9, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2801, 280, '0,1,280', '通知查询', 'B', NULL, '', NULL, 'sys:notice:list', NULL, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2802, 280, '0,1,280', '通知新增', 'B', NULL, '', NULL, 'sys:notice:create', NULL, NULL, 1, 2, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2803, 280, '0,1,280', '通知编辑', 'B', NULL, '', NULL, 'sys:notice:update', NULL, NULL, 1, 3, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2804, 280, '0,1,280', '通知删除', 'B', NULL, '', NULL, 'sys:notice:delete', NULL, NULL, 1, 4, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2805, 280, '0,1,280', '通知发布', 'B', NULL, '', NULL, 'sys:notice:publish', 0, 1, 1, 5, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (2806, 280, '0,1,280', '通知撤回', 'B', NULL, '', NULL, 'sys:notice:revoke', 0, 1, 1, 6, '', NULL, now(), now(), NULL);

-- 代码生成
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (310, 2, '0,2', '代码生成', 'M', 'Codegen', 'codegen', 'codegen/index', NULL, NULL, 1, 1, 1, 'code', NULL, now(), now(), NULL);

-- 平台文档
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, external_url, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (501, 4, '0,4', '平台文档(外链)', 'E', NULL, NULL, NULL, 'https://juejin.cn/post/7228990409909108793', NULL, NULL, NULL, 1, 1, 'document', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, external_url, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (502, 4, '0,4', '后端文档', 'E', NULL, NULL, NULL, 'https://youlai.blog.csdn.net/article/details/145178880', NULL, NULL, NULL, 1, 2, 'document', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, external_url, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (503, 4, '0,4', '移动端文档', 'E', NULL, NULL, NULL, 'https://youlai.blog.csdn.net/article/details/143222890', NULL, NULL, NULL, 1, 3, 'document', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, external_url, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (504, 4, '0,4', '内部文档', 'E', 'InternalDoc', 'internal-doc', 'iframe', 'https://juejin.cn/post/7228990409909108793', NULL, NULL, 1, 1, 4, 'document', '', now(), now(), NULL);

-- 接口文档
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (601, 5, '0,5', 'Apifox', 'M', 'Apifox', 'apifox', 'demo/api/apifox', NULL, NULL, 1, 1, 1, 'api', '', now(), now(), NULL);

-- 组件封装
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (701, 6, '0,6', '富文本编辑器', 'M', 'WangEditor', 'wang-editor', 'demo/wang-editor', NULL, NULL, 1, 1, 2, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (702, 6, '0,6', '图片上传', 'M', 'Upload', 'upload', 'demo/upload', NULL, NULL, 1, 1, 3, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (703, 6, '0,6', '图标选择器', 'M', 'DemoIconSelect', 'icon-select', 'demo/icon-select', NULL, NULL, 1, 1, 4, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (704, 6, '0,6', '字典组件', 'M', 'DictDemo', 'dict-demo', 'demo/dictionary', NULL, NULL, 1, 1, 4, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (705, 6, '0,6', '增删改查', 'M', 'Curd', 'curd', 'demo/curd/index', NULL, NULL, 1, 1, 0, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (706, 6, '0,6', '列表选择器', 'M', 'TableSelect', 'table-select', 'demo/table-select/index', NULL, NULL, 1, 1, 1, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (707, 6, '0,6', '拖拽组件', 'M', 'Drag', 'drag', 'demo/drag', NULL, NULL, NULL, 1, 5, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (708, 6, '0,6', '滚动文本', 'M', 'TextScroll', 'text-scroll', 'demo/text-scroll', NULL, NULL, NULL, 1, 6, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (709, 6, '0,6', '自适应表格操作列', 'M', 'AutoOperationColumn', 'operation-column', 'demo/auto-operation-column', NULL, NULL, 1, 1, 1, '', '', now(), now(), NULL);

-- 功能演示 / 多级菜单 / 路由参数
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (801, 7, '0,7', 'Icons', 'M', 'IconDemo', 'icon-demo', 'demo/icons', NULL, NULL, 1, 1, 2, 'el-icon-Notification', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (802, 7, '0,7', '字典实时同步', 'M', 'DictSync', 'dict-sync', 'demo/dict-sync', NULL, NULL, NULL, 1, 3, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (803, 7, '0,7', 'VxeTable', 'M', 'VxeTable', 'vxe-table', 'demo/vxe-table/index', NULL, NULL, 1, 1, 4, 'el-icon-MagicStick', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (804, 7, '0,7', 'CURD单文件', 'M', 'CurdSingle', 'curd-single', 'demo/curd-single', NULL, NULL, 1, 1, 5, 'el-icon-Reading', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (910, 8, '0,8', '菜单一级', 'C', NULL, 'multi-level1', 'Layout', NULL, 1, NULL, 1, 1, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (911, 910, '0,8,910', '菜单二级', 'C', NULL, 'multi-level2', 'Layout', NULL, 0, NULL, 1, 1, '', NULL, now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (912, 911, '0,8,910,911', '菜单三级-1', 'M', NULL, 'multi-level3-1', 'demo/multi-level/children/children/level3-1', NULL, 0, 1, 1, 1, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (913, 911, '0,8,910,911', '菜单三级-2', 'M', NULL, 'multi-level3-2', 'demo/multi-level/children/children/level3-2', NULL, 0, 1, 1, 2, '', '', now(), now(), NULL);
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (1001, 9, '0,9', '参数(type=1)', 'M', 'RouteParamType1', 'route-param-type1', 'demo/route-param', NULL, 0, 1, 1, 1, 'el-icon-Star', NULL, now(), now(), '{"type": "1"}');
INSERT INTO sys_menu (id, parent_id, tree_path, name, type, route_name, route_path, component, perm, always_show, keep_alive, visible, sort, icon, redirect, create_time, update_time, params) VALUES (1002, 9, '0,9', '参数(type=2)', 'M', 'RouteParamType2', 'route-param-type2', 'demo/route-param', NULL, 0, 1, 1, 2, 'el-icon-StarFilled', NULL, now(), now(), '{"type": "2"}');

-- sys_role
INSERT INTO sys_role VALUES (1, '超级管理员', 'ROOT', 1, 1, 1, NULL, now(), NULL, now(), 0);
INSERT INTO sys_role VALUES (2, '系统管理员', 'ADMIN', 2, 1, 1, NULL, now(), NULL, NULL, 0);
INSERT INTO sys_role VALUES (3, '访问游客', 'GUEST', 3, 1, 3, NULL, now(), NULL, now(), 0);
INSERT INTO sys_role VALUES (4, '部门主管', 'DEPT_MANAGER', 4, 1, 2, NULL, now(), NULL, now(), 0);
INSERT INTO sys_role VALUES (5, '部门成员', 'DEPT_MEMBER', 5, 1, 3, NULL, now(), NULL, now(), 0);
INSERT INTO sys_role VALUES (6, '普通员工', 'EMPLOYEE', 6, 1, 4, NULL, now(), NULL, now(), 0);
INSERT INTO sys_role VALUES (7, '自定义权限用户', 'CUSTOM_USER', 7, 1, 5, NULL, now(), NULL, now(), 0);

-- sys_role_dept
INSERT INTO sys_role_dept VALUES (7, 1) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_dept VALUES (7, 2) ON CONFLICT DO NOTHING;

-- sys_role_menu (管理员角色菜单权限)
INSERT INTO sys_role_menu VALUES (2, 1), (2, 2), (2, 4), (2, 5), (2, 6), (2, 7), (2, 8), (2, 9) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 210), (2, 2101), (2, 2102), (2, 2103), (2, 2104), (2, 2105), (2, 2106), (2, 2107) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 220), (2, 2201), (2, 2202), (2, 2203), (2, 2204), (2, 2205) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 230), (2, 2301), (2, 2302), (2, 2303), (2, 2304) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 240), (2, 2401), (2, 2402), (2, 2403), (2, 2404) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 250), (2, 2501), (2, 2502), (2, 2503), (2, 2504) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 251), (2, 2511), (2, 2512), (2, 2513), (2, 2514) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 260), (2, 2601) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 270), (2, 2701), (2, 2702), (2, 2703), (2, 2704), (2, 2705) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 280), (2, 2801), (2, 2802), (2, 2803), (2, 2804), (2, 2805), (2, 2806) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (4, 1) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (4, 210), (4, 2101), (4, 2102), (4, 2103), (4, 2104), (4, 2105), (4, 2106), (4, 2107) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (4, 220), (4, 2201), (4, 2202), (4, 2203), (4, 2204), (4, 2205) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (5, 1) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (5, 210), (5, 2101), (5, 2102), (5, 2103), (5, 2104), (5, 2105), (5, 2106), (5, 2107) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (5, 220), (5, 2201), (5, 2202), (5, 2203), (5, 2204), (5, 2205) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (6, 1) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (6, 210), (6, 2101), (6, 2102), (6, 2103), (6, 2104), (6, 2105), (6, 2106), (6, 2107) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (6, 220), (6, 2201), (6, 2202), (6, 2203), (6, 2204), (6, 2205) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (7, 1) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (7, 210), (7, 2101), (7, 2102), (7, 2103), (7, 2104), (7, 2105), (7, 2106), (7, 2107) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (7, 220), (7, 2201), (7, 2202), (7, 2203), (7, 2204), (7, 2205) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 310) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 501), (2, 502), (2, 503), (2, 504) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 601) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 701), (2, 702), (2, 703), (2, 704), (2, 705), (2, 706), (2, 707), (2, 708), (2, 709) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 801), (2, 802), (2, 803), (2, 804), (2, 910), (2, 911), (2, 912), (2, 913) ON CONFLICT DO NOTHING;
INSERT INTO sys_role_menu VALUES (2, 1001), (2, 1002) ON CONFLICT DO NOTHING;

-- sys_user
INSERT INTO sys_user VALUES (1, 'root', '有来技术', 0, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', NULL, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18812345677', 1, 'youlaitech@163.com', now(), NULL, now(), NULL, 0);
INSERT INTO sys_user VALUES (2, 'admin', '系统管理员', 1, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', 1, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18888888888', 1, 'youlaitech@163.com', now(), NULL, now(), NULL, 0);
INSERT INTO sys_user VALUES (3, 'test', '测试小用户', 1, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', 3, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18812345679', 1, 'youlaitech@163.com', now(), NULL, now(), NULL, 0);
INSERT INTO sys_user VALUES (4, 'dept_manager', '部门主管', 1, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', 1, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18812345680', 1, 'manager@youlaitech.com', now(), NULL, now(), NULL, 0);
INSERT INTO sys_user VALUES (5, 'dept_member', '部门成员', 1, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', 1, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18812345681', 1, 'member@youlaitech.com', now(), NULL, now(), NULL, 0);
INSERT INTO sys_user VALUES (6, 'employee', '普通员工', 1, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', 2, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18812345682', 1, 'employee@youlaitech.com', now(), NULL, now(), NULL, 0);
INSERT INTO sys_user VALUES (7, 'custom_user', '自定义权限用户', 1, '$2a$10$xVWsNOhHrCxh5UbpCE7/HuJ.PAOKcYAqRxD2CO2nVnJS.IAXkr5aq', 3, 'https://foruda.gitee.com/images/1723603502796844527/03cdca2a_716974.gif', '18812345683', 1, 'custom@youlaitech.com', now(), NULL, now(), NULL, 0);

-- sys_user_role
INSERT INTO sys_user_role VALUES (1, 1) ON CONFLICT DO NOTHING;
INSERT INTO sys_user_role VALUES (2, 2) ON CONFLICT DO NOTHING;
INSERT INTO sys_user_role VALUES (3, 3) ON CONFLICT DO NOTHING;
INSERT INTO sys_user_role VALUES (4, 4) ON CONFLICT DO NOTHING;
INSERT INTO sys_user_role VALUES (5, 5) ON CONFLICT DO NOTHING;
INSERT INTO sys_user_role VALUES (6, 6) ON CONFLICT DO NOTHING;
INSERT INTO sys_user_role VALUES (7, 7) ON CONFLICT DO NOTHING;

-- sys_config
INSERT INTO sys_config VALUES (1, '系统限流QPS', 'IP_QPS_THRESHOLD_LIMIT', '10', '单个IP请求的最大每秒查询数（QPS）阈值Key', now(), 1, NULL, NULL, 0);

-- sys_notice
INSERT INTO sys_notice VALUES (1, 'v3.0.0 版本发布 - 多租户功能上线', '<p>新版本发布，主要更新内容：</p><p>1. 新增多租户功能，支持租户隔离和数据管理</p><p>2. 优化系统性能，提升响应速度</p><p>3. 完善权限管理，增强安全性</p><p>4. 修复已知问题，提升系统稳定性</p>', 1, 'H', 1, NULL, 1, 1, '2024-12-15 10:00:00', NULL, 1, '2024-12-15 10:00:00', 1, '2024-12-15 10:00:00', 0);
INSERT INTO sys_notice VALUES (2, '系统维护通知 - 2024年12月20日', '<p>系统维护通知</p><p>系统将于 <strong>2024年12月20日（本周五）凌晨 2:00-4:00</strong> 进行例行维护升级。</p><p>维护期间系统将暂停服务，请提前做好数据备份工作。</p><p>给您带来的不便，敬请谅解！</p>', 2, 'H', 1, NULL, 1, 1, '2024-12-18 14:30:00', NULL, 1, '2024-12-18 14:30:00', 1, '2024-12-18 14:30:00', 0);
INSERT INTO sys_notice VALUES (3, '安全提醒 - 防范钓鱼邮件', '<p>安全提醒</p><p>近期发现有不法分子通过钓鱼邮件进行网络攻击，请大家提高警惕：</p><p>1. 不要点击来源不明的邮件链接</p><p>2. 不要下载可疑附件</p><p>3. 遇到可疑邮件请及时联系IT部门</p><p>4. 定期修改密码，使用强密码策略</p>', 3, 'H', 1, NULL, 1, 1, '2024-12-10 09:00:00', NULL, 1, '2024-12-10 09:00:00', 1, '2024-12-10 09:00:00', 0);
INSERT INTO sys_notice VALUES (4, '元旦假期安排通知', '<p>元旦假期安排</p><p>根据国家法定节假日安排，公司元旦假期时间为：</p><p><strong>2024年12月30日（周一）至 2025年1月1日（周三）</strong>，共3天。</p><p>2024年12月29日（周日）正常上班。</p><p>祝大家元旦快乐，假期愉快！</p>', 4, 'M', 1, NULL, 1, 1, '2024-12-25 16:00:00', NULL, 1, '2024-12-25 16:00:00', 1, '2024-12-25 16:00:00', 0);
INSERT INTO sys_notice VALUES (5, '新产品发布会邀请', '<p>新产品发布会邀请</p><p>公司将于 <strong>2025年1月15日下午14:00</strong> 在总部会议室举办新产品发布会。</p><p>届时将展示最新研发的产品和技术成果，欢迎全体员工参加。</p><p>请各部门提前安排好工作，准时参加。</p>', 5, 'M', 1, NULL, 1, 1, '2024-12-28 11:00:00', NULL, 1, '2024-12-28 11:00:00', 1, '2024-12-28 11:00:00', 0);
INSERT INTO sys_notice VALUES (6, 'v2.16.1 版本更新', '<p>版本更新</p><p>v2.16.1 版本已发布，主要修复内容：</p><p>1. 修复 WebSocket 重复连接导致的后台线程阻塞问题</p><p>2. 优化通知公告功能，提升用户体验</p><p>3. 修复部分已知bug</p><p>建议尽快更新到最新版本。</p>', 1, 'M', 1, NULL, 1, 1, '2024-12-05 15:30:00', NULL, 1, '2024-12-05 15:30:00', 1, '2024-12-05 15:30:00', 0);
INSERT INTO sys_notice VALUES (7, '年终总结会议通知', '<p>年终总结会议通知</p><p>各部门年终总结会议将于 <strong>2024年12月30日上午9:00</strong> 召开。</p><p>请各部门负责人提前准备好年度工作总结和下年度工作计划。</p><p>会议地点：总部大会议室</p>', 5, 'M', 2, '1,2', 1, 1, '2024-12-22 10:00:00', NULL, 1, '2024-12-22 10:00:00', 1, '2024-12-22 10:00:00', 0);
INSERT INTO sys_notice VALUES (8, '系统功能优化完成', '<p>系统功能优化</p><p>已完成以下功能优化：</p><p>1. 优化用户管理界面，提升操作体验</p><p>2. 增强数据导出功能，支持更多格式</p><p>3. 优化搜索功能，提升查询效率</p><p>4. 修复部分界面显示问题</p>', 1, 'L', 1, NULL, 1, 1, '2024-12-12 14:20:00', NULL, 1, '2024-12-12 14:20:00', 1, '2024-12-12 14:20:00', 0);
INSERT INTO sys_notice VALUES (9, '员工培训计划', '<p>员工培训计划</p><p>为提升员工专业技能，公司将于 <strong>2025年1月8日-10日</strong> 组织技术培训。</p><p>培训内容：</p><p>1. 新技术框架应用</p><p>2. 代码规范与最佳实践</p><p>3. 系统架构设计</p><p>请各部门合理安排工作，确保培训顺利进行。</p>', 5, 'M', 1, NULL, 1, 1, '2024-12-20 09:30:00', NULL, 1, '2024-12-20 09:30:00', 1, '2024-12-20 09:30:00', 0);
INSERT INTO sys_notice VALUES (10, '数据备份提醒', '<p>数据备份提醒</p><p>请各部门注意定期备份重要数据，建议每周至少备份一次。</p><p>备份方式：</p><p>1. 使用系统自带备份功能</p><p>2. 手动导出重要数据</p><p>3. 联系IT部门协助备份</p><p>数据安全，人人有责！</p>', 3, 'L', 1, NULL, 1, 1, '2024-12-08 08:00:00', NULL, 1, '2024-12-08 08:00:00', 1, '2024-12-08 08:00:00', 0);

-- sys_user_notice
INSERT INTO sys_user_notice VALUES (1, 1, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (2, 2, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (3, 3, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (4, 4, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (5, 5, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (6, 6, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (7, 7, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (8, 8, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (9, 9, 2, 1, NULL, now(), now(), 0);
INSERT INTO sys_user_notice VALUES (10, 10, 2, 1, NULL, now(), now(), 0);

-- 重置序列
SELECT setval(pg_get_serial_sequence('sys_dept', 'id'), COALESCE((SELECT MAX(id) FROM sys_dept), 1));
SELECT setval(pg_get_serial_sequence('sys_dict', 'id'), COALESCE((SELECT MAX(id) FROM sys_dict), 1));
SELECT setval(pg_get_serial_sequence('sys_dict_item', 'id'), COALESCE((SELECT MAX(id) FROM sys_dict_item), 1));
SELECT setval(pg_get_serial_sequence('sys_menu', 'id'), COALESCE((SELECT MAX(id) FROM sys_menu), 1));
SELECT setval(pg_get_serial_sequence('sys_role', 'id'), COALESCE((SELECT MAX(id) FROM sys_role), 1));
SELECT setval(pg_get_serial_sequence('sys_user', 'id'), COALESCE((SELECT MAX(id) FROM sys_user), 1));
SELECT setval(pg_get_serial_sequence('sys_log', 'id'), COALESCE((SELECT MAX(id) FROM sys_log), 1));
SELECT setval(pg_get_serial_sequence('sys_config', 'id'), COALESCE((SELECT MAX(id) FROM sys_config), 1));
SELECT setval(pg_get_serial_sequence('sys_notice', 'id'), COALESCE((SELECT MAX(id) FROM sys_notice), 1));
SELECT setval(pg_get_serial_sequence('sys_user_notice', 'id'), COALESCE((SELECT MAX(id) FROM sys_user_notice), 1));
SELECT setval(pg_get_serial_sequence('sys_user_social', 'id'), COALESCE((SELECT MAX(id) FROM sys_user_social), 1));

-- ============================================================
-- youlai-admin.sql 初始化完成
-- ============================================================
