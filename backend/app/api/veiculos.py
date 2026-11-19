from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Veiculo
from app.schemas import (
    VeiculoCreate,
    VeiculoResponse,
    VeiculoTipo,
    VeiculoUpdate,
)

router = APIRouter(prefix="/veiculos", tags=["Veículos"])


@router.post("", response_model=VeiculoResponse, status_code=status.HTTP_201_CREATED)
async def create_veiculo(
    veiculo: VeiculoCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VeiculoResponse:
    db_veiculo = Veiculo(**veiculo.model_dump())
    session.add(db_veiculo)
    await session.commit()
    await session.refresh(db_veiculo)
    return db_veiculo


@router.get("", response_model=list[VeiculoResponse])
async def list_veiculos(
    session: Annotated[AsyncSession, Depends(get_session)],
    ativo: Annotated[bool | None, Query()] = None,
    tipo: Annotated[VeiculoTipo | None, Query()] = None,
) -> list[VeiculoResponse]:
    stmt = select(Veiculo)
    if ativo is not None:
        stmt = stmt.where(Veiculo.ativo == ativo)
    if tipo is not None:
        stmt = stmt.where(Veiculo.tipo == tipo)
    stmt = stmt.order_by(Veiculo.placa)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{veiculo_id}", response_model=VeiculoResponse)
async def get_veiculo(
    veiculo_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VeiculoResponse:
    veiculo = await session.get(Veiculo, veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")
    return veiculo


@router.put("/{veiculo_id}", response_model=VeiculoResponse)
async def update_veiculo(
    veiculo_id: int,
    veiculo_update: VeiculoUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> VeiculoResponse:
    veiculo = await session.get(Veiculo, veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")

    update_data = veiculo_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(veiculo, field, value)

    await session.commit()
    await session.refresh(veiculo)
    return veiculo


@router.delete("/{veiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_veiculo(
    veiculo_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    veiculo = await session.get(Veiculo, veiculo_id)
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado")

    veiculo.ativo = False
    await session.commit()