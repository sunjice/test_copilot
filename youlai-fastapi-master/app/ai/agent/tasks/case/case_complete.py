"""补全用例字段任务 — 参考样本用例，补全缺失字段（含测试步骤）。"""

import json

from loguru import logger
from sqlalchemy import select

from app.aitc.constants import ConfirmStatus, TaskType
from app.aitc.models import AiTcCase, AiTcTask
from app.aitc.task.store import TaskStore
from app.aitc.case.service import CaseService
from app.ai.agent.tasks.base import TaskContext
from app.ai.agent.tasks.case.case_task import CaseTask
from app.ai.agent.tasks.case.constants import CaseCompleteConfig


class CaseCompleteTask(CaseTask):
    """参考同模块样本用例，补全用例的缺失字段（含测试步骤）。

    前置条件：用例必须有编号（external_id）、名称（name）、测试目的（purpose）。
    缺少上述任一字段的用例会被跳过并标记失败。
    """

    task_type = TaskType.CASE_COMPLETE
    batch_size = CaseCompleteConfig.BATCH_SIZE
    commit_every = CaseCompleteConfig.COMMIT_EVERY
    sample_limit = CaseCompleteConfig.SAMPLE_LIMIT
    system_prompt = (
        "你是一个资深的测试专家。请根据用例名称和测试目的，参考同模块样本用例的写法风格，"
        "补全给定用例的缺失字段（测试思想、前置条件、测试数据、拓扑、测试步骤）。"
        "保持与样本用例一致的术语表达、步骤粒度和格式。只返回 JSON。"
    )

    # ── 执行 ──

    async def execute(self, ctx: TaskContext) -> None:
        """逐条调用 AI 补全用例字段。

        从任务关联的套件下加载样本用例，替换 ctx.samples。
        对每条用例校验前置条件（编号/名称/目的），不满足则标记失败。
        """
        suite_samples = await self._load_suite_samples(ctx)
        if suite_samples:
            ctx.samples = suite_samples

        await self._execute_per_item(ctx)

    async def _execute_per_item(self, ctx: TaskContext) -> None:
        """覆写模板：逐条校验前置 → build prompt + 调 AI + 解析 → 写结果。"""
        case_ids = [it.case_id for it in ctx.items]
        cases = (await ctx.db.execute(
            select(AiTcCase).where(AiTcCase.id.in_(case_ids))
        )).scalars().all()
        case_map: dict[int, AiTcCase] = {c.id: c for c in cases}

        done = 0
        for it in ctx.items:
            case = case_map.get(it.case_id)
            if not case:
                self._mark_item_failed(it, "用例不存在")
                done += 1
                continue

            # 前置校验：必须有编号、名称、测试目的
            prerequisite_error = self._check_prerequisites(case)
            if prerequisite_error:
                self._mark_item_failed(it, prerequisite_error)
                logger.warning(
                    f"{self.task_type.value} skipped case {case.id}: {prerequisite_error}"
                )
                done += 1
                if done % self.commit_every == 0 or done == len(ctx.items):
                    await self._update_progress(ctx, done)
                continue

            case_detail = self._build_case_detail(case)
            # 附加编号字段，方便 prompt 引用
            case_detail["external_id"] = case.external_id or ""

            try:
                user_prompt = self.build_user_prompt(
                    case_detail, ctx.prompt, ctx.samples, ctx.specs,
                )
                raw = await ctx.client.chat_json(self.system_prompt, user_prompt)
                result = self.parse_result(raw)
                self._mark_item_success(it, result)
            except Exception as e:
                logger.error(f"{self.task_type.value} failed for case {case.id}: {e}")
                self._mark_item_failed(it, str(e))

            done += 1
            if done % self.commit_every == 0 or done == len(ctx.items):
                await self._update_progress(ctx, done)

    async def _load_suite_samples(self, ctx: TaskContext) -> str:
        """从套件下加载标记为样本的用例，构建样本文本。"""
        task = await ctx.db.get(AiTcTask, ctx.task_id)
        if task is None:
            return ""

        stmt = (
            select(AiTcCase)
            .where(
                AiTcCase.suite_id == task.suite_id,
                AiTcCase.is_sample == 1,
                AiTcCase.is_deleted == 0,
            )
            .limit(self.sample_limit)
        )
        result = await ctx.db.execute(stmt)
        sample_cases = result.scalars().all()

        if not sample_cases:
            return ""

        sample_dicts = [self._format_sample_case(c) for c in sample_cases]
        samples_json = json.dumps(sample_dicts, ensure_ascii=False, indent=2)

        logger.info(
            f"Task {ctx.task_id}: loaded {len(sample_cases)} sample cases "
            f"from suite {task.suite_id}"
        )
        return "同模块样本用例（供参考字段写法、粒度、术语）：\n" + samples_json

    @staticmethod
    def _format_sample_case(case: AiTcCase) -> dict:
        """将一条样本用例构建为与待补全用例同结构的 dict。"""
        return CaseTask._build_case_detail(case)

    # ── 前置校验 ──

    @staticmethod
    def _check_prerequisites(case: AiTcCase) -> str | None:
        """校验用例前置条件：编号 + 名称 + 测试目的。返回 None 表示通过。"""
        missing = []
        if not case.external_id:
            missing.append("编号")
        if not (case.name or "").strip():
            missing.append("名称")
        if not (case.purpose or "").strip():
            missing.append("测试目的")

        if missing:
            return f"缺少必要字段: {'、'.join(missing)}"
        return None

    # ── Prompt 构建 ──

    def build_user_prompt(
        self, case_detail: dict, template: str,
        samples: str = "", specs: str = "",
    ) -> str:
        """构建补全字段的用户 prompt。"""
        case_json = json.dumps(case_detail, ensure_ascii=False, indent=2)

        if template:
            return (
                template
                .replace("{{case}}", case_json)
                .replace("{{samples}}", samples)
                .replace("{{specs}}", specs)
            )

        return f"""请根据用例的「名称」和「测试目的」，参考同模块样本用例的写法，
补全以下用例的缺失字段。每个字段必须参考样本用例中对应字段的写法风格、粒度、术语表达。
如果有现有值但不够完善，也可以进行改进。

{samples}

补全指引：
1. 测试思想：应清晰说明测试策略、风险点和验证目标，体现测试设计思路。
2. 前置条件：应完整列出执行测试前必须满足的环境、数据、权限等条件。
3. 测试数据：应明确列出测试所需的具体数据内容、格式和来源。
4. 测试拓扑（topo）：应描述测试的网络拓扑、服务依赖关系。
5. 测试步骤：每步应包含明确的操作(action)和可验证的预期结果(expected)，
   步骤逻辑连贯无歧义，参考样本用例中步骤的 action/expected 格式。

返回 JSON：
{{
  "overall_note": "整体补全说明...",
  "fields": [
    {{
      "field_name": "summary",
      "original": "",
      "suggested_value": "验证在并发场景下用户登录接口的幂等性..."
    }},
    {{
      "field_name": "preconditions",
      "original": "",
      "suggested_value": "已部署v2.3版本服务，数据库包含1000条用户记录..."
    }},
    {{
      "field_name": "test_data",
      "original": "",
      "suggested_value": "账号: test_user_001, 密码: Abc12345, 角色: 普通用户"
    }},
    {{
      "field_name": "topo",
      "original": "",
      "suggested_value": "客户端 → Nginx → API Gateway → 用户服务 → MySQL"
    }},
    {{
      "field_name": "steps",
      "original": [],
      "suggested_value": [
        {{"step_no": 1, "action": "打开登录页面", "expected": "页面正常加载，显示用户名和密码输入框"}},
        {{"step_no": 2, "action": "输入正确账号密码，点击登录", "expected": "登录成功，跳转到首页"}}
      ]
    }}
  ]
}}

用例内容：
{case_json}"""

    # ── 结果解析 ──

    @staticmethod
    def parse_result(output: dict | list) -> dict:
        """解析补全结果。"""
        if not isinstance(output, dict):
            return {"overall_note": "", "fields": []}

        fields = output.get("fields") or []
        if isinstance(fields, list):
            cleaned = []
            for f in fields:
                if not isinstance(f, dict):
                    continue
                field_name = f.get("field_name", "")
                original = f.get("original", "")
                suggested = f.get("suggested_value")

                # 如果有原始值填的不是空但补全值也是空/相同，跳过
                if suggested is not None and (isinstance(suggested, str) and suggested.strip() == ""):
                    suggested = None if not original else original

                cleaned.append({
                    "field_name": field_name,
                    "original": original,
                    "suggested_value": suggested,
                })
            return {
                "overall_note": output.get("overall_note", ""),
                "fields": cleaned,
            }

        return {"overall_note": output.get("overall_note", ""), "fields": []}

    # ── 确认回写 ──

    async def apply_result(
        self,
        svc: TaskStore,
        item,
        output: dict,
        confirm_status: int,
        final_content: str = "",
        is_core: bool | None = None,
    ) -> None:
        """确认：将 AI 补全的字段值写入用例。"""
        case_svc = CaseService(svc.db)
        update_fields = self._extract_completed_fields(output)

        if update_fields:
            await case_svc.apply_case_review_result(item.case_id, update_fields)

    @staticmethod
    def _extract_completed_fields(output: dict) -> dict[str, str | list]:
        """从 AI 输出中提取需要写入的字段（有值的 suggested_value）。"""
        updates: dict = {}
        fields = output.get("fields") or []
        if not isinstance(fields, list):
            return updates

        field_map = {
            "summary": "summary",
            "preconditions": "preconditions",
            "test_data": "test_data",
            "topo": "topo",
            "steps": "steps",
        }

        for f in fields:
            if not isinstance(f, dict):
                continue
            fn = f.get("field_name", "")
            attr = field_map.get(fn)
            if not attr:
                continue
            sv = f.get("suggested_value")
            if sv is None:
                continue
            # 空字符串跳过
            if isinstance(sv, str) and sv.strip() == "":
                continue
            # 空列表跳过（steps 的情况）
            if isinstance(sv, list) and len(sv) == 0:
                continue
            updates[attr] = sv

        return updates
