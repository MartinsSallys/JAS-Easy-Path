"""Run and print the manual RotaCerta scenario with OR-Tools."""

import json
from dataclasses import asdict

from route_engine.examples.manual_distance_scenario import build_manual_scenario
from route_engine.optimizer import solve_routes


def main() -> None:
    problem, distance_matrix, duration_matrix = build_manual_scenario()
    result = solve_routes(problem, distance_matrix, duration_matrix)
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
