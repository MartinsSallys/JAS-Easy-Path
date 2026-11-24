"""Integração POST /rotas/{id}/otimizar com matriz determinística injetada.

Diferente de ``test_rotas_otimizar.py`` (que usa a matriz Haversine real), aqui
o provedor de matriz do adapter é substituído por tabelas fixas indexadas por
coordenada. Isso permite verificar de forma independente — sem depender da
heurística geográfica — a sequência escolhida pelo solver, os horários
propagados até o banco, a espera antes da janela, o retorno ao depósito e a
associação entre paradas e entregas. Nenhuma chamada externa é feita.
"""

from collections.abc import AsyncIterator
from datetime import date

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_session
from app.main import app
from app.models import Parada
from app.schemas import OptimizationLocation
from app.services.optimizer import RouteEngineAdapter

API = "/api/v1"
HTTP_OK = 200
HTTP_CREATED = 201
HTTP_BAD_REQUEST = 400
HTTP_NOT_FOUND = 404
HTTP_UNPROCESSABLE = 422

OPTIMIZE_TIME_LIMIT = 5
TIME_LIMIT_MINIMO = 5
TIME_LIMIT_ABAIXO_DO_MINIMO = 3

Coordenadas = tuple[float, float]

DEPOSITO_COORD: Coordenadas = (-23.5, -46.6)
LOCAL_A: Coordenadas = (-23.51, -46.61)
LOCAL_B: Coordenadas = (-23.52, -46.62)
LOCAL_C: Coordenadas = (-23.53, -46.63)
ORDEM_LOCAIS = [DEPOSITO_COORD, LOCAL_A, LOCAL_B, LOCAL_C]

# Duração em minutos; linhas e colunas seguem ORDEM_LOCAIS. Assimétrica de
# propósito para que D -> A -> B -> C -> D seja a única sequência ótima.
DURACAO_MIN = [
    [0, 10, 90, 25],
    [15, 0, 20, 35],
    [95, 25, 0, 50],
    [20, 40, 55, 0],
]

PARADAS_ESPERADAS = 5  # depósito + 3 entregas + depósito
CAPACIDADE_EXATA = 3  # 3 pedidos de 1 unidade = capacidade no limite
CAPACIDADE_INSUFICIENTE = 2
CAPACIDADE_FOLGADA = 100
TOTAL_ENTREGAS = 3
DISTANCIA_ESPERADA_KM = 10.0  # (10 + 20 + 50 + 20) min * 100 m/min
TEMPO_ESPERADO_MIN = 206  # 08:00 -> 11:26
METROS_POR_MINUTO = 100
SERVICE_TIME_MIN = 8
HORA_ABERTURA = "08:00:00"
HORA_FECHAMENTO = "18:00:00"

# Cronograma calculado à mão a partir de DURACAO_MIN, partindo às 08:00 e
# esperando a abertura da janela de B (10:00-11:00) quando a chegada é antes.
ESPERADO_CHEGADA_SAIDA = {
    "A": ("08:10:00", "08:18:00"),  # chega 08:10, atende 08:10-08:18
    "B": ("10:00:00", "10:08:00"),  # chegaria 08:38, espera até 10:00
    "C": ("10:58:00", "11:06:00"),  # chega 10:58, atende 10:58-11:06
}
RETORNO_ESPERADO = "11:26:00"


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
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_session, None)


class StubMatrixProvider:
    """Matrizes fixas indexadas por (latitude, longitude) do seed.

    O adapter monta as locations na ordem ``[depot, *entregas]``, mas a ordem
    das entregas vem do ORM; por isso o índice é resolvido pelas coordenadas,
    tornando a matriz independente da ordenação do banco.
    """

    def __init__(self, duracoes_min: list[list[int]], ordem: list[Coordenadas]) -> None:
        self._duracoes = duracoes_min
        self._indice = {coords: i for i, coords in enumerate(ordem)}

    def build(
        self, locations: list[OptimizationLocation]
    ) -> tuple[list[list[int]], list[list[int]]]:
        indices = [self._indice[(loc.latitude, loc.longitude)] for loc in locations]
        duracoes = [[self._duracoes[i][j] for j in indices] for i in indices]
        distancias = [[minutos * METROS_POR_MINUTO for minutos in linha] for linha in duracoes]
        return distancias, duracoes


def _instalar_matriz(monkeypatch: pytest.MonkeyPatch, provider: StubMatrixProvider) -> None:
    adapter = RouteEngineAdapter(
        matrix_provider=provider,
        time_limit_seconds=OPTIMIZE_TIME_LIMIT,
    )
    monkeypatch.setattr("app.api.rotas.get_optimizer", lambda: adapter)


def _entrega(pedido: str, coords: Coordenadas, **extra: object) -> dict:
    payload = {
        "pedido_id": pedido,
        "endereco": f"Rua {pedido}, 10",
        "latitude": coords[0],
        "longitude": coords[1],
        "demanda": 1,
    }
    payload.update(extra)
    return payload


async def _seed(
    client: AsyncClient,
    entregas: list[dict],
    *,
    capacidade: int = CAPACIDADE_EXATA,
    placa: str = "ABC1234",
    com_veiculo: bool = True,
) -> dict:
    deposito = await client.post(
        f"{API}/depositos",
        json={
            "nome": "CD Central",
            "endereco": "Av. Depot, 100",
            "latitude": DEPOSITO_COORD[0],
            "longitude": DEPOSITO_COORD[1],
        },
    )
    assert deposito.status_code == HTTP_CREATED

    veiculo_id = None
    if com_veiculo:
        veiculo = await client.post(
            f"{API}/veiculos",
            json={
                "placa": placa,
                "capacidade": capacidade,
                "tipo": "CAMINHAO",
            },
        )
        assert veiculo.status_code == HTTP_CREATED
        veiculo_id = veiculo.json()["id"]

    entrega_ids = {}
    for payload in entregas:
        entrega = await client.post(f"{API}/entregas", json=payload)
        assert entrega.status_code == HTTP_CREATED
        entrega_ids[payload["pedido_id"]] = entrega.json()["id"]

    rota = await client.post(
        f"{API}/rotas",
        json={
            "nome": "Rota Teste",
            "data": date.today().isoformat(),
            "deposito_id": deposito.json()["id"],
            "veiculo_id": veiculo_id,
            "entrega_ids": list(entrega_ids.values()),
        },
    )
    assert rota.status_code == HTTP_CREATED
    return {
        "rota_id": rota.json()["id"],
        "deposito_id": deposito.json()["id"],
        "veiculo_id": veiculo_id,
        "entrega_ids": entrega_ids,
    }


async def _otimizar(client: AsyncClient, rota_id: int) -> httpx.Response:
    return await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )


async def _entregas_da_rota(client: AsyncClient, rota_id: int) -> list[dict]:
    response = await client.get(f"{API}/entregas", params={"rota_id": rota_id})
    assert response.status_code == HTTP_OK
    return response.json()


def _cenario_padrao() -> list[dict]:
    return [
        _entrega("A", LOCAL_A),
        _entrega("B", LOCAL_B, janela_inicio="10:00", janela_fim="11:00"),
        _entrega("C", LOCAL_C),
    ]


@pytest.mark.asyncio
async def test_otimizar_sequencia_horarios_espera_e_ids(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Solver real + matriz fixa: sequência, cronograma, espera e IDs batendo
    com a conta feita à mão a partir da matriz."""
    _instalar_matriz(monkeypatch, StubMatrixProvider(DURACAO_MIN, ORDEM_LOCAIS))
    seed = await _seed(client, _cenario_padrao())

    response = await _otimizar(client, seed["rota_id"])

    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["status"] == "OTIMIZADA"
    assert body["veiculo_id"] == seed["veiculo_id"]
    assert body["distancia_total_km"] == DISTANCIA_ESPERADA_KM
    assert body["tempo_total_min"] == TEMPO_ESPERADO_MIN
    assert body["otimizada_em"] is not None

    paradas = body["paradas"]
    assert len(paradas) == PARADAS_ESPERADAS
    assert [p["ordem"] for p in paradas] == list(range(PARADAS_ESPERADAS))

    ids = seed["entrega_ids"]
    assert [p["entrega_id"] for p in paradas] == [
        None,
        ids["A"],
        ids["B"],
        ids["C"],
        None,
    ]

    # Saída e retorno no depósito, dentro do expediente fixo 08:00-18:00.
    assert paradas[0]["deposito_id"] == seed["deposito_id"]
    assert paradas[-1]["deposito_id"] == seed["deposito_id"]
    assert paradas[0]["chegada_prevista"] == HORA_ABERTURA
    assert paradas[-1]["chegada_prevista"] == RETORNO_ESPERADO
    assert paradas[-1]["chegada_prevista"] <= HORA_FECHAMENTO
    assert paradas[0]["demanda"] == 0
    assert paradas[-1]["demanda"] == 0

    entregas_db = {e["id"]: e for e in await _entregas_da_rota(client, seed["rota_id"])}
    for parada in paradas[1:-1]:
        pedido = next(p for p, eid in ids.items() if eid == parada["entrega_id"])
        chegada, saida = ESPERADO_CHEGADA_SAIDA[pedido]
        assert parada["chegada_prevista"] == chegada
        assert parada["saida_prevista"] == saida
        assert parada["tempo_servico_min"] == SERVICE_TIME_MIN
        assert parada["status"] == "PENDENTE"

        # Associação de IDs: parada aponta para a entrega certa e carrega os
        # mesmos endereço, coordenadas, demanda e janela do cadastro.
        entrega = entregas_db[parada["entrega_id"]]
        assert parada["endereco"] == entrega["endereco"]
        assert parada["latitude"] == entrega["latitude"]
        assert parada["longitude"] == entrega["longitude"]
        assert parada["demanda"] == entrega["demanda"]
        assert parada["janela_inicio"] == entrega["janela_inicio"]
        assert parada["janela_fim"] == entrega["janela_fim"]

        assert entrega["status"] == "ATRIBUIDA"
        assert entrega["parada_ordem"] == parada["ordem"]

    # Espera: a chegada física em B seria 08:38; a parada registra o início do
    # atendimento na abertura da janela, não antes dela.
    parada_b = next(p for p in paradas if p["entrega_id"] == ids["B"])
    assert parada_b["chegada_prevista"] == "10:00:00"
    assert parada_b["janela_inicio"].startswith("10:00")
    assert parada_b["janela_fim"].startswith("11:00")

    # GET /rotas/{id} devolve as mesmas paradas persistidas pelo POST.
    detalhe = await client.get(f"{API}/rotas/{seed['rota_id']}")
    assert detalhe.status_code == HTTP_OK
    assert [p["id"] for p in detalhe.json()["paradas"]] == [p["id"] for p in paradas]


@pytest.mark.asyncio
async def test_reotimizar_substitui_paradas_sem_duplicar(
    client: AsyncClient,
    session_maker: async_sessionmaker,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segunda otimização apaga as paradas antigas e grava um plano novo."""
    _instalar_matriz(monkeypatch, StubMatrixProvider(DURACAO_MIN, ORDEM_LOCAIS))
    seed = await _seed(client, _cenario_padrao())

    primeira = await _otimizar(client, seed["rota_id"])
    assert primeira.status_code == HTTP_OK

    segunda = await _otimizar(client, seed["rota_id"])
    assert segunda.status_code == HTTP_OK
    paradas_segunda = segunda.json()["paradas"]

    # Sem duplicatas na resposta e sem sobras no banco: a contagem total de
    # paradas da rota continua sendo a de um único plano.
    assert len(paradas_segunda) == PARADAS_ESPERADAS
    async with session_maker() as session:
        total = await session.execute(
            select(func.count()).select_from(Parada).where(Parada.rota_id == seed["rota_id"])
        )
        assert total.scalar_one() == PARADAS_ESPERADAS

    ids = seed["entrega_ids"]
    assert [p["entrega_id"] for p in paradas_segunda] == [
        None,
        ids["A"],
        ids["B"],
        ids["C"],
        None,
    ]
    for entrega in await _entregas_da_rota(client, seed["rota_id"]):
        assert entrega["parada_ordem"] is not None
        assert entrega["status"] == "ATRIBUIDA"


@pytest.mark.asyncio
async def test_otimizar_capacidade_insuficiente_retorna_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Demanda total acima da capacidade do veículo é inviável: 422 e nada
    persistido como otimizado."""
    _instalar_matriz(monkeypatch, StubMatrixProvider(DURACAO_MIN, ORDEM_LOCAIS))
    seed = await _seed(client, _cenario_padrao(), capacidade=CAPACIDADE_INSUFICIENTE)

    response = await _otimizar(client, seed["rota_id"])

    assert response.status_code == HTTP_UNPROCESSABLE
    assert "capacidade" in response.json()["detail"].lower()

    rota = await client.get(f"{API}/rotas/{seed['rota_id']}")
    assert rota.json()["status"] == "RASCUNHO"
    assert rota.json()["paradas"] == []
    for entrega in await _entregas_da_rota(client, seed["rota_id"]):
        assert entrega["status"] == "ATRIBUIDA"
        assert entrega["parada_ordem"] is None


@pytest.mark.asyncio
async def test_otimizar_usa_apenas_o_veiculo_da_rota(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Outros veículos cadastrados não entram na otimização: com o veículo
    pequeno a rota é inviável; ao associar o grande, ela passa."""
    _instalar_matriz(monkeypatch, StubMatrixProvider(DURACAO_MIN, ORDEM_LOCAIS))
    seed = await _seed(client, _cenario_padrao(), capacidade=CAPACIDADE_INSUFICIENTE)
    veiculo_grande = await client.post(
        f"{API}/veiculos",
        json={
            "placa": "XYZ9876",
            "capacidade": CAPACIDADE_FOLGADA,
            "tipo": "CAMINHAO",
        },
    )
    assert veiculo_grande.status_code == HTTP_CREATED

    # A frota tem veículo com capacidade de sobra, mas a rota está presa ao
    # pequeno: a operação falha mesmo assim.
    response = await _otimizar(client, seed["rota_id"])
    assert response.status_code == HTTP_UNPROCESSABLE

    # Trocando o veículo associado à rota, o mesmo conjunto de entregas passa.
    update = await client.put(
        f"{API}/rotas/{seed['rota_id']}",
        json={"veiculo_id": veiculo_grande.json()["id"]},
    )
    assert update.status_code == HTTP_OK

    response = await _otimizar(client, seed["rota_id"])
    assert response.status_code == HTTP_OK
    body = response.json()
    assert body["veiculo_id"] == veiculo_grande.json()["id"]
    assert len(body["paradas"]) == PARADAS_ESPERADAS


@pytest.mark.asyncio
async def test_otimizar_janela_fora_do_expediente_retorna_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Janela 19:00-20:00 não se sobrepõe ao expediente 08:00-18:00: 422."""
    _instalar_matriz(monkeypatch, StubMatrixProvider(DURACAO_MIN, ORDEM_LOCAIS))
    seed = await _seed(
        client,
        [
            _entrega(
                "FORA",
                LOCAL_A,
                janela_inicio="19:00",
                janela_fim="20:00",
            )
        ],
    )

    response = await _otimizar(client, seed["rota_id"])

    assert response.status_code == HTTP_UNPROCESSABLE
    assert "expediente" in response.json()["detail"].lower()

    rota = await client.get(f"{API}/rotas/{seed['rota_id']}")
    assert rota.json()["status"] == "RASCUNHO"
    assert rota.json()["paradas"] == []


@pytest.mark.asyncio
async def test_otimizar_sem_retorno_no_expediente_retorna_422(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entrega a 700 min do depósito não cabe no expediente: 422, não plano
    parcial."""
    _instalar_matriz(
        monkeypatch,
        StubMatrixProvider([[0, 700], [10, 0]], [DEPOSITO_COORD, LOCAL_A]),
    )
    seed = await _seed(client, [_entrega("LONGE", LOCAL_A)])

    response = await _otimizar(client, seed["rota_id"])

    assert response.status_code == HTTP_UNPROCESSABLE
    assert response.json()["detail"] == (
    "Não foi possível encontrar solução viável com as restrições atuais"
)

@pytest.mark.asyncio
async def test_otimizar_rota_inexistente_retorna_404(
    client: AsyncClient,
) -> None:
    response = await _otimizar(client, rota_id=999999)

    assert response.status_code == HTTP_NOT_FOUND


@pytest.mark.asyncio
async def test_otimizar_rota_sem_veiculo_retorna_400(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, [_entrega("A", LOCAL_A)], com_veiculo=False)

    response = await _otimizar(client, seed["rota_id"])

    assert response.status_code == HTTP_BAD_REQUEST
    assert "veículo" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_otimizar_rota_sem_entregas_retorna_400(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, [])

    response = await _otimizar(client, seed["rota_id"])

    assert response.status_code == HTTP_BAD_REQUEST
    assert "entregas" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_otimizar_time_limit_abaixo_do_minimo_retorna_422(
    client: AsyncClient,
) -> None:
    seed = await _seed(client, [_entrega("A", LOCAL_A)])

    response = await client.post(
        f"{API}/rotas/{seed['rota_id']}/otimizar",
        json={"time_limit_seconds": TIME_LIMIT_ABAIXO_DO_MINIMO},
    )

    assert response.status_code == HTTP_UNPROCESSABLE
