"""来源清单导入 → 本地原页核对 → 试采派工 → 补证恢复 → 核查 全流程测试。

场景：同一次导入两个同别名不同地址的来源；主站随附可解码原页，分站开始没有原页；
试采只派工核对通过的主站；补交分站编码样本后恢复派工，主站已受理不重发；
最后从采集调度的核查入口确认实际收到的试采请求及其原 CSV 行。
"""
import base64
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.crawler_config import CrawlerConfigService
from app.services.crawl_schedule import CrawlScheduleService

crawler = CrawlerConfigService()
schedule = CrawlScheduleService()

ALIAS = "晨讯早报"
MAIN_ADDR = "https://news.example.com/main"
BRANCH_ADDR = "https://news.example.com/branch"


def _b64(text: str, encoding: str) -> str:
    return base64.b64encode(text.encode(encoding)).decode("ascii")


def _csv_text() -> str:
    return (
        "来源别名,起始地址,页面编码\n"
        f"{ALIAS},{MAIN_ADDR},utf-8\n"
        f"{ALIAS},{BRANCH_ADDR},gbk\n"
    )


def test_full_intake_trial_flow():
    # 1) 导入：主站随附可解码的 utf-8 原页，分站没有原页
    main_page = _b64("<html><head><title>晨讯早报主站</title></head><body>主站列表页</body></html>", "utf-8")
    receipt, message = crawler.domain_import_source_list(
        _csv_text(),
        samples=[{"起始地址": MAIN_ADDR, "页面编码": "utf-8", "原页内容": main_page}],
        operator="值班员甲",
    )
    assert receipt is not None, message
    receipt_id = receipt["回执编号"]
    assert receipt["汇总"] == {"清单行数": 2, "核对通过": 1, "待查": 1}

    rows = {row["起始地址"]: row for row in receipt["清单行"]}
    # 同名来源按真实地址分清：主站核对通过，分站缺样本待查
    assert rows[MAIN_ADDR]["核对状态"] == "核对通过"
    assert rows[MAIN_ADDR]["原页标题"] == "晨讯早报主站"
    assert rows[BRANCH_ADDR]["核对状态"] == "待查"
    assert "缺少本地原页样本" in rows[BRANCH_ADDR]["待查原因"]
    # 两行同别名但地址不同，都保留自己的清单行号
    assert rows[MAIN_ADDR]["来源别名"] == rows[BRANCH_ADDR]["来源别名"] == ALIAS
    assert rows[MAIN_ADDR]["行号"] != rows[BRANCH_ADDR]["行号"]

    # 2) 值班员从导入回执提交一次试采：主站派工，分站待补证
    result, message = schedule.domain_dispatch_trial(receipt_id, operator="值班员甲")
    assert result is not None, message
    assert result["汇总"] == {"本次派工": 1, "已受理未重发": 0, "待补证": 1}
    assert result["本次派工"][0]["起始地址"] == MAIN_ADDR
    assert result["本次派工"][0]["状态"] == "已派工"
    assert result["待补证"][0]["起始地址"] == BRANCH_ADDR
    assert "缺少本地原页样本" in result["待补证"][0]["待查原因"]

    # 3) 补交分站编码样本（gbk 原页）：分站核对通过，旧回执保持
    branch_page = _b64("<html><head><title>晨讯早报分站</title></head><body>分站列表页</body></html>", "gbk")
    supplemented, message = crawler.domain_supplement_origin_sample(
        receipt_id, BRANCH_ADDR, branch_page, operator="值班员甲")
    assert supplemented is not None, message
    assert supplemented["回执"]["回执编号"] == receipt_id  # 旧回执不换新
    branch_row = [r for r in supplemented["回执"]["清单行"] if r["起始地址"] == BRANCH_ADDR][0]
    assert branch_row["核对状态"] == "核对通过"
    assert branch_row["待查原因"] == ""
    assert branch_row["原页标题"] == "晨讯早报分站"
    assert len(branch_row["核对记录"]) == 2  # 首次待查 + 补证通过都留痕
    assert supplemented["回执"]["汇总"]["核对通过"] == 2
    assert supplemented["回执"]["补证记录"]

    # 旧回执仍然可查
    listed = crawler.domain_list_source_imports()
    assert any(item["回执编号"] == receipt_id for item in listed["items"])

    # 4) 恢复试采：分站派工，主站已受理不重发
    result2, message = schedule.domain_dispatch_trial(receipt_id, operator="值班员甲")
    assert result2 is not None, message
    assert result2["汇总"] == {"本次派工": 1, "已受理未重发": 1, "待补证": 0}
    assert result2["本次派工"][0]["起始地址"] == BRANCH_ADDR
    assert result2["已受理未重发"][0]["起始地址"] == MAIN_ADDR
    # 主站试采编号保持第一次派工时的编号，没有重发
    assert result2["已受理未重发"][0]["试采编号"] == result["本次派工"][0]["试采编号"]

    # 5) 核查入口：实际收到两条试采请求，都能查到原 CSV 行
    trials = schedule.domain_list_trial_requests(receipt_id)
    assert trials["total"] == 2
    by_addr = {item["起始地址"]: item for item in trials["items"]}
    assert set(by_addr) == {MAIN_ADDR, BRANCH_ADDR}
    assert by_addr[MAIN_ADDR]["清单行号"] == 1
    assert by_addr[MAIN_ADDR]["原清单行"] == f"{ALIAS},{MAIN_ADDR},utf-8"
    assert by_addr[BRANCH_ADDR]["清单行号"] == 2
    assert by_addr[BRANCH_ADDR]["原清单行"] == f"{ALIAS},{BRANCH_ADDR},gbk"
    # 同别名不同地址的两条试采互不混淆
    assert by_addr[MAIN_ADDR]["试采编号"] != by_addr[BRANCH_ADDR]["试采编号"]


def test_import_rejects_bad_csv():
    receipt, message = crawler.domain_import_source_list("只有一列\n值\n")
    assert receipt is None
    assert "缺少必需列" in message

    receipt, message = crawler.domain_import_source_list("来源别名,起始地址,页面编码\n")
    assert receipt is None
    assert "没有数据行" in message


def test_import_flags_undecodable_sample():
    addr = "https://news.example.com/undecodable"
    # 用 gbk 字节冒充 utf-8 声明，解码必然失败
    fake = _b64("<html><body>字节页</body></html>", "gbk")
    receipt, message = crawler.domain_import_source_list(
        f"来源别名,起始地址,页面编码\n晨讯早报,{addr},utf-8\n",
        samples=[{"起始地址": addr, "页面编码": "gbk", "原页内容": fake}],
    )
    assert receipt is not None, message
    row = receipt["清单行"][0]
    assert row["核对状态"] == "待查"
    assert "解码失败" in row["待查原因"]


def test_import_flags_invalid_address():
    addr = "ftp://news.example.com/main"
    receipt, message = crawler.domain_import_source_list(
        f"来源别名,起始地址,页面编码\n晨讯早报,{addr},utf-8\n")
    assert receipt is not None, message
    row = receipt["清单行"][0]
    assert row["核对状态"] == "待查"
    assert "不是有效的 http(s) 地址" in row["待查原因"]


def test_dispatch_unknown_receipt():
    result, message = schedule.domain_dispatch_trial("IMP-9999")
    assert result is None
    assert "不存在" in message


def test_supplement_unknown_receipt_and_address():
    result, message = crawler.domain_supplement_origin_sample("IMP-9999", MAIN_ADDR, "AAAA")
    assert result is None
    assert "不存在" in message

    # 回执存在但地址不在清单里
    receipt, _ = crawler.domain_import_source_list(
        "来源别名,起始地址,页面编码\n晨讯早报,https://news.example.com/lonely,utf-8\n")
    result, message = crawler.domain_supplement_origin_sample(
        receipt["回执编号"], "https://news.example.com/elsewhere", "AAAA")
    assert result is None
    assert "没有起始地址" in message


def test_pending_row_keeps_reason_across_dispatches():
    addr = "https://news.example.com/no-sample"
    receipt, _ = crawler.domain_import_source_list(
        f"来源别名,起始地址,页面编码\n晨讯早报,{addr},utf-8\n")
    receipt_id = receipt["回执编号"]
    first, _ = schedule.domain_dispatch_trial(receipt_id)
    second, _ = schedule.domain_dispatch_trial(receipt_id)
    # 两次派工都不受理缺样本的来源，待查原因一直保留
    assert first["汇总"] == {"本次派工": 0, "已受理未重发": 0, "待补证": 1}
    assert second["汇总"] == {"本次派工": 0, "已受理未重发": 0, "待补证": 1}
    assert "缺少本地原页样本" in second["待补证"][0]["待查原因"]
