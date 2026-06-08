from aiogram import Router
from .start import router as start_router
from .onboarding import router as onboarding_router
from .subscription import router as subscription_router
from .home import router as home_router
from .earn_tickets import router as earn_router
from .rating import router as rating_router
from .winners import router as winners_router
from .profile import router as profile_router
from .info import router as info_router
from .reset import router as reset_router
from .admin import admin_router

main_router = Router()
main_router.include_router(reset_router)
main_router.include_router(start_router)
main_router.include_router(onboarding_router)
main_router.include_router(subscription_router)
main_router.include_router(home_router)
main_router.include_router(earn_router)
main_router.include_router(rating_router)
main_router.include_router(winners_router)
main_router.include_router(profile_router)
main_router.include_router(info_router)
main_router.include_router(admin_router)

__all__ = ["main_router"]
