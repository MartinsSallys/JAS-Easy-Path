from route_engine.domain.models import Delivery, Depot, Location, Problem, Vehicle

def _validate_location(location_data: dict, field_prefix: str) -> Location:
    if not isinstance(location_data, dict):
        error = _error(f"{field_prefix}.location", "Localização deve ser um dicionário")
        raise ValidationError([error])

    latitude = location_data.get("latitude")
    longitude = location_data.get("longitude")

    if latitude is None or longitude is None:
        error = _error(f"{field_prefix}.location", "Latitude e longitude são obrigatórias")
        raise ValidationError([error])

    if not _is_number(latitude) or not _is_number(longitude):
        error = _error(f"{field_prefix}.location", "Latitude e longitude devem ser números")
        raise ValidationError([error])

    if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
        error = _error(f"{field_prefix}.location", "Latitude e longitude fora do intervalo válido")
        raise ValidationError([error])

    address = location_data.get("address")
    if address is not None and not isinstance(address, str):
        error = _error(f"{field_prefix}.location.address", "Endereço deve ser uma string ou None")
        raise ValidationError([error])

    return Location(latitude=latitude, longitude=longitude, address=address)
    
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


def validate_problem(raw: dict) -> Problem:
    if not isinstance(raw, dict):
        error = _error("problem", "Deve ser um dicionário")
        raise ValidationError([error])
    
    depot_data = raw.get("depot")
    vehicles_data = raw.get("vehicles", [])
    deliveries_data = raw.get("deliveries", [])

#verificação do depósito
    if depot_data is None:
        error = _error("depot", "Depósito não informado")
        raise ValidationError([error])
    if not isinstance(depot_data, dict):
        error = _error("depot", "Depósito deve ser um dicionário")
        raise ValidationError([error])
    if not depot_data:
        error = _error("depot", "Depósito vazio ou inválido")
        raise ValidationError([error])
 #verificação dos veículos

    if vehicles_data is None:
        error = _error("vehicles", "Veículos não informados")
        raise ValidationError([error])
    if not isinstance(vehicles_data, list):
        error = _error("vehicles", "Veículos devem ser uma lista")
        raise ValidationError([error])
    if not vehicles_data:
        error = _error("vehicles", "Nenhum veículo disponível")
        raise ValidationError([error])
    
#verificação das entregas

    if deliveries_data is None:
        error = _error("deliveries", "Entregas não informadas")
        raise ValidationError([error])
    if not isinstance(deliveries_data, list):
        error = _error("deliveries", "Entregas devem ser uma lista")
        raise ValidationError([error])
    if not deliveries_data:
        error = _error("deliveries", "Nenhuma entrega informada")
        raise ValidationError([error])

 # verificação dos campos de localização do depósito, capacidade dos veículos e demanda das entregas
    
    depot_location = _validate_location(depot_data.get("location"), "depot")

    for vehicle in vehicles_data:
        if not isinstance(vehicle, dict):
            error = _error("vehicles", "Veículo deve ser um dicionário")
            raise ValidationError([error])
        
        if not _is_int(vehicle.get("capacity")) or vehicle["capacity"] <= 0:
            error = _error("vehicles.capacity", "Capacidade deve ser um número inteiro positivo")
            raise ValidationError([error])

    for delivery in deliveries_data:
        if not isinstance(delivery, dict):
            error = _error("deliveries", " Cada entrega deve ser um dicionário")
            raise ValidationError([error])

        if not _is_int(delivery.get("demand")) or delivery["demand"] <= 0:
            error = _error("deliveries.demand", "Demanda deve ser um número inteiro positivo")
            raise ValidationError([error])
        delivery_location = delivery.get("location")
        if not isinstance(delivery_location, dict):
            error = _error("deliveries.location", "Localização da entrega deve ser um dicionário")
            raise ValidationError([error])

        

    total_capacity = sum(
        vehicle["capacity"] for vehicle in vehicles_data
    )

    total_demand = sum(
        delivery["demand"] for delivery in deliveries_data
    )

    max_capacity = max(vehicle["capacity"] for vehicle in vehicles_data)

    if total_demand > total_capacity or total_capacity <= 0: 
        error = _error("vehicles", "Capacidade insuficiente para atender a demanda")
        raise ValidationError([error])
    
 

