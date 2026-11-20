import enum
from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    func,
)
from sqlalchemy import (
    Enum as SQLEnum,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EntregaStatus(enum.StrEnum):
    PENDENTE = "PENDENTE"
    ATRIBUIDA = "ATRIBUIDA"
    EM_ROTA = "EM_ROTA"
    ENTREGUE = "ENTREGUE"
    FALHA = "FALHA"
    CANCELADA = "CANCELADA"


class VeiculoTipo(enum.StrEnum):
    MOTO = "MOTO"
    CARRO = "CARRO"
    CAMINHAO = "CAMINHAO"
    VAN = "VAN"


class RotaStatus(enum.StrEnum):
    RASCUNHO = "RASCUNHO"
    OTIMIZADA = "OTIMIZADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


class ParadaStatus(enum.StrEnum):
    PENDENTE = "PENDENTE"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    FALHA = "FALHA"
    PULADA = "PULADA"


class Deposito(Base):
    __tablename__ = "depositos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    endereco: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    rotas: Mapped[list["Rota"]] = relationship(back_populates="deposito")


class Veiculo(Base):
    __tablename__ = "veiculos"

    id: Mapped[int] = mapped_column(primary_key=True)
    placa: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    capacidade: Mapped[int] = mapped_column(Integer, nullable=False)
    tipo: Mapped[VeiculoTipo] = mapped_column(SQLEnum(VeiculoTipo), default=VeiculoTipo.CAMINHAO)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    rotas: Mapped[list["Rota"]] = relationship(back_populates="veiculo")


class Entrega(Base):
    __tablename__ = "entregas"

    id: Mapped[int] = mapped_column(primary_key=True)
    pedido_id: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    endereco: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    demanda: Mapped[int] = mapped_column(Integer, default=1)
    janela_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    janela_fim: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[EntregaStatus] = mapped_column(
        SQLEnum(EntregaStatus), default=EntregaStatus.PENDENTE, index=True
    )
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    rota_id: Mapped[int | None] = mapped_column(ForeignKey("rotas.id"), nullable=True, index=True)
    parada_ordem: Mapped[int | None] = mapped_column(Integer, nullable=True)

    rota: Mapped[Optional["Rota"]] = relationship(back_populates="entregas")
    parada: Mapped[Optional["Parada"]] = relationship(back_populates="entrega", uselist=False)


class Rota(Base):
    __tablename__ = "rotas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    deposito_id: Mapped[int] = mapped_column(ForeignKey("depositos.id"), nullable=False)
    veiculo_id: Mapped[int | None] = mapped_column(ForeignKey("veiculos.id"), nullable=True)
    status: Mapped[RotaStatus] = mapped_column(
        SQLEnum(RotaStatus), default=RotaStatus.RASCUNHO, index=True
    )
    distancia_total_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    tempo_total_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())
    otimizada_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    deposito: Mapped[Deposito] = relationship(back_populates="rotas")
    veiculo: Mapped[Veiculo | None] = relationship(back_populates="rotas")
    entregas: Mapped[list[Entrega]] = relationship(back_populates="rota")
    paradas: Mapped[list["Parada"]] = relationship(
        back_populates="rota", order_by="Parada.ordem", cascade="all, delete-orphan"
    )


class Parada(Base):
    __tablename__ = "paradas"

    id: Mapped[int] = mapped_column(primary_key=True)
    rota_id: Mapped[int] = mapped_column(
        ForeignKey("rotas.id"), nullable=False, index=True
    )
    entrega_id: Mapped[int | None] = mapped_column(
        ForeignKey("entregas.id"), nullable=True, index=True
    )
    deposito_id: Mapped[int | None] = mapped_column(
        ForeignKey("depositos.id"), nullable=True
    )
    ordem: Mapped[int] = mapped_column(Integer, nullable=False)
    endereco: Mapped[str] = mapped_column(Text, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    demanda: Mapped[int] = mapped_column(Integer, default=0)
    janela_inicio: Mapped[time | None] = mapped_column(Time, nullable=True)
    janela_fim: Mapped[time | None] = mapped_column(Time, nullable=True)
    status: Mapped[ParadaStatus] = mapped_column(
        SQLEnum(ParadaStatus), default=ParadaStatus.PENDENTE
    )
    tempo_servico_min: Mapped[int] = mapped_column(Integer, default=8)
    chegada_prevista: Mapped[time | None] = mapped_column(Time, nullable=True)
    saida_prevista: Mapped[time | None] = mapped_column(Time, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(Text, nullable=True)

    rota: Mapped[Rota] = relationship(back_populates="paradas")
    entrega: Mapped[Entrega | None] = relationship(back_populates="parada")
    deposito: Mapped[Deposito | None] = relationship()

    __table_args__ = (
        Index("ix_paradas_rota_ordem", "rota_id", "ordem", unique=True),
    )