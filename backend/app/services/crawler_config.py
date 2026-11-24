"""爬虫配置领域服务：字段、状态和动作来自业务配置，数据处理骨架由基类复用。

新增来源清单 CSV 导入能力：用本地原页样本核对地址与编码，生成采集接入清单；
无法提出可用样本的来源保留待查原因，补证后旧回执保持可查。
"""
from __future__ import annotations

import base64
import binascii
import csv
import io
import re
import time
from typing import Any

from app.intake_store import intake_store
from app.services.base import BaseModuleService

# 来源清单 CSV 必须携带的三列；同名来源只靠真实起始地址区分。
SOURCE_CSV_COLUMNS = ["来源别名", "起始地址", "页面编码"]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _extract_title(html_text: str) -> str:
    match = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else ""


def verify_against_local_page(alias: str, address: str, encoding: str) -> dict[str, str]:
    """用本地原页样本核对一行来源的地址与编码。

    返回 核对状态/待查原因/原页标题：样本缺失、编码无法识别或解码失败都保留待查原因。
    """
    alias = alias.strip()
    address = address.strip()
    encoding = encoding.strip()
    problems: list[str] = []
    if not alias:
        problems.append("来源别名为空")
    if not address:
        problems.append("起始地址为空")
    elif not address.startswith(("http://", "https://")):
        problems.append("起始地址不是有效的 http(s) 地址")
    if not encoding:
        problems.append("页面编码为空")
    if problems:
        return {"核对状态": "待查", "待查原因": "；".join(problems), "原页标题": ""}

    sample = intake_store.find_sample(address)
    if sample is None:
        return {"核对状态": "待查", "待查原因": "缺少本地原页样本，地址与编码待核对", "原页标题": ""}
    try:
        raw = base64.b64decode(sample["原页内容"], validate=True)
    except (binascii.Error, ValueError):
        return {"核对状态": "待查", "待查原因": "本地原页样本不是有效的 base64 内容", "原页标题": ""}
    try:
        text = raw.decode(encoding)
    except LookupError:
        return {"核对状态": "待查", "待查原因": f"页面编码「{encoding}」无法识别", "原页标题": ""}
    except UnicodeDecodeError:
        return {"核对状态": "待查", "待查原因": f"本地原页按声明编码「{encoding}」解码失败，编码待核对", "原页标题": ""}
    if not text.strip():
        return {"核对状态": "待查", "待查原因": "本地原页样本内容为空", "原页标题": ""}
    return {"核对状态": "核对通过", "待查原因": "", "原页标题": _extract_title(text)}


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "清单行数": len(rows),
        "核对通过": sum(1 for row in rows if row.get("核对状态") == "核对通过"),
        "待查": sum(1 for row in rows if row.get("核对状态") == "待查"),
    }


class CrawlerConfigService(BaseModuleService):
    MODULE = "crawler_config"
    ENTITY = "爬虫配置"
    OPERATION_TERM = "校验"
    LIST_FIELDS = ["配置标识", "起始地址", "页面编码", "请求间隔", "超时秒数", "并发上限", "UA模板", "负责人"]
    REQUIRED_FIELDS = ["配置标识", "起始地址", "页面编码"]
    STATUS_ORDER = ["草稿", "待校验", "已启用", "已停用"]
    ACTION_RULES = {"提交校验": "待校验", "启用配置": "已启用", "停用配置": "已停用"}
    NEGATIVE_ACTIONS = ["停用配置"]

    def domain_validate_config(self, config_id: int, url: str = "") -> dict:
        """校验爬虫配置地址可达性。"""
        # 数据工程操作：归档→数据→处理，处理批次记录并写入可追溯结果
        from app.store import store
        entry = store.find(self.MODULE, config_id)
        reachable = bool(url and url.startswith(("http://", "https://")))        # 返回归档处理结果，含数据校验和处理批次信息

        return {
            "config_id": config_id,
            "url": url,
            "reachable": reachable,
            "checked_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
            "entry": entry,
        }

    # ---- 来源清单 CSV 导入 ----

    def domain_import_source_list(
        self,
        csv_text: str,
        samples: list[dict[str, Any]] | None = None,
        operator: str = "值班员",
    ) -> tuple[dict[str, Any] | None, str]:
        """导入来源清单 CSV，用本地原页核对地址与编码，生成采集接入清单和导入回执。"""
        registered = 0
        for sample in samples or []:
            address = str(sample.get("起始地址", "")).strip()
            content = str(sample.get("原页内容", "")).strip()
            if not address or not content:
                continue
            intake_store.register_sample(
                address,
                str(sample.get("页面编码", "")).strip(),
                content,
                origin="导入随附",
                operator=operator,
            )
            registered += 1

        parsed, error = self._parse_source_csv(csv_text)
        if parsed is None:
            return None, error

        receipt_id = intake_store.next_receipt_id()
        rows: list[dict[str, Any]] = []
        for row_no, (raw_line, cells) in enumerate(parsed, start=1):
            alias = cells.get("来源别名", "").strip()
            address = cells.get("起始地址", "").strip()
            encoding = cells.get("页面编码", "").strip()
            verdict = verify_against_local_page(alias, address, encoding)
            rows.append({
                "行号": row_no,
                "来源别名": alias,
                "起始地址": address,
                "页面编码": encoding,
                "核对状态": verdict["核对状态"],
                "待查原因": verdict["待查原因"],
                "原页标题": verdict["原页标题"],
                "原清单行": raw_line,
                "核对记录": [{
                    "时间": _now(),
                    "结果": verdict["核对状态"],
                    "说明": verdict["待查原因"] or "本地原页核对地址与编码通过",
                }],
            })

        receipt = {
            "回执编号": receipt_id,
            "导入时间": _now(),
            "导入人": operator,
            "随附样本数": registered,
            "清单行": rows,
            "汇总": summarize_rows(rows),
            "补证记录": [],
        }
        intake_store.add_receipt(receipt)
        summary = receipt["汇总"]
        message = (
            f"来源清单导入完成：共{summary['清单行数']}行，"
            f"核对通过{summary['核对通过']}行，待查{summary['待查']}行"
        )
        return receipt, message

    def _parse_source_csv(self, csv_text: str) -> tuple[list[tuple[str, dict[str, str]]] | None, str]:
        """解析来源清单 CSV，返回 (原始行文本, 按列名取值) 列表。"""
        text = csv_text.lstrip("﻿").strip()
        if not text:
            return None, "来源清单 CSV 内容为空"
        reader = csv.reader(io.StringIO(text))
        raw_rows = [row for row in reader if any(cell.strip() for cell in row)]
        if not raw_rows:
            return None, "来源清单 CSV 内容为空"
        header = [cell.strip() for cell in raw_rows[0]]
        missing = [column for column in SOURCE_CSV_COLUMNS if column not in header]
        if missing:
            return None, f"来源清单缺少必需列：{'、'.join(missing)}（需要：{'、'.join(SOURCE_CSV_COLUMNS)}）"
        data_rows = raw_rows[1:]
        if not data_rows:
            return None, "来源清单只有表头，没有数据行"
        parsed: list[tuple[str, dict[str, str]]] = []
        for raw in data_rows:
            cells = {
                column: (raw[header.index(column)].strip() if header.index(column) < len(raw) else "")
                for column in SOURCE_CSV_COLUMNS
            }
            parsed.append((",".join(raw), cells))
        return parsed, ""

    def domain_list_source_imports(self) -> dict[str, Any]:
        """列出全部导入回执；补证不换新回执，旧回执始终保持可查。"""
        receipts = [
            {key: value for key, value in receipt.items() if key != "清单行"}
            for receipt in intake_store.receipts()
        ]
        return {"items": receipts, "total": len(receipts)}

    def domain_get_source_import(self, receipt_id: str) -> dict[str, Any] | None:
        """按回执编号读取采集接入清单明细。"""
        return intake_store.find_receipt(receipt_id)

    def domain_supplement_origin_sample(
        self,
        receipt_id: str,
        address: str,
        content_b64: str,
        encoding: str = "",
        operator: str = "值班员",
    ) -> tuple[dict[str, Any] | None, str]:
        """补交本地原页样本：登记样本库并对该回执中同地址的清单行重新核对。

        旧回执保持原编号，只更新清单行核对结果并追加核对/补证记录。
        """
        receipt = intake_store.find_receipt(receipt_id)
        if receipt is None:
            return None, f"导入回执 {receipt_id} 不存在"
        address = address.strip()
        targets = [row for row in receipt["清单行"] if row.get("起始地址") == address]
        if not address or not targets:
            return None, f"回执 {receipt_id} 中没有起始地址为「{address}」的清单行"
        if not content_b64.strip():
            return None, "补交的原页样本内容为空"

        intake_store.register_sample(
            address,
            encoding.strip() or targets[0].get("页面编码", ""),
            content_b64.strip(),
            origin="补证登记",
            operator=operator,
        )
        rechecked: list[dict[str, Any]] = []
        for row in targets:
            verdict = verify_against_local_page(row["来源别名"], row["起始地址"], row["页面编码"])
            row["核对状态"] = verdict["核对状态"]
            row["待查原因"] = verdict["待查原因"]
            row["原页标题"] = verdict["原页标题"]
            row["核对记录"].append({
                "时间": _now(),
                "结果": verdict["核对状态"],
                "说明": verdict["待查原因"] or "补证样本核对地址与编码通过",
            })
            rechecked.append(row)

        receipt["补证记录"].append({
            "时间": _now(),
            "起始地址": address,
            "操作人": operator,
            "结果": "、".join(f"行{row['行号']}{row['核对状态']}" for row in rechecked),
        })
        receipt["汇总"] = summarize_rows(receipt["清单行"])
        passed = sum(1 for row in rechecked if row["核对状态"] == "核对通过")
        message = (
            f"补证样本已登记并重新核对：{address}，"
            f"{passed}/{len(rechecked)} 行核对通过，旧回执 {receipt_id} 保持有效"
        )
        return {"回执": receipt, "重新核对": rechecked}, message
