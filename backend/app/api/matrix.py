from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.schemas import MatrixRequest, MatrixResponse
from app.services import matrix_service

router = APIRouter(prefix="/matrix", tags=["Matriz de Distância/Tempo"])


@router.post("/calculate", response_model=MatrixResponse)
async def calculate_matrix(
    request: MatrixRequest,
    session: AsyncSession = Depends(get_session),
):
    try:
        locations = [
            {"latitude": loc["latitude"], "longitude": loc["longitude"]}
            for loc in request.locations
        ]
        result = await matrix_service.get_matrix_chunked(
            locations=locations,
            metrics=request.metrics,
            profile=request.profile,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no cálculo da matriz: {str(e)}")