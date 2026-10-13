from app.routers.system import router as system_router
from app.routers.auth import router as auth_router
from app.routers.admin import router as admin_router
from app.routers.queue import router as queue_router
from app.routers.doctor import router as doctor_router
from app.routers.nurse import router as nurse_router
from app.routers.qr import router as qr_router

__all__ = [
    "system_router",
    "auth_router",
    "admin_router",
    "queue_router",
    "doctor_router",
    "nurse_router",
    "qr_router",
]
