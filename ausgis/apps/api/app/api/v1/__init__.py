from fastapi import APIRouter
from app.api.v1.endpoints import auth, projects, layers, analysis, geocode, abs

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(projects.router)
api_router.include_router(layers.router)
api_router.include_router(analysis.router)
api_router.include_router(geocode.router)
api_router.include_router(abs.router)
