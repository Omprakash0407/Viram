"""API v1 router assembly."""

from fastapi import APIRouter

from app.api.v1 import health
from app.modules.commerce.router import router as commerce_router
from app.modules.geo.router import router as geo_router
from app.modules.planning.meta import router as planning_meta_router
from app.modules.planning.router import router as trips_router
from app.modules.users.router import auth_router, users_router

api_v1_router = APIRouter()
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(geo_router)
api_v1_router.include_router(planning_meta_router)
api_v1_router.include_router(trips_router)
api_v1_router.include_router(commerce_router)
