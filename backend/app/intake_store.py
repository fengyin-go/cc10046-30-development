"""来源接入数据仓库：导入回执、采集接入清单行、本地原页样本和试采派工记录。

与 18 个业务模块的示例数据分开存放，避免运营概览的模块统计被新对象稀释；
真实项目里这里会换成数据库表。
"""
from __future__ import annotations

import time
from typing import Any


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class IntakeStore:
    """来源清单导入到试采派工的全链路内存存储。"""

    def __init__(self) -> None:
        self._receipts: list[dict[str, Any]] = []
        # 本地原页样本库：以真实起始地址为键，同名别名靠地址区分。
        self._samples: dict[str, dict[str, Any]] = {}
        self._dispatches: list[dict[str, Any]] = []

    # ---- 导入回执 / 采集接入清单 ----
    def next_receipt_id(self) -> str:
        return f"IMP-{len(self._receipts) + 1:04d}"

    def add_receipt(self, receipt: dict[str, Any]) -> None:
        self._receipts.append(receipt)

    def receipts(self) -> list[dict[str, Any]]:
        return list(self._receipts)

    def find_receipt(self, receipt_id: str) -> dict[str, Any] | None:
        for receipt in self._receipts:
            if receipt.get("回执编号") == receipt_id:
                return receipt
        return None

    # ---- 本地原页样本 ----
    def register_sample(
        self,
        address: str,
        encoding: str,
        content_b64: str,
        origin: str,
        operator: str,
    ) -> dict[str, Any]:
        sample = {
            "起始地址": address,
            "页面编码": encoding,
            "原页内容": content_b64,
            "登记来源": origin,
            "登记人": operator,
            "登记时间": _now(),
        }
        self._samples[address] = sample
        return sample

    def find_sample(self, address: str) -> dict[str, Any] | None:
        return self._samples.get(address)

    # ---- 试采派工 ----
    def next_trial_id(self) -> str:
        return f"TRIAL-{len(self._dispatches) + 1:04d}"

    def add_dispatch(self, record: dict[str, Any]) -> None:
        self._dispatches.append(record)

    def find_dispatch(self, receipt_id: str, row_no: int) -> dict[str, Any] | None:
        for record in self._dispatches:
            if record.get("回执编号") == receipt_id and record.get("清单行号") == row_no:
                return record
        return None

    def dispatches(self, receipt_id: str | None = None) -> list[dict[str, Any]]:
        if receipt_id is None:
            return list(self._dispatches)
        return [r for r in self._dispatches if r.get("回执编号") == receipt_id]


intake_store = IntakeStore()
