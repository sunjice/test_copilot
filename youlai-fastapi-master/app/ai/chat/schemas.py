"""AI 对话系统 — Pydantic Schemas。"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.serializers import BigId


# ═══════════════ 会话 ═══════════════

class SessionCreate(BaseModel):
    """创建会话。"""
    title: str = Field(default="新对话", max_length=200, description="会话标题")
    domain: str = Field(default="case", description="会话域 case/bug/analytics")
    context_json: dict | None = Field(default=None, description="页面上下文快照")


class SessionUpdate(BaseModel):
    """更新会话。"""
    title: str | None = Field(default=None, max_length=200, description="会话标题")
    is_pinned: int | None = Field(default=None, description="是否置顶 0/1")


class SessionVO(BaseModel):
    """会话视图对象。"""
    id: BigId | None = None
    title: str = ""
    domain: str = "case"
    context_json: dict | None = None
    message_count: int = 0
    is_pinned: int = 0
    user_id: int | None = None
    create_time: str | None = None
    update_time: str | None = None
    model_config = {"from_attributes": True}


# ═══════════════ 消息 ═══════════════

class MessageSendReq(BaseModel):
    """发送消息请求。"""
    content: str = Field(..., min_length=1, description="用户输入内容")
    skill_name: str | None = Field(default=None, description="指定技能名称（可选）")


class MessageVO(BaseModel):
    """消息视图对象。"""
    id: BigId | None = None
    session_id: BigId | None = None
    role: str = "user"
    msg_type: str = "text"
    content: str = ""
    metadata_json: dict | None = None
    create_time: str | None = None
    model_config = {"from_attributes": True}


# ═══════════════ 上下文 ═══════════════

class ContextSetReq(BaseModel):
    """设置会话上下文请求。"""
    domain: str = Field(default="case", description="域")
    context_json: dict = Field(default_factory=dict, description="上下文数据")


# ═══════════════ 技能 ═══════════════

class SkillInfoVO(BaseModel):
    """技能信息（前端展示用）。"""
    name: str
    domain: str
    description: str
    mode: str  # SYNC / ASYNC
    keywords: list[str] = Field(default_factory=list)


# ═══════════════ 卡片状态更新 ═══════════════

class UpdateCardStatusReq(BaseModel):
    """更新会话中最后一条指定类型卡片的 metadata。"""
    msg_type: str = Field(..., description="卡片类型 clarify_card / confirm_card")
    metadata: dict = Field(..., description="要合并写入的元数据")


# ═══════════════ 任务确认 ═══════════════

class ConfirmCreateTaskReq(BaseModel):
    """确认创建任务 — 用户在对话框中点击确认后提交。"""
    skill_name: str = Field(..., description="技能名称，如 core_select")
    project_id: int = Field(..., description="项目ID")
    suite_id: int = Field(..., description="模块ID")
    case_ids: list[int] | None = Field(default=None, description="指定用例ID列表，为空则处理整个模块")
    selected_option: str | None = Field(default=None, description="用户选中的选项ID")


# ═══════════════ 用量日志 ═══════════════

class UsageLogVO(BaseModel):
    """用量日志视图对象。"""
    id: BigId | None = None
    module: str = "chat"
    session_id: int | None = None
    task_id: int | None = None
    model: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    duration_ms: int = 0
    created_at: str | None = None
    model_config = {"from_attributes": True}
