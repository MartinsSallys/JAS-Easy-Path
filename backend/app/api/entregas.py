from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models import Entrega, Parada
from app.schemas import (
    EntregaBatchCreate,
    EntregaCreate,
    EntregaResponse,
    EntregaStatus,
    EntregaUpdate,
)

router = APIRouter(prefix="/entregas", tags=["Entregas"])


@router.post("", response_model=EntregaResponse, status_code=status.HTTP_201_CREATED)
async def create_entrega(
    entrega: EntregaCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EntregaResponse:
    db_entrega = Entrega(**entrega.model_dump())
    session.add(db_entrega)
    await session.commit()
    await session.refresh(db_entrega)
    return db_entrega


@router.post("/batch", response_model=list[EntregaResponse], status_code=status.HTTP_201_CREATED)
async def create_entregas_batch(
    batch: EntregaBatchCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> list[EntregaResponse]:
    db_entregas = [Entrega(**e.model_dump()) for e in batch.entregas]
    session.add_all(db_entregas)
    await session.commit()
    for e in db_entregas:
        await session.refresh(e)
    return db_entregas


@router.get("", response_model=list[EntregaResponse])
async def list_entregas(
    session: Annotated[AsyncSession, Depends(get_session)],
    status: Annotated[EntregaStatus | None, Query()] = None,
    rota_id: Annotated[int | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[EntregaResponse]:
    stmt = select(Entrega).order_by(Entrega.created_at.desc())
    if status is not None:
        stmt = stmt.where(Entrega.status == status)
    if rota_id is not None:
        stmt = stmt.where(Entrega.rota_id == rota_id)
    stmt = stmt.limit(limit).offset(offset)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{entrega_id}", response_model=EntregaResponse)
async def get_entrega(
    entrega_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EntregaResponse:
    entrega = await session.get(Entrega, entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega não encontrada")
    return entrega


@router.put("/{entrega_id}", response_model=EntregaResponse)
async def update_entrega(
    entrega_id: int,
    entrega_update: EntregaUpdate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> EntregaResponse:
    entrega = await session.get(Entrega, entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega não encontrada")

    update_data = entrega_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(entrega, field, value)

    if (entrega.janela_inicio is None) != (entrega.janela_fim is None):
        raise HTTPException(
            status_code=422,
            detail="janela_inicio e janela_fim devem ser informados juntos",
        )

    await session.commit()
    await session.refresh(entrega)
    return entrega


@router.delete("/{entrega_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entrega(
    entrega_id: int,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> None:
    entrega = await session.get(Entrega, entrega_id)
    if not entrega:
        raise HTTPException(status_code=404, detail="Entrega não encontrada")

    if entrega.status in (EntregaStatus.EM_ROTA, EntregaStatus.ENTREGUE):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Entrega em andamento ou concluída não pode ser excluída "
                "— faz parte do histórico da rota"
            ),
        )

    entrega.status = EntregaStatus.CANCELADA
    entrega.parada_ordem = None
    # Remove a parada do plano otimizado: sem isso a rota continuaria
    # exibindo uma parada de entrega cancelada até a próxima reotimização.
    await session.execute(
        Parada.__table__.delete().where(Parada.entrega_id == entrega.id)
    )
    await session.commit()