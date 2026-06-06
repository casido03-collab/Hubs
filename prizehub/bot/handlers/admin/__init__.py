from aiogram import Router
from .router import router as base_router
from .stats import router as stats_router
from .seasons import router as seasons_router
from .raffles import router as raffles_router
from .users import router as users_router
from .winners import router as winners_router
from .pushes import router as pushes_router

admin_router = Router()
admin_router.include_router(base_router)
admin_router.include_router(stats_router)
admin_router.include_router(seasons_router)
admin_router.include_router(raffles_router)
admin_router.include_router(users_router)
admin_router.include_router(winners_router)
admin_router.include_router(pushes_router)

__all__ = ["admin_router"]
