"""测试部 AI 助手 — ORM 模型注册入口。
各域模型分别定义在 case/sample/script/spec/task 子包中，本文件集中 re-import
以保证 registry.py 能一次性收集所有表。
"""

from app.aitc.case.models import AiTcProject, AiTcSuite, AiTcCase  # noqa: F401
from app.aitc.sample.models import AiTcSample  # noqa: F401
from app.aitc.script.models import AiTcScript  # noqa: F401
from app.aitc.spec.models import AiTcSpec  # noqa: F401
from app.aitc.task.models import AiTcTask, AiTcTaskItem, AiTcReviewRecord  # noqa: F401
from app.aitc.testlink.models import AiTcSyncLog  # noqa: F401

