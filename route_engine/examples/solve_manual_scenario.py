"""Run and print the manual RotaCerta scenario with OR-Tools."""

import json
import sys
from dataclasses import asdict

from route_engine.examples.manual_distance_scenario import build_manual_scenario
from route_engine.optimizer import solve_routes


def main() -> None:
    problem, matrix = build_manual_scenario()
    result = solve_routes(problem, matrix)
    print(
        "Aviso: o solver considera apenas distância e capacidade; as rotas atuais "
        "não têm garantia temporal de atendimento, espera, janelas, expediente ou "
        "retorno dentro do horário.",
        file=sys.stderr,
    )
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
