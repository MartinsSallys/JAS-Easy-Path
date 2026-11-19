from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models import Deposito, Entrega, Parada, Rota, Veiculo
from app.schemas import (
    RotaCreate,
    RotaOptimizeRequest,
    RotaResponse,
    RotaStatus,
    RotaUpdate,
    RotaWithParadasResponse,
)
from app.services import get_optimizer
from app.services.optimizer import (
    OptimizationDelivery,
    OptimizationLocation,
    OptimizationRequest,
    OptimizationVehicle,
)

router = APIRouter(prefix="/rotas", tags=["Rotas"])


@router.post("", response_model=RotaResponse, status_code=status.HTTP_201_CREATED)
async def create_rota(
    rota: RotaCreate,
    session: AsyncSession = Depends(get_session),
) -> RotaResponse:
    deposito = await session.get(Deposito, rota.deposito_id)
    if not deposito:
        raise HTTPException(status_code=404, detail="Depósito não encontrado")

    if rota.veiculo_id:
        veiculo = await session.get(Veiculo, rota.veiculo_id)
        if not veiculo:
            raise HTTPException(status_code=404, detail="Veículo não encontrado")

    if rota.entrega_ids:
        entregas = await session.execute(
            select(Entrega).where(Entrega.id.in_(rota.entrega_ids))
        )
        entregas_list = list(entregas.scalars().all())
        if len(entregas_list) != len(rota.entrega_ids):
            raise HTTPException(
                status_code=404, detail="Uma ou mais entregas não encontradas"
            )

    db_rota = Rota(
        nome=rota.nome,
        data=rota.data,
        deposito_id=rota.deposito_id,
        veiculo_id=rota.veiculo_id,
    )
    session.add(db_rota)
    await session.flush()

    if rota.entrega_ids:
        for entrega in entregas_list:
            entrega.rota_id = db_rota.id
            entrega.status = "atribuida"

    await session.commit()
    await session.refresh(db_rota)
    return db_rota


@router.get("", response_model=list[RotaResponse])
async def list_rotas(
    data: str | None = Query(None),
    status: RotaStatus | None = Query(None),
    veiculo_id: int | None = Query(None),
    session: AsyncSession = Depends(get_session),
) -> list[RotaResponse]:
    stmt = select(Rota).order_by(Rota.data.desc(), Rota.created_at.desc())
    if data:
        stmt = stmt.where(Rota.data == date.fromisoformat(data))
    if status is not None:
        stmt = stmt.where(Rota.status == status)
    if veiculo_id is not None:
        stmt = stmt.where(Rota.veiculo_id == veiculo_id)
    result = await session.execute(stmt)
    return list(result.scalars().all())


@router.get("/{rota_id}", response_model=RotaWithParadasResponse)
async def get_rota(
    rota_id: int,
    session: AsyncSession = Depends(get_session),
) -> RotaWithParadasResponse:
    stmt = (
        select(Rota)
        .options(selectinload(Rota.paradas), selectinload(Rota.entregas))
        .where(Rota.id == rota_id)
    )
    result = await session.execute(stmt)
    rota = result.scalar_one_or_none()
    if not rota:
        raise HTTPException(status_code=404, detail="Rota não encontrada")
    return rota


@router.put("/{rota_id}", response_model=RotaResponse)
async def update_rota(
    rota_id: int,
    rota_update: RotaUpdate,
    session: AsyncSession = Depends(get_session),
) -> RotaResponse:
    rota = await session.get(Rota, rota_id)
    if not rota:
        raise HTTPException(status_code=404, detail="Rota não encontrada")

    update_data = rota_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rota, field, value)

    await session.commit()
    await session.refresh(rota)
    return rota


@router.post("/{rota_id}/otimizar", response_model=RotaWithParadasResponse)
async def otimizar_rota(
    rota_id: int,
    optimize_req: RotaOptimizeRequest,
    session: AsyncSession = Depends(get_session),
) -> RotaWithParadasResponse:
    stmt = (
        select(Rota)
        .options(
            selectinload(Rota.entregas),
            selectinload(Rota.deposito),
            selectinload(Rota.veiculo),
        )
        .where(Rota.id == rota_id)
    )
    result = await session.execute(stmt)
    rota = result.scalar_one_or_none()
    if not rota:
        raise HTTPException(status_code=404, detail="Rota não encontrada")

    if not rota.entregas:
        raise HTTPException(
            status_code=400, detail="Rota não possui entregas para otimizar"
        )

    if not rota.veiculo:
        raise HTTPException(
            status_code=400, detail="Rota não possui veículo atribuído"
        )

    depot_loc = OptimizationLocation(
        latitude=rota.deposito.latitude,
        longitude=rota.deposito.longitude,
        address=rota.deposito.endereco,
    )

    vehicles = [OptimizationVehicle(id=rota.veiculo.id, capacity=rota.veiculo.capacidade)]

    deliveries = [
        OptimizationDelivery(
            id=entrega.id,
            demand=entrega.demanda,
            location=OptimizationLocation(
                latitude=entrega.latitude,
                longitude=entrega.longitude,
                address=entrega.endereco,
            ),
            time_window_start=(
                entrega.janela_inicio.isoformat() if entrega.janela_inicio else None
            ),
            time_window_end=(
                entrega.janela_fim.isoformat() if entrega.janela_fim else None
            ),
        )
        for entrega in rota.entregas
    ]

    opt_request = OptimizationRequest(
        depot=depot_loc,
        vehicles=vehicles,
        deliveries=deliveries,
        options=optimize_req,
    )

    opt_response = get_optimizer().solve(opt_request)

    if opt_response.status == "infeasible":
        raise HTTPException(
            status_code=422,
            detail="Não foi possível encontrar solução viável com as restrições atuais",
        )

    await session.execute(
        Parada.__table__.delete().where(Parada.rota_id == rota.id)
    )

    for route_result in opt_response.routes:
        for stop in route_result.stops:
            if stop.delivery_id is None:
                demanda_parada = 0
            else:
                entrega = await session.get(Entrega, stop.delivery_id)
                demanda_parada = entrega.demanda if entrega else 0

            parada = Parada(
                rota_id=rota.id,
                entrega_id=stop.delivery_id,
                deposito_id=rota.deposito_id if stop.delivery_id is None else None,
                ordem=stop.sequence,
                endereco=stop.location.address or "",
                latitude=stop.location.latitude,
                longitude=stop.location.longitude,
                demanda=demanda_parada,
                tempo_servico_min=8,
                status="pendente",
            )
            session.add(parada)

            if stop.delivery_id:
                entrega = await session.get(Entrega, stop.delivery_id)
                if entrega:
                    entrega.parada_ordem = stop.sequence
                    entrega.status = "atribuida"

    rota.status = RotaStatus.OTIMIZADA
    rota.distancia_total_km = sum(r.total_distance_km for r in opt_response.routes)
    rota.tempo_total_min = sum(r.total_duration_min for r in opt_response.routes)
    rota.otimizada_em = datetime.utcnow()
    rota.veiculo_id = route_result.vehicle_id

    await session.commit()
    await session.refresh(rota)

    stmt = (
        select(Rota)
        .options(selectinload(Rota.paradas), selectinload(Rota.entregas))
        .where(Rota.id == rota_id)
    )
    result = await session.execute(stmt)
    return result.scalar_one()


@router.delete("/{rota_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_rota(
    rota_id: int,
    session: AsyncSession = Depends(get_session),
) -> None:
    rota = await session.get(Rota, rota_id)
    if not rota:
        raise HTTPException(status_code=404, detail="Rota não encontrada")

    entregas = await session.execute(
        select(Entrega).where(Entrega.rota_id == rota_id)
    )
    for entrega in entregas.scalars().all():
        entrega.rota_id = None
        entrega.parada_ordem = None
        entrega.status = "pendente"

    await session.delete(rota)
    await session.commit()


@router.get("/{rota_id}/mapa")
async def get_rota_mapa(
    rota_id: int,
    session: AsyncSession = Depends(get_session),
) -> dict:
    stmt = (
        select(Rota)
        .options(selectinload(Rota.paradas))
        .where(Rota.id == rota_id)
    )
    result = await session.execute(stmt)
    rota = result.scalar_one_or_none()
    if not rota:
        raise HTTPException(status_code=404, detail="Rota não encontrada")

    features = [
        {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [parada.longitude, parada.latitude],
            },
            "properties": {
                "ordem": parada.ordem,
                "endereco": parada.endereco,
                "tipo": "deposito" if parada.entrega_id is None else "entrega",
                "entrega_id": parada.entrega_id,
                "status": parada.status.value,
            },
        }
        for parada in sorted(rota.paradas, key=lambda p: p.ordem)
    ]

    coordinates = [
        [p.longitude, p.latitude]
        for p in sorted(rota.paradas, key=lambda p: p.ordem)
    ]
    features.append(
        {
            "type": "Feature",
            "geometry": {
                "type": "LineString",
                "coordinates": coordinates,
            },
            "properties": {
                "rota_id": rota.id,
                "distancia_km": rota.distancia_total_km,
                "tempo_min": rota.tempo_total_min,
            },
        }
    )

    return {
        "type": "FeatureCollection",
        "features": features,
    }