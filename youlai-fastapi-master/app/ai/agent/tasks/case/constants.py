"""用例领域 — AI 任务配置参数。"""


class CoreSelectConfig:
    """核心用例挑选。"""
    BATCH_SIZE = 30  # 每批提交给 AI 挑选的用例数


class CaseReviewConfig:
    """用例审核。"""
    BATCH_SIZE = 5   # 每批提交给 AI 审核的用例数（当前逐条执行，预留批量改造）
    COMMIT_EVERY = 1  # 每处理多少条向 DB 提交一次进度
    SAMPLE_LIMIT = 3  # 从套件下选取样本用例的最大条数


class ScriptGenConfig:
    """脚本生成。"""
    BATCH_SIZE = 1   # 每批提交给 AI 生成脚本的用例数


class CaseCompleteConfig:
    """补全用例字段。"""
    BATCH_SIZE = 1   # 每批提交给 AI 补全字段的用例数（逐条执行）
    COMMIT_EVERY = 1  # 每处理多少条向 DB 提交一次进度
    SAMPLE_LIMIT = 3  # 从套件下选取样本用例的最大条数
