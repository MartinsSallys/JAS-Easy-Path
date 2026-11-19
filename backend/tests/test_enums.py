from datetime import date

import pytest

from app.models import (
    Entrega,
    EntregaStatus,
    Parada,
    ParadaStatus,
    Rota,
    RotaStatus,
    Veiculo,
    VeiculoTipo,
)
from app.schemas import (
    EntregaCreate,
    EntregaUpdate,
    ParadaResponse,
    RotaCreate,
    RotaUpdate,
    VeiculoCreate,
    VeiculoUpdate,
)


def test_veiculo_tipo_enum_values() -> None:
    """Test that VeiculoTipo enum has correct uppercase values."""
    assert VeiculoTipo.MOTO == "MOTO"
    assert VeiculoTipo.CARRO == "CARRO"
    assert VeiculoTipo.CAMINHAO == "CAMINHAO"
    assert VeiculoTipo.VAN == "VAN"


def test_entrega_status_enum_values() -> None:
    """Test that EntregaStatus enum has correct uppercase values."""
    assert EntregaStatus.PENDENTE == "PENDENTE"
    assert EntregaStatus.ATRIBUIDA == "ATRIBUIDA"
    assert EntregaStatus.EM_ROTA == "EM_ROTA"
    assert EntregaStatus.ENTREGUE == "ENTREGUE"
    assert EntregaStatus.FALHA == "FALHA"
    assert EntregaStatus.CANCELADA == "CANCELADA"


def test_rota_status_enum_values() -> None:
    """Test that RotaStatus enum has correct uppercase values."""
    assert RotaStatus.RASCUNHO == "RASCUNHO"
    assert RotaStatus.OTIMIZADA == "OTIMIZADA"
    assert RotaStatus.EM_ANDAMENTO == "EM_ANDAMENTO"
    assert RotaStatus.CONCLUIDA == "CONCLUIDA"
    assert RotaStatus.CANCELADA == "CANCELADA"


def test_parada_status_enum_values() -> None:
    """Test that ParadaStatus enum has correct uppercase values."""
    assert ParadaStatus.PENDENTE == "PENDENTE"
    assert ParadaStatus.EM_ANDAMENTO == "EM_ANDAMENTO"
    assert ParadaStatus.CONCLUIDA == "CONCLUIDA"
    assert ParadaStatus.FALHA == "FALHA"
    assert ParadaStatus.PULADA == "PULADA"


def test_schema_enum_serialization() -> None:
    """Test that schema enums serialize to uppercase values."""
    veiculo = VeiculoCreate(placa="ABC1234", capacidade=10, tipo=VeiculoTipo.CAMINHAO)
    assert veiculo.tipo == VeiculoTipo.CAMINHAO
    assert veiculo.model_dump()["tipo"] == "CAMINHAO"

    veiculo_update = VeiculoUpdate(tipo=VeiculoTipo.CARRO)
    assert veiculo_update.model_dump()["tipo"] == "CARRO"

    entrega = EntregaCreate(
        pedido_id="P001",
        endereco="Rua A, 123",
        latitude=-23.5,
        longitude=-46.6,
    )
    # EntregaCreate doesn't have status field (uses default in DB)
    assert "status" not in entrega.model_dump()

    entrega_update = EntregaUpdate(status=EntregaStatus.ENTREGUE)
    assert entrega_update.model_dump()["status"] == "ENTREGUE"

    rota = RotaCreate(
        nome="Rota 1",
        data=date.today(),
        deposito_id=1,
        veiculo_id=1,
    )
    # RotaCreate doesn't have status field (uses default in DB)
    assert "status" not in rota.model_dump()

    rota_update = RotaUpdate(status=RotaStatus.OTIMIZADA)
    assert rota_update.model_dump()["status"] == "OTIMIZADA"

    parada = ParadaResponse(
        id=1,
        rota_id=1,
        ordem=1,
        endereco="Rua A, 123",
        latitude=-23.5,
        longitude=-46.6,
        status=ParadaStatus.PENDENTE,
    )
    assert parada.status == ParadaStatus.PENDENTE
    assert parada.model_dump()["status"] == "PENDENTE"


def test_model_enum_defaults() -> None:
    """Test that model enums have correct defaults when set."""
    # SQLAlchemy defaults are applied at DB level (server_default)
    # Here we test that we can set the enum values correctly
    veiculo = Veiculo(placa="ABC1234", capacidade=10, tipo=VeiculoTipo.CAMINHAO)
    assert veiculo.tipo == VeiculoTipo.CAMINHAO

    entrega = Entrega(
        pedido_id="P001",
        endereco="Rua A, 123",
        latitude=-23.5,
        longitude=-46.6,
        status=EntregaStatus.PENDENTE,
    )
    assert entrega.status == EntregaStatus.PENDENTE

    rota = Rota(nome="Rota 1", data=date.today(), deposito_id=1, status=RotaStatus.RASCUNHO)
    assert rota.status == RotaStatus.RASCUNHO

    parada = Parada(
        rota_id=1,
        ordem=1,
        endereco="Rua A, 123",
        latitude=-23.5,
        longitude=-46.6,
        status=ParadaStatus.PENDENTE,
    )
    assert parada.status == ParadaStatus.PENDENTE


def test_enum_case_sensitivity() -> None:
    """Test that enum values are case-sensitive and uppercase."""
    # Verify that lowercase values are NOT valid
    with pytest.raises(ValueError):
        VeiculoTipo("caminhao")
    with pytest.raises(ValueError):
        EntregaStatus("pendente")
    with pytest.raises(ValueError):
        RotaStatus("rascunho")
    with pytest.raises(ValueError):
        ParadaStatus("pendente")

    # Uppercase values work
    assert VeiculoTipo("CAMINHAO") == VeiculoTipo.CAMINHAO
    assert EntregaStatus("PENDENTE") == EntregaStatus.PENDENTE
    assert RotaStatus("RASCUNHO") == RotaStatus.RASCUNHO
    assert ParadaStatus("PENDENTE") == ParadaStatus.PENDENTE