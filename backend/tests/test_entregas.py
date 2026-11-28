"""Validação de janela de entrega no cadastro e na atualização de entregas."""

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
HTTP_NOT_FOUND = 404
HTTP_CONFLICT = 409
HTTP_UNPROCESSABLE = 422
OPTIMIZE_TIME_LIMIT = 5


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


def _entrega_payload(pedido_id: str = "P001", **extra: object) -> dict:
    return {
        "pedido_id": pedido_id,
        "endereco": f"Rua {pedido_id}, 10",
        "latitude": -23.5505,
        "longitude": -46.6333,
        "demanda": 3,
        **extra,
    }


async def _create_entrega(client: AsyncClient, **extra: object) -> dict:
    response = await client.post(
        f"{API}/entregas", json=_entrega_payload(**extra)
    )
    assert response.status_code == HTTP_CREATED
    return response.json()


async def _vincular_entrega_a_rota(
    client: AsyncClient, entrega_id: int
) -> int:
    """Cria depósito, veículo e rota contendo a entrega; devolve o rota_id."""
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

    rota = await client.post(
        f"{API}/rotas",
        json={
            "nome": "Rota Teste",
            "data": date.today().isoformat(),
            "deposito_id": deposito.json()["id"],
            "veiculo_id": veiculo.json()["id"],
            "entrega_ids": [entrega_id],
        },
    )
    assert rota.status_code == HTTP_CREATED
    return rota.json()["id"]


@pytest.mark.asyncio
async def test_criar_entrega_sem_janela(client: AsyncClient) -> None:
    """Janela totalmente ausente é válida: a entrega herda o expediente."""
    response = await client.post(f"{API}/entregas", json=_entrega_payload())

    assert response.status_code == HTTP_CREATED
    assert response.json()["janela_inicio"] is None
    assert response.json()["janela_fim"] is None


@pytest.mark.asyncio
async def test_criar_entrega_janela_completa(client: AsyncClient) -> None:
    response = await client.post(
        f"{API}/entregas",
        json=_entrega_payload(janela_inicio="09:00", janela_fim="12:00"),
    )

    assert response.status_code == HTTP_CREATED
    assert response.json()["janela_inicio"].startswith("09:00")
    assert response.json()["janela_fim"].startswith("12:00")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "janela",
    [{"janela_inicio": "17:00"}, {"janela_fim": "12:00"}],
    ids=["inicio_isolado", "fim_isolado"],
)
async def test_criar_entrega_janela_incompleta_rejeita(
    client: AsyncClient, janela: dict
) -> None:
    """Início ou fim isolado é rejeitado no cadastro."""
    response = await client.post(
        f"{API}/entregas", json=_entrega_payload(**janela)
    )

    assert response.status_code == HTTP_UNPROCESSABLE


@pytest.mark.asyncio
async def test_atualizar_janela_existente_aceita_update_parcial(
    client: AsyncClient,
) -> None:
    """PUT com um limite só é válido quando o outro já existe no registro."""
    entrega = await _create_entrega(
        client, janela_inicio="09:00", janela_fim="12:00"
    )

    response = await client.put(
        f"{API}/entregas/{entrega['id']}", json={"janela_inicio": "10:00"}
    )

    assert response.status_code == HTTP_OK
    assert response.json()["janela_inicio"].startswith("10:00")
    assert response.json()["janela_fim"].startswith("12:00")


@pytest.mark.asyncio
async def test_atualizar_sem_janela_para_incompleta_rejeita(
    client: AsyncClient,
) -> None:
    """PUT que deixaria o registro com janela pela metade é rejeitado."""
    entrega = await _create_entrega(client)

    response = await client.put(
        f"{API}/entregas/{entrega['id']}", json={"janela_inicio": "17:00"}
    )

    assert response.status_code == HTTP_UNPROCESSABLE

    persisted = await client.get(f"{API}/entregas/{entrega['id']}")
    assert persisted.json()["janela_inicio"] is None
    assert persisted.json()["janela_fim"] is None


@pytest.mark.asyncio
async def test_limpar_apenas_um_limite_da_janela_rejeita(
    client: AsyncClient,
) -> None:
    """Esvaziar só um lado da janela existente também é rejeitado."""
    entrega = await _create_entrega(
        client, janela_inicio="09:00", janela_fim="12:00"
    )

    response = await client.put(
        f"{API}/entregas/{entrega['id']}", json={"janela_fim": None}
    )

    assert response.status_code == HTTP_UNPROCESSABLE


@pytest.mark.asyncio
async def test_limpar_janela_inteira(client: AsyncClient) -> None:
    """Esvaziar os dois limites remove a janela e é aceito."""
    entrega = await _create_entrega(
        client, janela_inicio="09:00", janela_fim="12:00"
    )

    response = await client.put(
        f"{API}/entregas/{entrega['id']}",
        json={"janela_inicio": None, "janela_fim": None},
    )

    assert response.status_code == HTTP_OK
    assert response.json()["janela_inicio"] is None
    assert response.json()["janela_fim"] is None


@pytest.mark.asyncio
async def test_excluir_entrega_pendente_marca_cancelada(
    client: AsyncClient,
) -> None:
    """Soft delete: a entrega permanece no banco com status CANCELADA."""
    entrega = await _create_entrega(client)

    response = await client.delete(f"{API}/entregas/{entrega['id']}")

    assert response.status_code == HTTP_NO_CONTENT
    persisted = await client.get(f"{API}/entregas/{entrega['id']}")
    assert persisted.json()["status"] == "CANCELADA"


@pytest.mark.asyncio
async def test_excluir_entrega_inexistente_retorna_404(
    client: AsyncClient,
) -> None:
    response = await client.delete(f"{API}/entregas/999")

    assert response.status_code == HTTP_NOT_FOUND


@pytest.mark.asyncio
async def test_excluir_entrega_vinculada_remove_parada(
    client: AsyncClient,
) -> None:
    """Cancelar entrega de rota otimizada remove a parada na hora: sem isso
    o plano continuaria exibindo uma parada de entrega cancelada."""
    entrega = await _create_entrega(client)
    rota_id = await _vincular_entrega_a_rota(client, entrega["id"])

    otimizar = await client.post(
        f"{API}/rotas/{rota_id}/otimizar",
        json={"time_limit_seconds": OPTIMIZE_TIME_LIMIT},
    )
    assert otimizar.status_code == HTTP_OK
    assert any(
        p["entrega_id"] == entrega["id"] for p in otimizar.json()["paradas"]
    )

    response = await client.delete(f"{API}/entregas/{entrega['id']}")

    assert response.status_code == HTTP_NO_CONTENT

    persisted = await client.get(f"{API}/entregas/{entrega['id']}")
    assert persisted.json()["status"] == "CANCELADA"
    # rota_id é preservado como histórico; só o vínculo com a parada é limpo
    assert persisted.json()["rota_id"] == rota_id
    assert persisted.json()["parada_ordem"] is None

    rota = await client.get(f"{API}/rotas/{rota_id}")
    assert rota.status_code == HTTP_OK
    assert all(
        p["entrega_id"] != entrega["id"] for p in rota.json()["paradas"]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["EM_ROTA", "ENTREGUE"])
async def test_excluir_entrega_em_operacao_rejeita(
    client: AsyncClient, status: str
) -> None:
    """Entrega em andamento ou concluída é histórico: não pode ser excluída."""
    entrega = await _create_entrega(client)
    update = await client.put(
        f"{API}/entregas/{entrega['id']}", json={"status": status}
    )
    assert update.status_code == HTTP_OK

    response = await client.delete(f"{API}/entregas/{entrega['id']}")

    assert response.status_code == HTTP_CONFLICT
    persisted = await client.get(f"{API}/entregas/{entrega['id']}")
    assert persisted.json()["status"] == status


@pytest.mark.asyncio
async def test_excluir_entrega_com_falha_cancela_preservando_historico(
    client: AsyncClient,
) -> None:
    """Issue #32: FALHA pode ser cancelada — o motivo em `observacoes` é
    preservado e `status_anterior` registra a transição FALHA -> CANCELADA."""
    observacoes_falha = 'Cliente ausente\n[JAS_META]:{"r": "customer_absent"}'
    entrega = await _create_entrega(client)
    update = await client.put(
        f"{API}/entregas/{entrega['id']}",
        json={"status": "FALHA", "observacoes": observacoes_falha},
    )
    assert update.status_code == HTTP_OK

    response = await client.delete(f"{API}/entregas/{entrega['id']}")

    assert response.status_code == HTTP_NO_CONTENT
    persisted = await client.get(f"{API}/entregas/{entrega['id']}")
    assert persisted.json()["status"] == "CANCELADA"
    assert persisted.json()["status_anterior"] == "FALHA"
    assert persisted.json()["observacoes"] == observacoes_falha


@pytest.mark.asyncio
async def test_excluir_entrega_pendente_registra_status_anterior(
    client: AsyncClient,
) -> None:
    """Cancelada antes de sair: status_anterior marca o status pré-cancelamento."""
    entrega = await _create_entrega(client)

    response = await client.delete(f"{API}/entregas/{entrega['id']}")

    assert response.status_code == HTTP_NO_CONTENT
    persisted = await client.get(f"{API}/entregas/{entrega['id']}")
    assert persisted.json()["status"] == "CANCELADA"
    assert persisted.json()["status_anterior"] == "PENDENTE"


@pytest.mark.asyncio
async def test_atualizar_status_registra_status_anterior(
    client: AsyncClient,
) -> None:
    """Toda mudança de status via PUT preserva o status anterior."""
    entrega = await _create_entrega(client)

    update = await client.put(
        f"{API}/entregas/{entrega['id']}", json={"status": "FALHA"}
    )

    assert update.status_code == HTTP_OK
    assert update.json()["status_anterior"] == "PENDENTE"
