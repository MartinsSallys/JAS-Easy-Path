"""Simula operações piloto da issue #14 e registra as métricas coletadas.

Reproduz o fluxo real do sistema sem depender de chaves externas:

1. Geocodifica endereços reais (bairros de Teresina-PI) via ``NominatimGeocoder``,
   o mesmo serviço do backend, em estágios: endereço completo, depois
   ``rua + cidade`` e, por fim, centroide do bairro — a mesma degradação
   prevista em ``docs/arquitetura-mvp.md`` §6.1 para endereços incompletos.
   Cada estágio consumido vira um registro de problema de geocodificação.
2. Monta as matrizes de distância/duração por Haversine — o mesmo fallback
   documentado do backend (``AVERAGE_SPEED_M_PER_MIN``).
3. Otimiza com ``route_engine.solve_routes`` e mede paradas, distância, tempo e
   tempo de planejamento do solver.
4. Calcula a distância da sequência em ordem de registro, aproximação do método
   manual atual (o lojista entrega na ordem em que os pedidos chegaram).

Os resultados são dados de simulação — não são operações reais acompanhadas em
campo. Servem para exercitar o instrumento de coleta e dar uma primeira leitura
do comportamento da ferramenta antes da validação com pilotos reais.

Execução (a partir da raiz do repositório):

    # Git Bash / Linux / macOS
    PYTHONPATH="backend:route_engine" python scripts/validacao_piloto.py

    # PowerShell
    $env:PYTHONPATH = "backend;route_engine"; python scripts/validacao_piloto.py
"""

import asyncio
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from app.services.geocoding import NominatimGeocoder
from route_engine.domain.constraints import DELIVERY_SERVICE_DURATION_MINUTES

from route_engine import (
    SolverStatus,
    ValidationError,
    solve_routes,
    validate_problem,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTADO_JSON = REPO_ROOT / "docs" / "validacao-piloto-resultados.json"

CIDADE = "Teresina, PI"

AVERAGE_SPEED_M_PER_MIN = 500.0
"""Espelha ``backend/app/services/optimizer.py`` (~30 km/h)."""

OPERATING_HOURS = {"start": "08:00", "end": "18:00"}
"""Expediente fixo do MVP (ver docs/arquitetura-mvp.md)."""

CONFIANCA_BAIXA = 0.8
SOLVER_TIME_LIMIT_S = 5

# ---------------------------------------------------------------------------
# Operações piloto simuladas — pequenos comércios de Teresina-PI.
#
# Endereços misturam qualidades de digitação reais: rua + bairro, só bairro e
# nomes ambíguos — exatamente o que o lojista digitaria numa planilha.
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    {
        "nome": "Distribuidora de água e gás",
        "deposito": {"rua": "Avenida Bento Martins", "bairro": "Piçarra"},
        "veiculos": [
            {"id": 1, "capacity": 20, "tipo": "CAMINHAO"},
            {"id": 2, "capacity": 6, "tipo": "MOTO"},
        ],
        "entregas": [
            {"rua": "Avenida João XXIII", "bairro": "Itararé", "demanda": 2},
            {
                "rua": "Rua Desembargador Pires de Castro",
                "bairro": "Saci",
                "demanda": 1,
            },
            {"rua": "Avenida Barão de Gurguéia", "bairro": "Vermelha", "demanda": 3},
            {"rua": "Rua Principal", "bairro": "Saci", "demanda": 1},
            {
                "rua": "Avenida Professor Minervino de Castro",
                "bairro": "Dirceu",
                "demanda": 2,
            },
            {"rua": "Rua Luiz Quirino", "bairro": "Morada do Sol", "demanda": 1},
            {
                "rua": "Avenida Marechal Castelo Branco",
                "bairro": "Vermelha",
                "demanda": 2,
            },
            {"rua": "Rua Padre Wilson", "bairro": "Dirceu", "demanda": 1},
            {
                "rua": "Avenida João Paulo II",
                "bairro": "Santa Maria da Codipi",
                "demanda": 4,
            },
            {"rua": "Rua Anísio de Abreu", "bairro": "Fátima", "demanda": 1},
            {"rua": "Avenida dos Expedicionários", "bairro": "Fátima", "demanda": 2},
            {"rua": "Rua Quinze de Novembro", "bairro": "Itararé", "demanda": 1},
            {"rua": "Rua Rui Barbosa", "bairro": "Morada do Sol", "demanda": 1},
            {"rua": "Travessa São Raimundo", "bairro": "Piçarra", "demanda": 1},
        ],
    },
    {
        "nome": "Drogaria",
        "deposito": {"rua": "Rua Álvaro Mendes", "bairro": "Centro"},
        "veiculos": [{"id": 1, "capacity": 10, "tipo": "MOTO"}],
        "entregas": [
            {"rua": "Rua Elizeu Martins", "bairro": "Centro", "demanda": 1},
            {"rua": "Rua Treze de Maio", "bairro": "Centro", "demanda": 1},
            {
                "rua": "Rua Paissandu",
                "bairro": "Centro",
                "demanda": 1,
                "time_window": {"start": "08:00", "end": "12:00"},
            },
            {"rua": "Avenida Juscelino Kubitschek", "bairro": "Horto", "demanda": 1},
            {"rua": "Avenida Miguel Rosa", "bairro": "Mafrense", "demanda": 1},
            {
                "rua": "Rua Governador Raimundo Artur de Vasconcelos",
                "bairro": "Horto",
                "demanda": 1,
            },
            {
                "rua": "Avenida Jóquei Clube",
                "bairro": "Jóquei",
                "demanda": 1,
                "time_window": {"start": "14:00", "end": "18:00"},
            },
            {"rua": "Rua Benjamin Constant", "bairro": "Centro", "demanda": 1},
            {"rua": "Avenida Centenário", "bairro": "Aeroporto", "demanda": 1},
            {"rua": "Rua São Pedro", "bairro": "Cristo Rei", "demanda": 1},
        ],
    },
    {
        "nome": "Mercearia de bairro",
        "deposito": {"rua": "Avenida Miguel Rosa", "bairro": "Mafrense"},
        "veiculos": [{"id": 1, "capacity": 8, "tipo": "CARRO"}],
        "entregas": [
            {"rua": "", "bairro": "Mafrense", "demanda": 1},
            {"rua": "Rua Bento de Carvalho", "bairro": "Mafrense", "demanda": 1},
            {"rua": "Avenida Amazonas", "bairro": "São Cristóvão", "demanda": 1},
            {"rua": "Rua Osvaldo Cruz", "bairro": "São Cristóvão", "demanda": 1},
            {
                "rua": "Rua Rodolfo Gustavo",
                "bairro": "Tancredo Neves",
                "demanda": 1,
                "time_window": {"start": "08:00", "end": "10:00"},
            },
            {
                "rua": "Avenida Henry Wall de Carvalho",
                "bairro": "Tancredo Neves",
                "demanda": 1,
            },
            {"rua": "Rua José Mendes", "bairro": "Gurupi", "demanda": 1},
            {"rua": "Avenida Ulisses Maranhão", "bairro": "Gurupi", "demanda": 1},
        ],
    },
    {
        "nome": "Loja de material de construção",
        "deposito": {"rua": "Avenida Marechal Castelo Branco", "bairro": "Vermelha"},
        "veiculos": [{"id": 1, "capacity": 14, "tipo": "CAMINHAO"}],
        "entregas": [
            {"rua": "Rua Zoroastro Macedo", "bairro": "Vermelha", "demanda": 2},
            {"rua": "Avenida Zanuto Filho", "bairro": "Aeroporto", "demanda": 1},
            {
                "rua": "Rua Comandante Cardoso de Sá",
                "bairro": "Aeroporto",
                "demanda": 2,
            },
            {"rua": "Avenida Depósito Público", "bairro": "Vermelha", "demanda": 1},
            {
                "rua": "Rua Engenheiro Nelson Nogueira",
                "bairro": "Vermelha",
                "demanda": 1,
            },
            {"rua": "Avenida João XXIII", "bairro": "Itararé", "demanda": 1},
            {"rua": "Rua Quinze de Novembro", "bairro": "Itararé", "demanda": 1},
            {
                "rua": "Avenida Professor Minervino de Castro",
                "bairro": "Dirceu",
                "demanda": 1,
                "time_window": {"start": "10:00", "end": "14:00"},
            },
            {"rua": "Rua Padre Wilson", "bairro": "Dirceu", "demanda": 1},
            {
                "rua": "Rua Desembargador Pires de Castro",
                "bairro": "Saci",
                "demanda": 1,
            },
            {"rua": "Avenida Bento Martins", "bairro": "Piçarra", "demanda": 1},
            {"rua": "Rua Principal", "bairro": "Saci", "demanda": 1},
        ],
    },
    {
        "nome": "Confeitaria atacado",
        "deposito": {"rua": "Avenida Jóquei Clube", "bairro": "Jóquei"},
        "veiculos": [{"id": 1, "capacity": 16, "tipo": "VAN"}],
        "entregas": [
            {
                "rua": "Avenida Frei Serafim",
                "bairro": "Centro",
                "demanda": 1,
                "time_window": {"start": "08:00", "end": "10:00"},
            },
            {
                "rua": "Rua Álvaro Mendes",
                "bairro": "Centro",
                "demanda": 2,
                "time_window": {"start": "08:00", "end": "10:00"},
            },
            {"rua": "Rua Elizeu Martins", "bairro": "Centro", "demanda": 1},
            {"rua": "Avenida Miguel Rosa", "bairro": "Mafrense", "demanda": 1},
            {"rua": "Rua São Pedro", "bairro": "Cristo Rei", "demanda": 1},
            {"rua": "Avenida Juscelino Kubitschek", "bairro": "Horto", "demanda": 1},
            {"rua": "Avenida dos Expedicionários", "bairro": "Fátima", "demanda": 2},
            {"rua": "Rua Anísio de Abreu", "bairro": "Fátima", "demanda": 1},
            {
                "rua": "Avenida Marechal Castelo Branco",
                "bairro": "Vermelha",
                "demanda": 1,
            },
            {
                "rua": "Avenida Professor Minervino de Castro",
                "bairro": "Dirceu",
                "demanda": 1,
            },
            {"rua": "Avenida João XXIII", "bairro": "Itararé", "demanda": 1},
            {"rua": "Rua Benedito Martins", "bairro": "Buenos Aires", "demanda": 1},
            {"rua": "Rua Antônio Furtado", "bairro": "Lourival Parente", "demanda": 1},
            {
                "rua": "Avenida Henry Wall de Carvalho",
                "bairro": "Tancredo Neves",
                "demanda": 1,
            },
        ],
    },
]


def _endereco_display(local: dict[str, str]) -> str:
    if local["rua"]:
        return f"{local['rua']}, {local['bairro']}, {CIDADE}"
    return f"{local['bairro']}, {CIDADE}"


def _haversine_m(
    origin: tuple[float, float], destination: tuple[float, float]
) -> float:
    earth_radius_m = 6_371_000.0
    lat1 = math.radians(origin[0])
    lon1 = math.radians(origin[1])
    lat2 = math.radians(destination[0])
    lon2 = math.radians(destination[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    )
    return earth_radius_m * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _build_matrices(
    locations: list[tuple[float, float]],
) -> tuple[list[list[int]], list[list[int]]]:
    """Matrizes N x N por Haversine; duração derivada da distância."""
    size = len(locations)
    distances = [[0] * size for _ in range(size)]
    durations = [[0] * size for _ in range(size)]
    for i in range(size):
        for j in range(size):
            if i == j:
                continue
            meters = _haversine_m(locations[i], locations[j])
            distances[i][j] = math.ceil(meters)
            durations[i][j] = math.ceil(meters / AVERAGE_SPEED_M_PER_MIN)
    return distances, durations


def _sequential_distance_m(distance_matrix: list[list[int]]) -> int:
    """Distância do percurso na ordem de registro, ida e volta ao depósito."""
    total = 0
    previous = 0
    for index in range(1, len(distance_matrix)):
        total += distance_matrix[previous][index]
        previous = index
    return total + distance_matrix[previous][0]


async def _tentar_geocode(
    geocoder: NominatimGeocoder, query: str
) -> dict[str, Any] | None:
    response = await geocoder.geocode(query)
    if not response.results:
        return None
    melhor = response.results[0]
    return {
        "query": query,
        "candidatos": len(response.results),
        "ambiguous": response.ambiguous,
        "confianca": melhor.confidence,
        "display_name": melhor.display_name,
        "latitude": melhor.latitude,
        "longitude": melhor.longitude,
    }


async def _geocodificar(
    geocoder: NominatimGeocoder, local: dict[str, str]
) -> dict[str, Any]:
    """Geocodifica em estágios e classifica o resultado.

    ``exato``            — endereço completo, um resultado confiável.
    ``ambigu``           — há candidatos, mas o melhor tem confiança baixa ou
                           a resposta veio marcada como ambígua.
    ``centroide_bairro`` — só o bairro geocodificou; coordenada aproximada,
                           exige confirmação manual do ponto.
    ``sem_resultado``    — nenhum estágio retornou coordenada; a entrega fica
                           fora da rota simulada.
    """
    endereco = _endereco_display(local)
    tentativas = [endereco]
    if local["rua"]:
        tentativas.append(f"{local['rua']}, {CIDADE}")
    bairro_query = f"{local['bairro']}, {CIDADE}"
    if bairro_query not in tentativas:
        tentativas.append(bairro_query)

    melhor: dict[str, Any] | None = None
    etapa_usada = 0
    for etapa, query in enumerate(tentativas):
        tentativa = await _tentar_geocode(geocoder, query)
        if tentativa is not None:
            melhor = tentativa
            etapa_usada = etapa
            break

    registro: dict[str, Any] = {
        "endereco_informado": endereco,
        "tentativas": etapa_usada + 1 if melhor else len(tentativas),
    }
    if melhor is None:
        return {**registro, "status": "sem_resultado"}

    fonte = (
        "endereco" if etapa_usada == 0 else ("rua" if etapa_usada == 1 else "bairro")
    )
    if fonte == "bairro":
        status = "centroide_bairro"
    elif melhor["ambiguous"]:
        status = "ambigu"
    elif melhor["confianca"] < CONFIANCA_BAIXA:
        status = "baixa_confianca"
    else:
        status = "ok"

    return {
        **registro,
        **melhor,
        "fonte_coordenada": fonte,
        "status": status,
    }


def _route_delivery_count(route: Any) -> int:
    return sum(1 for point in route.points if point.kind == "delivery")


async def _simular_operacao(
    geocoder: NominatimGeocoder, scenario: dict[str, Any]
) -> dict[str, Any]:
    inicio = time.perf_counter()

    geocodes = [
        {"papel": "deposito", **await _geocodificar(geocoder, scenario["deposito"])}
    ]
    for indice, entrega in enumerate(scenario["entregas"]):
        geocodes.append(
            {
                "papel": "entrega",
                "indice": indice + 1,
                **await _geocodificar(geocoder, entrega),
            }
        )

    deposito_geo = geocodes[0]
    atendidas = []
    nao_geocodificadas = []
    for indice, (entrega, geo) in enumerate(
        zip(scenario["entregas"], geocodes[1:], strict=True), start=1
    ):
        if geo["status"] == "sem_resultado":
            nao_geocodificadas.append(geo["endereco_informado"])
            continue
        atendidas.append({"indice": indice, "entrega": entrega, "geo": geo})

    resultado: dict[str, Any] = {
        "nome": scenario["nome"],
        "deposito": _endereco_display(scenario["deposito"]),
        "veiculos": scenario["veiculos"],
        "entregas_total": len(scenario["entregas"]),
        "entregas_com_janela": sum(
            1 for e in scenario["entregas"] if "time_window" in e
        ),
        "geocodes": geocodes,
        "entregas_nao_geocodificadas": nao_geocodificadas,
    }

    if deposito_geo["status"] == "sem_resultado" or not atendidas:
        resultado["erro"] = "Depósito ou todas as entregas sem coordenadas"
        return resultado

    problem_dict: dict[str, Any] = {
        "operating_hours": OPERATING_HOURS,
        "depot": {
            "id": 0,
            "location": {
                "latitude": deposito_geo["latitude"],
                "longitude": deposito_geo["longitude"],
            },
        },
        "vehicles": [
            {"id": veiculo["id"], "capacity": veiculo["capacity"]}
            for veiculo in scenario["veiculos"]
        ],
        "deliveries": [
            {
                "id": item["indice"],
                "demand": item["entrega"]["demanda"],
                "location": {
                    "latitude": item["geo"]["latitude"],
                    "longitude": item["geo"]["longitude"],
                },
                **(
                    {"time_window": item["entrega"]["time_window"]}
                    if "time_window" in item["entrega"]
                    else {}
                ),
            }
            for item in atendidas
        ],
    }

    locations = [
        (deposito_geo["latitude"], deposito_geo["longitude"]),
        *[(item["geo"]["latitude"], item["geo"]["longitude"]) for item in atendidas],
    ]
    distance_matrix, duration_matrix = _build_matrices(locations)

    solve_inicio = time.perf_counter()
    try:
        problem = validate_problem(problem_dict)
        solve = solve_routes(
            problem,
            distance_matrix,
            duration_matrix,
            time_limit_seconds=SOLVER_TIME_LIMIT_S,
        )
    except ValidationError as exc:
        resultado["erro"] = str(exc)
        resultado["erros_validacao"] = exc.errors
        resultado["tempo_planejamento_ms"] = round(
            (time.perf_counter() - solve_inicio) * 1000
        )
        resultado["tempo_total_simulacao_s"] = round(time.perf_counter() - inicio, 1)
        return resultado
    solve_ms = round((time.perf_counter() - solve_inicio) * 1000)

    resultado["status_solver"] = solve.status.value
    resultado["tempo_planejamento_ms"] = solve_ms
    resultado["tempo_total_simulacao_s"] = round(time.perf_counter() - inicio, 1)

    if solve.status is SolverStatus.SOLUTION_FOUND and solve.routes is not None:
        distancia_otimizada_m = solve.total_distance_meters or 0
        baseline_m = _sequential_distance_m(distance_matrix)
        resultado["paradas"] = sum(_route_delivery_count(r) for r in solve.routes)
        resultado["distancia_otimizada_km"] = round(distancia_otimizada_m / 1000, 1)
        resultado["distancia_ordem_registro_km"] = round(baseline_m / 1000, 1)
        resultado["tempo_total_min"] = sum(
            route.return_minute - route.departure_minute for route in solve.routes
        )
        resultado["rotas"] = [
            {
                "veiculo_id": route.vehicle_id,
                "paradas_entrega": _route_delivery_count(route),
                "sequencia": [point.id for point in route.points],
                "distancia_km": round(route.distance_meters / 1000, 1),
                "partida_min": route.departure_minute,
                "retorno_min": route.return_minute,
            }
            for route in solve.routes
            if _route_delivery_count(route) > 0
        ]
        if baseline_m > 0:
            resultado["reducao_distancia_pct"] = round(
                (1 - distancia_otimizada_m / baseline_m) * 100, 1
            )

    return resultado


async def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    geocoder = NominatimGeocoder()
    cenarios = []
    try:
        for scenario in SCENARIOS:
            print(f"Simulando: {scenario['nome']}...")
            cenarios.append(await _simular_operacao(geocoder, scenario))
    finally:
        await geocoder.close()

    problemas_geo = [
        {
            "operacao": cenario["nome"],
            "endereco": geo["endereco_informado"],
            "status": geo["status"],
            "query_usada": geo.get("query"),
            "candidatos": geo.get("candidatos", 0),
            "confianca": geo.get("confianca", 0.0),
        }
        for cenario in cenarios
        for geo in cenario["geocodes"]
        if geo["status"] != "ok"
    ]

    resultado = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "cidade": CIDADE,
        "tipo": "simulacao",
        "expediente": OPERATING_HOURS,
        "tempo_servico_min": DELIVERY_SERVICE_DURATION_MINUTES,
        "cenarios": cenarios,
        "problemas_geocodificacao": problemas_geo,
    }
    RESULTADO_JSON.write_text(
        json.dumps(resultado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"\nResultado gravado em {RESULTADO_JSON}\n")
    print(
        "| Operação | Paradas | Otimizada (km) | Ordem de registro (km) "
        "| Variação | Solver (ms) |"
    )
    print("| --- | --- | --- | --- | --- | --- |")
    for cenario in cenarios:
        variacao = (
            f"{cenario['reducao_distancia_pct']}%"
            if "reducao_distancia_pct" in cenario
            else "-"
        )
        print(
            f"| {cenario['nome']} | {cenario.get('paradas', '-')} "
            f"| {cenario.get('distancia_otimizada_km', '-')} "
            f"| {cenario.get('distancia_ordem_registro_km', '-')} "
            f"| {variacao} | {cenario.get('tempo_planejamento_ms', '-')} |"
        )
    print(f"\nProblemas de geocodificação: {len(problemas_geo)}")
    for problema in problemas_geo:
        print(
            f"- [{problema['status']}] {problema['endereco']} ({problema['operacao']})"
        )


if __name__ == "__main__":
    asyncio.run(main())
