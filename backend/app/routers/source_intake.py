"""来源清单导入与试采派工接口。

爬虫配置侧：导入来源清单 CSV、查导入回执、补交本地原页样本；
采集调度侧：从导入回执发起试采派工、核查实际收到的试采请求。

路由挂在 /api 下并先于通用资源路由注册，避免被 /api/{module}/{entry_id} 抢先匹配。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas import SampleSupplementPayload, SourceImportPayload, TrialDispatchPayload
from app.services.crawler_config import CrawlerConfigService
from app.services.crawl_schedule import CrawlScheduleService

router = APIRouter(prefix="/api", tags=["来源接入与试采"])

_crawler = CrawlerConfigService()
_schedule = CrawlScheduleService()


@router.post("/crawler_config/source-imports")
def import_source_list(payload: SourceImportPayload) -> dict:
    """导入来源清单 CSV：本地原页核对地址与编码，生成采集接入清单和导入回执。"""
    receipt, message = _crawler.domain_import_source_list(
        payload.csv_text, samples=payload.samples, operator=payload.operator)
    if receipt is None:
        raise HTTPException(status_code=422, detail=message)
    return {"ok": True, "message": message, "回执": receipt}


@router.get("/crawler_config/source-imports")
def list_source_imports() -> dict:
    """列出全部导入回执；补证不换新回执，旧回执始终保持可查。"""
    result = _crawler.domain_list_source_imports()
    return {"ok": True, **result}


@router.get("/crawler_config/source-imports/{receipt_id}")
def get_source_import(receipt_id: str) -> dict:
    """按回执编号读取采集接入清单明细（含每行核对状态与待查原因）。"""
    receipt = _crawler.domain_get_source_import(receipt_id)
    if receipt is None:
        raise HTTPException(status_code=404, detail=f"导入回执 {receipt_id} 不存在")
    return {"ok": True, "回执": receipt}


@router.post("/crawler_config/source-imports/{receipt_id}/samples")
def supplement_origin_sample(receipt_id: str, payload: SampleSupplementPayload) -> dict:
    """补交本地原页样本：登记样本库并重新核对该回执中同地址的清单行。"""
    result, message = _crawler.domain_supplement_origin_sample(
        receipt_id,
        payload.address,
        payload.content_b64,
        encoding=payload.encoding or "",
        operator=payload.operator,
    )
    if result is None:
        raise HTTPException(status_code=422, detail=message)
    return {"ok": True, "message": message, **result}


@router.post("/crawl_schedule/trial-dispatches")
def dispatch_trial(payload: TrialDispatchPayload) -> dict:
    """试采派工入口：只派工核对通过的来源，已受理的试采不重发。"""
    result, message = _schedule.domain_dispatch_trial(
        payload.receipt_id, operator=payload.operator)
    if result is None:
        raise HTTPException(status_code=404, detail=message)
    return {"ok": True, "message": message, **result}


@router.get("/crawl_schedule/trial-dispatches")
def list_trial_dispatches(receipt_id: str | None = Query(default=None)) -> dict:
    """试采核查入口：列出实际收到的试采请求及其原清单行。"""
    result = _schedule.domain_list_trial_requests(receipt_id)
    return {"ok": True, **result}
