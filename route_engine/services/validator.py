from route_engine.domain.models import Delivery, Depot, Location, Problem, Vehicle


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
            )
        )

    problem = Problem(
        depot=depot,
        vehicles=tuple(vehicles),
        deliveries=tuple(deliveries),
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
