from fastapi import APIRouter

from app.api import (
    depositos,
    entregas,
    geocoding,
    health,
    matrix,
    rotas,
    veiculos,
)

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(depositos.router)
api_router.include_router(veiculos.router)
api_router.include_router(entregas.router)
api_router.include_router(rotas.router)
api_router.include_router(geocoding.router)
api_router.include_router(matrix.router)