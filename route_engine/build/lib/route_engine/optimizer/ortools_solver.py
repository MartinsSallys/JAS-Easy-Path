from datetime import time
from typing import Optional

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from route_engine.domain.models import (
    Delivery,
    Depot,
    Location,
    Problem,
    Route,
    Solution,
    SolveStatus,
    Stop,
    Vehicle,
    haversine_distance,
    minutes_to_time,
    time_to_minutes,
)


class RouteEngine:
    def __init__(
        self,
        time_limit_seconds: int = 30,
        first_solution_strategy: str = "PATH_CHEAPEST_ARC",
    ):
        self.time_limit = time_limit_seconds
        self.first_solution_strategy = getattr(
            routing_enums_pb2.FirstSolutionStrategy,
            first_solution_strategy,
        )

    def solve(self, problem: Problem) -> Solution:
        import time as time_module
        start_time = time_module.time()

        all_locations = [problem.depot.location] + [d.location for d in problem.deliveries]
        n = len(all_locations)

        distance_matrix = [[0] * n for _ in range(n)]
        duration_matrix = [[0] * n for _ in range(n)]

        for i in range(n):
            for j in range(n):
                if i != j:
                    dist_m = haversine_distance(
                        all_locations[i].latitude, all_locations[i].longitude,
                        all_locations[j].latitude, all_locations[j].longitude
                    )
                    distance_matrix[i][j] = int(dist_m)
                    duration_matrix[i][j] = int(dist_m / 8.33)

        demands = [0] + [d.demand for d in problem.deliveries]
        vehicle_capacities = [v.capacity for v in problem.vehicles]
        service_times = [0] + [d.service_time_min for d in problem.deliveries]

        time_windows = [(0, 24 * 60)]
        for d in problem.deliveries:
            if d.time_window_start and d.time_window_end:
                start = time_to_minutes(d.time_window_start)
                end = time_to_minutes(d.time_window_end)
                if end <= start:
                    end += 24 * 60
                time_windows.append((start, end))
            else:
                work_start = time_to_minutes(problem.work_start)
                work_end = time_to_minutes(problem.work_end)
                if work_end <= work_start:
                    work_end += 24 * 60
                time_windows.append((work_start, work_end))

        manager = pywrapcp.RoutingIndexManager(n, len(problem.vehicles), 0)
        routing = pywrapcp.RoutingModel(manager)

        def distance_callback(from_idx: int, to_idx: int) -> int:
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            return distance_matrix[from_node][to_node]

        transit_idx = routing.RegisterTransitCallback(distance_callback)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        def demand_callback(from_idx: int) -> int:
            from_node = manager.IndexToNode(from_idx)
            return demands[from_node]

        demand_idx = routing.RegisterUnaryTransitCallback(demand_callback)
        routing.AddDimensionWithVehicleCapacity(
            demand_idx, 0, vehicle_capacities, True, "Capacity"
        )

        def time_callback(from_idx: int, to_idx: int) -> int:
            from_node = manager.IndexToNode(from_idx)
            to_node = manager.IndexToNode(to_idx)
            return duration_matrix[from_node][to_node] + service_times[from_node]

        time_idx = routing.RegisterTransitCallback(time_callback)
        routing.AddDimension(
            time_idx,
            24 * 60,
            24 * 60,
            False,
            "Time",
        )
        time_dim = routing.GetDimensionOrDie("Time")

        for i, (start, end) in enumerate(time_windows):
            index = manager.NodeToIndex(i)
            time_dim.CumulVar(index).SetRange(start, end)

        for v in range(len(problem.vehicles)):
            start_idx = routing.Start(v)
            end_idx = routing.End(v)
            time_dim.CumulVar(start_idx).SetRange(
                time_to_minutes(problem.work_start),
                time_to_minutes(problem.work_end)
            )
            time_dim.CumulVar(end_idx).SetRange(
                time_to_minutes(problem.work_start),
                time_to_minutes(problem.work_end)
            )

        for i in range(1, n):
            routing.AddDisjunction([manager.NodeToIndex(i)], 100000)

        search_params = pywrapcp.DefaultRoutingSearchParameters()
        search_params.first_solution_strategy = self.first_solution_strategy
        search_params.time_limit.seconds = self.time_limit
        search_params.log_search = False

        solution = routing.SolveWithParameters(search_params)
        solve_time_ms = int((time_module.time() - start_time) * 1000)

        if not solution:
            return Solution(
                routes=[],
                unassigned=list(problem.deliveries),
                status=SolveStatus.INFEASIBLE,
                solve_time_ms=solve_time_ms,
            )

        routes = []
        unassigned_ids = set(range(len(problem.deliveries)))

        for v_idx in range(len(problem.vehicles)):
            index = routing.Start(v_idx)
            route_stops = []
            route_distance = 0
            route_load = 0
            sequence = 0

            while not routing.IsEnd(index):
                node = manager.IndexToNode(index)
                time_var = time_dim.CumulVar(index)
                arrival = minutes_to_time(solution.Value(time_var))
                departure = minutes_to_time(solution.Value(time_var) + service_times[node])

                if node == 0:
                    route_stops.append(Stop(
                        delivery_id=None,
                        location=problem.depot.location,
                        sequence=sequence,
                        arrival_time=arrival,
                        departure_time=departure,
                        load_after=route_load,
                        is_depot=True,
                    ))
                else:
                    d_idx = node - 1
                    delivery = problem.deliveries[d_idx]
                    route_load += delivery.demand
                    unassigned_ids.discard(d_idx)
                    route_stops.append(Stop(
                        delivery_id=delivery.id,
                        location=delivery.location,
                        sequence=sequence,
                        arrival_time=arrival,
                        departure_time=departure,
                        load_after=route_load,
                        is_depot=False,
                    ))

                sequence += 1
                prev = index
                index = solution.Value(routing.NextVar(index))
                prev_node = manager.IndexToNode(prev)
                curr_node = manager.IndexToNode(index)
                route_distance += distance_matrix[prev_node][curr_node]

            node = manager.IndexToNode(index)
            time_var = time_dim.CumulVar(index)
            arrival = minutes_to_time(solution.Value(time_var))
            route_stops.append(Stop(
                delivery_id=None,
                location=problem.depot.location,
                sequence=sequence,
                arrival_time=arrival,
                departure_time=arrival,
                load_after=0,
                is_depot=True,
            ))

            if len(route_stops) > 2:
                total_drive_time = 0
                for i in range(len(route_stops) - 1):
                    from_node = route_stops[i].sequence if not route_stops[i].is_depot or i == 0 else 0
                    to_node = route_stops[i + 1].sequence if not route_stops[i + 1].is_depot else 0
                    if i < len(route_stops) - 1:
                        from_idx = manager.NodeToIndex(from_node) if from_node < n else 0
                        to_idx = manager.NodeToIndex(to_node) if to_node < n else 0
                        from_n = manager.IndexToNode(from_idx)
                        to_n = manager.IndexToNode(to_idx)
                        total_drive_time += duration_matrix[from_n][to_n]

                total_service_time = sum(
                    d.service_time_min
                    for d in problem.deliveries
                    if d.id in [s.delivery_id for s in route_stops if s.delivery_id]
                )
                routes.append(Route(
                    vehicle_id=problem.vehicles[v_idx].id,
                    stops=route_stops,
                    total_distance_m=route_distance,
                    total_duration_min=(total_drive_time + total_service_time),
                    total_load=route_load,
                ))

        unassigned = [problem.deliveries[i] for i in unassigned_ids]

        status = SolveStatus.OPTIMAL
        if unassigned:
            status = SolveStatus.FEASIBLE

        return Solution(
            routes=routes,
            unassigned=unassigned,
            status=status,
            solve_time_ms=solve_time_ms,
        )