"""
LLM 时延测试脚本
---------------
测试 DeepSeek-V4-Flash 在当前网络/配置下的：
  1. TTFT (Time To First Token) — 流式首 token 到达时间
  2. 总耗时 — 完成整轮对话的时间
  3. 不同 prompt 大小的影响
  4. 流式 vs 非流式对比
  5. 连续多轮调用的耗时（模拟 Agent ReAct 循环）

用法: python test_llm_latency.py
"""

import asyncio
import os
import sys
import time
from pathlib import Path

# 让脚本能从项目根目录导入 app 模块
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

load_dotenv(".env.local", override=True)
load_dotenv(".env", override=False)

from openai import AsyncOpenAI

# ── 配置 ──
API_BASE = os.getenv("AI_API_BASE", "https://api.deepseek.com")
API_KEY = os.getenv("AI_API_KEY", "")
MODEL = os.getenv("AI_MODEL", "DeepSeek-V4-Flash")
TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.3"))
MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "4096"))

# ── 模拟消息：短 / 中 / 长（接近 agent 实际） ──
SHORT_MSG = "你好，请用一句话介绍你自己。"
MEDIUM_MSG = (
    "我有一个项目叫「路由器测试」，下面有模块「登录认证」，里面有 5 条测试用例。"
    "请帮我分析一下这些用例的质量如何，重点关注测试步骤是否完整、预期结果是否明确。"
)

# 模拟 agent 实际的 system prompt + tools（约 3000 tokens）
FULL_SYSTEM_PROMPT = """你是测试部的 AI 助手，专注于帮助测试工程师管理测试用例。你可以通过调用工具来查询数据、发起任务。
工具的详细描述和参数由系统动态注入。

## 工作原则

1. **主动查，不猜测** — 用户提到某个模块或用例时，先调用查询工具获取实际数据，再回复，不能猜测和编造数据。
2. **批量操作先确认** — 核心挑选、用例审核、脚本生成涉及批量处理，工具会返回确认卡片，让用户确认后再执行。
3. **利用页面上下文** — 如果 [当前页面上下文] 中已提供 project_id 和 suite_id，优先使用这些值，减少反问。
4. **引导用户** — 当用户表达模糊意图时，先查数据摸清情况，再建议使用合适的功能。
5. **回复简洁** — 直接给出操作建议和数据摘要，冗长的解释留给用户提问时再展开。
6. **少用加粗** — 只在极少数真正需要强调的地方使用 Markdown 加粗（**文本**），普通列表项、操作步骤不要加粗，保持阅读清爽。
7. **需要确认时用 ask_question** — 当需要用户做出选择，调用 ask_question 工具弹出交互式表单。**一次性列出所有需要确认的问题**。
8. **ask_question 后等待回答** — 调用 ask_question 后，不要紧接着调用任务工具。等待用户提交回答后，根据回答内容再决定下一步操作。
9. **上下文充足时直接创建** — 如果页面上下文中已有明确的 project_id 和 suite_id，且用户意图清晰，可以直接调用任务工具，无需 ask_question。

## 页面上下文

当用户进入对话时，前端会自动注入当前页面信息（项目名、模块名、选中的用例等）。以 [当前页面上下文] 消息块的形式提供。

## 当前页面上下文
- 项目：1 路由器测试
- 模块：11 登录认证

注意：如果用户有选中用例（selected_case_ids），可优先作为操作对象。但如果用户明确要求对整个模块操作，以用户意图为准。

## 你的工具箱

### 查询类工具（随时可用，只读安全）
- `list_projects` — 获取所有可用项目列表。当用户想了解有哪些项目、需要选择项目时调用。
- `get_suite_tree` (project_id: 必填) — 获取指定项目下的模块（套件）树结构。当用户想了解项目有哪些模块时调用。
- `search_cases` (suite_id: 可选, keywords: 可选, is_core: 可选, has_steps: 可选, page: 可选, page_size: 可选) — 搜索/列出测试用例，支持按模块、关键字、是否核心用例、是否有步骤等条件过滤。当用户想查看某个模块有哪些用例、查找特定用例、了解用例概况时调用。
- `get_case_detail` (case_id: 必填) — 获取单条测试用例的详细信息，包括步骤、前置条件、测试数据等。当用户想深入了解某条用例时调用。
- `get_suite_samples` (suite_id: 可选) — 获取指定模块下标记为样本的用例列表。

### 澄清类工具
- `ask_question` (title: 必填, questions: 必填) — 向用户提问，收集确认信息。重要规则：一次性把所有需要确认的问题都列入 questions 数组，让用户在一张表单中填写完所有信息。

### 任务类工具（发起批量处理，返回确认卡片等用户确认）
- `create_core_select_task` (suite_id: 可选, project_id: 可选, scope: 可选, case_ids: 可选) — 从指定模块的用例中挑选核心/重要用例。
- `create_case_review_task` (suite_id: 可选, project_id: 可选, scope: 可选, case_ids: 可选) — 审核指定模块下测试用例的质量，检查字段完整性、步骤规范性等。
- `create_script_gen_task` (suite_id: 可选, project_id: 可选, scope: 可选, case_ids: 可选) — 为指定模块下的测试用例生成 pytest 自动化测试脚本。
- `create_case_complete_task` (suite_id: 可选, project_id: 可选, scope: 可选, case_ids: 可选) — 对指定模块下字段不完整的用例进行 AI 补全（含测试步骤），参考同模块样本用例的写法。

### 即时处理工具
- `design_test_case` (requirement: 必填) — 根据需求描述，从零设计一条新的测试用例（包含标题、前置条件、测试步骤、预期结果）。"""


async def test_streaming(client: AsyncOpenAI, label: str, messages: list[dict]) -> dict:
    """流式调用，记录 TTFT 和总耗时。"""
    print(f"  [{label}] 流式调用...", end=" ", flush=True)
    t0 = time.time()
    ttft = None
    first_token_ts = None
    total_chars = 0
    token_count = 0

    stream = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        stream=True,
        stream_options={"include_usage": True},
    )

    async for chunk in stream:
        if ttft is None and chunk.choices and chunk.choices[0].delta.content:
            ttft = time.time() - t0
            first_token_ts = time.time()
        if chunk.choices and chunk.choices[0].delta.content:
            total_chars += len(chunk.choices[0].delta.content)
            token_count += 1
        # usage 在最后一个 chunk
        usage = chunk.usage

    total_time = time.time() - t0
    result = {
        "label": label,
        "mode": "streaming",
        "ttft_ms": round(ttft * 1000, 0) if ttft else None,
        "total_ms": round(total_time * 1000, 0),
        "generation_ms": round((total_time - (ttft or total_time)) * 1000, 0),
        "chars": total_chars,
        "tokens_out": usage.prompt_tokens if usage else 0,
        "tokens_in": usage.completion_tokens if usage else 0,
    }
    print(f"TTFT={result['ttft_ms']}ms 总耗时={result['total_ms']}ms")
    return result


async def test_non_streaming(client: AsyncOpenAI, label: str, messages: list[dict]) -> dict:
    """非流式调用，只记录总耗时。"""
    print(f"  [{label}] 非流式调用...", end=" ", flush=True)
    t0 = time.time()

    resp = await client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        stream=False,
    )

    total_time = time.time() - t0
    content = resp.choices[0].message.content or ""
    result = {
        "label": label,
        "mode": "non-streaming",
        "ttft_ms": None,
        "total_ms": round(total_time * 1000, 0),
        "generation_ms": round(total_time * 1000, 0),
        "chars": len(content),
        "tokens_in": resp.usage.prompt_tokens if resp.usage else 0,
        "tokens_out": resp.usage.completion_tokens if resp.usage else 0,
    }
    print(f"总耗时={result['total_ms']}ms tokens: in={result['tokens_in']} out={result['tokens_out']}")
    return result


async def main():
    print("=" * 70)
    print(f"LLM 时延测试")
    print(f"  模型: {MODEL}")
    print(f"  API:  {API_BASE}")
    print(f"  温度: {TEMPERATURE}, max_tokens: {MAX_TOKENS}")
    print("=" * 70)

    if not API_KEY:
        print("❌ 未配置 AI_API_KEY，请在 .env.local 中设置")
        return

    client = AsyncOpenAI(api_key=API_KEY, base_url=API_BASE, timeout=120.0, max_retries=1)

    results = []

    # ── 1. 短消息流式 ──
    results.append(await test_streaming(client, "短消息", [
        {"role": "user", "content": SHORT_MSG},
    ]))

    # ── 2. 短消息非流式 ──
    results.append(await test_non_streaming(client, "短消息", [
        {"role": "user", "content": SHORT_MSG},
    ]))

    # ── 3. 中消息流式 ──
    results.append(await test_streaming(client, "中消息", [
        {"role": "user", "content": MEDIUM_MSG},
    ]))

    # ── 4. 完整 system + 用户消息（模拟 agent 实际第一轮） ──
    results.append(await test_streaming(client, "Agent实际(system+user)", [
        {"role": "system", "content": FULL_SYSTEM_PROMPT},
        {"role": "user", "content": "审核用例质量"},
    ]))

    # ── 5. 完整 system + 用户消息 非流式 ──
    results.append(await test_non_streaming(client, "Agent实际(system+user)", [
        {"role": "system", "content": FULL_SYSTEM_PROMPT},
        {"role": "user", "content": "审核用例质量"},
    ]))

    # ── 6. 模拟 agent 第二轮（system + user + assistant + tool_result） ──
    results.append(await test_streaming(client, "Agent第二轮(含工具结果)", [
        {"role": "system", "content": FULL_SYSTEM_PROMPT},
        {"role": "user", "content": "审核用例质量"},
        {"role": "assistant", "content": "我来看看当前模块下用例的情况，先查一下数据"},
        {"role": "tool", "content": '{"total": 5, "cases": [{"id": 1, "title": "正常登录", "has_steps": true}, {"id": 2, "title": "密码错误", "has_steps": false}]}'},
    ]))

    # ── 7. 连续 3 次调用（模拟 Agent ReAct 3 轮） ──
    print("\n--- Agent ReAct 连续 3 轮模拟 ---")
    t_seq_start = time.time()
    for i in range(3):
        await test_streaming(client, f"ReAct轮{i+1}", [
            {"role": "system", "content": FULL_SYSTEM_PROMPT},
            {"role": "user", "content": "审核用例质量"},
        ])
    t_seq_total = time.time() - t_seq_start
    print(f"  连续 3 轮总耗时: {t_seq_total * 1000:.0f}ms")

    # ── 汇总 ──
    print("\n" + "=" * 70)
    print("汇总")
    print("=" * 70)
    print(f"{'场景':<25} {'模式':<12} {'TTFT(ms)':<10} {'总耗时(ms)':<10} {'生成(ms)':<10}")
    print("-" * 70)
    for r in results:
        print(f"{r['label']:<25} {r['mode']:<12} "
              f"{str(r['ttft_ms'] or 'N/A'):<10} "
              f"{r['total_ms']:<10} "
              f"{r['generation_ms']:<10}")

    # 关键指标
    print("\n--- 关键发现 ---")
    streaming_results = [r for r in results if r["mode"] == "streaming"]

    if streaming_results:
        ttfts = [r["ttft_ms"] for r in streaming_results if r["ttft_ms"]]
        if ttfts:
            print(f"  最短 TTFT: {min(ttfts):.0f}ms")
            print(f"  最长 TTFT: {max(ttfts):.0f}ms")
            print(f"  平均 TTFT: {sum(ttfts) / len(ttfts):.0f}ms")

        # agent 实际场景的 TTFT
        agent_results = [r for r in streaming_results if "Agent" in r["label"]]
        for r in agent_results:
            if r["ttft_ms"]:
                print(f"  {r['label']}: TTFT={r['ttft_ms']:.0f}ms, 总={r['total_ms']:.0f}ms")

    # 非流式 vs 流式对比
    for label in ["短消息", "Agent实际(system+user)"]:
        streams = [r for r in results if r["label"] == label and r["mode"] == "streaming"]
        nons = [r for r in results if r["label"] == label and r["mode"] == "non-streaming"]
        if streams and nons:
            ratio = nons[0]["total_ms"] / streams[0]["total_ms"] if streams[0]["total_ms"] else 0
            print(f"  {label}: 非流式/流式 = {ratio:.1f}x (非流式:{nons[0]['total_ms']:.0f}ms vs 流式:{streams[0]['total_ms']:.0f}ms)")


if __name__ == "__main__":
    asyncio.run(main())
