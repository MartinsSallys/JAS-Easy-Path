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
poetry check --lock           # confere metadados e sincronização do lock
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
fixado em `poetry.lock`. Ele minimiza a distância total em metros; a matriz de
duração em minutos impõe as restrições temporais e não acrescenta outro objetivo.
Todas as entregas são obrigatórias e atendidas uma vez, as capacidades individuais
são respeitadas e todos os veículos começam e terminam no depósito. Veículos sem
entregas podem permanecer sem rota e retornam ao depósito sem percorrer distância.

A busca usa `PATH_CHEAPEST_ARC` para criar uma solução inicial e `GUIDED_LOCAL_SEARCH`
para buscar melhorias, com limite padrão de 1 segundo (`time_limit_seconds` pode ser
configurado em `solve_routes`). O limite curto atende o exemplo pequeno; não garante
otimalidade global. O resultado separa inviabilidade comprovada de busca encerrada
sem solução: somente `ROUTING_INFEASIBLE` é tratado como inviabilidade comprovada;
`ROUTING_FAIL` e `ROUTING_FAIL_TIMEOUT` indicam busca encerrada sem solução. Sem uma
atribuição, rotas e distância total vêm como `None`.

Na dimensão temporal, cada valor acumulado de uma entrega representa o início do
atendimento. Esse início precisa estar entre a abertura da janela efetiva e o horário
de fechamento menos 8 minutos. O tempo de um arco inclui a viagem e, quando sai de
uma entrega, também os 8 minutos de atendimento; do depósito, inclui somente a
viagem. A folga da dimensão permite espera suficiente ao longo do expediente. As
partidas e os retornos ficam entre a abertura e o fechamento do expediente.

O modelo usa os cumulativos e as folgas de uma dimensão de tempo do
[exemplo oficial de VRPTW](https://developers.google.com/optimization/routing/vrptw)
e da [documentação de dimensões](https://developers.google.com/optimization/routing/dimensions).

Depois de escolher as rotas por distância, o exemplo reconstrói a programação
concreta a partir da abertura do expediente. Cada veículo parte nesse horário e cada
entrega começa no primeiro instante compatível com a viagem e sua janela; uma chegada
antecipada gera espera antes do atendimento. Essa escolha apresenta um horário viável
e não altera o objetivo de distância. Os resultados incluem
`departure_minute` e `return_minute` por veículo e `service_start_minute` e
`service_end_minute` em cada ponto de entrega. Todos são minutos desde o início do dia
(`08:00` = 480); os campos de atendimento dos pontos do depósito são `null`. Início de
atendimento não é horário de chegada física: o veículo pode chegar antes e esperar.
`solution_found` significa que foi encontrada uma solução viável, não que ela seja
ótima.

O motor ainda não geocodifica endereços nem calcula distâncias ou durações reais de
trânsito. O horizonte é um único dia, não há pausas, e a duração de atendimento é
fixa em 8 minutos.

## Contrato de expediente e janelas

O payload exige `operating_hours` com `start` e `end`. Cada entrega pode informar
`time_window`; se a chave for omitida ou tiver valor `null`, a entrega herda o
expediente. Uma janela explícita deve conter os dois limites.

```json
{
  "operating_hours": {"start": "08:00", "end": "18:00"},
  "depot": {
    "id": 0,
    "location": {
      "address": "Depósito, Parnaíba - PI",
      "latitude": -2.905,
      "longitude": -41.776
    }
  },
  "vehicles": [
    {"id": 152, "capacity": 10},
    {"id": 153, "capacity": 15}
  ],
  "deliveries": [
    {
      "id": 101,
      "demand": 4,
      "location": {
        "address": "Rua das Flores, Parnaíba - PI",
        "latitude": -2.910,
        "longitude": -41.780
      },
      "time_window": {"start": "09:00", "end": "12:00"}
    },
    {
      "id": 102,
      "demand": 3,
      "location": {
        "address": "Av. São Sebastião, Parnaíba - PI",
        "latitude": -2.920,
        "longitude": -41.790
      }
    }
  ]
}
```

Os horários usam `HH:MM`, com zero à esquerda e sem segundos. São convertidos em
minutos desde o início do dia (`08:00` = 480). `24:00` é aceito somente como limite
final e representa 1440 minutos; não pode ser início. Intervalos iguais, invertidos
ou que atravessam a meia-noite são rejeitados.

A janela efetiva é a interseção com o expediente. Por exemplo, expediente
`08:00–18:00` e janela solicitada `17:00–20:00` resultam em `17:00–18:00`. Janelas
sem interseção ou com menos de 8 minutos efetivos são rejeitadas; exatamente 8
minutos é válido. Cada atendimento dura 8 minutos, valor interno e não configurável
no payload. Produtos são considerados disponíveis e conferidos no início da
operação. A validação de entrada confere o contrato; a viabilidade da sequência é
verificada pelo solver temporal.

`Delivery.time_window` armazena somente a janela efetiva em minutos; a janela original
solicitada não é preservada nesse modelo. Um futuro cadastro que precise exibir ou
editar o valor original deverá armazená-lo separadamente.

### Migração de payloads existentes

Payloads sem expediente agora são rejeitados. Informe `operating_hours` em cada
problema existente; não há expediente padrão. Janelas por entrega continuam
opcionais, então omiti-las mantém o comportamento de herdar o expediente:

```json
{
  "operating_hours": {"start": "08:00", "end": "18:00"}
}
```

O solver aplica as janelas efetivas, o atendimento fixo de 8 minutos, a espera por
abertura, as partidas e os retornos dentro do expediente. A operação não atravessa a
meia-noite. Os produtos são considerados disponíveis e conferidos na abertura; não há
tempo de carga no depósito.

Após alterar restrições de dependências no `pyproject.toml`, atualize o lock com
`poetry lock` e revise as mudanças antes de instalá-las.

## Exemplo manual de distâncias e durações

O cenário em `route_engine/route_engine/examples/manual_distance_scenario.py`
fornece um `Problem`
validado, uma matriz de distâncias em metros e uma matriz de durações em minutos. As
duas usam a ordem `[depósito, *problem.deliveries]`: índice `0` representa o depósito
e índice `i + 1` representa `problem.deliveries[i]`, sem usar IDs como índices. Ambas
são manuais. As durações são dados sintéticos fornecidos para o experimento; não são
calculadas a partir dos metros nem representam trânsito real. As coordenadas também
são sintéticas e não alimentam as matrizes. Cada matriz deve ser quadrada, conter
inteiros não negativos e ter diagonal zero; assimetria e valores zero fora da diagonal
são permitidos. Booleanos não são aceitos como inteiros.

`solve_routes` exige as duas matrizes explicitamente:
`solve_routes(problem, distance_matrix, duration_matrix)`. O motor não infere minutos
a partir dos metros.

```text
Matriz de duração (minutos):
[
    [0, 10, 12, 10, 12],
    [10, 0,  4, 20, 22],
    [12, 4,  0, 22, 24],
    [10, 20, 22, 0,  4],
    [12, 22, 24, 4,  0],
]
```

Uma execução real do exemplo com OR-Tools encontrou esta solução:

| Veículo | Entregas na ordem | Carga | Distância | Partida | Atendimentos (início–fim, minuto do dia) | Retorno |
| --- | --- | ---: | ---: | ---: | --- | ---: |
| 152 | 101, 102 | 8 | 2.600 m | 480 (08:00) | 101: 490–498; 102: 502–510 | 522 (08:42) |
| 153 | 103, 104 | 6 | 2.600 m | 480 (08:00) | 103: 490–498; 104: 502–510 | 522 (08:42) |

Distância total: 5.200 metros. O horário de atendimento representa quando o serviço
começa e termina, não a chegada física. A sequência e os horários vêm do resultado
do solver; não são uma garantia de optimalidade global.

Para executar os testes dos validadores das duas matrizes:

```bash
poetry run pytest -q route_engine/tests/test_distance_matrix.py route_engine/tests/test_duration_matrix.py
```

Para executar o exemplo real com OR-Tools e imprimir o resultado estruturado:

```bash
poetry run python -m route_engine.examples.solve_manual_scenario
```

Os testes de integração temporal com OR-Tools também podem ser executados isoladamente:

```bash
poetry run pytest -q route_engine/tests/test_ortools_solver.py
```

### Experimento: reordenação por janela

O teste `test_delivery_windows_change_lowest_distance_feasible_route_order` compara
duas entregas com as mesmas matrizes, veículo, demandas e expediente. Com janelas
amplas, o solver escolhe depósito → A → B (300 m). Ao restringir B para 08:05–08:13,
essa sequência deixa de caber: A ocupa 08:05–08:13 e B só poderia começar às 08:18.
O solver então escolhe depósito → B → A (1.500 m), atendendo B das 08:05 às 08:13.
As durações são dados manuais sintéticos, independentes da matriz de distâncias. O
objetivo continua sendo minimizar a distância entre rotas que respeitam todas as
restrições.

Execute somente esse experimento com:

```bash
poetry run pytest -q route_engine/tests/test_ortools_solver.py -k delivery_windows_change_lowest_distance_feasible_route_order
```
