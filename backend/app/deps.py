"""
Dependency injection functions for TrendVest.
Avoids circular imports: routers import deps, main sets deps at startup.
"""
from typing import Optional

_db_pool = None
_stock_service = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


def set_stock_service(service):
    global _stock_service
    _stock_service = service


async def get_db_pool():
    if _db_pool is None:
        raise RuntimeError("Database pool not initialized")
    return _db_pool


async def get_stock_service():
    if _stock_service is None:
        from .services.stocks import StockPriceService
        set_stock_service(StockPriceService())
    return _stock_service
