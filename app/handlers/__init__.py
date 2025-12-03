from aiogram import Router

from .start import router as start_router
from .membership import router as membership_router
from .admin_panel import router as admin_router
from .user_flow import router as user_router
from .publish_flow import router as publish_router

# یک Router مرکزی صادر می‌کنیم
router = Router()
router.include_router(start_router)
router.include_router(membership_router)
router.include_router(admin_router)
router.include_router(user_router)
router.include_router(publish_router)
