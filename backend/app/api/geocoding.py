from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas import (
    GeocodeBatchRequest,
    GeocodeRequest,
    GeocodeResponse,
    ReverseGeocodeRequest,
)
from app.services import geocoder

router = APIRouter(prefix="/geocoding", tags=["Geocodificação"])


@router.post("/forward", response_model=GeocodeResponse)
async def forward_geocode(
    request: GeocodeRequest,
    session: AsyncSession = Depends(get_session),
) -> GeocodeResponse:
    try:
        return await geocoder.geocode(request.endereco, request.country_code or "br")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro na geocodificação: {str(e)}"
        ) from e


@router.post("/reverse", response_model=GeocodeResponse)
async def reverse_geocode(
    request: ReverseGeocodeRequest,
    session: AsyncSession = Depends(get_session),
) -> GeocodeResponse:
    try:
        result = await geocoder.reverse_geocode(request.latitude, request.longitude)
        return GeocodeResponse(results=[result], ambiguous=False)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro na geocodificação reversa: {str(e)}"
        ) from e


@router.post("/batch", response_model=list[GeocodeResponse])
async def batch_geocode(
    request: GeocodeBatchRequest,
    session: AsyncSession = Depends(get_session),
) -> list[GeocodeResponse]:
    try:
        return await geocoder.batch_geocode(request.enderecos, "br")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Erro no batch geocoding: {str(e)}"
        ) from e