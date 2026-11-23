"""Criação/leitura em banco gerado pelo Alembic (compatibilidade de enums)."""

import asyncio
from datetime import date, time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.models import (
    Deposito,
    Entrega,
    EntregaStatus,
    Parada,
    ParadaStatus,
    Rota,
    RotaStatus,
    Veiculo,
    VeiculoTipo,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _upgrade_head(database_url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", database_url)
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    command.upgrade(cfg, "head")


async def _roundtrip(database_url: str) -> None:
    engine = create_async_engine(database_url)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with maker() as session:
        deposito = Deposito(
            nome="CD", endereco="Rua 1", latitude=-23.5, longitude=-46.6
        )
        veiculo = Veiculo(placa="XYZ9A99", capacidade=10, tipo=VeiculoTipo.VAN)
        rota = Rota(
            nome="R1",
            data=date.today(),
            deposito=deposito,
            veiculo=veiculo,
            status=RotaStatus.EM_ANDAMENTO,
        )
        entrega = Entrega(
            pedido_id="P001",
            endereco="Rua A",
            latitude=-23.5,
            longitude=-46.6,
            demanda=2,
            status=EntregaStatus.EM_ROTA,
            rota=rota,
        )
        parada = Parada(
            rota=rota,
            entrega=entrega,
            ordem=1,
            endereco="Rua A",
            latitude=-23.5,
            longitude=-46.6,
            demanda=2,
            janela_inicio=time(9, 0),
            janela_fim=time(10, 0),
            status=ParadaStatus.CONCLUIDA,
        )
        session.add_all([deposito, veiculo, rota, entrega, parada])
        await session.commit()

        db_veiculo = (await session.execute(select(Veiculo))).scalar_one()
        assert db_veiculo.tipo == VeiculoTipo.VAN

        db_entrega = (await session.execute(select(Entrega))).scalar_one()
        assert db_entrega.status == EntregaStatus.EM_ROTA

        db_rota = (await session.execute(select(Rota))).scalar_one()
        assert db_rota.status == RotaStatus.EM_ANDAMENTO

        db_parada = (await session.execute(select(Parada))).scalar_one()
        assert db_parada.status == ParadaStatus.CONCLUIDA
        assert db_parada.janela_inicio == time(9, 0)

    await engine.dispose()


def test_alembic_upgrade_and_enum_roundtrip(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Banco criado via `alembic upgrade head` aceita os enums dos modelos."""
    database_url = f"sqlite+aiosqlite:///{(tmp_path / 'alembic.db').as_posix()}"
    _upgrade_head(database_url, monkeypatch)
    asyncio.run(_roundtrip(database_url))
