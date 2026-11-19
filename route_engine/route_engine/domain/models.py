from dataclasses import dataclass
from datetime import time
from enum import Enum


class SolveStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"


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
    time_window_start: time | None = None
    time_window_end: time | None = None
    service_time_min: int = 8


@dataclass(frozen=True)
class Problem:
    depot: Depot
    vehicles: tuple[Vehicle, ...]
    deliveries: tuple[Delivery, ...]
    work_start: time = time(8, 0)
    work_end: time = time(18, 0)

    @property
    def total_demand(self) -> int:
        return sum(d.demand for d in self.deliveries)

    @property
    def total_capacity(self) -> int:
        return sum(v.capacity for v in self.vehicles)

    @property
    def max_capacity(self) -> int:
        return max((v.capacity for v in self.vehicles), default=0)


@dataclass
class Stop:
    delivery_id: int | None
    location: Location
    sequence: int
    arrival_time: time
    departure_time: time
    load_after: int
    is_depot: bool = False


@dataclass
class Route:
    vehicle_id: int
    stops: list[Stop]
    total_distance_m: int
    total_duration_min: int
    total_load: int


@dataclass
class Solution:
    routes: list[Route]
    unassigned: list[Delivery]
    status: SolveStatus
    solve_time_ms: int


def time_to_minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def minutes_to_time(m: int) -> time:
    m = max(0, m)
    h = (m // 60) % 24
    mi = m % 60
    return time(h, mi)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    from math import atan2, cos, radians, sin, sqrt
    R = 6371000.0
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c