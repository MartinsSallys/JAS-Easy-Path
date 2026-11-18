# Ambiente Python do motor

O motor usa OR-Tools para resolver o CVRP com matriz de distâncias manual. Pytest,
Ruff e Taskipy são ferramentas de desenvolvimento.

## Preparar o ambiente

Use Python 3.14 e Poetry. Na raiz do repositório, crie o ambiente virtual dentro do
projeto e instale as versões fixadas no lock:

```bash
export POETRY_VIRTUALENVS_IN_PROJECT=true
poetry env use python3.14
poetry install --with dev
```

O ambiente local fica em `.venv/`, ignorado pelo Git. O Poetry não instala o motor
como pacote; instala apenas suas dependências.

## Comandos de desenvolvimento

Execute da raiz do repositório:

```bash
poetry run task lint          # Ruff no código Python do motor
poetry run task format        # aplica a formatação Ruff ao motor
poetry run task format-check  # verifica a formatação sem alterar arquivos
poetry run task test          # executa os testes descobertos em route_engine/tests
```

## Executar os testes Python

Depois de preparar o ambiente, rode os testes com:

```bash
poetry run pytest -q
```

O pytest descobre os arquivos `test_*.py` em `route_engine/tests/`. O atalho
`poetry run task test` executa o mesmo comando.

## Solver OR-Tools

O solver usa Google OR-Tools 9.15.6755, instalado como dependência de execução e
fixado em `poetry.lock`. Ele minimiza a distância total da matriz, atende todas as
entregas exatamente uma vez e aplica a capacidade individual de cada veículo. Todos
os veículos começam e terminam no depósito; um veículo sem entregas retorna ao mesmo
depósito sem percorrer distância.

A busca usa `PATH_CHEAPEST_ARC` para criar uma solução inicial e `GUIDED_LOCAL_SEARCH`
para buscar melhorias, com limite padrão de 1 segundo (`time_limit_seconds` pode ser
configurado em `solve_routes`). O limite curto atende o exemplo pequeno; não garante
otimalidade global. O resultado separa inviabilidade comprovada de busca encerrada
sem solução: somente `ROUTING_INFEASIBLE` é tratado como inviabilidade comprovada;
`ROUTING_FAIL` e `ROUTING_FAIL_TIMEOUT` indicam busca encerrada sem solução. Sem uma
atribuição, rotas e distância total vêm como `None`.

Janelas de entrega, duração de atendimento e limites de jornada ficam para uma etapa
posterior. O motor ainda não geocodifica endereços nem calcula distâncias rodoviárias.

Após alterar restrições de dependências no `pyproject.toml`, atualize o lock com
`poetry lock` e revise as mudanças antes de instalá-las.

## Exemplo manual da matriz de distâncias

O cenário reutilizável está em `route_engine/examples/manual_distance_scenario.py`.
Ele fornece um `Problem` validado e uma matriz manual em metros. A ordem dos pontos
é `[depósito, *problem.deliveries]`: índice `0` representa o depósito e índice
`i + 1` representa `problem.deliveries[i]`, sem usar IDs como índices. As
coordenadas são sintéticas; os valores da matriz não foram calculados a partir delas.
O teste de referência confere rotas e métricas inseridas manualmente; ele não
executa nem representa uma saída do solver.

Para executar os testes do cenário e do validador de matriz:

```bash
poetry run pytest -q route_engine/tests/test_distance_matrix.py
```

Para executar o exemplo real com OR-Tools e imprimir o resultado estruturado:

```bash
poetry run python -m route_engine.examples.solve_manual_scenario
```

Os testes de integração do solver também podem ser executados isoladamente:

```bash
poetry run pytest -q route_engine/tests/test_ortools_solver.py
```
