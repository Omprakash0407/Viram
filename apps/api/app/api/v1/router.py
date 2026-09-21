"""API v1 router assembly."""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.admin.router import router as admin_router
from app.modules.chat.router import router as chat_router
from app.modules.commerce.router import router as commerce_router
from app.modules.geo.router import router as geo_router
from app.modules.intelligence.router import router as intelligence_router
from app.modules.planning.companions_router import router as companions_router
from app.modules.planning.location_router import router as location_router
from app.modules.planning.meta import router as planning_meta_router
from app.modules.planning.router import router as trips_router
from app.modules.providers.router import router as providers_router
from app.modules.reviews.router import router as reviews_router
from app.modules.safety.router import router as safety_router
from app.modules.users.router import auth_router, users_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(chat_router)
api_v1_router.include_router(geo_router)
api_v1_router.include_router(planning_meta_router)
api_v1_router.include_router(trips_router)
api_v1_router.include_router(companions_router)
api_v1_router.include_router(location_router)
api_v1_router.include_router(commerce_router)
api_v1_router.include_router(reviews_router)
api_v1_router.include_router(intelligence_router)
api_v1_router.include_router(safety_router)
api_v1_router.include_router(providers_router)
api_v1_router.include_router(admin_router)
