import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.ai.agent.tasks.queue import dequeue_task, enqueue_task
from app.ai.agent.tasks.worker import TaskWorker


@pytest.mark.anyio
async def test_enqueue_dequeue_task(monkeypatch):
    stored = []

    class FakeRedis:
        async def rpush(self, key, value):
            stored.append((key, value))

        async def blpop(self, key, timeout):
            if not stored:
                return None
            return key, stored.pop(0)[1]

    fake_redis = FakeRedis()
    monkeypatch.setattr("app.ai.agent.tasks.queue.get_redis", AsyncMock(return_value=fake_redis))

    await enqueue_task(123, "CORE_SELECT")
    assert stored == [("aitc:task:queue", json.dumps({"task_id": 123, "task_type": "CORE_SELECT"}))]

    item = await dequeue_task(block_timeout=1)
    assert item == {"task_id": 123, "task_type": "CORE_SELECT"}


@pytest.mark.anyio
async def test_task_worker_consumes_queue_and_launches_execute_task_bg(monkeypatch):
    calls = []
    items = [{"task_id": 42, "task_type": "CASE_REVIEW"}, None]

    async def fake_dequeue_task(block_timeout=5):
        return items.pop(0)

    async def fake_execute_task_bg(task_id: int, task_type: str):
        calls.append((task_id, task_type))

    monkeypatch.setattr("app.ai.agent.tasks.worker.dequeue_task", fake_dequeue_task)
    monkeypatch.setattr("app.ai.agent.tasks.worker.execute_task_bg", AsyncMock(side_effect=fake_execute_task_bg))

    worker = TaskWorker()
    await worker.start()

    async def wait_for_call():
        for _ in range(20):
            if calls:
                return
            await asyncio.sleep(0.05)
        raise AssertionError("Worker did not process queued task")

    await wait_for_call()
    await worker.stop()

    assert calls == [(42, "CASE_REVIEW")]
