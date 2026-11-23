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
HTTP_NO_CONTENT = 204
HTTP_BAD_REQUEST = 400
HTTP_UNPROCESSABLE = 422
OPTIMIZE_TIME_LIMIT = 5
EXPECTED_PARADAS = 4  # depósito + 2 entregas + depósito
MIN_STOPS_EXPECTED = 3  # depósito + 1 entrega + depósito
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
async def test_otimizar_janela_valida_normaliza_hhmm(
    client: AsyncClient,
) -> None:
    """Janela 09:00–12:00 é válida: time do banco (HH:MM:SS) vira HH:MM no motor."""
    rota_id = await _seed_rota(
        client,
        [
            {
                **_entrega_payload("P001", -23.5505, -46.6333),
                "janela_inicio": "09:00",
                "janela_fim": "12:00",
            },
        ],
    )

    response = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["status"] == "OTIMIZADA"
    paradas = body["paradas"]
    assert len(paradas) == MIN_STOPS_EXPECTED
    parada_entrega = next(p for p in paradas if p["entrega_id"] is not None)
    assert parada_entrega["janela_inicio"].startswith("09:00")
    assert parada_entrega["janela_fim"].startswith("12:00")


@pytest.mark.asyncio
async def test_otimizar_janela_invertida_retorna_400(
    client: AsyncClient,
) -> None:
    """Janela com início após o fim é entrada malformada: 400, não 422."""
    rota_id = await _seed_rota(
        client,
        [
            {
                **_entrega_payload("P001", -23.5505, -46.6333),
                "janela_inicio": "12:00",
                "janela_fim": "09:00",
            },
        ],
    )

    response = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert response.status_code == HTTP_BAD_REQUEST


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


async def _entregas_da_rota(client: AsyncClient, rota_id: int) -> list[dict]:
    response = await client.get(
        f"{API}/entregas", params={"rota_id": rota_id}
    )
    assert response.status_code == HTTP_OK
    return response.json()


@pytest.mark.asyncio
async def test_otimizar_sem_elegiveis_nao_reativa_cancelada(
    client: AsyncClient,
) -> None:
    """Rota cuja única entrega foi cancelada: 400 claro, sem reativá-la."""
    rota_id = await _seed_rota(
        client, [_entrega_payload("P001", -23.5505, -46.6333)]
    )
    entrega_id = (await _entregas_da_rota(client, rota_id))[0]["id"]

    delete = await client.delete(f"{API}/entregas/{entrega_id}")
    assert delete.status_code == HTTP_NO_CONTENT
    cancelled = await client.get(f"{API}/entregas/{entrega_id}")
    assert cancelled.json()["status"] == "CANCELADA"

    response = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert response.status_code == HTTP_BAD_REQUEST

    # O cancelamento é preservado e nada foi persistido como otimizado
    after = await client.get(f"{API}/entregas/{entrega_id}")
    assert after.json()["status"] == "CANCELADA"
    rota = await client.get(f"{API}/rotas/{rota_id}")
    assert rota.json()["status"] == "RASCUNHO"
    assert rota.json()["paradas"] == []


@pytest.mark.asyncio
async def test_otimizar_exclui_cancelada_e_atende_elegiveis(
    client: AsyncClient,
) -> None:
    """Entrega cancelada não vai ao solver nem volta a ATRIBUIDA."""
    rota_id = await _seed_rota(
        client,
        [
            _entrega_payload("P001", -23.5505, -46.6333),
            _entrega_payload("P002", -23.5550, -46.6400),
        ],
    )
    entregas = await _entregas_da_rota(client, rota_id)
    cancelada_id = entregas[0]["id"]
    elegivel_id = entregas[1]["id"]

    delete = await client.delete(f"{API}/entregas/{cancelada_id}")
    assert delete.status_code == HTTP_NO_CONTENT

    response = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert response.status_code == HTTP_OK
    parada_entrega_ids = {
        p["entrega_id"] for p in response.json()["paradas"] if p["entrega_id"]
    }
    assert parada_entrega_ids == {elegivel_id}

    depois = {e["id"]: e for e in await _entregas_da_rota(client, rota_id)}
    assert depois[cancelada_id]["status"] == "CANCELADA"
    assert depois[cancelada_id]["parada_ordem"] is None
    assert depois[elegivel_id]["status"] == "ATRIBUIDA"
    assert depois[elegivel_id]["parada_ordem"] is not None


@pytest.mark.asyncio
async def test_reotimizar_preserva_entrega_concluida(
    client: AsyncClient,
) -> None:
    """Reotimização não reenvia nem reinicia entrega já concluída."""
    rota_id = await _seed_rota(
        client,
        [
            _entrega_payload("P001", -23.5505, -46.6333),
            _entrega_payload("P002", -23.5550, -46.6400),
        ],
    )
    first = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )
    assert first.status_code == HTTP_OK

    entregas = await _entregas_da_rota(client, rota_id)
    concluida_id = entregas[0]["id"]
    pendente_id = entregas[1]["id"]
    update = await client.put(
        f"{API}/entregas/{concluida_id}", json={"status": "ENTREGUE"}
    )
    assert update.status_code == HTTP_OK

    second = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )

    assert second.status_code == HTTP_OK
    parada_entrega_ids = {
        p["entrega_id"] for p in second.json()["paradas"] if p["entrega_id"]
    }
    assert parada_entrega_ids == {pendente_id}

    depois = {e["id"]: e for e in await _entregas_da_rota(client, rota_id)}
    assert depois[concluida_id]["status"] == "ENTREGUE"
    assert depois[pendente_id]["status"] == "ATRIBUIDA"
