"""业务路由汇总：所有模块共用一套资源路由，由领域服务完成分派。"""
from __future__ import annotations

from app.routers import source_intake
from app.routers import resource
from app.routers import chains

# source_intake 的固定路径（如 /api/crawler_config/source-imports）必须先于
# 通用资源路由注册，否则会被 /api/{module}/{entry_id} 抢先匹配。
ROUTERS = [source_intake, resource, chains]
