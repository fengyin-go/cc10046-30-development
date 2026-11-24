"""通用接口契约；模块字段由领域服务持有，不再为每个模块复制一份模型类。"""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int = 1
    size: int = 20


class ActionResult(BaseModel):
    ok: bool
    message: str
    entry: dict[str, Any] | None = None


class EntryPayload(BaseModel):
    values: dict[str, Any] = Field(default_factory=dict)
    remark: str | None = None


class ActionPayload(BaseModel):
    action: str
    remark: str | None = None


class SourceImportPayload(BaseModel):
    """来源清单 CSV 导入：清单文本 + 随附的本地原页样本。"""
    csv_text: str
    samples: list[dict[str, Any]] = Field(default_factory=list)
    operator: str = "值班员"


class SampleSupplementPayload(BaseModel):
    """补交本地原页样本：按真实起始地址登记并重新核对。"""
    address: str
    encoding: str | None = None
    content_b64: str
    operator: str = "值班员"


class TrialDispatchPayload(BaseModel):
    """从导入回执发起一次试采派工。"""
    receipt_id: str
    operator: str = "值班员"
