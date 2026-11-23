from dataclasses import dataclass


@dataclass(frozen=True)
class TimeWindow:
    start_minute: int
    end_minute: int


@dataclass(frozen=True)
class Location:
    latitude: float
    longitude: float
    address: str | None = None


@dataclass(frozen=True)
class Depot:
    id: int
    location: Location


@dataclass(frozen=True)
class Vehicle:
    id: int
    capacity: int


@dataclass(frozen=True)
class Delivery:
    id: int
    demand: int
    location: Location
    time_window: TimeWindow


@dataclass(frozen=True)
class Problem:
    depot: Depot
    vehicles: tuple[Vehicle, ...]
    deliveries: tuple[Delivery, ...]
    operating_hours: TimeWindow

    @property
    def total_demand(self) -> int:
        return sum(delivery.demand for delivery in self.deliveries)

    @property
    def total_capacity(self) -> int:
        return sum(vehicle.capacity for vehicle in self.vehicles)

    @property
    def max_capacity(self) -> int:
        return max((vehicle.capacity for vehicle in self.vehicles), default=0)
