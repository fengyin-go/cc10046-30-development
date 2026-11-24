"""采集调度领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。

新增试采派工能力：消费爬虫配置生成的采集接入清单，只派工核对通过的来源，
已受理的试采不重发；每条试采请求都能回查到原清单行。
"""
from __future__ import annotations

import time
from typing import Any

from app.intake_store import intake_store
from app.services.base import BaseModuleService


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


class CrawlScheduleService(BaseModuleService):
    MODULE = "crawl_schedule"
    ENTITY = "调度任务"
    OPERATION_TERM = "采集"
    LIST_FIELDS = ["任务标识", "关联配置", "调度周期", "起始水位", "截止水位", "分片策略", "上次执行", "下次执行"]
    REQUIRED_FIELDS = ["任务标识", "关联配置", "调度周期"]
    STATUS_ORDER = ["待启动", "运行中", "已完成", "调度失败"]
    ACTION_RULES = {"启动调度": "待启动", "取消调度": "调度失败"}
    NEGATIVE_ACTIONS = []

    def domain_create_schedule(self, config_name: str, period: str = "daily") -> dict:
        """生成采集调度计划。"""
        from app.store import store
        import time
        rows = store.rows(self.MODULE)
        task_id = f"SCHED-{max((int(r.get('id', 0)) for r in rows), default=0) + 1}"
        plan = {
            "task_id": task_id,
            "config_name": config_name,
            "period": period,
            "shard_count": 4,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "watermark_start": "2026-01-01",
            "watermark_end": time.strftime("%Y-%m-%d"),
        }
        return plan

    # ---- 试采派工（消费采集接入清单） ----

    def domain_dispatch_trial(self, receipt_id: str, operator: str = "值班员") -> tuple[dict[str, Any] | None, str]:
        """按导入回执发起一次试采派工。

        只读取核对通过的来源；同一回执同一清单行已受理过的试采不重发，
        待查来源保留待查原因，等补证后下次派工再受理。
        """
        receipt = intake_store.find_receipt(receipt_id)
        if receipt is None:
            return None, f"导入回执 {receipt_id} 不存在，无法发起试采"

        dispatched: list[dict[str, Any]] = []
        already_accepted: list[dict[str, Any]] = []
        pending_evidence: list[dict[str, Any]] = []
        for row in receipt["清单行"]:
            if row.get("核对状态") != "核对通过":
                pending_evidence.append({
                    "行号": row["行号"],
                    "来源别名": row["来源别名"],
                    "起始地址": row["起始地址"],
                    "页面编码": row["页面编码"],
                    "待查原因": row["待查原因"],
                    "原清单行": row["原清单行"],
                })
                continue
            existing = intake_store.find_dispatch(receipt_id, row["行号"])
            if existing is not None:
                already_accepted.append(existing)
                continue
            record = {
                "试采编号": intake_store.next_trial_id(),
                "回执编号": receipt_id,
                "清单行号": row["行号"],
                "来源别名": row["来源别名"],
                "起始地址": row["起始地址"],
                "页面编码": row["页面编码"],
                "原页标题": row.get("原页标题", ""),
                "原清单行": row["原清单行"],
                "状态": "已派工",
                "派工时间": _now(),
                "操作人": operator,
            }
            intake_store.add_dispatch(record)
            dispatched.append(record)

        result = {
            "回执编号": receipt_id,
            "本次派工": dispatched,
            "已受理未重发": already_accepted,
            "待补证": pending_evidence,
            "汇总": {
                "本次派工": len(dispatched),
                "已受理未重发": len(already_accepted),
                "待补证": len(pending_evidence),
            },
        }
        message = (
            f"试采派工完成：本次派工{len(dispatched)}个来源，"
            f"已受理未重发{len(already_accepted)}个，待补证{len(pending_evidence)}个"
        )
        return result, message

    def domain_list_trial_requests(self, receipt_id: str | None = None) -> dict[str, Any]:
        """核查入口：列出实际收到的试采请求，每条都带原清单行。"""
        records = intake_store.dispatches(receipt_id)
        return {"items": records, "total": len(records)}
