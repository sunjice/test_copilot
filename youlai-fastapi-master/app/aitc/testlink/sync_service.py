"""TestLink 同步服务（拉取方向：TestLink → 本地）。

基于 3 个接口实现全量同步：
    get_tree_nodes(root) 递归拉套件树 → upsert AiTcSuite
    get_tree_nodes(suite) 取用例节点 → get_case_detail 批量取详情
    parse_case_to_local 映射 → upsert AiTcCase

双轨策略（方案 §3.3）：
    原文 HTML → *_raw；清洗 → 结构化字段；steps → 结构化解析 + steps_parse_status。

增量同步/冲突处理在 monitor.py 调用（本文件提供 pull_cases 作为基础单元）。
"""

import asyncio
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.aitc.case.models import AiTcCase, AiTcProject, AiTcSuite
from app.aitc.testlink.base import TestLinkClient
from app.aitc.testlink.hashing import content_hash
from app.aitc.testlink.models import AiTcSyncLog
from app.aitc.testlink.parser import parse_case_to_local


class TestLinkSyncService:
    """拉取同步服务。"""

    def __init__(self, client: TestLinkClient, db: AsyncSession) -> None:
        self.client = client
        self.db = db

    async def sync_project(self, project_id: int) -> dict:
        """全量同步指定本地项目。

        流程：
            1. 校验项目已配置 testlink_project_id
            2. get_tree_nodes(root) 递归拉套件树，按 testlink_suite_id upsert AiTcSuite
            3. 遍历套件，get_tree_nodes(suite) 取用例节点
            4. get_case_detail 批量取详情，parse_case_to_local 映射 upsert AiTcCase
        """
        stats = {
            "suites_created": 0, "suites_updated": 0,
            "cases_created": 0, "cases_updated": 0,
            "cases_deleted": 0, "conflicts": 0, "failed": 0, "errors": [],
        }

        project = await self.db.get(AiTcProject, project_id)
        if project is None or project.testlink_project_id is None:
            stats["failed"] += 1
            stats["errors"].append(f"项目 {project_id} 未配置 testlink_project_id")
            return stats

        # 1. 递归拉套件树
        suite_ids = await self._sync_suite_tree(project_id, stats)

        # 2. 遍历套件拉用例
        for sid in suite_ids:
            try:
                await self.pull_cases(sid, stats)
            except Exception as e:  # noqa: BLE001
                stats["failed"] += 1
                stats["errors"].append(f"套件 {sid} 拉取用例失败: {e}")

        await self._log("pull", "sync", 1, project_id, f"全量同步完成 {stats}")
        await self.db.commit()
        return stats

    async def _sync_suite_tree(self, project_id: int, stats: dict) -> list[int]:
        """递归拉取套件树并 upsert，返回本地套件 ID 列表。"""
        nodes = await self.client.get_tree_nodes(root_node="root")

        # node_id -> 本地 suite_id 映射
        local_suite_ids: list[int] = []
        # 用队列做 BFS：node + 本地 parent_id
        queue: list[tuple[dict, int]] = []
        # 顶层套件 parent_id=0
        for n in nodes:
            if n.type == "test_suite":
                queue.append((n, 0))

        while queue:
            node, parent_id = queue.pop(0)
            suite_id = await self._upsert_suite(project_id, node, parent_id, stats)
            local_suite_ids.append(suite_id)
            # 拉子节点
            children = await self.client.get_tree_nodes(node_id=node.node_id)
            for child in children:
                if child.type == "test_suite":
                    queue.append((child, suite_id))

        return local_suite_ids

    async def _upsert_suite(self, project_id: int, node, parent_id: int, stats: dict) -> int:
        """按 testlink_suite_id 匹配 upsert 套件，返回本地 suite id。"""
        tl_suite_id = int(node.node_id) if str(node.node_id).isdigit() else None

        existing = None
        if tl_suite_id is not None:
            row = await self.db.execute(
                select(AiTcSuite).where(
                    AiTcSuite.testlink_suite_id == tl_suite_id,
                    AiTcSuite.project_id == project_id,
                    AiTcSuite.is_deleted == 0,
                )
            )
            existing = row.scalar_one_or_none()

        if existing is not None:
            existing.name = node.name
            existing.parent_id = parent_id
            stats["suites_updated"] += 1
            return existing.id

        suite = AiTcSuite(
            project_id=project_id,
            parent_id=parent_id,
            name=node.name,
            testlink_suite_id=tl_suite_id,
            sort_order=0,
        )
        self.db.add(suite)
        await self.db.flush()
        stats["suites_created"] += 1
        return suite.id

    async def pull_cases(self, suite_id: int, stats: dict | None = None) -> list[int]:
        """拉取指定套件（含子套件）的用例详情并落库。

        Returns:
            同步的 AiTcCase.id 列表
        """
        stats = stats or {}
        suite = await self.db.get(AiTcSuite, suite_id)
        if suite is None:
            return []

        # 递归收集该套件及其所有子套件（本地 id → testlink_suite_id 映射）
        suite_ids = await self._collect_subtree_suites(suite_id)

        synced_case_ids: list[int] = []
        for sid in suite_ids:
            # 取该套件对应的 TestLink suite node_id
            s = await self.db.get(AiTcSuite, sid)
            if s is None or s.testlink_suite_id is None:
                continue
            # 取该套件下的用例节点（用 TestLink 的 node_id）
            try:
                nodes = await self.client.get_tree_nodes(node_id=str(s.testlink_suite_id))
            except Exception:  # noqa: BLE001
                nodes = []

            # 从节点收集 case_id 与 name（真实 get_case_detail 不返回这两个字段）
            # external_id 用带横杠的 case_id（如 C-2185677）；name 去掉 "C-2185677:" 前缀
            node_map: dict[str, tuple[str, str]] = {}  # 去横杠key -> (带横杠external_id, name)
            for n in nodes:
                if n.type == "test_case" and n.case_id:
                    key = n.case_id.replace("-", "")
                    raw_name = n.name or ""
                    # name 形如 "C-2185677:ftps_login_fali_when_overtime"，取冒号后部分
                    if ":" in raw_name:
                        pure_name = raw_name.split(":", 1)[1].strip()
                    else:
                        pure_name = raw_name
                    node_map[key] = (n.case_id, pure_name)

            if not node_map:
                continue

            # get_case_detail 用带横杠的 case_id 批量取详情
            details = await self.client.get_case_detail(
                [v[0] for v in node_map.values()]
            )

            for key, detail in details.items():
                # key 是去横杠形式（如 C2185677）
                ext_id, pure_name = node_map[key]
                case_id = await self._upsert_case(
                    project_id=suite.project_id,
                    suite_id=sid,
                    external_id=ext_id,
                    name=pure_name,
                    detail=detail,
                    stats=stats,
                )
                if case_id:
                    synced_case_ids.append(case_id)

        return synced_case_ids

    async def _collect_subtree_suites(self, suite_id: int) -> list[int]:
        """收集套件及其所有子套件 id（parent_id 递归）。"""
        ids: list[int] = [suite_id]
        current = [suite_id]
        while current:
            rows = await self.db.execute(
                select(AiTcSuite.id).where(
                    AiTcSuite.parent_id.in_(current),
                    AiTcSuite.is_deleted == 0,
                )
            )
            children = [r[0] for r in rows]
            if not children:
                break
            ids.extend(children)
            current = children
        return ids

    async def _upsert_case(
        self, project_id: int, suite_id: int, external_id: str, name: str, detail, stats: dict
    ) -> int | None:
        """按 project_id + external_id 匹配 upsert 用例。

        Args:
            external_id: 去横杠的 TestLink case_id（如 C2185677）
            name: 用例名（来自 get_tree_nodes 节点，非 get_case_detail）
        """
        detail_dict = detail.model_dump() if hasattr(detail, "model_dump") else dict(detail)
        local = parse_case_to_local(external_id, detail_dict)
        local["name"] = name or local.get("name") or ""
        local["external_id"] = external_id

        # 幂等：按 project_id + external_id 匹配
        row = await self.db.execute(
            select(AiTcCase).where(
                AiTcCase.project_id == project_id,
                AiTcCase.external_id == external_id,
                AiTcCase.is_deleted == 0,
            )
        )
        existing = row.scalar_one_or_none()

        now = datetime.now()
        if existing is not None:
            existing.name = local.get("name") or existing.name
            existing.purpose = local.get("purpose")
            existing.summary = local.get("summary")
            existing.preconditions = local.get("preconditions")
            existing.topo = local.get("topo")
            existing.test_data = local.get("test_data")
            existing.steps = local.get("steps")
            existing.summary_raw = local.get("summary_raw")
            existing.preconditions_raw = local.get("preconditions_raw")
            existing.steps_raw = local.get("steps_raw")
            existing.test_data_raw = local.get("test_data_raw")
            existing.steps_parse_status = local.get("steps_parse_status", 0)
            existing.sync_status = 1
            existing.synced_hash = content_hash(local)
            existing.last_sync_at = now
            stats["cases_updated"] = stats.get("cases_updated", 0) + 1
            return existing.id

        case = AiTcCase(
            project_id=project_id,
            suite_id=suite_id,
            external_id=external_id,
            name=local.get("name") or external_id,
            purpose=local.get("purpose"),
            summary=local.get("summary"),
            preconditions=local.get("preconditions"),
            topo=local.get("topo"),
            test_data=local.get("test_data"),
            steps=local.get("steps"),
            summary_raw=local.get("summary_raw"),
            preconditions_raw=local.get("preconditions_raw"),
            steps_raw=local.get("steps_raw"),
            test_data_raw=local.get("test_data_raw"),
            steps_parse_status=local.get("steps_parse_status", 0),
            sync_status=1,
            synced_hash=content_hash(local),
            last_sync_at=now,
        )
        self.db.add(case)
        await self.db.flush()
        stats["cases_created"] = stats.get("cases_created", 0) + 1
        return case.id

    async def _log(self, direction: str, action: str, status: int, project_id: int, detail: str) -> None:
        """写同步审计日志。"""
        log = AiTcSyncLog(
            project_id=project_id,
            direction=direction,
            action=action,
            status=status,
            detail=detail,
            operator="system",
            operated_at=datetime.now(),
        )
        self.db.add(log)
