"""同义词/术语管理 — PG 持久化 + ES 热更新。

retrieval_synonyms 表结构：
    id, synonym_group, term, is_preferred, domain, created_at, updated_at

ES 同义词格式（每组一行）：
    登录, 登陆, login, sign in
    并发, 并行, concurrent
"""

from typing import Any

from elasticsearch import AsyncElasticsearch
from sqlalchemy import select, delete

from app.aitc.retrieval.common.client import get_es_client
from app.aitc.retrieval.common.config import ES_INDEX_CASE


class SynonymsManager:
    """同义词管理器 — 从 PG 加载 → 推送到 ES。"""

    def __init__(self, db_session_factory=None):
        self._session_factory = db_session_factory

    async def load_synonym_groups(self, db) -> dict[str, list[str]]:
        """从 PG retrieval_synonyms 表加载，按 synonym_group 聚合。

        Returns:
            {"login": ["登录", "登陆", "login", "sign in"], ...}
        """
        from sqlalchemy import text

        result = await db.execute(
            text(
                "SELECT synonym_group, term FROM retrieval_synonyms "
                "ORDER BY synonym_group, is_preferred DESC"
            )
        )
        rows = result.fetchall()

        groups: dict[str, list[str]] = {}
        for group, term in rows:
            if group not in groups:
                groups[group] = []
            if term not in groups[group]:
                groups[group].append(term)

        return groups

    def build_es_synonym_rules(self, groups: dict[str, list[str]]) -> list[str]:
        """将分组数据转为 ES 同义词规则。

        Returns:
            ["登录, 登陆, login, sign in", "并发, 并行, concurrent"]
        """
        rules = []
        for terms in groups.values():
            if len(terms) > 1:
                rules.append(", ".join(terms))
        return rules

    async def sync_to_es(self, db, index_name: str = ES_INDEX_CASE) -> int:
        """将 PG 同义词同步到 ES（热更新，无需重建索引）。

        Returns: 同步的同义词组数量
        """
        groups = await self.load_synonym_groups(db)
        rules = self.build_es_synonym_rules(groups)

        if not rules:
            return 0

        es = await get_es_client()

        # 更新 ES 索引的同义词过滤器
        # 方式：更新索引 settings 中的 synonym filter
        await es.indices.close(index=index_name)

        try:
            await es.indices.put_settings(
                index=index_name,
                body={
                    "analysis": {
                        "filter": {
                            "synonym_filter": {
                                "type": "synonym",
                                "synonyms": rules,
                                "updateable": True,
                            }
                        }
                    }
                },
            )
        finally:
            await es.indices.open(index=index_name)

        return len(rules)

    async def add_synonym(self, db, group: str, term: str, domain: str = "", is_preferred: bool = False) -> None:
        """添加单个术语。"""
        from sqlalchemy import text

        await db.execute(
            text(
                "INSERT INTO retrieval_synonyms (synonym_group, term, is_preferred, domain) "
                "VALUES (:group, :term, :preferred, :domain) "
                "ON CONFLICT (synonym_group, term) DO NOTHING"
            ),
            {"group": group, "term": term, "preferred": is_preferred, "domain": domain},
        )
        await db.commit()

    async def remove_synonym(self, db, group: str, term: str) -> None:
        """删除单个术语。"""
        from sqlalchemy import text

        await db.execute(
            text("DELETE FROM retrieval_synonyms WHERE synonym_group = :group AND term = :term"),
            {"group": group, "term": term},
        )
        await db.commit()

    # ═══════════════ 管理接口支撑（列表 / 更新 / 批量删除 / 查重） ═══════════════

    async def find_synonym(self, db, group: str, term: str) -> bool:
        """按 (分组, 词条) 查重，供新增前校验。"""
        from sqlalchemy import text

        result = await db.execute(
            text(
                "SELECT 1 FROM retrieval_synonyms "
                "WHERE synonym_group = :group AND term = :term"
            ),
            {"group": group, "term": term},
        )
        return result.scalar() is not None

    async def list_synonyms(
        self,
        db,
        page_num: int = 1,
        page_size: int = 10,
        domain: str | None = None,
        keyword: str | None = None,
    ) -> tuple[int, list[Any]]:
        """分页查询词条（按组排序，首选词优先）。

        Returns:
            (total, rows)，rows 元素为 Row(id, synonym_group, term, is_preferred,
            domain, created_at, updated_at)
        """
        from sqlalchemy import text

        conds: list[str] = []
        params: dict[str, Any] = {}
        if domain:
            conds.append("domain = :domain")
            params["domain"] = domain
        if keyword:
            conds.append("(term ILIKE :kw OR synonym_group ILIKE :kw)")
            params["kw"] = f"%{keyword}%"
        where = f"WHERE {' AND '.join(conds)}" if conds else ""

        total = (
            await db.execute(
                text(f"SELECT COUNT(*) FROM retrieval_synonyms {where}"), params
            )
        ).scalar() or 0

        params.update({"limit": page_size, "offset": (page_num - 1) * page_size})
        rows = await db.execute(
            text(
                "SELECT id, synonym_group, term, is_preferred, domain, created_at, updated_at "
                f"FROM retrieval_synonyms {where} "
                "ORDER BY synonym_group, is_preferred DESC, term "
                "LIMIT :limit OFFSET :offset"
            ),
            params,
        )
        return int(total), rows.fetchall()

    async def update_synonym(
        self,
        db,
        sid: int,
        group: str | None = None,
        term: str | None = None,
        domain: str | None = None,
        is_preferred: bool | None = None,
    ) -> bool:
        """更新单个词条（仅更新传入字段）。

        Returns: 是否命中并更新了记录
        """
        from sqlalchemy import text

        fields: list[str] = []
        params: dict[str, Any] = {"sid": sid}
        if group is not None:
            fields.append("synonym_group = :group")
            params["group"] = group
        if term is not None:
            fields.append("term = :term")
            params["term"] = term
        if domain is not None:
            fields.append("domain = :domain")
            params["domain"] = domain
        if is_preferred is not None:
            fields.append("is_preferred = :is_preferred")
            params["is_preferred"] = is_preferred
        if not fields:
            return False

        fields.append("updated_at = now()")
        result = await db.execute(
            text(
                f"UPDATE retrieval_synonyms SET {', '.join(fields)} WHERE id = :sid"
            ),
            params,
        )
        return (result.rowcount or 0) > 0

    async def delete_by_ids(self, db, ids: list[int]) -> int:
        """按 ID 批量删除词条。Returns: 删除条数。"""
        from sqlalchemy import text

        if not ids:
            return 0
        result = await db.execute(
            text("DELETE FROM retrieval_synonyms WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
        return result.rowcount or 0
