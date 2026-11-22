import re

from route_engine.domain.constraints import DELIVERY_SERVICE_DURATION_MINUTES
from route_engine.domain.models import (
    Delivery,
    Depot,
    Location,
    Problem,
    TimeWindow,
    Vehicle,
)

_TIME_PATTERN = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]\Z")


class ValidationError(Exception):
    def __init__(self, errors: list[dict]):
        super().__init__(f"{len(errors)} erro(s) de validação")
        self.errors = errors


def _is_int(value: object) -> bool:
    return type(value) is int


def _is_number(value: object) -> bool:
    return type(value) in (int, float)


def _error(field: str, message: str) -> dict:
    return {"field": field, "message": message}


def _parse_time(value: object, field: str, *, allow_24: bool = False) -> int:
    if not isinstance(value, str):
        raise ValidationError([_error(field, "Horário deve ser uma string HH:MM")])

    if value == "24:00" and allow_24:
        return 24 * 60

    if not _TIME_PATTERN.fullmatch(value):
        raise ValidationError(
            [_error(field, "Horário deve ser válido e estar no formato HH:MM")]
        )

    hours, minutes = (int(part) for part in value.split(":"))
    return hours * 60 + minutes


def _validate_time_window(raw: object, field: str) -> TimeWindow:
    if not isinstance(raw, dict):
        raise ValidationError([_error(field, "Intervalo deve ser um dicionário")])

    for boundary in ("start", "end"):
        boundary_field = f"{field}.{boundary}"
        if boundary not in raw or raw[boundary] is None:
            raise ValidationError([_error(boundary_field, "Horário é obrigatório")])

    start_minute = _parse_time(raw["start"], f"{field}.start")
    end_minute = _parse_time(raw["end"], f"{field}.end", allow_24=True)
    if start_minute >= end_minute:
        raise ValidationError(
            [
                _error(
                    field,
                    "Início deve ser anterior ao fim no mesmo dia",
                )
            ]
        )

    return TimeWindow(start_minute=start_minute, end_minute=end_minute)


def _delivery_time_window(
    delivery_data: dict,
    operating_hours: TimeWindow,
) -> TimeWindow:
    requested_data = delivery_data.get("time_window")
    if requested_data is None:
        effective_window = operating_hours
    else:
        requested_window = _validate_time_window(
            requested_data,
            "deliveries.time_window",
        )
        effective_start = max(
            requested_window.start_minute,
            operating_hours.start_minute,
        )
        effective_end = min(
            requested_window.end_minute,
            operating_hours.end_minute,
        )
        if effective_start >= effective_end:
            raise ValidationError(
                [
                    _error(
                        "deliveries.time_window",
                        "Janela não se sobrepõe ao expediente",
                    )
                ]
            )
        effective_window = TimeWindow(
            start_minute=effective_start,
            end_minute=effective_end,
        )

    if (
        effective_window.end_minute - effective_window.start_minute
        < DELIVERY_SERVICE_DURATION_MINUTES
    ):
        raise ValidationError(
            [
                _error(
                    "deliveries.time_window",
                    "Janela efetiva deve permitir pelo menos 8 minutos de atendimento",
                )
            ]
        )

    return effective_window


def _validate_id(value: object, field: str) -> int:
    if not _is_int(value):
        raise ValidationError([_error(field, "ID deve ser um número inteiro")])
    return value


def _validate_location(location_data: object, field_prefix: str) -> Location:
    location_field = f"{field_prefix}.location"
    if not isinstance(location_data, dict):
        raise ValidationError(
            [_error(location_field, "Localização deve ser um dicionário")]
        )

    latitude = location_data.get("latitude")
    longitude = location_data.get("longitude")

    if latitude is None or longitude is None:
        raise ValidationError(
            [_error(location_field, "Latitude e longitude são obrigatórias")]
        )

    if not _is_number(latitude) or not _is_number(longitude):
        raise ValidationError(
            [_error(location_field, "Latitude e longitude devem ser números")]
        )

    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        raise ValidationError(
            [_error(location_field, "Latitude e longitude fora do intervalo válido")]
        )

    address = location_data.get("address")
    if address is not None and not isinstance(address, str):
        raise ValidationError(
            [
                _error(
                    f"{location_field}.address",
                    "Endereço deve ser uma string ou None",
                )
            ]
        )

    return Location(latitude=latitude, longitude=longitude, address=address)


def validate_problem(raw: object) -> Problem:
    if not isinstance(raw, dict):
        raise ValidationError([_error("problem", "Deve ser um dicionário")])

    depot_data = raw.get("depot")
    vehicles_data = raw.get("vehicles", [])
    deliveries_data = raw.get("deliveries", [])

    if depot_data is None:
        raise ValidationError([_error("depot", "Depósito não informado")])
    if not isinstance(depot_data, dict):
        raise ValidationError([_error("depot", "Depósito deve ser um dicionário")])
    if not depot_data:
        raise ValidationError([_error("depot", "Depósito vazio ou inválido")])

    if vehicles_data is None:
        raise ValidationError([_error("vehicles", "Veículos não informados")])
    if not isinstance(vehicles_data, list):
        raise ValidationError([_error("vehicles", "Veículos devem ser uma lista")])
    if not vehicles_data:
        raise ValidationError([_error("vehicles", "Nenhum veículo disponível")])

    if deliveries_data is None:
        raise ValidationError([_error("deliveries", "Entregas não informadas")])
    if not isinstance(deliveries_data, list):
        raise ValidationError([_error("deliveries", "Entregas devem ser uma lista")])
    if not deliveries_data:
        raise ValidationError([_error("deliveries", "Nenhuma entrega informada")])

    if raw.get("operating_hours") is None:
        raise ValidationError([_error("operating_hours", "Expediente é obrigatório")])
    operating_hours = _validate_time_window(raw["operating_hours"], "operating_hours")

    depot_id = _validate_id(depot_data.get("id"), "depot.id")
    depot = Depot(
        id=depot_id,
        location=_validate_location(depot_data.get("location"), "depot"),
    )

    vehicles: list[Vehicle] = []
    for vehicle_data in vehicles_data:
        if not isinstance(vehicle_data, dict):
            raise ValidationError(
                [_error("vehicles", "Veículo deve ser um dicionário")]
            )

        vehicle_id = _validate_id(vehicle_data.get("id"), "vehicles.id")
        capacity = vehicle_data.get("capacity")
        if not _is_int(capacity) or capacity <= 0:
            raise ValidationError(
                [
                    _error(
                        "vehicles.capacity",
                        "Capacidade deve ser um número inteiro positivo",
                    )
                ]
            )
        vehicles.append(Vehicle(id=vehicle_id, capacity=capacity))

    deliveries: list[Delivery] = []
    for delivery_data in deliveries_data:
        if not isinstance(delivery_data, dict):
            raise ValidationError(
                [_error("deliveries", "Cada entrega deve ser um dicionário")]
            )

        delivery_id = _validate_id(delivery_data.get("id"), "deliveries.id")
        demand = delivery_data.get("demand")
        if not _is_int(demand) or demand <= 0:
            raise ValidationError(
                [
                    _error(
                        "deliveries.demand",
                        "Demanda deve ser um número inteiro positivo",
                    )
                ]
            )

        deliveries.append(
            Delivery(
                id=delivery_id,
                demand=demand,
                location=_validate_location(
                    delivery_data.get("location"), "deliveries"
                ),
                time_window=_delivery_time_window(delivery_data, operating_hours),
            )
        )

    problem = Problem(
        depot=depot,
        vehicles=tuple(vehicles),
        deliveries=tuple(deliveries),
        operating_hours=operating_hours,
    )

    if any(delivery.demand > problem.max_capacity for delivery in problem.deliveries):
        raise ValidationError(
            [
                _error(
                    "deliveries.demand",
                    "Demanda da entrega excede a capacidade do maior veículo",
                )
            ]
        )

    if problem.total_demand > problem.total_capacity:
        raise ValidationError(
            [_error("vehicles", "Capacidade insuficiente para atender a demanda")]
        )

    return problem
