"""Validação de janela de entrega no cadastro e na atualização de entregas."""

from collections.abc import AsyncIterator

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
