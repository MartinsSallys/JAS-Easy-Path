from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Deposito
from app.schemas import (
    DepositoCreate,
    DepositoResponse,
    DepositoUpdate,
)

router = APIRouter(prefix="/depositos", tags=["Depósitos"])


@router.post("", response_model=DepositoResponse, status_code=status.HTTP_201_CREATED)
async def create_deposito(
    deposito: DepositoCreate,
    session: AsyncSession = Depends(get_session),
) -> DepositoResponse:
    db_deposito = Deposito(**deposito.model_dump())
    session.add(db_deposito)
    await session.commit()
    await session.refresh(db_deposito)
    return db_deposito


@router.get("", response_model=list[DepositoResponse])
async def list_depositos(
    ativo: bool | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[DepositoResponse]:
    stmt = select(Deposito)
    if ativo is not None:
        stmt = stmt.where(Deposito.ativo == ativo)
    stmt = stmt.order_by(Deposito.nome)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{deposito_id}", response_model=DepositoResponse)
async def get_deposito(
    deposito_id: int,
    session: AsyncSession = Depends(get_session),
) -> DepositoResponse:
    deposito = await session.get(Deposito, deposito_id)
    if not deposito:
        raise HTTPException(status_code=404, detail="Depósito não encontrado")
    return deposito


@router.put("/{deposito_id}", response_model=DepositoResponse)
async def update_deposito(
    deposito_id: int,
    deposito_update: DepositoUpdate,
    session: AsyncSession = Depends(get_session),
) -> DepositoResponse:
    deposito = await session.get(Deposito, deposito_id)
    if not deposito:
        raise HTTPException(status_code=404, detail="Depósito não encontrado")

    update_data = deposito_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(deposito, field, value)

    await session.commit()
    await session.refresh(deposito)
    return deposito


@router.delete("/{deposito_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_deposito(
    deposito_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    deposito = await session.get(Deposito, deposito_id)
    if not deposito:
        raise HTTPException(status_code=404, detail="Depósito não encontrado")

    await session.delete(deposito)
    await session.commit()