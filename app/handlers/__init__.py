from aiogram import Router

from .admin_panel import router as admin_router
from .membership import router as membership_router
from .publish_flow import router as publish_router
from .start import router as start_router
from .user_flow import router as user_flow_router

router = Router()

# ترتیب مهم است: هندلرهای ادمین معمولاً بالاتر هستند
router.include_router(admin_router)
router.include_router(start_router)
router.include_router(membership_router)
router.include_router(publish_router)
router.include_router(user_flow_router)