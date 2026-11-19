from dataclasses import dataclass
from typing import Optional

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.core.config import settings
from app.schemas import (
    OptimizationDelivery,
    OptimizationLocation,
    OptimizationRequest,
    OptimizationResponse,
    OptimizationVehicle,
    RouteResult,
    StopResult,
)


@dataclass
class CVRPProblem:
    distance_matrix: list[list[int]]
    demands: list[int]
    vehicle_capacities: list[int]
    num_vehicles: int
    depot: int = 0


class ORToolsOptimizer:
    def __init__(self):
        self.time_limit = settings.ortools_time_limit_seconds
        self.first_solution_strategy = getattr(
            routing_enums_pb2.FirstSolutionStrategy,
            settings.ortools_first_solution_strategy,
        )

    def _create_problem(self, request: OptimizationRequest) -> CVRPProblem:
        all_locations = [request.depot] + [d.location for d in request.deliveries]
        n = len(all_locations)

        distance_matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    dist = self._haversine_distance(
                        all_locations[i].latitude, all_locations[i].longitude,
                        all_locations[j].latitude, all_locations[j].longitude
                    )
                    distance_matrix[i][j] = int(dist * 1000)

        demands = [0] + [d.demand for d in request.deliveries]
        vehicle_capacities = [v.capacity for v in request.vehicles]

        return CVRPProblem(
            distance_matrix=distance_matrix,
            demands=demands,
            vehicle_capacities=vehicle_capacities,
            num_vehicles=len(request.vehicles),
            depot=0,
        )

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        from math import atan2, cos, radians, sin, sqrt
        R = 6371.0
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))
        return R * c

    def solve(self, request: OptimizationRequest) -> OptimizationResponse:
        import time
        start_time = time.time()

        problem = self._create_problem(request)

        manager = pywrapcp.RoutingIndexManager(
            len(problem.distance_matrix),
            problem.num_vehicles,
            problem.depot,
        )
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_index: int, to_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            to_node = manager.IndexToNode(to_index)
            return problem.distance_matrix[from_node][to_node]

        transit_callback_index = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_callback_index)

        def demand_callback(from_index: int) -> int:
            from_node = manager.IndexToNode(from_index)
            return problem.demands[from_node]

        demand_callback_index = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_callback_index,
            0,
            problem.vehicle_capacities,
            True,
            "Capacity",
        )

        search_parameters = pywrapcp.DefaultRoutingSearchParameters()
        search_parameters.first_solution_strategy = self.first_solution_strategy
        search_parameters.time_limit.seconds = self.time_limit
        search_parameters.log_search = False

        solution = routing.SolveWithParameters(search_parameters)

        solve_time_ms = int((time.time() - start_time) * 1000)

        if not solution:
            return OptimizationResponse(
                routes=[],
                unassigned=request.deliveries,
                status="infeasible",
                solve_time_ms=solve_time_ms,
            )

        routes = []
        unassigned_ids = set(range(len(request.deliveries)))

        for vehicle_idx in range(problem.num_vehicles):
            index = routing.Start(vehicle_idx)
            route_stops = []
            route_distance = 0
            route_load = 0
            sequence = 0

            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                if node == 0:
                    route_stops.append(StopResult(
                        delivery_id=None,
                        location=request.depot,
                        sequence=sequence,
                        arrival_time=None,
                        departure_time=None,
                        load_after=route_load,
                    ))
                else:
                    delivery_idx = node - 1
                    delivery = request.deliveries[delivery_idx]
                    route_load += delivery.demand
                    unassigned_ids.discard(delivery_idx)
                    route_stops.append(StopResult(
                        delivery_id=delivery.id,
                        location=delivery.location,
                        sequence=sequence,
                        arrival_time=None,
                        departure_time=None,
                        load_after=route_load,
                    ))
                sequence += 1
                previous_index = index
                index = solution.Value(routing.NextVar(index))
                if not routing.IsEnd(index):
                    route_distance += problem.distance_matrix[manager.IndexToNode(previous_index)][manager.IndexToNode(index)]

            node = manager.IndexToNode(index)
            if node == 0:
                route_stops.append(StopResult(
                    delivery_id=None,
                    location=request.depot,
                    sequence=sequence,
                    arrival_time=None,
                    departure_time=None,
                    load_after=0,
                ))

            if len(route_stops) > 2:
                routes.append(RouteResult(
                    vehicle_id=request.vehicles[vehicle_idx].id,
                    stops=route_stops,
                    total_distance_km=round(route_distance / 1000, 2),
                    total_duration_min=int(route_distance / 1000 * 60 / 30),
                    total_load=route_load,
                ))

        unassigned = [request.deliveries[i] for i in unassigned_ids]

        status = "optimal"
        if unassigned and not request.options.allow_unassigned:
            status = "infeasible"
        elif unassigned:
            status = "feasible"

        return OptimizationResponse(
            routes=routes,
            unassigned=unassigned,
            status=status,
            solve_time_ms=solve_time_ms,
        )


optimizer = ORToolsOptimizer()