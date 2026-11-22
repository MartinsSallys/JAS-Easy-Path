"""Fluxo completo POST /rotas/{id}/otimizar: API -> motor -> persistência."""

from collections.abc import AsyncIterator
from datetime import date

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_session
from app.main import app

API = "/api/v1"
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_UNPROCESSABLE = 422
OPTIMIZE_TIME_LIMIT = 5
EXPECTED_PARADAS = 4  # depósito + 2 entregas + depósito
DELIVERY_COUNT = 2
EXPECTED_DEMAND = 3
SERVICE_TIME_MIN = 8


@pytest.fixture
async def session_maker() -> AsyncIterator[async_sessionmaker]:
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    yield maker
    await engine.dispose()


@pytest.fixture
async def client(
    session_maker: async_sessionmaker,
) -> AsyncIterator[AsyncClient]:
    async def override_session() -> AsyncIterator[AsyncSession]:
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)


async def _seed_rota(
    client: AsyncClient,
    entregas_payload: list[dict],
) -> int:
    deposito = await client.post(
        f"{API}/depositos",
        json={
            "nome": "CD Central",
            "endereco": "Av. Depot, 100",
            "latitude": -23.5617,
            "longitude": -46.6560,
        },
    )
    assert deposito.status_code == HTTP_CREATED

    veiculo = await client.post(
        f"{API}/veiculos",
        json={"placa": "ABC1234", "capacidade": 20, "tipo": "CAMINHAO"},
    )
    assert veiculo.status_code == HTTP_CREATED

    entrega_ids = []
    for payload in entregas_payload:
        entrega = await client.post(f"{API}/entregas", json=payload)
        assert entrega.status_code == HTTP_CREATED
        entrega_ids.append(entrega.json()["id"])

    rota = await client.post(
        f"{API}/rotas",
        json={
            "nome": "Rota Teste",
            "data": date.today().isoformat(),
            "deposito_id": deposito.json()["id"],
            "veiculo_id": veiculo.json()["id"],
            "entrega_ids": entrega_ids,
        },
    )
    assert rota.status_code == HTTP_CREATED
    return rota.json()["id"]


def _entrega_payload(pedido_id: str, latitude: float, longitude: float) -> dict:
    return {
        "pedido_id": pedido_id,
        "endereco": f"Rua {pedido_id}, 10",
        "latitude": latitude,
        "longitude": longitude,
        "demanda": EXPECTED_DEMAND,
    }


@pytest.mark.asyncio
async def test_otimizar_persiste_paradas_com_metricas(
    client: AsyncClient,
) -> None:
    rota_id = await _seed_rota(
        client,
        [
            _entrega_payload("P001", -23.5505, -46.6333),
            _entrega_payload("P002", -23.5550, -46.6400),
        ],
    )

    response = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["status"] == "OTIMIZADA"
    assert body["distancia_total_km"] > 0
    assert body["tempo_total_min"] > 0

    paradas = body["paradas"]
    assert len(paradas) == EXPECTED_PARADAS

    # Rota começa e termina no depósito, sem demanda residual negativa
    assert paradas[0]["entrega_id"] is None
    assert paradas[-1]["entrega_id"] is None
    for parada in paradas:
        assert parada["demanda"] >= 0
    assert paradas[-1]["demanda"] == 0

    # Paradas de entrega carregam janela e previsões do motor
    entrega_paradas = [p for p in paradas if p["entrega_id"] is not None]
    assert len(entrega_paradas) == DELIVERY_COUNT
    for parada in entrega_paradas:
        assert parada["demanda"] == EXPECTED_DEMAND
        assert parada["tempo_servico_min"] == SERVICE_TIME_MIN
        assert parada["chegada_prevista"] is not None
        assert parada["saida_prevista"] is not None
        assert parada["status"] == "PENDENTE"

    # Entregas foram vinculadas à ordem da parada
    entregas = await client.get(f"{API}/entregas")
    for entrega in entregas.json():
        assert entrega["parada_ordem"] is not None
        assert entrega["status"] == "ATRIBUIDA"


@pytest.mark.asyncio
async def test_otimizar_janela_inviavel_retorna_422(
    client: AsyncClient,
) -> None:
    """Janela 09:00–09:01 não comporta 8 min de atendimento: 422."""
    rota_id = await _seed_rota(
        client,
        [
            {
                **_entrega_payload("P001", -23.5505, -46.6333),
                "janela_inicio": "09:00",
                "janela_fim": "09:01",
            },
        ],
    )

    response = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert response.status_code == HTTP_UNPROCESSABLE

    # Nada foi persistido como otimizado
    rota = await client.get(f"{API}/rotas/{rota_id}")
    assert rota.json()["status"] == "RASCUNHO"
    assert rota.json()["paradas"] == []
