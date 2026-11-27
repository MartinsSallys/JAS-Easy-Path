"""Fluxo completo do dia com dados fictícios (issue #11).

Cenário de 15 entregas cobrindo o caminho do MVP de ponta a ponta:
geocodificação (incluindo endereço não localizado e sua correção),
cadastro válido e inválido, geração da rota pelo solver real com matriz
Haversine determinística, registro das baixas do entregador e os dados que
alimentam o resumo diário (contagens por status e totais da rota).

Nenhuma chamada externa é feita: o geocoder é substituído por um stub e a
matriz usada na otimização é a de linha reta, já determinística.
"""

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
from app.schemas import GeocodeResponse, GeocodeResult

API = "/api/v1"
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_UNPROCESSABLE = 422

OPTIMIZE_TIME_LIMIT = 10
TOTAL_ENTREGAS = 15
TOTAL_ENTREGUES = 12
TOTAL_FALHAS = 2
# 15 entregas - 12 concluídas - 2 com falha = 1 ainda em andamento
TOTAL_EM_ROTA = TOTAL_ENTREGAS - TOTAL_ENTREGUES - TOTAL_FALHAS
PARADAS_ESPERADAS = TOTAL_ENTREGAS + 2  # depósito na saída e no retorno

DEPOSITO_COORD = (-23.5505, -46.6333)
ENDERECO_NAO_LOCALIZADO = "Rua Inexistente do Teste, 99999"


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


class StubGeocoder:
    """Geocoder fictício: resolve qualquer endereço, exceto o "não localizado".

    Devolve coordenadas fixas perto do depósito, suficiente para exercitar o
    contrato ``/geocoding/forward`` e ``/geocoding/batch`` sem rede.
    """

    async def geocode(
        self, endereco: str, country_code: str = "br"
    ) -> GeocodeResponse:
        if "inexistente" in endereco.lower():
            return GeocodeResponse(results=[], ambiguous=False)
        return GeocodeResponse(
            results=[
                GeocodeResult(
                    latitude=DEPOSITO_COORD[0] - 0.01,
                    longitude=DEPOSITO_COORD[1] - 0.01,
                    display_name=f"{endereco} — São Paulo, SP",
                    confidence=0.9,
                    address_components={"city": "São Paulo", "state": "SP"},
                )
            ],
            ambiguous=False,
        )

    async def batch_geocode(
        self, enderecos: list[str], country_code: str = "br"
    ) -> list[GeocodeResponse]:
        return [await self.geocode(e, country_code) for e in enderecos]


def _instalar_geocoder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.api.geocoding.geocoder", StubGeocoder())


def _entrega(idx: int, **extra: object) -> dict:
    """Entrega fictícia válida espalhada numa grade perto do depósito."""
    payload = {
        "pedido_id": f"P{idx:03d}",
        "endereco": f"Rua Fictícia {idx}, {100 + idx} - São Paulo",
        "latitude": DEPOSITO_COORD[0] + (idx % 5) * 0.004 - 0.008,
        "longitude": DEPOSITO_COORD[1] + (idx % 3) * 0.004 - 0.004,
        "demanda": 1,
    }
    # A cada 5 entregas, uma janela de entrega dentro do expediente 08:00-18:00.
    if idx % 5 == 0:
        payload["janela_inicio"] = "09:00"
        payload["janela_fim"] = "12:00"
    payload.update(extra)
    return payload


def _cenario() -> list[dict]:
    return [_entrega(i) for i in range(1, TOTAL_ENTREGAS + 1)]


async def _seed_rota(client: AsyncClient, entregas: list[dict]) -> dict:
    """Cadastra depósito, veículo e as entregas em batch; cria a rota do dia."""
    deposito = await client.post(
        f"{API}/depositos",
        json={
            "nome": "CD Fictício",
            "endereco": "Av. do Teste, 1000",
            "latitude": DEPOSITO_COORD[0],
            "longitude": DEPOSITO_COORD[1],
        },
    )
    assert deposito.status_code == HTTP_CREATED

    veiculo = await client.post(
        f"{API}/veiculos",
        json={"placa": "FIC1234", "capacidade": 30, "tipo": "VAN"},
    )
    assert veiculo.status_code == HTTP_CREATED

    batch = await client.post(
        f"{API}/entregas/batch", json={"entregas": entregas}
    )
    assert batch.status_code == HTTP_CREATED
    assert len(batch.json()) == len(entregas)
    entrega_ids = [e["id"] for e in batch.json()]

    rota = await client.post(
        f"{API}/rotas",
        json={
            "nome": "Rota do Dia (fictícia)",
            "data": date.today().isoformat(),
            "deposito_id": deposito.json()["id"],
            "veiculo_id": veiculo.json()["id"],
            "entrega_ids": entrega_ids,
        },
    )
    assert rota.status_code == HTTP_CREATED
    return {"rota_id": rota.json()["id"], "entrega_ids": entrega_ids}


@pytest.mark.asyncio
async def test_geocoding_identifica_endereco_nao_localizado_e_permite_correcao(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Endereço sem resultado volta vazio (o frontend sinaliza a linha);
    corrigido, ele geocodifica normalmente."""
    _instalar_geocoder(monkeypatch)

    nao_localizado = await client.post(
        f"{API}/geocoding/forward",
        json={"endereco": ENDERECO_NAO_LOCALIZADO, "country_code": "br"},
    )
    assert nao_localizado.status_code == HTTP_OK
    assert nao_localizado.json()["results"] == []

    corrigido = await client.post(
        f"{API}/geocoding/forward",
        json={"endereco": "Rua Fictícia 1, 101 - São Paulo", "country_code": "br"},
    )
    assert corrigido.status_code == HTTP_OK
    resultados = corrigido.json()["results"]
    assert len(resultados) == 1
    assert resultados[0]["latitude"] == pytest.approx(DEPOSITO_COORD[0] - 0.01)

    # Batch: uma linha inválida não derruba as válidas — cada posição mantém
    # sua própria resposta, como o createMany do frontend espera.
    batch = await client.post(
        f"{API}/geocoding/batch",
        json={
            "enderecos": [
                "Rua Fictícia 2, 102 - São Paulo",
                ENDERECO_NAO_LOCALIZADO,
                "Rua Fictícia 3, 103 - São Paulo",
            ]
        },
    )
    assert batch.status_code == HTTP_OK
    respostas = batch.json()
    assert len(respostas) == 3
    assert len(respostas[0]["results"]) == 1
    assert respostas[1]["results"] == []
    assert len(respostas[2]["results"]) == 1


@pytest.mark.asyncio
async def test_cadastro_invalido_e_rejeitado_e_correcao_e_aceita(
    client: AsyncClient,
) -> None:
    """Payload sem campo obrigatório é rejeitado; corrigido, cadastra."""
    invalido = await client.post(
        f"{API}/entregas",
        json={
            "endereco": "Rua Fictícia, 10",
            "latitude": DEPOSITO_COORD[0],
            "longitude": DEPOSITO_COORD[1],
        },
    )
    assert invalido.status_code == HTTP_UNPROCESSABLE

    corrigido = await client.post(
        f"{API}/entregas",
        json={
            "pedido_id": "P-CORRIGIDO",
            "endereco": "Rua Fictícia, 10",
            "latitude": DEPOSITO_COORD[0],
            "longitude": DEPOSITO_COORD[1],
        },
    )
    assert corrigido.status_code == HTTP_CREATED
    assert corrigido.json()["status"] == "PENDENTE"


@pytest.mark.asyncio
async def test_fluxo_completo_do_dia_cadastro_rota_baixas_e_resumo(
    client: AsyncClient,
) -> None:
    """Cadastro -> otimização -> baixas -> resumo, com 15 entregas fictícias."""
    seed = await _seed_rota(client, _cenario())
    entrega_ids = seed["entrega_ids"]

    # Geração da rota: solver real + matriz Haversine (determinística).
    otimizar = await client.post(
        f"{API}/rotas/{seed['rota_id']}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )
    assert otimizar.status_code == HTTP_OK
    rota = otimizar.json()
    assert rota["status"] == "OTIMIZADA"
    assert len(rota["paradas"]) == PARADAS_ESPERADAS
    assert rota["paradas"][0]["deposito_id"] is not None
    assert rota["paradas"][-1]["deposito_id"] is not None

    paradas_entrega = [p for p in rota["paradas"] if p["entrega_id"] is not None]
    assert {p["entrega_id"] for p in paradas_entrega} == set(entrega_ids)

    # Registro das baixas do entregador: 12 concluídas, 2 com falha e a
    # última segue em andamento (EM_ROTA).
    for entrega_id in entrega_ids[:TOTAL_ENTREGUES]:
        baixa = await client.put(
            f"{API}/entregas/{entrega_id}", json={"status": "ENTREGUE"}
        )
        assert baixa.status_code == HTTP_OK

    for entrega_id in entrega_ids[TOTAL_ENTREGUES:-1]:
        baixa = await client.put(
            f"{API}/entregas/{entrega_id}", json={"status": "FALHA"}
        )
        assert baixa.status_code == HTTP_OK

    baixa = await client.put(
        f"{API}/entregas/{entrega_ids[-1]}", json={"status": "EM_ROTA"}
    )
    assert baixa.status_code == HTTP_OK

    # Resumo diário: o dashboard consome GET /entregas e os totais da rota.
    entregas = await client.get(f"{API}/entregas", params={"limit": 500})
    assert entregas.status_code == HTTP_OK
    por_status: dict[str, int] = {}
    for e in entregas.json():
        por_status[e["status"]] = por_status.get(e["status"], 0) + 1

    assert por_status == {
        "ENTREGUE": TOTAL_ENTREGUES,
        "FALHA": TOTAL_FALHAS,
        "EM_ROTA": TOTAL_EM_ROTA,
    }

    pendencias = await client.get(
        f"{API}/entregas", params={"status": "FALHA"}
    )
    assert pendencias.status_code == HTTP_OK
    assert {e["id"] for e in pendencias.json()} == set(
        entrega_ids[TOTAL_ENTREGUES:-1]
    )

    rota_final = await client.get(f"{API}/rotas/{seed['rota_id']}")
    assert rota_final.status_code == HTTP_OK
    assert rota_final.json()["distancia_total_km"] > 0
    assert rota_final.json()["tempo_total_min"] > 0
