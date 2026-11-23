from datetime import date, datetime, time
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EntregaStatus(StrEnum):
    PENDENTE = "PENDENTE"
    ATRIBUIDA = "ATRIBUIDA"
    EM_ROTA = "EM_ROTA"
    ENTREGUE = "ENTREGUE"
    FALHA = "FALHA"
    CANCELADA = "CANCELADA"


class VeiculoTipo(StrEnum):
    MOTO = "MOTO"
    CARRO = "CARRO"
    CAMINHAO = "CAMINHAO"
    VAN = "VAN"


class RotaStatus(StrEnum):
    RASCUNHO = "RASCUNHO"
    OTIMIZADA = "OTIMIZADA"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    CANCELADA = "CANCELADA"


class ParadaStatus(StrEnum):
    PENDENTE = "PENDENTE"
    EM_ANDAMENTO = "EM_ANDAMENTO"
    CONCLUIDA = "CONCLUIDA"
    FALHA = "FALHA"
    PULADA = "PULADA"


# --- Deposito Schemas ---
class DepositoBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    endereco: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class DepositoCreate(DepositoBase):
    pass


class DepositoUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=100)
    endereco: str | None = Field(None, min_length=1)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    ativo: bool | None = None


class DepositoResponse(DepositoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool
    created_at: datetime


# --- Veiculo Schemas ---
class VeiculoBase(BaseModel):
    placa: str = Field(..., min_length=1, max_length=10)
    capacidade: int = Field(..., gt=0)
    tipo: VeiculoTipo = VeiculoTipo.CAMINHAO


class VeiculoCreate(VeiculoBase):
    pass


class VeiculoUpdate(BaseModel):
    placa: str | None = Field(None, min_length=1, max_length=10)
    capacidade: int | None = Field(None, gt=0)
    tipo: VeiculoTipo | None = None
    ativo: bool | None = None


class VeiculoResponse(VeiculoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    ativo: bool
    created_at: datetime


# --- Entrega Schemas ---
class EntregaBase(BaseModel):
    pedido_id: str = Field(..., min_length=1, max_length=50)
    endereco: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    demanda: int = Field(default=1, ge=1)
    janela_inicio: time | None = None
    janela_fim: time | None = None
    observacoes: str | None = None


class EntregaCreate(EntregaBase):
    @model_validator(mode="after")
    def _janela_completa(self) -> "EntregaCreate":
        if (self.janela_inicio is None) != (self.janela_fim is None):
            raise ValueError(
                "janela_inicio e janela_fim devem ser informados juntos"
            )
        return self


class EntregaBatchCreate(BaseModel):
    entregas: list[EntregaCreate]


class EntregaUpdate(BaseModel):
    pedido_id: str | None = Field(None, min_length=1, max_length=50)
    endereco: str | None = Field(None, min_length=1)
    latitude: float | None = Field(None, ge=-90, le=90)
    longitude: float | None = Field(None, ge=-180, le=180)
    demanda: int | None = Field(None, ge=1)
    janela_inicio: time | None = None
    janela_fim: time | None = None
    observacoes: str | None = None
    status: EntregaStatus | None = None


class EntregaResponse(EntregaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: EntregaStatus
    created_at: datetime
    updated_at: datetime
    rota_id: int | None = None
    parada_ordem: int | None = None


# --- Parada Schemas ---
class ParadaBase(BaseModel):
    ordem: int = Field(..., ge=0)
    endereco: str = Field(..., min_length=1)
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    demanda: int = Field(default=0, ge=0)
    janela_inicio: time | None = None
    janela_fim: time | None = None
    tempo_servico_min: int = Field(default=8, ge=0)
    chegada_prevista: time | None = None
    saida_prevista: time | None = None
    observacoes: str | None = None


class ParadaResponse(ParadaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rota_id: int
    entrega_id: int | None = None
    deposito_id: int | None = None
    status: ParadaStatus


# --- Rota Schemas ---
class RotaBase(BaseModel):
    nome: str = Field(..., min_length=1, max_length=100)
    data: date
    deposito_id: int
    veiculo_id: int | None = None


class RotaCreate(RotaBase):
    entrega_ids: list[int] = Field(default_factory=list)


class RotaUpdate(BaseModel):
    nome: str | None = Field(None, min_length=1, max_length=100)
    data: date | None = None
    deposito_id: int | None = None
    veiculo_id: int | None = None
    status: RotaStatus | None = None


class RotaOptimizeRequest(BaseModel):
    minimize: str = Field(default="distance", pattern="^(distance|duration)$")
    time_limit_seconds: int = Field(default=30, ge=5, le=300)
    allow_unassigned: bool = False


class RotaResponse(RotaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    status: RotaStatus
    distancia_total_km: float | None = None
    tempo_total_min: int | None = None
    created_at: datetime
    updated_at: datetime
    otimizada_em: datetime | None = None


class RotaWithParadasResponse(RotaResponse):
    paradas: list[ParadaResponse] = []


# --- Geocoding Schemas ---
class GeocodeRequest(BaseModel):
    endereco: str = Field(..., min_length=1)
    country_code: str | None = "br"


class GeocodeResult(BaseModel):
    latitude: float
    longitude: float
    display_name: str
    confidence: float
    address_components: dict


class GeocodeResponse(BaseModel):
    results: list[GeocodeResult]
    ambiguous: bool = False


class GeocodeBatchRequest(BaseModel):
    enderecos: list[str]


class ReverseGeocodeRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


# --- Matrix Schemas ---
class MatrixRequest(BaseModel):
    locations: list[dict] = Field(..., min_length=2)
    metrics: list[str] = Field(default=["distance", "duration"])
    profile: str = "driving-car"


class MatrixResponse(BaseModel):
    distances_km: list[list[float | None]]
    durations_min: list[list[float | None]]
    provider: str
    cached: bool = False


# --- Optimization Schemas ---
class OptimizationLocation(BaseModel):
    latitude: float
    longitude: float
    address: str | None = None


class OptimizationVehicle(BaseModel):
    id: int
    capacity: int


class OptimizationDelivery(BaseModel):
    id: int
    demand: int
    location: OptimizationLocation
    time_window_start: str | None = None
    time_window_end: str | None = None


class OptimizationRequest(BaseModel):
    depot: OptimizationLocation
    vehicles: list[OptimizationVehicle]
    deliveries: list[OptimizationDelivery]
    options: RotaOptimizeRequest | None = None


class StopResult(BaseModel):
    delivery_id: int | None = None
    location: OptimizationLocation
    sequence: int
    arrival_time: str | None = None
    departure_time: str | None = None
    load_after: int


class RouteResult(BaseModel):
    vehicle_id: int
    stops: list[StopResult]
    total_distance_km: float
    total_duration_min: int
    total_load: int


class OptimizationResponse(BaseModel):
    routes: list[RouteResult]
    unassigned: list[OptimizationDelivery] = []
    status: str
    solve_time_ms: int
    message: str | None = None


# --- Health Schemas ---
class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"